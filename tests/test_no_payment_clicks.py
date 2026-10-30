"""Tests for the strict buy-only click boundary without requiring Selenium."""
from importlib import import_module
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared_checkout'))
browser = import_module('browser')


class FakeButton:
    def __init__(self, label, driver):
        self.text = label
        self.tag_name = 'button'
        self.driver = driver
        self.clicks = 0

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def get_attribute(self, name):
        if name == 'type':
            return 'button'
        return None

    def click(self):
        self.clicks += 1
        self.driver.current_url = 'https://www.vinted.de/transaction/buy/new'


class FakeDriver:
    def __init__(self):
        self.current_url = ''
        self.controls = []

    def get(self, url):
        self.current_url = url

    def find_elements(self, *args):
        return self.controls


@pytest.fixture(autouse=True)
def fake_selenium(monkeypatch):
    selenium = ModuleType('selenium')
    webdriver = ModuleType('selenium.webdriver')
    common = ModuleType('selenium.webdriver.common')
    by = ModuleType('selenium.webdriver.common.by')
    support = ModuleType('selenium.webdriver.support')
    ui = ModuleType('selenium.webdriver.support.ui')
    by.By = SimpleNamespace(CSS_SELECTOR='css')

    class Wait:
        def __init__(self, driver, timeout, **kwargs):
            self.driver = driver

        def until(self, callback):
            if not callback(self.driver):
                raise TimeoutError('Expected checkout URL')

    ui.WebDriverWait = Wait
    for name, mod in (
        ('selenium', selenium), ('selenium.webdriver', webdriver),
        ('selenium.webdriver.common', common),
        ('selenium.webdriver.common.by', by),
        ('selenium.webdriver.support', support),
        ('selenium.webdriver.support.ui', ui),
    ):
        monkeypatch.setitem(sys.modules, name, mod)


def test_dry_run_cannot_click_anything():
    driver = FakeDriver()
    buy = FakeButton('Kaufen', driver)
    driver.controls = [buy]
    assert browser.open_listing_and_click_buy(driver, 'https://www.vinted.de/items/123', True) is False
    assert buy.clicks == 0


def test_payment_label_is_never_clicked():
    driver = FakeDriver()
    pay = FakeButton('Zahlungspflichtig bestellen', driver)
    driver.controls = [pay]
    with pytest.raises(RuntimeError, match='Kein eindeutiger Kaufen-Button'):
        browser.open_listing_and_click_buy(driver, 'https://www.vinted.de/items/123', False)
    assert pay.clicks == 0


def test_only_exact_listing_buy_button_clicks_once():
    driver = FakeDriver()
    pay = FakeButton('Zahlungspflichtig bestellen', driver)
    buy = FakeButton('Kaufen', driver)
    driver.controls = [pay, buy]
    assert browser.open_listing_and_click_buy(driver, 'https://www.vinted.de/items/123', False)
    assert pay.clicks == 0
    assert buy.clicks == 1


def test_submit_button_never_clicked():
    driver = FakeDriver()
    dangerous = FakeButton('Kaufen', driver)
    original = dangerous.get_attribute
    dangerous.get_attribute = lambda name: 'submit' if name == 'type' else original(name)
    driver.controls = [dangerous]
    with pytest.raises(RuntimeError, match='Kein eindeutiger Kaufen-Button'):
        browser.open_listing_and_click_buy(driver, 'https://www.vinted.de/items/123', False)
    assert dangerous.clicks == 0


def test_two_ambiguous_buy_buttons_cannot_click():
    driver = FakeDriver()
    buy1, buy2 = FakeButton('Kaufen', driver), FakeButton('Kaufen', driver)
    driver.controls = [buy1, buy2]
    with pytest.raises(RuntimeError, match='Mehrere Kaufen-Buttons'):
        browser.open_listing_and_click_buy(driver, 'https://www.vinted.de/items/123', False)
    assert buy1.clicks == buy2.clicks == 0


def test_buy_deeplink_must_reference_current_item():
    assert browser._link_matches_item(
        'https://www.vinted.de/transaction/buy/new?transaction%5Bitem_id%5D=123',
        'https://vinted.de/items/123-beispiel',
    )
    assert not browser._link_matches_item(
        'https://www.vinted.de/transaction/buy/new?transaction%5Bitem_id%5D=999',
        'https://www.vinted.de/items/123-beispiel',
    )
    assert not browser._link_matches_item(
        'https://notvinted.example/transaction/buy/new?transaction%5Bitem_id%5D=123',
        'https://www.vinted.de/items/123-beispiel',
    )


def test_checkout_route_without_verified_dom_is_not_ui_confirmation(monkeypatch):
    monkeypatch.delenv('SNIPER_CHECKOUT_READY_CSS', raising=False)
    monkeypatch.delenv('SNIPER_CHECKOUT_DETAILS_CSS', raising=False)
    driver = FakeDriver()
    driver.current_url = 'https://www.vinted.de/transaction/buy/new'
    assert not browser.checkout_ui_verified(driver)


def test_checkout_verified_marker_requires_visible_element(monkeypatch):
    monkeypatch.setenv('SNIPER_CHECKOUT_READY_CSS', '.known-checkout-summary')
    monkeypatch.setenv('SNIPER_CHECKOUT_DETAILS_CSS', '.known-shipping-section')
    monkeypatch.delenv('SNIPER_CHECKOUT_ERROR_CSS', raising=False)
    driver = FakeDriver()
    driver.current_url = 'https://www.vinted.de/transaction/buy/new'
    driver.controls = [FakeButton('Checkout Summary', driver)]
    assert browser.checkout_ui_verified(driver)
    driver.controls = []
    assert not browser.checkout_ui_verified(driver)


def test_single_checkout_marker_never_confirms_ui(monkeypatch):
    monkeypatch.setenv('SNIPER_CHECKOUT_READY_CSS', '.known-checkout-summary')
    monkeypatch.delenv('SNIPER_CHECKOUT_DETAILS_CSS', raising=False)
    driver = FakeDriver()
    driver.current_url = 'https://www.vinted.de/transaction/buy/new'
    driver.controls = [FakeButton('Checkout Summary', driver)]
    assert not browser.checkout_ui_verified(driver)


def test_dry_run_inspection_reports_safe_button_but_does_not_click():
    driver = FakeDriver()
    button = FakeButton('Kaufen', driver)
    driver.current_url = 'https://www.vinted.de/items/123-example'
    driver.controls = [button]
    report = browser.inspect_buy_controls(driver, driver.current_url)
    assert 'safely eligible: 1' in report
    assert button.clicks == 0


def test_dry_run_inspection_excludes_payment_button():
    driver = FakeDriver()
    payment = FakeButton('Zahlungspflichtig bestellen', driver)
    driver.current_url = 'https://www.vinted.de/items/123-example'
    driver.controls = [payment]
    report = browser.inspect_buy_controls(driver, driver.current_url)
    assert 'safely eligible: 0' in report
    assert payment.clicks == 0
