---
entity_id: fix_3218_validator_soll_placements
type: bugfix
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: fix-3218-validator-soll-placements
tags: [validator, soll, placements, "#3218"]
---

# Validator-Soll (--konfig) liest placements.rows[].formats (Bug #3218)

## Approval

- [ ] Approved

## Purpose

Das Soll der Mail-Validatoren (`--konfig`) leitet Roh/Einfach nur aus Altfeldern ab und ignoriert die Tabelle `display_config.placements`, die der Renderer allein verwendet. Ergebnis: Fehlalarme bei korrekt gerenderter Mail (12 SOLL-Verletzungen) und nach Migration B6 ein Soll, das nur noch Standardwerte prüft. Das Soll folgt künftig mit Tabelle der Form aus `formats`; zusätzlich wird die `orte`-Hülle dokumentiert und fehlerfest gemacht.

## Source

- **File:** `.claude/hooks/_soll_aus_konfiguration.py`
- **Identifier:** `trip_soll`, `_modus`, `_formen_stunden`, `_orte_einfach`, `orte_soll`, `soll_aus_daten`

> Schicht: Prüfwerkzeug (`.claude/hooks/`), weder Frontend noch Go-API noch Produktcode. Kein Trip/Vergleich-Pendant-Problem: das Soll deckt beide Seiten in derselben Datei mit derselben Regel ab. Keine Nutzerdaten werden bewegt (nur Lesen von JSON); alle vier Kanäle unberührt (nur E-Mail-Prüfung).

## Estimated Scope

- **LoC:** +~70 Quelle, +~10 Doku, +~120 Tests / −~5
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.metric_catalog` (`zwei_formen_stellen`, `standard_form`, `AMPEL_METRIC_IDS`) | module | Statisches Register: an welchen Stellen es zwei Formen gibt, Katalog-Standard |
| `services.placements` (nur `_hat_tabelle`, bereits importiert) | module | Erkennung "Tabelle vorhanden" |
| `briefing_mail_validator.py`, `email_spec_validator.py` | Verbraucher | Lesen `darstellung_*`, `formen_*`, `uebersicht_*`, `ausblick.formen` |
| `tests/fixtures/einstellung_gleich_mail/fallliste_*.json` | Fixtures | Vorher/Nachher-Gleichheit für Altbestand |

## Implementation Details

Überlagerung statt neuer Zweige, alles hinter `_hat_tabelle(dc)`:

1. Neuer Helfer `_form(dc, mid, stelle)`: erste Zeile mit dieser `metric_id` (Duplikate ignorieren); nur wenn `stelle in zwei_formen_stellen(mid)`; `formats[stelle]` nur gültig, wenn Stelle bekannt und Wert `raw|simplified` (wie `_read_row` des Produkts); sonst `standard_form(mid)`.
2. `_mit_tabelle(liste, dc)` überlagert `format_mode`/`use_friendly_format` der E-Mail-Liste nach der Abbildung des Produkts (raw: Roh, `use_friendly_format=False`; simplified: Einfach mit `format_mode=simplified`, wenn der Katalog den Modus kennt, sonst Katalog-Standard, `use_friendly_format=True`). Windrichtung `simplified` → `default_format_mode`, damit `_wind_verschmolzen` nicht bricht.
3. `_modus`, `_formen_stunden`, `_wind_verschmolzen` bleiben unverändert und folgen automatisch (Ampel-Ausnahme hängt an `use_friendly_format`).
4. Orte: `_orte_einfach` im Tabellenzweig `_form(dc, m, "email") == "simplified" and len(format_modes) > 1`.
5. Ausblick Trip + Orte: `{m: _form(dc, m, "outlook") == "simplified"}` statt `outlook_metric_formats`, wenn Tabelle vorhanden.
6. `soll_aus_daten`: `daten["orte"]` als Liste → `ValueError` mit klarer Meldung (erwartet `{"<Kennung>": "<Name>"}`) statt `TypeError`.
7. Doku `docs/reference/mail_validators.md` (Abschnitt `--konfig`): Quelle der Form (Tabelle vor Altfeldern, fehlend = Katalog-Standard), Hülle `{"preset": …, "orte": {"<Kennung>": "<Name>"}}`, Restlücke Auswahl/Folge (#3242).

**Spiegel-Verbot:** Das Soll ruft weder `_cell` noch `placements_view` noch `resolve_channel_lists` auf; Regel entsteht aus rohem JSON plus Register. Einzige bestehende Ausnahme bleibt `ausblick_briefings` (#3155).

**Abgeleitete Größen ohne eigene Zeile (Randfall, Entscheidung):** Das Produkt vererbt der abgeleiteten Größe die Formate der Eltern-Zeile (`_ordered_rows`). Das Soll übernimmt dieselbe Regel statisch: Eltern-Zeile laut `_DERIVED_METRIC_RULES` vorhanden → deren `_form`; keine Eltern-Zeile → `standard_form`. Begründung: nur so gibt es bei einer einfach gestellten Eltern-Größe keinen neuen Fehlalarm; die Regel bleibt statisch (Register, kein Produktaufruf). Der Test fixiert das Verhalten gegen eine echt gerenderte Mail-Vorlage nicht per Mock.

## Expected Behavior

- **Input:** Abo-JSON (Trip oder Orte-Vergleich) mit oder ohne `display_config.placements`.
- **Output:** Soll-Struktur; mit Tabelle richtet sich Roh/Einfach nach `formats`, ohne Tabelle unverändert nach Altfeldern.
- **Side effects:** keine.

## Scope

- In: Darstellung Roh/Einfach im Soll mit Tabelle (Trip-Stundentabelle HTML/Klartext inkl. Ampel-Ausnahme, Orte-Vergleichstabelle, Ausblick Trip und Orte), abgeleitete Größen ohne eigene Zeile, `orte`-Hülle (Fehlermeldung und Doku).
- Dateien: `.claude/hooks/_soll_aus_konfiguration.py`, `docs/reference/mail_validators.md`, `tests/tdd/test_einstellung_gleich_mail_soll_placements.py`.

## Definition of Done

- AC-1 bis AC-13 durch Kern-Tests ohne Mock grün; bestehende Soll-Tests (`tests/tdd/test_einstellung_gleich_mail_*.py`) grün.
- Altbestand ohne Tabelle bytegleich (AC-10).
- Abnahme auf Staging: der Fall aus #3156 läuft durch den Briefing-Validator mit `--konfig` ohne SOLL-Verletzung.
- Doku `docs/reference/mail_validators.md` nachgezogen, Restlücke auf #3242 verwiesen.

## Out of Scope

- Auswahl und Reihenfolge der Größen mit Tabelle (Soll liest sie weiter aus Altfeldern): eigenes Issue #3242, Voraussetzung für #3237.
- Form des Orte-Stundenverlaufs (`formats.hourly`): das Soll prüft dort heute keine Form, bleibt so.

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/tdd/test_einstellung_gleich_mail_soll_placements.py`, ohne Mock; Eingabe ist rohes Abo-JSON, geprüft wird die Soll-Struktur.

- [ ] Konflikt Altfeld/Tabelle: Trip HTML/Klartext, Ampel- und Nicht-Ampel-Größe
- [ ] `formats` fehlt, Müllwerte, doppelte `metric_id`, Windrichtung
- [ ] Orte-Vergleichstabelle und Ausblick Trip + Orte
- [ ] Altbestand ohne Tabelle: Soll bytegleich zu vorher (Fixtures `fallliste_*.json`)
- [ ] Hülle `orte` als Liste, Abnahme-Fall #3156, abgeleitete Größe ohne Zeile

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Tabelle, in der `formats.email=simplified` steht und das Altfeld `use_friendly_format=false` / When das Soll abgeleitet wird / Then erwartet es für die E-Mail-Stundentabelle die Form Einfach (HTML inklusive Ampel-Ausnahme, Klartext als Wortstufe) und nicht Roh.
  - Test: Soll-Struktur für eine Ampel-Größe (z. B. Regenwahrscheinlichkeit) zeigt Einfach in HTML und Klartext.

- **AC-2:** Given dieselbe Konstellation mit einer Nicht-Ampel-Größe, die zwei Formen kennt / When das Soll abgeleitet wird / Then erwartet es ebenfalls Einfach, ohne Ampel-Sonderfall.
  - Test: Soll-Struktur für eine Nicht-Ampel-Größe zeigt Einfach.

- **AC-3:** Given eine Tabellenzeile ohne `formats` an einer Stelle mit zwei Formen / When das Soll abgeleitet wird / Then gilt der Katalog-Standard (`standard_form`) für Trip und Orte gleich.
  - Test: Zeile ohne `formats` ergibt je Größe die im Katalog hinterlegte Standardform.

- **AC-4:** Given `formats.email=raw` bei Altfeld `use_friendly_format=true` / When das Soll abgeleitet wird / Then erwartet es die Form Roh.
  - Test: Soll-Struktur zeigt Zahl statt Wortstufe/Ampel.

- **AC-5:** Given Müllwerte in `formats` (unbekannte Stelle oder Wert außerhalb von `raw|simplified`) / When das Soll abgeleitet wird / Then bleiben sie ohne Wirkung und es gilt der Katalog-Standard.
  - Test: Zeile mit `{"foo":"raw"}` und `{"email":"bunt"}` ergibt Standardform.

- **AC-6:** Given zwei Tabellenzeilen mit derselben `metric_id` und unterschiedlichen Formen / When das Soll abgeleitet wird / Then gilt die erste Zeile.
  - Test: Reihenfolge der Duplikate umdrehen kehrt das Ergebnis um.

- **AC-7:** Given Windrichtung mit `formats.email=simplified` neben Windstärke / When das Soll abgeleitet wird / Then bleibt die Wind-Verschmelzung erhalten.
  - Test: Soll-Struktur enthält weiterhin die verschmolzene Wind-Spalte.

- **AC-8:** Given ein Orte-Vergleich mit Tabelle / When das Soll abgeleitet wird / Then folgt die Vergleichstabelle `formats.email` und nicht `channel_layouts.email`.
  - Test: Altfeld sagt Roh, Tabelle Einfach: Soll `uebersicht_einfach` ist wahr für die Größe.

- **AC-9:** Given Trip und Orte-Vergleich mit Tabelle, in der `formats.outlook` und `outlook_metric_formats` auseinanderlaufen / When das Soll abgeleitet wird / Then gilt `formats.outlook`.
  - Test: `ausblick.formen` folgt der Tabelle in beiden Soll-Arten.

- **AC-10:** Given ein Altbestand ohne Tabelle / When das Soll abgeleitet wird / Then ist die Ausgabe bytegleich zu vorher.
  - Test: Vergleich der Soll-Ausgabe für alle Trip-/Orte-Eingaben ohne Tabelle aus `tests/fixtures/einstellung_gleich_mail/` (die `fallliste_*.json` sind Fall-Kataloge ohne Konfiguration und liefern keine Eingaben) plus erzeugte Trip-Varianten mit der gesicherten Vorher-Ausgabe `soll_ohne_tabelle_vorher_3218.json`.

- **AC-11:** Given eine `--konfig`-Datei, in der `orte` eine Liste statt `{"<Kennung>": "<Name>"}` ist / When der Validator startet / Then erscheint eine klare Fehlermeldung zur erwarteten Hülle statt eines `TypeError`; `docs/reference/mail_validators.md` beschreibt die Hülle und die Restlücke Auswahl/Folge (#3242).
  - Test: Aufruf von `soll_aus_daten` mit Listen-Hülle löst `ValueError` mit Hinweis auf die Hülle aus.

- **AC-12:** Given der Abnahme-Fall aus #3156 (`rain_probability` mit `formats.email=simplified`, `cloud_total` ohne `formats`, Altfelder `use_friendly_format=false`) / When das Soll gegen die korrekt gerenderte Mail geprüft wird / Then meldet der Validator keine SOLL-Verletzung.
  - Test: Soll erwartet für `rain_probability` Einfach und für `cloud_total` den Katalog-Standard; keine Verletzung "soll Zahl (Roh) zeigen".

- **AC-13:** Given eine abgeleitete Größe ohne eigene Tabellenzeile, deren Eltern-Zeile Einfach verlangt / When das Soll abgeleitet wird / Then übernimmt sie die Form der Eltern-Zeile, ohne Eltern-Zeile den Katalog-Standard.
  - Test: Zwei Fälle (mit/ohne Eltern-Zeile) ergeben jeweils die erwartete Form.

## Known Limitations

- Auswahl und Reihenfolge der Größen mit Tabelle prüft das Soll weiter aus Altfeldern (#3242).
- Form des Orte-Stundenverlaufs wird nicht geprüft.
- AC-13: Die Eltern-Vererbung ist mit dem heutigen Register nicht beobachtbar, weil keine abgeleitete Größe (`temperature_night`, `wind_chill_night`, `temperature_day_low/high`, `wind_chill_day_low/high`) und keiner ihrer Eltern (`temperature`, `wind_chill`) eine Stelle mit zwei Formen hat. Der Test sichert daher nur den Katalog-Standard ab; die Vererbung greift erst, wenn das Register dort zwei Formen einführt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fehlerbehebung im Prüfwerkzeug nach bestehender Regel (Spec feat_3122); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-21: Initial spec created (Issue #3218)
