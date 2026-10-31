import os
import re
import time
import json
from urllib.parse import urlparse, urljoin
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup

# Initialize FastAPI app for Vercel
app = FastAPI(
    title="CrawlPilot — SEO Crawler & Audit Suite",
    description="High-speed Technical SEO Crawler & Deep Audit Web Application",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_AGENT = "Mozilla/5.0 (compatible; CrawlPilotBot/2.0; +https://crawlpilot.vercel.app)"

def audit_single_url(target_url: str) -> Dict[str, Any]:
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    parsed_target = urlparse(target_url)
    domain = parsed_target.netloc

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    start_time = time.time()
    try:
        resp = requests.get(target_url, headers=headers, timeout=12, allow_redirects=True)
        response_time_ms = int((time.time() - start_time) * 1000)
    except Exception as e:
        return {
            "error": True,
            "message": f"Could not connect to {target_url}: {str(e)}",
            "url": target_url,
        }

    final_url = resp.url
    status_code = resp.status_code
    page_size_kb = round(len(resp.content) / 1024, 2)
    content_type = resp.headers.get("content-type", "")

    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return {
            "error": False,
            "url": final_url,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "page_size_kb": page_size_kb,
            "message": f"Non-HTML content type: {content_type}",
            "health_score": 50,
            "issues": [{"type": "warning", "msg": f"URL returned non-HTML content: {content_type}"}],
            "headings": {"h1": [], "h2": [], "h3": []},
            "meta": {},
            "links": {"internal": 0, "external": 0, "items": []},
            "images": {"total": 0, "missing_alt": 0, "items": []},
            "schema": []
        }

    soup = BeautifulSoup(resp.text, "lxml" if "lxml" in globals() else "html.parser")

    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    title_len = len(title)

    # Meta Description
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
    desc_len = len(meta_desc)

    # Meta Robots
    meta_robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    meta_robots = meta_robots_tag.get("content", "").strip() if meta_robots_tag else "index, follow"

    # Canonical
    canonical_tag = soup.find("link", attrs={"rel": re.compile(r"^canonical$", re.I)})
    canonical_url = canonical_tag.get("href", "").strip() if canonical_tag else ""
    if canonical_url:
        canonical_url = urljoin(final_url, canonical_url)

    # Open Graph & Social Cards
    og_title = (soup.find("meta", property="og:title") or {}).get("content", "")
    og_desc = (soup.find("meta", property="og:description") or {}).get("content", "")
    og_image = (soup.find("meta", property="og:image") or {}).get("content", "")
    if og_image:
        og_image = urljoin(final_url, og_image)
    twitter_card = (soup.find("meta", attrs={"name": "twitter:card"}) or {}).get("content", "")

    # Headings
    h1s = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]
    h2s = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)][:15]
    h3s = [h.get_text(strip=True) for h in soup.find_all("h3") if h.get_text(strip=True)][:15]

    # Word Count & Text
    body = soup.find("body")
    text_content = body.get_text(separator=" ", strip=True) if body else ""
    words = [w for w in text_content.split() if len(w) > 1]
    word_count = len(words)

    # Images Audit
    img_tags = soup.find_all("img")
    images_list = []
    missing_alt_count = 0
    for img in img_tags:
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue
        full_src = urljoin(final_url, src)
        alt = img.get("alt", None)
        is_missing = alt is None or alt.strip() == ""
        if is_missing:
            missing_alt_count += 1
        images_list.append({
            "src": full_src,
            "alt": alt if alt else "(Missing alt text)",
            "has_alt": not is_missing
        })

    # Links Audit
    internal_links = 0
    external_links = 0
    links_sample = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_href = urljoin(final_url, href)
        parsed_href = urlparse(full_href)
        is_internal = parsed_href.netloc == domain
        if is_internal:
            internal_links += 1
        else:
            external_links += 1
        
        if len(links_sample) < 30:
            anchor_text = a.get_text(strip=True) or "(No text / Image)"
            links_sample.append({
                "href": full_href,
                "text": anchor_text[:60],
                "type": "Internal" if is_internal else "External"
            })

    # Schema JSON-LD
    schema_items = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            raw_text = s.string or ""
            data = json.loads(raw_text)
            schema_type = data.get("@type", "Schema") if isinstance(data, dict) else "JSON-LD"
            schema_items.append({"type": str(schema_type), "raw": data})
        except Exception:
            schema_items.append({"type": "Invalid JSON-LD", "raw": {}})

    # Calculate SEO Score (0 to 100) and Identify Issues
    score = 100
    issues = []
    good_checks = []

    # 1. HTTP Status
    if status_code == 200:
        good_checks.append("HTTP 200 OK Status returned.")
    elif status_code in (301, 302):
        score -= 10
        issues.append({"type": "warning", "title": "Redirect Detected", "desc": f"Redirected to {final_url} (HTTP {status_code})."})
    else:
        score -= 40
        issues.append({"type": "critical", "title": "Error Status Code", "desc": f"Page returned HTTP {status_code}."})

    # 2. Page Title
    if not title:
        score -= 20
        issues.append({"type": "critical", "title": "Missing Title Tag", "desc": "The page has no <title> tag. Critical for rankings."})
    elif title_len < 30:
        score -= 8
        issues.append({"type": "warning", "title": "Short Title Tag", "desc": f"Title is only {title_len} chars. Recommended 50-60 chars."})
    elif title_len > 65:
        score -= 5
        issues.append({"type": "warning", "title": "Long Title Tag", "desc": f"Title is {title_len} chars. Might truncate on Google SERP."})
    else:
        good_checks.append(f"Optimal Title length ({title_len} characters).")

    # 3. Meta Description
    if not meta_desc:
        score -= 15
        issues.append({"type": "critical", "title": "Missing Meta Description", "desc": "No meta description found. Google may show generic text."})
    elif desc_len < 70:
        score -= 6
        issues.append({"type": "warning", "title": "Short Meta Description", "desc": f"Meta description is only {desc_len} chars. Recommended 120-160."})
    elif desc_len > 165:
        score -= 4
        issues.append({"type": "warning", "title": "Long Meta Description", "desc": f"Meta description is {desc_len} chars. Might truncate on mobile."})
    else:
        good_checks.append(f"Optimal Meta Description length ({desc_len} characters).")

    # 4. Heading H1
    if len(h1s) == 0:
        score -= 15
        issues.append({"type": "critical", "title": "Missing H1 Heading", "desc": "Page does not have any <h1> heading tag."})
    elif len(h1s) > 1:
        score -= 5
        issues.append({"type": "warning", "title": "Multiple H1 Headings", "desc": f"Found {len(h1s)} <h1> tags. Best practice is exactly one per page."})
    else:
        good_checks.append(f"Single H1 tag properly configured: \"{h1s[0][:40]}...\"")

    # 5. Canonical Tag
    if not canonical_url:
        score -= 8
        issues.append({"type": "warning", "title": "Missing Canonical Tag", "desc": "No rel=\"canonical\" tag found to avoid duplicate content."})
    else:
        good_checks.append("Canonical tag is configured correctly.")

    # 6. Images Alt Text
    if missing_alt_count > 0:
        score -= min(15, missing_alt_count * 3)
        issues.append({
            "type": "warning" if missing_alt_count < 5 else "critical",
            "title": f"{missing_alt_count} Images Missing Alt Text",
            "desc": f"{missing_alt_count} out of {len(images_list)} images are missing alt attributes."
        })
    elif len(images_list) > 0:
        good_checks.append(f"All {len(images_list)} images have alt attributes.")

    # 7. Word Count (Thin Content)
    if word_count < 300:
        score -= 12
        issues.append({"type": "warning", "title": "Thin Content Alert", "desc": f"Only {word_count} words found. Search engines favor comprehensive content (>= 300+ words)."})
    else:
        good_checks.append(f"Healthy content volume ({word_count} words).")

    # 8. Open Graph & Social
    if not og_title or not og_image:
        score -= 6
        issues.append({"type": "warning", "title": "Incomplete Open Graph Tags", "desc": "Missing og:title or og:image for rich social media cards."})
    else:
        good_checks.append("Open Graph social cards fully configured.")

    # 9. Response Time
    if response_time_ms > 1500:
        score -= 10
        issues.append({"type": "warning", "title": "Slow Response Time", "desc": f"Server took {response_time_ms}ms to respond. Target < 600ms."})
    else:
        good_checks.append(f"Fast server response speed ({response_time_ms}ms).")

    # Final score clamping
    health_score = max(5, min(100, score))

    return {
        "error": False,
        "url": final_url,
        "domain": domain,
        "status_code": status_code,
        "response_time_ms": response_time_ms,
        "page_size_kb": page_size_kb,
        "health_score": health_score,
        "title": title,
        "title_length": title_len,
        "meta_description": meta_desc,
        "meta_desc_length": desc_len,
        "meta_robots": meta_robots,
        "canonical_url": canonical_url,
        "open_graph": {
            "title": og_title or title,
            "description": og_desc or meta_desc,
            "image": og_image,
            "twitter_card": twitter_card
        },
        "headings": {
            "h1": h1s,
            "h2": h2s,
            "h3": h3s
        },
        "word_count": word_count,
        "links": {
            "internal": internal_links,
            "external": external_links,
            "total": internal_links + external_links,
            "sample": links_sample
        },
        "images": {
            "total": len(images_list),
            "missing_alt": missing_alt_count,
            "sample": images_list[:25]
        },
        "schema": schema_items,
        "issues": issues,
        "good_checks": good_checks
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "CrawlPilot Vercel Edition", "version": "2.0.0"}

@app.get("/api/audit")
def api_audit(url: str = Query(..., description="Target website URL to audit")):
    result = audit_single_url(url)
    return JSONResponse(content=result)

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CrawlPilot — Technical SEO Crawler & Audit Suite</title>
  <meta name="description" content="Modern, high-speed Technical SEO Crawler & Audit SaaS Web Application. Built for Vercel.">
  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Lucide Icons -->
  <script src="https://unpkg.com/lucide@latest"></script>
  <!-- Chart.js -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          },
          colors: {
            brand: {
              50: '#f0fdf4',
              100: '#dcfce7',
              500: '#10b981',
              600: '#059669',
              700: '#047857',
            },
            dark: {
              bg: '#090d16',
              surface: '#111827',
              border: '#1f293d',
            }
          }
        }
      }
    }
  </script>
  <style>
    body {
      background-color: #090d16;
      color: #f3f4f6;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .glass-card {
      background: rgba(17, 24, 39, 0.75);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .glass-glow {
      box-shadow: 0 0 30px -5px rgba(16, 185, 129, 0.15);
    }
    .gradient-text {
      background: linear-gradient(135deg, #34d399 0%, #38bdf8 50%, #818cf8 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .score-circle {
      transition: stroke-dashoffset 1s ease-in-out;
    }
    /* Custom scrollbar */
    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: #090d16;
    }
    ::-webkit-scrollbar-thumb {
      background: #1f293d;
      border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #374151;
    }
  </style>
</head>
<body class="min-h-screen flex flex-col antialiased selection:bg-emerald-500 selection:text-white">

  <!-- Navbar -->
  <header class="sticky top-0 z-50 glass-card border-b border-gray-800/80 px-4 lg:px-8 py-3.5">
    <div class="max-w-7xl mx-auto flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center text-xl shadow-lg shadow-emerald-500/20">
          🕷️
        </div>
        <div>
          <div class="flex items-center gap-2">
            <span class="text-xl font-bold tracking-tight text-white">CrawlPilot</span>
            <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Vercel Edition</span>
          </div>
          <p class="text-xs text-gray-400 hidden sm:block">Technical SEO Crawler & Audit Suite</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2 px-3 py-1 rounded-full bg-gray-900 border border-gray-800 text-xs text-gray-300">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>Engine Online</span>
        </div>
        <a href="https://github.com/AnsariAmirhasan/seo-crawler-app" target="_blank" class="px-3.5 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs font-medium text-gray-200 transition flex items-center gap-1.5 border border-gray-700">
          <i data-lucide="github" class="w-3.5 h-3.5"></i>
          <span>GitHub</span>
        </a>
      </div>
    </div>
  </header>

  <!-- Hero & Search Section -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 py-8 lg:py-12 space-y-8">
    <div class="text-center max-w-3xl mx-auto space-y-4">
      <div class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
        <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
        <span>Deep Technical SEO Intelligence • Instant Cloud Audit</span>
      </div>
      <h1 class="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight">
        Audit. Optimize. <span class="gradient-text">Rank Higher.</span>
      </h1>
      <p class="text-gray-400 text-sm sm:text-base leading-relaxed">
        Uncover critical SEO errors, broken tags, heading hierarchies, indexability issues, and social card previews in seconds.
      </p>

      <!-- URL Search Bar -->
      <form id="auditForm" class="pt-4 max-w-2xl mx-auto">
        <div class="relative flex items-center rounded-2xl glass-card border border-emerald-500/30 p-2 shadow-2xl glass-glow focus-within:border-emerald-500 transition-all">
          <div class="pl-3 pr-2 text-gray-400">
            <i data-lucide="globe" class="w-5 h-5"></i>
          </div>
          <input 
            type="text" 
            id="urlInput" 
            placeholder="Enter website URL (e.g. stripe.com or https://example.com)" 
            required
            class="flex-1 bg-transparent px-2 py-3 text-white text-sm sm:text-base focus:outline-none placeholder-gray-500"
          />
          <button 
            type="submit" 
            id="submitBtn"
            class="px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-semibold text-sm transition shadow-lg shadow-emerald-500/25 flex items-center gap-2 disabled:opacity-50"
          >
            <span id="btnText">Audit Now</span>
            <i id="btnIcon" data-lucide="arrow-right" class="w-4 h-4"></i>
            <svg id="btnSpinner" class="hidden animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
          </button>
        </div>
      </form>

      <!-- Preset Demos -->
      <div class="flex flex-wrap items-center justify-center gap-2 pt-1 text-xs text-gray-400">
        <span>Quick Try:</span>
        <button onclick="runPreset('https://stripe.com')" class="px-2.5 py-1 rounded-md bg-gray-900 border border-gray-800 hover:border-emerald-500/50 hover:text-white transition">stripe.com</button>
        <button onclick="runPreset('https://vercel.com')" class="px-2.5 py-1 rounded-md bg-gray-900 border border-gray-800 hover:border-emerald-500/50 hover:text-white transition">vercel.com</button>
        <button onclick="runPreset('https://github.com')" class="px-2.5 py-1 rounded-md bg-gray-900 border border-gray-800 hover:border-emerald-500/50 hover:text-white transition">github.com</button>
      </div>
    </div>

    <!-- Loading State Skeleton -->
    <div id="loadingBox" class="hidden glass-card rounded-2xl p-12 text-center space-y-4 max-w-xl mx-auto border border-emerald-500/20">
      <div class="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400 animate-bounce">
        <i data-lucide="activity" class="w-8 h-8"></i>
      </div>
      <h3 class="text-xl font-bold text-white">Crawling & Auditing Website...</h3>
      <p class="text-sm text-gray-400">Fetching DOM, inspecting meta tags, checking response time, and parsing social previews.</p>
      <div class="w-full bg-gray-800 rounded-full h-2 overflow-hidden">
        <div class="bg-gradient-to-r from-emerald-500 to-cyan-500 h-2 rounded-full animate-pulse w-3/4"></div>
      </div>
    </div>

    <!-- Error Box -->
    <div id="errorBox" class="hidden glass-card rounded-2xl p-6 border border-rose-500/30 bg-rose-500/5 max-w-2xl mx-auto flex items-start gap-4">
      <div class="p-2 rounded-lg bg-rose-500/20 text-rose-400">
        <i data-lucide="alert-triangle" class="w-6 h-6"></i>
      </div>
      <div>
        <h4 class="text-base font-semibold text-rose-300">Audit Request Failed</h4>
        <p id="errorMsg" class="text-sm text-gray-300 mt-1"></p>
      </div>
    </div>

    <!-- Audit Results Container -->
    <div id="resultsContainer" class="hidden space-y-8">
      
      <!-- Top Action Bar -->
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 glass-card p-5 rounded-2xl border border-gray-800">
        <div>
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
            <span class="text-xs uppercase font-bold tracking-wider text-gray-400">Audited Target</span>
          </div>
          <h2 id="auditedUrl" class="text-xl font-extrabold text-white mt-0.5 truncate max-w-xl"></h2>
        </div>

        <div class="flex items-center gap-2">
          <button onclick="downloadJsonReport()" class="px-3.5 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-xs font-semibold text-gray-200 transition flex items-center gap-1.5 border border-gray-700">
            <i data-lucide="download" class="w-4 h-4"></i>
            <span>Export JSON</span>
          </button>
          <button onclick="downloadCsvReport()" class="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white transition flex items-center gap-1.5 shadow-md shadow-emerald-600/30">
            <i data-lucide="file-spreadsheet" class="w-4 h-4"></i>
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      <!-- KPI Summary Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Score Card -->
        <div class="glass-card rounded-2xl p-5 border border-gray-800 flex items-center gap-4">
          <div class="relative w-20 h-20 flex-shrink-0">
            <svg class="w-20 h-20 transform -rotate-90" viewBox="0 0 36 36">
              <path class="text-gray-800" stroke-width="3.5" stroke="currentColor" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
              <path id="scorePath" class="score-circle text-emerald-500" stroke-width="3.5" stroke-dasharray="100, 100" stroke="currentColor" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
            </svg>
            <div class="absolute inset-0 flex items-center justify-center flex-col">
              <span id="scoreText" class="text-xl font-extrabold text-white">0</span>
              <span class="text-[9px] uppercase tracking-wider text-gray-400">Score</span>
            </div>
          </div>
          <div>
            <span class="text-xs font-medium text-gray-400">SEO Health Grade</span>
            <h4 id="healthGrade" class="text-lg font-bold text-emerald-400">Calculating...</h4>
            <span id="scoreSummary" class="text-xs text-gray-500">Based on 12+ checks</span>
          </div>
        </div>

        <!-- Passed Checks -->
        <div class="glass-card rounded-2xl p-5 border border-gray-800">
          <div class="flex items-center justify-between text-gray-400 mb-2">
            <span class="text-xs font-medium">Passed Checks</span>
            <div class="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
              <i data-lucide="check-circle-2" class="w-4 h-4"></i>
            </div>
          </div>
          <div class="text-3xl font-extrabold text-white" id="passedCount">0</div>
          <p class="text-xs text-emerald-400 mt-1 flex items-center gap-1">
            <i data-lucide="trending-up" class="w-3.5 h-3.5"></i> Ranking signals ready
          </p>
        </div>

        <!-- Issues Card -->
        <div class="glass-card rounded-2xl p-5 border border-gray-800">
          <div class="flex items-center justify-between text-gray-400 mb-2">
            <span class="text-xs font-medium">Issues to Fix</span>
            <div class="p-1.5 rounded-lg bg-amber-500/10 text-amber-400">
              <i data-lucide="alert-circle" class="w-4 h-4"></i>
            </div>
          </div>
          <div class="text-3xl font-extrabold text-white" id="issuesCount">0</div>
          <p class="text-xs text-amber-400 mt-1" id="issuesSubtitle">0 critical, 0 warnings</p>
        </div>

        <!-- Performance / Speed -->
        <div class="glass-card rounded-2xl p-5 border border-gray-800">
          <div class="flex items-center justify-between text-gray-400 mb-2">
            <span class="text-xs font-medium">Speed & Weight</span>
            <div class="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400">
              <i data-lucide="zap" class="w-4 h-4"></i>
            </div>
          </div>
          <div class="text-3xl font-extrabold text-white" id="speedText">0ms</div>
          <p class="text-xs text-gray-400 mt-1" id="pageSizeText">Page Size: 0 KB</p>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="flex border-b border-gray-800 space-x-2 overflow-x-auto pb-1">
        <button onclick="switchTab('overviewTab', this)" class="tab-btn px-4 py-2.5 rounded-xl font-semibold text-xs sm:text-sm bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-2 whitespace-nowrap">
          <i data-lucide="layout-dashboard" class="w-4 h-4"></i> Overview & Issues
        </button>
        <button onclick="switchTab('serpTab', this)" class="tab-btn px-4 py-2.5 rounded-xl font-medium text-xs sm:text-sm text-gray-400 hover:text-white hover:bg-gray-800/50 flex items-center gap-2 whitespace-nowrap">
          <i data-lucide="search" class="w-4 h-4"></i> SERP & Social Preview
        </button>
        <button onclick="switchTab('contentTab', this)" class="tab-btn px-4 py-2.5 rounded-xl font-medium text-xs sm:text-sm text-gray-400 hover:text-white hover:bg-gray-800/50 flex items-center gap-2 whitespace-nowrap">
          <i data-lucide="heading" class="w-4 h-4"></i> Headings & Content
        </button>
        <button onclick="switchTab('linksImagesTab', this)" class="tab-btn px-4 py-2.5 rounded-xl font-medium text-xs sm:text-sm text-gray-400 hover:text-white hover:bg-gray-800/50 flex items-center gap-2 whitespace-nowrap">
          <i data-lucide="image" class="w-4 h-4"></i> Links & Images
        </button>
        <button onclick="switchTab('technicalTab', this)" class="tab-btn px-4 py-2.5 rounded-xl font-medium text-xs sm:text-sm text-gray-400 hover:text-white hover:bg-gray-800/50 flex items-center gap-2 whitespace-nowrap">
          <i data-lucide="code" class="w-4 h-4"></i> Technical & Schema
        </button>
      </div>

      <!-- TAB 1: Overview & Issues -->
      <div id="overviewTab" class="tab-pane space-y-6">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Issues List (Left 2 cols) -->
          <div class="lg:col-span-2 glass-card rounded-2xl p-6 border border-gray-800 space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="text-base font-bold text-white flex items-center gap-2">
                <i data-lucide="list-checks" class="w-5 h-5 text-emerald-400"></i> Audit Findings
              </h3>
              <span id="issuesFilterBadge" class="text-xs px-2.5 py-1 rounded-full bg-gray-800 text-gray-300">All Insights</span>
            </div>

            <!-- Issues List Container -->
            <div id="issuesList" class="space-y-3 max-h-[480px] overflow-y-auto pr-2"></div>
          </div>

          <!-- Quick Specs & Directives (Right 1 col) -->
          <div class="space-y-6">
            <div class="glass-card rounded-2xl p-6 border border-gray-800 space-y-4">
              <h3 class="text-base font-bold text-white flex items-center gap-2">
                <i data-lucide="sliders" class="w-5 h-5 text-cyan-400"></i> Directives
              </h3>
              <div class="space-y-3 text-xs">
                <div class="flex items-center justify-between p-3 rounded-xl bg-gray-900 border border-gray-800">
                  <span class="text-gray-400">HTTP Status</span>
                  <span id="specStatus" class="font-bold text-emerald-400">200 OK</span>
                </div>
                <div class="flex items-center justify-between p-3 rounded-xl bg-gray-900 border border-gray-800">
                  <span class="text-gray-400">Robots Directive</span>
                  <span id="specRobots" class="font-mono text-cyan-400 truncate max-w-[150px]">index, follow</span>
                </div>
                <div class="flex items-center justify-between p-3 rounded-xl bg-gray-900 border border-gray-800">
                  <span class="text-gray-400">Word Count</span>
                  <span id="specWordCount" class="font-bold text-white">0 words</span>
                </div>
                <div class="flex items-center justify-between p-3 rounded-xl bg-gray-900 border border-gray-800">
                  <span class="text-gray-400">Internal Links</span>
                  <span id="specInLinks" class="font-bold text-white">0</span>
                </div>
                <div class="flex items-center justify-between p-3 rounded-xl bg-gray-900 border border-gray-800">
                  <span class="text-gray-400">Images Missing Alt</span>
                  <span id="specAltMissing" class="font-bold text-amber-400">0</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 2: SERP & Social Preview -->
      <div id="serpTab" class="tab-pane hidden space-y-6">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Google SERP Card -->
          <div class="glass-card rounded-2xl p-6 border border-gray-800 space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="text-base font-bold text-white flex items-center gap-2">
                <i data-lucide="chrome" class="w-5 h-5 text-blue-400"></i> Google SERP Snippet Simulator
              </h3>
              <span class="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">Desktop Preview</span>
            </div>
            
            <div class="p-5 rounded-xl bg-[#202124] border border-gray-700/80 space-y-1.5 font-sans">
              <div class="flex items-center gap-2 text-xs text-[#bdc1c6] truncate">
                <span class="w-4 h-4 rounded-full bg-gray-700 flex items-center justify-center text-[10px]">🌐</span>
                <span id="serpDomain" class="font-mono">https://example.com</span>
              </div>
              <h4 id="serpTitle" class="text-lg text-[#8ab4f8] hover:underline cursor-pointer font-medium leading-snug truncate">
                Page Title Goes Here
              </h4>
              <p id="serpDesc" class="text-xs text-[#bdc1c6] line-clamp-2 leading-relaxed">
                Meta description preview snippet...
              </p>
            </div>

            <div class="grid grid-cols-2 gap-3 text-xs pt-2">
              <div class="p-3 rounded-xl bg-gray-900 border border-gray-800">
                <span class="text-gray-400 block">Title Length</span>
                <span id="serpTitleLen" class="text-sm font-bold text-white">0 chars</span>
                <span class="text-[10px] text-gray-500 block">Optimal: 50-60 chars</span>
              </div>
              <div class="p-3 rounded-xl bg-gray-900 border border-gray-800">
                <span class="text-gray-400 block">Description Length</span>
                <span id="serpDescLen" class="text-sm font-bold text-white">0 chars</span>
                <span class="text-[10px] text-gray-500 block">Optimal: 120-160 chars</span>
              </div>
            </div>
          </div>

          <!-- Social Card (Open Graph) Preview -->
          <div class="glass-card rounded-2xl p-6 border border-gray-800 space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="text-base font-bold text-white flex items-center gap-2">
                <i data-lucide="share-2" class="w-5 h-5 text-indigo-400"></i> Open Graph Social Preview
              </h3>
              <span class="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">Facebook / LinkedIn</span>
            </div>

            <div class="rounded-xl overflow-hidden border border-gray-800 bg-gray-900">
              <div id="ogImageBox" class="w-full h-44 bg-gray-800 flex items-center justify-center text-gray-500 overflow-hidden">
                <img id="ogImage" src="" alt="OG Image Preview" class="w-full h-full object-cover hidden" onerror="this.classList.add('hidden')">
                <span id="noOgImgMsg" class="text-xs flex items-center gap-1.5"><i data-lucide="image-off" class="w-4 h-4"></i> No og:image tag found</span>
              </div>
              <div class="p-4 space-y-1">
                <span id="ogDomain" class="text-[10px] font-mono uppercase text-gray-400">EXAMPLE.COM</span>
                <h4 id="ogTitle" class="text-sm font-bold text-white truncate">OG Title</h4>
                <p id="ogDesc" class="text-xs text-gray-400 line-clamp-2">OG Description</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 3: Headings & Content -->
      <div id="contentTab" class="tab-pane hidden space-y-6">
        <div class="glass-card rounded-2xl p-6 border border-gray-800 space-y-6">
          <h3 class="text-base font-bold text-white flex items-center gap-2">
            <i data-lucide="heading-1" class="w-5 h-5 text-emerald-400"></i> Heading Structure Hierarchy
          </h3>

          <!-- H1s -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs uppercase font-bold text-emerald-400 tracking-wider">H1 Tags (<span id="h1Count">0</span>)</span>
              <span class="text-[10px] text-gray-400">Requirement: Exactly 1 per page</span>
            </div>
            <div id="h1List" class="space-y-1.5"></div>
          </div>

          <!-- H2s -->
          <div class="space-y-2 pt-2 border-t border-gray-800">
            <div class="flex items-center justify-between">
              <span class="text-xs uppercase font-bold text-cyan-400 tracking-wider">H2 Subheadings (<span id="h2Count">0</span>)</span>
            </div>
            <div id="h2List" class="grid grid-cols-1 md:grid-cols-2 gap-2"></div>
          </div>
        </div>
      </div>

      <!-- TAB 4: Links & Images -->
      <div id="linksImagesTab" class="tab-pane hidden space-y-6">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Images Table -->
          <div class="glass-card rounded-2xl p-6 border border-gray-800 space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="text-base font-bold text-white flex items-center gap-2">
                <i data-lucide="image" class="w-5 h-5 text-amber-400"></i> Images Audit (<span id="totalImgCount">0</span>)
              </h3>
              <span id="imgAltBadge" class="text-xs px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400">0 Missing Alt</span>
            </div>
            <div class="overflow-x-auto max-h-96 pr-1">
              <table class="w-full text-left text-xs">
                <thead class="text-gray-400 border-b border-gray-800">
                  <tr>
                    <th class="pb-2">Image Source</th>
                    <th class="pb-2">Alt Text</th>
                  </tr>
                </thead>
                <tbody id="imagesTableBody" class="divide-y divide-gray-800/50"></tbody>
              </table>
            </div>
          </div>

          <!-- Links Sample -->
          <div class="glass-card rounded-2xl p-6 border border-gray-800 space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="text-base font-bold text-white flex items-center gap-2">
                <i data-lucide="link" class="w-5 h-5 text-indigo-400"></i> Discovered Links (<span id="totalLinkCount">0</span>)
              </h3>
              <span id="linkRatioBadge" class="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400">0 Internal / 0 External</span>
            </div>
            <div class="overflow-x-auto max-h-96 pr-1">
              <table class="w-full text-left text-xs">
                <thead class="text-gray-400 border-b border-gray-800">
                  <tr>
                    <th class="pb-2">Anchor Text</th>
                    <th class="pb-2">Type</th>
                    <th class="pb-2">Destination</th>
                  </tr>
                </thead>
                <tbody id="linksTableBody" class="divide-y divide-gray-800/50"></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 5: Technical & Schema -->
      <div id="technicalTab" class="tab-pane hidden space-y-6">
        <div class="glass-card rounded-2xl p-6 border border-gray-800 space-y-4">
          <h3 class="text-base font-bold text-white flex items-center gap-2">
            <i data-lucide="binary" class="w-5 h-5 text-cyan-400"></i> Canonical & Indexation Verification
          </h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div class="p-4 rounded-xl bg-gray-900 border border-gray-800 space-y-1">
              <span class="text-gray-400 block font-semibold">Declared Canonical URL</span>
              <span id="techCanonical" class="font-mono text-emerald-400 break-all">None</span>
            </div>
            <div class="p-4 rounded-xl bg-gray-900 border border-gray-800 space-y-1">
              <span class="text-gray-400 block font-semibold">Robots Directives</span>
              <span id="techRobots" class="font-mono text-cyan-400">index, follow</span>
            </div>
          </div>

          <h3 class="text-base font-bold text-white pt-4 flex items-center gap-2">
            <i data-lucide="boxes" class="w-5 h-5 text-purple-400"></i> Schema.org Structured Data (JSON-LD)
          </h3>
          <div id="schemaList" class="space-y-2"></div>
        </div>
      </div>

    </div>
  </main>

  <!-- Footer -->
  <footer class="mt-auto border-t border-gray-800/80 py-6 text-center text-xs text-gray-500">
    <p>© 2026 CrawlPilot — Engineered for Vercel Cloud Serverless Execution. 100% Free & Open Source.</p>
  </footer>

  <script>
    lucide.createIcons();
    let currentAuditData = null;

    function runPreset(url) {
      document.getElementById('urlInput').value = url;
      document.getElementById('auditForm').dispatchEvent(new Event('submit'));
    }

    document.getElementById('auditForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const rawUrl = document.getElementById('urlInput').value.trim();
      if (!rawUrl) return;

      // UI Loading State
      document.getElementById('btnText').textContent = 'Auditing...';
      document.getElementById('btnIcon').classList.add('hidden');
      document.getElementById('btnSpinner').classList.remove('hidden');
      document.getElementById('submitBtn').disabled = true;

      document.getElementById('loadingBox').classList.remove('hidden');
      document.getElementById('errorBox').classList.add('hidden');
      document.getElementById('resultsContainer').classList.add('hidden');

      try {
        const res = await fetch(`/api/audit?url=${encodeURIComponent(rawUrl)}`);
        const data = await res.json();

        if (data.error) {
          throw new Error(data.message || 'Failed to crawl website.');
        }

        currentAuditData = data;
        renderResults(data);
      } catch (err) {
        document.getElementById('errorMsg').textContent = err.message;
        document.getElementById('errorBox').classList.remove('hidden');
      } finally {
        document.getElementById('btnText').textContent = 'Audit Now';
        document.getElementById('btnIcon').classList.remove('hidden');
        document.getElementById('btnSpinner').classList.add('hidden');
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('loadingBox').classList.add('hidden');
      }
    });

    function renderResults(data) {
      document.getElementById('resultsContainer').classList.remove('hidden');
      document.getElementById('auditedUrl').textContent = data.url;

      // Health Score & Gauge
      const score = data.health_score;
      document.getElementById('scoreText').textContent = score;
      
      const scorePath = document.getElementById('scorePath');
      scorePath.setAttribute('stroke-dasharray', `${score}, 100`);
      
      const grade = document.getElementById('healthGrade');
      if (score >= 80) {
        grade.textContent = 'Excellent (A)';
        grade.className = 'text-lg font-bold text-emerald-400';
        scorePath.classList.remove('text-amber-500', 'text-rose-500');
        scorePath.classList.add('text-emerald-500');
      } else if (score >= 60) {
        grade.textContent = 'Average (B)';
        grade.className = 'text-lg font-bold text-amber-400';
        scorePath.classList.remove('text-emerald-500', 'text-rose-500');
        scorePath.classList.add('text-amber-500');
      } else {
        grade.textContent = 'Needs Work (F)';
        grade.className = 'text-lg font-bold text-rose-400';
        scorePath.classList.remove('text-emerald-500', 'text-amber-500');
        scorePath.classList.add('text-rose-500');
      }

      // Passed & Issues Count
      document.getElementById('passedCount').textContent = data.good_checks.length;
      document.getElementById('issuesCount').textContent = data.issues.length;
      const criticalCount = data.issues.filter(i => i.type === 'critical').length;
      const warnCount = data.issues.length - criticalCount;
      document.getElementById('issuesSubtitle').textContent = `${criticalCount} critical, ${warnCount} warnings`;

      // Speed & Size
      document.getElementById('speedText').textContent = `${data.response_time_ms}ms`;
      document.getElementById('pageSizeText').textContent = `Page Size: ${data.page_size_kb} KB`;

      // Specs
      document.getElementById('specStatus').textContent = `${data.status_code} OK`;
      document.getElementById('specRobots').textContent = data.meta_robots;
      document.getElementById('specWordCount').textContent = `${data.word_count} words`;
      document.getElementById('specInLinks').textContent = `${data.links.internal} internal`;
      document.getElementById('specAltMissing').textContent = `${data.images.missing_alt} missing`;

      // Issues List
      const issuesList = document.getElementById('issuesList');
      issuesList.innerHTML = '';
      
      data.issues.forEach(issue => {
        const isCrit = issue.type === 'critical';
        const card = document.createElement('div');
        card.className = `p-3.5 rounded-xl border flex items-start gap-3 ${
          isCrit ? 'bg-rose-500/10 border-rose-500/20 text-rose-300' : 'bg-amber-500/10 border-amber-500/20 text-amber-300'
        }`;
        card.innerHTML = `
          <div class="mt-0.5"><i data-lucide="${isCrit ? 'alert-octagon' : 'alert-triangle'}" class="w-4 h-4"></i></div>
          <div class="flex-1">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-white">${issue.title}</span>
              <span class="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded ${
                isCrit ? 'bg-rose-500/20 text-rose-300' : 'bg-amber-500/20 text-amber-300'
              }">${issue.type}</span>
            </div>
            <p class="text-xs text-gray-300 mt-0.5">${issue.desc}</p>
          </div>
        `;
        issuesList.appendChild(card);
      });

      data.good_checks.forEach(check => {
        const card = document.createElement('div');
        card.className = 'p-3 rounded-xl border bg-emerald-500/5 border-emerald-500/20 text-emerald-300 flex items-center gap-3 text-xs';
        card.innerHTML = `
          <i data-lucide="check-circle" class="w-4 h-4 text-emerald-400 flex-shrink-0"></i>
          <span>${check}</span>
        `;
        issuesList.appendChild(card);
      });

      // SERP Simulator
      document.getElementById('serpDomain').textContent = data.domain;
      document.getElementById('serpTitle').textContent = data.title || '(No Title Tag Found)';
      document.getElementById('serpDesc').textContent = data.meta_description || '(No Meta Description Provided)';
      document.getElementById('serpTitleLen').textContent = `${data.title_length} chars`;
      document.getElementById('serpDescLen').textContent = `${data.meta_desc_length} chars`;

      // Open Graph
      document.getElementById('ogDomain').textContent = data.domain.toUpperCase();
      document.getElementById('ogTitle').textContent = data.open_graph.title || data.title;
      document.getElementById('ogDesc').textContent = data.open_graph.description || data.meta_description;
      if (data.open_graph.image) {
        const img = document.getElementById('ogImage');
        img.src = data.open_graph.image;
        img.classList.remove('hidden');
        document.getElementById('noOgImgMsg').classList.add('hidden');
      } else {
        document.getElementById('ogImage').classList.add('hidden');
        document.getElementById('noOgImgMsg').classList.remove('hidden');
      }

      // Headings
      document.getElementById('h1Count').textContent = data.headings.h1.length;
      document.getElementById('h2Count').textContent = data.headings.h2.length;
      
      const h1List = document.getElementById('h1List');
      h1List.innerHTML = '';
      if (data.headings.h1.length === 0) {
        h1List.innerHTML = '<p class="text-xs text-rose-400">⚠️ No <h1> tag found on page!</p>';
      } else {
        data.headings.h1.forEach(h1 => {
          h1List.innerHTML += `<div class="p-2.5 rounded-lg bg-gray-900 border border-gray-800 text-xs font-semibold text-white"><h1>${h1}</h1></div>`;
        });
      }

      const h2List = document.getElementById('h2List');
      h2List.innerHTML = '';
      data.headings.h2.forEach(h2 => {
        h2List.innerHTML += `<div class="p-2 rounded-lg bg-gray-900/60 border border-gray-800/80 text-xs text-gray-300"><h2>${h2}</h2></div>`;
      });

      // Images
      document.getElementById('totalImgCount').textContent = data.images.total;
      document.getElementById('imgAltBadge').textContent = `${data.images.missing_alt} Missing Alt`;
      const imgTable = document.getElementById('imagesTableBody');
      imgTable.innerHTML = '';
      data.images.sample.forEach(img => {
        imgTable.innerHTML += `
          <tr class="hover:bg-gray-800/30">
            <td class="py-2.5 max-w-[200px] truncate font-mono text-gray-400">${img.src}</td>
            <td class="py-2.5 font-medium ${img.has_alt ? 'text-emerald-400' : 'text-amber-400 font-semibold'}">${img.alt}</td>
          </tr>
        `;
      });

      // Links
      document.getElementById('totalLinkCount').textContent = data.links.total;
      document.getElementById('linkRatioBadge').textContent = `${data.links.internal} Internal / ${data.links.external} External`;
      const linkTable = document.getElementById('linksTableBody');
      linkTable.innerHTML = '';
      data.links.sample.forEach(l => {
        linkTable.innerHTML += `
          <tr class="hover:bg-gray-800/30">
            <td class="py-2 font-medium text-white max-w-[140px] truncate">${l.text}</td>
            <td class="py-2"><span class="px-2 py-0.5 rounded text-[10px] ${l.type === 'Internal' ? 'bg-cyan-500/10 text-cyan-400' : 'bg-purple-500/10 text-purple-400'}">${l.type}</span></td>
            <td class="py-2 font-mono text-gray-400 max-w-[180px] truncate">${l.href}</td>
          </tr>
        `;
      });

      // Technical & Schema
      document.getElementById('techCanonical').textContent = data.canonical_url || '(None specified)';
      document.getElementById('techRobots').textContent = data.meta_robots;
      
      const schemaList = document.getElementById('schemaList');
      schemaList.innerHTML = '';
      if (data.schema.length === 0) {
        schemaList.innerHTML = '<p class="text-xs text-gray-500">No JSON-LD structured data detected.</p>';
      } else {
        data.schema.forEach(s => {
          schemaList.innerHTML += `
            <div class="p-3 rounded-xl bg-gray-900 border border-gray-800">
              <span class="text-xs font-bold text-purple-400">@type: ${s.type}</span>
              <pre class="mt-2 text-[10px] font-mono text-gray-400 max-h-32 overflow-y-auto">${JSON.stringify(s.raw, null, 2)}</pre>
            </div>
          `;
        });
      }

      lucide.createIcons();
      document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth' });
    }

    function switchTab(tabId, el) {
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
      document.getElementById(tabId).classList.remove('hidden');

      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.className = 'tab-btn px-4 py-2.5 rounded-xl font-medium text-xs sm:text-sm text-gray-400 hover:text-white hover:bg-gray-800/50 flex items-center gap-2 whitespace-nowrap';
      });
      el.className = 'tab-btn px-4 py-2.5 rounded-xl font-semibold text-xs sm:text-sm bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-2 whitespace-nowrap';
      lucide.createIcons();
    }

    function downloadJsonReport() {
      if (!currentAuditData) return;
      const blob = new Blob([JSON.stringify(currentAuditData, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `crawlpilot-audit-${currentAuditData.domain}.json`;
      a.click();
    }

    function downloadCsvReport() {
      if (!currentAuditData) return;
      let csv = 'Factor,Status,Detail\\n';
      csv += `URL,Audited,"${currentAuditData.url}"\\n`;
      csv += `Health Score,${currentAuditData.health_score}/100,"Calculated SEO health"\\n`;
      csv += `Status Code,${currentAuditData.status_code},"HTTP status"\\n`;
      csv += `Title,${currentAuditData.title_length} chars,"${(currentAuditData.title || '').replace(/"/g, '""')}"\\n`;
      csv += `Meta Description,${currentAuditData.meta_desc_length} chars,"${(currentAuditData.meta_description || '').replace(/"/g, '""')}"\\n`;
      csv += `H1 Count,${currentAuditData.headings.h1.length},"Heading 1 tags count"\\n`;
      csv += `Internal Links,${currentAuditData.links.internal},"Internal link count"\\n`;
      csv += `Missing Image Alt,${currentAuditData.images.missing_alt},"Images without alt attribute"\\n`;
      
      const blob = new Blob([csv], { type: 'text/csv' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `crawlpilot-audit-${currentAuditData.domain}.csv`;
      a.click();
    }
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
@app.get("/index.py", response_class=HTMLResponse)
def index():
    return HTMLResponse(content=HTML_CONTENT)

@app.get("/audit")
@app.get("/api/index.py/api/audit")
@app.get("/api/index.py/audit")
def api_audit_alt(url: str = Query(..., description="Target website URL to audit")):
    return JSONResponse(content=audit_single_url(url))

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    path = request.url.path
    if "audit" in path:
        url = request.query_params.get("url")
        if url:
            return JSONResponse(content=audit_single_url(url))
        return JSONResponse(content={"error": True, "message": "Missing url parameter"}, status_code=400)
    return HTMLResponse(content=HTML_CONTENT)
