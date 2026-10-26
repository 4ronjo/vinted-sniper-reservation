"""Validate webhook listing inputs before passing them to an interactive browser."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit

ALLOWED_TLDS = frozenset({
    'de', 'at', 'fr', 'nl', 'es', 'it', 'pl', 'be', 'cz', 'sk', 'lt', 'pt',
    'se', 'ro', 'hu', 'gr', 'fi', 'dk', 'ie', 'lu', 'com', 'co.uk',
})
ITEM_PATH = re.compile(r'^/items/(\d+)(?:[-/?]|$)')
BUY_TEXTS = frozenset({
    'kaufen', 'jetzt kaufen', 'buy', 'buy now', 'acheter',
    'acheter maintenant', 'comprar', 'acquista',
})
CHECKOUT_PATH = re.compile(r'^/(?:transaction/buy|checkout)(?:/|$)', re.I)


@dataclass(frozen=True)
class Listing:
    item_key: str
    title: str
    url: str
    total: Decimal | None
    currency: str
    search: str


def is_vinted_item_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
            return False
        if parsed.fragment:
            return False
        host = (parsed.hostname or '').lower().removeprefix('www.')
        if not host.startswith('vinted.') or host[7:] not in ALLOWED_TLDS:
            return False
        return ITEM_PATH.match(parsed.path) is not None
    except ValueError:
        return False


def is_checkout_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').lower().removeprefix('www.')
        return parsed.scheme == 'https' and host.startswith('vinted.') and host[7:] in ALLOWED_TLDS and bool(CHECKOUT_PATH.match(parsed.path))
    except ValueError:
        return False


def parse_listing(item: object, search: str, max_total: Decimal | None) -> Listing | None:
    if not isinstance(item, dict):
        return None
    url = item.get('url')
    if not isinstance(url, str) or not is_vinted_item_url(url):
        return None
    match = ITEM_PATH.match(urlsplit(url).path)
    assert match is not None
    amount = item.get('total_price') or item.get('price')
    try:
        total = Decimal(str(amount)) if amount is not None else None
    except (InvalidOperation, ValueError):
        return None
    if max_total is not None and (total is None or total > max_total):
        return None
    return Listing(
        item_key=f'{urlsplit(url).hostname}:{match.group(1)}',
        title=str(item.get('title') or 'Artikel')[:180].replace('\n', ' '),
        url=url,
        total=total,
        currency=str(item.get('currency') or ''),
        search=search[:150],
    )
