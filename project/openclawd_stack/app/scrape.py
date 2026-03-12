import re
import json
import requests
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")

def _clean(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    return s or None

def scrape_requests(url: str, timeout: int = 20) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    r.raise_for_status()

    html = r.text
    soup = BeautifulSoup(html, "lxml")

    title = _clean(soup.title.text if soup.title else None)
    meta = soup.find("meta", attrs={"name": "description"})
    meta_description = _clean(meta.get("content") if meta else None)

    text = soup.get_text(" ", strip=True)
    emails = sorted(set(EMAIL_RE.findall(html + " " + text)))
    phones = sorted(set(m.group(0) for m in PHONE_RE.finditer(text)))

    # forms: detect basic contact forms
    forms = []
    for f in soup.find_all("form"):
        action = f.get("action")
        method = (f.get("method") or "get").lower()
        inputs = []
        for inp in f.find_all(["input", "textarea", "select"]):
            name = inp.get("name") or inp.get("id")
            itype = inp.get("type") if inp.name == "input" else inp.name
            if name:
                inputs.append({"name": name, "type": itype})
        if inputs:
            forms.append({"action": action, "method": method, "inputs": inputs})

    return {
        "url": r.url,
        "title": title,
        "meta_description": meta_description,
        "emails": ",".join(emails) if emails else None,
        "phones": ",".join(phones) if phones else None,
        "forms": json.dumps(forms) if forms else None,
        "source": "requests",
    }
