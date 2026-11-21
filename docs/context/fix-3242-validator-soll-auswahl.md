# Context: fix-3242-validator-soll-auswahl

## Request Summary
Das Validator-Soll (`--konfig` beider Mail-Validatoren) soll bei vorhandener Tabelle
`display_config.placements` Auswahl und Reihenfolge je Stelle (Trip: email + outlook;
Orte: email, hourly, outlook) aus `placements.rows[].places` ableiten statt aus den
Altfeldern. Voraussetzung für #3237 (Altfelder/Altpfad entfernen). #3218 hat bereits die
Darstellung (`formats`) umgestellt.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/_soll_aus_konfiguration.py` | Soll; Altfeld-Leser `_trip_email_liste`, `trip_soll` (`outlook_metrics`), `_orte_uebersicht`/`_orte_layout`, `_orte_stunden` (`hourly_metrics`), Orte-Ausblick; #3218-Helfer `_tabellen_zeile`, `_form`, `_hat_tabelle`, `_mit_tabelle` |
| `src/services/placements.py` | Produktregel: `_ordered_rows`, `resolve_rows`, `_cell`/`stellen_sperre`, `metrics_at` (inkl. `keine_eigene_spalte` bleibt in Ausgabe), `outlook_applies` |
| `src/services/channel_list_resolver.py` | `grundauswahl`, `placements_view`: Kanal-/Ausblick-/Stundenliste aus Tabelle; Orte: `_kanal_rows` weitet Katalog-ID auf Auswertungen der Grundauswahl |
| `src/app/metric_catalog.py` (`stellen_sperre`) | statisches Register, darf das Soll lesen |
| `tests/tdd/test_einstellung_gleich_mail_soll_placements.py` | #3218-Tests (Muster für neue Tests) |
| `tests/tdd/test_einstellung_gleich_mail_validatoren.py`, `tests/test_3047_*` | Bestandstests des Solls (Altpfad, müssen grün bleiben) |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py` | Aufrufer |

## Existing Patterns
- Soll liest nur rohe Datei + statisches Register, nie `resolve_*` (Spiegel-Verbot). Einzige
  dokumentierte Ausnahme: #3155 `ausblick_briefings` (OB der Ausblick im Briefing steht).
- #3218: `_hat_tabelle(dc)` schaltet zwischen Tabellenpfad und Altpfad.
- Tabellenregel (ADR-0124 / Spec #3122 Nr. 2, 3.1/3.2, 5): Zeilen der Grundauswahl in
  gespeicherter Folge; abgeleitete Größe ohne Zeile direkt hinter Eltern-Zeile mit deren
  Haken; restliche Grundauswahl hinten, überall an; `places[stelle] is False` = aus;
  Sperre laut Register; hourly/outlook nur, wenn email an; `keine_eigene_spalte`
  (Trip-email, Fenstergrößen) bleibt in Ausgabe.

## Dependencies
- Upstream: `app.metric_catalog` (Register, `stellen_sperre`), `COMPARE_METRIC_CATALOG`,
  `_DERIVED_METRIC_RULES` (bereits als `_ELTERN` statisch genutzt).
- Downstream: beide Mail-Validatoren (`--konfig`), Staging-E2E, #3237.

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` (Regeln der Tabelle)
- `docs/specs/modules/fix_3218_validator_soll_placements.md` (Vorgänger)
- `docs/specs/modules/feat_3157_migration_placements.md`

## Risks & Considerations
- Analysefrage: statische Nachbildung (ca. 30 Zeilen, unabhängige Zweitregel, Spiegel-Verbot
  gewahrt) vs. Ausnahme wie #3155 (eine Regel). Tendenz: statisch — Reihenfolge/Haken sind
  Gegenstand der Prüfung (anders als #3155, wo nur OB geprüft wird); mit der Produkt-Funktion
  würde der Validator Sortierfehler des Produkts nie finden.
- Grundauswahl Orte: Katalog-ID → mehrere Auswertungszeilen (`COMPARE_METRIC_CATALOG`),
  nur die der Grundauswahl (wie `_orte_layout`).
- Ausblick: mit Tabelle keine Drei-Werte-Semantik von `outlook_metrics` mehr; Liste = Zeilen
  mit outlook an (und email an), ohne Sperre `kein_tageswert`.
- Altpfad (ohne Tabelle) muss unverändert bleiben bis #3237.

## Analysis

### Type
Bug (Prüfwerkzeug: Validator-Soll weicht bei vorhandener Tabelle vom Produkt ab → Fehlalarme)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | neuer statischer Helfer `_tabellen_folge(dc, grund_ids, stelle, surface)` (~35 Z.); hinter `_hat_tabelle`: Trip-E-Mail-Liste, Trip-Ausblick, Orte-Übersicht, Orte-Stunden, Orte-Ausblick aus `placements.rows[].places` |
| `tests/tdd/test_einstellung_gleich_mail_soll_auswahl.py` | CREATE | Tests nach #3218-Muster: rohes JSON rein, Soll von Hand erwartet, nie aus `resolve_*` |
| `tests/tdd/test_einstellung_gleich_mail_soll_placements.py` | MODIFY (ggf.) | Tests, die neben der Tabelle `outlook_metrics`/Altfelder setzen und deren Wirkung erwarten (z. B. Z. 255, 314, 434), prüfen/anpassen |
| `docs/specs/modules/fix_3242_validator_soll_auswahl.md` | CREATE | Spec |

### Scope Assessment
- Files: 2–3 (+ Spec)
- Estimated LoC: Soll ca. +60/−15, Tests ca. +250
- Risk Level: LOW–MEDIUM (nur Prüfwerkzeug; Altpfad ohne Tabelle bleibt unverändert hinter `_hat_tabelle`)

### Technical Approach
Statische Nachbildung der Tabellenregel im Soll (unabhängige Zweitregel, Spiegel-Verbot gewahrt; keine Ausnahme wie #3155, weil Reihenfolge und Haken hier Prüfgegenstand sind; mit `resolve_rows` fände der Validator Sortierfehler des Produkts nie). Soll nutzt nur `read_placements` (wie `_hat_tabelle`) und das statische Register (`stellen_sperre`, `_ELTERN`, `COMPARE_METRIC_CATALOG`).

Regeln (Spiegel von `placements._ordered_rows`/`_cell`/`metrics_at`, ADR-0124, Spec #3122 Nr. 2/3.1/3.2/5):
1. Folge: Zeilen der Grundauswahl in gespeicherter Folge; abgeleitete Größe (nur wenn in der Grundauswahl der Datei, nicht künstlich erzeugen) ohne eigene Zeile direkt hinter Eltern-Zeile (hinter schon eingefügten Geschwistern) mit deren Haken; restliche Grundauswahl hinten, überall an. Zeilen außerhalb der Grundauswahl ohne Wirkung. `rows: []` = Tabelle ohne Zeilen (ganze Grundauswahl, alles an).
2. Zelle: Sperre laut `stellen_sperre` → raus, außer `keine_eigene_spalte` (Trip-email, Fenstergrößen) → bleibt. `places[stelle] is False` → aus, sonst an.
3. hourly/outlook nur, wenn die email-Zelle strikt `on` ist (gesperrte email = `not_in_email`: Fenstergrößen nie im Ausblick/Stundenverlauf).
4. Trip: Grundauswahl = bestehende Soll-Grundauswahl je Report (`_an`, `_sortiert`). E-Mail-Liste behält Einträge (metric_id/bucket/order), danach weiter `_mit_tabelle` (Form aus Tabelle, nötig für `_wind_verschmolzen`). Ausblick = Zeilen mit outlook an in Zeilenfolge, `outlook_metrics` ohne Wirkung; OB je Briefing bleibt bei #3155 (`trip_ausblick_briefings`).
5. Orte: Grundauswahl-Paare aus `active_metrics` (`_uebersicht_paare`); Zeile = Katalog-ID, aufgeweitet auf ihre Paare der Grundauswahl (min/max-Doppelzeilen; fehlt ein Paar in der Grundauswahl, entfällt es). Stundenverlauf: hourly an (email an, keine Sperre `kein_stundenwert`), danach bestehende Filter `_stuendlich`/`HOURLY_MERGE_ONLY`; `hourly_enabled: false` wie bisher. Ausblick: outlook an, Zeilenfolge.
6. Orte „nie eingestellt“ (kein `active_metrics`) MIT Tabelle: Grundauswahl = Standardzeilen (`orte_standardzeilen`, gleiche Quelle `CV2_ZEILEN` wie Produkt `_orte_standard`), NICHT der feste `_FEST`-Ausblick (verifiziert: `_FEST` = 6 feste Spalten; das Produkt nimmt mit Tabelle die Standard-Grundauswahl).

### Dependencies
- Upstream: `app.metric_catalog` (`stellen_sperre`, Register), `_DERIVED_METRIC_RULES` (`_ELTERN`), `COMPARE_METRIC_CATALOG`, `services.placements.read_placements` (nur Lesen).
- Downstream: beide Mail-Validatoren (`--konfig`), Staging-E2E, danach #3237.
- Abgeleitete Größen hängen im Produkt am Loader; im Soll wirken sie weder auf `stunden` noch `ueberblick` (NO_HOURLY_COLUMN, nicht in `_PILL_CATALOG_ORDER`), nur auf `darstellung_stunden`-Schlüssel (AC-13 aus #3218).

### Ränder, die Tests abdecken müssen
`rows: []`; alle email aus; abgeleitete Größe mit Eltern-Zeile email aus; Trip morning vs. evening (Grundauswahl je Report, Tabelle report-unabhängig); Windrichtung email aus → keine Verschmelzung; Orte-Doppelzeile mit nur einer Auswertung in der Grundauswahl; Orte nie eingestellt mit Tabelle; Zeile außerhalb der Grundauswahl; Umsortierung/Haken im Editor geändert, Altfelder bleiben alt (Fehlalarm-Fall aus dem Issue).

### Open Questions
- keine (rein technisch; Produktregel durch ADR-0124/Spec #3122 festgelegt)
