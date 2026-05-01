#!/usr/bin/env python3
"""
Instagram Stats Updater v3
- Newest posts at top, oldest at bottom
- Rolling 90-day stats refresh on every run
- Preserves ALL manually-entered fields
- No duplicate rows
- Falls back to existing stats for posts outside 90-day window
"""

import json, os, requests, openpyxl
from datetime import datetime, timezone, timedelta

CONFIG_FILE = os.path.expanduser("~/.instagram_stats_config.json")
EXCEL_PATH  = os.path.expanduser("~/Celina Krogmann SM Planning.xlsx")
BASE_URL    = "https://graph.facebook.com/v25.0"
FORMAT_MAP  = {"IMAGE": "Static", "CAROUSEL_ALBUM": "Carousel", "VIDEO": "Reel"}

# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    cfg = {
        "access_token":  "",
        "ig_user_id":    "17841401302003364",
        "app_id":        os.getenv("INSTAGRAM_APP_ID", ""),
        "app_secret":    os.getenv("INSTAGRAM_APP_SECRET", ""),
        "token_expires": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
        "last_run":      None,
    }
    save_config(cfg)
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

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
        print("  Generate a new token at developers.facebook.com → Celina Stats → Instagram → Generate token")
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
    """Read all non-empty data rows as list of lists (skip header)."""
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
    """
    Build a pool of existing rows keyed by date.
    manual_col_indices: set of 0-based col indices considered 'manual'
    """
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
    """Return first unmatched pool entry for this date, or {}."""
    for entry in pool.get(date_key, []):
        if not entry["matched"]:
            entry["matched"] = True
            return entry["row"]
    return None

def merge_posts(existing_rows, media_list, insights):
    """
    Returns list of merged post dicts, newest first.
    Priority:
      - API stats used when fresh insights available (within 90d)
      - Existing stats used as fallback for older posts
      - Manual fields ALWAYS preserved from existing rows
      - Views column always preserved (API never provides it for posts)
    """
    pool = build_pool(existing_rows, manual_col_indices={1, 2, 3, 16})

    merged = []
    for m in media_list:
        if m["media_type"] == "VIDEO":
            continue
        ts      = to_dt(m["timestamp"])
        ins     = insights.get(m["id"])  # None = not fetched OR pre-business
        ex      = pop_match(pool, ts.date()) or [None] * 20

        # Stats: prefer fresh API, fall back to existing
        def api_or_existing(api_val, ex_col):
            return api_val if api_val is not None else ex[ex_col]

        merged.append({
            "date":           ts.replace(tzinfo=None),
            # Manual fields — always from existing row
            "content_pillar": ex[1],
            "asset":          ex[2],
            "format":         ex[3] or FORMAT_MAP.get(m["media_type"], ""),
            # Views — API never provides this for posts, always preserve existing
            "views":          ex[4],
            # API stats with fallback to existing
            "reach":          api_or_existing(ins.get("reach")              if ins else None, 5),
            "interactions":   api_or_existing(ins.get("total_interactions") if ins else None, 8),
            "likes":          m.get("like_count") or ex[10],
            "saves":          api_or_existing(ins.get("saved")              if ins else None, 11),
            "shares":         api_or_existing(ins.get("shares")             if ins else None, 12),
            "profile_visits": api_or_existing(ins.get("profile_visits")     if ins else None, 13),
            "follows":        api_or_existing(ins.get("follows")            if ins else None, 14),
            # Manual fields continued
            "men_share":      ex[16],
        })

    # Add truly manual-only rows (have Content Pillar but no API post matched)
    # These are rows the user added for posts not in the API (e.g. deleted posts)
    for entries in pool.values():
        for entry in entries:
            if not entry["matched"] and entry["row"][1] is not None:  # has Content Pillar
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
        ws.cell(r,  5).value = d["views"]           # preserved from manual entry
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
    cfg   = load_config()
    cfg   = maybe_refresh_token(cfg)
    token = cfg["access_token"]
    ig_id = cfg["ig_user_id"]

    cutoff_90 = datetime.now(timezone.utc) - timedelta(days=90)
    last_run  = datetime.fromisoformat(cfg["last_run"]) if cfg.get("last_run") else None

    print(f"\n{'='*55}")
    print(f"Instagram Stats Updater v3  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"90-day refresh window:  posts since {cutoff_90.date()}")
    print(f"{'='*55}\n")

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
    wb        = openpyxl.load_workbook(EXCEL_PATH)
    post_rows = read_rows(wb["Instagram Posts 2026"])
    reel_rows = read_rows(wb["Instagram Reels 2026"])
    print(f"  Found {len(post_rows)} existing post rows, {len(reel_rows)} reel rows\n")

    print("Merging and deduplicating...")
    merged_posts = merge_posts(post_rows, all_media, insights)
    merged_reels = merge_reels(reel_rows, all_media, insights)

    print("Writing updated sheets...")
    write_posts(wb["Instagram Posts 2026"], merged_posts)
    write_reels(wb["Instagram Reels 2026"], merged_reels)

    wb.save(EXCEL_PATH)
    print(f"\nSaved  →  {EXCEL_PATH}")

    cfg["last_run"] = datetime.now(timezone.utc).isoformat()
    save_config(cfg)
    print("Done!\n")

if __name__ == "__main__":
    main()
