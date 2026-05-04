# Context: Konto erweitern

## Request Summary
Die `/account`-Seite soll um drei Bereiche erweitert werden: vollständige Kanal-Konfiguration (E-Mail, Signal, SMS, Satellite), Verwaltung gespeicherter Wetter-Templates, und Integration des System-Status (aktuell verwaist auf `/settings`).

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/account/+page.svelte` | **Hauptdatei** — aktuelle Konto-Seite (272 LoC): Profil, Kanäle (E-Mail/Signal/Telegram), Passwort, Account-Löschung |
| `frontend/src/routes/account/+page.server.ts` | Loader — lädt nur Profil, muss um Scheduler/Health/Trips/Subs/Locations erweitert werden |
| `frontend/src/routes/settings/+page.svelte` | **Verwaiste** System-Status-UI (178 LoC) — redirect 301 → /account seit Alt-Routen-Cleanup |
| `frontend/src/routes/settings/+page.server.ts` | Redirect 301 → /account |
| `src/app/metric_catalog.py:382-447` | `WEATHER_TEMPLATES` — 7 hardcoded Templates + `get_all_templates()` |
| `api/routers/config.py` | GET `/templates` API-Endpoint |
| `src/app/user.py` | User/Preferences Datenmodelle, Subscriptions |
| `src/app/config.py:96-97` | SMS-Config: `sms_gateway_url`, `sms_api_key` (system-level, nicht pro User) |
| `src/outputs/signal.py` | Signal via Callmebot API |
| `src/outputs/base.py:66-106` | Channel-Factory (`get_channel()`) — Email, Signal, SMS, Telegram, Console |
| `src/web/scheduler.py:284-302` | `/_scheduler_status` Endpoint |

## Existing Patterns

- **Kanäle auf Account-Seite:** E-Mail, Signal (Phone + write-only API Key), Telegram — einzelne Input-Felder in Card "Kanäle", gespeichert via `PUT /api/auth/profile`
- **System-Status auf Settings:** 3 Cards — "Deine Reports" (Scheduler-Jobs), "Dein Account" (Zähler + Channel-Badges), "Verfügbarkeit" (Health + Version)
- **Templates:** Statisch im Python-Code, keine User-spezifischen Templates. API liefert Liste mit `{id, label, metrics[]}`
- **Channel-Config:** E-Mail/Signal/Telegram sind per-User im Profil. SMS ist system-level (config.ini), kein per-User SMS

## Dependencies

- **Upstream:** Go API (`/api/auth/profile`, `/api/health`, `/api/scheduler/status`, `/api/locations`, `/api/subscriptions`, `/api/trips`, `/templates`)
- **Downstream:** Scheduler liest Kanal-Config pro User, Subscription-Processing nutzt Channel-Factory

## Existing Specs

- `docs/specs/modules/account_page.md` — Original Account-Seite (v1.0, implemented, F61)
- `docs/specs/modules/account_page_extend.md` — Signal API Key + Deletion (v1.0, draft, F72/F73) — **bereits implementiert**
- `docs/specs/ux_redesign_navigation.md` — UX Redesign Gesamt-Spec (#76)

## Ist-Zustand

### Account-Seite (`/account`)
1. **Profil** — Username, Mitglied seit (read-only)
2. **Kanäle** — E-Mail, Signal (Phone + API Key), Telegram — Speichern-Button
3. **Passwort ändern** — Alt/Neu/Bestätigen
4. **Gefahrenzone** — Account löschen mit Bestätigung

### System-Status (`/settings` → 301 → `/account`)
Die Settings-Svelte-Datei existiert noch, wird aber nicht gerendert (Redirect). Enthält:
1. **Deine Reports** — Morgen/Abend/Trip-Jobs mit Status-Dots und Next/Last-Run
2. **Dein Account** — Trips/Abos/Locations-Zähler, Channel-Badges, Wetter-Modelle pro Location
3. **Verfügbarkeit** — Health-Status-Dot + Version

## Scope-Analyse für "Konto erweitern"

### 1. Kanäle (E-Mail, Signal, SMS, Satellite)
- **E-Mail + Signal + Telegram:** Bereits vorhanden ✅
- **SMS:** Backend existiert system-level (config.ini), aber kein per-User SMS-Config. Braucht API-Erweiterung im Go-Backend + neue Felder
- **Satellite:** Kein Backend. Wahrscheinlich nur Info-Text / Coming-Soon

### 2. Gespeicherte Templates verwalten
- Templates sind aktuell hardcoded. Kein User-Speicher-Mechanismus
- Braucht: API zum Speichern/Laden von User-Templates, UI zur Verwaltung
- **Scope-Frage:** Nur bestehende System-Templates anzeigen? Oder Custom-Templates erstellen/editieren?

### 3. System-Status integrieren
- Content existiert bereits in `settings/+page.svelte` — muss in `/account` verschoben/eingebettet werden
- Loader muss um Scheduler/Health/Trips/Subs/Locations erweitert werden

## Risks & Considerations

1. **Settings-Seite verwaist:** Der Svelte-Content ist unerreichbar seit dem 301-Redirect. Muss in Account integriert oder gelöscht werden
2. **SMS per-User vs system-level:** Aktuell ist SMS system-weit konfiguriert, nicht per User. Per-User SMS braucht Go-API-Änderungen
3. **Satellite:** Kein Backend — Scope klären (Placeholder vs. echte Integration)
4. **Template-Speicherung:** Neues Konzept — braucht Datenmodell, API, UI. Könnte den Scope sprengen
5. **Account-Seite wird lang:** Mit System-Status + Templates + alle Kanäle wird die Seite komplex → Tab- oder Accordion-Layout erwägen
