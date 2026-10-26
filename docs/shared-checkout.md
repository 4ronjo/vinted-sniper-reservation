# Shared-browser Vinted checkout add-on (EXPERIMENTAL)

This feature has **not** been verified on Vinted live. A checkout being open is
**not proof of a reservation**, and any temporary hold can expire even while
the browser remains open. Automated access may violate Vinted's terms.

**The bot NEVER submits an order or pays.** It has exactly one automated click
site: a button/link on an **item page** matching "Kaufen" / "Buy" exactly.
After it reaches checkout, it makes no further clicks and waits for you to leave
the checkout using the **same visible Chromium browser**.

## 1. Configure

Use the `feature/checkout-snipe-email` branch.

Copy `checkout.env.example` to `.checkout.env`, then set:
- `SNIPER_CHECKOUT_WEBHOOK_TOKEN`: random secret of >=24 characters. Generate
  one with `openssl rand -hex 32`.
- `SNIPER_CHECKOUT_EMAIL_TO=theorieofgaming@gmail.com` (already the default).
- `SNIPER_SMTP_USER` and `SNIPER_SMTP_APP_PASSWORD` to Gmail SMTP sender
  credentials if you want email alerts. Use a **Google app password**, never
  your ordinary Gmail password.
- Keep `SNIPER_CHECKOUT_DRY_RUN=true` initially (opens listing but NOT checkout).

In the root `.env` file, set a strong password for the shared browser:

```
SNIPER_VNC_PASSWORD=YOUR_OWN_LONG_PRIVATE_PASSWORD
```

Never commit `.env` or `.checkout.env`. Vinted login happens interactively
inside the browser; no Vinted password belongs in either environment file.

## 2. Start Docker

```bash
docker compose -f docker-compose.yml -f docker-compose.checkout.yml up -d --build
```

Keep the shared browser open in a browser tab on your computer:

**http://localhost:7900/?autoconnect=1&resize=scale**

Authenticate with your VNC password, then log into your Vinted account
inside that Chromium browser. It is the **same browser** the sniper later
uses; it does not open a second checkout in a separate local window.

The original search dashboard is at http://localhost:8000.

## 3. Connect saved searches

In the original sniper dashboard create a **Webhook** destination pointing to

```
http://checkout-worker:8765/hook/YOUR_CHECKOUT_WEBHOOK_TOKEN
```

Replace the last segment with the same secret configured above, then route
your chosen saved searches to it. The existing search filters and max total
price rules still apply.

To test: create a saved search and wait for a new matching article. In dry run,
the worker only visits the listing and sends a test email.

When the dry run, account login and alert work, change
`SNIPER_CHECKOUT_DRY_RUN=false` in `.checkout.env` and restart only the worker:

```bash
docker compose -f docker-compose.yml -f docker-compose.checkout.yml up -d --force-recreate checkout-worker
```

## 4. Same checkout screen, no automatic payments

The bot navigates in the **already running** Chromium window seen through
noVNC. If it finds and clicks a supported listing-page Kaufen button and Vinted
opens checkout, the worker **stops all browser interactions**, emails
"Checkout geöffnet – Reservierung unbestätigt", and waits as long as the page
remains on checkout. You can interact with this same screen. Once you navigate
away, the worker can handle the next queued item.

If you want full manual control for longer, stop the worker while leaving the
browser running:

```bash
docker compose -f docker-compose.yml -f docker-compose.checkout.yml stop checkout-worker
```

The bot cannot cause a paid order: there is no automated checkout confirmation
or payment click anywhere in the source.

## Important limitations

- Original app maximum speed: **minimum 10-second polling**. New searches
  default to 10s on this branch. Existing saved searches have their own stored
  intervals and must be changed manually in the dashboard.
- Real elapsed detection latency depends on Vinted's indexing, network delay,
  rate limiting and queue length; microsecond API polling is not practical.
- If Vinted's button label or checkout URL changes, the automation fails
  safely and can send a failure email; it doesn't click another button.
- Real Vinted login, checkout behavior and SMTP delivery **not tested** here.
- A visible checkout could have an expired reservation. It must never be
  represented as a confirmed reservation without authoritative evidence.
- The noVNC port binds to **localhost only**. Do not expose it publicly:
  it permits remote control of a browser logged into your Vinted account.
- Cookies persist locally in a Docker volume; do not share the volume.
- No CAPTCHAs, rate limits or account restrictions are bypassed.

Diagnostics:

```bash
docker compose -f docker-compose.yml -f docker-compose.checkout.yml logs -f checkout-worker
```
