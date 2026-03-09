import requests
from logger import SimpleLogger
from result_enum import Result
from config import Config

REQUEST_TIMEOUT = 2


class ShellyPowerData:
    def __init__(self, logger: SimpleLogger, config: Config):
        self.logger = logger
        self.config = config

    def get_shelly_data(self):
        try:
            req = requests.get(self.config.SHELLY_API_URL,
                               timeout=REQUEST_TIMEOUT)
        except:
            self.logger.log("Shelly not reachable")
            return None, Result.NO_DATA

        if req.status_code != 200:
            self.logger.log(
                f"Could not get data from Shelly Device {req.status_code}")
            return None, Result.NO_DATA

        json_data = req.json()
        filtered_data = {
            "total_power": json_data.get("total_power"),
            "emeters": json_data.get("emeters")
        }

        if filtered_data is None or len(filtered_data) == 0:
            self.logger.log("Data from shelly is length 0 or None")
            return None, Result.NO_DATA

        return filtered_data, Result.SUCCESS

    def post_shelly_data(self, filtered_data):
        try:
            res = requests.post(self.config.POWER_UPLOAD_URL, json=filtered_data,
                                headers={'Content-Type': 'application/json',
                                         'apikey': self.config.UPLOAD_API_KEY},
                                timeout=REQUEST_TIMEOUT
                                )
        except:
            self.logger.log("Server not reachable")
            return Result.NO_DATA

        if res.status_code != 200:
            self.logger.log(f"Could not send data to server {res.status_code}")
            return Result.NO_DATA

        return Result.SUCCESS
