# Architektur – Gregor Zwanzig

**Updated:** 2026-06-11 (Issue #749 — Day Comparison Renderer: render_day_comparison_html/plain für Vortag-Vergleich-Sektion); 2026-06-09 (Issue #675 — Etappen-Startzeiten Editor-Widget; Issue #671 — Bot-Menü automatisch beim Service-Start + Live-Selftest); 2026-06-08 (Issue #655 — Telegram callback_query + editMessageText Zoom-Navigation); 2026-06-07 (Issue #637 — Telegram Webhook Migration); 2026-06-03 (Issue #572 — Inbound-Handler Multi-User Routing); 2026-05-31 (Issue #483 — Demo-Modus im Vorschau-Tab; Issue #495 — MapCanvas Leaflet-Karte; Issue #475 — OutputLayoutEditor zu Organisms)

## Überblick
Gregor Zwanzig ist ein verteiltes System mit separaten Backend (Go) und Frontend (SvelteKit):

- **Backend:** Go REST API mit Wetter-Pipeline + Subscription-Management
- **Frontend:** SvelteKit Web-UI für Trip-Management, Konfiguration und Orts-Vergleiche
- **Channels:** E-Mail (SMTP), SMS (future), Signal (via Callmebot)
- **Subscriptions:** Trip-Reports (automatisch pro Etappe), Orts-Vergleiche (personalisierte Standort-Rankings)

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
   - **Day Comparison Renderers** (Issue #749) – neue Pure Functions für Vortag-Vergleich-Sektion:
     - `render_day_comparison_html(comparison)` – HTML mit farblicher Richtungscodierung (BETTER/WORSE/EQUAL)
     - `render_day_comparison_plain(comparison)` – Plain-Text Variante mit Pfeilen
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

## Inbound-Handler (Multi-User Routing)

**Komponenten:** `src/services/inbound_email_reader.py`, `src/services/inbound_telegram_reader.py`

**Zweck:** Eingehende Befehle (E-Mail-Replies, Telegram-Nachrichten) dem richtigen User zuordnen und verarbeiten.

**Workflow:**

1. **Email-Handler** (`InboundEmailReader.poll_and_process()`)
   - Liest IMAP-Inbox (shared mailbox)
   - Pro Nachricht: `lookup_user_by_email(from_addr)` → sucht User-Profil mit passender `mail_to`
   - Fallback: `user_id = "default"` wenn kein User gefunden
   - Ladet Trips des Nutzers via `load_all_trips(user_id)`
   - Verarbeitet Befehl (z. B. "status", "help")
   - Antwortet an die aufgelöste User-Adresse

2. **Telegram-Handler** (`InboundTelegramReader._process_update()`)
   - **Empfängt Telegram-Updates per Webhook** (Push-basiert seit Issue #637; Polling entfernt)
   - Go-Endpoint `/api/webhooks/telegram/{secret}` mit Secret-Header-Validierung → Python-Weiterleitung
   - Extrahiert Chat-ID
   - `lookup_user_by_telegram_chat_id(chat_id)` → findet User-Profil
   - Fallback: `user_id = "default"` wenn kein User gefunden
   - Ladet Trips des Nutzers und verarbeitet Befehl
   - Idempotenz via `update_id`-Watermark → keine Doppel-Zustellung
   - **Hybrid-Navigation via callback_query** (seit Issue #655):
     - Button-Klicks (Tier-1 Glance, Tier-2 Timeline, Tier-3 Drilldown, Zurück) kommen als `callback_query`
     - `_process_callback_query()` mappt `callback_data` → Processor-Body (z.B. `tl_today` → `### query: timeline_heute`)
     - `TelegramOutput.edit_message_text()` ersetzt Nachricht in-place (statt neue zu senden) → Zoom-Navigation
     - `TelegramOutput.answer_callback_query()` wird immer aufgerufen → Telegram-Lade-Spinner stoppt (auch bei unbekannten Buttons)

**Lookup-Funktionen** (`src/app/loader.py`):
- `list_all_user_ids(data_dir)` – alle User-IDs unter `data/users/` (ausschließt test_ / _ Präfixe)
- `lookup_user_by_email(email)` – sucht User mit `mail_to == email` (case-insensitive)
- `lookup_user_by_telegram_chat_id(chat_id)` – sucht User mit `telegram_chat_id == chat_id`

**Konfiguration:** Nutzer-Profile liegen in `data/users/<user_id>/user.json` mit Feldern `mail_to` und `telegram_chat_id`.

### Telegram Bot-Menü (Automatisches Setup)

**Neu seit Issue #671 (2026-06-09):** Das Telegram-Bot-Menü wird **automatisch beim FastAPI-Service-Start**
aus `BOT_COMMANDS` gesetzt und verifiziert:

- **Startup-Hook** (`api/main.py`, Lifespan): ruft `TelegramOutput.set_my_commands()` auf
- **Quelle:** `BOT_COMMANDS` in `src/outputs/telegram.py` (7 Befehle: glance, hg, dd, now, status, config, help)
- **Idempotent:** jeder Deploy/Restart stellt das Menü sicher
- **Fail-soft:** fehlender Bot-Token blockt den Service-Start nicht
- **Live-Verifikation (Post-Deploy):** Der Selftest prüft via `getMyCommands` gegen den Prod-Bot,
  ob das Live-Menü dem erwarteten Stand entspricht (Issue #671, AC-4)

Manuelle Verwaltung ist nur noch im Notfall nötig — siehe `docs/runbooks/telegram-webhook.md` → „Bot-Menü".

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
│   │   │   ├── ui/               # Atom Library (shadcn + Gregor atoms)
│   │   │   │   ├── button/, card/, dialog/, badge/  # shadcn imports
│   │   │   │   ├── btn/, g-card/, pill/, eyebrow/, dot/, topo/, elev-sparkline/  # Gregor atoms (Epic #133)
│   │   │   │   └── sidebar/      # Main navigation (Issue #145)
│   │   │   ├── atoms/             # Atom-Schicht (Atomic Design Level 1, Epic #371)
│   │   │   │   └── *.svelte       # Token-basierte UI-Primitive (Button, Label, Badge, etc.)
│   │   │   ├── molecules/         # Molecule-Schicht (Atomic Design Level 2, Epic #372)
│   │   │   │   └── *.svelte       # Combinations of atoms (FieldGroup, StatCard, etc.)
│   │   │   ├── organisms/         # Organism-Schicht (Atomic Design Level 3, Epic #471)
│   │   │   │   ├── index.ts       # Barrel re-export (TripHeader, TripWizardShell, AlertRulesEditor)
│   │   │   │   └── organisms.test.ts  # Source-inspection tests (no ui/ imports)
│   │   │   ├── trip-wizard/       # Trip creation/editing wizard
│   │   │   │   ├── TripWizardShell.svelte
│   │   │   │   ├── Stepper.svelte
│   │   │   │   ├── steps/*.svelte
│   │   │   │   └── templates/
│   │   │   ├── trip-detail/       # Trip display & editing
│   │   │   │   ├── TripHeader.svelte
│   │   │   │   ├── TripTabs.svelte
│   │   │   │   ├── waypoints/
│   │   │   │   │   ├── MapCanvas.svelte    # Leaflet-Karte mit OpenTopoMap-Tiles (Issue #495)
│   │   │   │   │   └── ...
│   │   │   │   └── index.ts       # Barrel (TripHeader re-exported in organisms/)
│   │   │   ├── alert-rules-editor/  # Alert configuration
│   │   │   │   ├── AlertRulesEditor.svelte
│   │   │   │   └── components/
│   │   │   ├── compare/           # Compare-Wizard (Epic #438)
│   │   │   │   ├── CompareWizard.svelte
│   │   │   │   ├── CompareMatrix.svelte
│   │   │   │   ├── compareWizardState.svelte.ts
│   │   │   │   ├── compareMetricDefs.ts
│   │   │   │   ├── steps/
│   │   │   │   └── __tests__/
│   │   │   ├── shared/            # Cross-feature components (OutputLayoutEditor, etc.)
│   │   │   ├── preview/           # Email/SMS preview renderers
│   │   │   ├── email-preview/     # Email rendering
│   │   │   ├── mobile/            # Mobile-only components
│   │   │   ├── edit/              # Form & edit views
│   │   │   ├── briefings-tab/     # Briefings configuration
│   │   │   ├── alerts-tab/        # Alerts configuration
│   │   │   └── utils/             # Helpers (cn(), type utilities)
│   │   ├── types.ts               # Shared TypeScript types
│   │   └── stores/                # Svelte Stores (auth, theme, etc.)
│   └── routes/
│       ├── +layout.svelte         # Root layout (includes Sidebar)
│       ├── +page.svelte           # Home (Trip Cockpit Dashboard, Epic #134)
│       ├── trips/                 # Trip management (CRUD wizard)
│       ├── compare/               # Compare wizard + subscription list
│       │   ├── +page.svelte       # Create new comparison
│       │   ├── [id]/
│       │   │   └── edit/
│       │   │       ├── +page.svelte
│       │   │       └── +page.server.ts
│       │   └── +page.server.ts
│       ├── account/               # User account settings
│       └── _design/               # Component showcase (dev-only)
├── e2e/                           # Playwright E2E tests
│   ├── helpers.ts                 # Auth helpers, shared utilities
│   ├── design-system-lauf-a.spec.ts
│   ├── design-system-lauf-b.spec.ts
│   └── *.spec.ts                  # Feature tests
└── package.json                   # Dependencies (SvelteKit, Tailwind, shadcn, bits-ui, etc.)
```

### Atomic Design Layers (Epic #368, #371, #372, #471)

Frontend components follow Atomic Design principles with 3 explicit layers:

| Layer | Location | Purpose | Examples | Epic |
|-------|----------|---------|----------|------|
| **Atoms** | `components/atoms/` | Base UI primitives | Button, Label, Badge, Icon | #371 |
| **Molecules** | `components/molecules/` | Combinations of atoms | FieldGroup, StatCard, Tabs | #372 |
| **Organisms** | `components/organisms/` | Complex page sections | TripHeader, TripWizardShell, AlertRulesEditor | #471 |

**Import Rules:**
- **Atoms** may import from `ui/` (shadcn + gregor primitives)
- **Molecules** may import from `atoms/` and `ui/`
- **Organisms** may import from `atoms/`, `molecules/`, and other `organisms/` — **never** directly from `ui/`
- **Routes** should prefer importing from `organisms/` and `molecules/`, using `atoms/` only for rare custom layouts

**Organism Barrel** (`components/organisms/index.ts`):
Re-exports 4 core organisms without moving their physical source files:
```typescript
export { default as TripHeader } from '../trip-detail/TripHeader.svelte';
export { default as TripWizardShell } from '../trip-wizard/TripWizardShell.svelte';
export { default as AlertRulesEditor } from '../alert-rules-editor/AlertRulesEditor.svelte';
export { default as OutputLayoutEditor } from '../shared/OutputLayoutEditor.svelte';
```

Consumers import via: `import { TripHeader, OutputLayoutEditor } from '$lib/components/organisms'`

See `docs/design-system/COMPONENTS.md` for the canonical component catalog.

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

**Auth Methods:**
- **Username/Password:** `/api/auth/register` + `/api/auth/login` (traditional, bcrypt-hashed)
- **Passkey/WebAuthn (Issues #450, #467):** 
  - V1 Identifier-First: `/api/auth/passkey/register/begin|finish` (Face ID, Touch ID, Windows Hello, YubiKey), `/api/auth/passkey/login/begin|finish`, `/api/auth/passkey/credentials/{id}` (delete)
  - V3 Discoverable (login without username): `/api/auth/passkey/discoverable/begin|finish` (Conditional UI with native autofill picker)
- **Google OAuth (Issue #425, feature-gated via `GZ_GOOGLE_CLIENT_ID`):** OAuth 2.0 Authorization Code flow
  - Init: GET `/api/auth/google/init` → redirect to Google consent
  - Callback: GET `/api/auth/google/callback?code=...&state=...` → create/lookup user, issue session
  - User-ID format for OAuth users: `g-{8hex}` to prevent session parsing errors
- **Magic Link (Issue #449):** `/api/auth/magic-link` + `/api/auth/magic-link/verify` (6-digit OTP per E-Mail)

**Session Format:** Server-side-signed cookie `gz_session = <userId>.<timestamp>.<hmacSig>` (24h TTL, HttpOnly, SameSite=Lax, Secure on HTTPS) — identisch über alle Auth-Methoden hinweg.

**User Model Extensions (Issues #425, #450):**
- `PasswordHash` field optional (`omitempty` JSON tag) — leerer Hash für reine OAuth/Passkey-User
- `PasskeyCredentials[]` array für FIDO2 credentials (Credential-ID, Public-Key, Attestation-Type, Transport, AAGUID, SignCount, Label, timestamps)
- `OAuthProvider` + `OAuthSub` für externe Identitäten
- Profile endpoint (`GET /api/auth/profile`) returns `has_passkey: bool` + `passkeys[]` array (public metadata only, no secret key material)

**Server-side Validation:**
- `hooks.server.ts` verifies session cookie signature
- Protected Routes: All routes except `/login`, `/register`, `/magic-link`, `/api/auth/google/*` require valid session
- Client-side: Svelte Stores track auth state; components react to changes
- Development: `/_design` showcase is auth-protected (development convenience)

### Testing Strategy

**E2E Tests (Playwright):**
- All UI features must have E2E tests
- Use `[data-testid="..."]` for stable selectors
- Validate component structure via `[data-slot="..."]`
- Test token application (computed styles, not hardcoded colors)

**Example:** `frontend/e2e/design-system-lauf-b.spec.ts` (10 tests)

### Frontend Dependencies

**Key libraries:**
- **SvelteKit 5:** React framework + SSR
- **Svelte 5:** Runes-based reactivity
- **Tailwind CSS:** Utility-first styling
- **Leaflet (~1.9.4):** Interactive maps for waypoint editing (Issue #495)
  - Tile layer: OpenTopoMap (topographic tiles with contour lines)
  - Waypoint markers and polyline routing
  - Zoom control and bounds fitting
- **@types/leaflet:** TypeScript types for Leaflet
- **shadcn/svelte:** Pre-built accessible components (buttons, dialogs, etc.)
- **bits-ui:** Headless component library
- **@lucide/svelte:** Icon library
- **svelte-dnd-action:** Drag-and-drop utilities

### Build & Deployment

- **Build:** `npm run build` → static SvelteKit app (Node adapter)
- **Development:** `npm run dev` → local server (port 5173)
- **Production:** Systemd service `gregor-frontend.service` (port 5173)
- **Nginx Reverse-Proxy:** Routes `/` to SvelteKit frontend

### Multi-Step Wizards

The frontend includes two configurable wizard systems:

#### Trip Wizard (Epic #136)
- **Purpose:** Create/edit trips with stages and waypoints
- **Steps:** 4 (Name/Profile, Stages, Waypoints, Review)
- **State Management:** `tripWizardState.svelte.ts`
- **Component:** `frontend/src/lib/components/trip-wizard/`
- **Persistence:** `/api/trips` POST/PUT

#### Compare Wizard (Epic #438)
- **Purpose:** Create/edit location comparison subscriptions
- **Steps:** 5 (Name/Profile, Locations, Ideal Values, Layout, Schedule)
- **State Management:** `compareWizardState.svelte.ts`
- **Component:** `frontend/src/lib/components/compare/`
- **Persistence:** `/api/subscriptions` POST/PUT
- **Current Status:**
  - ✓ Step 1: Name + Activity Profile (Issue #440, auto-preselect via #547)
  - ✓ Step 2: Location selection (Issue #440)
  - ✓ Step 3: Ideal value ranges per metric (Issue #441, uses `compareMetricDefs.ts`)
  - ✓ Step 4: Output formatting layout (Issue #442)
  - ✓ Step 5: Schedule + delivery config (Issue #443)

**Key Data Structures:**
- `ActivityProfile` — Enum type for activity categories (WINTERSPORT, ALPINE_TOURING, SUMMER_TREKKING, ALLGEMEIN)
- `MetricDef` — Descriptor for a weather metric (label, unit, range, input kind)
- `IdealRange` — Min/max thresholds for a metric (numeric or enum)
- `PROFILE_METRICS_WITH_SCALES` — Metric definitions indexed by profile
- `IDEAL_DEFAULTS` — Default ranges per profile (populated on first render)

---

## Integration Points

### Backend ↔ Frontend

**REST API Contracts:**

*Authentication:*
- `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` — Password-based auth
- `/api/auth/passkey/register/begin|finish` — WebAuthn passkey registration (Issue #450)
- `/api/auth/passkey/login/begin|finish` — WebAuthn passkey login (Identifier-First)
- `/api/auth/passkey/discoverable/begin|finish` — WebAuthn passkey login (Conditional UI, login without username) (Issue #467)
- `/api/auth/passkey/credentials/{id}` — Passkey management (delete)
- `/api/auth/google/init|callback` — Google OAuth (Issue #425, feature-gated)
- `/api/auth/magic-link`, `/api/auth/magic-link/verify` — Magic Link OTP (Issue #449)
- `/api/auth/profile` — User profile + passkey list

*Data:*
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/trips` | GET/POST | Trip CRUD |
| `/api/trips/{id}` | GET/PUT/DELETE | Individual trip |
| `/api/trips/{id}/stages` | GET/POST | Stage management |
| `/api/trips/{id}/briefing-history` | GET | Briefing delivery log for archived trip (Issue #559) |
| `/api/locations` | GET/POST | Location library (for compare) |
| `/api/subscriptions` | GET/POST | Create/list subscriptions (compare) |
| `/api/subscriptions/{id}` | GET/PUT/DELETE | Individual subscription |
| `/api/subscriptions/{id}/preview` | POST | Preview comparison output |
| `/api/preview/{id}/email\|sms\|signal\|telegram` | GET | Trip report preview rendering (demo mode optional) |
| `/api/account` | GET/PUT | User account |
| `/api/scheduler/status` | GET | Job status monitoring |

**Subscription Types:**
- `"trip"` — Auto-generated reports per stage
- `"compare"` — Location comparison (configurable via wizard)

**Compare Subscription Payload:**
```json
{
  "id": "compare-001",
  "name": "Ski 2026",
  "enabled": true,
  "config": {
    "activity_profile": "WINTERSPORT",
    "location_ids": ["hut-a", "hut-b", "hut-c"]
  },
  "display_config": {
    "ideal_ranges": {
      "temp_max_c": { "min": -5, "max": 5 },
      "snow_depth_cm": { "min": 30, "max": 200 },
      "wind_max_kmh": { "min": 0, "max": 40 }
    },
    "output_layout": { /* TBD #442 */ },
    "schedule": { /* TBD #443 */ }
  }
}
```

**Format:** JSON, standard HTTP methods (GET, POST, PUT, DELETE)

**Auth:** Session cookies (format: `<userId>.<timestamp>.<hmacSig>`, set by Login or Passkey endpoints, 24h TTL)

### Frontend → Channels

Frontend **does not** directly call E-Mail/SMS channels. Instead:
- User configures subscriptions in `/account`
- Backend scheduler handles actual sends (cron-based)
- Frontend displays subscription status + last-send timestamps

---

## Monitoring & Observability

- **Frontend Errors:** Client-side error logging (future: Sentry)
- **Backend Metrics:** BetterStack heartbeats for jobs (morning/evening reports, trip alerts, compare subscriptions)
- **Health Checks:** `/api/health` (backend), `/` (frontend)
- **Scheduler Status:** `/api/scheduler/status` shows last-run timestamps and errors per job

**Compare-Specific:**
- Frontend validates wizard steps before saving
- Backend accepts any `display_config` (opaque, no schema enforcement)
- No server-side validation of `ideal_ranges` values yet (future enhancement)

See `~/.claude/CLAUDE.md` → Monitoring for details.

---

## Feature Documentation

- **Epic #438 (Compare Wizard):** `docs/features/epic-438-compare-wizard.md`
- **Epic #134 (Trip Cockpit Dashboard):** `docs/features/epic-134-cockpit-dashboard.md`
- **Design System:** `docs/design-system/` (CHARTER, COMPONENTS, TOKENS, SCREENS)
- **API Contract:** `docs/reference/api_contract.md`

---

## Related Issues

- **#559:** Archive page completion — Briefing-Verlauf modal, Template copy, Event summary ✓
- **#440:** Compare Wizard shell + Steps 1–2 ✓
- **#441:** Compare Wizard Step 3 (Ideal Ranges) ✓
- **#442:** Compare Wizard Step 4 (Layout) — planned
- **#443:** Compare Wizard Step 5 (Schedule) — planned
- **#134:** Trip Cockpit Dashboard ✓
- **#136:** Trip Wizard completion ✓
- **#133:** Design System (Atoms + Tokens) ✓