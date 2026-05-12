import requests
from bs4 import BeautifulSoup


def horizon_scan(keyword):

    rss_url = (
        f"https://news.google.com/rss/search?q={keyword}"
    )

    response = requests.get(rss_url)

    soup = BeautifulSoup(
        response.content,
        "xml"
    )

    items = soup.find_all("item")

    report = []

    for item in items[:15]:

        report.append({
            "title": item.title.text,
            "summary": item.description.text,
            "link": item.link.text
        })

    return report