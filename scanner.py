from datetime import datetime, timedelta
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
import feedparser
import requests
import re

# =========================================================
# HEADERS MELHORADOS (Simula Navegador Real)
# =========================================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Uso de Sessão para manter cookies e reduzir bloqueios 429
session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# NORMALIZAÇÃO
# =========================================================

def normalize_text(text: str) -> str:
    text = (text or "").lower()

    replacements = {
        "á": "a", "à": "a", "ã": "a", "â": "a",
        "é": "e", "ê": "e", "í": "i",
        "ó": "o", "ô": "o", "õ": "o",
        "ú": "u", "ç": "c",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def phrase_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _clean_list_csv(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value or "").split(",") if x.strip()]


def build_query_variants(theme: str, extra_terms: list[str]) -> list[str]:
    theme = " ".join((theme or "").split()).strip()
    extra_terms = [t for t in extra_terms if t]

    variants = []
    
    # Reduzimos a quantidade de queries para evitar bloqueios do Google,
    # focando apenas nas duas mais eficientes (Alta Precisão e Alto Recall)
    if theme and extra_terms:
        variants.append(f'"{theme}" {" ".join(extra_terms)}')
        variants.append(f'{theme} {" ".join(extra_terms)}')
    elif theme:
        variants.append(f'"{theme}"')
        variants.append(theme)

    seen = set()
    return [x for x in variants if not (x in seen or seen.add(x))]


# =========================================================
# SCORE (Regras Relaxadas para não descartar resultados)
# =========================================================

def calculate_score(text: str, theme: str, extra_terms: list[str]):
    text_norm = normalize_text(text)
    theme_norm = normalize_text(theme)

    if not theme_norm:
        return 0, []

    score = 0
    matched = []

    theme_words = [w for w in theme_norm.split() if len(w) >= 3]
    theme_hits = 0

    if theme_norm in text_norm:
        score += 12
        matched.append(theme)
        theme_hits = len(theme_words) if theme_words else 1
    else:
        for word in theme_words:
            if re.search(rf"\b{re.escape(word)}\b", text_norm):
                theme_hits += 1

        if theme_hits == 0:
            return 0, []

        # CORREÇÃO: Resumos do google são curtos. Exigir múltiplas palavras 
        # quase sempre falhava. Agora aceitamos matches parciais, mas com score menor.
        if len(theme_words) >= 4 and theme_hits < 2:
            return 0, []
        elif len(theme_words) >= 2 and theme_hits < 1:
            return 0, []

        score += theme_hits * 4
        matched.append(theme)

    matched_extra = 0
    for term in extra_terms:
        term_norm = normalize_text(term)
        if not term_norm:
            continue

        found = False
        if term_norm in text_norm:
            found = True
            score += 5
        else:
            words = [w for w in term_norm.split() if len(w) >= 3]
            hits = sum(1 for word in words if re.search(rf"\b{re.escape(word)}\b", text_norm))
            if words and hits >= 1:
                found = True
                score += hits * 2

        if found:
            matched_extra += 1
            matched.append(term)

    if matched_extra >= 3:
        score += 6
    elif matched_extra == 2:
        score += 4
    elif matched_extra == 1:
        score += 2

    return score, matched


# =========================================================
# DATA
# =========================================================

def safe_parse_date(date_str):
    if not date_str or date_str == "—":
        return None

    formats = [
        "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S %Z", # Formato do RSS do Google News
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y%m%d",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue

    return None


# =========================================================
# GDELT NEWS
# =========================================================

def parse_gdelt_news(theme, extra_terms, start_date=None, end_date=None):
    items = []
    queries = build_query_variants(theme, extra_terms)
    if not queries: return items

    start_dt = start_date or (datetime.now() - timedelta(days=180))
    end_dt = end_date or datetime.now()

    start_str = start_dt.strftime("%Y%m%d%H%M%S")
    end_str = end_dt.strftime("%Y%m%d%H%M%S")

    seen_links = set()

    for query in queries:
        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 100,
            "sort": "datedesc",
            "startdatetime": start_str,
            "enddatetime": end_str,
        }

        try:
            response = session.get(url, params=params, timeout=15)
            if response.status_code != 200:
                continue
            data = response.json()
        except:
            continue

        for article in data.get("articles", []):
            title = (article.get("title", "") or "").strip()
            link = (article.get("url", "") or "").strip()
            domain = (article.get("domain", "") or "").strip()
            summary = (article.get("summary", "") or "").strip()
            published_raw = article.get("seendate") or article.get("datetime") or ""

            if not link or link in seen_links: continue
            seen_links.add(link)

            score, matched = calculate_score(f"{title} {summary}", theme, extra_terms)
            if score <= 0: continue

            published = "—"
            if published_raw:
                try:
                    published = datetime.strptime(published_raw[:8], "%Y%m%d").strftime("%Y-%m-%d")
                except:
                    published = published_raw

            items.append({
                "type": "Notícia", "title": title, "source": domain or "GDELT",
                "authors": "—", "published": published, "score": score,
                "matched_terms": matched, "link": link,
            })

    return items


# =========================================================
# GOOGLE NEWS RSS (A SOLUÇÃO DEFINITIVA)
# =========================================================

def parse_google_news_rss(theme, extra_terms, start_date=None, end_date=None):
    """
    Busca notícias via RSS do Google. É imune a bloqueios de web scraping
    e respeita perfeitamente filtros de meses (ex: até 6 meses atrás).
    """
    items = []
    queries = build_query_variants(theme, extra_terms)
    
    # Filtro de tempo nativo do Google (ex: "when:180d")
    time_filter = ""
    if start_date:
        delta = datetime.now() - start_date
        days = max(1, delta.days)
        time_filter = f" when:{days}d"
    else:
        time_filter = " when:180d"

    seen_links = set()

    for query in queries:
        full_query = query + time_filter
        url = f"https://news.google.com/rss/search?q={quote_plus(full_query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                source = entry.source.title if hasattr(entry, 'source') else "Google News"
                
                if link in seen_links: continue
                seen_links.add(link)

                # Limpa HTML do summary do RSS
                summary_html = entry.get("summary", "")
                summary_text = BeautifulSoup(summary_html, "html.parser").get_text(" ", strip=True) if summary_html else ""

                score, matched = calculate_score(f"{title} {summary_text}", theme, extra_terms)
                if score <= 0: continue

                pub_date = safe_parse_date(entry.get("published", ""))
                published_str = pub_date.strftime("%Y-%m-%d") if pub_date else "—"

                # Validação estrita de janela de tempo
                if pub_date and end_date and pub_date > end_date: continue
                if pub_date and start_date and pub_date < start_date: continue

                items.append({
                    "type": "Notícia", "title": title, "source": source,
                    "authors": "—", "published": published_str, "score": score,
                    "matched_terms": matched, "link": link,
                })
        except:
            continue

    return items


# =========================================================
# GOOGLE WEB SEARCH (Fallback)
# =========================================================

def parse_google_web_results(theme, extra_terms):
    items = []
    queries = build_query_variants(theme, extra_terms)
    seen_links = set()

    for query in queries:
        url = "https://www.google.com/search?q=" + quote_plus(query) + "&hl=pt-BR&num=15"

        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
        except:
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        # Seletores atualizados que cobrem layouts novos do Google
        for block in soup.select("div.g, div.tF2Cxc"):
            try:
                a = block.select_one("a")
                h3 = block.select_one("h3")
                if not a or not h3: continue

                link = a.get("href", "").strip()
                title = h3.get_text(" ", strip=True)

                if not link or link.startswith("/search?") or link in seen_links: continue
                seen_links.add(link)

                snippet_el = block.select_one("div.VwiC3b, div.BNeawe, span.aCOpRe")
                snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

                score, matched = calculate_score(f"{title} {snippet}", theme, extra_terms)
                if score <= 0: continue

                items.append({
                    "type": "Notícia", "title": title, "source": "Google Web",
                    "authors": "—", "published": "—", "score": score,
                    "matched_terms": matched, "link": link,
                })
            except:
                continue

    return items


# =========================================================
# GOOGLE SCHOLAR
# =========================================================

def parse_google_scholar(query, theme, extra_terms):
    items = []
    if not query: return items

    scholar_url = "https://scholar.google.com/scholar?q=" + quote_plus(query) + "&hl=pt-BR"

    try:
        response = session.get(scholar_url, timeout=15)
        response.raise_for_status()
    except:
        return items

    soup = BeautifulSoup(response.text, "html.parser")
    for result in soup.select(".gs_ri"):
        title_tag = result.select_one(".gs_rt")
        if not title_tag: continue

        title = title_tag.get_text(" ", strip=True)
        link_tag = title_tag.find("a")
        link = link_tag.get("href", "—") if link_tag else "—"

        meta = result.select_one(".gs_a")
        authors, published = "—", "—"

        if meta:
            meta_text = meta.get_text(" ", strip=True)
            authors = meta_text.split("-")[0].strip() if "-" in meta_text else meta_text.strip()
            year_match = re.search(r"\b(19|20)\d{2}\b", meta_text)
            if year_match:
                published = year_match.group(0)

        score, matched = calculate_score(f"{title} {authors}", theme, extra_terms)
        if score <= 0: continue

        items.append({
            "type": "Artigo", "title": title, "source": "Google Scholar",
            "authors": authors, "published": published, "score": score,
            "matched_terms": matched, "link": link,
        })

    return items


# =========================================================
# RADAR
# =========================================================

def weak_signal_radar(results):
    now = datetime.now()
    last_30 = 0
    sources = set()
    term_counter = Counter()
    total_score = 0

    for item in results:
        published = safe_parse_date(item.get("published"))
        if published and (now - published).days <= 30:
            last_30 += 1

        src = item.get("source", "")
        if src: sources.add(src)

        for term in item.get("matched_terms", []):
            term_counter[term] += 1

        total_score += item.get("score", 0)

    avg_score = (total_score / len(results)) if results else 0
    weak_signal_index = 0

    if len(results) <= 20: weak_signal_index += 2
    elif len(results) <= 50: weak_signal_index += 1

    if last_30 >= 10: weak_signal_index += 2
    elif last_30 >= 5: weak_signal_index += 1

    if len(sources) >= 3: weak_signal_index += 2
    elif len(sources) >= 2: weak_signal_index += 1

    if avg_score >= 8: weak_signal_index += 2
    elif avg_score >= 5: weak_signal_index += 1

    classification = "Ruído"
    if weak_signal_index >= 7: classification = "Tendência Emergente"
    elif weak_signal_index >= 5: classification = "Sinal Fraco"
    elif weak_signal_index >= 3: classification = "Possível Tendência"

    return {
        "classification": classification,
        "weak_signal_index": weak_signal_index,
        "results_count": len(results),
        "average_score": round(avg_score, 2),
        "source_diversity": len(sources),
        "top_terms": [{"term": term, "count": count} for term, count in term_counter.most_common(10)],
    }


# =========================================================
# HORIZON SCAN (Fluxo Principal)
# =========================================================

def horizon_scan(theme, extra_terms, source, start_date=None, end_date=None):
    extra_list = _clean_list_csv(extra_terms)
    results = []
    query_variants = build_query_variants(theme, extra_list)

    if source in ["google", "both"]:
        # 1. GDELT
        results.extend(parse_gdelt_news(theme, extra_list, start_date, end_date))
        # 2. Google News RSS (Novo: resolve o problema dos 6 meses com precisão absoluta)
        results.extend(parse_google_news_rss(theme, extra_list, start_date, end_date))
        # 3. Web Scraping de Fallback
        results.extend(parse_google_web_results(theme, extra_list))

    if source in ["scholar", "both"]:
        scholar_query = query_variants[0] if query_variants else theme
        results.extend(parse_google_scholar(scholar_query, theme, extra_list))

    # Remoção de duplicatas baseada em Link
    unique = {item["link"]: item for item in results}
    
    results = list(unique.values())
    results.sort(key=lambda x: x["score"], reverse=True)

    radar = weak_signal_radar(results)

    return {
        "results": results,
        "radar": radar
    }
