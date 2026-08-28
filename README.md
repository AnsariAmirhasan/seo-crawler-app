# 🕷️ Screaming Frog & LibreCrawl SEO Spider (Web App)

A modern, fast, and feature-rich **Technical SEO Crawler & Audit Web Application** inspired by **Screaming Frog SEO Spider** and **LibreCrawl**, built with **Python** & **Streamlit**.

---

## 🌟 Key Features / मुख्य विशेषताएं

- **⚡ Multi-Threaded High-Speed Spider**: Concurrently crawl hundreds of URLs with customizable depth, speed, and timeout settings.
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

## 🚀 How to Run Locally / लोकल कैसे चलाएं

### 1. Requirements
Make sure you have **Python 3.9+** installed on your system.

### 2. Install Dependencies
Navigate to this folder and run:
```bash
pip install -r requirements.txt
```

### 3. Start the Streamlit Web App
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 🐙 Step-by-Step GitHub & Streamlit.app Deployment Guide
*(GitHub par code daal kar Streamlit Cloud par 100% Free Live chalane ka tarika)*

### Step 1: Initialize Git & Push to GitHub
1. Open your terminal inside this folder (`seo-crawler-app`):
   ```bash
   git init
   git add .
   git commit -m "Initial commit of Screaming Frog SEO Spider"
   ```
2. Go to [GitHub.com](https://github.com) and create a **New Repository** (e.g. `seo-spider-app`). Keep it **Public**.
3. Link and push your code:
   ```bash
   git branch -M main
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/seo-spider-app.git
   git push -u origin main
   ```

---

### Step 2: Deploy for Free on Streamlit Cloud (`streamlit.app`)
1. Go to **[share.streamlit.io](https://share.streamlit.io/)** and Sign in with your **GitHub account**.
2. Click on the **"New app"** button.
3. Select your repository: `<YOUR_GITHUB_USERNAME>/seo-spider-app`.
4. Branch: `main`
5. Main file path: `app.py`
6. Click **"Deploy!"** 🚀

Within 1-2 minutes, your SEO Crawler will be live on a custom URL like:
👉 `https://seo-spider-app.streamlit.app`

---

## 📁 Project Structure

```
seo-crawler-app/
├── .streamlit/
│   └── config.toml         # Theme and UI styling config
├── app.py                  # Streamlit frontend with Screaming Frog tabbed UI
├── crawler.py              # Multi-threaded crawler & network engine
├── seo_analyzer.py         # Technical SEO rules & health score calculations
├── visualizer.py           # Plotly interactive charts & network graphs
├── exporter.py             # Multi-tab Excel (.xlsx) and CSV generators
├── requirements.txt        # Python package dependencies
└── README.md               # Documentation & setup guide
```

---

## 📄 License
MIT License - 100% Free & Open Source.
