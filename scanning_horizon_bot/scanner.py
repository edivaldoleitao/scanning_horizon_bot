# scanner.py
from urllib.parse import quote_plus

import html as html_lib
import requests
from bs4 import BeautifulSoup


def clean(text: str):
    return " ".join((text or "").split()).strip()


def parse_item(item):
    raw_description = item.description.text if item.description else ""
    soup = BeautifulSoup(raw_description, "html.parser")

    link_tag = soup.find("a")
    source_tag = soup.find("font")

    title = clean(
        link_tag.get_text(" ", strip=True) if link_tag else (
            item.title.text if item.title else ""
        )
    )

    source = clean(source_tag.get_text(" ", strip=True) if source_tag else "")

    link = ""
    if link_tag and link_tag.get("href"):
        link = link_tag.get("href")
    elif item.link:
        link = item.link.text

    published = clean(item.pubDate.text if item.pubDate else "")

    summary = clean(soup.get_text(" ", strip=True))
    if title and summary.startswith(title):
        summary = summary[len(title):].strip()
    if source and summary.endswith(source):
        summary = summary[:-len(source)].strip()

    summary = html_lib.unescape(summary)

    return {
        "title": title or "—",
        "source": source or "—",
        "published": published or "—",
        "summary": summary or "—",
        "link": link or "#",
    }


def horizon_scan(theme: str, term: str = "", limit: int = 10):
    query_parts = []

    if theme.strip():
        query_parts.append(f'"{theme.strip()}"')

    if term.strip():
        query_parts.append(f'"{term.strip()}"')

    query = " ".join(query_parts)

    rss_url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )

    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(rss_url, headers=headers, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "xml")
    items = soup.find_all("item")

    results = []
    for item in items[:limit]:
        results.append(parse_item(item))

    return results