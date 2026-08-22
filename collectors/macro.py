# -*- coding: utf-8 -*-
"""Collect global macro indicators via Yahoo Finance (yfinance)."""
import warnings
warnings.filterwarnings("ignore")


def collect(tickers):
    """tickers: dict {name: (symbol, description)}"""
    import yfinance as yf
    out = {"error": None, "items": {}}
    try:
        for name, (sym, desc) in tickers.items():
            try:
                h = yf.Ticker(sym).history(period="1mo")
                if h is None or len(h) == 0:
                    out["items"][name] = {"error": "no data", "desc": desc}
                    continue
                closes = h["Close"].dropna()
                last = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) > 1 else last
                first = float(closes.iloc[0])
                out["items"][name] = {
                    "desc": desc,
                    "symbol": sym,
                    "last": round(last, 2),
                    "change_1d": round(last - prev, 2),
                    "change_1d_pct": round((last - prev) / prev * 100, 2) if prev else None,
                    "change_1mo_pct": round((last - first) / first * 100, 2) if first else None,
                    # ~30 sessions for a sparkline
                    "spark": [round(float(x), 2) for x in closes.tail(30).tolist()],
                }
            except Exception as e:
                out["items"][name] = {"error": str(e), "desc": desc}
    except Exception as e:
        out["error"] = str(e)
    return out


if __name__ == "__main__":
    import json
    from config import MACRO_TICKERS
    print(json.dumps(collect(MACRO_TICKERS), indent=2))
