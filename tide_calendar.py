#!/usr/bin/env python3
"""
台灣潮汐日曆產生器
從中央氣象署 API 取得潮汐預報，轉換為 iCal 格式供 iPhone 訂閱

API: F-A0021-001 (潮汐預報-未來 1 個月潮汐預報)
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from zoneinfo import ZoneInfo

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

# 載入潮汐觀測站對照表 (站名 -> LocationId)
def _load_tide_stations() -> dict[str, str]:
    """從 location.json 載入潮汐站對照表"""
    location_file = Path(__file__).parent / "location.json"
    try:
        with open(location_file, "r", encoding="utf-8") as f:
            locations = json.load(f)
        return {loc["LocationName"]: loc["LocationId"] for loc in locations}
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"無法載入 location.json: {e}，使用空字典")
        return {}

TIDE_STATIONS = _load_tide_stations()


class TideCalendarGenerator:
    """潮汐日曆產生器"""
    
    API_BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
    DATA_ID = "F-A0021-001"
    
    def __init__(self, api_key: str, station_name: str = "基隆市中正區"):
        """
        初始化

        Args:
            api_key: 中央氣象署 API 授權碼
            station_name: 潮汐站名稱
        """
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
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("success") != "true":
                raise Exception(f"API 回應失敗: {data}")
            
            logger.info("潮汐資料取得成功")
            return data
            
        except requests.RequestException as e:
            logger.error(f"API 請求失敗: {e}")
            raise
    
    def parse_tide_events(self, api_data: dict) -> list[dict]:
        """
        解析 API 資料，提取潮汐事件
        
        Returns:
            list of dict: [{"datetime": datetime, "type": "滿潮/乾潮", "height": float}, ...]
        """
        events = []
        
        try:
            records = api_data.get("records", {})
            # API 回傳的 key 是 TideForecasts（複數）
            tide_forecasts = records.get("TideForecasts", records.get("TideForecast", []))

            for forecast in tide_forecasts:
                # Location 包含所有資料
                location = forecast.get("Location", {})
                location_name = location.get("LocationName", "")

                if location_name != self.station_name:
                    continue

                # TimePeriods 在 Location 裡面
                time_periods = location.get("TimePeriods", {})
                daily_list = time_periods.get("Daily", [])

                for daily in daily_list:
                    lunar_date = daily.get("LunarDate", "")
                    # 潮汐資料在 Time 陣列裡
                    time_list = daily.get("Time", [])

                    for tide_info in time_list:
                        tide_type = tide_info.get("Tide", "")
                        # ISO 格式的時間
                        date_time_str = tide_info.get("DateTime", "")
                        tide_height = tide_info.get("TideHeights", {})

                        # 取得潮位高度
                        height_above_local = tide_height.get("AboveLocalMSL", "")
                        height_above_twvd = tide_height.get("AboveTWVD", "")
                        height_above_chart = tide_height.get("AboveChartDatum", "")
                        height = height_above_local or height_above_twvd or height_above_chart

                        if date_time_str:
                            try:
                                # 解析 ISO 格式: 2025-12-29T05:01:00+08:00
                                dt = datetime.fromisoformat(date_time_str)

                                events.append({
                                    "datetime": dt,
                                    "type": tide_type,
                                    "height": height,
                                    "lunar_day": lunar_date,
                                })
                            except ValueError as e:
                                logger.warning(f"日期解析失敗: {date_time_str}, {e}")
            
            logger.info(f"解析到 {len(events)} 個潮汐事件")
            return events
            
        except (KeyError, TypeError) as e:
            logger.error(f"資料解析錯誤: {e}")
            raise
    
    def create_ical(self, events: list[dict], days_ahead: int = 30) -> Calendar:
        """
        建立 iCal 日曆
        
        Args:
            events: 潮汐事件列表
            days_ahead: 包含未來幾天的資料
            
        Returns:
            Calendar: icalendar.Calendar 物件
        """
        cal = Calendar()
        cal.add("prodid", f"-//台灣潮汐日曆//{self.station_name}//TW")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        cal.add("method", "PUBLISH")
        cal.add("x-wr-calname", f"🌊 {self.station_name}潮汐")
        cal.add("x-wr-timezone", "Asia/Taipei")
        
        # 過濾未來 N 天的事件
        now = datetime.now(TW_TZ)
        cutoff = now + timedelta(days=days_ahead)
        
        for event_data in events:
            event_dt = event_data["datetime"]
            
            # 只包含未來的事件
            if event_dt < now or event_dt > cutoff:
                continue
            
            event = Event()
            
            tide_type = event_data["type"]
            height = event_data["height"]
            lunar_day = event_data.get("lunar_day", "")
            
            # 設定事件標題（加上簡化地點名稱）
            emoji = "🔺" if tide_type == "滿潮" else "🔻"
            # 簡化站點名稱（移除「縣市」等後綴，保留關鍵資訊）
            short_name = self.station_name.replace("市", "").replace("縣", "").replace("區", "").replace("鄉", "").replace("鎮", "")
            title = f"{short_name} {emoji}{tide_type}"
            if height:
                title += f" {height}cm"
            
            event.add("summary", title)
            event.add("dtstart", event_dt)
            event.add("dtend", event_dt + timedelta(minutes=30))
            
            # 設定描述
            description = f"站點: {self.station_name}\n"
            description += f"類型: {tide_type}\n"
            if height:
                description += f"潮位: {height} cm (平均海平面基準)\n"
            if lunar_day:
                description += f"農曆: {lunar_day}"
            
            event.add("description", description)
            
            # 設定唯一識別碼
            uid = f"{event_dt.strftime('%Y%m%d%H%M')}-{tide_type}-{self.station_name}@tide.tw"
            event.add("uid", uid)
            
            # 設定時間戳記
            event.add("dtstamp", datetime.now(TW_TZ))
            
            cal.add_component(event)
        
        event_count = len([c for c in cal.walk() if c.name == "VEVENT"])
        logger.info(f"建立 {event_count} 個日曆事件")
        
        return cal
    
    def generate(self, output_path: str, days_ahead: int = 30) -> str:
        """
        產生潮汐日曆檔案
        
        Args:
            output_path: 輸出檔案路徑
            days_ahead: 包含未來幾天的資料
            
        Returns:
            str: 輸出檔案路徑
        """
        # 取得資料
        api_data = self.fetch_tide_data()
        
        # 解析事件
        events = self.parse_tide_events(api_data)
        
        # 建立日曆
        cal = self.create_ical(events, days_ahead)
        
        # 儲存檔案
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(cal.to_ical())
        
        logger.info(f"日曆已儲存至: {output_path}")
        return str(output_path)


def main():
    """主程式"""
    import argparse
    
    parser = argparse.ArgumentParser(description="台灣潮汐日曆產生器")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("CWA_API_KEY"),
        help="中央氣象署 API 授權碼 (或設定環境變數 CWA_API_KEY)"
    )
    parser.add_argument(
        "--station",
        default="基隆市中正區",
        help="潮汐站名稱，使用 --list-stations 查看所有可用站點"
    )
    parser.add_argument(
        "--output",
        default="./output/tide.ics",
        help="輸出檔案路徑"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="包含未來幾天的資料 (預設: 30)"
    )
    parser.add_argument(
        "--list-stations",
        action="store_true",
        help="列出所有可用的潮汐站"
    )
    
    args = parser.parse_args()
    
    if args.list_stations:
        print("可用的潮汐觀測站:")
        for name in TIDE_STATIONS.keys():
            print(f"  - {name}")
        return
    
    if not args.api_key:
        print("錯誤: 請提供 API 授權碼")
        print("可透過 --api-key 參數或設定環境變數 CWA_API_KEY")
        print("申請授權碼: https://opendata.cwa.gov.tw/user/authkey")
        return 1
    
    try:
        generator = TideCalendarGenerator(
            api_key=args.api_key,
            station_name=args.station
        )
        generator.generate(args.output, args.days)
        print(f"\n✅ 成功產生潮汐日曆: {args.output}")
        
    except Exception as e:
        logger.error(f"產生失敗: {e}")
        return 1


if __name__ == "__main__":
    exit(main() or 0)
