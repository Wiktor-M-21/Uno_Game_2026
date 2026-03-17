import os
try:
    import curses
except ImportError:
    os.system("pip3 install windows-curses" if os.name == "nt" else "pip3 install curses")
    import curses    
import re

ANSI_TO_PAIR = {
    '\033[91m': 6,
    '\033[93m': 7,
    '\033[92m': 8,
    '\033[94m': 9,
    '\033[96m': 10,
    '\033[95m': 11,
}

_stdscr = None

TEXT_ITEM          = object()
MULTICHOICE_ITEM   = object()
INLINE_NUMBER_ITEM = object()


def text(label):
    return (TEXT_ITEM, label)


def multichoice(question, choices, default=None):
    return (MULTICHOICE_ITEM, question, choices, default)


def inline_number(label, current, min_val, max_val):
    return (INLINE_NUMBER_ITEM, label, int(current), min_val, max_val)


def get_stdscr():
    return _stdscr


def curses_control(type):
    if type == "end":
        global _stdscr
        if _stdscr:
            _stdscr.keypad(False)
        curses.nocbreak()
        curses.echo()
        curses.endwin()
        os.system("stty sane")
    elif type == "start":
        _init_curses()


def _init_curses():
    global _stdscr
    stdscr = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    _stdscr = stdscr

    curses.init_pair(1,  curses.COLOR_CYAN,    -1)
    curses.init_pair(2,  curses.COLOR_GREEN,   -1)
    curses.init_pair(3,  curses.COLOR_BLUE,    -1)
    curses.init_pair(4,  curses.COLOR_RED,     -1)
    curses.init_pair(5,  curses.COLOR_YELLOW,  -1)
    curses.init_pair(6,  curses.COLOR_RED,     -1)
    curses.init_pair(7,  curses.COLOR_YELLOW,  -1)
    curses.init_pair(8,  curses.COLOR_GREEN,   -1)
    curses.init_pair(9,  curses.COLOR_BLUE,    -1)
    curses.init_pair(10, curses.COLOR_CYAN,    -1)
    curses.init_pair(11, curses.COLOR_MAGENTA, -1)
    curses.init_pair(12, curses.COLOR_WHITE,   -1)
    curses.init_pair(13, curses.COLOR_GREEN,   -1)


def _cleanup_curses():
    global _stdscr
    if _stdscr:
        _stdscr.keypad(False)
        curses.nocbreak()
        curses.echo()
        curses.endwin()
        _stdscr = None


def _draw_colored_banner(stdscr, banner, start_row):
    row = start_row
    for line in banner.splitlines():
        if not line.strip():
            row += 1
            continue
        col = 4
        segments = re.split(r'(\033\[\d+m)', line)
        current_pair = 0
        for seg in segments:
            if seg in ANSI_TO_PAIR:
                current_pair = ANSI_TO_PAIR[seg]
            elif seg == '\033[0m':
                current_pair = 0
            else:
                try:
                    if current_pair:
                        stdscr.attron(curses.color_pair(current_pair) | curses.A_BOLD)
                    stdscr.addstr(row, col, seg)
                    if current_pair:
                        stdscr.attroff(curses.color_pair(current_pair) | curses.A_BOLD)
                    col += len(seg)
                except curses.error:
                    pass
        row += 1
    return row


def _draw_custom_sidebar(stdscr, pair, sidebar):
    h, w        = stdscr.getmaxyx()
    panel_x     = w // 2 + 4
    panel_width = w - panel_x - 2
    row         = 3

    try:
        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
        stdscr.addstr(row, panel_x, sidebar.get("title", ""))
        stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
    except curses.error:
        pass
    row += 1

    try:
        stdscr.addstr(row, panel_x, "─" * panel_width)
    except curses.error:
        pass
    row += 2

    for section in sidebar.get("sections", []):
        heading = section.get("heading", "")
        if heading:
            try:
                stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                stdscr.addstr(row, panel_x, heading)
                stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
            except curses.error:
                pass
            row += 1

        body = section.get("body", "")
        if body:
            words = body.split()
            line  = ""
            for word in words:
                if len(line) + len(word) + 1 > panel_width:
                    try:
                        stdscr.attron(curses.A_DIM)
                        stdscr.addstr(row, panel_x, line)
                        stdscr.attroff(curses.A_DIM)
                    except curses.error:
                        pass
                    row += 1
                    line  = word
                else:
                    line = f"{line} {word}".strip()
            if line:
                try:
                    stdscr.attron(curses.A_DIM)
                    stdscr.addstr(row, panel_x, line)
                    stdscr.attroff(curses.A_DIM)
                except curses.error:
                    pass
                row += 1
        row += 1


def _draw_mc_sidebar(stdscr, pair, selected_item, mc_values, mc_confirmed):
    if not (isinstance(selected_item, tuple) and selected_item[0] is MULTICHOICE_ITEM):
        return

    _, question, choices, _ = selected_item
    h, w        = stdscr.getmaxyx()
    panel_x     = w // 2 + 4
    panel_width = w - panel_x - 2
    row         = 3

    try:
        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
        stdscr.addstr(row, panel_x, "Options")
        stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
    except curses.error:
        pass
    row += 1

    try:
        stdscr.addstr(row, panel_x, "─" * panel_width)
    except curses.error:
        pass
    row += 2

    current_val   = mc_values.get(question)
    confirmed_val = mc_confirmed.get(question)

    for value, description in choices.items():
        is_confirmed = (value == confirmed_val)
        is_hovered   = (value == current_val)
        arrow        = "> " if is_hovered else "  "

        try:
            if is_confirmed and is_hovered:
                stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                stdscr.addstr(row, panel_x, f"{arrow}{value.upper()} ✓")
                stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
            elif is_confirmed:
                stdscr.attron(curses.color_pair(13) | curses.A_BOLD)
                stdscr.addstr(row, panel_x, f"{arrow}{value.upper()} ✓")
                stdscr.attroff(curses.color_pair(13) | curses.A_BOLD)
            elif is_hovered:
                stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                stdscr.addstr(row, panel_x, f"{arrow}{value.upper()}")
                stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
            else:
                stdscr.attron(curses.A_DIM)
                stdscr.addstr(row, panel_x, f"{arrow}{value.upper()}")
                stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass
        row += 1

        words = description.split()
        line  = ""
        for word in words:
            if len(line) + len(word) + 1 > panel_width:
                try:
                    stdscr.attron(curses.A_DIM)
                    stdscr.addstr(row, panel_x + 2, line)
                    stdscr.attroff(curses.A_DIM)
                except curses.error:
                    pass
                row += 1
                line  = word
            else:
                line = f"{line} {word}".strip()
        if line:
            try:
                stdscr.attron(curses.A_DIM)
                stdscr.addstr(row, panel_x + 2, line)
                stdscr.attroff(curses.A_DIM)
            except curses.error:
                pass
            row += 1
        row += 1


def _show(title, options, color, banner=None, sidebars=None, dev=False, on_change=None):
    sidebars_fn = sidebars if callable(sidebars) else (lambda: sidebars or {})
    pair        = {"cyan": 1, "green": 2, "blue": 3, "red": 4, "yellow": 5}.get(color, 1)

    items        = []
    mc_values    = {}
    mc_confirmed = {}
    in_values    = {}
    in_typed     = {}

    for opt in options:
        if isinstance(opt, tuple):
            if opt[0] is TEXT_ITEM:
                items.append(opt)
            elif opt[0] is MULTICHOICE_ITEM:
                _, question, choices, default = opt
                choice_keys            = list(choices.keys())
                current                = default if default in choices else choice_keys[0]
                mc_values[question]    = current
                mc_confirmed[question] = current
                items.append(opt)
            elif opt[0] is INLINE_NUMBER_ITEM:
                _, label, current, min_val, max_val = opt
                in_values[label] = current
                in_typed[label]  = ""
                items.append(opt)
        else:
            items.append(opt)

    selectable = [i for i, o in enumerate(items)
                  if not (isinstance(o, tuple) and o[0] is TEXT_ITEM)]
    if not selectable:
        return None, {}, {}

    sel_pos = 0

    while True:
        stdscr          = _stdscr
        active_sidebars = sidebars_fn()  # fresh every frame
        stdscr.clear()
        row = 1

        if banner:
            row = _draw_colored_banner(stdscr, banner, row)
            row += 1

        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
        try:
            stdscr.addstr(row, 4, title)
        except curses.error:
            pass
        stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
        row += 2

        selected_idx            = selectable[sel_pos]
        currently_selected_item = items[selected_idx]

        if dev:
            try:
                stdscr.addstr(0, 0, f"hover: '{currently_selected_item}' | keys: {list(active_sidebars.keys())}")
            except curses.error:
                pass

        # draw sidebar
        if isinstance(currently_selected_item, tuple) and currently_selected_item[0] is MULTICHOICE_ITEM:
            _draw_mc_sidebar(stdscr, pair, currently_selected_item, mc_values, mc_confirmed)
        elif isinstance(currently_selected_item, tuple) and currently_selected_item[0] is INLINE_NUMBER_ITEM:
            _, label, _, _, _ = currently_selected_item
            if label in active_sidebars:
                _draw_custom_sidebar(stdscr, pair, active_sidebars[label])
        elif isinstance(currently_selected_item, str) and currently_selected_item in active_sidebars:
            _draw_custom_sidebar(stdscr, pair, active_sidebars[currently_selected_item])

        cumulative_offset = 0
        for i, item in enumerate(items):
            y = row + i + cumulative_offset

            if isinstance(item, tuple) and item[0] is TEXT_ITEM:
                try:
                    stdscr.attron(curses.A_DIM)
                    stdscr.addstr(y, 4, f"    {item[1]}")
                    stdscr.attroff(curses.A_DIM)
                except curses.error:
                    pass

            elif isinstance(item, tuple) and item[0] is MULTICHOICE_ITEM:
                _, question, choices, _ = item
                current_val   = mc_values[question]
                confirmed_val = mc_confirmed[question]
                is_focused    = (i == selected_idx)
                choice_keys   = list(choices.keys())

                prefix = "  > " if is_focused else "    "
                try:
                    if is_focused:
                        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                    stdscr.addstr(y, 4, f"{prefix}{question}   ")
                    if is_focused:
                        stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
                except curses.error:
                    pass

                col = 4 + len(prefix) + len(question) + 3
                for k in choice_keys:
                    is_confirmed = (k == confirmed_val)
                    is_hovered   = (k == current_val) and is_focused

                    if is_hovered and is_confirmed:
                        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                        token = f"[{k}]"
                    elif is_confirmed:
                        stdscr.attron(curses.color_pair(13) | curses.A_BOLD)
                        token = f"[{k}]"
                    elif is_hovered:
                        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                        token = f"[{k}]"
                    else:
                        stdscr.attron(curses.A_DIM)
                        token = f" {k} "

                    try:
                        stdscr.addstr(y, col, token)
                    except curses.error:
                        pass

                    stdscr.attroff(curses.color_pair(13) | curses.A_BOLD)
                    stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
                    stdscr.attroff(curses.A_DIM)
                    col += len(token) + 1

            elif isinstance(item, tuple) and item[0] is INLINE_NUMBER_ITEM:
                _, label, _, min_val, max_val = item
                is_focused = (i == selected_idx)
                val        = in_values[label]
                typed      = in_typed[label]
                display    = typed if typed else str(val)
                prefix     = "  > " if is_focused else "    "

                try:
                    if is_focused:
                        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                    stdscr.addstr(y, 4, f"{prefix}{label}   < {display} >")
                    if is_focused:
                        stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
                except curses.error:
                    pass

                if is_focused:
                    try:
                        stdscr.attron(curses.A_DIM)
                        stdscr.addstr(y + 1, 4, f"       Left/Right to adjust or type a number   (min: {min_val}, max: {max_val})")
                        stdscr.attroff(curses.A_DIM)
                    except curses.error:
                        pass
                    cumulative_offset += 1

            else:
                is_focused = (i == selected_idx)
                try:
                    if is_focused:
                        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                        stdscr.addstr(y, 4, f"  > {item}")
                        stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
                    else:
                        stdscr.addstr(y, 4, f"    {item}")
                except curses.error:
                    pass

        stdscr.refresh()
        key = stdscr.getch()

        item  = items[selected_idx]
        is_mc = isinstance(item, tuple) and item[0] is MULTICHOICE_ITEM
        is_in = isinstance(item, tuple) and item[0] is INLINE_NUMBER_ITEM

        if key == curses.KEY_UP and sel_pos > 0:
            sel_pos -= 1
        elif key == curses.KEY_DOWN and sel_pos < len(selectable) - 1:
            sel_pos += 1
        elif is_in:
            _, label, _, min_val, max_val = item
            changed = False
            if ord('0') <= key <= ord('9'):
                in_typed[label] += chr(key)
                parsed = int(in_typed[label])
                if parsed > max_val:
                    in_typed[label] = str(max_val)
                in_values[label] = max(min_val, min(max_val, int(in_typed[label])))
                changed = True
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                in_typed[label] = in_typed[label][:-1]
                if in_typed[label]:
                    in_values[label] = max(min_val, min(max_val, int(in_typed[label])))
                changed = True
            elif key == curses.KEY_LEFT:
                in_typed[label]  = ""
                in_values[label] = max(min_val, in_values[label] - 1)
                changed = True
            elif key == curses.KEY_RIGHT:
                in_typed[label]  = ""
                in_values[label] = min(max_val, in_values[label] + 1)
                changed = True
            if changed and on_change:
                on_change(label, in_values[label])
        elif is_mc:
            _, question, choices, _ = item
            keys = list(choices.keys())
            if key == curses.KEY_LEFT:
                idx = keys.index(mc_values[question])
                mc_values[question] = keys[(idx - 1) % len(keys)]
            elif key == curses.KEY_RIGHT:
                idx = keys.index(mc_values[question])
                mc_values[question] = keys[(idx + 1) % len(keys)]
            elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                mc_confirmed[question] = mc_values[question]
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            return selected_idx, mc_confirmed, in_values

    return selected_idx, mc_confirmed, in_values


def number_input(stdscr, prompt, current, min_val, max_val, pair):
    val   = int(current)
    typed = ""

    while True:
        stdscr = _stdscr
        stdscr.clear()
        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
        stdscr.addstr(2, 4, prompt)
        stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)

        display = typed if typed else str(val)
        stdscr.addstr(4, 4, f"  < {display} >")
        stdscr.attron(curses.A_DIM)
        stdscr.addstr(6, 4, f"Left/Right to adjust   |   Type a number   |   Enter to confirm   (min: {min_val}, max: {max_val})")
        stdscr.attroff(curses.A_DIM)
        stdscr.refresh()

        key = stdscr.getch()
        if ord('0') <= key <= ord('9'):
            typed += chr(key)
            parsed = int(typed)
            if parsed > max_val:
                typed = str(max_val)
            val = max(min_val, min(max_val, int(typed)))
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            typed = typed[:-1]
            if typed:
                val = max(min_val, min(max_val, int(typed)))
        elif key == curses.KEY_LEFT:
            typed = ""
            val   = max(min_val, val - 1)
        elif key == curses.KEY_RIGHT:
            typed = ""
            val   = min(max_val, val + 1)
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            return max(min_val, min(max_val, val))


def text_input(stdscr, prompt, current, pair):
    curses.curs_set(1)
    val = list(current)

    while True:
        stdscr = _stdscr
        stdscr.clear()
        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
        stdscr.addstr(2, 4, prompt)
        stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)

        display = "".join(val)
        stdscr.addstr(4, 4, f"  {display}_")
        stdscr.attron(curses.A_DIM)
        stdscr.addstr(6, 4, "Type to edit   |   Backspace to delete   |   Enter to confirm")
        stdscr.attroff(curses.A_DIM)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            curses.curs_set(0)
            return "".join(val)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if val: val.pop()
        elif 32 <= key <= 126:
            if len(val) < 20:
                val.append(chr(key))


class menu:
    _stack = []

    def __init__(self, title, options, color="cyan", banner=None, sidebars=None, dev=False, on_change=None):
        self.title     = title
        self.options   = options
        self.color     = color
        self.banner    = banner
        self.sidebars  = sidebars
        self.dev       = dev
        self.on_change = on_change
        self.selected  = None
        self.values    = {}
        self.in_values = {}
        self._is_root  = len(menu._stack) == 0

    def __enter__(self):
        if self._is_root:
            _init_curses()
        menu._stack.append(self)
        self.selected, self.values, self.in_values = _show(
            self.title, self.options, self.color, self.banner,
            self.sidebars, self.dev, self.on_change
        )
        return self

    def __exit__(self, *args):
        menu._stack.pop()
        if self._is_root:
            _cleanup_curses()

    def is_selected(self, label):
        if isinstance(label, tuple):
            return False
        try:
            idx = self.options.index(label)
        except ValueError:
            return False
        return self.selected == idx

    def get_value(self, question):
        return self.values.get(question)

    def get_number(self, label):
        return self.in_values.get(label)