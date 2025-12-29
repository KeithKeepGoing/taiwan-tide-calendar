# Changelog

所有重要的變更都會記錄在此檔案。

格式基於 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)，
版本號遵循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## [1.1.0] - 2025-12-29

### 新增
- 日曆事件標題加入地點名稱，方便同時訂閱多個站點時識別
  - 範例：`基隆中正 🔻乾潮 -171cm`
  - 自動簡化站名（移除縣市區鄉鎮）

### 修復
- 修正 API 資料結構解析，正確處理 `TideForecasts` → `Location` → `TimePeriods` → `Daily` → `Time` 路徑
- 修正 API key 名稱為 `TideForecasts`（複數形式）
- 修正 URL 編碼問題，正確解碼中文站名
- 使用 `webcal://` 協定，修復 iPhone Safari 無法訂閱的問題

### 變更
- 移除 debug 端點（僅供開發除錯用）

### 技術細節
- **修改檔案**: `api/index.py`, `tide_calendar.py`, `server.py`, `README.md`
- **API 結構**: 潮汐資料位於 `Location.TimePeriods.Daily[].Time[]`，非原本預期的 `TideRange`

## [1.0.0] - 2025-12-29

### 新增
- 從中央氣象署 API (F-A0021-001) 取得潮汐預報
- 轉換為 iCal 格式供 iPhone/Google Calendar 訂閱
- 支援全台 263 個潮汐站點（縣市、海水浴場、漁港、海釣、潛點、衝浪點）
- Flask Web 服務，提供網頁界面選擇站點
- 支援 Docker 部署
- 支援 Vercel Serverless 部署
- 命令列工具產生 .ics 檔案

### 技術細節
- **新增檔案**: `tide_calendar.py`, `server.py`, `api/index.py`, `location.json`, `vercel.json`, `docker-compose.yml`, `Dockerfile`, `requirements.txt`
