"""厄尔尼诺/拉尼娜（ENSO）动态。

指数：NOAA CPC 周度 OISST（wksst9120.for，Niño 3.4 区 SST/SSTA）。
新闻：Google News 搜索 RSS（近 14 天 El Niño / La Niña / ENSO 相关报道）。
本机访问不了 NOAA/Google 域名时用构造 fixture 验证解析。
"""
import re
from datetime import datetime

import feedparser
import requests

from fetchers.news import _clean_snippet

SOURCE = "enso"
SST_URL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"
ADVISORY_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/"
NEWS_URL = ("https://news.google.com/rss/search?q=%28El%20Ni%C3%B1o%20OR%20La%20Ni%C3%B1a"
            "%20OR%20ENSO%29%20when%3A14d&hl=en-US&gl=US&ceid=US:en")

# 数据行：Week + 4 区（各 SST+SSTA）；SST/SSTA 间正值空格分隔、负值直接相连（26.5-0.2）
_LINE_RE = re.compile(
    r"^\s*(\d{2}[A-Z]{3}\d{4})\s+"
    r"(\d+\.\d)\s*(-?\d+\.\d)\s+"
    r"(\d+\.\d)\s*(-?\d+\.\d)\s+"
    r"(\d+\.\d)\s*(-?\d+\.\d)\s+"
    r"(\d+\.\d)\s*(-?\d+\.\d)"
)


def _grade(ssta):
    """SSTA 分级：|SSTA|>=0.5 厄尔尼诺(正)/拉尼娜(负)，其间中性；
    强度：0.5~0.9 弱、1.0~1.4 中等、1.5~1.9 强、>=2.0 超强。"""
    if ssta >= 0.5:
        word, kind = "厄尔尼诺", "el_nino"
    elif ssta <= -0.5:
        word, kind = "拉尼娜", "la_nina"
    else:
        return "中性", "neutral"
    a = abs(ssta)
    if a >= 2.0:
        level = "超强"
    elif a >= 1.5:
        level = "强"
    elif a >= 1.0:
        level = "中等"
    else:
        level = "弱"
    return level + word, kind


def parse_index(text):
    """从 wksst9120.for 文本解析最新一周 Niño 3.4 指数；解析失败返回 None。"""
    last = None
    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if m:
            last = m
    if not last:
        return None
    try:
        week = datetime.strptime(last.group(1), "%d%b%Y").date().isoformat()
        sst = float(last.group(6))    # 第 3 区（Niño 3.4）SST
        ssta = float(last.group(7))   # 第 3 区 SSTA
        status, kind = _grade(ssta)
        return {"week": week, "sst": sst, "ssta": ssta,
                "status": status, "kind": kind, "url": ADVISORY_URL}
    except ValueError:
        return None


def _fetch_index():
    try:
        r = requests.get(SST_URL, timeout=30,
                         headers={"User-Agent": "us-daily-brief/1.0"})
        r.raise_for_status()
        return parse_index(r.text)
    except Exception:
        return None


def _fetch_news(limit):
    try:
        r = requests.get(NEWS_URL, timeout=30,
                         headers={"User-Agent": "us-daily-brief/1.0"})
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        items = []
        for entry in feed.entries[:limit]:
            title = entry.get("title", "")
            if not title:
                continue
            raw = entry.get("summary") or entry.get("description") or ""
            items.append({
                "id": "en-" + (entry.get("guid") or entry.get("link", ""))[-48:],
                "title": title,
                "url": entry.get("link", ""),
                "snippet": _clean_snippet(raw),
                "extra": {
                    "source": (entry.get("source") or {}).get("title", "")
                    if isinstance(entry.get("source"), dict) else "",
                    "published": entry.get("published", ""),
                },
            })
        return items
    except Exception:
        return []


def fetch(limit=10):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None, "index": None}
    try:
        result["index"] = _fetch_index()
        result["items"] = _fetch_news(limit)
        result["ok"] = bool(result["items"])
        if not result["ok"]:
            result["error"] = "ENSO 新闻抓取失败（NOAA 指数单独获取，见页首卡片）"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result
