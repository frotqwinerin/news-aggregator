#!/usr/bin/env python3
"""
Malaysia & SEA News Aggregator — Scraper
=========================================
Fetches news from RSS feeds across three categories:
  1. Tech, AI & Cybersecurity  (global)
  2. Race, Religion & Royalty  (Malaysia/SEA)
  3. Counter-terrorism & Organised Crime  (Malaysia/SEA)

Generates AI summaries via the Anthropic API, then saves a dated JSON file
that the static dashboard reads from GitHub Pages.

Usage:
  python scripts/scraper.py                     # scrape today (MYT)
  python scripts/scraper.py --date 2025-03-12   # specific date
  python scripts/scraper.py --no-summarize      # skip AI (free run)
  python scripts/scraper.py --force             # overwrite existing data
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import feedparser
import requests
from anthropic import Anthropic
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── HTTP ───────────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
REQUEST_TIMEOUT = 20          # seconds per HTTP request
FETCH_TIMEOUT = 12            # seconds when fetching article pages

# ── Scraping limits ────────────────────────────────────────────────────────────
MAX_ARTICLES_PER_FEED = 20    # entries to read per RSS feed
MAX_ARTICLES_PER_CATEGORY = 30  # final cap after filtering
CRAWL_DELAY = 0.4             # seconds between requests (be polite)

# ── AI models ─────────────────────────────────────────────────────────────────
ARTICLE_MODEL = "claude-haiku-4-5"   # fast & cheap for per-article summaries
BRIEFING_MODEL = "claude-haiku-4-5"  # daily editorial briefing

# ── Malaysia time zone ─────────────────────────────────────────────────────────
MYT = timezone(timedelta(hours=8))

# ── SEA geo-filter keywords ────────────────────────────────────────────────────
SEA_KEYWORDS: set[str] = {
    "malaysia", "malaysian", "kuala lumpur", "kl", "putrajaya",
    "sabah", "sarawak", "johor", "selangor", "penang", "perak",
    "negeri sembilan", "pahang", "kelantan", "terengganu", "kedah", "perlis",
    "southeast asia", "south-east asia", "asean",
    "singapore", "singaporean",
    "indonesia", "indonesian", "jakarta", "bali",
    "thailand", "thai", "bangkok",
    "philippines", "filipino", "manila",
    "myanmar", "burmese", "yangon",
    "vietnam", "vietnamese", "hanoi", "ho chi minh",
    "cambodia", "cambodian", "phnom penh",
    "brunei",
    "laos", "lao",
    "timor-leste", "east timor",
}

# ── Category definitions ───────────────────────────────────────────────────────
CATEGORIES: dict[str, dict] = {
    "tech": {
        "label": "Tech, AI & Cybersecurity",
        "icon": "💻",
        "color": "#4f46e5",
        "sea_filter": False,        # global news; no geo-filter
        "keywords": [],             # accept all from these sources
        "sources": [
            {"name": "TechCrunch",        "url": "https://techcrunch.com/feed/"},
            {"name": "The Verge",         "url": "https://www.theverge.com/rss/index.xml"},
            {"name": "Wired",             "url": "https://www.wired.com/feed/rss"},
            {"name": "Ars Technica",      "url": "https://feeds.arstechnica.com/arstechnica/index"},
            {"name": "The Hacker News",   "url": "https://thehackernews.com/feeds/posts/default"},
            {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/"},
            {"name": "BleepingComputer",  "url": "https://www.bleepingcomputer.com/feed/"},
            {"name": "MIT Tech Review",   "url": "https://www.technologyreview.com/feed/"},
            {"name": "VentureBeat AI",    "url": "https://venturebeat.com/category/ai/feed/"},
            {"name": "Dark Reading",      "url": "https://www.darkreading.com/rss.xml"},
        ],
    },
    "society": {
        "label": "Race, Religion & Royalty",
        "icon": "🕌",
        "color": "#dc2626",
        "sea_filter": True,
        "keywords": [
            "race", "racial", "racism", "racist", "ethnic", "ethnicity",
            "bumiputera", "pribumi", "vernacular",
            "religion", "religious", "faith", "mosque", "masjid", "temple",
            "church", "synagogue", "interfaith", "blasphemy", "apostasy",
            "muslim", "islam", "islamic", "christian", "christianity",
            "hindu", "hinduism", "buddhist", "buddhism", "sikh", "sikhism",
            "royalty", "royal", "sultan", "agong", "king", "queen",
            "monarchy", "palace", "istana", "raja", "tengku",
            "malay", "chinese", "indian", "orang asli", "minority",
            "harmony", "tolerance", "discrimination", "hate crime",
        ],
        "sources": [
            {"name": "The Star Malaysia",       "url": "https://www.thestar.com.my/rss/news/nation"},
            {"name": "Malay Mail",              "url": "https://www.malaymail.com/feed"},
            {"name": "Free Malaysia Today",     "url": "https://www.freemalaysiatoday.com/feed/"},
            {"name": "New Straits Times",       "url": "https://www.nst.com.my/rss/news"},
            {"name": "Channel NewsAsia",        "url": "https://www.channelnewsasia.com/rss/8395694"},
            {"name": "Benar News",              "url": "https://www.benarnews.org/english/rss.xml"},
            {"name": "South China Morning Post","url": "https://www.scmp.com/rss/4/feed"},
            {"name": "The Diplomat",            "url": "https://thediplomat.com/feed/"},
        ],
    },
    "security": {
        "label": "Counter-terrorism & Organised Crime",
        "icon": "🔒",
        "color": "#b45309",
        "sea_filter": True,
        "keywords": [
            # Terrorism & extremism
            "terrorism", "terrorist", "extremism", "extremist", "radical",
            "radicalisation", "radicalization", "jihad", "jihadist",
            "isis", "daesh", "jemaah islamiyah", "abu sayyaf", "militan",
            # Organised crime
            "crime", "criminal", "organised crime", "syndicate", "cartel", "gang",
            # Trafficking
            "trafficking", "human trafficking", "drug trafficking", "smuggling",
            # Drugs
            "drug", "narcotics", "methamphetamine", "syabu", "ecstasy",
            # Financial crime
            "money laundering", "corruption", "bribery", "anti-corruption",
            "sprm", "macc", "graft",
            # Law enforcement
            "arrest", "raid", "seized", "detained", "remand", "charged",
            # Violence
            "bomb", "explosion", "attack", "militant", "insurgent",
            "kidnap", "ransom", "hostage",
            # Cybercrime
            "cybercrime", "scam", "fraud", "phishing", "mule account",
            "investment scam", "love scam",
            # Agencies
            "police", "pdrm", "interpol", "counter-terrorism", "cts",
        ],
        "sources": [
            {"name": "The Star Malaysia",   "url": "https://www.thestar.com.my/rss/news/nation"},
            {"name": "Malay Mail",          "url": "https://www.malaymail.com/feed"},
            {"name": "Free Malaysia Today", "url": "https://www.freemalaysiatoday.com/feed/"},
            {"name": "New Straits Times",   "url": "https://www.nst.com.my/rss/news"},
            {"name": "Channel NewsAsia",    "url": "https://www.channelnewsasia.com/rss/8395694"},
            {"name": "Benar News",          "url": "https://www.benarnews.org/english/rss.xml"},
            {"name": "RSIS",                "url": "https://www.rsis.edu.sg/feed/"},
            {"name": "The Diplomat",        "url": "https://thediplomat.com/feed/"},
        ],
    },
}


# ── Text helpers ───────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Strip HTML tags, decode common entities, normalise whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def url_hash(url: str) -> str:
    return hashlib.md5(url.strip().lower().encode()).hexdigest()[:12]


def contains_any(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


def is_sea_relevant(text: str) -> bool:
    return contains_any(text, list(SEA_KEYWORDS))


# ── Date helpers ───────────────────────────────────────────────────────────────

def parse_entry_date(entry) -> Optional[datetime]:
    """Extract UTC-aware datetime from a feedparser entry."""
    # Try struct_time fields first (already UTC)
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    # Try raw string fields
    for attr in ("published", "updated"):
        s = getattr(entry, attr, "")
        if s:
            try:
                dt = date_parser.parse(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    return None


def in_target_date(entry_dt: Optional[datetime], target: date) -> bool:
    """
    Return True if the article falls on `target` (in MYT UTC+8),
    OR if the article has no date at all (include by default).
    We also accept articles up to 1 day in the past to handle timezone gaps.
    """
    if entry_dt is None:
        return True
    myt_date = entry_dt.astimezone(MYT).date()
    utc_date = entry_dt.date()
    # Accept if MYT date or UTC date matches, or is within 1 day before
    return myt_date >= (target - timedelta(days=1)) and myt_date <= target or \
           utc_date >= (target - timedelta(days=1)) and utc_date <= target


# ── RSS fetching ───────────────────────────────────────────────────────────────

def _extract_image(entry) -> Optional[str]:
    """Attempt to extract a thumbnail URL from common RSS media fields."""
    for attr in ("media_thumbnail", "media_content"):
        media = getattr(entry, attr, None)
        if isinstance(media, list) and media and media[0].get("url"):
            return media[0]["url"]
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("image"):
            return enc.get("href") or enc.get("url")
    # Try links
    for link in getattr(entry, "links", []):
        if link.get("type", "").startswith("image"):
            return link.get("href")
    return None


def fetch_feed(source: dict) -> list[dict]:
    """
    Fetch one RSS source. Returns a list of normalised article dicts.
    Never raises — returns [] on any failure.
    """
    name = source["name"]
    url = source["url"]
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as exc:
        log.warning("  ✗ Feed error [%s]: %s", name, exc)
        return []

    articles = []
    for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
        link = getattr(entry, "link", "") or ""
        if not link:
            continue

        # Build snippet from content > summary > description
        raw = ""
        if hasattr(entry, "content") and entry.content:
            raw = entry.content[0].get("value", "")
        if not raw:
            raw = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        snippet = clean_text(raw)[:700]

        articles.append({
            "id": url_hash(link),
            "title": clean_text(getattr(entry, "title", "No title")),
            "url": link,
            "source": name,
            "published_dt": parse_entry_date(entry),
            "snippet": snippet,
            "image": _extract_image(entry),
        })

    log.info("  ✓ [%s] %d entries fetched", name, len(articles))
    return articles


# ── Article text extraction ────────────────────────────────────────────────────

def extract_article_text(url: str, fallback: str) -> str:
    """
    Attempt to retrieve and parse the full article page.
    Returns up to 1500 chars of main content, or `fallback` on failure.
    """
    if len(fallback) >= 500:
        return fallback  # Already enough context

    try:
        resp = requests.get(
            url, headers=HEADERS, timeout=FETCH_TIMEOUT, allow_redirects=True
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove noise elements
        for el in soup(["script", "style", "nav", "header", "footer",
                        "aside", "form", "noscript", "iframe"]):
            el.decompose()

        # Try semantic article containers
        selectors = [
            "article", "[role='main']", "main",
            ".article-body", ".article-content", ".post-content",
            ".entry-content", ".story-body", ".story-content",
            ".content-body", "#article-body",
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                text = clean_text(el.get_text(separator=" "))
                if len(text) > 300:
                    return text[:1500]

        # Fallback: collect <p> tags
        paragraphs = " ".join(
            p.get_text() for p in soup.find_all("p") if len(p.get_text()) > 50
        )
        text = clean_text(paragraphs)
        if len(text) > 200:
            return text[:1500]

    except Exception:
        pass  # Silent fallback

    return fallback


# ── AI summarisation ───────────────────────────────────────────────────────────

def summarise_article(client: Anthropic, article: dict) -> str:
    """
    Generate a 2–3 sentence factual summary of an article.
    Returns the snippet as fallback on any error.
    """
    title = article["title"]
    body = article.get("full_text") or article["snippet"]
    if not body:
        return article["snippet"][:280]

    prompt = (
        f"Summarise this news article in 2–3 concise, factual sentences. "
        f"Be neutral and objective. Write only the summary — no preamble, no labels.\n\n"
        f"Title: {title}\n\n"
        f"Content: {body[:1200]}"
    )

    try:
        resp = client.messages.create(
            model=ARTICLE_MODEL,
            max_tokens=220,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        log.warning("  ✗ Summary error for '%s': %s", title[:50], exc)
        return article["snippet"][:280]


def generate_briefing(client: Anthropic, cat_label: str, articles: list[dict]) -> str:
    """
    Generate a daily editorial briefing paragraph for a category.
    """
    if not articles:
        return "No articles found for this category today."

    headlines = "\n".join(
        f"- {a['title']}" for a in articles[:25]
    )

    prompt = (
        f'You are a senior editor writing the daily briefing for the "{cat_label}" section '
        f"of a Malaysia-focused news digest.\n\n"
        f"Today's headlines:\n{headlines}\n\n"
        f"Write a 3–5 sentence editorial briefing that:\n"
        f"1. Identifies the dominant theme or most significant story\n"
        f"2. Notes any notable trends or patterns\n"
        f"3. Gives readers a quick, informed overview\n\n"
        f"Write only the briefing text — no headlines, no bullet points, no preamble."
    )

    try:
        resp = client.messages.create(
            model=BRIEFING_MODEL,
            max_tokens=380,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        log.warning("  ✗ Briefing error for %s: %s", cat_label, exc)
        return f"Today's {cat_label} section covers {len(articles)} stories."


# ── Scraping orchestration ─────────────────────────────────────────────────────

def scrape_category(
    cat_id: str,
    cat: dict,
    target: date,
    no_fetch: bool,
) -> list[dict]:
    """
    Fetch all sources for a category, apply filters, and deduplicate.
    Returns a sorted, limited list of article dicts.
    """
    log.info("▶ Scraping: %s", cat["label"])
    seen_ids: set[str] = set()
    results: list[dict] = []

    for source in cat["sources"]:
        entries = fetch_feed(source)
        for entry in entries:
            art_id = entry["id"]
            if art_id in seen_ids:
                continue
            seen_ids.add(art_id)

            # Date filter
            if not in_target_date(entry["published_dt"], target):
                continue

            combined_text = f"{entry['title']} {entry['snippet']}"

            # Geo-filter for SEA categories
            if cat["sea_filter"] and not is_sea_relevant(combined_text):
                continue

            # Keyword filter
            if cat["keywords"] and not contains_any(combined_text, cat["keywords"]):
                continue

            results.append(entry)

        time.sleep(CRAWL_DELAY)

    # Sort newest-first (undated articles go to end)
    results.sort(
        key=lambda a: a["published_dt"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    results = results[:MAX_ARTICLES_PER_CATEGORY]
    log.info("  → %d articles after filtering", len(results))

    # Optionally fetch full article text for better AI summaries
    if not no_fetch and results:
        log.info("  Fetching article pages...")
        for i, art in enumerate(results):
            art["full_text"] = extract_article_text(art["url"], art["snippet"])
            log.debug("    [%d/%d] %s", i + 1, len(results), art["url"][:70])
            time.sleep(CRAWL_DELAY)

    return results


def build_category_output(
    cat_id: str,
    cat: dict,
    articles: list[dict],
    client: Optional[Anthropic],
    no_summarize: bool,
) -> dict:
    """
    Build the JSON-serialisable structure for one category.
    Calls AI summarisation if a client is available.
    """
    processed = []
    for art in articles:
        summary = ""
        if client and not no_summarize:
            summary = summarise_article(client, art)
            time.sleep(0.25)  # gentle rate-limit buffer

        published_iso = (
            art["published_dt"].isoformat() if art["published_dt"] else None
        )
        processed.append({
            "id": art["id"],
            "title": art["title"],
            "url": art["url"],
            "source": art["source"],
            "published": published_iso,
            "summary": summary or art["snippet"][:280],
            "image": art.get("image"),
        })

    # Daily briefing
    briefing = ""
    if client and not no_summarize and articles:
        log.info("  Generating briefing for %s...", cat["label"])
        briefing = generate_briefing(client, cat["label"], articles)

    return {
        "id": cat_id,
        "label": cat["label"],
        "icon": cat["icon"],
        "color": cat["color"],
        "article_count": len(processed),
        "briefing": briefing,
        "articles": processed,
    }


# ── Index management ───────────────────────────────────────────────────────────

def update_index(date_str: str) -> None:
    """Add `date_str` to data/index.json and record the latest date."""
    index_path = DATA_DIR / "index.json"
    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
    else:
        index = {"dates": [], "latest": None, "updated": None}

    dates: list[str] = index.get("dates", [])
    if date_str not in dates:
        dates.append(date_str)
    dates.sort(reverse=True)
    index["dates"] = dates[:120]   # keep up to 4 months
    index["latest"] = dates[0]
    index["updated"] = datetime.now(timezone.utc).isoformat()

    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    log.info("Index updated: %d dates available", len(dates))


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Malaysia & SEA News Aggregator — Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--date",
        default=datetime.now(MYT).strftime("%Y-%m-%d"),
        metavar="YYYY-MM-DD",
        help="Date to scrape (default: today in MYT)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape even if output file already exists",
    )
    parser.add_argument(
        "--no-summarize",
        action="store_true",
        help="Skip AI summarisation (no ANTHROPIC_API_KEY needed)",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip fetching full article pages (faster, uses only RSS snippets)",
    )
    parser.add_argument(
        "--categories",
        default="all",
        metavar="CAT,...",
        help="Comma-separated list of categories to scrape: tech,society,security (default: all)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── Parse target date ──────────────────────────────────────────────────────
    try:
        target_date = date.fromisoformat(args.date)
    except ValueError:
        log.error("Invalid date '%s' — expected YYYY-MM-DD", args.date)
        sys.exit(1)

    date_str = target_date.isoformat()
    output_path = DATA_DIR / f"{date_str}.json"

    log.info("Target date: %s  |  Output: %s", date_str, output_path)

    if output_path.exists() and not args.force:
        log.info("Data already exists. Pass --force to re-scrape.")
        sys.exit(0)

    # ── Set up Anthropic client ────────────────────────────────────────────────
    client: Optional[Anthropic] = None
    if not args.no_summarize:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            client = Anthropic(api_key=api_key)
            log.info("AI summarisation enabled (model: %s / %s)", ARTICLE_MODEL, BRIEFING_MODEL)
        else:
            log.warning("ANTHROPIC_API_KEY not set — running without AI summarisation")

    # ── Resolve categories ─────────────────────────────────────────────────────
    if args.categories == "all":
        cats_to_run = list(CATEGORIES.keys())
    else:
        cats_to_run = [c.strip() for c in args.categories.split(",") if c.strip()]
        unknown = [c for c in cats_to_run if c not in CATEGORIES]
        if unknown:
            log.error("Unknown categories: %s  (valid: %s)", unknown, list(CATEGORIES))
            sys.exit(1)

    # ── Scrape ─────────────────────────────────────────────────────────────────
    output: dict = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": {},
    }

    for cat_id in cats_to_run:
        cat = CATEGORIES[cat_id]
        articles = scrape_category(cat_id, cat, target_date, no_fetch=args.no_fetch)
        output["categories"][cat_id] = build_category_output(
            cat_id, cat, articles, client, args.no_summarize
        )

    # ── Save output ────────────────────────────────────────────────────────────
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    log.info("✅ Saved: %s", output_path)

    # ── Update index ───────────────────────────────────────────────────────────
    update_index(date_str)
    log.info("🎉 Done!")


if __name__ == "__main__":
    main()
