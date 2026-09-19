import time
import re
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser
import requests
import urllib3
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Suppress insecure request warnings when SSL fallback is active
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENTS = {
    "Chrome (Windows 11)": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Safari (macOS)": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Googlebot Desktop": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Googlebot Smartphone": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Screaming Frog Spider / SEO Bot": "Mozilla/5.0 (compatible; ScreamingFrogSEOSpider/19.0; +https://www.screamingfrog.co.uk/seo-spider/)",
    "LibreCrawl Bot": "Mozilla/5.0 (compatible; LibreCrawl/1.0; +https://librecrawl.com)"
}

def normalize_url(url: str) -> str:
    """Normalize a URL: remove fragments, strip trailing whitespace."""
    if not url:
        return ""
    url, _ = urldefrag(url.strip())
    parsed = urlparse(url)
    if parsed.path == "":
        url = url + "/"
    return url

def get_root_domain(netloc: str) -> str:
    """Extract root registrable domain (e.g. example.com or example.co.in)."""
    clean = re.sub(r"^www\.", "", netloc.lower())
    parts = clean.split(".")
    if len(parts) > 2 and parts[-2] in ["co", "com", "org", "net", "gov", "edu", "ac", "nic", "res"]:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return clean

def is_internal_url(target_url: str, allowed_domains, allow_subdomains: bool = False) -> bool:
    """Check if target_url belongs to allowed internal domain / subdomain based on mode."""
    try:
        parsed_target = urlparse(target_url)
        target_netloc = parsed_target.netloc.lower()
        target_clean = re.sub(r"^www\.", "", target_netloc)
        
        domains = allowed_domains if isinstance(allowed_domains, (set, list, tuple)) else [allowed_domains]
        for base_domain in domains:
            base_clean = re.sub(r"^www\.", "", str(base_domain).lower())
            
            # Exact subdomain or www equivalent match
            if target_clean == base_clean:
                return True
                
            # If All Subdomains mode is enabled
            if allow_subdomains:
                if target_clean.endswith("." + base_clean):
                    return True
                root_base = get_root_domain(base_clean)
                root_target = get_root_domain(target_clean)
                if root_base and root_base == root_target:
                    return True
        return False
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
        max_pages: int = 2000,
        max_depth: int = 5,
        concurrency: int = 10,
        user_agent_name: str = "Chrome (Windows 11)",
        respect_robots: bool = False,
        timeout: int = 10,
        include_regex: str = "",
        exclude_regex: str = "",
        crawl_mode: str = "Subdomain"
    ):
        self.start_url = normalize_url(start_url)
        parsed_start = urlparse(self.start_url)
        self.base_domain = parsed_start.netloc
        self.allowed_domains = {self.base_domain}
        self.subfolder_prefix = parsed_start.path.rstrip("/") if parsed_start.path and parsed_start.path != "/" else ""
        self.crawl_mode = crawl_mode  # "Subdomain", "Subfolder", "All Subdomains", "Exact URL"
        self.scheme = parsed_start.scheme or "https"

        if self.crawl_mode == "Exact URL":
            self.max_pages = 1
            self.max_depth = 0
        else:
            self.max_pages = max_pages
            self.max_depth = max_depth

        self.concurrency = concurrency
        self.user_agent = USER_AGENTS.get(user_agent_name, USER_AGENTS["Chrome (Windows 11)"])
        self.respect_robots = respect_robots
        self.timeout = timeout
        self.include_regex = re.compile(include_regex) if include_regex else None
        self.exclude_regex = re.compile(exclude_regex) if exclude_regex else None

        self.visited = set()
        self.lock = threading.Lock()
        self.crawled_data = []
        self.all_links = []
        self.all_images = []
        self.stop_requested = False

        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=concurrency * 2, pool_maxsize=concurrency * 2, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": "\"Not A(Brand\";v=\"99\", \"Google Chrome\";v=\"124\", \"Chromium\";v=\"124\"",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "\"Windows\"",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        })

    def fetch_single_url(self, url: str):
        """Fetch a single URL and measure latency, headers, status with smart SSL fallback."""
        start_time = time.time()
        response = None
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                verify=True
            )
        except requests.exceptions.SSLError:
            # Fallback for sites with missing intermediate SSL certificates (e.g. cairnindia.com)
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=False
                )
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
                    "error": f"SSL Certificate Error: {e}"
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

    def should_crawl(self, url: str, depth: int) -> bool:
        """Evaluate if URL passes filters, depth limits, and crawl mode scope."""
        if not url or depth > self.max_depth:
            return False
        
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False
            
        non_html_extensions = (
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.pdf',
            '.zip', '.tar', '.gz', '.exe', '.mp4', '.mp3', '.css', '.js',
            '.woff', '.woff2', '.ttf', '.eot', '.ico'
        )
        if parsed.path.lower().endswith(non_html_extensions):
            return False

        # Crawl Mode Scope Checking (Screaming Frog parity)
        if self.crawl_mode == "Exact URL":
            return False
        elif self.crawl_mode == "Subfolder":
            if not is_internal_url(url, self.allowed_domains, allow_subdomains=False):
                return False
            if self.subfolder_prefix and not parsed.path.startswith(self.subfolder_prefix):
                return False
        elif self.crawl_mode == "Subdomain":
            if not is_internal_url(url, self.allowed_domains, allow_subdomains=False):
                return False
        elif self.crawl_mode == "All Subdomains":
            if not is_internal_url(url, self.allowed_domains, allow_subdomains=True):
                return False
        else:
            if not is_internal_url(url, self.allowed_domains):
                return False

        if self.include_regex and not self.include_regex.search(url):
            return False
        if self.exclude_regex and self.exclude_regex.search(url):
            return False

        return True

    def crawl(self, progress_callback=None):
        """Execute high-speed multi-threaded crawl with memory optimizations."""
        visited_urls = set()
        to_visit = [(self.start_url, 0, "Initial Seed")]

        while to_visit and len(self.crawled_data) < self.max_pages and not self.stop_requested:
            batch = []
            while to_visit and len(batch) < self.concurrency and (len(self.crawled_data) + len(batch)) < self.max_pages:
                current_url, current_depth, source_url = to_visit.pop(0)
                norm_url = normalize_url(current_url)
                if norm_url not in visited_urls:
                    visited_urls.add(norm_url)
                    batch.append((norm_url, current_depth, source_url))

            if not batch:
                break

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
                    
                    # If root URL redirected to a new domain (e.g. cairnindia.com -> vedantaoilandgas.com),
                    # allow the destination domain so all internal pages get crawled!
                    if depth == 0 and fetch_res.get("final_url"):
                        final_netloc = urlparse(fetch_res["final_url"]).netloc
                        if final_netloc:
                            self.allowed_domains.add(final_netloc)

                    self.crawled_data.append(fetch_res)

                    # Extract outgoing links & images
                    if fetch_res.get("html"):
                        try:
                            soup = BeautifulSoup(fetch_res["html"], "html.parser")
                            allow_sub = (self.crawl_mode == "All Subdomains")
                            
                            # Extract Links
                            for a_tag in soup.find_all("a", href=True):
                                raw_href = a_tag["href"].strip()
                                if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                                    continue
                                
                                abs_url = normalize_url(urljoin(fetch_res["final_url"], raw_href))
                                is_internal = is_internal_url(abs_url, self.allowed_domains, allow_subdomains=allow_sub)
                                rel_val = a_tag.get("rel", [])
                                is_nofollow = "nofollow" in (rel_val if isinstance(rel_val, list) else [rel_val])
                                anchor_text = a_tag.get_text(strip=True)[:100]

                                if len(self.all_links) < 30000:
                                    self.all_links.append({
                                        "source_url": url,
                                        "target_url": abs_url,
                                        "anchor_text": anchor_text,
                                        "is_internal": is_internal,
                                        "nofollow": is_nofollow,
                                        "rel": str(rel_val)
                                    })

                                if is_internal and self.should_crawl(abs_url, depth + 1):
                                    if abs_url not in visited_urls:
                                        to_visit.append((abs_url, depth + 1, url))

                            # Extract Images
                            for img in soup.find_all("img"):
                                src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
                                if src and len(self.all_images) < 30000:
                                    img_abs = urljoin(fetch_res["final_url"], src)
                                    alt_text = img.get("alt", None)
                                    self.all_images.append({
                                        "page_url": url,
                                        "image_url": img_abs,
                                        "alt": alt_text,
                                        "has_alt": alt_text is not None and len(alt_text.strip()) > 0,
                                        "loading": img.get("loading", "")
                                    })
                        except Exception:
                            pass

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
