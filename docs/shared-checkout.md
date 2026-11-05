# Shared-browser Vinted checkout add-on (EXPERIMENTAL)

This feature has **not** been verified on Vinted live. A checkout being open is
**not proof of a reservation**, and any temporary hold can expire even while
the browser remains open. Automated access may violate Vinted's terms.

**The bot NEVER submits an order or pays.** It has exactly one automated click
site: a button/link on an **item page** matching "Kaufen" / "Buy" exactly.
After it reaches checkout, it makes no further clicks and waits for you to leave
the checkout using the **same visible Chromium browser**.

## Selenium: manual-first mode (no login automation)

**The Selenium/browser checkout mode remains experimental and has not
been accepted by Vinted in the reported session.** The changes below
do not conceal Selenium or bypass Vinted's anti-automation controls.

The Selenium worker now opens Chromium **without visiting Vinted at
startup**. This avoids an unnecessary automated login-page navigation,
but Chrome will still be an automated browser and Vinted may reject it.

1. Keep `SNIPER_CHECKOUT_DRY_RUN=true` and
   `SNIPER_CHECKOUT_ALERT_ONLY=false` in your private `.checkout.env`.
   `SNIPER_SELENIUM_OPEN_HOME_ON_CONNECT=false` is the default.
2. Start the three standard services:

   ```bash
   docker compose --env-file .checkout.env -f docker-compose.yml \
     -f docker-compose.checkout.yml up -d --build
   ```

3. Open `http://localhost:7900/vnc.html?autoconnect=1&resize=scale`,
   enter the VNC password, and **manually** visit `https://www.vinted.de`.
   Sign in yourself using a method Vinted supports for your account.
   Complete any required verification directly on the provider site.
4. Only if login really succeeded, confirm using the existing
   `/control/login-confirmed/{secret}` endpoint (instructions below).
   `/health` distinguishes manual acknowledgment from verified identity.

If Vinted displays **"Your session has been blocked"** or a notice
of unusual/automated activity, the worker records
`"platform_blocked": true` and
`"status": {"stage": "platform-blocked", ...}`, clears login
confirmation, and **stops all further browser navigation or clicks**.
`/control/resume` and `/control/login-confirmed` then reject with
HTTP 409. No repeated login attempts, random delays, or spoofing
are performed. A restart is not an instruction to retry against an
existing platform-side block; use Vinted support or the email-only
notification mode instead.

The existing worker does **not** control the separate human-operated
Chromium desktop at `https://localhost:7901`. That remains a
manual-only alternative.

## Confirmed Selenium login block and safe fallback

On **5 November 2026**, Vinted displayed **"Your session has been blocked"**
in the Selenium-managed Chromium browser, citing unusual or automated
activity. An earlier **Sign in with Apple** attempt failed identity
verification. This is a block from the platform; longer or randomized
waits are not a verified fix. The shared-browser checkout is therefore
**not working in that reported environment**.

### Human-operated Chromium without Selenium (new)

The experimental shared-browser session was blocked by Vinted, so there is
now a **separate, ordinary Chromium desktop** in
[`docker-compose.manual-chromium.yml`](../docker-compose.manual-chromium.yml).
It is a Chromium browser you control manually through a local web desktop;
it does **not** launch through Selenium or expose a WebDriver session.

On the Mac, from the repository root:

```bash
# Stop Selenium's blocked browser and its checkout worker; leave the
# original search dashboard running.
docker compose --env-file .checkout.env \
  -f docker-compose.yml -f docker-compose.checkout.yml \
  stop browser checkout-worker

# Start ordinary, manual Chromium only.
docker compose --env-file .checkout.env \
  -f docker-compose.manual-chromium.yml up -d

docker compose --env-file .checkout.env \
  -f docker-compose.manual-chromium.yml ps
```

Then open **https://localhost:7901** in your Mac's browser. The
LinuxServer Chromium desktop uses **HTTPS with a self-signed
certificate**; a local certificate warning is expected. It prompts
for username **`local`** and the existing
`SNIPER_VNC_PASSWORD` from your private `.checkout.env` file.
Only the local machine can connect to this port.

Manually sign in to Vinted inside this separate Chromium desktop via
**Sign in with Apple** or any other login method supported by your
account. Enter Apple/Vinted passwords and any 2FA code **only in the
official login pages**, never in a bot configuration file or chat.
This browser has its **own persistent `manual-chromium-config`
volume**, separate from Selenium's existing blocked session.

**Scope and limits:**
- This gives you a real, human-operated Chromium desktop without
  Selenium. We have **not verified** that Vinted will accept sign-in
  in this Docker environment. A platform-side/IP/account restriction
  may remain even without Selenium.
- The manual Chromium desktop is **NOT** controllable by the existing
  Selenium checkout worker; it does not implement the same-checkout
  automation, buy clicks, or reservations. Those remain unavailable.
- Keep using the original dashboard for search alerts, or use the
  email-only worker fallback below. Open listing links manually in
  this Chromium desktop or in regular Mac Chrome.
- If Vinted still reports your session blocked, stop retrying and
  use its official support or an ordinary local browser. There is
  no bypass or randomized-request workaround here.

Docker image documentation:
[LinuxServer Chromium](https://docs.linuxserver.io/images/docker-chromium/).
Its remote desktop can expose a terminal with elevated container privileges,
so **never expose port 7901 to your LAN or the internet**. The supplied
compose file binds it to `127.0.0.1` only.

### Continue using the bot for item alerts

You can sign in normally to Vinted in your ordinary Safari/Chrome browser
and run the original search/notification app separately. For email
notifications through the experimental worker, enable this **optional
email-only fallback** in your *private* `.checkout.env`:

```dotenv
SNIPER_CHECKOUT_ALERT_ONLY=true
SNIPER_CHECKOUT_DRY_RUN=true
SNIPER_SMTP_USER=your-sender@example.com
SNIPER_SMTP_APP_PASSWORD=your-private-email-app-password
SNIPER_CHECKOUT_EMAIL_TO=your-recipient@example.com
```

Use genuine sender credentials in the local file only, never in git or
chat. This mode requires all three SMTP values. If you already connected
saved searches to the checkout-worker webhook, keep their routing. Then
rebuild just the worker:

```bash
docker compose --env-file .checkout.env -f docker-compose.yml \
  -f docker-compose.checkout.yml up -d --build checkout-worker
curl -sS http://127.0.0.1:8765/health
```

Health should report `"mode": "alerts-only"`. In this mode, incoming
webhook listings are emailed with a direct listing URL, and **no Selenium
session is created by the worker**. It neither opens checkout, reserves
an item, nor confirms a purchase. You must follow the link manually in
the normal signed-in browser. The original dashboard's Discord,
Telegram, ntfy and webhook notification options also remain available
without using the checkout worker.

To return to the experimental shared-browser mode, set
`SNIPER_CHECKOUT_ALERT_ONLY=false`, keep dry-run enabled, and restart
the worker. This does **not** resolve Vinted's existing block: do not
manually confirm login unless it actually succeeds.

---

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

Authenticate with your VNC password, then manually navigate to Vinted and
log into your account inside that Chromium browser. It is the **same browser** the sniper later
uses; it does not open a second checkout in a separate local window.

**Manual SMS/email verification:** Vinted can require a one-time code when
signing in. Read the code on your own phone or in your linked mailbox and
enter it **directly into the Vinted page** in the shared noVNC browser.
Neither the phone number nor the code needs to be configured in this project.
The worker **will not navigate to new listings until you explicitly confirm**
that the login (including any verification challenge) is finished:

```bash
TOKEN=$(sed -n 's/^SNIPER_CHECKOUT_WEBHOOK_TOKEN=//p' .checkout.env)
curl -X POST "http://127.0.0.1:8765/control/login-confirmed/$TOKEN"
curl -s http://127.0.0.1:8765/health
```

Health should report `login_confirmed_by_user: true`. This is your manual
acknowledgment, **not automatic proof** that Vinted accepted your login.
If you later encounter a fresh verification or login prompt, use
`/control/login-required/$TOKEN`, complete it manually, and confirm again.
Any failed automated checkout attempt automatically returns to the manual
review gate. **Never put codes or credentials into GitHub, logs or chat.**


The original search dashboard is at http://localhost:8000.

## 3. Connect saved searches

In the original sniper dashboard create a **Webhook** destination pointing to

```
http://checkout-worker:8765/hook/YOUR_CHECKOUT_WEBHOOK_TOKEN
```

Replace the last segment with the same secret configured above, then route
your chosen saved searches to it. The existing search filters and max total
price rules still apply.

To test: finish the login confirmation first, then create a saved search and wait for a new matching article. In dry run,
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

## Docker command is not recognized on macOS

If `docker compose --env-file ...` shows `unknown flag: --env-file`
or `docker: 'compose' is not a docker command`, Docker Compose V2 is not
available through the Docker CLI. This is a **host installation issue**, not
a Vinted sniper error. Check:

```bash
docker --version
docker compose version
docker info
```

On a Mac, install or update **Docker Desktop** (with the included Compose V2
plugin), then start Docker Desktop and verify that `docker compose version`
works before running the commands above. Simply reinstalling Python packages
will not fix a missing Docker Compose command.

If `git clone` says the destination directory already exists, don't clone
again: run `cd ~/vinted-sniper-reservation && git pull --ff-only`.

## Mac: missing docker-credential-desktop during image pulls

If Docker Compose starts building but fails while downloading a base image with
`exec: "docker-credential-desktop": executable file not found in $PATH`,
this is a **local Docker Desktop credential helper issue**. It occurs before
our app is built and cannot be corrected by editing the Sniper's Dockerfile.

Check whether the helper is installed under the user CLI directory or inside
the Docker Desktop app bundle:

```bash
ls -l "$HOME/.docker/bin/docker-credential-desktop" \
  /Applications/Docker.app/Contents/Resources/bin/docker-credential-desktop 2>/dev/null
command -v docker-credential-desktop
```

If present but not found, in the current terminal session run:

```bash
export PATH="$HOME/.docker/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
command -v docker-credential-desktop
```

Then retry the Docker Compose build. For a permanent fix, update your shell's
PATH or use **Docker Desktop > Settings > Advanced > CLI tools installation**.
If neither location contains the helper, repair the Docker Desktop CLI install.

A temporary alternative for **public** images is to back up `~/.docker/config.json`
and remove the stale top-level `credsStore: desktop` setting, but that changes
credential handling for future `docker login` commands; restoring the helper
is preferable. Never rename `credsStore` to an unsupported key.
