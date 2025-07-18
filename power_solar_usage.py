from datetime import datetime
from typing import Dict


class PowerSolarUsage:
    def __init__(self):
        self.daily_buffer = []

    def store(self, current_solar, current_power):
        self.daily_buffer.append({
            "timestamp": datetime.now(),
            "solar_w": current_solar,
            "grid_w": current_power
        })

    def new_day(self):
        self.daily_buffer = []

    def calculate_energy_stats(self, interval_seconds: int = 10) -> Dict:
        interval_hours = interval_seconds / 3600

        total_solar_wh = 0
        total_export_wh = 0
        total_self_used_wh = 0
        total_house_wh = 0

        for entry in self.daily_buffer:
            solar_w = entry["solar_w"]
            grid_w = entry["grid_w"]

            # Calculate current house power usage
            house_w = solar_w + grid_w  # grid_w may be negative (export)
            # prevent negative if weird sensor glitch
            house_w = max(house_w, 0)

            # Energy for this interval
            solar_wh = solar_w * interval_hours
            house_wh = house_w * interval_hours

            # Self-used solar (the minimum the house can consume from solar)
            used_solar_w = min(solar_w, house_w)
            used_solar_wh = used_solar_w * interval_hours

            # Exported solar (only if solar exceeds house usage)
            exported_solar_w = max(solar_w - house_w, 0)
            exported_solar_wh = exported_solar_w * interval_hours

            # Sum totals
            total_solar_wh += solar_wh
            total_self_used_wh += used_solar_wh
            total_export_wh += exported_solar_wh
            total_house_wh += house_wh

        # Ratios
        self_consumption_rate = total_self_used_wh / \
            total_solar_wh if total_solar_wh else 0
        autarky_rate = total_self_used_wh / total_house_wh if total_house_wh else 0

        return {
            # "date": datetime.now().strftime("%Y-%m-%d"),
            # "solar_wh": round(total_solar_wh, 2),
            "self_used_wh": round(total_self_used_wh, 2),
            "exported_wh": round(total_export_wh, 2),
            "consumed_wh": round(total_house_wh, 2),
            "self_consumption_ratio": round(self_consumption_rate, 4),
            "autarky_ratio": round(autarky_rate, 4)
        }
