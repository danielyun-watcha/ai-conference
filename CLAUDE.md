# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is an AI Conference Deadlines web application that displays submission deadlines for top AI conferences like NeurIPS and ICLR. It's a React/TypeScript web app built with Vite, using shadcn-ui components and Tailwind CSS.

## Development Commands
```bash
# Frontend (Vite dev server on http://localhost:5002)
npm i
npm run dev

# Production build / lint / preview
npm run build
npm run build:dev
npm run lint
npm preview

# Backend (FastAPI on http://localhost:8005) — accepted-papers monitor
uv sync                                              # install Python deps
cp backend/.env.example backend/.env                 # set SLACK_WEBHOOK_URL
uv run uvicorn backend.main:app --port 8005 --reload
```

## Architecture

### Core Structure
- **Frontend**: React 18 + TypeScript + Vite
- **UI Framework**: shadcn-ui components with Radix UI primitives
- **Styling**: Tailwind CSS with custom animations
- **Data Source**: Individual YAML files per conference (`src/data/conferences/`) updated via GitHub Actions
- **State Management**: React hooks, no external state management library

### Key Directories
- `src/components/` - React components (UI components in `ui/` subdirectory)
- `src/pages/` - Route components (Index, Calendar, NotFound)
- `src/data/` - Conference data in YAML format
- `src/types/` - TypeScript type definitions
- `src/utils/` - Utility functions for date handling and conference processing
- `src/hooks/` - Custom React hooks

### Main Components
- `ConferenceList` - Primary list view of conferences
- `ConferenceCard` - Individual conference display card
- `ConferenceDialog` - Detailed conference information modal
- `FilterBar` - Conference filtering and search functionality
- `ConferenceCalendar` - Calendar view of conferences
- `Header` - Navigation and app header

### Data Model
Conferences are defined by the `Conference` interface in `src/types/conference.ts` with properties including:
- Basic info: `title`, `year`, `id`, `full_name`, `link`
- Dates: `deadline`, `abstract_deadline`, `date`, `start`, `end`
- Location: `city`, `country`, `venue`
- Metadata: `tags`, `hindex`, `note`

### Configuration Files
- `vite.config.ts` - Vite configuration with YAML plugin for loading conference data
- `tailwind.config.ts` - Tailwind CSS configuration with custom theme
- `components.json` - shadcn-ui component configuration
- `tsconfig.json` - TypeScript configuration

### Data Updates
Conference data is automatically updated via GitHub Actions workflow (`.github/workflows/update-conferences.yml`) that fetches from ccfddl repository and creates pull requests with updates to individual conference files.

### Accepted-papers monitor (backend/)
FastAPI service (`backend/`) that watches each conference's `accepted_papers_url`
and fires a Slack notification to the `#ML-Paper` channel the first time the
page goes live. The frontend reads the same release state via
`GET /api/accepted-papers/status` and shows a "Papers announced" badge on each
year cell.

- **YAML field**: add `accepted_papers_url: <listing page>` to the conference
  entry that should be monitored (see `wsdm.yml` 2026 entry as the reference).
  Conferences without this field are ignored by the monitor.
- **State**: SQLite at `backend/state.db` (gitignored). Slack fires exactly
  once per conference, on the `released = false → true` transition.
- **Endpoints**:
  - `GET  /health`
  - `GET  /api/accepted-papers/status` — used by the frontend
  - `POST /api/accepted-papers/check[?notify=true]` — crawl all monitored
    conferences. Use `?notify=false` on the very first run to seed the DB
    without flooding Slack with already-public conferences.
  - `POST /api/accepted-papers/check/{conference_id}[?notify=true]`
- **Release heuristic** (`backend/crawler.py`): HTTP 200 + body >= 500 chars +
  contains an "accepted papers" / "paper list" phrase + no "coming soon" /
  "TBA" / 404 markers. Conservative by design — false negatives just delay a
  notification by one poll cycle.
- **Scheduling**: n8n will call `POST /api/accepted-papers/check` on a cron
  (not yet wired up). Until then, call the endpoint manually.
- **Frontend integration**: `src/hooks/useAcceptedPapersStatus.tsx` provides a
  React context that fetches once on mount; `ConferenceYearCell` renders the
  badge when the matching `conference.id` is released. If the backend is
  unreachable the frontend silently renders without badges.

### Path Aliases
- `@/*` maps to `src/*` for cleaner imports

## Data Conventions
- **Timezone for deadlines**: Always use `AoE` (Anywhere on Earth, equivalent to UTC-12) for conference deadline timezones. Never use `UTC-12` — use `AoE` for consistency and clarity.
- Supported timezone formats in YAML: `AoE`, IANA names (e.g. `Asia/Seoul`), `UTC±X`, `GMT±X`

## Development Notes
- The app uses a YAML plugin to import conference data directly in components
- All UI components follow shadcn-ui patterns and conventions
- The project uses React Router for client-side routing
- Date handling uses `date-fns` and `date-fns-tz` for timezone support