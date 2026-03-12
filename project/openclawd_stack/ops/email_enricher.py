import os
import sys
import json
import logging
import requests
import re
from urllib.parse import urljoin
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def emit(msg):
    """Print and flush immediately so OpenClaw gateway captures output."""
    print(msg, flush=True)

def load_env():
    env_path = '/home/albi_agent/openclawd_stack/.env'
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v.strip('"\'')

def check_zerobounce(email):
    """Verifies email mathematically/SMTP using ZeroBounce API"""
    api_key = os.environ.get("ZEROBOUNCE_API_KEY")
    if not api_key:
        logger.warning("No ZEROBOUNCE_API_KEY found, skipping validation.")
        return "unverified"
        
    try:
        url = f"https://api.zerobounce.net/v2/validate"
        params = {"api_key": api_key, "email": email, "ip_address": ""}
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        return data.get("status", "unknown")
    except Exception as e:
        logger.error(f"ZeroBounce error: {e}")
        return "error"

def find_hunter(first_name, last_name, domain):
    """Finds email using Hunter.io API"""
    api_key = os.environ.get("HUNTER_API_KEY")
    if not api_key:
        return None
        
    try:
        url = "https://api.hunter.io/v2/email-finder"
        params = {
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": api_key
        }
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("email")
    except Exception as e:
        logger.error(f"Hunter error: {e}")
    return None

def find_snovio(first_name, last_name, domain):
    """Finds email using Snov.io API"""
    client_id = os.environ.get("SNOVIO_CLIENT_ID")
    client_secret = os.environ.get("SNOVIO_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
        
    try:
        # 1. Get Access Token
        auth_url = "https://api.snov.io/v1/oauth/access_token"
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }
        auth_resp = requests.post(auth_url, data=auth_data, timeout=5)
        if auth_resp.status_code != 200:
            logger.error(f"Snov.io Auth Error: {auth_resp.text}")
            return None
        token = auth_resp.json().get("access_token")
        
        # 2. Search Email
        search_url = "https://api.snov.io/v1/get-emails-from-names"
        headers = {"Authorization": f"Bearer {token}"}
        search_data = {
            "firstName": first_name,
            "lastName": last_name,
            "domain": domain
        }
        resp = requests.post(search_url, headers=headers, data=search_data, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Snov.io may return a list of potentials
            if data and isinstance(data, list) and len(data) > 0:
                return data[0].get("email")
    except Exception as e:
        logger.error(f"Snov.io error: {e}")
    return None


def find_apollo(first_name, last_name, domain):
    """Finds email using Apollo API — NOTE: blocked on free plan, skipped by default."""
    api_key = os.environ.get("APOLLO_API_KEY")
    if not api_key:
        return None
        
    try:
        url = "https://api.apollo.io/v1/people/match"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": api_key
        }
        data = {
            "first_name": first_name,
            "last_name": last_name,
            "organization_name": domain
        }
        resp = requests.post(url, headers=headers, json=data, timeout=5)
        if resp.status_code == 200:
            resp_data = resp.json()
            person = resp_data.get("person", {})
            return person.get("email")
    except Exception as e:
        logger.error(f"Apollo error: {e}")
    return None

def find_via_scraping(first_name, last_name, domain):
    """Scrapes the website looking for mailto: links and attempts to match with the person's name"""
    if not BeautifulSoup:
        logger.warning("BeautifulSoup not installed, skipping scraping.")
        return None
        
    logger.info("Attempting Web Scraping Fallback...")
    # List of common pages to check
    urls_to_check = [
        f"https://{domain}",
        f"https://{domain}/team",
        f"https://{domain}/about",
        f"https://{domain}/contact",
        f"https://{domain}/nosotros",
        f"https://{domain}/equipo"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Generate likely email patterns to help selection
    f = first_name.lower().replace(" ", "")
    l = last_name.lower().replace(" ", "")
    likely_starts = [f"{f}.{l}", f"{f[0]}{l}", f"{f}_{l}", f"{f}", f"{l}"]

    found_emails = set()
    
    for url in urls_to_check:
        try:
            resp = requests.get(url, headers=headers, timeout=4)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 1. Look for mailto: links
                for a in soup.find_all('a', href=True):
                    if a['href'].startswith('mailto:'):
                        email = a['href'].replace('mailto:', '').split('?')[0].strip().lower()
                        if '@' in email:
                            found_emails.add(email)
                
                # 2. Look for raw emails in text using regex
                text = soup.get_text()
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                matches = re.findall(email_pattern, text)
                for email in matches:
                    found_emails.add(email.lower())
        except Exception as e:
            pass # Ignore connection errors for specific subpages
            
    # Try to find the best match based on names
    for email in found_emails:
        local_part = email.split('@')[0]
        for start in likely_starts:
            if local_part.startswith(start) or start in local_part or f in local_part or l in local_part:
                # Extrapolate: Even if the domain is different (e.g. staging domains or personal), 
                # we force it to the target domain just to be sure, or return it verbatim if it already matches.
                if domain.lower() not in email:
                    logger.info(f"Extrapolating {local_part} to {domain}")
                    return f"{local_part}@{domain.lower()}"
                return email
                
    return None

def infer_domain_via_serpapi_fallback(company_name):
    """Fallback: Uses Google SerpAPI to infer the official global domain of a company."""
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        logger.warning("No SERPAPI_KEY found, skipping domain inference.")
        return company_name
        
    logger.info(f"Inferring generic domain for '{company_name}' via Google Search...")
    try:
        query = f'"{company_name}" official website'
        url = "https://serpapi.com/search.json"
        params = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": 3
        }
        
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            for result in data.get("organic_results", []):
                link = result.get("link", "")
                if link and "linkedin.com" not in link and "wikipedia.org" not in link and "facebook.com" not in link:
                    domain = link.split('//')[-1].split('/')[0]
                    domain = domain.replace('www.', '')
                    logger.info(f"Inferred Generic Domain: {domain}")
                    return domain
                    
    except Exception as e:
        logger.error(f"SerpAPI domain inference error: {e}")
        
    return company_name

def parse_natural_query(query_string):
    """Uses LLM to extract first_name, last_name, and company/context from a raw natural language query."""
    or_key = os.environ.get("OPENROUTER_API_KEY")
    if not or_key:
        logger.error("Missing OPENROUTER_API_KEY for natural query parsing.")
        # Basic split fallback
        parts = query_string.split()
        if len(parts) >= 3:
            return parts[0], parts[1], " ".join(parts[2:])
        return "Unknown", "Unknown", query_string
        
    prompt = f"""Extrae el nombre, apellido y empresa/contexto de esta petición de búsqueda de email: "{query_string}"
    
Reglas de extracción:
1. Identifica el primer nombre.
2. Identifica el apellido.
3. Todo lo demás (empresa, departamento, país, contexto) ponlo en "empresa_y_contexto". 
Ejemplo 1: Si es "hannah leeper norgine en inglaterra" -> Nombre: hannah, Apellido: leeper, Empresa: norgine en inglaterra
Ejemplo 2: Si es "paul shon pwc de HR" -> Nombre: paul, Apellido: shon, Empresa: pwc de HR

Responde ÚNICA Y EXCLUSIVAMENTE en este formato exacto separado por la barra vertical |:
Nombre|Apellido|Empresa_y_Contexto"""

    headers = {
        "Authorization": f"Bearer {or_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 50
    }
    
    emit(f"🧠 Analizando petición natural: '{query_string}'...")
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=8)
        if resp.status_code == 200:
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if "|" in content:
                parts = content.split("|")
                if len(parts) >= 3:
                    return parts[0].strip(), parts[1].strip(), parts[2].strip()
    except Exception as e:
        logger.error(f"Error parsing natural query: {e}")
        
    # Fallback to extremely basic split
    parts = query_string.split()
    if len(parts) >= 3:
        return parts[0], parts[1], " ".join(parts[2:])
    return "Unknown", "Unknown", str(query_string)

def infer_domain_via_llm(first_name, last_name, company_name):
    """Uses SerpAPI to find the person's location, then OpenRouter LLM to deduce local domain."""
    serpapi_key = os.environ.get("SERPAPI_KEY")
    or_key = os.environ.get("OPENROUTER_API_KEY")
    
    if not serpapi_key or not or_key:
        logger.warning("Missing API keys for LLM domain inference, falling back.")
        return infer_domain_via_serpapi_fallback(company_name)
        
    try:
        # 1. Gather context about the person via Google
        # Quotes removed around names so Google handles typos like "fray" -> "frau"
        query = f'{first_name} {last_name} {company_name} LinkedIn'
        url = "https://serpapi.com/search.json"
        params = {"q": query, "api_key": serpapi_key, "engine": "google", "num": 3}
        resp = requests.get(url, params=params, timeout=8)
        
        snippets = ""
        if resp.status_code == 200:
            data = resp.json()
            for r in data.get("organic_results", []):
                snippets += r.get("snippet", "") + " " + r.get("title", "") + "\n"
                
        # 2. Query LLM to deduce domain
        prompt = f"""Analiza este perfil profesional:
Nombre buscado: {first_name} {last_name} (ATENCIÓN: Puede contener errores tipográficos)
Empresa: {company_name}
Resultados de Google:
{snippets}

Tarea:
1. Encuentra a la persona correcta en los resultados. Si ves un nombre muy similar (ej. "Frau" en vez de "Fray") que SÍ trabaja en la empresa {company_name}, asume que ESA es la persona correcta (el usuario se equivocó al teclear). Ignora personas con el nombre exacto que NO trabajen en la empresa.
2. Descubre en qué país trabaja esa persona correcta basándote en su perfil de LinkedIn (ej. Italia, Alemania).
3. Deduce la extensión de email regional o corporativa correcta de la empresa para ese país. Por ejemplo, EY en Italia es it.ey.com, en Alemania es de.ey.com, en España es es.ey.com. BCG suele ser bcg.com global, PwC suele ser pwc.com, etc.
4. Responde ÚNICA Y EXCLUSIVAMENTE con el formato exacto: dominio|Nombre Correcto|Apellido Correcto. Sin explicaciones ni comillas. Ejemplo: it.ey.com|Silvia|Frau"""

        headers = {
            "Authorization": f"Bearer {or_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 50
        }
        
        llm_resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=8)
        if llm_resp.status_code == 200:
            llm_data = llm_resp.json()
            content = llm_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if "|" in content:
                parts = content.split("|")
                if len(parts) >= 3:
                    domain = parts[0].strip().lower()
                    c_first_name = parts[1].strip()
                    c_last_name = parts[2].strip()
                    
                    if "." in domain and " " not in domain and "@" not in domain:
                        logger.info(f"LLM Inferred Domain: {domain} and Corrected Name: {c_first_name} {c_last_name}")
                        return domain, c_first_name, c_last_name
                        
    except Exception as e:
        logger.error(f"LLM domain inference error: {e}")
        
    # If the LLM flow fails, fallback to the simple global domain logic
    return infer_domain_via_serpapi_fallback(company_name), first_name, last_name

def find_via_serpapi(first_name, last_name, domain):
    """Uses Google SerpAPI to search for the person's email publicly listed.
    Checks organic results, AI overviews, answer boxes, and knowledge panels."""
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        logger.warning("No SERPAPI_KEY found, skipping Google Search Fallback.")
        return None
        
    logger.info("Attempting SerpAPI Google Search Fallback...")
    
    # Try the 2 most effective query variations (reduced from 4 for speed)
    # Quotes removed to allow Google autocorrect on name typos
    queries = [
        f'{first_name} {last_name} email "{domain}"',
        f'{first_name} {last_name} email {domain.split(".")[0]}',
    ]
    
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    f = first_name.lower().replace(" ", "")
    l = last_name.lower().replace(" ", "")
    
    for query in queries:
        try:
            url = "https://serpapi.com/search.json"
            params = {
                "q": query,
                "api_key": api_key,
                "engine": "google",
                "num": 5
            }
            
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code != 200:
                continue
                
            data = resp.json()
            
            # Build a comprehensive text corpus from ALL Google response fields
            text_corpus = ""
            
            # Check AI Overview / Answer Box (where Google directly answers)
            for field in ["answer_box", "ai_overview"]:
                box = data.get(field, {})
                if isinstance(box, dict):
                    text_corpus += " " + json.dumps(box)
                elif isinstance(box, str):
                    text_corpus += " " + box
            
            # Check Knowledge Graph
            kg = data.get("knowledge_graph", {})
            if isinstance(kg, dict):
                text_corpus += " " + json.dumps(kg)
            
            # Check organic results (snippets + titles)
            for result in data.get("organic_results", []):
                text_corpus += " " + result.get("snippet", "") + " " + result.get("title", "")
                # Also check rich_snippet if available
                rich = result.get("rich_snippet", {})
                if isinstance(rich, dict):
                    text_corpus += " " + json.dumps(rich)
                    
            # Check related_questions (People Also Ask)
            for q in data.get("related_questions", []):
                text_corpus += " " + q.get("snippet", "") + " " + q.get("title", "")
            
            # Extract all emails from the corpus
            matches = re.findall(email_pattern, text_corpus)
            
            # First pass: match by name
            for email in matches:
                email = email.lower()
                local_part = email.split('@')[0]
                # Strong name match required
                if f in local_part or l in local_part or (f[0] + l) in local_part:
                    logger.info(f"Found email (name match in SERP): {email}")
                    return email
                        
        except Exception as e:
            logger.error(f"SerpAPI error for query '{query}': {e}")
        
    return None

def enrich_and_verify(first_name, last_name, domain_or_company):
    """Discovery waterfall — optimized for speed."""
    load_env()
    
    # Clean up quotes (sometimes passed literally by the chat gateway)
    first_name = first_name.strip('"\'“”')
    last_name = last_name.strip('"\'“”')
    domain_or_company = domain_or_company.strip('"\'“”')
    
    emit(f"⏳ Buscando email de {first_name} {last_name}...")
    
    # Check if the third argument is actually a domain (contains a dot)
    if "." not in domain_or_company:
        emit(f"🔍 Infiriendo dominio regional inteligente para '{domain_or_company}'...")
        domain, first_name, last_name = infer_domain_via_llm(first_name, last_name, domain_or_company)
        # Re-emit if the name was corrected so the user knows
        emit(f"✅ Nombre corregido por IA: {first_name} {last_name}")
    else:
        domain = domain_or_company
        
    logger.info(f"Enriching {first_name} {last_name} @ {domain}")
    
    # 1. Skip Apollo — blocked on free plan, wastes time
    email = None
    source = None
    
    # 2. Try Hunter
    if not email:
        email = find_hunter(first_name, last_name, domain)
        source = "hunter"
        
    # 2.5 Try Snov.io
    if not email:
        email = find_snovio(first_name, last_name, domain)
        source = "snovio"
        
    # 3. Try Web Scraping
    if not email:
        email = find_via_scraping(first_name, last_name, domain)
        source = "web_scraping_extrapolation" if email and domain.lower() in email else "web_scraping"
        
    # 4. Try SerpAPI (Google)
    if not email:
        email = find_via_serpapi(first_name, last_name, domain)
        source = "google_search_pattern" if email else "google_search"
        
    # 5. Smart Permutation Engine (generates all patterns, validates if possible)
    if not email:
        f = first_name.lower().replace(" ", "").replace("á","a").replace("à","a").replace("é","e").replace("è","e").replace("í","i").replace("ó","o").replace("ò","o").replace("ú","u").replace("ù","u").replace("ñ","n").replace("ü","u").replace("ç","c")
        l = last_name.lower().replace(" ", "").replace("á","a").replace("à","a").replace("é","e").replace("è","e").replace("í","i").replace("ó","o").replace("ò","o").replace("ú","u").replace("ù","u").replace("ñ","n").replace("ü","u").replace("ç","c")
        d = domain.lower()
        
        # Generate candidates in order of likelihood (corporate patterns)
        candidates = [
            f"{f}.{l}@{d}",         # javier.santiago@bms.com (60% of companies)
            f"{f[0]}{l}@{d}",       # jsantiago@bms.com (25%)
            f"{f}_{l}@{d}",         # javier_santiago@bms.com
            f"{f}{l}@{d}",          # javiersantiago@bms.com
            f"{f}@{d}",             # javier@bms.com
            f"{l}.{f}@{d}",         # santiago.javier@bms.com
            f"{f[0]}.{l}@{d}",     # j.santiago@bms.com
        ]
        
        logger.warning(f"All APIs failed. Generating {len(candidates)} permutations for {first_name} {last_name} @ {domain}")
        
        # If ZeroBounce is available, validate each candidate
        zb_key = os.environ.get("ZEROBOUNCE_API_KEY")
        if zb_key:
            logger.info("ZeroBounce available — validating permutations...")
            for candidate in candidates:
                zb_status = check_zerobounce(candidate)
                if zb_status == "valid":
                    email = candidate
                    source = "permutation_verified"
                    logger.info(f"✅ Verified via ZeroBounce: {email}")
                    break
                elif zb_status in ("catch-all", "unknown"):
                    # Might be valid, save as best guess
                    if not email:
                        email = candidate
                        source = "permutation_catchall"
        
        if not email:
            # Return the most common pattern (first.last)
            email = candidates[0]
            source = "permutation_unverified"
            logger.info(f"Best guess (unverified): {email}")
        
    # Validation step (if not already validated by ZeroBounce above)
    if source not in ("permutation_verified", "permutation_catchall"):
        status = check_zerobounce(email)
    else:
        status = "valid" if source == "permutation_verified" else "catch-all"
    
    is_valid = status == "valid"
    
    return {
        "email": email,
        "source": source,
        "zerobounce_status": status,
        "verified": is_valid
    }

def format_result(result, first_name, last_name):
    """Format result as a WhatsApp-friendly message."""
    email = result.get("email", "?")
    source = result.get("source", "?")
    status = result.get("zerobounce_status", "?")
    verified = result.get("verified", False)
    
    # Status emoji
    if verified:
        badge = "✅ Verificado"
    elif status == "catch-all":
        badge = "🟡 Catch-all (probable)"
    elif status == "unverified":
        badge = "🟠 Sin verificar"
    else:
        badge = f"⚪ {status}"
    
    # Source label
    source_labels = {
        "hunter": "Hunter.io",
        "snovio": "Snov.io",
        "apollo": "Apollo",
        "web_scraping": "Web Scraping",
        "web_scraping_extrapolation": "Web Scraping (extrapolado)",
        "google_search_pattern": "Google Search",
        "permutation_verified": "Permutación + ZeroBounce ✅",
        "permutation_catchall": "Permutación (catch-all)",
        "permutation_unverified": "Permutación (sin verificar)",
    }
    src = source_labels.get(source, source)
    
    lines = [
        f"📧 Email encontrado: {email}",
        f"",
        f"👤 {first_name} {last_name}",
        f"🔎 Fuente: {src}",
        f"🏷️ Estado: {badge}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    load_env()

    if len(sys.argv) < 2:
        emit(json.dumps({"error": "Usage: python email_enricher.py <first_name> <last_name> <domain> OR <natural query>"}))
        sys.exit(1)
        
    # Check if exactly 3 args were passed in explicit quotes
    if len(sys.argv) == 4:
        first_name = sys.argv[1]
        last_name = sys.argv[2]
        company = sys.argv[3]
    else:
        # Natural language / Unquoted parsing
        full_query = " ".join(sys.argv[1:])
        first_name, last_name, company = parse_natural_query(full_query)
        
    result = enrich_and_verify(first_name, last_name, company)
    # Print both: human-readable for WhatsApp, and JSON for programmatic use
    emit(format_result(result, first_name, last_name))
    emit("")
    emit(json.dumps(result, indent=2))
