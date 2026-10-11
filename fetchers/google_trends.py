"""Google 美国每日热搜（trends.google.com 官方 RSS，无需密钥）。

用 ElementTree 解析：feedparser 会把重复的 ht:news_item 拍平只留最后一条，
而 ET 的 {* } 通配命名空间能稳定取到每条热搜下的全部相关新闻标题。
"""
import requests
import xml.etree.ElementTree as ET

SOURCE = "google_trends"
FEED_URL = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"


def _text(el, tag):
    node = el.find(tag)
    return (node.text or "").strip() if node is not None and node.text else ""


def fetch(limit=15):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None}
    try:
        resp = requests.get(
            FEED_URL,
            timeout=30,
            headers={"User-Agent": "us-daily-brief/1.0"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS 无 channel")
        for item_el in channel.findall("item")[:limit]:
            title = _text(item_el, "title")
            if not title:
                continue
            traffic = _text(item_el, "{*}approx_traffic")
            news_titles = [(el.text or "").strip() for el in item_el.iter()
                           if el.tag.rsplit("}", 1)[-1] == "news_item_title"
                           and el.text and el.text.strip()]
            snippet_parts = []
            if traffic:
                snippet_parts.append(f"热度：{traffic}")
            if news_titles:
                snippet_parts.append("相关报道：" + "；".join(news_titles[:3]))
            result["items"].append({
                "id": "gt-" + (_text(item_el, "guid") or _text(item_el, "link"))[-48:],
                "title": title,
                "url": _text(item_el, "link"),
                "snippet": "。".join(snippet_parts),
                "extra": {
                    "traffic": traffic,
                    "news_titles": news_titles[:3],
                },
            })
        result["ok"] = bool(result["items"])
        if not result["ok"]:
            result["error"] = "Google Trends RSS 解析为空"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result
