# -*- coding: utf-8 -*-
"""
Thu thap du lieu thi truong VN qua vnstock:
- VN-Index, VN30-Index (gia + xu huong)
- VN30: 30 co phieu kem so sanh lich su gia (52 tuan) + dinh gia P/E, P/B, ROE, ROA
- Watchlist tuy chon (gia + thay doi)

Chi so co ban (P/E, P/B, ROE, ROA) lay tu VCI ratio_summary (TTM, cap nhat theo quy)
va duoc cache o tang tren (DB) de khong phai tai lai moi lan.
"""
import warnings
warnings.filterwarnings("ignore")
import io
import time
import contextlib
from datetime import datetime, timedelta

# --- Rate limiter: vnstock ban Guest gioi han ~20 request/phut ---
# Bo dem cua so truot: dam bao <= _LIMIT request trong bat ky cua so 60s nao.
# Moi thao tac khai bao 'cost' = so request ngam no tieu ton
# (lich su gia = 1; ratio_summary ~ 2).
from collections import deque
_LIMIT = 18
_WINDOW = 60.0
_reqs = deque()


def _gate(cost=1):
    while True:
        now = time.time()
        while _reqs and now - _reqs[0] > _WINDOW:
            _reqs.popleft()
        if len(_reqs) + cost <= _LIMIT:
            break
        sleep = _WINDOW - (now - _reqs[0]) + 0.15
        time.sleep(max(sleep, 0.15))
    now = time.time()
    for _ in range(cost):
        _reqs.append(now)

# Danh sach VN30 du phong (neu goi API nhom that bai)
VN30_FALLBACK = ["ACB", "BID", "BSR", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG", "LPB",
                 "MBB", "MCH", "MSN", "MWG", "SAB", "SHB", "SSB", "SSI", "STB", "TCB",
                 "TCX", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VPL", "VRE"]


def _vnstock():
    from vnstock import Vnstock
    with contextlib.redirect_stdout(io.StringIO()):
        return Vnstock()


def _stock(v, symbol):
    with contextlib.redirect_stdout(io.StringIO()):
        return v.stock(symbol=symbol, source="VCI")


def _history(s, symbol, days=90):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    _gate(1)
    with contextlib.redirect_stdout(io.StringIO()):
        df = s.quote.history(symbol=symbol, start=start, end=end, interval="1D")
    return df


def _index_block(s, symbol, name, days=120):
    df = _history(s, symbol, days=days)
    closes = df["close"].tolist()
    vols = df["volume"].tolist()
    last, prev = closes[-1], closes[-2]
    return {
        "name": name,
        "date": str(df["time"].iloc[-1])[:10],
        "close": round(last, 2),
        "change": round(last - prev, 2),
        "change_pct": round((last - prev) / prev * 100, 2),
        "volume": int(vols[-1]),
        "change_20d_pct": round((last - closes[-21]) / closes[-21] * 100, 2) if len(closes) > 21 else None,
        "spark": [round(float(x), 2) for x in closes[-30:]],
    }


def _pct(a, b):
    return round((a - b) / b * 100, 2) if b else None


def _price_and_history(s, sym):
    """Gia hien tai + ngan han (tuan/thang) + so sanh lich su gia 52 tuan."""
    df = _history(s, sym, days=380)
    closes = df["close"].tolist()
    last, prev = closes[-1], closes[-2]
    hi, lo = max(closes), min(closes)
    first = closes[0]
    pos = (last - lo) / (hi - lo) * 100 if hi > lo else None  # vi tri trong dai 52T (%)

    def ago(n):
        return closes[-1 - n] if len(closes) > n else None
    w = ago(5)   # ~1 tuan giao dich
    m = ago(21)  # ~1 thang giao dich
    return {
        "close": round(last, 2),
        "change_pct": _pct(last, prev),
        "change_1w": _pct(last, w) if w else None,
        "change_1m": _pct(last, m) if m else None,
        "w52_high": round(hi, 2),
        "w52_low": round(lo, 2),
        "w52_pos": round(pos, 0) if pos is not None else None,
        "ret_1y": _pct(last, first),
        "volume": int(df["volume"].iloc[-1]),
    }


def _stats(series):
    vals = [x for x in series if x is not None]
    if not vals:
        return {}
    avg = sum(vals) / len(vals)
    cur = vals[-1]
    return {
        "avg": round(avg, 2),
        "min": round(min(vals), 2),
        "max": round(max(vals), 2),
        "cur": round(cur, 2),
        "vs_avg_pct": round((cur - avg) / avg * 100, 1) if avg else None,
    }


def fetch_fundamentals(v, sym):
    """Lay P/E, P/B, ROE, ROA moi nhat + chuoi lich su P/E, P/B (TTM ~8 nam)."""
    _gate(2)
    with contextlib.redirect_stdout(io.StringIO()):
        rs = v.stock(symbol=sym, source="VCI").company.ratio_summary()
    ttm = rs[rs["ratio_type"] == "RATIO_TTM"].copy()
    ttm["yy"] = ttm["year"].astype(int)
    ttm["qq"] = ttm["quarter"].astype(int)
    ttm = ttm.sort_values(["yy", "qq"])
    last = ttm.iloc[-1]

    def num(x):
        try:
            return float(x)
        except Exception:
            return None
    pe_series = [round(num(x), 2) if num(x) is not None else None for x in ttm["pe"].tolist()]
    pb_series = [round(num(x), 2) if num(x) is not None else None for x in ttm["pb"].tolist()]
    periods = [f"{y}Q{q}" for y, q in zip(ttm["yy"].tolist(), ttm["qq"].tolist())]
    roe, roa = num(last["roe"]), num(last["roa"])
    return {
        "pe": pe_series[-1] if pe_series else None,
        "pb": pb_series[-1] if pb_series else None,
        "roe": round(roe * 100, 1) if roe is not None else None,
        "roa": round(roa * 100, 1) if roa is not None else None,
        "period": f"{last['year']}Q{last['quarter']}",
        "pe_series": pe_series,
        "pb_series": pb_series,
        "periods": periods,
        "pe_stats": _stats(pe_series),
        "pb_stats": _stats(pb_series),
    }


def get_vn30_list(v):
    try:
        _gate(1)
        with contextlib.redirect_stdout(io.StringIO()):
            g = v.stock(symbol="ACB", source="VCI").listing.symbols_by_group("VN30")
        syms = [str(x) for x in list(g)]
        return syms or VN30_FALLBACK
    except Exception:
        return VN30_FALLBACK


def collect(watchlist, fund_cache=None, fund_max_age_days=5, fund_is_fresh=None):
    """
    fund_cache: dict {symbol: {pe,pb,roe,roa,period,updated_at}} tu DB (de cache).
    fund_is_fresh: ham(row, max_age_days)->bool (truyen tu store de kiem tra do moi).
    Tra ve them 'fundamentals_fetched' = {sym: data} de tang tren luu vao DB.
    """
    fund_cache = fund_cache or {}
    out = {"error": None, "index": {}, "vn30_index": {}, "watchlist": [],
           "vn30": [], "fundamentals_fetched": {}}
    try:
        v = _vnstock()
        s = _stock(v, "VCI")
    except Exception as e:
        out["error"] = f"init vnstock: {e}"
        return out

    # VN-Index & VN30-Index
    try:
        out["index"] = _index_block(s, "VNINDEX", "VN-Index")
    except Exception as e:
        out["error"] = (out["error"] or "") + f" | vnindex: {e}"
    try:
        out["vn30_index"] = _index_block(s, "VN30", "VN30-Index")
    except Exception as e:
        out["error"] = (out["error"] or "") + f" | vn30index: {e}"

    # VN30 constituents
    vn30 = get_vn30_list(v)
    for sym in vn30:
        row = {"symbol": sym}
        try:
            row.update(_price_and_history(s, sym))
        except Exception as e:
            row["error"] = f"price: {e}"
        # fundamentals: dung cache neu con moi, khong thi tai moi
        cached = fund_cache.get(sym)
        fresh = (fund_is_fresh(cached, fund_max_age_days) if fund_is_fresh else False)
        # coi la cu neu thieu chuoi lich su (de bo sung series cho ban ghi cache cu)
        if fresh and not (cached and cached.get("pe_series")):
            fresh = False
        if fresh:
            for k in ("pe", "pb", "roe", "roa", "period",
                      "pe_series", "pb_series", "periods", "pe_stats", "pb_stats"):
                row[k] = cached.get(k)
        else:
            try:
                f = fetch_fundamentals(v, sym)
                row.update(f)
                out["fundamentals_fetched"][sym] = f
            except Exception:
                # tai loi -> dung cache cu neu co
                if cached:
                    for k in ("pe", "pb", "roe", "roa", "period"):
                        row[k] = cached.get(k)
        out["vn30"].append(row)

    # Watchlist tuy chon (gia + thay doi)
    for sym in (watchlist or []):
        try:
            df = _history(s, sym, days=30)
            closes = df["close"].tolist()
            last, prev = closes[-1], closes[-2]
            out["watchlist"].append({
                "symbol": sym,
                "close": round(last, 2),
                "change_pct": round((last - prev) / prev * 100, 2),
                "volume": int(df["volume"].iloc[-1]),
            })
        except Exception as e:
            out["watchlist"].append({"symbol": sym, "error": str(e)})

    return out


if __name__ == "__main__":
    import json
    r = collect([])
    print(json.dumps({k: (v if k != "vn30" else v[:3]) for k, v in r.items()},
                     ensure_ascii=False, indent=2, default=str))
