# -*- coding: utf-8 -*-
"""
Central configuration for the investment tracking tool.
Edit watchlists / alert thresholds / news sources here.

Note: strings shown to the user in the report (e.g. MACRO_TICKERS descriptions)
are intentionally kept in Vietnamese; everything else stays in English.
"""

# ---- Optional extra VN watchlist (besides VN30; leave empty to only use VN30) ----
VN_WATCHLIST = []

# Days to cache fundamentals (P/E, P/B, ROE) before refetching (they change quarterly)
FUND_MAX_AGE_DAYS = 5

# ---- Crypto watchlist (CoinGecko ids) ----
CRYPTO_WATCHLIST = ["bitcoin", "ethereum", "solana", "binancecoin"]

# ---- News RSS sources (verified working as of 2026-08) ----
NEWS_FEEDS = {
    "global_macro": [
        ("CNBC Economy", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ],
    "vn": [
        ("CafeF - Chung khoan", "https://cafef.vn/thi-truong-chung-khoan.rss"),
        ("CafeF - Vi mo", "https://cafef.vn/vi-mo-dau-tu.rss"),
        ("VnExpress - Kinh doanh", "https://vnexpress.net/rss/kinh-doanh.rss"),
    ],
    "crypto": [
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ],
}

# Items fetched per feed (before filtering)
NEWS_PER_FEED = 12

# Max news items DISPLAYED per topic (keep only the most important, avoid pile-up)
NEWS_MAX_PER_TOPIC = 12

# Keep only finance/market-relevant news: an item must contain at least one of these
# keywords (case-insensitive, Vietnamese & English) to be kept.
NEWS_FILTER_ENABLED = True
NEWS_RELEVANCE_KEYWORDS = [
    # --- Market & stocks (VN) ---
    "chứng khoán", "cổ phiếu", "vn-index", "vnindex", "vn30", "hnx", "upcom",
    "khối ngoại", "cổ tức", "niêm yết", "ipo", "vốn hóa", "thanh khoản", "phiên",
    "nâng hạng", "ftse", "msci", "quỹ", "etf", "trái phiếu", "doanh nghiệp",
    # --- Macro (VN) ---
    "lãi suất", "tỷ giá", "lạm phát", "gdp", "cpi", "tăng trưởng", "tín dụng",
    "ngân hàng", "sbv", "tiền tệ", "xuất khẩu", "nhập khẩu", "fdi", "đầu tư",
    "kinh tế", "vàng", "usd", "dầu", "thuế", "lợi nhuận", "doanh thu",
    # --- Global macro / English ---
    "stock", "share", "market", "fed", "inflation", "rate", "treasury", "yield",
    "bond", "gdp", "cpi", "economy", "economic", "earnings", "dollar", "gold",
    "oil", "recession", "tariff", "trade", "bank", "nasdaq", "s&p", "dow",
    "powell", "ecb", "deficit", "debt", "jobs", "unemployment",
    # --- Crypto ---
    "bitcoin", "btc", "ethereum", "eth", "crypto", "altcoin", "blockchain",
    "token", "defi", "stablecoin", "sec", "solana", "bnb", "coin",
]

# "Important" keywords: items containing these are ranked higher (shown first)
NEWS_IMPORTANT_KEYWORDS = [
    # VN
    "vn-index", "vnindex", "vn30", "nâng hạng", "ftse", "khối ngoại", "lãi suất",
    "tỷ giá", "lạm phát", "gdp", "sbv", "ngân hàng nhà nước", "cổ tức", "lợi nhuận",
    # Global
    "fed", "powell", "inflation", "rate cut", "rate hike", "treasury", "recession",
    "tariff", "cpi", "jobs", "ecb", "gdp",
    # Crypto
    "bitcoin", "btc", "ethereum", "eth", "etf", "sec", "halving",
]

# ---- Alert thresholds (reference only, NOT buy/sell advice) ----
# Fear & Greed Index (0-100)
FNG_ZONES = [
    (0, 25, "Extreme Fear", "red"),
    (25, 45, "Fear", "yellow"),
    (45, 55, "Neutral", "yellow"),
    (55, 75, "Greed", "yellow"),
    (75, 101, "Extreme Greed", "red"),
]

# VIX (US market fear gauge)
VIX_CALM = 20      # < 20: calm market
VIX_STRESS = 30    # > 30: high stress

# US 10-year Treasury yield (%)
US10Y_HIGH = 4.5   # > 4.5%: pressure on risk assets

# ---- Global macro tickers (Yahoo Finance). Descriptions shown in report -> Vietnamese ----
MACRO_TICKERS = {
    "DXY": ("DX-Y.NYB", "Chỉ số USD"),
    "Gold": ("GC=F", "Vàng (USD/oz)"),
    "Oil": ("CL=F", "Dầu WTI (USD/thùng)"),
    "US10Y": ("^TNX", "Lợi suất TPCP Mỹ 10N (%)"),
    "VIX": ("^VIX", "Chỉ số sợ hãi VIX"),
    "SP500": ("^GSPC", "S&P 500"),
}
