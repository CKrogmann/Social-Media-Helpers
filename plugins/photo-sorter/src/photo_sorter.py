#!/usr/bin/env python3
"""
Photo Sorter
Auto-sorts iPhone/Mac Photos (and videos) into albums using Claude AI vision.
Runs every 2-3 days via cron. Falls back to assisted mode if error rate > 20%.
"""

import os, json, base64, subprocess, sys, time, sqlite3, glob, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic

# ── Config ────────────────────────────────────────────────────────────────────

API_KEY = os.getenv("ANTHROPIC_API_KEY")
PHOTOS_DB     = Path.home() / "Pictures/Photos Library.photoslibrary/database/Photos.sqlite"
ORIGINALS_DIR = Path.home() / "Pictures/Photos Library.photoslibrary/originals"
TMP_DIR       = Path.home() / ".photo_sorter_tmp"
CONFIG_FILE   = Path.home() / ".photo_sorter_config.json"
LOG_FILE      = Path.home() / "photo_sorter.log"

# Apple Core Data epoch: Jan 1 2001
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

CONFIDENCE_THRESHOLD = 75   # skip if below this
ERROR_RATE_THRESHOLD = 0.20
BATCH_SIZE           = 200
BURST_WINDOW_SECS    = 3    # photos within this many seconds = same burst, keep only first

# ALBUMS is loaded from config at runtime (see load_config / run_setup_wizard)
ALBUMS = {}

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ── Config helpers ────────────────────────────────────────────────────────────

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "processed_uuids": [],
        "corrections":     0,
        "auto_classified": 0,
        "last_run":        None,
        "mode":            "auto",
        "user_name":       "",
        "user_context":    "",
        "albums":          {},
        "general_rules":   "",
    }

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def run_setup_wizard(cfg):
    """Interactive first-run wizard — defines who the user is and what albums to create."""
    print("\n" + "="*55)
    print("  Photo Sorter — First-time Setup")
    print("="*55)
    print("This runs once. Answers are saved to ~/.photo_sorter_config.json\n")

    cfg["user_name"] = input("Your name (e.g. Sarah): ").strip()

    print("\nDescribe what this photo library is for.")
    print("Example: 'social media content for a lifestyle blogger based in NYC'")
    cfg["user_context"] = input("Context: ").strip()

    print("\nNow define your albums. For each album you'll give:")
    print("  1. The exact name as it appears in your Photos app")
    print("  2. Criteria: what should go there (content, people, vibe, location, etc.)\n")

    albums = {}
    idx = 1
    while True:
        print(f"Album {idx} (press Enter with no name to finish):")
        name = input(f"  Photos app album name: ").strip()
        if not name:
            if not albums:
                print("  You need at least one album. Try again.")
                continue
            break
        key = f"album_{idx}"
        criteria = input(f"  Sorting criteria for '{name}': ").strip()
        albums[key] = {"name": name, "criteria": criteria}
        idx += 1

    cfg["albums"] = albums

    print("\nAny general rules that apply to all photos?")
    print("Example: 'Only include photos where I am clearly visible. Skip blurry shots.'")
    cfg["general_rules"] = input("General rules (or press Enter to skip): ").strip()

    save_config(cfg)
    print("\n✓ Setup complete. Your albums have been saved.")
    print("  Make sure these album names exist in your Photos app before running.\n")
    return cfg

def build_albums_dict(cfg):
    """Build the runtime ALBUMS dict from config."""
    albums = {}
    for key, val in cfg.get("albums", {}).items():
        albums[key] = val["name"]
    albums["skip"] = None
    return albums

def build_system_prompt(cfg):
    """Generate the Claude system prompt from user config."""
    name    = cfg.get("user_name", "the user")
    context = cfg.get("user_context", "personal use")
    rules   = cfg.get("general_rules", "")

    lines = [
        f"You are sorting photos and videos for {name} — {context}.",
        "Your job is to classify each photo into one of the defined albums. Only sort content that clearly fits; otherwise skip.",
        "",
        "IMPORTANT RULES:",
        "- For burst/similar shots, only the best one will be shown — classify it normally.",
    ]
    if rules:
        lines.append(f"- {rules}")

    lines += ["", "Albums and their criteria:", ""]
    for key, val in cfg.get("albums", {}).items():
        lines.append(f"{key}: {val['criteria']}")

    lines += [
        "",
        "skip: Everything that does not clearly fit one of the above albums.",
        "",
        "Reply with ONLY the album key and a confidence score 0-100.",
        "Format: ALBUM_KEY|CONFIDENCE",
        "Example: album_1|91",
        "",
        "Only use a category if you are 75 or above in confidence. Otherwise reply: skip|confidence",
    ]
    return "\n".join(lines)

# ── Photos library (SQLite) ───────────────────────────────────────────────────

def apple_date_to_utc(apple_ts):
    return APPLE_EPOCH + timedelta(seconds=apple_ts)

def find_original_path(uuid, filename, is_video=False):
    """Find the actual file in the originals folder."""
    first = uuid[0].upper()
    exact = ORIGINALS_DIR / first / filename
    if exact.exists():
        return exact
    matches = glob.glob(str(ORIGINALS_DIR / first / f"{uuid}.*"))
    if is_video:
        # For videos prefer .mov/.mp4, exclude _3.mov sidecars
        videos = [m for m in matches if m.lower().endswith(('.mov', '.mp4', '.m4v'))
                  and '_3.' not in m]
        return Path(videos[0]) if videos else None
    else:
        photos = [m for m in matches if not m.lower().endswith('.mov')]
        return Path(photos[0]) if photos else None

def deduplicate(rows):
    """
    Remove burst duplicates: keep only the first photo/video per BURST_WINDOW_SECS group.
    rows is a list of (uuid, filename, date_ts, is_video) sorted by date_ts ASC.
    """
    result = []
    last_ts = None
    for uuid, filename, date_ts, is_video in rows:
        if last_ts is None or (date_ts - last_ts) > BURST_WINDOW_SECS:
            result.append((uuid, filename, date_ts, is_video))
            last_ts = date_ts
        # else: same burst, skip duplicate
    return result

def get_photos_to_sort(since_dt, processed_uuids):
    """Query Photos SQLite for unprocessed photos and videos in the date range."""
    since_apple = (since_dt - APPLE_EPOCH).total_seconds()
    conn = sqlite3.connect(str(PHOTOS_DB))
    # ZKIND=0 photos, ZKIND=1 videos
    rows = conn.execute("""
        SELECT ZUUID, ZFILENAME, ZDATECREATED, ZKIND
        FROM ZASSET
        WHERE ZTRASHEDSTATE = 0
          AND ZHIDDEN       = 0
          AND ZKIND         IN (0, 1)
          AND ZDATECREATED >= ?
        ORDER BY ZDATECREATED ASC
    """, (since_apple,)).fetchall()
    conn.close()

    # Filter already processed, then deduplicate bursts
    unprocessed = [(uuid, fn, ts, kind == 1)
                   for uuid, fn, ts, kind in rows
                   if uuid not in processed_uuids]
    deduped = deduplicate(unprocessed)

    result = []
    for uuid, filename, date_ts, is_video in deduped:
        path = find_original_path(uuid, filename, is_video)
        if path is None:
            continue   # not downloaded from iCloud yet
        result.append({
            "uuid":     uuid,
            "filename": filename,
            "date":     apple_date_to_utc(date_ts),
            "path":     path,
            "is_video": is_video,
        })
    return result

# ── Photos app (AppleScript) ──────────────────────────────────────────────────

def ensure_albums_exist(albums):
    for album_name in [v for v in albums.values() if v]:
        script = f'''
        tell application "Photos"
            if not (exists album "{album_name}") then
                make new album named "{album_name}"
            end if
        end tell
        '''
        subprocess.run(["osascript", "-e", script], capture_output=True)

def add_to_album(uuid, album_name):
    photos_id = f"{uuid}/L0/001"
    script = f'''
    tell application "Photos"
        set theItems to (media items whose id is "{photos_id}")
        if (count of theItems) > 0 then
            add theItems to album "{album_name}"
        end if
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.returncode == 0

def open_photo_in_preview(path):
    subprocess.Popen(["open", "-a", "Preview", str(path)])
    time.sleep(1.5)

def close_preview():
    subprocess.run(["osascript", "-e", 'tell application "Preview" to quit'], capture_output=True)

# ── Image / video prep ────────────────────────────────────────────────────────

def extract_video_frame(video_path):
    """Extract a JPEG frame from a video using qlmanage (built into macOS)."""
    out = TMP_DIR / (video_path.stem + "_frame.jpg")
    subprocess.run(
        ["qlmanage", "-t", "-s", "1024", "-o", str(TMP_DIR), str(video_path)],
        capture_output=True
    )
    # qlmanage outputs <filename>.png
    png = TMP_DIR / (video_path.name + ".png")
    if png.exists():
        subprocess.run(["sips", "-s", "format", "jpeg", str(png), "--out", str(out)],
                       capture_output=True)
        png.unlink(missing_ok=True)
        return out if out.exists() else None
    return None

def prepare_for_api(photo_path, is_video=False):
    """
    Return (jpeg_path, needs_cleanup).
    Videos → extract frame. HEIC → convert. Large files → resize.
    """
    if is_video:
        frame = extract_video_frame(photo_path)
        if frame and frame.exists():
            return frame, True
        return None, False

    suffix  = photo_path.suffix.lower()
    tmp     = TMP_DIR / (photo_path.stem + "_converted.jpg")

    if suffix in ('.heic', '.heif'):
        subprocess.run(
            ["sips", "-s", "format", "jpeg", str(photo_path), "--out", str(tmp)],
            capture_output=True
        )
        out_path = tmp
    else:
        out_path = photo_path

    # Resize if > 2 MB — base64 adds ~33%, keeping us well under the 5 MB API limit
    if out_path.stat().st_size > 2_097_152:
        resized = TMP_DIR / (photo_path.stem + "_resized.jpg")
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-Z", "1400", str(out_path), "--out", str(resized)],
            capture_output=True
        )
        if out_path == tmp:
            tmp.unlink(missing_ok=True)
        return resized, True

    return out_path, out_path != photo_path

# ── Claude AI classification ──────────────────────────────────────────────────

# SYSTEM_PROMPT is generated at runtime from user config via build_system_prompt()

def classify_photo(client, photo_path, system_prompt, is_video=False):
    jpeg_path, needs_cleanup = prepare_for_api(photo_path, is_video)
    if jpeg_path is None:
        return "skip", 0
    try:
        with open(jpeg_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        suffix = jpeg_path.suffix.lower()
        media_type_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                          ".png": "image/png", ".gif": "image/gif",
                          ".webp": "image/webp"}
        media_type = media_type_map.get(suffix, "image/jpeg")

        label = "video frame" if is_video else "photo"
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": [{
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": image_data},
                }, {
                    "type": "text",
                    "text": f"Classify this {label}."
                }]
            }]
        )

        raw        = response.content[0].text.strip().splitlines()[0]
        parts      = raw.split("|")
        category   = parts[0].strip().lower()
        conf_str   = parts[1].strip() if len(parts) > 1 else "50"
        confidence = int(''.join(c for c in conf_str if c.isdigit())[:3] or "50")

        if category not in system_prompt:  # rough check; full validation in main
            return "skip", 0

        # Enforce confidence threshold — low confidence = skip
        if confidence < CONFIDENCE_THRESHOLD and category != "skip":
            return "skip", confidence

        return category, confidence

    except Exception as e:
        log(f"  Classification error: {e}")
        return "skip", 0
    finally:
        if needs_cleanup and jpeg_path and jpeg_path.exists():
            jpeg_path.unlink()

# ── Assisted mode ─────────────────────────────────────────────────────────────

def assisted_classify(photo, albums):
    category_keys = [k for k in albums.keys() if k != "skip"] + ["skip"]
    open_photo_in_preview(photo["path"])
    kind = "VIDEO" if photo["is_video"] else "photo"
    print(f"\n  {kind}: {photo['date'].strftime('%Y-%m-%d')} ({photo['filename']})")
    print("  Categories:")
    for i, key in enumerate(category_keys, 1):
        label = albums.get(key) or "Skip (not relevant)"
        print(f"    {i}. {label}")
    print("    q. Quit for now")

    n = len(category_keys)
    while True:
        choice = input(f"  Your choice (1-{n} or q): ").strip().lower()
        if choice == "q":
            close_preview()
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < n:
                close_preview()
                return category_keys[idx]
        except ValueError:
            pass
        print(f"  Invalid — enter a number 1-{n} or q")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    TMP_DIR.mkdir(exist_ok=True)
    cfg = load_config()

    # First-run setup wizard
    if not cfg.get("albums"):
        if not sys.stdin.isatty():
            print("ERROR: No albums configured. Run this script directly in a terminal first to complete setup.")
            print("  python3 photo_sorter.py")
            sys.exit(1)
        cfg = run_setup_wizard(cfg)

    albums        = build_albums_dict(cfg)
    system_prompt = build_system_prompt(cfg)

    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.")
        print("  export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=API_KEY)

    since = datetime.now(timezone.utc) - timedelta(days=30)
    log(f"Processing photos since {since.date()} (last 30 days)")

    log("Loading Photos library...")
    processed = set(cfg["processed_uuids"])
    photos    = get_photos_to_sort(since, processed)

    videos = sum(1 for p in photos if p["is_video"])
    log(f"Found {len(photos)} items to sort ({len(photos)-videos} photos, {videos} videos)\n")

    if not photos:
        log("Nothing to sort. Done.")
        cfg["last_run"] = datetime.now(timezone.utc).isoformat()
        save_config(cfg)
        return

    ensure_albums_exist(albums)

    mode = cfg.get("mode", "auto")
    if cfg["auto_classified"] > 0:
        error_rate = cfg["corrections"] / cfg["auto_classified"]
        if error_rate > ERROR_RATE_THRESHOLD:
            log(f"Error rate {error_rate:.0%} > {ERROR_RATE_THRESHOLD:.0%} — switching to assisted mode")
            mode = "assisted"

    log(f"Mode: {mode.upper()}\n")

    sorted_count = 0
    skipped      = 0
    batch        = 0
    last_photo_date = None

    for photo in photos:
        if batch >= BATCH_SIZE:
            log(f"\nBatch of {BATCH_SIZE} complete. Run again to continue.")
            break

        kind_label = "VIDEO" if photo["is_video"] else photo["date"].strftime("%Y-%m-%d")

        if mode == "auto":
            category, confidence = classify_photo(client, photo["path"], system_prompt, photo["is_video"])
            album_label = albums.get(category) or "skip"
            flag = " ⚠️ low confidence" if confidence < CONFIDENCE_THRESHOLD else ""
            log(f"  {kind_label} → {album_label} ({confidence}%){flag}")
            cfg["auto_classified"] = cfg.get("auto_classified", 0) + 1
        else:
            category = assisted_classify(photo, albums)
            if category is None:
                log("Paused by user.")
                break

        album_name = albums.get(category)
        if album_name:
            success = add_to_album(photo["uuid"], album_name)
            if success:
                sorted_count += 1
            else:
                log(f"  Warning: could not add {photo['uuid']} to album")
        else:
            skipped += 1

        processed.add(photo["uuid"])
        cfg["processed_uuids"] = list(processed)
        last_photo_date = photo["date"]
        batch += 1

        if batch % 10 == 0:
            save_config(cfg)

    log(f"\n{'='*45}")
    log(f"Sorted: {sorted_count}  |  Skipped: {skipped}  |  Mode: {mode}")
    log(f"Albums updated in Photos app — syncing to iPhone via iCloud")
    log(f"{'='*45}\n")

    # Advance last_run to the last photo's date (not today) so next batch continues from there
    if last_photo_date:
        cfg["last_run"] = last_photo_date.isoformat()
    else:
        cfg["last_run"] = datetime.now(timezone.utc).isoformat()
    save_config(cfg)

if __name__ == "__main__":
    main()
