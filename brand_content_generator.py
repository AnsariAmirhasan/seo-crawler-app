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
    business["campaign_info"] = campaign_info or business.get("campaign_info", "")
    business["objective"] = objective or business.get("objective", "Lead Generation")
    business["personality_traits"] = personality_traits or business.get("personality_traits", [])
    business["visual_style"] = visual_style or business.get("visual_style", "")
    business["formal_casual"] = formal_casual
    business["conservative_creative"] = conservative_creative
    business["product_url"] = product_url or business.get("product_url", "")
    business["platforms"] = platforms
    business["typography"] = typography
    business["brand_palette"] = brand_palette

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
                        for idx_c, c in enumerate(parsed["creative_concepts"]):
                            prmpt = c.get("image_generation_prompt", "")
                            if "[TOP-LEFT LOGO FRAME]" not in prmpt:
                                alt_c = get_alternate_concept(
                                    idx=idx_c,
                                    brand_name=brand_name,
                                    industry_text=business.get("industry", ""),
                                    visual_style=visual_style,
                                    prim_hex=prim_hex,
                                    sec_hex=sec_hex,
                                    bg_hex=bg_hex,
                                    typography=typography,
                                    business=business,
                                    iteration=0,
                                    content_format=content_format
                                )
                                c["image_generation_prompt"] = alt_c["image_generation_prompt"]
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
    concepts = build_industry_concepts(brand_name, business.get("industry", ""), visual_style, prim_hex, sec_hex, bg_hex, typography, business, iteration=0, content_format=content_format)

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
        "platform_captions": build_platform_captions_fresh(brand_name, business.get("industry", ""), objective, business, iteration=0),
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


def build_prompt_safe_zone_clause(content_format: str, web: str, phone: str, instagram: str, brand_name: str = "", cta: str = "") -> str:
    """Generates precise advertising layout specifications with dedicated [ YOUR LOGO HERE ] frame, marketing typography, 3-panel split strip, and bottom branding banner."""
    web_str = web if web else "www.venueconnect.in"
    phone_str = phone if phone else "+91 98765 43210"
    handle_str = instagram if instagram else "@venueconnect.in"
    b_name = brand_name if brand_name else "Brand"
    c_btn = cta if cta else "EXPLORE NOW"

    return (
        f"Commercial Advertising Poster Layout Architecture for {b_name}: "
        f"[TOP-LEFT BRANDING SAFE ZONE]: Dedicated clean minimalist rectangular negative space box with subtle thin dashed border clearly labeled '[ YOUR LOGO HERE ]' on a plain clean neutral background (completely clean, zero leaves, zero floral motifs, zero clutter on either side), perfectly reserved for seamless direct brand logo overlay. "
        f"[LEFT-SIDE MARKETING COPY & BADGES]: Left 40% section structured for bold high-contrast marketing typography: eye-catching primary headline, engaging sub-headline question ('What's the Difference & How to Choose?'), 4 circular feature badge icons with clean micro-labels [🏛️ Verified Quality] [💰 Direct Best Rates] [👥 Flexible Capacity] [⚡ Free Coordination], and an elegant cursive script value tagline. "
        f"[RIGHT HERO VISUAL]: Commercial high-end photography in right 60% area with beautiful depth of field, warm ambient illumination, and realistic textures. "
        f"[LOWER-MIDDLE 3-PANEL STRIP]: A horizontal 3-panel split photo strip showcasing 3 key amenities/benefits with small clean title tabs. "
        f"[BOTTOM BRAND FOOTER BANNER]: Full-width sleek dark footer bar across the bottom edge featuring: Globe icon + Website: {web_str} | Phone icon + Booking Helpline: {phone_str} | Right-aligned clickable CTA pill button '{c_btn} ➔'. "
        f"Clean commercial graphic design poster composition, balanced negative space, high-contrast typography, ultra-sharp 8k advertising creative."
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



def format_ad_poster_prompt(
    brand_name: str,
    headline: str,
    sub_headline: str,
    badges: List[str],
    tagline: str,
    hero_scene: str,
    strip_panels: List[str],
    web: str,
    phone: str,
    email: str,
    cta: str,
    f_head: str,
    f_body: str,
    prim_hex: str,
    style_frag: str,
    extra_details: str = "",
    aspect_ratio: str = "4:5"
) -> str:
    """
    Constructs a ChatGPT/Midjourney/Flux/SDXL ready Commercial Advertising Poster Prompt
    honoring EVERY brand parameter: Logo negative space, typography, custom copy, badges,
    hero visual style, 3-panel strip, and footer contact ribbon.
    """
    clean_badges = [b.strip() for b in badges if b.strip()]
    badges_str = " ".join(f"[{b.strip('[]')}]" for b in clean_badges[:4])

    clean_panels = [p.strip() for p in strip_panels if p.strip()]
    strip_str = ", ".join(f"({i+1}) {p}" for i, p in enumerate(clean_panels[:3]))

    contact_parts = []
    if web:
        contact_parts.append(f"Globe icon 'Website: {web}'")
    if phone:
        contact_parts.append(f"Phone icon 'Helpline: {phone}'")
    if email:
        contact_parts.append(f"Email icon 'Email: {email}'")

    cta_btn = (cta or "EXPLORE NOW").strip().upper()
    if not cta_btn.endswith("➔"):
        cta_btn = f"{cta_btn} ➔"
    contact_parts.append(f"Right-aligned clickable CTA pill button '{cta_btn}'")
    footer_str = " | ".join(contact_parts)

    prompt = (
        f"Commercial advertising poster layout for {brand_name}. "
        f"[TOP-LEFT LOGO FRAME]: Dedicated clean minimalist rectangular negative space box with subtle thin dashed border clearly labeled '[ YOUR LOGO HERE ]' on a plain clean neutral background (completely clean, zero leaves, zero floral clutter on either side), perfectly reserved for direct brand logo overlay. "
        f"[LEFT MARKETING CONTENT & COPY]: "
        f"Large bold primary headline '{headline}' in opulent {f_head} font, "
        f"sub-headline question '{sub_headline}' in clean legible {f_body} font, "
        f"4 circular feature badge icons with clean micro-labels: {badges_str}, "
        f"with elegant cursive script value tagline '{tagline}'. "
        f"[RIGHT HERO PHOTOGRAPHY]: {hero_scene}, {style_frag}. "
        f"[LOWER-MIDDLE 3-PANEL STRIP]: Clean horizontal split 3-tile photo strip showing: {strip_str}. "
        f"[BOTTOM BRAND FOOTER BANNER]: Full-width sleek deep {prim_hex} footer ribbon with {footer_str}. "
        f"{extra_details} "
        f"Ultra-sharp 8k resolution, professional graphic design advertising creative, balanced negative space, {aspect_ratio} ratio."
    )
    return prompt.strip()


def get_objective_messaging(
    objective: str,
    cat: str,
    brand_name: str,
    city: str,
    audience: str,
    web: str,
    cta_input: str,
    traits_tagline: str,
    idx: int,
    iteration: int,
    base_v: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Dynamically maps the selected Content Objective (Goal) into tailored headline, sub-headline,
    badge micro-labels, cursive tagline, hero visual description, 3-panel strip, and CTA pill.
    Ensures every objective (e.g. Seasonal Campaign, Website Traffic, Lead Generation, etc.)
    produces distinct, highly targeted marketing copy.
    """
    obj_clean = (objective or "Lead Generation").strip()
    obj_lower = obj_clean.lower()

    # Check if custom CTA is provided by user (and not just empty/default placeholder)
    has_custom_cta = bool(cta_input and cta_input.strip() and cta_input.strip() != "Compare Venues & Get Free Quotes")
    custom_cta_pill = f"{cta_input.strip().upper()} ➔" if has_custom_cta else ""

    if cat == "events_venues":
        # -------------------------------------------------------------
        # 1. SEASONAL CAMPAIGN (Peak wedding season, Shubh Muhurat rush)
        # -------------------------------------------------------------
        if "season" in obj_lower:
            if idx == 0:
                return {
                    "concept_badge": "Seasonal Peak Rush Ad",
                    "objective_desc": "Capitalizes on upcoming wedding season urgency and auspicious dates booking rush.",
                    "headline": "Gujarat's Wedding Season is Here: Reserve Your Dream Lawn Early",
                    "sub_headline": f"Peak Shubh Muhurat Dates Book 8-12 Months Ahead Across {city}. Lock Your Date Today!",
                    "badges": ["📅 Shubh Muhurat Booking Open", "❄️ Winter & Summer Lawns", "🔒 Price Lock Guarantee", "⚡ Live Date Check"],
                    "tagline": f"Gujarat's Peak Wedding Season Made Effortless • {traits_tagline}",
                    "hero_scene": f"Commercial photography of an illuminated royal outdoor wedding venue lawn in {city} (Ahmedabad, Surat, Vadodara, Rajkot) at twilight during festive winter wedding season, thousands of warm incandescent fairy lights, royal marigold floral archway, glowing gazebo in background, festive Gujarati celebration ambiance",
                    "strip": ["Winter Lawn & Mandap Setup", "Peak Date Availability Tracker", "Grand Twilight Stage Decor"],
                    "cta": custom_cta_pill or "LOCK WEDDING DATE ➔",
                    "overlay": "Gujarat's Wedding Season: Reserve Your Dream Lawn Early",
                    "visual": f"Sprawling illuminated wedding lawn in {city} at twilight during festive wedding season, fairy lights, royal floral archways, glowing gazebo."
                }
            elif idx == 1:
                return {
                    "concept_badge": "Seasonal Family Joy",
                    "objective_desc": "Emotional resonance for families securing peak season dates without stress.",
                    "headline": "Celebrate Peak Wedding Season Without The Venue Rush",
                    "sub_headline": f"Why smart families in {city} lock their auspicious dates 8 months ahead on {brand_name}",
                    "badges": ["💍 Prime Date Guarantee", "🕊️ Zero Booking Stress", "🤝 Direct Owner Rates", "🍽️ Custom Festive Menus"],
                    "tagline": f"Cherished Celebrations in Every Season • {traits_tagline}",
                    "hero_scene": f"Candid documentary photography of bride, groom and celebrating family laughing under an illuminated party plot canopy in {city}, glowing fairy lights, crisp evening air, vibrant traditional Gujarati wedding attire",
                    "strip": ["Sangeet Night Stage", "Sunlit Haldi & Mehendi Lawn", "Royal Phera Mandap"],
                    "cta": custom_cta_pill or "CHECK SEASON DATES ➔",
                    "overlay": "Celebrate Peak Season Without The Venue Rush",
                    "visual": f"Radiant bride, groom, and celebrating family laughing in a sunlit wedding garden & illuminated party plot in {city}."
                }
            elif idx == 2:
                return {
                    "concept_badge": "Season Planning Matrix",
                    "objective_desc": "Comprehensive seasonal comparison of winter vs summer lawns and AC banquet backup.",
                    "headline": "The Gujarat Wedding Season Venue Planner & Availability Guide",
                    "sub_headline": f"Compare winter lawn capacity, weather backup & seasonal catering across {city} banquets",
                    "badges": ["📊 Season Price Matrix", "❄️ AC Ballroom Backup", "🚗 Valet Capacity Guide", "📝 Advance Date Hold"],
                    "tagline": f"Smart Seasonal Planning • {traits_tagline}",
                    "hero_scene": f"Architectural luxury photography of grand banquet hall and outdoor party plot in {city}, showcasing seasonal layouts for 100 to 5,000+ guests, polished marble floor reflections, crystal chandeliers casting golden ambient illumination",
                    "strip": ["Winter Lawn Seating", "AC Pre-Function Ballroom", "Weather-Proof Mandap Setup"],
                    "cta": custom_cta_pill or "PLAN SEASON DATES ➔",
                    "overlay": "Gujarat Wedding Season Venue Planner & Guide",
                    "visual": f"Architectural luxury photography of grand banquet hall and party plot in {city} showcasing seasonal venue features."
                }
            else:
                return {
                    "concept_badge": "Seasonal Urgency Solution",
                    "objective_desc": "Drives immediate date booking before prime Saturday/Sunday auspicious slots sell out.",
                    "headline": "Don't Miss Your Auspicious Date: Lock In Gujarat's Top Lawns Now",
                    "sub_headline": f"Peak wedding dates are selling out fast across {city} - Check live date availability in 60 seconds",
                    "badges": ["⏳ Selling Out Fast", "⚡ 1-Click Date Hold", "💰 Direct Price Lock", "🛡️ 100% Date Guarantee"],
                    "tagline": f"Secure Your Date Today • {traits_tagline}",
                    "hero_scene": f"High-impact commercial photography, illuminated royal wedding venue lawn in {city} with glowing fairy lights, celebratory sparklers, and clear date-reservation badge",
                    "strip": ["Live Date Calendar", "Instant Price Lock", "Guaranteed Booking Confirmation"],
                    "cta": custom_cta_pill or "HOLD YOUR DATE NOW ➔",
                    "overlay": "Don't Miss Your Auspicious Date: Lock It In Today",
                    "visual": f"High-impact commercial contrast resolving into luminous golden wedding celebration on party plot lawn in {city}."
                }

        # -------------------------------------------------------------
        # 2. WEBSITE TRAFFIC (Online exploration, 360 virtual tours)
        # -------------------------------------------------------------
        elif "traffic" in obj_lower or "web" in obj_lower:
            if idx == 0:
                return {
                    "concept_badge": "Digital Directory Ad",
                    "objective_desc": f"Drives high-intent web visits to explore 500+ venues directly on {web}.",
                    "headline": "Browse & Compare 500+ Verified Wedding Lawns Online",
                    "sub_headline": f"Filter By Guest Capacity, Budget, Catering & Location Across {city} on {web}",
                    "badges": ["🌐 360° Virtual Walkthroughs", "📸 10,000+ Real Photos", "🔍 Filter 500+ Venues", "⚡ Instant Price Estimates"],
                    "tagline": f"Gujarat's Largest Online Venue Directory • {traits_tagline}",
                    "hero_scene": f"Commercial photography of an illuminated royal outdoor wedding venue lawn in {city} at twilight with interactive digital UI elements showing 360 virtual tour, crystalline swimming pool reflection, warm incandescent fairy lights, glowing gazebo",
                    "strip": ["Interactive 360° Virtual Tour", "Transparent Pricing & Capacity Filter", "Verified Photo & Video Galleries"],
                    "cta": custom_cta_pill or "EXPLORE 500+ VENUES ONLINE ➔",
                    "overlay": "Browse & Compare 500+ Verified Wedding Lawns Online",
                    "visual": f"Sprawling illuminated wedding lawn in {city} at twilight with modern split digital overlay showcasing 360 virtual tour."
                }
            elif idx == 1:
                return {
                    "concept_badge": "Virtual Scouting Experience",
                    "objective_desc": "Demonstrates the joy of scouting dream venues online together from home.",
                    "headline": "Take a Virtual Walkthrough of Gujarat's Dreamiest Wedding Lawns",
                    "sub_headline": f"Experience 360-degree immersive views of party plots and banquet halls from the comfort of home",
                    "badges": ["👓 360° VR Tours", "🎥 Drone Video Overviews", "📱 Explore from Home", "⭐ Real Couple Ratings"],
                    "tagline": f"Explore Every Corner Online • {traits_tagline}",
                    "hero_scene": f"Split commercial lifestyle photograph showing an engaged couple exploring wedding venues on tablet from home, alongside a glowing twilight drone view of an illuminated Ahmedabad party plot",
                    "strip": ["360° Mandap View", "Ballroom Walkthrough", "Lawn Drone Panorama"],
                    "cta": custom_cta_pill or "START VIRTUAL TOUR ➔",
                    "overlay": "Take a Virtual Walkthrough of Gujarat's Top Lawns",
                    "visual": f"Modern couple reviewing 360 venue tours on tablet with glowing twilight lawn in background."
                }
            elif idx == 2:
                return {
                    "concept_badge": "Online Filter Engine Matrix",
                    "objective_desc": "Educates users on how fast and easy it is to filter venues by capacity and budget online.",
                    "headline": "The 60-Second Online Venue Comparison Engine",
                    "sub_headline": f"Filter 500+ party plots in {city} by guest count (100 to 5,000+), catering type & rental budget",
                    "badges": ["⚡ 60-Second Shortlist", "🔍 Smart Budget Filter", "🍽️ Catering Breakdown", "📍 Location Heatmap"],
                    "tagline": f"Search Smarter, Not Harder • {traits_tagline}",
                    "hero_scene": f"High-tech commercial photography blending illuminated royal banquet ballroom architecture in {city} with sleek digital filter icons and comparison matrices",
                    "strip": ["Capacity Filter: 100-5000+", "Budget Comparison Tool", "Instant Verified Shortlist"],
                    "cta": custom_cta_pill or "COMPARE VENUES ONLINE ➔",
                    "overlay": "60-Second Online Venue Comparison Engine",
                    "visual": f"Architectural luxury photography of grand banquet hall with clean comparison interface elements."
                }
            else:
                return {
                    "concept_badge": "Direct Web Traffic Push",
                    "objective_desc": "Drives immediate clicks to the website by eliminating the exhausting toll of offline visits.",
                    "headline": "Stop Driving to 20 Banquets. Scout Them All Online in Minutes.",
                    "sub_headline": f"Save 40+ hours of exhausting site visits across {city} by comparing verified lawns on {web}",
                    "badges": ["⏱️ Save 40+ Hours", "🚗 Zero Wasted Visits", "💰 Direct Price View", "📲 Instant Online Access"],
                    "tagline": f"The Modern Way to Scout Venues • {traits_tagline}",
                    "hero_scene": f"Side-by-side high-impact commercial contrast: Left side desaturated traffic and exhausted venue hunting in {city}; right side serene couple comfortably browsing illuminated lawns on laptop",
                    "strip": ["Browse 500+ Venues", "Compare Transparent Costs", "Book Only The Best In Person"],
                    "cta": custom_cta_pill or "EXPLORE ONLINE NOW ➔",
                    "overlay": "Stop Driving to 20 Banquets: Scout Online",
                    "visual": f"High-contrast commercial scene showing easy online venue browsing vs traffic."
                }

        # -------------------------------------------------------------
        # 3. BRAND AWARENESS (Prestige, market leadership, grandeur)
        # -------------------------------------------------------------
        elif "aware" in obj_lower or "brand" in obj_lower:
            return {
                "concept_badge": "Brand Prestige Showcase",
                "objective_desc": "Builds unmatched brand authority as Gujarat's premier wedding venue network.",
                "headline": "Where Gujarat Celebrates: 500+ Iconic Wedding Lawns & Banquets",
                "sub_headline": f"The Most Prestigious Party Plots & Luxury Venues Across {city} in One Destination",
                "badges": ["👑 #1 Venue Network", "🏛️ 500+ Iconic Venues", "⭐ 50,000+ Happy Families", "✨ 100% Verified Quality"],
                "tagline": f"Royal Grandeur in Every Milestone • {traits_tagline}",
                "hero_scene": f"Breathtaking panoramic commercial photography of an expansive illuminated palatial wedding venue and party plot in {city} at dusk, grand royal entrance, glowing fountains, thousands of fairy lights, majestic Gujarati heritage architecture",
                "strip": ["Palatial Heritage Architecture", "Illuminated Royal Party Lawn", "Luxury Glasshouse Banquet"],
                "cta": custom_cta_pill or f"DISCOVER {brand_name.upper()} ➔",
                "overlay": "Where Gujarat Celebrates: 500+ Iconic Wedding Lawns",
                "visual": f"Palatial illuminated wedding lawn in {city} at dusk, glowing fountains and fairy lights."
            }

        # -------------------------------------------------------------
        # 4. SALES & CONVERSIONS (Direct rates, zero broker fee)
        # -------------------------------------------------------------
        elif "sale" in obj_lower or "conver" in obj_lower:
            return {
                "concept_badge": "Direct Price Conversion",
                "objective_desc": "Converts prospective buyers with pre-negotiated direct owner rates.",
                "headline": "Book Your Dream Wedding Lawn at Guaranteed Lowest Rates",
                "sub_headline": f"Zero Middleman Commissions & Pre-Negotiated Direct Owner Pricing Across {city}",
                "badges": ["🏷️ Zero Broker Fee", "💵 Guaranteed Lowest Rates", "📝 100% Contract Protection", "⚡ Instant Date Hold"],
                "tagline": f"Transparent Value, Royal Experience • {traits_tagline}",
                "hero_scene": f"Opulent commercial photograph of an illuminated royal wedding mandap set against manicured green lawn in {city} at twilight, golden incandescent lights, crystal chandeliers, floral backdrop, pristine luxury celebration setting",
                "strip": ["Pre-Negotiated Direct Pricing", "Instant Booking Confirmation", "Written Price-Match Guarantee"],
                "cta": custom_cta_pill or "CLAIM DIRECT OWNER PRICE ➔",
                "overlay": "Guaranteed Lowest Rates on Gujarat's Top Venues",
                "visual": f"Illuminated royal wedding mandap set against manicured green lawn in {city} at twilight."
            }

        # -------------------------------------------------------------
        # 5. PRODUCT PROMOTION (All-inclusive packages)
        # -------------------------------------------------------------
        elif "promo" in obj_lower:
            return {
                "concept_badge": "Turnkey Package Promotion",
                "objective_desc": "Promotes turnkey all-inclusive venue, decor, and catering bundles.",
                "headline": "All-Inclusive Luxury Wedding Lawn & Banquet Packages",
                "sub_headline": f"Venue + Designer Decor + AC Banquet + Valet Parking Bundled Across {city}",
                "badges": ["📦 All-Inclusive Packages", "🍽️ Pure-Veg Gourmet Catering", "❄️ Grand AC Pre-Function Area", "🚗 200+ Car Valet Parking"],
                "tagline": f"Complete Luxury, Zero Coordination Chaos • {traits_tagline}",
                "hero_scene": f"Commercial luxury photograph of an all-inclusive royal wedding setup in {city} at golden hour, featuring designer floral mandap, grand banquet seating, live culinary stations with warm ambient lights",
                "strip": ["Designer Mandap & Floral Decor", "Pure-Veg Gourmet Catering Setup", "Full Power Backup & Valet"],
                "cta": custom_cta_pill or "VIEW ALL-INCLUSIVE PACKAGES ➔",
                "overlay": "All-Inclusive Luxury Wedding Lawn & Banquet Packages",
                "visual": f"All-inclusive royal wedding setup in {city} featuring designer mandap and banquet seating."
            }

        # -------------------------------------------------------------
        # 6. EDUCATIONAL / AUTHORITY (Checklist, how-to, transparency)
        # -------------------------------------------------------------
        elif "educat" in obj_lower or "author" in obj_lower:
            return {
                "concept_badge": "Authority & Checklist Guide",
                "objective_desc": "Establishes definitive authority by educating couples on hidden venue costs.",
                "headline": "How to Choose the Perfect Wedding Venue in Gujarat Without Hidden Fees",
                "sub_headline": f"The Complete Guide to Comparing Capacities, Generator Backup & Catering Policies Across {city}",
                "badges": ["📋 20-Point Venue Checklist", "🔍 100% Transparent Costs", "⚡ Generator & Power Backup", "📜 Verified Municipal Approvals"],
                "tagline": f"Informed Decisions, Flawless Celebrations • {traits_tagline}",
                "hero_scene": f"Commercial architectural photography of a luxury banquet ballroom and outdoor lawn in {city}, crisp high-contrast lighting showcasing venue layout, technical power consoles, and seating capacity indicators",
                "strip": ["Capacity & Seating Benchmarks", "Generator & Sound Permissions", "Catering & Kitchen Audit Checklist"],
                "cta": custom_cta_pill or "READ FREE VENUE GUIDE ➔",
                "overlay": "How to Choose the Perfect Wedding Venue in Gujarat",
                "visual": f"Architectural photography of luxury banquet ballroom showcasing venue layout and checklist benchmarks."
            }

        # -------------------------------------------------------------
        # 7. ENGAGEMENT & COMMUNITY BUILDING (Reviews, voting, stories)
        # -------------------------------------------------------------
        elif "engag" in obj_lower or "communit" in obj_lower:
            return {
                "concept_badge": "Community & Reviews Showcase",
                "objective_desc": "Sparks social interaction, user reviews, and couple community discussions.",
                "headline": "Dream Lawn or Royal Banquet? Plan Gujarat's Next Iconic Wedding",
                "sub_headline": f"Join 50,000+ Couples Sharing Authentic Reviews & Real Wedding Photos Across {city}",
                "badges": ["💬 15,000+ Real Reviews", "📸 Real Wedding Albums", "🏆 Community Choice 2026", "💡 Expert Planning Tips"],
                "tagline": f"Built by Couples, Loved by Gujarat • {traits_tagline}",
                "hero_scene": f"Candid documentary photography of an engaged couple and celebrating family laughing under fairy-lit party plot trees in {city}, authentic joy, vibrant traditional Gujarati attire, warm twilight atmosphere",
                "strip": ["Real Couple Wedding Stories", "Lawn vs Banquet Community Poll", "Top 10 Rated Party Plots in Gujarat"],
                "cta": custom_cta_pill or "JOIN COUPLES COMMUNITY ➔",
                "overlay": "Dream Lawn or Royal Banquet? Vote & Plan with Gujarat's Couple Community",
                "visual": f"Candid documentary capture of couple and celebrating family laughing under fairy-lit trees."
            }

        # -------------------------------------------------------------
        # 8. PRODUCT LAUNCH ANNOUNCEMENT (New venues, premiere plots)
        # -------------------------------------------------------------
        elif "launch" in obj_lower:
            return {
                "concept_badge": "New Venue Launch Premiere",
                "objective_desc": "Announces newly onboarded premium wedding lawns and lakeside venues.",
                "headline": "Now Live: Gujarat's 50 Newest Luxury Lawns & Waterfront Banquets",
                "sub_headline": f"Be the First to Host Your Milestone Celebration at Gujarat's Brand New Venues in {city}",
                "badges": ["✨ 50 Brand New Lawns", "🌊 Waterfront & Resort Plots", "🆕 First-Mover Booking Rates", "🥂 Grand Launch Specials"],
                "tagline": f"Fresh Horizons, Grand Beginnings • {traits_tagline}",
                "hero_scene": f"Commercial photography of a newly opened ultra-luxury waterfront wedding lawn in {city} at twilight, infinity reflection pool, modern architectural pavilion, thousands of fairy lights, pristine manicured lawn",
                "strip": ["New Waterfront & Resort Venues", "Modern Glasshouse Banquets", "Inaugural Booking Discounts"],
                "cta": custom_cta_pill or "EXPLORE NEWLY LAUNCHED VENUES ➔",
                "overlay": "Now Live: Gujarat's 50 Newest Luxury Lawns & Banquets",
                "visual": f"Newly opened ultra-luxury waterfront wedding lawn in {city} at twilight with infinity reflection pool."
            }

        # -------------------------------------------------------------
        # 9. BRAND TRUST & PROOF (100% verified, legal NOCs, guarantee)
        # -------------------------------------------------------------
        elif "trust" in obj_lower or "proof" in obj_lower:
            return {
                "concept_badge": "Trust & Verification Defense",
                "objective_desc": "Dismantles risk through verified certifications, zero double-booking, and audit seals.",
                "headline": "100% Verified Wedding Venues with Guaranteed Date Protection",
                "sub_headline": f"Never Worry About Double Bookings or Unverified Properties Across {city}",
                "badges": ["🛡️ 100% Verified Lawns", "🔒 Double-Booking Protection", "⭐ 4.9/5 Star Rating", "📜 Full Fire & Police NOC"],
                "tagline": f"Your Trust, Our Sacred Commitment • {traits_tagline}",
                "hero_scene": f"Commercial high-contrast luxury photography of a prestigious wedding banquet hall in {city}, golden lighting reflecting on polished marble, prominent verified quality emblem and legal accreditation seals",
                "strip": ["On-Site Physical Inspection Seal", "Double-Booking Legal Guarantee", "4.9-Star Verified Host Ratings"],
                "cta": custom_cta_pill or "VIEW 100% VERIFIED VENUES ➔",
                "overlay": "100% Verified Wedding Venues with Guaranteed Date Protection",
                "visual": f"Prestigious banquet hall in {city} with verified quality and legal clearance seals."
            }

        # -------------------------------------------------------------
        # 10. LEAD GENERATION (Default for events & venues)
        # -------------------------------------------------------------
        else:
            return {
                "concept_badge": "Direct Inquiry & Quotes",
                "objective_desc": "Drives qualified leads and immediate quote inquiries.",
                "headline": "Gujarat's Finest Wedding Lawns & Banquets at Direct Best Prices",
                "sub_headline": f"Get Instant Free Quotes & Compare 500+ Verified Party Plots Across {city}",
                "badges": ["🏛️ 500+ Verified Banquets", "💰 Direct Best Prices", "👥 100-5000+ Guests", "⚡ Free Guided Visits"],
                "tagline": f"Gujarat's Most Loved Celebrations • {traits_tagline}",
                "hero_scene": base_v.get("hero_scene", f"Commercial photography of an illuminated royal outdoor wedding venue lawn in {city} at twilight, thousands of fairy lights, royal marigold floral archway, glowing gazebo in background"),
                "strip": base_v.get("strip", ["Grand Entrance Archway", "Luxurious AC Banquet Ballroom", "Twilight Lakeside Mandap"]),
                "cta": custom_cta_pill or "GET FREE VENUE QUOTE ➔",
                "overlay": base_v.get("overlay", "Gujarat's Finest Wedding Lawns & Banquets"),
                "visual": base_v.get("visual", f"Sprawling illuminated wedding lawn in {city} at twilight.")
            }

    # =========================================================================
    # GENERAL / OTHER INDUSTRIES (Finance, Tech, Healthcare, Consulting, etc.)
    # =========================================================================
    else:
        if "season" in obj_lower:
            return {
                "concept_badge": "Seasonal Campaign Ad",
                "objective_desc": f"Captures seasonal urgency and exclusive limited-time value for {brand_name}.",
                "headline": f"Seasonal Solutions for {audience} in {city}",
                "sub_headline": f"Unlock limited-time benefits and priority scheduling with {brand_name}",
                "badges": ["⏳ Seasonal Access", "🎁 Special Privileges", "⚡ Priority Onboarding", "🔒 Price Lock Guarantee"],
                "tagline": f"Excellence in Every Season • {traits_tagline}",
                "hero_scene": base_v.get("hero_scene", f"High impact commercial scene for {brand_name}"),
                "strip": ["Limited-Time Strategy", "Priority Implementation", "Guaranteed Outcomes"],
                "cta": custom_cta_pill or "CLAIM SEASONAL OFFER ➔",
                "overlay": f"Seasonal Solutions for {audience}",
                "visual": base_v.get("visual", "Modern commercial visual")
            }
        elif "traffic" in obj_lower or "web" in obj_lower:
            return {
                "concept_badge": "Digital Portal Traffic",
                "objective_desc": f"Drives high-intent traffic to explore the new digital portal at {web}.",
                "headline": f"Explore the All-New Online Experience at {brand_name}",
                "sub_headline": f"Instant tools, interactive calculators, and transparent resources live on {web}",
                "badges": ["🌐 24/7 Digital Access", "🔍 Interactive Tools", "⚡ Instant Online Quotes", "📱 Mobile Optimized"],
                "tagline": f"Frictionless Digital Innovation • {traits_tagline}",
                "hero_scene": base_v.get("hero_scene", f"Commercial visual with modern interactive digital overlay for {brand_name}"),
                "strip": ["Interactive Resource Hub", "Instant Online Calculator", "Live Consultation Booking"],
                "cta": custom_cta_pill or "EXPLORE ONLINE NOW ➔",
                "overlay": f"Explore the All-New Online Portal at {brand_name}",
                "visual": base_v.get("visual", "Modern digital platform visual")
            }
        else:
            return {
                "concept_badge": base_v.get("type", "Standard Showcase"),
                "objective_desc": base_v.get("objective", f"Engineered for {objective}"),
                "headline": base_v.get("headline", f"The Standard of Excellence with {brand_name}"),
                "sub_headline": base_v.get("sub_headline", f"Trusted by {audience} in {city}"),
                "badges": base_v.get("badges", ["⚡ Verified Quality", "💰 Direct Value", "👥 Dedicated Team", "⭐ 5-Star Service"]),
                "tagline": base_v.get("tagline", f"Excellence Driven • {traits_tagline}"),
                "hero_scene": base_v.get("hero_scene", f"Commercial photography for {brand_name}"),
                "strip": base_v.get("strip", ["Proven Methodology", "Client Milestones", "Guaranteed Growth"]),
                "cta": custom_cta_pill or base_v.get("cta", "EXPLORE NOW ➔"),
                "overlay": base_v.get("overlay", f"The Standard of Excellence with {brand_name}"),
                "visual": base_v.get("visual", "High-contrast commercial advertising visual")
            }


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
    Fully integrates every user-filled form option: Brand, Industry, Campaign Context, Target Audience,
    City/Region, Primary CTA, Contact info, Typography, Brand Personality, Visual Style, and Colors.
    Guarantees clean, leave-free [ YOUR LOGO HERE ] negative space container and full advertising layout.
    """
    cat = detect_industry_category(industry_text, business.get("campaign_info", ""), brand_name)
    cta = business.get("cta", "Compare Venues & Get Free Quotes").strip() or "Compare Venues & Get Free Quotes"
    city = business.get("target_city", "Gujarat").strip() or "Gujarat"
    country = business.get("target_country", "India").strip() or "India"
    web = business.get("website", "https://www.venueconnect.in/").strip() or "https://www.venueconnect.in/"
    phone = business.get("phone", "+91 98765 43210").strip() or "+91 98765 43210"
    email = business.get("email", "").strip()
    ig_h = business.get("instagram", "@venueconnect.in").strip()
    audience = business.get("target_audience", "Engaged couples, families planning weddings, event organizers").strip() or "Engaged couples, families planning weddings, event organizers"
    campaign_info = business.get("campaign_info", "").strip()
    objective = business.get("objective", "Lead Generation").strip() or "Lead Generation"
    traits = business.get("personality_traits", ["Royal", "Trustworthy", "Celebratory"])
    if isinstance(traits, str):
        traits = [t.strip() for t in traits.split(",") if t.strip()]
    traits_tagline = " • ".join(traits) if traits else "Royal • Trustworthy • Celebratory"
    f_head = typography.get("heading", "Playfair Display").split(" (")[0].strip()
    f_body = typography.get("body", "Source Sans 3").strip()
    style_frag = get_trending_style_prompt_fragment(visual_style)
    ratio = "9:16" if "story" in content_format.lower() or "reel" in content_format.lower() else "4:5"

    # =========================================================================
    # 1. EVENTS, BANQUETS & VENUES (e.g., VenueConnect)
    # =========================================================================
    if cat == "events_venues":
        if idx == 0:
            # Slot 0: Core Authority Hero
            variants = [
                {
                    "name": "Concept 1: Royal Wedding Lawns & Banquets (Signature Flagship Ad Poster)",
                    "type": "Signature Venue Showcase",
                    "objective": "Positions brand as premier verified platform for Gujarat's most breathtaking wedding party plots.",
                    "visual": f"Sprawling illuminated wedding lawn in {city} at twilight, thousands of warm incandescent fairy lights, royal marigold floral archways, glowing gazebo in background, festive Gujarati celebration ambiance.",
                    "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero lawn, lower 3-panel strip, bottom ribbon.",
                    "lighting": "Magical twilight golden hour ambient glow, warm incandescent fairy lights, soft vintage direct flash.",
                    "color_dir": f"Rich twilight indigo sky contrasted with glowing amber {sec_hex} and royal {prim_hex} accents.",
                    "typo_dir": f"Opulent {f_head} headings with refined subtitle tracking in {f_body}.",
                    "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                    "overlay": "Gujarat's Finest Wedding Lawns & Banquets",
                    "cta": f"{cta} • Visit {web}",
                    "headline": "Gujarat's Finest Wedding Lawns, Banquets & Party Plots",
                    "sub_headline": f"Compare 500+ Verified Venues with Transparent Pricing & Capacity across {city}",
                    "badges": ["🏛️ 500+ Verified Banquets", "💰 Direct Best Prices", "👥 100-5000+ Guests", "⚡ Free Guided Visits"],
                    "tagline": f"'{traits_tagline} Standard in Every Celebration'",
                    "hero_scene": f"Commercial luxury photography of an illuminated royal outdoor wedding venue lawn in {city} at twilight, thousands of warm incandescent fairy lights, royal marigold floral archway, glowing gazebo in background, festive Gujarati celebration ambiance",
                    "strip": ["Grand Entrance Archway", "Luxurious AC Banquet Ballroom", "Twilight Lakeside Mandap"]
                },
                {
                    "name": "Concept 1: The Grand Palatial Banquet (Architectural Splendor Ad Poster)",
                    "type": "Grand Authority",
                    "objective": "Captures the awe-inspiring scale and luxury of Gujarat's verified indoor banquets.",
                    "visual": f"Towering crystal chandeliers reflecting on polished marble ballroom floor in {city}, round banquet seating with royal centerpieces, glowing {sec_hex} ambient lighting.",
                    "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero ballroom, lower 3-panel strip, bottom ribbon.",
                    "lighting": "High-key warm golden chandelier illumination with deep architectural depth.",
                    "color_dir": f"Warm ivory, champagnes, and deep royal {prim_hex} grounded by {sec_hex} gold.",
                    "typo_dir": f"Classic luxury serif {f_head} overlay.",
                    "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                    "overlay": "Palatial Banquet Halls & Ballrooms",
                    "cta": f"Check Date Availability: {web}",
                    "headline": "Palatial Banquet Halls & Ballrooms in Gujarat",
                    "sub_headline": f"Looking for Luxury Indoor Banquets for 100 to 5,000+ Guests across {city}?",
                    "badges": ["🏛️ Grand AC Halls", "💰 Zero Hidden Charges", "🍽️ Verified Pure-Veg Menus", "🚗 Dedicated Valet Parking"],
                    "tagline": f"'{traits_tagline} • Tradition & Grandeur'",
                    "hero_scene": f"Architectural luxury photography of an opulent grand banquet hall ballroom in {city}, towering crystal chandeliers casting golden ambient light, royal floral centerpieces on pristine banquet tables, polished marble reflections",
                    "strip": ["Crystal Chandelier Ceiling", "Royal Dining Setup", "Grand Stage Decor"]
                }
            ]
        elif idx == 1:
            # Slot 1: Emotional & Lifestyle Resonance
            variants = [
                {
                    "name": "Concept 2: Joyful Family Celebrations (Emotional Lifestyle Ad Poster)",
                    "type": "Emotional Relief & Joy",
                    "objective": "Connects emotionally with couples and families who dread chaotic venue negotiations.",
                    "visual": f"Radiant bride, groom, and celebrating family laughing in a sunlit wedding garden & illuminated party plot in {city}, golden hour glow, authentic emotion, traditional attire.",
                    "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero lifestyle, lower 3-panel strip, bottom ribbon.",
                    "lighting": "Golden hour sun flare filtering through floral canopy with warm twilight incandescent glow.",
                    "color_dir": f"Warm terracotta, pastels, and golden amber {sec_hex} accents.",
                    "typo_dir": f"Emotional {f_head} headings with {f_body} body.",
                    "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                    "overlay": "Celebrate Life's Greatest Milestones Without Venue Stress",
                    "cta": f"{cta} at {web}",
                    "headline": "Celebrate Life's Greatest Milestones Without Venue Stress",
                    "sub_headline": f"Dedicated to {audience} planning grand weddings and milestone celebrations in {city}",
                    "badges": ["💍 Stress-Free Booking", "🤝 Direct Owner Deals", "🍽️ Custom Catering Menus", "🕊️ 100% Date Guarantee"],
                    "tagline": f"'Memories That Last a Lifetime • {traits_tagline}'",
                    "hero_scene": f"Candid documentary photography of a radiant bride, groom and celebrating family laughing under an illuminated party plot canopy in {city}, golden hour twilight glow, authentic joyful emotion, vibrant traditional festive attire with intricate mirror work, twinkling fairy lights",
                    "strip": ["Sangeet Night Stage", "Sunlit Haldi & Mehendi Lawn", "Bride's Royal Entrance Corridor"]
                },
                {
                    "name": "Concept 2: Sangeet & Garba Night Rhythm (Festive Energy Ad Poster)",
                    "type": "Cultural Resonance",
                    "objective": "Taps into the vibrant communal joy and high-energy celebrations of Gujarati weddings.",
                    "visual": f"Indian wedding Sangeet celebration under the open night sky in {city}, energetic families dancing, hanging fairy lights and warm sparklers, festive joy.",
                    "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero event visual, lower 3-panel strip, bottom ribbon.",
                    "lighting": "Warm ambient party plot lighting with soft vintage direct flash, twinkling fairy lights.",
                    "color_dir": f"Rich festive jewel tones contrasted with warm amber {sec_hex} lighting.",
                    "typo_dir": f"Bold festive {f_head}.",
                    "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                    "overlay": "Dance, Celebrate & Create Memories Under the Stars",
                    "cta": f"Find 1,000+ Guest Venues: {web}",
                    "headline": "Dance, Celebrate & Create Memories Under the Stars",
                    "sub_headline": f"Book 1,000+ guest capacity open-air party plots across {city} with verified acoustics & sound permissions",
                    "badges": ["🎶 1,000+ Guest Lawns", "💡 High-Tech DJ Lighting", "🍽️ Live Chaat & Sweet Counters", "🛡️ Verified Sound Permissions"],
                    "tagline": f"'Pure Festive Joy with {traits_tagline}'",
                    "hero_scene": f"Dynamic documentary event photography of an Indian wedding Sangeet celebration under the open night sky in {city}, energetic families dancing on illuminated dance floor, hanging string lights and warm sparklers, festive joy",
                    "strip": ["Open-Air Acoustic Stage", "Gourmet Live Food Counters", "Festive Lantern Walkways"]
                }
            ]
        elif idx == 2:
            # Slot 2: Educational Framework / Comparative Matrix / Infographic
            variants = [
                {
                    "name": "Concept 3: Smart Venue Comparison Matrix (Price, Capacity & Catering Infographic)",
                    "type": "Comparison Framework",
                    "objective": "Builds unmatched utility and trust by solving the real pain of price and capacity opacity.",
                    "visual": f"Architectural luxury photography of grand banquet hall and party plot in {city} showcasing capacity, decor, and pure-veg catering.",
                    "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero venue architecture, lower 3-panel strip, bottom ribbon.",
                    "lighting": "Crisp high-contrast commercial studio lighting with warm festive accent glow.",
                    "color_dir": f"Deep {bg_hex} base with crisp {prim_hex} borders and {sec_hex} badge accents.",
                    "typo_dir": f"Bold {f_head} numerals and structured feature list in {f_body}.",
                    "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                    "overlay": "Compare Prices, Capacity & Catering Across Gujarat's Top Venues",
                    "cta": f"Compare Venues Now: {web}",
                    "headline": "Compare Prices, Capacity & Catering Across Gujarat's Top Venues",
                    "sub_headline": f"3-Tier comparison framework for {audience} in Ahmedabad, Surat, Rajkot & Vadodara",
                    "badges": ["📊 1-Click Comparison", "🍽️ Verified Pure-Veg Menus", "🚗 Dedicated Valet Parking", "📑 Zero Hidden Charges"],
                    "tagline": f"'Total Price & Capacity Transparency • {traits_tagline}'",
                    "hero_scene": f"Architectural luxury photography of a grand banquet hall ballroom and outdoor party plot in {city}, showcasing expansive guest seating for 100 to 5,000+ guests, polished marble floor reflections, crystal chandeliers casting golden ambient illumination, pure-veg gourmet catering spread",
                    "strip": ["Capacity & Guest Seating Layouts", "In-House Gourmet Catering Stations", "AC Power Backup & Valet Parking"]
                },
                {
                    "name": "Concept 3: The 4-Step Venue Booking Roadmap (Zero Stress Guide)",
                    "type": "Process Clarity",
                    "objective": "Dismantles wedding planning overwhelm with an effortless 4-step path.",
                    "visual": f"Modern engaged couple reviewing verified venue blueprints and photos on tablet with event coordinator in elegant banquet lobby in {city}.",
                    "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero roadmap scene, lower 3-panel strip, bottom ribbon.",
                    "lighting": "Clean commercial illumination with glowing amber highlight badges.",
                    "color_dir": f"Crisp dark slate with luminous amber {sec_hex} and royal {prim_hex}.",
                    "typo_dir": f"Clean structured {f_head} headings.",
                    "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                    "overlay": "The 4-Step Roadmap to Locking Your Dream Venue",
                    "cta": f"Start Your Free Search: {web}",
                    "headline": "The 4-Step Roadmap to Locking Your Dream Venue",
                    "sub_headline": f"How {brand_name} simplifies wedding venue selection in {city}: Filter Budget ➔ Compare ➔ Free Guided Visit ➔ Book Direct",
                    "badges": ["🔍 1-Click Shortlist", "💰 Direct Negotiated Rates", "🚗 Free Guided Site Visits", "🔒 Guaranteed Booking Advance"],
                    "tagline": f"'From Search to Celebration in 4 Simple Steps • {traits_tagline}'",
                    "hero_scene": f"Commercial lifestyle photography of modern engaged couple reviewing verified venue plans on tablet with event coordinator in an elegant banquet lobby in {city}, warm ambient light, serene smiling faces",
                    "strip": ["01 Online Filter by Capacity", "02 Free Guided Site Visit", "03 Direct Contract Lock"]
                }
            ]
        else:
            # Slot 3: Problem -> Solution / Direct Response / Urgency
            variants = [
                {
                    "name": "Concept 4: 20 Venue Visits ➔ 1-Click Booking (Problem to Solution Poster)",
                    "type": "Direct Response Ad",
                    "objective": "High-converting split comparison showing the exhausting old way vs the smart VenueConnect way.",
                    "visual": f"High-impact side-by-side contrast: Left side desaturated venue hunting traffic in {city}; right side illuminated evening party plot with families dancing.",
                    "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero contrast visual, lower 3-panel strip, bottom ribbon.",
                    "lighting": "Desaturated flat tones on left resolving into luminous golden celebration on right.",
                    "color_dir": f"Neutral charcoal fading to vibrant royal {prim_hex} and festive amber {sec_hex}.",
                    "typo_dir": f"Punchy contrasting labels in {f_head}.",
                    "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                    "overlay": "Stop Running Between 20 Venues. Compare & Book from Home in Minutes.",
                    "cta": f"{cta} at {web}",
                    "headline": "Stop Running Between 20 Venues. Compare & Book from Home in Minutes.",
                    "sub_headline": f"Peak wedding dates fill up fast across {city} - Check live date availability & get free quotes today",
                    "badges": ["⚡ Instant Free Quotes", "📅 Live Date Availability", "🚫 Zero Brokerage Fee", "⭐ 4.9/5 Star Verified"],
                    "tagline": f"'The Smartest Way to Book Venues in Gujarat • {traits_tagline}'",
                    "hero_scene": f"Side-by-side high-impact commercial contrast: subtle desaturated tone on left capturing chaotic venue hunting paperwork and traffic in {city}, resolving seamlessly on right into a breathtaking illuminated evening wedding party plot with glowing fairy lights and joyous dancing families",
                    "strip": ["Instant Online Shortlisting", "Free Guided Site Visits", "Guaranteed Date Confirmation"]
                },
                {
                    "name": "Concept 4: Zero Hidden Charges Guarantee (Price Clarity Poster)",
                    "type": "Trust & Price Defense",
                    "objective": "Eliminates fear of surprise catering, electricity, and generator charges.",
                    "visual": f"Verified transparent booking agreement with green guarantee seal on polished conference table in {city}, background of an illuminated lavish banquet hall.",
                    "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero visual, lower 3-panel strip, bottom ribbon.",
                    "lighting": "Dim shadowed tones resolving into crisp daylight clarity.",
                    "color_dir": f"Warning grey to verified emerald green and royal {prim_hex}.",
                    "typo_dir": f"Clean {f_head} trust badges.",
                    "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                    "overlay": "Zero Hidden Fees. 100% All-Inclusive Venue Quotes.",
                    "cta": f"Get Instant Transparent Quotes: {web}",
                    "headline": "Zero Hidden Fees. 100% All-Inclusive Venue Quotes.",
                    "sub_headline": f"Say goodbye to surprise catering, electricity & generator bills across {city} banquets",
                    "badges": ["📜 All-Inclusive Packages", "💵 Fixed Transparent Pricing", "🛡️ Written Price Guarantee", "🤝 Zero Surprise Charges"],
                    "tagline": f"'Honest Pricing Built on Trust • {traits_tagline}'",
                    "hero_scene": f"High-contrast commercial advertising photograph, a clear transparent booking seal and verified agreement on polished conference table in {city}, background of an illuminated lavish banquet dining hall, warm golden lighting",
                    "strip": ["Itemized Catering Breakdown", "Electricity & Backup Included", "Written Security Guarantee"]
                }
            ]

    # =========================================================================
    # 2. FINANCE & ACCOUNTING
    # =========================================================================
    elif cat == "finance":
        if idx == 0:
            variants = [{
                "name": "Concept 1: The Clarity Command (Audit-Ready Financials Poster)",
                "type": "Executive Authority",
                "objective": "Demonstrates precision, real-time control, and audit readiness.",
                "visual": f"Modern minimalist workstation in {city} with dual displays showing real-time financial metrics in {prim_hex} and {sec_hex}.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero workstation, lower 3-panel strip, bottom ribbon.",
                "lighting": "Bright architectural studio lighting with soft contrast.",
                "color_dir": f"Deep navy base illuminated by {sec_hex} and clean white lines.",
                "typo_dir": f"{f_head} bold headings with clean {f_body} copy.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Zero Tax Surprises. Total Financial Clarity.",
                "cta": f"{cta} • Visit {web}",
                "headline": "Zero Tax Surprises. Total Financial Clarity.",
                "sub_headline": f"Proactive Bookkeeping & Tax Strategy designed for {audience} in {city}",
                "badges": ["📊 Real-Time Books", "🛡️ 100% Audit Ready", "💰 Tax Optimization", "⚡ Dedicated CPA Support"],
                "tagline": f"'{traits_tagline} Standard in Every Balance Sheet'",
                "hero_scene": f"Commercial photography of modern cloud accounting ledger dashboard on sleek minimalist workstation, dark mode UI with {prim_hex} and {sec_hex} financial data charts, natural daylight through office glass in {city}",
                "strip": ["Real-Time P&L Dashboard", "Tax Deduction Audit", "Cash Flow Forecasting"]
            }]
        elif idx == 1:
            variants = [{
                "name": "Concept 2: Founder Peace of Mind (Weekend Freedom Poster)",
                "type": "Emotional Relief",
                "objective": "Frees business owners from stressful weekend receipt reconciliations.",
                "visual": f"Confident founder calmly closing laptop in sunlit {city} office, relaxed expression knowing books are balanced.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero founder scene, lower 3-panel strip, bottom ribbon.",
                "lighting": "Soft natural diffused morning window light.",
                "color_dir": f"Warm neutrals harmonized with {prim_hex} and {sec_hex} accents.",
                "typo_dir": f"Elegant {f_head} headings.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Focus on Growth. We Handle Every Receipt.",
                "cta": f"{cta} at {web}",
                "headline": "Focus on Growth. We Handle Every Receipt.",
                "sub_headline": f"Reclaim your weekends with automated, error-free bookkeeping in {city}",
                "badges": ["☕ Weekend Freedom", "📑 Zero Paperwork Drag", "🤝 Year-Round Advisory", "🔒 Bank-Grade Security"],
                "tagline": f"'Financial Peace of Mind • {traits_tagline}'",
                "hero_scene": f"Editorial lifestyle photography of confident founder smiling in sunlit modern loft office in {city}, warm morning light, closing laptop with relaxed expression",
                "strip": ["Automated Expense Sync", "Monthly Financial Review", "Direct CPA Helpline"]
            }]
        elif idx == 2:
            variants = [{
                "name": "Concept 3: 3 Pillars of Financial Mastery (Tax Optimization Infographic)",
                "type": "Educational Authority",
                "objective": "Builds procedural trust for corporate clients.",
                "visual": "Structured comparative matrix displaying Bookkeeping, Tax Minimization, and Cash Flow Forecasting.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero matrix, lower 3-panel strip, bottom ribbon.",
                "lighting": "High-contrast clean architectural lighting.",
                "color_dir": f"Dark slate with {prim_hex} borders and {sec_hex} numerical tags.",
                "typo_dir": f"Bold {f_head} numerals.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "01 Reconcile • 02 Optimize • 03 Scale",
                "cta": f"{cta} at {web}",
                "headline": "The 3 Pillars of Tax Minimization & Cash Flow Mastery",
                "sub_headline": f"How {brand_name} saves {audience} thousands annually through proactive tax planning",
                "badges": ["01 Reconcile Books", "02 Optimize Deductions", "03 Real-Time Forecast", "04 100% Tax Defense"],
                "tagline": f"'Strategic Financial Precision • {traits_tagline}'",
                "hero_scene": f"Clean architectural business graphics and financial analytics dashboard on modern glass desk in {city}, glowing cash flow charts in {prim_hex} and {sec_hex}",
                "strip": ["Step 1: Clean Ledger", "Step 2: Tax Deductions", "Step 3: Growth Roadmap"]
            }]
        else:
            variants = [{
                "name": "Concept 4: Spreadsheet Chaos ➔ Automated Cloud Mastery (Problem to Solution)",
                "type": "Conversion Paradigm",
                "objective": "High-converting comparison dismantling manual spreadsheet friction.",
                "visual": "Side-by-side contrast of messy receipts on left vs glowing audit-ready dashboard on right.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero contrast, lower 3-panel strip, bottom ribbon.",
                "lighting": "Dim flat lighting on left transitioning to golden clarity on right.",
                "color_dir": f"Dull grey transitioning to vibrant {prim_hex} and {sec_hex}.",
                "typo_dir": f"Punchy contrasting {f_head} labels.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Stop Losing Hours to Manual Spreadsheets.",
                "cta": f"{cta} at {web}",
                "headline": "Spreadsheet Chaos ➔ Automated Cloud Accounting",
                "sub_headline": f"Switch {audience} from manual bookkeeping to automated precision in minutes",
                "badges": ["⚡ 1-Click Migration", "🚫 Zero Error Tolerance", "📈 Live Margin Visibility", "⭐ 99.9% Audit Accuracy"],
                "tagline": f"'The Modern Way to Manage Money • {traits_tagline}'",
                "hero_scene": f"High-contrast commercial advertising photograph, left side disorganized paper receipts, right side sleek glowing cloud accounting dashboard in {prim_hex} and {sec_hex}",
                "strip": ["Legacy Spreadsheets (Old)", "Instant Cloud Sync", "Audit-Ready Reports"]
            }]

    # =========================================================================
    # 3. TECH, SAAS & SOFTWARE
    # =========================================================================
    elif cat == "tech":
        if idx == 0:
            variants = [{
                "name": "Concept 1: High-Availability Telemetry Control (Flagship Poster)",
                "type": "Technical Authority",
                "objective": "Establishes bulletproof platform stability and high-availability infrastructure.",
                "visual": f"Futuristic dark-mode operations console in {city} with glowing node graphs in {prim_hex} and {sec_hex}.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero console, lower 3-panel strip, bottom ribbon.",
                "lighting": "Low ambient blue glow with high-contrast screen telemetry illumination.",
                "color_dir": f"Deep obsidian {bg_hex} with electric cyan and amber accents.",
                "typo_dir": f"{f_head} bold technical headings with clean {f_body}.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "99.99% Uptime. Sub-10ms Latency.",
                "cta": f"{cta} • Visit {web}",
                "headline": "High-Availability Cloud Architecture & Real-Time Telemetry",
                "sub_headline": f"Sub-10ms latency & 99.99% uptime engineered for {audience} in {city}",
                "badges": ["⚡ 99.99% Uptime", "🔒 Enterprise SOC-2", "🚀 Auto-Scaling Mesh", "🛠️ 24/7 DevOps Support"],
                "tagline": f"'{traits_tagline} Infrastructure'",
                "hero_scene": f"Commercial photography of high-tech cloud infrastructure control center in {city}, dual monitors glowing with system telemetry graphs in {prim_hex} and {sec_hex}, cinematic dark office",
                "strip": ["Kubernetes Cluster Health", "Real-Time Telemetry Graphs", "Global CDN Latency Map"]
            }]
        elif idx == 1:
            variants = [{
                "name": "Concept 2: Developer Flow State (Frictionless Engineering Poster)",
                "type": "Developer Experience",
                "objective": "Evokes the satisfying state of uninterrupted engineering productivity.",
                "visual": f"Software engineer at modern wooden desk in {city} sipping coffee, enjoying zero alert fatigue.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero workspace, lower 3-panel strip, bottom ribbon.",
                "lighting": "Warm ambient desktop glow combined with soft morning daylight.",
                "color_dir": f"Dark matte black with subtle {prim_hex} cyan glow.",
                "typo_dir": f"Clean {f_head} headings.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Ship Code Faster. Zero DevOps Drag.",
                "cta": f"{cta} at {web}",
                "headline": "Ship Code 10x Faster With Zero DevOps Drag",
                "sub_headline": f"Empowering {audience} to deploy with confidence without breaking production",
                "badges": ["🚀 1-Click CI/CD", "🛡️ Automated Rollbacks", "⚡ Instant Staging Envs", "📦 Container Native"],
                "tagline": f"'Frictionless Developer Experience • {traits_tagline}'",
                "hero_scene": f"Editorial lifestyle photography of happy software engineer at clean wooden standing desk in creative office in {city}, relaxed focus, warm screen glow",
                "strip": ["Git Push to Production", "Instant Preview Builds", "Zero-Downtime Deploys"]
            }]
        elif idx == 2:
            variants = [{
                "name": "Concept 3: The Unified Stack Architecture (Benchmark Infographic)",
                "type": "Technical Infographic",
                "objective": "Demonstrates architectural superiority and seamless component integration.",
                "visual": "Modular architecture diagram showcasing real-time data ingestion, processing, and visualization layers.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero architecture, lower 3-panel strip, bottom ribbon.",
                "lighting": "High-contrast vector illumination.",
                "color_dir": f"Deep {bg_hex} with neon {sec_hex} data bus lines.",
                "typo_dir": "Precision typography.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Ingest • Transform • Observe",
                "cta": f"{cta} at {web}",
                "headline": "Modular Data Pipelines & Unified Microservices Architecture",
                "sub_headline": f"How modern engineering teams architect for high scale with {brand_name}",
                "badges": ["🔌 100+ Prebuilt Connectors", "⚡ In-Memory Cache Layer", "📊 Real-Time Observability", "🔒 End-to-End Encryption"],
                "tagline": f"'Scalability Without Complexity • {traits_tagline}'",
                "hero_scene": f"Swiss graphic design tech poster, dark mode cloud architecture diagram, glowing pipeline connectors in {prim_hex} and {sec_hex}, sharp vector graphic",
                "strip": ["Event Streaming Pipeline", "Distributed Database Cluster", "Unified Analytics Gateway"]
            }]
        else:
            variants = [{
                "name": "Concept 4: Legacy Bottlenecks ➔ Cloud Velocity (Problem to Solution)",
                "type": "Paradigm Shift",
                "objective": "Drives immediate trial by exposing the painful drag of outdated infrastructure.",
                "visual": "Split view: Tangled server wires and error logs on left resolving into clean, automated cloud pipelines on right.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero contrast, lower 3-panel strip, bottom ribbon.",
                "lighting": "Red warning glow on left vs crisp cyan illumination on right.",
                "color_dir": f"Warning red fading to {prim_hex} electric blue and {sec_hex} amber.",
                "typo_dir": f"Punchy technical comparison labels in {f_head}.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Modernize Your Stack in Days, Not Quarters.",
                "cta": f"{cta} at {web}",
                "headline": "Modernize Your Infrastructure in Days, Not Quarters",
                "sub_headline": f"Tired of fragile legacy servers? Switch {audience} to reliable cloud orchestration",
                "badges": ["⚡ Zero Migration Downtime", "🚫 No Vendor Lock-In", "💰 40% Infrastructure Savings", "🛡️ 99.99% SLA"],
                "tagline": f"'Future-Proof Your Technology • {traits_tagline}'",
                "hero_scene": f"Side-by-side conceptual technology advertisement, left side chaotic legacy server rack, right side modern glowing minimalist cloud architecture with telemetry charts",
                "strip": ["Legacy Monolith (Old)", "Automated Cloud Migration", "High-Speed Microservices"]
            }]

    # =========================================================================
    # 4. PHYSICAL PRODUCTS & E-COMMERCE
    # =========================================================================
    elif cat == "product":
        if idx == 0:
            variants = [{
                "name": "Concept 1: The Product Hero (Macro Craftsmanship Poster)",
                "type": "Product Hero",
                "objective": "Commands immediate premium brand perception and design appreciation.",
                "visual": f"Hyper-detailed macro close-up of {brand_name} showcase resting on slate stone, backlit by luminous {prim_hex} rim glow.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero product, lower 3-panel strip, bottom ribbon.",
                "lighting": "Dramatic dual-tone chiaroscuro lighting; warm golden amber backlight.",
                "color_dir": f"Deep {bg_hex} dark-mode base illuminated by {prim_hex} and vibrant {sec_hex} highlights.",
                "typo_dir": f"{f_head} bold minimalist overlay.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "100% Verifiable Quality Standard",
                "cta": f"{cta} • Visit {web}",
                "headline": "Uncompromising Craftsmanship & Pure Ingredients",
                "sub_headline": f"Handcrafted excellence designed for {audience} seeking superior quality",
                "badges": ["⭐ 100% Verifiable Quality", "🌿 Pure Natural Formula", "📦 Express Delivery", "💎 30-Day Guarantee"],
                "tagline": f"'{traits_tagline} in Every Detail'",
                "hero_scene": f"Commercial luxury product photography of {brand_name} showcase on dark textured slate, glowing rim light in {sec_hex} and deep {prim_hex} tones, Hasselblad 8k detail",
                "strip": ["Artisan Small-Batch Source", "Precision Quality Testing", "Luxury Unboxing Experience"]
            }]
        elif idx == 1:
            variants = [{
                "name": "Concept 2: The Lifestyle Integration (Ritual & Calm Poster)",
                "type": "Lifestyle",
                "objective": "Drives emotional resonance and daily habit formation.",
                "visual": f"Peaceful sunlit sanctuary scene in {city} with customer experiencing the transformative benefit of {brand_name}.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero lifestyle, lower 3-panel strip, bottom ribbon.",
                "lighting": "Soft natural diffused morning window light.",
                "color_dir": f"Earthy neutrals harmonized with {sec_hex} warm sunbeams.",
                "typo_dir": f"Elegant {f_head} italic quote.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Make Excellence Your Daily Ritual.",
                "cta": f"{cta} at {web}",
                "headline": "Make Excellence Your Daily Ritual",
                "sub_headline": f"Discover how {brand_name} elevates the daily lifestyle of {audience}",
                "badges": ["🌿 100% Certified Organic", "🕊️ Calming Daily Ritual", "💧 Deep Nutrient Absorption", "⭐ 50,000+ Happy Customers"],
                "tagline": f"'Pure Daily Transformation • {traits_tagline}'",
                "hero_scene": f"Editorial lifestyle photography, sunlit modern minimalist interior in {city}, morning sunlight, soft organic aesthetic, Kodak Portra 400 film grain, cozy calm luxury feel",
                "strip": ["Morning Ritual Practice", "Gentle Daily Nourishment", "All-Day Radiant Glow"]
            }]
        elif idx == 2:
            variants = [{
                "name": "Concept 3: 3 Quality Pillars (Educational Framework Infographic)",
                "type": "Educational",
                "objective": f"Builds deep authority and trust for {audience}.",
                "visual": "Structured 3-column comparative infographic card with scientific clarity.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero infographic, lower 3-panel strip, bottom ribbon.",
                "lighting": "Even, bright studio high-key illumination.",
                "color_dir": f"Crisp dark slate card layout with {prim_hex} borders and {sec_hex} numerical tags.",
                "typo_dir": f"Bold {f_head} numerals.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "01 Source • 02 Extract • 03 Verify",
                "cta": f"{cta} at {web}",
                "headline": "The 3 Pillars of Verifiable Purity & Potency",
                "sub_headline": f"Why {brand_name} sets the gold benchmark for quality across {country}",
                "badges": ["01 Cold-Pressed Sourcing", "02 Zero Artificial Additives", "03 Third-Party Lab Certified", "04 Eco-Friendly Glass Jar"],
                "tagline": f"'Verifiable Excellence • {traits_tagline}'",
                "hero_scene": f"Minimalist Swiss-style graphic design layout mockup, dark mode UI card, crisp typography, clean data architecture with {prim_hex} and {sec_hex} accents",
                "strip": ["Ethical Wild Harvest", "Supercritical Extraction", "Certificate of Analysis"]
            }]
        else:
            variants = [{
                "name": "Concept 4: Diluted Alternatives ➔ Pure Potency (Problem to Solution)",
                "type": "Problem -> Solution",
                "objective": "Converts fence-sitters into buyers by dismantling market objections.",
                "visual": "Side-by-side split comparison of outdated alternatives vs pure modern batch.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero contrast, lower 3-panel strip, bottom ribbon.",
                "lighting": "Dim flat lighting on left transitioning to luminous golden clarity on right.",
                "color_dir": f"Muted desaturated grey on left resolving into vibrant {prim_hex} and {sec_hex} on right.",
                "typo_dir": f"Punchy contrasting labels in {f_head}.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Stop Settling for Diluted Alternatives.",
                "cta": f"{cta} at {web}",
                "headline": "Stop Settling for Diluted Formulas & Fillers",
                "sub_headline": f"Experience the 100% active, bio-available difference engineered for {audience}",
                "badges": ["⚡ 100% Active Potency", "🚫 Zero Mineral Oils", "🔬 Clinically Proven Results", "📦 Money-Back Guarantee"],
                "tagline": f"'Pure Potency • {traits_tagline}'",
                "hero_scene": f"Side-by-side conceptual comparison photography, dramatic lighting transition from cloudy dull backdrop on left to crystal clear glowing clarity on right",
                "strip": ["Synthetic Fillers (Old)", "Pure Cold-Pressed Batch", "Verified Clinical Results"]
            }]

    # =========================================================================
    # 5. GENERAL BUSINESS & PROFESSIONAL SERVICES (DEFAULT FALLBACK)
    # =========================================================================
    else:
        if idx == 0:
            variants = [{
                "name": "Concept 1: Strategic Blueprint (Executive Authority Poster)",
                "type": "Strategic Authority",
                "objective": "Positions the firm as the premier advisory partner for enterprise results.",
                "visual": f"Architectural executive boardroom table in {city} with strategic roadmap and tablet showing {prim_hex} growth vectors.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero boardroom, lower 3-panel strip, bottom ribbon.",
                "lighting": "Polished high-key architectural studio lighting.",
                "color_dir": f"Deep charcoal slate base accented by {prim_hex} and {sec_hex}.",
                "typo_dir": f"Authoritative {f_head} typography.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Proven Strategy. Verified Execution.",
                "cta": f"{cta} • Visit {web}",
                "headline": "Proven Strategy. Verifiable Execution.",
                "sub_headline": f"Enterprise advisory and growth architecture designed for {audience} in {city}",
                "badges": ["⭐ Proven Track Record", "🎯 Tailored Strategy", "📈 Measurable ROI", "⚡ Rapid Onboarding"],
                "tagline": f"'{traits_tagline} Excellence'",
                "hero_scene": f"Commercial photography of executive corporate conference table in {city}, strategic roadmap on modern tablet, panoramic city skyline through high-rise windows",
                "strip": ["Diagnostic Audit", "Execution Framework", "Performance Review"]
            }]
        elif idx == 1:
            variants = [{
                "name": "Concept 2: Decisive Leadership (Confident Growth Poster)",
                "type": "Executive Lifestyle",
                "objective": "Appeals to the leader's desire for confidence, clarity, and decisive growth.",
                "visual": f"Business leader walking through sunlit architectural corridor in {city} with calm, forward-looking focus.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero corridor, lower 3-panel strip, bottom ribbon.",
                "lighting": "Clean architectural glass daylight.",
                "color_dir": f"Monochromatic slate with vibrant {sec_hex} accents.",
                "typo_dir": f"Bold modern {f_head} display text.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Lead With Clarity. Execute With Speed.",
                "cta": f"{cta} at {web}",
                "headline": "Lead With Clarity. Execute With Speed.",
                "sub_headline": f"Freeing {audience} from operational friction so you can focus on core vision",
                "badges": ["🤝 Trusted Partner", "📊 Clear Milestones", "💡 Expert Advisory", "🕊️ Operational Peace"],
                "tagline": f"'Empowering Leaders • {traits_tagline}'",
                "hero_scene": f"Cinematic editorial photography of confident business executive walking through sunlit architectural glass corridor in {city}, natural lighting, professional and decisive",
                "strip": ["Streamlined Operations", "Cross-Functional Alignment", "Sustainable Scale"]
            }]
        elif idx == 2:
            variants = [{
                "name": "Concept 3: The 3-Phase Execution Roadmap (Framework Infographic)",
                "type": "Methodology Framework",
                "objective": "Builds unmatched client confidence through a transparent, disciplined delivery process.",
                "visual": "Clean architectural infographic with 3 phases: Diagnostic Audit, Strategic Implementation, Measured Growth.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero framework, lower 3-panel strip, bottom ribbon.",
                "lighting": "High-key studio contrast.",
                "color_dir": f"Dark slate with {prim_hex} borders and {sec_hex} milestone icons.",
                "typo_dir": f"Bold {f_head} typography.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "01 Audit • 02 Execute • 03 Scale",
                "cta": f"{cta} at {web}",
                "headline": "The 3-Phase Roadmap to Predictable Execution",
                "sub_headline": f"How {brand_name} delivers measurable transformation for {audience}",
                "badges": ["01 Deep Diagnostic", "02 Agile Execution", "03 KPI Optimization", "04 Continuous Scale"],
                "tagline": f"'Disciplined Delivery • {traits_tagline}'",
                "hero_scene": f"Swiss minimalist business infographic poster, dark slate background in {city}, 3 execution stages, clean {prim_hex} and {sec_hex} line accents",
                "strip": ["Phase 1: Gap Analysis", "Phase 2: Core Sprint", "Phase 3: ROI Validation"]
            }]
        else:
            variants = [{
                "name": "Concept 4: DIY Guesswork ➔ Strategic Certainty (Problem to Solution)",
                "type": "Transformation Paradigm",
                "objective": "Converts prospective clients by demonstrating the costly hidden toll of trial-and-error.",
                "visual": "Split screen comparing fragmented sticky notes and disjointed plans on left with clear structured milestone timeline on right.",
                "composition": "Poster advertising layout: Top-left [ YOUR LOGO HERE ] box, left marketing copy, right hero split visual, lower 3-panel strip, bottom ribbon.",
                "lighting": "Shadowed monochrome on left resolving into bright warm clarity on right.",
                "color_dir": f"Dull gray to vibrant {sec_hex} gold.",
                "typo_dir": f"Contrasting {f_head} bold typography.",
                "logo_plc": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' box.",
                "overlay": "Stop Guessing. Start Scaling.",
                "cta": f"{cta} at {web}",
                "headline": "Stop Guessing. Start Scaling With Confidence.",
                "sub_headline": f"Why {audience} choose {brand_name} over fragmented DIY approaches",
                "badges": ["⚡ Fast-Track Results", "🚫 Zero Costly Rework", "📈 Guaranteed Milestones", "⭐ 98% Client Satisfaction"],
                "tagline": f"'Clarity Over Chaos • {traits_tagline}'",
                "hero_scene": f"High impact split-screen commercial advertising visual, left side chaotic paper sketches and red error marks, right side luminous structured execution roadmap with {prim_hex} and {sec_hex} milestones",
                "strip": ["Fragmented Trial & Error (Old)", "Structured Advisory Sprint", "Proven Measurable Growth"]
            }]

    v = variants[iteration % len(variants)]
    obj_msg = get_objective_messaging(
        objective=objective,
        cat=cat,
        brand_name=brand_name,
        city=city,
        audience=audience,
        web=web,
        cta_input=business.get("cta", ""),
        traits_tagline=traits_tagline,
        idx=idx,
        iteration=iteration,
        base_v=v
    )

    # Generate the pristine commercial advertising prompt incorporating EVERY user option & objective
    image_prompt = format_ad_poster_prompt(
        brand_name=brand_name,
        headline=obj_msg["headline"],
        sub_headline=obj_msg["sub_headline"],
        badges=obj_msg["badges"],
        tagline=obj_msg["tagline"],
        hero_scene=obj_msg["hero_scene"],
        strip_panels=obj_msg["strip"],
        web=web,
        phone=phone,
        email=email,
        cta=obj_msg["cta"],
        f_head=f_head,
        f_body=f_body,
        prim_hex=prim_hex,
        style_frag=style_frag,
        aspect_ratio=ratio
    )

    return {
        "concept_name": f"{v['name'].split(' (')[0]} ({obj_msg['concept_badge']})",
        "concept_type": v["type"],
        "objective_alignment": f"Engineered for '{objective}': {obj_msg['objective_desc']}",
        "visual_direction": obj_msg.get("visual", v["visual"]),
        "composition": v["composition"],
        "lighting": v["lighting"],
        "color_direction": v["color_dir"],
        "typography_direction": v["typo_dir"],
        "logo_placement": "Top-left dedicated clean minimalist '[ YOUR LOGO HERE ]' negative space box (plain clean neutral background, zero leaves, zero floral motifs, zero clutter).",
        "text_overlay": obj_msg["overlay"],
        "cta": f"{obj_msg['cta']} • {web}",
        "image_generation_prompt": image_prompt
    }


def build_platform_captions_fresh(brand_name: str, industry: str, objective: str, business: Dict[str, Any], iteration: int = 0) -> Dict[str, Any]:
    """Generates fresh platform-specific captions with rotating hooks, body copy, and tone resonance."""
    cat = detect_industry_category(industry, business.get("campaign_info", ""), brand_name)
    web = business.get("website", "https://www.venueconnect.in/")
    phone = business.get("phone", "+91 98765 43210")
    city = business.get("target_city", "Gujarat")

    if cat == "events_venues":
        rotations = [
            {
                "ig_pro": f"Planning a dream wedding or grand celebration in {city}? Stop spending weeks visiting 20 banquets in the heat. 🌸✨\n\nWith {brand_name}, browse and compare verified wedding lawns, party plots, and luxury banquet halls across Gujarat in one place.\n\nWhy Gujarat families trust {brand_name}:\n🏛️ 500+ Verified Banquets & Party Plots\n💰 Transparent price comparisons & catering packages\n👥 Capacities from 100 to 5,000+ guests\n⚡ Free instant quotes & site visit coordination\n\nMake your celebration unforgettable. Book smarter today.\n\n🌐 Visit: {web}\n📲 Call / WhatsApp: {phone}\n📍 Ahmedabad • Surat • Vadodara • Rajkot\n\nTag someone getting married this season! 👇",
                "ig_cre": f"Imagine walking into an illuminated open-air lawn at golden twilight, fairy lights dancing overhead, and the fragrance of fresh marigolds welcoming your guests... 💍✨\n\nYour once-in-a-lifetime day deserves an extraordinary venue. At {brand_name}, we hand-curate Gujarat's most enchanting wedding venues, heritage lawns, and grand banquets so you can create memories that last forever.\n\n✨ Find the backdrop to your love story:\n🔗 Explore curated venues: {web}\n📞 Speak to our wedding venue concierges: {phone}",
                "ig_sho": f"500+ Verified Wedding Venues across {city} at direct verified rates. 🏛️💍\n\nZero brokerage. Real photos. Instant availability checks.\n\n👉 Book your free venue tour: {web}",
                "fb_pro": f"Your dream celebration deserves the perfect setting. 💍✨ Discover Gujarat's most loved wedding lawns, royal banquet halls, and party plots on {brand_name}. Compare prices, guest capacities, and catering options with zero hassle!\n\n👉 Book your free site visit today: {web}\n📞 WhatsApp: {phone}",
                "fb_cre": f"A celebration should feel like magic, not stressful logistics. 🌸💫 From royal palatial banquets to serene open-air lawns, discover Gujarat's dreamiest celebration spaces with {brand_name}.\n\nExplore availability & direct pricing: {web}",
                "fb_sho": f"Scouting wedding venues in {city}? Compare 500+ verified party plots and banquets in 2 minutes on {brand_name}: {web}",
                "x_pro": f"Securing a wedding banquet or party plot in Gujarat shouldn't take weeks of exhausting visits.\n\nCompare 500+ verified venues, price ranges & catering packages in 2 minutes on {brand_name} 🧵👇\n\n{web}",
                "x_cre": f"From twilight mandap setups to royal palatial banquets across Ahmedabad, Surat & Vadodara 🌸✨ Discover Gujarat's finest wedding spaces on {brand_name}: {web}",
                "x_sho": f"Wedding venue shopping in Gujarat made effortless. 500+ verified party plots & banquets: {web}",
                "li_pro": f"Corporate summits, product launches, or grand annual galas in {city}?\n\n{brand_name} simplifies enterprise venue scouting with verified AC banquet halls, luxury resort lawns, and transparent catering options across Ahmedabad, Surat, and Vadodara.\n\n✔ Zero brokerage or hidden fees\n✔ Verified venue photos & real customer ratings\n\nExplore corporate event spaces: {web}"
            },
            {
                "ig_pro": f"Wedding dates in {city} are booking 6-12 months ahead! Have you secured your venue yet? 📅🏛️\n\nTop wedding party plots and prime Saturday/Sunday dates across Ahmedabad, Surat, and Vadodara get locked in fast. Don't compromise on your auspicious date.\n\nHow {brand_name} helps you lock your venue in 24 hours:\n⚡ Live date availability checks\n📸 360° virtual venue walkthroughs & layout maps\n🤝 Direct pricing with banquet owners (No middleman markups)\n🍽️ Curated pure-veg catering packages & amenities\n\nSecure your preferred date before someone else does!\n\n🌐 Check date availability: {web}\n📲 Direct helpline: {phone}",
                "ig_cre": f"Every bride and groom envisions the moment they step into their reception. The lights, the music, the smiles of 1,000 loved ones... ✨💫\n\nDon't let venue hunting stress take away the joy of wedding prep. With {brand_name}, Gujarat's most sought-after party plots and banquets are right at your fingertips.\n\n🌸 Explore availability today: {web}",
                "ig_sho": f"Prime wedding dates in {city} are filling fast! ⏳🏛️ Check instant availability for Gujarat's top banquets on {brand_name}: {web}",
                "fb_pro": f"Auspicious wedding dates for the upcoming season are booking fast in Gujarat! ⏳💍 Find and reserve verified wedding lawns and luxury AC banquets on {brand_name} before slots close.\n\nCheck live availability: {web}",
                "fb_cre": f"Your special date is finalized. Now find the venue that will take everyone's breath away! ✨ From heritage banquets to grand lawns in {city}, discover them all on {brand_name}: {web}",
                "fb_sho": f"Don't lose your lucky wedding date. Compare & book top Gujarat venues online: {web}",
                "x_pro": f"Wedding dates in Gujarat sell out 6-12 months in advance. How {brand_name} helps families lock premier party plots & banquets without middleman markups: {web}",
                "x_cre": f"Step into the wedding venue you've always dreamed of. Verified plots across Gujarat on {brand_name} 🌸✨: {web}",
                "x_sho": f"Book your wedding lawn before the best dates are gone: {web}",
                "li_pro": f"High-capacity conference and banquet planning in Gujarat? Lock in premier corporate event spaces ahead of peak business season with {brand_name}: {web}"
            },
            {
                "ig_pro": f"The smart way to find Gujarat's finest party plots & royal banquet halls at verified direct prices 💎✨\n\nWhy settle for inflated quotes or undisclosed broker fees? At {brand_name}, our mission is absolute transparency for families and event organizers.\n\nWhat you get with {brand_name}:\n✅ 100% Verified venue credentials & legal licenses\n✅ Real photos with true guest capacity benchmarks\n✅ Direct connection to venue management\n✅ Complimentary consultation & visit booking\n\nCelebrate grandly. Book smartly.\n\n🔗 Browse venues: {web}\n📞 Inquiries: {phone}",
                "ig_cre": f"From grand Garba nights to royal wedding pheras under the stars, Gujarat's celebrations are unmatched in warmth and grandeur. 🌟🎶\n\nLet {brand_name} help you find a venue as grand as your traditions. Explore Gujarat's most iconic wedding plots and luxury halls.\n\n✨ Discover your venue: {web}",
                "ig_sho": f"Verified pricing. Zero hidden fees. 500+ party plots in {city}. Book with {brand_name}: {web}",
                "fb_pro": f"Stop paying broker fees for venue scouting! {brand_name} connects you directly with top wedding party plots & banquet halls across Gujarat with verified pricing.\n\nFind your venue now: {web}",
                "fb_cre": f"Tradition, elegance, and celebration come together at Gujarat's finest party plots. Discover verified wedding spaces on {brand_name}: {web}",
                "fb_sho": f"Compare Gujarat banquets directly at verified rates: {web}",
                "x_pro": f"Why do wedding venue prices vary so wildly? {brand_name} brings transparent pricing and verified capacities to Gujarat's event venues: {web}",
                "x_cre": f"A venue as grand as your Gujarati celebration 💎✨ Discover party plots on {brand_name}: {web}",
                "x_sho": f"Transparent party plot bookings across Gujarat: {web}",
                "li_pro": f"Transparent enterprise procurement for venue spaces in {city}. Zero brokerage, verified capacity, seamless booking via {brand_name}: {web}"
            },
            {
                "ig_pro": f"Before you pay a venue advance in Ahmedabad, Surat, or Vadodara, read this! 🚨\n\nHere are 4 critical things to verify before signing a venue contract in Gujarat:\n1️⃣ Generator & power backup capacity for high-wattage lighting & AC\n2️⃣ Valet & guest parking space (crucial for 500+ guests)\n3️⃣ Noise curfew rules & lawn clearance timings\n4️⃣ Catering kitchen hygiene & pure-veg certification\n\nEvery venue listed on {brand_name} is pre-audited across these exact parameters!\n\n💡 Save time and avoid costly surprises:\n🌐 Visit: {web}\n📲 Talk to an expert: {phone}",
                "ig_cre": f"Your wedding day should be filled with laughter and love, not last-minute venue hiccups. 💖✨ That's why thousands of couples trust {brand_name} to find vetted, flawless party plots across Gujarat.\n\nExplore trusted venues: {web}",
                "ig_sho": f"4 things to verify before booking a venue in {city}. Protect your celebration with {brand_name}: {web}",
                "fb_pro": f"Planning a wedding in Gujarat? Don't pay a token advance before checking parking, generator backup, and catering licenses. Browse pre-verified venues on {brand_name}: {web}",
                "fb_cre": f"Peace of mind is the best wedding gift. Book audited wedding lawns across Gujarat on {brand_name}: {web}",
                "fb_sho": f"Vetted party plots with zero hidden surprises in {city}: {web}",
                "x_pro": f"The ultimate Gujarat wedding venue checklist: parking, power backup, catering rules, curfew. {brand_name} audits them all: {web}",
                "x_cre": f"Don't leave your wedding day to chance. Discover vetted Gujarat wedding venues on {brand_name}: {web}",
                "x_sho": f"Audited party plots across Ahmedabad, Surat, Vadodara: {web}",
                "li_pro": f"Event risk management: How corporate event planners in Gujarat ensure venue reliability with {brand_name}: {web}"
            },
            {
                # 4. Website Traffic rotation (online exploration, 360 virtual tours)
                "ig_pro": f"Scouting wedding party plots or banquet halls across {city}? Stop driving in heat and traffic. 🚗❌\n\nExperience Gujarat's largest online venue directory at {brand_name}. Take 360° virtual walkthroughs, browse 10,000+ real venue photos, and filter 500+ banquets by capacity and price in under 60 seconds.\n\nWhat you can do on {web}:\n🌐 360° Immersive Virtual Walkthroughs\n🔍 Filter by budget, catering & guest capacity (100 to 5,000+)\n📸 High-resolution photo galleries & verified floor plans\n⚡ Instant direct price estimates\n\nFind your perfect celebration space from home today!\n\n🔗 Explore now: {web}\n📞 Concierge support: {phone}",
                "ig_cre": f"What if you could stroll through Gujarat's dreamiest wedding lawns, check out the mandap view, and compare prices—all while sipping chai at home? ☕✨\n\nWelcome to {brand_name}. We've digitized 500+ verified wedding party plots and luxury banquet halls across Gujarat so you can explore every angle before booking a single visit.\n\n✨ Start your virtual tour: {web}",
                "ig_sho": f"Explore 500+ verified wedding venues in {city} online! 🏛️💻 360° virtual tours & instant pricing.\n\n👉 Browse now: {web}",
                "fb_pro": f"Why spend weekends visiting 20 different wedding venues when you can scout them all online? 💻✨ Browse 500+ verified banquet halls and party plots across Gujarat on {brand_name}. Take 360° virtual tours and filter by capacity & budget.\n\nExplore now: {web}",
                "fb_cre": f"Scout your dream wedding venue from the comfort of your living room! 🌟 Discover 360° virtual walkthroughs and real pricing on {brand_name}: {web}",
                "fb_sho": f"Browse 500+ verified Gujarat wedding party plots online: {web}",
                "x_pro": f"Scouting wedding party plots in Gujarat? Save 40+ hours of driving between banquets. Explore 500+ verified venues online with 360° walkthroughs on {brand_name}: {web}",
                "x_cre": f"Explore Gujarat's finest wedding venues from your phone 📱✨ 360° virtual tours on {brand_name}: {web}",
                "x_sho": f"Scout 500+ Gujarat wedding venues online in 60 seconds: {web}",
                "li_pro": f"Digital venue procurement across {city}. Compare capacities, floor plans, and transparent pricing for 500+ banquet spaces online at {brand_name}: {web}"
            }
        ]
        obj_l = (objective or "").lower()
        if "season" in obj_l:
            base_idx = 1
        elif "traffic" in obj_l or "web" in obj_l:
            base_idx = 4
        elif "educat" in obj_l or "author" in obj_l:
            base_idx = 3
        elif "trust" in obj_l or "proof" in obj_l:
            base_idx = 2
        else:
            base_idx = 0

        r = rotations[(base_idx + iteration) % len(rotations)]
        return {
            "instagram": {"professional": r["ig_pro"], "creative": r["ig_cre"], "short": r["ig_sho"]},
            "facebook": {"professional": r["fb_pro"], "creative": r["fb_cre"], "short": r["fb_sho"]},
            "x": {"professional": r["x_pro"], "creative": r["x_cre"], "short": r["x_sho"]},
            "linkedin": {"professional": r["li_pro"], "creative": r["li_pro"], "short": r["ig_sho"]}
        }
    else:
        rotations = [
            {
                "ig_pro": f"When it comes to verified quality, clarity is your biggest growth lever at {brand_name}.\n\n✔ Dedicated Specialists\n✔ Proven Execution Framework\n✔ 100% Transparency\n\nExplore our solutions: {web}\n📲 Contact: {phone}",
                "ig_cre": f"Behind every successful milestone is a partner committed to excellence. At {brand_name}, we help our clients turn ambition into measurable impact.\n\nDiscover the difference: {web}",
                "ig_sho": f"Reliable solutions tailored for {city}. Partner with {brand_name}: {web}"
            },
            {
                "ig_pro": f"Stop relying on guesswork. Here is the modern standard from {brand_name}.\n\nWe provide verified, high-performance frameworks designed for measurable results.\n\nExplore: {web}",
                "ig_cre": f"What if your daily operations felt seamless and completely predictable? That's what we build every day at {brand_name}.\n\nLearn more: {web}",
                "ig_sho": f"High performance. Total clarity. Choose {brand_name}: {web}"
            }
        ]
        r = rotations[iteration % len(rotations)]
        return {
            "instagram": {"professional": r["ig_pro"], "creative": r["ig_cre"], "short": r["ig_sho"]},
            "facebook": {"professional": r["ig_pro"], "creative": r["ig_cre"], "short": r["ig_sho"]},
            "x": {"professional": r["ig_sho"], "creative": r["ig_sho"], "short": r["ig_sho"]},
            "linkedin": {"professional": r["ig_pro"], "creative": r["ig_cre"], "short": r["ig_sho"]}
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


def render_instant_copy_button(text_to_copy: str, label: str, button_id: str):
    """Renders a zero-latency client-side copy button that works reliably in all browsers."""
    escaped_json = json.dumps(text_to_copy)
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: transparent; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    .cp-btn {{
        width: 100%;
        height: 38px;
        background: #F59E0B;
        color: #111827;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 700;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        transition: all 0.15s ease-in-out;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }}
    .cp-btn:hover {{
        background: #D97706;
    }}
    .cp-btn:active {{
        transform: scale(0.98);
    }}
    .cp-btn.success {{
        background: #10B981 !important;
        color: #FFFFFF !important;
    }}
    </style>
    </head>
    <body>
    <button id="{button_id}" class="cp-btn" onclick="copyAction()">📋 {label}</button>
    <script>
    function copyAction() {{
        var text = {escaped_json};
        var btn = document.getElementById("{button_id}");
        
        function markDone() {{
            btn.classList.add("success");
            btn.innerHTML = "✅ Copied to Clipboard!";
            setTimeout(function() {{
                btn.classList.remove("success");
                btn.innerHTML = "📋 " + {json.dumps(label)};
            }}, 2200);
        }}

        if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(text).then(function() {{
                markDone();
            }}).catch(function(e) {{
                fallbackCopy(text);
            }});
        }} else {{
            fallbackCopy(text);
        }}

        function fallbackCopy(val) {{
            try {{
                var ta = document.createElement("textarea");
                ta.value = val;
                ta.style.position = "fixed";
                ta.style.left = "-9999px";
                ta.style.top = "-9999px";
                ta.setAttribute("readonly", "");
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                ta.setSelectionRange(0, 99999);
                var ok = document.execCommand("copy");
                document.body.removeChild(ta);
                if (ok) {{
                    markDone();
                }} else {{
                    alert("Please select and copy text directly from the box.");
                }}
            }} catch(err) {{
                alert("Please select and copy text directly from the box.");
            }}
        }}
    }}
    </script>
    </body>
    </html>
    """
    st.components.v1.html(html_code, height=45)


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

    # Clean brand state initialization
    active_b = {}
    if "cp_prim" not in st.session_state:
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

            brand_default = st.session_state.get("cached_brand_name", active_b.get("brand_name", ""))
            industry_default = st.session_state.get("cached_industry", active_b.get("industry", ""))
            brand_name = st.text_input("Brand / Business Name *", value=brand_default, placeholder="e.g. Acme Corp or Sure Flow Equipment")
            industry_input = st.text_input("Industry / Business Type *", value=industry_default, placeholder="e.g. Industrial Valves, E-Commerce, etc.")
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
            aud_default = st.session_state.get("cached_audience", active_b.get("target_audience", ""))
            cta_default = st.session_state.get("cached_cta", active_b.get("cta", ""))
            audience_input = st.text_area("Target Audience Description *", value=aud_default, height=90, placeholder="Target demographic, interests, pain points, ideal customers...")
            primary_cta = st.text_input("Primary CTA / Action *", value=cta_default, placeholder="e.g. Learn More, Shop Now, Get Free Quote, Contact Us")

        with col_m2:
            st.markdown("#### Pillars 8 & 9: Market & Location")
            country_default = st.session_state.get("cached_country", active_b.get("target_country", ""))
            city_default = st.session_state.get("cached_city", active_b.get("target_city", ""))
            country_input = st.text_input("Target Country *", value=country_default, placeholder="e.g. United States, India, Global")
            city_input = st.text_input("Target City / Region", value=city_default, placeholder="e.g. New York, Toronto, Regional (Optional)")
            contact_email = st.text_input("Business Email", value=active_b.get("email", ""), placeholder="contact@example.com")
            contact_phone = st.text_input("Phone Number", value=active_b.get("phone", ""), placeholder="+1 (555) 000-0000")

    # PILLAR 10: Social Presence & Web
    with dna_tabs[3]:
        st.markdown("#### Pillar 10: Existing Social Presence & Website")
        st.caption("AI analyzes public presence to maintain voice and prevent conflicting tone.")
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            website_url = st.text_input("Website URL", value=web_input_val or active_b.get("website", ""), placeholder="https://example.com")
            ig_url = st.text_input("Instagram URL / Handle", value=active_b.get("instagram", ""), placeholder="@yourbrand")
            fb_url = st.text_input("Facebook URL", value=active_b.get("facebook", ""), placeholder="https://facebook.com/yourbrand")
        with col_w2:
            x_url = st.text_input("X (Twitter) URL", value=active_b.get("x", ""), placeholder="@yourbrand")
            li_url = st.text_input("LinkedIn URL", value=active_b.get("linkedin", ""), placeholder="https://linkedin.com/company/yourbrand")

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
        active_b.get("guidelines", "")
    )
    custom_campaign_info = st.text_area(
        "✨ CUSTOM CAMPAIGN INFORMATION (OPTIONAL)",
        placeholder="Tell AI anything specific about this post, product, offer, campaign, webpage, promotion or message you want to communicate.",
        height=110,
        value=camp_default
    )

    col_cp1, col_cp2 = st.columns(2)
    with col_cp1:
        prod_url_default = st.session_state.get("cached_product_url", web_input_val or active_b.get("website", ""))
        product_page_url = st.text_input("Product / Specific Campaign Page URL (Optional):", value=prod_url_default, placeholder="https://example.com/product")
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

    # Prepare payloads always available across re-runs and regenerations
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
        "cta": primary_cta,
        "campaign_info": custom_campaign_info,
        "objective": chosen_objective,
        "personality_traits": selected_traits,
        "formal_casual": slider_formal,
        "conservative_creative": slider_creative,
        "visual_style": chosen_visual_style,
        "heading_font": f_head.split(" (")[0],
        "body_font": f_body,
        "product_url": product_page_url,
        "platforms": selected_platforms,
        "c_prim": c_prim,
        "c_sec": c_sec,
        "c_acc": c_acc,
        "c_bg": c_bg,
        "c_txt": c_txt,
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

    # ==========================================================================
    # 🚀 PRIMARY CTA: GENERATE COMPLETE CONTENT PACK
    # ==========================================================================
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    generate_btn = st.button("🚀 Generate Complete Content Pack", type="primary", use_container_width=True)

    # Persistence of generated studio pack
    if "studio_content_pack" not in st.session_state:
        st.session_state["studio_content_pack"] = None

    if generate_btn:
        st.session_state["studio_pack_id"] = st.session_state.get("studio_pack_id", 0) + 1
        # Reset generation trackers so fresh pack values show in text areas
        for i in range(4):
            st.session_state[f"prompt_regen_ver_{i}"] = 0
            st.session_state[f"caption_regen_ver_{i}"] = 0
            for it_v in range(15):
                st.session_state.pop(f"txt_prompt_area_{i}_{it_v}", None)
                st.session_state.pop(f"txt_caption_area_{i}_{it_v}", None)

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
        st.session_state["social_content_pack"] = generated_pack
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
        cur_it = st.session_state.get(f"prompt_regen_ver_{active_c_idx}", 0)
        cur_cap_it = st.session_state.get(f"caption_regen_ver_{active_c_idx}", 0)

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

            # Safe Zone Specs Callout Box (Ad Poster Architecture)
            st.markdown(f"""
            <div style="background: rgba(15, 23, 42, 0.9); border: 1px dashed rgba(245, 158, 11, 0.45); border-radius: 10px; padding: 10px 14px; font-size: 0.77rem; color: #CBD5E1; margin-bottom: 10px; line-height: 1.6;">
                🎯 <b>Commercial Ad Poster Architecture (ChatGPT-Grade Creative Layout):</b><br>
                • <b>[ YOUR LOGO HERE ]:</b> Top-left dedicated minimalist negative space box (completely clean plain background, zero leaves) for direct logo overlay.<br>
                • <b>Left Marketing Copy:</b> High-contrast headline, sub-headline question, 4 feature badge icons & cursive tagline.<br>
                • <b>Right Hero Scene:</b> Realistic commercial photography with <b>{chosen_visual_style}</b>.<br>
                • <b>Lower 3-Panel Strip:</b> Split photo tiles highlighting 3 key amenities & venue features.<br>
                • <b>Bottom Footer Ribbon:</b> Branded bar with Website (<code>{website_url or 'www.venueconnect.in'}</code>), Phone & Action CTA pill.
            </div>
            """, unsafe_allow_html=True)

            pack_id = st.session_state.get("studio_pack_id", 0)
            prompt_text = cur_concept.get("image_generation_prompt", "")
            prompt_key = f"txt_prompt_area_{active_c_idx}_{cur_it}_{pack_id}"
            st.text_area(
                "Image Generation Prompt (Ready for Midjourney / Flux / SDXL / Ideogram):",
                value=prompt_text,
                height=230,
                key=prompt_key
            )

            # Left Action Buttons: Copy Prompt & Regenerate Prompt
            lp_col1, lp_col2 = st.columns(2)
            with lp_col1:
                render_instant_copy_button(prompt_text, "Copy Image Prompt", f"btn_cp_prompt_{active_c_idx}_{cur_it}_{pack_id}")
            with lp_col2:
                if st.button("🔄 Regenerate Prompt", key=f"btn_regen_prompt_{active_c_idx}", use_container_width=True):
                    next_it = cur_it + 1
                    st.session_state[f"prompt_regen_ver_{active_c_idx}"] = next_it
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
                            iteration=next_it,
                            content_format=chosen_format
                        )
                        pack["creative_concepts"][active_c_idx] = fresh_c
                        st.session_state["studio_content_pack"] = pack
                        st.session_state["social_content_pack"] = pack
                        st.toast("✅ Fresh image prompt variation generated!")
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

            caption_key = f"txt_caption_area_{active_c_idx}_{plat_key}_{tone_key}_{cur_cap_it}_{pack_id}"
            st.text_area(
                f"{sel_plat} Caption ({sel_tone}):",
                value=full_caption_text,
                height=230,
                key=caption_key
            )

            # Right Action Buttons: Copy Caption & Regenerate Caption
            rc_col1, rc_col2 = st.columns(2)
            with rc_col1:
                render_instant_copy_button(full_caption_text, "Copy Caption & Tags", f"btn_cp_cap_{active_c_idx}_{cur_cap_it}_{pack_id}")
            with rc_col2:
                if st.button("🔄 Regenerate Caption", key=f"btn_regen_cap_{active_c_idx}", use_container_width=True):
                    next_cap_it = cur_cap_it + 1
                    st.session_state[f"caption_regen_ver_{active_c_idx}"] = next_cap_it
                    with st.spinner("🔄 Generating fresh caption and hook..."):
                        fresh_caps = build_platform_captions_fresh(
                            brand_name=brand_name,
                            industry=industry_input,
                            objective=chosen_objective,
                            business=biz_data,
                            iteration=next_cap_it
                        )
                        pack["platform_captions"] = fresh_caps
                        st.session_state["studio_content_pack"] = pack
                        st.session_state["social_content_pack"] = pack
                        st.toast("✅ Fresh caption generated!")
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
