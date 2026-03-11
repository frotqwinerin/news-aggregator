# MY News Digest — Malaysia & SEA News Aggregator

A self-hosted, AI-powered news dashboard focused on **Malaysia and Southeast Asia**, hosted for free on **GitHub Pages**. A Python scraper fetches articles from RSS feeds daily (via GitHub Actions), generates summaries with Claude AI, and saves JSON files that the static dashboard reads.

---

## Features

| Feature | Details |
|---|---|
| **3 topic categories** | Tech/AI/Cybersecurity (global); Race, Religion & Royalty (MY/SEA); Counter-terrorism & Organised Crime (MY/SEA) |
| **AI summaries** | Per-article 2–3 sentence summaries + a daily editorial briefing per category (powered by Claude claude-haiku-4-5) |
| **Date picker** | Browse any date that has been scraped; prev/next day navigation |
| **Live search** | Filter articles by keyword within the active category |
| **Auto scraping** | GitHub Actions runs the scraper every day at 09:00 MYT (01:00 UTC) |
| **Manual scrape** | Trigger on-demand from GitHub Actions UI or run locally |
| **Zero cost hosting** | Entirely static — served from GitHub Pages, no server needed |

---

## Project Structure

```
news-aggregator/
├── .github/
│   └── workflows/
│       └── scrape.yml        # GitHub Actions — daily + manual scraping
├── data/
│   ├── index.json            # List of available dates (auto-updated by scraper)
│   └── YYYY-MM-DD.json       # One file per scraped day (auto-generated)
├── scripts/
│   ├── scraper.py            # Main Python scraping & summarisation script
│   └── requirements.txt      # Python dependencies
├── index.html                # Dashboard — served by GitHub Pages
├── style.css                 # Stylesheet
├── app.js                    # Dashboard JavaScript
└── README.md
```

---

## Quick Start

### 1. Fork / Clone

```bash
git clone https://github.com/YOUR-USERNAME/news-aggregator.git
cd news-aggregator
```

### 2. Install Python dependencies

```bash
pip install -r scripts/requirements.txt
```

### 3. Get an Anthropic API key

Sign up at [console.anthropic.com](https://console.anthropic.com) and create an API key.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 4. Run the scraper for the first time

```bash
# Scrape today's news with AI summaries
python scripts/scraper.py

# Scrape without AI (no API key needed)
python scripts/scraper.py --no-summarize

# Scrape a specific date
python scripts/scraper.py --date 2025-03-12
```

This creates `data/YYYY-MM-DD.json` and updates `data/index.json`.

### 5. Preview locally

Open `index.html` in your browser. If you get CORS errors fetching the JSON files, serve with a local server:

```bash
python -m http.server 8080
# then open http://localhost:8080
```

---

## GitHub Pages Deployment

### Step 1 — Push to GitHub

```bash
git add .
git commit -m "Initial setup"
git push origin main
```

### Step 2 — Enable GitHub Pages

1. Go to your repository → **Settings** → **Pages**
2. Under **Source**, choose **Deploy from a branch**
3. Select branch: `main`, folder: `/ (root)`
4. Click **Save**

Your site will be live at `https://YOUR-USERNAME.github.io/news-aggregator/`

### Step 3 — Add your Anthropic API key as a secret

1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `ANTHROPIC_API_KEY`, Value: `sk-ant-...`

### Step 4 — Enable GitHub Actions

The workflow at `.github/workflows/scrape.yml` runs automatically at **09:00 MYT (01:00 UTC)** every day.

To trigger it manually:
1. Go to your repository → **Actions**
2. Click **Daily News Scraper** in the left panel
3. Click **Run workflow**
4. (Optional) enter a specific date, toggle flags, then click **Run workflow**

The action will scrape news, generate AI summaries, commit the JSON files, and push — GitHub Pages will update within a minute.

---

## Scraper CLI Reference

```
python scripts/scraper.py [OPTIONS]

Options:
  --date YYYY-MM-DD     Date to scrape (default: today in MYT)
  --force               Re-scrape even if data already exists for that date
  --no-summarize        Skip AI summarisation (no API key needed)
  --no-fetch            Skip fetching full article pages (uses RSS snippets only; faster)
  --categories CAT,...  Comma-separated categories: tech,society,security (default: all)
  --verbose             Enable DEBUG logging
```

### Examples

```bash
# Full scrape with AI
python scripts/scraper.py

# Fast scrape — no article page fetching, no AI summaries
python scripts/scraper.py --no-fetch --no-summarize

# Only scrape the security category
python scripts/scraper.py --categories security

# Force re-scrape a past date
python scripts/scraper.py --date 2025-01-20 --force
```

---

## Customisation

### Adding or removing news sources

Edit `CATEGORIES` in [scripts/scraper.py](scripts/scraper.py). Each source entry needs:

```python
{"name": "Display Name", "url": "https://example.com/feed.rss"}
```

### Changing keyword filters

The `keywords` list inside each category controls what gets included for the SEA-filtered categories (`society` and `security`). The `tech` category includes all articles from its sources without keyword filtering.

### Changing the scrape schedule

Edit the `cron` expression in [.github/workflows/scrape.yml](.github/workflows/scrape.yml):

```yaml
schedule:
  - cron: "0 1 * * *"   # 01:00 UTC = 09:00 MYT
```

Use [crontab.guru](https://crontab.guru) to build your expression.

### Adding the GitHub Actions link to the dashboard

In [app.js](app.js), set:

```javascript
const GITHUB_ACTIONS_URL = 'https://github.com/YOUR-USERNAME/news-aggregator/actions';
```

This enables the **⚡ Trigger scrape** button in the sidebar.

### AI models

The scraper uses `claude-haiku-4-5` for both article summaries and category briefings (fast and cost-efficient). To use a more capable model, edit these constants in `scripts/scraper.py`:

```python
ARTICLE_MODEL  = "claude-haiku-4-5"    # per-article summaries
BRIEFING_MODEL = "claude-haiku-4-5"    # daily category briefing
```

---

## Data Format

Each daily file (`data/YYYY-MM-DD.json`) has this structure:

```json
{
  "date": "2025-03-12",
  "generated_at": "2025-03-12T01:05:42+00:00",
  "categories": {
    "tech": {
      "id": "tech",
      "label": "Tech, AI & Cybersecurity",
      "icon": "💻",
      "color": "#4f46e5",
      "article_count": 28,
      "briefing": "Today in tech...",
      "articles": [
        {
          "id": "a1b2c3d4e5f6",
          "title": "Article title",
          "url": "https://example.com/article",
          "source": "TechCrunch",
          "published": "2025-03-12T08:30:00+00:00",
          "summary": "AI-generated 2–3 sentence summary.",
          "image": "https://example.com/image.jpg"
        }
      ]
    }
  }
}
```

`data/index.json` lists all available dates:

```json
{
  "dates": ["2025-03-12", "2025-03-11", "..."],
  "latest": "2025-03-12",
  "updated": "2025-03-12T01:06:00+00:00"
}
```

---

## News Sources

### Tech, AI & Cybersecurity (Global)

| Source | Focus |
|---|---|
| TechCrunch | Tech industry news |
| The Verge | Consumer tech & culture |
| Wired | Tech, science & culture |
| Ars Technica | In-depth tech reporting |
| The Hacker News | Cybersecurity |
| Krebs on Security | Cybersecurity investigations |
| BleepingComputer | Malware, cybercrime, security |
| MIT Technology Review | AI & emerging tech |
| VentureBeat AI | AI industry |
| Dark Reading | Enterprise security |

### Race, Religion & Royalty (Malaysia/SEA)

| Source | Country |
|---|---|
| The Star Malaysia | Malaysia |
| Malay Mail | Malaysia |
| Free Malaysia Today | Malaysia |
| New Straits Times | Malaysia |
| Channel NewsAsia | Singapore/Regional |
| Benar News | SEA (RFA-affiliated) |
| South China Morning Post | Regional |
| The Diplomat | SEA policy & politics |

### Counter-terrorism & Organised Crime (Malaysia/SEA)

Same regional sources as above, plus:

| Source | Focus |
|---|---|
| RSIS | Singapore security think tank |
| The Diplomat | Regional security analysis |

---

## Troubleshooting

**Dashboard shows "No data yet"**
→ Run `python scripts/scraper.py` locally, or trigger GitHub Actions manually.

**GitHub Actions runs but no data appears on the site**
→ Check that GitHub Pages is enabled (Settings → Pages) and pointing to the `main` branch root.

**AI summaries are missing / blank**
→ Ensure `ANTHROPIC_API_KEY` is set as a GitHub Actions secret, or export it locally.

**Some feeds return no articles**
→ RSS feeds occasionally go down or change their URLs. Check the scraper logs. You can add `--verbose` for detailed output.

**CORS error when opening index.html directly**
→ Open with `python -m http.server 8080` instead of `file://`.

**Rate limit errors from Anthropic**
→ The scraper has built-in delays. If you hit rate limits, add `--no-summarize` for test runs, or upgrade your API tier.

---

## Cost Estimate

Running the scraper daily with AI summaries enabled:

- ~30 articles × ~300 tokens input + 200 tokens output = ~15,000 tokens/day per category
- ~3 categories = ~45,000 tokens/day
- `claude-haiku-4-5` pricing: $1.00 per million input, $5.00 per million output tokens
- Estimated: **< $0.05/day** (< $1.50/month)

Briefing generation adds ~3 × 500 tokens ≈ negligible.

Running with `--no-summarize` is completely free (only RSS fetching).

---

## License

MIT — do whatever you like with it.
