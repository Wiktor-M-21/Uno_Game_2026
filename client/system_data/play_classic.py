import random
import configparser
import os

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
SP_CONFIG_PATH = os.path.join(BASE_DIR, "sp_settings.ini")

# ── Card Display ──────────────────────────────────────────────────────────

CARD_SYMBOLS = {
    "reverse":   "⇄",
    "skip":      "⊘",
    "draw_two":  "+2",
    "draw_four": "+4",
    "wild":      "W",
}

COLOUR_ANSI = {
    "red":    "\033[91m",
    "green":  "\033[92m",
    "blue":   "\033[94m",
    "yellow": "\033[93m",
    "wild":   "\033[97m",
}

RESET = "\033[0m"


def card_display(card):
    colour, value = card
    symbol = CARD_SYMBOLS.get(value, value)
    ansi   = COLOUR_ANSI.get(colour, "\033[97m")
    return f"{ansi}{symbol}{RESET}"


def hand_display(hand):
    return "  ".join(f"[{i+1}] {card_display(card)}" for i, card in enumerate(hand))


def top_card_display(state):
    top    = state["discard"][-1]
    active = state["active_colour"]
    colour, value = top
    symbol = CARD_SYMBOLS.get(value, value)

    if colour == "wild":
        active_ansi = COLOUR_ANSI.get(active, "\033[97m")
        return f"\033[97m{symbol}{RESET} ({active_ansi}{active}{RESET})"
    return card_display(top)


# ── Load Settings ─────────────────────────────────────────────────────────

def load_settings():
    sp_config = configparser.ConfigParser()
    sp_config.read(SP_CONFIG_PATH)

    num_bots = int(sp_config.get("bots", "number_of_bots", fallback="1"))

    bots = []
    for i in range(1, num_bots + 1):
        bots.append({
            "name":       sp_config.get(f"bot_{i}", "name",       fallback=f"Bot {i}"),
            "difficulty": int(sp_config.get(f"bot_{i}", "difficulty", fallback="50")),
        })

    rules = {
        "stack_draws": sp_config.getboolean("rules", "stack_draws",  fallback=True),
        "force_play":  sp_config.getboolean("rules", "force_play",   fallback=False),
        "jump_in":     sp_config.getboolean("rules", "jump_in",      fallback=False),
        "seven_swap":  sp_config.getboolean("rules", "seven_swap",   fallback=False),
        "zero_rotate": sp_config.getboolean("rules", "zero_rotate",  fallback=False),
    }

    game = {
        "starting_hand_size": int(sp_config.get("game", "starting_hand_size", fallback="7")),
        "win_condition":      sp_config.get("game", "win_condition",           fallback="first"),
        "points_to_win":      int(sp_config.get("game", "points_to_win",       fallback="500")),
    }

    return bots, rules, game


# ── Card Definition ───────────────────────────────────────────────────────

COLOURS = ["red", "green", "blue", "yellow"]

CARDS = (
      [(colour, str(n)) for colour in COLOURS for n in range(0, 10)]
    + [(colour, str(n)) for colour in COLOURS for n in range(1, 10)]
    + [(colour, action) for colour in COLOURS for action in ["skip", "reverse", "draw_two"]]
    + [(colour, action) for colour in COLOURS for action in ["skip", "reverse", "draw_two"]]
    + [("wild", "wild")]      * 4
    + [("wild", "draw_four")] * 4
)


# ── Deck ──────────────────────────────────────────────────────────────────

def build_deck():
    deck = list(CARDS)
    random.shuffle(deck)
    return deck


def draw_card(deck, discard):
    if not deck:
        if len(discard) <= 1:
            return ("wild", "wild")
        top      = discard[-1]
        new_deck = discard[:-1]
        discard.clear()
        discard.append(top)
        random.shuffle(new_deck)
        deck.extend(new_deck)
    return deck.pop()


# ── Game State ────────────────────────────────────────────────────────────

def new_game():
    bots, rules, game = load_settings()

    num_players = len(bots) + 1
    hand_size   = game["starting_hand_size"]
    deck        = build_deck()
    discard     = []

    hands = []
    for _ in range(num_players):
        hand = [draw_card(deck, discard) for _ in range(hand_size)]
        hands.append(hand)

    # flip first card — skip wilds
    while True:
        card = draw_card(deck, discard)
        if card[0] != "wild":
            discard.append(card)
            break
        deck.insert(0, card)

    state = {
        "deck":          deck,
        "discard":       discard,
        "hands":         hands,
        "current":       0,
        "direction":     1,
        "num_players":   num_players,
        "pending_draw":  0,
        "active_colour": discard[-1][0],
        "bots":          bots,
        "rules":         rules,
        "game":          game,
        "scores":        [0] * num_players,
        "round":         1,
    }

    return state


# ── Card Logic ────────────────────────────────────────────────────────────

def can_play(card, top_card, active_colour, rules, pending_draw=0):
    colour, value     = card
    top_colour, top_value = top_card

    if pending_draw > 0:
        if rules.get("stack_draws"):
            if top_value == "draw_two"  and value == "draw_two":  return True
            if top_value == "draw_four" and value == "draw_four": return True
        return False

    if colour == "wild":        return True
    if colour == active_colour: return True
    if value  == top_value:     return True
    return False


def get_playable(hand, top_card, active_colour, rules, pending_draw=0):
    return [
        card for card in hand
        if can_play(card, top_card, active_colour, rules, pending_draw)
    ]


def next_player(state, skip=False):
    n    = state["num_players"]
    step = state["direction"] * (2 if skip else 1)
    state["current"] = (state["current"] + step) % n


def apply_card(card, state, chosen_colour=None):
    colour, value = card

    if value == "skip":
        state["active_colour"] = colour
        next_player(state, skip=True)

    elif value == "reverse":
        state["direction"] *= -1
        state["active_colour"] = colour
        if state["num_players"] == 2:
            next_player(state, skip=True)
        else:
            next_player(state)

    elif value == "draw_two":
        state["active_colour"] = colour
        if state["rules"]["stack_draws"]:
            state["pending_draw"] += 2
        else:
            target = (state["current"] + state["direction"]) % state["num_players"]
            for _ in range(2):
                state["hands"][target].append(draw_card(state["deck"], state["discard"]))
        next_player(state)

    elif value == "draw_four":
        state["active_colour"] = chosen_colour or colour
        if state["rules"]["stack_draws"]:
            state["pending_draw"] += 4
        else:
            target = (state["current"] + state["direction"]) % state["num_players"]
            for _ in range(4):
                state["hands"][target].append(draw_card(state["deck"], state["discard"]))
        next_player(state)

    elif colour == "wild":
        state["active_colour"] = chosen_colour or "red"
        next_player(state)

    elif value == "7" and state["rules"]["seven_swap"]:
        state["active_colour"] = colour
        next_player(state)

    elif value == "0" and state["rules"]["zero_rotate"]:
        state["active_colour"] = colour
        hands = state["hands"]
        n     = len(hands)
        if state["direction"] == 1:
            hands[:] = [hands[(i - 1) % n] for i in range(n)]
        else:
            hands[:] = [hands[(i + 1) % n] for i in range(n)]
        next_player(state)

    else:
        state["active_colour"] = colour
        next_player(state)


# ── Turn ──────────────────────────────────────────────────────────────────

def play_turn(state, player_idx, card_idx=None, chosen_colour=None, swap_target=None):
    hand     = state["hands"][player_idx]
    top_card = state["discard"][-1]
    rules    = state["rules"]
    pending  = state["pending_draw"]

    # forced draw
    if pending > 0 and card_idx is None:
        for _ in range(pending):
            hand.append(draw_card(state["deck"], state["discard"]))
        state["pending_draw"] = 0
        next_player(state)
        return {"action": "drew", "amount": pending}

    # draw a card
    if card_idx is None:
        drawn = draw_card(state["deck"], state["discard"])
        hand.append(drawn)

        if rules["force_play"] and can_play(drawn, top_card, state["active_colour"], rules):
            hand.remove(drawn)
            state["discard"].append(drawn)
            if len(hand) == 0:
                return {"action": "won", "player": player_idx}
            apply_card(drawn, state, chosen_colour)
            return {"action": "force_played", "card": drawn}

        next_player(state)
        return {"action": "drew", "card": drawn}

    # play a card
    card = hand[card_idx]
    if not can_play(card, top_card, state["active_colour"], rules, pending):
        return {"action": "invalid"}

    hand.pop(card_idx)
    state["discard"].append(card)

    if len(hand) == 0:
        return {"action": "won", "player": player_idx}

    if card[1] == "7" and rules["seven_swap"] and swap_target is not None:
        state["hands"][player_idx], state["hands"][swap_target] = \
            state["hands"][swap_target], state["hands"][player_idx]

    apply_card(card, state, chosen_colour)
    return {"action": "played", "card": card}


# ── Scoring ───────────────────────────────────────────────────────────────

CARD_POINTS = {
    "skip":      20,
    "reverse":   20,
    "draw_two":  20,
    "wild":      50,
    "draw_four": 50,
}


def card_points(card):
    colour, value = card
    if value in CARD_POINTS:
        return CARD_POINTS[value]
    if value.isdigit():
        return int(value)
    return 0


def calculate_scores(state, winner_idx):
    total = sum(
        card_points(card)
        for i, hand in enumerate(state["hands"])
        if i != winner_idx
        for card in hand
    )
    state["scores"][winner_idx] += total
    return total


# ── Win Check ─────────────────────────────────────────────────────────────

def check_winner(state):
    for i, hand in enumerate(state["hands"]):
        if len(hand) == 0:
            return i
    return None


def check_game_winner(state):
    if state["game"]["win_condition"] != "points":
        return None
    target = state["game"]["points_to_win"]
    for i, score in enumerate(state["scores"]):
        if score >= target:
            return i
    return None


def is_bot(player_idx):
    return player_idx != 0