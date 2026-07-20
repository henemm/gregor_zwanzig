# Context: fix-1329-e2e-data-hygiene (#1329 Maßnahme B)

## Request Summary
Staging hat 706 Waisen-Orte + 429 Presets angesammelt (Prod: 31 / 19). Zwei Ziele:
(1) einmaliger Räumlauf auf dem Staging-Host, (2) E2E-Läufe so härten, dass sie ihre
Wegwerf-Daten selbst entfernen und die Anhäufung nicht nachwächst.

## Root Cause der Anhäufung (belegt via Explore-Recherche)
1. **Kein `globalTeardown`** in irgendeiner Playwright-Config → kein Sicherheitsnetz.
   Es gibt nur `frontend/e2e/global.setup.ts` (seedet 3 feste, idempotente Orte
   `e2e-loc-innsbruck/stubai/zillertal`, kein Leak) — aber kein Gegenstück, das aufräumt.
2. **`createLocation()` 12× per Copy-Paste dupliziert** statt zentral in `helpers.ts`.
   Mehrere Kopien registrieren die ID gar nicht für Teardown (z.B.
   `layout-tab-vergleich.spec.ts:18`, `compare-cross-user-write-block.spec.ts:19`).
3. **DELETE-Fehler werden verschluckt** (37× `.catch(() => {})`, Kommentar
   „Cleanup-Fehler nicht test-kritisch"). Geschluckte Fälle sind 401 (Session
   bereits abgelaufen, wenn Cleanup nach langer Testlaufzeit greift) oder 500 →
   Ort bleibt lautlos liegen. Korrektur: `DeleteLocationHandler`
   (`internal/handler/location.go`) macht KEINEN Reference-Check und liefert
   nie 409 — ein referenzierendes Preset blockiert die Ort-Löschung nicht. Die
   in der Härtung eingeführte Reihenfolge Preset-vor-Ort ist daher
   vorsorglich/Best-Practice (verhindert Waisen-Presets, die auf bereits
   gelöschte Orte zeigen), nicht der Fix eines existierenden 409-Pfads.
4. **Presets/Trips gelöscht, zugehörige Orte geleakt**: `issue-758`, `issue-951`,
   `versand-tab-vergleich`, `feat-880`.
5. **Uneinheitliche/fehlende Namens-Präfixe**: Nur ~45 der 706 sind offensichtlich
   `E2E`/`test`-benannt. Waisen wie `Loc-Mobile-A`, `Ort-880-A`, `Ort-758-A`, `Ort-951`,
   `__test_c4_group__` und Smart-Import-Orte (`issue-1080`) tragen KEINEN Test-Marker →
   von echten Orten nicht unterscheidbar. Präfix-Filter allein räumt nur die 45.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/helpers.ts` | Zielort für EINEN geteilten, auto-räumenden Location/Preset-Helfer |
| `frontend/e2e/global.setup.ts` | Bestehender Seed (3 feste Orte); Vorbild für ein `global.teardown.ts` |
| `frontend/e2e/playwright.*.staging.config.ts` | Configs, in die `globalTeardown` verdrahtet wird |
| 12 Spec-Dateien mit dupliziertem `createLocation()` | Migration auf geteilten Helfer |
| ~10 Spec-Dateien mit 0 Cleanup (`compare-editor-slice3/4`, `issue-682/718/758/951`, `feat-880`, `versand-tab-vergleich`, `layout-tab-vergleich`, `orts-vergleich-c4`) | garantierte Leaks — vorrangig migrieren |
| `internal/scheduler/scheduler_gate.go` / `cmd/server/main.go` | A-Gate: `SchedulerEnabled = Env != "staging"` — Scheduler auf Staging AUS |

## Dependencies
- **Upstream:** Go-REST-API `POST/DELETE /api/locations`, `.../compare-presets`, `.../trips`.
- **Downstream:** Alle Compare-/Trip-E2E-Specs, die Orte anlegen.

## Existing Specs
- Keine direkte; Bezug: Issue #1329 (Maßnahmen A–D).

## Design-Entscheidung 1 — Scheduler-Namespace-Skip: STREICHEN (Empfehlung)
Maßnahme A schaltet den Scheduler auf Staging bereits komplett ab
(`SchedulerEnabled = Env != "staging"`). Die Waisen-Orte werden auf Staging also gar
nicht mehr gepollt. Der ursprünglich in B genannte „Scheduler ignoriert Wegwerf-Namespace"
ist damit für das Kontingent-Ziel **redundant** und würde nur den prod-berührenden
Scheduler-Pfad (Kollisionsrisiko: echte Nutzer-Orte fälschlich überspringen) anfassen.
→ **Aus B streichen.** B = Räumen + selbsträumende E2E.

## Design-Entscheidung 2 — Räumlauf-Diskriminator
Präfix-Filter erfasst nur ~45/706. Staging hat **keine echten Produktiv-Nutzer** (reine
Testumgebung). Empfohlener Ops-Ansatz: **Allowlist-erhalten** — nur die vom Test-Harness
benötigten Seeds/Konten behalten, den Rest der Orte/Presets löschen. Mit Backup, als
`claude-gregor` auf dem Staging-Host, nach PO-„go".

## Härtungs-Ansatz (Regrowth-Prävention)
- **EIN geteilter Helfer** in `helpers.ts`: legt Ort/Preset/Trip an, vergibt reserviertes
  Präfix, registriert ID automatisch.
- **`global.teardown.ts`** als Sicherheitsnetz: löscht am Suite-Ende alles mit reserviertem
  Präfix (Presets VOR Orten → kein 409). In Configs als `globalTeardown` verdrahtet.
- **DELETE-Reihenfolge Preset→Ort** ist vorsorglich (verhindert Waisen-Presets auf bereits gelöschte Orte); der Go-Handler liefert nie 409 — s. korrigierte Ursache #3.

## Risks & Considerations
- Massen-Löschung auf Staging: Backup + Allowlist zwingend; nichts auf Prod.
- Migrations-Breite (~20 Dateien) kann LoC-Limit sprengen → ggf. auf „Sicherheitsnetz +
  Worst-Offender-Migration + reserviertes Präfix" begrenzen, Rest fängt das globalTeardown.
- Kollisionsarme Namen ohne `Date.now()`-Suffix (`Loc-Mobile-A`) mitfixen.
