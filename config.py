# -*- coding: utf-8 -*-
"""
Cau hinh trung tam cho tool theo doi dau tu.
Chinh sua watchlist / nguong canh bao / nguon tin o day.
"""

# ---- Watchlist co phieu VN tuy chon (ngoai VN30, de trong neu chi can VN30) ----
VN_WATCHLIST = []

# So ngay cache chi so co ban (P/E, P/B, ROE) truoc khi tai lai (doi theo quy)
FUND_MAX_AGE_DAYS = 5

# ---- Watchlist crypto (id theo CoinGecko) ----
CRYPTO_WATCHLIST = ["bitcoin", "ethereum", "solana", "binancecoin"]

# ---- Nguon tin RSS (da test chay on 2026-08) ----
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

# So tin lay moi feed (truoc khi loc)
NEWS_PER_FEED = 12

# Chi giu tin CO LIEN QUAN tai chinh/thi truong (bo tin nhieu: the thao, giai tri,
# giao thong, thoi tiet, luong huu...). Tin phai chua it nhat 1 tu khoa duoi day
# (khong phan biet hoa thuong, tieng Viet & Anh).
NEWS_FILTER_ENABLED = True
NEWS_RELEVANCE_KEYWORDS = [
    # --- Thi truong & co phieu (VN) ---
    "chứng khoán", "cổ phiếu", "vn-index", "vnindex", "vn30", "hnx", "upcom",
    "khối ngoại", "cổ tức", "niêm yết", "ipo", "vốn hóa", "thanh khoản", "phiên",
    "nâng hạng", "ftse", "msci", "quỹ", "etf", "trái phiếu", "doanh nghiệp",
    # --- Vi mo (VN) ---
    "lãi suất", "tỷ giá", "lạm phát", "gdp", "cpi", "tăng trưởng", "tín dụng",
    "ngân hàng", "sbv", "tiền tệ", "xuất khẩu", "nhập khẩu", "fdi", "đầu tư",
    "kinh tế", "vàng", "usd", "dầu", "thuế", "lợi nhuận", "doanh thu",
    # --- Vi mo toan cau / Anh ---
    "stock", "share", "market", "fed", "inflation", "rate", "treasury", "yield",
    "bond", "gdp", "cpi", "economy", "economic", "earnings", "dollar", "gold",
    "oil", "recession", "tariff", "trade", "bank", "nasdaq", "s&p", "dow",
    "powell", "ecb", "deficit", "debt", "jobs", "unemployment",
    # --- Crypto ---
    "bitcoin", "btc", "ethereum", "eth", "crypto", "altcoin", "blockchain",
    "token", "defi", "stablecoin", "sec", "solana", "bnb", "coin",
]

# ---- Nguong danh gia (chi de tham khao, KHONG phai khuyen nghi mua/ban) ----
# Fear & Greed Index (0-100)
FNG_ZONES = [
    (0, 25, "Extreme Fear", "red"),
    (25, 45, "Fear", "yellow"),
    (45, 55, "Neutral", "yellow"),
    (55, 75, "Greed", "yellow"),
    (75, 101, "Extreme Greed", "red"),
]

# VIX (chi so so hai thi truong My)
VIX_CALM = 20      # < 20: thi truong binh on
VIX_STRESS = 30    # > 30: cang thang cao

# Loi suat trai phieu My 10 nam (%)
US10Y_HIGH = 4.5   # > 4.5%: ap luc len tai san rui ro

# ---- Ticker vi mo toan cau (Yahoo Finance) ----
MACRO_TICKERS = {
    "DXY": ("DX-Y.NYB", "Chỉ số USD"),
    "Gold": ("GC=F", "Vàng (USD/oz)"),
    "Oil": ("CL=F", "Dầu WTI (USD/thùng)"),
    "US10Y": ("^TNX", "Lợi suất TPCP Mỹ 10N (%)"),
    "VIX": ("^VIX", "Chỉ số sợ hãi VIX"),
    "SP500": ("^GSPC", "S&P 500"),
}
