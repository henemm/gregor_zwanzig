# Context: fix-2317-anzeige-nach-neuladen

## Request Summary
Issue #2317: Auf `/trips/[id]` einen Wert ändern und innerhalb der 700-ms-Speicherverzögerung neu laden.
Der Server hat danach den neuen Wert, die neu geladene Seite zeigt aber noch den alten. Der Nutzer hält
die Eingabe für verloren. Seit #2316 („Aktualisieren") wird neu laden häufiger; `/compare/[id]` nutzt
denselben Wächter.

## Kernbefund aus der Recherche (gegengelesen)
Die im Bug benutzte Wertebereich-Obergrenze schickt beim Neuladen **keinen** `keepalive`-PUT, anders als
Issue und Spec #2316 annehmen. `CorridorEditor.svelte:177-186` (ebenso `CorridorEditorMobile.svelte:157-166`)
baut eine `saveFn` ohne `init`-Parameter. Die Option `{keepalive:true}` des Wächters geht verloren, dadurch:
- ein **normaler** PUT, eingereiht über `enqueueTripWrite` (Absenden erst im nächsten Microtask), mit `If-Match`
- beim Entladen darf der Browser normale Anfragen abbrechen. Dass der Wert trotzdem ankam, beweist nicht,
  dass „gespeichert" verlässlich ist.

Keepalive-fähig sind heute nur `EditStagesPanelNew.svelte:184-187` (Etappen) und der Vergleichs-Pfad der
Idealwerte (`CompareTabs.svelte:399-446`). Ebenfalls ohne `init`: Wetter-Metriken/Report-Config
(`WeatherMetricsTab`), Alarme (`AlarmeTab`).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/stores/ausstehendeSpeicherungSichern.ts` | Gemeinsamer Wächter (#2316 A): `willUnload` → `flush({keepalive:true})` ohne `cancel` (:40-42) |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | `schedule` 700 ms (:220-225), `hasPending` (:213), `flush(init)` → `doSave` → `saveFn(init)` (:163-186, :232-238), `defer` (:249) |
| `frontend/src/lib/api.ts` | `request` (:161-179): keepalive ⇒ nicht eingereiht, ohne If-Match; sonst `enqueueTripWrite` + If-Match; ETag-Übernahme (:150-156) |
| `frontend/src/lib/etagRegistry.ts` | `enqueueTripWrite` (:142-159), `adoptEtagFromPageLoad` nur bei Version 0 (:98-100) |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | Speichert Wertebereiche ohne `init` (:177-186); Compare-Zweig mit `init` (:227) |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | dito (:157-166 / :192) |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Muster **mit** `init` (:184-187) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Debounce-Verdrahtung der Reiter (:221-234), Reiterwechsel speichert vorher (:171-176) |
| `frontend/src/routes/trips/[id]/+page.server.ts` | SSR-Load: GET Trip + Metriken parallel, liefert `{trip, etag}` |
| `frontend/src/routes/trips/[id]/+page.svelte` | `trip = $state(data.trip)` einmalig (:21), `adoptEtagFromPageLoad` (:35-37), Wächter (:45); **kein** clientseitiges Nachladen |
| `frontend/src/routes/compare/[id]/+page.server.ts` / `+page.svelte` | `{preset, locations}` ohne ETag; Wächter (:57), `hubSaveCtl` ohne Kennung |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Nur Idealwerte laufen über `schedule`; Name/Region/Profil u.a. direkt `api.put` (Wächter wirkt dort nicht) |
| `frontend/src/lib/pwa/serviceWorkerUpdate.ts` | „Aktualisieren": `applyUpdate` (:205-210) → SKIP_WAITING → `controllerchange` → `reload()` (:95-110), Rückfall 4 s (:183-202). **Wartet nicht** auf ausstehende Speicherung |
| `frontend/src/routes/+layout.svelte` | Update-Hinweis (:206), `reload = location.reload()` (:158) |
| `frontend/src/service-worker.ts` | `/api/*` unberührt (:468); `/trips/<id>`, `/compare/<id>` Netz zuerst (:381-400). Online keine zweite Ursache |
| `internal/handler/trip.go` | GET (:61) und PUT (:275) nehmen dieselbe Sperre je Nutzer+Kennung (`briefing_lock.go:30-45`) |
| `internal/handler/etag.go`, `briefing_fingerprint.go` | ETag = sha256 der Dateibytes; If-Match-Prüfung |
| `frontend/src/routes/api/[...path]/+server.ts` | Lokal/E2E: Browser-PUT läuft über den SvelteKit-Proxy; SSR-GET direkt an `apiBase()` |
| `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts` | AC-10 (:53-113) prüft nur Serverwert, Anzeige bewusst nicht (:108-111); CI-Ratsche `ci_e2e_specs.txt:165` |
| `frontend/e2e/pwa-update-erkennung.spec.ts` | AC-10 über echten Update-Weg (:379-433), nur Serverwert |
| `frontend/src/lib/stores/__tests__/ausstehendeSpeicherungSichern.test.ts`, `frontend/src/lib/__tests__/apiKeepaliveSkipsIfMatch.test.ts`, `fakeTripServer.ts` | Unit-Schicht; **kein** Test, dass Speicherfunktionen `init` weiterreichen |

## Existing Patterns
- Speichern beim Verlassen: `beforeNavigate` + `willUnload` → still flushen, keine Rückfrage (PO-Entscheid 2026-07-25, #1376).
- keepalive-Schreiben: nicht eingereiht, ohne If-Match (#1395 S3 AC-6), ETag nur übernehmen, wenn unverändert.
- Gerätespeicher: `sessionStorage` nur für den Abmelde-Merker (`lib/pwa/geraetespeicher.ts`), mandantengetrennt und beim Abmelden geleert (ADR-0003, #2127-Leitsatz 2).
- Kein `pagehide`/`sendBeacon`/`BroadcastChannel`/Entwurfs-Wiederherstellung im Frontend.

## Dependencies
- Upstream: SvelteKit `beforeNavigate`, Fetch `keepalive`, Go-Trip-Handler mit Sperre + ETag, Service Worker (Netz zuerst).
- Downstream: alle Reiter der Trip-Detailseite, Idealwerte im Ortsvergleich, Update-Hinweis aus #2316, E2E-Ratschen `E2E_MIN_EXECUTED_HAUPT`/`_PWA`.

## Existing Specs
- `docs/specs/modules/pwa_update_erkennung.md` — AC-9/AC-10 sichern „gespeichert", Known Limitation verweist auf #2317
- `docs/specs/modules/trip_stage_date_editing.md` — #1376 `willUnload`-Flush
- `docs/specs/_archive/modules/issue_758_save_indicator.md` — Speichern vor Navigation
- `docs/specs/modules/issue_1395_s3_etag_registry.md` (+ S2/S4/S6) — keepalive ohne If-Match, Warteschlange
- `docs/adr/0061-pwa-service-worker-bauform.md`, `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md`

## Risks & Considerations
- **Ursache nicht belegt.** Zwei Kandidaten: (a) SSR-GET erreicht Go vor dem PUT (Zeitrennen), (b) der PUT ist gar kein keepalive und kommt spät bzw. nur zufällig an. Erst messen, dann entscheiden.
- Beim Browser-Neuladen (F5, Wischgeste) kann die App das Entladen nicht aufhalten. Beim „Aktualisieren"-Knopf kann sie vorher auf das Speichern warten.
- Eine clientseitige Nachlade-/Überblendlogik darf keine **ungespeicherten** Werte als gespeichert zeigen und keine neuere fremde Fassung überschreiben (ETag/If-Match #1395).
- Gerätespeicher-Lösungen müssen mandantengetrennt sein und beim Abmelden geleert werden.
- keepalive-Rumpf ist browserseitig auf 64 KB begrenzt: Trip-PUTs mit vollem `display_config` prüfen.
- Trip/Vergleich-Code-Teilung: Lösung im gemeinsamen Baustein, nicht doppelt.
- Alle Tests laufen ohne `uv run pytest` ohne Dateiliste; Frontend `node --test`, E2E nur über die Ratsche.

## Analysis

### Type
Bug (mit verdecktem Datenverlust-Risiko)

### Befund (statisch belegt, Messung gescheitert)
- Drei Trip-Speicherfunktionen, die über `schedule()` laufen, verschlucken die `{keepalive:true}`-Option des
  Wächters: Wertebereiche (`CorridorEditor.svelte:177-186`, `CorridorEditorMobile.svelte:157-166`), Alarme
  (`AlarmeTab.svelte:314-317`), Wetter-Metriken/Report-Config (`WeatherMetricsTab.svelte:973-979`, `:997-1001`).
- `WeatherMetricsTab.svelte:973-979` schickt zwei PUTs **nacheinander** (`/weather-config`, dann `/api/trips/{id}`).
  Beim Entladen kommt die Antwort des ersten nie an, der zweite startet also nie. Beide Go-Handler nehmen
  dieselbe Sperre (`weather_config.go:29,66`, `trip.go`) und mergen strukturell; die Reihenfolge dient nur der
  lokalen Übernahme von `alert_rules` (#850).
- TypeScript kann das nicht verhindern: `async () => …` erfüllt `SaveFn = (init?) => Promise<void>`.
- Go serialisiert GET und PUT je Trip. Eine veraltete Anzeige heißt: Der PUT war beim SSR-GET noch nicht bei Go
  oder kam nie an. Selbst mit korrektem keepalive ist die Reihenfolge nicht garantiert. Deshalb braucht es
  **zusätzlich** eine Anzeige-Korrektur.
- Messversuch (lokaler isolierter E2E-Stack, Ports 18091/18000): Das Login-Setup hing, kein Testkörper lief.
  Ursachen-Nachweis aus Nutzersicht folgt in `/40` über den bestehenden E2E-Fall (Anzeige-Assert statt Kommentar
  `speicherung-ueberlebt-neuladen.spec.ts:108-111`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | MODIFY | `init` durchreichen |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | MODIFY | `init` durchreichen |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | `init` durchreichen |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | `init` durchreichen; mit keepalive beide PUTs sofort absetzen, normal unverändert nacheinander |
| `frontend/src/lib/stores/ausstehendeSpeicherungSichern.ts` | MODIFY | beim Entladen-Flush Merker „Trip/Vergleich X beim Entladen gespeichert" (nur Kennung, kein Inhalt) |
| `frontend/src/lib/stores/nachEntladenNachladen.ts` (Name offen) | CREATE | geteilter Baustein: Merker lesen+löschen, begrenzt nachladen, nur übernehmen wenn Fassung neuer und nichts lokal aussteht |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | Baustein verdrahten (Zustand + ETag-Registry aktualisieren) |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | Baustein verdrahten (ohne ETag, Inhaltsvergleich) |
| `frontend/src/routes/+layout.svelte`, `frontend/src/lib/pwa/serviceWorkerUpdate.ts` | MODIFY | „Aktualisieren": vor SKIP_WAITING ausstehende Speicherung normal abschließen. Kontext fließt nur von oben nach unten ⇒ Layout stellt eine Anmeldestelle bereit, die Seite meldet ihren `SaveStatus` dort an |
| `frontend/src/lib/pwa/geraetespeicher.ts` | MODIFY | Merker beim Abmelden mit räumen (Leitsatz 2) |
| `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts` | MODIFY | Anzeige-Assert nach Neuladen (Trip + Vergleich, alle drei Reiter) |
| `frontend/src/lib/**/__tests__/*` | CREATE/MODIFY | je Speicherfunktion: `flush({keepalive:true})` ⇒ Fetch mit keepalive; Nachlade-Baustein (Obergrenze, Pending-Schutz, ältere Fassung) |
| `docs/specs/modules/pwa_update_erkennung.md` | MODIFY | Known Limitation korrigieren: „gespeichert" galt für diese Felder nie verlässlich |

### Scope Assessment
- Files: ~12 (davon ~4 Tests)
- Estimated LoC: +250…350 / -20 (Tests zählen mit) ⇒ `loc_limit_override 500` statt Scheibenschnitt
- Risk Level: MEDIUM

### Technical Approach
Ein Ticket, eine Spec, drei Bausteine in fester Reihenfolge:
1. **Speichern verlässlich:** jede über `schedule/defer` gemeldete Speicherung geht beim Entladen als keepalive raus
   (auch beide Wetter-PUTs). Absicherung per Verhaltenstest je Speicherfunktion, weil der Typ es nicht erzwingt.
2. **„Aktualisieren" wartet:** vor dem Fassungswechsel wird eine ausstehende Speicherung normal abgeschlossen. Kein
   Zeitrennen auf dem häufigsten Weg.
3. **Anzeige nach Browser-Neuladen:** Merker (nur Kennung, sessionStorage, beim Abmelden geräumt) ⇒ nach dem Laden
   begrenztes Nachladen. Übernommen wird nur, wenn die Server-Fassung neuer ist **und** keine neue lokale Eingabe
   aussteht. Kein Inhalt im Gerätespeicher (Option B verworfen: könnte Ungespeichertes als gespeichert zeigen).

Verworfen: nur Anzeige korrigieren (würde einen verlorenen Wert korrekt anzeigen); Verlassen-Rückfrage
(PO-Entscheid 2026-07-25); Aufteilen in Scheiben (Ticket ist nur mit allen drei behoben).

### Dependencies
- Baustein 3 setzt Baustein 1 voraus (sonst lädt er einen nie gespeicherten Wert nach).
- ETag-Registry `adoptEtagFromPageLoad` übernimmt nur bei Version 0 ⇒ Nachladen braucht einen Übernahmeweg für
  „neuere Fassung vom Server" ohne den If-Match-Schutz zu schwächen.

### Open Questions
- keine an den PO; Detailfragen (Nachlade-Obergrenze, Hinweis während des Nachladens) entscheidet die Spec.
