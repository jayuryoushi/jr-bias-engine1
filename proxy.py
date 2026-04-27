import http.server
import urllib.request
import urllib.error
import urllib.parse
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
 
# ── Config ────────────────────────────────────────────────────────
API_KEY  = os.environ.get("NVIDIA_API_KEY", "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")
ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL    = "nvidia/llama-3.3-nemotron-super-49b-v1"
PORT     = int(os.environ.get("PORT", 8765))
HOST     = "0.0.0.0"
 
# ── RSS feeds ─────────────────────────────────────────────────────
RSS_FEEDS = {
    "fed": [
        ("Fed Reserve Official",  "https://www.federalreserve.gov/feeds/press_all.xml"),
        ("CNBC Fed",              "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
        ("Reuters Fed",           "https://feeds.reuters.com/reuters/businessNews"),
    ],
    "macro": [
        ("Reuters Markets",       "https://feeds.reuters.com/reuters/businessNews"),
        ("MarketWatch Economy",   "https://feeds.marketwatch.com/marketwatch/economy-politics/"),
        ("CNBC Economy",          "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
        ("Investing.com",         "https://www.investing.com/rss/news_25.rss"),
        ("FT Markets",            "https://www.ft.com/rss/home/us"),
    ],
    "market": [
        ("Reuters Finance",       "https://feeds.reuters.com/reuters/moneyNews"),
        ("CNBC Markets",          "https://www.cnbc.com/id/15839135/device/rss/rss.html"),
        ("MarketWatch Markets",   "https://feeds.marketwatch.com/marketwatch/marketpulse/"),
        ("Investing.com News",    "https://www.investing.com/rss/news.rss"),
    ],
    "risk": [
        ("Reuters Top News",      "https://feeds.reuters.com/reuters/topNews"),
        ("CNBC Top News",         "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("Reuters World",         "https://feeds.reuters.com/Reuters/worldNews"),
    ],
}
 
# ── Yahoo Finance map ─────────────────────────────────────────────
# US100 CFD → use NQ=F (Nasdaq 100 futures, same price range as CFD)
YAHOO_MAP = {
    "US100 / NAS100":  "NQ=F",
    "SPX / ES":        "%5EGSPC",
    "NQ / Nasdaq":     "NQ=F",
    "Gold / XAUUSD":   "GC=F",
    "Crude Oil / WTI": "CL=F",
    "EUR/USD":         "EURUSD=X",
    "GBP/USD":         "GBPUSD=X",
    "US30":            "%5EDJI",
}
 
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":     "application/rss+xml, application/xml, text/xml, */*",
}
 
# ── FRED economic data ────────────────────────────────────────────
FRED_SERIES = {
    # Monetary Policy
    "Fed Funds Rate":        "FEDFUNDS",
    "10Y Treasury Yield":    "DGS10",
    "2Y Treasury Yield":     "DGS2",
    "10Y-2Y Spread":         "T10Y2Y",
    # Inflation
    "CPI YoY":               "CPIAUCSL",
    "Core PCE":              "PCEPILFE",
    "PPI":                   "PPIACO",
    # Growth & Labour
    "GDP Growth":            "A191RL1Q225SBEA",
    "Unemployment Rate":     "UNRATE",
    "Initial Jobless Claims":"IC4WSA",
    "Retail Sales":          "RSAFS",
    "ISM Manufacturing":     "MANEMP",
    # Risk & Liquidity
    "VIX":                   "VIXCLS",
    "US Dollar Index":       "DTWEXBGS",
    "M2 Money Supply":       "M2SL",
    "Credit Spread HY":      "BAMLH0A0HYM2",
}
FRED_API_KEY = os.environ.get("FRED_API_KEY", "e08c51195328cf35b05ae8d0f777f091")  # Optional — get free key at fred.stlouisfed.org
 
 
def fetch_deitaone():
    """Read latest Walter Bloomberg Telegram posts from local feed file."""
    feed_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tg_feed.json")
    try:
        if os.path.exists(feed_file):
            with open(feed_file, 'r', encoding='utf-8') as f:
                items = json.load(f)
            posts = [item['text'] for item in items[:15] if item.get('text')]
            print(f"  [WalterBloomberg TG] {len(posts)} posts loaded")
            return posts[:10]
        else:
            print("  [WalterBloomberg TG] tg_feed.json not found — run tg_feed.py")
    except Exception as e:
        print(f"  [WalterBloomberg TG] Read error: {e}")
    return []
 
 
def fetch_fred_data():
    """Fetch key macro numbers from FRED (St. Louis Fed)."""
    results = []
    try:
        for name, series_id in FRED_SERIES.items():
            try:
                if FRED_API_KEY:
                    # Official API — faster, higher rate limits
                    url = (f"https://api.stlouisfed.org/fred/series/observations"
                           f"?series_id={series_id}&api_key={FRED_API_KEY}"
                           f"&sort_order=desc&limit=1&file_type=json")
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = json.loads(r.read())
                    obs = data.get("observations", [])
                    if obs and obs[0].get("value") != ".":
                        results.append(f"{name}: {obs[0]['value']} (as of {obs[0]['date']})")
                else:
                    # Public CSV fallback — no key needed
                    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        csv = r.read().decode("utf-8", errors="ignore")
                    lines = [l for l in csv.strip().split("\n") if l and not l.startswith("DATE")]
                    if lines:
                        last = lines[-1].split(",")
                        if len(last) >= 2 and last[1].strip() not in (".", ""):
                            results.append(f"{name}: {last[1].strip()} (as of {last[0]})")
            except Exception:
                pass
    except Exception as e:
        print(f"  [FRED] Error: {e}")
    print(f"  [FRED] {len(results)}/{len(FRED_SERIES)} series loaded")
    return results
 
 
def fetch_rss(url, max_items=4):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read()
        root  = ET.fromstring(raw)
        ns    = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        results = []
        for item in items[:max_items]:
            title = item.findtext("title") or item.findtext("atom:title", namespaces=ns) or ""
            desc  = item.findtext("description") or item.findtext("atom:summary", namespaces=ns) or ""
            desc  = re.sub(r"<[^>]+>", "", desc).strip()[:200]
            title = re.sub(r"<[^>]+>", "", title).strip()
            if title:
                results.append(f"{title}: {desc}" if desc else title)
        return results
    except Exception:
        return []
 
 
def fetch_live_price(instrument):
    """Fetch real-time US100 CFD price — uses NQ futures as proxy (same price range)."""
    try:
        ticker = YAHOO_MAP.get(instrument, "NQ=F")
        url    = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
        req    = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        meta  = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        prev  = meta.get("previousClose", price)
        chg   = ((price - prev) / prev * 100) if prev else 0
        print(f"  [PRICE] US100 CFD: {price:.1f} ({chg:+.2f}%)")
        return price, chg
    except Exception as e:
        print(f"  [PRICE] Failed: {e}")
        return None, None
 
 
def gather_live_context(instrument):
    """Full live context: price + FRED macro data + 4 RSS categories."""
    price, chg = fetch_live_price(instrument)
 
    print("  Fetching FRED macro data...")
    fred_data = fetch_fred_data()
 
    print("  Fetching Fed news...")
    fed_items = []
    for name, url in RSS_FEEDS["fed"][:2]:
        items = fetch_rss(url, 2)
        if items:
            print(f"    {len(items)} items — {name}")
            fed_items.extend(items)
        if len(fed_items) >= 4:
            break
 
    print("  Fetching macro news...")
    macro_items = []
    for name, url in RSS_FEEDS["macro"][:3]:
        items = fetch_rss(url, 3)
        if items:
            print(f"    {len(items)} items — {name}")
            macro_items.extend(items)
        if len(macro_items) >= 8:
            break
 
    print("  Fetching market news...")
    market_items = []
    for name, url in RSS_FEEDS["market"][:3]:
        items = fetch_rss(url, 3)
        if items:
            print(f"    {len(items)} items — {name}")
            market_items.extend(items)
        if len(market_items) >= 8:
            break
 
    print("  Fetching risk/geopolitical news...")
    risk_items = []
    for name, url in RSS_FEEDS["risk"][:3]:
        items = fetch_rss(url, 2)
        if items:
            print(f"    {len(items)} items — {name}")
            risk_items.extend(items)
        if len(risk_items) >= 6:
            break
 
    print("  Fetching @DeItaone Bloomberg Terminal feed...")
    deitaone_posts = fetch_deitaone()
 
    lines = []
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y %H:%M UTC")
    lines.append(f"=== LIVE DATA AS OF: {today} ===")
    lines.append(f"TARGET INSTRUMENT: US100 CFD (Nasdaq 100 CFD)")
    lines.append(f"NOTE: All price levels in your analysis must use US100 CFD pricing (~19,000-25,000 range, NOT IXIC composite ~16,000-20,000)")
 
    if price:
        prev = price / (1 + chg / 100) if chg else price
        lines.append(f"\n=== US100 CFD LIVE PRICE (use EXACTLY these numbers for levels) ===")
        lines.append(f"US100 CFD current price: {price:.1f}")
        lines.append(f"US100 CFD change today: {chg:+.2f}%")
        lines.append(f"US100 CFD previous close: {prev:.1f}")
        lines.append(f"Example key level format: 'Resistance at {price+200:.0f}', 'Support at {price-300:.0f}'")
 
    if deitaone_posts:
        lines.append(f"\n=== WALTER BLOOMBERG TELEGRAM — BLOOMBERG TERMINAL HEADLINES (MOST TIME-SENSITIVE — prioritize these) ===")
        lines.extend(deitaone_posts)
 
    if fred_data:
        lines.append(f"\n=== FRED MACRO DATA (St. Louis Federal Reserve — official numbers) ===")
        lines.extend(fred_data)
 
    if fed_items:
        lines.append(f"\n=== FED & CENTRAL BANK NEWS (Fed Reserve, CNBC, Reuters) ===")
        lines.extend(fed_items[:4])
 
    if macro_items:
        lines.append(f"\n=== MACRO NEWS (Reuters, MarketWatch, CNBC, FT, Investing.com) ===")
        lines.extend(macro_items[:6])
 
    if market_items:
        lines.append(f"\n=== US100 / NASDAQ MARKET NEWS (Reuters, CNBC, MarketWatch, Investing.com) ===")
        lines.extend(market_items[:6])
 
    if risk_items:
        lines.append(f"\n=== RISK & GEOPOLITICAL (Reuters, CNBC) ===")
        lines.extend(risk_items[:5])
 
    total = len(fed_items) + len(macro_items) + len(market_items) + len(risk_items)
    print(f"  [CONTEXT] {total} headlines + {len(fred_data)} FRED data points ready")
    return "\n".join(lines)
 
 
def fetch_news_only():
    """Quick headlines fetch for live ticker — no AI, just RSS."""
    all_items = []
    feeds = [
        ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
        ("CNBC",    "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("MW",      "https://feeds.marketwatch.com/marketwatch/marketpulse/"),
    ]
    for name, url in feeds:
        items = fetch_rss(url, 4)
        for item in items:
            all_items.append({"source": name, "text": item[:150]})
    return all_items[:12]
 
 
def call_kimi(messages):
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 2000,
        "messages": messages,
        "temperature": 0.6
    }).encode("utf-8")
 
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        raw = json.loads(resp.read())
    choice  = raw.get("choices", [{}])[0]
    message = choice.get("message", {})
    return message.get("content") or message.get("reasoning") or ""
 
 
# ── HTTP Handler ──────────────────────────────────────────────────
class ProxyHandler(http.server.BaseHTTPRequestHandler):
 
    def log_message(self, format, *args):
        print(f"  {format % args}")
 
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()
 
    def do_POST(self):
        if self.path == "/v1/messages":
            length   = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(length)
            try:
                req_body = json.loads(body_raw)
                messages = list(req_body.get("messages", []))
                user_msg = messages[-1].get("content", "") if messages else ""
                inst_match = re.search(r"analyzing:\s*(.+?)[\.\n]", user_msg)
                instrument = inst_match.group(1).strip() if inst_match else "US100 / NAS100"
 
                print(f"\n  [START] Full analysis for {instrument}")
                live_ctx = gather_live_context(instrument)
                if live_ctx:
                    messages[-1]["content"] = (
                        f"LIVE MARKET DATA (fetched right now from FRED, Reuters, CNBC, MarketWatch, FT, Investing.com):\n"
                        f"{live_ctx}\n\n---\n{user_msg}"
                    )
 
                print("  [AI] Sending to Llama Nemotron Super 49B...")
                content_text = call_kimi(messages)
                print(f"  [AI] {len(content_text)} chars returned")
 
                json_match = re.search(r'\{[\s\S]*\}', content_text)
                final_text = json_match.group(0) if json_match else content_text
 
                result = json.dumps({
                    "content": [{"type": "text", "text": final_text}],
                    "model": MODEL, "role": "assistant"
                }).encode("utf-8")
 
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(result)
                print("  [DONE]\n")
 
            except urllib.error.HTTPError as e:
                err = e.read()
                print(f"  API Error {e.code}: {err.decode()[:400]}")
                self.send_response(e.code)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err)
            except Exception as e:
                print(f"  Error: {e}")
                self.send_response(500)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
 
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()
 
    def do_GET(self):
        # Health check
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return
 
        # Live news ticker endpoint — no AI needed
        if self.path == "/news":
            try:
                news = fetch_news_only()
                result = json.dumps({"items": news, "ts": datetime.now(timezone.utc).isoformat()}).encode()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(result)
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
 
        # Bloomberg Terminal TG feed endpoint
        if self.path == "/tg":
            try:
                feed_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tg_feed.json")
                if os.path.exists(feed_file):
                    with open(feed_file, 'r', encoding='utf-8') as f:
                        items = json.load(f)
                    result = json.dumps({"items": items[:20], "ts": datetime.now(timezone.utc).isoformat(), "ok": True}).encode()
                else:
                    result = json.dumps({"items": [], "ts": datetime.now(timezone.utc).isoformat(), "ok": False, "error": "tg_feed.json not found — run tg_feed.py"}).encode()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(result)
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        # Serve dashboard
        html_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trading_bias_dashboard.html")
        if os.path.exists(html_file):
            with open(html_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"trading_bias_dashboard.html not found.")
 
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-api-key, anthropic-version")
 
 
if __name__ == "__main__":
    print()
    print("=" * 60)
    print("   Trading Bias Dashboard — Nemotron Super 49B + FRED + RSS")
    print("=" * 60)
    print()
    print(f"  Model     : {MODEL}")
    print(f"  Instrument: US100 CFD (NAS100)")
    print(f"  Sources   : FRED, Reuters, CNBC, MarketWatch, FT, Investing.com")
    print(f"  Endpoints : / (dashboard)  /news (live ticker)  /v1/messages (AI)")
    print(f"  Host      : {HOST}:{PORT}")
    print()
    print(f"  Open Brave -> http://localhost:{PORT}")
    print()
    print("  Ctrl+C to stop.")
    print()
 
    server = http.server.HTTPServer((HOST, PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")