import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared_checkout'))
from validation import is_vinted_item_url, is_checkout_url, parse_listing


def test_vinted_link_validation():
    assert is_vinted_item_url('https://www.vinted.de/items/123-schuhe')
    assert is_vinted_item_url('https://vinted.fr/items/999')
    assert not is_vinted_item_url('https://vinted.de.bad.com/items/123')
    assert not is_vinted_item_url('http://www.vinted.de/items/123')
    assert not is_vinted_item_url('https://vinted.de/transaction/buy/new')
    assert not is_vinted_item_url('https://user:pass@vinted.de/items/123')


def test_checkout_url_validation():
    assert is_checkout_url('https://www.vinted.de/transaction/buy/new?foo=1')
    assert not is_checkout_url('https://evil.test/checkout/new')
    assert not is_checkout_url('https://www.vinted.de/items/1')


def test_price_filter_and_item_key():
    item = dict(url='https://www.vinted.de/items/120-pokemon', title='Pokemon', total_price='34.90')
    assert parse_listing(item, 'Pokemon', Decimal('35')).item_key == 'www.vinted.de:120'
    assert parse_listing(item, 'Pokemon', Decimal('34')) is None
    assert parse_listing(item, 'Pokemon', None).total == Decimal('34.90')


def test_bad_payload():
    assert parse_listing({'url': 'https://bad.com/items/1'}, 'x', None) is None
    assert parse_listing({'url': 'https://vinted.de/items/1', 'price': 'NaN-a-number'}, 'x', None) is None
