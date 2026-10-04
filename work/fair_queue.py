"""Fair card ordering shared by queue readers and the runner."""
import datetime
import json
from pathlib import Path

HUMANS = ('by:zhe', 'by:qwq', 'by:junsing')
COUNTER = 'humans_since_ai'


def names(card):
    return {x['name'] if isinstance(x, dict) else x for x in card.get('labels', [])}


def author(card):
    return next((x for x in HUMANS + ('by:ai',) if x in names(card)), 'by:unknown')


def oldest(card):
    return (card.get('createdAt', card.get('created', '')), card.get('number', card.get('n', 0)))


def read_fair(path=None):
    try:
        data = json.loads(Path(path or Path.home() / 'meow-loop-out/fair.json').read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def priority(card, fair=None):
    fair = fair or {}
    who = author(card)
    if 'type:task' in names(card):
        return (0, '', *oldest(card))
    ai_due = fair.get(COUNTER, 0) >= 3
    tier = (1 if ai_due else 3) if who == 'by:ai' else 2
    return (tier, fair.get(who, ''), *oldest(card))


def served(fair, card, when=None):
    result = dict(fair)
    if 'type:task' in names(card):
        return result
    who = author(card)
    result[who] = when or datetime.datetime.now(datetime.timezone.utc).isoformat()
    result[COUNTER] = 0 if who == 'by:ai' else min(3, result.get(COUNTER, 0) + 1)
    return result


def lock_taken(fair, card):
    """An AI card that gets a lock for any step has used the AI turn."""
    result = dict(fair)
    if author(card) == 'by:ai' and 'type:task' not in names(card) and result.get(COUNTER):
        result[COUNTER] = 0
    return result


def order_cards(cards, fair=None):
    pending, result, history = list(cards), [], dict(fair or {})
    # Virtual starts show a complete rotation without changing durable history.
    virtual = history
    turn = 0
    while pending:
        card = min(pending, key=lambda c: priority(c, virtual))
        pending.remove(card)
        result.append(card)
        virtual = served(virtual, card, '~' + str(turn).zfill(12))
        turn += 1
    return result
