<div align="center">

**English** · [Français](README.fr.md)

<img src="docs/media/banner.svg" alt="vinted-sniper — get told the moment something matches" width="820">

[![CI](https://github.com/jasp-nerd/vinted-sniper/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/jasp-nerd/vinted-sniper/actions/workflows/ci.yml)
[![Container image](https://img.shields.io/badge/ghcr.io-vinted--sniper-2496ED?logo=docker&logoColor=white)](https://github.com/jasp-nerd/vinted-sniper/pkgs/container/vinted-sniper)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Watch a Vinted search and get a message when something new matches —<br>
in Telegram, Discord, or wherever else you want it.

</div>

You paste the URL of a search you already made on Vinted. It checks that search every minute
or so and tells you about listings that weren't there before. That's the whole idea.

<div align="center">
  <img src="docs/media/demo.gif" width="820" alt="Adding a search by pasting a Vinted URL, the saved searches with their health, and the listings arriving in Discord and Telegram">
</div>

## Quickstart

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Linux: [Docker Engine](https://docs.docker.com/engine/install/)).
2. Download [docker-compose.yml](https://raw.githubusercontent.com/jasp-nerd/vinted-sniper/main/docker-compose.yml) (right-click, "Save link as...") into a folder.
3. Open a terminal in that folder and run `docker compose up -d`.
4. Open **http://localhost:8000**. Paste a Discord webhook and a Vinted search URL, or build the search right there.

That's it. No sign-in, no config file. Terminal version of steps 2 and 3:

```bash
curl -O https://raw.githubusercontent.com/jasp-nerd/vinted-sniper/main/docker-compose.yml
docker compose up -d
```

No Docker? It's a normal Python app (3.13+, [uv](https://docs.astral.sh/uv/)):

```bash
git clone https://github.com/jasp-nerd/vinted-sniper.git && cd vinted-sniper
uv sync --extra web && uv run vinted-sniper run
```

Alerts arrive while your computer is on and awake. For alerts around the clock, run it on a
Raspberry Pi, NAS or cheap VPS: see [the self-hosting guide](docs/self-hosting.md).

## Features

- **Filters on what you actually pay**, buyer protection included. Vinted's own price filter ignores it.
- **Tells you when it stops working.** A watchdog spots a search going silent and fixes the session itself.
- **No Vinted account, no login, no cookies.** Nothing for Vinted to restrict.
- **Search builder in the dashboard**: Vinted's own categories, brand autocomplete and filters, with live counts.
- **Quiet on the first run.** No opening flood of ninety-six old listings.
- **Discord, Telegram, ntfy, RSS, or plain JSON webhooks**, with per-search routing.
- **Every country site**: `vinted.fr`, `.de`, `.nl`, `.co.uk`, `.com`, and the rest.

## Screenshots

<div align="center">
  <img src="docs/media/builder.png" width="820" alt="The search builder in the dashboard: site, search text and price fields, Vinted's category tree, brand autocomplete, and condition and colour checkboxes with live item counts">
  <br><sub>The search builder</sub>
  <br><br>
  <img src="docs/media/discord.png" width="820" alt="A Discord notification: the search it matched, the title linking to the listing, links to the item, dashboard and seller, then price with buyer protection included, size, condition, brand, location, seller rating and photo">
  <br><sub><b>Discord</b> — one rich card per listing, stacked into embeds when several land at once</sub>
  <br><br>
  <img src="docs/media/telegram.png" width="820" alt="The same kind of notification in Telegram: photo preview, price with buyer protection included, brand, size, condition, seller, and the same three buttons">
  <br><sub><b>Telegram</b> — photo as a preview, so the message keeps its buttons</sub>
</div>

## Docs

- [Configuration](docs/configuration.md): every setting, the CLI, notification channels, and the dashboard password for remote access. Nothing is required to start.
- [Self-hosting](docs/self-hosting.md): Raspberry Pi, NAS, VPS, updating, backups.
- [Troubleshooting](docs/troubleshooting.md): nothing arrives, 403s, and the one-line test that shows whether your IP is blocked.
- [Architecture](docs/architecture.md) and [REVIEW](docs/REVIEW.md): for working on the code.

Not affiliated with Vinted. It reads public listings anonymously and never logs in, buys, or
lists; Vinted's terms prohibit automated access, so running it is your own call. More in
[docs/legal.md](docs/legal.md).

MIT licensed. Contributions welcome — especially bug reports with logs attached.


## Experimental shared checkout (fork-specific)

> **Experimental; not production-ready.** The upstream search-and-notify app
> works separately from this optional add-on. The optional checkout workflow
> has **not** been verified end to end on Vinted. In particular, an open
> checkout does **not** establish that a listing is reserved.

### Current verified status (4 November 2026)

| Component | Status |
| --- | --- |
| Search dashboard (`http://localhost:8000`) | Started successfully in a local Docker run |
| Selenium Chromium / noVNC (`http://localhost:7900`) | Container started |
| Checkout worker (`http://localhost:8765/health`) | Running and awaiting manual login |
| Python safety tests | 15 passed before the latest additional test; rerun locally |
| Vinted account login via **Sign in with Apple** in Selenium Chromium | **Blocked**: Apple/Vinted identity verification failed in the reported environment |
| Real checkout, exclusive reservation and email delivery | **Not yet verified** |

The Selenium-based browser uses **one shared Chromium session** controlled
through noVNC. It does not share Safari's or your ordinary browser's
existing login. The worker has exactly one intended automated action:
click a safely identified **Kaufen** button on a listing when dry-run is
disabled. **It does not complete orders or submit payments.** Do not enable
live clicking until you have verified the browser login and tested the
workflow.

### Getting started with the fork

Unlike the upstream Quickstart above, this add-on requires a **local build**
and a private configuration file:

```bash
git clone https://github.com/4ronjo/vinted-sniper-reservation.git
cd vinted-sniper-reservation
git switch feature/checkout-snipe-email
cp checkout.env.example .checkout.env
# Edit .checkout.env locally: VNC password, random webhook token,
# optional sender SMTP credentials. Leave DRY_RUN=true.
docker compose --env-file .checkout.env \
  -f docker-compose.yml -f docker-compose.checkout.yml up -d --build
docker compose --env-file .checkout.env \
  -f docker-compose.yml -f docker-compose.checkout.yml ps
curl -sS http://127.0.0.1:8765/health
```

For an existing clone, use `git pull --ff-only` instead of cloning again.
The regular dashboard is at `http://localhost:8000`, and the shared
browser is at
`http://localhost:7900/vnc.html?autoconnect=1&resize=scale`.
Both are exposed on the local machine only.

**Manual login, including Apple / 2FA:** Sign in inside the noVNC Chromium
window and manually complete any authorized SMS or email challenge. The
worker starts at `awaiting-manual-login` and will not process listings
until you explicitly confirm the completed login through
`POST /control/login-confirmed/{your-webhook-token}`. This is a manual
acknowledgment, **not an automatic verification of session validity**.

**Known blocker:** A reported attempt to sign in to Vinted using
**Sign in with Apple** inside the Selenium-managed Chromium browser
failed with an identity-verification error. No code change has resolved
that login problem. If Apple or Vinted refuses the login, **do not**
confirm it in the worker, import Safari cookies, supply passwords or
one-time codes to the bot, or attempt to bypass the verification.
Instead, use the ordinary search/notification workflow and complete
any purchase manually in your normal browser. That fallback **does not**
preserve the exact same checkout session.

The default polling interval is 10 seconds for newly created searches;
existing saved searches retain their stored intervals. The checkout
worker's detection and email notifications are separate from the base
searcher, and SMTP delivery still needs a successful local test.

**Do not commit** `.checkout.env`, account credentials, browser profiles,
OTP codes, or session cookies. The Docker images and Vinted login
have not received a full end-to-end integration test. Automated access
may violate Vinted's terms.

For detailed setup, controls, known limitations, and macOS Docker
troubleshooting, see **[shared checkout documentation](docs/shared-checkout.md)**.
