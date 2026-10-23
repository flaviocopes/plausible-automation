---
name: setup-plausible
description: Install and operate self-hosted Plausible Community Edition using credentials and API tokens stored in macOS Keychain. Provision sites, add trackers, diagnose integrations, manage goals, compare periods, break down traffic, and export reports through the Stats API. Always use when the user asks to install or check Plausible, create/list/delete goals, report or compare analytics, break down traffic, or export Plausible data.
---

# Set Up and Operate Plausible

Use the bundled `scripts/plausible-setup` CLI. Do not use or suggest the Sites API.

Before the first operation, configure the user's own self-hosted Plausible origin:

```bash
plausible-setup configure --plausible-url https://plausible.example.com
```

Never assume a vendor, account, analytics origin, or tracked website domain. Let the CLI infer the tracked domain from the project, or pass `--domain example.com` explicitly.

## Install Plausible

1. Inspect the project and preserve unrelated changes.
2. Preview the integration:

   ```bash
   plausible-setup setup --dry-run
   ```

3. If login credentials are missing, ask the user to run this in a local interactive terminal:

   ```bash
   plausible-setup credentials
   ```

4. Install the property and tracker:

   ```bash
   plausible-setup setup
   ```

5. Inspect the diff and run the project's relevant checks and build.

Pass `--domain example.com` when domain inference is wrong and `--target path/to/layout` when the shared `<head>` file is ambiguous.

## API-key login and agent queries

For an existing instance, use `plausible`. Have the user run this in their
interactive terminal, entering a Stats API key at the hidden prompt:

```bash
plausible login --url https://plausible.example.com
```

Never ask for a key in chat. Login stores the key in Keychain without selecting a website. API access is
checked when requesting analytics. Login prints a readable confirmation; use
`login --json` for structured output. Subsequent commands never create or rotate keys. JSON is the default:

```bash
plausible status
plausible report --site example.com --period 30d --compare previous
plausible breakdown --site example.com --by page --filter source=Google
plausible timeseries --site example.com --period 30d
plausible realtime --site example.com
plausible query --site example.com --file query.json
plausible capabilities --json
```

Use `--site` to select the website for each analytics request. `query` accepts the complete
Stats API v2 body, including custom dates, filters, ordering, and pagination.
The API key controls access; the CLI cannot list sites through the Stats API.
`logout` removes CLI configuration and keeps the shared Keychain item.

## Report analytics

Run a human-readable report containing summary metrics, top pages, top sources, and goal conversions:

```bash
plausible-setup report --period 7d
```

Compare with the immediately preceding range:

```bash
plausible-setup report --period 7d --compare previous
```

Use `--format json`, `--format csv`, or `--format markdown` for structured exports. Use `--period 30d` and `--limit 20` when requested. The first report creates a Stats API key through the authenticated dashboard and stores it in Keychain without printing it. If the saved key is invalid, rotate it with:

```bash
plausible-setup stats-key --refresh
```

Treat reports as read-only. Summarize the returned values in plain language and name the domain and period.

Break down traffic by country, source, page, goal, device, browser, operating system, campaign, or `prop:NAME`:

```bash
plausible-setup breakdown --period 30d --by country
plausible-setup breakdown --by page --filter source=Google
```

Repeat `--filter NAME=VALUE` to combine exact filters; use `*` for a contains filter.

## Diagnose an installation

Run the read-only health check after setup or when analytics appear broken:

```bash
plausible-setup doctor --domain example.com
```

Report failed checks and warnings separately. `doctor` verifies the Plausible origin, tracker endpoint, project snippet, property, Stats API, and optional Plugins API token without creating keys or changing the site.

## Manage goals

Goal commands use Plausible CE's site-scoped Plugins API. A site needs one plugin token. If it is missing, direct the user to the URL printed by the CLI, then ask them to run this in a local interactive terminal:

```bash
plausible-setup plugin-token --domain example.com
```

Never ask the user to paste a token into chat.

List goals:

```bash
plausible-setup goals-list --domain example.com
```

Create or find a custom-event or pageview goal:

```bash
plausible-setup goal-add --domain example.com --event Signup
plausible-setup goal-add --domain example.com --page '/thank-you*'
```

Delete only when the user explicitly requests the exact goal:

```bash
plausible-setup goal-delete --domain example.com --goal-id 123 --yes
```

List goals first when an ID is not already known.

## Defaults

- Plausible URL: the value saved by `configure`, overridden by `--plausible-url` or `PLAUSIBLE_URL`
- Tracker: `<plausible-url>/js/script.js`
- Timezone: the Mac's IANA timezone, falling back to `UTC`
- Login Keychain service: `plausible:<host>`
- Stats key service: `plausible-stats:<host>`
- Plugin token service: `plausible-plugin:<host>:<domain>`
- Domain: Astro `site`, package `homepage`, or dotted project directory name

Run `plausible-setup --help` for overrides.

## Safety

- Keep passwords and tokens out of chat, argv, output, and logs.
- Use `--dry-run` before project changes.
- Treat existing properties, trackers, goals, and keys idempotently.
- Stop on authentication, CSRF, two-factor-authentication, ambiguous-layout, or unexpected-response errors.
- Require `--yes` for goal deletion and never delete API keys automatically.
- Do not replace or duplicate an existing analytics integration without inspection.
