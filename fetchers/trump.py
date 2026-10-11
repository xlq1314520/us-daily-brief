"""特朗普 Truth Social 动态。Truth Social 是 Mastodon 分支，公开 API 可用；
直接 API 失败时回退 RSSHub 公共实例轮询。帖子限定为最近 3 天内。"""
import re
from datetime import datetime, timedelta, timezone

import feedparser
import requests

SOURCE = "trump"
ACCOUNT_ID = "107780257626128497"  # realDonaldTrump
ACCOUNT_ACCT = "realDonaldTrump"
MAX_AGE_DAYS = 3

RSSHub_INSTANCES = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub.ktachibana.party",
    "https://rsshub.woodland.cafe",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s):
    s = _TAG_RE.sub("", s or "")
    return re.sub(r"\s+", " ", s).strip()


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _recent_only(items):
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    kept = [it for it in items if it.get("_dt") and it["_dt"] >= cutoff]
    for it in kept:
        it.pop("_dt", None)
    return kept


def _fetch_direct(limit):
    """Truth Social Mastodon 兼容 API。"""
    headers = {"User-Agent": UA}
    acct_id = ACCOUNT_ID
    try:
        r = requests.get(
            f"https://truthsocial.com/api/v1/accounts/{acct_id}/statuses",
            params={"limit": limit}, headers=headers, timeout=30,
        )
        if r.status_code in (401, 403, 404):
            lookup = requests.get(
                "https://truthsocial.com/api/v1/accounts/lookup",
                params={"acct": ACCOUNT_ACCT}, headers=headers, timeout=30,
            )
            lookup.raise_for_status()
            acct_id = lookup.json().get("id", acct_id)
            r = requests.get(
                f"https://truthsocial.com/api/v1/accounts/{acct_id}/statuses",
                params={"limit": limit}, headers=headers, timeout=30,
            )
        r.raise_for_status()
        posts = r.json()
        if not isinstance(posts, list):
            return None, "Truth Social API 返回非列表数据"
        items = []
        for p in posts:
            content = _strip_html(p.get("content", ""))
            if not content:
                continue
            dt = _parse_dt(p.get("created_at", ""))
            items.append({
                "id": "ts-" + str(p.get("id", "")),
                "title": content[:120] + ("…" if len(content) > 120 else ""),
                "url": p.get("url", ""),
                "snippet": content,
                "extra": {
                    "published": p.get("created_at", ""),
                    "replies_count": p.get("replies_count", 0),
                    "reblogs_count": p.get("reblogs_count", 0),
                    "favourites_count": p.get("favourites_count", 0),
                    "via": "truthsocial.com API",
                },
                "_dt": dt,
            })
        kept = _recent_only(items)
        if kept:
            return kept, None
        return None, f"Truth Social 最近 {MAX_AGE_DAYS} 天内无新帖"
    except Exception as e:
        return None, f"Truth Social API: {type(e).__name__}: {e}"


def _fetch_rsshub(limit):
    errors = []
    for base in RSSHub_INSTANCES:
        try:
            r = requests.get(
                f"{base}/truthsocial/user/{ACCOUNT_ACCT}",
                headers={"User-Agent": UA}, timeout=30,
            )
            if r.status_code != 200:
                errors.append(f"{base}: HTTP {r.status_code}")
                continue
            feed = feedparser.parse(r.content)
            if not feed.entries:
                errors.append(f"{base}: RSS 无条目")
                continue
            items = []
            for entry in feed.entries[:limit]:
                title = _strip_html(entry.get("title", ""))
                snippet = _strip_html(entry.get("summary", ""))
                if not title and not snippet:
                    continue
                dt = None
                for key in ("published_parsed", "updated_parsed"):
                    if entry.get(key):
                        dt = datetime(*entry[key][:6], tzinfo=timezone.utc)
                        break
                items.append({
                    "id": "ts-" + (entry.get("id", "") or entry.get("link", ""))[-48:],
                    "title": title[:120] + ("…" if len(title) > 120 else ""),
                    "url": entry.get("link", ""),
                    "snippet": snippet[:500],
                    "extra": {
                        "published": entry.get("published", ""),
                        "via": f"RSSHub ({base})",
                    },
                    "_dt": dt,
                })
            kept = _recent_only(items)
            if kept:
                return kept, None
            errors.append(f"{base}: 最近 {MAX_AGE_DAYS} 天内无新帖")
        except Exception as e:
            errors.append(f"{base}: {type(e).__name__}")
    return None, "RSSHub 全部实例失败：" + "；".join(errors)


def fetch(limit=20):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None}
    items, err = _fetch_direct(limit)
    if items:
        result["ok"] = True
        result["items"] = items
        return result
    direct_err = err
    items, err = _fetch_rsshub(limit)
    if items:
        result["ok"] = True
        result["items"] = items
        return result
    result["error"] = f"{direct_err} | {err}"
    return result
