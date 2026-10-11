"""Kimi API 批量翻译（moonshot）。所有条目的 title+snippet 合并成一次调用，
要求模型返回严格 JSON 数组。带内容哈希缓存、失败重试一次、解析失败降级。"""
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
    resp = requests.post(API_URL, json=body, headers=headers, timeout=120)
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
        th, sh = _hash(e["title"]), _hash(e["snippet"] or "")
        if th in cache and (not e["snippet"] or sh in cache):
            result[e["key"]] = {"zh_title": cache[th], "zh_snippet": cache.get(sh)}
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

    texts = []
    for e, _, _ in pending:
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
        print(f"[translator] Kimi 调用失败（已重试 1 次）: {err}")
        _save_cache(cache)
        return result

    for item in arr:
        try:
            i = int(item.get("i"))
            e, th, sh = pending[i]
        except Exception:
            continue
        zh_title = (item.get("zh_title") or "").strip() or None
        zh_snippet = (item.get("zh_snippet") or "").strip() or None
        result[e["key"]]["zh_title"] = zh_title
        result[e["key"]]["zh_snippet"] = zh_snippet
        if zh_title:
            cache[th] = zh_title
        if zh_snippet:
            cache[sh] = zh_snippet
    _save_cache(cache)
    return result
