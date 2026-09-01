# 🕷️ Amir's SEO Spider (Web App)

A modern, high-speed, and feature-rich **Technical SEO Crawler & Audit Web Application** built with **Python** & **Streamlit**.

---

## 🌟 Key Features / मुख्य विशेषताएं

- **⚡ 10,000+ URLs Crawling Capacity**: No 500-page limit! Multi-threaded engine crawls large e-commerce websites and blogs.
- **🔍 Deep Technical SEO Auditing**:
  - **HTTP Status Codes**: 200 OK, 301/302 Redirect chains, 404 Broken links, 500 Server errors.
  - **Page Titles**: Character length, Google SERP pixel width estimation, duplicate detection, missing titles.
  - **Meta Descriptions**: Length optimization (70-160 chars), duplicates, missing descriptions.
  - **Heading Hierarchy**: H1 count, missing H1, duplicate H1s, multiple H1s, H2 subheadings.
  - **Indexability & Directives**: Meta robots (`noindex`, `nofollow`), Canonical tag verification (self-referential vs mismatch).
  - **Content Analysis**: Word count, thin content alerts (<300 words).
  - **Links & Architecture**: Internal vs External link breakdown, anchor text tracking, follow vs nofollow, broken link detection.
  - **Image Audit**: Missing `alt` tags, broken image URLs.
  - **Structured Data & Social**: Open Graph (`og:title`, `og:image`, `og:desc`), Twitter Cards, Schema.org JSON-LD tags.
- **📊 Interactive Visualizations**: SEO Health Score (0-100 Gauge), Status Code Donut chart, Issues breakdown, and interactive Network Graph of internal linking.
- **📥 Unlimited Free Exports**: Download comprehensive multi-tab **Excel Workbooks (`.xlsx`)** and **CSV** files.
- **🔎 Single URL Quick Inspector**: Instant single-page audit without running a full crawl.
- **🤖 Robots.txt & XML Sitemap Tool**: Live fetch, parser, and URL extractor.

---

## 🚀 How to Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```
Open browser at `http://localhost:8501`.

---

## 📄 License
MIT License - 100% Free & Open Source.
