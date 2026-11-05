"""Test email-only fallback without network or browser automation."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared_checkout'))
from notify import email_status  # noqa: E402


class FakeSMTP:
    sent = None

    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def login(self, _user, _password):
        pass

    def send_message(self, message):
        FakeSMTP.sent = message


def _listing():
    return SimpleNamespace(
        title='Example item',
        search='example',
        total='20.00',
        currency='EUR',
        url='https://www.vinted.de/items/123-example',
    )


def test_email_only_sends_item_link_without_vnc(monkeypatch):
    import notify  # noqa: PLC0415

    FakeSMTP.sent = None
    monkeypatch.setenv('SNIPER_SMTP_USER', 'sender@example.org')
    monkeypatch.setenv('SNIPER_SMTP_APP_PASSWORD', 'fake-test-password')
    monkeypatch.setenv('SNIPER_CHECKOUT_EMAIL_TO', 'recipient@example.org')
    monkeypatch.setattr(notify.smtplib, 'SMTP_SSL', FakeSMTP)

    assert email_status(_listing(), 'Neuer Artikel', 'Please open manually', alert_only=True)
    body = FakeSMTP.sent.get_content()
    assert 'https://www.vinted.de/items/123-example' in body
    assert 'localhost:7900' not in body
    assert 'kein automatischer Checkout' not in body.lower() or 'Kein Checkout' in body
    assert FakeSMTP.sent['To'] == 'recipient@example.org'


def test_email_only_refuses_unconfigured_smtp(monkeypatch):
    monkeypatch.delenv('SNIPER_SMTP_USER', raising=False)
    monkeypatch.delenv('SNIPER_SMTP_APP_PASSWORD', raising=False)
    assert email_status(_listing(), 'Neuer Artikel', '', alert_only=True) is False
