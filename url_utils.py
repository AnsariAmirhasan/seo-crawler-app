"""
url_utils.py - Utility functions for URL parsing, pagination detection, and base canonical normalization.
"""

import re
import urllib.parse

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
