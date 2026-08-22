# -*- coding: utf-8 -*-
"""
weekly.py - Build one week's report payload from the current data.

Aggregates the week's important news (existing hotness/importance logic) and
produces a rule-based "assessment" (no external AI): week-over-week moves,
Fear & Greed zone, threshold warnings, top hot headlines. All text is Vietnamese
(user-facing); code is English.
"""
import config
from collectors import news as newsmod


def _get(d, *path):
    """Nested get; when d is a list, the key matches item id/symbol."""
    for k in path:
        if isinstance(d, dict):
            d = d.get(k)
        elif isinstance(d, list):
            d = next((x for x in d if x.get("id") == k or x.get("symbol") == k), None)
        else:
            return None
        if d is None:
            return None
    return d


def _pct(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return round((cur - prev) / prev * 100, 2)


def _importance(it):
    text = (it.get("title", "") + " " + (it.get("summary") or "")).lower()
    return sum(1 for kw in config.NEWS_IMPORTANT_KEYWORDS if kw in text)


# Summary metrics: (label, path, unit, decimals)
_METRICS = [
    ("VN-Index", ("vn", "index", "close"), "", 2),
    ("VN30-Index", ("vn", "vn30_index", "close"), "", 2),
    ("Bitcoin", ("crypto", "coins", "bitcoin", "price"), " $", 0),
    ("Ethereum", ("crypto", "coins", "ethereum", "price"), " $", 0),
    ("Fear & Greed", ("crypto", "fear_greed", "value"), "", 0),
    ("Vàng", ("macro", "items", "Gold", "last"), " $", 0),
    ("DXY", ("macro", "items", "DXY", "last"), "", 2),
    ("Lợi suất Mỹ 10N", ("macro", "items", "US10Y", "last"), "%", 2),
    ("VIX", ("macro", "items", "VIX", "last"), "", 2),
    ("S&P 500", ("macro", "items", "SP500", "last"), "", 0),
]


def _summary(brief, prev):
    out = []
    for label, path, unit, d in _METRICS:
        cur = _get(brief, *path)
        pv = _get(prev, *path) if prev else None
        out.append({"label": label, "cur": cur, "prev": pv,
                    "delta_pct": _pct(cur, pv), "unit": unit, "d": d})
    return out


def _vn30_medians(brief):
    import statistics
    rows = [r for r in _get(brief, "vn", "vn30") or [] if r.get("close") is not None]

    def med(key):
        vals = [r.get(key) for r in rows
                if isinstance(r.get(key), (int, float))]
        vals = [v for v in vals if v == v]  # drop NaN
        return round(statistics.median(vals), 2) if vals else None
    return {"pe": med("pe"), "pb": med("pb"), "roe": med("roe"), "n": len(rows)}


def _rank_news(news_week):
    """Rank the week's news (hotness -> importance -> recency), cap per topic."""
    newsmod.annotate_hotness(news_week)
    by_topic = {}
    for it in news_week:
        by_topic.setdefault(it.get("topic", "?"), []).append(it)
    out = {}
    for topic, lst in by_topic.items():
        lst.sort(key=lambda it: (it.get("hot", 0), _importance(it),
                                 it.get("published") or it.get("first_seen") or ""),
                 reverse=True)
        out[topic] = [{"title": it.get("title"), "link": it.get("link"),
                       "source": it.get("source"), "published": it.get("published"),
                       "hot": it.get("hot", 0)}
                      for it in lst[:config.NEWS_MAX_PER_TOPIC]]
    return out


def _fng_zone(v):
    if v is None:
        return ""
    for lo, hi, label, _ in config.FNG_ZONES:
        if lo <= v < hi:
            return label
    return ""


def _fmt(v, unit, d):
    if v is None:
        return "-"
    return f"{v:,.{d}f}{unit}"


def _assessment(summary, vn30, ranked):
    """Rule-based weekly assessment (Vietnamese)."""
    by = {m["label"]: m for m in summary}

    def dtxt(label):
        m = by.get(label, {})
        p = m.get("delta_pct")
        if p is None:
            return f"{_fmt(m.get('cur'), m.get('unit',''), m.get('d',2))}"
        sign = "+" if p > 0 else ""
        return f"{_fmt(m.get('cur'), m.get('unit',''), m.get('d',2))} ({sign}{p:.1f}%/tuần)"

    market = [
        f"Chứng khoán VN: VN-Index {dtxt('VN-Index')}, VN30 {dtxt('VN30-Index')}."
        + (f" P/E trung vị rổ VN30 ≈ {vn30.get('pe')}." if vn30.get('pe') else ""),
        f"Crypto: BTC {dtxt('Bitcoin')}, ETH {dtxt('Ethereum')}. "
        f"Fear & Greed {by.get('Fear & Greed',{}).get('cur')} ({_fng_zone(by.get('Fear & Greed',{}).get('cur'))}).",
        f"Vĩ mô: Vàng {dtxt('Vàng')}, DXY {dtxt('DXY')}, "
        f"Lợi suất Mỹ 10N {dtxt('Lợi suất Mỹ 10N')}, VIX {dtxt('VIX')}.",
    ]

    warnings = []
    us10y = by.get("Lợi suất Mỹ 10N", {}).get("cur")
    if us10y is not None and us10y > config.US10Y_HIGH:
        warnings.append(f"Lợi suất TPCP Mỹ 10N {us10y}% > {config.US10Y_HIGH}% — áp lực lên tài sản rủi ro.")
    vix = by.get("VIX", {}).get("cur")
    if vix is not None and vix > config.VIX_STRESS:
        warnings.append(f"VIX {vix} > {config.VIX_STRESS} — thị trường căng thẳng.")
    fng = by.get("Fear & Greed", {}).get("cur")
    if fng is not None and (fng >= 75 or fng < 25):
        warnings.append(f"Fear & Greed {fng} ({_fng_zone(fng)}) — vùng cực đoan, dễ đảo chiều.")
    gold = by.get("Vàng", {}).get("delta_pct")
    if gold is not None and gold > 3:
        warnings.append(f"Vàng tăng mạnh {gold:+.1f}%/tuần — dòng tiền phòng thủ.")

    # top hot headlines across topics
    allnews = [it for lst in ranked.values() for it in lst]
    allnews.sort(key=lambda x: x.get("hot", 0), reverse=True)
    tophot = allnews[:3]

    # overall tone
    ups = sum(1 for k in ("VN-Index", "VN30-Index", "Bitcoin")
              if (by.get(k, {}).get("delta_pct") or 0) > 0)
    if ups >= 2:
        headline = "Tuần tăng — khẩu vị rủi ro tích cực"
    elif ups == 0:
        headline = "Tuần giảm — thị trường thận trọng"
    else:
        headline = "Tuần phân hóa"
    if warnings:
        headline += " (có tín hiệu cảnh báo)"

    return {"headline": headline, "market": market, "warnings": warnings, "tophot": tophot}


def _spark_week_ago(brief, *path):
    node = _get(brief, *path)
    spark = node.get("spark") if isinstance(node, dict) else None
    return spark[-6] if spark and len(spark) >= 6 else None


def _estimate_prev(brief):
    """Estimate ~1 week ago from real history in the brief (first-run fallback)."""
    p = {"vn": {"index": {}, "vn30_index": {}}, "crypto": {"coins": []},
         "macro": {"items": {}}}
    p["vn"]["index"]["close"] = _spark_week_ago(brief, "vn", "index")
    p["vn"]["vn30_index"]["close"] = _spark_week_ago(brief, "vn", "vn30_index")
    for cid in ("bitcoin", "ethereum"):
        c = _get(brief, "crypto", "coins", cid)
        if c and c.get("price") is not None and c.get("change_7d") is not None:
            p["crypto"]["coins"].append(
                {"id": cid, "price": c["price"] / (1 + c["change_7d"] / 100)})
    for k in ("Gold", "DXY", "US10Y", "VIX", "SP500"):
        v = _spark_week_ago(brief, "macro", "items", k)
        if v is not None:
            p["macro"]["items"][k] = {"last": v}
    return p


def build_payload(brief, prev_snapshot, news_week):
    if prev_snapshot and prev_snapshot.get("date") and prev_snapshot["date"] != brief.get("date"):
        prev = prev_snapshot["payload"]
    else:
        prev = _estimate_prev(brief)   # first run: estimate from history
    summary = _summary(brief, prev)
    vn30 = _vn30_medians(brief)
    ranked = _rank_news(news_week)
    assessment = _assessment(summary, vn30, ranked)
    return {
        "date": brief.get("date"),
        "generated_at": brief.get("generated_at"),
        "prev_date": prev_snapshot["date"] if prev_snapshot else None,
        "summary": summary,
        "vn30": vn30,
        "news": ranked,
        "assessment": assessment,
    }
