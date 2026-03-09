from datetime import datetime
from typing import Dict
import requests
from logger import SimpleLogger
from result_enum import Result
from database import DatabaseManager
from config import Config


def checkDataIsFloat(data, valueName, logger: SimpleLogger):
    try:
        float(data)
        return True
    except ValueError:
        logger.log(
            f"value {data} is not of type float -> continue anyway ({valueName})")
        return False


class SolarLiveData:
    def __init__(self, logger: SimpleLogger, config: Config):
        self.logger = logger
        self.config = config

    def uploadToServer(self, livedata):
        try:
            res = requests.post(self.config.SOLAR_UPLOAD_URL, json=livedata,
                                headers={'Content-Type': 'application/json', 'apikey': self.config.UPLOAD_API_KEY}, timeout=2)
            if res.status_code == 503:
                self.logger.log("Solar live data upload => invalid API key")
        except:
            self.logger.log("Could not upload live data")
            return

    def get_live_data(self):
        try:
            res = requests.get(self.config.OPENDTU_API_URL, timeout=2)
            if res.status_code != 200:
                self.logger.log("OpenDTU access error " + res.status_code)
            return (Result.SUCCESS if res.status_code == 200 else Result.NO_DATA, res.json())
        except:
            self.logger.log("OpenDTU not reachable")
            return (Result.NO_DATA, "")


class HistoryData:
    def __init__(self, logger: SimpleLogger, db_manager: DatabaseManager, config: Config):
        self.logger = logger
        self.max_value_temp = 0
        self.max_value_day = 0
        self.overall = 0
        self.today = 0
        self.highest_time_temp = datetime.now().strftime("%H:%M:%S")

        self.highest_time = datetime.now().strftime("%H:%M:%S")
        self.current_date = datetime.now().strftime("%d.%m.%Y")
        self.current_day = datetime.now().strftime("%d")
        self.current_power = ""
        self.current_temp = ""
        self.db = db_manager
        self.config = config

        # Try to restore today's values from DB
        try:
            # Convert DD.MM.YYYY to YYYY-MM-DD
            parts = self.current_date.split('.')
            date_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"

            row = self.db.get_daily_record(date_iso)
            if row:
                self.overall = row['total_solar_kwh']
                self.today = row['daily_solar_wh']
                self.max_value_day = row['peak_solar_watt']
                self.highest_time = row['peak_time']
                self.max_value_temp = row['peak_temp_inverter']
                self.highest_time_temp = row['peak_temp_time']
                self.logger.log(
                    f"Restored daily values: max_day={self.max_value_day}W, time={self.highest_time}, max_temp={self.max_value_temp}C, time={self.highest_time_temp}")
        except Exception as e:
            self.logger.log(f"Could not load previous data: {e}")

    def uploadHistoryData(self) -> Result:
        try:
            with open(self.db.db_path, "rb") as f:
                res = requests.post(self.config.SYNC_DB_URL, files={'file': f},
                                    headers={'apikey': self.config.UPLOAD_API_KEY}, timeout=10)

            if res.status_code == 503:
                self.logger.log("History Data => Invalid API Key")
                return Result.FAILED
            elif res.status_code == 200:
                self.logger.log("History Data => Database synced successfully")
                return Result.SUCCESS
            else:
                self.logger.log(
                    f"History Data => Upload failed {res.status_code}")
                return Result.FAILED
        except Exception as e:
            self.logger.log(f"Could not upload database: {e}")
            return Result.FAILED

    def check_next_day(self) -> bool:
        # next day:
        day = datetime.now().strftime("%d")
        if self.current_day != day:
            self.current_day = day
            self.max_value_day = 0
            self.today = 0
            self.max_value_temp = 0
            return True
        return False

    def make_data(self, livedata) -> Result:
        if len(livedata) == 0:
            self.logger.log("Could not get solar live data")
            return Result.FAILED

        try:
            self.current_power = round(
                livedata["inverters"][0]["AC"]["0"]["Power DC"]["v"], 1)
            self.current_temp = round(
                livedata['inverters'][0]['INV']['0']['Temperature']['v'], 0)
            self.overall = round(livedata['total']['YieldTotal']['v'], 1)
            self.today = round(livedata['total']['YieldDay']['v'], 0)
            return Result.SUCCESS
        except:
            return Result.FAILED

    def make_peak_values(self):
        # only when the value is an actual float -> current Power
        if checkDataIsFloat(self.current_power, "Aktueller Ertrag", self.logger):
            cur_pwr = float(self.current_power)
            if cur_pwr > self.max_value_day:
                self.max_value_day = cur_pwr
                self.highest_time = datetime.now().strftime("%H:%M:%S")

        # only when the value is an actual float -> current Temperature
        if checkDataIsFloat(self.current_temp, "Aktuelle Temperatur", self.logger):
            cur_tmp = float(self.current_temp)
            if cur_tmp > self.max_value_temp:
                self.max_value_temp = cur_tmp
                self.highest_time_temp = datetime.now().strftime("%H:%M:%S")

    def save_to_disk(self, energy: Dict):
        self.current_date = datetime.now().strftime("%d.%m.%Y")

        # Save to DB
        try:
            # Convert DD.MM.YYYY to YYYY-MM-DD
            parts = self.current_date.split('.')
            date_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"

            # Save solar part
            self.db.save_daily_solar(
                date_iso,
                self.overall,
                self.today,
                self.max_value_day,
                self.highest_time,
                self.max_value_temp,
                self.highest_time_temp
            )

            # Save power part
            self.db.save_daily_power(
                date_iso,
                energy['self_used_wh'],
                energy['exported_wh'],
                energy['consumed_wh'],
                energy['self_consumption_ratio'],
                energy['autarky_ratio']
            )

            self.logger.log(f"Saved daily data to DB: {self.current_date}")

        except Exception as e:
            self.logger.log(f"History Data => Error writing to DB: {e}")
