"""Google News 美国版头条 RSS（无需密钥）。"""
import html as html_mod
import re

import feedparser
import requests

SOURCE = "news"
FEED_URL = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
_TAG_RE = re.compile(r"<[^>]+>")
MAX_SNIPPET = 200


def _clean_snippet(raw):
    """Google News RSS 的 summary/description 是原始 HTML
    （<ol><li><a href=...>标题</a>&nbsp;<font>来源</font></li></ol>），
    剥掉标签转义实体，折叠空白，截断到 200 字符。"""
    text = _TAG_RE.sub(" ", raw or "")
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_SNIPPET]


def fetch(limit=20):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None}
    try:
        resp = requests.get(
            FEED_URL,
            timeout=30,
            headers={"User-Agent": "us-daily-brief/1.0"},
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "")
            if not title:
                continue
            raw = entry.get("summary") or entry.get("description") or ""
            result["items"].append({
                "id": "gn-" + entry.get("guid", entry.get("link", ""))[:64],
                "title": title,
                "url": entry.get("link", ""),
                "snippet": _clean_snippet(raw),
                "extra": {
                    "source": (entry.get("source") or {}).get("title", "") if isinstance(entry.get("source"), dict) else "",
                    "published": entry.get("published", ""),
                },
            })
        result["ok"] = bool(result["items"])
        if not result["ok"]:
            result["error"] = "Google News RSS 解析为空"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result
