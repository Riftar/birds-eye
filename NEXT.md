# NEXT: plan for agents to turn the prototype into the real Birds Eye

Read `docs/spec.md` first. The prototype code (`birdseye/core.py`) is the reference for behaviour, not for structure. Sizes: S = 1-2 days, M = 3-5 days, L = 1-2 weeks.
**Parallel** means the task can start alongside the others in its group once its "after" items are done.

## P0: Phase 1 core (do this first; nothing else is trustworthy until it's done)

| # | Task | Goal | Files | Acceptance check | Size | After / parallel |
|---|---|---|---|---|---|---|
| P0-1 | Project skeleton | Turn this into a proper package: `pyproject.toml`, uv, pytest, ruff, `birdseye.toml` config, and move the dashboard HTML out of the package path | `pyproject.toml`, `birdseye/`, `tests/` | `uv run pytest` passes the ported unittest suite; `uv tool install .` gives a `birdseye` command | S | first |
| P0-2 | Schema validation | Make `schema/post.schema.json` the contract, validated on every write and in `doctor` | `schema/post.schema.json`, `birdseye/core.py`, `birdseye/schema.py` | A bad field returns `SCHEMA_INVALID` and writes nothing; all 3 seed posts validate; `birdseye doctor` reports stale claims | M | after P0-1, parallel with P0-3 |
| P0-3 | Locking and store library | Harden `core`: `fcntl` lock with timeout and stale-lock recovery, append-only history guard, optional git commit authored as `birdseye <actor>`, full transition matrix from spec section 4 (on_hold, R6 revert, return-to on reject) | `birdseye/core.py`, `birdseye/store.py`, `tests/test_transitions.py` | Every allowed and forbidden (from, to, actor, format) pair is covered by a test; a 20-process claim race gives exactly 1 winner; editing a past history entry is refused | M | after P0-1, parallel with P0-2 |
| P0-4 | CLI parity | Implement every command in spec section 7.1 (`renew`, `release`, `check`, `comment`, `schedule`, `cost`, `metrics`, `doctor`, `request`), with `--json` everywhere and stable error codes | `birdseye/cli.py` | Each command has a test; `--json` output parses; exit code 2 plus the error code on refusal | M | after P0-3 |
| P0-5 | MCP server | Build a real stdio MCP server, `birdseye`, with one tool per CLI command (spec section 7.2) and no human-only tools | `mcp/server.py` (replaces `mcp/tools.py`) | A test diffs MCP tool schemas against the CLI params and they match; an agent can claim and move a seed post through MCP; `approve` isn't listed | M | after P0-4, parallel with P0-6 |
| P0-6 | Human-key gate | Replace the file-exists check with a real secret: on Riftar's machine, `.birdseye/human.key` signs human actions (HMAC of a nonce), and the dashboard session holds it server-side. Agents never get it | `birdseye/auth.py`, `birdseye/server.py` | `--as human` without the key gives `HUMAN_ONLY`; an MCP or agent process can't approve even with `BIRDSEYE_ACTOR=human` | S | after P0-3, parallel with P0-4/5 |
| P0-7 | CI and regen check | GitHub Actions plus pre-commit: tests, schema-validate all posts, fail if `STATUS.md` or `publish/*.json` differ from regeneration | `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `pipeline/status.py` | Hand-editing `STATUS.md` fails CI; a clean regen passes | S | after P0-2, parallel with P0-4 |

## P1: Phase 1c and Phase 2 (makes it usable day to day)

| # | Task | Goal | Files | Acceptance check | Size | After / parallel |
|---|---|---|---|---|---|---|
| P1-1 | Dashboard proper | FastAPI API plus Astro front end: board with filters, Mon-Sun week calendar in WIB, approval inbox with media preview, post detail with edit/attach/comment, and keyboard shortcuts | `birdseye/api.py`, `app/` | Disk edits appear within 5s; calendar shows WIB in any browser timezone; inbox count equals `birdseye list --blocked-on human`; inbox approve makes the same diff as the CLI | L | after P0-4 + P0-6; parallel with P1-2/3/4 |
| P1-2 | Asset tracker plus R2 | Per-format, per-stage rules in `pipeline/asset_rules.yaml`; `attach` stores sha256 and uploads to R2 (adapter can be disabled); `check` lists what's missing | `pipeline/asset_rules.yaml`, `birdseye/assets.py`, `birdseye/adapters/r2.py` | `move` lists each missing artifact; re-attaching the same sha256 is a no-op; with R2 off, attach still works with `r2_key: null` | M | after P0-3, parallel |
| P1-3 | Carousel renderer | Render `slides[]` through a `brand/` HTML template with Playwright Chromium, producing 1080x1350 PNGs in `out/slides/`, plus overflow QA | `pipeline/slides_to_png/`, `brand/` | The DealScout seed renders 5 PNGs with stable layout; an overflowing slide fails, naming the slide and field; PNGs attach automatically | M | after P0-3, parallel |
| P1-4 | Publisher adapters | Interface `enqueue/status/cancel/capabilities`; `manual` (checklist plus copy-ready caption) first, then `buffer` once the Buffer org question is settled, `cogsend` later | `birdseye/adapters/publish_*.py`, `pipeline/publish.py` | Switching `publisher` needs no other change; the weekly file regenerates deterministically; when Buffer is full, the post stays `scheduled` with a warning | M | after P0-4, parallel |
| P1-5 | Voice and render adapters | ElevenLabs (estimate first, then the real run), Nexabot fallback that reports failures loudly, HyperFrames render, video-use for footage | `birdseye/adapters/voice_*.py`, `render_hyperframes.py`, `edit_videouse.py` | One short goes from idea to review with agents only, except the gates and footage | M | after P1-2 |

## P2: Phase 3 (control and learning)

| # | Task | Goal | Files | Acceptance check | Size | After / parallel |
|---|---|---|---|---|---|---|
| P2-1 | Cost log plus spend caps | Write `logs/cost/<yyyy-mm>.jsonl`; caps per run, post, and month in `birdseye.toml` (placeholder blocks everything until Riftar sets values); over-cap runs go to the inbox for approval; cost screen | `birdseye/cost.py`, `app/cost` | A voice run with no estimate is refused; an over-cap run waits for human approval (recorded as `approved_override`); the monthly total matches the jsonl | M | after P1-5, parallel |
| P2-2 | Metrics notebook | `birdseye metrics`, 48h/7d prompts in the inbox, optional Buffer pull, a notebook table grouped by hook, format, and pillar, CSV export | `birdseye/metrics.py`, `app/metrics` | A post can't reach `measured` without h48 and d7; the CSV matches the post files | S-M | after P1-1, parallel |
| P2-3 | neatlogs (optional) | OTel span per API/CLI/MCP call (command, post, stage, actor, result, error); OTLP exporter off by default | `birdseye/telemetry.py` | Spans show in neatlogs with the exporter on; nothing changes with it off | S | after P0-5, parallel |

## Decisions Riftar needs to make (these block specific tasks)

- Publisher while Buffer is full (blocks P1-4 beyond manual).
- Platforms (sets carousel sizes in P1-3).
- English, Bahasa, or both (affects P1-5 voice choice and caption fields).
- Dashboard local vs Cloudflare (P1-1).
- Spend cap values (P2-1).
- ElevenLabs voice (P1-5).
