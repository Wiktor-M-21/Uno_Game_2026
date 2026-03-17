import curses


def show_changelog(stdscr):
    """Scrollable changelog viewer. Q to exit."""
    import os
    BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
    CHANGELOG_PATH = os.path.join(BASE_DIR, "changelog.txt")

    if not os.path.exists(CHANGELOG_PATH):
        lines = ["No changelog found."]
    else:
        with open(CHANGELOG_PATH, "r") as f:
            lines = f.read().splitlines()

    scroll = 0

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        visible = h - 3  # leave room for header and footer

        # header
        try:
            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(0, 0, "=" * w)
            stdscr.addstr(1, (w - len("CHANGELOG")) // 2, "CHANGELOG")
            stdscr.addstr(2, 0, "=" * w)
            stdscr.attroff(curses.A_BOLD)
        except curses.error:
            pass

        # content
        for i, line in enumerate(lines[scroll: scroll + visible]):
            try:
                stdscr.addstr(3 + i, 2, line[:w - 4])
            except curses.error:
                pass

        # footer
        max_scroll = max(0, len(lines) - visible)
        scroll_pct = int((scroll / max_scroll * 100)) if max_scroll > 0 else 100
        footer     = f"  Q to go back   ↑/↓ to scroll   {scroll_pct}%  "
        try:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(h - 1, 0, footer[:w])
            stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()

        if key in (ord('q'), ord('Q')):
            break
        elif key == curses.KEY_UP:
            scroll = max(0, scroll - 1)
        elif key == curses.KEY_DOWN:
            scroll = min(max_scroll, scroll + 1)
        elif key == curses.KEY_PPAGE:  # page up
            scroll = max(0, scroll - visible)
        elif key == curses.KEY_NPAGE:  # page down
            scroll = min(max_scroll, scroll + visible)


def confirm_screen(stdscr, prompt, warning=None):
    """
    Shows a confirmation screen.
    Returns True if user confirms, False if cancelled.
    """
    selected = 1  # default to No

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        box_h = 9
        box_w = min(60, w - 4)
        box_y = h // 2 - box_h // 2
        box_x = (w - box_w) // 2

        # draw box
        try:
            stdscr.addstr(box_y,     box_x, "┌" + "─" * (box_w - 2) + "┐")
            for i in range(1, box_h - 1):
                stdscr.addstr(box_y + i, box_x, "│" + " " * (box_w - 2) + "│")
            stdscr.addstr(box_y + box_h - 1, box_x, "└" + "─" * (box_w - 2) + "┘")
        except curses.error:
            pass

        # prompt
        prompt_lines = []
        words = prompt.split()
        line  = ""
        for word in words:
            if len(line) + len(word) + 1 > box_w - 4:
                prompt_lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            prompt_lines.append(line)

        for i, pl in enumerate(prompt_lines):
            try:
                stdscr.attron(curses.A_BOLD)
                stdscr.addstr(box_y + 2 + i, box_x + 2, pl)
                stdscr.attroff(curses.A_BOLD)
            except curses.error:
                pass

        # warning
        if warning:
            try:
                stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
                stdscr.addstr(box_y + 2 + len(prompt_lines) + 1,
                              box_x + 2, warning[:box_w - 4])
                stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)
            except curses.error:
                pass

        # buttons
        btn_y = box_y + box_h - 3
        yes_x = box_x + box_w // 2 - 10
        no_x  = box_x + box_w // 2 + 2

        try:
            if selected == 0:
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD | curses.A_REVERSE)
                stdscr.addstr(btn_y, yes_x, " YES ")
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD | curses.A_REVERSE)
                stdscr.attron(curses.A_DIM)
                stdscr.addstr(btn_y, no_x, "  NO ")
                stdscr.attroff(curses.A_DIM)
            else:
                stdscr.attron(curses.A_DIM)
                stdscr.addstr(btn_y, yes_x, " YES ")
                stdscr.attroff(curses.A_DIM)
                stdscr.attron(curses.color_pair(4) | curses.A_BOLD | curses.A_REVERSE)
                stdscr.addstr(btn_y, no_x, "  NO ")
                stdscr.attroff(curses.color_pair(4) | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

        try:
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(btn_y + 1, box_x + 2, "Left/Right to choose   Enter to confirm")
            stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()

        if key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            selected = 1 - selected
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            return selected == 0
        elif key in (ord('q'), ord('Q')):
            return False