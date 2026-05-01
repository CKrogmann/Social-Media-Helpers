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

# Album names (created in Photos app and sync to iPhone)
ALBUMS = {
    "model_bts":          "Model - BTS",
    "model_editorial":    "Model - Editorial",
    "lifestyle_peaceful": "Lifestyle - Peaceful",
    "lifestyle_cute":     "Lifestyle - Cute",
    "business":           "Business - Startup",
    "skip":               None,
}

CONFIDENCE_THRESHOLD = 75   # skip if below this
ERROR_RATE_THRESHOLD = 0.20
BATCH_SIZE           = 200
BURST_WINDOW_SECS    = 3    # photos within this many seconds = same burst, keep only first

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
    }

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

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

def ensure_albums_exist():
    for album_name in [v for v in ALBUMS.values() if v]:
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

SYSTEM_PROMPT = """You are sorting photos and videos for Celina Krogmann — a model and startup founder based in Miami.
Your job is to classify content for her social media. Only sort content that clearly fits a category; otherwise skip.

IMPORTANT RULES:
- Focus on content that includes Celina herself. If she is not visible and the photo does not clearly serve one of her content categories, classify as skip.
- For burst/similar shots, only the best one will be shown to you — classify it normally.

Categories:

model_bts: Behind-the-scenes on a model set. Shows a photography/video set environment, lighting equipment, crew, Celina getting hair/makeup done, candid work selfies, walking on set, short video clips from a shoot. Does NOT need to be a polished image.

model_editorial: Final, polished, professional model photos only. Must be razor sharp, high resolution, clearly from a professional shoot with intentional lighting and styling. Think catalog, lookbook, or magazine quality. If there is any doubt about quality or polish, do NOT use this category.

lifestyle_peaceful: Calm, aesthetic moments. Nature, sunsets, ocean, coffee, journaling, reading, travel scenery. Does NOT need to show Celina — the vibe and aesthetic matter. Skip if chaotic or unrelated.

lifestyle_cute: Must show Celina. Selfies, mirror pics, photos taken by others of her, cute outfits, smiling, expressing her personality. Casual but flattering. If Celina is not clearly visible, classify as skip.

business: Must relate to Celina's startup Nevo or founder/professional life. Includes: working on a laptop, office setting (929 Alton Road Miami), business meetings, networking events, screenshots of business-related apps/content, Nevo branding. Skip if business context is unclear.

skip: Everything else — food, random objects, other people without Celina, blurry shots, screenshots of non-business content, unrelated scenes, duplicates.

Reply with ONLY the category key and a confidence score 0-100.
Format: CATEGORY|CONFIDENCE
Example: model_editorial|91

Only use a category if you are 75 or above in confidence. Otherwise reply: skip|confidence"""

def classify_photo(client, photo_path, is_video=False):
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
            system=SYSTEM_PROMPT,
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

        if category not in ALBUMS:
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

CATEGORY_KEYS = [k for k in ALBUMS.keys() if k != "skip"] + ["skip"]

def assisted_classify(photo):
    open_photo_in_preview(photo["path"])
    kind = "VIDEO" if photo["is_video"] else "photo"
    print(f"\n  {kind}: {photo['date'].strftime('%Y-%m-%d')} ({photo['filename']})")
    print("  Categories:")
    for i, key in enumerate(CATEGORY_KEYS, 1):
        label = ALBUMS.get(key) or "Skip (not relevant)"
        print(f"    {i}. {label}")
    print("    q. Quit for now")

    while True:
        choice = input("  Your choice (1-6 or q): ").strip().lower()
        if choice == "q":
            close_preview()
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(CATEGORY_KEYS):
                close_preview()
                return CATEGORY_KEYS[idx]
        except ValueError:
            pass
        print("  Invalid — enter a number 1-6 or q")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    TMP_DIR.mkdir(exist_ok=True)
    cfg    = load_config()
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

    ensure_albums_exist()

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
            category, confidence = classify_photo(client, photo["path"], photo["is_video"])
            album_label = ALBUMS.get(category) or "skip"
            flag = " ⚠️ low confidence" if confidence < CONFIDENCE_THRESHOLD else ""
            log(f"  {kind_label} → {album_label} ({confidence}%){flag}")
            cfg["auto_classified"] = cfg.get("auto_classified", 0) + 1
        else:
            category = assisted_classify(photo)
            if category is None:
                log("Paused by user.")
                break

        album_name = ALBUMS.get(category)
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
