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

from fastapi import FastAPI, HTTPException, Request

from browser import connect, open_listing_and_click_buy
from notify import email_status
from validation import is_checkout_url, is_vinted_item_url, parse_listing

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger('shared_checkout')
SECRET = os.getenv('SNIPER_CHECKOUT_WEBHOOK_TOKEN', '')
QUEUE = Queue(maxsize=min(25, max(1, int(os.getenv('SNIPER_CHECKOUT_QUEUE_SIZE', '10')))))
LIMIT_STR = os.getenv('SNIPER_CHECKOUT_MAX_TOTAL_EUR', '').strip()
LIMIT = Decimal(LIMIT_STR) if LIMIT_STR else None
DRY_RUN = os.getenv('SNIPER_CHECKOUT_DRY_RUN', 'true').lower() == 'true'
GRID_URL = os.getenv('SNIPER_SELENIUM_URL', 'http://browser:4444/wd/hub')
HOME_URL = os.getenv('SNIPER_VINTED_HOME', 'https://www.vinted.de')
seen: set[str] = set()
paused = Event()
lock = Lock()
stop = Event()
state = {'stage': 'starting', 'item': None, 'message': ''}


def change_state(stage: str, item: str | None = None, message: str = '') -> None:
    with lock:
        state.update(stage=stage, item=item, message=message)
    LOG.info('State %s item=%s %s', stage, item, message)


def do_work():
    driver = None
    while not stop.is_set():
        if driver is None:
            try:
                change_state('browser-connecting')
                driver = connect(GRID_URL, HOME_URL)
                change_state('ready', message='Log in via the shared noVNC browser')
            except Exception:
                LOG.exception('Browser not yet ready')
                change_state('browser-not-ready')
                stop.wait(5)
                continue
        if paused.is_set():
            change_state('paused', message='Manual browser control – no automatic navigation')
            stop.wait(0.5)
            continue
        try:
            if is_checkout_url(driver.current_url):
                change_state('manual-checkout-protected', message='Existing checkout is not overwritten')
                stop.wait(1)
                continue
        except Exception:
            driver = None
            continue
        try:
            listing = QUEUE.get(timeout=1)
        except Empty:
            continue
        try:
            # A pause may have arrived while fetching the next item.
            while paused.is_set() and not stop.is_set():
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
                email_status(listing, 'TEST – Artikel gefunden', 'Der Kaufbutton wurde NICHT betätigt.')
                continue
            change_state('checkout-open', listing.item_key, 'No further clicks; user controls the shared browser')
            email_status(
                listing, 'Checkout geöffnet – Reservierung unbestätigt',
                'Die Seite ist im selben Docker-Browser geöffnet. '
                'Über die bereits geöffnete noVNC-Ansicht übernehmen. '
                'Der Bot klickt nichts mehr an, bis du die Checkout-Seite verlässt.',
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
            try:
                _ = driver.current_url
            except Exception:
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
async def lifespan(app: FastAPI):
    if len(SECRET) < 24:
        raise RuntimeError('Configure SNIPER_CHECKOUT_WEBHOOK_TOKEN (at least 24 characters)')
    if not is_vinted_item_url(HOME_URL.rstrip('/') + '/items/1'):
        raise RuntimeError('SNIPER_VINTED_HOME must be a permitted Vinted domain')
    t = Thread(target=do_work, name='checkout-browser', daemon=True)
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
    return {'status': current, 'queued': QUEUE.qsize(), 'dry_run': DRY_RUN, 'paused': paused.is_set()}


@app.post('/hook/{secret}')
async def webhook(secret: str, request: Request):
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
