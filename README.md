# TX Risk Exposure

台指期（TX）**Risk Score → Recommended Exposure** 儀表板。  
前端 **Vue 3**，計算在 **Python / FastAPI**（含籌碼／法人硬上限）。

Repo：https://github.com/ai410320/tx-risk-exposure

## 本機啟動

開兩個終端機。

**1. 後端 API**

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

**2. Vue 前端**

```bash
cd frontend
npm install
npm run dev
```

瀏覽器開 [http://localhost:5173](http://localhost:5173)

選填 API key：複製 `.env.example` 為 `.env`，填入 `FINMIND_TOKEN`。

## 公開給別人用（線上網址）

**GitHub Pages 不行**——它只能放靜態網頁，跑不了這個專案的 Python API。

建議用 **Render**（免費方案會給類似 `https://tx-risk-exposure.onrender.com` 的網址）：

1. 註冊 [https://render.com](https://render.com)，用 GitHub 登入
2. **New → Blueprint**，選這個 repo `ai410320/tx-risk-exposure`
3. 套用 `render.yaml`，Deploy
4.（選填）在 Environment 填 `FINMIND_TOKEN`

部署完成後，把 Render 給的網址傳給別人即可。免費方案久沒人造訪可能會休眠，第一次開啟會慢一點。

本機也可一次打包跑：

```bash
docker build -t tx-risk-exposure .
docker run --rm -p 8000:8000 -e CORS_ORIGINS='*' tx-risk-exposure
```

然後開 [http://localhost:8000](http://localhost:8000)

## 頁面

| 路由 | 內容 |
|------|------|
| `/` | Risk／Exposure 總覽 |
| `/chip` | 籌碼／法人 |
| `/outlook` | 走勢判讀 |
| `/trend` | 均線與乖離 |
| `/momentum` | 價量、MACD、KD |
| `/breadth` | 市場廣度 |
| `/external` | 外部市場 |
| `/monthly` | 月K 乖離 |

## 舊版 Streamlit（可選）

```bash
streamlit run app.py
```
