import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag, urlunparse
from collections import deque
from datetime import datetime, timezone
import json
import gzip
import os

IGNORED_SCHEMES = {"mailto", "javascript", "tel", "data", ""}

def normalize_url(raw_url, base_for_join=None):
    """
    Normalize URLs:
      - resolve relative via urljoin when base_for_join provided
      - remove fragments
      - ensure scheme and netloc are lowercase
      - remove trailing slash except for root
    """
    if base_for_join:
        raw_url = urljoin(base_for_join, raw_url)

    # remove fragments
    nofrag, _ = urldefrag(raw_url)

    parsed = urlparse(nofrag)

    # ignore non-http(s) schemes
    if parsed.scheme and parsed.scheme.lower() not in ("http", "https"):
        return None

    scheme = parsed.scheme or "https"  # prefer https if not present
    netloc = parsed.netloc.lower()

    # remove default ports 80/443 if present
    if ":" in netloc:
        host, port = netloc.split(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host

    path = parsed.path or "/"
    # Normalize path: strip excess multiple slashes, but keep single trailing slash only for root
    if path != "/":
        path = path.rstrip("/")

    new_parsed = parsed._replace(scheme=scheme, netloc=netloc, path=path, params="", query=parsed.query, fragment="")
    normalized = urlunparse(new_parsed)
    return normalized

def extract_links_from_soup(soup, current_url, consider_tags=None):
    """
    Return a set of absolute URLs found in a BeautifulSoup object.
    Images are explicitly ignored, with an else block reserved for later logic.
    """
    links = set()

    # respect <base href="">
    base_tag = soup.find('base', href=True)
    base_for_join = base_tag['href'] if base_tag else current_url

    # Collect candidate elements
    candidates = []
    candidates.extend(soup.find_all('a', href=True))
    candidates.extend(soup.find_all('area', href=True))
    candidates.extend(soup.find_all('link', href=True))
    candidates.extend(soup.find_all('iframe', src=True))
    candidates.extend(soup.find_all('frame', src=True))

    # NOTE: keep images separate so we explicitly handle with an else block
    image_candidates = soup.find_all('img', src=True)

    # Process NORMAL link-bearing tags
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

    # Process IMAGES — explicitly ignored
    for img in image_candidates:
        src = img.get('src')
        if not src:
            continue

        # We *explicitly ignore image links* but include an else block by user request
        # so additional image scraping can be implemented later.
        # Just normalize the URL and skip it.
        _normalized = normalize_url(src, base_for_join=base_for_join)

        # placeholder for future logic
        pass  # <-- You will implement this block later

    return links




def get_visible_text_without_mutation(soup):
    """Return visible text but do not mutate the original soup."""
    # operate on a copy so we don't remove nodes from the original soup
    temp = BeautifulSoup(str(soup), 'html.parser')
    for element in temp.find_all(['header', 'footer', 'script', 'style', 'nav', 'noscript', 'meta', 'link']):
        element.decompose()
    body = temp.find('body')
    text = body.get_text(separator=' ', strip=True) if body else temp.get_text(separator=' ', strip=True)

    # Clean up whitespace
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
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

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

            # Extract links FIRST (do not mutate soup before this)
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

            # Now extract visible text from a copy of the soup (no mutation)
            visible_text = get_visible_text_without_mutation(soup)

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

    # Save output
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
    """
    Load scraped data from a file.
    
    Args:
        input_file: Path to the input file (.json.gz or .json)
    
    Returns:
        List of page documents
    """
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
    # Starting URL
    start_url = "https://pantelis.github.io/courses/ai/in-person.html"
    
    # Output file (use .json.gz for compressed, .json for uncompressed)
    OUTPUT_FILE = "scraped_pages.json.gz"
    
    # Scrape all internal links and store locally
    all_links, stored_count = scrape_and_store_locally(
        start_url=start_url,
        output_file=OUTPUT_FILE
    )
    
    # Display results
    print("\n" + "="*80)
    print(f"SCRAPING COMPLETE!")
    print(f"Total internal links found: {len(all_links)}")
    print(f"Total pages stored: {stored_count}")
    print("="*80)
    print("\nAll internal links:")
    for link in sorted(all_links):
        print(f"  - {link}")
    
    # Optionally save links to file
    with open('internal_links.txt', 'w') as f:
        f.write(f"Total links found: {len(all_links)}\n")
        f.write(f"Total pages stored: {stored_count}\n\n")
        for link in sorted(all_links):
            f.write(f"{link}\n")
    
    print(f"\nLinks also saved to: internal_links.txt")
    print(f"Page content stored in: {OUTPUT_FILE}")
    
    # Example of how to load the data back
    print("\n" + "="*80)
    print("Example: Loading data back from file...")
    loaded_data = load_scraped_data(OUTPUT_FILE)
    if loaded_data:
        print(f"First page URL: {loaded_data[0]['url']}")
        print(f"First page text preview: {loaded_data[0]['text'][:100]}...")