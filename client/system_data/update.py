import os
try:
    import requests
except ImportError:
    os.system("pip3 install requests")
    import requests
import configparser
import shutil
import sys
import datetime


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
        "current_version": "1.0.6",
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


GITHUB_HEADERS = {
    "User-Agent": "UnoTerminalEdition-Updater/1.0",
    "Accept":     "application/json",
}


def fetch_manifest():
    response = requests.get(manifest_url, timeout=10, headers=GITHUB_HEADERS)
    if response.status_code == 429:
        retry = response.headers.get("Retry-After", "a few minutes")
        raise Exception(f"GitHub rate limit hit. Try again in {retry}.")
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
    try:
        manifest_uid = int(manifest.get("version_uid", 0))
    except (ValueError, TypeError):
        return False
    try:
        local_uid = int(load_config().get("update", "update_id", fallback="0"))
    except (ValueError, TypeError):
        local_uid = 0
    return manifest_uid > local_uid


def _extract_changelog_for_version(version: str) -> str:
    """
    Parse changelog.txt and return only the block for `version`.
    Returns an empty string if not found.
    """
    changelog_path = os.path.join(BASE_DIR, "utility", "changelog.txt")
    if not os.path.isfile(changelog_path):
        return ""
    with open(changelog_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    capturing = False
    block     = []
    for line in lines:
        stripped = line.rstrip()
        # A version header is a line whose first token matches the version string
        if stripped == version or stripped.startswith(version + " "):
            capturing = True
            continue
        if capturing:
            # Stop at the next version header (a line that looks like X.Y.Z)
            import re as _re
            if _re.match(r'^\d+\.\d+', stripped) and stripped != "":
                break
            block.append(stripped)

    return "\n".join(block).strip()



def _write_backup_properties(slot, source, from_version, to_version=None, update_id=None, notes=""):
    """Write a backup.ini descriptor into the given slot folder."""
    cfg = configparser.ConfigParser()
    cfg["backup"] = {
        "source":        source,
        "from_version":  from_version,
        "to_version":    to_version or "",
        "update_id":     str(update_id) if update_id is not None else "",
        "created_at":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_modified": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes":         notes,
    }
    with open(os.path.join(slot, "backup.ini"), "w") as f:
        cfg.write(f)


def read_backup_properties(name):
    """
    Read backup.ini from a named slot.
    Returns a dict with keys: source, from_version, to_version, update_id, created_at.
    Returns an empty dict if the file doesn't exist or can't be parsed.
    """
    props_path = os.path.join(OLD_PATH, name, "backup.ini")
    if not os.path.isfile(props_path):
        return {}
    cfg = configparser.ConfigParser()
    cfg.read(props_path)
    if not cfg.has_section("backup"):
        return {}
    return dict(cfg["backup"])


def write_backup_notes(name, notes: str):
    """
    Update only the notes field in a backup slot's backup.ini.
    Returns (success, message).
    """
    props_path = os.path.join(OLD_PATH, name, "backup.ini")
    if not os.path.isfile(props_path):
        return False, f"backup.ini not found for '{name}'."
    cfg = configparser.ConfigParser()
    cfg.read(props_path)
    if not cfg.has_section("backup"):
        return False, "Invalid backup.ini."
    cfg["backup"]["notes"]         = notes
    cfg["backup"]["last_modified"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(props_path, "w") as f:
        cfg.write(f)
    return True, "Notes saved."



def _backup_current(backup_name=None, source="manual", to_version=None, update_id=None, notes=None):
    """
    Copy all current files into utility/uno.old/<dated_folder> and write a backup.ini.

    source      : "manual" or "update"
    to_version  : the version being installed (update backups only)
    update_id   : numeric ID from the manifest (update backups only)
    notes       : freeform string; if None and source=="update", auto-extracted from changelog
    """
    os.makedirs(OLD_PATH, exist_ok=True)

    DATENOW = datetime.datetime.now().strftime("%d.%m.%Y_%H-%M")
    suffix  = ("_" + backup_name) if backup_name else ""
    slot    = os.path.join(OLD_PATH, DATENOW + suffix)
    os.makedirs(slot, exist_ok=True)

    # Auto-extract changelog notes for update backups
    if notes is None:
        if source == "update" and to_version:
            notes = _extract_changelog_for_version(to_version)
        else:
            notes = ""

    # Back up everything in system_data (except uno.old itself and __pycache__)
    for item in os.listdir(BASE_DIR):
        if item in ("uno.old", "__pycache__"):
            continue
        src = os.path.join(BASE_DIR, item)
        dst = os.path.join(slot, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "uno.old"))
        else:
            shutil.copy2(src, dst)

    # Back up uno_client.py from the project root
    root_client = os.path.join(CLIENT_DIR, "uno_client.py")
    if os.path.exists(root_client):
        shutil.copy2(root_client, os.path.join(slot, "uno_client.py"))

    _write_backup_properties(slot, source, CURRENT_VERSION, to_version, update_id, notes)

    print(f"Backup created: uno.old/{DATENOW}{suffix}")
    return slot

    print(f"Backup created: uno.old/{DATENOW}{suffix}")
    return slot


def list_backups(filter_source=None):
    """
    Return a sorted list of backup folder names inside uno.old (newest first).

    filter_source : None (all), "manual", or "update"
    """
    if not os.path.isdir(OLD_PATH):
        return []
    names = sorted(
        [d for d in os.listdir(OLD_PATH) if os.path.isdir(os.path.join(OLD_PATH, d))],
        reverse=True,
    )
    if filter_source is None:
        return names
    return [n for n in names if read_backup_properties(n).get("source") == filter_source]


def restore_backup(name):
    """
    Restore a named backup slot to the live install.

    Safety check: the backup's from_version must be <= CURRENT_VERSION
    and the backup's update_id (if present) must be <= the local update_id
    (stored in system_properties.ini [update] update_id).

    Returns (success, message).
    """
    slot = os.path.join(OLD_PATH, name)
    if not os.path.isdir(slot):
        return False, f"Backup '{name}' not found."

    props = read_backup_properties(name)

    # Version guard — only restore if this backup was taken from a version <= current
    backup_from = props.get("from_version", "")
    if backup_from and _parse_version(backup_from) > _parse_version(CURRENT_VERSION):
        return False, (
            f"Cannot restore: backup was taken from v{backup_from}, "
            f"which is newer than current v{CURRENT_VERSION}."
        )

    # Update-ID guard — if both sides have an ID, backup's ID must be <= local ID
    backup_uid = props.get("update_id", "").strip()
    cfg = load_config()
    local_uid  = cfg.get("update", "update_id", fallback="").strip()
    if backup_uid and local_uid:
        try:
            if int(backup_uid) > int(local_uid):
                return False, (
                    f"Cannot restore: backup update_id ({backup_uid}) "
                    f"is higher than local update_id ({local_uid})."
                )
        except ValueError:
            pass  # non-numeric IDs — skip the check

    print(f"Restoring backup '{name}'...")

    # Copy slot files back to their original locations
    for item in os.listdir(slot):
        if item == "backup.ini":
            continue
        src = os.path.join(slot, item)
        # uno_client.py lives one level up (CLIENT_DIR), everything else in BASE_DIR
        if item == "uno_client.py":
            dst = os.path.join(CLIENT_DIR, item)
        else:
            dst = os.path.join(BASE_DIR, item)

        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # Rewrite version in system_properties.ini to the backup's from_version
    if backup_from:
        _merge_system_properties(backup_from)

    return True, f"Restored to backup '{name}' (v{backup_from or '?'})."


def rename_backup(old_name, new_name):
    """Rename a backup slot. Returns (success, message)."""
    src = os.path.join(OLD_PATH, old_name)
    dst = os.path.join(OLD_PATH, new_name)
    if not os.path.isdir(src):
        return False, f"Backup '{old_name}' not found."
    if os.path.exists(dst):
        return False, f"A backup named '{new_name}' already exists."
    try:
        os.rename(src, dst)
        return True, f"Renamed '{old_name}' → '{new_name}'."
    except Exception as e:
        return False, str(e)


def delete_backup(name):
    """Permanently delete a single named backup slot. Returns (success, message)."""
    target = os.path.join(OLD_PATH, name)
    if not os.path.isdir(target):
        return False, f"Backup '{name}' not found."
    try:
        shutil.rmtree(target)
        return True, f"Deleted backup '{name}'."
    except Exception as e:
        return False, str(e)


def _download_file(url, dest_path):
    try:
        response = requests.get(url, timeout=15, headers=GITHUB_HEADERS)
        if response.status_code == 429:
            retry = response.headers.get("Retry-After", "a few minutes")
            return False, f"GitHub rate limit hit. Try again in {retry}."
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
    new_manifest_url = manifest.get("manifest_url")
    update_id        = manifest.get("version_uid")

    if not _is_update_available(manifest):
        print(f"Already up to date ({CURRENT_VERSION})")
        return {"status": "up_to_date", "version": latest, "errors": [], "notes": notes}

    print(f"Update available: {CURRENT_VERSION} → {latest}")
    to_update = input("Do you want to update now? (y/n): ").strip().lower()
    if to_update == "y":
        print("Creating backup...")
        _backup_current(
            backup_name=f"update_{latest.replace('.', '_')}",
            source="update",
            to_version=latest,
            update_id=update_id,
        )

        print("Downloading files...")
        success, errors = _apply_update(manifest)

        if success:
            _merge_system_properties(latest, new_manifest_url, update_id)
            print(f"Updated to {latest} successfully.")
            return {"status": "updated", "version": latest, "errors": [], "notes": notes}
        else:
            print("Update failed — backup preserved in uno.old")
            return {"status": "failed", "version": latest, "errors": errors, "notes": notes}
    else:
        return {"status": "cancelled", "version": latest, "errors": [], "notes": notes}

def _merge_system_properties(new_version, new_manifest_url=None, update_id=None):
    """
    After update — only change version, manifest_url, and update_id.
    Leave all user preferences (auto_update, channel, etc) untouched.
    """
    cfg_path = os.path.join(BASE_DIR, "system_properties.ini")
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    if not cfg.has_section("version"):
        cfg.add_section("version")
    cfg["version"]["current_version"] = new_version

    if not cfg.has_section("update"):
        cfg.add_section("update")

    if new_manifest_url:
        cfg["update"]["update_manifest_url"] = new_manifest_url

    if update_id is not None:
        cfg["update"]["update_id"] = str(update_id)

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