import os
from dotenv import load_dotenv


class Config:
    def __init__(self):
        load_dotenv()

        self.DOMAIN = os.getenv('DOMAIN')
        self.OPENDTU_IP = os.getenv("OPENDTU_IP")
        self.SHELLY_IP = os.getenv("SHELLY_IP")
        self.UPLOAD_API_KEY = os.getenv("UPLOAD_API_KEY")
        self.DATABASE_PATH = os.getenv("DATABASE_PATH")
        self.BUFFER_FILE_PATH = os.getenv("BUFFER_FILE_PATH")
        self.LOG_FILE = os.getenv("LOG_FILE")

        self.SYNC_DB_URL = f"http://{self.DOMAIN}/api/data/syncdb"
        self.OPENDTU_API_URL = f"http://{self.OPENDTU_IP}/api/livedata/status"
        self.SOLAR_UPLOAD_URL = f"http://{self.DOMAIN}/api/data/solar"
        self.POWER_UPLOAD_URL = f"http://{self.DOMAIN}/api/data/power"
        self.SHELLY_API_URL = f"http://{self.SHELLY_IP}/status"
