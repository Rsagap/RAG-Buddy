"""
scrape.py — Smart PortSwigger Academy Scraper
=============================================
Automatically discovers and scrapes ALL pages under a topic:
  - Main topic page        e.g. /web-security/sql-injection
  - Sub-topic pages        e.g. /web-security/sql-injection/union-attacks
  - Lab pages              e.g. /web-security/sql-injection/union-attacks/lab-find-column
  - Cheat sheets           e.g. /web-security/sql-injection/cheat-sheet

How it works:
  1. Scrapes the topic root page
  2. Reads the LEFT SIDEBAR — which has the full topic tree
  3. Follows every link that belongs to the same topic
  4. Saves each page as a clean .md file (nav/header/footer stripped)

Run:
  pip install requests beautifulsoup4
  python scrape.py
"""

import requests
import os
import time
import re
from bs4 import BeautifulSoup


# ─── CONFIG ──────────────────────────────────────────────────────────────────

TOPIC_ROOTS = [
    "https://portswigger.net/web-security/sql-injection",
    # Uncomment to add more topics:
    # "https://portswigger.net/web-security/cross-site-scripting",
    # "https://portswigger.net/web-security/csrf",
    # "https://portswigger.net/web-security/ssrf",
    # "https://portswigger.net/web-security/os-command-injection",
]

OUTPUT_DIR = "docs"      # Folder where .md files are saved
SLEEP_SEC  = 1.5         # Pause between requests — don't hammer the server
TIMEOUT    = 15          # Request timeout in seconds

# Full browser-like headers — needed to avoid 403 from Cloudflare
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def fetch_page(session: requests.Session, url: str) -> BeautifulSoup | None:
    """Download a page and return BeautifulSoup, or None on failure."""
    try:
        # Add Referer to look like normal browser navigation
        hdrs = {**HEADERS, "Referer": "https://portswigger.net/web-security"}
        resp = session.get(url, headers=hdrs, timeout=TIMEOUT)
        if resp.status_code == 200:
            return BeautifulSoup(resp.text, "html.parser")
        else:
            print(f"    ✗ HTTP {resp.status_code} — {url}")
            return None
    except Exception as e:
        print(f"    ✗ Error fetching {url}: {e}")
        return None


def discover_links(soup: BeautifulSoup, topic_prefix: str) -> list[str]:
    """
    Find all sub-page links that belong to this topic.

    PortSwigger's left sidebar is the table-of-contents for a topic.
    It contains links to ALL sub-topics and ALL labs in the correct order.
    We collect every link whose URL starts with the topic root URL.

    Example for sql-injection topic, we keep:
      /web-security/sql-injection/union-attacks         ← sub-topic
      /web-security/sql-injection/union-attacks/lab-xyz ← lab
      /web-security/sql-injection/cheat-sheet           ← cheat sheet

    We skip:
      /web-security/xss          ← different topic
      /web-security/sql-injection#section  ← just an anchor, not a new page
    """
    found = []
    seen  = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Make absolute
        if href.startswith("/"):
            href = "https://portswigger.net" + href

        # Only keep portswigger.net links
        if not href.startswith("https://portswigger.net"):
            continue

        # Strip #anchor fragments — we want page URLs only
        href = href.split("#")[0].rstrip("/")

        # Must be inside our topic tree
        if not href.startswith(topic_prefix):
            continue

        # Skip the root itself (we already have it)
        if href == topic_prefix:
            continue

        if href not in seen:
            seen.add(href)
            found.append(href)

    return found


def discover_all_pages(session: requests.Session, topic_root: str):
    """Recursively discover all pages under `topic_root` by following links
    found on each page, as long as they start with the topic prefix.

    Returns a tuple: (ordered_list_of_urls, dict(url -> BeautifulSoup))
    """
    topic_prefix = topic_root.rstrip("/")
    seen = set()
    order = []
    soups = {}

    # BFS queue starting at the topic root
    queue = [topic_prefix]
    seen.add(topic_prefix)
    order.append(topic_prefix)

    # Also try to seed from sitemap (helps find lab pages not present in static HTML)
    try:
        sitemap_url = 'https://portswigger.net/sitemap.xml'
        r = session.get(sitemap_url, timeout=10, headers=HEADERS)
        if r.status_code == 200 and r.text:
            # simple regex to extract <loc>...</loc>
            import re as _re
            locs = _re.findall(r'<loc>(.*?)</loc>', r.text)
            for loc in locs:
                if loc.startswith(topic_prefix) and loc not in seen:
                    seen.add(loc)
                    order.append(loc)
                    queue.append(loc)
    except Exception:
        pass

    while queue:
        url = queue.pop(0)
        soup = fetch_page(session, url)
        if not soup:
            continue
        soups[url] = soup

        # Find links from this page that belong to the topic
        for href in discover_links(soup, topic_prefix):
            if href not in seen:
                seen.add(href)
                order.append(href)
                queue.append(href)

        # Be polite between discovery requests
        if url != topic_prefix:
            time.sleep(SLEEP_SEC)

    return order, soups


def page_type(url: str) -> str:
    """Classify the page type for metadata tagging."""
    if "/lab-" in url:
        return "LAB"
    if "cheat-sheet" in url:
        return "CHEAT_SHEET"
    return "THEORY"


def url_to_filename(url: str, topic_prefix: str) -> str:
    """
    Convert URL → safe flat filename that reflects the hierarchy.

    /web-security/sql-injection                          → index.md
    /web-security/sql-injection/union-attacks            → union-attacks.md
    /web-security/sql-injection/union-attacks/lab-xyz    → union-attacks__lab-xyz.md
    """
    path = url.replace(topic_prefix, "").strip("/")
    if not path:
        return "index.md"
    safe = path.replace("/", "__")
    safe = re.sub(r"[^\w\-]", "-", safe)
    return f"{safe}.md"


def html_to_markdown(soup: BeautifulSoup, url: str) -> str:
    """
    Strip all chrome (nav, header, footer, sidebars, ads).
    Convert the article body to clean readable markdown.
    Preserves: headings, paragraphs, lists, code blocks, tables.
    """

    # ── Remove everything that isn't article content ──────────────────────
    noise = [
        "nav", "header", "footer",
        "script", "style", "noscript",
        ".breadcrumb", ".cookie-bar",
        "[class*='nav']", "[class*='header']", "[class*='footer']",
        "[class*='sidebar']", "[class*='widget']",
        "[class*='banner']", "[class*='promo']",
    ]
    for sel in noise:
        for tag in soup.select(sel):
            tag.decompose()

    # ── Find the main content ─────────────────────────────────────────────
    content = (
        soup.find("main")
        or soup.find("article")
        or soup.find("section", class_=re.compile(r"content|article|main", re.I))
        or soup.find("body")
    )

    if not content:
        return ""

    lines = []

    def add(text: str):
        if text and text.strip():
            lines.append(text)

    # ── Walk the DOM and convert tags to markdown ─────────────────────────
    # We iterate top-level children so we don't double-process nested tags
    def walk(node):
        if not hasattr(node, "name") or node.name is None:
            return  # text node — handled by parent

        tag = node.name

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            text  = node.get_text(" ", strip=True)
            add(f"\n{'#' * level} {text}\n")

        elif tag == "p":
            text = node.get_text(" ", strip=True)
            add(f"\n{text}\n")

        elif tag in ("ul", "ol"):
            add("")
            for li in node.find_all("li", recursive=False):
                text = li.get_text(" ", strip=True)
                add(f"- {text}")
            add("")

        elif tag == "pre":
            # Code blocks — the most important thing for a hacking companion!
            code = node.get_text()
            add(f"\n```\n{code.strip()}\n```\n")

        elif tag == "blockquote":
            text = node.get_text(" ", strip=True)
            add(f"\n> {text}\n")

        elif tag == "table":
            rows = []
            for tr in node.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
                rows.append("| " + " | ".join(cells) + " |")
            if rows:
                sep = "| " + " | ".join(["---"] * (rows[0].count("|") - 1)) + " |"
                rows.insert(1, sep)
                add("\n" + "\n".join(rows) + "\n")

        else:
            # For div/section/span/etc — recurse into children
            for child in node.children:
                walk(child)

    for child in content.children:
        walk(child)

    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)   # collapse excess blank lines
    return result.strip()


# ─── MAIN ────────────────────────────────────────────────────────────────────

def scrape_topic(session: requests.Session, topic_root: str):
    topic_root = topic_root.rstrip("/")
    topic_name = topic_root.split("/")[-1]
    topic_dir  = os.path.join(OUTPUT_DIR, topic_name)
    os.makedirs(topic_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  TOPIC : {topic_name}")
    print(f"  URL   : {topic_root}")
    print(f"  SAVING: ./{topic_dir}/")
    print(f"{'='*60}")

    # Step 1: Fetch root page
    print("\n[1/3] Fetching root page...")
    root_soup = fetch_page(session, topic_root)
    if not root_soup:
        print("  ERROR: Cannot access root page. Check your internet connection.")
        return

    # Step 2: Discover all sub-pages (recursively)
    print("[2/3] Discovering all sub-pages (recursive)...")
    all_urls, soups = discover_all_pages(session, topic_root)

    print(f"  Found {len(all_urls)} pages:\n")
    for u in all_urls:
        ptype = page_type(u)
        short = u.replace("https://portswigger.net", "")
        label = {"LAB": "LAB       ", "CHEAT_SHEET": "CHEAT_SHEET", "THEORY": "THEORY    "}[ptype]
        print(f"    {label}  {short}")

    # Step 3: Scrape each page
    print(f"\n[3/3] Scraping {len(all_urls)} pages...\n")
    saved  = 0
    failed = []

    for i, url in enumerate(all_urls, 1):
        short    = url.replace("https://portswigger.net", "")
        ptype    = page_type(url)
        filename = url_to_filename(url, topic_root)
        filepath = os.path.join(topic_dir, filename)

        print(f"  [{i:02d}/{len(all_urls)}] {short}")

        # Skip already-scraped pages (safe to re-run)
        if os.path.exists(filepath):
            print(f"          -> Already saved, skipping.\n")
            saved += 1
            continue

        # Reuse soup fetched during discovery when available to avoid double requests
        if 'soups' in locals() and url in soups:
            soup = soups[url]
        else:
            soup = root_soup if url == topic_root else fetch_page(session, url)
        if not soup:
            failed.append(url)
            continue

        # Convert to markdown
        md = html_to_markdown(soup, url)
        if not md.strip():
            print(f"          -> WARN No content extracted.\n")
            failed.append(url)
            continue

        # Write file with YAML frontmatter (LlamaIndex uses this as metadata)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(
                f"---\n"
                f"source: {url}\n"
                f"topic: {topic_name}\n"
                f"type: {ptype}\n"
                f"---\n\n"
                + md
            )

        print(f"          -> OK {filename}\n")
        saved += 1

        # Only sleep if we had to fetch this page just now (not reused from discovery)
        if url != topic_root and not ('soups' in locals() and url in soups):
            time.sleep(SLEEP_SEC)   # be polite

    # Summary
    print(f"\n  OK {saved}/{len(all_urls)} pages saved to ./{topic_dir}/")
    if failed:
        print(f"  ERROR {len(failed)} failed:")
        for f in failed:
            print(f"      {f}")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("+------------------------------------------+")
    print("|  PortSwigger Academy Scraper             |")
    print("+------------------------------------------+")
    print(f"\nOutput  : ./{OUTPUT_DIR}/")
    print(f"Topics  : {len(TOPIC_ROOTS)}")
    print(f"Sleep   : {SLEEP_SEC}s between requests")

    # Use a Session so cookies/headers persist across requests
    session = requests.Session()

    for topic_url in TOPIC_ROOTS:
        scrape_topic(session, topic_url)
        time.sleep(2)

    print("\n\nAll done!")
    print(f"   Your docs are in ./{OUTPUT_DIR}/")
    print(f"   Next step -> python ingest.py")