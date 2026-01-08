import requests
import configparser

def load_config(path="system_properties.ini"):
    config = configparser.ConfigParser()
    config.read(path)
    return config

config = load_config("client/system_data/system_properties.ini")
CURRENT_VERSION = config.get("version", "current_version")
print(CURRENT_VERSION)

UPDATE_URL = "https://raw.githubusercontent.com/Wiktor-M-21/Updates/main/uno_update.json"

def install_update():
    # Placeholder for update installation logic
    pass


def check_for_updates():
    try:
        response = requests.get(UPDATE_URL, timeout=5)
        response.raise_for_status()

        data = response.json()
        latest_version = data["version"]

        if latest_version != CURRENT_VERSION:
            print("Update available!")
            print(f"Current version: {CURRENT_VERSION}")
            print(f"Latest version: {latest_version}")
            print(f"Changelog: {data.get('changelog', 'No details')}")
            while True:
                choice = input("Do you want to install the update? (y/n): ").strip().lower()
                if choice == 'y':
                    install_update()
                    print("Update installed. Restarting the game.")
                    quit()
                elif choice == 'n':
                    print("Update skipped.")
                    break
                else:
                    print("Invalid input. Please enter 'y' or 'n'.")

        else:
            print("Game is up to date.")

    except requests.RequestException as e:
        print("Could not check for updates:", e)

#check_for_updates()


