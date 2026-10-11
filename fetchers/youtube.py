"""YouTube 美国热门视频榜（YouTube Data API v3）。

需要环境变量 YOUTUBE_API_KEY。无 key 时返回 ok=False，不抛出异常。
"""
import os

import requests

SOURCE = "youtube"


def fetch(limit=20):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None}
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        result["error"] = "未配置 YOUTUBE_API_KEY，跳过 YouTube 板块"
        return result
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "snippet",
                "chart": "mostPopular",
                "regionCode": "US",
                "maxResults": limit,
                "key": api_key,
            },
            timeout=30,
            headers={"User-Agent": "us-daily-brief/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        for v in data.get("items", []):
            snippet = v.get("snippet", {})
            result["items"].append({
                "id": "yt-" + v.get("id", ""),
                "title": snippet.get("title", ""),
                "url": "https://www.youtube.com/watch?v=" + v.get("id", ""),
                "snippet": snippet.get("channelTitle", ""),
                "extra": {
                    "channel": snippet.get("channelTitle", ""),
                    "publishedAt": snippet.get("publishedAt", ""),
                    "categoryId": snippet.get("categoryId", ""),
                },
            })
        result["ok"] = bool(result["items"])
        if not result["ok"]:
            result["error"] = "YouTube API 返回空列表"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result
