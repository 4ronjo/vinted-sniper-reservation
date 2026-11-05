"""Docker-side webhook receiver and single shared-browser worker.

Never clicks within checkout; a successful checkout URL just freezes navigation
until the user leaves the page in the same noVNC-controlled Chromium instance.
"""
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from decimal import Decimal
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread

from browser import checkout_ui_verified, connect, inspect_buy_controls, open_listing_and_click_buy
from fastapi import FastAPI, HTTPException, Request
from notify import email_status
from validation import is_checkout_url, is_vinted_item_url, parse_listing

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger('shared_checkout')
MIN_WEBHOOK_SECRET_LENGTH = 24
SECRET = os.getenv('SNIPER_CHECKOUT_WEBHOOK_TOKEN', '')
QUEUE = Queue(maxsize=min(25, max(1, int(os.getenv('SNIPER_CHECKOUT_QUEUE_SIZE', '10')))))
LIMIT_STR = os.getenv('SNIPER_CHECKOUT_MAX_TOTAL_EUR', '').strip()
LIMIT = Decimal(LIMIT_STR) if LIMIT_STR else None
DRY_RUN = os.getenv('SNIPER_CHECKOUT_DRY_RUN', 'true').lower() == 'true'
ALERT_ONLY = os.getenv('SNIPER_CHECKOUT_ALERT_ONLY', 'false').lower() == 'true'
GRID_URL = os.getenv('SNIPER_SELENIUM_URL', 'http://browser:4444/wd/hub')
HOME_URL = os.getenv('SNIPER_VINTED_HOME', 'https://www.vinted.de')
seen: set[str] = set()
paused = Event()
auth_ready = Event()  # Never navigate until the user finishes login + any 2FA
lock = Lock()
stop = Event()
state = {'stage': 'starting', 'item': None, 'message': ''}


def change_state(stage: str, item: str | None = None, message: str = '') -> None:
    with lock:
        state.update(stage=stage, item=item, message=message)
    LOG.info('State %s item=%s %s', stage, item, message)


def do_alert_only():
    """Send listing links without using Selenium or controlling the Vinted browser."""
    change_state('alerts-only', message='Browser automation disabled; waiting for listings')
    while not stop.is_set():
        if paused.is_set():
            change_state('paused', message='Listing email alerts paused')
            stop.wait(0.5)
            continue
        try:
            listing = QUEUE.get(timeout=1)
        except Empty:
            continue
        try:
            # A pause could have been requested while the queue was read.
            while paused.is_set() and not stop.is_set():
                stop.wait(0.5)
            if stop.is_set():
                break
            change_state('alerting', listing.item_key)
            sent = email_status(
                listing,
                'Neuer Artikel - manuell öffnen',
                'Keine Browserautomatisierung oder Reservierung: '
                'Öffne den Artikellink in deinem normal angemeldeten Browser.',
                alert_only=True,
            )
            if sent:
                change_state('alerts-only', message='Email sent; waiting for listings')
            else:
                change_state(
                    'alert-delivery-failed', listing.item_key,
                    'SMTP delivery failed; inspect worker logs',
                )
        except Exception:
            LOG.exception('Email-only notification failed')
            change_state('alert-delivery-failed', listing.item_key)
        finally:
            QUEUE.task_done()


def do_work():  # noqa: C901, PLR0912, PLR0915 - explicit fail-closed checkout state machine
    driver = None
    while not stop.is_set():
        if driver is None:
            try:
                change_state('browser-connecting')
                driver = connect(GRID_URL, HOME_URL)
                auth_ready.clear()
                change_state(
                    'awaiting-manual-login',
                    message='Log in via noVNC, enter any SMS/email code, then confirm login',
                )
            except Exception:
                LOG.exception('Browser not yet ready')
                change_state('browser-not-ready')
                stop.wait(5)
                continue
        if not auth_ready.is_set():
            change_state(
                'awaiting-manual-login',
                message='Automated navigation blocked until manual login is confirmed',
            )
            stop.wait(0.5)
            continue
        if paused.is_set():
            change_state('paused', message='Manual browser control - no automatic navigation')
            stop.wait(0.5)
            continue
        try:
            if is_checkout_url(driver.current_url):
                change_state(
                    'manual-checkout-protected',
                    message='Existing checkout is not overwritten',
                )
                stop.wait(1)
                continue
        except Exception:  # noqa: BLE001 - Selenium may disconnect for many reasons
            driver = None
            continue
        try:
            listing = QUEUE.get(timeout=1)
        except Empty:
            continue
        try:
            # A pause may have arrived while fetching the next item.
            while (paused.is_set() or not auth_ready.is_set()) and not stop.is_set():
                stop.wait(0.5)
            if stop.is_set():
                break
            # The user may have opened checkout between queue polling and navigation.
            while not stop.is_set() and is_checkout_url(driver.current_url):
                change_state('manual-checkout-protected', listing.item_key)
                stop.wait(1)
            if stop.is_set():
                break
            change_state('opening', listing.item_key)
            opened = open_listing_and_click_buy(driver, listing.url, DRY_RUN)
            if not opened:
                change_state('dry-run', listing.item_key)
                inspection = inspect_buy_controls(driver, listing.url)
                email_status(
                    listing,
                    'TEST - Artikel gefunden',
                    'Kein Kaufen-Button wurde angeklickt. ' + inspection,
                )
                continue
            # A checkout-shaped URL alone is insufficient evidence of a usable UI.
            # No extra clicks, form submissions or payment actions are permitted.
            verified = checkout_ui_verified(driver)
            stage = 'checkout-ui-verified' if verified else 'checkout-url-unverified'
            change_state(
                stage, listing.item_key, 'Browser yielded to user; no more automatic clicks'
            )
            email_status(
                listing,
                (
                    'Checkout-Oberfläche erkannt - Reservierung unbestätigt'
                    if verified else 'Checkout-URL erreicht - Oberfläche UNBESTÄTIGT'
                ),
                (
                    'Der sichtbare Checkout-Marker wurde erkannt.'
                    if verified else
                    'Nur der Checkout-Pfad wurde erkannt. Bitte manuell im selben Browser '
                    'prüfen, ob ein nutzbarer Checkout oder eine Fehlermeldung angezeigt wird.'
                )
                + ' Die gemeinsame Browseransicht bleibt geöffnet. '
                + 'Der Bot führt keine weiteren Klicks aus, bis du die Seite verlässt.',
            )
            while not stop.is_set():
                if not is_checkout_url(driver.current_url):
                    break
                stop.wait(1)
            change_state('checkout-left', listing.item_key)
        except Exception as exc:
            LOG.exception('Checkout failed')
            change_state('failed', listing.item_key, str(exc))
            email_status(listing, 'Checkout fehlgeschlagen', str(exc))
            # Fail closed after any failed checkout attempt: the user's browser may
            # display login/2FA or a changed site. Require explicit manual review.
            # Never capture a password, email challenge or one-time code.
            auth_ready.clear()
            try:
                _ = driver.current_url
            except Exception:  # noqa: BLE001 - Selenium may disconnect for many reasons
                driver = None
        finally:
            QUEUE.task_done()
            if driver is not None and not stop.is_set():
                change_state('ready', message='Waiting for new item')
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            LOG.exception('Browser cleanup failed')


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if len(SECRET) < MIN_WEBHOOK_SECRET_LENGTH:
        raise RuntimeError('Configure SNIPER_CHECKOUT_WEBHOOK_TOKEN (at least 24 characters)')
    if not is_vinted_item_url(HOME_URL.rstrip('/') + '/items/1'):
        raise RuntimeError('SNIPER_VINTED_HOME must be a permitted Vinted domain')
    if ALERT_ONLY and not all((
        os.getenv('SNIPER_SMTP_USER', '').strip(),
        os.getenv('SNIPER_SMTP_APP_PASSWORD', '').strip(),
        os.getenv('SNIPER_CHECKOUT_EMAIL_TO', '').strip(),
    )):
        raise RuntimeError('Email-only mode requires sender, SMTP app password, and recipient')
    target = do_alert_only if ALERT_ONLY else do_work
    t = Thread(target=target, name='checkout-alerts' if ALERT_ONLY else 'checkout-browser',
               daemon=True)
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join(timeout=5)


app = FastAPI(title='Vinted Shared Browser', lifespan=lifespan)


@app.get('/health')
def health():
    with lock:
        current = state.copy()
    return {
        'status': current,
        'queued': QUEUE.qsize(),
        'dry_run': DRY_RUN or ALERT_ONLY,
        'mode': 'alerts-only' if ALERT_ONLY else 'shared-browser',
        'paused': paused.is_set(),
        'login_confirmed_by_user': auth_ready.is_set(),
        'login_note': 'Manual confirmation only; does not prove platform authentication',
    }


@app.post('/hook/{secret}')
async def webhook(secret: str, request: Request):  # noqa: C901 - validate each input boundary
    if not SECRET or not hmac.compare_digest(secret, SECRET):
        raise HTTPException(status_code=403, detail='Invalid token')
    raw = await request.body()
    if len(raw) > 512 * 1024:
        raise HTTPException(status_code=413, detail='Payload too large')
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail='Invalid JSON') from exc
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise HTTPException(status_code=400, detail='Invalid version')
    if 'items' not in payload:
        return {'queued': 0}
    if not isinstance(payload['items'], list):
        raise HTTPException(status_code=400, detail='Invalid items')
    count = 0
    for item in payload['items'][:40]:
        listing = parse_listing(item, str(payload.get('search') or ''), LIMIT)
        if listing is None:
            continue
        with lock:
            if listing.item_key in seen:
                continue
            try:
                QUEUE.put_nowait(listing)
            except Full:
                break
            seen.add(listing.item_key)
        count += 1
    return {'queued': count, 'pending': QUEUE.qsize()}


@app.post('/control/pause/{secret}')
def pause_browser(secret: str):
    if not SECRET or not hmac.compare_digest(secret, SECRET):
        raise HTTPException(status_code=403, detail='Invalid token')
    paused.set()
    return {'paused': True, 'note': 'In-progress navigation cannot be interrupted mid-click'}


@app.post('/control/resume/{secret}')
def resume_browser(secret: str):
    if not SECRET or not hmac.compare_digest(secret, SECRET):
        raise HTTPException(status_code=403, detail='Invalid token')
    paused.clear()
    return {'paused': False}


@app.post('/control/login-confirmed/{secret}')
def confirm_manual_login(secret: str):
    """User acknowledges completing all Vinted login/2FA steps in the shared browser."""
    if not SECRET or not hmac.compare_digest(secret, SECRET):
        raise HTTPException(status_code=403, detail='Invalid token')
    if ALERT_ONLY:
        raise HTTPException(
            status_code=409,
            detail='Email-only mode does not use browser login confirmation',
        )
    auth_ready.set()
    return {
        'login_confirmed_by_user': True,
        'warning': 'Acknowledgement only; the worker never reads SMS or email codes',
    }


@app.post('/control/login-required/{secret}')
def require_manual_login(secret: str):
    """Pause worker navigation to permit another manual authentication challenge."""
    if not SECRET or not hmac.compare_digest(secret, SECRET):
        raise HTTPException(status_code=403, detail='Invalid token')
    auth_ready.clear()
    return {'login_confirmed_by_user': False}
