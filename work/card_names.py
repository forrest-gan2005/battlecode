"""Pure card naming rules shared by board and message formatting."""
import re


def label_names(card):
    return [x['name'] if isinstance(x, dict) else x for x in card.get('labels', [])]


def card_name(card):
    return next((x[5:] for x in label_names(card) if x.startswith('name:')), card.get('name', ''))


def card_ref(card):
    number = card.get('number', card.get('n', card.get('card', '?')))
    name = card_name(card)
    if not name:
        title = re.sub(r'^(?:\s*\[(?:Idea|Task)\]\s*)+', '', (card.get('title') or ''), flags=re.I)
        title = re.sub(r'^#\d+\s*', '', title)
        name = ' '.join(title.split()[:4])
    return f"#{number}" + (f" {name}" if name else '')


def valid_slug(value):
    return isinstance(value, str) and len(value) <= 16 and bool(re.fullmatch(r'[a-z]+(?:-[a-z]+)?', value))


def unique_slug(title, used=(), suggested=None):
    words = re.findall(r'[a-z]+', title.lower())
    words = [w for w in words if w not in {'idea', 'task', 'the', 'a', 'an', 'and', 'for', 'of', 'to', 'in'}]
    base = suggested if valid_slug(suggested) else '-'.join(words[:2])[:16].rstrip('-')
    base = base or 'idea'
    used = set(used)
    if base not in used:
        return base
    index = 0
    while True:
        n, suffix = index, ''
        while True:
            suffix = chr(97 + n % 26) + suffix
            n = n // 26 - 1
            if n < 0:
                break
        candidate = base.split('-')[0][:15-len(suffix)] + '-' + suffix
        if candidate not in used:
            return candidate
        index += 1
