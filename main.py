import time
from power import PowerData
from logger import SimpleLogger
from enum import Enum
from solar import SolarLiveData, HistoryData
from datetime import datetime


class Result(Enum):
    SUCCESS = 0
    NO_DATA = 1
    FAILED = 2


logger = SimpleLogger()
power_data = PowerData(logger)
live_solar_uploader = SolarLiveData(logger)
history_solar_manager = HistoryData(logger)


while True:
    currenthour = int(datetime.now().strftime("%H"))

    # night mode:
    if currenthour > 21 or currenthour < 5:
        logger.log(f"{datetime.now().strftime('%H:%M:%S')}: Night mode")
        # time.sleep(600)  # all 10 minutes
        continue

    shelly_data, shelly_result = power_data.get_shelly_data()
    if shelly_result == Result.SUCCESS:
        power_data.post_shelly_data()

    # solar live data:
    live_solar_result, live_solar_data = live_solar_uploader.get_live_data()
    if live_solar_result == Result.SUCCESS:
        live_solar_uploader.uploadToServer(live_solar_data)

    # solar history data:
    history_solar_manager.check_next_day()

    if history_solar_manager.make_data(live_solar_data) == Result.SUCCESS:
        history_solar_manager.make_peak_values()

        history_solar_manager.save_to_disk()
        history_solar_manager.uploadHistoryData()

    time.sleep(10)
