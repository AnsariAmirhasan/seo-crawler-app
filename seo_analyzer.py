import re
import json
import urllib.parse
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
from collections import Counter
import requests
from concurrent.futures import ThreadPoolExecutor

PAGINATION_QUERY_KEYS = {
    "page", "p", "pg", "paged", "page_number", "page_no", "pagination", "pageid", "pno"
}
PAGINATION_PATH_REGEX = re.compile(
    r'(?:^|/)(?:page|paged|p|pagina|seite)[/-](\d+)(?:/|$)',
    re.IGNORECASE
)

def is_pagination_url(url: str, canonical_url: str = "") -> bool:
    """
    Checks if a URL represents a paginated view (e.g. ?page=3, /page/2/, ?p=2).
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
        # 1. Query parameters
        if parsed.query:
            qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            for k, vals in qs.items():
                if k.lower() in PAGINATION_QUERY_KEYS:
                    for val in vals:
                        if val.isdigit() or val.lower().startswith("page"):
                            return True
                    if k.lower() in ("page", "paged", "page_no", "page_number"):
                        return True
        # 2. Path patterns
        if parsed.path and PAGINATION_PATH_REGEX.search(parsed.path):
            return True
        # 3. Canonical URL points to root path without query params
        if canonical_url and isinstance(canonical_url, str) and canonical_url.strip():
            c_parsed = urllib.parse.urlsplit(canonical_url.strip())
            if c_parsed.netloc.lower() == parsed.netloc.lower() and c_parsed.path.rstrip("/") == parsed.path.rstrip("/"):
                if parsed.query and not c_parsed.query:
                    return True
    except Exception:
        pass
    return False

def get_base_unpaginated_url(url: str, canonical_url: str = "") -> str:
    """
    Strips pagination query parameters and path segments to find the root/base page URL.
    Example:
      https://plantspower.ca/collections/all-collections?page=3 -> https://plantspower.ca/collections/all-collections
      https://example.com/blog/page/2/ -> https://example.com/blog
    """
    if not url or not isinstance(url, str):
        return ""
    # If canonical_url is provided and clean on the same domain
    if canonical_url and isinstance(canonical_url, str) and canonical_url.strip():
        c_clean = canonical_url.strip().split("#")[0]
        if not is_pagination_url(c_clean):
            try:
                p_url = urllib.parse.urlsplit(url)
                p_can = urllib.parse.urlsplit(c_clean)
                if p_url.netloc.lower() == p_can.netloc.lower():
                    return c_clean.rstrip("/")
            except Exception:
                pass
    try:
        parsed = urllib.parse.urlsplit(url)
        filtered_qs = []
        if parsed.query:
            for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
                if k.lower() not in PAGINATION_QUERY_KEYS:
                    filtered_qs.append((k, v))
        new_query = urllib.parse.urlencode(filtered_qs)
        clean_path = parsed.path
        if clean_path:
            clean_path = PAGINATION_PATH_REGEX.sub("/", clean_path)
            clean_path = re.sub(r"/+", "/", clean_path)
        base = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, clean_path.rstrip("/"), new_query, ""))
        return base.rstrip("/")
    except Exception:
        return url.rstrip("/")

def estimate_pixel_width(text: str) -> int:
    """Approximate Google SERP title pixel width."""
    if not text:
        return 0
    # Standard Arial 18px approximations: uppercase/wide chars ~10-12px, lowercase ~7-9px
    width = 0
    for char in text:
        if char in "WM@#%&":
            width += 14
        elif char.isupper():
            width += 11
        elif char in "ijl|!.,:;' ":
            width += 4
        elif char in "ftr":
            width += 6
        else:
            width += 8
    return width

def parse_page_seo(page_data: dict, all_links: list = None, all_images: list = None) -> dict:
    """Deeply inspect a single crawled page for technical SEO metrics and issues."""
    url = page_data.get("url", "")
    final_url = page_data.get("final_url", url)
    status_code = page_data.get("status_code", 0)
    latency_ms = page_data.get("latency_ms", 0)
    size_bytes = page_data.get("size_bytes", 0)
    size_kb = round(size_bytes / 1024, 2)
    content_type = page_data.get("content_type", "")
    html = page_data.get("html", "")
    depth = page_data.get("depth", 0)
    error_msg = page_data.get("error", None)
    source_page = page_data.get("source_page", "")

    # Redirect Chain & Loop Data from Crawler
    redirect_chain = page_data.get("redirect_chain", [])
    redirect_chain_statuses = page_data.get("redirect_chain_statuses", [])
    redirect_chain_str = page_data.get("redirect_chain_str", "")
    redirect_hops = page_data.get("redirect_hops", 0)
    redirect_issue_type = page_data.get("redirect_issue_type", "None")
    redirect_severity = page_data.get("redirect_severity", "None")
    is_redirect_chain = page_data.get("is_redirect_chain", False)
    is_redirect_loop = page_data.get("is_redirect_loop", False)

    seo_info = {
        "url": url,
        "final_url": final_url,
        "source_page": source_page,
        "source_url": source_page,
        "anchor_text": "",
        "status_code": status_code,
        "depth": depth,
        "latency_ms": latency_ms,
        "size_kb": size_kb,
        "content_type": content_type,
        "error": error_msg,
        # Redirect Chain & Loop Tracking
        "redirect_chain": redirect_chain,
        "redirect_chain_statuses": redirect_chain_statuses,
        "redirect_chain_str": redirect_chain_str,
        "redirect_hops": redirect_hops,
        "redirect_issue_type": redirect_issue_type,
        "redirect_severity": redirect_severity,
        "is_redirect_chain": is_redirect_chain,
        "is_redirect_loop": is_redirect_loop,
        # Page Title
        "title": "",
        "title_length": 0,
        "title_pixel_width": 0,
        "title_count": 0,
        # Meta Description
        "meta_description": "",
        "meta_description_length": 0,
        # Headings
        "h1": "",
        "h1_2": "",
        "h1_count": 0,
        "h2_first": "",
        "h2_2": "",
        "h2_count": 0,
        # Directives & Indexability
        "meta_robots": "",
        "is_noindex": False,
        "is_nofollow": False,
        "is_indexable": True,
        "indexability_reason": "Indexable",
        "canonical_url": "",
        "canonical_status": "Missing",
        # Content
        "word_count": 0,
        "text_ratio": 0.0,
        # Social & Schema
        "has_schema": False,
        "schema_types": [],
        "og_title": "",
        "og_image": "",
        "og_description": "",
        "twitter_card": "",
        # Links & Images Stats
        "internal_outlinks_count": 0,
        "external_outlinks_count": 0,
        "inlinks_count": 0,
        "is_orphan": False,
        "has_meta_refresh": False,
        "meta_refresh_content": "",
        "has_js_redirect": False,
        "images_count": 0,
        "images_missing_alt_count": 0,
        # Issues Detected on this page
        "issues": []
    }

    # Evaluate HTTP Status Issues
    if error_msg and not is_redirect_loop:
        seo_info["is_indexable"] = False
        seo_info["indexability_reason"] = f"Fetch Failed ({error_msg})"
        seo_info["issues"].append({
            "type": "Error",
            "category": "Status Code",
            "issue": f"Fetch Error: {error_msg}",
            "recommendation": "Fix server connectivity, DNS or SSL certificate configuration."
        })
        return seo_info

    # 1. Redirect Loop (Severity: Error)
    if is_redirect_loop:
        seo_info["is_indexable"] = False
        seo_info["indexability_reason"] = "Redirect Loop"
        seo_info["canonical_status"] = "N/A (Redirect Loop)"
        seo_info["issues"].append({
            "type": "Error",
            "category": "Redirect",
            "issue": f"Redirect Loop Detected ({redirect_hops} Hops)",
            "recommendation": f"Resolve circular redirects: {redirect_chain_str or url}. Ensure URL resolves directly to the final destination without infinite loops."
        })
        return seo_info

    # 2. Redirect Chain (Severity: Warning)
    if is_redirect_chain:
        seo_info["is_indexable"] = False
        seo_info["indexability_reason"] = f"Redirect Chain ({redirect_hops} Hops)"
        seo_info["canonical_status"] = "N/A (Redirect)"
        seo_info["issues"].append({
            "type": "Warning",
            "category": "Redirect",
            "issue": f"Redirect Chain Detected ({redirect_hops} Hops) -> {final_url}",
            "recommendation": f"Eliminate redirect chain: update internal links to point directly to final destination '{final_url}' instead of passing through {redirect_hops} intermediate hops ({redirect_chain_str})."
        })
        return seo_info

    # 3. Client / Server Error (4xx, 5xx)
    if status_code >= 400:
        seo_info["is_indexable"] = False
        seo_info["indexability_reason"] = f"HTTP {status_code}"
        rec = f"Fix broken link on referring source page '{source_page}' or configure a 301 redirect if page moved." if source_page else "Fix broken link or configure a 301 redirect if page moved."
        seo_info["issues"].append({
            "type": "Error",
            "category": "Status Code",
            "issue": f"Client/Server Error ({status_code})",
            "recommendation": rec
        })
        return seo_info

    # 4. Standard Single Redirect (Severity: Notice)
    if 300 <= status_code < 400:
        seo_info["is_indexable"] = False
        seo_info["indexability_reason"] = f"Redirect ({status_code})"
        seo_info["canonical_status"] = "N/A (Redirect)"
        seo_info["issues"].append({
            "type": "Notice",
            "category": "Redirect",
            "issue": f"Page Redirects ({status_code}) -> {final_url}",
            "recommendation": "Update internal links to point directly to the destination URL."
        })
        return seo_info

    # Response time warning (>1500ms)
    if latency_ms > 1500:
        seo_info["issues"].append({
            "type": "Warning",
            "category": "Performance",
            "issue": f"Slow Page Response ({latency_ms} ms)",
            "recommendation": "Optimize server response time, database queries or enable caching."
        })

    # If not HTML, stop detailed SEO parsing
    if not html:
        return seo_info

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # 1. Meta Robots & Indexability (Check FIRST so we know if page is Noindex!)
    meta_robots = soup.find("meta", attrs={"name": re.compile(r"^(robots|googlebot)$", re.I)})
    robots_content = ""
    if meta_robots and meta_robots.get("content"):
        robots_content = meta_robots["content"].lower().strip()
        seo_info["meta_robots"] = meta_robots["content"].strip()

    headers_dict = page_data.get("headers", {}) or {}
    x_robots = ""
    for hk, hv in headers_dict.items():
        if hk.lower() == "x-robots-tag":
            x_robots = str(hv).lower().strip()
            if not seo_info["meta_robots"]:
                seo_info["meta_robots"] = str(hv).strip()
            break

    combined_robots = f"{robots_content} {x_robots}".strip()
    is_noindex = "noindex" in combined_robots
    is_nofollow = "nofollow" in combined_robots

    seo_info["is_noindex"] = is_noindex
    seo_info["is_nofollow"] = is_nofollow

    if is_noindex:
        seo_info["is_indexable"] = False
        seo_info["indexability_reason"] = "Blocked by meta robots noindex" if "noindex" in robots_content else "Blocked by X-Robots-Tag noindex"
        seo_info["issues"].append({
            "type": "Notice",
            "category": "Indexability",
            "issue": f"Noindex Tag Detected ({seo_info['meta_robots']})",
            "recommendation": "This page is intentionally excluded from search engines. On-page SEO issues (H1, title, description) are bypassed."
        })
    elif is_nofollow:
        seo_info["issues"].append({
            "type": "Notice",
            "category": "Indexability",
            "issue": f"Nofollow Tag Detected ({seo_info['meta_robots']})",
            "recommendation": "Search engine crawlers are instructed not to follow outbound links on this page."
        })

    # 2. Page Titles
    title_tags = soup.find_all("title")
    seo_info["title_count"] = len(title_tags)
    if title_tags:
        title_text = title_tags[0].get_text(strip=True)
        seo_info["title"] = title_text
        seo_info["title_length"] = len(title_text)
        seo_info["title_pixel_width"] = estimate_pixel_width(title_text)

        if not is_noindex:
            if len(title_tags) > 1:
                seo_info["issues"].append({
                    "type": "Warning",
                    "category": "Page Title",
                    "issue": f"Multiple <title> tags found ({len(title_tags)})",
                    "recommendation": "Keep only one canonical <title> tag inside the <head>."
                })
            if len(title_text) == 0:
                seo_info["issues"].append({
                    "type": "Error",
                    "category": "Page Title",
                    "issue": "Empty <title> tag",
                    "recommendation": "Add a descriptive, keyword-rich title between 40-60 characters."
                })
            elif len(title_text) < 30:
                seo_info["issues"].append({
                    "type": "Notice",
                    "category": "Page Title",
                    "issue": f"Title too short ({len(title_text)} chars)",
                    "recommendation": "Expand title tag to 40-60 characters for better search click-through."
                })
            elif len(title_text) > 60:
                seo_info["issues"].append({
                    "type": "Warning",
                    "category": "Page Title",
                    "issue": f"Title too long ({len(title_text)} chars / {seo_info['title_pixel_width']}px)",
                    "recommendation": "Shorten title to under 60 characters (approx. 580px) to prevent truncation in Google SERPs."
                })
    else:
        if not is_noindex:
            seo_info["issues"].append({
                "type": "Error",
                "category": "Page Title",
                "issue": "Missing <title> tag",
                "recommendation": "Add a unique <title> tag to every indexable page."
            })

    # 3. Meta Descriptions
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_desc and meta_desc.get("content"):
        desc_text = meta_desc["content"].strip()
        seo_info["meta_description"] = desc_text
        seo_info["meta_description_length"] = len(desc_text)

        if not is_noindex:
            if len(desc_text) < 70:
                seo_info["issues"].append({
                    "type": "Notice",
                    "category": "Meta Description",
                    "issue": f"Meta description too short ({len(desc_text)} chars)",
                    "recommendation": "Aim for 120-155 characters to maximize search snippet engagement."
                })
            elif len(desc_text) > 160:
                seo_info["issues"].append({
                    "type": "Warning",
                    "category": "Meta Description",
                    "issue": f"Meta description too long ({len(desc_text)} chars)",
                    "recommendation": "Shorten description to under 160 characters to avoid SERP truncation."
                })
    else:
        if not is_noindex:
            seo_info["issues"].append({
                "type": "Warning",
                "category": "Meta Description",
                "issue": "Missing Meta Description",
                "recommendation": "Add a unique and compelling meta description summarizing the page content."
            })

    # 4. Headings (H1 & H2)
    h1_tags = soup.find_all("h1")
    seo_info["h1_count"] = len(h1_tags)
    if h1_tags:
        seo_info["h1"] = h1_tags[0].get_text(strip=True)
        if len(h1_tags) > 1:
            seo_info["h1_2"] = h1_tags[1].get_text(strip=True)
            if not is_noindex:
                seo_info["issues"].append({
                    "type": "Warning",
                    "category": "H1 Heading",
                    "issue": f"Multiple H1 tags found ({len(h1_tags)}): H1-1 ('{seo_info['h1'][:28]}...') & H1-2 ('{seo_info['h1_2'][:28]}...')",
                    "recommendation": "Use exactly one primary H1 tag per page for clean structural hierarchy."
                })
    else:
        if not is_noindex:
            seo_info["issues"].append({
                "type": "Error",
                "category": "H1 Heading",
                "issue": "Missing H1 tag",
                "recommendation": "Add a primary H1 heading reflecting the main topic of the page."
            })

    h2_tags = soup.find_all("h2")
    seo_info["h2_count"] = len(h2_tags)
    if h2_tags:
        seo_info["h2_first"] = h2_tags[0].get_text(strip=True)
        if len(h2_tags) > 1:
            seo_info["h2_2"] = h2_tags[1].get_text(strip=True)
    else:
        if not is_noindex:
            seo_info["issues"].append({
                "type": "Notice",
                "category": "H2 Heading",
                "issue": "No H2 subheadings found",
                "recommendation": "Structure content with H2 tags to improve scannability and topic coverage."
            })

    # Meta Refresh Redirects
    meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"^refresh$", re.I)})
    if meta_refresh and meta_refresh.get("content"):
        seo_info["has_meta_refresh"] = True
        seo_info["meta_refresh_content"] = meta_refresh["content"]
        seo_info["issues"].append({
            "type": "Warning",
            "category": "Redirect",
            "issue": f"Meta Refresh Redirect Found: {meta_refresh['content'][:60]}",
            "recommendation": "Replace meta refresh redirects with standard 301 HTTP redirects."
        })

    # JavaScript Redirects
    has_js_redirect = False
    for script in soup.find_all("script"):
        stext = script.string or ""
        if stext and ("window.location" in stext or "location.href" in stext or "location.replace" in stext):
            has_js_redirect = True
            break
    seo_info["has_js_redirect"] = has_js_redirect
    if has_js_redirect:
        seo_info["issues"].append({
            "type": "Warning",
            "category": "Redirect",
            "issue": "JavaScript Client-Side Redirect Detected",
            "recommendation": "Use 301 HTTP server redirects instead of client-side JavaScript redirects."
        })

    # 5. Canonical Tag
    canonical_tags = soup.find_all("link", attrs={"rel": lambda x: x and "canonical" in (x.lower() if isinstance(x, str) else [item.lower() for item in x])})
    if not canonical_tags:
        canonical_tags = soup.find_all("link", attrs={"rel": re.compile(r"^canonical$", re.I)})

    if len(canonical_tags) > 1:
        raw_canon = canonical_tags[0].get("href", "").strip()
        seo_info["canonical_url"] = urljoin(final_url, raw_canon) if raw_canon else ""
        seo_info["canonical_status"] = "Multiple"
        seo_info["issues"].append({
            "type": "Error",
            "category": "Canonical",
            "issue": f"Multiple canonical tags detected ({len(canonical_tags)} tags found)",
            "recommendation": "Search engines may ignore all canonical tags when multiples are found. Retain only one valid canonical tag."
        })
    elif canonical_tags and canonical_tags[0].get("href"):
        raw_canon = canonical_tags[0]["href"].strip()
        canon_url = urljoin(final_url, raw_canon)
        seo_info["canonical_url"] = canon_url

        # Compare canonical with actual crawled URL
        if canon_url.rstrip("/") == final_url.rstrip("/"):
            seo_info["canonical_status"] = "Self-Referential"
        else:
            seo_info["canonical_status"] = "Canonicalised"
            if not is_noindex:
                seo_info["issues"].append({
                    "type": "Notice",
                    "category": "Canonical",
                    "issue": f"Canonical points to alternative URL: {canon_url}",
                    "recommendation": "Verify that this canonical target is the desired master version to consolidate link equity."
                })
    else:
        if is_noindex:
            seo_info["canonical_status"] = "Noindex (Optional)"
        else:
            seo_info["canonical_status"] = "Missing"
            seo_info["issues"].append({
                "type": "Notice",
                "category": "Canonical",
                "issue": "Missing Canonical Tag",
                "recommendation": "Add a self-referential canonical tag (<link rel='canonical' href='...'>) to prevent duplicate content issues."
            })

    # 6. Word Count & Content Quality
    # Remove script, style, nav, footer for word count estimation
    for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        element.extract()
    raw_text = soup.get_text(separator=" ", strip=True)
    words = re.findall(r"\b\w+\b", raw_text)
    seo_info["word_count"] = len(words)

    if seo_info["is_indexable"] and not is_noindex and len(words) < 250:
        seo_info["issues"].append({
            "type": "Warning",
            "category": "Content",
            "issue": f"Thin Content ({len(words)} words)",
            "recommendation": "Provide comprehensive, high-value content exceeding 300+ words."
        })

    # 7. OpenGraph & Twitter Cards
    og_title = soup.find("meta", property="og:title")
    seo_info["og_title"] = og_title["content"] if og_title and og_title.get("content") else ""
    og_img = soup.find("meta", property="og:image")
    seo_info["og_image"] = og_img["content"] if og_img and og_img.get("content") else ""
    og_desc = soup.find("meta", property="og:description")
    seo_info["og_description"] = og_desc["content"] if og_desc and og_desc.get("content") else ""

    twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
    seo_info["twitter_card"] = twitter_card["content"] if twitter_card and twitter_card.get("content") else ""

    if not is_noindex and (not seo_info["og_title"] or not seo_info["og_image"]):
        seo_info["issues"].append({
            "type": "Notice",
            "category": "Social Meta",
            "issue": "Missing Open Graph (og:title or og:image) tags",
            "recommendation": "Add OpenGraph social tags for rich previews on Facebook, LinkedIn, Twitter/X."
        })

    # 8. Structured Data / Schema.org
    schema_scripts = soup.find_all("script", type="application/ld+json")
    if schema_scripts:
        seo_info["has_schema"] = True
        schema_types = []
        for s in schema_scripts:
            try:
                data = json.loads(s.string)
                if isinstance(data, dict) and "@type" in data:
                    schema_types.append(data["@type"])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "@type" in item:
                            schema_types.append(item["@type"])
            except Exception:
                pass
        seo_info["schema_types"] = schema_types

    return seo_info

def resolve_image_sizes(df_images: pd.DataFrame, max_workers: int = 20, timeout: float = 3.0) -> pd.DataFrame:
    """Fetch HTTP content-length for unique image URLs in parallel and compute size_kb & is_over_100kb."""
    if df_images is None or df_images.empty:
        return df_images

    if "size_kb" in df_images.columns and "is_over_100kb" in df_images.columns:
        return df_images

    unique_urls = [u for u in df_images["image_url"].dropna().unique() if str(u).startswith("http")]
    if not unique_urls:
        df_images["size_kb"] = 0.0
        df_images["is_over_100kb"] = False
        return df_images

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    def fetch_single_size(url):
        try:
            r = session.head(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200 and "content-length" in r.headers:
                return url, round(int(r.headers["content-length"]) / 1024.0, 1)
            # Fallback to streaming GET if HEAD fails or doesn't return content-length
            r = session.get(url, stream=True, timeout=timeout)
            if "content-length" in r.headers:
                return url, round(int(r.headers["content-length"]) / 1024.0, 1)
            content = r.raw.read(1024 * 1024 * 10)
            return url, round(len(content) / 1024.0, 1)
        except Exception:
            return url, 0.0

    url_to_size = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(unique_urls)))) as executor:
        results = executor.map(fetch_single_size, unique_urls)
        for u, sz in results:
            url_to_size[u] = sz

    df_images["size_kb"] = df_images["image_url"].map(url_to_size).fillna(0.0)
    df_images["is_over_100kb"] = df_images["size_kb"] > 100.0
    return df_images

def analyze_crawl_results(crawled_pages: list, all_links: list, all_images: list):
    """Aggregate all page audits, compute site-wide duplicates, metrics, and health score."""
    pages_audit = []
    
    for page in crawled_pages:
        audit = parse_page_seo(page, all_links, all_images)
        pages_audit.append(audit)

    df_pages = pd.DataFrame(pages_audit)
    df_links = pd.DataFrame(all_links) if all_links else pd.DataFrame(columns=["source_url", "target_url", "anchor_text", "link_location", "is_internal", "nofollow", "rel"])
    if not df_links.empty:
        for col_name, default_val in [
            ("source_url", ""),
            ("target_url", ""),
            ("anchor_text", ""),
            ("link_location", "Content"),
            ("is_internal", True),
            ("nofollow", False),
            ("rel", "")
        ]:
            if col_name not in df_links.columns:
                df_links[col_name] = default_val
    df_images = pd.DataFrame(all_images) if all_images else pd.DataFrame(columns=["page_url", "image_url", "alt", "has_alt", "loading"])
    if not df_images.empty:
        df_images = resolve_image_sizes(df_images)
    else:
        df_images["size_kb"] = []
        df_images["is_over_100kb"] = []

    # Compute link stats and map source_page / anchor_text per page
    if not df_links.empty and not df_pages.empty:
        internal_outlinks = df_links[df_links["is_internal"] == True].groupby("source_url").size().to_dict()
        external_outlinks = df_links[df_links["is_internal"] == False].groupby("source_url").size().to_dict()
        internal_inlinks = df_links[df_links["is_internal"] == True].groupby("target_url").size().to_dict()
        df_pages["internal_outlinks_count"] = df_pages["url"].map(internal_outlinks).fillna(0).astype(int)
        df_pages["external_outlinks_count"] = df_pages["url"].map(external_outlinks).fillna(0).astype(int)
        df_pages["inlinks_count"] = df_pages["url"].map(internal_inlinks).fillna(0).astype(int)

        source_map = {}
        anchor_map = {}
        for _, r in df_links.iterrows():
            tgt = str(r.get("target_url", "")).strip()
            src = str(r.get("source_url", "")).strip()
            anc = str(r.get("anchor_text", "")).strip()
            if tgt:
                if tgt not in source_map:
                    source_map[tgt] = src
                    anchor_map[tgt] = anc
                tgt_alt = tgt.rstrip('/') if tgt.endswith('/') else (tgt + '/')
                if tgt_alt not in source_map:
                    source_map[tgt_alt] = src
                    anchor_map[tgt_alt] = anc

        df_pages["source_url"] = df_pages["url"].map(source_map).fillna(df_pages.get("source_page", ""))
        df_pages["anchor_text"] = df_pages["url"].map(anchor_map).fillna("")
    else:
        df_pages["internal_outlinks_count"] = 0
        df_pages["external_outlinks_count"] = 0
        df_pages["inlinks_count"] = 0
        df_pages["source_url"] = df_pages.get("source_page", "")
        df_pages["anchor_text"] = ""

    # Determine starting seed URL (first crawled URL)
    start_url = crawled_pages[0].get("url") if crawled_pages else ""
    df_pages["is_orphan"] = (df_pages["inlinks_count"] == 0) & (df_pages["url"] != start_url)

    # Classify Response Description and Screaming Frog Response Category
    def classify_response(row):
        code = row.get("status_code", 0)
        err = str(row.get("error") or "").lower()
        has_meta = row.get("has_meta_refresh", False)
        has_js = row.get("has_js_redirect", False)
        is_noindex = bool(row.get("is_noindex", False) or ("noindex" in str(row.get("meta_robots", "")).lower()))

        # Status Description
        if code == 200:
            desc = "200 OK (Noindex)" if is_noindex else "200 OK"
        elif code == 201:
            desc = "201 Created"
        elif code == 204:
            desc = "204 No Content"
        elif code == 301:
            desc = "301 Moved Permanently"
        elif code == 302:
            desc = "302 Found"
        elif code == 307:
            desc = "307 Temporary Redirect"
        elif code == 308:
            desc = "308 Permanent Redirect"
        elif code == 400:
            desc = "400 Bad Request"
        elif code == 401:
            desc = "401 Unauthorized"
        elif code == 403:
            desc = "403 Forbidden"
        elif code == 404:
            desc = "404 Not Found"
        elif code == 410:
            desc = "410 Gone"
        elif code == 500:
            desc = "500 Internal Server Error"
        elif code == 502:
            desc = "502 Bad Gateway"
        elif code == 503:
            desc = "503 Service Unavailable"
        elif code == 504:
            desc = "504 Gateway Timeout"
        elif code == 0 or "timeout" in err or "failed" in err or "connection" in err:
            desc = f"No Response ({err[:25]})" if err else "No Response"
        else:
            desc = f"HTTP {code}"

        is_loop = row.get("is_redirect_loop", False)
        is_chain = row.get("is_redirect_chain", False)

        # Category for Screaming Frog filter parity
        if "robots" in err:
            cat = "Blocked by Robots.txt"
        elif is_noindex and 200 <= code < 300:
            cat = "Noindex (2xx)"
        elif code == 403 or (code != 200 and "blocked" in err):
            cat = "Blocked Resource"
        elif is_loop:
            cat = "Redirection (Loop)"
        elif is_chain:
            cat = "Redirection (Chain)"
        elif code == 0 or "timeout" in err or "failed" in err or "connection" in err:
            cat = "No Response"
        elif 200 <= code < 300:
            cat = "Success (2xx)"
        elif 300 <= code < 400:
            cat = "Redirection (3xx)"
        elif 400 <= code < 500:
            cat = "Client Error (4xx)"
        elif 500 <= code < 600:
            cat = "Server Error (5xx)"
        else:
            cat = "Other"

        return pd.Series([desc, cat], index=["status_description", "response_category"])

    if not df_pages.empty:
        resp_df = df_pages.apply(classify_response, axis=1)
        df_pages["status_description"] = resp_df["status_description"]
        df_pages["response_category"] = resp_df["response_category"]
    else:
        df_pages["status_description"] = []
        df_pages["response_category"] = []

    # Compute image stats per page
    if not df_images.empty and not df_pages.empty:
        img_counts = df_images.groupby("page_url").size().to_dict()
        img_missing_alt = df_images[df_images["has_alt"] == False].groupby("page_url").size().to_dict()
        img_over_100kb = df_images[df_images.get("is_over_100kb", False) == True].groupby("page_url").size().to_dict() if "is_over_100kb" in df_images.columns else {}
        df_pages["images_count"] = df_pages["url"].map(img_counts).fillna(0).astype(int)
        df_pages["images_missing_alt_count"] = df_pages["url"].map(img_missing_alt).fillna(0).astype(int)
        df_pages["images_over_100kb_count"] = df_pages["url"].map(img_over_100kb).fillna(0).astype(int)
    else:
        df_pages["images_count"] = 0
        df_pages["images_missing_alt_count"] = 0
        df_pages["images_over_100kb_count"] = 0

    # Detect duplicate Page Titles across the site (ONLY 200 OK & Indexable pages, ignoring pagination!)
    indexable_pages = df_pages[(df_pages["status_code"] == 200) & (df_pages["is_indexable"] == True)].copy()
    canon_col = indexable_pages["canonical_url"] if "canonical_url" in indexable_pages.columns else [""] * len(indexable_pages)
    
    indexable_pages["is_pagination"] = [
        is_pagination_url(u, c) for u, c in zip(indexable_pages["url"], canon_col)
    ]
    indexable_pages["base_url"] = [
        get_base_unpaginated_url(u, c) for u, c in zip(indexable_pages["url"], canon_col)
    ]

    valid_titles = indexable_pages[indexable_pages["title"].fillna("").str.strip() != ""]
    title_to_bases = valid_titles.groupby("title")["base_url"].apply(lambda s: set(s)).to_dict()
    duplicate_titles = {t for t, bases in title_to_bases.items() if len(bases) > 1}

    # Detect duplicate H1 Headings across the site (ONLY 200 OK & Indexable pages, ignoring pagination!)
    valid_h1s = indexable_pages[indexable_pages["h1"].fillna("").str.strip() != ""]
    h1_to_bases = valid_h1s.groupby("h1")["base_url"].apply(lambda s: set(s)).to_dict()
    duplicate_h1s = {h for h, bases in h1_to_bases.items() if len(bases) > 1}

    # Detect duplicate Meta Descriptions across the site (ONLY 200 OK & Indexable pages, ignoring pagination!)
    valid_descs = indexable_pages[indexable_pages["meta_description"].fillna("").str.strip() != ""]
    desc_to_bases = valid_descs.groupby("meta_description")["base_url"].apply(lambda s: set(s)).to_dict()
    duplicate_descriptions = {d for d, bases in desc_to_bases.items() if len(bases) > 1}

    # Add duplicate issues to individual pages & collect aggregated issue list
    all_issues = []
    
    for idx, row in df_pages.iterrows():
        issues_list = row["issues"]
        url = row["url"]
        can = row.get("canonical_url", "")
        is_paginated = is_pagination_url(url, can)

        # Only evaluate duplicate content warnings for 200 OK & Indexable pages that are NOT pagination pages
        if row["status_code"] == 200 and row.get("is_indexable", True) and not is_paginated:
            if row["title"] in duplicate_titles:
                issues_list.append({
                    "type": "Warning",
                    "category": "Page Title",
                    "issue": f"Duplicate Page Title ('{row['title'][:40]}...')",
                    "recommendation": "Ensure every page has a unique title describing its distinct content."
                })

            if row["h1"] in duplicate_h1s:
                issues_list.append({
                    "type": "Notice",
                    "category": "H1 Heading",
                    "issue": f"Duplicate H1 Heading ('{row['h1'][:40]}...')",
                    "recommendation": "Provide unique H1 tags for distinct pages."
                })

            if row["meta_description"] in duplicate_descriptions:
                issues_list.append({
                    "type": "Notice",
                    "category": "Meta Description",
                    "issue": "Duplicate Meta Description",
                    "recommendation": "Write tailored meta descriptions for key landing pages."
                })

        is_row_noindex = bool(row.get("is_noindex", False) or ("noindex" in str(row.get("meta_robots", "")).lower()))

        if row.get("is_orphan", False) and not is_row_noindex and row.get("is_indexable", True):
            issues_list.append({
                "type": "Warning",
                "category": "Architecture",
                "issue": "Orphan Page (0 Internal Inlinks)",
                "recommendation": "Add internal links pointing to this URL from navigation, category pages, or relevant articles."
            })

        if row.get("images_missing_alt_count", 0) > 0 and not is_row_noindex and row.get("is_indexable", True):
            issues_list.append({
                "type": "Warning",
                "category": "Images",
                "issue": f"{row['images_missing_alt_count']} images missing ALT text",
                "recommendation": "Add descriptive alt attributes to help image search and accessibility."
            })

        if row.get("images_over_100kb_count", 0) > 0 and not is_row_noindex and row.get("is_indexable", True):
            issues_list.append({
                "type": "Warning",
                "category": "Images",
                "issue": f"{row['images_over_100kb_count']} images over 100 KB",
                "recommendation": "Compress or convert images to next-gen WebP/AVIF format to keep file sizes under 100 KB and improve PageSpeed / Core Web Vitals (LCP)."
            })

        df_pages.at[idx, "issues"] = issues_list

        for issue in issues_list:
            all_issues.append({
                "url": url,
                "type": issue["type"],
                "category": issue["category"],
                "issue": issue["issue"],
                "recommendation": issue["recommendation"]
            })

    df_issues = pd.DataFrame(all_issues)

    # Calculate Overall SEO Health Score (0-100)
    total_pages = max(len(df_pages), 1)
    critical_errors = len(df_issues[df_issues["type"] == "Error"]) if not df_issues.empty else 0
    warnings = len(df_issues[df_issues["type"] == "Warning"]) if not df_issues.empty else 0
    notices = len(df_issues[df_issues["type"] == "Notice"]) if not df_issues.empty else 0

    # Weighted penalty normalized by total pages
    penalty = (critical_errors * 10 + warnings * 3 + notices * 0.5) / total_pages * 10
    health_score = max(0, min(100, round(100 - penalty)))

    # Count noindex pages
    c_noindex_pages = len(df_pages[(df_pages.get("is_noindex", False) == True) | (df_pages.get("meta_robots", "").fillna("").str.contains("noindex", case=False))]) if not df_pages.empty else 0

    return {
        "df_pages": df_pages,
        "df_issues": df_issues,
        "df_links": df_links,
        "df_images": df_images,
        "health_score": health_score,
        "summary": {
            "total_crawled": len(df_pages),
            "critical_errors": critical_errors,
            "warnings": warnings,
            "notices": notices,
            "health_score": health_score,
            "noindex_pages_count": c_noindex_pages,
            "duplicate_titles_count": len(duplicate_titles),
            "duplicate_descriptions_count": len(duplicate_descriptions),
            "duplicate_h1_count": len(duplicate_h1s),
            "orphan_pages_count": int(df_pages["is_orphan"].sum()) if not df_pages.empty and "is_orphan" in df_pages.columns else 0,
            "redirect_chains_count": int(df_pages["is_redirect_chain"].sum()) if not df_pages.empty and "is_redirect_chain" in df_pages.columns else 0,
            "redirect_loops_count": int(df_pages["is_redirect_loop"].sum()) if not df_pages.empty and "is_redirect_loop" in df_pages.columns else 0,
            "total_links": len(df_links),
            "total_images": len(df_images),
            "images_missing_alt_count": int(df_pages["images_missing_alt_count"].sum()) if not df_pages.empty and "images_missing_alt_count" in df_pages.columns else 0,
            "missing_titles_count": len(df_pages[(df_pages["title"].fillna("").str.strip() == "") & (df_pages["status_code"] == 200) & (df_pages.get("is_noindex", False) == False) & (df_pages["is_indexable"] == True)]) if not df_pages.empty and "title" in df_pages.columns else 0,
            "images_over_100kb_count": int(df_images["is_over_100kb"].sum()) if not df_images.empty and "is_over_100kb" in df_images.columns else 0
        }
    }

def extract_redirect_chain_instances(df_pages: pd.DataFrame, df_links: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts all redirect chain & loop instances matching Semrush and Screaming Frog format.
    Maps each internal hyperlink in df_links to its corresponding redirect chain,
    listing the exact Source Page, Initial Redirect URL, Length, and Final Destination URL.
    """
    if df_pages.empty:
        return pd.DataFrame()

    chain_mask = (df_pages.get("is_redirect_chain", False) == True) | (df_pages.get("is_redirect_loop", False) == True)
    chain_pages = df_pages[chain_mask]
    if chain_pages.empty:
        return pd.DataFrame()

    chain_map = {}
    for _, r in chain_pages.iterrows():
        u = str(r["url"]).strip()
        chain_urls = r.get("redirect_chain", []) or []
        hops = r.get("redirect_hops", max(len(chain_urls) - 1, 1) if chain_urls else 1)
        length = len(chain_urls) if chain_urls else (hops + 1)
        is_loop = bool(r.get("is_redirect_loop", False))
        chain_str = str(r.get("redirect_chain_str", "") or "")
        
        statuses = r.get("redirect_chain_statuses", []) or []
        if not statuses and chain_str:
            statuses = [int(s) for s in re.findall(r'\((\d{3})\)', chain_str)]
        if not statuses:
            statuses = [r.get("status_code", 301)] + [301] * max(len(chain_urls) - 2, 0) + [200]

        info = {
            "redirect_type": "loop" if is_loop else "chain",
            "length": length,
            "status_code": statuses[0] if statuses else r.get("status_code", 301),
            "final_url": r.get("final_url", u),
            "redirect_chain_str": chain_str,
            "redirect_chain": chain_urls,
            "statuses": statuses,
            "source_page_fallback": r.get("source_url", "")
        }
        chain_map[u] = info
        chain_map[u.rstrip("/")] = info
        chain_map[u.rstrip("/") + "/"] = info

    instances = []
    seen_pairs = set()

    if not df_links.empty:
        for _, l in df_links.iterrows():
            tgt = str(l.get("target_url", "")).strip()
            src = str(l.get("source_url", "")).strip()
            if not tgt or not src:
                continue

            inf = chain_map.get(tgt) or chain_map.get(tgt.rstrip("/")) or chain_map.get(tgt.rstrip("/") + "/")
            if inf:
                pair_key = (src, tgt)
                seen_pairs.add(pair_key)

                chain_list = inf["redirect_chain"]
                st_list = inf["statuses"]
                row_data = {
                    "Source Page": src,
                    "Redirect Type": inf["redirect_type"],
                    "Length": inf["length"],
                    "Initial Redirect URL": tgt,
                    "Status code of Initial Redirect URL": inf["status_code"],
                    "Final Destination URL": inf["final_url"],
                    "Anchor Text": str(l.get("anchor_text", "")),
                    "Redirect Path": inf["redirect_chain_str"],
                    "Recommended Action": f"Update link on Source Page directly to final destination '{inf['final_url']}'."
                }

                # Add intermediate and destination hops (URL 2, Status code of URL 2, URL 3...)
                if len(chain_list) > 1:
                    for hop_idx in range(1, len(chain_list)):
                        hop_num = hop_idx + 1
                        row_data[f"URL {hop_num}"] = chain_list[hop_idx]
                        hop_status = st_list[hop_idx] if hop_idx < len(st_list) else (200 if hop_idx == len(chain_list) - 1 else 301)
                        row_data[f"Status code of URL {hop_num}"] = hop_status

                instances.append(row_data)

    for _, r in chain_pages.iterrows():
        u = str(r["url"]).strip()
        inf = chain_map.get(u, {})
        has_instance = any(k[1] == u or k[1] == u.rstrip('/') for k in seen_pairs)
        if not has_instance:
            chain_list = inf.get("redirect_chain", [])
            st_list = inf.get("statuses", [])
            row_data = {
                "Source Page": r.get("source_url", "") or "Direct / Discovered URL",
                "Redirect Type": inf.get("redirect_type", "chain"),
                "Length": inf.get("length", 2),
                "Initial Redirect URL": u,
                "Status code of Initial Redirect URL": inf.get("status_code", 301),
                "Final Destination URL": inf.get("final_url", u),
                "Anchor Text": r.get("anchor_text", ""),
                "Redirect Path": inf.get("redirect_chain_str", ""),
                "Recommended Action": f"Update internal links directly to final destination '{inf.get('final_url', u)}'."
            }
            if len(chain_list) > 1:
                for hop_idx in range(1, len(chain_list)):
                    hop_num = hop_idx + 1
                    row_data[f"URL {hop_num}"] = chain_list[hop_idx]
                    hop_status = st_list[hop_idx] if hop_idx < len(st_list) else (200 if hop_idx == len(chain_list) - 1 else 301)
                    row_data[f"Status code of URL {hop_num}"] = hop_status

            instances.append(row_data)

    return pd.DataFrame(instances)

