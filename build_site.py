"""生成静态站点：site/index.html（最新一期）+ site/archive/YYYY-MM-DD.html。

每天一期（北京时间 07:00 更新）。index.html 侧栏列出最近 ARCHIVE_KEEP 期归档
（兼容旧的 YYYY-MM-DD-{am,pm}.html 命名，新的在前）。
"""
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

SITE_DIR = os.path.join("site")
ARCHIVE_DIR = os.path.join(SITE_DIR, "archive")
ARCHIVE_KEEP = 15

SECTION_META = {
    "youtube": {"zh": "YouTube 美国热榜", "en": "YOUTUBE TRENDING", "color": "#111111"},
    "reddit": {"zh": "Reddit 热帖", "en": "Reddit Hot", "color": "#111111"},
    "news": {"zh": "美国新闻头条", "en": "TOP STORIES · Google News", "color": "#e0457a"},
    "enso": {"zh": "厄尔尼诺动态", "en": "ENSO WATCH · NOAA + Google News", "color": "#0e7c86"},
    "google_trends": {"zh": "Google 美国热搜", "en": "Google Trending", "color": "#111111"},
    "x_trends": {"zh": "X 美国热搜", "en": "X TRENDS · getdaytrends", "color": "#111111"},
    "trump": {"zh": "特朗普动态", "en": "TRUMP LIVE · Truth Social", "color": "#1d4ed8"},
}

SECTION_ORDER = ["youtube", "news", "enso", "google_trends", "reddit", "x_trends", "trump"]

SOURCE_NAMES = {
    "news": "Google News",
    "enso": "Google News",
    "x_trends": "getdaytrends.com",
    "trump": "trumpstruth.org",
}

# X 热搜渲染在侧栏，其余板块渲染在主栏
SIDEBAR_SOURCES = {"x_trends"}


def _archive_label(name):
    """2026-11-06.html → '2026-11-06'；旧命名 2026-10-11-pm.html → '2026-10-11 下午'。"""
    stem = name[:-5] if name.endswith(".html") else name
    if stem.endswith("-am"):
        return stem[:-3] + " 上午"
    if stem.endswith("-pm"):
        return stem[:-3] + " 下午"
    return stem


def beijing_now():
    return datetime.now(timezone.utc) + timedelta(hours=8)


def _fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def _date_str(source, extra):
    """条目头部的日期显示。"""
    p = extra.get("published", "")
    if not p:
        return ""
    if source == "trump":
        return p[:10]
    try:
        return parsedate_to_datetime(p).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return p[:16]


def _domain(url):
    try:
        return (urlparse(url).hostname or "").replace("www.", "")
    except ValueError:
        return ""


def _render(env, context, out_path):
    tpl = env.get_template("page.html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(tpl.render(**context))


def build(results, translations, run_dt=None):
    """results: fetcher 返回结构列表；translations: {"key": {"zh_title","zh_snippet"}}。"""
    run_dt = run_dt or beijing_now()
    archive_name = f"{run_dt.strftime('%Y-%m-%d')}.html"

    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html"]),
    )

    sections = []
    for source in SECTION_ORDER:
        r = next((x for x in results if x["source"] == source), None)
        if r is None:
            continue  # 该源未启用（不在 main.py 的 FETCHERS 中），不渲染板块
        meta = SECTION_META[source]
        if not r.get("ok"):
            sections.append({
                "source": source,
                "zh": meta["zh"], "en": meta["en"], "color": meta["color"],
                "ok": False,
                "error": (r.get("error") or "未知错误")[:100],
                "entries": [],
            })
            continue
        items = []
        for it in r["items"]:
            zh = translations.get(it["id"], {})
            extra = it.get("extra", {})
            items.append({
                "id": it["id"],
                "title": it["title"],
                "url": it["url"],
                "snippet": it["snippet"],
                "extra": extra,
                "zh_title": zh.get("zh_title"),
                "zh_snippet": zh.get("zh_snippet"),
                "date_str": _date_str(source, extra),
                "domain": _domain(it.get("url", "")),
                "source_name": SOURCE_NAMES.get(source, ""),
            })
        sections.append({
            "source": source,
            "zh": meta["zh"], "en": meta["en"], "color": meta["color"],
            "ok": True, "error": None, "entries": items,
        })
        continue

    # 归档索引：最近 ARCHIVE_KEEP 期；新命名 YYYY-MM-DD.html 与旧命名
    # YYYY-MM-DD-{am,pm}.html 均能列出（字典序即时间序，新的在前）
    archives = []
    if os.path.isdir(ARCHIVE_DIR):
        names = sorted(
            (n for n in os.listdir(ARCHIVE_DIR) if n.endswith(".html")),
            reverse=True,
        )[:ARCHIVE_KEEP]
        archives = [{"name": n, "label": _archive_label(n)} for n in names]

    enso_index = next((r.get("index") for r in results
                       if r.get("source") == "enso" and r.get("index")), None)

    total_count = sum(len(s["entries"]) for s in sections)
    main_sections = [s for s in sections if s["source"] not in SIDEBAR_SOURCES]
    sidebar_sections = [s for s in sections if s["source"] in SIDEBAR_SOURCES]

    context = {
        "generated_at": _fmt_dt(run_dt) + "（北京）",
        "main_sections": main_sections,
        "sidebar_sections": sidebar_sections,
        "archives": archives,
        "enso_index": enso_index,
        "total_count": total_count,
        "is_archive": False,
        "archive_prefix": "archive/",
        "archive_date": run_dt.strftime("%Y-%m-%d"),
    }

    _render(env, context, os.path.join(SITE_DIR, "index.html"))
    _render(env, {**context, "is_archive": True, "archive_prefix": ""},
            os.path.join(ARCHIVE_DIR, archive_name))
    return archive_name
