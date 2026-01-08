import system_data.update as update


BLUE = '\033[94m'    # Blue
GREEN = '\033[92m'   # Green
RED = '\033[91m'     # Red
YELLOW = '\033[93m'  # Yellow
MAGENTA = '\033[95m' # Magenta
CYAN = '\033[96m'    # Cyan
RESET = '\033[0m'    # Reset to default



print(f"""
{RED}██╗   ██╗{YELLOW}███╗   ██╗{GREEN}███████╗{BLUE}  ██╗{RESET}
{RED}██║   ██║{YELLOW}████╗  ██║{GREEN}██╔══██║{BLUE}  ██║{RESET}
{RED}██║   ██║{YELLOW}██╔██╗ ██║{GREEN}██║  ██║{BLUE}  ██║{RESET}
{RED}██║   ██║{YELLOW}██║╚██╗██║{GREEN}██║  ██║{BLUE}  ╚═╝{RESET}
{RED}╚██████╔╝{YELLOW}██║ ╚████║{GREEN}███████║{BLUE}  ██╗{RESET}
{RED} ╚═════╝ {YELLOW}╚═╝  ╚═══╝{GREEN}╚══════╝{BLUE}  ╚═╝{RESET}
{CYAN}Socket-based Command-line Card Game{RESET}
    """)

auto_update = True

if auto_update == True:
    print("Auto-update is enabled. Checking for updates...")
    update.check_for_updates()