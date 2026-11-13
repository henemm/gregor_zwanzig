---
entity_id: paritaets_bestandsaufnahme
type: module
created: 2026-11-13
updated: 2026-11-13
status: draft
version: "1.0"
tags: [paritaet, bestandsaufnahme, tests, issue-1986]
workflow: feature-1986-paritaets-bestandsaufnahme
---

# Paritaets-Bestandsaufnahme (Issue #1986)

## Approval

- [ ] Approved

## Purpose

Bestandsaufnahme aller Paritaets-Tests des Repos: Welche Paare von Code-Stellen werden durch Tests gleichgehalten, und welche dieser Doppelungen sollten zu einem Baustein zusammengefuehrt werden. Das Ergebnis ist eine priorisierte Liste im Body von Issue #1986; Produktivcode wird nicht geaendert (AC-5 des Issues).

## Source

- **File:** GitHub-Issue #1986 (Body); Test-Kopfzeilen in den "begruendet getrennt"-Paritaetstests; neuer Prueftest `tests/unit/test_paritaet_begruendung_marker.py`
- **Identifier:** Marker `PARITAET-BEGRUENDUNG:`

> **Schicht-Hinweis:** Kein Frontend-, Go- oder Python-Produktivcode betroffen. Es gibt nur Kommentar-Kopfzeilen in vorhandenen Tests (Python `tests/`, Go `internal/**/*_test.go`, TypeScript `frontend/`) und einen neuen Python-Prueftest.
> Trip/Compare-Teilung, Mandantentrennung und Kanaele sind nicht beruehrt (reine Doku-/Testkommentare; Pendant-Sperre greift nicht, da keine neue Komponente entsteht).

## Estimated Scope

- **LoC:** ca. +150 (Kommentare) plus ca. 60 (Prueftest)
- **Files:** ca. 25 Testdateien (nur Kommentar) plus 1 neuer Test; 0 Produktivdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Issue #1986 | GitHub-Issue | Ziel der Liste (Read-Modify-Write, Text und ACs bleiben) |
| #2277, #2278, #2279, #2280, #2284, #2285, #2288 | GitHub-Issues | bestehende Folge-Issues, werden verlinkt statt doppelt angelegt |
| #1197, Epic #1230 | GitHub-Issues | Klon-Detektor-Entscheidung, uebergeordnetes Epic |
| #1481 (Pendant-Sperre), #1406 B (Vokabular-Ratsche) | Gates | bestehende Schutzmechanismen, unveraendert |
| #1982, #1911, #1480, #1848, #2961 | GitHub-Issues | Startpunkte aus dem Issue, werden in der Liste eingeordnet |

## Implementation Details

**1. Zaehler-Beleg.** Das Issue sagt "zwoelf", tatsaechlich sind es ca. 65 Paritaets-Testdateien (Python 35, Go 13, Frontend 17), zusammengefasst ca. 45 Paare. Beleg-Befehle, die in den Issue-Body kommen:
`git ls-files | grep -iE 'parit|parity'` (118 Treffer inkl. Doku und Fixtures) und `grep -rliE 'parit' internal --include=*_test.go` (Go-Funde ohne passenden Dateinamen). Der Titel "zwoelf" ist ueberholt und wird im Body vermerkt.

**2. Liste je Paar.** Jedes Paar bekommt `Datei:Zeile` beidseitig, die bewachenden Tests und ein Verdikt: zusammenfuehrbar / begruendet getrennt. Kein Verdikt bleibt "unklar" (siehe 5).

**3. Priorisierung der zusammenfuehrbaren Paare.**
- high: Alarm- und Versandpfade (OnsetEvent-Bau `notification_service.py:1932` gegen `alert/project.py:645`; Vorschau gegen Versand `preview_service.py` gegen `trip_report_scheduler.py`; Ortsformatierer `official_alerts.py:887, 2464` gegen `segments.py:94`; Segmentbestimmung #1982 Rest; `compare_alert_preview_service.py:38` gegen `notification_service.py`).
- medium: Frontend-Kopien (`TAB_DEFS` `TripNewEditor.svelte:116` gegen `CompareNewEditor.svelte:221`; Standardwerte-Ergaenzer `tripNewLogic.ts:309` gegen `VersandTab.svelte`; Ampel TS gegen Python; `COMPARE_METRIC_KEYS`; Kanalfunktionen) sowie Klartext-Labels `comparison.py` gegen `compare_html.py:1703`, Trip- gegen Vergleichs-Metriken, Go `kind_required`, `alert_metric_channels`, Drift `ValidEntityIDRe` (#2961).
- low: `formatHHMM` in TS, Python und Go (geringer Gewinn).

**4. Marker fuer "begruendet getrennt".** Jede Testdatei, die in der Liste als begruendet getrennt gefuehrt wird, bekommt in der Kopfzeile einen Kommentar `PARITAET-BEGRUENDUNG: <Begruendung in einem Satz>` (Python `#`, Go `//`, TypeScript `//`). Ein deterministischer Prueftest liest die Liste der begruendet getrennten Dateien (feste Liste im Test) und stellt sicher, dass jede den Marker mit nichtleerer Begruendung traegt. Der Test ist ein Dateiinhalt-Check und traegt deshalb den Marker `# doc-compliance-test` (erlaubte Ausnahme, weil das Verhalten "Begruendung vorhanden" selbst Dokumentation ist).

**5. Entscheidung der fuenf Unklar-Faelle (technisch, nach Stichprobe gegen den Code).**
- `test_briefing_parity_night_thunder` (`html.py` gegen `plain.py`): begruendet getrennt, Kanal gegen Kanal, die Renderer sind je Kanal eigene Ausgabeformen.
- `test_channel_origin_guard_parity`: begruendet getrennt, Kanal gegen Kanal.
- `hub-anlegen-paritaet-flaechen.spec.ts`: begruendet getrennt, Rahmen ist bereits geteilt, Test ist Regressionswaechter.
- `briefing_route_get_lock_etag_test.go`: begruendet getrennt, Go-Route gegen Python-Verhalten in zwei Prozessen, Fixture ist der Zwang.
- `standardwerte_payload_paritaet_compare.test.ts`: zusammenfuehrbar (medium), haengt am Standardwerte-Ergaenzer `tripNewLogic.ts:309`.

**6. Folge-Issues.** Je zusammenfuehrbarem Paar ein Issue mit Label `priority:high|medium|low`. Existiert schon eines (#2277, #2278, #2279, #2280, #2284, #2285, #2288), wird es in der Liste verlinkt, nicht neu angelegt.

**7. Stichprobenpruefung.** Vor dem Eintrag werden die Verdikte der Lese-Agenten gegen den Code geprueft. Bereits bestaetigt: `select_active_segment` (`trip_segments.py:437`), `ValidEntityIDRe` (`internal/store/pathsafe.go:64`) und `VALID_ENTITY_ID_RE` (`src/app/loader.py:1334`) existieren an den genannten Stellen; Name-taeuscht-Faelle (`btn-feature-parity.spec.ts`, `test_702_alerts_mobile_parity.py`, `test_alert_preview_compare_paritaet_drossel_frei.py`, `test_stage_weather_parity.py`) sind keine Doppelung und stehen als solche in der Liste.

**8. Ergebnis-Ort.** Nur im Body von #1986 per Read-Modify-Write (Body lesen, Abschnitt anhaengen, Rest unveraendert); keine Datei im Repo.

## Scope

In Scope: Liste aller Paritaets-Tests und Doppelungen im Body von #1986, Verdikte, Marker-Kopfzeilen in Tests, Prueftest, Folge-Issues.
Nicht in Scope: Sanierung der Doppelungen, Klon-Detektor (#1197), Ortsvergleich-Umbau (#1374), jeder Produktivcode.

## Definition of Done

- Liste im Issue-Body mit Zaehler-Beleg, Datei:Zeile beidseitig und Verdikt je Paar (AC-1, AC-2)
- Marker `PARITAET-BEGRUENDUNG:` in allen "begruendet getrennt"-Tests, Prueftest gruen (AC-3)
- Folge-Issue je zusammenfuehrbarem Paar mit `priority:*` (AC-4)
- Kein Produktivcode geaendert (AC-5)

## Test Plan

- Deterministischer Prueftest `tests/unit/test_paritaet_begruendung_marker.py` (`# doc-compliance-test`) mit Gegenprobe ohne Marker (AC-3)
- Zaehlerabgleich Beleg-Befehl gegen Liste (AC-1), Durchsicht Verdikte (AC-2), Abgleich gegen `gh issue list` (AC-4), Diff-Pruefung auf Testpfade (AC-5)

## Expected Behavior

- **Input:** Alle Paritaets-Testdateien (Python, Go, Frontend) und der Code der bewachten Paare.
- **Output:** Aktualisierter Body von #1986 mit Zaehler-Beleg, priorisierter Liste, Verdikten; Folge-Issues; Marker-Kopfzeilen; gruener Prueftest.
- **Side effects:** Nur Kommentaraenderungen in Tests; Doppelungen ausserhalb der Tests (Startpunkte aus dem Issue) werden ebenfalls in die Liste eingetragen.

## Acceptance Criteria

- **AC-1:** Given das Repo mit allen Paritaets-Testdateien in Python, Go und Frontend / When der Beleg-Befehl `git ls-files | grep -iE 'parit|parity'` plus die Go-Suche ausgefuehrt wird / Then enthaelt die Liste im Issue-Body jede gefundene Testdatei mit Datei:Zeile beider Seiten des Paares und der echten Menge (ca. 65 Dateien, ca. 45 Paare) statt "zwoelf"
  - Test: Zaehlerabgleich: jede vom Beleg-Befehl gelieferte Testdatei kommt in der Liste vor oder ist als "Name taeuscht" ausgewiesen.

- **AC-2:** Given die vollstaendige Liste der Paare / When jedes Paar bewertet wird / Then traegt jedes ein Verdikt "zusammenfuehrbar" oder "begruendet getrennt", und kein Paar bleibt "unklar", ausser es ist eine echte Produktfrage
  - Test: Durchsicht der Liste: kein Eintrag mit Verdikt "unklar"; die fuenf frueheren Unklar-Faelle sind entschieden.

- **AC-3:** Given eine Testdatei mit Verdikt "begruendet getrennt" / When der Prueftest laeuft / Then traegt die Datei in der Kopfzeile den Kommentar `PARITAET-BEGRUENDUNG:` mit nichtleerer Begruendung, und eine Datei ohne Marker laesst den Test scheitern
  - Test: `# doc-compliance-test`: deterministischer Prueftest ueber die feste Dateiliste; Gegenprobe mit entferntem Marker ist rot.

- **AC-4:** Given ein Paar mit Verdikt "zusammenfuehrbar" / When die Liste fertig ist / Then existiert dazu ein Folge-Issue mit Label `priority:high`, `priority:medium` oder `priority:low` (Alarm-/Versandpfade high, Frontend-Kopien medium, formatHHMM low), und bestehende Issues #2277 bis #2280, #2284, #2285, #2288 sind verlinkt statt doppelt angelegt
  - Test: Abgleich Liste gegen `gh issue list`: jedes zusammenfuehrbare Paar nennt genau eine Issue-Nummer; keine Dublette zu den genannten Issues.

- **AC-5:** Given der Stand von main vor und nach der Bestandsaufnahme / When die Aenderungen verglichen werden / Then ist kein Produktivcode geaendert (nur Test-Kommentare und der Prueftest), und der Body von #1986 enthaelt den urspruenglichen Text samt ACs unveraendert plus die neue Liste
  - Test: Diff-Pruefung: geaenderte Dateien liegen ausschliesslich unter Tests; Issue-Body-Vergleich zeigt nur angehaengten Text.

## Known Limitations

- Die Liste ist eine Momentaufnahme (Stand 2026-11-13); ein automatischer Klon-Detektor bleibt zurueckgestellt (#1197).
- Der Prueftest kennt nur die feste Dateiliste; neue Paritaetstests muessen bei der Aufnahme in die Liste eingetragen werden.
- Kopfzeilen-Edits in Tests koennen Test-/Pendant-Gates ausloesen; Doku-Ausnahme ist vorab zu pruefen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bestandsaufnahme und Kommentare, keine Entscheidungsflaeche (Kanaele, Provider, Datenmodell, Auth) beruehrt.

## Changelog

- 2026-11-13: Initial spec created
