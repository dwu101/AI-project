import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag, urlunparse, parse_qs
from collections import deque
from datetime import datetime, timezone
import json
import gzip
import os
import xml.etree.ElementTree as ET

import yt_dlp  # pip install yt-dlp

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "*/*",
}


def safe_get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return ""


def extract_youtube_id(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "youtube.com" in host:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1]
    if "youtu.be" in host:
        return parsed.path.lstrip("/")
    return None


def get_youtube_transcription(url):
    """
    Uses yt-dlp to reliably fetch YouTube captions (auto-generated or manual)
    Works for all URL types: watch?v=, embed/, shorts/, youtu.be
    """
    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "vtt",
        "quiet": True,
        "nocheckcertificate": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"  ✗ yt-dlp failed for {url}: {e}")
            return None

        subtitles = info.get("subtitles") or {}
        auto_subs = info.get("automatic_captions") or {}

        # Prefer auto-generated English
        sub_url = None
        if "en" in auto_subs:
            sub_url = auto_subs["en"][0]["url"]
        elif "en" in subtitles:
            sub_url = subtitles["en"][0]["url"]

        if sub_url:
            r = requests.get(sub_url)
            if r.ok:
                lines = []
                for line in r.text.splitlines():
                    line = line.strip()
                    if line and not line[0].isdigit() and "-->" not in line:
                        lines.append(line)
                return " ".join(lines)
    return None


IGNORED_SCHEMES = {"mailto", "javascript", "tel", "data", ""}


def normalize_url(raw_url, base_for_join=None):
    if base_for_join:
        raw_url = urljoin(base_for_join, raw_url)
    nofrag, _ = urldefrag(raw_url)
    parsed = urlparse(nofrag)
    if parsed.scheme and parsed.scheme.lower() not in ("http", "https"):
        return None
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    if ":" in netloc:
        host, port = netloc.split(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    new_parsed = parsed._replace(
        scheme=scheme, netloc=netloc, path=path, params="", query=parsed.query, fragment=""
    )
    return urlunparse(new_parsed)


def extract_links_from_soup(soup, current_url):
    links = set()
    base_tag = soup.find('base', href=True)
    base_for_join = base_tag['href'] if base_tag else current_url
    candidates = []
    candidates.extend(soup.find_all('a', href=True))
    candidates.extend(soup.find_all('area', href=True))
    candidates.extend(soup.find_all('link', href=True))
    candidates.extend(soup.find_all('iframe', src=True))
    candidates.extend(soup.find_all('frame', src=True))
    image_candidates = soup.find_all('img', src=True)

    for tag in candidates:
        raw = tag.get('href') or tag.get('src')
        if not raw:
            continue
        parsed = urlparse(raw)
        if parsed.scheme and parsed.scheme.lower() in IGNORED_SCHEMES:
            continue
        normalized = normalize_url(raw, base_for_join=base_for_join)
        if normalized:
            links.add(normalized)

    for img in image_candidates:
        src = img.get('src')
        if not src:
            continue
        _normalized = normalize_url(src, base_for_join=base_for_join)
        pass  # Placeholder for future image logic

    return links


def get_visible_text_without_mutation(soup):
    temp = BeautifulSoup(str(soup), 'html.parser')
    for element in temp.find_all(['header', 'footer', 'script', 'style', 'nav', 'noscript', 'meta', 'link']):
        element.decompose()
    body = temp.find('body')
    text = body.get_text(separator=' ', strip=True) if body else temp.get_text(separator=' ', strip=True)
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return ' '.join(chunk for chunk in chunks if chunk)


def scrape_and_store_locally(start_url, base_domain="https://pantelis.github.io",
                             max_pages=None, output_file="scraped_pages.json.gz"):
    parsed_base = urlparse(base_domain)
    base_netloc = parsed_base.netloc.lower()
    internal_links = set()
    queue = deque([normalize_url(start_url)])
    visited = set()
    scraped_pages = []

    print(f"\nStarting scrape from: {start_url}")
    print(f"Looking for links within domain: {base_netloc}")
    if max_pages:
        print(f"Maximum pages to crawl: {max_pages}")
    print()

    pages_crawled = 0
    pages_stored = 0
    session = requests.Session()
    session.headers.update({'User-Agent': HEADERS["User-Agent"]})

    while queue:
        if max_pages and pages_crawled >= max_pages:
            print(f"\nReached maximum page limit ({max_pages})")
            break

        current_url = queue.popleft()
        if not current_url or current_url in visited:
            continue
        visited.add(current_url)
        pages_crawled += 1
        print(f"[{pages_crawled}] Crawling: {current_url}")

        try:
            resp = session.get(current_url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            youtube_transcription = None

            found_links = extract_links_from_soup(soup, current_url)
            new_internal_count = 0
            for link in found_links:
                parsed_link = urlparse(link)
                if parsed_link.netloc == base_netloc:
                    if link not in internal_links:
                        internal_links.add(link)
                        new_internal_count += 1
                    if link not in visited and link not in queue:
                        queue.append(link)
                else:  # Capture YouTube links
                    if "youtube.com" in parsed_link.netloc or "youtu.be" in parsed_link.netloc:
                        print(f"\n\nFOUND YOUTUBE: {link}\n\n")
                        youtube_transcription = get_youtube_transcription(link)
                        print(f"TRANSCRIPTION IS {youtube_transcription}\n\n")

            visible_text = youtube_transcription if youtube_transcription else get_visible_text_without_mutation(soup)

            page_document = {
                'url': current_url,
                'text': visible_text,
                'text_length': len(visible_text),
                'scraped_at': datetime.now(timezone.utc).isoformat(),
                'domain': base_domain
            }
            scraped_pages.append(page_document)
            pages_stored += 1
            print(f"  ✓ Stored locally (text length: {len(visible_text)})")
            print(f"  → Found {len(found_links)} total link candidates, {new_internal_count} new internal")

        except requests.RequestException as e:
            print(f"  ✗ Error fetching {current_url}: {e}")
            continue
        except Exception as e:
            print(f"  ✗ Error processing {current_url}: {e}")
            continue

    try:
        if output_file.endswith('.gz'):
            with gzip.open(output_file, 'wt', encoding='utf-8') as f:
                json.dump(scraped_pages, f, indent=2, ensure_ascii=False)
        else:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(scraped_pages, f, indent=2, ensure_ascii=False)
        file_size = os.path.getsize(output_file)
        print(f"✓ Data saved to {output_file} ({file_size:,} bytes)")
    except Exception as e:
        print(f"✗ Error saving file: {e}")

    return internal_links, pages_stored


def load_scraped_data(input_file="scraped_pages.json.gz"):
    try:
        if input_file.endswith('.gz'):
            with gzip.open(input_file, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        else:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        print(f"✓ Loaded {len(data)} pages from {input_file}")
        return data
    except Exception as e:
        print(f"✗ Error loading file: {e}")
        return []


if __name__ == "__main__":
    start_url = "https://pantelis.github.io/courses/ai/in-person.html"
    OUTPUT_FILE = "scraped_pages.json.gz"

    all_links, stored_count = scrape_and_store_locally(
        start_url=start_url,
        output_file=OUTPUT_FILE
    )

    print("\n" + "="*80)
    print(f"SCRAPING COMPLETE!")
    print(f"Total internal links found: {len(all_links)}")
    print(f"Total pages stored: {stored_count}")
    print("="*80)

    with open('internal_links.txt', 'w') as f:
        f.write(f"Total links found: {len(all_links)}\n")
        f.write(f"Total pages stored: {stored_count}\n\n")
        for link in sorted(all_links):
            f.write(f"{link}\n")

    print(f"\nLinks saved to: internal_links.txt")
    print(f"Page content stored in: {OUTPUT_FILE}")

    loaded_data = load_scraped_data(OUTPUT_FILE)
    if loaded_data:
        print(f"First page URL: {loaded_data[0]['url']}")
        print(f"First page text preview: {loaded_data[0]['text'][:100]}...")
