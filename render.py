# -*- coding: utf-8 -*-
"""
render.py - Build report.html from briefing_latest.json + assessment.json + DB.

Run:
  python render.py           # build report (does NOT advance the watermark - safe to rerun)
  python render.py --seen    # build, then mark everything seen (use at end of week)

Sources:
- briefing_latest.json : raw data (required, produced by update.py)
- assessment.json      : Claude's analysis (optional)
- data/investment.db   : news history + 'last_viewed' watermark + snapshots
"""
import sys
import os
import json
import html
import math
import statistics
from datetime import datetime

import store
import config
from collectors import news

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")


def _chartjs_lib():
    """Return the inlined Chart.js library source (self-contained, works offline)."""
    path = os.path.join(BASE, "assets", "chart.min.js")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "/* chart.min.js not found */"

STATUS_COLOR = {"green": "#16a34a", "yellow": "#d97706", "red": "#dc2626"}
STATUS_LABEL = {"green": "Tích cực", "yellow": "Trung tính / Thận trọng", "red": "Rủi ro cao"}


def esc(x):
    return html.escape(str(x)) if x is not None else ""


def _finite(x):
    """True if x is a real (non-None, non-NaN, non-inf) number."""
    return isinstance(x, (int, float)) and math.isfinite(x)


def fmt_num(x, d=2):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "-"
    try:
        return f"{x:,.{d}f}"
    except Exception:
        return str(x)


def pct_span(v):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return '<span class="muted">-</span>'
    cls = "up" if v > 0 else ("down" if v < 0 else "flat")
    sign = "+" if v > 0 else ""
    return f'<span class="{cls}">{sign}{v:.2f}%</span>'


def sparkline(vals, w=120, h=32):
    vals = [v for v in (vals or []) if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    n = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = i / (n - 1) * (w - 4) + 2
        y = h - 2 - (v - lo) / rng * (h - 4)
        pts.append(f"{x:.1f},{y:.1f}")
    color = "#16a34a" if vals[-1] >= vals[0] else "#dc2626"
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'preserveAspectRatio="none"><polyline fill="none" stroke="{color}" '
            f'stroke-width="1.5" points="{" ".join(pts)}"/></svg>')


def _year_ticks(labels):
    """From labels ('2018Q1' or '2014-09') -> [(index, 'year')] at the first of each year."""
    out = []
    seen = set()
    for i, lb in enumerate(labels or []):
        s = str(lb)
        year = s[:4]
        if year.isdigit() and year not in seen:
            seen.add(year)
            out.append((i, year))
    return out


def multichart(series, labels, w=600, h=220, unit="", baseline=None,
               baseline_label="", y_is_ratio=False):
    """Detailed line chart: multiple lines + grid + Y-axis labels + YEAR ticks + dots.
    series: list of dict {values, color, label}. Shared Y-axis."""
    allv = []
    for s in series:
        allv += [v for v in s["values"] if v is not None]
    if baseline is not None:
        allv.append(baseline)
    if len(allv) < 2:
        return '<div class="muted">Không đủ dữ liệu để vẽ.</div>'
    lo, hi = min(allv), max(allv)
    rng = (hi - lo) or 1
    lo -= rng * 0.10
    hi += rng * 0.10
    rng = hi - lo
    n = max(len(s["values"]) for s in series)
    padL, padR, padT, padB = 44, 12, 10, 20
    plotW, plotH = w - padL - padR, h - padT - padB

    def X(i):
        return padL + (i / (n - 1) * plotW if n > 1 else 0)

    def Y(v):
        return padT + (hi - v) / rng * plotH

    def yfmt(v):
        return (f"x{v:.2f}" if y_is_ratio else f"{fmt_num(v)}{unit}")

    p = [f'<svg class="lc" viewBox="0 0 {w} {h}" width="100%" height="{h}" '
         f'xmlns="http://www.w3.org/2000/svg" font-family="sans-serif">']
    # horizontal grid + Y-axis labels (5 levels)
    for k in range(5):
        val = hi - rng * k / 4
        y = Y(val)
        p.append(f'<line x1="{padL}" y1="{y:.1f}" x2="{w-padR}" y2="{y:.1f}" '
                 f'stroke="var(--line)" stroke-width="1"/>')
        p.append(f'<text x="{padL-5}" y="{y+3:.1f}" font-size="10" fill="#9aa3b2" '
                 f'text-anchor="end">{yfmt(val)}</text>')
    # year ticks on the X-axis
    for i, yr in _year_ticks(labels):
        x = X(i)
        p.append(f'<line x1="{x:.1f}" y1="{padT}" x2="{x:.1f}" y2="{h-padB}" '
                 f'stroke="var(--line)" stroke-width="1" stroke-dasharray="2 3" opacity="0.6"/>')
        p.append(f'<text x="{x:.1f}" y="{h-6}" font-size="10" fill="#9aa3b2" '
                 f'text-anchor="middle">{esc(yr)}</text>')
    # baseline line (e.g. average = 1.0)
    if baseline is not None:
        yb = Y(baseline)
        p.append(f'<line x1="{padL}" y1="{yb:.1f}" x2="{w-padR}" y2="{yb:.1f}" '
                 f'stroke="#f59e0b" stroke-width="1.4" stroke-dasharray="5 3"/>')
        if baseline_label:
            p.append(f'<text x="{w-padR-2}" y="{yb-4:.1f}" font-size="10" fill="#f59e0b" '
                     f'text-anchor="end">{esc(baseline_label)}</text>')
    # the lines
    for s in series:
        pts = [(i, v) for i, v in enumerate(s["values"]) if v is not None]
        if len(pts) < 2:
            continue
        poly = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in pts)
        p.append(f'<polyline fill="none" stroke="{s["color"]}" stroke-width="2" points="{poly}"/>')
        for i, v in pts:
            p.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="1.6" fill="{s["color"]}"/>')
        li, lv = pts[-1]
        p.append(f'<circle cx="{X(li):.1f}" cy="{Y(lv):.1f}" r="3.2" fill="{s["color"]}"/>')
    p.append("</svg>")
    # legend
    leg = " &nbsp; ".join(
        f'<span class="lgd"><span class="dot2" style="background:{s["color"]}"></span>{esc(s["label"])}</span>'
        for s in series)
    if baseline_label:
        leg += (f' &nbsp; <span class="lgd"><span class="dash2"></span>{esc(baseline_label)}</span>')
    return f'<div class="chartleg">{leg}</div>' + "".join(p)


def vs_avg_badge(vs_pct, cheap_is_low=True):
    """Badge: cheap/expensive vs historical average."""
    if not _finite(vs_pct):
        return ""
    # cheap_is_low: lower ratio = cheaper (P/E, P/B). vs_pct < 0 = below avg = cheap
    cheap = (vs_pct < 0) if cheap_is_low else (vs_pct > 0)
    cls = "up" if cheap else "down"
    txt = "dưới TB" if vs_pct < 0 else ("trên TB" if vs_pct > 0 else "= TB")
    sign = "+" if vs_pct > 0 else ""
    return f'<span class="{cls}" style="font-size:11.5px">({sign}{vs_pct:.0f}% {txt})</span>'


# ---------------- Chart.js helpers ----------------

def chart_canvas(cid, cfg, height=240):
    """A Chart.js canvas carrying its config in data-cfg (lazily initialized by JS)."""
    data = esc(json.dumps(cfg, ensure_ascii=False))
    return (f'<div class="chartwrap" style="height:{height}px">'
            f'<canvas id="{esc(cid)}" class="jschart" data-cfg="{data}"></canvas></div>')


def _ds(label, data, color, axis="y", dash=False, fill=False):
    d = {"label": label, "data": data, "borderColor": color, "backgroundColor": color,
         "borderWidth": 1.6 if dash else 2, "pointRadius": 0, "tension": 0.25,
         "spanGaps": True, "yAxisID": axis}
    if dash:
        d["borderDash"] = [5, 3]
    if fill:
        d["fill"] = True
        d["backgroundColor"] = color + "22"
    return d


def pe_pb_chart(cid, periods, pe_series, pb_series, pe_avg, pb_avg):
    """Dual-axis chart: P/E (left) + P/B (right), each with its historical average line."""
    n = len(periods)
    cfg = {
        "type": "line",
        "data": {"labels": periods, "datasets": [
            _ds("P/E", pe_series, "#4f46e5", "yl"),
            _ds("TB P/E", [pe_avg] * n if pe_avg else [], "#4f46e5", "yl", dash=True),
            _ds("P/B", pb_series, "#0d9488", "yr"),
            _ds("TB P/B", [pb_avg] * n if pb_avg else [], "#0d9488", "yr", dash=True),
        ]},
        "options": {
            "responsive": True, "maintainAspectRatio": False,
            "interaction": {"mode": "index", "intersect": False},
            "plugins": {"legend": {"labels": {"boxWidth": 12, "font": {"size": 11}}}},
            "scales": {
                "x": {"grid": {"display": False}, "ticks": {"maxTicksLimit": 8, "maxRotation": 0}},
                "yl": {"position": "left", "title": {"display": True, "text": "P/E"}},
                "yr": {"position": "right", "title": {"display": True, "text": "P/B"},
                       "grid": {"drawOnChartArea": False}},
            },
        },
    }
    return chart_canvas(cid, cfg)


def price_chart(cid, labels, series, avg, log=True):
    """Long-term price line (log scale) with an all-time average line."""
    n = len(labels or [])
    cfg = {
        "type": "line",
        "data": {"labels": labels, "datasets": [
            _ds("Giá", series, "#4f46e5", "y", fill=True),
            _ds("TB toàn kỳ", [avg] * n if avg else [], "#f59e0b", "y", dash=True),
        ]},
        "options": {
            "responsive": True, "maintainAspectRatio": False,
            "interaction": {"mode": "index", "intersect": False},
            "plugins": {"legend": {"labels": {"boxWidth": 12, "font": {"size": 11}}}},
            "scales": {
                "x": {"grid": {"display": False}, "ticks": {"maxTicksLimit": 8, "maxRotation": 0}},
                "y": {"type": "logarithmic" if log else "linear"},
            },
        },
    }
    return chart_canvas(cid, cfg)


# ---------------- Metric strips ----------------

def render_macro(macro):
    items = macro.get("items", {})
    if not items:
        return '<p class="muted">Khong co du lieu vi mo.</p>'
    rows = []
    for name, it in items.items():
        if it.get("last") is None:
            rows.append(f'<div class="metric"><div class="mname">{esc(it.get("desc", name))}</div>'
                        f'<div class="muted">lỗi</div></div>')
            continue
        rows.append(f"""
        <div class="metric">
          <div class="mname">{esc(name)} <span class="mdesc">{esc(it.get('desc',''))}</span></div>
          <div class="mval">{fmt_num(it['last'])}</div>
          <div class="mchg">{pct_span(it.get('change_1d_pct'))} <span class="muted">1 ngày</span>
             &nbsp; {pct_span(it.get('change_1mo_pct'))} <span class="muted">1 tháng</span></div>
          {sparkline(it.get('spark'))}
        </div>""")
    return '<div class="metric-grid">' + "".join(rows) + "</div>"


def _index_metric(idx):
    if not idx.get("close"):
        return ""
    return f"""
        <div class="metric big">
          <div class="mname">{esc(idx['name'])} <span class="mdesc">{esc(idx.get('date',''))}</span></div>
          <div class="mval">{fmt_num(idx['close'])} {pct_span(idx.get('change_pct'))}</div>
          <div class="mchg"><span class="muted">20 phiên:</span> {pct_span(idx.get('change_20d_pct'))}
             &nbsp; <span class="muted">KLGD:</span> {fmt_num(idx.get('volume'),0)}</div>
          {sparkline(idx.get('spark'), w=200, h=40)}
        </div>"""


def render_vn(vn):
    html_ = _index_metric(vn.get("index", {})) + _index_metric(vn.get("vn30_index", {}))
    wl = vn.get("watchlist", [])
    if wl:
        cells = []
        for w in wl:
            if w.get("error"):
                cells.append(f'<td>{esc(w["symbol"])}</td><td colspan="2" class="muted">lỗi</td>')
                continue
            cells.append(
                f'<tr><td class="sym">{esc(w["symbol"])}</td>'
                f'<td class="r">{fmt_num(w.get("close"))}</td>'
                f'<td class="r">{pct_span(w.get("change_pct"))}</td></tr>')
        html_ += ('<table class="wl"><thead><tr><th>Mã</th><th class="r">Giá</th>'
                  '<th class="r">+/-</th></tr></thead><tbody>'
                  + "".join(cells) + "</tbody></table>")
    return html_ or '<p class="muted">Không có dữ liệu VN.</p>'


def _years_of(periods):
    return round(len(periods) / 4, 1) if periods else None


def _stock_card(r):
    sym = r.get("symbol", "")
    pe, pb = r.get("pe"), r.get("pb")
    pe_st = r.get("pe_stats") or {}
    pb_st = r.get("pb_stats") or {}
    periods = r.get("periods") or []
    yrs = _years_of(periods)
    yrs_txt = f"~{yrs:.0f} năm".replace(".0", "") if yrs else ""

    # summary row (grid)
    summary = f"""
      <div class="vcell sym">{esc(sym)}</div>
      <div class="vcell r">{fmt_num(r.get('close'))}</div>
      <div class="vcell r">{pct_span(r.get('change_1w'))}<div class="clab">tuần</div></div>
      <div class="vcell r">{pct_span(r.get('change_1m'))}<div class="clab">tháng</div></div>
      <div class="vcell r">{fmt_num(pe)} {vs_avg_badge(pe_st.get('vs_avg_pct'))}<div class="clab">P/E vs TB</div></div>
      <div class="vcell r">{fmt_num(pb)} {vs_avg_badge(pb_st.get('vs_avg_pct'))}<div class="clab">P/B vs TB</div></div>
      <div class="vcell mini">{sparkline(r.get('pe_series'), w=90, h=26)}</div>
    """

    # body: dual-axis Chart.js of P/E (left) & P/B (right) with their average lines
    pe_avg, pb_avg = pe_st.get("avg"), pb_st.get("avg")
    pe_series, pb_series = r.get("pe_series") or [], r.get("pb_series") or []
    combo = pe_pb_chart(f"chart_{esc(sym)}", periods, pe_series, pb_series, pe_avg, pb_avg)

    def stat_line(name, cur, st, cheap=True):
        if not st:
            return ""
        return (f'<div class="statline"><b>{name}</b>: hiện tại <b>{fmt_num(cur)}</b> · '
                f'TB {yrs_txt} <b>{fmt_num(st.get("avg"))}</b> {vs_avg_badge(st.get("vs_avg_pct"), cheap)} · '
                f'thấp {fmt_num(st.get("min"))} · cao {fmt_num(st.get("max"))}</div>')

    body = f"""
      <div class="carddetail">
        {stat_line("P/E", pe, pe_st)}
        {stat_line("P/B", pb, pb_st)}
        <div class="chartbox"><div class="charttitle">P/E &amp; P/B theo quý ({yrs_txt}) — đường nét đứt = trung bình lịch sử</div>{combo}</div>
        <div class="statline muted">ROE {fmt_num(r.get('roe'))}% · giá 52 tuần:
          {fmt_num(r.get('w52_low'))} – {fmt_num(r.get('w52_high'))} (hiện ở {fmt_num(r.get('w52_pos'))}% dải) ·
          Δ 1 năm {r.get('ret_1y')}%</div>
      </div>
    """
    return (f'<details class="vcard"><summary><div class="vsummary">{summary}'
            f'<span class="vexp">▸</span></div></summary>{body}</details>')


def vn30_aggregate(rows):
    """Aggregate metrics for the whole VN30 basket: median P/E, P/B, ROE + cheap/expensive breadth."""
    def med(key):
        vals = [r.get(key) for r in rows if _finite(r.get(key))]
        return round(statistics.median(vals), 2) if vals else None
    pe_med, pb_med, roe_med = med("pe"), med("pb"), med("roe")
    # breadth: how many stocks are below their own historical average P/E
    disc = [(r.get("pe_stats") or {}).get("vs_avg_pct") for r in rows]
    disc = [x for x in disc if _finite(x)]
    below = [x for x in disc if x < 0]
    avg_disc = round(sum(disc) / len(disc), 1) if disc else None
    breadth = (f'<b>{len(below)}/{len(disc)}</b> mã đang dưới P/E trung bình lịch sử'
               f' (bình quân {avg_disc:+.0f}% so với TB)') if disc else ""
    return f"""
    <div class="agg">
      <div class="agg-title">📌 Chỉ số chung VN30 ({len(rows)} mã)</div>
      <div class="agg-row">
        <div class="agg-item"><div class="agg-val">{fmt_num(pe_med)}</div><div class="agg-lab">P/E trung vị</div></div>
        <div class="agg-item"><div class="agg-val">{fmt_num(pb_med)}</div><div class="agg-lab">P/B trung vị</div></div>
        <div class="agg-item"><div class="agg-val">{fmt_num(roe_med)}%</div><div class="agg-lab">ROE trung vị</div></div>
      </div>
      <div class="agg-note">{breadth}</div>
    </div>"""


def _num_td(v, suffix="", pct=False):
    """A right-aligned table cell with data-v for numeric sorting."""
    if not _finite(v):
        return '<td class="r muted" data-v="">-</td>'
    if pct:
        cls = "up" if v > 0 else ("down" if v < 0 else "")
        sign = "+" if v > 0 else ""
        return f'<td class="r {cls}" data-v="{v}">{sign}{v:.2f}%</td>'
    return f'<td class="r" data-v="{v}">{fmt_num(v)}{suffix}</td>'


def render_vn30_table(rows):
    """Sortable + filterable VN30 table."""
    body = ""
    for r in rows:
        pe_vs = (r.get("pe_stats") or {}).get("vs_avg_pct")
        body += (
            f'<tr><td class="sym" data-v="{esc(r["symbol"])}">{esc(r["symbol"])}</td>'
            f'{_num_td(r.get("close"))}'
            f'{_num_td(r.get("change_pct"), pct=True)}'
            f'{_num_td(r.get("ret_1y"), pct=True)}'
            f'{_num_td(r.get("pe"))}'
            f'{_num_td(r.get("pb"))}'
            f'{_num_td(r.get("roe"), suffix="%")}'
            f'{_num_td(pe_vs, pct=True)}'
            f'{_num_td(r.get("w52_pos"), suffix="%")}'
            f'</tr>')
    cols = [("Mã", "sym"), ("Giá", "px"), ("Δ ngày", "d"), ("Δ 1 năm", "y"),
            ("P/E", "pe"), ("P/B", "pb"), ("ROE", "roe"), ("P/E vs TB", "pevs"),
            ("Vị trí 52T", "pos")]
    head = "".join(
        f'<th data-key="{k}" onclick="sortTable(this)"'
        f'{"" if i == 0 else " class=r"}>{esc(lbl)}</th>'
        for i, (lbl, k) in enumerate(cols))
    return f"""
    <input class="tblfilter" data-table="vn30tbl" oninput="filterTable(this)" placeholder="Lọc mã... (vd FPT)">
    <div class="tblwrap"><table class="vn30" id="vn30tbl">
      <thead><tr>{head}</tr></thead>
      <tbody>{body}</tbody>
    </table></div>
    <div class="sub" style="margin-top:6px">Bấm tiêu đề cột để sắp xếp · "P/E vs TB" âm = rẻ hơn trung bình lịch sử.</div>"""


def render_vn30(vn):
    rows = [r for r in vn.get("vn30", []) if r.get("close") is not None]
    if not rows:
        return '<p class="muted">Không có dữ liệu VN30.</p>'
    period = next((r.get("period") for r in rows if r.get("period")), "")
    cards = "".join(_stock_card(r) for r in rows)
    return f"""
    {vn30_aggregate(rows)}
    <div class="sub" style="margin-bottom:8px">30 cổ phiếu VN30 · định giá TTM mới nhất {esc(period)}.</div>
    {render_vn30_table(rows)}
    <details class="chartswrap" style="margin-top:14px"><summary>&#128200; Xem biểu đồ P/E &amp; P/B từng mã</summary>
      <div class="sub" style="margin:8px 0">Bấm vào một mã để xem biểu đồ dài hạn (~8 năm).</div>
      {cards}
    </details>"""


def render_crypto(cr):
    g = cr.get("global", {})
    html_ = ""
    if g:
        mc = g.get("total_market_cap_usd", 0) / 1e12
        html_ += f"""
        <div class="metric big">
          <div class="mname">Tổng vốn hóa</div>
          <div class="mval">${mc:,.2f}T {pct_span(g.get('market_cap_change_24h'))}</div>
          <div class="mchg"><span class="muted">BTC.D:</span> {fmt_num(g.get('btc_dominance'))}%
             &nbsp; <span class="muted">ETH.D:</span> {fmt_num(g.get('eth_dominance'))}%</div>
        </div>"""
    fng = cr.get("fear_greed", {})
    if fng:
        v = fng.get("value")
        col = STATUS_COLOR["red"] if (v is not None and (v < 25 or v >= 75)) else STATUS_COLOR["yellow"]
        html_ += f"""
        <div class="metric big">
          <div class="mname">Fear &amp; Greed Index</div>
          <div class="mval" style="color:{col}">{esc(v)} <span class="mdesc">{esc(fng.get('label'))}</span></div>
          <div class="mchg"><span class="muted">Hôm qua:</span> {esc(fng.get('prev_value'))}</div>
        </div>"""
    coins = cr.get("coins", [])
    if coins:
        cells = []
        for c in coins:
            cells.append(
                f'<tr><td class="sym">{esc(c["symbol"])}</td>'
                f'<td class="r">${fmt_num(c.get("price"))}</td>'
                f'<td class="r">{pct_span(c.get("change_24h"))}</td>'
                f'<td class="r">{pct_span(c.get("change_7d"))}</td></tr>')
        html_ += ('<table class="wl"><thead><tr><th>Coin</th><th class="r">Giá</th>'
                  '<th class="r">24h</th><th class="r">7 ngày</th></tr></thead><tbody>'
                  + "".join(cells) + "</tbody></table>")
    return html_ or '<p class="muted">Không có dữ liệu crypto.</p>'


CRYPTO_NAMES = {"bitcoin": "Bitcoin (BTC)", "ethereum": "Ethereum (ETH)"}


def _crypto_card(coin, coin_data, lt):
    name = CRYPTO_NAMES.get(coin, coin)
    price = coin_data.get("price")
    summary = f"""
      <div class="vcell sym">{esc(name)}</div>
      <div class="vcell r">${fmt_num(price)}</div>
      <div class="vcell r">{pct_span(coin_data.get('change_7d'))}<div class="clab">tuần</div></div>
      <div class="vcell r">{pct_span(coin_data.get('change_30d'))}<div class="clab">tháng</div></div>
      <div class="vcell r">{fmt_num(lt.get('vs_avg_pct'))}%<div class="clab">vs TB toàn kỳ</div></div>
      <div class="vcell r">{fmt_num(lt.get('mayer'))}<div class="clab">Mayer</div></div>
      <div class="vcell mini">{sparkline(lt.get('series'), w=90, h=26)}</div>
    """
    chart = price_chart(f"chart_{coin}", lt.get("labels"), lt.get("series") or [],
                        lt.get("avg_all"), log=True)
    mayer = lt.get("mayer")
    mayer_note = ""
    if mayer is not None:
        if mayer >= 2.4:
            mayer_note = ' <span class="down">(≥2,4: nóng theo lịch sử)</span>'
        elif mayer <= 1:
            mayer_note = ' <span class="up">(≤1: rẻ theo lịch sử)</span>'
    body = f"""
      <div class="carddetail">
        <div class="statline">Giá hiện tại <b>${fmt_num(price)}</b> · TB toàn kỳ (từ {esc(lt.get('start'))})
          <b>${fmt_num(lt.get('avg_all'))}</b> {vs_avg_badge(lt.get('vs_avg_pct'), cheap_is_low=True)}</div>
        <div class="statline">Mayer Multiple (giá / MA200 ngày) = <b>{fmt_num(mayer)}</b>{mayer_note}</div>
        <div class="chartbox"><div class="charttitle">Giá theo tháng (từ {esc(lt.get('start'))})</div>{chart}</div>
      </div>
    """
    return (f'<details class="vcard"><summary><div class="vsummary">{summary}'
            f'<span class="vexp">▸</span></div></summary>{body}</details>')


def render_crypto_valuation(cr):
    lt = cr.get("longterm", {})
    coins = {c["id"]: c for c in cr.get("coins", [])}
    cards = ""
    for coin in ("bitcoin", "ethereum"):
        cd = coins.get(coin, {})
        cl = lt.get(coin, {})
        if not cd and not cl:
            continue
        cards += _crypto_card(coin, cd, cl)
    if not cards:
        return '<p class="muted">Không có dữ liệu định giá crypto.</p>'
    return f"""
    <div class="sub" style="margin-bottom:8px">BTC &amp; ETH · Δ <b>tuần</b> / <b>tháng</b> + giá so với
      <b>trung bình dài hạn</b>. Crypto không có P/E nên dùng: giá vs TB toàn kỳ và
      <b>Mayer Multiple</b> (giá/MA200). <b>Bấm vào</b> để xem biểu đồ dài hạn.</div>
    <div class="vhead">
      <div class="vcell">Coin</div><div class="vcell r">Giá</div>
      <div class="vcell r">Δ tuần</div><div class="vcell r">Δ tháng</div>
      <div class="vcell r">vs TB</div><div class="vcell r">Mayer</div>
      <div class="vcell">Dài hạn</div>
    </div>
    {cards}"""


# ---------------- Assessment (Claude) ----------------

def render_segment_assessment(seg):
    if not seg:
        return ""
    status = seg.get("status", "yellow")
    color = STATUS_COLOR.get(status, "#666")
    label = STATUS_LABEL.get(status, "")
    points = ""
    for p in seg.get("points", []):
        ev = ""
        for e in p.get("evidence", []):
            link = e.get("link")
            src = f' <span class="ev-src">{esc(e.get("source",""))}</span>' if e.get("source") else ""
            a = (f'<a href="{esc(link)}" target="_blank" rel="noopener">Nguon &#8599;</a>'
                 if link else "")
            ev += (f'<div class="ev"><b>{esc(e.get("label",""))}</b>{src}'
                   f'<div class="ev-detail">{esc(e.get("detail",""))} {a}</div></div>')
        detail_block = (f'<details class="drill"><summary>Bằng chứng ({len(p.get("evidence",[]))})</summary>'
                        f'{ev}</details>') if p.get("evidence") else ""
        points += f'<li>{esc(p.get("text",""))}{detail_block}</li>'
    return f"""
    <div class="seg-card">
      <div class="seg-head">
        <span class="dot" style="background:{color}"></span>
        <h3>{esc(seg.get('title',''))}</h3>
        <span class="seg-status" style="color:{color}">{esc(label)}</span>
      </div>
      <ul class="points">{points}</ul>
    </div>"""


def render_assessment(a):
    if not a:
        return ('<div class="assess"><p class="muted">Chưa có phân tích. '
                'Hãy nhắn Claude Code "cập nhật báo cáo" để tạo assessment.json.</p></div>')
    overall = a.get("overall", {})
    segs = a.get("segments", {})
    seg_html = "".join(render_segment_assessment(segs.get(k))
                       for k in ("macro", "vn", "crypto") if segs.get(k))
    risks = "".join(f"<li>{esc(r)}</li>" for r in a.get("risks", []))
    watch = "".join(f"<li>{esc(w)}</li>" for w in a.get("watch", []))
    extra = ""
    if risks:
        extra += f'<div class="box risk"><h4>&#9888; Rủi ro chính</h4><ul>{risks}</ul></div>'
    if watch:
        extra += f'<div class="box watch"><h4>&#128064; Cần theo dõi</h4><ul>{watch}</ul></div>'
    return f"""
    <div class="assess">
      <div class="overall">
        <h2>{esc(overall.get('headline','Đánh giá thị trường'))}</h2>
        <p>{esc(overall.get('summary',''))}</p>
      </div>
      <div class="segs">{seg_html}</div>
      <div class="boxes">{extra}</div>
    </div>"""


# ---------------- Week-over-week ----------------

def _get(d, *path, default=None):
    for k in path:
        if isinstance(d, dict):
            d = d.get(k)
        elif isinstance(d, list):
            d = next((x for x in d if x.get("id") == k or x.get("symbol") == k), None)
        else:
            return default
        if d is None:
            return default
    return d


def _delta_row(label, now, prev, unit="", d=2):
    if now is None:
        return ""
    now_s = f"{now:,.{d}f}{unit}"
    if prev is None:
        return (f'<tr><td>{esc(label)}</td><td class="r">{now_s}</td>'
                f'<td class="r muted">-</td><td class="r muted">n/a</td></tr>')
    diff = now - prev
    pct = (diff / prev * 100) if prev else 0
    cls = "up" if diff > 0 else ("down" if diff < 0 else "flat")
    sign = "+" if diff > 0 else ""
    return (f'<tr><td>{esc(label)}</td><td class="r">{now_s}</td>'
            f'<td class="r">{prev:,.{d}f}{unit}</td>'
            f'<td class="r {cls}">{sign}{pct:.2f}%</td></tr>')


def _spark_week_ago(brief, *path):
    """Get the value ~5 trading sessions ago from the spark array (real history)."""
    node = _get(brief, *path)
    spark = node.get("spark") if isinstance(node, dict) else None
    if spark and len(spark) >= 6:
        return spark[-6]
    return None


def _prev_from_brief(brief):
    """Estimate values ~1 week ago from the historical data already in the brief.
    Used when there is no real week-old snapshot in the DB yet (first run)."""
    p = {"vn": {"index": {}}, "crypto": {"coins": [], "fear_greed": {}},
         "macro": {"items": {}}}
    p["vn"] = {"index": {}, "vn30_index": {}}
    p["vn"]["index"]["close"] = _spark_week_ago(brief, "vn", "index")
    p["vn"]["vn30_index"]["close"] = _spark_week_ago(brief, "vn", "vn30_index")
    # BTC: derive from change_7d
    btc = _get(brief, "crypto", "coins", "bitcoin")
    if btc and btc.get("price") is not None and btc.get("change_7d") is not None:
        p["crypto"]["coins"].append(
            {"id": "bitcoin", "price": btc["price"] / (1 + btc["change_7d"] / 100)})
    for k in ("Gold", "DXY", "US10Y", "VIX"):
        v = _spark_week_ago(brief, "macro", "items", k)
        if v is not None:
            p["macro"]["items"][k] = {"last": v}
    return p


def render_wow(brief, prev):
    """Compare this week vs the snapshot ~7 days ago."""
    estimated = False
    if prev and prev.get("date") and prev["date"] != brief.get("date"):
        p = prev["payload"]
        pdate = prev["date"]
    else:
        # No real week-old snapshot yet -> estimate from real history
        p = _prev_from_brief(brief)
        pdate = None
        estimated = True
    rows = ""
    # VN-Index & VN30-Index
    rows += _delta_row("VN-Index", _get(brief, "vn", "index", "close"),
                       _get(p, "vn", "index", "close"))
    rows += _delta_row("VN30-Index", _get(brief, "vn", "vn30_index", "close"),
                       _get(p, "vn", "vn30_index", "close"))
    # BTC
    rows += _delta_row("Bitcoin (USD)", _get(brief, "crypto", "coins", "bitcoin", "price"),
                       _get(p, "crypto", "coins", "bitcoin", "price"), d=0)
    # Fear & Greed
    rows += _delta_row("Fear & Greed", _get(brief, "crypto", "fear_greed", "value"),
                       _get(p, "crypto", "fear_greed", "value"), d=0)
    # Macro
    for key, lab, unit in (("Gold", "Vàng (USD/oz)", ""), ("DXY", "Chỉ số USD", ""),
                           ("US10Y", "Lợi suất Mỹ 10N", "%"), ("VIX", "VIX", "")):
        rows += _delta_row(lab, _get(brief, "macro", "items", key, "last"),
                           _get(p, "macro", "items", key, "last"), unit=unit)
    if pdate:
        note = f'so với snapshot ngày {esc(pdate)}'
    elif estimated:
        note = ('&#8776; ước lượng từ dữ liệu ~5 phiên trước (lịch sử thật). '
                'Từ tuần sau sẽ so sánh bằng snapshot đã lưu trong DB.')
    else:
        note = 'chưa có đủ lịch sử để so sánh'
    return f"""
    <table class="wow">
      <thead><tr><th>Chỉ số</th><th class="r">Hiện tại</th>
        <th class="r">Tuần trước</th><th class="r">&#916; tuần</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div class="sub" style="margin-top:6px">({note})</div>"""


# ---------------- News (from DB, ranked & capped) ----------------

TOPIC_NAMES = {"global_macro": "Vĩ mô toàn cầu", "vn": "Chứng khoán VN", "crypto": "Crypto"}


def _importance(it):
    """Importance score: number of 'important' keywords present."""
    text = (it.get("title", "") + " " + (it.get("summary") or "")).lower()
    return sum(1 for kw in config.NEWS_IMPORTANT_KEYWORDS if kw in text)


def _news_li(it):
    pub = (it.get("published") or it.get("first_seen") or "")[:16].replace("T", " ")
    link = it.get("link")
    title = esc(it.get("title", ""))
    if link:
        title = (f'<a href="{esc(link)}" target="_blank" rel="noopener" '
                 f'class="newslink">{title}</a>')
    summ = f'<div class="nsum">{esc(it.get("summary",""))}</div>' if it.get("summary") else ""
    hot = (' <span class="hot" title="Được nhiều nguồn cùng đưa">&#128293;</span>'
           if it.get("hot", 0) >= 4 else "")
    # is_new is decided SERVER-side (consistent across devices) -> baked into the class
    cls = "newsitem is-new" if it.get("is_new") else "newsitem is-read"
    return (f'<li class="{cls}">'
            f'<div class="ntitle">{title}{hot}</div>'
            f'<div class="nmeta">{esc(it.get("source",""))} &middot; {esc(pub)}</div>'
            f'{summ}</li>')


def _rank_key(it):
    """Ranking: new first -> hotter (more sources) -> more important -> more recent."""
    return (
        1 if it.get("is_new") else 0,
        it.get("hot", 0),
        _importance(it),
        it.get("published") or it.get("first_seen") or "",
    )


def _group_by_topic(items, max_per_topic):
    """Group by topic; within each topic rank by _rank_key and cap to max_per_topic."""
    blocks = ""
    by_topic = {}
    for it in items:
        by_topic.setdefault(it.get("topic", "?"), []).append(it)
    for topic in ("global_macro", "vn", "crypto"):
        lst = by_topic.get(topic)
        if not lst:
            continue
        lst.sort(key=_rank_key, reverse=True)
        shown = lst[:max_per_topic]
        n_new = sum(1 for it in shown if it.get("is_new"))
        rows = "".join(_news_li(it) for it in shown)
        cnt = (f'<span class="nbnew">{n_new} mới</span> / {len(shown)}' if n_new
               else f'{len(shown)}')
        blocks += (f'<details class="newsblock" open>'
                   f'<summary><span class="nbtitle">{esc(TOPIC_NAMES.get(topic, topic))}</span> '
                   f'<span class="nbcount">({cnt})</span></summary>'
                   f'<ul class="newslist">{rows}</ul></details>')
    return blocks


def render_news(news_rows):
    # 'New / read' is decided SERVER-side (via last_viewed, advanced weekly at build time)
    # -> consistent across ALL devices. Cap + rank by hotness/importance.
    news.annotate_hotness(news_rows)   # cross-source "hotness" (covered by many sources)
    n_new = sum(1 for n in news_rows if n.get("is_new"))
    blocks = _group_by_topic(news_rows, config.NEWS_MAX_PER_TOPIC)
    return f"""
    <div class="newstools">
      <span class="newcounter">🆕 {n_new} tin mới tuần này</span>
      <label class="switch"><input type="checkbox" id="onlynew" onchange="toggleOnlyNew()">
        <span>Chỉ hiện tin mới</span></label>
    </div>
    {blocks}
    <div class="sub" style="margin-top:8px">Nhãn 🆕 = tin mới trong tuần này (giống nhau trên mọi thiết bị) ·
      🔥 = được nhiều nguồn cùng đưa (đang nóng). Mỗi chủ đề hiện tối đa {config.NEWS_MAX_PER_TOPIC} tin,
      ưu tiên: mới → nóng → quan trọng → mới nhất. Chủ nhật tới tự làm mới.</div>"""


# ---------------- Page ----------------

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--txt:#1a1d24;--muted:#6b7280;--line:#e5e7eb;--accent:#4f46e5;}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--txt:#e5e7eb;--muted:#9aa3b2;--line:#2a2f3a;--accent:#818cf8;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.55 -apple-system,Segoe UI,Roboto,Arial,sans-serif;}
.wrap{max-width:960px;margin:0 auto;padding:20px 16px 60px;}
header h1{margin:0 0 4px;font-size:22px;}
.sub{color:var(--muted);font-size:13px;margin-bottom:8px;}
.disc{background:#fffbeb;color:#92400e;border:1px solid #fde68a;border-radius:8px;padding:8px 12px;font-size:12.5px;margin:10px 0 20px;}
@media (prefers-color-scheme:dark){.disc{background:#2a2413;color:#fcd34d;border-color:#544a1f;}}
h2{font-size:18px;margin:22px 0 10px;} h3{font-size:15px;margin:0;} h4{margin:0 0 6px;font-size:13.5px;}
.tabbar{display:flex;gap:4px;overflow-x:auto;position:sticky;top:0;z-index:20;background:var(--bg);
  padding:8px 0;margin-bottom:12px;border-bottom:1px solid var(--line);-webkit-overflow-scrolling:touch;}
.tab{flex:0 0 auto;background:transparent;border:1px solid var(--line);color:var(--muted);
  border-radius:999px;padding:7px 14px;font-size:13.5px;font-weight:600;cursor:pointer;white-space:nowrap;}
.tab.active{background:var(--accent);color:#fff;border-color:var(--accent);}
.tabpanel{display:none;} .tabpanel.active{display:block;}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px;}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
@media(max-width:820px){.grid3{grid-template-columns:1fr;}}
.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}
@media(max-width:600px){.metric-grid{grid-template-columns:repeat(2,1fr);}}
.metric{border:1px solid var(--line);border-radius:10px;padding:10px;}
.metric.big{border:none;padding:0 0 10px;}
.mname{font-weight:600;font-size:13px;} .mdesc{color:var(--muted);font-weight:400;font-size:11.5px;}
.mval{font-size:20px;font-weight:700;margin:2px 0;} .mchg{font-size:12px;color:var(--muted);}
.spark{margin-top:6px;display:block;}
.up{color:#16a34a;font-weight:600;} .down{color:#dc2626;font-weight:600;} .flat{color:var(--muted);}
.muted{color:var(--muted);}
table.wl{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px;}
table.wl th,table.wl td{padding:5px 6px;border-bottom:1px solid var(--line);} .wl .r{text-align:right;} .wl .sym{font-weight:600;}
.seg-card{margin-bottom:14px;} .seg-head{display:flex;align-items:center;gap:8px;margin-bottom:6px;}
.dot{width:11px;height:11px;border-radius:50%;display:inline-block;flex:0 0 auto;}
.seg-status{margin-left:auto;font-size:12px;font-weight:600;}
ul.points{margin:4px 0;padding-left:20px;} ul.points>li{margin-bottom:8px;}
details.drill{margin-top:5px;} details.drill>summary{cursor:pointer;color:var(--accent);font-size:12.5px;}
.ev{border-left:2px solid var(--line);padding:5px 10px;margin:6px 0;font-size:13px;}
.ev-src{color:var(--muted);font-size:11.5px;} .ev-detail{color:var(--muted);font-size:12.5px;margin-top:2px;}
.overall{background:linear-gradient(135deg,rgba(79,70,229,.08),transparent);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:14px;}
.overall h2{margin:0 0 6px;} .overall p{margin:0;}
.boxes{display:grid;grid-template-columns:1fr 1fr;gap:12px;} @media(max-width:600px){.boxes{grid-template-columns:1fr;}}
.box{border:1px solid var(--line);border-radius:10px;padding:12px;} .box ul{margin:0;padding-left:18px;font-size:13.5px;}
.box.risk{border-color:#fca5a5;} .box.watch{border-color:#93c5fd;}
details.newsblock{margin-bottom:10px;} details.newsblock>summary{cursor:pointer;font-weight:600;padding:6px 0;}
ul.newslist{list-style:none;margin:0;padding:0;}
.ntitle a{color:var(--txt);text-decoration:none;font-weight:600;font-size:14px;} .ntitle a:hover{color:var(--accent);}
.nmeta{color:var(--muted);font-size:11.5px;margin:2px 0;} .nsum{color:var(--muted);font-size:12.5px;}
a{color:var(--accent);}
/* --- VN30 aggregate --- */
.agg{border:1px solid var(--accent);border-radius:10px;padding:12px 14px;margin-bottom:12px;background:rgba(79,70,229,.05);}
.agg-title{font-weight:700;font-size:14px;margin-bottom:8px;}
.agg-row{display:flex;gap:20px;flex-wrap:wrap;}
.agg-item{min-width:80px;} .agg-val{font-size:22px;font-weight:700;} .agg-lab{font-size:11.5px;color:var(--muted);}
.agg-note{font-size:12.5px;color:var(--muted);margin-top:8px;}
/* --- Valuation cards (VN30 & crypto) --- */
.vhead,.vsummary{display:grid;grid-template-columns:64px 1fr 1fr 1fr 1.3fr 1.3fr 100px;gap:6px;align-items:center;}
.vhead{padding:4px 30px 6px 8px;font-size:11px;color:var(--muted);}
.vcard{border:1px solid var(--line);border-radius:9px;margin-bottom:6px;background:var(--card);}
.vcard>summary{list-style:none;cursor:pointer;padding:8px;position:relative;}
.vcard>summary::-webkit-details-marker{display:none;}
.vsummary{padding-right:22px;}
.vcell{font-size:13px;min-width:0;overflow:hidden;} .vcell.r{text-align:right;}
.vcell.sym{font-weight:700;} .vcell.mini{overflow:visible;}
.clab{font-size:9.5px;color:var(--muted);line-height:1;}
.vexp{position:absolute;right:10px;top:50%;transform:translateY(-50%);color:var(--muted);transition:transform .15s;}
.vcard[open]>summary .vexp{transform:translateY(-50%) rotate(90deg);}
.vcard[open]>summary{border-bottom:1px solid var(--line);}
.carddetail{padding:10px 12px 14px;}
.statline{font-size:13px;margin:6px 0;}
.chartbox{margin:6px 0 12px;border:1px solid var(--line);border-radius:8px;padding:8px;}
.charttitle{font-size:11.5px;color:var(--muted);margin-bottom:4px;}
.chartwrap{position:relative;width:100%;}
.chartwrap canvas{width:100%!important;}
th[data-key]{cursor:pointer;user-select:none;} th[data-key]:hover{color:var(--accent);}
th.sort-asc::after{content:" \\2191";} th.sort-desc::after{content:" \\2193";}
.tblfilter{margin:0 0 8px;padding:6px 10px;border:1px solid var(--line);border-radius:8px;
  background:var(--card);color:var(--txt);font-size:13px;width:180px;max-width:100%;}
svg.lc{display:block;width:100%;height:auto;}
.chartleg{font-size:11.5px;color:var(--muted);margin-bottom:4px;}
.lgd{display:inline-flex;align-items:center;gap:4px;}
.dot2{width:9px;height:9px;border-radius:2px;display:inline-block;}
.dash2{width:14px;height:0;border-top:2px dashed #f59e0b;display:inline-block;}
@media(max-width:640px){
  .vhead{display:none;}
  .vsummary{grid-template-columns:52px 1fr 1fr 1fr;grid-auto-rows:auto;}
  .vsummary .vcell.mini{display:none;}
}
.tblwrap{overflow-x:auto;}
table.vn30{width:100%;border-collapse:collapse;font-size:13px;min-width:560px;}
table.vn30 th,table.vn30 td{padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap;}
table.vn30 th{font-size:12px;color:var(--muted);text-align:left;position:sticky;top:0;background:var(--card);}
table.vn30 .r{text-align:right;} table.vn30 .sym{font-weight:700;}
table.vn30 tbody tr:hover{background:rgba(127,127,127,.06);}
.wow{width:100%;border-collapse:collapse;font-size:13.5px;}
.wow th,.wow td{padding:6px 8px;border-bottom:1px solid var(--line);} .wow .r{text-align:right;}
.wow tbody tr:hover{background:rgba(127,127,127,.06);}
/* --- News toolbar + moi/da doc (client-side) --- */
.newstools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:2px 0 12px;
  position:sticky;top:0;z-index:5;background:var(--card);padding:8px 0;}
.newcounter{font-weight:700;font-size:14px;color:var(--accent);margin-right:2px;}
.btn{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:8px 14px;font-size:13px;
  font-weight:600;cursor:pointer;}
.btn:active{transform:translateY(1px);}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--line);font-weight:500;}
.switch{display:inline-flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;user-select:none;}
.switch input{width:16px;height:16px;accent-color:var(--accent);}
.readinfo{font-size:12px;color:var(--muted);}
.newsblock{margin-bottom:8px;}
.newsblock>summary{cursor:pointer;font-weight:600;padding:6px 0;}
.nbcount{color:var(--muted);font-weight:400;font-size:12.5px;}
.nbnew{color:var(--accent);font-weight:700;}
.hot{font-size:12px;}
details.chartswrap>summary{cursor:pointer;font-weight:600;color:var(--accent);padding:6px 0;}
.newsitem{padding:9px 4px 9px 12px;border-bottom:1px solid var(--line);position:relative;transition:opacity .15s;}
.newsitem.is-new{border-left:3px solid var(--accent);background:rgba(79,70,229,.045);border-radius:0 6px 6px 0;}
.newsitem.is-new .ntitle::before{content:"MỚI";background:var(--accent);color:#fff;font-size:9px;
  font-weight:700;padding:1px 5px;border-radius:4px;margin-right:6px;vertical-align:middle;}
.newsitem.is-read{opacity:.5;}
"""

# ---------------- Client-side JS ----------------
# 'new/read' is decided SERVER-side (baked into HTML). JS only handles the "only new" toggle.

JS = """
<script>
(function(){
  // ---- Chart.js theme defaults (match light/dark) ----
  if(window.Chart){
    try{
      var cs=getComputedStyle(document.body);
      Chart.defaults.color = (cs.getPropertyValue('--muted')||'#888').trim();
      Chart.defaults.borderColor = (cs.getPropertyValue('--line')||'#ddd').trim();
      Chart.defaults.font.size = 11;
      Chart.defaults.maintainAspectRatio = false;
    }catch(e){}
  }
  // ---- Chart.js lazy init ----
  function initChart(cv){
    if(!cv || cv.dataset.done) return;
    try{
      var cfg = JSON.parse(cv.getAttribute('data-cfg'));
      cv.dataset.done = "1";
      new Chart(cv.getContext('2d'), cfg);
    }catch(e){ /* ignore */ }
  }
  function initIn(root){ (root||document).querySelectorAll('canvas.jschart').forEach(function(cv){
    if(cv.offsetParent !== null) initChart(cv);   // only when actually visible
  }); }

  // ---- Tabs ----
  window.showTab=function(id){
    document.querySelectorAll('.tab').forEach(function(t){ t.classList.toggle('active', t.dataset.tab===id); });
    document.querySelectorAll('.tabpanel').forEach(function(p){ p.classList.toggle('active', p.id==='tab-'+id); });
    var panel=document.getElementById('tab-'+id);
    if(panel) initIn(panel);
    if(window.scrollTo) window.scrollTo({top:0,behavior:'instant'});
  };
  document.addEventListener('click',function(e){
    var t=e.target.closest('.tab'); if(t){ window.showTab(t.dataset.tab); }
  });

  // ---- Init charts when a <details> opens ----
  document.addEventListener('toggle', function(e){
    var d=e.target;
    if(d.tagName==='DETAILS' && d.open) initIn(d);
  }, true);

  // ---- News: only-new toggle ----
  window.toggleOnlyNew=function(){
    var el=document.getElementById('onlynew');
    var only = el && el.checked;
    document.querySelectorAll('.newsitem').forEach(function(li){
      var isNew = li.classList.contains('is-new');
      li.style.display = (only && !isNew) ? 'none' : '';
    });
    document.querySelectorAll('.newsblock').forEach(function(b){
      var hasNew = b.querySelector('.newsitem.is-new');
      b.style.display = (only && !hasNew) ? 'none' : '';
    });
  };

  // ---- Sortable tables (click header th[data-key]) ----
  window.sortTable=function(th){
    var table=th.closest('table'), tb=table.tBodies[0];
    var key=th.getAttribute('data-key');
    var idx=Array.prototype.indexOf.call(th.parentNode.children, th);
    var asc = th.classList.contains('sort-asc') ? false : true;
    table.querySelectorAll('th').forEach(function(h){ h.classList.remove('sort-asc','sort-desc'); });
    th.classList.add(asc?'sort-asc':'sort-desc');
    var rows=Array.prototype.slice.call(tb.rows);
    rows.sort(function(a,b){
      var x=a.cells[idx].getAttribute('data-v'), y=b.cells[idx].getAttribute('data-v');
      var nx=parseFloat(x), ny=parseFloat(y);
      var both=!isNaN(nx)&&!isNaN(ny);
      if(both){ return asc?nx-ny:ny-nx; }
      x=(x||'').toString(); y=(y||'').toString();
      return asc? x.localeCompare(y) : y.localeCompare(x);
    });
    rows.forEach(function(r){ tb.appendChild(r); });
  };
  window.filterTable=function(inp){
    var q=(inp.value||'').toUpperCase();
    var tb=document.getElementById(inp.getAttribute('data-table')).tBodies[0];
    Array.prototype.slice.call(tb.rows).forEach(function(r){
      r.style.display = r.cells[0].textContent.toUpperCase().indexOf(q)>=0 ? '' : 'none';
    });
  };

  document.addEventListener('DOMContentLoaded', function(){ initIn(document); });
  initIn(document);
})();
</script>
"""


def page_content(brief, assess, news_rows, watermark, prev_snapshot):
    """Page content (style + body + script), WITHOUT doctype/html/head/body.
    Shared by the standalone report.html and the Artifact (body-only) build."""
    gen = brief.get("generated_at", "")[:16].replace("T", " ")
    tabs = [
        ("overview", "Tổng quan", "&#128202;"),
        ("vn30", "VN30", "&#127974;"),
        ("crypto", "Crypto", "&#8383;"),
        ("macro", "Vĩ mô", "&#127758;"),
        ("news", "Tin tức", "&#128240;"),
    ]
    tabbar = "".join(
        f'<button class="tab{" active" if i == 0 else ""}" data-tab="{tid}">'
        f'{icon} {esc(label)}</button>'
        for i, (tid, label, icon) in enumerate(tabs))

    return f"""<style>{CSS}</style>
<div class="wrap">
  <header>
    <h1>&#128202; Báo cáo Theo dõi Thị trường &amp; Đầu tư</h1>
    <div class="sub">Cập nhật: {esc(gen)} &middot; VN &middot; Crypto &middot; Vĩ mô toàn cầu</div>
  </header>
  <div class="disc">&#9888; Đây là công cụ <b>tổng hợp dữ liệu &amp; đánh giá tham khảo</b>, KHÔNG phải
    khuyến nghị mua/bán. Mọi quyết định đầu tư do bạn tự chịu trách nhiệm.</div>

  <div class="tabbar">{tabbar}</div>

  <section class="tabpanel active" id="tab-overview">
    {render_assessment(assess)}
    <h2>&#128197; So sánh tuần (Week-over-Week)</h2>
    <div class="card">{render_wow(brief, prev_snapshot)}</div>
    <h2>&#128200; Số liệu nhanh</h2>
    <div class="grid3">
      <div class="card"><h3>Vĩ mô toàn cầu</h3>{render_macro(brief.get('macro',{}))}</div>
      <div class="card"><h3>Chứng khoán VN</h3>{render_vn(brief.get('vn',{}))}</div>
      <div class="card"><h3>Crypto</h3>{render_crypto(brief.get('crypto',{}))}</div>
    </div>
  </section>

  <section class="tabpanel" id="tab-vn30">
    <h2>&#127974; VN30 &middot; Định giá vs Lịch sử</h2>
    <div class="card">{render_vn30(brief.get('vn',{}))}</div>
  </section>

  <section class="tabpanel" id="tab-crypto">
    <h2>&#8383; Crypto &middot; Số liệu</h2>
    <div class="card">{render_crypto(brief.get('crypto',{}))}</div>
    <h2>&#8383; Crypto &middot; Định giá dài hạn (BTC, ETH)</h2>
    <div class="card">{render_crypto_valuation(brief.get('crypto',{}))}</div>
  </section>

  <section class="tabpanel" id="tab-macro">
    <h2>&#127758; Vĩ mô toàn cầu</h2>
    <div class="card">{render_macro(brief.get('macro',{}))}</div>
  </section>

  <section class="tabpanel" id="tab-news">
    <h2>&#128240; Tin tức (bằng chứng)</h2>
    <div class="card">{render_news(news_rows)}</div>
  </section>

  <div class="sub" style="margin-top:20px;text-align:center;">
    Tạo bởi tool theo dõi đầu tư &middot; Claude Code
  </div>
</div>
<script>{_chartjs_lib()}</script>
{JS}"""


def build(brief, assess, news_rows, watermark, prev_snapshot):
    """Standalone build: open report.html directly in a browser."""
    date = brief.get("date", "")
    body = page_content(brief, assess, news_rows, watermark, prev_snapshot)
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Bao cao dau tu {esc(date)}</title></head><body>{body}</body></html>')


def main():
    do_seen = "--seen" in sys.argv

    brief_path = os.path.join(DATA_DIR, "briefing_latest.json")
    if not os.path.exists(brief_path):
        print("! No briefing_latest.json yet. Run 'python update.py' first.")
        sys.exit(1)
    with open(brief_path, encoding="utf-8") as f:
        brief = json.load(f)

    assess = None
    assess_path = os.path.join(DATA_DIR, "assessment.json")
    if os.path.exists(assess_path):
        with open(assess_path, encoding="utf-8") as f:
            assess = json.load(f)

    # DB: news (with is_new), last_viewed watermark, previous-week snapshot
    conn = store.connect()
    try:
        store.init_db(conn)
        news_rows, watermark = store.get_news(conn=conn)
        prev_snapshot = store.get_snapshot_near(days_ago=7, conn=conn)
        out = os.path.join(BASE, "report.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(build(brief, assess, news_rows, watermark, prev_snapshot))
        print(f"OK -> {out}")
        # body-only build for publishing as an Artifact (mobile viewing)
        art = os.path.join(BASE, "report_artifact.html")
        with open(art, "w", encoding="utf-8") as f:
            f.write(page_content(brief, assess, news_rows, watermark, prev_snapshot))
        print(f"OK -> {art} (body-only, for publishing as an Artifact)")
        if do_seen:
            ts = store.mark_seen(conn=conn)
            print(f"   Marked seen up to: {ts[:16].replace('T',' ')} (--seen)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
