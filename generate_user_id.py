import json
import uuid
import os

CONFIG_FILE = 'config.json'

def generate_user_id():
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            pass

    if 'user_id' not in config or not config['user_id']:
        # Generate 8-character UUID
        user_id = str(uuid.uuid4())[:8]
        config['user_id'] = user_id
        print(f"Generated new user_id: {user_id}")
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    else:
        print(f"Existing user_id found: {config['user_id']}")

if __name__ == "__main__":
    generate_user_id()
