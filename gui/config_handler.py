import json
import os
import threading
from pathlib import Path

class ConfigHandler:
    _instance = None
    _lock = threading.Lock()
    CONFIG_FILE = Path(__file__).parent.parent / 'config.json'

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConfigHandler, cls).__new__(cls)
                    cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        self.config = {}
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
            except json.JSONDecodeError:
                print(f"Error decoding {self.CONFIG_FILE}. Starting with empty config.")
        else:
            print(f"{self.CONFIG_FILE} not found. Starting with empty config.")

    def save_config(self):
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_value(self, key, default=None):
        return self.config.get(key, default)

    def set_value(self, key, value):
        if self.config.get(key) != value:
            self.config[key] = value
            self.save_config()

    def update_values(self, updates):
        changed = False
        for key, value in updates.items():
            if self.config.get(key) != value:
                self.config[key] = value
                changed = True
        if changed:
            self.save_config()
