# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

台灣潮汐日曆 - 從中央氣象署 API (F-A0021-001) 取得潮汐預報，轉換為 iCal 格式供 iPhone/Google Calendar 訂閱。

## Development Commands

```bash
# 安裝依賴
pip install -r requirements.txt

# 本地開發 (Flask server)
python server.py

# 命令列產生 .ics 檔案
python tide_calendar.py --station 基隆市中正區 --output ./tide.ics

# 列出所有可用站點
python tide_calendar.py --list-stations

# Docker 部署
docker-compose up -d
```

## Architecture

```
├── api/index.py          # Vercel serverless 進入點 (獨立版本，包含完整 Flask app)
├── tide_calendar.py      # 核心模組：TideCalendarGenerator 類別 + CLI
├── server.py             # 本地 Flask server (import tide_calendar)
├── location.json         # 263 個潮汐站對照表 (LocationName → LocationId)
└── vercel.json           # Vercel 路由設定
```

### Key Components

**TideCalendarGenerator** (`tide_calendar.py`, `api/index.py`)
- `fetch_tide_data()` - 呼叫氣象署 API
- `parse_tide_events()` - 解析 API 回應結構：`records.TideForecasts[].Location.TimePeriods.Daily[].Time[]`
- `create_ical()` - 建立 iCal 日曆，事件標題格式：`{簡化地名} {emoji}{潮汐類型} {高度}cm`

**API Response Structure** (重要)
```
records.TideForecasts[] → Location → TimePeriods → Daily[] → Time[]
                                                              ├── DateTime (ISO format)
                                                              ├── Tide ("滿潮"/"乾潮")
                                                              └── TideHeights.AboveLocalMSL
```

### Deployment Modes

| 模式 | 檔案 | 特點 |
|------|------|------|
| Vercel | `api/index.py` | Serverless，每次請求即時取得資料，無快取 |
| Docker/本地 | `server.py` + `tide_calendar.py` | 可設定快取 |

## Environment Variables

- `CWA_API_KEY` - 中央氣象署 API 授權碼 (必要)
- `PORT` - 服務 port (預設 5000)

## API Endpoints

- `GET /` - 首頁 (站點選擇界面)
- `GET /tide/{station}.ics` - 取得指定站點的 iCal 日曆
- `GET /api/stations` - 列出所有站點
- `GET /health` - 健康檢查

## Notes

- iPhone 訂閱需使用 `webcal://` protocol，不是 `https://`
- URL 中的中文站名需要用 `unquote()` 解碼
- 事件標題會簡化站名（移除縣市區鄉鎮）以便多站點訂閱時識別
