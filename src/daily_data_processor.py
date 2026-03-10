import pandas as pd
import json
import os
from datetime import datetime
from database import DatabaseManager


class DailyDataProcessor:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.solar_threshold = 150

    def process_day(self, raw_data):
        if not raw_data:
            return

        df = pd.DataFrame(raw_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')

        if 'solar_w' in df.columns and 'grid_w' in df.columns:
            pass

        df['consumption_w'] = df['solar_w'] + df['grid_w']

        # Calculate energy (Wh) via integration
        df['duration_h'] = df['timestamp'].diff().dt.total_seconds() / 3600.0
        df['duration_h'] = df['duration_h'].fillna(0)  # First row 0 duration
        df['energy_wh'] = df['consumption_w'] * df['duration_h']

        metrics = self._calculate_metrics(df)

        batches = self._get_10min_batches(df)

        date_str = df['timestamp'].iloc[0].strftime('%Y-%m-%d')

        morning = metrics.get('morning', {})
        if morning and morning.get('time'):
            self.db.update_daily_power_phase(
                date_str, 'morning', morning['sum_wh'], morning['time'])

        evening = metrics.get('evening', {})
        if evening and evening.get('time'):
            self.db.update_daily_power_phase(
                date_str, 'evening', evening['sum_wh'], evening['time'])

        self.db.clear_intraday_history(date_str)
        for batch in batches:
            self.db.save_intraday_record(
                date_str, batch['t'], batch['s'], batch['g'])

        return {
            "date": date_str,
            "morning_phase": metrics['morning'],
            "evening_phase": metrics['evening'],
            "history_10min": batches
        }

    def _calculate_metrics(self, df):
        # Morgen: Bis zum ersten Überschuss
        surplus_mask = df['solar_w'] > df['consumption_w']
        morning_data = {"time": None, "sum_wh": 0.0}

        if surplus_mask.any():
            idx = df[surplus_mask].index[0]
            morning_data["time"] = df.loc[idx,
                                          'timestamp'].strftime('%H:%M:%S')
            morning_data["sum_wh"] = round(df.loc[:idx, 'energy_wh'].sum(), 2)

        # Abend: Ab letztem Mal > 150W Solar
        solar_active_mask = df['solar_w'] >= self.solar_threshold
        evening_data = {"time": None, "sum_wh": 0.0}

        if solar_active_mask.any():
            last_idx = df[solar_active_mask].index[-1]
            if last_idx + 1 < len(df):
                evening_start_idx = last_idx + 1
                evening_data["time"] = df.loc[evening_start_idx,
                                              'timestamp'].strftime('%H:%M:%S')
                evening_data["sum_wh"] = round(
                    df.loc[evening_start_idx:, 'energy_wh'].sum(), 2)

        return {"morning": morning_data, "evening": evening_data}

    def _get_10min_batches(self, df):
        # Index auf Zeit setzen für Resample
        temp_df = df.set_index('timestamp')
        resampled = temp_df.resample('10min').mean(numeric_only=True)

        # Liste aus Dictionaries erstellen (Time, Solar, Grid)
        batches = []
        for ts, row in resampled.iterrows():
            batches.append({
                "t": ts.strftime('%H:%M'),
                "s": round(row['solar_w'], 1),
                "g": round(row['grid_w'], 1)
            })
        return batches
