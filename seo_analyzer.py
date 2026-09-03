import re
import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
from collections import Counter

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

    seo_info = {
        "url": url,
        "final_url": final_url,
        "status_code": status_code,
        "depth": depth,
        "latency_ms": latency_ms,
        "size_kb": size_kb,
        "content_type": content_type,
        "error": error_msg,
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
        "h1_count": 0,
        "h2_count": 0,
        "h2_first": "",
        # Directives & Indexability
        "meta_robots": "",
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
        "images_count": 0,
        "images_missing_alt_count": 0,
        # Issues Detected on this page
        "issues": []
    }

    # Evaluate HTTP Status Issues
    if error_msg:
        seo_info["is_indexable"] = False
        seo_info["indexability_reason"] = f"Fetch Failed ({error_msg})"
        seo_info["issues"].append({
            "type": "Error",
            "category": "Status Code",
            "issue": f"Fetch Error: {error_msg}",
            "recommendation": "Fix server connectivity, DNS or SSL certificate configuration."
        })
        return seo_info

    if status_code >= 400:
        seo_info["is_indexable"] = False
        seo_info["indexability_reason"] = f"HTTP {status_code}"
        seo_info["issues"].append({
            "type": "Error",
            "category": "Status Code",
            "issue": f"Client/Server Error ({status_code})",
            "recommendation": f"Fix broken link or configure a 301 redirect if page moved."
        })
        return seo_info

    if 300 <= status_code < 400:
        seo_info["is_indexable"] = False
        seo_info["indexability_reason"] = f"Redirect ({status_code})"
        seo_info["issues"].append({
            "type": "Notice",
            "category": "Redirect",
            "issue": f"Page Redirects ({status_code}) -> {final_url}",
            "recommendation": "Update internal links to point directly to the destination URL."
        })

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

    # 1. Page Titles
    title_tags = soup.find_all("title")
    seo_info["title_count"] = len(title_tags)
    if title_tags:
        title_text = title_tags[0].get_text(strip=True)
        seo_info["title"] = title_text
        seo_info["title_length"] = len(title_text)
        seo_info["title_pixel_width"] = estimate_pixel_width(title_text)

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
        seo_info["issues"].append({
            "type": "Error",
            "category": "Page Title",
            "issue": "Missing <title> tag",
            "recommendation": "Add a unique <title> tag to every indexable page."
        })

    # 2. Meta Descriptions
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_desc and meta_desc.get("content"):
        desc_text = meta_desc["content"].strip()
        seo_info["meta_description"] = desc_text
        seo_info["meta_description_length"] = len(desc_text)

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
        seo_info["issues"].append({
            "type": "Warning",
            "category": "Meta Description",
            "issue": "Missing Meta Description",
            "recommendation": "Add a unique and compelling meta description summarizing the page content."
        })

    # 3. Headings (H1 & H2)
    h1_tags = soup.find_all("h1")
    seo_info["h1_count"] = len(h1_tags)
    if h1_tags:
        seo_info["h1"] = h1_tags[0].get_text(strip=True)
        if len(h1_tags) > 1:
            seo_info["issues"].append({
                "type": "Warning",
                "category": "H1 Heading",
                "issue": f"Multiple H1 tags found ({len(h1_tags)})",
                "recommendation": "Use exactly one primary H1 tag per page for clean structural hierarchy."
            })
    else:
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
    else:
        seo_info["issues"].append({
            "type": "Notice",
            "category": "H2 Heading",
            "issue": "No H2 subheadings found",
            "recommendation": "Structure content with H2 tags to improve scannability and topic coverage."
        })

    # 4. Meta Robots & Indexability
    meta_robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    if meta_robots and meta_robots.get("content"):
        robots_content = meta_robots["content"].lower()
        seo_info["meta_robots"] = robots_content
        if "noindex" in robots_content:
            seo_info["is_indexable"] = False
            seo_info["indexability_reason"] = "Blocked by meta robots noindex"
            seo_info["issues"].append({
                "type": "Notice",
                "category": "Indexability",
                "issue": "Meta robots contains 'noindex'",
                "recommendation": "Verify if this page is intentionally hidden from search engines."
            })
        if "nofollow" in robots_content:
            seo_info["issues"].append({
                "type": "Notice",
                "category": "Indexability",
                "issue": "Meta robots contains 'nofollow'",
                "recommendation": "Ensure internal link juice is not inadvertently blocked."
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
            seo_info["issues"].append({
                "type": "Notice",
                "category": "Canonical",
                "issue": f"Canonical points to alternative URL: {canon_url}",
                "recommendation": "Verify that this canonical target is the desired master version to consolidate link equity."
            })
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

    if seo_info["is_indexable"] and len(words) < 250:
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

    if not seo_info["og_title"] or not seo_info["og_image"]:
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

def analyze_crawl_results(crawled_pages: list, all_links: list, all_images: list):
    """Aggregate all page audits, compute site-wide duplicates, metrics, and health score."""
    pages_audit = []
    
    for page in crawled_pages:
        audit = parse_page_seo(page, all_links, all_images)
        pages_audit.append(audit)

    df_pages = pd.DataFrame(pages_audit)
    df_links = pd.DataFrame(all_links) if all_links else pd.DataFrame(columns=["source_url", "target_url", "anchor_text", "is_internal", "nofollow", "rel"])
    df_images = pd.DataFrame(all_images) if all_images else pd.DataFrame(columns=["page_url", "image_url", "alt", "has_alt", "loading"])

    # Compute link stats per page
    if not df_links.empty and not df_pages.empty:
        internal_outlinks = df_links[df_links["is_internal"] == True].groupby("source_url").size().to_dict()
        external_outlinks = df_links[df_links["is_internal"] == False].groupby("source_url").size().to_dict()
        df_pages["internal_outlinks_count"] = df_pages["url"].map(internal_outlinks).fillna(0).astype(int)
        df_pages["external_outlinks_count"] = df_pages["url"].map(external_outlinks).fillna(0).astype(int)

    # Compute image stats per page
    if not df_images.empty and not df_pages.empty:
        img_counts = df_images.groupby("page_url").size().to_dict()
        img_missing_alt = df_images[df_images["has_alt"] == False].groupby("page_url").size().to_dict()
        df_pages["images_count"] = df_pages["url"].map(img_counts).fillna(0).astype(int)
        df_pages["images_missing_alt_count"] = df_pages["url"].map(img_missing_alt).fillna(0).astype(int)

    # Detect duplicate Page Titles across the site
    title_counts = Counter(df_pages[df_pages["title"] != ""]["title"])
    duplicate_titles = {t for t, count in title_counts.items() if count > 1}

    # Detect duplicate H1 Headings across the site
    h1_counts = Counter(df_pages[df_pages["h1"] != ""]["h1"])
    duplicate_h1s = {h for h, count in h1_counts.items() if count > 1}

    # Detect duplicate Meta Descriptions across the site
    desc_counts = Counter(df_pages[df_pages["meta_description"] != ""]["meta_description"])
    duplicate_descriptions = {d for d, count in desc_counts.items() if count > 1}

    # Add duplicate issues to individual pages & collect aggregated issue list
    all_issues = []
    
    for idx, row in df_pages.iterrows():
        issues_list = row["issues"]
        url = row["url"]

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

        if row["images_missing_alt_count"] > 0:
            issues_list.append({
                "type": "Warning",
                "category": "Images",
                "issue": f"{row['images_missing_alt_count']} images missing ALT text",
                "recommendation": "Add descriptive alt attributes to help image search and accessibility."
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
            "duplicate_titles_count": len(duplicate_titles),
            "duplicate_h1_count": len(duplicate_h1s),
            "total_links": len(df_links),
            "total_images": len(df_images)
        }
    }
