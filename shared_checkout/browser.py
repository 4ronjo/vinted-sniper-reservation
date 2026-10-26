"""Interact with one browser window shared with the user through noVNC.

NEVER submit payments: this module clicks at most an explicitly named *listing*
buy button and will never click a button, link or form in checkout.
"""
import re

from validation import BUY_TEXTS, is_checkout_url, is_vinted_item_url


def connect(grid_url: str, home_url: str):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument('--window-size=1440,900')
    options.add_argument('--user-data-dir=/home/seluser/snipe-profile')
    options.add_argument('--no-first-run')
    driver = webdriver.Remote(command_executor=grid_url, options=options)
    driver.set_page_load_timeout(25)
    driver.get(home_url)
    return driver


def open_listing_and_click_buy(driver, url: str, dry_run: bool) -> bool:
    """Return True only if checkout has been reached (never complete purchase)."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    driver.get(url)  # same browser window, never a new window or tab
    if not is_vinted_item_url(driver.current_url):
        raise RuntimeError('Artikel nicht erreichbar oder Konto nicht angemeldet')
    if dry_run:
        return False

    candidate = None
    for el in driver.find_elements(By.CSS_SELECTOR, 'button, a, [role="button"]'):
        try:
            if not (el.is_displayed() and el.is_enabled()):
                continue
            label = re.sub(r'\s+', ' ', (el.text or el.get_attribute('aria-label') or '').strip()).casefold()
            if label not in BUY_TEXTS:
                continue
            # Do not risk a popup: the whole purpose is one shared browser view.
            if (el.get_attribute('target') or '_self').lower() not in ('_self', ''):
                continue
            candidate = el
            break
        except Exception:
            continue
    if candidate is None:
        raise RuntimeError('Kein eindeutiger Kaufen-Button im selben Fenster gefunden')
    if not is_vinted_item_url(driver.current_url):
        raise RuntimeError('Nicht mehr auf der Artikelseite; Klick abgebrochen')
    candidate.click()  # ONLY automated click in the application
    WebDriverWait(driver, 15).until(lambda d: is_checkout_url(d.current_url))
    return True
