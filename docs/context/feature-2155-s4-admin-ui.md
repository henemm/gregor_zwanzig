# Context: feature-2155-s4-admin-ui

## Request Summary
#2155 S4: Minimal-UI `/admin` (Nutzerliste, Tier-Dropdown, Konto sperren/entsperren) plus Navigationseintrag, sichtbar nur für Admins. Backend (S1–S3) ist live, S4 ist reine Frontend-Arbeit.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/admin_users.go` | DTO `AdminUser` + 3 Handler (Routen `internal/router/router.go:287-289`, `requireAdmin`) |
| `docs/reference/api_contract.md` (ab Z. 1496, Routen Z. 175-177) | Vertrag der Admin-API |
| `frontend/src/routes/+layout.server.ts` | holt Profil, reicht `role` heute NICHT durch → `isAdmin` ergänzen |
| `frontend/src/routes/+layout.svelte` (Z. 255-280) | rendert Sidebar, BottomNav, KontoSheet |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` (Z. 30) | hartkodiertes `navItems` (Desktop) |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` (Z. 32) | mobil, voll → Admin-Link stattdessen im KontoSheet |
| `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte` (Z. 36) | `links`-Array, Ort für Admin-Link mobil |
| `frontend/src/lib/types.ts:712` | `UserTier`; kein `role`-Feld |
| `frontend/src/routes/account/+page.svelte:123-127` | lokale `TIER_LABELS` (keine geteilte Konstante) |
| `frontend/src/routes/account/+page.server.ts` | Muster: `load({cookies})`, Cookie `gz_session`, `API()` aus `$lib/server/apiBase.ts` |
| `frontend/src/routes/api/[...path]/+server.ts` | Proxy, reicht Status 403/409/400 unverändert durch |
| `frontend/src/hooks.server.ts` | nur Session-Guard, kein Rollenschutz |
| `frontend/src/routes/account/__tests__/premium_sms_link_code_load.test.ts` + `server-load-resolve.hooks.mjs` | Vorlage für `load()`-Tests (node --test, fetch-Ersatz) |

## API-Vertrag (S3)
- `GET /api/admin/users` → 200 `{"users":[AdminUser]}`
- `AdminUser` (kein omitempty): `id, email, display_name, tier, requested_tier, requested_at, email_verified_at, created_at, disabled, is_test_user, last_trip_report_run ({time,status,error}|null)`
- `PUT …/{id}/tier` `{"tier":"free|standard|premium"}` → 200 AdminUser (löscht `requested_tier`/`requested_at`)
- `PUT …/{id}/disabled` `{"disabled":bool}` (Pflicht) → 200 AdminUser
- Fehler `{"error":code}`: 401, 403 `forbidden`, 400 `invalid_request`/`invalid_tier`, 404 `not_found`, 409 `cannot_disable_self`, 500 `store_error`

## Existing Patterns
- Wiederverwendbar: Atoms `Switch, Pill, Btn, Card, PageHeader, Dot` (`atoms/index.ts`), `ui/select/Select.svelte` (natives select), `molecules/ConfirmDialog.svelte`, `organisms/ListTable.svelte`.
- Import-Guard `issue_470_atom_import_guard.test.ts`: Seiten nutzen atoms/molecules, nicht direkt `ui/`.
- Mutationen laufen im Client via `fetch('/api/...')`/`$lib/api.ts`, keine Form-Actions.
- Rollenschutz im Frontend existiert nirgends; `admin/+page.server.ts` prüft `profile.role`, Go bleibt die eigentliche Sperre.
- Keine Svelte-Render-Umgebung: reine Helfer als `.ts` daneben testen.

## Dependencies
- Upstream: Admin-API (S3), `role` aus `GET /api/auth/profile` (`internal/handler/auth.go`, `profileRole`, `GZ_ADMIN_USER_IDS`).
- Downstream: Navigation (3 Komponenten), Layout-Daten.

## Existing Specs
- `docs/specs/modules/admin_rolle_s1.md` (S4 dort Nicht-Ziel), ADR-0078 (Admin-Rolle), ADR-0080 (Kontosperre), Kontexte `feature-2155-admin-rolle.md`, `feature-2155-s3-admin-api.md`.

## Risks & Considerations
- Sichtbarkeit: Nav-Eintrag nur für Admins, aber Seite muss auch bei Direktaufruf durch Nicht-Admin abweisen (Server-Load) — Test mit zwei Nutzern (Admin/Nicht-Admin).
- Auf Prod ist `GZ_ADMIN_USER_IDS` leer: niemand sieht die Seite dort, Betriebsfrage für den PO offen. Staging: Konto `gz-staging-admin` (`.claude/staging_admin.env`).
- Selbstsperre (409) und 403/404 müssen in der UI sichtbar behandelt werden; Sperren mit Bestätigungsdialog.
- Tier-Labels mehrfach definiert → zentrale Konstante statt dritter Kopie.
- Staging-Datenbestand für `hem` nicht lesbar; UI-Prüfung nur per Browser/API mit Admin-Konto.
- Kein Passwort-Hash/Token im DTO — UI darf nichts darüber hinaus anzeigen.

## Analysis

### Type
Feature (reine Frontend-Arbeit, Backend S1–S3 live)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/routes/+layout.server.ts` | MODIFY | `isAdmin` aus `profile.role === 'admin'` durchreichen (gleicher Profil-Abruf) |
| `frontend/src/routes/+layout.svelte` | MODIFY | `isAdmin` an Sidebar/KontoSheet weitergeben |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | MODIFY | Nav-Eintrag „Admin" nur bei `isAdmin` |
| `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte` | MODIFY | Admin-Link mobil nur bei `isAdmin` (BottomNav ist voll) |
| `frontend/src/routes/admin/+page.server.ts` | CREATE | Load: Rolle prüfen (Nicht-Admin abweisen), Nutzerliste holen |
| `frontend/src/routes/admin/+page.svelte` | CREATE | Nutzerliste, Tier-Dropdown, Sperren/Entsperren mit ConfirmDialog, Fehleranzeige |
| `frontend/src/lib/admin.ts` (o. ä.) | CREATE | Reine Helfer (zentrale Tier-Labels, Fehlercode→Text) |
| `frontend/src/routes/admin/__tests__/*.test.ts` | CREATE | `node --test`: Load Admin vs. Nicht-Admin, Helfer |
| `frontend/src/lib/types.ts` | MODIFY | `AdminUser`-Typ |
| `frontend/e2e/…` | CREATE | Playwright-Spec gegen Staging (Konto `gz-staging-admin`) |
| `docs/specs/modules/admin_ui_s4.md` | CREATE | Spec mit ACs |

### Scope Assessment
- Files: ~10
- Estimated LoC: +350/-5 (ggf. `loc_limit_override`)
- Risk Level: LOW–MEDIUM (Backend unverändert; Risiko: Sichtbarkeit/Rollenschutz, Selbstsperre)

### Technical Approach
1. `isAdmin` im Layout-Load aus vorhandenem Profil-Abruf ableiten (kein Zusatzabruf).
2. Nav-Eintrag nur für Admins: Desktop Sidebar, mobil im KontoSheet.
3. `/admin/+page.server.ts` prüft Rolle serverseitig, Nicht-Admin wird abgewiesen (Go bleibt die eigentliche Sperre).
4. Mutationen im Client per `fetch('/api/admin/users/{id}/tier|disabled')` (Projektmuster); Antwort-`AdminUser` ersetzt die Zeile.
5. Sperren mit `ConfirmDialog`; Fehler 403/404/409 (`cannot_disable_self`)/400 in Klartext.
6. Tier-Labels als zentrale Konstante; Bauteile aus atoms/molecules (Import-Guard #470).
7. Nur DTO-Felder anzeigen; `requested_tier` hervorheben (Freigabe ist der Hauptanlass).

### Dependencies
Upstream: Admin-API S3, `role` aus `/api/auth/profile` (`GZ_ADMIN_USER_IDS`). Downstream: 3 Navigationskomponenten, Layout-Daten.

### Open Questions
- [ ] Betrieb: Auf Prod ist `GZ_ADMIN_USER_IDS` leer → niemand sieht die Seite. Setzen ist Betriebsaufgabe, kein Code (in Spec als Hinweis).
