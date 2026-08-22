# -*- coding: utf-8 -*-
"""
update.py - Thu thap toan bo du lieu + tin tuc -> luu briefing pack (JSON).

Chay:  python update.py

Sau khi chay xong, se co file data/briefing_YYYY-MM-DD.json va data/briefing_latest.json.
Roi nhan Claude Code "cap nhat bao cao" de phan tich va dung report.html.
"""
import sys
import io
import os
import json
from datetime import datetime

# Bao dam in tieng Viet / emoji khong loi tren Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import store
from collectors import vn_market, crypto, macro, news

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def log(msg):
    print(msg, flush=True)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now()
    log(f"=== Thu thap du lieu luc {now:%Y-%m-%d %H:%M} ===")

    pack = {
        "generated_at": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
    }

    log("[1/4] Thi truong VN + VN30 (vnstock)...")
    fund_cache = store.get_fundamentals_cache()
    pack["vn"] = vn_market.collect(
        config.VN_WATCHLIST,
        fund_cache=fund_cache,
        fund_max_age_days=config.FUND_MAX_AGE_DAYS,
        fund_is_fresh=store.fundamentals_is_fresh,
    )
    if pack["vn"].get("index", {}).get("close"):
        log(f"      VN-Index = {pack['vn']['index']['close']} "
            f"({pack['vn']['index']['change_pct']:+.2f}%)")
    if pack["vn"].get("vn30_index", {}).get("close"):
        log(f"      VN30     = {pack['vn']['vn30_index']['close']} "
            f"({pack['vn']['vn30_index']['change_pct']:+.2f}%)")
    fetched = pack["vn"].get("fundamentals_fetched", {})
    for sym, data in fetched.items():
        store.save_fundamentals(sym, data)
    log(f"      VN30: {len(pack['vn'].get('vn30', []))} ma "
        f"({len(fetched)} ma tai moi chi so co ban, con lai dung cache)")
    if pack["vn"].get("error"):
        log(f"      ! Luu y VN: {pack['vn'].get('error')}")

    log("[2/4] Crypto (CoinGecko + Fear&Greed)...")
    pack["crypto"] = crypto.collect(config.CRYPTO_WATCHLIST)
    fng = pack["crypto"].get("fear_greed", {})
    if fng:
        log(f"      Fear & Greed = {fng.get('value')} ({fng.get('label')})")

    log("[3/4] Vi mo toan cau (Yahoo Finance)...")
    pack["macro"] = macro.collect(config.MACRO_TICKERS)
    items = pack["macro"].get("items", {})
    for k in ("DXY", "US10Y", "VIX", "Gold"):
        it = items.get(k, {})
        if it.get("last") is not None:
            log(f"      {k:6} = {it['last']} ({it.get('change_1d_pct')}%/1d)")

    log("[4/4] Tin tuc (RSS, loc tin lien quan)...")
    kw = config.NEWS_RELEVANCE_KEYWORDS if getattr(config, "NEWS_FILTER_ENABLED", False) else None
    pack["news"] = news.collect(config.NEWS_FEEDS, config.NEWS_PER_FEED, relevance_keywords=kw)
    for topic, items in pack["news"].items():
        log(f"      {topic:14}: {len(items)} tin")

    # Luu file JSON
    dated = os.path.join(DATA_DIR, f"briefing_{pack['date']}.json")
    latest = os.path.join(DATA_DIR, "briefing_latest.json")
    for path in (dated, latest):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=2)

    # Luu vao DB (tin + snapshot so lieu)
    log("")
    log("[DB] Luu tin & snapshot vao SQLite...")
    conn = store.connect()
    try:
        new_count = store.upsert_news(pack["news"], conn=conn)
        pruned = 0
        if kw:  # don tin nhieu cu con sot trong DB
            pruned = store.prune_news(lambda r: news.is_relevant(r, kw), conn=conn)
        store.save_snapshot(pack, conn=conn)
        last_viewed = store.get_last_viewed(conn=conn)
    finally:
        conn.close()
    log(f"      +{new_count} tin moi luu vao DB, don {pruned} tin nhieu cu")
    log(f"      Xem lan cuoi (last_viewed): {last_viewed[:16].replace('T',' ')}")

    log("")
    log(f"OK -> {dated}")
    log(f"OK -> {latest}")
    log(f"OK -> {store.DB_PATH}")
    log("")
    log(">> Buoc tiep: nhan Claude Code 'cap nhat bao cao' de phan tich + dung report.html")


if __name__ == "__main__":
    main()
