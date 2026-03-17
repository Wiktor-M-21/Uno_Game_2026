import random
from collections import Counter


# ── Smooth Difficulty ─────────────────────────────────────────────────────
# difficulty 1   = fully random
# difficulty 100 = always optimal
# Everything in between is a weighted blend

def should_play_optimally(difficulty):
    """Returns True if the bot should make the optimal play this decision."""
    return random.randint(1, 100) <= int(difficulty)


def get_aggression(difficulty):
    """0.0 - 1.0 scale. Higher = more aggressive with action cards."""
    return int(difficulty) / 100


# ── Card Scoring ──────────────────────────────────────────────────────────

CARD_PRIORITY = {
    "draw_four":  10,
    "draw_two":   8,
    "skip":       7,
    "reverse":    6,
    "wild":       5,
}

def card_score(card):
    colour, value = card
    return CARD_PRIORITY.get(value, int(value) if value.isdigit() else 0)


# ── Colour Choice ─────────────────────────────────────────────────────────

def choose_colour(hand, difficulty):
    """
    Low difficulty  = random colour
    High difficulty = most common colour in hand
    Blended in between
    """
    colour_counts = Counter(
        card[0] for card in hand
        if card[0] != "wild"
    )

    if not colour_counts:
        return random.choice(["red", "green", "blue", "yellow"])

    best   = colour_counts.most_common(1)[0][0]
    random_colour = random.choice(["red", "green", "blue", "yellow"])

    return best if should_play_optimally(difficulty) else random_colour


# ── Card Picking ──────────────────────────────────────────────────────────

def optimal_pick(playable, hand, state, bot_idx):
    """Always picks the best card."""
    non_wilds  = [c for c in playable if c[0] != "wild"]
    wilds      = [c for c in playable if c[0] == "wild" and c[1] == "wild"]
    draw_fours = [c for c in playable if c[1] == "draw_four"]

    hands     = state["hands"]
    direction = state["direction"]
    current   = state["current"]
    n         = state["num_players"]
    next_idx  = (current + direction) % n

    opponent_counts = {
        i: len(hands[i])
        for i in range(n)
        if i != bot_idx
    }

    # aggressive if next player is close to winning
    if opponent_counts.get(next_idx, 99) <= 2:
        draw_cards = [c for c in playable if c[1] in ("draw_two", "draw_four")]
        skip_cards = [c for c in playable if c[1] in ("skip", "reverse")]
        if draw_fours:  return draw_fours[0]
        if draw_cards:  return draw_cards[0]
        if skip_cards:  return skip_cards[0]

    # shed lowest value cards when close to winning
    if len(hand) <= 3:
        number_cards = [c for c in non_wilds if c[1].isdigit()]
        if number_cards:
            return min(number_cards, key=lambda c: int(c[1]))

    # prefer action cards, save wilds and draw_fours
    action_cards = [c for c in non_wilds if not c[1].isdigit()]
    if action_cards:
        return max(action_cards, key=card_score)
    if non_wilds:
        return max(non_wilds, key=card_score)
    if wilds:
        return wilds[0]
    if draw_fours:
        return draw_fours[0]

    return random.choice(playable)


def pick_card(playable, hand, state, bot_idx, difficulty):
    """
    Blends random and optimal based on difficulty.
    At difficulty 1  — fully random
    At difficulty 50 — 50% chance of optimal play each decision
    At difficulty 100 — always optimal
    """
    if should_play_optimally(difficulty):
        return optimal_pick(playable, hand, state, bot_idx)
    else:
        return random.choice(playable)


# ── Draw Decision ─────────────────────────────────────────────────────────

def should_play_drawn_card(drawn, top_card, active_col, rules, pending, difficulty):
    """
    Low difficulty bots always keep drawn cards.
    High difficulty bots always play them if possible.
    """
    from system_data.play_classic import can_play
    if not can_play(drawn, top_card, active_col, rules, pending):
        return False
    return should_play_optimally(difficulty)


# ── Seven Swap Target ─────────────────────────────────────────────────────

def pick_swap_target(state, bot_idx, difficulty):
    """
    Low difficulty = random target
    High difficulty = player with fewest cards
    """
    n = state["num_players"]
    others = [i for i in range(n) if i != bot_idx]

    if should_play_optimally(difficulty):
        return min(others, key=lambda i: len(state["hands"][i]))
    else:
        return random.choice(others)


# ── Main Entry Point ──────────────────────────────────────────────────────

def bot_turn(state, bot_idx, difficulty):
    from system_data.play_classic import (
        can_play, get_playable, draw_card, next_player, apply_card
    )

    hand       = state["hands"][bot_idx]
    top_card   = state["discard"][-1]
    active_col = state["active_colour"]
    rules      = state["rules"]
    pending    = state["pending_draw"]
    playable   = get_playable(hand, top_card, active_col, rules, pending)

    # forced draw from pending stack
    if pending > 0 and not playable:
        for _ in range(pending):
            hand.append(draw_card(state["deck"], state["discard"]))
        amount = pending
        state["pending_draw"] = 0
        next_player(state)
        return {"action": "drew", "amount": amount}

    # no playable cards — draw one
    if not playable:
        drawn = draw_card(state["deck"], state["discard"])
        hand.append(drawn)

        if should_play_drawn_card(drawn, top_card, active_col, rules, pending, difficulty):
            playable = [drawn]
        else:
            next_player(state)
            return {"action": "drew", "card": drawn}

    # pick and play a card
    card = pick_card(playable, hand, state, bot_idx, difficulty)

    chosen_colour = None
    if card[0] == "wild":
        chosen_colour = choose_colour(hand, difficulty)

    hand.remove(card)
    state["discard"].append(card)

    if len(hand) == 0:
        return {"action": "won", "player": bot_idx}

    # seven swap
    swap_target = None
    if card[1] == "7" and rules.get("seven_swap"):
        swap_target = pick_swap_target(state, bot_idx, difficulty)
        state["hands"][bot_idx], state["hands"][swap_target] = \
            state["hands"][swap_target], state["hands"][bot_idx]

    apply_card(card, state, chosen_colour)

    return {
        "action":        "played",
        "card":          card,
        "chosen_colour": chosen_colour,
        "swap_target":   swap_target,
    }