# -*- coding: utf-8 -*-
"""
store.py - SQLite storage layer for the investment tool.

- news       : all news over time (deduplicated by link)
- snapshots  : market data per run (for week-over-week comparison)
- meta       : the 'last_viewed' watermark and other settings
- fundamentals: per-symbol P/E, P/B, ROE, ROA + historical series (cached)
"""
import os
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "data", "investment.db")


def _now_iso():
    return datetime.utcnow().isoformat() + "Z"


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn=None):
    close = conn is None
    conn = conn or connect()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS news (
        id         TEXT PRIMARY KEY,
        topic      TEXT,
        source     TEXT,
        title      TEXT,
        summary    TEXT,
        link       TEXT,
        published  TEXT,
        first_seen TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_news_topic ON news(topic);
    CREATE INDEX IF NOT EXISTS idx_news_pub   ON news(published);

    CREATE TABLE IF NOT EXISTS snapshots (
        date    TEXT PRIMARY KEY,
        ts      TEXT,
        payload TEXT
    );

    CREATE TABLE IF NOT EXISTS meta (
        key   TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS fundamentals (
        symbol     TEXT PRIMARY KEY,
        period     TEXT,
        pe         REAL,
        pb         REAL,
        roe        REAL,
        roa        REAL,
        updated_at TEXT
    );
    """)
    # Migration: add columns for P/E, P/B historical series (JSON) if missing
    cols = {r[1] for r in conn.execute("PRAGMA table_info(fundamentals)").fetchall()}
    for col in ("pe_series", "pb_series", "periods", "pe_stats", "pb_stats"):
        if col not in cols:
            conn.execute(f"ALTER TABLE fundamentals ADD COLUMN {col} TEXT")
    conn.commit()
    if close:
        conn.close()


def _news_id(item):
    key = item.get("link") or (item.get("title", "") + item.get("source", ""))
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def upsert_news(news_by_topic, conn=None):
    """Insert new items; skip existing ones (by id). Return the count of new items."""
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    now = _now_iso()
    new_count = 0
    for topic, items in (news_by_topic or {}).items():
        for it in items:
            if not it.get("title"):
                continue
            nid = _news_id(it)
            cur = conn.execute("SELECT 1 FROM news WHERE id=?", (nid,))
            if cur.fetchone():
                continue
            conn.execute(
                "INSERT INTO news (id,topic,source,title,summary,link,published,first_seen)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (nid, topic, it.get("source"), it.get("title"), it.get("summary"),
                 it.get("link"), it.get("published"), now))
            new_count += 1
    conn.commit()
    if close:
        conn.close()
    return new_count


def prune_news(keep_predicate, conn=None):
    """Delete news NOT matching keep_predicate(row). Return count deleted.
    Used to clean out previously-stored noise after enabling the filter."""
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    rows = conn.execute("SELECT id, title, summary FROM news").fetchall()
    drop = [r["id"] for r in rows if not keep_predicate(dict(r))]
    for nid in drop:
        conn.execute("DELETE FROM news WHERE id=?", (nid,))
    conn.commit()
    if close:
        conn.close()
    return len(drop)


def save_snapshot(brief, conn=None):
    """Save market data (vn/crypto/macro) by date for week-over-week comparison."""
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    payload = {"vn": brief.get("vn"), "crypto": brief.get("crypto"),
               "macro": brief.get("macro"), "generated_at": brief.get("generated_at")}
    conn.execute("INSERT OR REPLACE INTO snapshots (date,ts,payload) VALUES (?,?,?)",
                 (brief.get("date"), _now_iso(), json.dumps(payload, ensure_ascii=False)))
    conn.commit()
    if close:
        conn.close()


def get_snapshot_near(days_ago=7, conn=None):
    """Return the snapshot closest to `days_ago` days ago (for weekly comparison)."""
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    target = (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    # latest snapshot with date <= target
    row = conn.execute(
        "SELECT * FROM snapshots WHERE date<=? ORDER BY date DESC LIMIT 1", (target,)
    ).fetchone()
    if row is None:
        # not enough history yet -> use the oldest snapshot available
        row = conn.execute(
            "SELECT * FROM snapshots ORDER BY date ASC LIMIT 1").fetchone()
    result = None
    if row:
        result = {"date": row["date"], "payload": json.loads(row["payload"])}
    if close:
        conn.close()
    return result


# ---- Meta / watermark ----

def get_meta(key, default=None, conn=None):
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    if close:
        conn.close()
    return row["value"] if row else default


def set_meta(key, value, conn=None):
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    conn.execute("INSERT OR REPLACE INTO meta (key,value) VALUES (?,?)", (key, str(value)))
    conn.commit()
    if close:
        conn.close()


def get_last_viewed(conn=None):
    """The 'last viewed' watermark. Defaults to 7 days ago on first use."""
    v = get_meta("last_viewed", None, conn=conn)
    if v is None:
        v = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
    return v


def mark_seen(conn=None):
    """Mark everything as seen up to now (advance the watermark)."""
    ts = _now_iso()
    set_meta("last_viewed", ts, conn=conn)
    return ts


_FUND_JSON = ("pe_series", "pb_series", "periods", "pe_stats", "pb_stats")


def get_fundamentals_cache(conn=None):
    """Return {symbol: {pe,pb,roe,roa,period,updated_at, + historical series}} from DB."""
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    rows = conn.execute("SELECT * FROM fundamentals").fetchall()
    out = {}
    for r in rows:
        d = dict(r)
        for k in _FUND_JSON:
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except Exception:
                    d[k] = None
        out[r["symbol"]] = d
    if close:
        conn.close()
    return out


def save_fundamentals(symbol, data, conn=None):
    """data: {pe,pb,roe,roa,period, pe_series,pb_series,periods,pe_stats,pb_stats}."""
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    js = {k: json.dumps(data.get(k), ensure_ascii=False) if data.get(k) is not None else None
          for k in _FUND_JSON}
    conn.execute(
        "INSERT OR REPLACE INTO fundamentals "
        "(symbol,period,pe,pb,roe,roa,updated_at,pe_series,pb_series,periods,pe_stats,pb_stats)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, data.get("period"), data.get("pe"), data.get("pb"),
         data.get("roe"), data.get("roa"), _now_iso(),
         js["pe_series"], js["pb_series"], js["periods"], js["pe_stats"], js["pb_stats"]))
    conn.commit()
    if close:
        conn.close()


def fundamentals_is_fresh(row, max_age_days=5):
    """True if the fundamentals record is still fresh (younger than max_age_days)."""
    if not row or not row.get("updated_at"):
        return False
    try:
        ts = datetime.fromisoformat(row["updated_at"].replace("Z", ""))
        return (datetime.utcnow() - ts) < timedelta(days=max_age_days)
    except Exception:
        return False


def get_news(topic=None, conn=None):
    """Return news from DB (newest first), each flagged 'is_new' vs last_viewed."""
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    watermark = get_last_viewed(conn=conn)
    q = "SELECT * FROM news"
    args = []
    if topic:
        q += " WHERE topic=?"
        args.append(topic)
    q += " ORDER BY COALESCE(published, first_seen) DESC"
    rows = conn.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        # 'new' = entered the feed after last_viewed (use first_seen, not published)
        # -> correct even when fetching multiple times in the same day.
        stamp = d.get("first_seen") or d.get("published") or ""
        d["is_new"] = stamp > watermark
        out.append(d)
    if close:
        conn.close()
    return out, watermark


if __name__ == "__main__":
    init_db()
    print("DB ready at", DB_PATH)
    print("last_viewed =", get_last_viewed())
