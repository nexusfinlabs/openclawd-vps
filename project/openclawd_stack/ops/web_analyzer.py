#!/usr/bin/env python3
"""
Web Analyzer — Deep analysis of websites, documents, and linked content.

Usage:
  python3 web_analyzer.py "https://norgine.com/clinical-trial-disclosure/"
  python3 web_analyzer.py "https://example.com" "contexto adicional"
  python3 web_analyzer.py --prompt-file /tmp/prompt.txt

Flow:
  1. Scrape the target URL (HTML → text)
  2. Extract and follow internal/external links (depth=1, max 10 links)
  3. Read linked documents (PDF, HTML, TXT)
  4. Send aggregated content to LLM for structured analysis
  5. Return analysis via stdout (for WhatsApp delivery)

Supports: HTML pages, PDFs, plain text, CSV, and common document formats.
"""

import json
import os
import re
import sys
import time
import logging
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime

# ── Config ──────────────────────────────────────────
DRAFTS_DIR = "/home/albi_agent/.openclaw/workspace/docs/drafts"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MAX_LINKS = 10          # Max links to follow from main page
MAX_CONTENT_PER_PAGE = 8000   # chars per page
MAX_TOTAL_CONTENT = 50000     # total chars to send to LLM
REQUEST_TIMEOUT = 20    # seconds per request
CRAWL_DELAY = 0.5       # seconds between requests

# ── Logging ─────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("web_analyzer")

# ── Headers ─────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}


def load_env():
    for path in ["/home/albi_agent/openclawd_stack/.env", ".env"]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k, v.strip("\"'"))
    global OPENROUTER_API_KEY
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")


# ═══════════════════════════════════════════════════
#  Content Extraction
# ═══════════════════════════════════════════════════

def extract_text_from_html(html_content, url=""):
    """Extract readable text from HTML, stripping tags."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove scripts, styles, nav, footer
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        # Get text
        text = soup.get_text(separator="\n", strip=True)
        # Clean up whitespace
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines)
    except ImportError:
        # Fallback: regex-based extraction
        text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


def extract_links_from_html(html_content, base_url):
    """Extract links from HTML page."""
    links = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                continue
            full_url = urljoin(base_url, href)
            link_text = a.get_text(strip=True)[:100]
            links.append({"url": full_url, "text": link_text})
    except ImportError:
        # Fallback: regex
        for match in re.finditer(r'href=["\']([^"\']+)["\']', html_content):
            href = match.group(1)
            if href.startswith("#") or href.startswith("javascript:"):
                continue
            full_url = urljoin(base_url, href)
            links.append({"url": full_url, "text": ""})
    return links


def extract_pdf_text(content_bytes):
    """Extract text from PDF bytes."""
    import tempfile
    try:
        # Try markitdown first
        from markitdown import MarkItDown
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(content_bytes)
            tmp_path = f.name
        mid = MarkItDown()
        result = mid.convert(tmp_path)
        os.unlink(tmp_path)
        return result.text_content
    except Exception:
        pass

    try:
        # Fallback: pdfplumber
        import pdfplumber
        import io
        text_parts = []
        with pdfplumber.open(io.BytesIO(content_bytes)) as pdf:
            for page in pdf.pages[:30]:  # max 30 pages
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except Exception:
        pass

    return "[PDF contenido no extraíble]"


def fetch_url(url, follow_redirects=True):
    """Fetch a URL and return (content_type, text_content)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
                           allow_redirects=follow_redirects, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "").lower()

        if "pdf" in content_type or url.lower().endswith(".pdf"):
            # PDF
            pdf_bytes = resp.content
            text = extract_pdf_text(pdf_bytes)
            return "pdf", text[:MAX_CONTENT_PER_PAGE]

        elif "html" in content_type or "xml" in content_type:
            # HTML/XML
            html = resp.text
            text = extract_text_from_html(html, url)
            return "html", text[:MAX_CONTENT_PER_PAGE]

        elif "text" in content_type or "csv" in content_type:
            # Plain text / CSV
            return "text", resp.text[:MAX_CONTENT_PER_PAGE]

        elif "json" in content_type:
            return "json", resp.text[:MAX_CONTENT_PER_PAGE]

        else:
            return "unknown", f"[Tipo de contenido no soportado: {content_type}]"

    except requests.exceptions.Timeout:
        return "error", f"[Timeout al acceder a {url}]"
    except requests.exceptions.RequestException as e:
        return "error", f"[Error: {str(e)[:200]}]"


# ═══════════════════════════════════════════════════
#  Crawler
# ═══════════════════════════════════════════════════

def crawl_url(target_url, max_links=MAX_LINKS):
    """
    Crawl a URL: fetch main page, extract links, follow interesting ones.
    Returns structured content dict.
    """
    log.info("Crawling: %s", target_url)
    results = {
        "target_url": target_url,
        "main_page": None,
        "linked_pages": [],
        "total_chars": 0,
    }

    # 1. Fetch main page
    content_type, text = fetch_url(target_url)
    results["main_page"] = {
        "url": target_url,
        "type": content_type,
        "content": text,
    }
    results["total_chars"] += len(text)
    log.info("  Main page: %s (%d chars)", content_type, len(text))

    if content_type == "error":
        return results

    # 2. Extract links (only from HTML pages)
    links = []
    if content_type == "html":
        resp = requests.get(target_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        links = extract_links_from_html(resp.text, target_url)
        log.info("  Found %d links", len(links))

    # 3. Filter and prioritize links
    target_domain = urlparse(target_url).netloc
    seen_urls = {target_url}
    interesting_links = []

    # Prioritize: documents (PDF, etc), then same-domain, then external
    for link in links:
        url = link["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Skip obvious non-content URLs
        parsed = urlparse(url)
        if any(x in parsed.path.lower() for x in ["/login", "/signup", "/cart", "/cookie", "/privacy"]):
            continue
        if any(url.lower().endswith(x) for x in [".jpg", ".png", ".gif", ".svg", ".css", ".js", ".zip"]):
            continue

        # Score links (higher = more interesting)
        score = 0
        if any(url.lower().endswith(x) for x in [".pdf", ".doc", ".docx", ".xlsx", ".csv"]):
            score += 10  # Documents are highly interesting
        if parsed.netloc == target_domain:
            score += 5   # Same domain
        if link["text"] and len(link["text"]) > 5:
            score += 2   # Has meaningful text
        interesting_links.append((score, url, link["text"]))

    # Sort by score, take top N
    interesting_links.sort(reverse=True)
    links_to_follow = interesting_links[:max_links]

    # 4. Follow links
    for score, url, link_text in links_to_follow:
        if results["total_chars"] >= MAX_TOTAL_CONTENT:
            log.info("  Reached content limit (%d chars), stopping", MAX_TOTAL_CONTENT)
            break

        time.sleep(CRAWL_DELAY)
        log.info("  Following: %s (%s)", url[:80], link_text[:30] if link_text else "")

        ct, text = fetch_url(url)
        page_data = {
            "url": url,
            "link_text": link_text,
            "type": ct,
            "content": text[:MAX_CONTENT_PER_PAGE],
        }
        results["linked_pages"].append(page_data)
        results["total_chars"] += len(page_data["content"])
        log.info("    → %s (%d chars)", ct, len(page_data["content"]))

    log.info("Crawl complete: %d pages, %d total chars",
             1 + len(results["linked_pages"]), results["total_chars"])
    return results


# ═══════════════════════════════════════════════════
#  LLM Analysis
# ═══════════════════════════════════════════════════

def analyze_content(crawl_results, user_context=""):
    """Send crawled content to LLM for structured analysis."""
    # Build the content payload
    content_parts = []

    main = crawl_results["main_page"]
    content_parts.append(f"=== PÁGINA PRINCIPAL: {main['url']} ({main['type']}) ===\n{main['content']}")

    for i, page in enumerate(crawl_results["linked_pages"]):
        label = page.get("link_text", "") or page["url"]
        content_parts.append(f"\n=== PÁGINA {i+2}: {label} ({page['type']}) ===\n{page['content']}")

    all_content = "\n\n".join(content_parts)
    # Truncate if needed
    if len(all_content) > MAX_TOTAL_CONTENT:
        all_content = all_content[:MAX_TOTAL_CONTENT] + "\n\n[... contenido truncado ...]"

    system = """Eres un analista senior especializado en investigación de empresas, mercados, y documentos técnicos.
Tu trabajo es analizar contenido web y documentos, y entregar un análisis estructurado, profesional y accionable.

Responde SIEMPRE en español. Estructura tu análisis así:

## 🏢 Resumen Ejecutivo
Breve resumen de qué es la entidad/empresa/página analizada y su relevancia.

## 📊 Hallazgos Clave
Lista numerada de los descubrimientos más relevantes del análisis.

## 📄 Documentos Analizados
Si hay documentos (PDFs, estudios, etc.), lista cada uno con un breve resumen de su contenido.

## 🔍 Análisis Detallado
Análisis en profundidad de los temas más relevantes encontrados.

## ⚠️ Observaciones
Riesgos, señales de alerta, o puntos que requieren atención.

## 💡 Recomendaciones
Acciones sugeridas basadas en el análisis.

Se conciso pero completo. Máximo ~800 palabras. No inventes datos — solo analiza lo proporcionado."""

    user_msg = f"Analiza el siguiente contenido web.\n\nURL objetivo: {crawl_results['target_url']}\nPáginas analizadas: {1 + len(crawl_results['linked_pages'])}\n"
    if user_context:
        user_msg += f"\nContexto adicional del usuario: {user_context}\n"
    user_msg += f"\n--- CONTENIDO ---\n{all_content}"

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        log.error("LLM analysis failed: %s", e)
        return f"❌ Error en análisis LLM: {str(e)[:300]}"


# ═══════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════

def run_analysis(target_url, user_context=""):
    """Full pipeline: crawl → analyze → save → return."""
    load_env()

    log.info("Starting analysis: %s", target_url)

    # 1. Crawl
    results = crawl_url(target_url)

    if results["main_page"]["type"] == "error":
        return None, f"❌ No se pudo acceder: {results['main_page']['content']}"

    # 2. Analyze with LLM
    analysis = analyze_content(results, user_context)

    # 3. Save to file
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    domain = urlparse(target_url).netloc.replace(".", "_")[:30]
    filename = f"ANALYSIS_{domain}_{ts}.md"
    filepath = os.path.join(DRAFTS_DIR, filename)

    report = f"# Análisis: {target_url}\n"
    report += f"*Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Páginas: {1 + len(results['linked_pages'])} | Chars: {results['total_chars']:,}*\n\n"
    report += analysis

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    # 4. Build summary for WhatsApp (truncated)
    pages_info = f"📄 {1 + len(results['linked_pages'])} páginas analizadas ({results['total_chars']:,} chars)"
    links_detail = ", ".join(
        f"{p.get('link_text', urlparse(p['url']).path)[:25]} ({p['type']})"
        for p in results["linked_pages"][:5]
    )
    if links_detail:
        pages_info += f"\n📎 Links: {links_detail}"

    summary = f"🔍 *Análisis Web Completado*\n\n{pages_info}\n\n{analysis}\n\n📁 Reporte guardado: `{filename}`"

    # Truncate for WhatsApp if too long (max ~4000 chars)
    if len(summary) > 3800:
        summary = summary[:3800] + f"\n\n... _[truncado, ver reporte completo: {filename}]_"

    return filepath, summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Web Analyzer")
    parser.add_argument("url", help="URL to analyze")
    parser.add_argument("context", nargs="*", help="Additional context")
    parser.add_argument("--prompt-file", default=None, help="Read context from file")
    args = parser.parse_args()

    context = ""
    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            context = f.read().strip()
    elif args.context:
        context = " ".join(args.context)

    filepath, message = run_analysis(args.url, context)
    print(message)
