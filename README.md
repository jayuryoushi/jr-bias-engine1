# JR Bias Engine — Local Setup

## Files
```
BiasEngine/
├── proxy.py                  ← Main server (port 8765) + AI + RSS + FRED
├── trading_bias_dashboard.html ← Dashboard (served by proxy.py)
├── tg_feed.py                ← Telegram scraper (@WalterBloomberg)
├── tg_feed.json              ← Auto-created when tg_feed.py runs
├── START.bat                 ← One-click launcher (Windows)
└── README.md
```

## Requirements
- Python 3.8+ (no extra packages needed — stdlib only)
- Internet access

## Quick Start (Windows)

**Option A — Double-click:**
Just run `START.bat`. It opens two terminal windows and your browser automatically.

**Option B — Manual (two terminals):**

Terminal 1 — Telegram feed:
```
cd C:\Users\DZ Laptops\Desktop\BiasEngine
python tg_feed.py
```

Terminal 2 — Proxy + dashboard:
```
cd C:\Users\DZ Laptops\Desktop\BiasEngine
python proxy.py
```

Then open: http://localhost:8765

## Environment Variables (optional overrides)

| Variable       | Default                              | Purpose                    |
|----------------|--------------------------------------|----------------------------|
| NVIDIA_API_KEY | hardcoded in proxy.py                | Kimi K2.5 via NVIDIA NIMs  |
| PORT           | 8765                                 | Proxy server port          |
| FRED_API_KEY   | (empty — works without it)           | FRED macro data            |

To set a custom key without editing code:
```bat
set NVIDIA_API_KEY=nvapi-your-key-here
python proxy.py
```

## Endpoints
| URL                        | What it does                        |
|----------------------------|-------------------------------------|
| http://localhost:8765/     | Dashboard HTML                      |
| http://localhost:8765/news | Live RSS headlines (JSON)           |
| http://localhost:8765/v1/messages | AI analysis via Kimi K2.5   |
| http://localhost:8765/health | Health check (returns OK)         |

## How it works
1. `tg_feed.py` scrapes @WalterBloomberg Telegram every 60s and saves to `tg_feed.json`
2. `proxy.py` serves the dashboard and handles all API calls:
   - On "Run Analysis": fetches live price (Yahoo Finance), FRED macro data, RSS feeds, reads tg_feed.json, then sends everything to Kimi K2.5
   - The `/news` endpoint powers the live headline ticker in the dashboard

## Troubleshooting
- **Port in use**: Change PORT env var or kill the process using 8765
- **No Bloomberg headlines**: Make sure `tg_feed.py` is running — it creates `tg_feed.json`
- **API error**: Check your NVIDIA_API_KEY is valid at https://integrate.api.nvidia.com
- **CORS issues**: The proxy handles CORS — always open the dashboard via http://localhost:8765, not as a local file
