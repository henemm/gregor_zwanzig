---
entity_id: refactor_2989_compare_default_order_ssot
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: refactor-2989-compare-keys-ssot
tags: [compare, katalog, ssot, refactor, "#2989", "#1986"]
---

# Ortsvergleich: Standardliste der Wettergroessen aus dem Backend-Katalog (#2989)

## Approval

- [ ] Approved

## Purpose

Die Frontend-Liste `COMPARE_METRIC_KEYS` ist eine handgepflegte Kopie der Ortsvergleich-Katalog-Schluessel und traegt zwei Bedeutungen: die Menge „nie eingestellt = alle Groessen" und die Mail-Standardreihenfolge (`CV2_ZEILEN`). Dieses Refactoring macht den Backend-Katalog zur einzigen Quelle: der Endpoint liefert die Standardfolge als `default_order` mit, das Frontend liest sie von dort, die Kopie entfaellt (PO-Auftrag #1986 NEU-8: kein doppelter Code fuer dieselbe Aufgabe). Fuer Nutzer aendert sich nichts Sichtbares.

## Source

- **File:** `src/output/renderers/compare_metric_catalog.py` (Backend-Ableitung), `api/routers/compare.py` (Endpoint), `frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts` (Frontend-Speicher)
- **Identifier:** `default_order()` (neu), `GET /api/compare/metrics`, `getCompareDefaultOrder()` (neu); geloescht: `COMPARE_METRIC_KEYS`

Schicht-Zuordnung: Python-Core (`src/output/renderers/`, `api/routers/`) und Frontend (`frontend/src/lib/components/shared/`). Der Go-Proxy (`internal/router/router.go`) reicht die Antwort unveraendert durch und bleibt unberuehrt.

Querschnitts-Pruefpunkte:

- **Trip/Ortsvergleich-Teilung:** Keine neue Komponente. Es werden ausschliesslich bestehende Bausteine unter `shared/` angepasst; kein Pendant-Verstoss (#1170).
- **Mandantentrennung:** Der Endpoint liefert einen statischen Katalog ohne Nutzerdaten. Daher kein Zwei-Nutzer-Test noetig; es wird keine `user_id` gelesen oder geschrieben.
- **Kanaele:** E-Mail, Telegram, SMS und Premium-SMS aendern sich nicht. Weder Briefing- noch Alarm-Inhalt noch die Mail-Reihenfolge werden veraendert (Reihenfolge-Erhalt ist AC-4).

## Scope

**Drin:** Standardfolge `default_order` im Katalog-Endpoint; Frontend liest Menge und Reihenfolge fuer „nie eingestellt" daraus; Speicherschutz bei ungeladener Folge; Loeschung von `COMPARE_METRIC_KEYS` samt Frontend-Paritaetstest; Migration der Bestandstests.

**Nicht drin:** Aenderung der Reihenfolge des Feldes `metrics`; Aenderungen an Mail-, Telegram-, SMS- oder Premium-SMS-Ausgabe; Trip-Pfad; weitere Doppelungen aus #1986.

## Estimated Scope

- **LoC:** ca. +/-250 gesamt (Produktion plus Tests)
- **Files:** 6 Produktionsdateien (davon eine nur Loeschung einer Konstante) plus Testanpassungen
- **Effort:** medium

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/compare_metric_catalog.py` | MODIFY | `default_order()` aus `CV2_ZEILEN` (ohne `warn`) ueber `key_for(metric_id, aggregation)`, fail-fast gegen waehlbare Katalog-Schluessel |
| `api/routers/compare.py` | MODIFY | Antwort additiv um `default_order` erweitern |
| `frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts` | MODIFY | Typ und modulweiter Speicher fuer `default_order`, `getCompareDefaultOrder(): string[] \| null` |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricOrder.ts` | MODIFY | `materializeActiveMetricKeys(null)` liest den Speicher statt der Kopie |
| `frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts` | MODIFY | `bisherigeZeilen` rangiert ueber den Speicher; Speicherpfad schreibt `active_metrics` nicht, solange die Standardfolge fehlt |
| `frontend/src/lib/components/shared/wetter-tab/corridorEditorState.ts` | MODIFY | `COMPARE_METRIC_KEYS` loeschen |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/compareMetricKeysParity.test.ts` | DELETE | Ersetzt durch Backend-Waechter |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/corridorEditorCapeExclusion.test.ts`, `corridorEditorState.test.ts`, `frontend/src/lib/components/shared/__tests__/compareMetricOrder.test.ts`, `frontend/src/lib/components/compare/__tests__/fix_3061_hub_hydrierer.test.ts` | MODIFY | Seed aus Antwortobjekt statt Import der Konstante |
| `tests/tdd/test_2989_compare_default_order.py` | CREATE | Backend-Waechter gegen echten Katalog |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CV2_ZEILEN` (`src/output/renderers/email/compare_html.py`) | Konstante | SSOT der Mail-Standardfolge (#1356) |
| `compare_metric_ids.py` (`FRONTEND_TO_RENDERER_METRIC_ID`, `key_for`) | Modul | Uebersetzung Renderer-ID zu Katalog-Schluessel |
| `get_compare_metric_catalog()` | Funktion | Menge der waehlbaren Katalog-Schluessel |
| `_sort_by_cv2_order` | Funktion | Vorbild fuer fail-fast bei Abweichung |
| `compareMetricCatalogLoader.ts` (Promise-Cache) | Modul | Laedt `GET /api/compare/metrics`, je Sprache |
| `compareHubHydration.ts` | Modul | Wartet den Katalog vor dem Dirty-Check-Grundzustand ab (#1373 F001) |
| Go-Proxy `internal/router/router.go` | Proxy | Reicht die Antwort unveraendert durch |
| Spec `compare_metric_default_order_ssot.md`, `compare_metric_order.md` | Spec | Reihenfolge-SSOT (#1356, #1359) |

## Implementation Details

Backend:

1. `default_order()` in `compare_metric_catalog.py` leitet die Folge aus `CV2_ZEILEN` ab (ohne `warn`), uebersetzt jede Zeile ueber `key_for(metric_id, aggregation)` zu einem Katalog-Schluessel.
2. Fail-fast wie bei `_sort_by_cv2_order`: weicht die Menge der abgeleiteten Schluessel von der Menge der waehlbaren Katalog-Schluessel ab (fehlender oder zusaetzlicher Schluessel), wird ein Fehler geworfen.
3. `GET /api/compare/metrics` liefert `{"metrics": [...], "default_order": [...]}`. Das Feld `metrics` und seine Reihenfolge bleiben unveraendert (die Auswahlliste zeigt weiter die Katalogfolge; Variante C verworfen).

Frontend:

4. Lader: modulweiter Speicher fuer `default_order`, im geteilten Promise-Chain befuellt (sprachunabhaengig, erste Antwort fuellt). Zugriff ueber `getCompareDefaultOrder()`, `null` solange nicht geladen.
5. `materializeActiveMetricKeys(null)`: geladen gibt eine Kopie der Standardfolge zurueck; ungeladen gibt `[]` nur fuer reine Anzeige-Ableitungen zurueck (die Aufrufer `AlarmeTab`, `CompareTabs`, `anlegeVorbelegung` sind je Aufrufer geprueft und ohne Katalog harmlos).
6. Speicherpfad (`vergleichSpeicherPayload`): ist die Standardfolge ungeladen und `active_metrics` nie gesetzt, wird `active_metrics` nicht geschrieben. `[]` bedeutet „bewusst leer" und wuerde alle Mail-Zeilen abwaehlen (Datenverlust-Klasse #102).
7. `bisherigeZeilen` (`ampelSchreiben.ts`) rangiert Alt-Schluessel ueber `default_order`, damit die Mail-Reihenfolge eines Altvergleichs nach dem ersten Speichern erhalten bleibt.
8. `COMPARE_METRIC_KEYS` und der Frontend-Paritaetstest werden geloescht; der Backend-Waechter (fail-fast plus Python-Test) ersetzt ihn.

## Expected Behavior

- **Input:** `GET /api/compare/metrics` (Sprache wie bisher); im Frontend ein Ortsvergleich mit `active_metrics === null` oder mit gespeicherter Auswahl.
- **Output:** Antwort mit `metrics` (unveraendert) und neuem `default_order`; Frontend zeigt dieselbe Menge in derselben Reihenfolge wie bisher.
- **Side effects:** Keine. Keine Datenmigration, keine neuen Permissions oder AppStorage-Keys, keine Aenderung an Kanal-Ausgaben.

## Test Plan

### Automated Tests (TDD RED)

Python (echter Katalog, keine Mocks), neue Testdatei `tests/tdd/test_2989_compare_default_order.py` (ergaenzt, nicht ersetzt, `tests/unit/test_compare_metric_default_order_ssot.py`, das nur die Klartext-Folge im Renderer prueft):

- [ ] Test 1: GIVEN der echte Katalog / WHEN `default_order()` aufgerufen wird / THEN entspricht die Folge `CV2_ZEILEN` ohne `warn`, uebersetzt in Katalog-Schluessel.
- [ ] Test 2: GIVEN der echte Katalog / WHEN `default_order()` mit der Menge der waehlbaren Katalog-Schluessel verglichen wird / THEN sind beide Mengen gleich und ohne Duplikate (Backend-Waechter, ersetzt Frontend-Paritaetstest).
- [ ] Test 3: GIVEN ein Aufruf des Endpoints `GET /api/compare/metrics` ueber den FastAPI-TestClient / WHEN die Antwort gelesen wird / THEN enthaelt sie `default_order` und `metrics` in der bisherigen Reihenfolge.
- [ ] Test 4: GIVEN eine kuenstlich abweichende Menge (Zeile in `CV2_ZEILEN` ohne Katalog-Schluessel, ueber Parameter der Ableitungsfunktion injiziert, keine Mocks) / WHEN die Ableitung laeuft / THEN bricht sie mit Fehler ab (fail-fast).

Frontend (`node:test`, echte Lader-Funktionen, Speicher ueber ein Antwortobjekt befuellt, kein Mock-Theater):

- [ ] Test 5: GIVEN eine Katalog-Antwort mit `default_order` / WHEN der Lader sie verarbeitet / THEN liefert `getCompareDefaultOrder()` genau diese Folge; vor dem Laden `null`.
- [ ] Test 6: GIVEN geladene Standardfolge / WHEN `materializeActiveMetricKeys(null)` laeuft / THEN entspricht das Ergebnis der Folge und ist eine Kopie (Mutation veraendert den Speicher nicht).
- [ ] Test 7: GIVEN ungeladene Standardfolge und nie gesetztes `active_metrics` / WHEN der Speicher-Payload gebaut wird / THEN enthaelt er kein `active_metrics` (nicht `[]`).
- [ ] Test 8: GIVEN ein Altvergleich mit `active_metrics === null` und geladene Standardfolge / WHEN `bisherigeZeilen` die Alt-Schluessel rangiert / THEN entspricht die Reihenfolge der bisherigen CV2-Folge.
- [ ] Test 9: Bestehende Tests (`corridorEditorCapeExclusion`, `corridorEditorState`, `compareMetricOrder`, `fix_3061_hub_hydrierer`) laufen mit Seed aus Antwortobjekt statt Konstante gruen.

Hinweis zu RED: Tests 1 bis 8 schlagen vor der Implementierung fehl (Funktion, Feld bzw. Speicher fehlen).

## Acceptance Criteria

- **AC-1:** Given der Katalog-Endpoint `GET /api/compare/metrics` / When er aufgerufen wird / Then enthaelt die Antwort zusaetzlich `default_order` mit den Katalog-Schluesseln in der Mail-Standardfolge (`CV2_ZEILEN` ohne `warn`), und die Menge entspricht genau den waehlbaren Katalog-Schluesseln.
  - Test: Python-Test gegen den echten Katalog und den echten Endpoint prueft Folge und Menge der Antwort.

- **AC-2:** Given die Standardfolge weicht von den waehlbaren Katalog-Schluesseln ab (fehlender oder zusaetzlicher Schluessel) / When `default_order()` abgeleitet wird / Then bricht die Ableitung sofort mit einem Fehler ab (fail-fast wie bei `_sort_by_cv2_order`), statt eine falsche Folge auszuliefern.
  - Test: Python-Test mit absichtlich abweichender Eingabe erwartet den Fehler.

- **AC-3:** Given der bestehende Endpoint / When die Antwort um `default_order` erweitert ist / Then ist das Feld `metrics` mit Inhalt und Reihenfolge unveraendert, sodass die Auswahlliste im Editor und die Anzeigefolge gleich bleiben.
  - Test: Python-Test vergleicht `metrics` gegen `get_compare_metric_catalog()` in Reihenfolge.

- **AC-4:** Given ein Ortsvergleich ohne gespeicherte Auswahl (`active_metrics` ist null) / When er im Frontend geoeffnet wird / Then zeigt und materialisiert er dieselbe Menge in derselben Reihenfolge wie bisher (Wert identisch zur frueheren `COMPARE_METRIC_KEYS`-Liste), wobei die Quelle jetzt `default_order` aus der Katalog-Antwort ist.
  - Test: Frontend-Test befuellt den Speicher ueber die echte Lader-Funktion aus einem Antwortobjekt und prueft das Ergebnis von `materializeActiveMetricKeys(null)` gegen die erwartete Folge.

- **AC-5:** Given ein nie eingestellter Vergleich und die Standardfolge ist noch nicht geladen / When der Vergleich gespeichert wird / Then wird `active_metrics` nicht als leere Liste geschrieben, sondern bleibt ungesetzt, sodass keine Mail-Zeilen versehentlich abgewaehlt werden (Datenverlust-Schutz).
  - Test: Frontend-Test baut den Speicher-Payload bei leerem Speicher und prueft, dass `active_metrics` fehlt und nicht `[]` ist.

- **AC-6:** Given ein Altvergleich mit bisheriger Mail-Reihenfolge / When er zum ersten Mal gespeichert wird / Then bleibt die Mail-Reihenfolge unveraendert, weil `bisherigeZeilen` die Schluessel ueber `default_order` rangiert.
  - Test: Frontend-Test mit geladener Standardfolge prueft die Reihenfolge der Alt-Schluessel nach `bisherigeZeilen`.

- **AC-7:** Given der Frontend-Code nach dem Refactoring / When nach der Liste der Vergleichs-Schluessel gesucht wird / Then existiert `COMPARE_METRIC_KEYS` nicht mehr und es gibt keine zweite handgepflegte Liste im Frontend; der Frontend-Paritaetstest ist entfallen und der Backend-Waechter aus AC-1/AC-2 ersetzt ihn.
  - Test: `svelte-check` und Frontend-Tests laufen ohne die Konstante gruen; `compareMetricKeysParity.test.ts` ist geloescht (Verhalten ueber AC-4 bis AC-6 bewiesen, kein Dateiinhalt-Check).

## Definition of Done

- AC-1 bis AC-7 durch automatisierte Tests bzw. Loeschnachweis belegt, alle gruen.
- Kern-Testschicht gruen; `svelte-check` ohne neue Fehler; alle 6 CI-Checks gruen.
- Keine Referenz auf `COMPARE_METRIC_KEYS` mehr im Repository (ausser Changelog/Historie in Specs).
- Staging-Verifikation: `GET /api/compare/metrics` liefert `default_order`; Orts-Vergleich-Mail-Validator gruen.

## Known Limitations

- Synchrones Lesen der Standardfolge setzt voraus, dass der Katalog geladen ist. Alle fuenf Aufrufer sind einzeln geprueft: `AlarmeTab` und `CompareTabs` verrechnen mit `catalog ?? []`, `anlegeVorbelegung` bricht im Aufrufer ohne Katalog ab, `wertebereicheVergleichSpeicherung` hat aktuell keinen Produktions-Aufrufer, `ampelSchreiben` bezieht Alt-Schluessel aus dem geladenen Katalog.
- Ein neuer, nicht in `CV2_ZEILEN` enthaltener waehlbarer Katalog-Schluessel faellt beim Backend-Start bzw. im Waechter-Test auf (gewollt, fail-fast).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Konsolidiert eine Doppelung im Sinne bestehender Entscheidungen (CV2-Folge als Reihenfolge-SSOT, #1356) und aendert weder Kanaele, Provider, Datenmodell noch Auth. Variante C (Katalog selbst umsortieren) wurde verworfen, weil sie die Anzeigefolge der Auswahlliste aendern wuerde.

## Changelog

- 2026-11-26: Initial spec created (Variante A aus `docs/context/refactor-2989-compare-keys-ssot.md`)
