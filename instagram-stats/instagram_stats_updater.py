#!/usr/bin/env python3
"""
Instagram Stats Updater v3
- Newest posts at top, oldest at bottom
- Rolling 90-day stats refresh on every run
- Preserves ALL manually-entered fields
- No duplicate rows
- Falls back to existing stats for posts outside 90-day window
- Creates Excel file on first run with proper structure
"""

import json, os, requests, openpyxl, sys
from datetime import datetime, timezone, timedelta

CONFIG_FILE = os.path.expanduser("~/.instagram_stats_config.json")
BASE_URL    = "https://graph.facebook.com/v25.0"
FORMAT_MAP  = {"IMAGE": "Static", "CAROUSEL_ALBUM": "Carousel", "VIDEO": "Reel"}

POST_HEADERS = [
    "Post Date", "Content Pillar", "Asset", "Format", "Views",
    "Reach", "Avg Reach", "Views/Reach", "Interactions", "Interaction Rate",
    "Likes", "Saves", "Shares", "Profile Visits", "Follows", "Follow Rate",
    "% Men", "% Women", "", "Score"
]
REEL_HEADERS = [
    "Post Date", "Content Pillar", "Series", "Asset", "Hook",
    "Views", "Reach", "Avg Reach", "Views/Reach", "Interactions", "Interaction Rate",
    "Likes", "Saves", "Shares", "Follows", "Follow Rate",
    "% Men", "% Women", "", "Score"
]

# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    cfg = {
        "access_token":  "",
        "ig_user_id":    "",
        "app_id":        os.getenv("INSTAGRAM_APP_ID", ""),
        "app_secret":    os.getenv("INSTAGRAM_APP_SECRET", ""),
        "token_expires": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
        "last_run":      None,
        "excel_path":    "",
    }
    save_config(cfg)
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ── First-run setup ───────────────────────────────────────────────────────────

def fetch_ig_user_id(token):
    """Fetch Instagram user ID automatically from the Graph API."""
    r = requests.get(f"{BASE_URL}/me", params={"fields": "id,name", "access_token": token}).json()
    if "id" in r:
        return r["id"], r.get("name", "")
    return None, None

def create_excel_file(path, year):
    """Create a new Excel workbook with properly structured sheets and headers."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    ws_posts = wb.create_sheet(f"Instagram Posts {year}")
    ws_posts.append(POST_HEADERS)

    ws_reels = wb.create_sheet(f"Instagram Reels {year}")
    ws_reels.append(REEL_HEADERS)

    wb.save(path)
    print(f"  Created new Excel file: {path}")

def run_setup_wizard(cfg):
    """Interactive first-run wizard — collects token, fetches user ID, sets Excel path."""
    print("\n" + "="*55)
    print("  Instagram Stats — First-time Setup")
    print("="*55 + "\n")

    # Step 1: Access token
    if not cfg.get("access_token"):
        print("Step 1 of 3 — Instagram Access Token")
        print("─" * 40)
        print("You need a long-lived access token from the Instagram Graph API.\n")
        print("How to get one (takes ~2 minutes):")
        print("  1. Go to developers.facebook.com")
        print("  2. Open your app → click 'Instagram' in the left menu")
        print("  3. Click 'Generate Access Token'")
        print("  4. Log in with your Instagram account when prompted")
        print("  5. Copy the long token that appears\n")
        token = input("Paste your access token here: ").strip()
        if not token:
            print("No token entered. Run the script again when you have your token.")
            sys.exit(1)
        cfg["access_token"] = token
        cfg["token_expires"] = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()

    # Step 2: Instagram User ID — fetched automatically from the token
    if not cfg.get("ig_user_id"):
        print("\nStep 2 of 3 — Connecting to your Instagram account...")
        ig_id, ig_name = fetch_ig_user_id(cfg["access_token"])
        if ig_id:
            cfg["ig_user_id"] = ig_id
            print(f"  ✓ Connected as: {ig_name} (User ID: {ig_id})")
        else:
            print("  Could not fetch your user ID — your token may be invalid or expired.")
            print("  Find it manually: Graph API Explorer → me?fields=id,name")
            ig_id = input("  Enter your Instagram User ID: ").strip()
            if not ig_id:
                print("User ID is required. Exiting.")
                sys.exit(1)
            cfg["ig_user_id"] = ig_id

    # Step 3: Excel file path
    if not cfg.get("excel_path"):
        year = datetime.now().year
        default_path = os.path.expanduser(f"~/Instagram Stats {year}.xlsx")
        print(f"\nStep 3 of 3 — Stats Spreadsheet")
        print("─" * 40)
        print(f"I'll create a new Excel file to store your stats.")
        print(f"Default location: {default_path}")
        path_input = input("Full path (or press Enter for default): ").strip()
        excel_path = path_input if path_input else default_path

        if os.path.exists(excel_path):
            print(f"  Found existing file: {excel_path}")
        else:
            create_excel_file(excel_path, year)

        cfg["excel_path"] = excel_path

    save_config(cfg)
    print("\n✓ Setup complete! Running your stats now...\n")
    return cfg

# ── Token ─────────────────────────────────────────────────────────────────────

def maybe_refresh_token(cfg):
    expires   = datetime.fromisoformat(cfg["token_expires"])
    days_left = (expires - datetime.now(timezone.utc)).days
    if days_left > 10:
        return cfg
    print(f"Token expires in {days_left}d — refreshing...")
    r = requests.get(f"{BASE_URL}/refresh_access_token", params={
        "grant_type":   "ig_refresh_token",
        "access_token": cfg["access_token"],
    }).json()
    if "access_token" in r:
        cfg["access_token"]  = r["access_token"]
        cfg["token_expires"] = (datetime.now(timezone.utc) + timedelta(seconds=r.get("expires_in", 5184000))).isoformat()
        save_config(cfg)
        print("  Token refreshed.")
    else:
        print(f"  WARNING: Could not refresh — {r.get('error',{}).get('message')}")
        print("  Generate a new token at developers.facebook.com → your app → Instagram → Generate Token")
        print("  Then update 'access_token' in ~/.instagram_stats_config.json")
    return cfg

# ── Instagram API ─────────────────────────────────────────────────────────────

def fetch_all_media(ig_id, token):
    items, url = [], f"{BASE_URL}/{ig_id}/media"
    params = {
        "fields":       "id,timestamp,media_type,like_count,comments_count",
        "limit":        50,
        "access_token": token,
    }
    while url:
        r = requests.get(url, params=params).json()
        params = {}
        if "error" in r:
            print(f"  API error: {r['error']['message']}")
            break
        items.extend(r.get("data", []))
        url = r.get("paging", {}).get("next")
    return items

def fetch_insights(media_id, media_type, token):
    metrics = "reach,saved,shares,views,total_interactions" if media_type == "VIDEO" \
              else "reach,saved,shares,profile_visits,follows,total_interactions"
    r = requests.get(f"{BASE_URL}/{media_id}/insights",
                     params={"metric": metrics, "access_token": token}).json()
    if "error" in r:
        return None  # pre-business post or unsupported
    return {d["name"]: d["values"][0]["value"] for d in r.get("data", [])}

# ── Excel helpers ─────────────────────────────────────────────────────────────

def read_rows(ws, n_cols=20):
    out = []
    for row in ws.iter_rows(min_row=2, max_col=n_cols, values_only=True):
        if any(v is not None for v in row):
            out.append(list(row) + [None] * (n_cols - len(row)))
    return out

def clear_data(ws):
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.value = None

def to_dt(ts_str):
    return datetime.fromisoformat(ts_str.replace("+0000", "+00:00"))

# ── Merge logic ───────────────────────────────────────────────────────────────

def build_pool(existing_rows, manual_col_indices):
    from collections import defaultdict
    pool = defaultdict(list)
    for row in existing_rows:
        d = row[0]
        if d is None:
            continue
        dt = d if isinstance(d, datetime) else None
        if dt is None:
            continue
        key = dt.date()
        pool[key].append({"row": row, "matched": False})
    return pool

def pop_match(pool, date_key):
    for entry in pool.get(date_key, []):
        if not entry["matched"]:
            entry["matched"] = True
            return entry["row"]
    return None

def merge_posts(existing_rows, media_list, insights):
    pool   = build_pool(existing_rows, manual_col_indices={1, 2, 3, 16})
    merged = []
    for m in media_list:
        if m["media_type"] == "VIDEO":
            continue
        ts  = to_dt(m["timestamp"])
        ins = insights.get(m["id"])
        ex  = pop_match(pool, ts.date()) or [None] * 20

        def api_or_existing(api_val, ex_col):
            return api_val if api_val is not None else ex[ex_col]

        merged.append({
            "date":           ts.replace(tzinfo=None),
            "content_pillar": ex[1],
            "asset":          ex[2],
            "format":         ex[3] or FORMAT_MAP.get(m["media_type"], ""),
            "views":          ex[4],
            "reach":          api_or_existing(ins.get("reach")              if ins else None, 5),
            "interactions":   api_or_existing(ins.get("total_interactions") if ins else None, 8),
            "likes":          m.get("like_count") or ex[10],
            "saves":          api_or_existing(ins.get("saved")              if ins else None, 11),
            "shares":         api_or_existing(ins.get("shares")             if ins else None, 12),
            "profile_visits": api_or_existing(ins.get("profile_visits")     if ins else None, 13),
            "follows":        api_or_existing(ins.get("follows")            if ins else None, 14),
            "men_share":      ex[16],
        })

    for entries in pool.values():
        for entry in entries:
            if not entry["matched"] and entry["row"][1] is not None:
                ex = entry["row"]
                d  = ex[0]
                merged.append({
                    "date":           d if isinstance(d, datetime) else None,
                    "content_pillar": ex[1],
                    "asset":          ex[2],
                    "format":         ex[3],
                    "views":          ex[4],
                    "reach":          ex[5],
                    "interactions":   ex[8],
                    "likes":          ex[10],
                    "saves":          ex[11],
                    "shares":         ex[12],
                    "profile_visits": ex[13],
                    "follows":        ex[14],
                    "men_share":      ex[16],
                })

    merged.sort(key=lambda x: x["date"] or datetime.min, reverse=True)
    return merged

def merge_reels(existing_rows, media_list, insights):
    pool   = build_pool(existing_rows, manual_col_indices={1, 2, 3, 4, 16})
    merged = []

    for m in media_list:
        if m["media_type"] != "VIDEO":
            continue
        ts  = to_dt(m["timestamp"])
        ins = insights.get(m["id"])
        ex  = pop_match(pool, ts.date()) or [None] * 20

        def api_or_existing(api_val, ex_col):
            return api_val if api_val is not None else ex[ex_col]

        merged.append({
            "date":           ts.replace(tzinfo=None),
            "content_pillar": ex[1],
            "series":         ex[2],
            "asset":          ex[3],
            "hook":           ex[4],
            "views":          api_or_existing(ins.get("views")              if ins else None, 5),
            "reach":          api_or_existing(ins.get("reach")              if ins else None, 6),
            "interactions":   api_or_existing(ins.get("total_interactions") if ins else None, 9),
            "likes":          m.get("like_count") or ex[11],
            "saves":          api_or_existing(ins.get("saved")              if ins else None, 12),
            "shares":         api_or_existing(ins.get("shares")             if ins else None, 13),
            "follows":        api_or_existing(ins.get("follows")            if ins else None, 14),
            "men_share":      ex[16],
        })

    for entries in pool.values():
        for entry in entries:
            if not entry["matched"] and entry["row"][1] is not None:
                ex = entry["row"]
                d  = ex[0]
                merged.append({
                    "date": d if isinstance(d, datetime) else None,
                    "content_pillar": ex[1], "series": ex[2],
                    "asset": ex[3], "hook": ex[4],
                    "views": ex[5], "reach": ex[6], "interactions": ex[9],
                    "likes": ex[11], "saves": ex[12], "shares": ex[13],
                    "follows": ex[14], "men_share": ex[16],
                })

    merged.sort(key=lambda x: x["date"] or datetime.min, reverse=True)
    return merged

# ── Write sheets ──────────────────────────────────────────────────────────────

def write_posts(ws, rows):
    clear_data(ws)
    for i, d in enumerate(rows):
        r = i + 2
        ws.cell(r,  1).value = d["date"]
        ws.cell(r,  2).value = d["content_pillar"]
        ws.cell(r,  3).value = d["asset"]
        ws.cell(r,  4).value = d["format"]
        ws.cell(r,  5).value = d["views"]
        ws.cell(r,  6).value = d["reach"]
        ws.cell(r,  7).value = "=AVERAGE(F:F)"
        ws.cell(r,  8).value = f"=E{r}/F{r}"
        ws.cell(r,  9).value = d["interactions"]
        ws.cell(r, 10).value = f"=I{r}/F{r}"
        ws.cell(r, 11).value = d["likes"]
        ws.cell(r, 12).value = d["saves"]
        ws.cell(r, 13).value = d["shares"]
        ws.cell(r, 14).value = d["profile_visits"]
        ws.cell(r, 15).value = d["follows"]
        ws.cell(r, 16).value = f"=O{r}/N{r}"
        ws.cell(r, 17).value = d["men_share"]
        ws.cell(r, 18).value = f"=1-Q{r}"
        ws.cell(r, 20).value = (
            f"=(30*MIN(E{r}/F{r},3)/3"
            f" + 20*MIN(I{r}/F{r},0.15)/0.15 * ((Q{r} + 2*R{r})/3)"
            f" + 50*IF(N{r}=0,0, MIN(O{r}/N{r},0.5)/0.5))"
            f"* (0.5 + (MIN(F{r}/G{r}, 2) / 2) * 0.7)"
        )
    print(f"  Posts: {len(rows)} rows written (newest first)")

def write_reels(ws, rows):
    clear_data(ws)
    for i, d in enumerate(rows):
        r = i + 2
        ws.cell(r,  1).value = d["date"]
        ws.cell(r,  2).value = d["content_pillar"]
        ws.cell(r,  3).value = d["series"]
        ws.cell(r,  4).value = d["asset"]
        ws.cell(r,  5).value = d["hook"]
        ws.cell(r,  6).value = d["views"]
        ws.cell(r,  7).value = d["reach"]
        ws.cell(r,  8).value = "=AVERAGE(G:G)"
        ws.cell(r,  9).value = f"=F{r}/G{r}"
        ws.cell(r, 10).value = d["interactions"]
        ws.cell(r, 11).value = f"=J{r}/G{r}"
        ws.cell(r, 12).value = d["likes"]
        ws.cell(r, 13).value = d["saves"]
        ws.cell(r, 14).value = d["shares"]
        ws.cell(r, 15).value = d["follows"]
        ws.cell(r, 16).value = f"=O{r}/G{r}"
        ws.cell(r, 17).value = d["men_share"]
        ws.cell(r, 18).value = f"=1-Q{r}"
        ws.cell(r, 20).value = (
            f"=IF(G{r}=0,0,"
            f"(30*MIN(F{r}/G{r},3)/3"
            f" + 20*MIN(J{r}/G{r},0.15)/0.15 * ((Q{r} + 2*R{r})/3)"
            f" + 50*MIN(O{r}/G{r},0.05)/0.05)"
            f"* (0.5 + (MIN(G{r}/H{r},2)/2) * 0.7))"
        )
    print(f"  Reels: {len(rows)} rows written (newest first)")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    cfg = load_config()

    # First-run setup if any required fields are missing
    needs_setup = (
        not cfg.get("access_token")
        or not cfg.get("ig_user_id")
        or not cfg.get("excel_path")
    )
    if needs_setup:
        if not sys.stdin.isatty():
            print("ERROR: First-time setup required. Run this script directly in a terminal:")
            print("  python3 instagram_stats_updater.py")
            sys.exit(1)
        cfg = run_setup_wizard(cfg)

    cfg        = maybe_refresh_token(cfg)
    token      = cfg["access_token"]
    ig_id      = cfg["ig_user_id"]
    excel_path = cfg["excel_path"]
    year       = datetime.now().year

    cutoff_90 = datetime.now(timezone.utc) - timedelta(days=90)
    last_run  = datetime.fromisoformat(cfg["last_run"]) if cfg.get("last_run") else None

    print(f"\n{'='*55}")
    print(f"Instagram Stats Updater v3  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"90-day refresh window:  posts since {cutoff_90.date()}")
    print(f"{'='*55}\n")

    # Recreate Excel if it was deleted or moved
    if not os.path.exists(excel_path):
        print(f"Excel file not found at {excel_path} — creating a fresh copy...")
        create_excel_file(excel_path, year)

    print("Fetching media list from Instagram...")
    all_media = fetch_all_media(ig_id, token)
    print(f"  {len(all_media)} total posts/reels found\n")

    print("Fetching insights (90-day rolling)...")
    insights = {}
    for m in all_media:
        ts = to_dt(m["timestamp"])
        if ts >= cutoff_90 or last_run is None:
            insights[m["id"]] = fetch_insights(m["id"], m["media_type"], token)
    print(f"  Fetched insights for {len(insights)} posts/reels\n")

    print("Reading existing Excel data...")
    wb          = openpyxl.load_workbook(excel_path)
    posts_sheet = f"Instagram Posts {year}"
    reels_sheet = f"Instagram Reels {year}"

    # Create sheets for the current year if they don't exist (new year rollover)
    if posts_sheet not in wb.sheetnames:
        ws = wb.create_sheet(posts_sheet)
        ws.append(POST_HEADERS)
    if reels_sheet not in wb.sheetnames:
        ws = wb.create_sheet(reels_sheet)
        ws.append(REEL_HEADERS)

    post_rows = read_rows(wb[posts_sheet])
    reel_rows = read_rows(wb[reels_sheet])
    print(f"  Found {len(post_rows)} existing post rows, {len(reel_rows)} reel rows\n")

    print("Merging and deduplicating...")
    merged_posts = merge_posts(post_rows, all_media, insights)
    merged_reels = merge_reels(reel_rows, all_media, insights)

    print("Writing updated sheets...")
    write_posts(wb[posts_sheet], merged_posts)
    write_reels(wb[reels_sheet], merged_reels)

    wb.save(excel_path)
    print(f"\nSaved  →  {excel_path}")

    cfg["last_run"] = datetime.now(timezone.utc).isoformat()
    save_config(cfg)
    print("Done!\n")

if __name__ == "__main__":
    main()
