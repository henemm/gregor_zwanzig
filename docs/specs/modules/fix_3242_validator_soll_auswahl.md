---
entity_id: fix_3242_validator_soll_auswahl
type: bugfix
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: fix-3242-validator-soll-auswahl
tags: [validator, soll, placements, auswahl, reihenfolge, "#3242", "#3122"]
---

# Validator-Soll (--konfig): Auswahl und Reihenfolge aus placements (Bug #3242)

## Approval

- [ ] Approved

## Purpose

Das Soll der Mail-Validatoren (`--konfig`) leitet Auswahl (welche Größen) und Reihenfolge je Stelle bei vorhandener Tabelle `display_config.placements` noch aus Altfeldern ab, obwohl der Renderer allein die Tabelle verwendet. Wer im Editor Haken oder Reihenfolge ändert, löst damit Fehlalarme bei korrekt gerenderter Mail aus. Das Soll folgt künftig mit Tabelle der Tabelle (Trip: E-Mail und Ausblick; Orte: E-Mail, Stundenverlauf, Ausblick). Voraussetzung für #3237 (Altfelder und Altpfad entfernen); Fortsetzung von #3218 (Darstellung) im Epic #3122.

## Source

- **File:** `.claude/hooks/_soll_aus_konfiguration.py`
- **Identifier:** `_tabellen_folge` (neu), `_trip_email_liste`, `trip_soll`, `_orte_uebersicht`, `_orte_stunden`, Orte-Ausblick; Schalter `_hat_tabelle`

> Schicht: Prüfwerkzeug (`.claude/hooks/`), weder Frontend noch Go-API noch Produktcode. Trip und Orte-Vergleich werden in derselben Datei mit derselben Regel abgedeckt (kein Pendant-Problem). Nutzerdaten werden nur gelesen (JSON); alle vier Kanäle unberührt (nur E-Mail-Prüfung).

## Estimated Scope

- **LoC:** Soll ca. +60/-15, Tests ca. +250, Doku ca. +5
- **Files:** 4 (+ Spec)
- **Effort:** low bis medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.metric_catalog` (`stellen_sperre`, Register) | module | Statisch: Sperre je Stelle, `keine_eigene_spalte` |
| `_DERIVED_METRIC_RULES` (als `_ELTERN`) | register | Eltern-Zeile abgeleiteter Größen |
| `COMPARE_METRIC_CATALOG`, `orte_standardzeilen` (`CV2_ZEILEN`) | register | Orte: Katalog-ID zu Auswertungszeilen, Standard-Grundauswahl |
| `services.placements.read_placements` | module | Nur Lesen der rohen Tabelle (wie `_hat_tabelle`) |
| `briefing_mail_validator.py`, `email_spec_validator.py` | Verbraucher | Lesen das Soll (`--konfig`) |
| `docs/specs/modules/feat_3122_was_steht_wo.md`, ADR-0124 | Spec/ADR | Produktregel der Tabelle |
| `docs/specs/modules/fix_3218_validator_soll_placements.md` | Spec | Vorgänger (Darstellung, `_hat_tabelle`, `_mit_tabelle`) |

## Implementation Details

Statische Nachbildung der Tabellenregel im Soll, alles hinter `_hat_tabelle(dc)`; der Altpfad ohne Tabelle bleibt unverändert bis #3237. Neuer Helfer `_tabellen_folge(dc, grund_ids, stelle, surface)` (ca. 35 Zeilen). Regeln (Spiegel der Produktregel aus ADR-0124 / Spec #3122, aber als unabhängige Zweitregel):

1. **Folge:** Zeilen der Grundauswahl in gespeicherter Folge. Eine abgeleitete Größe, die in der Grundauswahl der Datei steht und keine eigene Zeile hat, folgt direkt hinter ihrer Eltern-Zeile (hinter schon eingefügten Geschwistern) und erbt deren Haken. Restliche Grundauswahl hinten, überall an. Zeilen außerhalb der Grundauswahl bleiben ohne Wirkung. `rows: []` heißt: ganze Grundauswahl, alles an.
2. **Zelle:** Sperre laut `stellen_sperre` entfernt die Größe, außer `keine_eigene_spalte` (Trip-E-Mail, Fenstergrößen): diese bleibt in der Ausgabe. `places[stelle] is False` bedeutet aus, sonst an.
3. **Stundenverlauf/Ausblick** nur, wenn die E-Mail-Zelle strikt an ist; eine gesperrte E-Mail-Zelle (Fenstergrößen) ergibt nie Ausblick oder Stundenverlauf.
4. **Trip:** Grundauswahl ist die bestehende Soll-Grundauswahl je Report (`_an`, `_sortiert`). Die E-Mail-Liste behält ihre Einträge (metric_id, bucket, order); danach wirkt weiter `_mit_tabelle` (Form aus Tabelle, nötig für `_wind_verschmolzen`). Ausblick = Zeilen mit outlook an in Zeilenfolge; `outlook_metrics` ohne Wirkung. Das OB des Ausblicks je Briefing bleibt bei `trip_ausblick_briefings` (#3155).
5. **Orte:** Grundauswahl-Paare aus `active_metrics` (`_uebersicht_paare`). Eine Zeile (Katalog-ID) weitet sich auf ihre Auswertungspaare der Grundauswahl auf (min/max-Doppelzeilen); fehlt ein Paar in der Grundauswahl, entfällt es. Stundenverlauf: hourly an, E-Mail an, keine Sperre `kein_stundenwert`, danach die bestehenden Filter (`_stuendlich`, `HOURLY_MERGE_ONLY`); `hourly_enabled: false` wirkt wie bisher. Ausblick: outlook an in Zeilenfolge, ohne Sperre `kein_tageswert`.
6. **Orte ohne `active_metrics` (nie eingestellt) mit Tabelle:** Grundauswahl = Standardzeilen (`orte_standardzeilen`, dieselbe Quelle `CV2_ZEILEN` wie im Produkt), nicht der feste `_FEST`-Ausblick.

Abgeleitete Größen wirken im Soll weder auf `stunden` noch auf `ueberblick` (kein Stundenwert, nicht in `_PILL_CATALOG_ORDER`), nur auf `darstellung_stunden`-Schlüssel (wie AC-13 aus #3218).

**Spiegel-Verbot:** Das Soll ruft im neuen Pfad weder `resolve_rows`, `resolve_channel_lists`, `placements_view`, `_cell` noch `metrics_at` auf. Begründung: Reihenfolge und Haken sind Prüfgegenstand; mit der Produktfunktion fände der Validator Sortierfehler des Produkts nie. Einzige bestehende Ausnahme bleibt `ausblick_briefings` (#3155, geprüft wird dort nur OB).

## Expected Behavior

- **Input:** Abo-JSON (Trip oder Orte-Vergleich) mit oder ohne `display_config.placements`.
- **Output:** Soll-Struktur; mit Tabelle folgen Auswahl und Reihenfolge (E-Mail, Ausblick, Orte-Stundenverlauf) der Tabelle, ohne Tabelle unverändert den Altfeldern.
- **Side effects:** keine.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | Helfer `_tabellen_folge`; Trip-E-Mail, Trip-Ausblick, Orte-Übersicht, Orte-Stunden, Orte-Ausblick hinter `_hat_tabelle` aus Tabelle |
| `tests/tdd/test_einstellung_gleich_mail_soll_auswahl.py` | CREATE | Neue Tests (rohes JSON rein, Soll von Hand erwartet) |
| `tests/tdd/test_einstellung_gleich_mail_soll_placements.py` | MODIFY (ggf.) | Tests, die neben der Tabelle Altfelder setzen und deren Wirkung erwarten, anpassen |
| `docs/reference/mail_validators.md` | MODIFY | Abschnitt `--konfig`: Restlücke Auswahl/Folge geschlossen |

- In: Auswahl und Reihenfolge mit Tabelle (Trip E-Mail + Ausblick; Orte E-Mail, Stundenverlauf, Ausblick), Ränder, Altpfad unverändert.
- Out: Altfelder/Altpfad entfernen (#3237); Form-Ableitung (schon #3218); OB des Ausblicks im Briefing (#3155).

## Definition of Done

- AC-1 bis AC-14 durch Kern-Tests ohne Mock grün; bestehende Soll-Tests (`tests/tdd/test_einstellung_gleich_mail_*.py`, `tests/test_3047_*`) grün.
- Abnahme auf Staging: Fehlalarm-Fall (Haken/Reihenfolge im Editor geändert) läuft durch den Validator mit `--konfig` ohne SOLL-Verletzung.
- Keine Änderung an Gate-Konfiguration; kein Schritt, der eine Gate-Sperre aufheben muss.

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/tdd/test_einstellung_gleich_mail_soll_auswahl.py`, ohne `Mock`/`patch`; Eingabe ist rohes Abo-JSON, das erwartete Soll steht von Hand im Test und wird nie aus `resolve_*` berechnet.

- [ ] GIVEN Tabelle umsortiert und Haken gesetzt, Altfelder alt WHEN Soll THEN Soll folgt der Tabelle
- [ ] GIVEN `rows: []` / alle email aus / Zeile außerhalb der Grundauswahl WHEN Soll THEN erwartete Grundauswahl bzw. leere Liste
- [ ] GIVEN abgeleitete Größe ohne Zeile, Eltern-Zeile email aus WHEN Soll THEN sie ist aus
- [ ] GIVEN Trip morning vs. evening mit identischer Tabelle WHEN Soll THEN je Report eigene Grundauswahl
- [ ] GIVEN Windrichtung email aus WHEN Soll THEN keine Wind-Verschmelzung
- [ ] GIVEN Orte-Doppelzeile mit nur einer Auswertung in der Grundauswahl WHEN Soll THEN nur dieses Paar
- [ ] GIVEN Orte ohne `active_metrics` mit Tabelle WHEN Soll THEN Standardzeilen
- [ ] GIVEN Fenstergröße im Trip WHEN Soll THEN in E-Mail-Ausgabe, nie im Ausblick
- [ ] GIVEN Altbestand ohne Tabelle WHEN Soll THEN Bestandstests und gesicherte Vorher-Ausgabe unverändert
- [ ] Quelltext-Kontrolle des neuen Pfads gegen `resolve_*` als `# doc-compliance-test` (Spiegel-Verbot)

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Tabelle, in der die Reihenfolge und die E-Mail-Haken im Editor geändert wurden, während die Altfelder noch den alten Stand tragen / When das Soll abgeleitet wird / Then erwartet es die E-Mail-Größen in der Reihenfolge und Auswahl der Tabelle und meldet bei korrekt gerenderter Mail keinen Fehlalarm.
  - Test: Rohes Trip-JSON mit umsortierter Tabelle und alten Altfeldern; die von Hand notierte Liste entspricht der Tabelle, nicht den Altfeldern.

- **AC-2:** Given ein Orte-Vergleich mit Tabelle, deren Haken und Folge von `active_metrics`-Reihenfolge und Altfeldern abweichen / When das Soll abgeleitet wird / Then folgen Vergleichstabelle, Stundenverlauf und Ausblick der Tabelle je Stelle.
  - Test: Rohes Orte-JSON; Soll für email, hourly und outlook weicht erwartbar von den Altfeldern ab und entspricht der Tabelle.

- **AC-3:** Given eine Tabelle mit `rows: []` / When das Soll abgeleitet wird / Then gilt die gesamte Grundauswahl in ihrer Standardfolge, überall an.
  - Test: Trip und Orte mit leerer Zeilenliste ergeben die vollständige Grundauswahl für E-Mail.

- **AC-4:** Given eine Tabelle, in der bei allen Zeilen die E-Mail-Zelle aus ist / When das Soll abgeleitet wird / Then ist die E-Mail-Liste leer (bis auf Größen ohne eigene Spalte), und Stundenverlauf sowie Ausblick sind leer, weil sie nur mit E-Mail an wirken.
  - Test: Alle email-Haken aus; Soll hat leeren Ausblick und leeren Stundenverlauf.

- **AC-5:** Given eine abgeleitete Größe in der Grundauswahl ohne eigene Zeile, deren Eltern-Zeile in E-Mail aus ist / When das Soll abgeleitet wird / Then ist die abgeleitete Größe ebenfalls aus; ist die Eltern-Zeile an, steht sie direkt hinter ihr und erbt deren Haken.
  - Test: Zwei Fälle (Eltern an/aus) mit von Hand erwarteter Folge.

- **AC-6:** Given ein Trip, dessen Grundauswahl je Report (Morgen/Abend) verschieden ist, und eine report-unabhängige Tabelle / When das Soll für beide Reports abgeleitet wird / Then enthält jedes Soll nur die Größen der eigenen Grundauswahl, geordnet nach der Tabelle.
  - Test: Gleiche Tabelle, Report morning und evening ergeben je erwartete Liste.

- **AC-7:** Given Windrichtung mit E-Mail aus bei vorhandener Windstärke / When das Soll abgeleitet wird / Then gibt es keine verschmolzene Wind-Spalte; bei Windrichtung an bleibt die Verschmelzung erhalten.
  - Test: Beide Fälle prüfen das Vorhandensein der verschmolzenen Wind-Spalte.

- **AC-8:** Given eine Orte-Doppelzeile (Katalog-ID mit Minimum und Maximum), von der nur eine Auswertung in der Grundauswahl steht / When das Soll abgeleitet wird / Then erscheint nur dieses Paar; stehen beide in der Grundauswahl, erscheinen beide in Zeilenfolge.
  - Test: Zwei Eingaben mit von Hand erwarteter Paarliste.

- **AC-9:** Given ein Orte-Vergleich ohne `active_metrics` (nie eingestellt) mit vorhandener Tabelle / When das Soll abgeleitet wird / Then ist die Grundauswahl die Standardzeilen-Auswahl und nicht der feste Ausblick `_FEST`.
  - Test: Soll enthält die Standardzeilen, gesteuert durch die Tabelle.

- **AC-10:** Given Tabellenzeilen, deren Größe nicht in der Grundauswahl der Datei steht / When das Soll abgeleitet wird / Then bleiben sie ohne Wirkung und erzeugen weder Spalte noch Ausblickeintrag.
  - Test: Zusatzzeile mit fremder Größe ändert das Soll nicht.

- **AC-11:** Given ein Trip mit Fenstergrößen (keine eigene Spalte in der E-Mail) und eine Größe mit Sperre für Stundenwert oder Tageswert / When das Soll abgeleitet wird / Then bleibt die Fenstergröße in der E-Mail-Ausgabe, erscheint aber nie in Ausblick oder Stundenverlauf, und gesperrte Größen entfallen an der gesperrten Stelle.
  - Test: Fenstergröße im Trip-E-Mail-Soll vorhanden, im Ausblick-Soll nicht; Größe mit Sperre entfällt dort.

- **AC-12:** Given ein Orte-Vergleich mit `hourly_enabled: false` / When das Soll abgeleitet wird / Then ist der Stundenverlauf wie bisher aus, unabhängig von hourly-Haken der Tabelle.
  - Test: hourly-Haken an, `hourly_enabled` false: Stundenverlauf leer.

- **AC-13:** Given ein Altbestand ohne Tabelle (Trip und Orte) / When das Soll abgeleitet wird / Then ist die Ausgabe unverändert zu vorher, und die bestehenden Soll-Tests bleiben grün.
  - Test: Bestandstests `test_einstellung_gleich_mail_validatoren.py` und `test_3047_*` sowie die gesicherte Vorher-Ausgabe aus #3218 laufen unverändert grün.

- **AC-14:** Given der neue Tabellenpfad im Soll / When der Quelltext des Pfads geprüft wird / Then enthält er keinen Aufruf von `resolve_rows`, `resolve_channel_lists`, `placements_view` oder `metrics_at`; einzige Ausnahme bleibt `ausblick_briefings` (#3155).
  - Test: Als `# doc-compliance-test` gekennzeichnet; ergänzend beweisen die Tests AC-1 und AC-2, dass das Soll von Hand erwartet wird und nicht aus dem Produkt berechnet ist.

## Known Limitations

- Altfelder und Altpfad bleiben bis #3237 bestehen.
- Das OB des Ausblicks je Briefing hängt weiter an der #3155-Ausnahme (`resolve_*` nur dort).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fehlerbehebung im Prüfwerkzeug nach bestehender Regel (ADR-0124, Spec feat_3122); keine neue Entscheidungsfläche. Gewählt: statische Zweitregel statt #3155-Ausnahme, weil sonst Sortierfehler des Produkts nie auffallen.

## Changelog

- 2026-11-21: Initial spec created (Issue #3242)
