# Open Inbox

A universal inbox where trusted sources push content (text, images, files) and skills assess, route, and surface it.

## How It Works

```
Sources (trusted) → Memos (#inbox) → Skills pipeline → Output
```

Content flows into Memos from any source. Skills evaluate each item. Items either get stored to reference or surfaced to the user.

## Inbox Layer: Memos

[Memos](https://usememos.com) runs locally at `localhost:5230` (Docker, SQLite). It provides:

- REST API for programmatic read/write
- Web UI for manual capture
- File/image attachments as resources
- Tag-based organization and filtering

**Tag lifecycle:**

| Tag | Meaning | Set by |
|-----|---------|--------|
| `#inbox` | New, unprocessed | Source on capture |
| `#processing` | Skills are evaluating | Pipeline |
| `#done` | Routed and completed | Pipeline |

**Infrastructure:** `infra/services/memos/docker-compose.yml`

## Input Sources

All sources are trusted (safety/trust assessment is a future phase).

- **Mobile/web** - Memos UI (PWA on phone, browser)
- **Automated feeds** - RSS, email forwards, API integrations
- **Voice** - Transcribed voice memos
- **Manual notes** - Quick text capture
- **File drops** - Documents, images, screenshots

## Processing Modes

Content arrives in two fundamentally different contexts, and the skills pipeline should treat them differently.

### Backfill Mode
Processing old content -- files from folders, historical notes, accumulated captures. This content has aged and needs a relevance filter before anything else.

Key questions in backfill mode:
- **Is this still relevant?** A task from 6 months ago is probably stale. A git command is evergreen.
- **Has this been superseded?** An idea that was already built, a contact that changed, a plan that happened.
- **Is this worth the effort?** Old content has a higher bar for storage since the context around it has faded.

Backfill mode leans toward discarding. The default assumption is that old content is stale unless it's clearly evergreen (facts, commands, contacts, reference material). Confidence in routing should be lower across the board -- old context is unreliable, so surface more items to the user rather than auto-routing.

### Live Mode
Content just landed -- a note taken right now, a voice memo from today, a fresh capture. This content is alive in the user's mind.

Key questions in live mode:
- **What does the user need to do with this?** Fresh content is more likely to be actionable.
- **Should the user see this again soon?** Recent items deserve attention even when routing seems obvious, because they might trigger related thoughts.
- **How urgent is this?** Urgency only matters for live content -- backfill items are never urgent by definition.

Live mode leans toward surfacing. The default assumption is that fresh content matters and the user should see it, even if routing is high-confidence. Auto-storing quietly is fine for clearly evergreen reference (a command, a fact), but anything with a whiff of action or decision should be surfaced.

### How Mode Is Determined
The pipeline detects mode based on content metadata:
- **Backfill**: content has an original date significantly in the past, came from a batch import, or was explicitly marked as historical
- **Live**: content was just created in Memos, timestamp is recent

Skills adjust their behavior based on mode. Urgency skill skips entirely in backfill mode. Excitement skill weights differently (discovering an old gem vs. a fresh idea). Routing skill adjusts confidence thresholds.

## Skills Pipeline

Each inbox item gets assessed by multiple skills. Skills adjust their behavior based on processing mode (backfill vs. live).

### Routing
Decides where content belongs -- which `ref/` subfolder, GitHub issue, or discard.

Inherits learned routing rules from the existing inbox system:
- 210+ logged decisions in `decisions.jsonl` for pattern learning
- Reference rules (`.claude/skills/inbox-prepare/resources/reference-rules.md`)
- Todo rules (`.claude/skills/inbox-prepare/resources/todo-rules.md`)
- Content routed by what it's about, not where it came from
- File-per-topic structure in `ref/` optimized for LLM retrieval
- Nothing is too basic to save -- if it was written down, it matters

### Urgency
How time-sensitive is this item?

- **Immediate** - needs attention now (appointment conflicts, expiring deadlines)
- **Today** - should see it today (tasks, reminders)
- **This week** - important but not urgent (ideas, reference material)
- **Whenever** - evergreen, store and forget (commands, facts, contacts)

### Excitement
How excited would the user be to see this?

Useful for prioritizing what to surface vs. quietly store. A new product idea scores differently than a git command reference.

### Future Skills
Skills can be added as needs emerge. Each skill is a Claude Code skill file (markdown with instructions) that evaluates content and produces a structured assessment.

## Output Actions

Two actions for now:

### 1. Store to Reference
Route content to the appropriate `ref/` subfolder as markdown. The `ref/` folder is the permanent, git-versioned knowledge base organized by topic:

```
ref/
├── dev/          # Programming, tools, commands
├── family/       # Family member info
├── houses/       # Property info (PEI, Flagstaff, Boston)
├── business/     # Companies, taxes, investments
├── travel/       # Trip planning and research
├── health/       # Health topics
├── friends/      # Contacts
├── pets/         # Pet care
└── ...
```

### 2. Tell the User
Surface content that needs human attention. Items tagged for review stay visible in Memos filtered to a review tag. The user checks when ready.

Examples: urgent items, items needing a decision, exciting discoveries, ambiguous content the routing skill wasn't confident about.

## Inherited From Existing System

This project evolves from the current `tmp/` inbox pipeline:

| Component | Current | Open Inbox |
|-----------|---------|------------|
| Capture | Files dropped in `tmp/` | Memos API |
| Parsing | `/inbox-prepare` skill | Routing skill |
| Decisions | Ruby stepper (`inbox-stepper.rb`) | Skills pipeline |
| Execution | `/inbox-process` skill | Output actions |
| Learning | `decisions.jsonl` | Same format, same loop |
| Storage | `ref/` markdown files | Same |

The decision logging format and learning loop carry forward. Past decisions inform future routing confidence.

## Output Destinations

### 1. Reference (`ref/`)
Markdown knowledge base in the personal repo. Context, explanations, how-tos.

### 2. TODO (GitHub Issues)
Actionable items tracked as issues in the appropriate repo.

### 3. Calendar (Google Calendar)
Time-based events created via `aarond@wondermill.com` account.

### 4. NAS (`/Dropbox/nas/`)
Physical files: PDFs, images, documents, tax filings, attachments.

**NAS mirrors the ref/ structure exactly:**
```
ref/                          /Dropbox/nas/
├── business/                 ├── business/
│   └── taxes.md             │   └── taxes/2024/return.pdf
├── family/                   ├── family/
│   └── reuben/              │   └── reuben/
├── houses/                   ├── houses/
│   └── pei/                 │   └── pei/
└── ...                       └── ...
```

**Linking convention:**
```markdown
See: nas://business/taxes/2024/return.pdf
```

The path after `nas://` mirrors the ref structure. Reference explains context; NAS stores the actual files.

### 5. Discard
Not worth keeping. Logged but not stored.

## Development Principles

### Everything Logs Its Actions
All skills and scripts must log what they do. No silent operations.

- **Routing decisions** → `logs/routing.jsonl`
- **Calendar events created** → `logs/calendar.jsonl`
- **Files written to NAS** → `logs/nas.jsonl`
- **Errors and failures** → `logs/errors.jsonl`

Logs are append-only JSONL files with timestamps. This enables:
- Debugging when things go wrong
- Learning from patterns over time
- Auditing what the system did

### Daily Setup Skill
A `/daily-setup` skill runs each morning to:
- Sync ref/ and NAS folder structures (create missing folders in either)
- Report any orphaned files (NAS files with no corresponding ref/ area)
- Surface any stuck or failed items from previous day
- Summarize what's pending

This keeps the system healthy and prevents drift.
