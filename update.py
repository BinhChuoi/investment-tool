# -*- coding: utf-8 -*-
"""
update.py - Collect all data + news -> save briefing pack (JSON) + DB.

Run:  python update.py

Produces data/briefing_YYYY-MM-DD.json and data/briefing_latest.json, and updates
the SQLite DB. Then ask Claude Code "cap nhat bao cao" to analyze + build report.html.
"""
import sys
import os
import json
from datetime import datetime

# Ensure Vietnamese / emoji print without errors on Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import store
import weekly
from collectors import vn_market, crypto, macro, news

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def log(msg):
    print(msg, flush=True)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now()
    log(f"=== Collecting data at {now:%Y-%m-%d %H:%M} ===")

    pack = {
        "generated_at": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
    }

    log("[1/4] VN market + VN30 (vnstock)...")
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
    log(f"      VN30: {len(pack['vn'].get('vn30', []))} symbols "
        f"({len(fetched)} refetched fundamentals, rest from cache)")
    if pack["vn"].get("error"):
        log(f"      ! VN note: {pack['vn'].get('error')}")

    log("[2/4] Crypto (CoinGecko + Fear&Greed)...")
    pack["crypto"] = crypto.collect(config.CRYPTO_WATCHLIST)
    fng = pack["crypto"].get("fear_greed", {})
    if fng:
        log(f"      Fear & Greed = {fng.get('value')} ({fng.get('label')})")

    log("[3/4] Global macro (Yahoo Finance)...")
    pack["macro"] = macro.collect(config.MACRO_TICKERS)
    items = pack["macro"].get("items", {})
    for k in ("DXY", "US10Y", "VIX", "Gold"):
        it = items.get(k, {})
        if it.get("last") is not None:
            log(f"      {k:6} = {it['last']} ({it.get('change_1d_pct')}%/1d)")

    log("[4/4] News (RSS, relevance-filtered)...")
    kw = config.NEWS_RELEVANCE_KEYWORDS if getattr(config, "NEWS_FILTER_ENABLED", False) else None
    pack["news"] = news.collect(config.NEWS_FEEDS, config.NEWS_PER_FEED, relevance_keywords=kw)
    for topic, items in pack["news"].items():
        log(f"      {topic:14}: {len(items)} items")

    # Save JSON files
    dated = os.path.join(DATA_DIR, f"briefing_{pack['date']}.json")
    latest = os.path.join(DATA_DIR, "briefing_latest.json")
    for path in (dated, latest):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=2)

    # Save to DB (news + market snapshot)
    log("")
    log("[DB] Saving news & snapshot to SQLite...")
    conn = store.connect()
    try:
        new_count = store.upsert_news(pack["news"], conn=conn)
        pruned = 0
        if kw:  # clean out old noise still stored in the DB
            pruned = store.prune_news(lambda r: news.is_relevant(r, kw), conn=conn)
        store.save_snapshot(pack, conn=conn)
        last_viewed = store.get_last_viewed(conn=conn)
    finally:
        conn.close()
    log(f"      +{new_count} new items saved, pruned {pruned} old noise items")
    log(f"      last_viewed: {last_viewed[:16].replace('T',' ')}")

    # Build & save this week's report snapshot (aggregate + rule-based assessment)
    log("[DB] Building weekly report...")
    conn = store.connect()
    try:
        prev_snapshot = store.get_snapshot_near(days_ago=7, conn=conn)
        news_week = store.get_news_since(days=7, conn=conn)
        payload = weekly.build_payload(pack, prev_snapshot, news_week)
        wk = now.strftime("%G-W%V")
        label = f"Tuần {now:%d/%m/%Y}"
        store.save_weekly_report(wk, label, payload, conn=conn)
    finally:
        conn.close()
    log(f"      Weekly report saved: {wk} ({label}) — {payload['assessment']['headline']}")

    log("")
    log(f"OK -> {dated}")
    log(f"OK -> {latest}")
    log(f"OK -> {store.DB_PATH}")
    log("")
    log(">> Next: ask Claude Code 'cap nhat bao cao' to analyze + build report.html")


if __name__ == "__main__":
    main()
