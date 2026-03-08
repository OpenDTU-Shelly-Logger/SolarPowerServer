import pandas as pd
import json
import os
from datetime import datetime

class DailyDataProcessor:
    def __init__(self, storage_path="solar_history.json"):
        self.storage_path = storage_path
        self.solar_threshold = 150

    def process_day(self, raw_data):
        """
        Verarbeitet die Rohdaten eines Tages und speichert sie ab.
        Überschreibt existierende Einträge für denselben Tag.
        """
        df = pd.DataFrame(raw_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Basis-Berechnungen
        df['consumption_w'] = df['solar_w'] + df['grid_w']
        df['duration_h'] = df['timestamp'].diff().dt.total_seconds() / 3600.0
        df['duration_h'] = df['duration_h'].fillna(0)
        df['energy_wh'] = df['consumption_w'] * df['duration_h']
        
        # 1. Metriken berechnen
        metrics = self._calculate_metrics(df)
        
        # 2. 10-Minuten-Batches erstellen (Resampling)
        batches = self._get_10min_batches(df)
        
        # 3. Datenstruktur für den Tag
        day_str = df['timestamp'].iloc[0].strftime('%Y-%m-%d')
        day_entry = {
            "date": day_str,
            "morning_phase": metrics['morning'],
            "evening_phase": metrics['evening'],
            "history_10min": batches
        }
        
        # 4. Speichern (mit Overwrite-Logik)
        self._save_to_json(day_str, day_entry)
        return day_entry

    def _calculate_metrics(self, df):
        # Morgen: Bis zum ersten Überschuss
        surplus_mask = df['solar_w'] > df['consumption_w']
        morning_data = {"time": None, "sum_wh": 0.0}
        
        if surplus_mask.any():
            idx = df[surplus_mask].index[0]
            morning_data["time"] = df.loc[idx, 'timestamp'].strftime('%H:%M:%S')
            morning_data["sum_wh"] = round(df.loc[:idx, 'energy_wh'].sum(), 2)

        # Abend: Ab letztem Mal > 150W Solar
        solar_active_mask = df['solar_w'] >= self.solar_threshold
        evening_data = {"time": None, "sum_wh": 0.0}
        
        if solar_active_mask.any():
            last_idx = df[solar_active_mask].index[-1]
            if last_idx + 1 < len(df):
                evening_start_idx = last_idx + 1
                evening_data["time"] = df.loc[evening_start_idx, 'timestamp'].strftime('%H:%M:%S')
                evening_data["sum_wh"] = round(df.loc[evening_start_idx:, 'energy_wh'].sum(), 2)
        
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

    def _save_to_json(self, day_key, day_entry):
        data = {}
        # Falls Datei existiert, laden
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = {}

        # Tag hinzufügen oder überschreiben
        data[day_key] = day_entry

        # Speichern
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Daten für {day_key} erfolgreich in {self.storage_path} gespeichert.")
