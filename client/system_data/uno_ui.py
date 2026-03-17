import curses
import time
from system_data import play_classic as classic

COLOUR_PAIRS = {
    "red":    1,
    "green":  2,
    "blue":   3,
    "yellow": 5,
    "wild":   12,
}

COLOUR_ORDER    = ["red", "green", "blue", "yellow"]
COLOUR_PAIR_MAP = {"red": 1, "green": 2, "blue": 3, "yellow": 5}

DIRECTION_CLOCKWISE     = ["│", "│", "▼"]
DIRECTION_ANTICLOCKWISE = ["▲", "│", "│"]


def _init_game_colours():
    curses.init_pair(1,  curses.COLOR_RED,     -1)
    curses.init_pair(2,  curses.COLOR_GREEN,   -1)
    curses.init_pair(3,  curses.COLOR_BLUE,    -1)
    curses.init_pair(4,  curses.COLOR_CYAN,    -1)
    curses.init_pair(5,  curses.COLOR_YELLOW,  -1)
    curses.init_pair(12, curses.COLOR_WHITE,   -1)
    curses.init_pair(15, curses.COLOR_CYAN,    -1)


def _card_pair(card):
    return COLOUR_PAIRS.get(card[0], 12)


def _card_sym(card):
    return classic.CARD_SYMBOLS.get(card[1], card[1])


def _draw_header(stdscr, y, w):
    title = "UNO: TERMINAL EDITION"
    bar   = "=" * w
    try:
        stdscr.addstr(y,     0, bar)
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(y + 1, (w - len(title)) // 2, title)
        stdscr.attroff(curses.A_BOLD)
        stdscr.addstr(y + 2, 0, bar)
    except curses.error:
        pass
    return y + 3


def _draw_players(stdscr, state, y, panel_w, points_mode):
    direction = state["direction"]
    current   = state["current"]
    num       = state["num_players"]
    bots      = state["bots"]
    arrows    = DIRECTION_CLOCKWISE if direction == 1 else DIRECTION_ANTICLOCKWISE

    for i in range(num):
        arrow  = arrows[min(i, len(arrows) - 1)]
        hand   = state["hands"][i]
        count  = len(hand)
        name   = "YOU" if i == 0 else bots[i - 1]["name"]
        blocks = "⎕ " * count
        uno    = "  ← UNO!" if count == 1 else ""
        line   = f"{arrow}   {name}: {blocks}({count}){uno}"

        try:
            if i == current:
                stdscr.attron(curses.A_BOLD | curses.color_pair(4))
            stdscr.addstr(y + i, 0, line[:panel_w])
            if i == current:
                stdscr.attroff(curses.A_BOLD | curses.color_pair(4))
        except curses.error:
            pass

        if points_mode:
            try:
                stdscr.addstr(y + i, panel_w - 10, f"| {state['scores'][i]} pts")
            except curses.error:
                pass

    return y + num + 1


def _draw_divider(stdscr, y, w):
    try:
        stdscr.addstr(y, 0, "=" * w)
    except curses.error:
        pass
    return y + 1


def _draw_top_card(stdscr, state, y):
    top     = state["discard"][-1]
    active  = state["active_colour"]
    colour, value = top
    sym     = _card_sym(top)
    pair    = _card_pair(top)
    pending = state["pending_draw"]

    # if wild, show active colour instead of white
    display_pair = COLOUR_PAIR_MAP.get(active, 12) if colour == "wild" else pair

    label = "Current Card:   "
    try:
        stdscr.addstr(y, 2, label)
        stdscr.attron(curses.color_pair(display_pair) | curses.A_BOLD)
        stdscr.addstr(y, 2 + len(label), sym)
        stdscr.attroff(curses.color_pair(display_pair) | curses.A_BOLD)

        if colour == "wild":
            active_pair = COLOUR_PAIR_MAP.get(active, 12)
            stdscr.attron(curses.color_pair(active_pair))
            stdscr.addstr(y, 2 + len(label) + len(sym) + 1, f"({active})")
            stdscr.attroff(curses.color_pair(active_pair))

        if pending > 0:
            stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
            stdscr.addstr(y, 2 + len(label) + len(sym) + 14,
                          f"← Active (+{pending} to draw)")
            stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)
    except curses.error:
        pass

    return y + 2


def _build_hand_slots(hand, panel_w, scroll_offset):
    """
    Returns list of (card, x_position, visible) for rendering.
    Fixed width per slot so cards never shift.
    Also returns max_scroll.
    """
    SLOT_W    = 5   # fixed width per card slot " sym "
    DRAW_W    = 7   # " Draw "
    start_x   = 2
    available = panel_w - start_x - DRAW_W - 2

    slots_visible = max(1, available // SLOT_W)
    max_scroll    = max(0, len(hand) - slots_visible)
    scroll_offset = min(scroll_offset, max_scroll)

    slots = []
    for i, card in enumerate(hand):
        x = start_x + (i - scroll_offset) * SLOT_W
        visible = start_x <= x < start_x + slots_visible * SLOT_W
        slots.append((card, x, visible, i))

    draw_x = start_x + slots_visible * SLOT_W + 1
    return slots, draw_x, scroll_offset, max_scroll


def _draw_hand(stdscr, state, y, selected, uno_called, picking_colour, colour_idx, scroll_offset):
    hand     = state["hands"][0]
    top_card = state["discard"][-1]
    active   = state["active_colour"]
    rules    = state["rules"]
    pending  = state["pending_draw"]
    playable = classic.get_playable(hand, top_card, active, rules, pending)
    h, w     = stdscr.getmaxyx()
    panel_w  = w // 2

    SLOT_W = 5

    try:
        stdscr.addstr(y, 2, "Your hand:")
    except curses.error:
        pass
    y += 1

    slots, draw_x, scroll_offset, max_scroll = _build_hand_slots(hand, panel_w, scroll_offset)

    # row 1: card symbols — ALWAYS in their own colour, never greyed
    for card, x, visible, i in slots:
        if not visible:
            continue
        sym  = _card_sym(card)
        pair = _card_pair(card)
        can  = card in playable

        padded = f" {sym:<3}"

        # if picking colour for this card, show it in the chosen colour
        if picking_colour and i == selected:
            chosen_pair = COLOUR_PAIR_MAP.get(COLOUR_ORDER[colour_idx], 12)
            try:
                stdscr.attron(curses.color_pair(chosen_pair) | curses.A_BOLD)
                stdscr.addstr(y, x, padded)
                stdscr.attroff(curses.color_pair(chosen_pair) | curses.A_BOLD)
            except curses.error:
                pass
        else:
            # always render in card's own colour — dim or not doesn't change colour
            try:
                stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
                stdscr.addstr(y, x, padded)
                stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
            except curses.error:
                pass

    # Draw button
    try:
        if selected == len(hand) and not picking_colour:
            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(y, draw_x, ">Draw<")
            stdscr.attroff(curses.A_BOLD)
        else:
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(y, draw_x, " Draw ")
            stdscr.attroff(curses.A_DIM)
    except curses.error:
        pass

    y += 1

    # row 2: arrows — no colour picker here anymore
    for card, x, visible, i in slots:
        if not visible:
            continue
        can    = card in playable
        is_sel = (i == selected)
        try:
            if is_sel and not picking_colour:
                stdscr.attron(curses.A_BOLD)
                stdscr.addstr(y, x + 1, "^")
                stdscr.attroff(curses.A_BOLD)
            elif can and not is_sel:
                stdscr.attron(curses.color_pair(2))
                stdscr.addstr(y, x + 1, "↑")
                stdscr.attroff(curses.color_pair(2))
        except curses.error:
            pass

    # scroll indicators
    if scroll_offset > 0:
        try:
            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(y - 1, 0, "<")
            stdscr.attroff(curses.A_BOLD)
        except curses.error:
            pass
    if scroll_offset < max_scroll:
        try:
            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(y - 1, panel_w - 3, ">")
            stdscr.attroff(curses.A_BOLD)
        except curses.error:
            pass

    return y + 2, scroll_offset


def _draw_controls(stdscr, y, pending, uno_called, hand_size, picking_colour, selected_card=None):
    panel_w = 60  # keep controls within left panel only
    lines   = []

    if picking_colour:
        lines.append("Up/Down to pick colour   Enter to confirm")
    else:
        lines.append("Left/Right to select   Enter to play   D to draw   U for UNO   Q to quit")
        if hand_size == 2 and not uno_called:
            lines.append("Call UNO (U) before playing your second to last card!")
        if pending > 0:
            lines.append("Green ↑ cards can be stacked on the active draw card")

    try:
        for i, line in enumerate(lines):
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(y + i, 2, line[:panel_w])
            stdscr.attroff(curses.A_DIM)
    except curses.error:
        pass

    return y + len(lines) + 1


def _draw_sidebar(stdscr, state, selected, w, picking_colour, colour_idx):
    panel_x = w // 2 + 4
    pw      = w - panel_x - 2
    row     = 3

    hand     = state["hands"][0]
    top_card = state["discard"][-1]
    active   = state["active_colour"]
    rules    = state["rules"]
    pending  = state["pending_draw"]

    def sb_title(text):
        nonlocal row
        try:
            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(row, panel_x, text)
            stdscr.attroff(curses.A_BOLD)
        except curses.error:
            pass
        row += 1
        try:
            stdscr.addstr(row, panel_x, "-" * pw)
        except curses.error:
            pass
        row += 1

    def sb_line(label, value, pair=0):
        nonlocal row
        try:
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(row, panel_x, label)
            stdscr.attroff(curses.A_DIM)
            if pair:
                stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
            stdscr.addstr(row, panel_x + len(label), str(value))
            if pair:
                stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
        except curses.error:
            pass
        row += 1

    def sb_gap():
        nonlocal row
        row += 1

    direction = "Clockwise" if state["direction"] == 1 else "Anti-clockwise"

    sb_title("General Information:")
    sb_line("Direction:       ", direction)
    sb_line("Cards in deck:   ", len(state["deck"]))
    sb_line("Cards played:    ", len(state["discard"]))
    sb_line("Win condition:   ", state["game"]["win_condition"].capitalize())
    sb_gap()

    top_sym  = classic.CARD_SYMBOLS.get(top_card[1], top_card[1])
    top_pair = COLOUR_PAIR_MAP.get(active, 12) if top_card[0] == "wild" else _card_pair(top_card)
    sb_title("Active Card:")
    try:
        stdscr.attron(curses.color_pair(top_pair) | curses.A_BOLD)
        stdscr.addstr(row, panel_x, top_sym)
        stdscr.attroff(curses.color_pair(top_pair) | curses.A_BOLD)
    except curses.error:
        pass
    row += 1

    if pending > 0:
        sb_line("Pending draw:    ", f"+{pending} cards")

    chain = [
        classic.CARD_SYMBOLS.get(c[1], c[1])
        for c in reversed(state["discard"])
        if c[1] in ("draw_two", "draw_four")
    ]
    if chain:
        sb_line("Draw chain:      ", " → ".join(chain[:6]))
    sb_gap()

    # colour picker in sidebar when picking
    if picking_colour:
        sb_title("Choose Colour:")
        for ci, col in enumerate(COLOUR_ORDER):
            cpair = COLOUR_PAIR_MAP[col]
            try:
                if ci == colour_idx:
                    stdscr.attron(curses.color_pair(cpair) | curses.A_BOLD)
                    stdscr.addstr(row, panel_x, f"> {col.upper()}")
                    stdscr.attroff(curses.color_pair(cpair) | curses.A_BOLD)
                else:
                    stdscr.attron(curses.color_pair(cpair))
                    stdscr.addstr(row, panel_x, f"  {col.upper()}")
                    stdscr.attroff(curses.color_pair(cpair))
            except curses.error:
                pass
            row += 1
        sb_gap()
        try:
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(row, panel_x, "Up/Down to select")
            row += 1
            stdscr.addstr(row, panel_x, "Enter to confirm")
            stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass
        return

    sb_title("Selected Card:")
    if selected < len(hand):
        card        = hand[selected]
        colour, val = card
        sym         = classic.CARD_SYMBOLS.get(val, val)
        pair        = _card_pair(card)
        can         = card in classic.get_playable(hand, top_card, active, rules, pending)
        pts         = classic.card_points(card)

        try:
            stdscr.attron(curses.color_pair(pair) | curses.A_BOLD)
            stdscr.addstr(row, panel_x, sym)
            stdscr.attroff(curses.color_pair(pair) | curses.A_BOLD)
        except curses.error:
            pass
        row += 1

        if can:
            sb_line("Status:          ", "Can be played", pair=2)
        else:
            sb_line("Status:          ", "Must draw or stack" if pending > 0 else "Cannot be played", pair=4)

        if state["game"]["win_condition"] == "points":
            sb_line("Points value:    ", f"+{pts}")
        sb_gap()

        explanations = {
            "skip":      "Skips the next player's turn.",
            "reverse":   "Reverses the direction of play.",
            "draw_two":  "Next player draws 2 cards.",
            "draw_four": "Next player draws 4. You pick the colour.",
            "wild":      "Change the active colour to any colour.",
        }
        if val in explanations:
            words = explanations[val].split()
            line  = ""
            for word in words:
                if len(line) + len(word) + 1 > pw:
                    try:
                        stdscr.attron(curses.A_DIM)
                        stdscr.addstr(row, panel_x, line)
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
                    stdscr.addstr(row, panel_x, line)
                    stdscr.attroff(curses.A_DIM)
                except curses.error:
                    pass
    else:
        sb_line("", "Draw selected")


def _draw_log(stdscr, log, y, w):
    for i, entry in enumerate(log[-3:]):
        try:
            stdscr.attron(curses.A_DIM)
            stdscr.addstr(y + i, 2, entry[:w - 4])
            stdscr.attroff(curses.A_DIM)
        except curses.error:
            pass


def _draw_win_screen(stdscr, winner_name, points_earned, state):
    h, w = stdscr.getmaxyx()
    stdscr.clear()
    lines = ["", f"{winner_name} wins!", ""]
    if points_earned:
        lines += [f"+{points_earned} points", ""]
    lines += ["R - Play again", "M - Main menu", "Q - Quit"]

    start = h // 2 - len(lines) // 2
    for i, line in enumerate(lines):
        try:
            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(start + i, (w - len(line)) // 2, line)
            stdscr.attroff(curses.A_BOLD)
        except curses.error:
            pass

    stdscr.refresh()
    while True:
        key = stdscr.getch()
        if key in (ord('r'), ord('R')): return "replay"
        if key in (ord('m'), ord('M')): return "menu"
        if key in (ord('q'), ord('Q')): return "quit"


def run_game(stdscr, state):
    _init_game_colours()
    curses.curs_set(0)

    log            = []
    selected       = 0
    uno_called     = False
    picking_colour = False
    colour_idx     = 0
    scroll_offset  = 0

    def add_log(msg):
        log.append(msg)
        if len(log) > 50:
            log.pop(0)

    while True:
        h, w        = stdscr.getmaxyx()
        panel_w     = w // 2
        points_mode = state["game"]["win_condition"] == "points"
        hand        = state["hands"][0]
        current     = state["current"]

        selected = min(selected, len(hand))

        # auto scroll to keep selected card visible
        SLOT_W         = 5
        slots_visible  = max(1, (panel_w - 2 - 7 - 2) // SLOT_W)
        if selected < scroll_offset:
            scroll_offset = selected
        elif selected < len(hand) and selected >= scroll_offset + slots_visible:
            scroll_offset = selected - slots_visible + 1
        scroll_offset = max(0, min(scroll_offset, max(0, len(hand) - slots_visible)))

        stdscr.clear()

        y = _draw_header(stdscr, 0, panel_w)
        y = _draw_players(stdscr, state, y + 1, panel_w, points_mode)
        y = _draw_divider(stdscr, y, panel_w)
        y += 1
        y = _draw_top_card(stdscr, state, y)
        y, scroll_offset = _draw_hand(stdscr, state, y, selected, uno_called,
                                       picking_colour, colour_idx, scroll_offset)
        y = _draw_controls(stdscr, y, state["pending_draw"], uno_called,
                           len(hand), picking_colour)
        _draw_log(stdscr, log, h - 5, panel_w)
        _draw_sidebar(stdscr, state, selected, w, picking_colour, colour_idx)

        stdscr.refresh()

        # ── Bot turn ──────────────────────────────────────────────────────
        if current != 0 and not picking_colour:
            import system_data.bot as bot_ai
            bot    = state["bots"][current - 1]
            result = bot_ai.bot_turn(state, current, bot["difficulty"])
            name   = bot["name"]

            if result["action"] == "played":
                card = result["card"]
                sym  = classic.CARD_SYMBOLS.get(card[1], card[1])
                col  = result.get("chosen_colour", "")
                msg  = f"{name} played {sym}"
                if col: msg += f" → calls {col}"
                add_log(msg)
            elif result["action"] == "drew":
                amt = result.get("amount", 1)
                add_log(f"{name} drew {amt} card{'s' if amt != 1 else ''}")
            elif result["action"] == "won":
                pts    = classic.calculate_scores(state, current) if points_mode else None
                action = _draw_win_screen(stdscr, name, pts, state)
                return action

            time.sleep(0.4)
            continue

        key = stdscr.getch()

# ── Colour picking mode ───────────────────────────────────────────
        if picking_colour:
            if key == curses.KEY_UP:
                colour_idx = (colour_idx - 1) % 4
            elif key == curses.KEY_DOWN:
                colour_idx = (colour_idx + 1) % 4
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
                # moving left/right cancels and navigates normally
                picking_colour = False
                colour_idx     = 0
                if key == curses.KEY_LEFT:
                    selected = max(0, selected - 1)
                else:
                    selected = min(len(hand), selected + 1)
            elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                chosen_colour  = COLOUR_ORDER[colour_idx]
                picking_colour = False
                colour_idx     = 0
                card           = hand[selected]
                result         = classic.play_turn(state, 0, card_idx=selected,
                                                   chosen_colour=chosen_colour)
                if result["action"] == "won":
                    pts    = classic.calculate_scores(state, 0) if points_mode else None
                    action = _draw_win_screen(stdscr, "You", pts, state)
                    return action
                sym = classic.CARD_SYMBOLS.get(card[1], card[1])
                add_log(f"You played {sym} → calls {chosen_colour}")
                uno_called    = False
                selected      = min(selected, len(hand) - 1)
                scroll_offset = max(0, scroll_offset - 1)
            continue

        # ── Normal navigation ─────────────────────────────────────────────
        if key == curses.KEY_LEFT:
            selected = max(0, selected - 1)

        elif key == curses.KEY_RIGHT:
            selected = min(len(hand), selected + 1)

        elif key in (ord('d'), ord('D')):
            result = classic.play_turn(state, 0, card_idx=None)
            if result["action"] == "drew":
                card = result.get("card")
                add_log(f"You drew {classic.CARD_SYMBOLS.get(card[1], card[1]) if card else result.get('amount', 1)}")
            elif result["action"] == "force_played":
                add_log(f"Force played {classic.CARD_SYMBOLS.get(result['card'][1], result['card'][1])}")
            selected      = 0
            scroll_offset = 0
            uno_called    = False

        elif key in (ord('u'), ord('U')):
            if len(hand) == 2:
                uno_called = True
                add_log("You called UNO!")

        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            if selected == len(hand):
                result = classic.play_turn(state, 0, card_idx=None)
                if result["action"] == "drew":
                    card = result.get("card")
                    add_log(f"You drew {classic.CARD_SYMBOLS.get(card[1], card[1]) if card else '?'}")
                selected      = 0
                scroll_offset = 0
                uno_called    = False
            else:
                card    = hand[selected]
                rules   = state["rules"]
                pending = state["pending_draw"]

                if not classic.can_play(card, state["discard"][-1],
                                        state["active_colour"], rules, pending):
                    add_log("That card cannot be played right now")
                    continue

                if len(hand) == 2 and not uno_called:
                    add_log("Forgot to call UNO! Drawing 2 penalty cards...")
                    for _ in range(2):
                        hand.append(classic.draw_card(state["deck"], state["discard"]))
                    continue

                if card[0] == "wild":
                    picking_colour = True
                    colour_idx     = 0
                    add_log("Up/Down to pick colour, Enter to confirm, Left/Right to cancel")
                    continue

                result = classic.play_turn(state, 0, card_idx=selected)
                if result["action"] == "won":
                    pts    = classic.calculate_scores(state, 0) if points_mode else None
                    action = _draw_win_screen(stdscr, "You", pts, state)
                    return action
                if result["action"] == "played":
                    add_log(f"You played {classic.CARD_SYMBOLS.get(card[1], card[1])}")
                    uno_called    = False
                    selected      = min(selected, len(hand) - 1)
                    scroll_offset = max(0, scroll_offset - 1)

        elif key in (ord('q'), ord('Q')):
            return "menu"