---
entity_id: feat_3197_tempo_je_etappe
type: module
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: feat-3197-tempo-je-etappe
tags: [trip, etappen, tempo, gehzeit, ueberschreibung, pausentag, i18n, kanal-paritaet, epic-2791]
---

# Einstellungen neu S4b-2: Tempo je Etappe überschreiben, Gehzeit und „Tempo ändern“ (#3197)

## Approval

- [ ] Approved

## Purpose

Das Trip-Tempo (Fortbewegung und Grundtempo, #3196) gilt bisher für alle Etappen gleich. Eine Bergetappe oder ein Ruhetag braucht aber ein eigenes Tempo. Diese Spec gibt jeder Etappe im Reiter Etappen die Zeile „Gehzeit h:mm" mit dem Knopf „Tempo ändern": Der Nutzer überschreibt das Grundtempo nur für diese Etappe. Ohne Überschreibung gilt das Trip-Tempo. Gehzeit und bewertete Stunden der Wegpunkte ändern sich nur bei der überschriebenen Etappe, in allen vier Kanälen gleich.

Grundlagen: Issue #3197 (Teil von #2796, Epic #2791), ADR-0108 (Override je Etappe nur Grundtempo), ADR-0095 (Kanal-Parität), ADR-0101 (Read-Modify-Write), ADR-0104 (zweisprachig), Vorgänger-Spec `docs/specs/modules/feat_3196_trip_tempo_etappen.md`, Analyse `docs/context/feat-3197-tempo-je-etappe.md`, Soll-Bild `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (Etappenzeile mit „Gehzeit …" und Knopf „Tempo ändern").

## Entscheidungen (Tech Lead, aus ADR-0108 abgeleitet)

1. **Je Etappe wird NUR das Grundtempo (km/h) überschrieben.** Die Fortbewegung (zu Fuß, Rad, MTB, Ski) bleibt trip-weit (ADR-0108). Der Issue-Wortlaut „Tempo flach/Aufstieg" wird ADR-konform erfüllt: Steig- und Abstiegsraten skalieren mit `R = R_ref · v / v_ref` (Spec #3196). Ein eigenes Grundtempo wirkt dadurch auf flach UND Aufstieg/Abstieg; ein getrenntes Aufstiegstempo je Etappe gibt es bewusst nicht.
2. **Datenform:** Feld `Stage.grundtempo_kmh`, optional, absolut in km/h, Bereich 0,5 bis 60 (wie das Trip-Grundtempo). Fehlt es, gilt das Trip-Grundtempo.
3. **Verworfene Alternativen:**
   - `Stage.tempo = {fortbewegung, grundtempo_kmh}` verschachtelt: Das ergäbe nur Sinn, wenn die Fortbewegung je Etappe überschreibbar wäre; ADR-0108 schließt das aus.
   - Relativer Faktor zum Trip-Tempo („20 % langsamer"): Der Wert wanderte still mit, wenn der Nutzer das Trip-Tempo ändert, und wäre schwer erklärbar. Ein absoluter Wert ist eindeutig und im Mockup als Zahl vorgesehen.
4. **Wechsel der Trip-Fortbewegung verwirft alle Etappen-Überschreibungen**, mit Hinweis, wie viele Etappen zurückgesetzt wurden. Ein 3-km/h-Wert zu Fuß ist auf dem Rad sinnlos; der Wechsel setzt das Trip-Grundtempo ohnehin schon auf den Vorschlagswert (Spec #3196, AC-4).
5. **Pausentag** (Etappe ohne Wegpunkte): kein Knopf „Tempo ändern", keine Gehzeit.
6. **Keine Migration:** Bestandstrips tragen kein Etappen-Tempo, ihre Gehzeiten und Ankünfte bleiben unverändert.

## Source

- **File:** `src/core/naismith.py` (Python), `internal/model/naismith.go` (Go), `frontend/src/lib/utils/naismith.ts` (TypeScript)
- **Identifier:** `stage_speeds(trip, stage)` · `ResolveStageTempo(trip, stage)` · `stageTempo(stage, tripTempo)` (je eine Auflösungsfunktion pro Schicht, neben `tempo_speeds` / `ResolveTempo` / `tripTempo`)

Auflösung je Etappe: Fortbewegung immer vom Trip, Grundtempo = `stage.grundtempo_kmh` falls gültig, sonst `trip.tempo.grundtempo_kmh`. Die drei Funktionen sind Spiegel voneinander und werden durch eine gemeinsame JSON-Falltabelle bewacht.

Schichten: Frontend (`frontend/src`), Go-API (`internal`), Python-Core (`src`). Trip/Orte-Teilung: Ortsvergleiche haben keine Etappen, es gibt kein Compare-Pendant. Die UI nutzt die vorhandene Karte `TempoKarteInhalt` mit einem zusätzlichen Prop (`nurGrundtempo`) wieder, es entsteht keine neue Doppelkomponente (CLAUDE.md, Code-Teilung).

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/trip.py` | MODIFY | `Stage.grundtempo_kmh: Optional[float] = None` |
| `src/app/loader.py` | MODIFY | Parse (ungültig ⇒ ignorieren), Serialize nur wenn gesetzt, Compute-on-Save je Etappe mit `stage_speeds` |
| `src/core/naismith.py` | MODIFY | neu `stage_speeds(trip, stage)` |
| `src/services/trip_segments.py` | MODIFY | Self-Heal mit `stage_speeds` statt `tempo_speeds` |
| `internal/model/trip.go` | MODIFY | Go-`Stage`: `GrundtempoKmh *float64 json:"grundtempo_kmh,omitempty"` |
| `internal/model/naismith.go` | MODIFY | neu `ResolveStageTempo(trip, stage)` |
| `internal/store/trip.go` | MODIFY | `SaveTrip` löst Tempo je Etappe auf, bevor `ComputeStageArrivals` rechnet |
| `internal/handler/trip.go` | MODIFY | Validierung 0,5 bis 60 je Etappe beim Etappen-PUT, sonst 422; Merge-Verhalten wie `tempo` |
| `frontend/src/lib/types.ts` | MODIFY | `Stage.grundtempo_kmh?: number` |
| `frontend/src/lib/utils/naismith.ts` | MODIFY | neu `stageTempo(stage, tripTempo)` |
| `frontend/src/lib/components/edit/etappenListe.ts` | MODIFY | Gehzeit mit Etappen-Tempo, Kennzeichnung „eigenes Tempo" |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY | Knopf „Tempo ändern", Grundtempo-Feld und „Trip-Tempo verwenden", Live-Ankünfte, Fortbewegungswechsel verwirft Überschreibungen mit Hinweis |
| `frontend/src/lib/components/organisms/tempo-karte/TempoKarteInhalt.svelte` | MODIFY | Prop `nurGrundtempo` (Fortbewegung ausgeblendet) |
| `frontend/src/lib/components/mobile/StageCardM.svelte` | MODIFY | Gehzeit mit Etappen-Tempo |
| `frontend/src/lib/i18n/messages/{de,en}/trip.json` | MODIFY | Texte: Tempo je Etappe überschreibbar, „Trip-Tempo verwenden", Hinweis zurückgesetzter Etappen |
| `tests/fixtures/trip_schema_full.json`, `tests/test_trip_schema_drift.py`, `internal/model/trip_schema_drift_test.go` | MODIFY | Drift-Gates um das Etappen-Feld |
| `tests/fixtures/naismith_dav_paritaet.json` | MODIFY | Fälle mit Etappen-Überschreibung (1 von 2 Etappen) |
| `frontend/src/lib/components/trip-detail/__tests__/tempo_karte_3196.test.ts` | MODIFY | prüft heute „kein überschreibbar" bis #3197; auf neuen Text anpassen |
| `frontend/src/lib/components/molecules/__tests__/listenzeile_3007.test.ts` | MODIFY | prüft heute „kein Tempo ändern"; anpassen |
| `docs/reference/api_contract.md` | MODIFY | Etappen-Feld `grundtempo_kmh` dokumentieren |
| Neue Tests (Python, Go, `node --test`) | CREATE | siehe Test Plan |

Nicht betroffen: Ortsvergleich, `compute_stage_arrivals` / `ComputeStageArrivals` / `computeArrivalTimes` selbst (sie erhalten fertige Raten), `stage_weather.py` (der Scoped-Trip trägt die Etappe samt Feld), `scripts/migrate_3196_trip_tempo.py`.

### Estimated Scope

- **Files:** ca. 15 bis 18
- **LoC:** ca. +500 / -30 (Python ~60, Go ~50, Frontend ~150, Tests ~250)
- **Effort:** medium, **Risiko MEDIUM** (dreifach gespiegelte Rechnung; Datenverlust, wenn das Feld in einer Schicht fehlt)
- Ein Durchlauf, ein Deploy (Backend ohne UI hat keinen Nutzen). Scope für den Deploy: full-stack.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #3196 (`Trip.tempo`, DAV-Rechnung) | issue/feature | Voraussetzung, ausgeliefert |
| ADR-0108 | adr | Override je Etappe nur Grundtempo |
| ADR-0095 | adr | Kanal-Parität, gleiche bewertete Stunden in allen vier Kanälen |
| ADR-0101 | adr | Read-Modify-Write mit Merge |
| `internal/store/trip.go` `SaveTrip` | go | speichert `arrival_calculated` zentral |
| `src/app/loader.py` (`_write_trip_locked`), `src/services/trip_segments.py` | python | Compute-on-Save und Self-Heal |
| Risk Engine, Renderer (E-Mail, Telegram, SMS, Premium-SMS) | python | lesen `arrival_calculated` (bewertete Stunden je Wegpunkt) |
| `TempoKarteInhalt.svelte` | frontend | wiederverwendet mit Prop `nurGrundtempo` |
| `tests/fixtures/naismith_dav_paritaet.json` | testdaten | gemeinsame Falltabelle Go/Python/TS |

## Implementation Details

### Datenfluss

Die Kanäle lesen die persistierten `arrival_calculated` der Wegpunkte. Die Wirkung des Etappen-Tempos entsteht deshalb **beim Speichern**:

- Go: `SaveTrip` löst je Etappe `ResolveStageTempo(trip, stage)` auf und ruft damit `ComputeStageArrivals`. Bisher wurde einmal vor der Schleife aufgelöst; jetzt je Etappe.
- Python: Compute-on-Save im Loader (`_write_trip_locked`) analog mit `stage_speeds`.
- Self-Heal (`trip_segments.py`) heilt nur bei komplett leeren Ankünften und nutzt ebenfalls `stage_speeds`; Bestandstrips ohne Überschreibung bleiben unberührt.
- Go und Python müssen für dieselbe Eingabe dieselben Minuten liefern (Falltabelle).

### Persistenz und RMW

Das Feld steht je Etappe im Trip. Go-`Stage` hat kein Catch-all, das Feld muss daher in allen drei Schichten existieren, sonst geht es beim Round-Trip verloren. Beim Etappen-PUT gilt Read-Modify-Write mit Merge: bestehende Etappenfelder bleiben, nur gelieferte Felder werden überschrieben; `grundtempo_kmh` wird beim Serialisieren weggelassen, wenn nicht gesetzt (omitempty / nur wenn nicht None). Das Zurücknehmen der Überschreibung entfernt das Feld.

### Validierung

- API: Wert außerhalb 0,5 bis 60 oder kein Zahlenwert ⇒ HTTP 422, nichts wird gespeichert.
- Laden: ungültiger gespeicherter Wert wird ignoriert (Trip-Tempo gilt), analog `valid_tempo`; die Datei wird dabei nicht umgeschrieben.

### Oberfläche

- Etappenzeile: „Gehzeit h:mm" (existiert in `etappenListe.ts`, nutzt künftig das Etappen-Tempo) und Knopf „Tempo ändern" (i18n-Schlüssel `trip.hub.tempo_aendern` ist vorhanden). Eine Etappe mit eigenem Tempo ist gekennzeichnet.
- Klick auf „Tempo ändern" öffnet `TempoKarteInhalt` mit `nurGrundtempo`: ein Zahlenfeld Grundtempo und die Aktion „Trip-Tempo verwenden" (entfernt die Überschreibung).
- Live-Ankünfte im Editor rechnen mit `stageTempo`.
- Der Wechsel der Trip-Fortbewegung (`tempoAendern` in `EditStagesPanelNew.svelte`) entfernt alle `grundtempo_kmh` der Etappen und zeigt einen Hinweis mit der Zahl der zurückgesetzten Etappen (nur wenn mindestens eine betroffen war).
- Pausentag (keine Wegpunkte): weder Knopf noch Gehzeit.
- Texte nur über den Katalog (DE/EN); Hinweis zur Etappenzahl mit Pluralform; Protokoll-Token bleiben unübersetzt.
- Mobil (`StageCardM`) zeigt die Gehzeit mit Etappen-Tempo.

## Test Plan

### Automated Tests (TDD RED, Kern-Schicht ohne Mock-Theater)

- [ ] Parität: Falltabelle mit Überschreibung auf 1 von 2 Etappen; Go (`ResolveStageTempo`, `ComputeStageArrivals`), Python (`stage_speeds`) und TS (`stageTempo`, `computeArrivalTimes`) liefern dieselben Minuten; die nicht überschriebene Etappe entspricht dem Trip-Tempo
- [ ] Python/Go: ungültiger Wert (0, 0,4, 61, negativ, kein Zahlwert) beim Laden ignoriert ⇒ Trip-Tempo
- [ ] Go-Handler: Etappen-PUT mit `grundtempo_kmh` außerhalb 0,5 bis 60 ⇒ 422, Datei unverändert
- [ ] PUT→GET-Roundtrip mit **zwei Nutzern**: Nutzer A setzt Etappen-Tempo, GET liefert Wert und neu berechnete `arrival_calculated` nur für die Etappe; Nutzer B sieht seinen Trip unverändert; alle übrigen Etappen- und Trip-Felder bleiben (RMW-Merge); Zurücknehmen entfernt das Feld
- [ ] Python-Roundtrip: Loader liest und schreibt Trip mit Etappen-Tempo ohne Feldverlust (Python-Schreibpfad)
- [ ] Drift-Gates: `tests/test_trip_schema_drift.py` und `trip_schema_drift_test.go` kennen das Etappen-Feld (Fixture `trip_schema_full.json`)
- [ ] Kanal-Parität: Trip mit Überschreibung auf Etappe 3; für E-Mail, Telegram, SMS, Premium-SMS sind die bewerteten Stunden der Wegpunkte von Etappe 3 gegenüber dem Lauf ohne Überschreibung geändert, in allen vier Kanälen gleich; Wegpunkte der anderen Etappen identisch
- [ ] Bestand: Trip ohne Überschreibung liefert byte-gleiche Ankunftszeiten wie vor der Änderung
- [ ] Frontend (`node --test`): `stageTempo`, `etappenZeile` (Gehzeit, Kennzeichnung), Pausentag ohne Knopf und ohne Gehzeit, Fortbewegungswechsel verwirft Überschreibungen und zählt sie, „Trip-Tempo verwenden" entfernt das Feld
- [ ] Frontend: Katalog-Vollständigkeit DE/EN für alle neuen Schlüssel
- [ ] Alt-Tests angepasst: `tempo_karte_3196.test.ts`, `listenzeile_3007.test.ts`

### E2E gegen Staging (`/e2e-verify`)

- [ ] Etappe 3 auf 3 km/h setzen, speichern, neu laden: Wert und Gehzeit bleiben, andere Etappen unverändert
- [ ] Trip-Briefing: Wegpunkte von Etappe 3 mit geänderten Stunden, übrige gleich
- [ ] „Trip-Tempo verwenden" und Fortbewegungswechsel mit Hinweis
- [ ] Sprache EN

## Definition of Done

Fertig ist #3197, wenn jede Etappe mit Wegpunkten im Reiter Etappen (Desktop und mobil) ihre Gehzeit zeigt und per „Tempo ändern" ein eigenes Grundtempo bekommen und wieder zurücknehmen kann, das Feld in allen drei Schichten (Go, Python, Frontend) ohne Datenverlust gespeichert und gelesen wird (Drift-Gates grün), die drei Rechner mit Überschreibung dieselben Gehzeiten liefern (Paritätstabelle grün), nur die Wegpunkte der überschriebenen Etappe in allen vier Kanälen geänderte Stunden zeigen, Bestandstrips ohne Überschreibung unverändert rechnen, Texte DE und EN aus dem Katalog kommen, die Staging-Prüfung (Zwei-Nutzer-Trennung, Etappe-3-Szenario, Briefing) bestanden ist und Henning ein Soll/Ist-Bild des Reiters Etappen mit einer überschriebenen Etappe bekommen hat.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Trip-Tempo (zu Fuß, 4 km/h) und mehreren Etappen mit Wegpunkten / When der Nutzer den Reiter Etappen öffnet / Then zeigt jede Etappenzeile „Gehzeit h:mm" und den Knopf „Tempo ändern", und die Gehzeit entspricht dem Trip-Tempo, solange keine Etappe überschrieben wurde.
  - Test: E2E gegen Staging: Zeile lesen, Gehzeit gegen die Falltabelle prüfen; Frontend-Test von `etappenZeile`.

- **AC-2:** Given ein Trip mit mehreren Etappen / When der Nutzer bei Etappe 3 über „Tempo ändern" das Grundtempo auf 3 km/h setzt / Then ändern sich nur die Gehzeit von Etappe 3 und die bewerteten Stunden ihrer Wegpunkte (flach wie Aufstieg, weil die Steigraten mit dem Grundtempo skalieren); Gehzeiten, Ankünfte und bewertete Stunden aller anderen Etappen bleiben unverändert.
  - Test: Paritäts-Falltabelle (Überschreibung auf 1 von 2 Etappen) in Go, Python und TS; E2E liest Gehzeiten aller Etappen vor und nach dem Setzen.

- **AC-3:** Given Etappe 3 hat ein eigenes Tempo / When ein Briefing erzeugt wird / Then zeigen E-Mail, Telegram, SMS und Premium-SMS für die Wegpunkte von Etappe 3 dieselben geänderten bewerteten Stunden, und die Wegpunkte der übrigen Etappen sind in allen vier Kanälen unverändert (ADR-0095).
  - Test: Kanal-Paritäts-Test über die vier Renderer; E2E gegen Staging mit zugestellter Trip-Briefing-Mail.

- **AC-4:** Given Etappe 3 hat ein eigenes Tempo / When der Nutzer „Trip-Tempo verwenden" wählt und speichert / Then folgt Etappe 3 wieder dem Trip-Tempo, ihre Gehzeit und die bewerteten Stunden entsprechen wieder den Werten ohne Überschreibung, und das gespeicherte Feld ist entfernt.
  - Test: Roundtrip-Test PUT→GET (Feld fehlt danach) und Frontend-Test; E2E mit Sichtprüfung der Gehzeit.

- **AC-5:** Given Etappe 3 mit eigenem Tempo und weitere Trip-Daten (Empfänger, Metriken, übrige Etappen) / When der Nutzer speichert und die Seite neu lädt / Then zeigt Etappe 3 weiterhin das eigene Tempo und die Gehzeit, und alle übrigen Felder des Trips sind unverändert (Read-Modify-Write über Go-API und Python, kein Datenverlust).
  - Test: PUT→GET-Roundtrip mit zwei Nutzern (Nutzer B bleibt unverändert, nie Kennung „default"), Python-Roundtrip über den Loader, Drift-Gates in Go und Python.

- **AC-6:** Given ein Trip mit Etappen-Überschreibungen / When der Nutzer die Fortbewegung des Trips wechselt (zum Beispiel von zu Fuß auf Rad) / Then werden alle Etappen-Überschreibungen verworfen, jede Etappe folgt dem neuen Trip-Tempo, und ein Hinweis nennt, wie viele Etappen zurückgesetzt wurden (kein Hinweis, wenn keine betroffen war).
  - Test: Frontend-Komponententest mit zwei überschriebenen Etappen (Hinweis „2 Etappen"); E2E mit Sichtprüfung.

- **AC-7:** Given ein Pausentag, also eine Etappe ohne Wegpunkte / When der Nutzer den Reiter Etappen ansieht / Then zeigt diese Zeile weder „Gehzeit" noch den Knopf „Tempo ändern".
  - Test: Frontend-Test von `etappenZeile`; E2E mit Trip, der einen Pausentag enthält.

- **AC-8:** Given ein Etappen-Tempo außerhalb von 0,5 bis 60 km/h oder kein Zahlenwert / When es per API gespeichert wird / Then antwortet die API mit 422 und speichert nichts; Given ein solcher Wert steht bereits in einer gespeicherten Datei / When der Trip geladen wird / Then wird er ignoriert und die Etappe folgt dem Trip-Tempo.
  - Test: Go-Handler-Test (422, Datei unverändert); Python- und Go-Ladetest mit ungültigem Wert.

- **AC-9:** Given ein Bestandstrip ohne Etappen-Überschreibung / When er nach der Auslieferung geladen, gespeichert und als Briefing erzeugt wird / Then sind Gehzeiten, Ankunftszeiten und bewertete Stunden identisch zu vorher, und es ist keine Migration nötig.
  - Test: Kern-Test mit Bestands-Fixture (Ankünfte vor und nach identisch); E2E mit Bestandstrip auf Staging.

- **AC-10:** Given die Oberfläche steht auf Englisch bzw. Deutsch / When der Nutzer den Reiter Etappen öffnet und „Tempo ändern" wählt / Then erscheinen Knopf, Feldbezeichnung, „Trip-Tempo verwenden" und der Hinweis zu zurückgesetzten Etappen in der jeweiligen Sprache aus dem Katalog; Protokoll-Kürzel bleiben unübersetzt.
  - Test: Katalog-Vollständigkeits-Test DE/EN; E2E in beiden Sprachen.

## Known Limitations

- Je Etappe ist nur das Grundtempo überschreibbar; Fortbewegung und ein getrenntes Aufstiegstempo je Etappe gibt es nicht (ADR-0108).
- Der Wert ist absolut: Ändert der Nutzer später das Trip-Tempo, bleibt ein Etappen-Tempo wie gesetzt. Der Wechsel der Fortbewegung setzt es dagegen zurück (AC-6).
- Ruhetage werden nur als Pausentag (Etappe ohne Wegpunkte) behandelt; ein Tempo für eine Etappe mit Wegpunkten, aber ohne Gehzeit, gibt es nicht.
- Die Rechnung ist in Go, Python und TS gespiegelt; Gleichheit sichert nur die gemeinsame Falltabelle.
- Der Hook `data_schema_backup.py` löst bei Änderungen an `trip.py`, `loader.py` und `internal/model/*.go` eine Sicherung aus.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0108 (keine Änderung nötig)
- **Rationale:** ADR-0108 sieht den Override je Etappe nur für das Grundtempo vor; diese Spec setzt genau das um. Auch das Verwerfen der Überschreibungen beim Wechsel der Fortbewegung folgt aus dem ADR (Fortbewegung bleibt trip-weit). Kein neues ADR.

## Changelog

- 2026-11-20: Initial spec created (v1.0, draft, wartet auf PO-Freigabe der ACs)
