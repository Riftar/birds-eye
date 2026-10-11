# Birds Eye: Product and Technical Spec

Owner: Riftar | Timezone: WIB (UTC+7) | Status: Draft v0.1 | Date: 2026-10-11

## 1. Summary

Birds Eye is a personal content workflow and dashboard that lets Riftar post carousels and short videos about the things he really builds. Underneath, it is a file-based pipeline in its own git repo: one folder per post holding a `post.json` with a strict state machine, two human gates, claims so agents never collide, and generated files (`STATUS.md`, weekly publish queues) that are never hand-edited. On top, it is a local web dashboard (board, calendar, approval inbox, post detail, cost) that reads and writes the same files. Humans use the dashboard and CLI; AI agents use the same CLI or an MCP server with the identical surface. All outside services (ElevenLabs, Nexabot, HyperFrames, video-use, Buffer, cogsend, R2, neatlogs) are plug-in adapters, so the core runs with none of them.

## 2. Goals and non-goals

### Goals

| # | Goal |
|---|------|
| G1 | One source of truth (files in git) shared equally by Riftar and agents. |
| G2 | Riftar sees at a glance: ideas, progress, schedule, and what is blocked on him. |
| G3 | Agents can do every step except the two human gates and human-shot footage. |
| G4 | Hard enforcement of stage transitions, gates, required assets, and spend caps. |
| G5 | Publisher is swappable (Buffer, cogsend, manual) with no change to posts. |
| G6 | Reuse the proven tiktok-viral pattern: job file per item, generated status, QA gates, weekly publish file, media in R2 not git. |
| G7 | Day-one usable after Phase 1 (components 1-4). |

### Non-goals

| # | Non-goal |
|---|----------|
| N1 | Not a multi-user SaaS. Single owner, no accounts or roles beyond `human` and agent ids. |
| N2 | Not a video editor or design tool. It orchestrates HyperFrames, video-use, and the carousel renderer. |
| N3 | Not a replacement for tiktok-viral or its faceless brands. Separate repo, separate queue. |
| N4 | No auto-posting that skips gate 2 (Review). |
| N5 | No external observability as a hard dependency (neatlogs is optional). |
| N6 | No database in Phase 1. Files plus git are the store. |

## 3. Users and their jobs

| User | Identity | Jobs |
|------|----------|------|
| Riftar (human) | `human` | Add ideas; approve or reject ideas (gate 1); shoot screen/desk footage; review finished posts (gate 2); approve spend over cap; paste metrics if not pulled. |
| Idea agent | e.g. `agent:ideas` | Mine repos, commits, logs for post ideas; add to backlog as `idea`. |
| Script agent | `agent:script` | Write script (short) or slides (carousel), hook, caption, hashtags. Move Approved to Scripted. |
| Asset agent | `agent:assets` | Gather screenshots, logs, diagrams, request human footage; attach artifacts. Move to Assets. |
| Voice agent | `agent:voice` | Generate voiceover via ElevenLabs (fallback Nexabot), log cost. Move to Voiced. |
| Edit agent | `agent:edit` | Render HyperFrames video, cut footage with video-use, or render carousel PNGs. Run QA. Move to Edited, then Review. |
| Publish agent | `agent:publish` | Build weekly publish file, push to publisher adapter, record post id and URL. Move Scheduled to Posted. |
| Metrics agent | `agent:metrics` | Pull or prompt for 48h and 7d numbers. Move Posted to Measured. |

Agent ids are free-form strings with the `agent:` prefix. One process may act as several agents.

## 4. Stages and gate rules

Order: Idea > Approved > Scripted > Assets > Voiced (shorts only) > Edited > Review > Scheduled > Posted > Measured. Plus terminal `rejected` and side state `on_hold`.

| Stage (`status`) | Entered by | Who may move it here | Exit requirements (checked by `move`) |
|---|---|---|---|
| `idea` | add | human or agent | title, pillar, format, source_repo |
| `approved` | **Gate 1** | **human only** | approved_by=human, approved_at set |
| `scripted` | script done | agent or human | short: `script.md` with hook + beats; carousel: `slides[]` 3-10 items; caption set |
| `assets` | assets attached | agent or human | every artifact marked `required` is present; human-shot items have `provided_by: human` |
| `voiced` | voice done (shorts only) | agent or human | voice file attached, duration known, cost entry logged |
| `edited` | render done | agent or human | `out/` render attached (MP4 or PNG set), QA checks pass |
| `review` | QA passed | agent or human | same as edited; enters approval inbox |
| `scheduled` | **Gate 2** | **human only** approves; then agent or human sets schedule_at and enqueues | approved review decision, schedule_at (WIB), publisher chosen |
| `posted` | publisher confirms | agent or human | publisher_post_id or post_url |
| `measured` | metrics in | agent or human | metrics.h48 and metrics.d7 filled |
| `rejected` | gate decision | human only | decision comment required |
| `on_hold` | pause | human only | reason note |

Transition rules:

| Rule | Detail |
|---|---|
| R1 | Only forward moves to the next stage, except: carousels skip `voiced`; any stage may go back to an earlier stage with a reason (logged); any stage may go to `on_hold`, and back to its prior stage. |
| R2 | `approved`, `rejected`, `on_hold`, and the gate 2 approval are human-only. Enforced by the CLI/API checking actor = `human`, which is only available via the dashboard session or a CLI run with `--as human` on Riftar's machine (local secret in `.birdseye/human.key`, gitignored). Agents never receive this key. |
| R3 | Rejection at gate 2 sends the post back to a stage named in the decision (default `edited`) with the comment attached. |
| R4 | Artifacts with `provided_by: human` (screen recordings, desk footage) cannot be attached by an agent. Agents can only create a `request` for them, which shows in "blocked on you". |
| R5 | A move requires the actor to hold the claim (or the post to be unclaimed and human). |
| R6 | Any edit after gate 2 approval to script, slides, caption, or renders reverts status to `review`. |

## 5. Data model

### post.json fields

| Field | Type | Notes |
|---|---|---|
| `id` | string | `YYYY-MM-DD-slug`, unique, equals folder name |
| `pillar` | enum | `build-in-public`, `failures-lessons`, `how-i-automate`, `tool-breakdowns` |
| `format` | enum | `carousel`, `short` |
| `platforms` | string[] | e.g. `tiktok`, `instagram`, `linkedin`, `x`, `youtube-shorts` (open question 12.2) |
| `title` | string | internal title |
| `hook` | string | first line / first 2 seconds |
| `source_repo` | string | e.g. `Riftar/dealscout` |
| `artifacts` | object[] | `{id, kind, path_or_url, required, provided_by, sha256, r2_key, added_by, added_at}`; kind: `screen`, `log`, `screenshot`, `footage`, `voice`, `render`, `slide`, `diagram`, `other` |
| `script` | object | short only: `{path: "script.md", beats[], est_seconds}` |
| `slides` | object[] | carousel only: `{n, heading, body, image_artifact?, notes}` |
| `caption` | string | |
| `hashtags` | string[] | |
| `voice` | object | `{provider, voice_id, model, fallback: {provider, voice_id}}` |
| `status` | enum | see section 4 |
| `owner` | string | `human` or agent id responsible for the current stage |
| `claim` | object or null | `{by, until, token}` until is ISO with offset |
| `approved_by` | string or null | gate 1 approver |
| `approved_at` | string or null | ISO, WIB offset |
| `review` | object or null | gate 2: `{decision, by, at, comment, return_to}` |
| `history` | object[] | append-only `{at, actor, action, from, to, note}` |
| `schedule_at` | string or null | ISO with `+07:00` |
| `publisher` | enum | `buffer`, `cogsend`, `manual` |
| `publisher_post_id` | string or null | |
| `post_url` | string or null | |
| `metrics` | object | `{h48: {...}, d7: {...}}`, each `{views, likes, comments, shares, saves, follows, source: pasted|pulled, at}` |
| `notes` | string | free text |
| `cost` | object[] | `{at, provider, kind, units, usd, agent, run_id, approved_override}` |
| `schema_version` | int | starts at 1 |

### Example

```json
{
  "schema_version": 1,
  "id": "2026-10-14-stock-agent-cost",
  "pillar": "failures-lessons",
  "format": "short",
  "platforms": ["tiktok", "instagram"],
  "title": "Stock-analysis agent monthly cost",
  "hook": "My stock-analysis agent costs $2.66 a month.",
  "source_repo": "Riftar/trading-signal-pipeline",
  "artifacts": [
    {"id": "a1", "kind": "screenshot", "path_or_url": "capture/billing.png", "required": true,
     "provided_by": "agent", "sha256": null, "r2_key": "posts/2026-10/2026-10-14-stock-agent-cost/capture/billing.png",
     "added_by": "agent:assets", "added_at": "2026-10-13T10:02:00+07:00"},
    {"id": "a2", "kind": "footage", "path_or_url": null, "required": true,
     "provided_by": "human", "request": "10s desk shot, laptop showing dashboard", "added_by": "agent:assets",
     "added_at": "2026-10-13T10:03:00+07:00"}
  ],
  "script": {"path": "script.md", "beats": ["hook", "what it does", "cost breakdown", "lesson"], "est_seconds": 35},
  "slides": [],
  "caption": "What it really costs to run my stock-analysis agent.",
  "hashtags": ["#buildinpublic", "#aiagents"],
  "voice": {"provider": "elevenlabs", "voice_id": "TBD", "model": "TBD",
            "fallback": {"provider": "nexabot", "voice_id": "Achernar"}},
  "status": "assets",
  "owner": "agent:assets",
  "claim": {"by": "agent:assets", "until": "2026-10-13T10:32:00+07:00", "token": "c-7f3a"},
  "approved_by": "human",
  "approved_at": "2026-10-12T21:15:00+07:00",
  "review": null,
  "history": [
    {"at": "2026-10-12T09:00:00+07:00", "actor": "agent:ideas", "action": "add", "from": null, "to": "idea"},
    {"at": "2026-10-12T21:15:00+07:00", "actor": "human", "action": "approve", "from": "idea", "to": "approved"},
    {"at": "2026-10-13T08:40:00+07:00", "actor": "agent:script", "action": "move", "from": "approved", "to": "scripted"}
  ],
  "schedule_at": null,
  "publisher": "manual",
  "publisher_post_id": null,
  "post_url": null,
  "metrics": {"h48": null, "d7": null},
  "notes": "",
  "cost": []
}
```

The cost figure in the hook is Riftar's own number from the seed list, not a Birds Eye metric. A JSON Schema file (`schema/post.schema.json`) is the contract; every write validates against it.

### Seed posts (Phase 1 fixtures)

| id (slug) | pillar | format | hook | source_repo |
|---|---|---|---|---|
| dealscout-listings | failures-lessons | carousel | 0 of 12 vs 3 of 12 listings confirmed | DealScout repo |
| tiktok-viral-sleep | how-i-automate | short | My AI posts 4 videos a day while I sleep | Riftar/tiktok-viral |
| stock-agent-cost | failures-lessons | short | My stock-analysis agent costs $2.66 a month | trading-signal-pipeline repo |

## 6. Components

### C1. Post store and state machine (Phase 1)

Requirements:
- One folder per post: `posts/<yyyy-mm>/<id>/post.json`.
- All writes go through one Python library (`birdseye.core`): load, validate, check transition, append history, atomic write (temp file + rename), optional git commit.
- Transition table from section 4 is code, not config, plus a unit-tested matrix.
- `status.py` equivalent (`birdseye status --write`) regenerates `STATUS.md`; a pre-commit hook and CI fail if `STATUS.md` is stale or hand-edited.
- Per-post file lock (`.lock` via `fcntl`/`O_EXCL`) around read-modify-write.

Acceptance:
- Invalid transition (e.g. `idea` to `scripted`) is refused with a clear error, nothing written.
- Agent attempting `approved` or gate 2 is refused even if it holds the claim.
- Carousel can go `assets` to `edited`; short cannot skip `voiced`.
- Every successful change adds exactly one history entry with actor and WIB timestamp.
- `STATUS.md` diff after any command matches regeneration; CI check passes.
- pytest coverage for every allowed and forbidden transition.

### C2. Board and calendar view (Phase 1)

Requirements:
- Local web app (`app/`) served by the FastAPI backend that reads post files on every request (or via file watcher), no separate DB.
- Kanban columns per stage, cards show title, format, pillar, owner, claim, age in stage, missing-asset badge.
- Week calendar (Mon-Sun, WIB) placing posts by `schedule_at`; unscheduled approved items in a side list.
- "Blocked on you" panel: items at gate 1, gate 2, human footage requests, spend-cap holds.

Acceptance:
- Editing a `post.json` on disk shows in the board within 5 seconds without restart.
- Calendar displays times in WIB regardless of browser timezone.
- "Blocked on you" count equals the count from `birdseye status --blocked-on human`.

### C3. Approval inbox (Phase 1)

Requirements:
- One screen listing every item awaiting Riftar: gate 1 ideas, gate 2 reviews, footage requests, spend overrides.
- Gate 2 card shows the rendered video or carousel PNGs, caption, hashtags, schedule proposal.
- Actions: Approve, Reject (requires comment, choose return stage), Comment (no state change).
- Writes `approved_by/approved_at` or `review{}` and a history entry, through C1.
- Keyboard shortcuts (a / r / c, j / k to move).

Acceptance:
- Approving from inbox produces the same file change as `birdseye approve <id> --as human`.
- Reject without comment is blocked.
- Inbox is empty when nothing is blocked on human; zero false entries against C2 count.

### C4. Agent API, CLI, MCP server (Phase 1)

See section 7 for the full surface. Requirements:
- `birdseye` CLI (Python, `uv tool install`), local HTTP API (FastAPI), and MCP server (`mcp/`) all call `birdseye.core`. No logic in the wrappers.
- Claims/leases (section 7.3).
- Every call writes an activity line to `logs/activity/<yyyy-mm-dd>.jsonl`.
- JSON output mode (`--json`) on every CLI command for agents.

Acceptance:
- Each CLI command has an MCP tool with the same name and params, verified by a test that diffs the two schemas.
- Two agents racing `claim` on the same post: exactly one wins, the other gets `ALREADY_CLAIMED` with holder and expiry.
- An expired claim can be taken by another agent; the old holder's next write is refused.

### C5. Asset tracker (Phase 2)

Requirements:
- Required-asset rules per format and stage, in `pipeline/asset_rules.yaml` (e.g. short at `edited` needs `voice` + `render`; carousel at `edited` needs one `slide` per slide).
- `birdseye attach` uploads to R2 (adapter), stores `r2_key` and `sha256`, keeps local copy in gitignored dir.
- `birdseye check <id>` lists missing assets for the next stage; `move` calls it.
- Human footage requests surface in "blocked on you".

Acceptance:
- `move` to next stage fails listing each missing required artifact.
- Re-attaching the same file (same sha256) is a no-op.
- With R2 adapter disabled, attach still works locally and marks `r2_key: null`.

### C6. Carousel renderer (Phase 2)

Requirements:
- `pipeline/slides_to_png`: `slides[]` + `brand/` template (HTML/CSS) rendered via headless Chromium (Playwright) to PNGs in `out/slides/`.
- Sizes per platform: 1080x1350 (4:5) default, 1080x1920 optional. Final list per open question 12.2.
- Text overflow detection: fail QA if any text box overflows.
- Optional image per slide from an artifact (screenshot, chart).

Acceptance:
- Same input produces byte-stable layout (fonts bundled in `brand/fonts`).
- Overflowing slide fails with slide number and field.
- Output attached as `slide` artifacts automatically.

### C7. Scheduler queue (Phase 2)

Requirements:
- Birds Eye owns the queue: `publish/<year>-w<N>.json` generated from posts at `scheduled` (ISO week, WIB).
- Publisher adapter interface: `enqueue(post) -> publisher_post_id`, `status(id)`, `cancel(id)`, `capabilities()` (e.g. max scheduled, channels).
- Adapters: `buffer`, `cogsend`, `manual`. Manual produces a checklist and copy-ready caption; human marks posted with URL.
- Per-adapter limits respected (Buffer: queue only up to its free slots; overflow stays in Birds Eye queue and drips in).

Acceptance:
- Switching `publisher` on a post from `buffer` to `manual` before enqueue needs no other change.
- Weekly file regenerates deterministically; not hand-edited (CI check like STATUS.md).
- When Buffer reports full, items stay `scheduled` with `publisher_post_id: null` and a warning, never dropped.

### C8. Cost and activity log (Phase 3)

Requirements:
- Every voice, render, and paid API run logs to `post.cost[]` and `logs/cost/<yyyy-mm>.jsonl`: provider, kind, units, usd, agent, run_id.
- Pre-run estimate where the provider supports it (ElevenLabs `estimate_only`).
- Spend caps in `AGENTS.md` front matter / `birdseye.toml`: per run, per post, per month (values set by Riftar, no defaults invented beyond a placeholder that blocks everything until set).
- If estimate exceeds a cap, the run is blocked and an override request goes to the approval inbox.
- Cost screen in dashboard.

Acceptance:
- A voice run without a prior estimate or log entry is refused by the voice adapter wrapper.
- Over-cap run cannot execute until human approves; approval recorded as `approved_override`.
- Monthly total on dashboard equals sum of the jsonl file.

### C9. Metrics notebook (Phase 3)

Requirements:
- At `posted` +48h and +7d, metrics agent prompts (inbox) or pulls (adapter, if publisher exposes metrics, e.g. Buffer analytics).
- Pasted values allowed via dashboard form or `birdseye metrics <id> --h48 views=...`.
- Notebook view: table by post with hook, format, pillar, platform, h48, d7; group-by hook style, format, pillar; simple sorts. No invented scoring; only raw numbers and ratios computed from them.

Acceptance:
- Post moves to `measured` only when both h48 and d7 exist.
- Notebook export to CSV matches post files.

## 7. Agent interface

### 7.1 CLI commands

All commands accept `--json` and `--as <actor>` (defaults to `BIRDSEYE_ACTOR` env). Human-only commands require the local human key.

| Command | Purpose | Key params |
|---|---|---|
| `birdseye add` | New idea | `--title --pillar --format --hook --source-repo --platforms` |
| `birdseye list` | Query posts | `--status --owner --format --pillar --blocked-on human --week` |
| `birdseye show <id>` | Full post | |
| `birdseye claim <id>` | Take lease | `--ttl 30m` |
| `birdseye renew <id>` | Extend lease | `--token --ttl` |
| `birdseye release <id>` | Drop lease | `--token` |
| `birdseye update <id>` | Edit fields (allowed per stage) | `--set key=value`, `--slides-file`, `--script-file`, `--token` |
| `birdseye attach <id>` | Add artifact | `--kind --file/--url --required --token` |
| `birdseye request <id>` | Ask human for footage | `--kind footage --desc` |
| `birdseye check <id>` | Missing requirements for next stage | |
| `birdseye move <id> <stage>` | Transition | `--token --note` |
| `birdseye approve <id>` | Gate 1 or 2 (human) | `--comment` |
| `birdseye reject <id>` | Gate decision (human) | `--comment --return-to` |
| `birdseye comment <id>` | Note, no state change | `--text` |
| `birdseye schedule <id>` | Set time and publisher | `--at "2026-10-20 19:00" --publisher` |
| `birdseye publish` | Build weekly file, push to adapters | `--week 2026-w43 --dry-run` |
| `birdseye cost <id>` | Log or estimate cost | `--provider --units --usd --estimate` |
| `birdseye metrics <id>` | Record numbers | `--h48 k=v ... / --d7 k=v ...` |
| `birdseye status` | Print or `--write` STATUS.md | `--blocked-on` |
| `birdseye doctor` | Validate all posts, stale claims, schema | |

### 7.2 MCP tools

MCP server name `birdseye`, stdio transport (local) and optional streamable HTTP. One tool per CLI command, same params, snake_case:

| Tool | Params | Returns |
|---|---|---|
| `add_post` | title, pillar, format, hook, source_repo, platforms[] | post |
| `list_posts` | status?, owner?, format?, pillar?, blocked_on?, week? | post summaries |
| `get_post` | id | post |
| `claim_post` | id, ttl_minutes (default 30, max 240) | claim {by, until, token} |
| `renew_claim` | id, token, ttl_minutes | claim |
| `release_claim` | id, token | ok |
| `update_post` | id, token, fields{} | post |
| `attach_artifact` | id, token, kind, path or url, required | artifact |
| `request_human_asset` | id, kind, description | request |
| `check_post` | id | missing[] |
| `move_post` | id, token, to, note? | post |
| `comment_post` | id, text | history entry |
| `schedule_post` | id, token, at (WIB), publisher | post |
| `build_publish_week` | week, dry_run | publish file |
| `log_cost` / `estimate_cost` | id, provider, kind, units, usd? | cost entry / estimate + cap verdict |
| `record_metrics` | id, window (h48/d7), values{} | post |
| `get_status` | blocked_on? | summary |

Not exposed over MCP: `approve`, `reject`, `on_hold`, spend override approval. Human-only actions exist only in the dashboard and CLI with the human key.

### 7.3 Claim and lease semantics

| Rule | Detail |
|---|---|
| Lease | `claim {by, until, token}` written into post.json under the file lock. Default TTL 30 min, max 240. |
| Exclusive | `claim` fails with `ALREADY_CLAIMED` if `until` is in the future and `by` is someone else. |
| Token | Every write by an agent must pass the current token; mismatch returns `CLAIM_LOST`. |
| Expiry | Expired claims are free; `doctor` and the board show stale claims. No background daemon needed. |
| Human | Human may write without a claim, and may force-release any claim (logged). |
| Release on move | A move clears the claim unless `--keep-claim` (same agent continues next stage). |
| Clock | Expiry compared in UTC internally, displayed in WIB. |

### 7.4 Concurrency

- Per-post lock file for read-modify-write; atomic rename on write.
- Agents on other machines: work through the HTTP API on Riftar's box (single writer), or through git with the rule "pull, claim, commit, push; on push conflict, re-pull and retry from claim". Phase 1 recommends the single-writer API.
- Generated files (`STATUS.md`, `publish/*.json`) are regenerated, never merged by hand; conflicts resolved by regenerating.

### 7.5 Audit

- `post.history[]` is append-only (core refuses edits to past entries).
- `logs/activity/*.jsonl`: every call, including refused ones, with actor, command, params hash, result, error code.
- Git history is the second audit trail; commits authored as `birdseye <actor>`.
- Optional OpenTelemetry spans per call (section 9, neatlogs).

### 7.6 Error codes

`INVALID_TRANSITION`, `HUMAN_ONLY`, `ALREADY_CLAIMED`, `CLAIM_LOST`, `MISSING_ASSETS`, `SCHEMA_INVALID`, `SPEND_CAP`, `ADAPTER_UNAVAILABLE`, `NOT_FOUND`.

## 8. Dashboard screens

Stack: FastAPI backend serving JSON + Astro (static, same style as riftar-dashboard) front end. Runs at `localhost:8787` by default.

| Screen | Shows | Actions |
|---|---|---|
| Board | Columns per stage, cards with owner, claim, age, missing-asset badge, format icon. Filters: pillar, format, platform, owner. | Open card; human drag only along allowed transitions (server validates). |
| Calendar | Week grid in WIB, scheduled posts by slot; unscheduled approved list; publisher capacity bar (e.g. Buffer slots used). | Set or change schedule_at, publisher. |
| Approval inbox | Gate 1 ideas, gate 2 reviews with media preview, footage requests, spend overrides. Count badge in nav. | Approve, reject + comment + return stage, comment, upload footage. |
| Post detail | All fields, script/slides, artifacts with previews and R2 links, history timeline, cost entries, metrics. | Edit allowed fields, attach, comment, force-release claim. |
| Cost | Month spend by provider, by agent, by post; caps and remaining; pending overrides. | Approve override (Phase 3). |
| Metrics notebook | Table of measured posts, group by format/pillar/hook. | Paste metrics, export CSV (Phase 3). |

## 9. Adapters

All adapters implement a small interface, are configured in `birdseye.toml`, and can be disabled. Core and dashboard run with zero adapters enabled.

| Adapter | Type | Used by | How | Notes |
|---|---|---|---|---|
| ElevenLabs | Voice (primary) | voice agent | ElevenLabs connector: `creative_generate_speech` with `estimate_only` first, then real run; voice design for brand voice; `creative_transcribe_audio` for captions/timing | Estimate feeds C8 caps. voice_id and model to pick (open). |
| Nexabot | Voice (fallback) | voice agent | Browser-driven on nexabot.id, voice Achernar; downloads file into `voice/` | Used when ElevenLabs fails or is over cap. Browser flow is fragile; adapter must report failure clearly, never retry silently. |
| HyperFrames | Video render | edit agent | heygen-com/hyperframes, HTML to MP4 from `hf/` composition + `brand/` intro/outro; animation via cth9191/animate and LottieFiles/motion-design-skill | Output to `out/`, attached as `render`. |
| video-use | Footage edit | edit agent | browser-use/video-use cuts screen/desk footage from `capture/` | Human-shot source only from Riftar. |
| Carousel renderer | Internal | edit agent | C6, Playwright + Chromium | Not an outside service. |
| Buffer | Publisher | publish agent | Buffer connector (create_post, list_posts, get_channel) | Org is full (3 channels, 10 scheduled, used by faceless brands). Needs a separate org/plan or channel swap. Adapter respects `capabilities()`. |
| cogsend | Publisher | publish agent | Self-hosted cogsend/cogsend, HTTP API | Hosting and platform support to verify before Phase 2. |
| Manual | Publisher | human | Checklist + copy-ready caption + media download; human enters post_url | Always available; default until a publisher is chosen. |
| Cloudflare R2 | Media storage | attach, render | S3-compatible API, bucket `birdseye-media`, key `posts/<yyyy-mm>/<id>/<dir>/<file>` | Same pattern as tiktok-viral. Media never in git. |
| neatlogs (optional) | Agent observability | watching agents | See below | Not required. |

### Optional: neatlogs integration

neatlogs (https://neatlogs.com) is an agent observability product: it imports agent traces (OpenTelemetry, Python/TS SDKs, Langfuse/LangSmith and others), detects failed or poor-judgement runs, groups them into incidents, supports root-cause investigation, and has a CLI, MCP, and Slack/GitHub/Linear integrations. Free tier: 1M spans/month, then $8 per 100k spans, 90-day retention (per their site; verify before enabling).

| Aspect | Decision |
|---|---|
| Role | Optional plug-in to watch the agents working inside Birds Eye. |
| Feed | Birds Eye agent API emits OpenTelemetry spans per call (command, post id, stage, actor, result, error code, adapter run ids). OTLP exporter endpoint set in config; off by default. |
| Example catches | Script agent ignored the brief (hook missing from script); voice run failed or used wrong voice; wrong asset attached to a post; repeated `CLAIM_LOST` from one agent. |
| Not replaced | Board, approval inbox, and the in-house cost/activity log (C8) stay the source of truth. neatlogs only reads a copy of spans. |
| Dependency | None. Disabling the exporter changes nothing else. |
| Volume | Spans per post are low (tens); expected to fit free tier, to confirm with real counts after Phase 1. |

## 10. Repo layout

New repo `Riftar/birds-eye` (name to confirm), separate from tiktok-viral.

```
birds-eye/
  AGENTS.md                 # rules for agents: gates, claims, cost caps, style
  STATUS.md                 # generated by `birdseye status --write`, never hand-edited
  birdseye.toml             # adapters, caps, publisher defaults, R2 bucket
  ideas/backlog.md          # loose idea list; promoted to posts via `birdseye add`
  posts/<yyyy-mm>/<id>/
    post.json
    script.md
    slides/                 # slide source (md/json), small, committed
    capture/                # gitignored, R2
    voice/                  # gitignored, R2
    hf/                     # HyperFrames composition (HTML committed, renders not)
    out/                    # gitignored, R2
  publish/<year>-w<N>.json  # generated weekly queue
  pipeline/
    status.py               # STATUS.md generator (thin wrapper over core)
    publish.py              # weekly file + adapter push
    slides_to_png/          # C6 renderer
    asset_rules.yaml
  brand/                    # fonts, colors, carousel templates, HyperFrames intro/outro
  schema/post.schema.json
  birdseye/                 # Python package: core, cli, api, adapters/
  app/                      # Astro dashboard
  mcp/                      # MCP server (Python, imports birdseye.core)
  logs/                     # activity + cost jsonl (committed or gitignored, open question)
  tests/                    # pytest: transitions, claims, schema, CLI/MCP parity
  .birdseye/                # local only, gitignored: human.key, locks
```

Tooling: Python with uv, FastAPI, pytest; Astro for `app/`; pre-commit + GitHub Actions running tests, schema validation, STATUS.md and publish freshness checks.

## 11. Phased roadmap

Sizes are rough (S = 1-2 days, M = 3-5 days, L = 1-2 weeks of solo work).

| Phase | Scope | Size | Done when |
|---|---|---|---|
| 0 | Repo, schema, AGENTS.md, seed the 3 example posts | S | Schema validates seeds, CI green |
| 1a | C1 core + state machine + STATUS.md + tests | M | All transition tests pass |
| 1b | C4 CLI + HTTP API + MCP, claims, activity log | M | CLI/MCP parity test, claim race test |
| 1c | C2 board + calendar, C3 approval inbox | M | Riftar approves a seed idea in the inbox and an agent moves it to scripted via MCP |
| 2a | C5 asset tracker + R2 adapter | M | Missing-asset block works; media lands in R2 |
| 2b | C6 carousel renderer + brand template | M | DealScout carousel renders to PNGs, passes overflow QA |
| 2c | C7 scheduler queue + manual + Buffer adapters (cogsend after decision) | M | One real post goes out through manual or Buffer from the weekly file |
| 2d | Voice + HyperFrames + video-use adapters wired to agents | M | One short goes idea to review with agents only, except gates and footage |
| 3a | C8 cost log, estimates, caps, override flow, cost screen | M | Over-cap voice run blocked until approved |
| 3b | C9 metrics notebook, 48h/7d prompts, optional pulls | S-M | Seed posts reach `measured` |
| 3c | Optional neatlogs OTel exporter | S | Spans visible in neatlogs with exporter on; nothing breaks with it off |

## 12. Open questions

| # | Question | Options | Notes |
|---|---|---|---|
| 12.1 | Publisher choice given Buffer limit | (a) second Buffer org/paid plan for personal accounts, (b) self-host cogsend, (c) manual first | Recommend manual for Phase 1-2 start, decide (a) vs (b) before 2c. Check cogsend platform coverage and hosting effort. |
| 12.2 | Which platforms | TikTok, Instagram, LinkedIn, X, YouTube Shorts | Drives carousel sizes, caption limits, and adapter scope. |
| 12.3 | Language | English, Bahasa Indonesia, or both per post | If both: one post with two variants, or two posts? Affects voice selection and caption fields. |
| 12.4 | Dashboard hosting | Local only (localhost) vs Cloudflare (Workers/Pages + Access) | Local is simplest and matches file store; Cloudflare needs a sync layer (git push or R2) and auth (Cloudflare Access) for phone approvals. |
| 12.5 | Spend cap values | per run / per post / per month | Riftar to set; system blocks paid runs until set. |
| 12.6 | ElevenLabs voice | stock voice vs designed voice vs clone; model | Pick before 2d. |
| 12.7 | Logs in git? | commit jsonl logs vs gitignore + R2 | Commit is simpler audit; may get noisy. |
| 12.8 | Remote agents | single-writer HTTP API vs git-based writes | Phase 1 assumes single-writer API on Riftar's box. |
| 12.9 | Repo name | `birds-eye` or `birdseye` | Cosmetic, decide at Phase 0. |
