import time
from datetime import datetime
from logger import SimpleLogger
from power_solar_usage import PowerSolarUsage
from result_enum import Result
from shelly_power_data import ShellyPowerData
from solar_data import SolarLiveData, HistoryData
from daily_data_processor import DailyDataProcessor
from config import Config
from database import DatabaseManager

config = Config()
logger = SimpleLogger(config.LOG_FILE)
dbManager = DatabaseManager(config.DATABASE_PATH)
daily_data_processor = DailyDataProcessor(config)
live_solar_uploader = SolarLiveData(logger, config)
power_data = ShellyPowerData(logger, config)
history_solar_manager = HistoryData(logger, dbManager, config)
power_solar_usage = PowerSolarUsage(logger, daily_data_processor, config)

current_solar = 0
current_power = 0
solar_history_counter = 0

while True:
    currenthour = int(datetime.now().strftime("%H"))

    shelly_data, shelly_result = power_data.get_shelly_data()
    if shelly_result == Result.SUCCESS:
        power_data.post_shelly_data(shelly_data)
        current_power = shelly_data["total_power"]

    # solar history data:
    if history_solar_manager.check_next_day():
        power_solar_usage.new_day()

    # send solar only at day
    if config.UPLOAD_24_7 or currenthour <= 23 and currenthour >= 5:
        live_solar_result, live_solar_data = live_solar_uploader.get_live_data()
        if live_solar_result == Result.SUCCESS:
            live_solar_uploader.uploadToServer(live_solar_data)
            current_solar = live_solar_data["inverters"][0]["AC"]["0"]["Power DC"]["v"]

            if history_solar_manager.make_data(live_solar_data) == Result.SUCCESS:
                history_solar_manager.make_peak_values()
                solar_history_counter += 1

                if solar_history_counter > 30:
                    solar_history_counter = 0
                    # only every 5 minutes:
                    energy = power_solar_usage.calculate_energy_stats()
                    history_solar_manager.save_to_disk(energy)
                    history_solar_manager.uploadHistoryData()
        else:
            current_solar = 0
    else:
        current_solar = 0

    power_solar_usage.store(current_solar, current_power)

    time.sleep(10)
