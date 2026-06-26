# Terminus extension — landscape agenda

The display side of this project: a **Terminus extension** (self-hosted TRMNL
server), not a TRMNL cloud plugin. It renders a landscape (800×480) daily
agenda — big date + mini month calendar on the left, upcoming events grouped by
day on the right.

- **`agenda.liquid`** — the Liquid template. Paste its contents into the
  Terminus extension's markup editor. This file is the source of truth; keep it
  in sync with what's pasted in Terminus.

## Data source (exchange) setup

The template expects the API's day-grouped endpoint, exposed in Liquid as
`source_1`:

- **URL:** `http://<server>:<port>/upcoming?days=7`
  (optionally `&max_events=8` — the count cap that keeps the bottom edge clean;
  raise/lower it to fit more/fewer rows).
- **Headers (hash):** `{"X-API-Key": "<your terminus key>"}`
- **Polling:** every 15–30 min is plenty for e-ink.

### Response shape the template reads

```jsonc
{
  "today":    { "day": 26, "weekday_long": "Friday", "month_long": "June", "year": 2026 },
  "calendar": { "weekday_headers": ["Mo",…,"Su"], "weeks": [[1,…,7],…], "today": 26 },
  "days":     [ { "day": 26, "weekday_short": "Fri",
                  "events": [ { "name": …, "start": ISO, "end": ISO|null,
                                "all_day": false, "source": "Team L" } ] } ]
}
```

`weeks` uses `0` for padding cells (days outside the month); the template skips
those and circles the cell matching `calendar.today`.

## Font

Uses the TRMNL framework's **default built-in font**. To switch to the `Classic`
or `TRMNL` family, apply the framework's font-family class on the wrapper (the
exact class is in the framework docs / visible in the Terminus preview). The
layout fonts (sizes/weights) are in the scoped `<style>` block at the top.

## Where this lives / how it's shared

- **Stored here, in this repo.** Terminus keeps its own copy in its database,
  but that's not version-controlled and easy to lose, so `agenda.liquid` is the
  canonical copy. Edit here, then paste into Terminus.
- **Sharing:** Terminus extensions are not published to the TRMNL plugin
  marketplace (that's the cloud product). "Sharing" a Terminus extension means
  sharing this template file + the exchange setup above. To share with the wider
  TRMNL community you'd repackage it as a TRMNL **plugin** (a different format:
  `settings.yml` + markup, e.g. a `trmnlp` project) — not required for your own
  self-hosted use.
