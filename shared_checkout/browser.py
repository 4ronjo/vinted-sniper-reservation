"""Interact with one browser window shared with the user through noVNC.

NEVER submit payments: this module clicks at most an explicitly named *listing*
buy button and will never click a button, link or form in checkout.
"""
import os
import re
from urllib.parse import parse_qs, urlsplit

from validation import BUY_TEXTS, ITEM_PATH, is_checkout_url, is_vinted_item_url


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



def checkout_ui_verified(driver) -> bool:
    """Require an operator-validated checkout-only DOM marker.

    Without a known stable marker from an actual Vinted checkout, a matching
    URL is *unverified*, not proof that checkout has rendered.
    """
    from selenium.webdriver.common.by import By

    if not is_checkout_url(driver.current_url):
        return False
    ready_css = os.getenv('SNIPER_CHECKOUT_READY_CSS', '').strip()
    details_css = os.getenv('SNIPER_CHECKOUT_DETAILS_CSS', '').strip()
    error_css = os.getenv('SNIPER_CHECKOUT_ERROR_CSS', '').strip()
    if error_css and any(
        el.is_displayed() for el in driver.find_elements(By.CSS_SELECTOR, error_css)
    ):
        return False
    # Two independently verified checkout-only sections are required.
    if not ready_css or not details_css or ready_css == details_css:
        return False
    return all(
        any(el.is_displayed() for el in driver.find_elements(By.CSS_SELECTOR, selector))
        for selector in (ready_css, details_css)
    )


def _link_matches_item(href: str, item_url: str) -> bool:
    """Avoid redirecting a matching-label link to another listing's checkout."""
    if not is_checkout_url(href):
        return False
    link = urlsplit(href)
    listing = urlsplit(item_url)
    match = ITEM_PATH.match(listing.path)
    return bool(
        match
        and (link.hostname or '').removeprefix('www.') == (listing.hostname or '').removeprefix('www.')
        and parse_qs(link.query).get('transaction[item_id]') == [match.group(1)]
    )



def inspect_buy_controls(driver, item_url: str) -> str:
    """Read-only listing button audit; NEVER clicks or submits forms."""
    from selenium.webdriver.common.by import By

    matching = 0
    safe = 0
    reasons = []
    for element in driver.find_elements(By.CSS_SELECTOR, 'button, a'):
        try:
            if not element.is_displayed() or not element.is_enabled():
                continue
            label = re.sub(
                r'\s+', ' ',
                (element.text or element.get_attribute('aria-label') or '').strip(),
            ).casefold()
            if label not in BUY_TEXTS:
                continue
            matching += 1
            tag = element.tag_name.lower()
            if (element.get_attribute('target') or '_self').lower() not in ('_self', ''):
                reasons.append('link opens a different window')
            elif tag == 'button' and (
                element.get_attribute('type') or ''
            ).lower() == 'submit':
                reasons.append('button submits a form')
            elif tag == 'a' and not _link_matches_item(
                element.get_attribute('href') or '', item_url
            ):
                reasons.append('link is not checkout for this listing')
            elif tag in ('button', 'a'):
                safe += 1
            else:
                reasons.append('unsupported element')
        except Exception:
            reasons.append('element changed while inspecting')
    return (
        f'Buy-label controls: {matching}; safely eligible: {safe}; '
        f'require exactly one. Skipped: {", ".join(reasons[:6]) or "none"}. '
        'Read-only inspection, no clicks performed.'
    )


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
    # Listings are hydrated by JavaScript; wait briefly for a safely identifiable control.
    try:
        WebDriverWait(driver, 8, poll_frequency=0.25).until(
            lambda d: any(
                el.is_displayed() and el.is_enabled()
                and re.sub(r'\s+', ' ', (el.text or el.get_attribute('aria-label') or '').strip()).casefold() in BUY_TEXTS
                for el in d.find_elements(By.CSS_SELECTOR, 'button, a')
            )
        )
    except Exception as exc:
        raise RuntimeError('Kein eindeutiger Kaufen-Button gefunden; kein Klick') from exc
    for el in driver.find_elements(By.CSS_SELECTOR, 'button, a'):
        try:
            if not (el.is_displayed() and el.is_enabled()):
                continue
            label = re.sub(r'\s+', ' ', (el.text or el.get_attribute('aria-label') or '').strip()).casefold()
            if label not in BUY_TEXTS:
                continue
            # Fail closed: do not submit forms or click arbitrary role buttons.
            tag = el.tag_name.lower()
            if tag == 'button':
                if (el.get_attribute('type') or '').lower() == 'submit':
                    continue
            elif tag == 'a':
                if not _link_matches_item(el.get_attribute('href') or '', url):
                    continue
            else:
                continue
            # Do not risk a popup: the whole purpose is one shared browser view.
            if (el.get_attribute('target') or '_self').lower() not in ('_self', ''):
                continue
            if candidate is not None:
                raise RuntimeError('Mehrere Kaufen-Buttons gefunden; kein automatischer Klick')
            candidate = el
        except RuntimeError:
            raise
        except Exception:
            continue
    if candidate is None:
        raise RuntimeError('Kein eindeutiger Kaufen-Button im selben Fenster gefunden')
    if not is_vinted_item_url(driver.current_url):
        raise RuntimeError('Nicht mehr auf der Artikelseite; Klick abgebrochen')
    candidate.click()  # ONLY automated click in the application
    WebDriverWait(driver, 15).until(lambda d: is_checkout_url(d.current_url))
    return True
