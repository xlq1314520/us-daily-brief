"""多国媒体源（配置表驱动）。每个源独立容错，单源失败不影响其他源。

统一返回标准结构，item 额外带 country / outlet 字段。
"""
import hashlib

import feedparser
import requests

from fetchers.news import _clean_snippet

SOURCE = "outlets"
PER_SOURCE = 6

OUTLETS = [
    # (country, outlet, feed_url)
    ("美国", "The New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    ("美国", "CNN", "http://rss.cnn.com/rss/edition.rss"),
    ("美国", "NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("俄罗斯", "TASS", "https://tass.com/rss/v2.xml"),
    ("俄罗斯", "The Moscow Times", "https://www.themoscowtimes.com/rss/news"),
    ("中国", "Global Times", "https://www.globaltimes.cn/rss/outbrain.xml"),
    ("法国", "France 24", "https://www.france24.com/en/rss"),
    ("法国", "RFI", "https://www.rfi.fr/en/rss"),
    ("英国", "BBC", "https://www.bbc.com/news/world/rss.xml"),
]


def _fetch_feed(country, outlet, url, limit):
    resp = requests.get(url, timeout=30, headers={"User-Agent": "us-daily-brief/1.0"})
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    items = []
    for entry in feed.entries[:limit]:
        title = entry.get("title", "")
        if not title:
            continue
        guid = entry.get("guid") or entry.get("link") or title
        raw = entry.get("summary") or entry.get("description") or ""
        items.append({
            "id": "ol-" + hashlib.sha1(guid.encode("utf-8")).hexdigest()[:16],
            "title": title,
            "url": entry.get("link", ""),
            "snippet": _clean_snippet(raw),
            "extra": {
                "outlet": outlet,
                "published": entry.get("published", ""),
            },
            "country": country,
            "outlet": outlet,
        })
    return items


def fetch(limit=PER_SOURCE):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None}
    errors = []
    for country, outlet, url in OUTLETS:
        try:
            items = _fetch_feed(country, outlet, url, limit or PER_SOURCE)
            result["items"].extend(items)
        except Exception as e:
            errors.append(f"{outlet}: {type(e).__name__}")
    result["ok"] = bool(result["items"])
    if not result["ok"]:
        result["error"] = "全部媒体源失败：" + "；".join(errors)
    elif errors:
        result["partial_errors"] = errors
    return result
