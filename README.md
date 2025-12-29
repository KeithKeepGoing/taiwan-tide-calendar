# 🌊 台灣潮汐日曆

從中央氣象署 API 取得潮汐預報，轉換為 iCal 格式供 iPhone / Google Calendar 訂閱。

## 功能特色

- 📅 自動產生未來 30 天潮汐日曆
- 🔄 每 6 小時自動更新
- 📱 支援 iPhone / iPad / Mac / Google Calendar 訂閱
- 🗺️ 支援全台 263 個潮汐站點（縣市、海水浴場、漁港、海釣、潛點、衝浪點）
- 🐳 Docker 一鍵部署
- ☁️ 支援 Vercel 免費部署

## 快速開始

### 1. 申請 API 授權碼

1. 前往 [中央氣象署開放資料平台](https://opendata.cwa.gov.tw/)
2. 註冊帳號並登入
3. 前往 [取得授權碼](https://opendata.cwa.gov.tw/user/authkey)
4. 點擊「取得授權碼」

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env 填入你的 API 授權碼
```

### 3. 啟動服務

#### 方式 A: Docker (推薦)

```bash
docker-compose up -d
```

#### 方式 B: 直接執行

```bash
pip install -r requirements.txt
python server.py
```

### 4. 在 iPhone 訂閱

1. 用 Safari 開啟 `http://your-server:5000`
2. 選擇想要的潮汐站
3. 點擊後選擇「訂閱」
4. 完成！潮汐資訊會自動出現在行事曆中

## 支援的潮汐站

站點資料來自 `location.json`，共 263 個站點，分類如下：

| 分類 | 範例站點 |
|------|----------|
| 縣市區域 | 基隆市中正區、新北市貢寮區、高雄市旗津區 |
| 海水浴場 | 海水浴場頭城、海水浴場墾丁、海水浴場福隆 |
| 漁港 | 漁港八斗子、漁港南方澳、漁港後壁湖 |
| 海釣點 | 海釣外木山、海釣西子灣、海釣三仙台 |
| 潛點 | 潛點龍洞灣水域B區北側、潛點後壁湖航道西側 |
| 衝浪點 | 衝浪中角沙珠灣、衝浪南灣、衝浪大灣 |
| 離島 | 澎湖縣馬公市、金門縣金城鎮、連江縣南竿鄉、臺東縣蘭嶼鄉 |

使用 `--list-stations` 查看完整站點列表。

## API 使用

### 訂閱 URL 格式

```
http://your-server:5000/tide/{站名}.ics
```

### 範例

- 基隆: `http://your-server:5000/tide/基隆市中正區.ics`
- 高雄旗津: `http://your-server:5000/tide/高雄市旗津區.ics`
- 漁港: `http://your-server:5000/tide/漁港八斗子.ics`
- 指定天數: `http://your-server:5000/tide/基隆市中正區.ics?days=14`

### API 端點

| 端點 | 說明 |
|------|------|
| `GET /` | 首頁（有網頁界面） |
| `GET /tide/{station}.ics` | 取得指定站點的潮汐日曆 |
| `GET /api/stations` | 列出所有可用站點 |
| `GET /health` | 健康檢查 |

## 命令列工具

也可以直接產生 .ics 檔案：

```bash
# 產生基隆潮汐日曆
python tide_calendar.py --station 基隆市中正區 --output ./tide.ics

# 列出所有可用站點
python tide_calendar.py --list-stations

# 指定天數
python tide_calendar.py --station 高雄市旗津區 --days 14 --output ./kaohsiung.ics

# 漁港站點
python tide_calendar.py --station 漁港八斗子 --output ./badouzi.ics
```

## 部署方式

### Vercel 部署（推薦）

免費、快速、自動 HTTPS，適合個人使用。

#### 方式 A：透過 Vercel Dashboard

1. Fork 或 Push 專案到你的 GitHub
2. 前往 [vercel.com/new](https://vercel.com/new)
3. 點擊 **Import Git Repository**
4. 選擇你的 `taiwan-tide-calendar` repository
5. 在 **Environment Variables** 新增：
   - Name: `CWA_API_KEY`
   - Value: 你的中央氣象署 API 授權碼
6. 點擊 **Deploy**
7. 部署完成後會得到 URL，如 `https://taiwan-tide-calendar.vercel.app`

#### 方式 B：透過 Vercel CLI

```bash
# 安裝 Vercel CLI
npm i -g vercel

# 登入
vercel login

# 部署（會引導你連結 GitHub）
vercel

# 設定環境變數
vercel env add CWA_API_KEY

# 正式部署
vercel --prod
```

#### Vercel 訂閱 URL 範例

```
https://your-project.vercel.app/tide/基隆市中正區.ics
https://your-project.vercel.app/tide/漁港八斗子.ics
https://your-project.vercel.app/tide/衝浪中角沙珠灣.ics?days=14
```

### VPS / NAS 部署

1. 安裝 Docker
2. 複製專案到伺服器
3. 設定環境變數
4. `docker-compose up -d`
5. 設定防火牆開放 5000 port
6. （可選）設定 Nginx 反向代理 + HTTPS

### Nginx 反向代理範例

```nginx
server {
    listen 443 ssl;
    server_name tide.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### n8n 工作流程

如果你使用 n8n，可以建立工作流程定期呼叫 API：

1. 新增 Schedule Trigger（每 6 小時）
2. 新增 HTTP Request 節點呼叫 `/tide/基隆市中正區.ics`
3. （可選）儲存到 Google Drive 或發送通知

## 日曆事件格式

每個潮汐事件包含：

- **標題**: `🔺 滿潮 123cm` 或 `🔻 乾潮 45cm`
- **時間**: 30 分鐘的事件（方便查看）
- **描述**: 站點、潮位高度、農曆日期

## 常見問題

### Q: 日曆多久更新一次？

A: Vercel 部署版本每次請求即時取得最新資料。Docker 部署版本每 6 小時更新快取。iPhone 的訂閱日曆通常每天更新 1-2 次。

### Q: 可以同時訂閱多個站點嗎？

A: 可以，每個站點是獨立的日曆訂閱。

### Q: 潮位高度是什麼基準？

A: 預設使用「當地平均海平面」基準，這是一般漁釣最常用的基準面。

### Q: iPhone 訂閱後看不到資料？

A: 
1. 確認日曆 App 中已勾選顯示該訂閱
2. 下拉重新整理
3. 等待 iPhone 自動同步（可能需要數小時）

## 授權

MIT License

## 資料來源

- [中央氣象署開放資料平台](https://opendata.cwa.gov.tw/)
- API: F-A0021-001 (潮汐預報-未來 1 個月潮汐預報)
