import system_data.update as update
from system_data.api_menu import menu, text, multichoice, inline_number, curses_control, number_input, text_input, multiline_input, backup_editor, get_stdscr, set_terminal_mode, get_terminal_mode, terminal_confirm, switch_terminal_mode
import system_data.play_classic as classic
from system_data.uno_ui import run_game
from system_data import play_classic as classic
from system_data.utility.update_utility import (
    get_old_exists, get_old_version, get_changelog,
    restore_old_version, delete_old
)
from system_data.utility.ui_utility import show_changelog, confirm_screen

#Libaries to import
import curses
import os
import configparser
import time

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH    = os.path.join(BASE_DIR, "system_data", "system_properties.ini")
SP_CONFIG_PATH = os.path.join(BASE_DIR, "system_data", "sp_settings.ini")

config    = configparser.ConfigParser()
config.read(CONFIG_PATH)

sp_config = configparser.ConfigParser()
sp_config.read(SP_CONFIG_PATH)

BLUE    = '\033[94m'
GREEN   = '\033[92m'
RED     = '\033[91m'
YELLOW  = '\033[93m'
MAGENTA = '\033[95m'
CYAN    = '\033[96m'
RESET   = '\033[0m'

CURRENT_VERSION = config.get("version", "current_version", fallback="unknown")
latest_version  = None


DEV_MODE = config.getboolean("dev_mode", "developer_mode", fallback=False)

# Apply terminal mode from config if previously saved
_saved_terminal = config.getboolean("display", "terminal_mode", fallback=False)
if _saved_terminal:
    set_terminal_mode(True)

UNO_BANNER = (f"""
{RED}██╗   ██╗{YELLOW}███╗   ██╗{GREEN}███████╗{BLUE}  ██╗{RESET}
{RED}██║   ██║{YELLOW}████╗  ██║{GREEN}██╔══██║{BLUE}  ██║{RESET}
{RED}██║   ██║{YELLOW}██╔██╗ ██║{GREEN}██║  ██║{BLUE}  ██║{RESET}
{RED}██║   ██║{YELLOW}██║╚██╗██║{GREEN}██║  ██║{BLUE}  ╚═╝{RESET}
{RED}╚██████╔╝{YELLOW}██║ ╚████║{GREEN}███████║{BLUE}  ██╗{RESET}
{RED} ╚═════╝ {YELLOW}╚═╝  ╚═══╝{GREEN}╚══════╝{BLUE}  ╚═╝{RESET}
{CYAN}Command-line based Card Game{RESET}
        """)


def build_main_menu_sidebar():
    return {
        "Single Player": {
            "title": "Modes available",
            "colour": "green",
            "sections": [
                {"heading": "Vs Bot", "body": "Play against computer-controlled opponents with adjustable difficulty and rules!"},
                {"heading": "Practice Mode (Coming Soon)", "body": "Learn how different cards interact and stack in a risk-free environment. Practice with an infinite deck and no opponents!{red} (coming soon){/}"},
            ]
        },
        "Multiplayer": {
            "title": "Modes available",
            "colour": "blue",
            "sections": [
                {"heading": "Pass and Play (Coming Soon)", "body": "Play with friends on the same device. Pass the device around as you play!"},
                {"heading": "LAN (Local Area Network) (Coming Soon)", "body": "Play with others on the same network. Connect over Wi-Fi or Ethernet!"},
                {"heading": "Online (Matchmaking) (Coming Soon)", "body": "Play with others online. Find random opponents or play with friends!"},
            ]
        },
        "Settings": {
            "title": "Adjust game preferences",
            "colour": "yellow",
            "sections": [
                {"heading": "Account Settings (Coming Soon)", "body": "Manage your UCL (Uno Command Line) account, view stats, and customize your profile!"},
                {"heading": "Update Settings", "body": "Adjust how Uno updates and view update history."},
                {"heading": "Mods and Customization", "body": "Coming soon!"},
                {"heading": "Other Settings (Coming Soon)", "body": "Adjust various other settings such as display options, controls, and more!"}
            ]
        },
        "Exit": {
            "title": "Exit the game",
            "colour": "red",
        }
    }

def build_update_sidebar():
    return {
        "Check for updates": {
            "title": "Updates",
            "sections": [
                {"heading": "Current Version", "body": CURRENT_VERSION},
                {"heading": "Latest Version",  "body": str(latest_version) if latest_version else "Not checked yet"},
                {"heading": "Status",          "body": "Up to date!" if CURRENT_VERSION == latest_version else f"Update available: {latest_version}"},
                {"heading": "Update Channel",  "body": config.get("update", "update_channel", fallback="stable")},
            ]
        }
    }
def build_settings_sidebar():
    return {
        "Display Options (BETA)": {
            "title": "Display Options",
            "sections": [
                {"heading": "Terminal Mode", "body": "Use a simpler terminal-based interface instead of the curses UI. This is less visually appealing and has no sidebars, but can be more compatible with certain terminals and remote play."},
            ]
        },
        "Mods and Customization": {
            "title": "Mods and Customization",
            "sections": [
                {"heading": "Uno 4 supports mods!", "body": "You can create your own custom game modes, rules, cards, and more using the modding API. Mods can be shared with other players and easily toggled on or off."},
                {"heading": "Mod Manager (Coming Soon)", "body": "Easily browse, install, and manage mods created by the community in the Mod Manager!"},
            ]
        },
        "Account Settings": {
            "title": "Account Settings",
            "sections": [
                {"heading": "UCL Account (Uno Command Line)", "body": "Create a UCL account to track your stats, customize your profile, and access online features!"},
                {"heading": "Profile Customization (Coming Soon)", "body": "Customize your profile with different colors, icons, and more! Show off your unique style!"},
            ]
        },
        "Backup and Update Settings": {
            "title": "Backup and Update Settings",
            "sections": [
                {"heading": "Backup Game Data", "body": "Create a backup of your game data and settings."},
                {"heading": "Update Settings", "body": "Adjust how Uno updates and view update history."},
            ]
        },
        "Developer Options": {
            "title": "Developer Options (Hidden)",
            "colour": "red",
            "sections": [
                {"heading": "Developer Tools toggle", "body": "Toggle to enable or disable developer tools."},
                {"heading": "View Terminal Output", "body": "View debug output from the game in the terminal."},
                {"heading": "Restart Game to Apply Code Changes", "body": "Restart the game to apply changes made to the code. (For developers testing changes)"},
            ]
        }

    }
def build_display_sidebar():
    return {
        "Terminal Mode": {
            "title": "Terminal Mode",
            "sections": [
                {"heading": "Terminal Mode", "body": "Terminal mode is a simpler display mode that uses basic text output instead of the curses-based UI. It is less visually appealing and has no sidebars, but can be more compatible with certain terminals and remote play setups."},
                {"heading": "Use Terminal Mode?", "body": "Toggle terminal mode on or off. Changes take effect immediately."},
            ]
        }
    }

def build_classic_sidebar():
    return {
        "Classic": {
            "title": "Classic",
            "sections": [
                {"heading": "Rules", "body": "The original Uno experience with standard rules and cards. No stacking of Draw Twos or Wild Draw Fours, and no special house rules."},
                {"heading": "Cards", "body": "1x0 per colour, 2x1-9 per colour, 2x Skip/Reverse/Draw Two per colour, 4x Wild, 4x Wild Draw Four"},
            ]
        }
    }


def build_game_sidebars():
    """Called every frame so bot count updates live in the sidebar."""
    sp_config.read(SP_CONFIG_PATH)
    num_bots = int(sp_config.get("bots", "number_of_bots", fallback="1"))

    bot_sections = [
        {
            "heading": f"Bot {i}: {sp_config.get(f'bot_{i}', 'name', fallback=f'Bot {i}')}",
            "body":    f"Difficulty: {sp_config.get(f'bot_{i}', 'difficulty', fallback='50')} / 100"
        }
        for i in range(1, num_bots + 1)
    ]

    return {
        "Number of Bots": {
            "title": "Bots",
            "sections": bot_sections + [{"heading": "", "body": "Left / Right or type a number to change"}]
        },
        "Customise Bots": {
            "title": "Bots",
            "sections": bot_sections + [{"heading": "", "body": "Press Enter to customise bots"}]
        },
        "Stack Draws": {"title": "Stack Draws", "sections": [
            {"heading": "What is this?", "body": "When enabled, players can stack +2 cards on top of other +2 cards, and +4 on +4. The next player must draw the total combined amount unless they also stack."},
            {"heading": "On",  "body": "Stacking is allowed."},
            {"heading": "Off", "body": "Draw cards must be taken immediately."},
        ]},
        "Force Play": {"title": "Force Play", "sections": [
            {"heading": "What is this?", "body": "When enabled, if the card you draw from the deck can be played immediately, you must play it. You cannot choose to keep it."},
            {"heading": "On",  "body": "Must play a drawn card if it is playable."},
            {"heading": "Off", "body": "You can keep the drawn card."},
        ]},
        "Jump In": {"title": "Jump In", "sections": [
            {"heading": "What is this?", "body": "If you have an identical card (same number and colour) to the one just played, you can play it out of turn instantly. Play then continues from you."},
            {"heading": "On",  "body": "Jump in with an identical card at any time."},
            {"heading": "Off", "body": "Players must wait for their turn."},
        ]},
        "Seven Swap": {"title": "Seven Swap", "sections": [
            {"heading": "What is this?", "body": "Playing a 7 lets you choose any player to swap your entire hand with. This can be a powerful strategic move."},
            {"heading": "On",  "body": "Playing a 7 swaps your hand with another player."},
            {"heading": "Off", "body": "7 cards have no special effect."},
        ]},
        "Zero Rotate": {"title": "Zero Rotate", "sections": [
            {"heading": "What is this?", "body": "When a 0 is played, every player passes their hand to the next player in the current direction of play. Everyone gets a new hand."},
            {"heading": "On",  "body": "Playing a 0 rotates all hands."},
            {"heading": "Off", "body": "0 cards have no special effect."},
        ]},
        "Starting Hand Size": {"title": "Starting Hand Size", "sections": [
            {"heading": "What is this?", "body": "The number of cards each player is dealt at the start of the game. Standard UNO uses 7 cards."},
            {"heading": "Default",       "body": "7 cards per player."},
        ]},
        "Win Condition": {"title": "Win Condition", "sections": [
            {"heading": "First",  "body": "The first player to empty their hand wins the round immediately."},
            {"heading": "Points", "body": "Play continues across multiple rounds. Cards left in other players hands score points against them. First to reach the target wins."},
        ]},
        "Points to Win": {"title": "Points to Win", "sections": [
            {"heading": "What is this?", "body": "Only used when Win Condition is set to Points. The first player to accumulate this many points wins. Standard UNO is 500."},
        ]},
    }


def on_bots_change(label, value):
    if label == "Number of Bots":
        if not sp_config.has_section("bots"):
            sp_config.add_section("bots")
        sp_config["bots"]["number_of_bots"] = str(value)

        # create any missing bot sections with defaults
        for i in range(1, value + 1):
            if not sp_config.has_section(f"bot_{i}"):
                sp_config.add_section(f"bot_{i}")
                sp_config[f"bot_{i}"]["name"]       = f"Bot {i}"
                sp_config[f"bot_{i}"]["difficulty"] = "50"

        with open(SP_CONFIG_PATH, "w") as f:
            sp_config.write(f)


def main():
    global latest_version, sp_config

    while True:
        with menu("Main Menu", ["Single Player", "Multiplayer", "Settings", "Exit"], color="cyan", banner=UNO_BANNER,sidebars=build_main_menu_sidebar()) as m:
            # ── Single Player ────────────────────────────────────────────
            if m.is_selected("Single Player"):
                while True:
                    with menu("Single Player", [
                        text("-- Choose Mode --"),
                        "vs Bots",
                        "Practice",
                        "< Back",
                    ], color="green") as sub:

                        if sub.is_selected("vs Bots"):
                            while True:
                                with menu("Play against Bots", [
                                    text("-- Play against computer players --"),
                                    "Play",
                                    "Settings",
                                    "< Back",
                                ], color="green") as sp_bot_menu:
                                    if sp_bot_menu.is_selected("Play"):
                                        def launch_game(stdscr):
                                            curses.start_color()
                                            curses.use_default_colors()
                                            state  = classic.new_game()
                                            action = run_game(stdscr, state)
                                            while action == "replay":
                                                state  = classic.new_game()
                                                action = run_game(stdscr, state)

                                        curses_control("end")
                                        curses.wrapper(launch_game)
                                        curses_control("start")
                                    if sp_bot_menu.is_selected("Settings"):
                                        while True:
                                            sp_config = configparser.ConfigParser()
                                            sp_config.read(SP_CONFIG_PATH)
                                            num_bots      = int(sp_config.get("bots",  "number_of_bots",    fallback="1"))
                                            cards         = sp_config.get("rules", "cards",              fallback="classic")
                                            stack_draws   = sp_config.get("rules", "stack_draws",        fallback="true")
                                            force_play    = sp_config.get("rules", "force_play",         fallback="false")
                                            jump_in       = sp_config.get("rules", "jump_in",            fallback="false")
                                            seven_swap    = sp_config.get("rules", "seven_swap",         fallback="false")
                                            zero_rotate   = sp_config.get("rules", "zero_rotate",        fallback="false")
                                            reshuffle      = sp_config.get("rules", "reshuffle_discard_pile", fallback="false")
                                            hand_size     = sp_config.get("game",  "starting_hand_size", fallback="7")
                                            win_condition = sp_config.get("game",  "win_condition",      fallback="first")
                                            points_to_win = sp_config.get("game",  "points_to_win",      fallback="500")

                                            def b(val):  return "yes" if val == "true" else "no"
                                            def yn(val): return "true" if val == "yes" else "false"

                                            with menu("Game Settings", [
                                                text("--- Bot Settings ---"),
                                                inline_number("Number of Bots", num_bots, 1, 9),
                                                "Customise Bots",
                                                text(""),
                                                text("--- Card Rules ---"),
                                                multichoice("Cards",        {"classic": "Classic Uno cards"}, default=b(cards)),
                                                multichoice("Stack Draws",  {"yes": "On", "no": "Off"}, default=b(stack_draws)),
                                                multichoice("Force Play",   {"yes": "On", "no": "Off"}, default=b(force_play)),
                                                multichoice("Jump In",      {"yes": "On", "no": "Off"}, default=b(jump_in)),
                                                multichoice("Seven Swap",   {"yes": "On", "no": "Off"}, default=b(seven_swap)),
                                                multichoice("Zero Rotate",  {"yes": "On", "no": "Off"}, default=b(zero_rotate)),
                                                multichoice("Reshuffle Discard Pile", {"yes": "This means as soon as a card is played it is reshuffled into the discard pile", "no": "This means the there is a discard pile and when the deck is empty the discard pile is reshuffled and made into the new deck to pick cards from"}, default=b(reshuffle)),
                                                text(""),
                                                text("--- Game Settings ---"),
                                                inline_number("Starting Hand Size", int(hand_size),     1,   20),
                                                text("Win Condition"),
                                                text("Points to Win"),
                                                text(""),
                                                "< Back",
                                            ], color="green",
                                               sidebars=build_game_sidebars,  # callable — fresh every frame
                                               on_change=on_bots_change) as sp_settings:

                                                # customise bots submenu
                                                if sp_settings.is_selected("Customise Bots"):
                                                    cur_num = int(sp_config.get("bots", "number_of_bots", fallback="1"))
                                                    while True:
                                                        bot_options  = []
                                                        bot_sidebars = {}
                                                        for i in range(1, cur_num + 1):
                                                            name  = sp_config.get(f"bot_{i}", "name",       fallback=f"Bot {i}")
                                                            diff  = sp_config.get(f"bot_{i}", "difficulty", fallback="50")
                                                            label = f"Bot {i}: {name}"
                                                            bot_options.append(label)
                                                            bot_sidebars[label] = {
                                                                "title": "All Bots",
                                                                "sections": [
                                                                    {
                                                                        "heading": f"Bot {j}: {sp_config.get(f'bot_{j}', 'name', fallback=f'Bot {j}')}",
                                                                        "body":    f"Difficulty: {sp_config.get(f'bot_{j}', 'difficulty', fallback='50')} / 100"
                                                                    }
                                                                    for j in range(1, cur_num + 1)
                                                                ] + [{"heading": "", "body": "Press Enter to edit"}]
                                                            }

                                                        with menu("Customise Bots", [
                                                            text("-- Select a bot to customise --"),
                                                            text(""),
                                                            *bot_options,
                                                            text(""),
                                                            "< Back",
                                                        ], color="green", sidebars=bot_sidebars) as bot_list:

                                                            for i in range(1, cur_num + 1):
                                                                name  = sp_config.get(f"bot_{i}", "name", fallback=f"Bot {i}")
                                                                label = f"Bot {i}: {name}"
                                                                if bot_list.is_selected(label):
                                                                    diff = sp_config.get(f"bot_{i}", "difficulty", fallback="50")
                                                                    while True:
                                                                        same_diff  = sp_config.get("bots", "same_difficulty", fallback="false")
                                                                        same_label = f"Same Difficulty: {'ON  (press Enter to toggle)' if same_diff == 'true' else 'OFF (press Enter to toggle)'}"
                                                                        with menu(f"Editing Bot {i}", [
                                                                            text(f"-- {name}  |  Difficulty: {diff} --"),
                                                                            text(""),
                                                                            same_label,
                                                                            "Edit Name",
                                                                            "Edit Difficulty",
                                                                            text(""),
                                                                            "< Back",
                                                                        ], color="green") as bot_edit:

                                                                            if bot_edit.is_selected(same_label):
                                                                                new_same = "false" if same_diff == "true" else "true"
                                                                                if not sp_config.has_section("bots"):
                                                                                    sp_config.add_section("bots")
                                                                                sp_config["bots"]["same_difficulty"] = new_same
                                                                                with open(SP_CONFIG_PATH, "w") as f:
                                                                                    sp_config.write(f)

                                                                            if bot_edit.is_selected("Edit Name"):
                                                                                new_name = text_input(get_stdscr(), f"Name for Bot {i}", name, 2)
                                                                                if not sp_config.has_section(f"bot_{i}"):
                                                                                    sp_config.add_section(f"bot_{i}")
                                                                                sp_config[f"bot_{i}"]["name"] = new_name
                                                                                with open(SP_CONFIG_PATH, "w") as f:
                                                                                    sp_config.write(f)
                                                                                name = new_name

                                                                            if bot_edit.is_selected("Edit Difficulty"):
                                                                                new_diff = number_input(get_stdscr(), f"Difficulty for Bot {i} (1-100)", int(diff), 1, 100, 2)
                                                                                if not sp_config.has_section(f"bot_{i}"):
                                                                                    sp_config.add_section(f"bot_{i}")
                                                                                sp_config[f"bot_{i}"]["difficulty"] = str(new_diff)
                                                                                if sp_config.get("bots", "same_difficulty", fallback="false") == "true":
                                                                                    for j in range(1, cur_num + 1):
                                                                                        if not sp_config.has_section(f"bot_{j}"):
                                                                                            sp_config.add_section(f"bot_{j}")
                                                                                        sp_config[f"bot_{j}"]["difficulty"] = str(new_diff)
                                                                                with open(SP_CONFIG_PATH, "w") as f:
                                                                                    sp_config.write(f)
                                                                                diff = str(new_diff)

                                                                            if bot_edit.is_selected("< Back"):
                                                                                break

                                                            if bot_list.is_selected("< Back"):
                                                                break

                                                # save rules
                                                if not sp_config.has_section("rules"): sp_config.add_section("rules")
                                                if not sp_config.has_section("game"):  sp_config.add_section("game")
                                                sp_config["rules"]["cards"]       = sp_settings.get_value("Cards") or b(cards)
                                                sp_config["rules"]["stack_draws"] = yn(sp_settings.get_value("Stack Draws") or b(stack_draws))
                                                sp_config["rules"]["force_play"]  = yn(sp_settings.get_value("Force Play")  or b(force_play))
                                                sp_config["rules"]["jump_in"]     = yn(sp_settings.get_value("Jump In")     or b(jump_in))
                                                sp_config["rules"]["seven_swap"]  = yn(sp_settings.get_value("Seven Swap")  or b(seven_swap))
                                                sp_config["rules"]["zero_rotate"] = yn(sp_settings.get_value("Zero Rotate") or b(zero_rotate))
                                                sp_config["rules"]["reshuffle_discard_pile"] = yn(sp_settings.get_value("Reshuffle Discard Pile") or b(reshuffle))

                                                new_size = sp_settings.get_number("Starting Hand Size")
                                                if new_size:
                                                    sp_config["game"]["starting_hand_size"] = str(new_size)

                                                new_wc = sp_settings.get_value("Win Condition")
                                                if new_wc:
                                                    sp_config["game"]["win_condition"] = new_wc

                                                new_pts = sp_settings.get_number("Points to Win")
                                                if new_pts:
                                                    sp_config["game"]["points_to_win"] = str(new_pts)

                                                with open(SP_CONFIG_PATH, "w") as f:
                                                    sp_config.write(f)

                                                if sp_settings.is_selected("< Back"):
                                                    break
                                    if sp_bot_menu.is_selected("< Back"):
                                        break

                        if sub.is_selected("Practice"):
                            while True:
                                with menu("Practice Mode", [
                                    text("-- Learn how different cards interact and stack --"),
                                    text(""),
                                    text("Mode is currently unavailable."),
                                    text(""),
                                    "< Back",
                                ], color="green") as practice_menu:
                                    if practice_menu.is_selected("< Back"):
                                        break

                        if sub.is_selected("< Back"):
                            break

            # ── Multiplayer ──────────────────────────────────────────────
            if m.is_selected("Multiplayer"):
                while True:
                    with menu("Multiplayer", [
                        text("-- Choose Mode --"),
                        "Pass and Play",
                        "LAN (Local Area Network)",
                        "Online (Matchmaking)",
                        "< Back",
                    ], color="blue") as sub:

                        if sub.is_selected("Pass and Play"):
                            while True:
                                with menu("Pass and Play", [
                                    text("-- Pass the device to the next player --"),
                                    text(""),
                                    text("Mode is currently unavailable."),
                                    text(""),
                                    "< Back",
                                ], color="blue") as passplaymenu:
                                    if passplaymenu.is_selected("< Back"):
                                        break

                        if sub.is_selected("LAN (Local Area Network)"):
                            while True:
                                with menu("LAN (Local Area Network)", [
                                    text("-- Play with people on the same network --"),
                                    text(""),
                                    text("Mode is currently unavailable."),
                                    text(""),
                                    "< Back",
                                ], color="blue") as lanmenu:
                                    if lanmenu.is_selected("< Back"):
                                        break

                        if sub.is_selected("Online (Matchmaking)"):
                            while True:
                                with menu("Online (Matchmaking)", [
                                    text("-- Play with others online --"),
                                    text(""),
                                    text("Mode is currently unavailable."),
                                    text(""),
                                    "< Back",
                                ], color="blue") as onlinemenu:
                                    if onlinemenu.is_selected("< Back"):
                                        break

                        if sub.is_selected("< Back"):
                            break

            # ── Settings ─────────────────────────────────────────────────
            if m.is_selected("Settings"):
                while True:
                    settings_items = [
                        text("-- Choose settings category to change --"),
                        "Display Options (BETA)",
                        "Mods and Customization",
                        "Account Settings",
                        text(""),
                        "Backup and Update Settings",
                        text(""),
                    ]
                    DEV_MODE = config.getboolean("dev_mode", "developer_mode", fallback=False)
                    if DEV_MODE == True:
                        settings_items += ["Developer Options", text("")]
                    settings_items.append("< Back")

                    with menu("Settings", settings_items, color="yellow",sidebars=build_settings_sidebar) as sub:

                        if sub.is_selected("Display Options (BETA)"):
                            while True:
                                cur_terminal = get_terminal_mode()
                                disp_default = "yes" if cur_terminal else "no"
                                disp_items = [
                                    text("-- Adjust how the game is displayed --"),
                                    text("")
                                    ]
                                BETA_MODE = config.getboolean("dev_mode", "beta_features", fallback=False)
                                if BETA_MODE:
                                    disp_items += [
                                    multichoice(
                                        "Terminal mode",
                                        {
                                            "yes": "Use plain terminal instead of curses UI",
                                            "no":  "Use curses UI (default)",
                                        },
                                        default=disp_default,
                                    ),
                                    ]
                                else:
                                    disp_items += [
                                        text("Terminal mode is currently a beta feature and can be enabled in Developer Options if you want to try it out. It is recommended to keep it disabled unless you are having issues with the curses UI."),
                                    ]
                                disp_items.append(text(""))
                                disp_items.append("< Back")
                                with menu("Display Options (BETA)", disp_items, color="yellow") as disp_menu:
                                    new_val = disp_menu.get_value("Terminal mode")
                                    if new_val is not None:
                                        enabled = (new_val == "yes")
                                        if enabled != cur_terminal:
                                            switch_terminal_mode(enabled)
                                            if not config.has_section("display"):
                                                config.add_section("display")
                                            config["display"]["terminal_mode"] = "True" if enabled else "False"
                                            with open(CONFIG_PATH, "w") as f:
                                                config.write(f)
                                    if disp_menu.is_selected("< Back"):
                                        break

                        if DEV_MODE and sub.is_selected("Developer Options"):
                            while True:
                                raw         = config.get("dev_mode", "developer_mode", fallback="True")
                                raw_beta    = config.get("dev_mode", "beta_features", fallback="False")
                                default_val = "yes" if raw == "True" else "no"
                                default_beta = "yes" if raw_beta == "True" else "no"
                                with menu("Developer Options", [
                                    text("-- Developer tools (dev_mode enabled) --"),
                                    text(""),
                                    multichoice(
                                        "Developer Tools",
                                        {
                                            "yes": "Allows Uno to update automatically",
                                            "no":  "Uno does not update automatically",
                                        },
                                        default=default_val
                                    ),
                                    "Restart game to apply code changes",
                                    multichoice(
                                        "Enable Beta Features",
                                        {
                                            "yes": "Allows for Beta features to be enabled in the game (Use with caution, may cause instability) (Display Options)",
                                            "no": "False (default)",
                                        },
                                        default=default_beta
                                    ),
                                    text(""),
                                    text("-- Terminal Tools --"),
                                    text(""),
                                    "View terminal output",
                                    "Clear terminal",
                                    text(""),
                                    "< Back",
                                ], color="red") as dev_menu:
                                    
                                    dev_menu_toggle = dev_menu.get_value("Developer Tools")
                                    if not config.has_section("dev_mode"):
                                        config.add_section("dev_mode")
                                    config["dev_mode"]["developer_mode"] = "True" if dev_menu_toggle == "yes" else "False"

                                    dev_menu_beta = dev_menu.get_value("Enable Beta Features")
                                    if not config.has_section("dev_mode"):
                                        config.add_section("dev_mode")
                                    config["dev_mode"]["beta_features"] = "True" if dev_menu_beta == "yes" else "False" 

                                    with open(CONFIG_PATH, "w") as f:
                                        config.write(f)
                                        DEV_MODE = False
                                    if dev_menu.is_selected("View terminal output"):
                                        curses_control("end")
                                        print("\n── Terminal output ──────────────────")
                                        print("(Scroll up to see previous output)")
                                        input("\nPress Enter to return to menu...")
                                        curses_control("start")
                                    if dev_menu.is_selected("Clear terminal"):
                                        curses_control("end")
                                        print("\033c", end="")  # ANSI escape code to clear terminal
                                        print("Terminal cleared.")
                                        input("\nPress Enter to return to menu...")
                                        curses_control("start")
                                    if dev_menu.is_selected("Restart game to apply code changes"):
                                        curses_control("end")
                                        print("\nRestarting game...")
                                        update.restart_game()

                                    if dev_menu.is_selected("< Back"):
                                        break

                        
                        if sub.is_selected("Backup and Update Settings"):
                            while True:
                                raw         = config.get("update", "auto_update", fallback="True")
                                default_val = "yes" if raw == "True" else "no"

                                old_exists  = get_old_exists()
                                old_version = get_old_version() if old_exists else None

                                def build_update_sidebars():
                                    changelog_preview = get_changelog()[:3]
                                    preview_text      = " / ".join(changelog_preview) if changelog_preview else "No changelog"
                                    old_ex            = get_old_exists()
                                    old_ver           = get_old_version() if old_ex else None

                                    def _backup_sections():
                                        backups = update.list_backups()
                                        if not backups:
                                            return [{"heading": "No backups", "body": "Use 'Create a new backup' to make one."}]
                                        sections = []
                                        for b in backups:
                                            props  = update.read_backup_properties(b)
                                            source = props.get("source", "unknown")
                                            fv     = props.get("from_version", "?")
                                            tv     = props.get("to_version", "")
                                            ver    = f"v{fv} → v{tv}" if tv else f"v{fv}"
                                            tag    = "[update]" if source == "update" else "[manual]"
                                            notes  = props.get("notes", "").strip()
                                            notes_preview = notes.split("\n")[0][:60] if notes else ""
                                            body = f"{ver}   {notes_preview}" if notes_preview else ver
                                            sections.append({"heading": f"{tag} {b}", "body": body})
                                        return sections

                                    return {
                                        "Create a new backup": {
                                            "title": "Existing Backups",
                                            "sections": _backup_sections(),
                                        },
                                        "Manage backups": {
                                            "title": "Existing Backups",
                                            "sections": _backup_sections(),
                                        },
                                        "Check for updates": {
                                            "title": "Updates",
                                            "sections": [
                                                {"heading": "Current Version", "body": CURRENT_VERSION},
                                                {"heading": "Latest Version",  "body": str(latest_version) if latest_version else "Not checked yet"},
                                                {"heading": "Status",          "body": "Up to date!" if CURRENT_VERSION == latest_version else f"Update available: {latest_version}"},
                                                {"heading": "Update Channel",  "body": config.get("update", "update_channel", fallback="stable")},
                                            ]
                                        },
                                        "Latest Update": {
                                            "title": "Latest Update",
                                            "sections": [
                                                {"heading": "Version",         "body": CURRENT_VERSION},
                                                {"heading": "Channel",         "body": config.get("update", "update_channel", fallback="stable")},
                                                {"heading": "Changelog:",      "body": preview_text},
                                            ]
                                        },
                                        "Remove Backup (uno.old)": {
                                            "title": "Remove Backup",
                                            "sections": [
                                                {"heading": "Backup found",    "body": "Yes" if old_ex else "No"},
                                                {"heading": "Backup version",  "body": old_ver if old_ver else "N/A"},
                                                {"heading": "",                "body": "This permanently deletes the backup. Cannot be undone."},
                                            ]
                                        },
                                    }

                                with menu("Backup and Update Settings", [
                                    text("-- Manage backups --"),
                                    "Create a new backup",
                                    "Manage backups",
                                    text(""),
                                    text("-- Adjust update preferences --"),
                                    "Check for updates",
                                    "Latest Update",
                                    "Remove Backup (uno.old)",
                                    multichoice(
                                        "Auto update",
                                        {
                                            "yes": "Allows Uno to update automatically",
                                            "no":  "Uno does not update automatically",
                                        },
                                        default=default_val
                                    ),
                                    text(""),
                                    "< Back",
                                ], color="yellow", sidebars=build_update_sidebars) as update_menu:

                                    if update_menu.is_selected("Create a new backup"):
                                        bk_title, bk_notes = backup_editor(pair=5)
                                        if bk_title is not None:
                                            slot      = update._backup_current(bk_title.strip() or None, source="manual")
                                            slot_name = os.path.basename(slot)
                                            if bk_notes and bk_notes.strip():
                                                update.write_backup_notes(slot_name, bk_notes)

                                    if update_menu.is_selected("Manage backups"):
                                        while True:
                                            backups = update.list_backups()
                                            if not backups:
                                                with menu("Manage Backups", [
                                                    text("No backups found."),
                                                    text("Use 'Create a new backup' to make one."),
                                                    text(""),
                                                    "< Back",
                                                ], color="yellow") as empty_menu:
                                                    break
                                            else:
                                                def build_backup_list_sidebars():
                                                    sb = {}
                                                    for b in update.list_backups():
                                                        props   = update.read_backup_properties(b)
                                                        source  = props.get("source", "unknown")
                                                        fv      = props.get("from_version", "?")
                                                        tv      = props.get("to_version", "")
                                                        uid     = props.get("update_id", "")
                                                        created = props.get("created_at", "")
                                                        modified = props.get("last_modified", "")
                                                        bk_notes = props.get("notes", "").strip()
                                                        ver     = f"v{fv} → v{tv}" if tv else f"v{fv}"
                                                        tag     = "Update" if source == "update" else "Manual"
                                                        sections = [
                                                            {"heading": "Source",  "body": tag},
                                                            {"heading": "Version", "body": ver},
                                                            {"heading": "Created", "body": created},
                                                        ]
                                                        if modified and modified != created:
                                                            sections.append({"heading": "Modified", "body": modified})
                                                        if uid:
                                                            sections.append({"heading": "Update ID", "body": uid})
                                                        if bk_notes:
                                                            sections.append({"heading": "Notes", "body": bk_notes.split("\n")[0][:80]})
                                                        sb[b] = {"title": b, "colour": "yellow", "sections": sections}
                                                    return sb

                                                backup_items = list(backups) + [text(""), "< Back"]
                                                with menu("Manage Backups", backup_items,
                                                          color="yellow", sidebars=build_backup_list_sidebars) as bk_list:

                                                    if bk_list.is_selected("< Back"):
                                                        break

                                                    selected_backup = next((b for b in backups if bk_list.is_selected(b)), None)

                                                    if selected_backup:
                                                        props   = update.read_backup_properties(selected_backup)
                                                        source  = props.get("source", "manual")
                                                        fv      = props.get("from_version", "?")
                                                        tv      = props.get("to_version", "")
                                                        ver     = f"v{fv} → v{tv}" if tv else f"v{fv}"
                                                        created = props.get("created_at", "")
                                                        bk_notes = props.get("notes", "").strip()

                                                        while True:
                                                            def build_action_sidebars():
                                                                props_fresh = update.read_backup_properties(selected_backup)
                                                                modified    = props_fresh.get("last_modified", "")
                                                                info_sections = [
                                                                    {"heading": "Source",   "body": "Update" if source == "update" else "Manual"},
                                                                    {"heading": "Version",  "body": ver},
                                                                    {"heading": "Created",  "body": created},
                                                                ]
                                                                if modified and modified != created:
                                                                    info_sections.append({"heading": "Modified", "body": modified})
                                                                info_sections.append(
                                                                    {"heading": "Notes", "body": bk_notes.split("\n")[0][:80] if bk_notes else "No notes"}
                                                                )
                                                                return {
                                                                    "Restore": {"title": selected_backup, "colour": "yellow", "sections": info_sections},
                                                                    "Edit":    {"title": selected_backup, "colour": "yellow", "sections": info_sections},
                                                                    "View notes": {"title": "Notes", "colour": "yellow", "sections": [{"heading": "", "body": bk_notes or "No notes."}]},
                                                                    "Delete":  {"title": selected_backup, "colour": "red",    "sections": [{"heading": "{red}Warning{/}", "body": "Permanently deletes this backup. Cannot be undone."}]},
                                                                    "< Back":  {"title": selected_backup, "colour": "yellow", "sections": info_sections},
                                                                }

                                                            action_items = [
                                                                text(f"-- {selected_backup} --"),
                                                                text(""),
                                                                "Restore",
                                                                "Edit",
                                                            ]
                                                            if source == "update":
                                                                action_items.append("View notes")
                                                            action_items += [text(""), "Delete", text(""), "< Back"]

                                                            with menu(selected_backup, action_items,
                                                                      color="yellow", sidebars=build_action_sidebars) as action_menu:

                                                                if action_menu.is_selected("Restore"):
                                                                    ok, msg = update.restore_backup(selected_backup)
                                                                    if ok:
                                                                        curses_control("end")
                                                                        print(f"\n{msg}")
                                                                        input("Press Enter — game will restart...")
                                                                        update.restart_game()
                                                                    else:
                                                                        curses_control("end")
                                                                        print(f"\n{msg}")
                                                                        input("Press Enter to return...")
                                                                        curses_control("start")

                                                                if action_menu.is_selected("Edit"):
                                                                    new_title, new_notes = backup_editor(
                                                                        pair=5,
                                                                        initial_title=selected_backup,
                                                                        initial_notes=bk_notes,
                                                                    )
                                                                    if new_title is not None:
                                                                        # Rename if title changed
                                                                        if new_title.strip() and new_title.strip() != selected_backup:
                                                                            ok, msg = update.rename_backup(selected_backup, new_title.strip())
                                                                            if ok:
                                                                                selected_backup = new_title.strip()
                                                                        # Save notes if changed
                                                                        if new_notes != bk_notes:
                                                                            update.write_backup_notes(selected_backup, new_notes)
                                                                            bk_notes = new_notes.strip()

                                                                if action_menu.is_selected("View notes") and source == "update":
                                                                    multiline_input(
                                                                        f"Notes — {selected_backup}  (Esc to close)",
                                                                        bk_notes or "No notes.", pair=5, readonly=True
                                                                    )

                                                                if action_menu.is_selected("Delete"):
                                                                    curses_control("end")
                                                                    confirm = input(f"Delete '{selected_backup}'? Cannot be undone. (y/N)\n> ").strip().lower()
                                                                    if confirm == "y":
                                                                        ok, msg = update.delete_backup(selected_backup)
                                                                        print(f"\n{msg}")
                                                                        input("Press Enter to return...")
                                                                        curses_control("start")
                                                                        break
                                                                    else:
                                                                        print("\nCancelled.")
                                                                        input("Press Enter to return...")
                                                                        curses_control("start")

                                                                if action_menu.is_selected("< Back"):
                                                                    break

                                    if update_menu.is_selected("Check for updates"):
                                        global latest_version
                                        curses_control("end")
                                        print("\nChecking for updates...")
                                        result = update.check_for_updates()
                                        latest_version = result.get("version") 

                                        if result["status"] == "updated":
                                            print(f"\nUpdated to {result['version']}!")
                                            if result["notes"]:
                                                print(f"Notes: {result['notes']}")
                                            print("\nRestarting game...")
                                            time.sleep(2)
                                            update.restart_game()  # replaces this process with a fresh one

                                        elif result["status"] == "up_to_date":
                                            print(f"\nYou are up to date ({result['version']})")
                                            input("\nPress Enter to return to menu...")
                                            curses_control("start")

                                        elif result["status"] == "failed":
                                            print(f"\nUpdate failed:")
                                            for err in result["errors"]:
                                                print(f"  - {err}")
                                            input("\nPress Enter to return to menu...")
                                            curses_control("start")

                                        elif result["status"] == "no_manifest":
                                            print("\nCould not reach update server.")
                                            input("\nPress Enter to return to menu...")
                                            curses_control("start")

                                    if update_menu.is_selected("Latest Update"):
                                        while True:
                                            old_ex  = get_old_exists()
                                            old_ver = get_old_version() if old_ex else "Not found"

                                            latest_sidebars = {
                                                "View full changelog": {
                                                    "title": "Changelog",
                                                    "sections": [
                                                        {"heading": "Full changelog", "body": "Scroll through all version history"},
                                                    ]
                                                },
                                                "Uninstall Update": {
                                                    "title": "Uninstall Update",
                                                    "sections": [
                                                        {"heading": "Backup found",   "body": "Yes" if old_ex else "No — cannot restore"},
                                                        {"heading": "Backup version", "body": old_ver},
                                                        {"heading": "",               "body": "Restoring will replace the current install with the backup version." if old_ex else "No backup available to restore."},
                                                    ]
                                                },
                                                "Enable Developer Tools": {
                                                    "title": "Developer Tools",
                                                    "sections": [
                                                        {"heading": "Developer mode", "body": "Enabled" if DEV_MODE else "Disabled"},
                                                        {"heading": "",               "body": "Enabling developer mode allows access to experimental features and tools intended for development and debugging."},
                                                    ]
                                                },
                                            }

                                            with menu("Latest Update", [
                                                
                                                text(f"-- Version {CURRENT_VERSION} --"),
                                                text(""),
                                                "View "+CURRENT_VERSION+" Changelog",
                                                "View full changelog",
                                                "Uninstall Update",
                                                "Enable Developer Tools",
                                                text(""),
                                                "< Back",
                                            ], color="yellow", sidebars=latest_sidebars) as latest_menu:
                                                if latest_menu.is_selected("View "+CURRENT_VERSION+" Changelog"):
                                                    changelog_notes = update._extract_changelog_for_version(CURRENT_VERSION)
                                                    curses_control("start")
                                                    multiline_input(
                                                        f"Changelog — v{CURRENT_VERSION}  (Esc to close)",
                                                        changelog_notes or "No changelog entry found for this version.",
                                                        pair=5, readonly=True
                                                    )
                                                    curses_control("end")
                                                    curses_control("start")
                                                if latest_menu.is_selected("View full changelog"):
                                                        full = "\n".join(get_changelog())
                                                        curses_control("start")
                                                        multiline_input(
                                                            "Full Changelog  (Esc to close)",
                                                            full,
                                                            pair=5, readonly=True
                                                        )
                                                        curses_control("end")
                                                        curses_control("start")

                                                if latest_menu.is_selected("Uninstall Update"):
                                                    if not get_old_exists():
                                                        curses_control("end")
                                                        print("\nuno.old not found — no backup to restore.")
                                                        input("Press Enter to return...")
                                                        curses_control("start")
                                                    else:
                                                        if get_terminal_mode():
                                                            confirmed = terminal_confirm(
                                                                f"Restore backup version {get_old_version()}? This will replace your current install.",
                                                                warning="This cannot be undone."
                                                            )
                                                        else:
                                                            confirmed = confirm_screen(
                                                                get_stdscr(),
                                                                f"Restore backup version {get_old_version()}? This will replace your current install.",
                                                                warning="This cannot be undone."
                                                            )
                                                        if confirmed:
                                                            curses_control("end")
                                                            success, msg = restore_old_version()
                                                            print(f"\n{msg}")
                                                            input("Press Enter to return...")
                                                            curses_control("start")
                                                if latest_menu.is_selected("Enable Developer Tools"):
                                                    curses_control("end")
                                                    print("\nEnabling developer tools...")
                                                    print("")
                                                    print("Developer mode allows access to experimental features and tools intended for development and debugging.")
                                                    print("Developer mode has been enabled")
                                                    input("Press Enter to continue...")
                                                    curses_control("start")
                                                    if not config.has_section("dev_mode"):
                                                        config.add_section("dev_mode")
                                                    config["dev_mode"]["developer_mode"] = "True"
                                                    with open(CONFIG_PATH, "w") as f:
                                                        config.write(f)
                                                        DEV_MODE = True

                                                if latest_menu.is_selected("< Back"):
                                                    break

                                    if update_menu.is_selected("Remove Backup (uno.old)"):
                                        if not get_old_exists():
                                            curses_control("end")
                                            print("\nuno.old not found — nothing to delete.")
                                            input("Press Enter to return...")
                                            curses_control("start")
                                        else:
                                            if get_terminal_mode():
                                                confirmed = terminal_confirm(
                                                    "Permanently delete uno.old? This removes your ability to roll back.",
                                                    warning="This CANNOT be undone."
                                                )
                                            else:
                                                confirmed = confirm_screen(
                                                    get_stdscr(),
                                                    "Permanently delete uno.old? This removes your ability to roll back.",
                                                    warning="This CANNOT be undone."
                                                )
                                            if confirmed:
                                                success, msg = delete_old()
                                                curses_control("end")
                                                print(f"\n{msg}")
                                                input("Press Enter to return...")
                                                curses_control("start")

                                    auto_update = update_menu.get_value("Auto update")
                                    if not config.has_section("update"):
                                        config.add_section("update")
                                    config["update"]["auto_update"] = "True" if auto_update == "yes" else "False"
                                    with open(CONFIG_PATH, "w") as f:
                                        config.write(f)

                                    if update_menu.is_selected("< Back"):
                                        break

                        if sub.is_selected("Mods and Customization"):
                            while True:
                                with menu("Mods and Customization", [
                                    text("-- Manage mods and customize your game --"),
                                    text(""),
                                    "Classic",
                                    text(""),
                                    "< Back",
                                ], color="yellow", sidebars=build_classic_sidebar()) as mod_menu:
                                    if mod_menu.is_selected("Classic"):
                                        pass
                                    if mod_menu.is_selected("< Back"):
                                        break

                        if sub.is_selected("< Back"):
                            break

            # ── Exit ─────────────────────────────────────────────────────
            if m.is_selected("Exit"):
                os.system("clear")
                break


# ── Startup ───────────────────────────────────────────────────────────────
auto_update = update.auto_update()

if update.auto_update():
    print("Checking for updates...")
    result = update.silent_update_check()
    if result["status"] == "updated":
        print(f"Updated to {result['version']}. Restarting...")
        time.sleep(2)
        update.restart_game()
    elif result["status"] == "failed":
        print(f"Update failed: {result.get('errors', [])}")
        input("Press Enter to continue anyway...")

print("Starting the game...")
main()