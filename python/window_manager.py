import json
import os

CONFIG_FILE = "window_config.json"

def load_window_config():
    """Loads window configurations from a JSON file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_window_config(config):
    """Saves window configurations to a JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_window_geometry(window_name):
    """Retrieves the geometry for a specific window."""
    config = load_window_config()
    return config.get(window_name)

def set_window_geometry(window, window_name):
    """Saves the current geometry of a Tkinter window."""
    config = load_window_config()
    config[window_name] = window.geometry()
    save_window_config(config)

def apply_saved_geometry(window, window_name):
    """Applies saved geometry to a Tkinter window if available."""
    geometry = get_window_geometry(window_name)
    if geometry:
        window.geometry(geometry)
        return True
    return False