"""特朗普 Truth Social 动态。

主数据源 trumpstruth.org（Truth Social 帖子的独立存档站，云端实测直连可达）。
回退顺序：
1. trumpstruth.org 直连 HTML 解析（含 ISO 时间戳，过滤最近 3 天）
2. r.jina.ai 代理拉 trumpstruth.org（markdown，时间未知）
3. Truth Social 官方 Mastodon API
4. RSSHub 公共实例轮询
"""
import json
import re
from datetime import datetime, timedelta, timezone

import feedparser
import requests

SOURCE = "trump"
ACCOUNT_ID = "107780257626128497"  # realDonaldTrump
ACCOUNT_ACCT = "realDonaldTrump"
MAX_AGE_DAYS = 3

TRUMPTRUTH_URL = "https://trumpstruth.org/"
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


def _beijing_str(dt):
    if not dt:
        return "时间未知"
    return (dt + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M") + "（北京）"


def _recent_only(items):
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    kept = [it for it in items if it.get("_dt") and it["_dt"] >= cutoff]
    for it in kept:
        it.pop("_dt", None)
    return kept


def _statuses_to_items(posts, via):
    """Mastodon Status 列表 → 统一条目结构（带 _dt 内部字段，供最近 3 天过滤）。"""
    items = []
    for p in posts:
        if not isinstance(p, dict):
            continue
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
                "via": via,
            },
            "_dt": dt,
        })
    return items


# ---------------------------------------------------------------------------
# 1. trumpstruth.org 直连
# ---------------------------------------------------------------------------

def _parse_trumpstruth_html(text, limit):
    """解析 trumpstruth.org 首页 HTML：class="status" 块，正文在 class="status__content"，
    时间为 time 标签的 datetime 属性，帖子链接在 data-status-url。"""
    items = []
    seen_urls = set()
    # 按 status 块切分（容忍属性间空白/换行；最新一块可能没有 data-status-url，从其内部链接补取）
    parts = re.split(r'<div\s+class="status"([^>]*)>', text)
    for k in range(1, len(parts) - 1, 2):
        attrs, body = parts[k], parts[k + 1]
        um = re.search(r'data-status-url="([^"]+)"', attrs)
        if um:
            url = um.group(1)
        else:
            lm = re.search(r'https?://(?:www\.)?trumpstruth\.org/statuses/(\d+)', body)
            if not lm:
                continue
            url = lm.group(0)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        dm = re.search(r'datetime="([^"]+)"', body)
        dt = _parse_dt(dm.group(1)) if dm else None

        # 正文：从 status__content 到 attachments/footer 之间，避免嵌套 div 截断
        content = ""
        cm = re.search(r'<div\s+class="status__content"[^>]*>', body)
        if cm:
            start = cm.end()
            end_m = re.search(r'<div\s+class="status__attachments|<div\s+class="status__footer|<button[^>]*class="post-preview-toggle', body[start:])
            end = start + end_m.start() if end_m else len(body)
            content = _strip_html(body[start:end])

        media = ""
        if not content:
            if 'status-attachment--video' in body:
                media, content = "video", "[Video post]"
            elif 'status-attachment--image' in body:
                media, content = "image", "[Image post]"
            else:
                continue
        items.append({
            "id": "tt-" + url.rstrip("/").rsplit("/", 1)[-1],
            "title": content[:80] + ("…" if len(content) > 80 else ""),
            "url": url,
            "snippet": content if media == "" else "",
            "extra": {
                "published": _beijing_str(dt),
                "media": media,
                "via": "trumpstruth.org",
            },
            "_dt": dt,
        })
        if len(items) >= limit:
            break
    return items


def _fetch_trumpstruth(limit):
    try:
        r = requests.get(TRUMPTRUTH_URL, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        items = _parse_trumpstruth_html(r.text, limit)
        if not items:
            return None, "trumpstruth.org: 未解析到帖子（页面结构可能改版）"
        kept = _recent_only(items)
        if kept:
            return kept, None
        return None, f"trumpstruth.org: 最近 {MAX_AGE_DAYS} 天内无新帖"
    except Exception as e:
        return None, f"trumpstruth.org: {type(e).__name__}"


# ---------------------------------------------------------------------------
# 2. r.jina.ai 代理拉 trumpstruth.org（markdown，无时间戳）
# ---------------------------------------------------------------------------

def _parse_jina_markdown(text, limit):
    """jina 返回的 trumpstruth.org markdown 尽力提取：按帖子链接分段。"""
    lines = text.splitlines()
    items = []
    url_re = re.compile(r"https?://(?:www\.)?trumpstruth\.org/statuses/(\d+)")
    dt_re = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
    prev_end = 0
    for i, line in enumerate(lines):
        m = url_re.search(line)
        if not m:
            continue
        seg = lines[prev_end:i]
        prev_end = i + 1
        published, dt = "时间未知", None
        for s in reversed(seg):
            dm = dt_re.search(s)
            if dm:
                dt = _parse_dt(dm.group(0))
                if dt:
                    published = _beijing_str(dt)
                break
        content_lines = [s.strip() for s in seg
                         if s.strip() and not s.strip().startswith("#")
                         and not dt_re.search(s) and not url_re.search(s)]
        content = _strip_html(" ".join(content_lines))
        if not content:
            continue
        items.append({
            "id": "tt-" + m.group(1),
            "title": content[:80] + ("…" if len(content) > 80 else ""),
            "url": m.group(0),
            "snippet": content[:500],
            "extra": {"published": published, "via": "r.jina.ai (trumpstruth.org)"},
            "_dt": dt,
        })
        if len(items) >= limit:
            break
    return items


def _fetch_jina(limit):
    try:
        r = requests.get("https://r.jina.ai/" + TRUMPTRUTH_URL,
                         headers={"User-Agent": UA}, timeout=90)
        r.raise_for_status()
        items = _parse_jina_markdown(r.text, limit)
        if items:
            for it in items:
                it.pop("_dt", None)
            return items, None
        return None, "r.jina.ai: 未能从 markdown 中提取帖子"
    except Exception as e:
        return None, f"r.jina.ai: {type(e).__name__}"


# ---------------------------------------------------------------------------
# 3/4. Truth Social 官方 API + RSSHub（最后兜底）
# ---------------------------------------------------------------------------

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
        kept = _recent_only(_statuses_to_items(posts, "truthsocial.com API"))
        if kept:
            return kept, None
        return None, f"Truth Social 最近 {MAX_AGE_DAYS} 天内无新帖"
    except Exception as e:
        return None, f"Truth Social API: {type(e).__name__}"


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
    errors = []
    for fn in (_fetch_trumpstruth, _fetch_jina, _fetch_direct, _fetch_rsshub):
        items, err = fn(limit)
        if items:
            result["ok"] = True
            result["items"] = items
            return result
        errors.append(err or f"{fn.__name__}: 无数据")
    result["error"] = " | ".join(errors)
    return result
