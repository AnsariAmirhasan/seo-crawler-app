import io
import pandas as pd

def generate_excel_report(analysis_result: dict, start_url: str) -> bytes:
    """Generate a multi-tab formatted Excel workbook containing all crawl data."""
    output = io.BytesIO()
    
    df_pages = analysis_result.get("df_pages", pd.DataFrame()).copy()
    df_issues = analysis_result.get("df_issues", pd.DataFrame()).copy()
    df_links = analysis_result.get("df_links", pd.DataFrame()).copy()
    df_images = analysis_result.get("df_images", pd.DataFrame()).copy()
    summary = analysis_result.get("summary", {})

    # Clean issues column inside df_pages for excel export
    if "issues" in df_pages.columns:
        df_pages["issues_count"] = df_pages["issues"].apply(lambda x: len(x) if isinstance(x, list) else 0)
        df_pages = df_pages.drop(columns=["issues"])

    # Create Summary DataFrame
    df_summary = pd.DataFrame([
        {"Metric": "Target Website", "Value": start_url},
        {"Metric": "SEO Health Score", "Value": f"{summary.get('health_score', 0)} / 100"},
        {"Metric": "Total URLs Crawled", "Value": summary.get('total_crawled', 0)},
        {"Metric": "Critical Errors", "Value": summary.get('critical_errors', 0)},
        {"Metric": "Warnings", "Value": summary.get('warnings', 0)},
        {"Metric": "Notices", "Value": summary.get('notices', 0)},
        {"Metric": "Duplicate Page Titles", "Value": summary.get('duplicate_titles_count', 0)},
        {"Metric": "Duplicate H1 Headings", "Value": summary.get('duplicate_h1_count', 0)},
        {"Metric": "Total Links Discovered", "Value": summary.get('total_links', 0)},
        {"Metric": "Total Images Discovered", "Value": summary.get('total_images', 0)}
    ])

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_summary.to_excel(writer, sheet_name='Audit Summary', index=False)
        if not df_pages.empty:
            df_pages.to_excel(writer, sheet_name='Internal Pages', index=False)
            if "canonical_url" in df_pages.columns:
                canon_cols = [c for c in ["url", "canonical_url", "canonical_status", "status_code", "is_indexable"] if c in df_pages.columns]
                df_pages[canon_cols].to_excel(writer, sheet_name='Canonicals', index=False)
        if not df_issues.empty:
            df_issues.to_excel(writer, sheet_name='Issues & Fixes', index=False)
        if not df_links.empty:
            df_links.head(30000).to_excel(writer, sheet_name='Discovered Links', index=False)
        if not df_images.empty:
            df_images.head(30000).to_excel(writer, sheet_name='Images & Alt', index=False)

    return output.getvalue()

def generate_csv(df: pd.DataFrame) -> bytes:
    """Generate clean CSV bytes for export."""
    df_clean = df.copy()
    if "issues" in df_clean.columns:
        df_clean["issues_count"] = df_clean["issues"].apply(lambda x: len(x) if isinstance(x, list) else 0)
        df_clean = df_clean.drop(columns=["issues"])
    return df_clean.to_csv(index=False).encode('utf-8')
