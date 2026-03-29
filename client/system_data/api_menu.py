"""
api_menu.py — Curses menu system for UNO: Terminal Edition
===========================================================
Provides a context-manager menu API (``menu``) plus standalone input helpers.

Item types
----------
text(label)                             — non-selectable label row
multichoice(question, choices, default) — left/right to cycle, Enter to confirm
inline_number(label, current, min, max) — left/right or type to adjust

Rich text in sidebars
---------------------
Sidebar ``title``, ``heading``, and ``body`` strings all support inline
brace tags for colour and style::

    "heading": "{red}Warning:{/} this will reset your data"
    "body":    "Play as {bold}Red{/} or {green}Green{/}!"

Supported colour tags : red  green  blue  yellow  cyan  magenta  white
Supported style tags  : bold  dim
Reset tag             : {/}   (resets to the surrounding section style)

Sidebar format (passed as the `sidebars` dict or callable)
----------------------------------------------------------
Keys are the option label strings.  Each value is a sidebar dict::

    {
        "title":    "Sidebar {bold}heading{/}",
        "colour":   "green",           # one of: cyan green blue red yellow
        "sections": [
            {"heading": "{cyan}Sub-heading{/}", "body": "Body text here."},
            ...
        ]
    }

Example usage::

    def build_sidebars():
        return {
            "Single Player": {
                "title": "Modes available",
                "colour": "green",
                "sections": [
                    {"heading": "Vs {bold}Bot{/}",
                     "body": "Play against bots with adjustable difficulty!"},
                ]
            },
        }

    with menu("Main Menu", ["Single Player", "Quit"],
              color="cyan", sidebars=build_sidebars) as m:
        if m.is_selected("Single Player"):
            ...
"""

import os
import re

try:
    import curses
except ImportError:
    os.system("pip3 install windows-curses" if os.name == "nt" else "pip3 install curses")
    import curses


# ── Colour palette ────────────────────────────────────────────────────────────
# Maps colour name strings → curses colour-pair numbers.
# Must match the pairs registered in _init_curses().

COLOUR_NAME_TO_PAIR = {
    "cyan":    1,
    "green":   2,
    "blue":    3,
    "red":     4,
    "yellow":  5,
}

# ANSI escape → pair number (used when rendering coloured banners).
ANSI_TO_PAIR = {
    '\033[91m': 4,   # red
    '\033[93m': 5,   # yellow
    '\033[92m': 2,   # green
    '\033[94m': 3,   # blue
    '\033[96m': 1,   # cyan
    '\033[95m': 11,  # magenta
}

# Pair number used for the confirmed-value highlight (bright green tick).
PAIR_CONFIRMED = 13


# ── Item type sentinels ───────────────────────────────────────────────────────

TEXT_ITEM          = object()
MULTICHOICE_ITEM   = object()
INLINE_NUMBER_ITEM = object()


# ── Item constructors ─────────────────────────────────────────────────────────

def text(label: str) -> tuple:
    """Non-selectable label displayed between menu options."""
    return (TEXT_ITEM, label)


def multichoice(question: str, choices: dict, default=None) -> tuple:
    """
    Inline option row.  Left/Right to cycle through choices, Enter to confirm.

    Parameters
    ----------
    question : str   — label shown to the left of the choices
    choices  : dict  — {value: description} — description shown in the sidebar
    default  : str   — initially selected/confirmed value (defaults to first key)
    """
    return (MULTICHOICE_ITEM, question, choices, default)


def inline_number(label: str, current, min_val: int, max_val: int) -> tuple:
    """
    Inline numeric input.  Left/Right to adjust by 1, or type a number directly.

    Parameters
    ----------
    label   : str — label shown to the left of the value
    current : int — starting value
    min_val : int — minimum allowed value
    max_val : int — maximum allowed value
    """
    return (INLINE_NUMBER_ITEM, label, int(current), min_val, max_val)


# ── Global curses state ───────────────────────────────────────────────────────

_stdscr = None


def get_stdscr():
    """Return the active curses window, or None if curses is not running."""
    return _stdscr


def curses_control(type: str):
    """
    Manually start or stop the curses session.

    type : "start" — initialise curses
           "end"   — tear down curses cleanly
    """
    if type == "start":
        _init_curses()
    elif type == "end":
        _cleanup_curses()
        os.system("stty sane")


def _init_curses():
    """Initialise curses, register colour pairs, store the window globally."""
    global _stdscr
    stdscr = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    _stdscr = stdscr

    # ── Colour pairs ──────────────────────────────────────────────────────
    # Pairs 1-5 are the named menu colours (see COLOUR_NAME_TO_PAIR).
    curses.init_pair(1,  curses.COLOR_CYAN,    -1)
    curses.init_pair(2,  curses.COLOR_GREEN,   -1)
    curses.init_pair(3,  curses.COLOR_BLUE,    -1)
    curses.init_pair(4,  curses.COLOR_RED,     -1)
    curses.init_pair(5,  curses.COLOR_YELLOW,  -1)
    # Pairs 6-11 are used for ANSI banner colours.
    curses.init_pair(6,  curses.COLOR_RED,     -1)
    curses.init_pair(7,  curses.COLOR_YELLOW,  -1)
    curses.init_pair(8,  curses.COLOR_GREEN,   -1)
    curses.init_pair(9,  curses.COLOR_BLUE,    -1)
    curses.init_pair(10, curses.COLOR_CYAN,    -1)
    curses.init_pair(11, curses.COLOR_MAGENTA, -1)
    curses.init_pair(12, curses.COLOR_WHITE,   -1)
    # Pair 13 is the confirmed-value green tick.
    curses.init_pair(13, curses.COLOR_GREEN,   -1)


def _cleanup_curses():
    """Restore the terminal to its normal state."""
    global _stdscr
    if _stdscr:
        _stdscr.keypad(False)
        curses.nocbreak()
        curses.echo()
        curses.endwin()
        _stdscr = None


# ── Internal draw helpers ─────────────────────────────────────────────────────

def _colour_pair(name: str, fallback: int = 1) -> int:
    """Resolve a colour name string to its curses pair number."""
    return COLOUR_NAME_TO_PAIR.get(name, fallback)


# ── Sidebar rich text engine ──────────────────────────────────────────────────
# Sidebar strings (title, heading, body) support inline brace tags:
#
#   {red}text{/}      — colour a span
#   {bold}text{/}     — bold a span
#   {dim}text{/}      — dim a span
#   {/}               — reset back to the surrounding base style
#
# Supported colour tags : red  green  blue  yellow  cyan  magenta  white
# Supported style tags  : bold  dim
#
# Tags can be combined: {bold}{red}warning!{/}{/}
# Only used inside _draw_custom_sidebar — option labels are plain strings.

_SIDEBAR_COLOUR_TAGS = {
    "red":     4,
    "green":   2,
    "blue":    3,
    "yellow":  5,
    "cyan":    1,
    "magenta": 11,
    "white":   12,
}

_SIDEBAR_STYLE_TAGS = {
    "bold": curses.A_BOLD,
    "dim":  curses.A_DIM,
}

# Matches {tagname} or {/}
_TAG_RE = re.compile(r'\{(/|[a-zA-Z]+)\}')


def _sidebar_addstr(stdscr, row: int, col: int, text: str, base_attr: int = 0) -> int:
    """
    Draw a sidebar string with inline {tag} formatting at (row, col).

    base_attr is the curses attribute active for the surrounding context
    (e.g. the section's default colour pair).  {/} resets back to this,
    not to zero, so the base style is preserved outside tagged spans.

    Returns the column position after the last character drawn.

    Tracks colour pair and style flags separately to avoid unreliable
    bit-masking of curses attribute integers.
    """
    # Decompose base_attr into a pair number (0 = none) and extra style flags.
    # We store them separately so we can swap the pair without touching styles.
    base_pair  = 0   # will be overridden if base_attr contains a pair
    base_style = base_attr  # keep all style bits; pair bits don't hurt addstr

    cur_pair  = base_pair
    cur_style = base_style

    def _attr():
        """Build the curses attr integer from current pair + style."""
        if cur_pair:
            return curses.color_pair(cur_pair) | cur_style
        return cur_style

    pos = 0
    for m in _TAG_RE.finditer(text):
        # Draw literal text before this tag.
        if m.start() > pos:
            chunk = text[pos:m.start()]
            try:
                attr = _attr()
                stdscr.attron(attr)
                stdscr.addstr(row, col, chunk)
                stdscr.attroff(attr)
                col += len(chunk)
            except curses.error:
                pass

        tag = m.group(1)
        if tag == "/":
            # Reset to the base context.
            cur_pair  = base_pair
            cur_style = base_style
        elif tag in _SIDEBAR_COLOUR_TAGS:
            cur_pair = _SIDEBAR_COLOUR_TAGS[tag]
        elif tag in _SIDEBAR_STYLE_TAGS:
            cur_style |= _SIDEBAR_STYLE_TAGS[tag]
        # Unrecognised tags are silently skipped.

        pos = m.end()

    # Draw any remaining text after the last tag.
    if pos < len(text):
        chunk = text[pos:]
        try:
            attr = _attr()
            stdscr.attron(attr)
            stdscr.addstr(row, col, chunk)
            stdscr.attroff(attr)
            col += len(chunk)
        except curses.error:
            pass

    return col


def _sidebar_plain(text: str) -> str:
    """Return the visible text of a sidebar string with all tags stripped."""
    return _TAG_RE.sub("", text)


def _draw_colored_banner(stdscr, banner: str, start_row: int) -> int:
    """
    Render a multi-line ANSI-coloured banner string.
    Returns the next free row after the banner.
    """
    row = start_row
    for line in banner.splitlines():
        if not line.strip():
            row += 1
            continue
        col      = 4
        segments = re.split(r'(\033\[\d+m)', line)
        cur_pair = 0
        for seg in segments:
            if seg in ANSI_TO_PAIR:
                cur_pair = ANSI_TO_PAIR[seg]
            elif seg == '\033[0m':
                cur_pair = 0
            elif seg:
                try:
                    if cur_pair:
                        stdscr.attron(curses.color_pair(cur_pair) | curses.A_BOLD)
                    stdscr.addstr(row, col, seg)
                    if cur_pair:
                        stdscr.attroff(curses.color_pair(cur_pair) | curses.A_BOLD)
                    col += len(seg)
                except curses.error:
                    pass
        row += 1
    return row


def _draw_custom_sidebar(stdscr, menu_pair: int, sidebar: dict):
    """
    Render a custom info sidebar on the right half of the screen.

    Parameters
    ----------
    stdscr    : curses window
    menu_pair : int   — fallback colour pair (the menu's own colour)
    sidebar   : dict  — {"title": str, "colour": str, "sections": [...]}

    The sidebar dict's "colour" key overrides menu_pair for the title/headings.
    If "colour" is absent or unrecognised, menu_pair is used instead.
    """
    h, w        = stdscr.getmaxyx()
    panel_x     = w // 2 + 4
    panel_width = w - panel_x - 2
    row         = 3

    title       = sidebar.get("title", "")
    colour_name = sidebar.get("colour", "")
    # Use the sidebar's own colour if valid, otherwise fall back to the menu colour.
    title_pair  = _colour_pair(colour_name, fallback=menu_pair)
    title_attr  = curses.color_pair(title_pair) | curses.A_BOLD

    # ── Title ─────────────────────────────────────────────────────────────
    _sidebar_addstr(stdscr, row, panel_x, title, base_attr=title_attr)
    row += 1

    try:
        stdscr.addstr(row, panel_x, "─" * panel_width)
    except curses.error:
        pass
    row += 2

    # ── Sections ──────────────────────────────────────────────────────────
    for section in sidebar.get("sections", []):
        heading = section.get("heading", "")
        body    = section.get("body", "")

        if heading:
            _sidebar_addstr(stdscr, row, panel_x, heading, base_attr=title_attr)
            row += 1

        if body:
            # Word-wrap the body, splitting on plain visible characters.
            # Tags are not split across lines — whole words (including any
            # tags they contain) move together.
            plain_words = _sidebar_plain(body).split()
            # Rebuild word list paired with their original tagged versions.
            # Strategy: split on whitespace boundaries in the original string,
            # then strip leading/trailing whitespace from each chunk.
            raw_words = [w for w in re.split(r'(\s+)', body) if w.strip()]
            line_plain  = ""
            line_raw    = []

            for raw_word, plain_word in zip(raw_words, plain_words):
                if line_plain and len(line_plain) + 1 + len(plain_word) > panel_width:
                    # Flush current line
                    col = panel_x
                    for segment in line_raw:
                        col = _sidebar_addstr(stdscr, row, col, segment,
                                              base_attr=curses.A_DIM)
                    row     += 1
                    line_plain = plain_word
                    line_raw   = [raw_word]
                else:
                    if line_plain:
                        line_plain += " " + plain_word
                        line_raw.append(" " + raw_word)
                    else:
                        line_plain = plain_word
                        line_raw   = [raw_word]

            # Flush final line
            if line_raw:
                col = panel_x
                for segment in line_raw:
                    col = _sidebar_addstr(stdscr, row, col, segment,
                                          base_attr=curses.A_DIM)
                row += 1

        row += 1   # blank line between sections


def _draw_mc_sidebar(stdscr, menu_pair: int, selected_item: tuple,
                     mc_values: dict, mc_confirmed: dict):
    """
    Render the multichoice option sidebar showing all choices and their
    descriptions, with hover and confirmed-value highlighting.
    Only renders if selected_item is a MULTICHOICE_ITEM tuple.
    """
    if not (isinstance(selected_item, tuple) and selected_item[0] is MULTICHOICE_ITEM):
        return

    _, question, choices, _ = selected_item
    h, w        = stdscr.getmaxyx()
    panel_x     = w // 2 + 4
    panel_width = w - panel_x - 2
    row         = 3

    try:
        stdscr.attron(curses.color_pair(menu_pair) | curses.A_BOLD)
        stdscr.addstr(row, panel_x, "Options")
        stdscr.attroff(curses.color_pair(menu_pair) | curses.A_BOLD)
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
                stdscr.attron(curses.color_pair(menu_pair) | curses.A_BOLD)
                stdscr.addstr(row, panel_x, f"{arrow}{value.upper()} ✓")
                stdscr.attroff(curses.color_pair(menu_pair) | curses.A_BOLD)
            elif is_confirmed:
                stdscr.attron(curses.color_pair(PAIR_CONFIRMED) | curses.A_BOLD)
                stdscr.addstr(row, panel_x, f"  {value.upper()} ✓")
                stdscr.attroff(curses.color_pair(PAIR_CONFIRMED) | curses.A_BOLD)
            elif is_hovered:
                stdscr.attron(curses.color_pair(menu_pair) | curses.A_BOLD)
                stdscr.addstr(row, panel_x, f"{arrow}{value.upper()}")
                stdscr.attroff(curses.color_pair(menu_pair) | curses.A_BOLD)
            else:
                stdscr.attron(curses.A_DIM)
                stdscr.addstr(row, panel_x, f"  {value.upper()}")
                stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass
        row += 1

        # Word-wrap the description under the choice.
        line = ""
        for word in description.split():
            if len(line) + len(word) + 1 > panel_width:
                try:
                    stdscr.attron(curses.A_DIM)
                    stdscr.addstr(row, panel_x + 2, line)
                    stdscr.attroff(curses.A_DIM)
                except curses.error:
                    pass
                row += 1
                line = word
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


# ── Core menu renderer ────────────────────────────────────────────────────────

def _show(title: str, options: list, color: str, banner=None,
          sidebars=None, dev: bool = False, on_change=None):
    """
    Render and run the interactive menu loop.

    Parameters
    ----------
    title    : str   — heading shown above the options
    options  : list  — mix of strings, text(), multichoice(), inline_number()
    color    : str   — accent colour name (see COLOUR_NAME_TO_PAIR)
    banner   : str   — optional ANSI art printed above the title
    sidebars : dict or callable → dict
                 Keys are option label strings.
                 Values are sidebar dicts (see _draw_custom_sidebar).
                 Pass a callable to rebuild the sidebar dict every frame
                 (useful when sidebar content depends on in_values).
    dev      : bool  — show debug info on row 0
    on_change: callable(label, value) — called when an inline_number changes

    Returns
    -------
    (selected_idx, mc_confirmed, in_values)
    """
    # Resolve sidebars to a callable so we always call it the same way.
    sidebars_fn = sidebars if callable(sidebars) else (lambda: sidebars or {})
    pair        = _colour_pair(color)

    # ── Initialise item state ─────────────────────────────────────────────
    items        = []
    mc_values    = {}   # question → currently-hovered value
    mc_confirmed = {}   # question → confirmed value
    in_values    = {}   # label → current int value
    in_typed     = {}   # label → partially-typed string

    for opt in options:
        if isinstance(opt, tuple):
            if opt[0] is TEXT_ITEM:
                items.append(opt)
            elif opt[0] is MULTICHOICE_ITEM:
                _, question, choices, default = opt
                keys                   = list(choices.keys())
                current                = default if default in choices else keys[0]
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

    # Only string items and interactive tuples are selectable; text() labels are not.
    selectable = [i for i, o in enumerate(items)
                  if not (isinstance(o, tuple) and o[0] is TEXT_ITEM)]
    if not selectable:
        return None, {}, {}

    sel_pos = 0   # index into `selectable`

    # ── Render + input loop ───────────────────────────────────────────────
    while True:
        stdscr          = _stdscr
        active_sidebars = sidebars_fn()   # rebuilt every frame
        stdscr.clear()

        row = 1
        if banner:
            row = _draw_colored_banner(stdscr, banner, row)
            row += 1

        # Title
        try:
            stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
            stdscr.addstr(row, 4, title)
            stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
        except curses.error:
            pass
        row += 2

        selected_idx  = selectable[sel_pos]
        selected_item = items[selected_idx]

        # ── Debug overlay ─────────────────────────────────────────────────
        if dev:
            try:
                stdscr.addstr(0, 0,
                    f"hover: '{selected_item}' | sidebar keys: {list(active_sidebars.keys())}")
            except curses.error:
                pass

        # ── Sidebar ───────────────────────────────────────────────────────
        # Priority: multichoice gets its own sidebar; otherwise look up by label.
        if isinstance(selected_item, tuple) and selected_item[0] is MULTICHOICE_ITEM:
            _draw_mc_sidebar(stdscr, pair, selected_item, mc_values, mc_confirmed)

        elif isinstance(selected_item, tuple) and selected_item[0] is INLINE_NUMBER_ITEM:
            _, label, _, _, _ = selected_item
            if label in active_sidebars:
                _draw_custom_sidebar(stdscr, pair, active_sidebars[label])

        elif isinstance(selected_item, str) and selected_item in active_sidebars:
            _draw_custom_sidebar(stdscr, pair, active_sidebars[selected_item])

        # ── Option rows ───────────────────────────────────────────────────
        cumulative_offset = 0   # extra rows consumed by inline_number hints
        for i, item in enumerate(items):
            y         = row + i + cumulative_offset
            is_focused = (i == selected_idx)

            if isinstance(item, tuple) and item[0] is TEXT_ITEM:
                # Non-selectable label
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
                choice_keys   = list(choices.keys())
                prefix        = "  > " if is_focused else "    "

                # Question label
                prefix = "  > " if is_focused else "    "
                try:
                    if is_focused:
                        stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                    stdscr.addstr(y, 4, f"{prefix}{question}   ")
                    if is_focused:
                        stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
                except curses.error:
                    pass

                # Inline choice tokens
                col = 4 + len(prefix) + len(question) + 3
                for k in choice_keys:
                    is_k_confirmed = (k == confirmed_val)
                    is_k_hovered   = (k == current_val) and is_focused

                    if is_k_hovered and is_k_confirmed:
                        attr  = curses.color_pair(pair) | curses.A_BOLD
                        token = f"[{k}]"
                    elif is_k_confirmed:
                        attr  = curses.color_pair(PAIR_CONFIRMED) | curses.A_BOLD
                        token = f"[{k}]"
                    elif is_k_hovered:
                        attr  = curses.color_pair(pair) | curses.A_BOLD
                        token = f"[{k}]"
                    else:
                        attr  = curses.A_DIM
                        token = f" {k} "

                    try:
                        stdscr.attron(attr)
                        stdscr.addstr(y, col, token)
                        stdscr.attroff(attr)
                    except curses.error:
                        pass
                    col += len(token) + 1

            elif isinstance(item, tuple) and item[0] is INLINE_NUMBER_ITEM:
                _, label, _, min_val, max_val = item
                val     = in_values[label]
                typed   = in_typed[label]
                display = typed if typed else str(val)
                prefix = "  > " if is_focused else "    "
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
                        stdscr.addstr(y + 1, 4,
                            f"       Left/Right to adjust or type a number"
                            f"   (min: {min_val}, max: {max_val})")
                        stdscr.attroff(curses.A_DIM)
                    except curses.error:
                        pass
                    cumulative_offset += 1

            else:
                # Plain string option
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

        # ── Input handling ────────────────────────────────────────────────
        is_mc = isinstance(selected_item, tuple) and selected_item[0] is MULTICHOICE_ITEM
        is_in = isinstance(selected_item, tuple) and selected_item[0] is INLINE_NUMBER_ITEM

        if key == curses.KEY_UP and sel_pos > 0:
            sel_pos -= 1

        elif key == curses.KEY_DOWN and sel_pos < len(selectable) - 1:
            sel_pos += 1

        elif is_in:
            _, label, _, min_val, max_val = selected_item
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
            _, question, choices, _ = selected_item
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


# ── Standalone input helpers ──────────────────────────────────────────────────

def number_input(stdscr, prompt: str, current, min_val: int, max_val: int,
                 pair: int) -> int:
    """
    Full-screen numeric input prompt.  Left/Right to nudge, type to enter.
    Returns the confirmed integer value.
    """
    val   = int(current)
    typed = ""

    while True:
        stdscr = _stdscr
        stdscr.clear()

        try:
            stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
            stdscr.addstr(2, 4, prompt)
            stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
        except curses.error:
            pass

        display = typed if typed else str(val)
        try:
            stdscr.addstr(4, 4, f"  < {display} >")
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(6, 4,
                f"Left/Right to adjust   |   Type a number   |   "
                f"Enter to confirm   (min: {min_val}, max: {max_val})")
            stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass
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


def text_input(stdscr, prompt: str, current: str, pair: int) -> str:
    """
    Full-screen text input prompt.  Type to edit, Backspace to delete.
    Returns the confirmed string (max 20 characters).
    """
    curses.curs_set(1)
    val = list(current)

    while True:
        stdscr = _stdscr
        stdscr.clear()

        try:
            stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
            stdscr.addstr(2, 4, prompt)
            stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
            stdscr.addstr(4, 4, f"  {''.join(val)}_")
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(6, 4,
                "Type to edit   |   Backspace to delete   |   Enter to confirm")
            stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            curses.curs_set(0)
            return "".join(val)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if val:
                val.pop()
        elif 32 <= key <= 126:
            if len(val) < 20:
                val.append(chr(key))


# ── menu context manager ──────────────────────────────────────────────────────

class menu:
    """
    Context manager for displaying an interactive curses menu.

    The outermost ``menu`` in a nested stack owns the curses session —
    it starts curses on entry and cleans up on exit.  Inner menus reuse
    the existing session.

    Usage::

        with menu("Title", ["Option A", "Option B"], color="cyan",
                  sidebars=my_sidebar_dict) as m:
            if m.is_selected("Option A"):
                do_something()
            bots = m.get_number("Number of bots")

    Parameters
    ----------
    title     : str
    options   : list   — strings, text(), multichoice(), inline_number()
    color     : str    — accent colour (cyan / green / blue / red / yellow)
    banner    : str    — optional ANSI art displayed above the title
    sidebars  : dict or callable
                   Keys match option label strings.  Values are sidebar dicts::

                       {
                           "title":    "Heading",
                           "colour":   "green",
                           "sections": [
                               {"heading": "Sub", "body": "Description text."},
                           ]
                       }

                   Pass a callable for dynamic sidebars that depend on
                   the current in_values state.
    dev       : bool   — show hover/key debug info on row 0
    on_change : callable(label, value) — called when an inline_number changes
    """

    _stack = []

    def __init__(self, title: str, options: list, color: str = "cyan",
                 banner: str = None, sidebars=None,
                 dev: bool = False, on_change=None):
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
            self.title, self.options, self.color,
            self.banner, self.sidebars, self.dev, self.on_change,
        )
        return self

    def __exit__(self, *args):
        menu._stack.pop()
        if self._is_root:
            _cleanup_curses()

    def is_selected(self, label) -> bool:
        """Return True if the user pressed Enter on this option label."""
        if isinstance(label, tuple):
            return False
        try:
            idx = self.options.index(label)
        except ValueError:
            return False
        return self.selected == idx

    def get_value(self, question: str):
        """Return the confirmed value for a multichoice question."""
        return self.values.get(question)

    def get_number(self, label: str):
        """Return the current value for an inline_number field."""
        return self.in_values.get(label)