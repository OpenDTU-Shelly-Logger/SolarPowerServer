import datetime


class SimpleLogger:
    def __init__(self, name="output.log"):
        self.filename = name

    def log(self, message: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        print(f"[{timestamp}] {message}")
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(line)
