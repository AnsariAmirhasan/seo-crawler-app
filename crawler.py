import time
import re
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

USER_AGENTS = {
    "Screaming Frog Spider / SEO Bot": "Mozilla/5.0 (compatible; ScreamingFrogSEOSpider/19.0; +https://www.screamingfrog.co.uk/seo-spider/)",
    "Googlebot Desktop": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Googlebot Smartphone": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Chrome (Windows 11)": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Safari (macOS)": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "LibreCrawl Bot": "Mozilla/5.0 (compatible; LibreCrawl/1.0; +https://librecrawl.com)"
}

def normalize_url(url: str) -> str:
    """Normalize a URL: remove fragments, strip trailing whitespace."""
    if not url:
        return ""
    url, _ = urldefrag(url.strip())
    # Strip unnecessary trailing slash for homepages if appropriate
    parsed = urlparse(url)
    if parsed.path == "":
        url = url + "/"
    return url

def is_internal_url(target_url: str, base_domain: str) -> bool:
    """Check if target_url belongs to the same domain / subdomain."""
    try:
        parsed_target = urlparse(target_url)
        target_netloc = parsed_target.netloc.lower()
        base_netloc = base_domain.lower()
        
        # Remove 'www.' prefix for comparison
        target_clean = re.sub(r"^www\.", "", target_netloc)
        base_clean = re.sub(r"^www\.", "", base_netloc)
        
        return target_clean == base_clean or target_clean.endswith("." + base_clean)
    except Exception:
        return False

def check_robots_allowed(url: str, user_agent_str: str, base_url: str) -> bool:
    """Check if URL is allowed in robots.txt."""
    try:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent_str, url)
    except Exception:
        return True

class SEOSpider:
    def __init__(
        self,
        start_url: str,
        max_pages: int = 50,
        max_depth: int = 3,
        concurrency: int = 5,
        user_agent_name: str = "Screaming Frog Spider / SEO Bot",
        respect_robots: bool = False,
        timeout: int = 10,
        include_regex: str = "",
        exclude_regex: str = ""
    ):
        self.start_url = normalize_url(start_url)
        parsed_start = urlparse(self.start_url)
        self.base_domain = parsed_start.netloc
        self.scheme = parsed_start.scheme or "https"
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.user_agent = USER_AGENTS.get(user_agent_name, USER_AGENTS["Screaming Frog Spider / SEO Bot"])
        self.respect_robots = respect_robots
        self.timeout = timeout
        self.include_regex = re.compile(include_regex) if include_regex else None
        self.exclude_regex = re.compile(exclude_regex) if exclude_regex else None

        self.visited = set()
        self.lock = threading.Lock()
        self.crawled_data = []
        self.all_links = []
        self.all_images = []
        self.queue = [(self.start_url, 0, "")]  # (url, depth, source_url)
        self.stop_requested = False

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def fetch_single_url(self, url: str):
        """Fetch a single URL and measure latency, headers, status."""
        start_time = time.time()
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                verify=True
            )
            latency_ms = round((time.time() - start_time) * 1000, 2)
            redirect_chain = [r.url for r in response.history] + [response.url] if response.history else []
            content_type = response.headers.get("Content-Type", "")
            content_length = len(response.content) if response.content else 0
            
            return {
                "url": url,
                "final_url": response.url,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "content_type": content_type,
                "size_bytes": content_length,
                "headers": dict(response.headers),
                "redirect_chain": redirect_chain,
                "html": response.text if "text/html" in content_type.lower() else "",
                "error": None
            }
        except requests.exceptions.Timeout:
            return {
                "url": url,
                "final_url": url,
                "status_code": 0,
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "content_type": "",
                "size_bytes": 0,
                "headers": {},
                "redirect_chain": [],
                "html": "",
                "error": "Request Timeout"
            }
        except requests.exceptions.SSLError:
            return {
                "url": url,
                "final_url": url,
                "status_code": 0,
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "content_type": "",
                "size_bytes": 0,
                "headers": {},
                "redirect_chain": [],
                "html": "",
                "error": "SSL Certificate Error"
            }
        except Exception as e:
            return {
                "url": url,
                "final_url": url,
                "status_code": 0,
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "content_type": "",
                "size_bytes": 0,
                "headers": {},
                "redirect_chain": [],
                "html": "",
                "error": str(e)
            }

    def should_crawl(self, url: str, depth: int) -> bool:
        """Evaluate if URL passes filters and should be crawled."""
        if not url or depth > self.max_depth:
            return False
        
        # Check scheme
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False
            
        # Ignore media/file downloads from crawling as web pages
        non_html_extensions = (
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.pdf',
            '.zip', '.tar', '.gz', '.exe', '.mp4', '.mp3', '.css', '.js'
        )
        if parsed.path.lower().endswith(non_html_extensions):
            return False

        # Domain matching
        if not is_internal_url(url, self.base_domain):
            return False

        # Regex filters
        if self.include_regex and not self.include_regex.search(url):
            return False
        if self.exclude_regex and self.exclude_regex.search(url):
            return False

        return True

    def crawl(self, progress_callback=None):
        """Execute the multi-threaded website crawl."""
        visited_urls = set()
        to_visit = [(self.start_url, 0, "Initial Seed")]

        while to_visit and len(self.crawled_data) < self.max_pages and not self.stop_requested:
            # Batch URLs up to concurrency limit
            batch = []
            while to_visit and len(batch) < self.concurrency and (len(self.crawled_data) + len(batch)) < self.max_pages:
                current_url, current_depth, source_url = to_visit.pop(0)
                norm_url = normalize_url(current_url)
                if norm_url not in visited_urls:
                    visited_urls.add(norm_url)
                    batch.append((norm_url, current_depth, source_url))

            if not batch:
                break

            # Execute batch requests in parallel
            with ThreadPoolExecutor(max_workers=min(self.concurrency, len(batch))) as executor:
                future_to_info = {
                    executor.submit(self.fetch_single_url, item[0]): item
                    for item in batch
                }

                for future in as_completed(future_to_info):
                    if self.stop_requested:
                        break
                    url, depth, source_page = future_to_info[future]
                    fetch_res = future.result()
                    
                    fetch_res["depth"] = depth
                    fetch_res["source_page"] = source_page
                    
                    self.crawled_data.append(fetch_res)

                    # Extract outgoing links and images if HTML
                    if fetch_res.get("html"):
                        soup = BeautifulSoup(fetch_res["html"], "lxml" if "lxml" in BeautifulSoup.__dict__ else "html.parser")
                        
                        # Extract Links
                        for a_tag in soup.find_all("a", href=True):
                            raw_href = a_tag["href"].strip()
                            if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                                continue
                            
                            abs_url = normalize_url(urljoin(fetch_res["final_url"], raw_href))
                            is_internal = is_internal_url(abs_url, self.base_domain)
                            rel_val = a_tag.get("rel", [])
                            is_nofollow = "nofollow" in (rel_val if isinstance(rel_val, list) else [rel_val])
                            anchor_text = a_tag.get_text(strip=True)[:100]

                            self.all_links.append({
                                "source_url": url,
                                "target_url": abs_url,
                                "anchor_text": anchor_text,
                                "is_internal": is_internal,
                                "nofollow": is_nofollow,
                                "rel": str(rel_val)
                            })

                            # Add to next depth queue if eligible
                            if is_internal and self.should_crawl(abs_url, depth + 1):
                                if abs_url not in visited_urls:
                                    to_visit.append((abs_url, depth + 1, url))

                        # Extract Images
                        for img in soup.find_all("img"):
                            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
                            if src:
                                img_abs = urljoin(fetch_res["final_url"], src)
                                alt_text = img.get("alt", None)
                                self.all_images.append({
                                    "page_url": url,
                                    "image_url": img_abs,
                                    "alt": alt_text,
                                    "has_alt": alt_text is not None and len(alt_text.strip()) > 0,
                                    "loading": img.get("loading", "")
                                })

                    if progress_callback:
                        progress_callback(
                            crawled_count=len(self.crawled_data),
                            max_pages=self.max_pages,
                            current_url=url,
                            status_code=fetch_res["status_code"]
                        )

        return {
            "crawled_pages": self.crawled_data,
            "links": self.all_links,
            "images": self.all_images
        }
