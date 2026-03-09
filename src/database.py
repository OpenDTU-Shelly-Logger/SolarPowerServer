
import sqlite3
import os
import json
from datetime import datetime


class DatabaseManager:
    def __init__(self, db_path="solar_data.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Table 1: daily_solar (Base solar data)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_solar (
                date TEXT PRIMARY KEY,
                total_solar_kwh REAL,
                daily_solar_wh REAL,
                peak_solar_watt REAL,
                peak_time TEXT,
                peak_temp_inverter REAL,
                peak_temp_time TEXT
            )
        ''')

        # Table 2: daily_power_usage (Power usage data)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_power_usage (
                date TEXT PRIMARY KEY,
                solar_used_in_home_wh REAL,
                solar_exported_to_grid_wh REAL,
                total_power_consumed_wh REAL,
                self_used_percent REAL,
                autarky_percent REAL,
                morning_usage_wh REAL,
                morning_measurement_time TEXT,
                evening_usage_wh REAL,
                evening_measurement_time TEXT,
                FOREIGN KEY (date) REFERENCES daily_solar(date)
            )
        ''')

        # Table 3: intraday_history (10-minute history)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS intraday_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                time TEXT,
                solar_generation REAL,
                grid_usage REAL,
                FOREIGN KEY (date) REFERENCES daily_solar(date)
            )
        ''')

        # Indexes for performance
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_intraday_date ON intraday_history(date)')

        conn.commit()
        conn.close()

    def save_daily_solar(self, date_str, total_solar_kwh, daily_solar_wh, peak_solar_watt, peak_time, peak_temp_inverter, peak_temp_time):
        """Insert or update daily solar data."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO daily_solar (date, total_solar_kwh, daily_solar_wh, peak_solar_watt, peak_time, peak_temp_inverter, peak_temp_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_solar_kwh=excluded.total_solar_kwh,
                daily_solar_wh=excluded.daily_solar_wh,
                peak_solar_watt=excluded.peak_solar_watt,
                peak_time=excluded.peak_time,
                peak_temp_inverter=excluded.peak_temp_inverter,
                peak_temp_time=excluded.peak_temp_time
        ''', (date_str, total_solar_kwh, daily_solar_wh, peak_solar_watt, peak_time, peak_temp_inverter, peak_temp_time))

        conn.commit()
        conn.close()

    def save_daily_power(self, date_str, solar_used, exported, consumed, self_used_pct, autarky_pct, morning_usage=None, morning_time=None, evening_usage=None, evening_time=None):
        """Insert or update daily power usage data."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if record exists to update partial fields if needed
        cursor.execute(
            'SELECT * FROM daily_power_usage WHERE date = ?', (date_str,))
        row = cursor.fetchone()

        if row:
            # Update existing
            if morning_usage is None and row['morning_usage_wh'] is not None:
                morning_usage = row['morning_usage_wh']
            if morning_time is None and row['morning_measurement_time'] is not None:
                morning_time = row['morning_measurement_time']
            if evening_usage is None and row['evening_usage_wh'] is not None:
                evening_usage = row['evening_usage_wh']
            if evening_time is None and row['evening_measurement_time'] is not None:
                evening_time = row['evening_measurement_time']
            if solar_used is None and row['solar_used_in_home_wh'] is not None:
                solar_used = row['solar_used_in_home_wh']
            # ... and so on. For now, assuming caller provides what they have.

            cursor.execute('''
                UPDATE daily_power_usage SET
                    solar_used_in_home_wh = COALESCE(?, solar_used_in_home_wh),
                    solar_exported_to_grid_wh = COALESCE(?, solar_exported_to_grid_wh),
                    total_power_consumed_wh = COALESCE(?, total_power_consumed_wh),
                    self_used_percent = COALESCE(?, self_used_percent),
                    autarky_percent = COALESCE(?, autarky_percent),
                    morning_usage_wh = COALESCE(?, morning_usage_wh),
                    morning_measurement_time = COALESCE(?, morning_measurement_time),
                    evening_usage_wh = COALESCE(?, evening_usage_wh),
                    evening_measurement_time = COALESCE(?, evening_measurement_time)
                WHERE date = ?
            ''', (solar_used, exported, consumed, self_used_pct, autarky_pct, morning_usage, morning_time, evening_usage, evening_time, date_str))
        else:
            cursor.execute('''
                INSERT INTO daily_power_usage (date, solar_used_in_home_wh, solar_exported_to_grid_wh, total_power_consumed_wh, self_used_percent, autarky_percent, morning_usage_wh, morning_measurement_time, evening_usage_wh, evening_measurement_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (date_str, solar_used, exported, consumed, self_used_pct, autarky_pct, morning_usage, morning_time, evening_usage, evening_time))

        conn.commit()
        conn.close()

    def update_daily_power_phase(self, date_str, phase, usage_wh, time_str):
        """Update morning/evening phase logic."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Ensure row exists (might need to insert dummy valid if only phases come first?)
        # Usually solar/power comes first. If not, insert date only.
        cursor.execute(
            'INSERT OR IGNORE INTO daily_power_usage (date) VALUES (?)', (date_str,))

        if phase == 'morning':
            cursor.execute('''
                UPDATE daily_power_usage SET morning_usage_wh = ?, morning_measurement_time = ? WHERE date = ?
            ''', (usage_wh, time_str, date_str))
        elif phase == 'evening':
            cursor.execute('''
                UPDATE daily_power_usage SET evening_usage_wh = ?, evening_measurement_time = ? WHERE date = ?
            ''', (usage_wh, time_str, date_str))

        conn.commit()
        conn.close()

    def clear_intraday_history(self, date_str):
        """Clear intraday history for a specific date (to overwrite)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM intraday_history WHERE date = ?", (date_str,))
        conn.commit()
        conn.close()

    def save_intraday_record(self, date_str, time_str, solar_generation, grid_usage):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO intraday_history (date, time, solar_generation, grid_usage)
            VALUES (?, ?, ?, ?)
        ''', (date_str, time_str, solar_generation, grid_usage))
        conn.commit()
        conn.close()

    def get_full_history(self):
        """
        Mimics alldata.txt format retrieval.
        Returns list of strings or dicts resembling the lines in alldata.txt
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Join daily_solar and daily_power_usage
        cursor.execute('''
            SELECT 
                ds.date, 
                ds.total_solar_kwh, 
                ds.daily_solar_wh, 
                ds.peak_solar_watt, 
                ds.peak_time, 
                ds.peak_temp_inverter, 
                ds.peak_temp_time,
                dp.solar_used_in_home_wh,
                dp.solar_exported_to_grid_wh,
                dp.total_power_consumed_wh,
                dp.self_used_percent,
                dp.autarky_percent
            FROM daily_solar ds
            LEFT JOIN daily_power_usage dp ON ds.date = dp.date
            ORDER BY ds.date ASC
        ''')

        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_daily_record(self, date_str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
             SELECT 
                ds.*,
                dp.*
            FROM daily_solar ds
            LEFT JOIN daily_power_usage dp ON ds.date = dp.date
            WHERE ds.date = ?
        ''', (date_str,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_intraday_history(self, date_str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM intraday_history WHERE date = ? ORDER BY time ASC', (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return rows
