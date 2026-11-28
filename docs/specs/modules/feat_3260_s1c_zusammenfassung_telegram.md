---
entity_id: feat_3260_s1c_zusammenfassung_telegram
type: feature
created: 2026-11-27
updated: 2026-11-27
status: approved
version: "1.0"
tags: [issue-3260, adr-0127, metric-format, kurz-zusammenfassung, telegram, orte, schritt-1]
supersedes: [feat_3260_s1b_form_je_stelle (Known Limitation: STUNDEN_MARKE ohne Leser)]
---

# Schritt 1, Scheibe C: Kurz-Zusammenfassung (Gewitter, Windrichtung) und Orte-Telegram ohne Stunden-Marke an der Windrichtung

## Approval

- [x] Approved
- PO-Freigabe 2026-11-21, Issue #3260 (E1; T1; Pflicht-Nachtrag P1–P3). ACs AC-1.5, AC-1.6, AC-1.7 wörtlich aus dem Issue, AC-4 bis AC-6 verfeinern sie.

## Purpose

Die Kurz-Zusammenfassung der Trip-Mail wählt heute an zwei Stellen selbst eine Form nach dem E-Mail-Umschalter: Gewitter erscheint je nach Umschalter als „⚡ möglich“ oder „Gewitter möglich“, ohne Stufe; die Windrichtung erscheint nur, wenn Wind auf Einfach steht. Das Orte-Telegram hängt bei Einfach an jede Größe mit Ampel-Seite eine Stunden-Marke `@h`, auch an die Windrichtung (Vorlage Radtour). Nach dieser Scheibe kommen Gewitterwort und Windrichtung aus der einen Darstellung (`metric_format.darstellung`) und die Marke folgt dem Katalog (`STUNDEN_MARKE` über `stunden_marke_erlaubt`), keine örtliche Ausnahme.

## Source

- `src/output/renderers/compact_summary.py`: `format_weather_summary` (Aufrufe :243-258), `_format_wind` (Kompass :555), `_format_thunder` (MED/HIGH-Zweig :644-647).
- `src/output/renderers/comparison.py`: `_plain_metric_cell` (Marke :726), `_ampel_stunde`.
- `src/output/metric_format.py`: `darstellung`, `stunden_marke_erlaubt` (unverändert, neue Leser).
- `src/i18n/messages/{de,en}/mail.json`: neuer Schlüssel `mail.zusammenfassung.gewitter_stufe`; `gewitter_symbol` und `gewitter_moeglich` entfallen (einziger Leser ist `compact_summary`).
- Landkarte: `docs/context/3260/s1b_darstellungswege.md` Nr. 3-5; Kontext und Analyse: `docs/context/feat-3260-s1c-zusammenfassung.md`.

## Scope

- **Files:** 4 Produkt-/Katalogdateien, 1 neuer Test, ~5 umzuschreibende Bestandstests plus Goldens.
- **LoC:** ~40 Produkt, ~150 Test; Goldens und Fixtures mit MED/HIGH-Gewitter in der Zusammenfassung werden neu erzeugt.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `feat_3260_s1b_form_je_stelle` | Spec | liefert `STELLEN_FORMEN`, `WORTSKALA`, `darstellung`, `STUNDEN_MARKE` |
| `feat_3260_s1a_ratsche_ein_katalog` | Spec | Ratsche: Funde in berührten Dateien dürfen nicht steigen |
| ADR-0127 | ADR | ein Katalog, eine Verarbeitung |

## Kanal-Prüfung

- E-Mail (HTML, Nur-Text) und Telegram-Kurzfassung: betroffen, Kern-Tests decken beide ab.
- Orte-Telegram: betroffen (Stunden-Marke).
- SMS und Premium-SMS: nicht betroffen. Sie lesen die Kurz-Zusammenfassung nicht, Gewitter kommt dort als eigenes `TH:`-Token aus `dp.thunder_level` (`sms_trip.py`), die Orte-SMS baut keine `@h`-Marke über `_plain_metric_cell`.

## Implementation Details

1. **Gewitter (AC-1.5, AC-4):** `_format_thunder(hourly)` verliert den Parameter `friendly`; der Aufruf in `format_weather_summary` reicht keinen Umschalter mehr weiter. LOW-Zweig (Luftmassen-Aussage, #2176) bleibt unverändert. MED/HIGH: `stufe = darstellung("thunder", max_lvl.value, stelle="email", ausgabeart="text", fmt=None, ampel=None, lang=lang).text`; Text `t("mail.zusammenfassung.gewitter_stufe", lang, stufe=stufe)` + ` {start}:00–{ende}:00`, danach wie bisher Herkunft und Hagel. DE „Gewitter mittel 14:00–17:00“, EN „Thunderstorm medium 14:00–17:00“.
2. **Windrichtung (AC-1.6, AC-5):** `_format_wind` verliert `friendly`; der Kompass hängt nur an `wind_dir_enabled` und am vorhandenen Mittelwert. Der Kompass kommt aus `darstellung("wind_direction", deg, stelle="email", ausgabeart="text", fmt="simplified", ampel=None).text`.
3. **Orte-Telegram (AC-1.7, AC-6):** In `_plain_metric_cell` wird die Marke nur gesetzt, wenn `friendly` und `stunden_marke_erlaubt(<Katalog-ID>)` (Katalog-ID über `_CV2_BY_KEY`). Wind, Böen, Niederschlag, Regenwahrscheinlichkeit behalten die Marke.
4. Die Wind-Wortskala der Zusammenfassung (15/35/60, „Sturm“) bleibt in dieser Scheibe; sie wird mit AC-3.5 in Schritt 3 auf die Tabellenskala umgestellt (Ratschen-Ausnahme bleibt bis dahin bestehen, wächst nicht).

## Expected Behavior

- **Input:** Trip- oder Orte-Briefing mit Gewitter-Stunden der Stufe mittel/hoch, Wind mit Windrichtung in der Auswahl, Orts-Vergleich mit Telegram auf Einfach.
- **Output:** Zusammenfassung „Gewitter <Stufenwort> hh:00–hh:00 …“ in HTML und Nur-Text, unabhängig vom Umschalter; Kompass auch bei Wind roh; Orte-Telegram ohne `@hh` an der Windrichtung.
- **Side effects:** Keine Datenänderung. SMS und Premium-SMS unberührt (eigenes TH-Token).

## Acceptance Criteria

- **AC-1.5:** Given ein Trip mit Gewitter auf Einfach bzw. auf Roh in der E-Mail / When die Kurz-Zusammenfassung der HTML- und der Nur-Text-Mail erzeugt wird / Then steht in beiden Fällen dasselbe Stufenwort, und der Text ändert sich durch den Umschalter nicht.
- **AC-1.6:** Given ein Trip mit Wind auf Roh und Windrichtung in der Auswahl / When die Kurz-Zusammenfassung erzeugt wird / Then erscheint die Windrichtung genauso wie bei Wind auf Einfach.
- **AC-1.7:** Given ein Orts-Vergleich der Vorlage Radtour mit Windrichtung in Telegram / When das Telegram-Briefing erzeugt wird / Then trägt die Windrichtung keine Stunden-Marke.
- **AC-4:** Given Gewitter-Stunden der Stufe mittel in einer deutschen und einer englischen Trip-Mail / When die Kurz-Zusammenfassung erzeugt wird / Then lautet sie „Gewitter mittel“ bzw. „Thunderstorm medium“ mit Zeitfenster, und weder „⚡ möglich“ noch „Gewitter möglich“ kommt vor; Gewitter der Stufe leicht zeigt weiter die Luftmassen-Aussage.
- **AC-5:** Given ein Trip mit Windrichtung, aber ohne Windrichtung in der Auswahl / When die Kurz-Zusammenfassung erzeugt wird / Then erscheint keine Windrichtung, egal ob Wind auf Roh oder Einfach steht.
- **AC-6:** Given zwei Nutzer mit je einem Orts-Vergleich, Nutzer A Vorlage Radtour mit Wind und Windrichtung auf Einfach in Telegram und gelbem Wind, Nutzer B ohne Windrichtung / When beide Telegram-Briefings erzeugt werden / Then trägt bei A die Wind-Zelle weiter ihre Stunden-Marke und die Windrichtung keine, und keiner sieht Orte oder Werte des anderen.

## Definition of Done

- Neue Kern-Tests rot vor, grün nach der Änderung; umgeschriebene Bestandstests und Goldens grün; Ratsche grün ohne neue Ausnahme.
- Nachweis an echter Staging-Mail (Trip mit Gewitter, Orts-Vergleich mit Telegram) per `/e2e-verify`.

## Test Plan

- `tests/tdd/test_feat_3260_s1c_zusammenfassung_telegram.py`: echter `CompactSummaryFormatter` (DE/EN, friendly True/False, MED/HIGH/LOW), echter Orte-Telegram-Renderer mit Vorlage radtour, zwei Nutzer. Erwartung von Hand geschrieben.
- Umschreiben: `test_gewitter_zelle_zusammenfassung_sprache.py`, `test_trip_summary_text.py` und weitere Tests, die „⚡ möglich“/„Gewitter möglich“ der Zusammenfassung festschreiben.

## Out of Scope

- Wind-Wortskala der Zusammenfassung (AC-3.5, Schritt 3); Mail-Validatoren und Prüfkatalog (AC-1.4, Scheibe D).

## Affected Files

| Datei | Änderung |
|---|---|
| `src/output/renderers/compact_summary.py` | MODIFY |
| `src/output/renderers/comparison.py` | MODIFY |
| `src/i18n/messages/de/mail.json`, `src/i18n/messages/en/mail.json` | MODIFY |
| `tests/tdd/test_feat_3260_s1c_zusammenfassung_telegram.py` | CREATE |
| `tests/unit/test_gewitter_zelle_zusammenfassung_sprache.py`, `tests/unit/test_trip_summary_text.py`, `tests/unit/test_briefing_compact_plain_sprache.py`, `tests/tdd/test_thunder_origin_trip.py`, `tests/tdd/test_thunder_headline_sentence.py` (soweit sie den Zusammenfassungs-Wortlaut prüfen) | MODIFY |
| `tests/golden/email/*`, `tests/fixtures/golden_3237/*`, `tests/fixtures/einstellung_gleich_mail/*` (nur Dateien mit MED/HIGH-Gewitter in der Zusammenfassung) | MODIFY (regeneriert) |

## Known Limitations

- Wind-Adjektiv der Zusammenfassung weicht bis Schritt 3 von der Tabellenskala ab.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0127 (Umsetzung, keine neue Entscheidung)
- **Rationale:** Kurz-Zusammenfassung und Orte-Telegram werden als weitere Verbraucher an Katalog und Verarbeitungsmodul angeschlossen; keine Entscheidungsfläche ändert sich.

## Changelog

- 2026-11-27: Erstfassung (Workflow feat-3260-s1c-zusammenfassung).
