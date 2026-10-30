# Shared-browser Vinted checkout add-on (EXPERIMENTAL)

This feature has **not** been verified on Vinted live. A checkout being open is
**not proof of a reservation**, and any temporary hold can expire even while
the browser remains open. Automated access may violate Vinted's terms.

**The bot NEVER submits an order or pays.** It has exactly one automated click
site: a button/link on an **item page** matching "Kaufen" / "Buy" exactly.
After it reaches checkout, it makes no further clicks and waits for you to leave
the checkout using the **same visible Chromium browser**.

## 1. Configure

Use the `feature/checkout-snipe-email` branch. The same live browser can be viewed through noVNC; it is NOT the Vinted tab in another browser or app.

Copy `checkout.env.example` to `.checkout.env`, then set:
- `SNIPER_CHECKOUT_WEBHOOK_TOKEN`: random secret of >=24 characters. Generate
  one with `openssl rand -hex 32`.
- `SNIPER_CHECKOUT_EMAIL_TO=theorieofgaming@gmail.com` (already the default).
- `SNIPER_SMTP_USER` and `SNIPER_SMTP_APP_PASSWORD` to Gmail SMTP sender
  credentials if you want email alerts. Use a **Google app password**, never
  your ordinary Gmail password.
- Keep `SNIPER_CHECKOUT_DRY_RUN=true` initially (opens listing but NOT checkout).

Set `SNIPER_VNC_PASSWORD` in **.checkout.env** alongside your other checkout settings. Do not add it to the original sniper's `.env` file (which is parsed with strict settings).

Never commit `.env` or `.checkout.env`. Vinted login happens interactively
inside the browser; no Vinted password belongs in either environment file.

## 2. Start Docker

```bash
docker compose --env-file .checkout.env -f docker-compose.yml -f docker-compose.checkout.yml up -d --build
```

Keep the shared browser open in a browser tab on your computer:

**http://localhost:7900/vnc.html?autoconnect=1&resize=scale**

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
docker compose --env-file .checkout.env -f docker-compose.yml -f docker-compose.checkout.yml up -d --force-recreate checkout-worker
```

## 4. Same checkout screen, no automatic payments

The bot navigates in the **already running** Chromium window seen through
noVNC. If it finds and clicks a supported listing-page Kaufen button and Vinted
opens checkout, the worker **stops all browser interactions**, emails
"Checkout geöffnet – Reservierung unbestätigt", and waits as long as the page
remains on checkout. You can interact with this same screen. Once you navigate
away, the worker can handle the next queued item.

For manual control, use the **pause endpoint** (see below) while leaving the worker running. Stopping the worker normally closes its managed browser session and should not be used to hold a checkout.

The bot cannot cause a paid order: there is no automated checkout confirmation
or payment click anywhere in the source.

## Important limitations

- Original app maximum speed: **minimum 10-second polling**. New searches
  default to 10s on this branch. Existing saved searches have their own stored
  intervals. To use 10 seconds, delete and re-create those searches with the
  10-second interval in the dashboard (the upstream UI has no interval edit).
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
docker compose --env-file .checkout.env -f docker-compose.yml -f docker-compose.checkout.yml logs -f checkout-worker
```

## Manual pause/resume

You can pause automatic navigation without closing the shared browser:

```bash
TOKEN=$(sed -n 's/^SNIPER_CHECKOUT_WEBHOOK_TOKEN=//p' .checkout.env)
curl -X POST "http://127.0.0.1:8765/control/pause/$TOKEN"
# Later, after leaving the checkout:
curl -X POST "http://127.0.0.1:8765/control/resume/$TOKEN"
```

The worker's control API is bound to the host loopback address only. Never expose
it directly on the public internet. In noVNC, leave the tab open to see the
checkout immediately; clicking the view link in an email also opens the **same
remote browser instance**, not a new checkout session. For access from your phone,
set up private authenticated VPN access (e.g., Tailscale); localhost URLs work
only on the computer running Docker.

## Checkout verification (critical)

The checkout URL alone is **not evidence** that the purchase screen is usable.
By default the worker reports `Checkout-URL erreicht – Oberfläche UNBESTÄTIGT`.
It never claims that an item has been reserved.

To enable a stronger *UI-rendered* signal, manually visit a real Vinted checkout
in the shared browser (without paying), inspect its DOM, and identify a stable
TWO different CSS selectors only present in a properly rendered checkout,
such as separate verified order-summary and delivery sections. Set both
`SNIPER_CHECKOUT_READY_CSS` and `SNIPER_CHECKOUT_DETAILS_CSS` in
`.checkout.env` to those manually verified selectors. If either is missing,
the checkout remains UNVERIFIED.
Optionally set `SNIPER_CHECKOUT_ERROR_CSS` to a selector for a Vinted checkout
error banner. Restart only the worker to apply settings. If these reliable
selectors cannot be determined, **leave them blank** and use the cautious notice.

Even a verified checkout UI **does not prove an exclusive reservation**.
That must be confirmed separately with a permitted, controlled two-account
seller/buyer test or Vinted-provided explicit reservation state, observing
whether the second participant can still buy before and after opening checkout.
Never finalize an order during this test. If no authoritative observation is
possible, keep the status `reservation unverified`.

The buy control is only clicked when exactly one safe listing-level candidate
exists; checkout links must contain the current listing ID. If Vinted changes
its markup, the worker fails rather than guessing a payment-related control.

## Buy-button dry-run diagnostics

With `SNIPER_CHECKOUT_DRY_RUN=true`, incoming listings are opened but NO
button is clicked. A read-only audit records the number of visible controls
labeled exactly like Kaufen/Buy, and how many are eligible under the strict
safety rules. You will receive this summary in the test email.

- `safely eligible: 1` means one potentially actionable control was
  identified; it is **not** proof the live checkout will work.
- `safely eligible: 0` means a manual review of the live site's HTML is
  required. Do not remove payment-safety exclusions just to force a click.
- More than one eligible control means the bot deliberately refuses to click.

This diagnostic does not read card details, credentials or payment forms.
Inspect the actual Vinted listing/checkout within your own noVNC session
before configuring the two checkout verification selectors.
