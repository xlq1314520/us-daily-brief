"""Google News 美国版头条 RSS（无需密钥）。"""
import feedparser
import requests

SOURCE = "news"
FEED_URL = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"


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
            snippet = ""
            if entry.get("summary"):
                snippet = entry["summary"]
            elif entry.get("description"):
                snippet = entry["description"]
            result["items"].append({
                "id": "gn-" + entry.get("guid", entry.get("link", ""))[:64],
                "title": title,
                "url": entry.get("link", ""),
                "snippet": snippet[:500],
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
