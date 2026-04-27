# Polls t.me/WalterBloomberg every 60 seconds during market hours
# Saves latest Bloomberg Terminal headlines to tg_feed.json
# proxy.py reads this file and injects headlines into Kimi's prompt

import urllib.request
import urllib.error
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta

CHANNEL     = "WalterBloomberg"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tg_feed.json")
MAX_POSTS   = 20
POLL_SECS   = 60   # during market hours
SLEEP_SECS  = 300  # outside market hours

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def is_market_hours():
    """True from 8:30am to 4:30pm ET Mon-Fri (includes pre-market)."""
    et  = datetime.now(timezone(timedelta(hours=-4)))
    day = et.weekday()
    if day >= 5:
        return False
    mins = et.hour * 60 + et.minute
    return 510 <= mins <= 990  # 8:30am to 4:30pm


def fetch_channel():
    """Scrape t.me/s/WalterBloomberg (public preview page)."""
    url = f"https://t.me/s/{CHANNEL}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")

        texts = re.findall(
            r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        ids = re.findall(r'data-post="WalterBloomberg/(\d+)"', html)

        clean = []
        for t in texts:
            t = re.sub(r'<br\s*/?>', ' ', t)
            t = re.sub(r'<[^>]+>', '', t)
            t = t.strip()
            if t and len(t) > 5:
                clean.append(t)

        return list(zip(ids[-len(clean):], clean)) if ids else list(enumerate(clean))

    except Exception as e:
        print(f"  [TG] Fetch error: {e}")
        return []


def load_existing():
    try:
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return []


def save_posts(new_posts, existing):
    """Merge new posts with existing, keep latest MAX_POSTS."""
    existing_ids = {str(p.get('id', '')) for p in existing}
    added = []
    for pid, text in new_posts:
        if str(pid) not in existing_ids:
            added.append({
                "id":     str(pid),
                "text":   text,
                "time":   datetime.now(timezone.utc).isoformat(),
                "source": "WalterBloomberg (Bloomberg Terminal)"
            })
            print(f"  [NEW] {text[:120]}")

    if added:
        combined = added + existing
        combined = combined[:MAX_POSTS]
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(combined, f, indent=2, ensure_ascii=False)
        print(f"  [SAVED] {len(added)} new posts — {len(combined)} total")
    return len(added)


def main():
    print()
    print("=" * 54)
    print("   Walter Bloomberg Telegram Feed Monitor")
    print("=" * 54)
    print(f"  Channel : t.me/{CHANNEL}")
    print(f"  Output  : {OUTPUT_FILE}")
    print(f"  Interval: {POLL_SECS}s (market) / {SLEEP_SECS}s (closed)")
    print()
    print("  Monitoring... (Ctrl+C to stop)")
    print()

    while True:
        now = datetime.now().strftime('%H:%M:%S')
        try:
            posts     = fetch_channel()
            existing  = load_existing()
            new_count = save_posts(posts, existing)

            if new_count == 0:
                print(f"  [{now}] No new posts — {len(existing)} in feed")

        except Exception as e:
            print(f"  [{now}] Error: {e}")

        if is_market_hours():
            time.sleep(POLL_SECS)
        else:
            print(f"  [{now}] Outside market hours — sleeping {SLEEP_SECS}s")
            time.sleep(SLEEP_SECS)


if __name__ == "__main__":
    main()
