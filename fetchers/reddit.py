"""Reddit r/news 与 r/worldnews 当日热门帖（公开 JSON 接口，无需密钥）。

Reddit 会封数据中心 IP，带多级回退：
1. 直连 www.reddit.com
2. old.reddit.com
3. r.jina.ai 免费代理（从其自身 IP 抓取，返回原始 JSON 文本，可能有包装，解析容错）
每个版块任一方式拿到数据即算成功。
"""
import json
import re

import requests

SOURCE = "reddit"
SUBREDDITS = ["news", "worldnews"]
JINA_PREFIX = "https://r.jina.ai/"
HEADERS = {"User-Agent": "us-daily-brief/1.0 (news aggregation)"}


def _extract_json(text):
    """从（可能带包装的）响应文本中提取 Reddit listing JSON。"""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("响应中未找到 JSON 对象")
    return json.loads(text[start:end + 1])


def _parse_listing(text, sub, limit):
    data = _extract_json(text)
    items = []
    for post in data.get("data", {}).get("children", []):
        d = post.get("data", {})
        title = d.get("title", "")
        if not title:
            continue
        snippet = (d.get("selftext", "") or "").strip()
        items.append({
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
        if len(items) >= limit:
            break
    return items


def _fetch_subreddit(sub, limit):
    """单个版块：按回退链尝试，返回 (items, None) 或 (None, error)。"""
    import time
    from urllib.parse import quote
    target = f"https://www.reddit.com/r/{sub}/top.json?t=day&limit={limit}"
    candidates = [
        ("直连", target, 30),
        ("old.reddit.com", target.replace("://www.", "://old."), 30),
        # jina 免费代理较慢，放宽超时；限速 20rpm，我们每天只用几次
        ("r.jina.ai", JINA_PREFIX + target, 90),
    ]
    errors = []
    for name, url, timeout in candidates:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            items = _parse_listing(resp.text, sub, limit)
            if items:
                return items, None
            errors.append(f"{name}: 空列表")
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}")
    # 最后兜底：allorigins 免费代理。它有时返回 HTML 外壳（无 data.children），
    # 解析阶段会自动识别丢弃；已知不稳定（520/522 频发），重试 2 次间隔 3 秒。
    proxy_url = "https://api.allorigins.win/raw?url=" + quote(target, safe="")
    for attempt in range(2):
        try:
            resp = requests.get(proxy_url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            items = _parse_listing(resp.text, sub, limit)
            if items:
                return items, None
            errors.append(f"allorigins(第{attempt + 1}次): 返回内容无可解析帖子数据")
        except Exception as e:
            errors.append(f"allorigins(第{attempt + 1}次): {type(e).__name__}")
        if attempt == 0:
            time.sleep(3)
    return None, "；".join(errors)


def fetch(limit=15):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None}
    try:
        errors = []
        for sub in SUBREDDITS:
            items, err = _fetch_subreddit(sub, limit)
            if items:
                result["items"].extend(items)
            else:
                errors.append(f"r/{sub}: {err}")
        result["ok"] = bool(result["items"])
        if not result["ok"]:
            result["error"] = "Reddit 全部回退失败：" + "；".join(errors)
        elif errors:
            # 部分版块失败：保留成功版块，error 记录失败原因
            result["error"] = None
            print(f"[fetch] reddit 部分版块失败：{'；'.join(errors)}")
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result
