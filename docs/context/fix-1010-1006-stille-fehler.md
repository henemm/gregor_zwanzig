# Context: fix-1010-1006-stille-fehler (Issues #1010 + #1006)

## Request Summary
PO-Bündel (2026-07-04): Zwei „stille Fehler"-Bugs. #1010: Etappen-Startzeit-Eingabe
geht verloren, obwohl der Nutzer sie eingetragen hat (heute zweimal live passiert,
PO-Daten). #1006: Abgelaufene Sitzung (24h-TTL) führt bei Aktionen/Eingaben zu
unspezifischen Fehlermeldungen bzw. stillem Verlust statt klarem Re-Login-Hinweis.

## Root Cause #1010 (BESTÄTIGT, nicht gerätespezifisch!)
`frontend/src/lib/components/edit/EditStagesPanelNew.svelte:144-154`
(`handleStartTimeChange`, Issue #675) aktualisiert NUR den lokalen State — als
EINZIGER Änderungs-Handler des Panels ruft er weder `scheduleSave()` noch `save()`
auf (vgl. Zeilen 133, 140, 270: alle anderen Handler tun das). Wer ausschließlich
die Startzeit ändert, speichert nie — auf jedem Gerät. Der Verdacht „iPhone" war
Zufall: Auf Desktop rettet oft eine zweite Änderung (anderer Handler) die Startzeit
mit. Beleg heute: PO trug 11:00 ein (gültige Sitzung, 13:35), Nginx-/API-Logs
zeigen NULL Schreibzugriffe.
Aufruferkette: `StageTimeField.svelte` (Issue #675, input type=time) →
`onchange={(newTime) => handleStartTimeChange(...)}` (Zeile 344).

## Root Cause #1006
`frontend/src/lib/api.ts::request()` (Zeilen 3-19): wirft bei !res.ok den
JSON-Fehler — für 401 kommt `{"error":"unauthorized"}` (Go-Middleware,
internal/middleware/auth.go:58-62) und landet als nichtssagende Meldung in den
jeweiligen Komponenten-Fehlerpfaden (z.B. saveController.setError, „Speichern
fehlgeschlagen"). Seiten-NAVIGATION wird via hooks.server.ts (24h-TTL-Check,
frontend/src/lib/auth.ts:verifySession) korrekt zu /login umgeleitet — aber
Client-Fetches aus offenen Tabs nicht. Beide Vorfälle heute dokumentiert in #1006
(Kommentare mit Logbelegen).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte:144-154,344` | #1010-Kernfix: handleStartTimeChange muss speichern (scheduleSave/save wie die Nachbar-Handler) |
| `frontend/src/lib/components/edit/StageTimeField.svelte` | Startzeit-Input (#675) — Ereignisquelle, vermutlich unverändert lassbar |
| `frontend/src/lib/api.ts:3-19` | #1006-Kernfix: zentrale 401-Behandlung im request()-Wrapper (EIN Ort für alle api.*-Aufrufe) |
| `frontend/src/hooks.server.ts` + `frontend/src/lib/auth.ts` | bestehende Session-Prüfung (24h) für Seitenloads — Vorbild/Konsistenz |
| `frontend/src/routes/login/+page.svelte` | Ziel des Redirects; Hinweis „Sitzung abgelaufen" (Query-Param) |
| `frontend/src/lib/stores/saveStatusStore.svelte` | Auto-Save-Controller (#758) — Fehlerpfad zeigt heute nur setError(msg) |
| `tests/tdd/test_issue_675_stage_start_time.py` | bestehende Playwright-Suite Startzeit (staging-gebunden) — Vorbild für E2E |
| `e2e/` bzw. frontend/e2e | Playwright-Infrastruktur für Staging-E2E |

## Existing Patterns
- Save-Pattern im Panel: `if (saveController) scheduleSave(); else void save();`
  (drei Vorbilder in derselben Datei — #1010-Fix ist eine Zeile nach diesem Muster).
- Session-Validierung: identische TTL-Logik Frontend (auth.ts) und Go
  (middleware/auth.go) — 401 vom Server ist der verlässliche Trigger.
- Login-Seite existiert; Redirect-Pattern aus hooks.server.ts (redirect 302 /login).

## Risks & Considerations
- **#1006-Redirect-UX:** Bei 401 während Auto-Save droht Verlust ungespeicherter
  Eingaben durch harten Redirect — Meldung muss VOR dem Redirect sichtbar sein
  bzw. Redirect mit Query-Param (?expired=1&redirect=<pfad>) zurückführen.
  Eingabe-Erhalt über Login hinweg ist ausdrücklich NICHT Teil dieses Bündels
  (wäre Feature; im Issue #1006 als „idealerweise" notiert → Known Limitation).
- **Kein Design-Neubau:** Meldung über bestehende Fehler-/SaveStatus-Mechanik bzw.
  Login-Seiten-Hinweis — keine neue UI-Architektur (sonst Design-Request nötig).
- **E2E-Pflicht:** Frontend-Bugs → Playwright gegen Staging als eingeloggter
  Nutzer; #1010 rot-vor-Fix reproduzieren (nur Startzeit ändern → Reload → weg).
  401-Fall E2E: Sitzung künstlich altern lassen ist schwer — Cookie löschen/
  manipulierten Cookie setzen simuliert den Ablauf REAL (der Server lehnt echt ab).
- Scope frontend-only → E2E-Pfad „frontend" (kein Mail-Versand nötig); aber
  Playwright-Nachweis Pflicht.

## Analysis — Scope
| File | Change |
|------|--------|
| EditStagesPanelNew.svelte | MODIFY (~3 LoC): handleStartTimeChange → scheduleSave/save nach Staging-Muster |
| api.ts | MODIFY (~15 LoC): 401 → zentrale Behandlung (Redirect /login?expired=1 + aussagekräftiger Fehler) |
| login/+page.svelte | MODIFY (~10 LoC): Hinweis-Banner bei ?expired=1 |
| e2e/ Playwright-Spec | CREATE: #1010-Repro + #1006-401-Fall |
Risk: LOW (zwei kleine, zentrale Fixes nach bestehenden Mustern)
