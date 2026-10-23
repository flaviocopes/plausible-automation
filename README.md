# Plausible Automation Toolkit

This is one of the software packages I publish with full source. The landing page is https://flaviocopes.com/software/plausible-automation/.

It is MIT licensed. You can use it, fork it and change it, also for commercial work.

There is no support. Issues, pull requests, discussions, and the wiki are turned off, and there is no roadmap. Forks are welcome.

If you point a coding agent at this repository, have it read `AGENTS.md` first.

## Table of contents

- [What it does](#what-it-does)
- [Requirements](#requirements)
- [Install](#install)
- [First run](#first-run)
- [Health, reports, and goals](#health-reports-and-goals)
- [Codex use](#codex-use)
- [Run the tests](#run-the-tests)
- [Architecture](#architecture)
- [How it was built](#how-it-was-built)
- [Configuration](#configuration)
- [Installation and distribution](#installation-and-distribution)
- [Customization](#customization)
- [Security](#security)
- [Technical decisions](#technical-decisions)
- [Changelog](#changelog)
- [License](#license)

## What it does

Plausible Automation Toolkit is a macOS command-line tool and Codex skill for
operating a self-hosted Plausible Community Edition instance. It can create a
website property through the authenticated dashboard, install the tracking
script in a project, produce traffic reports, and manage goals.

You supply both values that identify your setup:

- the HTTPS origin of your own Plausible instance;
- the public domain of each website you operate.

This repository contains no real domain, login, API key, plugin token, or
analytics data. Every example uses `example.com` or `plausible.example.com`.

Current release: **1.0.0**.

## Requirements

- macOS with the `security` and `expect` commands
- Python 3.10 or newer
- a self-hosted Plausible Community Edition account
- a website project with one shared file containing `</head>`
- Codex if you want natural-language skill triggering; the CLI works directly

The implementation is intentionally macOS-first because all secrets are stored
in login Keychain.

## Install

Clone the repository, open Terminal in it, and run the installer:

```bash
git clone https://github.com/flaviocopes/plausible-automation.git
cd plausible-automation
./install.sh --plausible-url https://plausible.example.com
```

Replace the example URL with the HTTPS origin of your own Plausible instance.
The installer copies the skill to `~/.codex/skills/setup-plausible` and the CLI
to `~/.local/bin/plausible-setup`.

If `~/.local/bin` is not on `PATH`, add this to `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then open a new Terminal window.

## First run

Store the Plausible dashboard login in Keychain:

```bash
plausible-setup credentials
```

From a website project, preview and apply the integration:

```bash
plausible-setup setup --dry-run
plausible-setup setup
```

The CLI infers the tracked domain from Astro's `site`, `package.json`'s
`homepage`, or a dotted project-directory name. Override it whenever needed:

```bash
plausible-setup setup --domain shop.example.com --target src/layouts/Layout.astro
```

## Health, reports, and goals

```bash
plausible-setup doctor --domain example.com
plausible-setup report --domain example.com --period 7d
plausible-setup report --domain example.com --period 30d --compare previous
plausible-setup breakdown --domain example.com --period 30d --by country
plausible-setup breakdown --domain example.com --by page --filter source=Google
plausible-setup report --domain example.com --format markdown
plausible-setup goals-list --domain example.com
plausible-setup goal-add --domain example.com --event Signup
plausible-setup goal-add --domain example.com --page '/thank-you*'
```

`doctor` checks the instance, tracker endpoint, project snippet, property,
Stats API, and optional goal token without changing anything. Reports support
text, JSON, CSV, and Markdown output. The first report creates a Stats API key
through the authenticated dashboard and saves it in Keychain. Goal commands
require one site-scoped plugin token; the CLI prints the exact dashboard URL
and stores the resulting token through a secure Terminal prompt.

## Codex use

After installation, ask Codex things like:

- “Install Plausible on this site.”
- “Show me Plausible traffic for the last 30 days.”
- “Add a Signup goal in Plausible.”

The skill tells Codex to inspect changes, keep secrets out of chat, preview
tracker edits, and avoid Plausible's Sites API.

## Run the tests

From the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 setup-plausible/scripts/plausible-setup --version
```

The eight tests use a local fake server. They do not contact Plausible, change
a real site, or read your Keychain.

## Architecture

### Overview

The toolkit has two entry points over one implementation:

```text
Developer or Codex request
          |
          v
   plausible-setup CLI
    /       |       |       \
 doctor  dashboard  Stats   Plugins
 checks    session   API v2    API
             |         |       |
          property   reports   goals
      |
 project tracker edit

Secrets -> separate macOS Keychain items
Config  -> ~/.config/plausible-setup/config.json
```

Codex loads `setup-plausible/SKILL.md` when a request concerns installation,
traffic reporting, or goals. The skill delegates deterministic work to the
bundled CLI.

### Configuration and identity

The Plausible origin is selected in this order:

1. `--plausible-url` for one invocation;
2. `PLAUSIBLE_URL` for one process environment;
3. the value saved by `plausible-setup configure`.

The tracked domain is selected independently from `--domain`, Astro's `site`,
`package.json`'s `homepage`, or the project directory name. This separation is
what allows one CLI installation to operate many websites on one Plausible
instance.

### Dashboard flow

Property creation and Stats key generation use an authenticated cookie session.
The CLI fetches the current HTML forms, preserves hidden inputs including CSRF
tokens, submits the documented dashboard fields, follows redirects, and checks
the resulting state. It does not use the Sites API.

### Tracker flow

The CLI finds a shared layout or HTML file containing a standalone `</head>`,
builds a script tag from the configured origin and resolved website domain,
and produces a unified diff. It refuses ambiguous layouts and existing
analytics snippets instead of guessing.

### Reporting flow

The first report creates a Stats API key and hands the generated value directly
to the Keychain helper over standard input. Reports query Stats API v2 for the
summary, top pages, top sources, and goal conversions. Output can be human
readable, JSON, CSV, or Markdown. Comparison reports calculate the immediately
preceding calendar range locally and query both periods. Breakdowns map stable
CLI aliases to Stats API dimensions and translate repeatable `NAME=VALUE`
filters into structured API filters.

### Diagnostic flow

`doctor` performs independent read-only checks and retains every result instead
of stopping at the first problem. Missing optional keys are warnings; instance,
tracker, property, project-snippet, or API failures make the command non-zero.

### Goal flow

Each website has its own Plugins API token. The CLI authenticates with the
tracked domain and token, then lists, creates, or deletes custom-event and
pageview goals. Deletion requires both an exact numeric ID and `--yes`.

## How it was built

The runtime is plain Python and does not have a build step. Release work is
about validating source, tests, permissions, and documentation.

### Local checks

From the repository root:

```bash
python3 -m py_compile setup-plausible/scripts/plausible-setup
python3 -m unittest discover -s tests -v
setup-plausible/scripts/plausible-setup --version
setup-plausible/scripts/plausible-setup --help
```

Validate the skill with Codex's `quick_validate.py` when that helper is
available. The required frontmatter fields are `name` and `description`.

### Installer test

Use a temporary home directory when validating file placement. Do not point a
release test at a real Plausible instance or login Keychain.

The installer must place:

- the complete skill at `$CODEX_HOME/skills/setup-plausible`, falling back to
  `~/.codex/skills/setup-plausible`;
- `plausible-setup` and its Keychain helper in `~/.local/bin`.

### Release checklist

1. Update `VERSION` in the CLI and the [changelog](#changelog) together.
2. Run the unit tests and syntax check.
3. Search the repository for private domains, email addresses, paths, and secrets.
4. Confirm every example uses `example.com` or `plausible.example.com`.
5. Confirm executable bits on `install.sh` and both bundled scripts.
6. Tag the release in Git and check the tagged tree from a fresh clone.

## Configuration

### Plausible instance origin

Configure the HTTPS origin of your own instance:

```bash
plausible-setup configure --plausible-url https://plausible.example.com
```

The origin is saved at `~/.config/plausible-setup/config.json`. It is not a
secret. For temporary overrides, use either:

```bash
PLAUSIBLE_URL=https://analytics.example.com plausible-setup report --domain example.com
plausible-setup report --plausible-url https://analytics.example.com --domain example.com
```

`--plausible-url` has highest precedence, then `PLAUSIBLE_URL`, then the saved
configuration.

### Tracked website domain

The website domain is separate from the Plausible origin. Pass it explicitly:

```bash
plausible-setup setup --domain example.com
```

Without `--domain`, the CLI checks Astro's `site`, `package.json`'s `homepage`,
then a dotted project-directory name. `www.` is normalized away. The tracker
uses the resolved domain in `data-domain`, and the same value identifies the
Plausible property and Plugins API account.

### Tracker target

The CLI prefers common Astro, Svelte, and static HTML entry points. Override an
ambiguous project with a path inside the project root:

```bash
plausible-setup setup --target src/layouts/Shell.astro
```

### Timezone

Property creation uses `--timezone`, then `TZ`, then the Mac's local IANA zone,
and finally `UTC`.

### Keychain services

For a Plausible origin hosted at `plausible.example.com`, the defaults are:

```text
plausible:plausible.example.com
plausible-stats:plausible.example.com
plausible-plugin:plausible.example.com:example.com
```

They hold the dashboard login, Stats API key, and one website's plugin token.
Advanced users can override service names through the matching CLI flags.

### Plugin token setup

Run the command below. It prints the exact site integration URL, then waits for
the token at a secure Keychain prompt:

```bash
plausible-setup plugin-token --domain example.com
```

Create the token in the browser, paste it in Terminal, and do not paste it into
an AI chat, issue, or configuration file.

## Installation and distribution

### Install for one macOS account

From the repository root:

```bash
./install.sh --plausible-url https://plausible.example.com
```

The installation is local to the current user and does not need `sudo`.

### Configure later or change instances

```bash
plausible-setup configure --plausible-url https://analytics.example.com
```

Changing the origin changes the default Keychain service names because they
are derived from the configured host. Credentials for the old origin remain in
Keychain until you remove them deliberately.

### Upgrade

Pull the newer version and run the installer again. It replaces the installed
scripts and skill files while preserving the configuration file and Keychain
items. Review the [changelog](#changelog) first when command behavior changes.

### Remove

Delete these non-secret installed files manually:

```text
~/.codex/skills/setup-plausible/
~/.local/bin/plausible-setup
~/.local/bin/plausible-keychain-store
~/.config/plausible-setup/config.json
```

Keychain secrets are intentionally not removed by an uninstall script. Review
and delete the matching `plausible:`, `plausible-stats:`, and
`plausible-plugin:` items in Keychain Access only when they are no longer
needed.

### Distribute a derivative

Keep the MIT license notice, remove all real credentials and account data, run
the test suite, and verify your fork from a fresh clone before shipping.

## Customization

### Change domain discovery

Extend `infer_domain()` to read another framework's canonical-site setting.
Keep `--domain` as the final explicit override and test normalization for
subdomains, `www`, paths, and invalid hostnames.

### Support another project layout

Add a preferred shared-head path in `resolve_target()` or pass `--target` from
the skill. Preserve the rule that multiple plausible targets are an error.

### Add report sections

Add another Stats API v2 query in `build_report()` and render it in
`format_report()`. Keep JSON output stable or version its structure when making
breaking changes.

Useful additions include cohorts, funnels, revenue attribution, annotations,
and richer multi-period trend summaries.

### Add exports or scheduled summaries

Build CSV or Markdown formatters around the report object. A scheduler should
invoke the CLI with read-only report commands and should never place Keychain
secrets in a shell script or job definition.

### Port secret storage

The current release is macOS-first. Linux Secret Service and Windows Credential
Manager can be added behind `keychain_account()`, `keychain_secret()`, and the
two storage functions. Do not fall back to a plaintext token file by default.

### Rebrand the skill

Update the skill folder name, `SKILL.md` frontmatter, `agents/openai.yaml`,
installer destinations, and helper lookup paths together. Validate triggering
with realistic user phrases after renaming.

## Security

### Protected values

The dashboard password, generated Stats API key, and site-scoped plugin tokens
are secrets. The configured Plausible origin and public website domains are not.

### Storage model

Secrets live in separate macOS login Keychain generic-password items. Login
accounts use the Plausible email as the Keychain account. Stats keys use a
non-secret label, and plugin tokens use the tracked website domain.

Interactive passwords and plugin tokens are entered through `security -w`.
Generated Stats keys are sent to the Expect helper over standard input. The
tool never intentionally prints secret values or places them in command-line
arguments.

### Network boundaries

The configured Plausible origin must be HTTPS. The CLI communicates only with
that origin for dashboard sessions, Stats API queries, and Plugins API goal
operations. It does not send credentials to the tracked website project.

### Project-edit boundary

`setup --dry-run` prints the intended diff. The write path is limited to one
resolved file inside the project root. Existing Plausible-like or `data-domain`
scripts stop the operation for review instead of being replaced or duplicated.

### Remote-mutation boundary

- Property creation is idempotent and verifies an existing property first.
- Stats key creation happens only when no stored key exists or `--refresh` is
  explicitly supplied.
- Goal creation is idempotent according to Plausible's API response.
- Goal deletion requires an exact ID and `--yes`.
- API keys are never deleted automatically.
- `doctor`, reports, comparisons, breakdowns, and exports are read-only. Health
  checks never create a missing Stats key or plugin token.

### Known trust assumptions

You control the Mac account, Plausible instance, dashboard account, and
website source tree. A compromised local account can invoke Keychain access
under macOS policy. A compromised Plausible origin can return malicious or
unexpected content; response validation limits but cannot remove that trust.

Dashboard HTML is an integration surface and may change between Community
Edition releases. Unexpected forms or redirects fail closed and require a tool
update rather than bypassing CSRF or authentication checks.

## Technical decisions

### Ship a CLI and a skill together

The CLI makes network and file behavior deterministic and testable. The skill
adds natural-language triggering, inspection, and project-aware judgment
without duplicating the implementation in prompts.

### Configure the Plausible origin separately from website domains

One self-hosted instance commonly tracks several websites. A saved instance
origin plus per-project domain inference makes the common case short while
keeping every value overridable.

### Use dashboard forms for property creation

Community Edition exposes the needed dashboard workflow, while this tool
intentionally avoids the Sites API. Form parsing is more sensitive to upstream
UI changes, so every submission verifies the resulting state and fails closed
on unexpected responses.

### Use official APIs for operations after setup

Reports use Stats API v2. Goals use the site-scoped Plugins API. These are more
stable and structured than scraping analytics tables or goal settings screens.

### Store secrets in macOS Keychain

Login passwords, Stats keys, and plugin tokens have different scopes and
lifecycles. Separate service names prevent one broad plaintext configuration
file and make individual rotation possible.

### Keep generated secrets out of arguments

Plausible generates the Stats key. The CLI sends it to the Expect helper over
standard input because command-line arguments can be visible to other local
processes and shell history.

### Require previews and explicit deletion

Tracker changes are visible before writes. Goal deletion needs an exact ID plus
`--yes`. The CLI favors a stopped workflow over silent mutation when project
layout, authentication, or remote responses are ambiguous.

## Analytics CLI

The installer also installs `plausible`. It reads an existing Plausible instance
using a Stats API key you supply. It needs Python 3, macOS Keychain and Expect,
just like `plausible-setup`. There are no extra packages to install.

Run this once in your terminal:

```bash
plausible login --url https://plausible.example.com
```

Create a Stats API key in your Plausible account settings and paste it at the
hidden prompt. Login saves the key in Keychain. The first analytics request checks access
to the selected website. You can then let agents run reports without your dashboard password.

```bash
plausible status
plausible report --site example.com --period 30d --compare previous
plausible breakdown --site example.com --by country --period 30d
plausible breakdown --site example.com --by page --filter source=Google --format csv
plausible timeseries --site example.com --period 30d --interval day
plausible realtime --site example.com
plausible capabilities --json
```

Login prints a readable confirmation and a report command to try next. Use
`plausible login --url https://plausible.example.com --json` for a structured result.
Analytics results are JSON by default. Reports and breakdowns also accept `--format text`,
`--format markdown`, and `--format csv`. Use `--site` to select a website accessible to the saved key. `status` checks
that credentials are saved locally; it does not verify API access.

For custom dates, multiple dimensions, complex filters, custom metrics, ordering,
or pagination, save a complete [Stats API v2 query](https://plausible.io/docs/stats-api)
to a JSON file:

```json
{
  "date_range": ["2026-09-01", "2026-09-30"],
  "metrics": ["visitors", "pageviews"],
  "dimensions": ["event:page"],
  "order_by": [["visitors", "desc"]],
  "pagination": {"limit": 100, "offset": 0}
}
```

```bash
plausible query --site example.com --file query.json
cat query.json | plausible query --site example.com --file -
```

Supply `site_id` in the query file or select a website with `--site`.
An explicit `--site` overrides the file's `site_id`. Results keep the API response,
including metadata and warnings. Use pagination to retrieve more rows.

The available metrics and reports depend on your Community Edition version and
the data it collects. This is aggregate analytics, not individual visitor logs.
Website discovery is outside the Stats API; supply the domains you want to query.

Configuration lives in `~/.config/plausible/config.json` and contains only the
instance URL. Older configuration with a default website remains supported. `PLAUSIBLE_CLI_CONFIG` overrides this path.
Keys use the same `plausible-stats:<host>` Keychain item as `plausible-setup`.
Login stores the supplied key for that instance; API access is verified when
you request analytics. `plausible logout`
removes CLI configuration while keeping the shared key. Revoke keys in Plausible
when you want to remove their API access.

Analytics requests require HTTPS and refuse redirects to protect the bearer key.
Errors go to stderr as JSON and return a nonzero exit code. Keys never appear in
arguments, output, configuration, or query files. Analytics commands never create
keys or change the remote instance. The entry point reuses the existing reporting,
formatting, and Keychain implementation in its sibling `plausible-setup` script.

## Changelog

### 1.1.2 (2026-10-23)

- Added readable login instructions, a saved-key confirmation and the next command.
- Kept structured login output available through `--json`.

### 1.1.1 (2026-10-23)

- Removed website selection from login. Analytics commands select the website.
- Made login and status distinguish saved credentials from verified API access.

### 1.1.0 (2026-10-23)

- Added `plausible` with API-key login, JSON reports, time series, realtime visitors,
  full Stats API queries, and an agent capabilities manifest.
- Kept API credentials in Keychain and refused analytics redirects.


### 1.0.0 (2026-08-06)

- Added a configurable self-hosted Plausible origin.
- Added automatic tracked-domain inference with explicit `--domain` overrides.
- Added dashboard login storage in macOS Keychain.
- Added idempotent property creation through Plausible's dashboard forms.
- Added safe tracker insertion with dry-run diffs and duplicate detection.
- Added Stats API key creation, rotation, secure storage, and reports.
- Added read-only health diagnostics for the instance, tracker, property, and APIs.
- Added previous-period comparisons with percentage changes.
- Added country, source, page, goal, device, browser, campaign, and custom-property breakdowns.
- Added repeatable breakdown filters and text, JSON, CSV, and Markdown output.
- Added custom-event and pageview goal management through the Plugins API.
- Added a Codex skill, one-command installer, tests, and complete project docs.

## License

MIT. See `LICENSE`. Keep the license notice with substantial copies.
