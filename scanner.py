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

def normalize_text(text: str):

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
# SCORE / RELEVÂNCIA
# =========================================================

def calculate_score(
    text,
    theme,
    extra_terms
):

    text_norm = normalize_text(text)

    matched = []

    score = 0

    # =====================================================
    # TEMA PRINCIPAL
    # =====================================================

    theme_norm = normalize_text(theme)

    theme_words = [

        w for w in theme_norm.split()

        if len(w) >= 3
    ]

    theme_hits = 0

    for word in theme_words:

        if re.search(
            rf"\b{re.escape(word)}\b",
            text_norm
        ):

            theme_hits += 1

    has_theme = False

    # tema completo
    if theme_norm in text_norm:

        score += 10

        has_theme = True

        matched.append(theme)

    # parcialmente relevante
    elif theme_hits >= max(1, len(theme_words) // 2):

        score += theme_hits * 2

        has_theme = True

        matched.append(theme)

    # =====================================================
    # TERMOS COMPLEMENTARES
    # =====================================================

    extra_matches = 0

    for term in extra_terms:

        term_norm = normalize_text(term)

        if not term_norm:
            continue

        found = False

        # match completo
        if term_norm in text_norm:

            score += 5

            found = True

        else:

            words = [

                w for w in term_norm.split()

                if len(w) >= 3
            ]

            word_hits = 0

            for word in words:

                if re.search(
                    rf"\b{re.escape(word)}\b",
                    text_norm
                ):

                    word_hits += 1

            if word_hits >= 1:

                score += word_hits

                found = True

        if found:

            extra_matches += 1

            matched.append(term)

    # =====================================================
    # FILTRO DE COERÊNCIA
    # =====================================================

    relevant = False

    # contém tema
    if has_theme:

        relevant = True

    # OU:
    # tema parcial + termo complementar
    elif theme_hits >= 1 and extra_matches >= 1:

        relevant = True

    # resultado irrelevante
    if not relevant:

        return 0, []

    # bônus contextual
    if extra_matches >= 2:

        score += 4

    elif extra_matches == 1:

        score += 2

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
    theme,
    extra_terms,
    start_date=None,
    end_date=None
):

    items = []

    search_queries = []

    # query principal
    search_queries.append(theme)

    # query combinada
    for term in extra_terms:

        search_queries.append(
            f"{theme} {term}"
        )

    seen_links = set()

    for query in search_queries:

        encoded_query = quote_plus(query)

        rss_url = (
            "https://news.google.com/rss/search?q="
            f"{encoded_query}"
        )

        feed = feedparser.parse(
            rss_url
        )

        for entry in feed.entries:

            title = entry.get(
                "title",
                ""
            )

            summary = entry.get(
                "summary",
                ""
            )

            link = entry.get(
                "link",
                ""
            )

            if link in seen_links:
                continue

            seen_links.add(link)

            published = entry.get(
                "published",
                "—"
            )

            published_date = safe_parse_date(
                published
            )

            # filtro período
            if start_date and published_date:

                if published_date < start_date:
                    continue

            if end_date and published_date:

                if published_date > end_date:
                    continue

            full_text = f"""
            {title}
            {summary}
            """

            score, matched = calculate_score(
                full_text,
                theme,
                extra_terms
            )

            if score <= 0:
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
    theme,
    extra_terms
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
            theme,
            extra_terms
        )

        if score <= 0:
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

def weak_signal_radar(results):

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

    if growth_7_30 > 20:
        weak_signal_index += 3

    if growth_30_90 > 20:
        weak_signal_index += 2

    if diversity >= 3:
        weak_signal_index += 2

    elif diversity >= 2:
        weak_signal_index += 1

    if avg_score >= 5:
        weak_signal_index += 2

    elif avg_score >= 3:
        weak_signal_index += 1

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

    extra_list = []

    if extra_terms:

        extra_list = [

            x.strip()

            for x in extra_terms.split(",")

            if x.strip()

        ]

    results = []

    # =====================================================
    # GOOGLE NEWS
    # =====================================================

    if source in ["google", "both"]:

        results.extend(

            parse_google_news(
                theme,
                extra_list,
                start_date,
                end_date
            )

        )

    # =====================================================
    # GOOGLE SCHOLAR
    # =====================================================

    if source in ["scholar", "both"]:

        scholar_query = (
            f"{theme} "
            f"{' '.join(extra_list)}"
        )

        results.extend(

            parse_google_scholar(
                scholar_query,
                theme,
                extra_list
            )

        )

    # =====================================================
    # REMOVE DUPLICADOS
    # =====================================================

    unique = {}

    for item in results:

        unique[item["link"]] = item

    results = list(
        unique.values()
    )

    # =====================================================
    # ORDENAÇÃO
    # =====================================================

    results.sort(

        key=lambda x: x["score"],

        reverse=True

    )

    # =====================================================
    # RADAR
    # =====================================================

    radar = weak_signal_radar(
        results
    )

    return {

        "results": results,

        "radar": radar

    }
