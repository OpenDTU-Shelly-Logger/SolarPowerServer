from datetime import datetime
from typing import Dict
import requests
import os
from logger import SimpleLogger
from result_enum import Result


def checkDataIsFloat(data, valueName, logger: SimpleLogger):
    try:
        float(data)
        return True
    except ValueError:
        logger.log(
            f"value {data} is not of type float -> continue anyway ({valueName})")
        return False


class SolarLiveData:
    def __init__(self, logger: SimpleLogger):
        self.logger = logger

    def uploadToServer(self, livedata):
        try:
            res = requests.post("https://solar.frozenassassine.de/openDTU/livedata", json=livedata,
                                headers={'Content-Type': 'application/json', 'apikey': os.getenv("WetterLiveAPIKey")}, timeout=2)
            if res.status_code == 503:
                self.logger.log("Solar live data upload => invalid API key")
        except:
            self.logger.log("Could not upload live data")
            return

    def get_live_data(self):
        try:
            res = requests.get(
                'http://192.168.10.150/api/livedata/status', timeout=2)
            if res.status_code != 200:
                self.logger.log("OpenDTU access error " + res.status_code)
            return (Result.SUCCESS if res.status_code == 200 else Result.NO_DATA, res.json())
        except:
            self.logger.log("OpenDTU not reachable")
            return (Result.NO_DATA, "")


class HistoryData:
    def __init__(self, logger: SimpleLogger):
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

        if os.path.exists("solar.txt"):
            try:
                with open("solar.txt", "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        parts = last_line.split("|")
                        if len(parts) >= 7 and parts[0] == self.current_date:
                            self.overall = float(parts[1])
                            self.today = float(parts[2])
                            self.max_value_day = float(parts[3])
                            self.highest_time = parts[4]
                            self.max_value_temp = float(parts[5])
                            self.highest_time_temp = parts[6]
                            self.logger.log(f"Restored daily values: max_day={self.max_value_day}W, time={self.highest_time}, max_temp={self.max_value_temp}C, time={self.highest_time_temp}")
            except Exception as e:
                self.logger.log(f"Could not load previous data: {e}")

    def format_data(self, energy: Dict):
        # OVERALL KWH | TODAY WH | MAXDAY WH | MAXTIME | MAXTEMP |MAXTEMPTIME
        data = f"{self.overall}|{self.today}|{self.max_value_day}|{self.highest_time}|{self.max_value_temp}|{self.highest_time_temp}|{energy['self_used_wh']}|{energy['exported_wh']}|{energy['consumed_wh']}|{energy['self_consumption_ratio']}|{energy['autarky_ratio']}"

        self.logger.log(f"History Data => {self.current_date}|{data}")
        return f"{self.current_date}|{data}"

    def uploadHistoryData(self) -> Result:
        with open("solar.txt", encoding="utf-8") as f:
            lines = f.readlines()
            historyData = "\n".join([line for line in lines if line.strip()])

        if len(historyData) == 0:
            return

        try:
            res = requests.post("https://solar.frozenassassine.de/openDTU/alldata", data=historyData,
                                headers={'Content-Type': 'application/json', 'apikey': os.getenv("WetterLiveAPIKey")}, timeout=2)
            if res.status_code == 503:
                self.logger.log("History Data => Invalid API Key")
                return Result.FAILED
            elif res.status_code == 200:
                return Result.SUCCESS
        except:
            self.logger.log("Could not upload live data")
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

        lines = []
        lastline = ""
        try:
            # check for existing entry:
            with open("solar.txt", "r", encoding="utf-8") as file:
                lines = file.readlines()
                if len(lines) > 0:
                    lastline = lines[len(lines)-1]

            if self.current_date in lastline:  # line exists:
                lines[len(lines) - 1] = f"{self.format_data(energy)}\n"
                with open("solar.txt", "w", encoding="utf-8") as file:
                    file.writelines(lines)
            else:
                with open("solar.txt", "a", encoding="utf-8") as file:
                    file.write(f"{self.format_data(energy)}\n")

        except:  # write to file error:
            self.logger.log(
                "History Data => Error occured while writing to file")
