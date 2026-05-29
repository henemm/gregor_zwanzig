# Architektur – Gregor Zwanzig

**Updated:** 2026-05-09 (Frontend hinzugefügt)

## Überblick
Gregor Zwanzig ist ein verteiltes System mit separaten Backend (Go) und Frontend (SvelteKit):

- **Backend:** Go REST API mit Wetter-Pipeline
- **Frontend:** SvelteKit Web-UI für Trip-Management und Konfiguration
- **Channels:** E-Mail (SMTP), SMS (future), Signal (via Callmebot)

---

## Backend Architecture (Go)

Kern-Geschäftslogik läuft im Go-API-Service (`gregor-api`), strukturiert in drei Ebenen:

1. **CLI & Config**
   - Einstiegspunkt: `src/app/cli.py`
   - Optionen: `--report`, `--channel`, `--dry-run`, `--config`, `--debug`
   - Priorität: CLI > ENV > config.ini
   - Ausgabe: Console (immer) und optional Versand (E-Mail)

2. **Business-Logik**
   - **Provider-Adapter**: holen Rohdaten von Wetter-APIs (z. B. MET Norway, DWD)
   - **Normalizer**: wandelt Daten in ein gemeinsames DTO ([api_contract.md](./api_contract.md))
   - **Risk Engine**: bewertet Forecasts anhand Schwellen (Regen, Gewitter, Wind, Hitze)
   - **Report Formatter**: erzeugt kurze Texte + Debug-Anhang
   - **DebugBuffer**: gemeinsame Quelle für Console + E-Mail-Debug

3. **Render-Pipeline**
   - **Channel Renderers** (`src/output/renderers/`) – β3: Pure-Function Renderer für E-Mail + SMS
   - `render_email()` – HTML + Plain-Text Körper (aus Token-Zeilen)
   - `render_sms()` – Kompaktes Format ≤160 Zeichen (v2.0 Wire-Format)
   - Schnittstelle: TokenLine (aus Report Formatter) → Channel-spezifischer Output

4. **Channels**
   - **SMTP-Mailer** (`src/app/core.py`) – einziger aktiver Kanal im MVP
   - Weitere Kanäle (SMS, Push, Garmin-Mail) später möglich

## Datenfluss (MVP)
CLI  
  ↓  
Config / ENV  
  ↓  
Provider-Adapter  
  ↓  
Normalisierung  
  ↓  
Risk Engine  
  ↓  
Formatter → TokenLine  
  ↓  
Channel Renderers  
  ├─→ render_email() → (HTML, Plain)  
  ├─→ render_sms() → Wire-Format ≤160 Zeichen  
  └─→ DebugBuffer  
  ↓  
Channel (E-Mail / Console / SMS)

## Debug-Prinzip
- Alle Schritte schreiben standardisierte Debug-Zeilen in den DebugBuffer
- Console = vollständige Ausgabe
- E-Mail = 1:1 identisches Subset
- Kern-Debug-Zeilen (immer enthalten): `cfg.path`, `report`, `channel`, `debug`, `dry_run`

---

## Frontend Architecture (SvelteKit)

**Stack:** SvelteKit 5 (Svelte 5 Runes), Tailwind CSS, Playwright E2E

**Location:** `frontend/` (SvelteKit project root)

### Directory Structure

```
frontend/
├── src/
│   ├── app.css                    # Global design tokens (@layer base) + atom styles (@layer components)
│   ├── app.html                   # HTML shell (Fonts: Inter Tight, JetBrains Mono)
│   ├── lib/
│   │   ├── components/
│   │   │   └── ui/               # Component library
│   │   │       ├── button/, card/, dialog/, badge/  # shadcn imports
│   │   │       ├── btn/, g-card/, pill/, eyebrow/, dot/, topo/, elev-sparkline/  # Gregor atoms (Epic #133)
│   │   │       └── sidebar/      # Main navigation (Issue #145)
│   │   ├── utils/                # Helpers (cn(), type utilities)
│   │   ├── types.ts              # Shared TypeScript types
│   │   └── stores/               # Svelte Stores (auth, theme, etc.)
│   └── routes/
│       ├── +layout.svelte        # Root layout (includes Sidebar)
│       ├── +page.svelte          # Home page
│       ├── trips/                # Trip management
│       ├── account/              # User account settings
│       └── _design/              # Component showcase (dev-only)
├── e2e/                          # Playwright E2E tests
│   ├── helpers.ts                # Auth helpers, shared utilities
│   ├── design-system-lauf-a.spec.ts
│   ├── design-system-lauf-b.spec.ts
│   └── *.spec.ts                 # Feature tests
└── package.json                  # Dependencies (SvelteKit, Tailwind, shadcn, bits-ui, etc.)
```

### Component Library (Epic #133)

#### Design-System Lauf A (Issues #141, #142, #145)

- **Design Tokens:** `--g-*` namespace in `app.css @layer base`
  - Primary colors: `--g-accent`, `--g-paper`, `--g-ink`
  - Surfaces: `--g-surface-0`, `--g-surface-1`, `--g-surface-2`
  - Semantic: `--g-success`, `--g-warning`, `--g-danger`, `--g-info`
  - Weather: `--g-wx-rain`, `--g-wx-sun`, `--g-wx-wind`, `--g-wx-snow`, `--g-wx-thunder`, `--g-wx-fog`
  - Typography: `--g-font-ui` (Inter Tight), `--g-font-data` (JetBrains Mono)
  - Layout: `--g-radius-*`, `--g-elev-*` (shadows)

- **Sidebar Component:** `$lib/components/ui/sidebar/Sidebar.svelte`
  - Main navigation container
  - Responsive design, icon-based nav items
  - Extracted from `+layout.svelte` (Issue #145)

#### Design-System Lauf B (Issues #143, #144, #146)

**Atom Components** — lightweight, token-based UI primitives:

| Component | Slot | Props | Purpose |
|-----------|------|-------|---------|
| `<Btn>` | `btn` | `variant`, `size` | Interactive button |
| `<GCard>` | `g-card` | - | Surface container with elevation |
| `<Pill>` | `pill` | `tone` | Compact label (semantic colors) |
| `<Eyebrow>` | `eyebrow` | - | All-caps metadata text |
| `<Dot>` | `dot` | `tone`, `size` | Circular indicator (weather/status) |
| `<TopoBg>` | `topo-bg` | `opacity` | Topographic background pattern |
| `<ElevSparkline>` | `elev-sparkline` | `data`, `width`, `height`, `active` | SVG elevation sparkline |

**Styling Approach:**
- `data-slot="<name>"` + `data-variant`/`data-tone`/`data-size` attributes
- Global CSS selectors in `app.css @layer components`
- Token references only (no arbitrary Tailwind values)
- Safer for Tailwind 4 scanning

**Reference:** `docs/reference/frontend_components.md`, `docs/reference/sveltekit_best_practices.md`

### Data Flow

```
User Action (Route/Form)
  ↓
SvelteKit Handler (+layout.server.ts, +page.server.ts)
  ↓
REST API Call (gregor-api)
  ↓
Go Backend (Business Logic)
  ↓
JSON Response
  ↓
SvelteKit Page Component (load() data → Svelte $state)
  ↓
Component Render (Atoms + Slots + Effects)
  ↓
HTML + Client-Side Interactivity
```

### Authentication & Authorization

- **Server-side:** `hooks.server.ts` verifies session via cookies
- **Protected Routes:** All routes except `/login` and `/register` require valid session
- **Client-side:** Svelte Stores track auth state; components react to changes
- **Development:** `/_design` showcase is auth-protected (development convenience)
- **Login Methods:**
  - **Username/Password:** Traditional auth via session cookies
  - **Google OAuth:** OAuth 2.0 Authorization Code flow (Issue #425, feature-gated via `GZ_GOOGLE_CLIENT_ID`)
    - Init: GET `/api/auth/google/init` → redirect to Google consent
    - Callback: GET `/api/auth/google/callback?code=...&state=...` → create/lookup user, issue session
    - User-ID format for OAuth users: `g-{8hex}` to prevent session parsing errors

### Testing Strategy

**E2E Tests (Playwright):**
- All UI features must have E2E tests
- Use `[data-testid="..."]` for stable selectors
- Validate component structure via `[data-slot="..."]`
- Test token application (computed styles, not hardcoded colors)

**Example:** `frontend/e2e/design-system-lauf-b.spec.ts` (10 tests)

### Build & Deployment

- **Build:** `npm run build` → static SvelteKit app (Node adapter)
- **Development:** `npm run dev` → local server (port 5173)
- **Production:** Systemd service `gregor-frontend.service` (port 5173)
- **Nginx Reverse-Proxy:** Routes `/` to SvelteKit frontend

---

## Integration Points

### Backend ↔ Frontend

**REST API Contracts:**
- `/api/trips` — Trip CRUD
- `/api/trips/{id}/stages` — Stage management
- `/api/subscriptions` — Email/SMS subscription settings
- `/api/account` — User account
- `/api/scheduler/status` — Job status monitoring

**Format:** JSON, standard HTTP methods (GET, POST, PUT, DELETE)

**Auth:** Session cookies (set by `hooks.server.ts`)

### Frontend → Channels

Frontend **does not** directly call E-Mail/SMS channels. Instead:
- User configures subscriptions in `/account`
- Backend scheduler handles actual sends (cron-based)
- Frontend displays subscription status + last-send timestamps

---

## Monitoring & Observability

- **Frontend Errors:** Client-side error logging (future: Sentry)
- **Backend Metrics:** BetterStack heartbeats for jobs (morning/evening reports, trip alerts)
- **Health Checks:** `/api/health` (backend), `/` (frontend)

See `~/.claude/CLAUDE.md` → Monitoring for details.