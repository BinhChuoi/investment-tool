# 📊 Tool Theo dõi Thị trường & Đầu tư

Công cụ tổng hợp **dữ liệu + tin tức** thị trường (Việt Nam · Crypto · Vĩ mô toàn cầu),
kèm **đánh giá có bằng chứng** để bạn tham khảo khi ra quyết định đầu tư.

> ⚠️ **Miễn trừ trách nhiệm:** Đây là công cụ *tổng hợp & phân tích tham khảo*,
> **KHÔNG phải khuyến nghị mua/bán**. Mọi quyết định đầu tư do bạn tự chịu trách nhiệm.

---

## 🚀 Quy trình xem theo tuần

### Bước 1 — Thu thập dữ liệu
```bash
python update.py
```
Tải VN-Index, watchlist cổ phiếu, giá crypto, chỉ số vĩ mô (vàng/dầu/DXY/lợi suất/VIX/S&P)
và tin tức RSS → lưu `data/briefing_latest.json` **và vào DB** (`data/investment.db`):
tin được khử trùng lặp + lưu snapshot số liệu để so sánh tuần.

### Bước 2 — Tạo báo cáo
Nhắn Claude Code: **"cập nhật báo cáo"** → Claude đọc dữ liệu, viết phân tích kèm bằng chứng
vào `data/assessment.json`, rồi dựng `report.html`.

Mở `report.html` bằng trình duyệt / điện thoại.

### Bước 3 — Xem xong, đánh dấu đã đọc
Ngay **trong báo cáo** (chạy được cả trên điện thoại, không cần server):
- Bấm nút **“✓ Đã đọc hết & lưu mốc”** → trình duyệt nhớ mốc thời điểm này (localStorage).
  Lần sau chỉ tin **mới về sau mốc đó** hiện nhãn 🆕.
- Bật **“Chỉ hiện tin mới”** để ẩn tin đã đọc; **“Bỏ mốc”** để xem lại tất cả.
- Bấm vào một tin cũng đánh dấu tin đó (và cũ hơn) là đã đọc.

> Cách phân loại: mỗi tin nhớ **`first_seen`** (lúc *vào feed*); tin có `first_seen` **sau** mốc đã-đọc = 🆕.
> Dùng `first_seen` (không phải ngày xuất bản) nên **fetch nhiều lần trong ngày vẫn đúng**.

> Chỉ dựng lại HTML (không đổi mốc đã xem — an toàn chạy lại nhiều lần):
> ```bash
> python render.py
> ```

## 🏦 VN30 · Định giá & Lịch sử giá
Báo cáo có bảng **30 cổ phiếu VN30** với:
- **Giá** và **Δ ngày**
- **Δ 1 năm** và **Vị trí 52 tuần** (giá hiện tại nằm đâu trong dải đỉnh–đáy 52 tuần) → *so sánh lịch sử giá*
- **P/E, P/B, ROE** (TTM, cập nhật theo quý, lấy từ VCI `ratio_summary`)
- Tô xanh gợi ý nhanh: ROE≥20% · P/E≤10 · P/B≤1,5 (chỉ để dễ nhìn, **không phải khuyến nghị**)

> ⏳ **Lần chạy `update.py` đầu tiên mất ~6-7 phút** vì vnstock (bản miễn phí) giới hạn ~20 request/phút,
> nên tool tự giãn nhịp gọi cho 30 mã. Các chỉ số cơ bản (P/E, P/B, ROE + chuỗi lịch sử) được **cache trong DB**
> và chỉ tải lại sau `FUND_MAX_AGE_DAYS` ngày (mặc định 5) → những lần sau nhanh hơn nhiều (~2 phút).

### Định giá vs lịch sử (bấm vào từng mã)
- **VN30:** mỗi mã là một thẻ bấm mở được — dòng tóm tắt hiện Δ **tuần** / **tháng** và **P/E, P/B so với
  trung bình lịch sử (~8 năm)** (nhãn *dưới TB* = rẻ hơn lịch sử). **Bấm vào** → biểu đồ P/E & P/B dài hạn
  (đường trung bình), min/max/hiện tại.
- **Crypto (BTC, ETH):** tương tự — Δ tuần/tháng + **giá so với trung bình toàn kỳ** và **Mayer Multiple**
  (giá/MA200: ≥2,4 nóng, ≤1 rẻ theo lịch sử). Bấm vào → biểu đồ giá dài hạn (từ 2014/2017, qua yfinance).
- ⚠️ Dữ liệu P/E/P/B chỉ có **~8 năm** (từ 2018) — nguồn miễn phí không có P/E 10-20 năm. Giá thì dài hơn.

## 🧹 Lọc tin nhiễu
Chỉ giữ tin **liên quan tài chính/thị trường**. Mỗi tin phải chứa ít nhất 1 từ khoá trong
`config.NEWS_RELEVANCE_KEYWORDS` (song ngữ Việt–Anh: chứng khoán, lãi suất, vàng, Fed, inflation,
bitcoin…). Tin nhiễu (thể thao, giải trí, giao thông, lương hưu, xổ số…) bị loại. Tin nhiễu cũ
đã lưu cũng được dọn khỏi DB mỗi lần chạy. Tắt bằng `NEWS_FILTER_ENABLED = False`.

## 📅 Tính năng theo tuần
- **🆕 Tin mới từ lần xem trước** vs **📁 Đã xem** — tách nhóm rõ ràng theo mốc `last_viewed` trong DB.
- **So sánh Δ tuần (Week-over-Week):** VN-Index, BTC, Vàng, DXY, Lợi suất Mỹ 10N, VIX, Fear&Greed —
  tuần đầu ước lượng từ dữ liệu lịch sử thật, từ tuần sau so bằng snapshot đã lưu trong DB.
- **Click = đã đọc:** bấm 1 tin → tin đó + cũ hơn coi như đã xem (localStorage).

---

## 📁 Cấu trúc

| File / thư mục | Vai trò |
|---|---|
| `config.py` | Cấu hình: watchlist cổ phiếu/coin, nguồn tin, ngưỡng cảnh báo |
| `collectors/` | Bộ thu thập: `vn_market`, `crypto`, `macro`, `news` |
| `store.py` | Lớp DB SQLite: lưu tin (khử trùng lặp), snapshot, mốc "xem lần cuối" |
| `update.py` | Chạy thu thập → briefing pack + ghi DB |
| `render.py` | Dựng `report.html` (thêm `--seen` để đánh dấu đã xem) |
| `data/investment.db` | DB SQLite: lịch sử tin + snapshot + mốc xem |
| `data/` | Dữ liệu thô + phân tích theo ngày |
| `report.html` | Báo cáo cuối (tương tác, click xem bằng chứng / đã đọc) |

---

## ⚙️ Tùy chỉnh

Mở `config.py`:
- `VN_WATCHLIST` — danh sách mã cổ phiếu VN theo dõi
- `CRYPTO_WATCHLIST` — danh sách coin (dùng id CoinGecko: `bitcoin`, `ethereum`, `solana`...)
- `NEWS_FEEDS` — thêm/bớt nguồn RSS
- Các ngưỡng: `VIX_STRESS`, `US10Y_HIGH`, `FNG_ZONES`...

---

## 🔧 Cài đặt lần đầu
```bash
pip install -r requirements.txt
```

Nguồn dữ liệu (miễn phí, không cần API key): CoinGecko · alternative.me (Fear & Greed) ·
Yahoo Finance (`yfinance`) · vnstock · RSS (CafeF, VnExpress, CoinDesk, CNBC, MarketWatch).

---

## 🔼 Nâng cấp về sau (tùy chọn — Bước 2 trong kế hoạch)
Cắm **Anthropic API key** để tool tự gọi Claude phân tích → tự động 100%,
và click drill-down sinh phân tích mới tức thì (thay vì nhắn Claude Code mỗi lần).
Nói với Claude Code khi bạn muốn làm phần này.
