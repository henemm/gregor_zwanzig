---
entity_id: fix_3359_e2e_pruefungen_ohne_altfelder
type: bugfix
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.0"
workflow: fix-3359-staging-pruefungen-altfelder
tags: [e2e, testarbeit, altfelder, epic-3122]
---

# E2E-Prüfungen ohne die zehn Altfelder (#3359)

## Approval

- [ ] Approved

## Purpose

Mehrere automatische Browser-Prüfungen (E2E) säen und vergleichen noch die zehn alten Einstellungs-Felder, die seit #3277 nichts mehr bewirken. Sie werden auf die heute allein gültige Wahrheit "Was steht wo" (`display_config.placements`) umgestellt, ohne dass eine Prüfung dabei schwächer wird. Es ist reine Testarbeit, am Produkt ändert sich nichts.

## Source

- **File:** `frontend/e2e/` (13 Dateien, siehe Scope)
- **Identifier:** Playwright-Prüfungen (AC-10/AC-11 in `editor-gleich-gespeichert.staging.spec.ts`, AC-6 in `standardwerte-und-hilfe.spec.ts`, ALTFELDER/WS-14 in `was-steht-wo-karte.spec.ts` u. a.)

> **Schicht-Hinweis:** Ausschließlich Test-Schicht `frontend/e2e/`. Kein Produktcode in `frontend/src`, `internal/`, `api/`, `src/`. Kontext und Bestandsaufnahme: `docs/context/fix-3359-staging-pruefungen-altfelder.md`.
>
> **Querschnitt:** Trip/Ortsvergleich-Teilung: Prüfungen für beide Kontexte werden gleichartig umgestellt (`route` und `vergleich`). Mandantentrennung: keine neue datenbewegende Funktion, Saat läuft über die bestehenden Prüfkonten. Kanäle: E-Mail, Telegram, SMS und Premium-SMS bleiben wie bisher durch die vorhandenen Prüfungen abgedeckt.

## Estimated Scope

- **LoC:** +~120 / -~150
- **Files:** ~13, alle unter `frontend/e2e/`
- **Effort:** low bis medium (Risiko liegt in versehentlicher Abschwächung)

## Scope

- **In Scope:** Umstellung bzw. Streichung der Altfeld-Saat und Altfeld-Vergleiche in den Prüfungen unter `frontend/e2e/` (Klassen C, B, E, Kommentar in `hub-anlegen-ablauf`), wie unter Implementation Details aufgeführt.
- **Out of Scope:** Produktcode (`frontend/src`, `internal/`, `api/`, `src/`), die Golden-C-Fixtures, das Löschen der Altfelder auf der Platte (Folge-Issue #3351), die bewusst bleibenden Abwesenheits-Prüfungen (A/D).

## Definition of Done

- AC-1 bis AC-13 erfüllt; die zwei heute roten Prüfungen (Golden C, Ausblick nur abends) laufen gegen Staging grün.
- Mutationsprobe des Adversary: jede umgestellte Prüfung wird bei gezielter Verfälschung rot.
- Alle 6 CI-Checks grün, `/e2e-verify` gegen Staging bestanden.
- Changelog der Spec nennt die Entscheidung zu `kurzform-gefuehlte-temperatur-kind-mitnahme` S1 (umgestellt oder gestrichen).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md` | Spec | Ursprung der Prüfungen AC-10/11/17 |
| `docs/specs/modules/feat_3122_was_steht_wo.md` | Spec | Epic-Spec "Was steht wo", Altfelder-Ablösung |
| `docs/specs/modules/feat_3277_altfelder_entfernen.md` | Spec | Python liest die Altfelder nicht mehr; Go reicht sie bewusst durch |
| `frontend/e2e/was-steht-wo.helpers.ts` | Test-Helfer | `oeffneKarte`, `folge`, `haken`, `stand`, `tabelle` |
| `src/services/placements.py`, `src/services/placements_view_service.py` | Python-Core (nur lesen) | Format `placements`, Feld `outlook_reports` der Tabellen-Ansicht |
| `tests/fixtures/einstellung_auslieferung/golden_c.json`, `erwartung_golden_c.json` | Fixtures (nur lesen, NICHT ändern) | Von ca. 14 Python-Tests genutzt |
| `.github/ci_e2e_specs.txt` | CI-Liste | Welche Prüfungen in CI laufen |
| Staging-Stack, lokaler E2E-Stack | Umgebung | Lauf der Prüfungen |

## Implementation Details

Prüfgruppen (Klassen aus der Bestandsaufnahme):

- **C (heute rot, erwarten Wirkung der Altfelder):**
  - AC-10 in `editor-gleich-gespeichert.staging.spec.ts`: Option (a). Die Karte muss je Stelle exakt der Server-Tabelle (`tabelle()`, Zellen mit Zustand "on") entsprechen, und `erwartung_golden_c.json` muss als Teilmenge darin enthalten sein (wie Python `test_placements_tabelle_jede_metrik.py:96-107`). Optional wird `cloud_low` auf E-Mail "an" festgenagelt. Kopfkommentar "GENAU" anpassen.
  - AC-6 in `standardwerte-und-hilfe.spec.ts`: Statt `report_config.multi_day_trend_reports` wird der wirksame Wert aus der Tabellen-Ansicht geprüft (`outlook_reports == ['evening']`), nicht ein gespeichertes Feld. Zusätzlich Tabelle A == Tabelle B.
- **B (Schein-Schutz, auf `placements` umstellen):** AC-11 (`metrics` + `placements` vorher = nachher); `was-steht-wo-karte.spec.ts` ALTFELDER und WS-14 (Read-Modify-Write mit echten fremden Feldern `daily_summary_metrics`, `wind_exposition_min_elevation_m`); `feat-3276-vergleich-ohne-altfelder.spec.ts`; `hub-save-chip.spec.ts` SC-1b; `kurzform-gefuehlte-temperatur-kind-mitnahme.spec.ts` S1 (SMS-Teil über `placements.rows`, wind_chill sms an, sonst streichen); `compare-outlook-metric-selection.staging.spec.ts` (Bestand über `placements` oder Schleife streichen). Saat immer mit `version: 1`; Saat-Zeilen weichen bewusst von der Grundauswahl ab, sonst wäre die Prüfung eine Tautologie.
- **E (tote Saat/Helfer, streichen):** `compare-uebersicht-kanal-persistenz.staging.spec.ts` (leere Prüfung), `hub-wetter-metriken-speichert-selbst.spec.ts`, `compare-uebersicht-kanal.helpers.ts` (`gespeicherteKanalAuswahl`, ohne Aufrufer), `compare-hourly-metric-order.spec.ts`, `s3b2795-zustellung.helpers.ts` (`show_outlook`), `hub-konfliktschutz-zwei-kontexte.spec.ts`.
- **A/D (bleiben):** `feat-3297-trip-ohne-altfelder`, `layout-tab-vergleich`, `vergleich-anlegen-was-steht-wo-3306`, `trip-anlegen-zustellung-3332` prüfen bewusst die Abwesenheit. `hub-anlegen-ablauf.spec.ts` bekommt nur einen korrigierten Kommentar (Z.430-432).

Ausführung: In CI (lokaler Stack, laut `.github/ci_e2e_specs.txt`) laufen `hub-save-chip`, `kurzform-gefuehlte-temperatur-kind-mitnahme`, `hub-wetter-metriken-speichert-selbst`, `hub-konfliktschutz-zwei-kontexte`, `was-steht-wo-karte`. Nur in `/e2e-verify` gegen Staging laufen `*.staging.spec.ts`, `feat-3276` und `standardwerte-und-hilfe`. `compare-hourly-metric-order` steht nicht in der CI-Liste (nur `/e2e-verify`); der Helfer `s3b2795-zustellung.helpers.ts` wird u. a. von `hub-save-chip` (CI) genutzt, die Streichung von `show_outlook` dort wird also in CI mitgeprüft (geprüft 25.11.).

Offene Detailfrage für den RED-Lauf: normalisiert Python eine gesäte `placements.rows` beim Laden? Dann wird gegen die normalisierte Form verglichen.

## Expected Behavior

- **Input:** Bestehende E2E-Prüfungen mit Altfeld-Saat bzw. Altfeld-Vergleich.
- **Output:** Dieselben Fragen, jetzt über `placements`/Tabellen-Ansicht gestellt; die zwei heute roten Prüfungen (AC-10, AC-6) sind grün, Schein-Schutz ist durch echten Schutz ersetzt.
- **Side effects:** Keine. `golden_c.json` und `erwartung_golden_c.json` bleiben unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] AC-10 (Staging): heute rot (E-Mail-Spalte 11 statt 7 Ausgaben), nach Umstellung grün.
- [ ] AC-6 (Staging): heute rot (Schlüssel wird nicht mehr gesendet), nach Umstellung grün.
- [ ] Je Klasse-B-Prüfung: gesäter Bestand mit abweichenden Zeilen; Speichern ohne Änderung lässt `placements`, `metrics` und fremde Felder unverändert.
- [ ] Mutationsprobe je umgestellter Prüfung (Adversary, per String-Ersetzung mit externer Sicherung, nie git checkout/stash/reset).
- [ ] Wächter: Suche in `frontend/e2e` nach den zehn Altfeld-Namen findet nur die A/D-Abwesenheits-Prüfungen und Kommentare ohne Wirkung.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit der Standard-Einstellung "Golden C" ist gespeichert / When der Nutzer den Reiter "Was steht wo" öffnet / Then zeigt die Karte je Ausgabestelle (E-Mail, Telegram, SMS, Ausblick) genau die Haken, die der Server in seiner Tabelle ausweist, und alle Ausgaben aus der Golden-C-Erwartung sind angehakt (heute rot, weil die Prüfung noch auf das alte E-Mail-Layout wartet).
  - Test: `editor-gleich-gespeichert.staging.spec.ts` AC-10, Karte gegen `tabelle()` exakt je Stelle plus `erwartung_golden_c.json` als Teilmenge; Golden-Dateien unverändert.

- **AC-2:** Given ein neuer Trip, bei dem der Nutzer den Ausblick nur für den Abendbericht wählt / When Karte und Server-Ansicht verglichen werden / Then meldet der Server als wirksamen Ausblick-Bericht nur "abends" (`outlook_reports == ['evening']`) und zwei Trips mit gleicher Wahl liefern dieselbe Tabelle (heute rot, weil das alte Feld nicht mehr gesendet wird).
  - Test: `standardwerte-und-hilfe.spec.ts` AC-6, Prüfung über `tabelle(request,'route',id).outlook_reports`, nicht über ein gespeichertes Feld.

- **AC-3:** Given ein gespeicherter Trip mit eigener Tabelle "Was steht wo" und einer Grundauswahl / When der Nutzer im Editor ohne Änderung speichert / Then bleiben Grundauswahl und Tabelle unverändert (vorher = nachher) und es wird nichts Zusätzliches ausgegeben.
  - Test: `editor-gleich-gespeichert.staging.spec.ts` AC-11, vergleicht `metrics` und `placements` statt des alten Layout-Felds.

- **AC-4:** Given ein gespeicherter Trip und ein gespeicherter Ortsvergleich mit fremden Einstellungen außerhalb von "Was steht wo" (z. B. Tageszusammenfassung, Mindesthöhe für Windexposition) / When der Nutzer in der Karte etwas ändert und speichert / Then sind diese fremden Einstellungen danach unverändert erhalten und nichts geht verloren.
  - Test: `was-steht-wo-karte.spec.ts` Abschnitte ALTFELDER und WS-14 (Read-Modify-Write mit `daily_summary_metrics`, `wind_exposition_min_elevation_m`), je ein Lauf für Trip und Vergleich.

- **AC-5:** Given zwei gespeicherte Ortsvergleiche A und B mit eigener, von der Grundauswahl abweichender Tabelle (`placements.rows`, `version: 1`) / When der Nutzer A öffnet und speichert / Then enthält die gesendete Speicherung keine der zehn Altfelder, und die Tabellen von A und B bleiben unverändert.
  - Test: `feat-3276-vergleich-ohne-altfelder.spec.ts`, Saat mit `placements.rows`, Fehlen-Prüfung im PUT bleibt.

- **AC-6:** Given ein gespeicherter Trip mit eigener Tabelle, die von der Grundauswahl abweicht / When der Nutzer auf dem Hub nichts ändert / Then bleibt der Speichern-Hinweis ruhig, es wird keine Speicherung gesendet (0 PUTs) und die Tabelle ist danach gleich.
  - Test: `hub-save-chip.spec.ts` SC-1b mit eigener `placements.rows`, Netzwerk-Zähler 0, `placements` vorher = nachher.

- **AC-7:** Given ein Trip, bei dem die gefühlte Temperatur (wind_chill) in der Tabelle für SMS angehakt ist / When die Kurz-SMS erzeugt wird / Then enthält sie den Wert der gefühlten Temperatur, und ohne Haken fehlt er.
  - Test: `kurzform-gefuehlte-temperatur-kind-mitnahme.spec.ts` S1, SMS-Teil über `placements.rows` statt `channel_active_metrics` (oder gestrichen, falls nicht ausdrückbar; Entscheidung im RED-Lauf, im Spec-Changelog zu vermerken).

- **AC-8:** Given ein Ortsvergleich mit eigener Ausblick-Stelle in der Tabelle / When der Nutzer eine Ausblick-Metrik auswählt bzw. wieder abwählt / Then zeigt die Ausblick-Auswahl genau den gespeicherten Stand der Tabelle, auch nach dem Neuladen.
  - Test: `compare-outlook-metric-selection.staging.spec.ts`, Bestand über `placements` (Ausblick-Stelle plus `outlook_reports`) statt über `outlook_metrics`.

- **AC-9:** Given Prüfungen, die nur tote Altfeld-Saat oder einen Helfer ohne Aufrufer enthielten / When die Prüfungen laufen / Then sind sie weiterhin grün und prüfen dasselbe wie zuvor, nur ohne die wirkungslose Saat; Prüfungen, die nichts mehr prüften, sind ersatzlos entfernt.
  - Test: `hub-wetter-metriken-speichert-selbst`, `compare-hourly-metric-order`, `hub-konfliktschutz-zwei-kontexte`, `s3b2795-zustellung.helpers.ts`, `compare-uebersicht-kanal.helpers.ts` (`gespeicherteKanalAuswahl` entfernt), `compare-uebersicht-kanal-persistenz.staging.spec.ts`; Lauf grün, Vergleichstabellen im Staging unverändert.

- **AC-10:** Given die bewusst bleibenden Abwesenheits-Prüfungen (Trip- und Vergleich-Anlegen, Layout-Reiter, Zustellung) / When ihre Saat und Kommentare durchgesehen werden / Then bleiben sie unverändert wirksam, und der veraltete Kommentar in `hub-anlegen-ablauf.spec.ts` (Z.430-432) beschreibt den heutigen Zustand.
  - Test: `feat-3297-trip-ohne-altfelder`, `layout-tab-vergleich`, `vergleich-anlegen-was-steht-wo-3306`, `trip-anlegen-zustellung-3332` laufen unverändert grün.

- **AC-11:** Given jede umgestellte Prüfung / When die Karte oder der Speicherweg absichtlich falsch gemacht wird (Mutationsprobe: falscher Haken in der Karte, Tabelle verliert eine erwartete Ausgabe, Speichern überschreibt ein fremdes Feld, Altfeld wird mitgesendet) / Then wird genau diese Prüfung rot; es gibt keine Abschwächung gegenüber dem bisherigen Schutz.
  - Test: Adversary-Mutationsprobe je Prüfung per String-Ersetzung mit externer Sicherungskopie, Ergebnis je Prüfung im Validator-Bericht; kein Mock-Theater.

- **AC-12:** Given der gesamte Ordner `frontend/e2e` / When nach den zehn Altfeldern gesucht wird (`channel_layouts`, `channel_layouts_per_report`, `channel_active_metrics`, `outlook_metrics`, `outlook_metric_formats`, `hourly_metrics`, `hourly_metric_formats`, `show_outlook`, `multi_day_trend_reports`, `outlook_enabled`) / Then säet oder vergleicht keine Prüfung mehr eines davon, ausgenommen die bewusst bleibenden Abwesenheits-Prüfungen (A/D), die nur nachweisen, dass das Feld fehlt.
  - Test: Durchsuchung von `frontend/e2e` nach den zehn Namen; jeder Treffer ist eine Abwesenheits-Prüfung oder ein Kommentar ohne Wirkung (als Wächter im Validator-Lauf dokumentiert). Reiner Zusatznachweis (Dateiinhalt), kein Verhaltensnachweis; die Wirkung belegen AC-1 bis AC-11.

- **AC-13:** Given die Golden-C-Dateien im Prüf-Ordner der Python-Tests / When die Umstellung abgeschlossen ist / Then sind `golden_c.json` und `erwartung_golden_c.json` Byte für Byte unverändert, und die Python-Tests, die sie nutzen (Golden-Tests, Drift-Test), laufen weiter grün.
  - Test: `git diff` auf beide Dateien leer; `tests/test_erwartungsdatei_drift_einstellung_gleich_auslieferung.py` und `tests/test_placements_tabelle_jede_metrik.py` grün. Der Unverändert-Abgleich ist Zusatznachweis; Verhaltensnachweis sind die Python-Tests.

## Known Limitations

- Restlücke bei AC-10: Zeigen Karte und Server gemeinsam zu viele Haken, fängt das nur Python (Golden-Tests). Je Kanal eigene Folgen sind in "Was steht wo" nicht ausdrückbar, daher Teilmengen-Prüfung wie auf Python-Seite.
- Go reicht die Altfelder weiter durch (bewusst, #3277); "Altfeld bleibt unberührt" wäre grün, schützt aber nichts, deshalb entfällt es.
- Staging-Prüfungen laufen nur in `/e2e-verify`, nicht in CI.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testarbeit; folgt der bestehenden Entscheidung #3277/#3122 (Wahrheit allein in `placements`). Verworfene Alternativen für AC-10: (b) eigene Fixture (prüft nicht mehr Golden C), (c) nur Teilmenge (zu schwach).

## Changelog

- 2026-11-25: Initial spec created
