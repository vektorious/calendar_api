# Calendar Aggregator API

A small FastAPI service that aggregates events from multiple calendar
sources (`.ics` URLs, CalDAV servers like Nextcloud) and exposes them as
plain JSON, protected by an API key, packaged for Docker/Portainer, and
designed to feed a TRMNL e-ink display via Terminus.

## Endpoints

- `GET /today` — all events happening today, merged from every configured source, sorted by start time. **Requires API key.**
- `GET /events?on=YYYY-MM-DD` — same, for an arbitrary date. **Requires API key.**
- `GET /health` — lists which sources are loaded. Deliberately open (no key) so container/Portainer healthchecks don't need a secret.

Pass your API key via the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-key-here" http://localhost:8000/today
```

Example response:

```json
[
  {
    "name": "Dentist appointment",
    "start": "2026-06-25T08:00:00+00:00",
    "end": "2026-06-25T08:30:00+00:00",
    "all_day": false,
    "location": null,
    "source": "Nextcloud Personal",
    "uid": "abc123@nextcloud"
  }
]
```

## Running locally without Docker

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export API_KEYS="some-dev-key"
uvicorn app.main:app --reload --port 8000
```

## Running with Docker (local)

1. Copy `.env.example` to `.env` and fill in real values:
   ```bash
   cp .env.example .env
   # generate a strong key:
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Create your `sources.yaml` from the example and edit in your real
   calendar sources (see below). `sources.yaml` is gitignored so your
   private calendar URLs are never committed:
   ```bash
   cp sources.yaml.example sources.yaml
   ```
3. Build and run:
   ```bash
   docker compose up --build
   ```
4. Test:
   ```bash
   curl -H "X-API-Key: your-key-from-.env" http://localhost:8000/today
   ```

## Deploying with Portainer (repository stack)

The `docker-compose.yml` is parameterised so it runs unchanged as a
Portainer **Repository stack** that builds straight from this Git repo. Two
env vars adapt it to a remote host:

- `SOURCES_FILE` — absolute path to your real `sources.yaml` on the host
  (the gitignored config isn't in the repo checkout, and the default
  `./sources.yaml` would resolve to Portainer's managed stack directory).
- `HOST_PORT` — the published host port (defaults to `8000`). Set it to
  avoid clashing with anything else on the host.

### 1. Put your config on the host (via SSH)

This file lives on the host, not in the repo (it's gitignored), so write it
directly — there's nothing to `cp` from on the host. The password stays as a
`${...}` placeholder; the app resolves it from the container environment at
load time, so no secret is written to this file:

```bash
sudo mkdir -p /opt/calendar-api
sudo tee /opt/calendar-api/sources.yaml > /dev/null <<'EOF'
sources:
  - type: ics_url
    name: "Public Holidays"
    url: "https://example.com/holidays.ics"

  - type: caldav
    name: "Nextcloud Personal"
    url: "https://your-nextcloud.example.com/remote.php/dav/calendars/your-username/personal/"
    username: "your-username"
    password: "${NEXTCLOUD_APP_PASSWORD}"
EOF
sudo nano /opt/calendar-api/sources.yaml   # edit in your real sources
sudo chmod 644 /opt/calendar-api/sources.yaml
```

(If you'd rather start from the committed sample, copy the contents of
`sources.yaml.example` from the repo on GitHub. The format reference is in
the [Configuring](#configuring-a-nextcloud-calendar-recommended-approach-caldav)
sections below.)

### 2. Create the stack in Portainer

1. **Stacks → Add stack**, name it `calendar-api`.
2. **Build method: Repository.**
   - Repository URL: this repo's clone URL
   - Reference: `refs/heads/main`
   - Compose path: `docker-compose.yml`
   - If the repo is private, enable Authentication and add a GitHub
     username + personal access token.
3. **Environment variables** (these feed the `${...}` substitutions in the
   compose file — no `.env` needed):

   | Name | Value |
   |---|---|
   | `API_KEYS` | your generated key(s), comma-separated |
   | `NEXTCLOUD_APP_PASSWORD` | your Nextcloud app password (only if using a caldav source) |
   | `SOURCES_FILE` | `/opt/calendar-api/sources.yaml` |
   | `HOST_PORT` | e.g. `8087` (optional; defaults to `8000`) |

4. **Deploy.** Portainer clones the repo, builds the image from the
   Dockerfile, and starts the container. Use Portainer's container Logs view
   in place of `docker logs`, and check the container reports `healthy`.

### 3. Verify

```bash
curl http://SERVER_IP:HOST_PORT/health
curl -H "X-API-Key: YOUR_KEY" http://SERVER_IP:HOST_PORT/today
```

### Updating later

- **Calendars:** edit `/opt/calendar-api/sources.yaml` on the host and
  restart the container (config is loaded once at startup).
- **Code:** push to `main`, then use Portainer's **Pull and redeploy** to
  rebuild from the latest commit.

### Prebuilt image instead of building on the server

If you'd rather not build on the Portainer host, build/push the image to a
registry (GHCR, Docker Hub, a self-hosted registry) and change `build: .`
to `image: yourregistry/calendar-api:latest` in `docker-compose.yml`.

## API key management

- Set `API_KEYS` as a comma-separated list — one key per consumer (e.g. one for Terminus, one for testing from your laptop). This lets you revoke a single key without affecting others.
- If `API_KEYS` is unset or empty, the service **fails closed**: every request to a protected endpoint gets a `503`, rather than silently running open.
- Keys are compared using a constant-time comparison to avoid timing attacks.
- `/health` is intentionally not protected — it returns only source *names*, not URLs/credentials/event data, and Docker/Portainer healthchecks need something they can hit without a secret.

## Configuring a Nextcloud calendar (recommended approach: CalDAV)

CalDAV is the better choice over an `.ics` link for your own Nextcloud
calendars because it works with private calendars and supports efficient
server-side date filtering.

1. **Find your CalDAV URL.** It's:
   ```
   https://your-nextcloud.example.com/remote.php/dav/calendars/YOUR_USERNAME/CALENDAR_NAME/
   ```
   You can see your calendar's URI (the last path segment) in the Nextcloud
   Calendar app under that calendar's settings → "Copy link" or "Edit".
   If unsure, you can point the `url` field at the calendar *home* instead
   (`.../calendars/YOUR_USERNAME/`) and add `calendar_name: "Personal"` to
   pick a specific one.

2. **Create an app password.** Don't use your real Nextcloud password.
   Go to Nextcloud → Settings → Security → "Create new app password",
   and use that instead.

3. **Don't put the password in `sources.yaml` directly.** Use the
   `${ENV_VAR}` placeholder syntax shown in `sources.yaml.example` — it's
   resolved from the environment (which Docker Compose / Portainer inject)
   at load time, so the secret never sits in a file on disk.

## Configuring an .ics URL source

Useful for public/shared calendars (holiday calendars, a public Google
Calendar export link, someone else's published Nextcloud subscription
link, etc.) where you don't have/need credentials. Just provide the URL —
see `sources.yaml.example` for the format. Recurring events (RRULE) are expanded
automatically.

## Adding a new backend type

1. Create `app/sources/your_backend.py`, subclass `CalendarSource` from
   `app/sources/base.py`, and implement `async def get_events_for_date(self, day)`.
2. Register it in `SOURCE_TYPES` in `app/config.py`.
3. Reference it by that key in `sources.yaml`.

That's the entire extension point — the aggregation, sorting, auth, and
endpoint logic in `app/main.py` never need to change.

## Feeding this into Terminus / a TRMNL e-ink display

[Terminus](https://github.com/usetrmnl/terminus) is the open-source,
self-hosted server for TRMNL e-ink devices — it polls data sources and
renders dashboards onto the display. The path from here to "daily agenda
on my e-ink screen" is:

1. Run this API somewhere Terminus can reach it (same Docker network, or
   over your LAN/server IP).
2. In Terminus, build a **private plugin** whose data source is this API's
   `/today` endpoint, sending the `X-API-Key` header. Terminus plugins
   support a polling URL + headers + a templating layer (typically
   Liquid-style) to turn the JSON into a rendered layout.
3. Map fields from the response (`name`, `start`, `end`, `all_day`,
   `location`) into whatever layout/template you want on the e-ink panel —
   e.g. a simple list, grouped by time of day.
4. Set the plugin's refresh interval to whatever's reasonable for an
   e-ink device (e.g. every 15–30 min; e-ink doesn't need to refresh often
   and frequent polling just wastes the device's battery and your API's
   resources).

This part — the actual Terminus plugin template/config — is a good fit for
Claude Code, since it benefits from iterating directly against your real
Terminus instance and seeing the rendered output rather than guessing
blind.

## Notes / known limitations

- All sources are queried concurrently and a failing source is logged and
  skipped rather than failing the whole request (see `/health` to debug
  which sources are configured).
- Config is loaded once at process start. Restart the container after
  editing `sources.yaml`.
- Timezone handling: every event's start/end is normalized to a
  timezone-aware UTC datetime so multiple sources sort together
  correctly, regardless of each source's original timezone.

