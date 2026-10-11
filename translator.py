"""Kimi API 批量翻译（moonshot）。所有条目的 title+snippet 分批调用（每批最多 10 条），
要求模型返回严格 JSON 数组。带内容哈希缓存、失败重试一次、单批失败互不影响、解析失败降级。"""
import hashlib
import json
import os
import re

import requests

API_URL = "https://api.moonshot.cn/v1/chat/completions"
MODEL = "kimi-k2.6"
CACHE_PATH = os.path.join("data", "translation_cache.json")
MAX_TEXT_LEN = 2000  # 单条 title/snippet 截断长度，控制 token 消耗


def _hash(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _call_kimi(payload_texts, api_key):
    """调用 Kimi API，返回 (items, None) 或 (None, error)。"""
    lines = []
    for i, t in enumerate(payload_texts):
        lines.append(f'[{i}] {t}')
    user = (
        "把下面的英文新闻条目翻译成中文。每条格式为 [编号] TITLE || SNIPPET。\n"
        "严格返回一个 JSON 数组，每个元素为 {\"i\": 编号, \"zh_title\": \"...\", \"zh_snippet\": \"...\"}，"
        "不要返回任何其他文字、解释或 markdown 代码块。\n\n" + "\n".join(lines)
    )
    body = {
        "model": MODEL,  # kimi-k2.6 为推理模型，仅允许默认 temperature=1
        "messages": [{"role": "user", "content": user}],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(API_URL, json=body, headers=headers, timeout=300)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    # 容错：剥离可能的 markdown 代码块包裹
    m = re.search(r"```(?:json)?\s*(.*?)```", content, re.S)
    if m:
        content = m.group(1).strip()
    arr = json.loads(content)
    if not isinstance(arr, list):
        raise ValueError("Kimi 返回非 JSON 数组")
    return arr


def translate(entries):
    """entries: [{"key", "title", "snippet"}...] → {"key": {"zh_title":..,"zh_snippet":..}}。

    无 key 或全部缓存命中时不发请求；任何异常降级为 zh 字段为 None。
    """
    result = {}
    api_key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    cache = _load_cache()
    pending = []
    for e in entries:
        # 空 snippet 不查/不写缓存（否则所有空 snippet 共享 _hash("") 一个槽位，
        # 某条目模型幻觉出的 zh_snippet 会串到所有空 snippet 条目上），也永远不求翻译
        th = _hash(e["title"])
        sh = _hash(e["snippet"]) if e["snippet"] else None
        if th in cache and (sh is None or sh in cache):
            result[e["key"]] = {"zh_title": cache[th],
                                "zh_snippet": cache.get(sh) if sh else None}
        else:
            pending.append((e, th, sh))
    for e, _, _ in pending:
        result[e["key"]] = {"zh_title": None, "zh_snippet": None}

    if not api_key or not pending:
        if not api_key and pending:
            for e, _, _ in pending:
                pass  # 无 key：保持 None，页面显示"翻译失败"
        _save_cache(cache)
        return result

    # 分批调用：kimi-k2.6 为推理模型，单批过大容易超时；每批最多 10 条。
    # 某批失败只影响该批条目（保持 None，页面显示"翻译失败"），其余批次照常。
    BATCH_SIZE = 10
    failed_errs = []
    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]
        texts = []
        for e, _, _ in batch:
            title = e["title"][:MAX_TEXT_LEN]
            snippet = (e["snippet"] or "")[:MAX_TEXT_LEN]
            texts.append(f"{title} || {snippet}" if snippet else title)

        arr, err = None, None
        for attempt in range(2):
            try:
                arr = _call_kimi(texts, api_key)
                err = None
                break
            except Exception as ex:
                err = f"{type(ex).__name__}: {ex}"
                arr = None

        if arr is None:
            failed_errs.append(f"第 {start // BATCH_SIZE + 1} 批: {err}")
            continue

        for item in arr:
            try:
                i = int(item.get("i"))
                e, th, sh = batch[i]
            except Exception:
                continue
            zh_title = (item.get("zh_title") or "").strip() or None
            # 空 snippet 的条目不接受模型"看图说话"编出的 zh_snippet
            zh_snippet = (item.get("zh_snippet") or "").strip() or None if sh else None
            result[e["key"]]["zh_title"] = zh_title
            result[e["key"]]["zh_snippet"] = zh_snippet
            if zh_title:
                cache[th] = zh_title
            if zh_snippet and sh:
                cache[sh] = zh_snippet

    if failed_errs:
        print("[translator] 以下批次失败（已重试 1 次）: " + "；".join(failed_errs))
    _save_cache(cache)
    return result
