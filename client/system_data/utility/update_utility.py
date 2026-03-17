import os
import shutil
import configparser

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
OLD_PATH       = os.path.join(BASE_DIR, "uno.old")
CONFIG_PATH    = os.path.join(BASE_DIR, "system_properties.ini")
CHANGELOG_PATH = os.path.join(BASE_DIR, "changelog.txt")


def get_old_exists():
    return os.path.exists(OLD_PATH)


def get_old_version():
    """Try to read version from uno.old's system_properties.ini."""
    old_config_path = os.path.join(OLD_PATH, "system_properties.ini")
    if not os.path.exists(old_config_path):
        return "Unknown"
    cfg = configparser.ConfigParser()
    cfg.read(old_config_path)
    return cfg.get("version", "current_version", fallback="Unknown")


def get_changelog():
    if not os.path.exists(CHANGELOG_PATH):
        return ["No changelog found."]
    with open(CHANGELOG_PATH, "r") as f:
        return f.read().splitlines()


def restore_old_version():
    """
    Swap current system_data contents with uno.old contents.
    Returns (success, message)
    """
    if not get_old_exists():
        return False, "uno.old not found."

    temp_path = os.path.join(BASE_DIR, "uno.current_backup")
    try:
        # move current to temp
        shutil.copytree(BASE_DIR, temp_path,
                        ignore=shutil.ignore_patterns("uno.old", "uno.current_backup"))
        # copy old into current
        for item in os.listdir(OLD_PATH):
            src = os.path.join(OLD_PATH, item)
            dst = os.path.join(BASE_DIR, item)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        # clean up temp
        shutil.rmtree(temp_path, ignore_errors=True)
        return True, "Restored successfully. Please restart Uno."
    except Exception as e:
        shutil.rmtree(temp_path, ignore_errors=True)
        return False, f"Restore failed: {e}"


def delete_old():
    """Delete uno.old folder completely. Returns (success, message)"""
    if not get_old_exists():
        return False, "uno.old does not exist."
    try:
        shutil.rmtree(OLD_PATH)
        return True, "uno.old deleted successfully."
    except Exception as e:
        return False, f"Failed to delete: {e}"