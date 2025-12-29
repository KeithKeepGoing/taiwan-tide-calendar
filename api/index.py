#!/usr/bin/env python3
"""
台灣潮汐日曆 - Vercel Serverless 版本
移除快取機制，每次請求即時產生日曆
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import Flask, Response, request, jsonify, render_template_string
from urllib.parse import unquote
import requests
from icalendar import Calendar, Event

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 台灣時區
TW_TZ = ZoneInfo("Asia/Taipei")

# 載入潮汐觀測站對照表
def _load_tide_stations() -> dict[str, str]:
    """從 location.json 載入潮汐站對照表"""
    # Vercel 部署時，檔案路徑相對於專案根目錄
    possible_paths = [
        Path(__file__).parent.parent / "location.json",
        Path(__file__).parent / "location.json",
        Path("location.json"),
    ]

    for location_file in possible_paths:
        try:
            with open(location_file, "r", encoding="utf-8") as f:
                locations = json.load(f)
            return {loc["LocationName"]: loc["LocationId"] for loc in locations}
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            continue

    logger.warning("無法載入 location.json，使用空字典")
    return {}

TIDE_STATIONS = _load_tide_stations()


class TideCalendarGenerator:
    """潮汐日曆產生器"""

    API_BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
    DATA_ID = "F-A0021-001"

    def __init__(self, api_key: str, station_name: str = "基隆市中正區"):
        self.api_key = api_key
        self.station_name = station_name

        if station_name not in TIDE_STATIONS:
            available = ", ".join(list(TIDE_STATIONS.keys())[:10]) + "..."
            raise ValueError(f"不支援的潮汐站: {station_name}\n可用站點: {available}")

        self.location_id = TIDE_STATIONS[station_name]

    def fetch_tide_data(self) -> dict:
        """從氣象署 API 取得潮汐資料"""
        url = f"{self.API_BASE_URL}/{self.DATA_ID}"
        params = {
            "Authorization": self.api_key,
            "format": "JSON",
            "LocationId": self.location_id,
        }

        logger.info(f"正在取得 {self.station_name} 潮汐資料...")

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("success") != "true":
            raise Exception(f"API 回應失敗: {data}")

        return data

    def parse_tide_events(self, api_data: dict) -> list[dict]:
        """解析 API 資料，提取潮汐事件"""
        events = []

        records = api_data.get("records", {})
        tide_forecasts = records.get("TideForecast", [])

        logger.info(f"API 回傳 {len(tide_forecasts)} 個預報")

        for forecast in tide_forecasts:
            location = forecast.get("Location", {})
            location_name = location.get("LocationName", "")

            logger.info(f"比較站名: API='{location_name}' vs 輸入='{self.station_name}'")

            # 直接使用第一個預報（因為已經用 LocationId 過濾過了）
            if not tide_forecasts:
                continue

            time_periods = forecast.get("TimePeriods", {})
            daily_list = time_periods.get("Daily", [])

            logger.info(f"找到 {len(daily_list)} 天的資料")

            for daily in daily_list:
                date_str = daily.get("Date", "")
                lunar_day = daily.get("LunarDay", "")
                tide_range = daily.get("TideRange", [])

                for tide_info in tide_range:
                    tide_type = tide_info.get("Tide", "")
                    tide_time_str = tide_info.get("TideTime", "")
                    tide_height = tide_info.get("TideHeights", {})

                    height_above_local = tide_height.get("AboveLocalMSL", "")
                    height_above_twvd = tide_height.get("AboveTWVD", "")
                    height_above_chart = tide_height.get("AboveChartDatum", "")
                    height = height_above_local or height_above_twvd or height_above_chart

                    if tide_time_str:
                        try:
                            dt_str = f"{date_str} {tide_time_str}"
                            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                            dt = dt.replace(tzinfo=TW_TZ)

                            events.append({
                                "datetime": dt,
                                "type": tide_type,
                                "height": height,
                                "lunar_day": lunar_day,
                            })
                        except ValueError as e:
                            logger.warning(f"日期解析失敗: {dt_str}, {e}")

        logger.info(f"共解析 {len(events)} 個潮汐事件")
        return events

    def create_ical(self, events: list[dict], days_ahead: int = 30) -> Calendar:
        """建立 iCal 日曆"""
        cal = Calendar()
        cal.add("prodid", f"-//台灣潮汐日曆//{self.station_name}//TW")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        cal.add("method", "PUBLISH")
        cal.add("x-wr-calname", f"🌊 {self.station_name}潮汐")
        cal.add("x-wr-timezone", "Asia/Taipei")

        now = datetime.now(TW_TZ)
        cutoff = now + timedelta(days=days_ahead)
        # 往前推 1 天，避免時區問題導致今天的事件被過濾掉
        start = now - timedelta(days=1)

        logger.info(f"過濾時間範圍: {start} ~ {cutoff}")
        event_count = 0

        for event_data in events:
            event_dt = event_data["datetime"]

            if event_dt < start or event_dt > cutoff:
                continue

            event_count += 1

            event = Event()

            tide_type = event_data["type"]
            height = event_data["height"]
            lunar_day = event_data.get("lunar_day", "")

            emoji = "🔺" if tide_type == "滿潮" else "🔻"
            title = f"{emoji} {tide_type}"
            if height:
                title += f" {height}cm"

            event.add("summary", title)
            event.add("dtstart", event_dt)
            event.add("dtend", event_dt + timedelta(minutes=30))

            description = f"站點: {self.station_name}\n"
            description += f"類型: {tide_type}\n"
            if height:
                description += f"潮位: {height} cm (平均海平面基準)\n"
            if lunar_day:
                description += f"農曆: {lunar_day}"

            event.add("description", description)

            uid = f"{event_dt.strftime('%Y%m%d%H%M')}-{tide_type}-{self.station_name}@tide.tw"
            event.add("uid", uid)
            event.add("dtstamp", datetime.now(TW_TZ))

            cal.add_component(event)

        logger.info(f"加入 {event_count} 個事件到日曆")
        return cal

    def generate_ical_bytes(self, days_ahead: int = 30) -> bytes:
        """產生 iCal 日曆並回傳 bytes"""
        api_data = self.fetch_tide_data()
        events = self.parse_tide_events(api_data)
        cal = self.create_ical(events, days_ahead)
        return cal.to_ical()


# Flask App
app = Flask(__name__)

API_KEY = os.environ.get("CWA_API_KEY", "")

# HTML 首頁模板
INDEX_HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌊 台灣潮汐日曆</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 { color: #333; margin-bottom: 10px; }
        .subtitle { color: #666; margin-bottom: 30px; }
        .station-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 12px;
            margin-top: 20px;
        }
        .station-btn {
            display: block;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 10px;
            text-decoration: none;
            color: #333;
            text-align: center;
            transition: all 0.2s;
            border: 2px solid transparent;
        }
        .station-btn:hover {
            background: #e8f4fd;
            border-color: #667eea;
            transform: translateY(-2px);
        }
        .instructions {
            background: #f0f4ff;
            border-radius: 10px;
            padding: 20px;
            margin-top: 30px;
        }
        .instructions h3 { margin-top: 0; color: #4a5568; }
        .instructions ol { padding-left: 20px; }
        .instructions li { margin-bottom: 8px; color: #666; }
        code {
            background: #e2e8f0;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #888;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌊 台灣潮汐日曆</h1>
        <p class="subtitle">自動更新的潮汐預報日曆，支援 iPhone / Google Calendar 訂閱</p>

        <h2>選擇觀測站</h2>
        <p>點擊下方站點即可訂閱該站的潮汐日曆：</p>

        <div class="station-grid">
            {% for station in stations %}
            <a href="webcal://{{ host }}/tide/{{ station }}.ics" class="station-btn">{{ station }}</a>
            {% endfor %}
        </div>

        <div class="instructions">
            <h3>📱 iPhone 訂閱方式</h3>
            <ol>
                <li>點擊上方任一站點</li>
                <li>系統會自動開啟行事曆 App 並詢問是否訂閱</li>
                <li>點擊「訂閱」即可完成</li>
            </ol>

            <h3>💻 手動訂閱 URL</h3>
            <p>iPhone/Mac 訂閱：<code>webcal://{{ host }}/tide/站名.ics</code></p>
            <p>Google Calendar：<code>{{ base_url }}/tide/站名.ics</code></p>
            <p>可選參數：<code>?days=14</code> (預設 30 天)</p>
        </div>

        <div class="footer">
            <p>資料來源：中央氣象署開放資料平台</p>
            <p>每次請求即時取得最新資料</p>
        </div>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    """首頁"""
    base_url = request.host_url.rstrip("/")
    host = request.host  # 不含 protocol，用於 webcal://
    return render_template_string(
        INDEX_HTML,
        stations=TIDE_STATIONS.keys(),
        base_url=base_url,
        host=host,
    )


@app.route("/tide/<station>.ics")
def tide_calendar(station: str):
    """提供潮汐日曆 iCal 檔案（即時產生，無快取）"""
    # 解碼 URL 編碼的站名
    station = unquote(station)

    if not API_KEY:
        return jsonify({"error": "API key not configured"}), 500

    if station not in TIDE_STATIONS:
        return jsonify({
            "error": f"Unknown station: {station}",
            "available_stations": list(TIDE_STATIONS.keys())
        }), 404

    days = request.args.get("days", 30, type=int)
    days = min(max(days, 7), 30)

    try:
        generator = TideCalendarGenerator(API_KEY, station)
        ical_data = generator.generate_ical_bytes(days)

        filename_encoded = quote(f"{station}_tide.ics")

        return Response(
            ical_data,
            mimetype="text/calendar",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}",
                "Cache-Control": "public, max-age=3600",  # 瀏覽器快取 1 小時
            }
        )

    except Exception as e:
        logger.error(f"Error generating calendar: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/stations")
def list_stations():
    """列出所有可用的潮汐站"""
    return jsonify({
        "stations": list(TIDE_STATIONS.keys()),
        "total": len(TIDE_STATIONS)
    })


@app.route("/health")
def health():
    """健康檢查"""
    return jsonify({
        "status": "ok",
        "api_configured": bool(API_KEY),
        "stations_loaded": len(TIDE_STATIONS),
    })
