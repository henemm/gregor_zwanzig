# Context: Issue #439 — Orts-Vergleich Übersichtsseite /compare

## Request Summary

Die bestehende `/compare`-Seite (interaktiver Vergleichsrechner mit Sidebar) wird durch eine **Tabellen-Übersicht** aller gespeicherten Orts-Vergleiche ersetzt — analog zu `/trips`. Teil von Epic #438 (Orts-Vergleich Rework).

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/+page.svelte` | Wird **ersetzt** — aktuell interaktiver Vergleich; wird neue Übersichtsseite |
| `frontend/src/routes/compare/+page.server.ts` | SSR-Loader — lädt bereits `locations`, `subscriptions`, `groups`. Muss auf `CompareSubscription`-Liste erweitert/angepasst werden |
| `frontend/src/lib/types.ts` | `Subscription` (TS-Typ) + `CompareSubscription` (Go-Modell) — braucht evtl. `status`-Feld |
| `frontend/src/routes/trips/+page.svelte` | **Pattern-Referenz**: Eyebrow, H1, Stats-Row, Search-Pill, Table, Actions, EmptyState, Delete-Dialog |
| `frontend/src/lib/components/atoms/index.ts` | `Btn`, `Pill`, `Dot`, `Eyebrow`, `Input` — Atom-Komponenten für Header und Tabelle |
| `frontend/src/lib/components/ui/table/index.js` | Tabellen-Primitives |
| `frontend/src/lib/components/ui/dialog/index.js` | Confirm-Dialog für Löschen |
| `frontend/src/lib/components/ui/empty-state/index.js` | Empty-State für 0 Vergleiche + 0 Suchergebnisse |
| `internal/model/subscription.go` | `CompareSubscription` Go-Struct — `enabled`, `name`, `locations`, `schedule`, `activity_profile`, `last_run`, `last_status`. **KEIN `status`-Feld** |
| `internal/handler/subscription.go` | CRUD-Handler: GET/POST `/api/subscriptions`, PUT `/api/subscriptions/{id}`, DELETE, PATCH run-status |
| `docs/design-system/TOKENS.md` | `--g-accent`, `--g-ink-3`, `--g-ink-4`, `--g-rule-soft`, `--g-r-2` |
| `frontend/src/lib/components/compare/AutoReportsOverview.svelte` | Bisherige Subscription-Übersicht (innerhalb der alten /compare-Seite) — wird abgelöst |

## Existing Patterns

- **Trips-Tabellen-Pattern** (`/trips/+page.svelte`): Eyebrow `WORKSPACE · TRIPS` → H1 → Stats-Row (Counts, `--g-accent`) → Search-Input (pill, SearchIcon) → Desktop-Table + Mobile-Cards. Exakt das gleiche Muster ist für Compare gefordert.
- **Status-Dot**: `Dot`-Atom mit `tone` prop (`success`/`info`/`warning`/`danger`) — muss für Compare auf `accent`/`ink-3`/`ink-4` gemappt werden (eigene Inline-Styles laut Issue, da keine direkte Dot-Tone-Entsprechung für `paused` und `draft`).
- **Aktions-Buttons**: 30×30, `border: 1px solid var(--g-rule-soft)`, `border-radius: var(--g-r-2)` — gleiche Spec wie in Trip-Aktionen.
- **Optimistic Update** für Pause/Play: Lokalen State direkt mutieren, dann API-Call (wie bei Trip-Status-Toggle).
- **Delete-Dialog**: `Dialog.Root` + `Dialog.Content` mit Confirm-Button, analog zu Trips.
- **EmptyState**: `EmptyState`-Komponente mit `icon`, `title`, `description` + Slot für CTA-Button.

## Dependencies

- **Upstream (Backend)**: `GET /api/subscriptions` liefert alle `CompareSubscription[]` für den User. `PUT /api/subscriptions/{id}` zum Pause/Play-Toggle (`enabled` setzen). `DELETE /api/subscriptions/{id}` zum Löschen.
- **Downstream**: Die neuen Routen `/compare/new` (#440) und `/compare/{id}/edit` (#440+#443) werden per `goto()` bzw. `href` von der Übersicht aus verlinkt.
- **Teilt**: `Btn`, `Pill`, `Dot`, `Eyebrow`, `Input`, `Table`, `Dialog`, `EmptyState` aus Atoms/UI.

## Existing Specs

- `docs/specs/modules/issue_252_compare_presets.md` — Subscription-Modell (CRUD)
- `docs/specs/modules/issue_251_compare_main_stage.md` — bisherige /compare Hauptbühne (wird abgelöst)

## Key Design Decisions / Risks

### 1. Status-Feld fehlt im Backend-Modell

`CompareSubscription` hat nur `enabled: bool` — kein `status: "active" | "paused" | "draft"`.

**Optionen:**
- **Option A (empfohlen für #439):** `draft` = `!name || locations.length === 0`, `active` = `enabled && !draft`, `paused` = `!enabled && !draft`. Rein Frontend-seitig, kein Backend-Change.
- **Option B:** Neues `status`-Feld im Go-Modell (eigenes Issue).

Für #439 reicht Option A — der Wizard (#440+) wird später für echte Draft-Persistenz zuständig sein.

### 2. Kanal-Pills

Die Issue-Spec zeigt Pills pro Kanal (`E-Mail · Signal · Telegram · SMS`). Die `Subscription`-TS-Typ-Felder sind `send_email`, `send_signal`, `send_telegram` (kein `send_sms` in `CompareSubscription`). **SMS** ist im Go-Modell nicht vorhanden — Pill nur für vorhandene Felder rendern.

### 3. Bestehende /compare-Seite

Issue #438 beschreibt `/compare` als neue Übersicht. Die aktuell bestehende interaktive Vergleichs-Seite wird **ersetzt**. Der interaktive Vergleich (Matrix, Ranking) wird ggf. in `/compare/{id}` oder als Preview-Modal leben — das ist Scope von #440+, nicht #439.

### 4. Schedule-Formatierung

`schedule` Feld: `'daily_morning' | 'daily_evening' | 'weekly'`. Anzeige laut Issue: `tgl. 06:30`, `Sa 06:00`. Ableitung: `time_window_start` als Uhrzeit, `weekday` für wöchentliche. Formatierungsfunktion nötig.

### 5. Preview-Action

"Preview" zeigt Briefing-Vorschau in Modal — Scope-Risiko. Kann für #439 als Stub (deaktivierter Button oder `goto`) umgesetzt werden, da die Preview-API aus dem alten Compare-Flow kommt.

### 6. Send-Now-Action

Sofortversand mit Bestätigungsdialog — API-Endpunkt prüfen: `POST /api/subscriptions/{id}/send` oder ähnlich. Noch nicht in den Handler-Routes gesehen → evtl. Stub für #439.

## Acceptance Criteria (aus Issue #439)

- AC-1: `/compare` zeigt Tabelle mit Spalten: Name · Orte · Profil · Kanäle · Versand · Aktionen
- AC-2: Header hat Eyebrow `WORKSPACE · ORTS-VERGLEICHE`, H1 „Orts-Vergleiche", Intro-Subtext, primary `+ Neuer Vergleich` rechts → `/compare/new`
- AC-3: Search-Pill filtert Vergleiche nach Name (case-insensitive)
- AC-4: Stats-Row zeigt Counts: Aktiv (accent) · Pausiert · Drafts
- AC-5: Status-Dot in Accent (aktiv) / Ink-3 (pausiert) / Ink-4 (draft)
- AC-6: Pause/Play-Action togglet Status sofort (optimistic update)
- AC-7: Edit-Action navigiert zu `/compare/{id}/edit`
- AC-8: Trash-Action öffnet Confirm-Dialog vor dem Löschen
- AC-9: Empty-State wenn keine Vergleiche vorhanden: CTA zu `/compare/new`
- AC-10: Empty-State bei Suche ohne Treffer: „Keine Vergleiche für »$query« gefunden."
