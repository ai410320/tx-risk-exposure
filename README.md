# 台指期大波段反轉預警系統

5 層評分：**趨勢 + 乖離 + 價量 + 市場廣度 + 外部市場**。  
前端是 **Vue 3**，計算在 **Python / FastAPI**。

## 啟動（Vue 畫面）

開兩個終端機。

**1. 後端 API**

```bash
cd /Users/jiangziqi/Desktop/stock_Kbar
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

**2. Vue 3 前端**

```bash
cd /Users/jiangziqi/Desktop/stock_Kbar/frontend
npm install
npm run dev
```

瀏覽器開啟 [http://localhost:5173](http://localhost:5173)

## 頁面

| 路由 | 內容 |
|------|------|
| `/` | 轉折分數總覽、訊號燈、減碼建議 |
| `/trend` | 20/60/120/240MA 與乖離 |
| `/momentum` | 價量、MACD、KD |
| `/breadth` | 台指期 vs 上漲／下跌家數 |
| `/external` | vs Nasdaq、SOX、KOSPI、三星、海力士 |
| `/monthly` | 即時價 vs 月K 乖離（含夜盤） |

## 舊版 Streamlit（可選）

```bash
streamlit run app.py
```
