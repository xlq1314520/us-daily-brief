"""Reddit r/news 与 r/worldnews 当日热门帖（公开 JSON 接口，无需密钥）。"""
import requests

SOURCE = "reddit"
SUBREDDITS = ["news", "worldnews"]


def fetch(limit=15):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None}
    headers = {"User-Agent": "us-daily-brief/1.0 (news aggregation)"}
    try:
        for sub in SUBREDDITS:
            url = f"https://www.reddit.com/r/{sub}/top.json?t=day&limit={limit}"
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for post in data.get("data", {}).get("children", []):
                d = post.get("data", {})
                title = d.get("title", "")
                if not title:
                    continue
                snippet = (d.get("selftext", "") or "").strip()
                result["items"].append({
                    "id": "rd-" + d.get("id", ""),
                    "title": title,
                    "url": d.get("url_overridden_by_dest") or ("https://www.reddit.com" + d.get("permalink", "")),
                    "snippet": snippet[:500],
                    "extra": {
                        "subreddit": sub,
                        "score": d.get("score", 0),
                        "num_comments": d.get("num_comments", 0),
                        "author": d.get("author", ""),
                        "permalink": "https://www.reddit.com" + d.get("permalink", ""),
                    },
                })
        result["ok"] = bool(result["items"])
        if not result["ok"]:
            result["error"] = "Reddit 返回空列表"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result
