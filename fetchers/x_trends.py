"""X(推特) 美国热搜趋势。数据源：trends24.in（首选）→ getdaytrends.com（回退）。"""
import re
import html as html_mod

import requests

SOURCE = "x_trends"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _parse_trends24(text):
    """trends24.in 页面解析：trend-card 中的 ol li a 即趋势词，span.trend-card__list-item-count 为 tweet 量。"""
    items = []
    seen = set()
    blocks = re.findall(r'<ol class="trend-card__list"[^>]*>(.*?)</ol>', text, re.S)
    for m in re.finditer(
        r'<a[^>]*>([^<]+)</a>(?:\s*<span[^>]*class="[^"]*list-item-count[^"]*"[^>]*>([^<]*)</span>)?',
        "\n".join(blocks) if blocks else "",
    ):
        word = html_mod.unescape(m.group(1)).strip()
        count = m.group(2)
        if not word or word in seen:
            continue
        seen.add(word)
        count_txt = html_mod.unescape(count).strip() if count else ""
        items.append({
            "id": "xt-" + re.sub(r"\W+", "-", word)[:48],
            "title": word,
            "url": "https://twitter.com/search?q=" + requests.utils.quote(word),
            "snippet": "",
            "extra": {"tweet_count": count_txt, "via": "trends24.in"},
        })
        if len(items) >= 20:
            break
    return items


def _parse_getdaytrends(text):
    """getdaytrends.com 解析：<td class="main"><a ...>词</a></td><td class="details...">NNN score</td>。"""
    items = []
    seen = set()
    pattern = re.compile(
        r'<td class="main"><a[^>]*href="(/united-states/trend/[^"]*)"[^>]*>([^<]+)</a></td>'
        r'<td class="details[^"]*"[^>]*>([^<]*)</td>'
    )
    for m in pattern.finditer(text):
        href, word, score = m.group(1), html_mod.unescape(m.group(2)).strip(), m.group(3).strip()
        if not word or word in seen:
            continue
        seen.add(word)
        items.append({
            "id": "xt-" + re.sub(r"\W+", "-", word)[:48],
            "title": word,
            "url": "https://getdaytrends.com" + href,
            "snippet": "",
            "extra": {"tweet_count": score, "via": "getdaytrends.com"},
        })
        if len(items) >= 20:
            break
    return items


def fetch(limit=20):
    result = {"ok": False, "source": SOURCE, "items": [], "error": None}
    attempts = [
        ("https://trends24.in/united-states/", _parse_trends24),
        ("https://getdaytrends.com/united-states/", _parse_getdaytrends),
    ]
    errors = []
    for url, parser in attempts:
        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": UA})
            resp.raise_for_status()
            items = parser(resp.text)
            if items:
                result["ok"] = True
                result["items"] = items[:limit]
                result["error"] = None
                return result
            errors.append(f"{url}: 页面中未解析到趋势词（可能被反爬拦截）")
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")
    result["error"] = "；".join(errors)
    return result
