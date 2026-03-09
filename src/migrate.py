# only for the migration from my old data to the new database version:
# can be ignored

from database import DatabaseManager
import os
import json
import sqlite3
import sys

sys.path.append(os.path.dirname(__file__))


def migrate_solar_history_data(db):
    # 2. Migrate solar_history.json
    history_path = os.path.join(os.path.dirname(
        os.path.dirname(__file__)), 'solar_history.json')
    if os.path.exists(history_path):
        print(f"Reading {history_path}...")
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                input_str = f.read()

            data = json.loads(input_str)

            for date_key, day_data in data.items():
                # Date format in json key is usually YYYY-MM-DD
                # Verify date_key format
                date_str = date_key

                # Update phases
                # Direct DB access for custom stuff if needed, but methods are better
                conn = db._get_connection()

                if 'morning_phase' in day_data:
                    mp = day_data['morning_phase']
                    if 'sum_wh' in mp and 'time' in mp:
                        check = conn.execute(
                            "SELECT 1 FROM daily_solar WHERE date=?", (date_str,)).fetchone()
                        if not check:
                            db.save_daily_solar(
                                date_str, 0, 0, 0, "00:00:00", 0, "00:00:00")

                        db.update_daily_power_phase(
                            date_str, 'morning', mp['sum_wh'], mp['time'])

                if 'evening_phase' in day_data:
                    ep = day_data['evening_phase']
                    if 'sum_wh' in ep and 'time' in ep:
                        check = conn.execute(
                            "SELECT 1 FROM daily_solar WHERE date=?", (date_str,)).fetchone()
                        if not check:
                            db.save_daily_solar(
                                date_str, 0, 0, 0, "00:00:00", 0, "00:00:00")

                        db.update_daily_power_phase(
                            date_str, 'evening', ep['sum_wh'], ep['time'])

                if 'history_10min' in day_data:
                    # Clear existing history for this day to avoid duplicates if re-run
                    db.clear_intraday_history(date_str)

                    hist_list = day_data['history_10min']
                    for h in hist_list:
                        time_val = h.get('t')
                        solar_val = h.get('s', 0.0)
                        grid_val = h.get('g', 0.0)

                        # Ensure parent exists
                        check = conn.execute(
                            "SELECT 1 FROM daily_solar WHERE date=?", (date_str,)).fetchone()
                        if not check:
                            db.save_daily_solar(
                                date_str, 0, 0, 0, "00:00:00", 0, "00:00:00")

                        db.save_intraday_record(
                            date_str, time_val, solar_val, grid_val)

                conn.close()

        except Exception as e:
            print(f"Error parsing json: {e}")


def migrate_all_data(db):
    # 1. Migrate alldata.txt
    alldata_path = os.path.join(os.path.dirname(
        os.path.dirname(__file__)), 'alldata.txt')
    if os.path.exists(alldata_path):
        print(f"Reading {alldata_path}...")
        with open(alldata_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        mode = "solar"  # Start with solar only
        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split('|')
            if len(parts) < 7:
                continue

            # Date format in file is DD.MM.YYYY
            try:
                date_parts = parts[0].split('.')
                date_str = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
            except:
                print(f"Skipping line due to date format: {line}")
                continue

            if len(parts) == 7:
                # Date|Total Solar|Daily Solar| Peak Solar| Peak Time| Peak Temp Inverter| Peak temp time|
                # 05.03.2023|1.581|1581|678.4|14:51:04|42.1|15:06:11
                try:
                    total_solar = float(parts[1])
                    daily_solar = float(parts[2])
                    peak_solar = float(parts[3])
                    peak_time = parts[4]
                    peak_temp = float(parts[5])
                    peak_temp_time = parts[6]

                    db.save_daily_solar(
                        date_str, total_solar, daily_solar, peak_solar, peak_time, peak_temp, peak_temp_time)
                except ValueError as e:
                    print(f"Error parsing solar line: {line} - {e}")

            elif len(parts) == 12:
                # Date|Total Solar(kWh)|Daily Solar(Watt)| Peak Solar(Watt)| Peak Time| Peak Temp Inverter| Peak temp time|Solar Used in Home(Watt)|Solar Exported to Grid(Watt)|Total Power Consumed On Day (Watt)|Self Used Percent|Autarky Percent
                try:
                    # First 7 are same as solar, update them just in case (or ensure record exists)
                    total_solar = float(parts[1])
                    daily_solar = float(parts[2])
                    peak_solar = float(parts[3])
                    peak_time = parts[4]
                    peak_temp = float(parts[5])
                    peak_temp_time = parts[6]

                    db.save_daily_solar(
                        date_str, total_solar, daily_solar, peak_solar, peak_time, peak_temp, peak_temp_time)

                    # Remaining are power
                    if len(parts) >= 12:
                        solar_used = float(parts[7])
                        exported = float(parts[8])
                        consumed = float(parts[9])
                        self_used = float(parts[10])
                        autarky = float(parts[11])

                        db.save_daily_power(
                            date_str, solar_used, exported, consumed, self_used, autarky)
                except ValueError as e:
                    print(f"Error parsing power line: {line} - {e}")


def migrate():
    print("Starting migration...")
    db = DatabaseManager()

    migrate_all_data(db)

    migrate_solar_history_data(db)

    print("Migration complete.")


if __name__ == "__main__":
    migrate()
