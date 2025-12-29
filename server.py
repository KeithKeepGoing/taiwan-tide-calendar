#!/usr/bin/env python3
"""
台灣潮汐日曆 Web 服務
提供 iCal 訂閱 URL 供 iPhone/Google Calendar 等訂閱

使用方式:
    python server.py

訂閱 URL 範例:
    http://your-server:5000/tide/基隆.ics
    http://your-server:5000/tide/高雄港.ics?days=14
"""

import os
import logging
from urllib.parse import quote

from flask import Flask, Response, request, jsonify, render_template_string
from dotenv import load_dotenv

from tide_calendar import TideCalendarGenerator, TIDE_STATIONS

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 設定
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
            <a href="/tide/{{ station }}.ics" class="station-btn">{{ station }}</a>
            {% endfor %}
        </div>
        
        <div class="instructions">
            <h3>📱 iPhone 訂閱方式</h3>
            <ol>
                <li>點擊上方任一站點</li>
                <li>Safari 會詢問是否訂閱日曆，選擇「訂閱」</li>
                <li>開啟「行事曆」App 即可看到潮汐資訊</li>
            </ol>
            
            <h3>💻 手動訂閱 URL</h3>
            <p>訂閱格式：<code>{{ base_url }}/tide/站名.ics</code></p>
            <p>例如：<code>{{ base_url }}/tide/基隆.ics</code></p>
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
    return render_template_string(
        INDEX_HTML,
        stations=TIDE_STATIONS.keys(),
        base_url=base_url,
    )


@app.route("/tide/<station>.ics")
def tide_calendar(station: str):
    """
    提供潮汐日曆 iCal 檔案（即時產生，無快取）

    Args:
        station: 潮汐站名稱
    """
    if not API_KEY:
        return jsonify({"error": "API key not configured"}), 500

    if station not in TIDE_STATIONS:
        return jsonify({
            "error": f"Unknown station: {station}",
            "available_stations": list(TIDE_STATIONS.keys())
        }), 404

    days = request.args.get("days", 30, type=int)
    days = min(max(days, 7), 30)  # 限制 7-30 天

    try:
        logger.info(f"產生日曆: {station}")
        generator = TideCalendarGenerator(API_KEY, station)

        # 即時產生 iCal
        api_data = generator.fetch_tide_data()
        events = generator.parse_tide_events(api_data)
        cal = generator.create_ical(events, days)
        ical_data = cal.to_ical()

        # 使用 RFC 5987 編碼處理非 ASCII 檔名
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    
    if not API_KEY:
        logger.warning("⚠️  CWA_API_KEY 未設定，請設定環境變數")
        logger.warning("申請授權碼: https://opendata.cwa.gov.tw/user/authkey")
    
    logger.info(f"🌊 台灣潮汐日曆服務啟動中...")
    logger.info(f"📍 http://localhost:{port}")
    
    app.run(host="0.0.0.0", port=port, debug=debug)
