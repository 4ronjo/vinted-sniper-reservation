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
        def __init__(self, driver, timeout):
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
