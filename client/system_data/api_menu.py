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

_stdscr       = None
_terminal_mode = False   # When True, skip curses and use plain terminal rendering


def get_stdscr():
    """Return the active curses window, or None if curses is not running."""
    return _stdscr


def set_terminal_mode(enabled: bool):
    """Switch between curses UI and plain terminal UI (flag only, no session change)."""
    global _terminal_mode
    _terminal_mode = enabled


def switch_terminal_mode(enabled: bool):
    """
    Safely switch between curses UI and plain terminal UI mid-session.

    Unlike ``set_terminal_mode``, this also tears down or restarts the curses
    session immediately so the change takes effect on the next menu render.
    Safe to call from inside a nested menu stack — curses is only touched when
    the root is active (i.e. _stdscr is set or needs to be set).
    """
    global _terminal_mode
    if enabled == _terminal_mode:
        return  # already in the requested mode
    _terminal_mode = enabled
    if enabled:
        # Switching to terminal mode: tear curses down if it is running.
        if _stdscr is not None:
            _cleanup_curses()
            os.system("stty sane")
    else:
        # Switching to curses mode: start curses if not already running.
        os.system("cls" if os.name == "nt" else "clear")
        os.system("cls" if os.name == "nt" else "clear")
        if _stdscr is None:
            _init_curses()





def get_terminal_mode() -> bool:
    return _terminal_mode


def curses_control(type: str):
    """
    Manually start or stop the curses session.
    No-op when terminal mode is active.

    type : "start" — initialise curses
           "end"   — tear down curses cleanly
    """
    if _terminal_mode:
        return
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


def _draw_custom_sidebar(stdscr, menu_pair: int, sidebar: dict,
                         scroll_offset: int = 0) -> int:
    """
    Render a custom info sidebar on the right half of the screen.

    Parameters
    ----------
    stdscr        : curses window
    menu_pair     : int   — fallback colour pair (the menu's own colour)
    sidebar       : dict  — {"title": str, "colour": str, "sections": [...]}
    scroll_offset : int   — number of content rows to skip at the top

    Returns the total number of content rows (for scroll-limit calculation).

    The sidebar dict's "colour" key overrides menu_pair for the title/headings.
    If "colour" is absent or unrecognised, menu_pair is used instead.
    """
    h, w        = stdscr.getmaxyx()
    panel_x     = w // 2 + 4
    panel_width = w - panel_x - 2
    draw_row    = 3          # screen row we're currently writing to
    content_row = 0          # logical row index (before scroll)

    title       = sidebar.get("title", "")
    colour_name = sidebar.get("colour", "")
    title_pair  = _colour_pair(colour_name, fallback=menu_pair)
    title_attr  = curses.color_pair(title_pair) | curses.A_BOLD

    # ── Title (always visible, not scrollable) ─────────────────────────────
    _sidebar_addstr(stdscr, draw_row, panel_x, title, base_attr=title_attr)
    draw_row += 1
    try:
        stdscr.addstr(draw_row, panel_x, "─" * panel_width)
    except curses.error:
        pass
    draw_row += 2

    def _emit(text_str, attr):
        """Write one logical row, honouring scroll_offset and screen height."""
        nonlocal draw_row, content_row
        visible = (content_row >= scroll_offset) and (draw_row < h - 1)
        if visible:
            try:
                stdscr.attron(attr)
                stdscr.addstr(draw_row, panel_x, text_str[:panel_width])
                stdscr.attroff(attr)
            except curses.error:
                pass
            draw_row += 1
        content_row += 1

    # ── Sections ──────────────────────────────────────────────────────────
    for section in sidebar.get("sections", []):
        heading = section.get("heading", "")
        body    = section.get("body", "")

        if heading:
            visible = (content_row >= scroll_offset) and (draw_row < h - 1)
            if visible:
                _sidebar_addstr(stdscr, draw_row, panel_x, heading,
                                base_attr=title_attr)
                draw_row += 1
            content_row += 1

        if body:
            plain_words = _sidebar_plain(body).split()
            raw_words   = [w for w in re.split(r'(\s+)', body) if w.strip()]
            line_plain  = ""
            line_raw    = []

            for raw_word, plain_word in zip(raw_words, plain_words):
                if line_plain and len(line_plain) + 1 + len(plain_word) > panel_width:
                    visible = (content_row >= scroll_offset) and (draw_row < h - 1)
                    if visible:
                        col = panel_x
                        for segment in line_raw:
                            col = _sidebar_addstr(stdscr, draw_row, col, segment,
                                                  base_attr=curses.A_DIM)
                        draw_row += 1
                    content_row += 1
                    line_plain = plain_word
                    line_raw   = [raw_word]
                else:
                    if line_plain:
                        line_plain += " " + plain_word
                        line_raw.append(" " + raw_word)
                    else:
                        line_plain = plain_word
                        line_raw   = [raw_word]

            if line_raw:
                visible = (content_row >= scroll_offset) and (draw_row < h - 1)
                if visible:
                    col = panel_x
                    for segment in line_raw:
                        col = _sidebar_addstr(stdscr, draw_row, col, segment,
                                              base_attr=curses.A_DIM)
                    draw_row += 1
                content_row += 1

        # blank line between sections
        _emit("", curses.A_NORMAL)

    # Scroll hint at bottom of sidebar
    if scroll_offset > 0:
        try:
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(3, panel_x + panel_width - 6, "▲ ,..")
            stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass
    if content_row > scroll_offset + (h - 7):
        try:
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(h - 2, panel_x, "▼  . to scroll down")
            stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass

    return content_row   # total logical rows — used by caller to cap scroll


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

    sel_pos        = 0   # index into `selectable`
    scroll_offset  = 0   # first item index (into `items`) visible on screen
    sidebar_scroll = 0   # logical row offset for sidebar content

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
        sidebar_total = 0
        if isinstance(selected_item, tuple) and selected_item[0] is MULTICHOICE_ITEM:
            _draw_mc_sidebar(stdscr, pair, selected_item, mc_values, mc_confirmed)

        elif isinstance(selected_item, tuple) and selected_item[0] is INLINE_NUMBER_ITEM:
            _, label, _, _, _ = selected_item
            if label in active_sidebars:
                sidebar_total = _draw_custom_sidebar(
                    stdscr, pair, active_sidebars[label], sidebar_scroll)

        elif isinstance(selected_item, str) and selected_item in active_sidebars:
            sidebar_total = _draw_custom_sidebar(
                stdscr, pair, active_sidebars[selected_item], sidebar_scroll)

        # ── Option rows ───────────────────────────────────────────────────
        h, _w           = stdscr.getmaxyx()
        max_item_rows   = h - row - 2          # rows available for menu items
        cumulative_offset = 0
        item_row = 0   # logical row index within items list

        for i, item in enumerate(items):
            # Each item occupies at least 1 logical row; inline_number hint adds 1 more.
            item_height = 1
            if isinstance(item, tuple) and item[0] is INLINE_NUMBER_ITEM:
                if i == selected_idx:
                    item_height = 2

            # Skip items above scroll window
            if item_row < scroll_offset:
                item_row += item_height
                continue

            y = row + (item_row - scroll_offset) + cumulative_offset
            if y >= h - 1:
                break   # no more room on screen

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

            item_row += item_height

        # Scroll hints for option list
        if scroll_offset > 0:
            try:
                stdscr.attron(curses.A_DIM)
                stdscr.addstr(row - 1, 4, "▲ more above")
                stdscr.attroff(curses.A_DIM)
            except curses.error:
                pass
        if item_row > scroll_offset + max_item_rows:
            try:
                stdscr.attron(curses.A_DIM)
                stdscr.addstr(h - 2, 4, "▼ more below")
                stdscr.attroff(curses.A_DIM)
            except curses.error:
                pass

        stdscr.refresh()
        key = stdscr.getch()

        # ── Input handling ────────────────────────────────────────────────
        is_mc = isinstance(selected_item, tuple) and selected_item[0] is MULTICHOICE_ITEM
        is_in = isinstance(selected_item, tuple) and selected_item[0] is INLINE_NUMBER_ITEM

        if key == curses.KEY_UP and sel_pos > 0:
            sel_pos -= 1
            sidebar_scroll = 0   # reset sidebar scroll on navigation
            # Scroll up if cursor moves above the visible window
            cursor_item = selectable[sel_pos]
            if cursor_item < scroll_offset:
                scroll_offset = cursor_item

        elif key == curses.KEY_DOWN and sel_pos < len(selectable) - 1:
            sel_pos += 1
            sidebar_scroll = 0   # reset sidebar scroll on navigation
            # Scroll down if cursor moves below the visible window
            cursor_item = selectable[sel_pos]
            h2, _ = stdscr.getmaxyx()
            if cursor_item >= scroll_offset + (h2 - row - 2):
                scroll_offset = cursor_item - (h2 - row - 3)

        elif key == ord(','):
            sidebar_scroll = max(0, sidebar_scroll - 1)

        elif key == ord('.'):
            sidebar_scroll = min(max(0, sidebar_total - 1), sidebar_scroll + 1)

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


# ── Terminal-mode renderer ────────────────────────────────────────────────────

def _show_terminal(title: str, options: list, color: str, banner=None,
                   sidebars=None, dev: bool = False, on_change=None):
    """
    Plain-terminal equivalent of _show.
    Two-column layout: menu on the left, sidebar on the right.
    Uses shutil.get_terminal_size() so nothing ever wraps.
    """
    import shutil

    ANSI = {
        "cyan":    '\033[96m', "green":  '\033[92m', "blue":   '\033[94m',
        "red":     '\033[91m', "yellow": '\033[93m', "magenta": '\033[95m',
        "white":   '\033[97m',
    }
    RESET  = '\033[0m'
    BOLD   = '\033[1m'
    DIM    = '\033[2m'
    accent = ANSI.get(color, '\033[96m')

    sidebars_fn = sidebars if callable(sidebars) else (lambda: sidebars or {})

    # ── Build item state ──────────────────────────────────────────────────
    items        = []
    mc_values    = {}
    mc_confirmed = {}
    in_values    = {}

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
                items.append(opt)
        else:
            items.append(opt)

    selectable  = [i for i, o in enumerate(items)
                   if not (isinstance(o, tuple) and o[0] is TEXT_ITEM)]
    if not selectable:
        return None, {}, {}

    num_to_item = {n + 1: idx for n, idx in enumerate(selectable)}
    hover_num   = 1

    def _wrap(text: str, width: int) -> list:
        """Word-wrap plain text to a list of lines of at most `width` chars."""
        words, lines, line = text.split(), [], ""
        for w in words:
            if len(line) + len(w) + (1 if line else 0) > width:
                if line:
                    lines.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            lines.append(line)
        return lines or [""]

    def _pad(s: str, width: int) -> str:
        """Pad/truncate a plain string to exactly `width` chars."""
        visible = len(s)
        if visible >= width:
            return s[:width]
        return s + " " * (width - visible)

    while True:
        term_w   = shutil.get_terminal_size((80, 24)).columns

        os.system("cls" if os.name == "nt" else "clear")

        active_sidebars = sidebars_fn()

        # ── Print banner full-width above the two-column layout ───────────
        # Banner lines contain ANSI escapes whose byte length != visible width,
        # so they must never be sliced or padded — just print them raw.
        if banner:
            for line in banner.splitlines():
                print(line)
            print()

        # ── Build left column lines ───────────────────────────────────────
        left_lines = []

        left_lines.append(f"{accent}{BOLD}{title}{RESET}")
        left_lines.append("")

        n = 1
        for item in items:
            if isinstance(item, tuple) and item[0] is TEXT_ITEM:
                label = item[1]
                if label:
                    left_lines.append(f"{DIM}  {label[:term_w - 4]}{RESET}")
                else:
                    left_lines.append("")
            elif isinstance(item, tuple) and item[0] is MULTICHOICE_ITEM:
                _, question, choices, _ = item
                confirmed_val = mc_confirmed[question]
                tokens = ""
                for k in choices:
                    if k == confirmed_val:
                        tokens += f" {accent}[{k}]✓{RESET}"
                    else:
                        tokens += f" {DIM}{k}{RESET}"
                left_lines.append(f"  {accent}{n}.{RESET} {question}{tokens}")
                n += 1
            elif isinstance(item, tuple) and item[0] is INLINE_NUMBER_ITEM:
                _, label, _, min_val, max_val = item
                val    = in_values[label]
                left_lines.append(
                    f"  {accent}{n}.{RESET} {label}  "
                    f"{accent}< {val} >{RESET}  {DIM}({min_val}–{max_val}){RESET}"
                )
                n += 1
            else:
                left_lines.append(f"  {accent}{n}.{RESET} {item}")
                n += 1

        # ── Render menu lines ───────────────────────────────────────────
        for line in left_lines:
            print(line)

        # ── Render ALL sidebars below the menu ─────────────────────────
        if active_sidebars:
            any_printed = False
            for n_check, idx_check in num_to_item.items():
                it = items[idx_check]
                if isinstance(it, str):
                    sb_key = it
                elif isinstance(it, tuple) and it[0] in (MULTICHOICE_ITEM, INLINE_NUMBER_ITEM):
                    sb_key = it[1]
                else:
                    continue
                if sb_key not in active_sidebars:
                    continue
                sb       = active_sidebars[sb_key]
                sb_col   = ANSI.get(sb.get("colour", ""), accent)
                sb_title = _sidebar_plain(sb.get("title", ""))
                sections = sb.get("sections", [])
                if not sb_title and not sections:
                    continue
                if not any_printed:
                    print(f"\n{DIM}{chr(0x2500) * min(term_w, 60)}{RESET}")
                    any_printed = True
                label_str = f"[{n_check}]  {sb_title}" if sb_title else f"[{n_check}]"
                print(f"\n{sb_col}{BOLD}{label_str}{RESET}")
                wrap_w = min(term_w - 6, 70)
                for section in sections:
                    h_text = _sidebar_plain(section.get("heading", ""))
                    b_text = _sidebar_plain(section.get("body", ""))
                    if h_text:
                        print(f"  {sb_col}{h_text}{RESET}")
                    if b_text:
                        for wrapped_line in _wrap(b_text, wrap_w):
                            print(f"{DIM}    {wrapped_line}{RESET}")

        # ── Input ─────────────────────────────────────────────────────────
        print(f"\n{DIM}Enter number:{RESET} ", end="", flush=True)
        raw = input().strip()

        if not raw.isdigit():
            continue
        choice = int(raw)
        if choice not in num_to_item:
            continue

        hover_num    = choice
        item_idx     = num_to_item[choice]
        item         = items[item_idx]

        if isinstance(item, tuple) and item[0] is MULTICHOICE_ITEM:
            _, question, choices, _ = item
            keys = list(choices.keys())
            idx  = keys.index(mc_values[question])
            mc_values[question]    = keys[(idx + 1) % len(keys)]
            mc_confirmed[question] = mc_values[question]
            if on_change:
                on_change(question, mc_confirmed[question])
            continue

        if isinstance(item, tuple) and item[0] is INLINE_NUMBER_ITEM:
            _, label, _, min_val, max_val = item
            print(f"  New value for '{label}' "
                  f"(current: {in_values[label]}, {min_val}–{max_val}): ", end="")
            v = input().strip()
            if v.lstrip('-').isdigit():
                in_values[label] = max(min_val, min(max_val, int(v)))
            continue

        return item_idx, mc_confirmed, in_values


def terminal_confirm(prompt: str, warning: str = "") -> bool:
    """
    Plain-terminal equivalent of confirm_screen.
    Used automatically when terminal mode is active.
    """
    os.system("cls" if os.name == "nt" else "clear")
    print(f"\n  {prompt}")
    if warning:
        print(f"  \033[91m{warning}\033[0m")
    raw = input("\n  Confirm? (y/N): ").strip().lower()
    return raw == "y"


# ── Standalone input helpers ──────────────────────────────────────────────────

def number_input(stdscr, prompt: str, current, min_val: int, max_val: int,
                 pair: int) -> int:
    """
    Full-screen numeric input prompt.  Falls back to plain terminal when
    terminal mode is active.  Returns the confirmed integer value.
    """
    if _terminal_mode:
        os.system("cls" if os.name == "nt" else "clear")
        print(f"{prompt}  (current: {current}, min:{min_val} max:{max_val})")
        raw = input("Enter value: ").strip()
        if raw.lstrip('-').isdigit():
            return max(min_val, min(max_val, int(raw)))
        return int(current)
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
    Full-screen text input prompt.  Falls back to plain terminal when
    terminal mode is active.  Returns the confirmed string (max 20 chars).
    """
    if _terminal_mode:
        os.system("cls" if os.name == "nt" else "clear")
        print(f"{prompt}  (current: '{current}')")
        raw = input("Enter value: ").strip()
        return raw[:20] if raw else current
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


def multiline_input(title: str, initial: str, pair: int, readonly: bool = False) -> str:
    """
    Full-screen multi-line text editor.

    Arrow keys move the cursor.  Enter adds a newline.  Type normally to insert.
    Backspace deletes the character before the cursor.
    Ctrl+S (or Ctrl+X) saves and exits.  Escape cancels (returns original text).

    In readonly mode (e.g. for viewing update notes) only Escape / Ctrl+S exits.

    Falls back to a plain terminal viewer/editor when terminal mode is active.

    Returns the edited string, or `initial` if cancelled.
    """
    if _terminal_mode:
        os.system("cls" if os.name == "nt" else "clear")
        print(f"\n  {title}\n  {'─' * len(title)}\n")
        if readonly:
            for line in (initial or "(no notes)").splitlines():
                print(f"  {line}")
            input("\n  Press Enter to return...")
            return initial
        else:
            print(f"  Current notes:\n")
            for line in (initial or "").splitlines():
                print(f"    {line}")
            print("\n  Enter new notes (blank line + Enter to finish):\n")
            lines, line = [], ""
            while True:
                line = input("  ")
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            return "\n".join(lines).rstrip()

    stdscr = _stdscr
    curses.curs_set(1)

    # Split text into a list-of-lists (rows of chars)
    rows = [list(r) for r in initial.split("\n")]
    if not rows:
        rows = [[]]

    cur_row = 0
    cur_col = 0
    saved   = False

    def _clamp():
        nonlocal cur_row, cur_col
        cur_row = max(0, min(cur_row, len(rows) - 1))
        cur_col = max(0, min(cur_col, len(rows[cur_row])))

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        edit_area_top    = 4
        edit_area_bottom = h - 3
        edit_area_height = edit_area_bottom - edit_area_top

        # Title bar
        try:
            stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
            stdscr.addstr(1, 4, title[:w - 6])
            stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
            stdscr.addstr(2, 4, "─" * min(w - 8, 60))
        except curses.error:
            pass

        # Hint bar at bottom
        hint = "Ctrl+S to save  |  Esc to cancel" if not readonly else "Esc to close"
        try:
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(h - 2, 4, hint[:w - 6])
            stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass

        # Scroll so cursor row is always visible
        scroll = max(0, cur_row - edit_area_height + 1)

        # Render text rows
        for screen_r, row_idx in enumerate(range(scroll, scroll + edit_area_height)):
            y = edit_area_top + screen_r
            if y >= edit_area_bottom:
                break
            if row_idx < len(rows):
                line_text = "".join(rows[row_idx])[:(w - 6)]
                try:
                    stdscr.addstr(y, 4, line_text)
                except curses.error:
                    pass
            # Cursor
            if row_idx == cur_row:
                cursor_x = 4 + cur_col
                if cursor_x < w - 1:
                    try:
                        stdscr.move(y, cursor_x)
                    except curses.error:
                        pass

        stdscr.refresh()
        key = stdscr.getch()

        # Ctrl+S (19) or Ctrl+X (24)
        if key in (19, 24):
            saved = True
            break
        elif key == 27:  # Escape
            break
        elif readonly:
            continue
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            # Split current row at cursor
            rest = rows[cur_row][cur_col:]
            rows[cur_row] = rows[cur_row][:cur_col]
            rows.insert(cur_row + 1, rest)
            cur_row += 1
            cur_col  = 0
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if cur_col > 0:
                rows[cur_row].pop(cur_col - 1)
                cur_col -= 1
            elif cur_row > 0:
                # Merge with previous row
                cur_col = len(rows[cur_row - 1])
                rows[cur_row - 1].extend(rows[cur_row])
                rows.pop(cur_row)
                cur_row -= 1
        elif key == curses.KEY_UP:
            cur_row -= 1
            _clamp()
        elif key == curses.KEY_DOWN:
            cur_row += 1
            _clamp()
        elif key == curses.KEY_LEFT:
            if cur_col > 0:
                cur_col -= 1
            elif cur_row > 0:
                cur_row -= 1
                cur_col = len(rows[cur_row])
        elif key == curses.KEY_RIGHT:
            if cur_col < len(rows[cur_row]):
                cur_col += 1
            elif cur_row < len(rows) - 1:
                cur_row += 1
                cur_col  = 0
        elif key == curses.KEY_HOME:
            cur_col = 0
        elif key == curses.KEY_END:
            cur_col = len(rows[cur_row])
        elif 32 <= key <= 126:
            rows[cur_row].insert(cur_col, chr(key))
            cur_col += 1

    curses.curs_set(0)
    if saved:
        return "\n".join("".join(r) for r in rows)
    return initial


def backup_editor(pair: int, initial_title: str = "", initial_notes: str = ""):
    """
    Full-screen curses editor with two fields: backup title and notes.

    Tab / Shift-Tab switches focus between fields.
    F2 saves and exits.  Escape cancels (returns None, None).

    Returns (title_str, notes_str) on save, or (None, None) on cancel.
    """
    stdscr = _stdscr
    try:
        curses.curs_set(1)

        # ── Field state ───────────────────────────────────────────────────────
        title_chars = list(initial_title)
        notes_rows  = [list(r) for r in (initial_notes or "").split("\n")]
        if not notes_rows:
            notes_rows = [[]]

        focus    = 0   # 0 = title field, 1 = notes area
        t_col    = len(title_chars)   # cursor col in title
        n_row    = 0                  # cursor row in notes
        n_col    = 0                  # cursor col in notes
        n_scroll = 0                  # scroll offset for notes

        def _clamp_notes():
            nonlocal n_row, n_col
            n_row = max(0, min(n_row, len(notes_rows) - 1))
            n_col = max(0, min(n_col, len(notes_rows[n_row])))

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()

            # ── Chrome ────────────────────────────────────────────────────────
            try:
                stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                stdscr.addstr(1, 4, "Create Backup")
                stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
                stdscr.attron(curses.color_pair(pair))
                stdscr.addstr(2, 4, "─" * min(40, w - 8))
                stdscr.attroff(curses.color_pair(pair))
            except curses.error:
                pass

            hint = "Tab = switch field   F2 = save   Esc = cancel"
            try:
                stdscr.attron(curses.color_pair(pair) | curses.A_DIM)
                stdscr.addstr(h - 2, 4, hint[:w - 6])
                stdscr.attroff(curses.color_pair(pair) | curses.A_DIM)
            except curses.error:
                pass

            # ── Title field ───────────────────────────────────────────────────
            title_label_attr = (curses.color_pair(pair) | curses.A_BOLD) if focus == 0 else curses.A_DIM
            try:
                stdscr.attron(title_label_attr)
                stdscr.addstr(4, 4, "Title:")
                stdscr.attroff(title_label_attr)
            except curses.error:
                pass

            title_display = "".join(title_chars)[:(w - 14)]
            title_box_attr = curses.color_pair(pair) if focus == 0 else 0
            try:
                if focus == 0:
                    stdscr.attron(title_box_attr)
                stdscr.addstr(4, 11, title_display or " ")
                if focus == 0:
                    stdscr.attroff(title_box_attr)
            except curses.error:
                pass

            # ── Notes field ───────────────────────────────────────────────────
            notes_label_attr = (curses.color_pair(pair) | curses.A_BOLD) if focus == 1 else curses.A_DIM
            try:
                stdscr.attron(notes_label_attr)
                stdscr.addstr(6, 4, "Notes:")
                stdscr.attroff(notes_label_attr)
            except curses.error:
                pass

            notes_top    = 7
            notes_bottom = h - 4
            notes_height = notes_bottom - notes_top

            if focus == 1:
                n_scroll = max(0, n_row - notes_height + 1)

            for screen_r, row_idx in enumerate(range(n_scroll, n_scroll + notes_height)):
                y = notes_top + screen_r
                if y >= notes_bottom:
                    break
                if row_idx < len(notes_rows):
                    line_text = "".join(notes_rows[row_idx])[:(w - 8)]
                    try:
                        stdscr.addstr(y, 6, line_text)
                    except curses.error:
                        pass

            # ── Place cursor ──────────────────────────────────────────────────
            try:
                if focus == 0:
                    stdscr.move(4, 11 + min(t_col, w - 15))
                else:
                    cy = notes_top + (n_row - n_scroll)
                    cx = 6 + n_col
                    if notes_top <= cy < notes_bottom and cx < w - 1:
                        stdscr.move(cy, cx)
            except curses.error:
                pass

            stdscr.refresh()
            key = stdscr.getch()

            # ── Global keys ───────────────────────────────────────────────────
            if key == curses.KEY_F2:
                curses.curs_set(0)
                return "".join(title_chars), "\n".join("".join(r) for r in notes_rows)
            elif key == 27:  # Escape
                curses.curs_set(0)
                return None, None
            elif key == ord('\t'):  # Tab — switch focus
                focus = 1 - focus
                continue

            # ── Title field keys ──────────────────────────────────────────────
            if focus == 0:
                if key in (curses.KEY_BACKSPACE, 127, 8):
                    if title_chars:
                        title_chars.pop(t_col - 1)
                        t_col = max(0, t_col - 1)
                elif key == curses.KEY_LEFT:
                    t_col = max(0, t_col - 1)
                elif key == curses.KEY_RIGHT:
                    t_col = min(len(title_chars), t_col + 1)
                elif key == curses.KEY_HOME:
                    t_col = 0
                elif key == curses.KEY_END:
                    t_col = len(title_chars)
                elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                    focus = 1  # Enter moves to notes
                elif 32 <= key <= 126:
                    title_chars.insert(t_col, chr(key))
                    t_col += 1

            # ── Notes field keys ──────────────────────────────────────────────
            else:
                if key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                    rest = notes_rows[n_row][n_col:]
                    notes_rows[n_row] = notes_rows[n_row][:n_col]
                    notes_rows.insert(n_row + 1, rest)
                    n_row += 1
                    n_col  = 0
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    if n_col > 0:
                        notes_rows[n_row].pop(n_col - 1)
                        n_col -= 1
                    elif n_row > 0:
                        n_col = len(notes_rows[n_row - 1])
                        notes_rows[n_row - 1].extend(notes_rows[n_row])
                        notes_rows.pop(n_row)
                        n_row -= 1
                elif key == curses.KEY_UP:
                    n_row -= 1
                    _clamp_notes()
                elif key == curses.KEY_DOWN:
                    n_row += 1
                    _clamp_notes()
                elif key == curses.KEY_LEFT:
                    if n_col > 0:
                        n_col -= 1
                    elif n_row > 0:
                        n_row -= 1
                        n_col = len(notes_rows[n_row])
                elif key == curses.KEY_RIGHT:
                    if n_col < len(notes_rows[n_row]):
                        n_col += 1
                    elif n_row < len(notes_rows) - 1:
                        n_row += 1
                        n_col  = 0
                elif key == curses.KEY_HOME:
                    n_col = 0
                elif key == curses.KEY_END:
                    n_col = len(notes_rows[n_row])
                elif 32 <= key <= 126:
                    notes_rows[n_row].insert(n_col, chr(key))
                    n_col += 1
    except curses.error:
        print("Backup creation cancelled. Unable to create backup in terminal mode.")
        print("Disable terminal mode to use this feature.")
        input("Press Enter to continue...")
        return None, None

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
        if self._is_root and not _terminal_mode:
            _init_curses()
        menu._stack.append(self)
        renderer = _show_terminal if _terminal_mode else _show
        self.selected, self.values, self.in_values = renderer(
            self.title, self.options, self.color,
            self.banner, self.sidebars, self.dev, self.on_change,
        )
        return self

    def __exit__(self, *args):
        menu._stack.pop()
        if self._is_root and not _terminal_mode:
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