"""生成静态站点：site/index.html（最新一期）+ site/archive/YYYY-MM-DD.html。

每天一期（北京时间 07:00 更新）。页面为顶部标签栏切换结构：
头条 / 政治 / 军事 / 科技 / 财经 / 厄尔尼诺专板 / X 热搜 / 特朗普动态 / 历史归档。
归档兼容旧的 YYYY-MM-DD-{am,pm}.html 命名，新的在前。
"""
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

SITE_DIR = os.path.join("site")
ARCHIVE_DIR = os.path.join(SITE_DIR, "archive")
ARCHIVE_KEEP = 30

CAT_TABS = [("politics", "政治"), ("military", "军事"), ("tech", "科技"),
            ("finance", "财经"), ("entertainment", "娱乐"), ("sports", "体育")]
COUNTRY_ORDER = {"美国": 0, "英国": 1, "法国": 2, "俄罗斯": 3, "中国": 4, "国际": 5}
COUNTRY_COLORS = {
    "美国": "#1d4ed8", "英国": "#9f1239", "法国": "#1e40af",
    "俄罗斯": "#475569", "中国": "#b91c1c", "国际": "#0e7c86",
}

SOURCE_NAMES = {
    "news": "Google News",
    "enso": "Google News",
    "x_trends": "getdaytrends.com",
    "trump": "trumpstruth.org",
}


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


def _date_str(source, extra):
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


def _entry(it, source, translations):
    extra = it.get("extra", {})
    zh = translations.get(it["id"], {})
    country = it.get("country") or ""
    return {
        "id": it["id"],
        "title": it["title"],
        "url": it["url"],
        "snippet": it["snippet"],
        "extra": extra,
        "zh_title": zh.get("zh_title"),
        "zh_snippet": zh.get("zh_snippet"),
        "category": it.get("category") or zh.get("category") or "general",
        "country": country,
        "country_color": COUNTRY_COLORS.get(country, "#555555"),
        "outlet": it.get("outlet") or extra.get("outlet") or extra.get("source") or SOURCE_NAMES.get(source, ""),
        "date_str": _date_str(source, extra),
        "domain": _domain(it.get("url", "")),
        "source_name": SOURCE_NAMES.get(source, ""),
        "source": source,
    }


def build(results, translations, run_dt=None):
    """results: fetcher 返回结构列表；translations: {"key": {"zh_title","zh_snippet","category"}}。"""
    run_dt = run_dt or beijing_now()
    archive_name = f"{run_dt.strftime('%Y-%m-%d')}.html"
    by_source = {r["source"]: r for r in results}

    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html"]),
    )

    def entries_of(source):
        r = by_source.get(source)
        if not r or not r.get("ok"):
            return []
        return [_entry(it, source, translations) for it in r["items"]]

    def by_country(entries):
        return sorted(entries, key=lambda e: COUNTRY_ORDER.get(e["country"], 9))

    # ---- 组装各标签模块 ----
    modules = []  # [{"key","label","kind",...}]，模板按列表遍历避免 dict.items 坑

    news_entries = entries_of("news")
    outlet_entries = entries_of("outlets")
    headlines = news_entries + by_country([e for e in outlet_entries if e["category"] == "general"])
    outlets_r = by_source.get("outlets")
    partial_note = ""
    if outlets_r and outlets_r.get("partial_errors"):
        partial_note = "部分媒体源本次失败：" + "、".join(outlets_r["partial_errors"])
    modules.append({"key": "headlines", "label": "头条", "kind": "news",
                    "entries": headlines, "note": partial_note,
                    "error": None if headlines else "头条源本次更新失败"})

    topics_entries = entries_of("topics")
    for cat, label in CAT_TABS:
        # 各国媒体对照在前，专题版块源保底在后（保证每板块 5 条以上）
        entries = by_country([e for e in outlet_entries if e["category"] == cat]) + \
                  [e for e in topics_entries if e["category"] == cat]
        note = ""
        if 0 < len(entries) < 5:
            note = f"本期该类内容较少（{len(entries)} 条）"
        modules.append({"key": cat, "label": label, "kind": "news", "entries": entries,
                        "note": note, "error": None if entries else "本期暂无此类报道"})

    enso_r = by_source.get("enso")
    enso_groups = []
    if enso_r and enso_r.get("groups"):
        for g in enso_r["groups"]:
            enso_groups.append({"key": g["key"], "name": g["name"],
                                "entries": [_entry(it, "enso", translations) for it in g["items"]]})
    modules.append({"key": "enso", "label": "厄尔尼诺专板", "kind": "enso",
                    "groups": enso_groups,
                    "error": None if enso_groups else "ENSO 各子板块本次更新失败（指数见页首卡片）"})

    xt_entries = entries_of("x_trends")
    modules.append({"key": "x_trends", "label": "X 美国热搜", "kind": "x_trends",
                    "entries": xt_entries,
                    "error": None if xt_entries else "X 热搜本次更新失败"})

    trump_entries = entries_of("trump")
    modules.append({"key": "trump", "label": "特朗普动态", "kind": "trump",
                    "entries": trump_entries,
                    "error": None if trump_entries else "特朗普动态本次更新失败"})

    # 归档索引：最近 ARCHIVE_KEEP 期；新旧命名混排，新的在前
    archives = []
    if os.path.isdir(ARCHIVE_DIR):
        names = sorted(
            (n for n in os.listdir(ARCHIVE_DIR) if n.endswith(".html")),
            reverse=True,
        )[:ARCHIVE_KEEP]
        archives = [{"name": n, "label": _archive_label(n)} for n in names]

    enso_index = enso_r.get("index") if enso_r else None
    total_count = sum(len(m.get("entries", [])) for m in modules) + \
        sum(len(g["entries"]) for m in modules if m["kind"] == "enso" for g in m["groups"])

    context = {
        "generated_at": run_dt.strftime("%Y-%m-%d %H:%M") + "（北京）",
        "modules": modules,
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
