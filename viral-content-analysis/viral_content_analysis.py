#!/usr/bin/env python3
"""
Viral Content Analysis
Tracks 10-15 public Instagram accounts, surfaces top-performing posts,
hooks, formats, and content types into a personal Notion workspace.
Runs manually on first use (180-day lookback), then monthly via cron (90-day).
"""

import os, json, base64, subprocess, sys, time, shutil, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic

# Resolve ffmpeg binary — prefer system, fall back to imageio_ffmpeg bundle
def _find_ffmpeg():
    import shutil
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

FFMPEG_BIN = _find_ffmpeg()


# ── Config ────────────────────────────────────────────────────────────────────

API_KEY = os.getenv("ANTHROPIC_API_KEY")
CONFIG_FILE = Path.home() / ".viral_content_config.json"
LOG_FILE    = Path.home() / "viral_content_analysis.log"
TMP_DIR     = Path.home() / ".viral_content_tmp"

NOTION_API  = "https://api.notion.com/v1"
NOTION_VER  = "2022-06-28"

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
    cfg = {
        "accounts":                [],
        "notion_token":            "",
        "notion_page_id":          "",
        "notion_viral_posts_db":   None,
        "notion_patterns_db":      None,
        "notion_niche_journey_db": None,
        "last_run":                None,
        "niche_journey_completed": [],
        "thresholds": {
            "reel_views": 1_000_000,
            "top_pct":    0.20,
        },
    }
    save_config(cfg)
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ── Setup ─────────────────────────────────────────────────────────────────────

def setup_tmp_dir():
    TMP_DIR.mkdir(exist_ok=True)

# ── Instagram scraping ────────────────────────────────────────────────────────

def scrape_recent_posts(account, loader, days):
    """Scrape posts from the last `days` days. Returns list of post dicts."""
    import instaloader
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    posts  = []
    try:
        profile = instaloader.Profile.from_username(loader.context, account)
        followers = profile.followers
        consecutive_old = 0
        for i, post in enumerate(profile.get_posts()):
            if i >= 500:   # hard cap per account
                break
            post_date = post.date_utc.replace(tzinfo=timezone.utc)
            if post_date < cutoff:
                consecutive_old += 1
                if consecutive_old >= 10 and i >= 5:
                    # 10 consecutive old posts after the first 5 = done
                    break
                continue   # skip (could be a pinned old post)
            consecutive_old = 0
            posts.append(_post_to_dict(post, followers))
    except instaloader.exceptions.ProfileNotExistsException:
        log(f"  [{account}] Profile not found — skipping")
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        log(f"  [{account}] Private profile — skipping")
    except instaloader.exceptions.TooManyRequestsException:
        log(f"  [{account}] Rate limited — sleeping 15 min then retrying once")
        time.sleep(900)
        try:
            profile = instaloader.Profile.from_username(loader.context, account)
            followers = profile.followers
            consecutive_old = 0
            for i, post in enumerate(profile.get_posts()):
                if i >= 500:
                    break
                post_date = post.date_utc.replace(tzinfo=timezone.utc)
                if post_date < cutoff:
                    consecutive_old += 1
                    if consecutive_old >= 10 and i >= 5:
                        break
                    continue
                consecutive_old = 0
                posts.append(_post_to_dict(post, followers))
        except Exception as e:
            log(f"  [{account}] Retry failed: {e} — skipping")
    except Exception as e:
        log(f"  [{account}] Error scraping: {e} — skipping")
    return posts

def scrape_oldest_posts(account, loader, limit=30):
    """Scrape up to `limit` oldest posts (for niche journey analysis)."""
    import instaloader
    collected = []
    try:
        profile = instaloader.Profile.from_username(loader.context, account)
        followers = profile.followers
        for post in profile.get_posts():
            collected.append(_post_to_dict(post, followers))
            if len(collected) >= 500:   # cap at 500 to avoid huge accounts
                break
    except Exception as e:
        log(f"  [{account}] Error scraping oldest posts: {e}")
    # posts come newest-first, so oldest are at the end
    return collected[-limit:] if collected else []

def _post_to_dict(post, followers):
    """Convert an instaloader Post to a plain dict."""
    typename = post.typename   # 'GraphImage', 'GraphSidecar', 'GraphVideo'
    fmt_map  = {
        "GraphImage":    "Single Photo",
        "GraphSidecar":  "Carousel",
        "GraphVideo":    "Reel",
    }
    return {
        "shortcode":  post.shortcode,
        "url":        f"https://www.instagram.com/p/{post.shortcode}/",
        "account":    post.owner_profile.username,
        "format":     fmt_map.get(typename, "Single Photo"),
        "date":       post.date_utc.replace(tzinfo=timezone.utc).isoformat(),
        "views":      max(post.video_view_count or 0, 0),
        "likes":      max(post.likes or 0, 0),
        "comments":   max(post.comments or 0, 0),
        "followers":  followers or 1,
        "caption":    post.caption or "",
        "thumbnail_url": getattr(post, "url", "") or "",
        "video_url":  post.video_url if typename == "GraphVideo" else None,
    }

# ── Media download helpers ────────────────────────────────────────────────────

def download_thumbnail(post_dict):
    """Download the thumbnail image for a post. Returns Path or None."""
    url = post_dict.get("thumbnail_url")
    if not url:
        return None
    dest = TMP_DIR / f"{post_dict['shortcode']}_thumb.jpg"
    if dest.exists():
        return dest
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return dest
    except Exception as e:
        log(f"    Thumbnail download failed ({post_dict['shortcode']}): {e}")
        return None

def download_reel_audio(post_dict):
    """Download Reel video and extract first 5s as .wav. Returns Path or None."""
    url = post_dict.get("video_url")
    if not url:
        return None
    video_path = TMP_DIR / f"{post_dict['shortcode']}.mp4"
    audio_path = TMP_DIR / f"{post_dict['shortcode']}_hook.wav"
    if audio_path.exists():
        return audio_path
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        video_path.write_bytes(r.content)
        if not FFMPEG_BIN:
            log(f"    ffmpeg not available — skipping audio for {post_dict['shortcode']}")
            return None
        result = subprocess.run(
            [FFMPEG_BIN, "-y", "-i", str(video_path),
             "-t", "5", "-ar", "16000", "-ac", "1",
             str(audio_path)],
            capture_output=True, timeout=30
        )
        video_path.unlink(missing_ok=True)
        return audio_path if audio_path.exists() else None
    except Exception as e:
        log(f"    Audio extract failed ({post_dict['shortcode']}): {e}")
        video_path.unlink(missing_ok=True)
        return None

# ── Filtering ─────────────────────────────────────────────────────────────────

def calculate_engagement_rate(post_dict):
    followers = max(post_dict.get("followers", 1), 1)
    eng = post_dict.get("likes", 0) + post_dict.get("comments", 0)
    return round(eng / followers * 100, 4)

def get_top_performers(posts, cfg):
    """
    Filter posts to top performers per format:
      - Reels: 1M+ views OR top 20% engagement
      - Carousels: top 20% engagement
      - Single Photos: top 20% engagement
    """
    thresholds = cfg.get("thresholds", {})
    reel_views_min = thresholds.get("reel_views", 1_000_000)
    top_pct        = thresholds.get("top_pct", 0.20)

    # Add engagement rate to each post
    for p in posts:
        p["engagement_rate"] = calculate_engagement_rate(p)

    # Group by format
    by_format = {"Reel": [], "Carousel": [], "Single Photo": []}
    for p in posts:
        fmt = p.get("format", "Single Photo")
        by_format.setdefault(fmt, []).append(p)

    result = []
    for fmt, group in by_format.items():
        if not group:
            continue
        sorted_group = sorted(group, key=lambda x: x["engagement_rate"], reverse=True)
        cutoff_idx   = max(1, int(len(sorted_group) * top_pct))
        top_eng      = set(id(p) for p in sorted_group[:cutoff_idx])

        for p in group:
            keep = False
            if fmt == "Reel" and p.get("views", 0) >= reel_views_min:
                keep = True
            if id(p) in top_eng:
                keep = True
            if keep:
                result.append(p)

    return result

# ── Per-post AI analysis ──────────────────────────────────────────────────────

def analyze_visual_hook(client, thumbnail_path):
    """Use Claude Haiku to detect text overlay on thumbnail. Returns dict."""
    fallback = {"has_text": False, "text": ""}
    if thumbnail_path is None or not thumbnail_path.exists():
        return fallback
    try:
        with open(thumbnail_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [{
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data},
                }, {
                    "type": "text",
                    "text": (
                        "Look at this Instagram post thumbnail. "
                        "Is there any text overlaid on the image (like a title, hook text, subtitle, or caption burned into the visual)? "
                        "Reply in this exact format:\n"
                        "HAS_TEXT: yes/no\n"
                        "TEXT: (the exact text you see, or empty if none)"
                    )
                }]
            }]
        )
        raw = response.content[0].text.strip()
        has_text = "has_text: yes" in raw.lower()
        text = ""
        for line in raw.splitlines():
            if line.upper().startswith("TEXT:"):
                text = line.split(":", 1)[1].strip()
                break
        return {"has_text": has_text, "text": text}
    except Exception as e:
        log(f"    Visual hook analysis error: {e}")
        return fallback

def analyze_audio_hook(whisper_model, audio_path):
    """Transcribe first 5s of audio with Whisper. Returns dict."""
    fallback = {"has_voiceover": False, "text": ""}
    if whisper_model is None or audio_path is None or not audio_path.exists():
        return fallback
    try:
        import numpy as np
        # Decode audio to raw float32 PCM via our bundled ffmpeg binary,
        # then pass the numpy array to Whisper — avoids Whisper's internal
        # 'ffmpeg' shell call which requires ffmpeg to be in system PATH.
        cmd = [FFMPEG_BIN, "-i", str(audio_path),
               "-ar", "16000", "-ac", "1", "-f", "f32le", "-"]
        proc = subprocess.run(cmd, capture_output=True, timeout=30)
        if proc.returncode != 0 or not proc.stdout:
            raise RuntimeError(f"ffmpeg decode failed: {proc.stderr[:200]}")
        audio_array = np.frombuffer(proc.stdout, dtype=np.float32)
        result = whisper_model.transcribe(audio_array, language="en", fp16=False)
        text = result.get("text", "").strip()
        return {"has_voiceover": bool(text), "text": text}
    except Exception as e:
        log(f"    Audio hook analysis error: {e}")
        return fallback

def classify_content_type(client, caption, visual_text):
    """Use Claude Haiku to classify content type. Returns label string."""
    fallback = "other"
    try:
        combined = f"Caption: {caption[:500]}\nVisual text overlay: {visual_text or 'none'}"
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{
                "role": "user",
                "content": (
                    "Classify this Instagram post into exactly one content type.\n"
                    "Options: educational / personal story / product / trend / BTS / humor / other\n"
                    "Reply with ONLY the label, nothing else.\n\n"
                    + combined
                )
            }]
        )
        label = response.content[0].text.strip().lower()
        valid = {"educational", "personal story", "product", "trend", "bts", "humor", "other"}
        return label if label in valid else "other"
    except Exception as e:
        log(f"    Content type classification error: {e}")
        return fallback

def analyze_post(client, whisper_model, post_dict):
    """Run full AI analysis on a single post. Returns enriched dict."""
    try:
        thumbnail_path = download_thumbnail(post_dict)

        visual = analyze_visual_hook(client, thumbnail_path)

        audio = {"has_voiceover": False, "text": ""}
        if post_dict.get("format") == "Reel" and whisper_model is not None:
            audio_path = download_reel_audio(post_dict)
            audio = analyze_audio_hook(whisper_model, audio_path)
            if audio_path and audio_path.exists():
                audio_path.unlink(missing_ok=True)

        caption       = post_dict.get("caption", "")
        caption_hook  = caption.splitlines()[0].strip() if caption else ""
        content_type  = classify_content_type(client, caption, visual["text"])

        # Clean up thumbnail
        if thumbnail_path and thumbnail_path.exists():
            thumbnail_path.unlink(missing_ok=True)

        return {
            **post_dict,
            "engagement_rate":        post_dict.get("engagement_rate", calculate_engagement_rate(post_dict)),
            "caption_hook":           caption_hook,
            "has_visual_text":        visual["has_text"],
            "visual_hook_text":       visual["text"],
            "has_voiceover":          audio["has_voiceover"],
            "audio_hook_text":        audio["text"],
            "content_type":           content_type,
        }
    except Exception as e:
        log(f"    analyze_post error ({post_dict.get('shortcode')}): {e}")
        return {
            **post_dict,
            "engagement_rate":  post_dict.get("engagement_rate", 0),
            "caption_hook":     "",
            "has_visual_text":  False,
            "visual_hook_text": "",
            "has_voiceover":    False,
            "audio_hook_text":  "",
            "content_type":     "other",
        }

# ── Notion helpers ────────────────────────────────────────────────────────────

def notion_headers(token):
    return {
        "Authorization":  f"Bearer {token}",
        "Content-Type":   "application/json",
        "Notion-Version": NOTION_VER,
    }

def create_database(token, page_id, title, schema):
    """Create a Notion database under page_id with given schema. Returns db_id."""
    payload = {
        "parent":     {"type": "page_id", "page_id": page_id},
        "title":      [{"type": "text", "text": {"content": title}}],
        "properties": schema,
    }
    r = requests.post(f"{NOTION_API}/databases", headers=notion_headers(token), json=payload)
    data = r.json()
    if not r.ok:
        raise RuntimeError(f"Failed to create database '{title}': {data}")
    log(f"  Created Notion DB: {title} ({data['id']})")
    return data["id"]

# Database schemas — Notion property format

VIRAL_POSTS_SCHEMA = {
    "Post URL":                {"title": {}},
    "Account":                 {"select": {}},
    "Format":                  {"select": {}},
    "Post Date":               {"date": {}},
    "Views":                   {"number": {"format": "number"}},
    "Likes":                   {"number": {"format": "number"}},
    "Comments":                {"number": {"format": "number"}},
    "Engagement Rate":         {"number": {"format": "percent"}},
    "Caption":                 {"rich_text": {}},
    "Caption Hook":            {"rich_text": {}},
    "Has Visual Text Overlay": {"checkbox": {}},
    "Visual Hook Text":        {"rich_text": {}},
    "Has Voiceover":           {"checkbox": {}},
    "Audio Hook Text":         {"rich_text": {}},
    "Content Type":            {"select": {}},
    "Post ID":                 {"rich_text": {}},
}

PATTERNS_SCHEMA = {
    "Pattern Name":  {"title": {}},
    "Pattern Type":  {"select": {}},
    "Description":   {"rich_text": {}},
    "Accounts":      {"rich_text": {}},
    "Account Count": {"number": {"format": "number"}},
    "Frequency":     {"rich_text": {}},
    "Analysis Date": {"date": {}},
}

NICHE_JOURNEY_SCHEMA = {
    "Account":                  {"title": {}},
    "Start Date":               {"date": {}},
    "Current Niche":            {"rich_text": {}},
    "Journey Summary":          {"rich_text": {}},
    "Had Clear Niche From Start": {"checkbox": {}},
    "Shift Date Estimate":      {"rich_text": {}},
    "Posts Analyzed":           {"number": {"format": "number"}},
    "Analysis Date":            {"date": {}},
}

def ensure_databases_exist(cfg):
    """Create all 3 Notion databases on first run; skip if already exist."""
    token   = cfg["notion_token"]
    page_id = cfg["notion_page_id"]
    changed = False

    if not cfg.get("notion_viral_posts_db"):
        cfg["notion_viral_posts_db"] = create_database(token, page_id, "Viral Posts", VIRAL_POSTS_SCHEMA)
        changed = True

    if not cfg.get("notion_patterns_db"):
        cfg["notion_patterns_db"] = create_database(token, page_id, "Cross-Account Patterns", PATTERNS_SCHEMA)
        changed = True

    if not cfg.get("notion_niche_journey_db"):
        cfg["notion_niche_journey_db"] = create_database(token, page_id, "Niche Journey", NICHE_JOURNEY_SCHEMA)
        changed = True

    if changed:
        save_config(cfg)
    return cfg

def post_already_exists(token, db_id, post_id):
    """Check if a post with this shortcode already exists in the Viral Posts DB."""
    payload = {
        "filter": {
            "property": "Post ID",
            "rich_text": {"equals": post_id}
        }
    }
    r = requests.post(f"{NOTION_API}/databases/{db_id}/query",
                      headers=notion_headers(token), json=payload)
    if not r.ok:
        return False
    return len(r.json().get("results", [])) > 0

def _rt(text):
    """Helper: rich_text property value."""
    return {"rich_text": [{"text": {"content": str(text)[:2000]}}]}

def _title(text):
    """Helper: title property value."""
    return {"title": [{"text": {"content": str(text)[:2000]}}]}

def push_viral_post(token, db_id, analysis):
    """Push a single analyzed post to the Viral Posts Notion database."""
    post_date = analysis.get("date", "")[:10]  # ISO date string YYYY-MM-DD
    eng_rate  = analysis.get("engagement_rate", 0) / 100  # Notion stores percent as decimal

    properties = {
        "Post URL":                _title(analysis.get("url", "")),
        "Account":                 {"select": {"name": analysis.get("account", "")}},
        "Format":                  {"select": {"name": analysis.get("format", "Single Photo")}},
        "Post Date":               {"date": {"start": post_date}} if post_date else {"date": None},
        "Views":                   {"number": analysis.get("views", 0)},
        "Likes":                   {"number": analysis.get("likes", 0)},
        "Comments":                {"number": analysis.get("comments", 0)},
        "Engagement Rate":         {"number": eng_rate},
        "Caption":                 _rt(analysis.get("caption", "")[:2000]),
        "Caption Hook":            _rt(analysis.get("caption_hook", "")),
        "Has Visual Text Overlay": {"checkbox": bool(analysis.get("has_visual_text"))},
        "Visual Hook Text":        _rt(analysis.get("visual_hook_text", "")),
        "Has Voiceover":           {"checkbox": bool(analysis.get("has_voiceover"))},
        "Audio Hook Text":         _rt(analysis.get("audio_hook_text", "")),
        "Content Type":            {"select": {"name": analysis.get("content_type", "other")}},
        "Post ID":                 _rt(analysis.get("shortcode", "")),
    }

    payload = {
        "parent":     {"database_id": db_id},
        "properties": properties,
    }
    r = requests.post(f"{NOTION_API}/pages", headers=notion_headers(token), json=payload)
    if not r.ok:
        log(f"    Notion push failed for {analysis.get('shortcode')}: {r.json()}")

def push_pattern(token, db_id, pattern):
    """Push a cross-account pattern to the Patterns database."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    properties = {
        "Pattern Name":  _title(pattern.get("name", "Unnamed Pattern")),
        "Pattern Type":  {"select": {"name": pattern.get("type", "other")}},
        "Description":   _rt(pattern.get("description", "")),
        "Accounts":      _rt(pattern.get("accounts", "")),
        "Account Count": {"number": pattern.get("account_count", 0)},
        "Frequency":     _rt(pattern.get("frequency", "")),
        "Analysis Date": {"date": {"start": today}},
    }
    payload = {"parent": {"database_id": db_id}, "properties": properties}
    r = requests.post(f"{NOTION_API}/pages", headers=notion_headers(token), json=payload)
    if not r.ok:
        log(f"    Notion push failed for pattern '{pattern.get('name')}': {r.json()}")

def push_niche_journey(token, db_id, journey):
    """Push a niche journey analysis to the Niche Journey database."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    properties = {
        "Account":                    _title(journey.get("account", "")),
        "Start Date":                 {"date": {"start": journey.get("start_date", today)}},
        "Current Niche":              _rt(journey.get("current_niche", "")),
        "Journey Summary":            _rt(journey.get("summary", "")),
        "Had Clear Niche From Start": {"checkbox": bool(journey.get("had_clear_niche"))},
        "Shift Date Estimate":        _rt(journey.get("shift_date_estimate", "")),
        "Posts Analyzed":             {"number": journey.get("posts_analyzed", 0)},
        "Analysis Date":              {"date": {"start": today}},
    }
    payload = {"parent": {"database_id": db_id}, "properties": properties}
    r = requests.post(f"{NOTION_API}/pages", headers=notion_headers(token), json=payload)
    if not r.ok:
        log(f"    Notion push failed for niche journey '{journey.get('account')}': {r.json()}")

# ── AI analysis — cross-account & niche ──────────────────────────────────────

def analyze_cross_account_patterns(client, all_post_analyses):
    """
    Single Claude Sonnet call across all analyzed posts.
    Returns list of pattern dicts.
    """
    if not all_post_analyses:
        return []

    # Build a compact summary for the prompt
    lines = []
    for p in all_post_analyses:
        lines.append(
            f"Account={p.get('account')} Format={p.get('format')} "
            f"ContentType={p.get('content_type')} "
            f"Views={p.get('views')} ER={p.get('engagement_rate'):.2f}% "
            f"HasText={p.get('has_visual_text')} HasVoice={p.get('has_voiceover')} "
            f"Hook: {p.get('caption_hook', '')[:80]}"
        )
    summary = "\n".join(lines[:200])   # cap at 200 posts to stay in token budget

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": (
                    "You are analyzing top-performing Instagram posts across multiple public accounts.\n"
                    "Identify 5-10 patterns that explain WHY content is going viral.\n"
                    "Look for: common hook structures, formats that overperform, topics clustering, "
                    "audio/visual patterns, content types that dominate.\n\n"
                    "For each pattern output a JSON object on its own line:\n"
                    '{"name": "...", "type": "Format|Hook|Topic|Audio|Visual", '
                    '"description": "...", "accounts": "acc1, acc2", '
                    '"account_count": N, "frequency": "..."}\n\n'
                    "Data:\n" + summary
                )
            }]
        )
        raw = response.content[0].text.strip()
        patterns = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    patterns.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return patterns
    except Exception as e:
        log(f"  Cross-account pattern analysis error: {e}")
        return []

def analyze_niche_journey(client, account, oldest_posts):
    """
    Claude Sonnet analysis of an account's niche journey from their earliest posts.
    Returns a dict.
    """
    fallback = {
        "account": account, "start_date": "", "current_niche": "",
        "summary": "", "had_clear_niche": False,
        "shift_date_estimate": "", "posts_analyzed": len(oldest_posts),
    }
    if not oldest_posts:
        return fallback

    lines = []
    for p in oldest_posts:
        lines.append(
            f"Date={p.get('date','')[:10]} "
            f"Format={p.get('format')} "
            f"Caption: {p.get('caption','')[:120]}"
        )
    posts_text = "\n".join(lines)

    # Earliest post date
    dates = [p.get("date", "") for p in oldest_posts if p.get("date")]
    start_date = min(dates)[:10] if dates else ""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": (
                    f"Analyze the niche journey of Instagram account @{account} "
                    "based on their earliest posts below.\n\n"
                    "Answer these questions in a single JSON object:\n"
                    '{"current_niche": "one-line description of what they post now", '
                    '"had_clear_niche": true/false (did they start with a clear niche?), '
                    '"shift_date_estimate": "approximate date they found their niche, or empty string", '
                    '"summary": "2-3 sentence paragraph describing their niche journey"}\n\n'
                    "Earliest posts:\n" + posts_text
                )
            }]
        )
        raw = response.content[0].text.strip()
        # Extract JSON from response
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(raw[start:end])
            return {
                "account":             account,
                "start_date":          start_date,
                "current_niche":       data.get("current_niche", ""),
                "summary":             data.get("summary", ""),
                "had_clear_niche":     data.get("had_clear_niche", False),
                "shift_date_estimate": data.get("shift_date_estimate", ""),
                "posts_analyzed":      len(oldest_posts),
            }
    except Exception as e:
        log(f"  Niche journey analysis error ({account}): {e}")

    return {**fallback, "start_date": start_date}

# ── Claude retry wrapper ──────────────────────────────────────────────────────

def _claude_with_retry(fn, *args, **kwargs):
    """Call fn once; on failure wait 30s and retry once; return fallback on second fail."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        log(f"  Claude error (will retry in 30s): {e}")
        time.sleep(30)
        try:
            return fn(*args, **kwargs)
        except Exception as e2:
            log(f"  Claude retry failed: {e2}")
            return None

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    setup_tmp_dir()
    cfg = load_config()

    # Validate config
    if not cfg.get("notion_token"):
        log("ERROR: notion_token not set in ~/.viral_content_config.json")
        log("  1. Go to notion.so/my-integrations → New integration → copy token")
        log("  2. Set 'notion_token' in ~/.viral_content_config.json")
        sys.exit(1)

    if not cfg.get("notion_page_id"):
        log("ERROR: notion_page_id not set in ~/.viral_content_config.json")
        log("  1. Create a blank page called 'Viral Content Analysis' in Notion")
        log("  2. Connect your integration via the ... menu → Connections")
        log("  3. Copy the page ID from the URL and set 'notion_page_id'")
        sys.exit(1)

    if not cfg.get("accounts"):
        log("ERROR: no accounts configured in ~/.viral_content_config.json")
        log("  Add Instagram usernames to the 'accounts' list")
        sys.exit(1)

    # Determine lookback window (VIRAL_TEST_DAYS env var overrides for testing)
    days = 180 if cfg.get("last_run") is None else 90
    if os.environ.get("VIRAL_TEST_DAYS"):
        days = int(os.environ["VIRAL_TEST_DAYS"])
    log(f"\n{'='*55}")
    log(f"Viral Content Analysis — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log(f"Lookback: {days} days  |  Accounts: {len(cfg['accounts'])}")
    log(f"{'='*55}\n")

    # Init AI clients
    client = anthropic.Anthropic(api_key=API_KEY)

    whisper_model = None
    try:
        import whisper
        log("Loading Whisper base model...")
        whisper_model = whisper.load_model("base")
        log("  Whisper loaded.\n")
    except ImportError:
        log("Whisper not installed — audio analysis disabled (pip3 install openai-whisper)\n")
    except Exception as e:
        log(f"Whisper load failed: {e} — audio analysis disabled\n")

    # Init instaloader
    try:
        import instaloader
    except ImportError:
        log("ERROR: instaloader not installed. Run: pip3 install instaloader")
        sys.exit(1)

    loader = instaloader.Instaloader(
        sleep=True,
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
    )

    # Ensure Notion databases exist
    log("Ensuring Notion databases exist...")
    try:
        cfg = ensure_databases_exist(cfg)
    except Exception as e:
        log(f"ERROR creating Notion databases: {e}")
        sys.exit(1)

    token           = cfg["notion_token"]
    viral_posts_db  = cfg["notion_viral_posts_db"]
    patterns_db     = cfg["notion_patterns_db"]
    niche_db        = cfg["notion_niche_journey_db"]

    all_analyses = []

    accounts = cfg["accounts"]
    if os.environ.get("VIRAL_TEST_ACCOUNTS"):
        accounts = os.environ["VIRAL_TEST_ACCOUNTS"].split(",")

    for account in accounts:
        log(f"\n── @{account} ──────────────────────────────")

        # Scrape recent posts
        log(f"  Scraping last {days} days...")
        posts = scrape_recent_posts(account, loader, days)
        log(f"  Found {len(posts)} posts in window")

        if not posts:
            time.sleep(30)
            continue

        # Filter to top performers
        top_posts = get_top_performers(posts, cfg)
        log(f"  Top performers: {len(top_posts)} posts pass filter")

        # Analyze and push each post
        for post in top_posts:
            shortcode = post["shortcode"]

            # Dedup check
            if post_already_exists(token, viral_posts_db, shortcode):
                log(f"  Skip (exists): {shortcode}")
                continue

            log(f"  Analyzing {shortcode} [{post.get('format')}] ...")
            analysis = analyze_post(client, whisper_model, post)
            all_analyses.append(analysis)

            push_viral_post(token, viral_posts_db, analysis)
            log(f"    → Pushed to Notion (ER={analysis['engagement_rate']:.2f}%, type={analysis['content_type']})")

            # Save config after every post — crash-safe
            save_config(cfg)

        # Niche journey (once per account)
        if account not in cfg.get("niche_journey_completed", []):
            log(f"  Running niche journey analysis (first time)...")
            oldest = scrape_oldest_posts(account, loader, limit=30)
            log(f"  Scraped {len(oldest)} oldest posts for niche analysis")

            journey = analyze_niche_journey(client, account, oldest)
            push_niche_journey(token, niche_db, journey)
            log(f"  Niche journey pushed: {journey.get('current_niche', 'N/A')}")

            cfg.setdefault("niche_journey_completed", []).append(account)
            save_config(cfg)

        # Rate limit between accounts
        log(f"  Sleeping 30s before next account...")
        time.sleep(30)

    # Cross-account pattern analysis
    if all_analyses:
        log(f"\nAnalyzing cross-account patterns ({len(all_analyses)} posts)...")
        patterns = analyze_cross_account_patterns(client, all_analyses)
        log(f"  Found {len(patterns)} patterns")
        for pattern in patterns:
            push_pattern(token, patterns_db, pattern)
            log(f"  → Pattern pushed: {pattern.get('name', '?')}")
    else:
        log("\nNo new analyses this run — skipping cross-account patterns")

    # Finalize
    cfg["last_run"] = datetime.now(timezone.utc).isoformat()
    save_config(cfg)

    log(f"\n{'='*55}")
    log(f"Done! {len(all_analyses)} posts analyzed and pushed to Notion.")
    log(f"Next monthly run will look back 90 days.")
    log(f"{'='*55}\n")

if __name__ == "__main__":
    main()
