"""入口：抓取 5 个数据源 → 批量翻译 → 生成静态站点。

用法：
    python main.py                # 抓取 + 翻译（需要 MOONSHOT_API_KEY）
    python main.py --no-translate # 抓取后跳过翻译，先跑通全流程
"""
import argparse
import json
import os
import traceback
from datetime import datetime

import build_site
import translator
from fetchers import news, reddit, trump, x_trends, youtube

# 用户暂不使用油管：重新启用时在列表中加回 youtube 即可
FETCHERS = [news, reddit, x_trends, trump]

# 每板块最多翻译/展示的条数
SECTION_LIMITS = {
    "youtube": 20,
    "news": 20,
    "reddit": 30,
    "x_trends": 20,
    "trump": 20,
}


def run_fetchers():
    results = []
    for mod in FETCHERS:
        limit = SECTION_LIMITS.get(mod.SOURCE, 20)
        try:
            r = mod.fetch(limit=limit)
        except Exception:
            r = {"ok": False, "source": mod.SOURCE, "items": [],
                 "error": "fetcher 内部异常：" + traceback.format_exc(limit=1).strip().splitlines()[-1]}
        results.append(r)
        status = f"OK {len(r['items'])} 条" if r["ok"] else f"失败 ({r['error']})"
        print(f"[fetch] {r['source']}: {status}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-translate", action="store_true", help="跳过翻译（无需 MOONSHOT_API_KEY）")
    args = ap.parse_args()

    os.makedirs("data", exist_ok=True)
    results = run_fetchers()

    # 保存原始数据便于调试与回溯
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    raw_path = os.path.join("data", f"raw-{stamp}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"[data] 原始数据已保存: {raw_path}")

    translations = {}
    if not args.no_translate:
        entries = []
        for r in results:
            if not r["ok"]:
                continue
            for it in r["items"]:
                entries.append({"key": it["id"], "title": it["title"], "snippet": it["snippet"]})
        print(f"[translate] 待翻译条目 {len(entries)} 条…")
        translations = translator.translate(entries)
        done = sum(1 for v in translations.values() if v.get("zh_title"))
        print(f"[translate] 完成 {done}/{len(entries)} 条")
    else:
        print("[translate] --no-translate：跳过翻译")

    archive_name = build_site.build(results, translations)
    print(f"[site] 已生成 site/index.html 与 site/archive/{archive_name}")


if __name__ == "__main__":
    main()
