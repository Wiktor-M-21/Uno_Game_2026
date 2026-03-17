import os
try:
    import requests
except ImportError:
    os.system("pip3 install requests")
    import requests
import configparser
import shutil
import sys


def generate_system_properties():
    """Create system_properties.ini with defaults if it doesn't exist."""
    if os.path.exists(SYS_CONFIG_PATH):
        return

    config = configparser.ConfigParser()

    config["update"] = {
        "auto_update":        "False",
        "update_channel":     "stable",
        "update_manifest_url": "https://raw.githubusercontent.com/Wiktor-M-21/Updates/main/uno_update.json",
    }
    config["version"] = {
        "current_version": "1.0.0",
    }
    config["modules"] = {
        "enabled": "True",
    }
    config["dev_mode"] = {
        "display_hover": "False",
    }

    with open(SYS_CONFIG_PATH, "w") as f:
        config.write(f)

    print("Generated system_properties.ini")


def generate_sp_settings():
    """Create sp_settings.ini with defaults if it doesn't exist."""
    if os.path.exists(SP_CONFIG_PATH):
        return

    config = configparser.ConfigParser()

    config["bots"] = {
        "number_of_bots":   "1",
        "same_difficulty":  "false",
    }
    config["bot_1"] = {
        "name":       "Bot 1",
        "difficulty": "50",
    }
    config["rules"] = {
        "stack_draws":          "true",
        "force_play":           "false",
        "jump_in":              "false",
        "seven_swap":           "false",
        "zero_rotate":          "false",
        "reshuffle_discard_pile": "false",
    }
    config["game"] = {
        "starting_hand_size": "7",
        "win_condition":      "first",
        "points_to_win":      "500",
    }

    with open(SP_CONFIG_PATH, "w") as f:
        config.write(f)

    print("Generated sp_settings.ini")


def run_setup():
    generate_system_properties()
    generate_sp_settings()

def restart_game():
    """Restart the game process completely."""
    os.execv(sys.executable, [sys.executable] + sys.argv)


BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR  = os.path.dirname(BASE_DIR)
OLD_PATH    = os.path.join(BASE_DIR, "utility", "uno.old")
SYS_CONFIG_PATH    = os.path.join(BASE_DIR, "system_properties.ini")
SP_CONFIG_PATH = os.path.join(BASE_DIR, "sp_settings.ini")

def load_config():
    path = os.path.join(BASE_DIR, "system_properties.ini")
    config = configparser.ConfigParser()
    config.read(path)
    return config

config          = load_config()
CURRENT_VERSION = config.get("version", "current_version", fallback="1.0.0")
manifest_url    = config.get("update", "update_manifest_url", fallback="").strip('"')


def auto_update():
    return load_config().getboolean("update", "auto_update", fallback=False)


def fetch_manifest():
    response = requests.get(manifest_url, timeout=10)
    response.raise_for_status()
    return response.json()


def check_for_latest_version():
    try:
        return fetch_manifest().get("version")
    except Exception as e:
        print(f"Could not check for updates: {e}")
        return None


def _parse_version(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0,)


def _is_update_available(manifest):
    return _parse_version(manifest.get("version")) > _parse_version(CURRENT_VERSION)


def _backup_current():
    """Copy all current files into utility/uno.old before updating."""
    if os.path.exists(OLD_PATH):
        shutil.rmtree(OLD_PATH)
    os.makedirs(OLD_PATH, exist_ok=True)

    # back up everything in system_data (except uno.old itself)
    for item in os.listdir(BASE_DIR):
        if item in ("uno.old", "__pycache__"):
            continue
        src = os.path.join(BASE_DIR, item)
        dst = os.path.join(OLD_PATH, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "uno.old"))
        else:
            shutil.copy2(src, dst)

    # back up uno_client.py from root
    root_client = os.path.join(CLIENT_DIR, "uno_client.py")
    if os.path.exists(root_client):
        shutil.copy2(root_client, os.path.join(OLD_PATH, "uno_client.py"))

    print("Backup created in uno.old")


def _download_file(url, dest_path):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        return True, None
    except Exception as e:
        return False, str(e)


def _apply_update(manifest):
    errors  = []
    SKIP    = {
        "system_data/system_properties.ini",
        "system_data/sp_settings.ini",
    }

    for file_entry in manifest.get("files", []):
        rel_path = file_entry["path"]
        url      = file_entry["url"]

        if rel_path in SKIP:
            print(f"  Skipping {rel_path} (user preferences preserved)")
            continue

        dest = os.path.join(CLIENT_DIR, rel_path)
        print(f"  Downloading {rel_path}...")
        success, err = _download_file(url, dest)
        if not success:
            errors.append(f"{rel_path}: {err}")
            print(f"  Failed: {err}")

    return len(errors) == 0, errors





def check_for_updates():
    try:
        manifest = fetch_manifest()
    except Exception as e:
        print(f"Could not reach update server: {e}")
        return {"status": "no_manifest", "version": None, "errors": [], "notes": ""}

    latest          = manifest.get("version")
    notes           = manifest.get("notes", "")
    new_manifest_url = manifest.get("manifest_url")  # optional — only if URL changes

    if not _is_update_available(manifest):
        print(f"Already up to date ({CURRENT_VERSION})")
        return {"status": "up_to_date", "version": latest, "errors": [], "notes": notes}

    print(f"Update available: {CURRENT_VERSION} → {latest}")
    print("Creating backup...")
    _backup_current()

    print("Downloading files...")
    success, errors = _apply_update(manifest)

    if success:
        _merge_system_properties(latest, new_manifest_url)  # ← only touches version + url
        print(f"Updated to {latest} successfully.")
        return {"status": "updated", "version": latest, "errors": [], "notes": notes}
    else:
        print("Update failed — backup preserved in uno.old")
        return {"status": "failed", "version": latest, "errors": errors, "notes": notes}

def _merge_system_properties(new_version, new_manifest_url=None):
    """
    After update — only change version and manifest_url.
    Leave all user preferences (auto_update, channel, etc) untouched.
    """
    cfg_path = os.path.join(BASE_DIR, "system_properties.ini")
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    # update version
    if not cfg.has_section("version"):
        cfg.add_section("version")
    cfg["version"]["current_version"] = new_version

    # update manifest url only if a new one was provided in the manifest
    if new_manifest_url:
        if not cfg.has_section("update"):
            cfg.add_section("update")
        cfg["update"]["update_manifest_url"] = new_manifest_url

    with open(cfg_path, "w") as f:
        cfg.write(f)


def silent_update_check():
    try:
        manifest = fetch_manifest()
    except Exception:
        return {"status": "no_manifest"}

    if not _is_update_available(manifest):
        return {"status": "up_to_date", "version": manifest.get("version")}

    print(f"\nAuto-update: {manifest.get('version')} available. Updating...")
    return check_for_updates()