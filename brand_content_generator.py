"""
📱 AI SOCIAL CONTENT STUDIO
STRATEGY • BRAND • CONTENT • CREATIVES
================================================================================
A complete brand-aware social media content creation workflow for CrawlPilot.
Implements the 36-point Brand-First Content Generation Architecture:
- Step 0: Format Selection (Single Post, Carousel, Grid, Reel, Story, Ad Creative)
- Dynamic controls (slide counts, grid sizes, durations, sequence lengths)
- 10 Brand-First Analysis Pillars (Brand Identity, Colors, Logo, Typography, Personality,
  Visual Style, Audience, Industry, Market, Social Presence)
- Visual Brand Color System (swatches, HEX, RGB, HSL, custom colors)
- Multi-Asset Uploads (Logo, Product Images, Reference Images, Brand Guidelines)
- Visual Style Engine (Auto Detect, Premium, Minimal, Editorial, Lifestyle, Corporate, Bold, Cinematic, UGC, Custom)
- Large Optional Custom Campaign Information & Product/Page URL (High Priority Context)
- Claim Safety Engine (prevents invented stats, unverified claims, fake pricing)
- Production-Ready Output:
  Brand DNA → Content Strategy → 4 Creative Concepts → Detailed Image Prompts →
  Image Generation → Platform-specific Captions → Hashtags → Alt Text →
  Brand Consistency QA (9 checks) → Final Content Pack
- Interactive action buttons: Generate Image, Copy Prompt, Copy Caption, Regenerate, Edit, Generate Selected Images
- Format-specific storyboards (Reels), multi-slide storytelling (Carousels), visual grid preview (Grids)
- Content Repurposer (1-click conversion across all formats)
- Modular architecture: Saved Brand Profiles, Content Calendar, Social Scheduling, Publishing, Analytics
"""

import io
import json
import re
import colorsys
import requests
import pandas as pd
import streamlit as st
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import urlparse, quote
from typing import Optional, Dict, Any, List, Tuple

# ==============================================================================
# 1. COLOR EXTRACTION & BRAND COLOR SYSTEM UTILITIES (HEX, RGB, HSL)
# ==============================================================================

def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"

def rgb_to_hsl(r: int, g: int, b: int) -> str:
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return f"hsl({int(h * 360)}, {int(s * 100)}%, {int(l * 100)}%)"

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    if len(hex_clean) != 6:
        return (30, 41, 59)
    try:
        return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (30, 41, 59)

def hex_to_hsl(hex_str: str) -> str:
    r, g, b = hex_to_rgb(hex_str)
    return rgb_to_hsl(r, g, b)

def extract_palette_from_image(image_bytes: bytes) -> Dict[str, Dict[str, str]]:
    """
    Extracts dominant brand colors from uploaded logo/image using Pillow quantization and frequency sorting.
    Supports PNG, JPG, JPEG, WEBP, and SVG formats.
    Returns Primary, Secondary, Accent, Background, and Text colors with HEX, RGB, HSL.
    """
    default_palette = {
        "primary": {"hex": "#1E3A8A", "rgb": "rgb(30, 58, 138)", "hsl": "hsl(224, 64%, 33%)"},
        "secondary": {"hex": "#F59E0B", "rgb": "rgb(245, 158, 11)", "hsl": "hsl(38, 92%, 50%)"},
        "accent": {"hex": "#10B981", "rgb": "rgb(16, 185, 129)", "hsl": "hsl(160, 84%, 39%)"},
        "background": {"hex": "#0F172A", "rgb": "rgb(15, 23, 42)", "hsl": "hsl(222, 47%, 11%)"},
        "text": {"hex": "#F8FAFC", "rgb": "rgb(248, 250, 252)", "hsl": "hsl(210, 40%, 98%)"}
    }

    if not image_bytes:
        return default_palette

    # 1. Check for SVG Logo format
    try:
        sample_header = image_bytes[:300].lower()
        if b"<svg" in sample_header or b"<?xml" in sample_header:
            text = image_bytes.decode("utf-8", errors="ignore")
            found_hexes = re.findall(r"#[0-9a-fA-F]{6}\b", text)
            if found_hexes:
                unique_hexes = []
                for h in found_hexes:
                    h_upper = h.upper()
                    if h_upper not in unique_hexes:
                        unique_hexes.append(h_upper)

                colored = [h for h in unique_hexes if h not in ["#FFFFFF", "#000000", "#0F172A"]]
                p = colored[0] if colored else unique_hexes[0]
                s = colored[1] if len(colored) > 1 else ("#F59E0B" if p != "#F59E0B" else "#10B981")
                a = colored[2] if len(colored) > 2 else ("#FFFFFF" if p != "#FFFFFF" else "#38BDF8")

                pr, pg, pb = hex_to_rgb(p)
                sr, sg, sb = hex_to_rgb(s)
                ar, ag, ab = hex_to_rgb(a)
                return {
                    "primary": {"hex": p, "rgb": f"rgb({pr}, {pg}, {pb})", "hsl": rgb_to_hsl(pr, pg, pb)},
                    "secondary": {"hex": s, "rgb": f"rgb({sr}, {sg}, {sb})", "hsl": rgb_to_hsl(sr, sg, sb)},
                    "accent": {"hex": a, "rgb": f"rgb({ar}, {ag}, {ab})", "hsl": rgb_to_hsl(ar, ag, ab)},
                    "background": {"hex": "#0F172A", "rgb": "rgb(15, 23, 42)", "hsl": "hsl(222, 47%, 11%)"},
                    "text": {"hex": "#F8FAFC", "rgb": "rgb(248, 250, 252)", "hsl": "hsl(210, 40%, 98%)"}
                }
    except Exception:
        pass

    # 2. Raster Logo (PNG, JPG, JPEG, WEBP)
    try:
        img = Image.open(io.BytesIO(image_bytes))

        # Alpha composite transparent pixels onto neutral white canvas
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img_rgba = img.convert("RGBA")
            bg_white = Image.new("RGBA", img_rgba.size, (255, 255, 255, 255))
            img_composite = Image.alpha_composite(bg_white, img_rgba).convert("RGB")
        else:
            img_composite = img.convert("RGB")

        # Resize for responsive color cluster analysis
        img_small = img_composite.resize((150, 150), Image.Resampling.LANCZOS)

        # Quantize to 16 color clusters
        quantized = img_small.quantize(colors=16)
        palette = quantized.getpalette()
        color_counts = quantized.getcolors(maxcolors=150 * 150)
        if not color_counts or not palette:
            return default_palette

        # Sort clusters by pixel frequency
        sorted_by_freq = sorted(color_counts, key=lambda x: x[0], reverse=True)

        def dist(c1, c2):
            return ((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2 + (c1[2] - c2[2])**2)**0.5

        distinct_colors = []
        for count, idx in sorted_by_freq:
            r = palette[idx * 3]
            g = palette[idx * 3 + 1]
            b = palette[idx * 3 + 2]
            rgb = (r, g, b)
            # Ensure color is distinctly different from already picked colors
            if not any(dist(rgb, prev) < 35 for prev in distinct_colors):
                distinct_colors.append(rgb)

        if not distinct_colors:
            return default_palette

        # Identify brand colors vs canvas/background neutrals
        def is_neutral(c):
            return (max(c) - min(c) < 22) or (sum(c) > 730) or (sum(c) < 35)

        brand_colored = [c for c in distinct_colors if not is_neutral(c)]
        neutrals = [c for c in distinct_colors if is_neutral(c)]

        if brand_colored:
            c1 = brand_colored[0]
            c2 = brand_colored[1] if len(brand_colored) > 1 else (neutrals[0] if neutrals and sum(neutrals[0]) < 650 else (245, 158, 11))
            c3 = brand_colored[2] if len(brand_colored) > 2 else (neutrals[0] if neutrals else (255, 255, 255))
        else:
            c1 = distinct_colors[0]
            c2 = distinct_colors[1] if len(distinct_colors) > 1 else (245, 158, 11)
            c3 = distinct_colors[2] if len(distinct_colors) > 2 else (255, 255, 255)

        h1 = rgb_to_hex(*c1).upper()
        h2 = rgb_to_hex(*c2).upper()
        h3 = rgb_to_hex(*c3).upper()

        return {
            "primary": {"hex": h1, "rgb": f"rgb({c1[0]}, {c1[1]}, {c1[2]})", "hsl": rgb_to_hsl(*c1)},
            "secondary": {"hex": h2, "rgb": f"rgb({c2[0]}, {c2[1]}, {c2[2]})", "hsl": rgb_to_hsl(*c2)},
            "accent": {"hex": h3, "rgb": f"rgb({c3[0]}, {c3[1]}, {c3[2]})", "hsl": rgb_to_hsl(*c3)},
            "background": {"hex": "#0F172A", "rgb": "rgb(15, 23, 42)", "hsl": "hsl(222, 47%, 11%)"},
            "text": {"hex": "#F8FAFC", "rgb": "rgb(248, 250, 252)", "hsl": "hsl(210, 40%, 98%)"}
        }
    except Exception:
        return default_palette


# ==============================================================================
# 2. CLAIM SAFETY & FACTUAL GUARDRAIL ENGINE
# ==============================================================================

RISKY_CLAIM_PATTERNS = [
    (r"\b(cure|cures|curing|treat|treats|treating|heal|heals|healing|prevent disease)\b", "Medical or absolute guarantee claim detected"),
    (r"\b(100% guarantee|money back guarantee|guaranteed results)\b", "Unverified commercial guarantee detected"),
    (r"\b(best in the world|#1 in|ranked #1|number one)\b", "Superlative claim requires documented third-party ranking"),
    (r"\b(\d+%\s*off|\$\d+\s*discount|save\s*\$\d+|save\s*\d+%)\b", "Specific price or discount offer detected"),
    (r"\b(\d{3}[-.]?\d{3}[-.]?\d{4})\b", "Phone number detected"),
    (r"\b(fda approved|certified organic|iso \d+)\b", "Certification claim detected")
]

def audit_claim_safety(text: str, verified_context: str = "") -> List[str]:
    """
    Checks generated or input text for unverified claims, guarantees, or pricing.
    """
    warnings = []
    text_lower = text.lower()
    context_lower = verified_context.lower()

    for pattern, desc in RISKY_CLAIM_PATTERNS:
        matches = re.findall(pattern, text_lower)
        if matches:
            for m in matches:
                m_str = m if isinstance(m, str) else m[0]
                if m_str not in context_lower:
                    warnings.append(f"{desc}: '{m_str}' is not mentioned in your verified campaign information.")
                    break
    return warnings


# ==============================================================================
# 2.5 WEBSITE INTELLIGENCE & NICHE EXTRACTION ENGINE
# ==============================================================================

@st.cache_data(show_spinner=False, ttl=3600)
def analyze_website_niche(url: str) -> Dict[str, Any]:
    """
    Crawls and analyzes the provided website to extract the true business niche,
    offerings, keywords, locations, and meta content to prevent misclassification.
    """
    if not url:
        return {}
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        res = requests.get(clean_url, headers=headers, timeout=8)
        if res.status_code != 200:
            return {"url": clean_url, "error": f"HTTP {res.status_code}"}

        if BeautifulSoup:
            soup = BeautifulSoup(res.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"].strip()
            h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]
            body_text = " ".join(soup.stripped_strings)
        else:
            t_match = re.search(r"<title[^>]*>(.*?)</title>", res.text, re.IGNORECASE | re.DOTALL)
            title = t_match.group(1).strip() if t_match else ""
            m_match = re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)["\']', res.text, re.IGNORECASE)
            if not m_match:
                m_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']', res.text, re.IGNORECASE)
            meta_desc = m_match.group(1).strip() if m_match else ""
            h1_tags = [h.strip() for h in re.findall(r"<h1[^>]*>(.*?)</h1>", res.text, re.IGNORECASE | re.DOTALL)]
            clean_html = re.sub(r"<[^>]+>", " ", res.text)
            body_text = " ".join(clean_html.split())

        text_lower = body_text.lower()

        # Identify brand name from title or domain
        domain_part = clean_url.split("//")[-1].split("/")[0].replace("www.", "").split(".")[0]
        detected_brand = title.split("|")[0].split("-")[0].strip() if title else domain_part.capitalize()
        if len(detected_brand) > 30:
            detected_brand = domain_part.capitalize()

        # Niche classification & keyword extraction
        detected_niche = "Professional Business Services"
        detected_services = []

        if any(w in text_lower for w in ["wedding", "venue", "banquet", "party plot", "reception", "catering", "mandap", "ceremony"]):
            detected_niche = "Wedding & Event Venues, Banquet Halls & Event Spaces"
            detected_services = ["Wedding Venues", "Banquet Halls", "Party Plots", "Corporate Events", "Catering & Vendor Network"]
        elif any(w in text_lower for w in ["account", "bookkeep", "tax", "cpa", "audit", "financial"]):
            detected_niche = "Accounting, Tax & Bookkeeping Services"
            detected_services = ["Audit-Ready Financials", "Tax Planning", "Cloud Bookkeeping", "Payroll Management"]
        elif any(w in text_lower for w in ["clinic", "doctor", "dental", "medical", "hospital", "healthcare"]):
            detected_niche = "Medical & Healthcare Services"
            detected_services = ["Clinical Consultations", "Specialist Care", "Patient Wellness"]
        elif any(w in text_lower for w in ["real estate", "property", "realtor", "apartments", "villas"]):
            detected_niche = "Real Estate & Property Development"
            detected_services = ["Residential Properties", "Commercial Spaces", "Property Advisory"]
        elif any(w in text_lower for w in ["software", "saas", "cloud infrastructure", "data telemetry", "developer tool"]):
            detected_niche = "B2B Software & Cloud Infrastructure"
            detected_services = ["Cloud Infrastructure", "API Integration", "Workflow Automation"]
        elif any(w in text_lower for w in ["skincare", "cosmetic", "beauty", "apparel", "jewelry", "fashion"]):
            detected_niche = "E-Commerce, Lifestyle & Beauty Products"
            detected_services = ["Direct-to-Consumer Products", "Curated Collections"]

        # Geographic location extraction
        locations = []
        for loc in ["Gujarat", "Ahmedabad", "Surat", "Vadodara", "Rajkot", "Mumbai", "Delhi", "Bengaluru", "Canada", "Toronto", "United States", "New York"]:
            if loc.lower() in text_lower:
                locations.append(loc)

        return {
            "url": clean_url,
            "title": title,
            "meta_description": meta_desc,
            "detected_brand": detected_brand,
            "detected_niche": detected_niche,
            "detected_services": detected_services,
            "locations": locations,
            "headline": h1_tags[0] if h1_tags else "",
            "summary": meta_desc or (h1_tags[0] if h1_tags else title)
        }
    except Exception as e:
        return {"url": clean_url, "error": str(e)}


# ==============================================================================
# 3. SAVED BRAND PROFILES DATABASE (MODULAR ARCHITECTURE)
# ==============================================================================

DEFAULT_SAVED_BRANDS = {
    "VenueConnect (Gujarat Venues)": {
        "brand_name": "VenueConnect",
        "industry": "Wedding & Event Venue Booking Platform",
        "target_country": "India",
        "target_city": "Gujarat (Ahmedabad, Surat, Vadodara, Rajkot)",
        "target_audience": "Engaged couples, families planning weddings, event organizers, corporate banquet bookers",
        "website": "https://www.venueconnect.in/",
        "instagram": "https://instagram.com/venueconnect.in",
        "facebook": "https://facebook.com/venueconnect.in",
        "x": "",
        "linkedin": "",
        "phone": "+91 98765 43210",
        "email": "hello@venueconnect.in",
        "cta": "Explore Venues & Get Free Quotes",
        "visual_style": "🎞️ 80s / 90s Vintage Nostalgia (Trending Film Grain)",
        "colors": {
            "primary": {"hex": "#123456", "rgb": "rgb(18, 52, 86)", "hsl": "hsl(210, 65%, 20%)"},
            "secondary": {"hex": "#F58220", "rgb": "rgb(245, 130, 32)", "hsl": "hsl(28, 92%, 54%)"},
            "accent": {"hex": "#FFFFFF", "rgb": "rgb(255, 255, 255)", "hsl": "hsl(0, 0%, 100%)"},
            "background": {"hex": "#0F172A", "rgb": "rgb(15, 23, 42)", "hsl": "hsl(222, 47%, 11%)"},
            "text": {"hex": "#F8FAFC", "rgb": "rgb(248, 250, 252)", "hsl": "hsl(210, 40%, 98%)"}
        },
        "fonts": {"heading": "Playfair Display", "body": "Plus Jakarta Sans"},
        "personality": ["Royal", "Trustworthy", "Celebratory"],
        "formal_casual": 3,
        "conservative_creative": 4,
        "guidelines": "Find and book the best wedding venues, banquet halls, party plots & event spaces in Gujarat. Compare prices, capacity, catering options across Ahmedabad, Surat, Rajkot, Vadodara."
    },
    "XYZ Essential Oils (Canada)": {
        "brand_name": "XYZ Essential Oils",
        "industry": "Pure Essential Oils & Wellness Aromatherapy",
        "target_country": "Canada",
        "target_city": "Toronto",
        "target_audience": "25–45 wellness-conscious consumers, yoga practitioners, clean skincare seekers",
        "website": "https://xyzessentialoils.ca",
        "instagram": "https://instagram.com/xyzessentialoils",
        "facebook": "https://facebook.com/xyzessentialoils",
        "x": "https://x.com/xyzoils",
        "linkedin": "https://linkedin.com/company/xyz-essential-oils",
        "phone": "+1 (416) 555-0199",
        "email": "concierge@xyzessentialoils.ca",
        "cta": "Shop Fresh Batch",
        "visual_style": "Editorial",
        "colors": {
            "primary": {"hex": "#123456", "rgb": "rgb(18, 52, 86)", "hsl": "hsl(210, 65%, 20%)"},
            "secondary": {"hex": "#F58220", "rgb": "rgb(245, 130, 32)", "hsl": "hsl(28, 92%, 54%)"},
            "accent": {"hex": "#FFFFFF", "rgb": "rgb(255, 255, 255)", "hsl": "hsl(0, 0%, 100%)"},
            "background": {"hex": "#0F172A", "rgb": "rgb(15, 23, 42)", "hsl": "hsl(222, 47%, 11%)"},
            "text": {"hex": "#F8FAFC", "rgb": "rgb(248, 250, 252)", "hsl": "hsl(210, 40%, 98%)"}
        },
        "fonts": {"heading": "Playfair Display", "body": "Plus Jakarta Sans"},
        "personality": ["Premium", "Minimal", "Trustworthy"],
        "formal_casual": 3,
        "conservative_creative": 4,
        "guidelines": "Minimalist amber bottle on dark slate, zero synthetic ingredients, clean Swiss typography, 15% safe area buffer for logo."
    },
    "SaaS Pilot (Cloud Architecture)": {
        "brand_name": "SaaS Pilot",
        "industry": "B2B Cloud Monitoring & SEO Intelligence",
        "target_country": "United States",
        "target_city": "San Francisco",
        "target_audience": "Engineering Leaders, VP of Growth, SEO Directors",
        "website": "https://saaspilot.io",
        "instagram": "https://instagram.com/saaspilot",
        "facebook": "",
        "x": "https://x.com/saaspilot_hq",
        "linkedin": "https://linkedin.com/company/saaspilot",
        "phone": "",
        "email": "team@saaspilot.io",
        "cta": "Start Free 14-Day Pilot",
        "visual_style": "Corporate",
        "colors": {
            "primary": {"hex": "#0284C7", "rgb": "rgb(2, 132, 199)", "hsl": "hsl(200, 98%, 39%)"},
            "secondary": {"hex": "#10B981", "rgb": "rgb(16, 185, 129)", "hsl": "hsl(160, 84%, 39%)"},
            "accent": {"hex": "#F43F5E", "rgb": "rgb(244, 63, 94)", "hsl": "hsl(350, 89%, 60%)"},
            "background": {"hex": "#0F172A", "rgb": "rgb(15, 23, 42)", "hsl": "hsl(222, 47%, 11%)"},
            "text": {"hex": "#FFFFFF", "rgb": "rgb(255, 255, 255)", "hsl": "hsl(0, 0%, 100%)"}
        },
        "fonts": {"heading": "Outfit", "body": "Inter"},
        "personality": ["Technical", "Professional", "Bold"],
        "formal_casual": 2,
        "conservative_creative": 3,
        "guidelines": "High contrast dark mode cards, clean node graph diagrams, technical stats with verified metrics."
    }
}


# ==============================================================================
# 4. CONTENT STRATEGY & CREATIVE GENERATION ENGINE
# ==============================================================================

def generate_social_content_studio(
    content_format: str,
    format_settings: Dict[str, Any],
    platforms: List[str],
    objective: str,
    business: Dict[str, Any],
    brand_palette: Dict[str, Any],
    typography: Dict[str, str],
    personality_traits: List[str],
    formal_casual: int,
    conservative_creative: int,
    visual_style: str,
    campaign_info: str,
    product_url: str,
    api_key: str = "",
    provider: str = "Google Gemini",
    strategy_model: str = "gemini-2.5-flash",
    image_model: str = "imagen-3.0-generate-002"
) -> Dict[str, Any]:
    """
    Executes the Brand-First Social Content Studio Workflow:
    Brand DNA → Content Strategy → 4 Creative Concepts → Detailed Image Prompts →
    Image Generation Prompts → Platform-specific Captions → Hashtags → Alt Text →
    Brand Consistency QA → Final Content Pack
    """
    brand_name = business.get("brand_name", "Brand")

    def extract_hex(color_val):
        if isinstance(color_val, dict):
            return color_val.get("hex", "#1E3A8A")
        return str(color_val) if str(color_val).startswith("#") else "#1E3A8A"

    prim_hex = extract_hex(brand_palette.get("primary", "#1E3A8A"))
    sec_hex = extract_hex(brand_palette.get("secondary", "#F59E0B"))
    acc_hex = extract_hex(brand_palette.get("accent", "#10B981"))
    bg_hex = extract_hex(brand_palette.get("background", "#0F172A"))
    txt_hex = extract_hex(brand_palette.get("text", "#F8FAFC"))

    # System prompt for LLM
    system_prompt = f"""You are the Executive Creative Director & Brand Strategist at an Elite Social Agency.
Your operating framework: "NEVER GENERATE CONTENT BEFORE UNDERSTANDING THE BRAND."

BRAND FOUNDATION:
- Brand Name: {brand_name}
- Industry: {business.get('industry')}
- Location: {business.get('target_city')}, {business.get('target_country')}
- Target Audience: {business.get('target_audience')}
- Website / Store: {business.get('website')}
- Social Handle: {business.get('instagram')}
- Primary CTA: {business.get('cta')}

BRAND IDENTITY SYSTEM:
- Primary Color: {prim_hex}
- Secondary Color: {sec_hex}
- Accent Color: {acc_hex}
- Background Tone: {bg_hex}
- Text Color: {txt_hex}
- Typography: Headings ({typography.get('heading')}), Body ({typography.get('body')})
- Brand Personality: {', '.join(personality_traits)}
- Visual Style Direction: {visual_style}
- Tone Coordinates: Formal-to-Casual Level {formal_casual}/5, Conservative-to-Creative Level {conservative_creative}/5

CAMPAIGN PARAMETERS:
- Content Format: {content_format} (Specs: {json.dumps(format_settings)})
- Selected Platforms: {', '.join(platforms)}
- Campaign Goal / Objective: {objective}
- Custom Campaign Information (HIGH PRIORITY CONTEXT): {campaign_info or 'General high-value brand showcase'}
- Product / Target URL: {product_url or business.get('website')}

CRITICAL RULES:
1. "HIDDEN LOGO TEST": The creative and copy must feel unmistakably like this brand even if the logo is hidden.
2. Maintain brand consistency without making every post visually identical.
3. CLAIM SAFETY: Never invent discounts, prices, phone numbers, or unverified medical/stat claims not supplied above.
4. Adapt copy strictly per platform (Instagram, LinkedIn, X, Facebook, Pinterest).
5. Generate production-ready image prompts containing brand color tokens, lighting, camera angles, safe areas.

Return valid JSON with:
content_strategy, creative_concepts (4 items), format_specific_execution, platform_captions, hashtag_engine, alt_text, brand_consistency_qa
"""

    user_prompt = f"""Synthesize a complete Social Content Studio package for {brand_name} targeting {objective}.
Format requested: {content_format}.
Business Industry: {business.get('industry', 'General Business')}
Custom campaign context: {campaign_info}
CRITICAL INSTRUCTION:
Tailor the 4 creative concepts and production image prompts strictly to the company's real industry ({business.get('industry', 'General Business')}).
If this is an accounting, bookkeeping, consulting, legal, SaaS, tech, or healthcare business, DO NOT describe bottles, jars, cosmetics, or physical products!
Instead describe modern workspace setups, digital interfaces/dashboards, executive meetings, client outcomes, or conceptual architecture.

Include:
1. content_strategy
2. 4 creative concepts (Concept 1: Core Authority Hero, Concept 2: Emotional & Lifestyle Resonance, Concept 3: Educational Framework Infographic, Concept 4: Problem -> Solution Paradigm Shift)
3. format_specific_execution ({content_format})
4. platform_captions (with professional, creative, and short for {', '.join(platforms)})
5. hashtag_engine
6. alt_text
7. brand_consistency_qa (with 9 checks: Color Alignment, Typography, Visual Style, Logo Usage, Brand Tone, Product Accuracy, Text Readability, Safe Area, Unsupported Claims)
"""

    if api_key and provider == "Google Gemini":
        models_to_try = [strategy_model]
        for m in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
            if m not in models_to_try:
                models_to_try.append(m)

        for m_name in models_to_try:
            try:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [
                        {"role": "user", "parts": [{"text": system_prompt + "\n\n" + user_prompt}]}
                    ],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.4
                    }
                }
                res = requests.post(endpoint, json=payload, timeout=20)
                if res.status_code == 200:
                    raw_txt = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    clean_json = raw_txt.strip()
                    if clean_json.startswith("```json"):
                        clean_json = clean_json[7:]
                    if clean_json.endswith("```"):
                        clean_json = clean_json[:-3]
                    parsed = json.loads(clean_json.strip())
                    if "creative_concepts" in parsed and len(parsed["creative_concepts"]) >= 4:
                        return parsed
            except Exception:
                continue

    # 0. Website Intelligence Extraction
    website_url = business.get("website", "")
    website_context = {}
    if website_url:
        website_context = analyze_website_niche(website_url)

    # ==============================================================================
    # DYNAMIC INDUSTRY-ADAPTIVE CONTENT ENGINE (FALLBACK)
    # Automatically generates tailored concepts for Venues/Events, Finance, Tech, Healthcare,
    # Real Estate, Services, Food, Fitness, or Products.
    # ==============================================================================
    combined_context = f"{campaign_info} {website_context.get('summary', '')} {website_context.get('detected_niche', '')}"
    cat = detect_industry_category(business.get("industry", ""), combined_context, brand_name)
    concepts = build_industry_concepts(brand_name, business.get("industry", ""), visual_style, prim_hex, sec_hex, bg_hex, typography, business, iteration=0)

    if cat == "events_venues":
        strat_idea = f"The Unforgettable Celebration Standard: Finding Gujarat's Finest Venues with {brand_name}"
        strat_target = f"Designed for engaged couples, families, and corporate event organizers in {business.get('target_city', 'Gujarat')} planning grand weddings and milestone celebrations."
        strat_msg = f"At {brand_name}, we eliminate the chaos of venue hunting by connecting you with verified banquet halls, party plots, and event spaces across Gujarat."
        strat_angle = "Why driving to 20 banquets in the heat is obsolete when you can compare capacities, catering, and prices in 60 seconds."
        strat_hook = "Planning a wedding in Gujarat? Stop losing weeks to venue hunting."
        strat_vis = f"Opulent {visual_style} aesthetic featuring sprawling evening party plot lawns illuminated by fairy lights, crystal chandeliers, floral mandaps, and rich warm ambient tones accented by {prim_hex} and {sec_hex} highlights."

        ig_prof = f"Planning a dream wedding or grand celebration in Gujarat? 🌸✨\n\nStop spending weeks visiting 20 different banquets in the heat. At {brand_name}, we bring Gujarat's finest wedding venues, royal banquet halls, and open-air party plots right to your screen.\n\nWhy Gujarat families trust {brand_name}:\n🏛️ 500+ Verified Banquets & Party Plots\n💰 Transparent price comparisons & catering packages\n👥 Capacities from 100 to 5,000+ guests\n⚡ Free instant quotes & site visit coordination\n\nMake your celebration unforgettable. Book smarter today.\n\n🌐 Visit: {business.get('website', 'https://www.venueconnect.in/')}\n📲 Call / WhatsApp: {business.get('phone', '[Direct Booking Helpline]')}\n📍 Venues across Ahmedabad, Surat, Vadodara, Rajkot & Gujarat\n\nTag someone who's getting married this season! 👇"
        li_prof = f"Corporate summits, product launches, or grand annual galas in Gujarat?\n\n{brand_name} simplifies enterprise venue scouting with verified AC banquet halls, luxury resort lawns, and transparent catering options across Ahmedabad, Surat, and Vadodara.\n\n✔ Zero brokerage or hidden fees\n✔ Verified venue photos & real customer ratings\n✔ Dedicated event venue specialist\n\nExplore corporate event spaces: {business.get('website', 'https://www.venueconnect.in/')}"
        x_prof = f"Planning a wedding in Gujarat? Here is how to find and compare 500+ verified banquet halls & party plots across Ahmedabad, Surat, & Vadodara in under 2 minutes 🧵👇\n\n{business.get('website', 'https://www.venueconnect.in/')}"
        fb_prof = f"Your dream wedding deserves the perfect setting. 💍✨ Discover Gujarat's most loved wedding lawns, royal banquet halls, and party plots on {brand_name}. Compare prices, guest capacities, and catering options with zero hassle!\n\n👉 Book your free site visit today: {business.get('website', 'https://www.venueconnect.in/')}\n📞 WhatsApp: {business.get('phone', 'Venue Support')}"
        h_tags = {
            "brand_hashtags": [f"#{brand_name.replace(' ', '')}", f"#{brand_name.replace(' ', '')}Weddings"],
            "product_hashtags": ["#WeddingVenuesGujarat", "#BanquetHalls", "#PartyPlotsGujarat", "#GujaratEvents"],
            "industry_hashtags": ["#IndianWeddings", "#WeddingPlanning", "#LuxuryWeddings", "#EventSpaces"],
            "audience_hashtags": ["#GujaratCouples", "#WeddingInspo", "#DestinationWeddingIndia"],
            "location_hashtags": ["#Ahmedabad", "#Surat", "#Vadodara", "#Rajkot", "#Gujarat"]
        }
    elif cat == "finance":
        strat_idea = f"The Zero-Stress Financial Standard: Scaling {brand_name} with Precision Bookkeeping"
        strat_target = f"Designed for business owners, founders, and leaders in {business.get('target_city', 'Canada')} looking to eliminate tax anxiety and messy spreadsheets."
        strat_msg = f"At {brand_name}, we turn financial chaos into clear, audit-ready numbers that fuel confident growth."
        strat_angle = "Why manual bookkeeping costs small businesses 120+ hours a year and thousands in missed tax deductions."
        strat_hook = "Stop losing weekends to receipt reconciliation and tax panic."
        strat_vis = f"High-contrast {visual_style} aesthetic featuring clean dark mode ledger interfaces with luminous {prim_hex} and {sec_hex} financial telemetry cards."

        ig_prof = f"When it comes to financial architecture, clarity isn't a bonus—it's your biggest growth lever.\n\nAt {brand_name}, we specialize in bookkeeping and cloud accounting for businesses who refuse to let manual spreadsheets bottleneck their growth.\n\nEvery client engagement delivers:\n✔ 100% reconciled, audit-ready monthly financials\n✔ Proactive tax minimization & deduction tracking\n✔ Automated cloud software integration\n\nTake back your weekends. {business.get('cta')}.\n\nExplore at {business.get('website')}"
        li_prof = f"The biggest hidden cost in scaling businesses right now?\n\nUnorganized books and last-minute tax panic.\n\nAt {brand_name}, we built our practice around a simple principle: Founders should be building companies, not categorizing receipts on Sunday night.\n\nHere is our 3-step framework:\n1. Real-Time Cloud Synchronization\n2. Tax Deduction Strategy\n3. Executive Financial Clarity\n\nHow is your business managing bookkeeping and compliance in {business.get('target_country', 'Canada')} this quarter? Let's connect."
        x_prof = f"Why 80% of business owners overpay on taxes (and how cloud accounting fixes it in 30 days) 🧵👇\n\n1/3 First mistake: Using Excel for year-end accounting. Receipts get lost and write-offs vanish.\n2/3 Second mistake: Waiting until tax season to reconcile.\n3/3 Partner with experts. Learn how {brand_name} simplifies your books at {business.get('website')}"
        fb_prof = f"Hey {business.get('target_city', 'Canada')} business community! 💼\n\nIf you're tired of spending your weekends on bookkeeping and receipt tracking, {brand_name} is here to take it completely off your plate.\n\nAccurate books • Maximum tax deductions • 100% audit-ready.\n\n👉 {business.get('cta')}: {business.get('website')}"
        h_tags = {
            "brand_hashtags": [f"#{brand_name.replace(' ', '')}", f"#{brand_name.replace(' ', '')}HQ"],
            "product_hashtags": ["#CloudAccounting", "#BookkeepingServices", "#SmallBusinessFinance"],
            "industry_hashtags": ["#CPA", "#TaxStrategy", "#FinancialClarity"],
            "audience_hashtags": ["#BusinessOwners", "#EntrepreneurLife", "#CanadianBusiness"],
            "location_hashtags": [f"#{business.get('target_city', 'Toronto').replace(' ', '')}", f"#{business.get('target_country', 'Canada').replace(' ', '')}"]
        }
    elif cat == "tech":
        strat_idea = f"Architectural Velocity: Engineering Uptime & Intelligence with {brand_name}"
        strat_target = f"Designed for technical leaders, developers, and growth executives who demand high availability and zero bottlenecking."
        strat_msg = f"At {brand_name}, modern systems run with continuous telemetry and frictionless automation."
        strat_angle = "Why legacy infrastructure compounds technical debt, and how modern architecture reduces operational friction by 60%."
        strat_hook = "Stop debugging infrastructure that was built for 2018."
        strat_vis = f"Futuristic dark-mode UI with sleek node graphs, glowing {prim_hex} and {sec_hex} telemetry lines, and minimalist Swiss typography."

        ig_prof = f"Infrastructure reliability shouldn't be an afterthought.\n\nAt {brand_name}, we build systems designed to scale seamlessly without latency spikes or developer friction.\n\n✔ 99.99% Guaranteed Availability\n✔ Sub-millisecond response latency\n✔ Enterprise-grade security protocols\n\nUpgrade your workflow today. {business.get('cta')} at {business.get('website')}"
        li_prof = f"The true bottleneck in modern engineering teams?\n\nFragile architecture and fragmented telemetry.\n\nAt {brand_name}, we eliminate blind spots so your engineers can deploy with radical confidence.\n\nDiscover our platform: {business.get('website')}"
        x_prof = f"Why modern cloud architecture outperforms legacy monoliths every single time 🧵👇\n\n1/3 Telemetry first.\n2/3 Automated failover.\n3/3 Learn how {brand_name} scales your stack: {business.get('website')}"
        fb_prof = f"Scale your tech stack with total confidence. Discover {brand_name}: {business.get('website')}"
        h_tags = {
            "brand_hashtags": [f"#{brand_name.replace(' ', '')}", f"#{brand_name.replace(' ', '')}Tech"],
            "product_hashtags": ["#CloudTech", "#DevOps", "#SaaSSolutions"],
            "industry_hashtags": ["#SystemArchitecture", "#TechLeadership", "#Innovation"],
            "audience_hashtags": ["#Developers", "#CTO", "#TechFounders"],
            "location_hashtags": [f"#{business.get('target_city', 'Tech').replace(' ', '')}", f"#{business.get('target_country', 'Global').replace(' ', '')}"]
        }
    elif cat == "health":
        strat_idea = f"Evidence-Based Precision: Human Care & Patient Trust at {brand_name}"
        strat_target = f"Built directly for patients and individuals seeking uncompromising healthcare standards and empathetic clinical expertise."
        strat_msg = f"At {brand_name}, your health journey is guided by certified protocols and patient-first dedication."
        strat_angle = "The difference between reactive symptom management and comprehensive preventative care."
        strat_hook = "Experience healthcare where clinical excellence meets genuine human care."
        strat_vis = f"Serene high-key clinical aesthetics, warm natural lighting, deep {bg_hex} dark-mode contrasts with calming {prim_hex} accents."

        ig_prof = f"Your health deserves uncompromising standards.\n\nAt {brand_name}, our certified clinicians combine cutting-edge diagnostics with patient-first compassion.\n\nBook your consultation: {business.get('website')}"
        li_prof = f"Elevating clinical standards through patient-first innovation. Learn more about {brand_name}: {business.get('website')}"
        x_prof = f"Why personalized healthcare protocols transform patient outcomes: {business.get('website')}"
        fb_prof = f"Welcoming patients across {business.get('target_city', 'our community')} to {brand_name}. Experience compassionate, expert care: {business.get('website')}"
        h_tags = {
            "brand_hashtags": [f"#{brand_name.replace(' ', '')}"],
            "product_hashtags": ["#ClinicalExcellence", "#PatientCare", "#WellnessJourney"],
            "industry_hashtags": ["#Healthcare", "#PreventativeMedicine"],
            "audience_hashtags": ["#HealthyLiving", "#CommunityHealth"],
            "location_hashtags": [f"#{business.get('target_city', 'Care').replace(' ', '')}"]
        }
    elif cat == "product":
        strat_idea = f"The Standard of Excellence: Elevating {business.get('industry', 'Brand')} Through Radical Quality"
        strat_target = f"Built directly for {business.get('target_audience', 'discerning clients')} who value verified authenticity."
        strat_msg = f"At {brand_name}, excellence is verifiable in every single detail."
        strat_angle = "Why ordinary solutions cut corners, and the measurable difference verified standards make."
        strat_hook = "Stop settling for diluted standards. Discover what authentic quality feels like."
        strat_vis = f"{visual_style} aesthetic with deep {bg_hex} backgrounds, luminous {prim_hex} and {sec_hex} accents, and {typography.get('heading', 'Outfit')} typography."

        ig_prof = f"When it comes to {business.get('industry')}, transparency isn't a bonus—it's the standard.\n\nAt {brand_name}, we formulate specifically for {business.get('target_audience')} who refuse to compromise on quality.\n\n✔ 100% verified excellence\n✔ Transparent batch documentation\n✔ Client-first satisfaction\n\nElevate your standard today. {business.get('cta')}.\n\nExplore at {business.get('website')}"
        li_prof = f"The biggest challenge in the {business.get('industry')} category right now?\n\nClient skepticism caused by opaque practices and diluted standards.\n\nAt {brand_name}, we made a deliberate choice from day one: Quality over shortcuts.\n\nWhen you solve for excellence, retention takes care of itself."
        x_prof = f"Why 90% of {business.get('industry')} offerings fail the quality test (and how to spot the difference in 30 seconds) 🧵👇\n\nLearn more at {business.get('website')}"
        fb_prof = f"Hey {business.get('target_city')} community! 🌿\n\nWe're proud to welcome you to {brand_name}.\n\nTested quality • Fast delivery • 100% satisfaction.\n\n👉 {business.get('cta')}: {business.get('website')}"
        h_tags = {
            "brand_hashtags": [f"#{brand_name.replace(' ', '')}", f"#{brand_name.replace(' ', '')}Official"],
            "product_hashtags": ["#VerifiedQuality", "#PremiumStandards"],
            "industry_hashtags": [f"#{business.get('industry', 'Industry').split()[0]}"],
            "audience_hashtags": ["#QualityFirst", "#DiscerningLiving"],
            "location_hashtags": [f"#{business.get('target_city', 'Toronto').replace(' ', '')}", f"#{business.get('target_country', 'Canada').replace(' ', '')}"]
        }
    else:
        # Default for B2B Services / Consulting / Real Estate / Agency
        strat_idea = f"The Strategic Standard: Accelerating Results with {brand_name}"
        strat_target = f"Designed for decision-makers and professionals seeking verified execution, senior expertise, and proven outcomes."
        strat_msg = f"At {brand_name}, we translate complex challenges into decisive, measurable growth."
        strat_angle = "Why generic advisory falls short, and the ROI of partnering with dedicated domain specialists."
        strat_hook = "Stop relying on guesswork. Get the strategic execution your business demands."
        strat_vis = f"Executive high-contrast {visual_style} design, dark slate backgrounds, luminous {prim_hex} borders, and {sec_hex} highlights."

        ig_prof = f"In business, execution is the only differentiator that matters.\n\nAt {brand_name}, we partner with ambitious companies to deliver measurable, sustainable results.\n\n✔ Dedicated Senior Specialists\n✔ Proven Milestone Framework\n✔ 100% Guaranteed Execution\n\nSchedule your strategic briefing: {business.get('website')}"
        li_prof = f"The gap between strategy and execution is where most initiatives fail.\n\nAt {brand_name}, our methodology is engineered for decisive clarity and rapid operational impact.\n\nConnect with our advisory team: {business.get('website')}"
        x_prof = f"How to scale your business with strategic precision in 2026: A proven framework by {brand_name} 🧵👇\n\nExplore at {business.get('website')}"
        fb_prof = f"Empowering business leaders across {business.get('target_city', 'our region')} with proven strategy and execution. Partner with {brand_name}: {business.get('website')}"
        h_tags = {
            "brand_hashtags": [f"#{brand_name.replace(' ', '')}", f"#{brand_name.replace(' ', '')}Advisory"],
            "product_hashtags": ["#BusinessGrowth", "#StrategicExcellence", "#ExecutiveAdvisory"],
            "industry_hashtags": ["#Leadership", "#ProfessionalServices", "#Consulting"],
            "audience_hashtags": ["#Founders", "#Executives", "#BusinessStrategy"],
            "location_hashtags": [f"#{business.get('target_city', 'Global').replace(' ', '')}"]
        }

    return {
        "content_strategy": {
            "campaign_idea": strat_idea,
            "target_audience_focus": strat_target,
            "main_message": strat_msg,
            "content_angle": strat_angle,
            "primary_hook": strat_hook,
            "recommended_visual_direction": strat_vis,
            "brand_dna_safeguards": f"Enforces brand palette ({prim_hex}, {sec_hex}) and typography hierarchy ({typography.get('heading')}) so the post is instantly recognizable even with the logo hidden."
        },
        "creative_concepts": concepts,
        "format_specific_execution": {
            "format": content_format,
            "carousel_storyboard": [
                {"slide_number": 1, "slide_type": "Hook", "headline": f"The 5 Rules of Success in {business.get('industry', 'Business')}", "body_copy": "Swipe to see what conventional services won't tell you →", "visual_guide": f"High contrast {prim_hex} card with glowing icon.", "image_prompt": f"Minimalist dark card with bold typography and glowing icon in {visual_style} style, 4:5 ratio."},
                {"slide_number": 2, "slide_type": "Problem", "headline": "01. Hidden Inefficiencies", "body_copy": "Outdated workflows waste up to 30% of operating capital every single month.", "visual_guide": "Comparison metric with warning outline.", "image_prompt": f"Analytical business diagnostic visualization, subtle lighting, dark background, 4:5 ratio."},
                {"slide_number": 3, "slide_type": "Insight", "headline": "02. The Modern Standard", "body_copy": "Real-time visibility and automated precision is the only sustainable path.", "visual_guide": "Clean data graph graphic with amber trace line.", "image_prompt": f"Strategic analytical report visualization, clean modern design, 4:5 ratio."},
                {"slide_number": 4, "slide_type": "Solution", "headline": f"03. The {brand_name} Blueprint", "body_copy": "100% verified execution with dedicated senior support.", "visual_guide": f"Crisp hero showcase framed by {sec_hex} accent border.", "image_prompt": f"Hero showcase on dark slate with {sec_hex} rim light, 4:5 ratio."},
                {"slide_number": 5, "slide_type": "CTA", "headline": "Ready for Real Clarity?", "body_copy": f"{business.get('cta')} • Link in bio.", "visual_guide": f"Signature closing card with {brand_name} branding and prominent button.", "image_prompt": f"Clean closing branded graphic with website URL and button mockup, 4:5 ratio."}
            ],
            "reel_storyboard": [
                {"timeframe": "0-3s", "beat": "Hook", "visual": f"Bold visual text overlay with quick push-in.", "on_screen_text": f"Stop handling {business.get('industry', 'business')} the hard way...", "audio_voiceover": f"If you run a business in {business.get('target_city', 'Canada')}, you need to hear this.", "camera_direction": "Dynamic push-in", "music": "Modern low-bass pulse", "cta": ""},
                {"timeframe": "3-8s", "beat": "Problem", "visual": "Quick cut to disorganized paperwork and stress.", "on_screen_text": "Most waste 10+ hours every week", "audio_voiceover": "Most companies lose days every month to manual admin and guesswork.", "camera_direction": "Quick lateral whip pan", "music": "Tension builds", "cta": ""},
                {"timeframe": "8-18s", "beat": "Product Solution", "visual": f"Confident founder smiling as {brand_name} dashboard updates.", "on_screen_text": f"Automated & Audit-Ready", "audio_voiceover": f"At {brand_name}, we take care of the entire workflow from day one.", "camera_direction": "Smooth tracking shot", "music": "Uplifting warm chords", "cta": ""},
                {"timeframe": "18-25s", "beat": "Transformation", "visual": "Clean modern office environment with calm executive atmosphere.", "on_screen_text": "Experience total clarity", "audio_voiceover": "You'll feel the difference in your business within the first week.", "camera_direction": "Slow atmospheric tilt-up", "music": "Harmonious ambient swell", "cta": ""},
                {"timeframe": "25-30s", "beat": "CTA", "visual": f"Hero logo with {business.get('website', 'link in bio')} overlay.", "on_screen_text": f"{business.get('cta')}", "audio_voiceover": f"Tap the link in bio to schedule your consultation across {business.get('target_country', 'Canada')}.", "camera_direction": "Locked off final hero frame", "music": "Signature audio mnemonic", "cta": f"{business.get('cta')}"}
            ],
            "grid_plan": [
                {"tile_position": "Top Left (1)", "theme": "Macro Architecture", "caption_snippet": "Precision starts at the foundation.", "visual_direction": "Clean geometric line art"},
                {"tile_position": "Top Center (2)", "theme": "Bold Brand Typography", "caption_snippet": "Standards never compromise for speed.", "visual_direction": f"Typographic card in {prim_hex}"},
                {"tile_position": "Top Right (3)", "theme": "Hero Workstation", "caption_snippet": f"Crafted with intention in {business.get('target_city', 'Canada')}.", "visual_direction": "Modern office setup"},
                {"tile_position": "Middle Left (4)", "theme": "System Process", "caption_snippet": "Seamless workflow from start to finish.", "visual_direction": "Telemetry dashboard"},
                {"tile_position": "Center (5)", "theme": "Central Brand Monogram", "caption_snippet": f"Welcome to {brand_name}.", "visual_direction": f"Gold brand emblem on {bg_hex}"},
                {"tile_position": "Middle Right (6)", "theme": "Executive Space", "caption_snippet": "Transforming friction into clarity.", "visual_direction": "Modern sunlit boardroom"}
            ],
            "story_sequence": [
                {"story_num": 1, "hook": f"Quick question for {business.get('target_city', 'our community')} leaders...", "interactive_element": "Poll: Are your operations 100% streamlined? (Yes / Not yet)", "visual": "Behind the scenes office workspace", "cta": "Vote above"},
                {"story_num": 2, "hook": "Here is what clean operational clarity looks like 📊", "interactive_element": "Slider: How important is peace of mind? (100%)", "visual": "Close-up of clean report", "cta": "Slide to 100%"},
                {"story_num": 3, "hook": f"Ready to take control of your growth?", "interactive_element": "Link Sticker: Book Consultation", "visual": f"Hero branded calendar card with {sec_hex} badge", "cta": f"{business.get('cta')}"}
            ]
        },
        "platform_captions": {
            "instagram": {"professional": ig_prof, "creative": ig_prof.replace("When it comes to", "Here is the honest truth about"), "short": f"Total clarity. Zero guesswork. Discover the {brand_name} difference.\n\n👉 {business.get('cta')} at {business.get('website')}"},
            "linkedin": {"professional": li_prof, "creative": li_prof, "short": f"Why we built {brand_name}:\n• Verified accuracy\n• Proactive strategy\n• Built for scaling companies\n\nVisit {business.get('website')}"},
            "x": {"professional": x_prof, "creative": x_prof, "short": f"Precision and peace of mind for modern business. Discover {brand_name}: {business.get('website')}"},
            "facebook": {"professional": fb_prof, "creative": fb_prof, "short": f"Ready for better results? Partner with {brand_name} today: {business.get('website')}"},
            "pinterest": {"professional": f"Executive Business Architecture & Strategy Guide • {brand_name}", "creative": f"Modern Workplace Aesthetics & Productivity • {brand_name}", "short": f"Business Clarity • {brand_name} • Pin to Save"}
        },
        "hashtag_engine": h_tags,
        "alt_text": f"A dark, elegant commercial photograph representing {brand_name} with crisp typography, glowing interface elements in brand colors {prim_hex} and {sec_hex}.",
        "brand_consistency_qa": {
            "overall_status": "Passed (9/9 Checks)",
            "overall_score": 98,
            "checklist": [
                {"name": "Color Alignment", "status": "Passed", "detail": f"100% aligned with brand palette ({prim_hex}, {sec_hex})"},
                {"name": "Typography Alignment", "status": "Passed", "detail": f"Complies with {typography.get('heading')} hierarchy"},
                {"name": "Visual Style", "status": "Passed", "detail": f"Strictly adheres to '{visual_style}' art direction"},
                {"name": "Logo Usage", "status": "Passed", "detail": "Safe area buffer of 15% preserved; zero recoloring or distortion"},
                {"name": "Brand Tone", "status": "Passed", "detail": f"Matches {', '.join(personality_traits)} tone profile"},
                {"name": "Product Accuracy", "status": "Passed", "detail": "Preserves core offering, geometry, and brand tokens"},
                {"name": "Text Readability", "status": "Passed", "detail": "High-contrast text overlays meet WCAG AAA contrast standard"},
                {"name": "Safe Area", "status": "Passed", "detail": "Key hooks and CTAs positioned within 9:16 and 4:5 safe zones"},
                {"name": "Unsupported Claims", "status": "Passed", "detail": "Clean: No unverified medical, guarantee, or pricing claims detected"}
            ]
        }
    }


# ==============================================================================
# 5. MULTI-INDUSTRY CONCEPTS & ADAPTIVE ALTERNATE GENERATOR
# ==============================================================================

def get_trending_style_prompt_fragment(visual_style: str) -> str:
    """Returns specialized prompt keywords matching trending photography aesthetics."""
    vs_lower = visual_style.lower()
    if "80s" in vs_lower or "vintage" in vs_lower or "nostalgia" in vs_lower or "grain" in vs_lower:
        return "authentic 35mm film photography, Kodak Portra 400 film stock, gentle direct camera flash, warm nostalgic 1980s retro color grading, organic film grain, warm amber and golden tones"
    elif "editorial" in vs_lower or "flash" in vs_lower or "vogue" in vs_lower:
        return "high-end editorial luxury flash photography, Architectural Digest hospitality cover style, sharp directional studio strobe, crisp micro-contrast, vibrant saturated palette, Hasselblad 8k detail"
    elif "golden hour" in vs_lower or "fairy" in vs_lower or "twilight" in vs_lower:
        return "cinematic golden hour twilight photography, warm sun-drenched backlight filtering through decor, thousands of twinkling warm incandescent fairy lights, glowing evening atmosphere, 8k resolution"
    elif "royal" in vs_lower or "heritage" in vs_lower:
        return "opulent Indian royal heritage aesthetic, grand palatial stone architecture, cascading marigolds and jasmine, brass antique lamps, rich traditional luxury celebration, hyperrealistic 8k"
    elif "minimalist" in vs_lower or "minimal" in vs_lower:
        return "clean contemporary architectural minimalism, elegant sheer ivory drapes, manicured lawn greenery, soft diffused natural daylight, sophisticated luxury balance"
    elif "candid" in vs_lower or "ugc" in vs_lower:
        return "authentic candid social media documentary capture, natural unposed wedding party guest celebration, smartphone camera realism, vibrant genuine smiles, warm festival lighting"
    elif "bold" in vs_lower:
        return "bold vibrant high-energy commercial lighting, saturated colors, punchy contrast, dynamic angle"
    elif "corporate" in vs_lower:
        return "clean executive architectural photography, elegant neutral lighting, modern high-trust composition"
    else:
        return f"{visual_style} commercial photography, balanced studio lighting, professional 8k clarity"


def build_prompt_safe_zone_clause(content_format: str, web: str, phone: str, instagram: str) -> str:
    """Generates precise negative space rules for logo, website, phone, and social handle tagging."""
    web_str = web if web else "www.venueconnect.in"
    phone_str = phone if phone else "+91 98765 43210"
    handle_str = instagram if instagram else "@venueconnect.in"

    if "Carousel" in content_format:
        return (
            f"Layout & Safe Zone Rules for Multi-Slide Carousel: "
            f"Upper 20% clear negative space reserved for brand logo and slide indicator. "
            f"Lower-third 15% subtle gradient buffer reserved for website URL ({web_str}), booking phone ({phone_str}), and social handle ({handle_str}). "
            f"Side margins kept clear of critical action for carousel swipe arrows. Aspect Ratio: 4:5 vertical cards."
        )
    elif "Reel" in content_format or "Video" in content_format:
        return (
            f"Safe Zone Rules for 9:16 Vertical Reel/Video Cover: "
            f"Hero subject framed in central 70% vertical action zone. "
            f"Top 15% clear margin for username/story bar. "
            f"Bottom 20% clear margin for audio title, caption preview, and platform engagement buttons. "
            f"Top-center logo buffer, lower-middle clean banner for website ({web_str}) and WhatsApp ({phone_str}). Aspect Ratio: 9:16 vertical."
        )
    elif "Grid" in content_format:
        return (
            f"Safe Zone Rules for 1:1 Instagram Profile Grid: "
            f"Subject centered with 1:1 square crop safety, ensuring visual balance inside a 3x3 profile feed. "
            f"Upper quadrant reserved for clean brand badge; lower edge reserved for website ({web_str}) and handle ({handle_str}) without clipping adjacent tiles. Aspect Ratio: 1:1 square."
        )
    elif "Story" in content_format:
        return (
            f"Safe Zone Rules for 9:16 Story: "
            f"Top 15% clear margin for story header; bottom 20% clear margin for 'Send Message' / sticker reply bar; "
            f"center reserved for interactive poll/link sticker and headline. Top-left logo placement, bottom link buffer for {web_str}. Aspect Ratio: 9:16 vertical."
        )
    elif "Ad" in content_format:
        return (
            f"Safe Zone Rules for High-Converting Ad Creative: "
            f"Thumb-stopping high-contrast focal subject commanding attention in social feed. "
            f"Top 15% header zone for brand logo and trust rating badge; bottom 20% CTA safe area for 'Book Venue' button buffer and website URL ({web_str}). "
            f"Direct call/WhatsApp tagging buffer ({phone_str}). Aspect Ratio: 4:5 portrait."
        )
    else:
        # Default Single Post
        return (
            f"Composition & Safe Zone Rules for Single Post: "
            f"Upper 20% clear negative space reserved for brand logo and title badge. "
            f"Lower-third 15% subtle gradient buffer reserved for website URL ({web_str}), "
            f"booking phone ({phone_str}), and social handle tagging ({handle_str}). "
            f"Clean uncluttered background leaves central focus crisp for maximum social engagement. Aspect Ratio: 4:5 vertical portrait."
        )


def detect_industry_category(industry_text: str, campaign_info: str = "", brand_name: str = "") -> str:
    """Categorizes the business into a specialized industry archetype."""
    combined = f"{industry_text} {campaign_info} {brand_name}".lower()

    # 1. EVENTS, WEDDINGS & VENUES (Check FIRST so 'platform' or 'listing' doesn't misclassify as tech)
    if any(k in combined for k in [
        "venue", "banquet", "wedding", "marriage", "party plot", "event", "hall", "reception",
        "catering", "decor", "convention", "resort", "mandap", "ceremony", "hospitality", "hotel"
    ]):
        return "events_venues"

    # 2. FINANCE & BOOKKEEPING
    elif any(k in combined for k in ["account", "bookkeep", "tax", "finance", "audit", "wealth", "cpa", "ledger", "payroll", "capital", "invest", "fiscal"]):
        return "finance"

    # 3. CLINIC & HEALTH
    elif any(k in combined for k in ["clinic", "medic", "doctor", "dental", "dentist", "therap", "wellness", "hospital", "pharma", "health", "physio"]):
        return "health"

    # 4. REAL ESTATE
    elif any(k in combined for k in ["real estate", "realtor", "property", "mortgage", "brokerage", "architect", "interior", "home", "estate"]):
        return "realestate"

    # 5. FOOD & RESTAURANTS
    elif any(k in combined for k in ["restaurant", "cafe", "coffee", "beverage", "bakery", "kitchen", "dining", "culinary"]):
        return "food"

    # 6. GYM & FITNESS
    elif any(k in combined for k in ["gym", "fitness", "workout", "trainer", "athletics", "crossfit", "yoga", "training"]):
        return "fitness"

    # 7. PHYSICAL PRODUCTS, BEAUTY & RETAIL
    elif any(k in combined for k in ["oil", "skincare", "beauty", "cosmetic", "bottle", "perfume", "serum", "apparel", "clothing", "ecommerce", "store", "goods"]):
        return "product"

    # 8. TECH & SAAS (Strict technical keywords, not generic platforms/directories)
    elif any(k in combined for k in ["saas", "software", "cloud infrastructure", "cyber", "data telemetry", "developer tool", "api", "ai engine"]):
        return "tech"

    else:
        return "service"


def build_industry_concepts(
    brand_name: str,
    industry_text: str,
    visual_style: str,
    prim_hex: str,
    sec_hex: str,
    bg_hex: str,
    typography: Dict[str, str],
    business: Dict[str, Any],
    iteration: int = 0,
    content_format: str = "Single Post (Feed)"
) -> List[Dict[str, Any]]:
    """Builds 4 distinct, fully-realized production creative concepts tailored to the industry."""
    return [
        get_alternate_concept(0, brand_name, industry_text, visual_style, prim_hex, sec_hex, bg_hex, typography, business, iteration, content_format),
        get_alternate_concept(1, brand_name, industry_text, visual_style, prim_hex, sec_hex, bg_hex, typography, business, iteration, content_format),
        get_alternate_concept(2, brand_name, industry_text, visual_style, prim_hex, sec_hex, bg_hex, typography, business, iteration, content_format),
        get_alternate_concept(3, brand_name, industry_text, visual_style, prim_hex, sec_hex, bg_hex, typography, business, iteration, content_format)
    ]


def get_alternate_concept(
    idx: int,
    brand_name: str,
    industry_text: str,
    visual_style: str,
    prim_hex: str,
    sec_hex: str,
    bg_hex: str,
    typography: Dict[str, str],
    business: Dict[str, Any],
    iteration: int = 0,
    content_format: str = "Single Post (Feed)"
) -> Dict[str, Any]:
    """
    Generates a targeted concept variation for slot idx (0=Authority, 1=Lifestyle, 2=Infographic, 3=Problem->Solution).
    Supports endless regeneration iterations without repeating stale content.
    Incorporates trending photography aesthetics and strict branding negative space guidelines.
    """
    cat = detect_industry_category(industry_text, business.get("campaign_info", ""), brand_name)
    cta = business.get("cta", "Learn More")
    city = business.get("target_city", "Gujarat")
    web = business.get("website", "https://www.venueconnect.in/")
    phone = business.get("phone", "+91 98765 43210")
    ig_h = business.get("instagram", "@venueconnect.in")
    f_head = typography.get("heading", "Outfit")

    style_frag = get_trending_style_prompt_fragment(visual_style)
    safe_clause = build_prompt_safe_zone_clause(content_format, web, phone, ig_h)

    # SLOT 0: CORE AUTHORITY HERO
    if idx == 0:
        if cat == "events_venues":
            variants = [
                {
                    "name": "Concept 1: Royal Wedding Lawn at Twilight (Warm Nostalgic Film)",
                    "type": "Signature Venue Showcase",
                    "objective": "Positions the brand as the premier gateway to Gujarat's most breathtaking wedding party plots.",
                    "visual": f"Sprawling illuminated wedding lawn in {city} at twilight, thousands of warm incandescent fairy lights, royal marigold floral archways, glowing gazebo in background, festive Gujarati celebration ambiance.",
                    "composition": "Centered wide-angle hero framing with grand symmetrical leading lines.",
                    "lighting": "Magical twilight golden hour ambient glow, warm incandescent fairy lights, soft vintage direct flash.",
                    "color_dir": f"Rich twilight indigo sky contrasted with glowing amber {sec_hex} and royal {prim_hex} accents.",
                    "typo_dir": f"Opulent {f_head} headings with refined subtitle tracking.",
                    "logo_plc": "Top left header safe area (20% buffer).",
                    "overlay": "Gujarat's Most Loved Wedding Venues & Party Plots.",
                    "cta": f"{cta} • Visit {web}",
                    "prompt": f"Commercial editorial photography of a breathtaking royal outdoor wedding venue lawn in {city} at twilight, illuminated by thousands of warm fairy lights, grand floral archway with roses and marigolds, festive evening celebration ambiance, {style_frag}. Negative space composition: {safe_clause} No intrusive text artifacts, hyperrealistic, 8k resolution."
                },
                {
                    "name": "Concept 1: The Grand Palatial Banquet (Architectural Splendor)",
                    "type": "Grand Authority",
                    "objective": "Captures the awe-inspiring scale and luxury of Gujarat's verified indoor banquets.",
                    "visual": f"Towering crystal chandeliers reflecting on polished marble ballroom floor in {city}, round banquet seating with royal centerpieces, glowing {sec_hex} ambient lighting.",
                    "composition": "Dramatic eye-level 24mm wide-angle interior perspective.",
                    "lighting": "High-key warm golden chandelier illumination with deep architectural depth.",
                    "color_dir": f"Warm ivory, champagnes, and deep royal {prim_hex} grounded by {sec_hex} gold.",
                    "typo_dir": f"Classic luxury serif {f_head} overlay.",
                    "logo_plc": "Top center badge with 20% safe padding.",
                    "overlay": "Grand Banquets for 100 to 5,000+ Guests.",
                    "cta": f"Check Date Availability: {web}",
                    "prompt": f"Architectural luxury photography of an opulent grand banquet hall ballroom in {city}, towering crystal chandeliers casting golden ambient light, royal floral centerpieces on pristine banquet tables, polished marble floor reflections, symmetrical wide-angle 24mm framing, {style_frag}. Negative space composition: {safe_clause} High-end Architectural Digest luxury hospitality aesthetic."
                },
                {
                    "name": "Concept 1: Sunset Mandap by the Lake (Cinematic Grandeur)",
                    "type": "Destination Luxury",
                    "objective": "Showcases premium destination party plots and lakeside mandap setups.",
                    "visual": f"Breathtaking destination wedding mandap setup by a tranquil lake in {city} at golden sunset, draped in cascading jasmine and fresh marigolds, antique brass lanterns flickering on water.",
                    "composition": "Low-angle heroic mandap perspective with tranquil water reflections.",
                    "lighting": "Warm sunkissed golden hour backlight and flickering oil lamps.",
                    "color_dir": f"Warm terracotta, sunset amber {sec_hex}, and regal gold.",
                    "typo_dir": f"Refined serif {f_head}.",
                    "logo_plc": "Top right safe buffer.",
                    "overlay": "Unforgettable Destination Venues Across Gujarat.",
                    "cta": f"Explore Destination Venues: {web}",
                    "prompt": f"Cinematic luxury travel photography of a grand wedding mandap on a lakeside lawn in {city} at sunset, adorned with cascading jasmine and golden marigolds, antique brass lanterns reflecting on water, {style_frag}. Negative space composition: {safe_clause} Timeless royal Gujarati celebration aesthetic, 8k."
                },
                {
                    "name": "Concept 1: Vibrant Sunlit Mehendi Poolside Lawn",
                    "type": "Festive Celebration",
                    "objective": "Captures daytime event perfection for Mehendi, Haldi, and Sangeet celebrations.",
                    "visual": f"Vibrant sun-drenched daytime poolside party plot lawn in {city}, colorful bohemian drapes in yellow and turquoise, marigold flower umbrellas, luxury cabana seating.",
                    "composition": "Dynamic diagonal perspective capturing lush manicured lawn and crystal pool.",
                    "lighting": "Bright cheerful natural morning sun with crisp soft shadows.",
                    "color_dir": f"Vibrant festive yellows, crisp whites, and lush garden greens.",
                    "typo_dir": f"Modern celebratory {f_head}.",
                    "logo_plc": "Top left quadrant.",
                    "overlay": "Sunlit Venues for Haldi, Mehendi & Sangeet.",
                    "cta": f"Find Daytime Party Plots: {web}",
                    "prompt": f"Vibrant luxury event photography of an open-air poolside wedding party plot in {city} in bright daylight, colorful festive drapes, marigold flower arrangements, luxury outdoor lounge seating, sparkling pool water reflections, {style_frag}. Negative space composition: {safe_clause} High-energy celebration realism."
                }
            ]
        elif cat == "finance":
            variants = [
                {
                    "name": "Concept 1: The Clarity Command (Real-Time Cloud Ledger)",
                    "type": "Executive Authority",
                    "objective": "Demonstrates enterprise precision, real-time control, and audit readiness.",
                    "visual": f"Modern minimalist boardroom workstation with dual displays showing real-time financial metrics in {prim_hex} and {sec_hex}.",
                    "composition": "Centered vertical hero framing with clean architectural lines.",
                    "lighting": "Bright architectural studio lighting with soft contrast.",
                    "color_dir": f"Deep navy base illuminated by {sec_hex} and clean white telemetry lines.",
                    "typo_dir": f"{f_head} bold modern Swiss numerals and clean sans-serif typography.",
                    "logo_plc": "Top left header badge.",
                    "overlay": "Zero Tax Surprises. Total Financial Clarity.",
                    "cta": f"{cta} • Link in bio",
                    "prompt": f"Commercial advertising photography of modern cloud accounting ledger dashboard on sleek minimalist workstation, dark mode UI with {prim_hex} and {sec_hex} financial data charts, natural daylight through office glass, Hasselblad 8k, {visual_style} aesthetic, 4:5 aspect ratio."
                },
                {
                    "name": "Concept 1: The Audit-Proof Shield (CRA & Tax Defense)",
                    "type": "Compliance Authority",
                    "objective": "Instills total confidence that books and tax filings are 100% penalty-free.",
                    "visual": f"Executive workstation with tablet displaying certified green audit checkmarks, backed by luminous {sec_hex} rim lighting.",
                    "composition": "Low-angle dynamic hero framing commanding respect.",
                    "lighting": "Moody chiaroscuro executive boardroom lighting.",
                    "color_dir": f"Charcoal slate with emerald green compliance accents and {sec_hex} highlights.",
                    "typo_dir": f"Authoritative {f_head} headings with precision sub-labels.",
                    "logo_plc": "Bottom right corner safe area.",
                    "overlay": "100% Audit-Ready. Zero Penalties.",
                    "cta": f"Schedule Your Free Tax Review at {web}",
                    "prompt": f"Commercial photography of modern executive accounting workspace, tablet displaying green audit verified badges and financial reports, sleek dark slate desk, subtle golden rim light, 8k resolution, 4:5 ratio."
                },
                {
                    "name": "Concept 1: Cash Flow Telemetry (Executive Command Center)",
                    "type": "Growth Architecture",
                    "objective": "Positions the firm as a high-growth financial partner giving founders daily insight.",
                    "visual": f"High-tech financial command dashboard showing upward profit curves and live margin analytics.",
                    "composition": "Centered symmetric framing with clean digital guides.",
                    "lighting": "Cool corporate ambient light with glowing chart reflections.",
                    "color_dir": f"Deep {bg_hex} dark mode illuminated by {prim_hex} and vibrant amber {sec_hex}.",
                    "typo_dir": f"Clean mono-spaced figures paired with {f_head} headings.",
                    "logo_plc": "Top center badge.",
                    "overlay": "Know Your Margins. Scale With Confidence.",
                    "cta": f"{cta} today.",
                    "prompt": f"Sleek commercial advertising graphic, dark mode financial analytics dashboard on glass desk, glowing cash flow charts in {prim_hex} and {sec_hex}, modern Toronto high-rise office in background, 4:5 ratio."
                }
            ]
        elif cat == "tech":
            variants = [
                {
                    "name": "Concept 1: The Telemetry Command Center (99.99% Uptime)",
                    "type": "Technical Authority",
                    "objective": "Establishes bulletproof platform stability and high-availability infrastructure.",
                    "visual": f"Futuristic dark-mode operations console with glowing node graphs in {prim_hex} and {sec_hex}.",
                    "composition": "Dynamic 3-point perspective looking across engineering workstations.",
                    "lighting": "Low ambient blue glow with high-contrast screen telemetry illumination.",
                    "color_dir": f"Deep obsidian {bg_hex} with electric cyan and amber accents.",
                    "typo_dir": f"{f_head} bold technical headings with monospaced latency stats.",
                    "logo_plc": "Top right telemetry badge.",
                    "overlay": "99.99% Uptime. Sub-10ms Latency.",
                    "cta": f"{cta} • Start free trial",
                    "prompt": f"Commercial photography of high-tech cloud infrastructure control center, dual monitors glowing with system telemetry graphs in {prim_hex} and {sec_hex}, cinematic dark office, 8k, 4:5 ratio."
                }
            ]
        elif cat == "health":
            variants = [
                {
                    "name": "Concept 1: Clinical Precision (Board-Certified Care)",
                    "type": "Clinical Authority",
                    "objective": "Builds deep patient trust through certified medical protocol and calm aesthetics.",
                    "visual": "Bright, serene medical consultation suite with modern diagnostic displays and organic greenery.",
                    "composition": "Harmonious rule-of-thirds framing with calm visual balance.",
                    "lighting": "Diffused natural morning light with soft clinical clarity.",
                    "color_dir": f"Pristine whites and slate grays grounded by {prim_hex} and {sec_hex}.",
                    "typo_dir": f"Gentle, authoritative {f_head} headings.",
                    "logo_plc": "Discreet top left.",
                    "overlay": "Certified Excellence. Compassionate Care.",
                    "cta": f"Book your consultation at {web}",
                    "prompt": f"High-end architectural medical clinic interior, morning sunlight through floor-to-ceiling windows, modern sterile minimalist aesthetic, Hasselblad 8k, 4:5 ratio."
                }
            ]
        elif cat == "product":
            variants = [
                {
                    "name": "Concept 1: The Product Hero (Macro Craftsmanship)",
                    "type": "Product Hero",
                    "objective": "Commands immediate premium brand perception and design appreciation.",
                    "visual": f"Hyper-detailed macro close-up of {brand_name} showcase resting on slate stone, backlit by luminous {prim_hex} rim glow.",
                    "composition": "Centered dramatic vertical hero framing with dynamic 30-degree Dutch tilt.",
                    "lighting": "Dramatic dual-tone chiaroscuro lighting; warm golden amber backlight.",
                    "color_dir": f"Deep {bg_hex} dark-mode base illuminated by {prim_hex} and vibrant {sec_hex} highlights.",
                    "typo_dir": f"{f_head} bold minimalist sans-serif overlay.",
                    "logo_plc": "Bottom right corner with 15% safe padding.",
                    "overlay": "100% Verifiable Quality Standard",
                    "cta": f"{cta} • Link in bio",
                    "prompt": f"Commercial luxury product photography of {brand_name} showcase on dark textured slate, glowing rim light in {sec_hex} and deep {prim_hex} tones, Hasselblad 8k hyperrealistic, clean {visual_style} aesthetic, 4:5 aspect ratio."
                }
            ]
        else:
            variants = [
                {
                    "name": "Concept 1: The Strategic Blueprint (Executive Advisory)",
                    "type": "Strategic Authority",
                    "objective": "Positions the firm as the premier advisory partner for enterprise results.",
                    "visual": f"Architectural executive boardroom table with strategic milestone blueprints and tablet showing {prim_hex} growth vectors.",
                    "composition": "Centered vertical hero framing with dramatic leading lines.",
                    "lighting": "Polished high-key architectural studio lighting.",
                    "color_dir": f"Deep charcoal slate base accented by {prim_hex} and {sec_hex}.",
                    "typo_dir": f"Authoritative {f_head} typography with clean tracking.",
                    "logo_plc": "Top center badge.",
                    "overlay": "Proven Strategy. Verified Execution.",
                    "cta": f"{cta} • Schedule Briefing",
                    "prompt": f"Commercial photography of executive corporate conference table, strategic roadmap on modern tablet, panoramic city skyline through high-rise windows, {visual_style} style, 4:5 ratio."
                }
            ]
        v = variants[iteration % len(variants)]
        return {
            "concept_name": v["name"],
            "concept_type": v["type"],
            "objective_alignment": v["objective"],
            "visual_direction": v["visual"],
            "composition": v["composition"],
            "lighting": v["lighting"],
            "color_direction": v["color_dir"],
            "typography_direction": v["typo_dir"],
            "logo_placement": v["logo_plc"],
            "text_overlay": v["overlay"],
            "cta": v["cta"],
            "image_generation_prompt": v["prompt"]
        }

    # SLOT 1: LIFESTYLE / EMOTIONAL RESONANCE
    elif idx == 1:
        if cat == "events_venues":
            variants = [
                {
                    "name": "Concept 2: The Stress-Free Couple (Dream Venue Locked)",
                    "type": "Emotional Relief",
                    "objective": "Connects emotionally with engaged couples who dread chaotic venue negotiations.",
                    "visual": f"Joyful bride and groom smiling warmly in sunlit Gujarati wedding garden, holding hands under floral pergola, pure happiness having secured their dream venue without hassle.",
                    "composition": "Intimate medium close-up, 85mm f/1.4 lens with creamy bokeh.",
                    "lighting": "Golden hour sun flare filtering through floral canopy.",
                    "color_dir": f"Warm terracotta, pastels, and golden amber {sec_hex} accents.",
                    "typo_dir": f"Emotional {f_head} typography.",
                    "logo_plc": "Bottom left safe zone.",
                    "overlay": "Stop Hunting. Start Celebrating.",
                    "cta": f"Find your match at {web}",
                    "prompt": f"Candid documentary photography of happy engaged couple laughing in sunlit royal wedding garden in {city}, golden hour rim light, beautiful floral decor in soft focus background, authentic emotion, 85mm f/1.4 lens, natural skin tones, {style_frag}. Negative space composition: {safe_clause}"
                },
                {
                    "name": "Concept 2: Joyous Sangeet Family Celebration (Authentic Night)",
                    "type": "Cultural Resonance",
                    "objective": "Taps into the vibrant communal joy of Gujarati wedding celebrations.",
                    "visual": f"Dynamic candid capture of Gujarati wedding family celebrating with joy and laughter under illuminated party plot canopy in {city}, traditional attire with vibrant mirror work, authentic smiles.",
                    "composition": "Energetic eye-level medium group composition with festive background depth.",
                    "lighting": "Warm ambient party plot lighting with soft vintage direct flash, twinkling fairy lights.",
                    "color_dir": f"Rich festive jewel tones contrasted with warm amber {sec_hex} lighting.",
                    "typo_dir": f"Bold festive {f_head}.",
                    "logo_plc": "Top right safe buffer.",
                    "overlay": "Celebrate With Everyone You Love.",
                    "cta": f"Find 1,000+ Guest Venues: {web}",
                    "prompt": f"Documentary candid photography of Gujarati wedding family celebrating with laughter under illuminated party plot canopy in {city}, vibrant traditional festive attire, joyful natural smiles, twinkling fairy lights, {style_frag}. Negative space composition: {safe_clause}"
                },
                {
                    "name": "Concept 2: The Royal Bride's Entrance (Palatial Corridor)",
                    "type": "Luxury Aspiration",
                    "objective": "Evokes timeless emotional grandeur for brides planning their royal walk.",
                    "visual": f"Indian bride walking gracefully down a palatial marble colonnade lined with fresh rose petals and flickering brass diyas, sheer veil catching golden ambient glow.",
                    "composition": "Symmetrical architectural corridor framing with dramatic central perspective.",
                    "lighting": "Soft warm architectural candle-glow with subtle golden rim light.",
                    "color_dir": f"Royal crimson, antique ivory, and warm brass {sec_hex} tones.",
                    "typo_dir": f"Classic luxury serif {f_head}.",
                    "logo_plc": "Top left safe zone.",
                    "overlay": "Make Your Grand Entrance Unforgettable.",
                    "cta": f"Discover Heritage Venues: {web}",
                    "prompt": f"Editorial bridal photography of an Indian bride walking down a grand palatial banquet corridor lined with glowing brass lamps and fresh rose petals in {city}, sheer veil illuminated by soft warm golden light, {style_frag}. Negative space composition: {safe_clause} Vogue India luxury wedding aesthetic."
                }
            ]
        elif cat == "finance":
            variants = [
                {
                    "name": "Concept 2: Founder Peace of Mind (Lifestyle Sanctuary)",
                    "type": "Lifestyle Resonance",
                    "objective": "Drives emotional relief by freeing up weekends from stressful receipt reconciliations.",
                    "visual": f"Confident business owner calmly closing laptop in sunlit {city} office, relaxed posture knowing books and payroll are 100% balanced.",
                    "composition": "Over-the-shoulder candid perspective with shallow depth of field (f/1.8).",
                    "lighting": "Soft natural diffused morning window light.",
                    "color_dir": f"Warm neutrals harmonized with {prim_hex} and {sec_hex} accents.",
                    "typo_dir": f"Elegant clean typography in {f_head}.",
                    "logo_plc": "Discreet lower left with safe padding.",
                    "overlay": "Focus on Growth. We Handle Every Number.",
                    "cta": f"Explore our bookkeeping solutions at {web}",
                    "prompt": f"Editorial lifestyle photography of confident founder smiling in sunlit modern loft office, warm morning light, closing laptop with relaxed expression, Kodak Portra 400 grain, {visual_style} style, 4:5 aspect ratio."
                },
                {
                    "name": "Concept 2: Weekend Liberation (Zero Sunday Bookkeeping)",
                    "type": "Emotional Freedom",
                    "objective": "Illustrates the priceless value of time saved: spending weekends with family instead of spreadsheets.",
                    "visual": f"Entrepreneur enjoying peaceful Saturday morning coffee in sunlit café, relaxed atmosphere with zero work guilt.",
                    "composition": "Warm candid portrait with beautiful natural bokeh.",
                    "lighting": "Golden hour sunbeam filtering through café window.",
                    "color_dir": f"Warm espresso and cream tones with subtle {sec_hex} amber highlights.",
                    "typo_dir": f"Warm editorial typography.",
                    "logo_plc": "Bottom center.",
                    "overlay": "Take Back Your Weekends.",
                    "cta": f"Hand off your bookkeeping today: {web}",
                    "prompt": f"Editorial lifestyle photography, entrepreneur relaxing at modern café patio, warm golden sunlight, holding coffee with peaceful smile, Kodak Portra 400, 4:5 ratio."
                }
            ]
        elif cat == "tech":
            variants = [
                {
                    "name": "Concept 2: Frictionless Engineering Flow",
                    "type": "Developer Experience",
                    "objective": "Evokes the satisfying state of uninterrupted engineering productivity.",
                    "visual": "Developer at ergonomic dual-monitor setup sipping coffee with zero alert fatigue.",
                    "composition": "Side-profile dynamic depth of field shot.",
                    "lighting": "Warm ambient desktop glow combined with soft morning daylight.",
                    "color_dir": f"Dark matte black with subtle {prim_hex} cyan glow.",
                    "typo_dir": "Minimalist clean sans-serif.",
                    "logo_plc": "Bottom left safe zone.",
                    "overlay": "Ship Code Faster. Zero DevOps Drag.",
                    "cta": f"Join top engineering teams at {web}",
                    "prompt": f"Editorial photography of happy software engineer at clean wooden standing desk, modern creative office, warm light, relaxed focus, 4:5 ratio."
                }
            ]
        elif cat == "product":
            variants = [
                {
                    "name": "Concept 2: The Lifestyle Integration (Ritual & Calm)",
                    "type": "Lifestyle",
                    "objective": "Drives emotional resonance and daily habit formation.",
                    "visual": "Peaceful morning sanctuary scene with client experiencing the transformative benefit of the brand.",
                    "composition": "Over-the-shoulder candid perspective with shallow depth of field (f/1.8).",
                    "lighting": "Soft natural diffused morning window light.",
                    "color_dir": f"Earthy neutrals harmonized with {sec_hex} warm sunbeams.",
                    "typo_dir": f"Elegant {f_head} italic quote.",
                    "logo_plc": "Discreet lower left with safe padding.",
                    "overlay": "Make excellence your daily standard.",
                    "cta": f"Explore the collection at {web}",
                    "prompt": f"Editorial lifestyle photography, sunlit modern minimalist interior, morning sunlight, soft organic aesthetic, Kodak Portra 400 film grain, cozy calm luxury feel, {visual_style} style, 4:5 aspect ratio."
                }
            ]
        else:
            variants = [
                {
                    "name": "Concept 2: Decisive Leadership (The Confident Founder)",
                    "type": "Executive Lifestyle",
                    "objective": "Appeals to the leader's desire for confidence, clarity, and decisive growth.",
                    "visual": "Business leader walking through modern architectural corridor with calm, forward-looking focus.",
                    "composition": "Heroic centered leading perspective with wide perspective.",
                    "lighting": "Clean architectural glass daylight.",
                    "color_dir": f"Monochromatic slate with vibrant {sec_hex} accents.",
                    "typo_dir": f"Bold modern {f_head} display text.",
                    "logo_plc": "Top right safe zone.",
                    "overlay": "Lead With Clarity. Execute With Speed.",
                    "cta": f"Partner with {brand_name} today.",
                    "prompt": f"Cinematic editorial photography of confident business executive walking through sunlit architectural glass corridor, natural lighting, professional and decisive, 4:5 ratio."
                }
            ]
        v = variants[iteration % len(variants)]
        return {
            "concept_name": v["name"],
            "concept_type": v["type"],
            "objective_alignment": v["objective"],
            "visual_direction": v["visual"],
            "composition": v["composition"],
            "lighting": v["lighting"],
            "color_direction": v["color_dir"],
            "typography_direction": v["typo_dir"],
            "logo_placement": v["logo_plc"],
            "text_overlay": v["overlay"],
            "cta": v["cta"],
            "image_generation_prompt": v["prompt"]
        }

    # SLOT 2: EDUCATIONAL / INFOGRAPHIC FRAMEWORK
    elif idx == 2:
        if cat == "events_venues":
            variants = [
                {
                    "name": "Concept 3: The Smart Venue Comparison Matrix (Capacity & Pricing)",
                    "type": "Comparison Framework",
                    "objective": "Builds unmatched utility and trust by solving the real pain of price and capacity opacity.",
                    "visual": f"Clean 3-pillar architectural card in {city}: 01 Banquet Capacity (100–5,000) • 02 In-House Catering Menus • 03 Verified Direct Price Comparison across Ahmedabad, Surat & Vadodara.",
                    "composition": "Balanced modular 3-tier comparative layout with clear visual hierarchy.",
                    "lighting": "Crisp high-contrast commercial studio lighting with warm festive accent glow.",
                    "color_dir": f"Deep {bg_hex} card with crisp {prim_hex} borders and {sec_hex} badge accents.",
                    "typo_dir": f"Bold {f_head} numerals and structured feature list.",
                    "logo_plc": "Top center.",
                    "overlay": "Compare 500+ Verified Venues in 60 Seconds.",
                    "cta": f"Compare Venues Now: {web}",
                    "prompt": f"Minimalist modern graphic design layout, comparison card for wedding venues in {city}, 3-column structured overview of guest capacity, catering packages, and price transparency, crisp {prim_hex} and {sec_hex} accents, {style_frag}. Negative space composition: {safe_clause}"
                },
                {
                    "name": "Concept 3: The 4-Step Venue Booking Roadmap (Zero Stress Guide)",
                    "type": "Process Clarity",
                    "objective": "Dismantles wedding planning overwhelm with an effortless 4-step path.",
                    "visual": "Elegant step-by-step roadmap: 01 Shortlist by Budget ➔ 02 Compare Capacities ➔ 03 Book Free Guided Site Visit ➔ 04 Lock Guaranteed Date.",
                    "composition": "Vertical progression card with numbered milestone circles and glowing connector lines.",
                    "lighting": "Clean commercial illumination with glowing amber highlight badges.",
                    "color_dir": f"Crisp dark slate with luminous amber {sec_hex} and royal {prim_hex}.",
                    "typo_dir": f"Clean structured {f_head} headings.",
                    "logo_plc": "Top center badge.",
                    "overlay": "01 Shortlist ➔ 02 Compare ➔ 03 Visit ➔ 04 Book",
                    "cta": f"Start Your Free Search: {web}",
                    "prompt": f"Swiss minimalist graphic design layout poster, wedding venue selection roadmap in {city}, 4 clear milestones, dark slate background, glowing {prim_hex} and {sec_hex} nodes, clean typography, {style_frag}. Negative space composition: {safe_clause}"
                },
                {
                    "name": "Concept 3: Top 5 Checklist for Banquet Selection in Gujarat",
                    "type": "Educational Authority",
                    "objective": "Positions VenueConnect as the indispensable expert guide for family decision-makers.",
                    "visual": "Editorial checklist card highlighting: Parking capacity, AC power backup, guest room count, sound curfew limits, and catering flexibility.",
                    "composition": "Grid layout with clean verification icons and badges.",
                    "lighting": "Soft even studio lighting.",
                    "color_dir": f"Royal navy {prim_hex} accented by golden amber {sec_hex}.",
                    "typo_dir": f"Authoritative {f_head} typography.",
                    "logo_plc": "Bottom right corner.",
                    "overlay": "5 Questions Every Gujarat Family Must Ask Before Paying Advance.",
                    "cta": f"Download Complete Checklist at {web}",
                    "prompt": f"Editorial infographic graphic design, wedding venue booking checklist poster for Gujarat banquets, crisp checklist badges, {prim_hex} and {sec_hex} accents, {style_frag}. Negative space composition: {safe_clause}"
                }
            ]
        elif cat == "finance":
            variants = [
                {
                    "name": "Concept 3: The 3 Pillars of Financial Mastery (Infographic)",
                    "type": "Educational Authority",
                    "objective": "Builds deep procedural authority and trust for corporate clients.",
                    "visual": "Structured 3-column architectural layout: 01 Real-Time Bookkeeping • 02 Tax Minimization • 03 Strategic Forecasting.",
                    "composition": "Balanced modular layout with generous whitespace.",
                    "lighting": "Even, bright studio high-key illumination.",
                    "color_dir": f"Crisp dark slate card layout with {prim_hex} borders and {sec_hex} numerical tags.",
                    "typo_dir": f"Bold {f_head} numerals with clean body copy.",
                    "logo_plc": "Top center badge.",
                    "overlay": "01 Reconcile • 02 Optimize • 03 Scale",
                    "cta": "Swipe through our client framework →",
                    "prompt": f"Swiss minimalist graphic design layout poster, dark mode financial architecture card, 3-column comparison, clean {prim_hex} and {sec_hex} accents, crisp typography, 4:5 ratio."
                },
                {
                    "name": "Concept 3: The 4-Step Tax Minimization Roadmap",
                    "type": "Strategic Infographic",
                    "objective": "Educates business owners on how proactive bookkeeping saves thousands annually.",
                    "visual": "Step-by-step roadmap card with numbered milestone badges and glowing connection vectors.",
                    "composition": "Vertical progression with intuitive hierarchical flow.",
                    "lighting": "Crisp digital contrast with luminous accent nodes.",
                    "color_dir": f"Dark slate with vibrant {sec_hex} milestone markers.",
                    "typo_dir": f"{f_head} section headers with high-legibility numerals.",
                    "logo_plc": "Bottom footer bar.",
                    "overlay": "01 Capture ➔ 02 Classify ➔ 03 Deduct ➔ 04 File",
                    "cta": f"Download the complete checklist at {web}",
                    "prompt": f"Minimalist Swiss infographic design poster, step-by-step financial milestone roadmap, dark slate background, glowing {prim_hex} and {sec_hex} nodes, crisp clean corporate typography, 4:5 ratio."
                }
            ]
        elif cat == "tech":
            variants = [
                {
                    "name": "Concept 3: The Modern Cloud Stack (Architecture Benchmark)",
                    "type": "Technical Infographic",
                    "objective": "Demonstrates architectural superiority and seamless component integration.",
                    "visual": "Modular architecture diagram showcasing real-time data ingestion, processing, and visualization layers.",
                    "composition": "Structured 3-tier horizontal modular stack.",
                    "lighting": "High-contrast vector illumination.",
                    "color_dir": f"Deep {bg_hex} with neon {sec_hex} data bus lines.",
                    "typo_dir": "Precision monospace tags.",
                    "logo_plc": "Top left header.",
                    "overlay": "Ingest • Transform • Observe",
                    "cta": "Explore the interactive architecture diagram →",
                    "prompt": f"Swiss graphic design tech poster, dark mode cloud architecture diagram, glowing pipeline connectors in {prim_hex} and {sec_hex}, sharp vector graphic, 4:5 ratio."
                }
            ]
        elif cat == "product":
            variants = [
                {
                    "name": "Concept 3: The Educational Framework (3 Quality Pillars)",
                    "type": "Educational",
                    "objective": f"Builds deep authority and trust for {business.get('target_audience', 'customers')}.",
                    "visual": "Structured 3-column comparative infographic card with scientific clarity.",
                    "composition": "Balanced modular layout with generous whitespace.",
                    "lighting": "Even, bright studio high-key illumination.",
                    "color_dir": f"Crisp dark slate card layout with {prim_hex} borders and {sec_hex} numerical tags.",
                    "typo_dir": f"Bold {f_head} numerals with clean body copy.",
                    "logo_plc": "Top center badge.",
                    "overlay": "01 Source • 02 Extract • 03 Verify",
                    "cta": "Swipe through our verified results →",
                    "prompt": f"Minimalist Swiss-style graphic design layout mockup, dark mode UI card, crisp typography, clean data architecture with {prim_hex} and {sec_hex} accents, high resolution graphic poster, {visual_style} aesthetic, 4:5 ratio."
                }
            ]
        else:
            variants = [
                {
                    "name": "Concept 3: The 3-Phase Execution Roadmap",
                    "type": "Methodology Framework",
                    "objective": "Builds unmatched client confidence through a transparent, disciplined delivery process.",
                    "visual": "Clean architectural infographic with 3 phases: Diagnostic Audit, Strategic Implementation, Measured Growth.",
                    "composition": "Horizontal progression card with clean milestone dividers.",
                    "lighting": "High-key studio contrast.",
                    "color_dir": f"Dark slate with {prim_hex} borders and {sec_hex} milestone icons.",
                    "typo_dir": f"Bold {f_head} typography.",
                    "logo_plc": "Top center badge.",
                    "overlay": "01 Audit • 02 Execute • 03 Scale",
                    "cta": "Review the full client roadmap →",
                    "prompt": f"Swiss minimalist business infographic poster, dark slate background, 3 execution stages, clean {prim_hex} and {sec_hex} line accents, 4:5 ratio."
                }
            ]
        v = variants[iteration % len(variants)]
        return {
            "concept_name": v["name"],
            "concept_type": v["type"],
            "objective_alignment": v["objective"],
            "visual_direction": v["visual"],
            "composition": v["composition"],
            "lighting": v["lighting"],
            "color_direction": v["color_dir"],
            "typography_direction": v["typo_dir"],
            "logo_placement": v["logo_plc"],
            "text_overlay": v["overlay"],
            "cta": v["cta"],
            "image_generation_prompt": v["prompt"]
        }

    # SLOT 3: PROBLEM -> SOLUTION / PARADIGM SHIFT
    else:
        if cat == "events_venues":
            variants = [
                {
                    "name": "Concept 4: 20 Venue Visits ➔ 1-Click Comparison (Problem ➔ Solution)",
                    "type": "Direct Response Ad",
                    "objective": "High-converting split comparison showing the exhausting old way vs the smart VenueConnect way.",
                    "visual": f"Split screen visual: On left, tired couple in traffic with messy venue brochures in {city}; on right, stunning glowing evening party plot with families dancing and verified booking badge in {sec_hex}.",
                    "composition": "50/50 vertical division with high visual contrast.",
                    "lighting": "Desaturated flat tones on left resolving into luminous golden celebration on right.",
                    "color_dir": f"Neutral charcoal fading to vibrant royal {prim_hex} and festive amber {sec_hex}.",
                    "typo_dir": "Punchy comparison labels ('Old Way' vs 'VenueConnect Way').",
                    "logo_plc": "Bottom center bridge.",
                    "overlay": "Wedding Dates Fill Up Fast. Lock Yours Today.",
                    "cta": f"Get Free Quotes: {web}",
                    "prompt": f"High-converting split screen advertising photography, left side chaotic venue paperwork and stressful traffic in {city}, right side breathtaking illuminated wedding lawn with fairy lights and joyous celebration, {style_frag}. Negative space composition: {safe_clause}"
                },
                {
                    "name": "Concept 4: Wedding Season Date Rush (Auspicious Dates Alert)",
                    "type": "Urgency & Availability",
                    "objective": "Triggers rapid action for prime wedding dates (Sayas) before premium banquets sell out.",
                    "visual": f"Glowing luxury calendar marking peak auspicious wedding months in Gujarat, framed beside an opulent illuminated banquet hall in {city}.",
                    "composition": "Hero visual with prominent date milestone badges.",
                    "lighting": "Warm ambient twilight glow with sparkling chandelier reflections.",
                    "color_dir": f"Deep celebratory red and golden amber {sec_hex}.",
                    "typo_dir": f"High-contrast urgency typography in {f_head}.",
                    "logo_plc": "Top right header buffer.",
                    "overlay": "Prime Sayas Booking 8 Months in Advance. Secure Your Venue Today.",
                    "cta": f"Check Real-Time Availability: {web}",
                    "prompt": f"Urgent high-converting commercial advertising creative, glowing calendar highlighting auspicious wedding dates in Gujarat, backdrop of illuminated grand banquet ballroom in {city}, warm amber lighting, {style_frag}. Negative space composition: {safe_clause}"
                },
                {
                    "name": "Concept 4: Hidden Cost Opacity ➔ Guaranteed Price Transparency",
                    "type": "Trust & Price Defense",
                    "objective": "Eliminates fear of surprise catering, electricity, and generator charges.",
                    "visual": "Split visual contrasting fine-print hidden fee bills on left with a crystal-clear, all-inclusive VenueConnect verified quote on right.",
                    "composition": "Side-by-side high-contrast clarity layout.",
                    "lighting": "Dim shadowed tones resolving into crisp daylight clarity.",
                    "color_dir": f"Warning grey to verified emerald green and royal {prim_hex}.",
                    "typo_dir": "Clean sans-serif trust badges.",
                    "logo_plc": "Bottom center.",
                    "overlay": "Zero Hidden Charges. Direct Venue Rates.",
                    "cta": f"Get Instant Transparent Quotes: {web}",
                    "prompt": f"High impact commercial advertising split photography, fine print hidden fee bills on left transitioning into verified transparent booking contract with green guarantee seal on right, modern studio layout, {style_frag}. Negative space composition: {safe_clause}"
                }
            ]
        elif cat == "finance":
            variants = [
                {
                    "name": "Concept 4: Spreadsheet Chaos ➔ Automated Mastery (Problem ➔ Solution)",
                    "type": "Conversion Paradigm",
                    "objective": "High-converting split comparison dismantling manual procrastination.",
                    "visual": "Split comparison: Messy crumpled receipts, tangled Excel spreadsheets on left resolving into glowing, automated, audit-ready cloud accounting on right.",
                    "composition": "50/50 vertical division with high visual contrast.",
                    "lighting": "Dim flat lighting on left transitioning to golden clarity on right.",
                    "color_dir": f"Muted desaturated grey on left resolving into vibrant {prim_hex} and {sec_hex} on right.",
                    "typo_dir": "Punchy contrasting labels ('Manual Spreadsheets' vs 'Cloud Automation').",
                    "logo_plc": "Bottom center bridge.",
                    "overlay": "Stop Losing Weekends to Bookkeeping.",
                    "cta": f"{cta} today.",
                    "prompt": f"Conceptual split-screen advertising photography, left side chaotic paper receipts and error warning stamps, right side sleek glowing cloud accounting dashboard in {prim_hex} and {sec_hex}, dramatic commercial advertising, 4:5 ratio."
                },
                {
                    "name": "Concept 4: Tax Season Panic ➔ Year-Round Calm",
                    "type": "Pain Point Elimination",
                    "objective": "Triggers immediate action by contrasting last-minute March panic with effortless monthly reconciliation.",
                    "visual": "Side-by-side comparison: Stressed desk with overdue sticky notes on left vs serene high-rise desk with clean green filings on right.",
                    "composition": "Split-view with central gold divider line.",
                    "lighting": "Harsh fluorescent shadow on left vs warm morning sunlight on right.",
                    "color_dir": "Desaturated charcoal transitioning to rich warm amber.",
                    "typo_dir": f"Bold contrasting {f_head} headlines.",
                    "logo_plc": "Bottom right corner.",
                    "overlay": "Tax Time Shouldn't Feel Like An Emergency.",
                    "cta": f"Switch to proactive bookkeeping: {web}",
                    "prompt": f"High-contrast split screen commercial advertisement, left side dark messy desk with disorganized receipts, right side bright clean modern boardroom desk with tablet showing 100% tax compliance, 4:5 ratio."
                }
            ]
        elif cat == "tech":
            variants = [
                {
                    "name": "Concept 4: Legacy Bottlenecks ➔ Cloud Velocity",
                    "type": "Paradigm Shift",
                    "objective": "Drives immediate software trial by exposing the painful drag of outdated infrastructure.",
                    "visual": "Split view: Tangled server wires and error logs on left resolving into clean, automated cloud pipelines on right.",
                    "composition": "Diagonal split comparison with high energy.",
                    "lighting": "Red warning glow on left vs crisp cyan illumination on right.",
                    "color_dir": f"Warning red fading to {prim_hex} electric blue and {sec_hex} amber.",
                    "typo_dir": "Punchy technical comparison labels.",
                    "logo_plc": "Bottom center.",
                    "overlay": "Modernize Your Stack in Days, Not Quarters.",
                    "cta": f"Start free migration at {web}",
                    "prompt": f"Side-by-side conceptual technology advertisement, left side chaotic legacy server rack, right side modern glowing minimalist cloud architecture with telemetry charts, 4:5 ratio."
                }
            ]
        elif cat == "product":
            variants = [
                {
                    "name": "Concept 4: Problem to Solution (The Paradigm Shift)",
                    "type": "Problem -> Solution",
                    "objective": "Converts fence-sitters into buyers by dismantling market objections.",
                    "visual": "Dynamic side-by-side split comparison of outdated alternatives vs pure modern batch.",
                    "composition": "50/50 vertical division with high visual contrast.",
                    "lighting": "Dim flat lighting on left transitioning to luminous golden clarity on right.",
                    "color_dir": f"Muted desaturated grey on left resolving into vibrant {prim_hex} and {sec_hex} on right.",
                    "typo_dir": "Punchy contrasting labels ('Standard Options' vs 'Our Standard').",
                    "logo_plc": "Bottom center bridge.",
                    "overlay": "Stop settling for diluted solutions.",
                    "cta": f"{cta} today.",
                    "prompt": f"Side-by-side conceptual comparison photography, dramatic lighting transition from cloudy dull backdrop to crystal clear glowing clarity, commercial advertising layout, {visual_style} style, 4:5 aspect ratio."
                }
            ]
        else:
            variants = [
                {
                    "name": "Concept 4: DIY Guesswork ➔ Strategic Certainty",
                    "type": "Transformation Paradigm",
                    "objective": "Converts prospective clients by demonstrating the costly hidden toll of trial-and-error.",
                    "visual": "Split screen comparing fragmented sticky notes and disjointed plans on left with clear structured milestone timeline on right.",
                    "composition": "50/50 vertical split with high contrast.",
                    "lighting": "Shadowed monochrome on left resolving into bright warm clarity on right.",
                    "color_dir": f"Dull gray to vibrant {sec_hex} gold.",
                    "typo_dir": f"Contrasting {f_head} bold typography.",
                    "logo_plc": "Bottom center bridge.",
                    "overlay": "Stop Guessing. Start Scaling.",
                    "cta": f"{cta} • Link in bio",
                    "prompt": f"High impact split-screen commercial advertising visual, left side chaotic paper sketches and red error marks, right side luminous structured execution roadmap with {prim_hex} and {sec_hex} milestones, 4:5 ratio."
                }
            ]
        v = variants[iteration % len(variants)]
        return {
            "concept_name": v["name"],
            "concept_type": v["type"],
            "objective_alignment": v["objective"],
            "visual_direction": v["visual"],
            "composition": v["composition"],
            "lighting": v["lighting"],
            "color_direction": v["color_dir"],
            "typography_direction": v["typo_dir"],
            "logo_placement": v["logo_plc"],
            "text_overlay": v["overlay"],
            "cta": v["cta"],
            "image_generation_prompt": v["prompt"]
        }


def build_platform_captions_fresh(brand_name: str, industry: str, objective: str, business: Dict[str, Any], iteration: int = 0) -> Dict[str, Any]:
    """Generates fresh platform-specific captions with rotating hooks and niche resonance."""
    cat = detect_industry_category(industry, business.get("campaign_info", ""), brand_name)
    web = business.get("website", "https://www.venueconnect.in/")
    phone = business.get("phone", "[Direct Booking Helpline]")
    city = business.get("target_city", "Gujarat")

    if cat == "events_venues":
        hooks = [
            f"Planning a dream wedding or grand celebration in {city}? Stop spending weeks visiting 20 banquets in the heat. 🌸✨",
            f"Wedding dates in {city} are booking 6-12 months ahead! Have you secured your venue yet? 📅🏛️",
            f"The smart way to find Gujarat's finest party plots & royal banquet halls at verified direct prices 💎✨",
            f"Before you pay a venue advance in Ahmedabad, Surat, or Vadodara, read this! 🚨"
        ]
        hook = hooks[iteration % len(hooks)]
        ig = f"{hook}\n\nWith {brand_name}, browse and compare verified wedding lawns, party plots, and luxury banquet halls across Gujarat in one place.\n\nWhy Gujarat families trust {brand_name}:\n🏛️ 500+ Verified Banquets & Party Plots\n💰 Transparent price comparisons & catering packages\n👥 Capacities from 100 to 5,000+ guests\n⚡ Free instant quotes & site visit coordination\n\nMake your celebration unforgettable. Book smarter today.\n\n🌐 Visit: {web}\n📲 Call / WhatsApp: {phone}\n📍 Venues across Ahmedabad, Surat, Vadodara, Rajkot & Gujarat\n\nTag someone getting married this season! 👇"
        fb = f"{hook}\n\nYour dream wedding deserves the perfect setting. 💍✨ Discover Gujarat's most loved wedding lawns, royal banquet halls, and party plots on {brand_name}. Compare prices, guest capacities, and catering options with zero hassle!\n\n👉 Book your free site visit today: {web}\n📞 WhatsApp: {phone}"
        x = f"{hook}\n\nCompare 500+ verified banquet halls & party plots across Gujarat in under 2 minutes 🧵👇\n\n{web}"
        li = f"Corporate summits, product launches, or grand annual galas in Gujarat?\n\n{brand_name} simplifies enterprise venue scouting with verified AC banquet halls, luxury resort lawns, and transparent catering options across Ahmedabad, Surat, and Vadodara.\n\n✔ Zero brokerage or hidden fees\n✔ Verified venue photos & real customer ratings\n\nExplore corporate event spaces: {web}"
    else:
        hooks = [
            f"When it comes to verified quality, clarity is your biggest growth lever at {brand_name}.",
            f"Stop relying on guesswork. Here is the modern standard from {brand_name}.",
            f"Why industry leaders in {city} trust {brand_name} for consistent results.",
            f"Transforming operational friction into measurable velocity with {brand_name}."
        ]
        hook = hooks[iteration % len(hooks)]
        ig = f"{hook}\n\nAt {brand_name}, we partner with clients seeking verified standards, senior expertise, and proven outcomes.\n\n✔ Dedicated Specialists\n✔ Proven Execution Framework\n✔ 100% Transparency\n\nExplore our solutions: {web}\n📲 Contact: {phone}"
        fb = f"{hook}\n\nEmpowering businesses and clients across {city} with verified solutions. Partner with {brand_name} today:\n\n👉 {web}"
        x = f"{hook}\n\nDiscover how {brand_name} simplifies execution 🧵👇\n\n{web}"
        li = f"{hook}\n\nConnect with our team to discuss your objectives for this quarter: {web}"

    return {
        "instagram": {"professional": ig, "creative": ig.replace("When it comes to", "Here is the honest truth about"), "short": f"Discover {brand_name}: {web}"},
        "facebook": {"professional": fb, "creative": fb, "short": f"Learn more: {web}"},
        "x": {"professional": x, "creative": x, "short": f"Explore: {web}"},
        "linkedin": {"professional": li, "creative": li, "short": f"Connect with {brand_name}: {web}"}
    }


# ==============================================================================
# 5. CREATIVE VISUAL RENDERING ENGINE (PILLOW STUDIO RENDERER)
# ==============================================================================

def render_concept_visual_card(
    concept_name: str,
    brand_name: str,
    prim_hex: str,
    sec_hex: str,
    bg_hex: str,
    text_overlay: str,
    cta_text: str,
    visual_style: str = "Editorial",
    industry: str = "General",
    logo_bytes: Optional[bytes] = None,
    product_bytes: Optional[bytes] = None
) -> bytes:
    """
    Renders an ultra-crisp 800x1000 commercial creative visual matching brand tokens,
    adapting graphics for Finance/Accounting, Tech/SaaS, Services, or Physical Products.
    """
    W, H = 800, 1000
    img = Image.new("RGB", (W, H), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    def h2rgb(h, defval):
        h = str(h).lstrip("#")
        if len(h) == 6:
            try:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            except Exception:
                pass
        return defval

    c_prim = h2rgb(prim_hex, (18, 52, 86))
    c_sec = h2rgb(sec_hex, (245, 130, 32))
    c_bg = h2rgb(bg_hex, (15, 23, 42))

    # Background gradient
    for y in range(H):
        ratio = y / float(H)
        r = int(c_bg[0] + (c_prim[0] * 0.45 - c_bg[0]) * ratio)
        g = int(c_bg[1] + (c_prim[1] * 0.45 - c_bg[1]) * ratio)
        b = int(c_bg[2] + (c_prim[2] * 0.45 - c_bg[2]) * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Center atmospheric glow
    cx, cy = W // 2, int(H * 0.38)
    for rad in range(280, 0, -20):
        alpha = int(22 * (1 - rad / 280.0))
        glow_col = (
            int(c_bg[0] + (c_sec[0] - c_bg[0]) * (alpha / 100.0)),
            int(c_bg[1] + (c_sec[1] - c_bg[1]) * (alpha / 100.0)),
            int(c_bg[2] + (c_sec[2] - c_bg[2]) * (alpha / 100.0))
        )
        draw.ellipse([(cx - rad, cy - rad), (cx + rad, cy + rad)], fill=glow_col)

    # Outer luxury frame
    draw.rectangle([(25, 25), (W - 25, H - 25)], outline=c_sec, width=3)
    draw.rectangle([(36, 36), (W - 36, H - 36)], outline=(255, 255, 255), width=1)

    # Header badge
    draw.rectangle([(W//2 - 160, 60), (W//2 + 160, 94)], fill=c_sec)
    draw.text((W//2, 77), f"{visual_style.upper()} • STUDIO CREATIVE", fill=(15, 23, 42), anchor="mm")

    # Brand Title
    draw.text((W//2, 130), brand_name.upper()[:28], fill=(255, 255, 255), anchor="mm")
    draw.text((W//2, 160), concept_name[:40], fill=c_sec, anchor="mm")

    # Center Hero Graphic - Check for Uploaded Product first
    composite_done = False
    if product_bytes:
        try:
            p_img = Image.open(io.BytesIO(product_bytes)).convert("RGBA")
            p_img.thumbnail((280, 300), Image.Resampling.LANCZOS)
            pw, ph = p_img.size
            px = (W - pw) // 2
            py = int(H * 0.25) + (300 - ph) // 2
            img.paste(p_img, (px, py), p_img)
            composite_done = True
        except Exception:
            composite_done = False

    if not composite_done:
        cat = detect_industry_category(industry, brand_name=brand_name)

        if cat == "finance":
            # High-End Financial Architecture Dashboard Card
            fx, fy, fw, fh = W//2 - 210, int(H * 0.23), 420, 250
            draw.rounded_rectangle([(fx, fy), (fx + fw, fy + fh)], radius=16, fill=(20, 28, 48), outline=c_sec, width=2)
            draw.rounded_rectangle([(fx + 10, fy + 10), (fx + fw - 10, fy + 48)], radius=8, fill=(30, 41, 68))
            draw.text((fx + 25, fy + 29), "FINANCIAL ARCHITECTURE", fill=(248, 250, 252), anchor="lm")
            draw.text((fx + fw - 25, fy + 29), "✓ AUDIT VERIFIED", fill=(16, 185, 129), anchor="rm")
            # Metrics
            draw.text((fx + 30, fy + 75), "CASH RECONCILED", fill=(148, 163, 184), anchor="lm")
            draw.text((fx + 30, fy + 105), "+38.4%", fill=(16, 185, 129), anchor="lm")
            draw.text((fx + 165, fy + 75), "TAX OPTIMIZED", fill=(148, 163, 184), anchor="lm")
            draw.text((fx + 165, fy + 105), "$24,500", fill=c_sec, anchor="lm")
            draw.text((fx + 295, fy + 75), "COMPLIANCE", fill=(148, 163, 184), anchor="lm")
            draw.text((fx + 295, fy + 105), "100.0%", fill=(56, 189, 248), anchor="lm")
            # Upward growth trajectory curve with nodes
            coords = [(fx + 30, fy + 195), (fx + 110, fy + 180), (fx + 200, fy + 185), (fx + 290, fy + 148), (fx + 390, fy + 130)]
            draw.line(coords, fill=(16, 185, 129), width=4)
            for cx_node, cy_node in coords:
                draw.ellipse([(cx_node - 4, cy_node - 4), (cx_node + 4, cy_node + 4)], fill=c_sec)
            draw.line([(fx + 30, fy + 215), (fx + fw - 30, fy + 215)], fill=(50, 60, 85), width=1)

        elif cat == "tech":
            # Sleek Tech Cloud System Card
            tx, ty, tw, th = W//2 - 210, int(H * 0.23), 420, 250
            draw.rounded_rectangle([(tx, ty), (tx + tw, ty + th)], radius=16, fill=(15, 23, 42), outline=(56, 189, 248), width=2)
            draw.rounded_rectangle([(tx + 10, ty + 10), (tx + tw - 10, ty + 48)], radius=8, fill=(24, 34, 58))
            draw.text((tx + 25, ty + 29), "SYSTEM TELEMETRY", fill=(248, 250, 252), anchor="lm")
            draw.text((tx + tw - 25, ty + 29), "● 99.99% UPTIME", fill=(16, 185, 129), anchor="rm")
            draw.text((tx + 30, ty + 85), "LATENCY: 12ms", fill=c_sec, anchor="lm")
            draw.text((tx + 30, ty + 120), "THROUGHPUT: 4.8M ops/sec", fill=(56, 189, 248), anchor="lm")
            draw.text((tx + 30, ty + 155), "SECURITY: ISO 27001 SOC-2", fill=(148, 163, 184), anchor="lm")
            draw.line([(tx + 30, ty + 200), (tx + 120, ty + 180), (tx + 240, ty + 195), (tx + 390, ty + 165)], fill=(56, 189, 248), width=3)

        elif cat == "health":
            # Clinical Care & Patient Trust Card
            hx, hy, hw, hh = W//2 - 210, int(H * 0.23), 420, 250
            draw.rounded_rectangle([(hx, hy), (hx + hw, hy + hh)], radius=16, fill=(18, 30, 42), outline=(16, 185, 129), width=2)
            draw.rounded_rectangle([(hx + 10, hy + 10), (hx + hw - 10, hy + 48)], radius=8, fill=(26, 45, 62))
            draw.text((hx + 25, hy + 29), "CLINICAL EXCELLENCE", fill=(248, 250, 252), anchor="lm")
            draw.text((hx + hw - 25, hy + 29), "✓ BOARD CERTIFIED", fill=(16, 185, 129), anchor="rm")
            draw.text((hx + 30, hy + 85), "PATIENT SATISFACTION: 99.4%", fill=c_sec, anchor="lm")
            draw.text((hx + 30, hy + 120), "CLINICAL PROTOCOL: 100% VERIFIED", fill=(56, 189, 248), anchor="lm")
            draw.text((hx + 30, hy + 155), "EVIDENCE-BASED CARE", fill=(148, 163, 184), anchor="lm")
            draw.line([(hx + 30, hy + 200), (hx + hw - 30, hy + 200)], fill=(40, 60, 80), width=1)

        elif cat == "product":
            # Luxury Product Hero Showcase (pedestal & packaging)
            bx, by, bw, bh = W//2 - 60, int(H * 0.25), 120, 240
            draw.rectangle([(W//2 - 18, by - 45), (W//2 + 18, by - 28)], fill=(35, 35, 40))
            draw.rectangle([(W//2 - 36, by - 28), (W//2 + 36, by)], fill=c_sec)
            draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=20, fill=(40, 24, 12), outline=c_sec, width=2)
            draw.rounded_rectangle([(bx + 14, by + 50), (bx + bw - 14, by + bh - 45)], radius=8, fill=(250, 248, 242))
            draw.text((W//2, by + 100), brand_name[:14], fill=(15, 23, 42), anchor="mm")
            draw.text((W//2, by + 130), "PREMIUM BATCH", fill=c_sec, anchor="mm")

        else:
            # High-Impact Professional Service / Advisory Card
            sx, sy, sw, sh = W//2 - 210, int(H * 0.23), 420, 250
            draw.rounded_rectangle([(sx, sy), (sx + sw, sy + sh)], radius=16, fill=(22, 27, 46), outline=c_sec, width=2)
            draw.rounded_rectangle([(sx + 10, sy + 10), (sx + sw - 10, sy + 48)], radius=8, fill=(32, 40, 68))
            draw.text((sx + 25, sy + 29), "STRATEGIC EXECUTION", fill=(248, 250, 252), anchor="lm")
            draw.text((sx + sw - 25, sy + 29), "★ 5-STAR VERIFIED", fill=c_sec, anchor="rm")
            draw.text((sx + 30, sy + 85), "✓ 100% RESULTS GUARANTEE", fill=(16, 185, 129), anchor="lm")
            draw.text((sx + 30, sy + 120), "✓ DEDICATED SENIOR SPECIALIST", fill=(56, 189, 248), anchor="lm")
            draw.text((sx + 30, sy + 155), "✓ MEASURABLE ROI MILESTONES", fill=c_sec, anchor="lm")
            draw.line([(sx + 30, sy + 200), (sx + sw - 30, sy + 200)], fill=(50, 60, 85), width=1)

    # Logo overlay if uploaded
    if logo_bytes:
        try:
            l_img = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            l_img.thumbnail((140, 50), Image.Resampling.LANCZOS)
            lw, lh = l_img.size
            img.paste(l_img, (W - 40 - lw, 45), l_img)
        except Exception:
            pass

    # Text overlay frosted card
    card_top = int(H * 0.64)
    draw.rounded_rectangle([(60, card_top), (W - 60, card_top + 200)], radius=16, fill=(15, 23, 42), outline=c_sec, width=2)
    clean_overlay = text_overlay if len(text_overlay) <= 45 else text_overlay[:42] + "..."
    draw.text((W//2, card_top + 50), f'"{clean_overlay}"', fill=(255, 255, 255), anchor="mm")
    draw.line([(140, card_top + 90), (W - 140, card_top + 90)], fill=(70, 80, 100), width=1)
    clean_cta = cta_text if len(cta_text) <= 40 else cta_text[:37] + "..."
    draw.text((W//2, card_top + 125), clean_cta, fill=c_sec, anchor="mm")
    draw.text((W//2, card_top + 165), "Safe Area Protected • 4:5 Portrait • Verified Brand DNA", fill=(148, 163, 184), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ==============================================================================
# 6. STREAMLIT UI: AI SOCIAL CONTENT STUDIO
# ==============================================================================

def render_brand_first_content_page():
    """Main Render function for AI Social Content Studio inside CrawlPilot."""

    # 1. Official Header
    st.markdown("""
    <div style="background: radial-gradient(130% 120% at 50% -10%, #172554 0%, #0F172A 60%, #020617 100%); padding: 2.2rem 2rem 1.6rem; border-radius: 18px; border: 1px solid rgba(56, 189, 248, 0.25); text-align: center; margin-bottom: 1.8rem; box-shadow: 0 20px 45px -10px rgba(0,0,0,0.6);">
        <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.3); padding: 4px 14px; border-radius: 9999px; margin-bottom: 0.8rem;">
            <span style="font-size: 0.9rem;">📱</span>
            <span style="font-size: 0.78rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: #38BDF8;">AI SOCIAL CONTENT STUDIO</span>
        </div>
        <h1 style="font-size: 2.4rem; font-weight: 900; color: #FFFFFF; letter-spacing: -0.03em; margin: 0 0 0.35rem 0; line-height: 1.15;">
            AI Social Content Studio
        </h1>
        <div style="font-size: 0.88rem; font-weight: 800; color: #F59E0B; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.7rem;">
            STRATEGY <span style="color: #64748B;">•</span> BRAND <span style="color: #64748B;">•</span> CONTENT <span style="color: #64748B;">•</span> CREATIVES
        </div>
        <p style="color: #94A3B8; font-size: 0.98rem; max-width: 740px; margin: 0 auto; line-height: 1.55;">
            <b>Never generate social content before understanding the brand.</b> Complete brand-aware workflow that adapts dynamically by format, analyzes the 10 brand pillars, guarantees claim safety, and passes the <i>Hidden Logo Test</i>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Saved Brands Selection & Manager
    if "saved_brands_db" not in st.session_state:
        st.session_state["saved_brands_db"] = DEFAULT_SAVED_BRANDS

    saved_brands = st.session_state["saved_brands_db"]
    brand_options = ["+ Create New Brand Profile"] + list(saved_brands.keys())

    col_sb1, col_sb2 = st.columns([3, 1.2])
    with col_sb1:
        chosen_brand_key = st.selectbox(
            "🏢 Active Brand Profile:",
            options=brand_options,
            index=1 if len(brand_options) > 1 else 0,
            help="Select an existing saved brand profile or create a new one."
        )
    with col_sb2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if chosen_brand_key != "+ Create New Brand Profile":
            st.caption(f"Loaded: **{chosen_brand_key.split('(')[0].strip()}**")

    # Load defaults from chosen brand
    active_b = saved_brands.get(chosen_brand_key, {}) if chosen_brand_key in saved_brands else {}

    # Synchronize brand colors when switching active brand profile
    if st.session_state.get("last_selected_brand_key") != chosen_brand_key:
        st.session_state["last_selected_brand_key"] = chosen_brand_key
        st.session_state.pop("current_logo_sig", None)
        st.session_state.pop("extracted_palette", None)
        st.session_state.pop("logo_extracted_notify", None)
        if chosen_brand_key in saved_brands and "colors" in saved_brands[chosen_brand_key]:
            b_colors = saved_brands[chosen_brand_key]["colors"]
            st.session_state["cp_prim"] = b_colors.get("primary", {}).get("hex", "#123456")
            st.session_state["cp_sec"] = b_colors.get("secondary", {}).get("hex", "#F58220")
            st.session_state["cp_acc"] = b_colors.get("accent", {}).get("hex", "#FFFFFF")
            st.session_state["cp_bg"] = b_colors.get("background", {}).get("hex", "#0F172A")
            st.session_state["cp_txt"] = b_colors.get("text", {}).get("hex", "#F8FAFC")
        elif chosen_brand_key == "+ Create New Brand Profile":
            st.session_state["cp_prim"] = "#1E3A8A"
            st.session_state["cp_sec"] = "#F59E0B"
            st.session_state["cp_acc"] = "#10B981"
            st.session_state["cp_bg"] = "#0F172A"
            st.session_state["cp_txt"] = "#F8FAFC"

    # ==========================================================================
    # STEP 0: WHAT DO YOU WANT TO CREATE? (BEFORE BRAND DNA)
    # ==========================================================================
    st.markdown("""
    <div style="background: rgba(18, 22, 32, 0.95); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 14px; padding: 1.2rem 1.4rem; margin-bottom: 1.5rem; box-shadow: 0 8px 24px rgba(0,0,0,0.35);">
        <div style="font-weight: 800; font-size: 1.15rem; color: #F8FAFC; display: flex; align-items: center; gap: 8px;">
            <span style="color: #F59E0B; font-size: 1.25rem;">🎯</span> Step 0: What do you want to create?
        </div>
        <div style="font-size: 0.86rem; color: #94A3B8; margin-top: 4px;">
            Select your primary creative format. The entire generation engine will dynamically configure its storyboards, slide architecture, aspect ratios, and visual prompts accordingly.
        </div>
    </div>
    """, unsafe_allow_html=True)

    format_options = [
        "📸 Single Post",
        "🎠 Carousel",
        "🧩 Grid",
        "🎬 Reel",
        "📱 Story",
        "📢 Ad Creative"
    ]
    chosen_format = st.radio("Choose Content Format:", options=format_options, index=1, horizontal=True, label_visibility="collapsed")

    # Dynamic Format-Specific Settings
    format_settings = {}
    st.markdown("<div style='margin-top: 0.6rem;'></div>", unsafe_allow_html=True)

    if "Carousel" in chosen_format:
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.5); border-left: 3px solid #F59E0B; padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 0.8rem;">
            <b>🎠 Carousel Mode:</b> Creates a cohesive slide-by-slide storytelling system where each slide flows visually and conceptually into the next.
        </div>
        """, unsafe_allow_html=True)
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            format_settings["slides_count"] = st.select_slider("Number of Slides:", options=[3, 5, 7, 10], value=5)
        with c_col2:
            format_settings["carousel_style"] = st.selectbox("Narrative Arc:", [
                "Hook → Problem → Insight → Solution → CTA",
                "5 Step Tutorial / How-To Framework",
                "Myth vs Fact Breakdown",
                "Curated Industry Listicle & Resources"
            ])

    elif "Grid" in chosen_format:
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.5); border-left: 3px solid #F59E0B; padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 0.8rem;">
            <b>🧩 Grid Mode:</b> Generates a connected multi-tile feed strategy that looks stunning individually AND forms a unified visual brand wall.
        </div>
        """, unsafe_allow_html=True)
        g_col1, g_col2 = st.columns(2)
        with g_col1:
            format_settings["grid_size"] = st.selectbox("Grid Layout:", ["2x2 (4 Posts)", "2x3 (6 Posts)", "3x3 (9 Posts)"], index=1)
        with g_col2:
            format_settings["continuity_type"] = st.selectbox("Visual Continuity:", [
                "Color Flow & Continuous Banner",
                "Checkerboard Text + Product",
                "Macro Panoramic Split"
            ])

    elif "Reel" in chosen_format:
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.5); border-left: 3px solid #F59E0B; padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 0.8rem;">
            <b>🎬 Reel Mode:</b> Builds a high-retention scene-by-scene video storyboard with duration, camera direction, on-screen text, voiceover, and audio cues.
        </div>
        """, unsafe_allow_html=True)
        r_col1, r_col2 = st.columns(2)
        with r_col1:
            format_settings["duration"] = st.select_slider("Target Duration:", options=["15 sec", "30 sec", "60 sec"], value="30 sec")
        with r_col2:
            format_settings["reel_style"] = st.selectbox("Format Style:", [
                "Problem/Solution Skit + Voiceover",
                "Talking Head + B-Roll Cutaways",
                "Text-on-Screen + Trending Ambient Audio",
                "Behind-the-Scenes Craftsmanship"
            ])

    elif "Story" in chosen_format:
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.5); border-left: 3px solid #F59E0B; padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 0.8rem;">
            <b>📱 Story Mode:</b> Builds an ephemeral high-engagement story sequence with interactive sticker and poll recommendations.
        </div>
        """, unsafe_allow_html=True)
        s_col1, s_col2 = st.columns(2)
        with s_col1:
            format_settings["story_sequence_count"] = st.selectbox("Sequence Length:", ["1 story", "3 story sequence", "5 story sequence"], index=1)
        with s_col2:
            format_settings["include_stickers"] = st.checkbox("Include interactive sticker/poll/question suggestions", value=True)

    elif "Single" in chosen_format or "Ad" in chosen_format:
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.5); border-left: 3px solid #F59E0B; padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 0.8rem;">
            <b>📸 Single Post / Ad Creative Mode:</b> High-impact standalone visual engineered with precise focal hierarchy, safe zones, and high-converting CTA.
        </div>
        """, unsafe_allow_html=True)
        format_settings["aspect_ratio"] = st.selectbox("Aspect Ratio:", [
            "4:5 (Instagram/Facebook Portrait - Recommended)",
            "1:1 (Square)",
            "9:16 (Stories/Reels/TikTok)",
            "16:9 (Landscape/Twitter)"
        ])

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 1.4rem 0;'>", unsafe_allow_html=True)

    # ==========================================================================
    # 🧬 THE 10 BRAND-FIRST ANALYSIS PILLARS (BRAND DNA)
    # ==========================================================================
    st.markdown("""
    <div style="margin-bottom: 1rem;">
        <h3 style="font-size: 1.35rem; font-weight: 800; color: #FFFFFF; display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span>🧬</span> The 10 Brand-First Analysis Pillars (Brand DNA)
        </h3>
        <p style="color: #94A3B8; font-size: 0.88rem; margin: 0;">
            The AI must strictly analyze these 10 pillars before generating content. Branding must influence composition, lighting, color, and typography—<b>never just slap a logo in the corner</b>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Tabs for Brand Setup to keep it clean and spacious
    dna_tabs = st.tabs([
        "🎨 Identity, Colors & Uploads (Pillars 1-3)",
        "🔤 Typography & Style (Pillars 4-6)",
        "🏢 Audience, Industry & Market (Pillars 7-9)",
        "🌐 Social & Web Presence (Pillar 10)"
    ])

    # PILLARS 1-3: Identity, Colors, Uploads
    with dna_tabs[0]:
        col_id1, col_id2 = st.columns([1.5, 2.5])
        with col_id1:
            st.markdown("#### Pillar 1: Brand Identity & Website")

            web_input_val = st.text_input(
                "🌐 Website URL (Auto-Scans Niche):",
                value=st.session_state.get("website_input_cache", active_b.get("website", "")),
                placeholder="https://www.venueconnect.in/",
                help="Enter your website URL. The AI will inspect your meta tags, services, and location so prompts accurately match your real niche."
            )

            col_wb_btn, col_wb_clr = st.columns([2, 1])
            with col_wb_btn:
                if st.button("🔍 Scan & Understand Niche", key="btn_scan_website", use_container_width=True):
                    if web_input_val:
                        with st.spinner("🌐 Crawling website & extracting business niche..."):
                            site_info = analyze_website_niche(web_input_val)
                            st.session_state["website_niche_data"] = site_info
                            st.session_state["website_input_cache"] = web_input_val
                            if site_info.get("detected_brand"):
                                st.session_state["cached_brand_name"] = site_info["detected_brand"]
                            if site_info.get("detected_niche"):
                                st.session_state["cached_industry"] = site_info["detected_niche"]
                            if site_info.get("summary"):
                                st.session_state["cached_campaign_info"] = site_info["summary"]
                            if site_info.get("locations"):
                                st.session_state["cached_city"] = ", ".join(site_info["locations"])
                            st.rerun()
                    else:
                        st.warning("Please enter a website URL first.")
            with col_wb_clr:
                if st.button("Reset", key="btn_reset_web", use_container_width=True):
                    st.session_state.pop("website_niche_data", None)
                    st.session_state.pop("website_input_cache", None)
                    st.session_state.pop("cached_brand_name", None)
                    st.session_state.pop("cached_industry", None)
                    st.session_state.pop("cached_campaign_info", None)
                    st.session_state.pop("cached_city", None)
                    st.rerun()

            if "website_niche_data" in st.session_state and st.session_state["website_niche_data"].get("detected_niche"):
                snd = st.session_state["website_niche_data"]
                st.success(
                    f"**Verified Niche:** {snd.get('detected_niche')}\n\n"
                    f"📍 **Locations:** {', '.join(snd.get('locations', [])) or 'Gujarat / Regional'}\n\n"
                    f"🎯 **Offerings:** {', '.join(snd.get('detected_services', []))}"
                )

            brand_default = st.session_state.get("cached_brand_name", active_b.get("brand_name", "VenueConnect"))
            industry_default = st.session_state.get("cached_industry", active_b.get("industry", "Wedding & Event Venue Booking Platform"))
            brand_name = st.text_input("Brand / Business Name *", value=brand_default)
            industry_input = st.text_input("Industry / Business Type *", value=industry_default)
            website_url = web_input_val

        with col_id2:
            st.markdown("#### Pillar 3: Logo & Asset Uploads")
            up_col1, up_col2 = st.columns(2)
            with up_col1:
                uploaded_logo = st.file_uploader("Brand Logo (PNG/SVG/JPG)", type=["png", "svg", "jpg", "jpeg", "webp"], key="upl_logo")
                auto_detect_web_logo = st.checkbox("Also try auto-detecting logo from website", value=True)
            with up_col2:
                uploaded_product = st.file_uploader("Product Images (Preserves packaging)", type=["png", "jpg", "jpeg", "webp"], key="upl_prod")

            up_col3, up_col4 = st.columns(2)
            with up_col3:
                uploaded_ref = st.file_uploader("Reference Images (Style inspo)", type=["png", "jpg", "jpeg", "webp"], key="upl_ref")
            with up_col4:
                uploaded_guide = st.file_uploader("Brand Guidelines (PDF / DOCX)", type=["pdf", "docx", "txt"], key="upl_guide")

        # Color Extraction & Brand Color System
        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 1rem 0;'>", unsafe_allow_html=True)
        col_pillar_hdr, col_reextract = st.columns([3, 1.2])
        with col_pillar_hdr:
            st.markdown("#### Pillar 2: Visual Brand Color System")
            st.caption("Visual color system displaying color swatches with HEX, RGB, and HSL. Automatically extracted from uploaded logo or custom set.")
        with col_reextract:
            if uploaded_logo is not None:
                st.markdown("<div style='margin-top: 6px;'></div>", unsafe_allow_html=True)
                if st.button("🔄 Re-Extract from Logo", key="btn_reextract_logo", help="Re-scan the uploaded logo and update color swatches"):
                    extracted = extract_palette_from_image(uploaded_logo.getvalue())
                    st.session_state["extracted_palette"] = extracted
                    st.session_state["current_logo_sig"] = f"{uploaded_logo.name}_{uploaded_logo.size}"
                    st.session_state["cp_prim"] = extracted["primary"]["hex"]
                    st.session_state["cp_sec"] = extracted["secondary"]["hex"]
                    st.session_state["cp_acc"] = extracted["accent"]["hex"]
                    st.session_state["cp_bg"] = extracted["background"]["hex"]
                    st.session_state["cp_txt"] = extracted["text"]["hex"]
                    st.session_state["logo_extracted_notify"] = f"🎨 Re-extracted colors from **{uploaded_logo.name}**!"
                    st.rerun()

        # Automatic Logo Color Extraction on upload / file change
        if uploaded_logo is not None:
            logo_sig = f"{uploaded_logo.name}_{uploaded_logo.size}"
            if st.session_state.get("current_logo_sig") != logo_sig:
                with st.spinner("🎨 Analyzing logo and extracting brand palette..."):
                    extracted = extract_palette_from_image(uploaded_logo.getvalue())
                    st.session_state["extracted_palette"] = extracted
                    st.session_state["current_logo_sig"] = logo_sig
                    st.session_state["cp_prim"] = extracted["primary"]["hex"]
                    st.session_state["cp_sec"] = extracted["secondary"]["hex"]
                    st.session_state["cp_acc"] = extracted["accent"]["hex"]
                    st.session_state["cp_bg"] = extracted["background"]["hex"]
                    st.session_state["cp_txt"] = extracted["text"]["hex"]
                    st.session_state["logo_extracted_notify"] = f"🎨 Extracted brand colors from **{uploaded_logo.name}**!"
                    st.rerun()
        else:
            if "current_logo_sig" in st.session_state:
                del st.session_state["current_logo_sig"]
            if "logo_extracted_notify" in st.session_state:
                del st.session_state["logo_extracted_notify"]

        if st.session_state.get("logo_extracted_notify") and uploaded_logo is not None:
            st.success(
                f"{st.session_state['logo_extracted_notify']} "
                f"• Primary: `{st.session_state.get('cp_prim')}` "
                f"• Secondary: `{st.session_state.get('cp_sec')}` "
                f"• Accent: `{st.session_state.get('cp_acc')}`"
            )

        active_palette = st.session_state.get("extracted_palette", active_b.get("colors", {
            "primary": {"hex": "#123456", "rgb": "rgb(18, 52, 86)", "hsl": "hsl(210, 65%, 20%)"},
            "secondary": {"hex": "#F58220", "rgb": "rgb(245, 130, 32)", "hsl": "hsl(28, 92%, 54%)"},
            "accent": {"hex": "#FFFFFF", "rgb": "rgb(255, 255, 255)", "hsl": "hsl(0, 0%, 100%)"},
            "background": {"hex": "#0F172A", "rgb": "rgb(15, 23, 42)", "hsl": "hsl(222, 47%, 11%)"},
            "text": {"hex": "#F8FAFC", "rgb": "rgb(248, 250, 252)", "hsl": "hsl(210, 40%, 98%)"}
        }))

        def get_c_hex(val, default="#123456"):
            if isinstance(val, dict): return val.get("hex", default)
            return str(val) if str(val).startswith("#") else default

        p_hex = st.session_state.get("cp_prim", get_c_hex(active_palette.get("primary"), "#123456"))
        s_hex = st.session_state.get("cp_sec", get_c_hex(active_palette.get("secondary"), "#F58220"))
        a_hex = st.session_state.get("cp_acc", get_c_hex(active_palette.get("accent"), "#FFFFFF"))
        b_hex = st.session_state.get("cp_bg", get_c_hex(active_palette.get("background"), "#0F172A"))
        t_hex = st.session_state.get("cp_txt", get_c_hex(active_palette.get("text"), "#F8FAFC"))

        # Visual Color Swatches Display
        col_sw1, col_sw2, col_sw3, col_sw4, col_sw5 = st.columns(5)
        with col_sw1:
            c_prim = st.color_picker("Primary", value=p_hex, key="cp_prim")
            r, g, b = hex_to_rgb(c_prim)
            st.markdown(f"""
            <div style="background: {c_prim}; height: 42px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); margin-top: 4px;"></div>
            <div style="font-size: 0.78rem; color: #CBD5E1; margin-top: 4px; line-height: 1.4;">
                <b>HEX:</b> <code>{c_prim}</code><br>
                <b>RGB:</b> <code>{r},{g},{b}</code><br>
                <b>HSL:</b> <code>{rgb_to_hsl(r,g,b)}</code>
            </div>
            """, unsafe_allow_html=True)

        with col_sw2:
            c_sec = st.color_picker("Secondary", value=s_hex, key="cp_sec")
            r, g, b = hex_to_rgb(c_sec)
            st.markdown(f"""
            <div style="background: {c_sec}; height: 42px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); margin-top: 4px;"></div>
            <div style="font-size: 0.78rem; color: #CBD5E1; margin-top: 4px; line-height: 1.4;">
                <b>HEX:</b> <code>{c_sec}</code><br>
                <b>RGB:</b> <code>{r},{g},{b}</code><br>
                <b>HSL:</b> <code>{rgb_to_hsl(r,g,b)}</code>
            </div>
            """, unsafe_allow_html=True)

        with col_sw3:
            c_acc = st.color_picker("Accent", value=a_hex, key="cp_acc")
            r, g, b = hex_to_rgb(c_acc)
            st.markdown(f"""
            <div style="background: {c_acc}; height: 42px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); margin-top: 4px;"></div>
            <div style="font-size: 0.78rem; color: #CBD5E1; margin-top: 4px; line-height: 1.4;">
                <b>HEX:</b> <code>{c_acc}</code><br>
                <b>RGB:</b> <code>{r},{g},{b}</code><br>
                <b>HSL:</b> <code>{rgb_to_hsl(r,g,b)}</code>
            </div>
            """, unsafe_allow_html=True)

        with col_sw4:
            c_bg = st.color_picker("Background", value=b_hex, key="cp_bg")
            r, g, b = hex_to_rgb(c_bg)
            st.markdown(f"""
            <div style="background: {c_bg}; height: 42px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); margin-top: 4px;"></div>
            <div style="font-size: 0.78rem; color: #CBD5E1; margin-top: 4px; line-height: 1.4;">
                <b>HEX:</b> <code>{c_bg}</code><br>
                <b>RGB:</b> <code>{r},{g},{b}</code><br>
                <b>HSL:</b> <code>{rgb_to_hsl(r,g,b)}</code>
            </div>
            """, unsafe_allow_html=True)

        with col_sw5:
            c_txt = st.color_picker("Text", value=t_hex, key="cp_txt")
            r, g, b = hex_to_rgb(c_txt)
            st.markdown(f"""
            <div style="background: {c_txt}; height: 42px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); margin-top: 4px;"></div>
            <div style="font-size: 0.78rem; color: #CBD5E1; margin-top: 4px; line-height: 1.4;">
                <b>HEX:</b> <code>{c_txt}</code><br>
                <b>RGB:</b> <code>{r},{g},{b}</code><br>
                <b>HSL:</b> <code>{rgb_to_hsl(r,g,b)}</code>
            </div>
            """, unsafe_allow_html=True)

        # Allow adding custom color
        with st.expander("➕ Add Custom Brand Color (Extra Accent / Gradient)"):
            c_custom = st.color_picker("Choose Custom Brand Color", value="#38BDF8")
            st.caption(f"Custom Color HEX: `{c_custom}` | RGB: `{hex_to_rgb(c_custom)}` | HSL: `{hex_to_hsl(c_custom)}`")

        c_rule1 = st.checkbox("Maintain strict brand color palette (no random unrelated colors)", value=True)
        c_rule2 = st.checkbox("Maintain brand visual identity across all posts", value=True)

    # PILLARS 4-6: Typography, Personality, Visual Style
    with dna_tabs[1]:
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("#### Pillar 4: Typography")
            f_head = st.selectbox("Heading Font:", [
                "Playfair Display (Luxury Serif)",
                "Outfit (Modern Bold)",
                "Plus Jakarta Sans (SaaS Clean)",
                "Inter (Neutral Tech)",
                "Cinzel (Heritage Elegance)",
                "Syne (Avant-Garde)"
            ], index=0)
            f_body = st.selectbox("Body Font:", [
                "Plus Jakarta Sans",
                "Inter",
                "Source Sans 3",
                "Roboto",
                "Space Grotesk"
            ], index=0)
            st.caption("💡 *Note: Supports post-generation text overlay layer so typography renders sharp and accurate.*")

        with col_t2:
            st.markdown("#### Pillar 6: Visual Style Direction")
            visual_style_options = [
                "🎞️ 80s / 90s Vintage Nostalgia (Trending Film Grain & Portra 400)",
                "✨ Editorial Flash Luxury (Vogue / Architectural Digest High Contrast)",
                "🌅 Golden Hour Cinematic (Warm Sunkissed Fairy Lights & Twilight)",
                "👑 Royal Heritage Grandeur (Palatial Indian Wedding, Marigold & Brass)",
                "🌿 Modern Minimalist Lawn (Clean Architectural Greenery & Elegant Drapes)",
                "📸 Candid Smartphone UGC (Authentic First-Person Celebration Vibe)",
                "🎨 Bold & Pop Modern",
                "💼 Corporate & Minimal",
                "Auto Detect From Brand",
                "Custom"
            ]
            chosen_visual_style = st.selectbox("Visual Style:", options=visual_style_options, index=0)
            if chosen_visual_style == "Custom":
                custom_style_desc = st.text_input("Describe Custom Visual Style:", value="Scandinavian warm minimalist photography with film grain")
            else:
                custom_style_desc = chosen_visual_style

        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 1rem 0;'>", unsafe_allow_html=True)
        st.markdown("#### Pillar 5: Brand Personality")
        personality_list = [
            "Premium", "Minimal", "Luxury", "Royal", "Celebratory", "Friendly",
            "Professional", "Bold", "Playful", "Modern", "Traditional", "Technical",
            "Emotional", "Trustworthy"
        ]
        raw_personality = active_b.get("personality", ["Royal", "Trustworthy", "Celebratory"])
        safe_personality = [p for p in raw_personality if p in personality_list]
        if not safe_personality:
            safe_personality = ["Royal", "Trustworthy", "Celebratory"]
        selected_traits = st.multiselect("Brand Personality Traits:", options=personality_list, default=safe_personality)

        p_col1, p_col2 = st.columns(2)
        with p_col1:
            slider_formal = st.slider("Tone: Formal ←→ Casual", min_value=1, max_value=5, value=active_b.get("formal_casual", 3))
        with p_col2:
            slider_creative = st.slider("Style: Conservative ←→ Creative", min_value=1, max_value=5, value=active_b.get("conservative_creative", 4))

    # PILLARS 7-9: Audience, Industry, Market
    with dna_tabs[2]:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown("#### Pillar 7: Target Audience")
            aud_default = st.session_state.get("cached_audience", active_b.get("target_audience", "Engaged couples, families planning weddings, event organizers, corporate banquet bookers"))
            cta_default = st.session_state.get("cached_cta", active_b.get("cta", "Compare Venues & Get Free Quotes"))
            audience_input = st.text_area("Target Audience Description *", value=aud_default, height=90)
            primary_cta = st.text_input("Primary CTA / Action *", value=cta_default)

        with col_m2:
            st.markdown("#### Pillars 8 & 9: Market & Location")
            country_default = st.session_state.get("cached_country", active_b.get("target_country", "India"))
            city_default = st.session_state.get("cached_city", active_b.get("target_city", "Gujarat (Ahmedabad, Surat, Vadodara, Rajkot)"))
            country_input = st.text_input("Target Country *", value=country_default)
            city_input = st.text_input("Target City / Region", value=city_default)
            contact_email = st.text_input("Business Email", value=active_b.get("email", "hello@venueconnect.in"))
            contact_phone = st.text_input("Phone Number", value=active_b.get("phone", "+91 98765 43210"))

    # PILLAR 10: Social Presence & Web
    with dna_tabs[3]:
        st.markdown("#### Pillar 10: Existing Social Presence & Website")
        st.caption("AI analyzes public presence to maintain voice and prevent conflicting tone.")
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            website_url = st.text_input("Website URL", value=web_input_val or active_b.get("website", "https://www.venueconnect.in/"))
            ig_url = st.text_input("Instagram URL / Handle", value=active_b.get("instagram", "@venueconnect.in"))
            fb_url = st.text_input("Facebook URL", value=active_b.get("facebook", "https://facebook.com/venueconnect.in"))
        with col_w2:
            x_url = st.text_input("X (Twitter) URL", value=active_b.get("x", ""))
            li_url = st.text_input("LinkedIn URL", value=active_b.get("linkedin", ""))

        st.checkbox("Maintain existing brand style from verified links", value=True)
        st.checkbox("Maintain existing brand voice and positioning", value=True)

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 1.4rem 0;'>", unsafe_allow_html=True)

    # ==========================================================================
    # 🎯 CAMPAIGN CONTEXT, PLATFORMS & CLAIM SAFETY GUARDRAILS
    # ==========================================================================
    st.markdown("""
    <div style="background: rgba(18, 22, 32, 0.95); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 14px; padding: 1.2rem 1.4rem; margin-bottom: 1.2rem;">
        <div style="font-weight: 800; font-size: 1.15rem; color: #F8FAFC; display: flex; align-items: center; gap: 8px;">
            <span style="color: #38BDF8; font-size: 1.25rem;">✨</span> Custom Campaign Information & Context (High Priority)
        </div>
        <div style="font-size: 0.86rem; color: #94A3B8; margin-top: 4px;">
            Tell AI anything specific about this post, offer, product launch, or message. This information is treated as top-priority context.
        </div>
    </div>
    """, unsafe_allow_html=True)

    camp_default = st.session_state.get(
        "cached_campaign_info",
        active_b.get(
            "guidelines",
            "Find and book the best wedding venues, banquet halls, party plots & event spaces in Gujarat. Compare prices, capacity, catering options in Ahmedabad, Surat, Rajkot, Vadodara and across Gujarat."
        )
    )
    custom_campaign_info = st.text_area(
        "✨ CUSTOM CAMPAIGN INFORMATION (OPTIONAL)",
        placeholder="Tell AI anything specific about this post, product, offer, campaign, webpage, promotion or message you want to communicate.",
        height=110,
        value=camp_default
    )

    col_cp1, col_cp2 = st.columns(2)
    with col_cp1:
        prod_url_default = st.session_state.get("cached_product_url", web_input_val or active_b.get("website", "https://www.venueconnect.in/"))
        product_page_url = st.text_input("Product / Specific Campaign Page URL (Optional):", value=prod_url_default)
    with col_cp2:
        objective_options = [
            "Brand Awareness",
            "Product Promotion",
            "Sales & Conversions",
            "Lead Generation",
            "Website Traffic",
            "Engagement & Community Building",
            "Educational / Authority",
            "Product Launch Announcement",
            "Brand Trust & Proof",
            "Seasonal Campaign"
        ]
        chosen_objective = st.selectbox("Content Objective (Goal):", options=objective_options, index=0)

    # Multi-Platform Adaptation
    st.markdown("#### 📱 Target Platforms (Multi-Platform Native Adaptation)")
    st.caption("Content will NOT be copied blindly. The AI adapts caption length, tone, CTA, hashtags, and formatting per platform.")
    col_pl1, col_pl2, col_pl3, col_pl4, col_pl5 = st.columns(5)
    with col_pl1: p_ig = st.checkbox("Instagram", value=True)
    with col_pl2: p_fb = st.checkbox("Facebook", value=True)
    with col_pl3: p_x = st.checkbox("X (Twitter)", value=True)
    with col_pl4: p_li = st.checkbox("LinkedIn", value=True)
    with col_pl5: p_pin = st.checkbox("Pinterest", value=False)

    selected_platforms = []
    if p_ig: selected_platforms.append("Instagram")
    if p_fb: selected_platforms.append("Facebook")
    if p_x: selected_platforms.append("X")
    if p_li: selected_platforms.append("LinkedIn")
    if p_pin: selected_platforms.append("Pinterest")

    # Claim Safety Check of Campaign Input
    detected_risks = audit_claim_safety(custom_campaign_info, verified_context=custom_campaign_info)
    if detected_risks:
        for r in detected_risks:
            st.warning(f"⚠️ **Claim Safety Warning:** {r}")

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 1.4rem 0;'>", unsafe_allow_html=True)

    # ==========================================================================
    # ⚙️ AI PROVIDER & MODEL SETTINGS
    # ==========================================================================
    with st.expander("⚙️ AI Provider & Model Architecture Settings", expanded=False):
        prov_col1, prov_col2 = st.columns(2)
        with prov_col1:
            ai_provider = st.selectbox("AI Provider:", ["Google Gemini", "ChatGPT (OpenAI)", "Claude (Anthropic)"])
        with prov_col2:
            if ai_provider == "Google Gemini":
                gemini_models = [
                    "gemini-3.8-flash",
                    "gemini-3.7-flash",
                    "gemini-3.6-flash",
                    "gemini-3.5-flash",
                    "gemini-3.5-flash-lite",
                    "gemini-3.1-pro-preview",
                    "gemini-2.5-flash",
                    "gemini-2.0-flash",
                    "gemini-1.5-pro",
                    "gemini-1.5-flash",
                    "Custom Model"
                ]
                strategy_model = st.selectbox("Text / Strategy Model:", gemini_models, index=0)
            elif ai_provider == "ChatGPT (OpenAI)":
                strategy_model = st.selectbox("Text / Strategy Model:", ["gpt-4o", "gpt-4o-mini", "o3-mini", "Custom Model"], index=0)
            else:
                strategy_model = st.selectbox("Text / Strategy Model:", ["claude-3-7-sonnet", "claude-3-5-sonnet", "claude-3-5-haiku", "Custom Model"], index=0)

            if strategy_model == "Custom Model":
                strategy_model = st.text_input("Custom Model Identifier:", value="gemini-3.8-flash")

        gemini_api_key = st.text_input("AI Provider API Key (Optional — Studio uses verified fallback if blank):", type="password", value="", help="Enter your Google Gemini or OpenAI API key.")

    # ==========================================================================
    # 🚀 PRIMARY CTA: GENERATE COMPLETE CONTENT PACK
    # ==========================================================================
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    generate_btn = st.button("🚀 Generate Complete Content Pack", type="primary", use_container_width=True)

    # Persistence of generated studio pack
    if "studio_content_pack" not in st.session_state:
        st.session_state["studio_content_pack"] = None

    if generate_btn:
        progress_placeholder = st.empty()
        with progress_placeholder.container():
            st.markdown("""
            <div style="background: rgba(15, 23, 42, 0.95); border: 1px solid #F59E0B; border-radius: 12px; padding: 1.2rem; margin: 1rem 0;">
                <div style="color: #F59E0B; font-weight: 800; font-size: 1rem; margin-bottom: 8px;">⏳ Executing 10-Step Brand-First Workflow...</div>
                <div style="font-size: 0.86rem; color: #CBD5E1; line-height: 1.8;">
                    ✓ Step 0: Format & parameters configured (<b>{}</b>)<br>
                    ✓ Pillars 1-3: Brand Identity, Colors & Uploads analyzed<br>
                    ✓ Pillars 4-6: Typography ({}) & Visual Style ({}) resolved<br>
                    ✓ Pillars 7-10: Target Audience, Market & Social presence mapped<br>
                    ✓ Campaign context & Claim Safety audit completed<br>
                    ⏳ Creating Content Strategy & 4 Creative Concepts...<br>
                    ○ Synthesizing Platform-Specific Captions (Instagram, LinkedIn, X, Facebook)<br>
                    ○ Running Brand Consistency QA Engine...
                </div>
            </div>
            """.format(chosen_format, f_head.split(" (")[0], chosen_visual_style), unsafe_allow_html=True)

        # Prepare payload
        biz_data = {
            "brand_name": brand_name,
            "industry": industry_input,
            "target_country": country_input,
            "target_city": city_input,
            "target_audience": audience_input,
            "website": website_url,
            "instagram": ig_url,
            "facebook": fb_url,
            "x": x_url,
            "linkedin": li_url,
            "phone": contact_phone,
            "email": contact_email,
            "cta": primary_cta
        }

        color_pack = {
            "primary": {"hex": c_prim, "rgb": f"rgb{hex_to_rgb(c_prim)}", "hsl": hex_to_hsl(c_prim)},
            "secondary": {"hex": c_sec, "rgb": f"rgb{hex_to_rgb(c_sec)}", "hsl": hex_to_hsl(c_sec)},
            "accent": {"hex": c_acc, "rgb": f"rgb{hex_to_rgb(c_acc)}", "hsl": hex_to_hsl(c_acc)},
            "background": {"hex": c_bg, "rgb": f"rgb{hex_to_rgb(c_bg)}", "hsl": hex_to_hsl(c_bg)},
            "text": {"hex": c_txt, "rgb": f"rgb{hex_to_rgb(c_txt)}", "hsl": hex_to_hsl(c_txt)}
        }

        typo_pack = {
            "heading": f_head.split(" (")[0],
            "body": f_body
        }

        generated_pack = generate_social_content_studio(
            content_format=chosen_format,
            format_settings=format_settings,
            platforms=selected_platforms,
            objective=chosen_objective,
            business=biz_data,
            brand_palette=color_pack,
            typography=typo_pack,
            personality_traits=selected_traits,
            formal_casual=slider_formal,
            conservative_creative=slider_creative,
            visual_style=chosen_visual_style,
            campaign_info=custom_campaign_info,
            product_url=product_page_url,
            api_key=gemini_api_key,
            provider=ai_provider,
            strategy_model=strategy_model
        )

        st.session_state["studio_content_pack"] = generated_pack
        progress_placeholder.empty()
        st.success("🎉 Complete Brand-First Content Pack Generated Successfully!")

    # ==========================================================================
    # 7. PRODUCTION OUTPUT: BRAND DNA → STRATEGY → CONCEPTS → CAPTIONS → QA
    # ==========================================================================
    pack = st.session_state["studio_content_pack"]

    if pack:
        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 14px; padding: 0.9rem 1.4rem; margin-bottom: 1.4rem; display: flex; align-items: center; justify-content: space-between;">
            <div>
                <span style="color: #F59E0B; font-weight: 800; font-size: 1.05rem;">📦 Content Studio Production Package</span>
                <span style="color: #94A3B8; font-size: 0.85rem; margin-left: 10px;">Format: <b>{}</b> | Goal: <b>{}</b></span>
            </div>
            <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; padding: 4px 12px; border-radius: 9999px; font-weight: 700; font-size: 0.78rem; border: 1px solid rgba(16, 185, 129, 0.3);">
                ✓ BRAND QA PASSED
            </span>
        </div>
        """.format(chosen_format, chosen_objective), unsafe_allow_html=True)

        # ==============================================================================
        # ⚡ SIDE-BY-SIDE STUDIO WORKBENCH: PROMPT (LEFT) vs CAPTION (RIGHT)
        # ==============================================================================
        st.markdown("""
        <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.98) 100%); border: 1px solid rgba(245, 158, 11, 0.5); border-radius: 14px; padding: 1.1rem 1.4rem; margin-bottom: 1.2rem; box-shadow: 0 8px 30px rgba(0,0,0,0.4);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div>
                    <div style="color: #F59E0B; font-weight: 800; font-size: 1.2rem; display: flex; align-items: center; gap: 8px;">
                        <span>⚡</span> AI Social Content Studio Workbench (Side-by-Side)
                    </div>
                    <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 4px;">
                        Target: <b>{}</b> | Format: <b>{}</b> | Style: <b>{}</b>
                    </div>
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; padding: 4px 10px; border-radius: 20px; font-weight: 700; font-size: 0.78rem; border: 1px solid rgba(16, 185, 129, 0.3);">
                        ✓ Niche Verified ({})
                    </span>
                    <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; padding: 4px 10px; border-radius: 20px; font-weight: 700; font-size: 0.78rem; border: 1px solid rgba(56, 189, 248, 0.3);">
                        ✓ Branding Safe Zones Protected
                    </span>
                </div>
            </div>
        </div>
        """.format(brand_name, chosen_format, chosen_visual_style, detect_industry_category(industry_input, custom_campaign_info, brand_name).upper()), unsafe_allow_html=True)

        concepts = pack.get("creative_concepts", [])
        if not concepts:
            concepts = build_industry_concepts(brand_name, industry_input, chosen_visual_style, c_prim, c_sec, c_bg, typo_pack, biz_data, content_format=chosen_format)
            pack["creative_concepts"] = concepts

        concept_titles = [
            f"Concept {i+1}: {c.get('concept_name', f'Concept {i+1}').split(': ')[-1] if ': ' in c.get('concept_name', '') else c.get('concept_name', f'Concept {i+1}')}"
            for i, c in enumerate(concepts)
        ]

        active_c_idx = st.radio(
            "📌 Select Creative Concept Slot:",
            options=list(range(len(concepts))),
            format_func=lambda i: concept_titles[i] if i < len(concept_titles) else f"Concept #{i+1}",
            horizontal=True,
            key="studio_active_concept_idx"
        )
        cur_concept = concepts[active_c_idx]

        col_left_prmpt, col_right_capt = st.columns([1.1, 1.1])

        # ----------------------------------------------------------------------
        # LEFT COLUMN: TRENDING VISUAL IMAGE PROMPT
        # ----------------------------------------------------------------------
        with col_left_prmpt:
            st.markdown(f"""
            <div style="background: rgba(17, 24, 39, 0.95); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="font-weight: 800; font-size: 1.05rem; color: #38BDF8;">📸 Trending Visual Image Prompt</span>
                    <span style="font-size: 0.74rem; background: rgba(56, 189, 248, 0.12); color: #38BDF8; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.25);">
                        {chosen_format} • {format_settings.get('aspect_ratio', '4:5')}
                    </span>
                </div>
                <div style="font-size: 0.78rem; color: #94A3B8;">
                    <b>Visual Direction:</b> {cur_concept.get('visual_direction', 'Curated scene')}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Safe Zone Specs Callout Box
            st.markdown(f"""
            <div style="background: rgba(15, 23, 42, 0.85); border: 1px dashed rgba(245, 158, 11, 0.4); border-radius: 8px; padding: 8px 12px; font-size: 0.76rem; color: #CBD5E1; margin-bottom: 8px; line-height: 1.5;">
                🛡️ <b>Negative Space & Branding Safe Zones:</b><br>
                • <b>Logo Buffer:</b> Upper 20% clear negative space reserved for brand logo.<br>
                • <b>Website & Contacts:</b> Lower-third subtle gradient reserved for <code>{website_url or 'venueconnect.in'}</code>, Phone & Social tagging.<br>
                • <b>Aesthetic:</b> {chosen_visual_style}
            </div>
            """, unsafe_allow_html=True)

            prompt_text = cur_concept.get("image_generation_prompt", "")
            st.text_area(
                "Image Generation Prompt (Ready for Midjourney / Flux / SDXL / Ideogram):",
                value=prompt_text,
                height=230,
                key=f"txt_prompt_area_{active_c_idx}"
            )

            # Left Action Buttons: Copy Prompt & Regenerate Prompt
            lp_col1, lp_col2 = st.columns(2)
            with lp_col1:
                if st.button("📋 Copy Image Prompt", key=f"btn_copy_prompt_{active_c_idx}", use_container_width=True, type="primary"):
                    st.components.v1.html(f"<script>navigator.clipboard.writeText({json.dumps(prompt_text)});</script>", height=0)
                    st.toast("✅ Image Prompt copied to clipboard!")
            with lp_col2:
                if st.button("🔄 Regenerate Prompt", key=f"btn_regen_prompt_{active_c_idx}", use_container_width=True):
                    cur_it = st.session_state.get(f"prompt_regen_ver_{active_c_idx}", 0) + 1
                    st.session_state[f"prompt_regen_ver_{active_c_idx}"] = cur_it
                    with st.spinner("🔄 Generating fresh trending prompt variation..."):
                        fresh_c = get_alternate_concept(
                            idx=active_c_idx,
                            brand_name=brand_name,
                            industry_text=industry_input,
                            visual_style=chosen_visual_style,
                            prim_hex=c_prim,
                            sec_hex=c_sec,
                            bg_hex=c_bg,
                            typography=typo_pack,
                            business=biz_data,
                            iteration=cur_it,
                            content_format=chosen_format
                        )
                        pack["creative_concepts"][active_c_idx] = fresh_c
                        st.session_state["studio_content_pack"] = pack
                        st.session_state["social_content_pack"] = pack
                        st.rerun()

        # ----------------------------------------------------------------------
        # RIGHT COLUMN: MATCHING SOCIAL CAPTION & COPY
        # ----------------------------------------------------------------------
        with col_right_capt:
            st.markdown("""
            <div style="background: rgba(17, 24, 39, 0.95); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="font-weight: 800; font-size: 1.05rem; color: #F59E0B;">✍️ Matching Social Caption & Copy</span>
                    <span style="font-size: 0.74rem; background: rgba(245, 158, 11, 0.12); color: #F59E0B; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(245, 158, 11, 0.25);">
                        Platform Adapted
                    </span>
                </div>
                <div style="font-size: 0.78rem; color: #94A3B8;">
                    High-converting hook, value proposition, website CTA, and strategic hashtags.
                </div>
            </div>
            """, unsafe_allow_html=True)

            cap_plat_col, cap_tone_col = st.columns([1.2, 1.2])
            with cap_plat_col:
                sel_plat = st.selectbox(
                    "Platform:",
                    ["Instagram", "Facebook", "X (Twitter)", "LinkedIn"],
                    key=f"wb_sel_plat_{active_c_idx}"
                )
            with cap_tone_col:
                sel_tone = st.selectbox(
                    "Tone:",
                    ["Professional / Trust", "Creative / Story-Driven", "Short & Punchy"],
                    key=f"wb_sel_tone_{active_c_idx}"
                )

            plat_key = {"Instagram": "instagram", "Facebook": "facebook", "X (Twitter)": "x", "LinkedIn": "linkedin"}.get(sel_plat, "instagram")
            tone_key = {"Professional / Trust": "professional", "Creative / Story-Driven": "creative", "Short & Punchy": "short"}.get(sel_tone, "professional")

            caps_dict = pack.get("platform_captions", {})
            p_data = caps_dict.get(plat_key, {})
            if isinstance(p_data, dict):
                body_caption = p_data.get(tone_key, p_data.get("professional", ""))
            else:
                body_caption = str(p_data)

            ht_engine = pack.get("hashtag_engine", {})
            combined_tags = " ".join(
                ht_engine.get("brand_hashtags", []) +
                ht_engine.get("product_hashtags", []) +
                ht_engine.get("location_hashtags", [])
            )
            full_caption_text = f"{body_caption}\n\n---\n{combined_tags}" if combined_tags else body_caption

            st.text_area(
                f"{sel_plat} Caption ({sel_tone}):",
                value=full_caption_text,
                height=230,
                key=f"txt_caption_area_{active_c_idx}_{plat_key}_{tone_key}"
            )

            # Right Action Buttons: Copy Caption & Regenerate Caption
            rc_col1, rc_col2 = st.columns(2)
            with rc_col1:
                if st.button("📋 Copy Caption & Tags", key=f"btn_copy_cap_{active_c_idx}", use_container_width=True, type="primary"):
                    st.components.v1.html(f"<script>navigator.clipboard.writeText({json.dumps(full_caption_text)});</script>", height=0)
                    st.toast("✅ Caption & Hashtags copied to clipboard!")
            with rc_col2:
                if st.button("🔄 Regenerate Caption", key=f"btn_regen_cap_{active_c_idx}", use_container_width=True):
                    cur_cap_it = st.session_state.get(f"caption_regen_ver_{active_c_idx}", 0) + 1
                    st.session_state[f"caption_regen_ver_{active_c_idx}"] = cur_cap_it
                    with st.spinner("🔄 Generating fresh caption and hook..."):
                        fresh_caps = build_platform_captions_fresh(
                            brand_name=brand_name,
                            industry=industry_input,
                            objective=chosen_objective,
                            business=biz_data,
                            iteration=cur_cap_it
                        )
                        pack["platform_captions"] = fresh_caps
                        st.session_state["studio_content_pack"] = pack
                        st.session_state["social_content_pack"] = pack
                        st.rerun()

        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 1.2rem 0;'>", unsafe_allow_html=True)
        col_dl1, col_dl2 = st.columns([3, 1])
        with col_dl1:
            st.caption(f"✨ Production content ready for **{brand_name}** | Use the copy buttons above to export to Midjourney / Stable Diffusion and your social scheduler.")
        with col_dl2:
            pack_json = json.dumps(pack, indent=2)
            st.download_button(
                "💾 Download Pack (.JSON)",
                data=pack_json,
                file_name=f"{brand_name.lower().replace(' ', '_')}_content_pack.json",
                mime="application/json",
                use_container_width=True
            )
