---
entity_id: compare_summary_trip_ids_from_catalog
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: fix-2992-trip-metrik-zuordnung
tags: [compare, summary, metric-ids, "#2992", "#1986"]
---

# Eine Metrik-ID-Zuordnung fuer Trip- und Vergleichsmail (#2992)

## Approval

- [ ] Approved

## Purpose

Die Zuordnung "Vergleichs-Zeile (Renderer-ID) -> Trip-Metrik-ID" fuer den Zusammenfassungssatz der Vergleichsmail steht heute zweimal von Hand getippt: in `RENDERER_TO_TRIP_METRIC_ID` und im Vergleichs-Katalog. Die Spec fuehrt beides zu einem Baustein zusammen (Ableitung aus dem Katalog); das Produktverhalten bleibt unveraendert.

## Source

- **File:** `src/output/renderers/compare_metric_ids.py`
- **Identifier:** `RENDERER_TO_TRIP_METRIC_ID` (entfaellt), neu `SUMMARY_SENTENCE_RENDERER_IDS` und `renderer_to_trip_metric_id()`

> **Schicht:** Python-Core (`src/output/renderers/`), Renderer der Vergleichsmail. Kein Frontend, keine Go-API.
>
> **Trip/Ortsvergleich-Teilung:** Der Satz-Baustein `format_location_summary` ist bereits gemeinsam (`context="vergleich"`); es entsteht keine neue Komponente mit Pendant.
>
> **Mandantentrennung:** Keine Nutzerdaten betroffen (reine Renderer-Konstante).
>
> **Kanaele:** Betrifft den Fliesstext-Satz der Vergleichsmail in allen Kanaelen, die ihn zeigen (E-Mail, Telegram, SMS, Premium-SMS) — gleicher Inhalt, kein Format-Unterschied zu vorher.

## Estimated Scope

- **LoC:** ~60-80 (davon ~45 Test)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `COMPARE_METRIC_CATALOG` (`compare_metric_catalog.py`) | module | traegt je Eintrag `metric_id` (= Trip-ID) und `aggregation`; einzige Quelle der Trip-ID |
| `FRONTEND_TO_RENDERER_METRIC_ID` (`compare_metric_ids.py`) | constant | Verbindung Frontend-Schluessel -> Renderer-ID |
| `katalog_paar()` / `_katalog_paare()` (`compare_metric_ids.py`) | function | vorhandener Ableitungsweg (#3101), liefert `(metric_id, aggregation)` |
| `format_location_summary` (`compact_summary.py`) | function | einziger Verbraucher, baut den Vergleichs-Fliesstext |
| Metrik-Listen-Ratsche (`tests/helpers/metrik_listen_scan.py`) | test helper | registriert die entfallende Liste; Eintrag wird entfernt |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/compare_metric_ids.py` | MODIFY | Getippte Tabelle entfernen; Tupel `SUMMARY_SENTENCE_RENDERER_IDS` (sechs Renderer-IDs in Satz-Reihenfolge) und `renderer_to_trip_metric_id()` ueber `katalog_paar()` (lazy import wegen Zyklus) |
| `src/output/renderers/compact_summary.py` | MODIFY | `format_location_summary` nutzt die Funktion statt der Konstante; Docstring nachziehen |
| `tests/helpers/metrik_listen_scan.py` | MODIFY | Registrierung von `RENDERER_TO_TRIP_METRIC_ID` entfernen (Kommentar #2992); keine neue Register-Liste |
| `tests/unit/test_compare_summary_trip_ids_from_catalog.py` | CREATE | Verhaltens-Tests mit echten `LocationResult`/`ForecastDataPoint`-Fixtures |

## Implementation Details

- Auswahl und Reihenfolge der sechs Renderer-IDs (`temp_max`, `cloud_avg`, `precip_sum`, `pop_max`, `wind_max`, `thunder_max`) bleibt eine eigene Festlegung (nur Groessen mit `_format_*`-Zweig, Satz-Reihenfolge) und ist keine Doppelung.
- Die Trip-ID je Eintrag wird nicht mehr getippt, sondern ueber `katalog_paar(renderer_id)[0]` aus dem Katalog gelesen (Muster #3101, lazy import in einer Funktion wegen Import-Zyklus `compare_metric_catalog` <-> `compare_metric_ids`).
- Fehlt fuer eine Satz-Renderer-ID das Katalog-Paar, wirft `renderer_to_trip_metric_id()` einen `ValueError`, der die Renderer-ID nennt. Kein stilles Entfallen.
- Der Filter im Satz bleibt auf der Renderer-ID. Ein Filter ueber die Trip-ID waere falsch: `temp_min` hat ebenfalls `metric_id=temperature` und wuerde allein den Temperatur-Satzteil einschalten.
- Kein Alias `RENDERER_TO_TRIP_METRIC_ID`, damit keine zweite Quelle bleibt.
- Mail-Inhaltspfad: Renderer-Commit-Gate (Modus-Matrix-Test + Validator) greift beim Commit.

## Expected Behavior

- **Input:** Auswahl der Vergleichs-Zeilen (auch `None` = alles) und `LocationResult`-Daten.
- **Output:** Fliesstext-Satz der Vergleichsmail, byte-gleich zum Stand vor der Aenderung.
- **Side effects:** Keine. Konstante `RENDERER_TO_TRIP_METRIC_ID` entfaellt, Ratschen-Registrierung entfaellt.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Katalog WHEN `renderer_to_trip_metric_id()` THEN je Satz-Renderer-ID gleich `katalog_paar(rid)[0]` (sechs Paare).
- [ ] Test 2: GIVEN Auswahl `None`, nur Temperatur+Wind, sowie plus Regen/Gewitter WHEN Satz gebaut THEN Inhalt und Reihenfolge gleich wie im Referenztext vor der Aenderung.
- [ ] Test 3: GIVEN nur `temp_min` gewaehlt WHEN Satz gebaut THEN kein Temperatur-Satzteil.
- [ ] Test 4: GIVEN Satz-Renderer-ID ohne Katalog-Paar WHEN Zuordnung gebaut THEN `ValueError` mit der Renderer-ID im Text.
- [ ] Test 5: Metrik-Listen-Ratsche (bestehender Test) bleibt gruen.

## Acceptance Criteria

- **AC-1:** Given der Vergleichs-Katalog traegt je Eintrag eine Trip-Metrik-ID / When die Zuordnung Vergleichs-Zeile -> Trip-Groesse fuer den Zusammenfassungssatz gebraucht wird / Then wird sie aus dem Vergleichs-Katalog abgeleitet und die getippte Trip-ID-Tabelle `RENDERER_TO_TRIP_METRIC_ID` existiert nicht mehr.
  - Test: Zuordnung je Satz-Zeile ist gleich der Katalog-Trip-ID; die Konstante ist nicht mehr importierbar.

- **AC-2:** Given eine Vergleichsmail mit Auswahl `None` (alles), nur Temperatur+Wind oder zusaetzlich Regen und Gewitter / When der Fliesstext-Satz gebaut wird / Then sind Inhalt und Reihenfolge der Satzteile identisch zum Stand vor der Aenderung.
  - Test: Satz fuer die drei Auswahlen mit echten `LocationResult`/`ForecastDataPoint`-Fixtures gegen den vorher erfassten Referenztext.

- **AC-3:** Given ausschliesslich die Zeile `temp_min` ist gewaehlt / When der Fliesstext-Satz gebaut wird / Then wird der Temperatur-Satzteil NICHT eingeschaltet, weil der Filter auf der Renderer-ID bleibt und nicht auf der gemeinsamen Trip-ID `temperature`.
  - Test: Satz mit nur `temp_min` enthaelt keinen Temperaturteil.

- **AC-4:** Given eine Satz-Renderer-ID hat kein Katalog-Paar / When die Zuordnung abgeleitet wird / Then bricht sie laut mit einem Fehler ab, der die Renderer-ID nennt, statt den Satzteil still entfallen zu lassen.
  - Test: Aufruf mit einer ID ohne Katalog-Paar wirft `ValueError` mit dem Namen.

- **AC-5:** Given die Metrik-Listen-Ratsche prueft alle Register-Listen / When die Registrierung der entfallenen Liste entfernt ist / Then bleibt die Ratsche gruen und es gibt keine unregistrierte neue Register-Liste.
  - Test: bestehender Ratschen-Test laeuft gruen; das neue Tupel enthaelt Renderer-IDs, keine Register-Kennungen.

## Definition of Done

- Die Trip-Groesse je Satz-Zeile steht nur noch im Vergleichs-Katalog; die getippte Tabelle ist entfernt.
- Der Zusammenfassungssatz der Vergleichsmail ist fuer alle geprueften Auswahlen wortgleich zum Stand vorher.
- Eine Satz-Zeile ohne Katalog-Eintrag faellt laut mit Namen auf statt still zu fehlen.
- Alle fuenf Acceptance Criteria durch Tests belegt; Metrik-Listen-Ratsche und bestehende Satz-Tests gruen.

## Known Limitations

- Der in #1986 genannte Paritaetstest (`tests/unit/test_compare_metric_parity.py:232`) bewacht diese Zuordnung nicht (er prueft Matrix-Zeilen, #1324) und bleibt unveraendert; der neue Wachtest dieser Spec schliesst die Luecke.
- Auswahl und Reihenfolge der sechs Satz-Renderer-IDs bleiben bewusst eigenstaendig festgelegt.
- Kein Produktverhalten aendert sich.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Entdoppelung innerhalb eines Moduls nach bestehendem Muster (#3101); keine Entscheidungsflaeche (Kanaele, Provider, Datenmodell, Auth) beruehrt.

## Changelog

- 2026-11-26: Initial spec created (Issue #2992)
