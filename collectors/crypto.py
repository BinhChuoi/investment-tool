# -*- coding: utf-8 -*-
"""Collect crypto data: CoinGecko (prices, market cap, dominance) + Fear & Greed."""
import requests

CG = "https://api.coingecko.com/api/v3"
TIMEOUT = 20


def _get(url, params=None):
    r = requests.get(url, params=params, timeout=TIMEOUT,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.json()


def longterm(coin_to_ticker):
    """Long-term price for BTC/ETH: monthly series + all-time average + MA200 (Mayer Multiple)."""
    import warnings
    warnings.filterwarnings("ignore")
    import yfinance as yf
    out = {}
    for coin, ticker in coin_to_ticker.items():
        try:
            m = yf.Ticker(ticker).history(period="max", interval="1mo")["Close"].dropna()
            d = yf.Ticker(ticker).history(period="400d")["Close"].dropna()
            series = [round(float(x), 2) for x in m.tolist()]
            labels = [str(i)[:7] for i in m.index]
            cur = float(d.iloc[-1]) if len(d) else float(m.iloc[-1])
            avg_all = float(m.mean())
            ma200 = float(d.tail(200).mean()) if len(d) >= 200 else None
            out[coin] = {
                "series": series,
                "labels": labels,
                "start": labels[0] if labels else None,
                "current": round(cur, 2),
                "avg_all": round(avg_all, 2),
                "vs_avg_pct": round((cur - avg_all) / avg_all * 100, 1) if avg_all else None,
                "ma200": round(ma200, 2) if ma200 else None,
                "mayer": round(cur / ma200, 2) if ma200 else None,
            }
        except Exception as e:
            out[coin] = {"error": str(e)}
    return out


def collect(watchlist):
    out = {"error": None, "global": {}, "coins": [], "fear_greed": {}, "longterm": {}}
    # Market overview
    try:
        g = _get(f"{CG}/global")["data"]
        out["global"] = {
            "total_market_cap_usd": g["total_market_cap"]["usd"],
            "total_volume_usd": g["total_volume"]["usd"],
            "btc_dominance": g["market_cap_percentage"]["btc"],
            "eth_dominance": g["market_cap_percentage"].get("eth"),
            "market_cap_change_24h": g["market_cap_change_percentage_24h_usd"],
        }
    except Exception as e:
        out["error"] = f"global: {e}"

    # Watchlist coin prices
    try:
        data = _get(f"{CG}/coins/markets", {
            "vs_currency": "usd",
            "ids": ",".join(watchlist),
            "price_change_percentage": "24h,7d,30d",
        })
        for c in data:
            out["coins"].append({
                "id": c["id"],
                "symbol": c["symbol"].upper(),
                "name": c["name"],
                "price": c["current_price"],
                "change_24h": c.get("price_change_percentage_24h"),
                "change_7d": c.get("price_change_percentage_7d_in_currency"),
                "change_30d": c.get("price_change_percentage_30d_in_currency"),
                "market_cap": c.get("market_cap"),
                "ath_change": c.get("ath_change_percentage"),
            })
    except Exception as e:
        out["error"] = (out["error"] or "") + f" | coins: {e}"

    # Long-term valuation (price vs multi-year average) via yfinance
    try:
        out["longterm"] = longterm({"bitcoin": "BTC-USD", "ethereum": "ETH-USD"})
    except Exception as e:
        out["longterm"] = {}
        out["error"] = (out["error"] or "") + f" | longterm: {e}"

    # Fear & Greed
    try:
        f = _get("https://api.alternative.me/fng/", {"limit": 2})["data"]
        out["fear_greed"] = {
            "value": int(f[0]["value"]),
            "label": f[0]["value_classification"],
            "prev_value": int(f[1]["value"]) if len(f) > 1 else None,
        }
    except Exception as e:
        out["error"] = (out["error"] or "") + f" | fng: {e}"

    return out


if __name__ == "__main__":
    import json
    print(json.dumps(collect(["bitcoin", "ethereum"]), indent=2))
