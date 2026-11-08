"""专题版块源（Google News 官方版块 RSS + 主题检索 RSS）。

作用：为政治/军事/科技/财经/娱乐/体育各板块提供保底内容（每板块 5~10 条），
不依赖各国媒体当天是否有对应分类的新闻。条目 country="国际"，outlet=原始媒体名。
"""
import hashlib
from urllib.parse import quote

import feedparser
import requests

from fetchers.news import _clean_snippet

SOURCE = "topics"

# (category, 主要源, 备用源, 条数)。topic: 官方版块；search: 主题检索
TOPICS = [
    ("politics",
     "search:(election OR government OR diplomacy OR parliament OR congress) when:3d",
     "topic:NATION", 8),
    ("military",
     "search:(military OR defense OR missile OR troops OR ceasefire OR airstrike) when:3d",
     "topic:WORLD", 8),
    ("tech", "topic:TECHNOLOGY", "search:(technology OR AI OR software) when:3d", 8),
    ("finance", "topic:BUSINESS", "search:(market OR economy OR stocks OR finance) when:3d", 8),
    ("entertainment", "topic:ENTERTAINMENT",
     "search:(movie OR film OR series OR music OR Netflix OR box office) when:3d", 10),
    ("sports", "topic:SPORTS", "search:(NBA OR NFL OR soccer OR tennis OR Olympics) when:3d", 8),
]

TOPIC_URL = "https://news.google.com/rss/headlines/section/topic/{name}?hl=en-US&gl=US&ceid=US:en"
SEARCH_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _fetch_url(url, category, limit):
    r = requests.get(url, timeout=30, headers={"User-Agent": "us-daily-brief/1.0"})
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    items = []
    for entry in feed.entries[:limit]:
        title = entry.get("title", "")
        if not title:
            continue
        guid = entry.get("guid") or entry.get("link") or title
        publisher = ""
        src = entry.get("source")
        if isinstance(src, dict):
            publisher = src.get("title", "")
        items.append({
            "id": "tp-" + hashlib.sha1(guid.encode("utf-8")).hexdigest()[:16],
            "title": title,
            "url": entry.get("link", ""),
            "snippet": _clean_snippet(entry.get("summary") or entry.get("description") or ""),
            "extra": {"published": entry.get("published", "")},
            "category": category,
            "country": "国际",
            "outlet": publisher or "Google News",
        })
    return items


def fetch(limit=None):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None}
    errors = []
    for category, primary, backup, n in TOPICS:
        items = []
        for spec in (primary, backup):
            if not spec:
                continue
            kind, _, val = spec.partition(":")
            url = TOPIC_URL.format(name=val) if kind == "topic" else SEARCH_URL.format(q=quote(val))
            try:
                items = _fetch_url(url, category, n)
                if items:
                    break
            except Exception as e:
                errors.append(f"{category}/{kind}: {type(e).__name__}")
        result["items"].extend(items)
    result["ok"] = bool(result["items"])
    if not result["ok"]:
        result["error"] = "专题版块源全部失败：" + "；".join(errors)
    elif errors:
        result["partial_errors"] = errors
    return result
