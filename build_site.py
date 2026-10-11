"""生成静态站点：site/index.html（最新一期）+ site/archive/YYYY-MM-DD-{am,pm}.html。

上午/下午按北京时间（UTC+8）判断：0~11 点为 am，12~23 点为 pm。
index.html 底部列出最近 30 期归档链接。
"""
import os
from datetime import datetime, timedelta, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

SITE_DIR = os.path.join("site")
ARCHIVE_DIR = os.path.join(SITE_DIR, "archive")
ARCHIVE_KEEP = 30

SECTION_META = {
    "youtube": {"zh": "YouTube 美国热榜", "en": "YouTube US Trending"},
    "reddit": {"zh": "Reddit 热帖", "en": "Reddit Hot (r/news · r/worldnews)"},
    "news": {"zh": "美国新闻头条", "en": "US Headlines (Google News)"},
    "google_trends": {"zh": "Google 美国热搜", "en": "Google US Trending Searches"},
    "x_trends": {"zh": "X 美国热搜", "en": "X US Trends"},
    "trump": {"zh": "特朗普动态", "en": "Trump on Truth Social"},
}

SECTION_ORDER = ["youtube", "news", "google_trends", "reddit", "x_trends", "trump"]


def beijing_now():
    return datetime.now(timezone.utc) + timedelta(hours=8)


def _fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") + "（北京）"


def _render(env, context, out_path):
    tpl = env.get_template("page.html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(tpl.render(**context))


def build(results, translations, run_dt=None):
    """results: fetcher 返回结构列表；translations: {"key": {"zh_title","zh_snippet"}}。"""
    run_dt = run_dt or beijing_now()
    stamp = run_dt.strftime("%Y-%m-%d-%H%M")
    period = "am" if run_dt.hour < 12 else "pm"
    archive_name = f"{run_dt.strftime('%Y-%m-%d')}-{period}.html"

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
                "zh": meta["zh"], "en": meta["en"],
                "ok": False,
                "error": r.get("error") or "未知错误",
                "entries": [],
            })
            continue
        items = []
        for it in r["items"]:
            zh = translations.get(it["id"], {})
            items.append({
                "id": it["id"],
                "title": it["title"],
                "url": it["url"],
                "snippet": it["snippet"],
                "extra": it.get("extra", {}),
                "zh_title": zh.get("zh_title"),
                "zh_snippet": zh.get("zh_snippet"),
            })
        sections.append({
            "source": source,
            "zh": meta["zh"], "en": meta["en"],
            "ok": True, "error": None, "entries": items,
        })

    # 归档索引：最近 ARCHIVE_KEEP 期
    archives = []
    if os.path.isdir(ARCHIVE_DIR):
        names = sorted(
            (n for n in os.listdir(ARCHIVE_DIR) if n.endswith(".html")),
            reverse=True,
        )[:ARCHIVE_KEEP]
        archives = [{"name": n, "label": n.replace(".html", "").replace("-", " ")}
                    for n in names]

    context = {
        "title": "美国每日热榜 · 中英对照",
        "generated_at": _fmt_dt(run_dt),
        "period_label": "上午版" if period == "am" else "下午版",
        "sections": sections,
        "archives": archives,
        "is_archive": False,
    }

    _render(env, context, os.path.join(SITE_DIR, "index.html"))
    _render(env, {**context, "is_archive": True},
            os.path.join(ARCHIVE_DIR, archive_name))
    return archive_name
