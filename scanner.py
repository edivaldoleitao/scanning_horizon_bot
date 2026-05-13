# scanner.py

from datetime import datetime
from collections import Counter
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

import requests
import feedparser
import re


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# =========================================================
# NORMALIZAÇÃO
# =========================================================

def normalize_text(text: str) -> str:

    text = (text or "").lower()

    replacements = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def phrase_similarity(a, b):

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


# =========================================================
# SCORE
# =========================================================

def calculate_score(text, terms):

    text_norm = normalize_text(text)

    score = 0

    matched = []

    for term in terms:

        term_norm = normalize_text(term)

        if not term_norm:
            continue

        term_score = 0

        found = False

        # match exato
        if term_norm in text_norm:

            occurrences = text_norm.count(
                term_norm
            )

            term_score += (
                4 * occurrences
            )

            found = True

        # match por palavras
        words = term_norm.split()

        word_hits = 0

        for word in words:

            if len(word) >= 3:

                if re.search(
                    rf"\b{re.escape(word)}\b",
                    text_norm
                ):

                    word_hits += 1

        if word_hits:

            term_score += word_hits

            found = True

        # match aproximado
        if not found and len(term_norm) >= 4:

            best = 0.0

            for chunk in text_norm.split():

                sim = phrase_similarity(
                    term_norm,
                    chunk
                )

                if sim > best:
                    best = sim

            if best >= 0.8:

                term_score += 1

                found = True

        # bônus se todas palavras aparecem
        if words and all(

            re.search(
                rf"\b{re.escape(w)}\b",
                text_norm
            )

            for w in words
            if len(w) >= 3

        ):

            term_score += 2

            found = True

        if found:

            matched.append(term)

            score += term_score

    return score, matched


# =========================================================
# DATAS
# =========================================================

def safe_parse_date(date_str):

    if not date_str or date_str == "—":
        return None

    formats = [

        "%a, %d %b %Y %H:%M:%S GMT",

        "%Y-%m-%d",

        "%Y"

    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                str(date_str),
                fmt
            )

        except:
            pass

    return None


# =========================================================
# GROWTH
# =========================================================

def calculate_growth(
    recent,
    old
):

    if old <= 0:

        if recent > 0:
            return 100

        return 0

    return (
        ((recent - old) / old) * 100
    )


# =========================================================
# GOOGLE NEWS
# =========================================================

def parse_google_news(
    query,
    terms,
    start_date=None,
    end_date=None
):

    items = []

    encoded_query = quote_plus(
        query
    )

    rss_url = (
        "https://news.google.com/rss/search?q="
        f"{encoded_query}"
    )

    feed = feedparser.parse(
        rss_url
    )

    for entry in feed.entries:

        title = (
            entry.get("title", "")
        )

        link = (
            entry.get("link", "")
        )

        published = (
            entry.get(
                "published",
                "—"
            )
        )

        published_date = safe_parse_date(
            published
        )

        # filtro por período
        if start_date and published_date:

            if published_date < start_date:
                continue

        if end_date and published_date:

            if published_date > end_date:
                continue

        text = title

        score, matched = calculate_score(
            text,
            terms
        )

        # FILTRO MAIS FLEXÍVEL
        if score < 1:
            continue

        items.append({

            "type": "Notícia",

            "title": title,

            "source": "Google News",

            "authors": "—",

            "published": published,

            "score": score,

            "matched_terms": matched,

            "link": link

        })

    return items


# =========================================================
# GOOGLE SCHOLAR
# =========================================================

def parse_google_scholar(
    query,
    terms
):

    items = []

    encoded_query = quote_plus(
        query
    )

    scholar_url = (
        "https://scholar.google.com/scholar?q="
        f"{encoded_query}"
    )

    response = requests.get(
        scholar_url,
        headers=HEADERS,
        timeout=20
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    results = soup.select(
        ".gs_ri"
    )

    for result in results:

        title_tag = result.select_one(
            ".gs_rt"
        )

        if not title_tag:
            continue

        title = title_tag.get_text(
            " ",
            strip=True
        )

        link_tag = title_tag.find("a")

        link = "—"

        if link_tag:

            link = link_tag.get(
                "href",
                "—"
            )

        meta = result.select_one(
            ".gs_a"
        )

        authors = "—"

        published = "—"

        if meta:

            meta_text = meta.get_text(
                " ",
                strip=True
            )

            parts = meta_text.split(
                "-"
            )

            if len(parts) >= 1:
                authors = parts[0].strip()

            year_match = re.search(
                r"\b(19|20)\d{2}\b",
                meta_text
            )

            if year_match:

                published = (
                    year_match.group(0)
                )

        text = f"""
        {title}
        {authors}
        """

        score, matched = calculate_score(
            text,
            terms
        )

        if score < 1:
            continue

        items.append({

            "type": "Artigo",

            "title": title,

            "source": "Google Scholar",

            "authors": authors,

            "published": published,

            "score": score,

            "matched_terms": matched,

            "link": link

        })

    return items


# =========================================================
# RADAR DE SINAIS FRACOS
# =========================================================

def weak_signal_radar(
    results
):

    now = datetime.now()

    last_7 = 0
    last_30 = 0
    last_90 = 0

    sources = set()

    term_counter = Counter()

    total_score = 0

    for item in results:

        published = safe_parse_date(
            item.get("published")
        )

        if published:

            delta = now - published

            if delta.days <= 7:
                last_7 += 1

            if delta.days <= 30:
                last_30 += 1

            if delta.days <= 90:
                last_90 += 1

        source = item.get(
            "source",
            ""
        )

        if source:
            sources.add(source)

        for term in item.get(
            "matched_terms",
            []
        ):

            term_counter[term] += 1

        total_score += item.get(
            "score",
            0
        )

    growth_7_30 = calculate_growth(

        last_7,

        max(last_30 - last_7, 1)

    )

    growth_30_90 = calculate_growth(

        last_30,

        max(last_90 - last_30, 1)

    )

    diversity = len(sources)

    avg_score = 0

    if results:

        avg_score = (
            total_score / len(results)
        )

    weak_signal_index = 0

    # crescimento recente
    if growth_7_30 > 20:
        weak_signal_index += 3

    if growth_30_90 > 20:
        weak_signal_index += 2

    # diversidade de fontes
    if diversity >= 3:
        weak_signal_index += 2

    elif diversity >= 2:
        weak_signal_index += 1

    # relevância média
    if avg_score >= 5:
        weak_signal_index += 2

    elif avg_score >= 3:
        weak_signal_index += 1

    # volume baixo favorece sinal fraco
    if len(results) <= 20:
        weak_signal_index += 2

    elif len(results) <= 50:
        weak_signal_index += 1

    classification = "Ruído"

    if weak_signal_index >= 8:

        classification = (
            "Tendência Emergente"
        )

    elif weak_signal_index >= 6:

        classification = (
            "Sinal Fraco"
        )

    elif weak_signal_index >= 4:

        classification = (
            "Possível Tendência"
        )

    top_terms = []

    for term, count in term_counter.most_common(10):

        top_terms.append({

            "term": term,

            "count": count

        })

    return {

        "classification": classification,

        "weak_signal_index": weak_signal_index,

        "results_count": len(results),

        "growth_7_30": round(
            growth_7_30,
            2
        ),

        "growth_30_90": round(
            growth_30_90,
            2
        ),

        "source_diversity": diversity,

        "average_score": round(
            avg_score,
            2
        ),

        "top_terms": top_terms,

        "recent_mentions": {

            "7_days": last_7,

            "30_days": last_30,

            "90_days": last_90,

        }

    }


# =========================================================
# HORIZON SCAN
# =========================================================

def horizon_scan(
    theme,
    extra_terms,
    source,
    start_date=None,
    end_date=None
):

    # termos usados para scoring
    terms = []

    terms.append(theme)

    if extra_terms:

        extra_list = [

            x.strip()

            for x in extra_terms.split(",")

            if x.strip()

        ]

        terms.extend(extra_list)

    # IMPORTANTE:
    # busca só pelo tema principal
    query = theme

    results = []

    if source in ["google", "both"]:

        results.extend(

            parse_google_news(
                query,
                terms,
                start_date,
                end_date
            )

        )

    if source in ["scholar", "both"]:

        results.extend(

            parse_google_scholar(
                query,
                terms
            )

        )

    results.sort(

        key=lambda x: x["score"],

        reverse=True

    )

    radar = weak_signal_radar(
        results
    )

    return {

        "results": results,

        "radar": radar

    }