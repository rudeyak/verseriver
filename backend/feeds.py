"""
RSS feed parsing and source discovery.
"""
import re
import httpx
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime

from backend.scraper import scrape_poem, HEADERS, TIMEOUT

# Known RSS feed URLs for sources that don't advertise them well
RSS_OVERRIDES = {
    "apoemaday.tumblr.com": "https://apoemaday.tumblr.com/rss",
    "havingapoemwithyou.tumblr.com": "https://havingapoemwithyou.tumblr.com/rss",
    "firstfullmoon.tumblr.com": "https://firstfullmoon.tumblr.com/rss",
    "dreaminginthedeepsouth.tumblr.com": "https://dreaminginthedeepsouth.tumblr.com/rss",
    "ginevrakirkland.blog": "https://ginevrakirkland.blog/rss",
    "readalittlepoetry.com": "https://readalittlepoetry.com/feed/",
    "poets.org": "https://poets.org/feed/poem-a-day",
    "poetryfoundation.org": "https://www.poetryfoundation.org/rss/poems",
    "themarginalian.org": "https://www.themarginalian.org/feed/",
    "onbeing.org": "https://onbeing.org/feed/",
    "slowdownshow.org": "https://feeds.simplecast.com/72FGCot2",
    "bestamericanpoetry.com": "https://blog.bestamericanpoetry.com/the_best_american_poetry/atom.xml",
    "lithub.com": "https://lithub.com/category/fictionandpoetry/poem/feed/",
    "guernicamag.com": "https://www.guernicamag.com/format/poetry/feed/",
    "yalereview.org": "https://yalereview.org/poem-of-the-week/rss",
    "thecommononline.org": "https://www.thecommononline.org/category/poetry/feed/",
    "newyorker.com": "https://www.newyorker.com/feed/poetry",
}


def discover_rss(site_url: str) -> str | None:
    """Try to find an RSS feed URL for a given site."""
    domain = urlparse(site_url).netloc.replace("www.", "")

    # Check overrides first
    for key, rss in RSS_OVERRIDES.items():
        if key in domain:
            return rss

    # Try common paths
    candidates = [
        urljoin(site_url, "/feed/"),
        urljoin(site_url, "/rss"),
        urljoin(site_url, "/rss.xml"),
        urljoin(site_url, "/atom.xml"),
        urljoin(site_url, "/feed.xml"),
    ]

    try:
        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            # Check <link rel="alternate"> in the page HTML
            r = client.get(site_url)
            soup = BeautifulSoup(r.text, "lxml")
            for link in soup.find_all("link", rel="alternate"):
                t = link.get("type", "")
                if "rss" in t or "atom" in t:
                    href = link.get("href", "")
                    if href:
                        return urljoin(site_url, href)

            # Try candidates
            for url in candidates:
                try:
                    resp = client.get(url)
                    ct = resp.headers.get("content-type", "")
                    if resp.status_code == 200 and ("xml" in ct or "rss" in ct or "atom" in ct):
                        return url
                except Exception:
                    continue
    except Exception:
        pass

    return None


def parse_feed(rss_url: str) -> list[dict]:
    """
    Fetch and parse an RSS/Atom feed.
    Returns list of dicts with: url, title, author, text, published_date, source_name
    """
    feed = feedparser.parse(rss_url, request_headers={"User-Agent": HEADERS["User-Agent"]})
    items = []

    for entry in feed.entries:
        url = entry.get("link", "")
        if not url:
            continue

        title = entry.get("title", "").strip()
        author = entry.get("author", "").strip()

        # Try to get poem text from the feed content itself
        text = ""
        content = entry.get("content", [])
        summary = entry.get("summary", "")

        raw_html = ""
        if content:
            raw_html = content[0].get("value", "")
        elif summary:
            raw_html = summary

        if raw_html:
            soup = BeautifulSoup(raw_html, "lxml")
            for br in soup.find_all("br"):
                br.replace_with("\n")
            for p in soup.find_all("p"):
                p.append("\n\n")
            text = soup.get_text().strip()

        # Published date
        published = ""
        if entry.get("published_parsed"):
            try:
                dt = datetime(*entry.published_parsed[:6])
                published = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        source_name = feed.feed.get("title", urlparse(rss_url).netloc)

        items.append({
            "url": url,
            "title": title,
            "author": author,
            "text": text if len(text) > 50 else "",  # discard tiny snippets
            "published_date": published,
            "source_name": source_name,
            "source_url": f"{urlparse(rss_url).scheme}://{urlparse(rss_url).netloc}",
            "scrape_status": "done" if len(text) > 50 else "pending",
        })

    return items


def refresh_source(source: dict) -> list[dict]:
    """
    Fetch new poems from a source. Returns list of poem dicts.
    Uses RSS if available, otherwise a basic scrape of the source URL.
    """
    rss_url = source.get("rss_url") or discover_rss(source["url"])

    if rss_url:
        try:
            poems = parse_feed(rss_url)
            return poems
        except Exception as e:
            print(f"Feed error for {source['url']}: {e}")

    # No RSS — could add page scraping per-site here
    return []


def classify_url(url: str) -> str:
    """
    Heuristically classify a URL as 'poem' or 'source'.
    Sources are root/category pages; poems are specific content pages.
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    domain = parsed.netloc.replace("www.", "")

    # Explicit source URL patterns
    SOURCE_PATTERNS = [
        r"^$",                               # root
        r"^/poem-a-day/?$",
        r"^/poetrymagazine/?$",
        r"^/fiction-and-poetry/?$",
        r"^/category/",
        r"^/format/",
        r"^/poetry/?$",
        r"^/archives?",
        r"^/issues?/?$",
    ]
    for pattern in SOURCE_PATTERNS:
        if re.search(pattern, path):
            return "source"

    # Tumblr root (no post ID in path)
    if "tumblr.com" in domain and re.match(r"^/?$", path):
        return "source"

    # Short paths with no slug depth suggest index pages
    parts = [p for p in path.split("/") if p]
    if len(parts) <= 1 and not any(c.isdigit() for c in path):
        return "source"

    return "poem"
