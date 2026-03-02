"""
Poem text extraction from URLs.
Strategy: site-specific extractor first, then trafilatura fallback.
"""
import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 20


def fetch_html(url: str) -> tuple[str, str]:
    """Returns (html, final_url) following redirects."""
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text, str(r.url)


def clean_text(text: str) -> str:
    """Normalize whitespace while preserving line structure."""
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]
    # Collapse runs of 3+ blank lines to 2
    result = []
    blanks = 0
    for line in lines:
        if line.strip() == "":
            blanks += 1
            if blanks <= 2:
                result.append("")
        else:
            blanks = 0
            result.append(line)
    return "\n".join(result).strip()


# --- Site-specific extractors ---

def extract_poetry_foundation(soup: BeautifulSoup) -> dict:
    data = {}
    # Title
    title_el = soup.select_one("h1.c-feature-hd, h1.o-kicker, .c-feature-hd h1")
    if title_el:
        data["title"] = title_el.get_text(strip=True)

    # Author
    author_el = soup.select_one(".c-feature-sub a, .c-feature-sub")
    if author_el:
        data["author"] = author_el.get_text(strip=True)

    # Poem text — try multiple selectors across their different layouts
    poem_el = soup.select_one(".o-poem, .c-feature-bd .o-poem, [class*='poem__body']")
    if not poem_el:
        poem_el = soup.select_one(".poem, .poem-body")
    if poem_el:
        # Preserve line breaks from <br> and <p>
        for br in poem_el.find_all("br"):
            br.replace_with("\n")
        for p in poem_el.find_all("p"):
            p.append("\n")
        data["text"] = clean_text(poem_el.get_text())

    return data


def extract_poets_org(soup: BeautifulSoup) -> dict:
    data = {}
    title_el = soup.select_one("h1.poem-page__title, h1.field--name-title, h1")
    if title_el:
        data["title"] = title_el.get_text(strip=True)

    author_el = soup.select_one(".poem-page__author a, .field--name-field-author a, .byline a")
    if author_el:
        data["author"] = author_el.get_text(strip=True)

    poem_el = soup.select_one(
        ".poem-page__poem-body, .field--name-body, "
        ".field--type-text-long, .poem__body"
    )
    if poem_el:
        for br in poem_el.find_all("br"):
            br.replace_with("\n")
        for p in poem_el.find_all("p"):
            p.append("\n")
        data["text"] = clean_text(poem_el.get_text())

    return data


def extract_tumblr(soup: BeautifulSoup) -> dict:
    data = {}
    # Post title sometimes in h1 or og:title
    og_title = soup.find("meta", property="og:title")
    if og_title:
        raw = og_title.get("content", "")
        # Tumblr og:title is often "Poem Title — Blog Name"; strip blog name
        data["title"] = raw.split(" — ")[0].split(" - ")[0].strip()

    # Poem text is in the post body
    post_el = soup.select_one(
        ".post-body, .body-text, .tmblr-full, "
        "article .body, .post .body, "
        "[data-body-length] > *"
    )
    if not post_el:
        # Fallback: main content area
        post_el = soup.select_one("article, main, .post")

    if post_el:
        # Remove interactive/nav elements
        for el in post_el.select("nav, footer, .post-controls, .reblog"):
            el.decompose()
        for br in post_el.find_all("br"):
            br.replace_with("\n")
        for p in post_el.find_all("p"):
            p.append("\n\n")
        data["text"] = clean_text(post_el.get_text())

    return data


def extract_waxwing(soup: BeautifulSoup) -> dict:
    data = {}
    title_el = soup.select_one("h1, h2.poem-title")
    if title_el:
        data["title"] = title_el.get_text(strip=True)

    author_el = soup.select_one(".author, .byline, h2 + p em, h3")
    if author_el:
        data["author"] = author_el.get_text(strip=True)

    # Waxwing uses a simple div or pre for poem content
    poem_el = soup.select_one("#poem-body, .poem, pre, .content p")
    if not poem_el:
        # Try the main column
        poem_el = soup.select_one("#column-right, .column, main, article")
    if poem_el:
        for br in poem_el.find_all("br"):
            br.replace_with("\n")
        data["text"] = clean_text(poem_el.get_text())

    return data


def extract_readalittlepoetry(soup: BeautifulSoup) -> dict:
    data = {}
    title_el = soup.select_one("h1.entry-title, h1.post-title, h1")
    if title_el:
        data["title"] = title_el.get_text(strip=True)

    # Author from title pattern "Poem Title by Author Name"
    if data.get("title") and " by " in data["title"]:
        parts = data["title"].rsplit(" by ", 1)
        data["title"] = parts[0].strip()
        data["author"] = parts[1].strip()

    poem_el = soup.select_one(".entry-content, .post-content, article")
    if poem_el:
        for br in poem_el.find_all("br"):
            br.replace_with("\n")
        for p in poem_el.find_all("p"):
            p.append("\n\n")
        data["text"] = clean_text(poem_el.get_text())

    return data


def extract_slowdown(soup: BeautifulSoup) -> dict:
    data = {}
    title_el = soup.select_one("h1.episode-title, h1")
    if title_el:
        data["title"] = title_el.get_text(strip=True)

    # The Slow Down embeds the poem in a transcript block
    poem_el = soup.select_one(".transcript, .episode-transcript, .poem-text, .content")
    if poem_el:
        for br in poem_el.find_all("br"):
            br.replace_with("\n")
        data["text"] = clean_text(poem_el.get_text())

    return data


def extract_generic_trafilatura(html: str) -> dict:
    """Fallback: use trafilatura for general extraction."""
    try:
        import trafilatura
        extracted = trafilatura.extract(
            html,
            include_formatting=True,
            include_links=False,
            no_fallback=False,
        )
        if extracted:
            return {"text": clean_text(extracted)}
    except Exception:
        pass
    return {}


def extract_metadata_from_soup(soup: BeautifulSoup) -> dict:
    """Pull title/author/date from og: and other common meta tags."""
    meta = {}

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        meta["title"] = og_title["content"].strip()

    og_author = (
        soup.find("meta", {"name": "author"})
        or soup.find("meta", property="article:author")
    )
    if og_author and og_author.get("content"):
        meta["author"] = og_author["content"].strip()

    pub_date = (
        soup.find("meta", property="article:published_time")
        or soup.find("meta", {"name": "date"})
        or soup.find("time")
    )
    if pub_date:
        dt = pub_date.get("content") or pub_date.get("datetime") or pub_date.get_text()
        if dt:
            meta["published_date"] = dt.strip()[:10]

    return meta


EXTRACTORS = {
    "poetryfoundation.org": extract_poetry_foundation,
    "poets.org": extract_poets_org,
    "tumblr.com": extract_tumblr,
    "waxwingmag.org": extract_waxwing,
    "readalittlepoetry.com": extract_readalittlepoetry,
    "slowdownshow.org": extract_slowdown,
}


def scrape_poem(url: str) -> dict:
    """
    Main entry point. Returns a dict with keys:
        title, author, text, source_name, source_url, published_date,
        scrape_status ('done' | 'error'), error_msg
    """
    result = {
        "url": url,
        "scrape_status": "error",
        "error_msg": None,
    }

    # Skip obviously non-scrapable URLs
    if url.endswith(".pdf"):
        result["error_msg"] = "PDF — manual entry required"
        return result
    if "instagram.com" in url:
        result["error_msg"] = "Instagram — cannot auto-scrape"
        return result

    try:
        html, final_url = fetch_html(url)
    except Exception as e:
        result["error_msg"] = f"Fetch error: {e}"
        return result

    soup = BeautifulSoup(html, "lxml")
    domain = urlparse(final_url).netloc.replace("www.", "")

    # Source info
    result["source_url"] = f"{urlparse(final_url).scheme}://{urlparse(final_url).netloc}"
    result["source_name"] = _source_name(domain)

    # Run site-specific extractor
    extractor = None
    for pattern, fn in EXTRACTORS.items():
        if pattern in domain:
            extractor = fn
            break

    extracted = extractor(soup) if extractor else {}

    # Fallback to trafilatura for missing text
    if not extracted.get("text"):
        extracted.update(extract_generic_trafilatura(html))

    # Fill gaps from og: meta
    og = extract_metadata_from_soup(soup)
    for key in ("title", "author", "published_date"):
        if not extracted.get(key) and og.get(key):
            extracted[key] = og[key]

    result.update(extracted)

    if result.get("text"):
        result["scrape_status"] = "done"
    else:
        result["error_msg"] = "Could not extract poem text"

    return result


def _source_name(domain: str) -> str:
    """Human-readable source name from domain."""
    mapping = {
        "poetryfoundation.org": "Poetry Foundation",
        "poets.org": "Poets.org",
        "tumblr.com": "Tumblr",
        "havingapoemwithyou.tumblr.com": "Having a Poem With You",
        "apoemaday.tumblr.com": "A Poem a Day",
        "waxwingmag.org": "Waxwing",
        "readalittlepoetry.com": "Read a Little Poetry",
        "slowdownshow.org": "The Slow Down",
        "scottishpoetrylibrary.org.uk": "Scottish Poetry Library",
        "newyorker.com": "The New Yorker",
        "yalereview.org": "Yale Review",
        "theparisreview.org": "The Paris Review",
        "guernicamag.com": "Guernica",
        "lithub.com": "Lit Hub",
        "onbeing.org": "On Being",
        "agnionline.bu.edu": "AGNI",
        "theadroitjournal.org": "The Adroit Journal",
        "northamericanreview.org": "North American Review",
        "swwim.org": "SWWIM",
        "themarginalian.org": "The Marginalian",
        "aprweb.org": "American Poetry Review",
        "poems.com": "Poems.com",
        "sixthfinch.com": "Sixth Finch",
        "verse.press": "Verse Press",
        "ciderpressreview.com": "Cider Press Review",
        "forwardartsfoundation.org": "Forward Arts Foundation",
        "thehtml.review": "The HTML Review",
        "thenorthmeridianreview.org": "The North Meridian Review",
        "expostmag.com": "Ex/Post Magazine",
        "granta.com": "Granta",
        "genius.com": "Genius",
        "mcsweeneys.net": "McSweeney's",
        "bestamericanpoetry.com": "Best American Poetry",
        "allpoetry.com": "All Poetry",
        "fsgworkinprogress.com": "FSG Work in Progress",
        "dailypoetry.me": "Daily Poetry",
        "blog.bestamericanpoetry.com": "Best American Poetry Blog",
    }
    for key, name in mapping.items():
        if key in domain:
            return name
    # Fallback: capitalise domain
    return domain.split(".")[0].replace("-", " ").title()
