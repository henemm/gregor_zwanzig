---
entity_id: feat_2799_s7a1_ampel_ableitung
type: module
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
issue: 2799
epic: 2791
workflow: feat-2799-s7a1-ableitung
tags: [ampel, vorbau, ableitung, kanal-paritaet, epic-2791]
---

# Einstellungen neu S7, Teil-PR S7a1: Ampel-Färbung je Stelle aus einer Quelle (#2799)

## Approval

- [ ] Approved

## Purpose

Teil-PR S7a1 der freigegebenen Gesamt-Spec `feat_2799_s7_ampel_weitere.md` (Lieferplan, „Nachtrag Teil S7a1“). Vorbau ohne sichtbare Änderung: Jede Stelle, die über die Ampel-Farbe einer Metrik entscheidet (Pille, Stundentabelle, Orte-Übersicht, SMS-Kürzel), fragt künftig eine zentrale Regel `faerbt_an(stelle, metric_id)`, die zur Laufzeit aus `AMPEL_LESER` liest und die heutigen bewussten Ausnahmen je Stelle benennt. Damit färbt die spätere Aufnahme einer Metrik in `AMPEL_LESER` (S7a2) alle Kanäle zugleich, ohne Drift. Heute ändert sich keine Ausgabe.

## Source

- `src/app/ampel.py`: `AMPEL_BESTANDSAUSNAHMEN`, `faerbt_an`
- `src/output/renderers/email/helpers.py`: Pillen Bewölkung, tiefe Wolken, Taupunkt, Sonnenstunden (`_pille_ampelton`)
- `src/output/renderers/email/html.py`: Rückfall-Tönung der Stundentabelle (`_stundentabelle_metrik`)
- `src/output/renderers/email/compare_html.py`: generische Stufe für Orte-Übersicht-Zeilen ohne eigene `sev`
- `src/output/tokens/builder.py`: Kürzelkarte `ampel_metrik_je_kuerzel` aus der Katalog-Zuordnung

## Estimated Scope

- **LoC:** Produktivcode ca. +75/−30, fünf Dateien; Tests ca. 600 LoC plus Golden-Dateien
- **Effort:** mittel

## Scope

**In Scope:** Ableitung der vier Farb-Entscheidungsstellen aus `faerbt_an`; benannte Bestandsausnahmen (`stundentabelle`: gefühlte Temperatur, UV, Neuschnee; `orte_uebersicht`: gefühlte Temperatur, Neuschnee; `pille`, `sms`: keine); Pillen-Stufe aus dem schärfsten Tageswert je Seite.

**Out of Scope:** Form-Listen (`AMPEL_METRIC_IDS` und Aliasse), Alarm-Stunden (S7c), Nullgrad-/Schneefallgrenze (S7b), Validator-Spalten (S7a2), jede Aktivierung neuer Metriken (S7a2).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_2799_s7_ampel_weitere.md` | Gesamt-Spec | Lieferplan, Nachtrag S7a1, AC-18 und AC-22 |
| `tests/helpers/metrik_listen_scan.py` | Ratsche | Register der Metrik-Listen |

## Implementation Details

Siehe Gesamt-Spec, Abschnitt „Nachtrag Teil S7a1“ (verbindlich). Telegram, Outlook und Orte-Stunden lesen bereits über `hat_ampel` und bleiben unverändert.

## Expected Behavior

- **Input:** Wetterdaten, aufgelöste Ampel, gewählte Metriken.
- **Output:** Heute byte-gleiche Ausgaben in allen Kanälen; nach Aufnahme einer Metrik in `AMPEL_LESER` trägt sie überall ihre Stufe.
- **Side effects:** keine.

## Acceptance Criteria

- **AC-1:** Given ein Trip- und ein Orte-Briefing mit Bewölkung, tiefen Wolken, Taupunkt, Sonnenstunden, Schneehöhe, Nullgradgrenze, gefühlter Temperatur, UV und Neuschnee / When E-Mail (HTML und Klartext), Telegram, SMS und Premium-SMS nach S7a1 erzeugt werden / Then sind alle Ausgaben byte-gleich zum Stand vor S7a1 (Gesamt-Spec AC-22)
- **AC-2:** Given eine Metrik der Gesamt-Spec (z. B. Bewölkung) wird zur Laufzeit in `AMPEL_LESER` aufgenommen / When Pille, Stundentabelle, Orte-Übersicht, SMS-Kürzel und Telegram erzeugt werden / Then trägt sie an jeder dieser Stellen die Stufe der Vorlage (Vorbau für Gesamt-Spec AC-18)
- **AC-3:** Given die Regel `faerbt_an` / When für jede Stelle die gefärbte Menge gebildet wird / Then ist sie `AMPEL_LESER` minus der benannten Bestandsausnahme dieser Stelle, die Ausnahmen sind Teilmengen von `AMPEL_LESER`, und eine unbekannte Stelle ist für eine Metrik mit Ampel-Leser ein Fehler (Gesamt-Spec AC-18)
- **AC-4:** Given ein Taupunkt, der über den Tag schwankt (5 °C, Spitze 19 °C) / When die Pille bei aktivierter Metrik erzeugt wird / Then zeigt sie den Tageswert wie heute und färbt nach dem schärfsten Wert (orange)
- **AC-5:** Given eine Orte-Übersicht-Zeile mit eigener Färbung (Gewitter) / When neue Metriken aktiviert werden / Then behält sie ihre eigene Färbung, und gefühlte Temperatur sowie Neuschnee bleiben in der Übersicht ungefärbt

## Test Plan

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_2799_s7a1_ampel_ableitung.py`: Golden byte-gleich (AC-1), Nahtstellen-Tests mit Aufnahme in `AMPEL_LESER` (AC-2, AC-4, AC-5), Ratsche je Stelle (AC-3); Mutations-Gegenprobe durch den Adversary.

## Definition of Done

- [ ] AC-1 bis AC-5 grün in `tests/tdd/test_2799_s7a1_ampel_ableitung.py`, Metrik-Listen- und Ein-Katalog-Ratsche grün, alle 6 CI-Checks grün.
- [ ] Adversary VERIFIED inklusive Mutations-Gegenprobe.
- [ ] Staging-Lauf und `/e2e-verify` grün, Prod-Deploy mit Selftest Exit 0; Issue #2799 bleibt offen (weitere Teile folgen).

## Known Limitations

- Bei Metriken ohne Ampel-Leser liefert `faerbt_an` für eine unbekannte Stelle `False` statt eines Fehlers (Kurzschluss über `hat_ampel`); alle Aufrufer nutzen feste Stellennamen.
- Sichtbare Formatfrage `CT`/`CL` im SMS bei Aktivierung wird in S7a2 entschieden (Gesamt-Spec, offener Punkt).

## Changelog

- 2026-11-28: Teil-Spec S7a1 aus dem Nachtrag der Gesamt-Spec abgeleitet
