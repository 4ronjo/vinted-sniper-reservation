"""Optional SMTP alerts; failures never cause any purchase actions."""
import logging
import os
import smtplib
from email.message import EmailMessage

from validation import Listing

LOG = logging.getLogger(__name__)


def email_status(item: Listing, status: str, details: str, *, alert_only: bool = False) -> bool:
    user = os.getenv('SNIPER_SMTP_USER', '')
    password = os.getenv('SNIPER_SMTP_APP_PASSWORD', '')
    destination = os.getenv('SNIPER_CHECKOUT_EMAIL_TO', 'theorieofgaming@gmail.com')
    if not (user and password):
        LOG.warning('SMTP not configured; no mail to %s', destination)
        return False
    msg = EmailMessage()
    msg['From'] = user
    msg['To'] = destination
    msg['Subject'] = f'Vinted: {status} - {item.title}'
    viewer_url = os.getenv(
        'SNIPER_CHECKOUT_VIEW_URL',
        'http://localhost:7900/vnc.html?autoconnect=1&resize=scale',
    )
    if alert_only:
        preamble = ''
        warning = (
            'Kein Checkout und keine Reservierung. '
            'Öffne den Artikellink in deinem normalen Browser.\n'
        )
    else:
        preamble = f'Browseransicht (derselbe Checkout, kein neues Vinted-Fenster): {viewer_url}\n\n'
        warning = (
            'Achtung: Checkout geöffnet bedeutet NICHT nachweislich reserviert. '
            'Der Bot bestätigt NIEMALS eine Bestellung oder Zahlung.\n'
        )
    msg.set_content(
        f'{preamble}Status: {status}\nArtikel: {item.title}\nSuche: {item.search}\n'
        f'Preis inkl. Käuferschutz: {item.total} {item.currency}\n'
        f'Artikel: {item.url}\n\n{details}\n\n{warning}'
    )
    try:
        with smtplib.SMTP_SSL(
            os.getenv('SNIPER_SMTP_HOST', 'smtp.gmail.com'),
            int(os.getenv('SNIPER_SMTP_PORT', '465')),
            timeout=20,
        ) as client:
            client.login(user, password)
            client.send_message(msg)
        return True
    except Exception:
        LOG.exception('Email delivery failed')
        return False
