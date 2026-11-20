---
entity_id: feat_3228_windrichtung_mail
type: feature
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: feat-3228-windrichtung-mail
epic_spec: docs/specs/modules/feat_3222_windrichtung.md
issue: 3228
tags: [ampel, windrichtung, gegenwind, mail, briefing, ortsvergleich]
---

# Windrichtung in der Mail färben (Scheibe S2 von Epic #3222)

## Approval

- [ ] Approved

## Purpose

Bisher steht die Windrichtung in der Mail nur als Zahl oder Kompassbuchstabe, ohne Farbe. Diese Scheibe färbt sie in der Briefing-Mail (Trip) und in der Vergleichs-Mail (Ortsvergleich) nach der normalen Ampel: im Trip, wenn der Wind den Radfahrer bremst (Gegenwind), im Ortsvergleich, wenn der Wind aus einer vom Nutzer markierten, unerwünschten Himmelsrichtung kommt. Rückenwind, Seitenwind und schwacher Wind bleiben ungefärbt.

Diese Spec leitet sich aus der freigegebenen Epic-Spec `docs/specs/modules/feat_3222_windrichtung.md` ab (Issue #3228, Scheibe S2). Der Fachkern (Gegenwind-Rechnung, Peilung, Modell, Validierung) liegt seit S1 auf main; hier wird er erstmals an die Mail angeschlossen. Kontext und Analyse: `docs/context/feat-3228-windrichtung-mail.md`, Epic-Kontext `docs/context/feat-3222-windrichtung.md`.

## Source

- **File:** `src/app/ampel.py`, `src/services/windrichtung.py`, `src/output/renderers/trip_report.py`, `src/output/renderers/email/helpers.py`, `src/output/renderers/email/html.py`, `src/output/renderers/email/compare_html.py`
- **Identifier:** `AMPEL_ABGELEITET` (neu), `schwellen_aus_ampel`, Zeilenwert-Helfer in `windrichtung.py` (neu), `_dp_to_row`, `fmt_val`, `_row_risk`, Zelltönung `ampel_level`

> **Schicht-Hinweis:** Alles liegt im Python-Core (`src/`). Keine Änderung an Go-API oder Frontend (Editor folgt in S4). Validatoren liegen unter `.claude/hooks/`.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Beide Mail-Pfade nutzen denselben Wert-Helfer in `windrichtung.py` und dieselbe Ampel-Auflösung; nur die Tabellenzelle (Briefing-Tabelle bzw. Vergleichstabelle) ist je Mail-Template eigen. Kein neues Pendant-Bauteil.
> - **Mandantentrennung:** Die Einstellung kommt je Nutzer aus `display_config.ampel`; `user_id` aus dem Auth-Kontext, nie `"default"`. Test mit zwei verschiedenen Nutzern (AC-9).
> - **Kanäle (ADR-0095):** S2 betrifft ausschließlich die E-Mail. Telegram, SMS und Premium-SMS bleiben in S2 byte-gleich; sie ziehen in S3 nach (Epic-Plan, Entscheidung 9). Die Kanalparität ist damit erst mit S3 hergestellt; bis dahin ist das Feature nur für Nutzer sichtbar, die ihn in der Mail einschalten (Radtour-Vorlage oder Ortsvergleich mit Sektoren).

## Estimated Scope

- **LoC:** ca. 110 Code (Budget 200, hartes Maximum 250); Tests, Doku und Validatoren zählen nicht
- **Files:** 6 Quelldateien, 2 Validatoren, 1 bis 2 neue Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services/windrichtung.py` (`wind_unerwuenscht_kmh`, `segment_peilung_deg`) | module | Aus S1; liefert den km/h-Wert aus Modus, Sektoren, Windstärke, Herkunft und Peilung |
| `utils/geo.py` (`bearing_deg`, `mean_direction_deg`) | module | Aus S1; Peilung und Winkelmittel |
| `app/ampel.py` (`resolve_ampel`, `schwellen_aus_ampel`, `hat_ampel`, `schlimmster_index`) | module | Ampel-Auflösung; `schwellen_aus_ampel` liest zusätzlich `AMPEL_ABGELEITET` |
| `output/metric_format.py` (`severity_from_thresholds`) | module | Bleibt UNVERÄNDERT (ADR-0106) |
| `output/renderers/trip_report.py`, `email/helpers.py`, `email/html.py`, `email/compare_html.py` | module | Zeilenbau, Stufen-Helfer, Zelltönung Briefing und Vergleichstabelle |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py` | tooling | Prüfung gegen echt zugestellte Staging-Mail (Renderer-Gate) |
| `tests/tdd/test_issue_811_mode_matrix.py` | test | Mail-Modus-Matrix; muss für Alt-Trips grün und unverändert bleiben |
| ADR-0095, ADR-0106, ADR-0126 | adr | Kanalparität, Ampel als einzige Bewertung, Windrichtung als abgeleitete Ampelgröße |

## Scope

**Drin (S2):**
- Färbung der Wind-Zelle (Standard, Kompass in der Wind-Zelle) bzw. der eigenen WDir-Spalte (Roh-Modus) in der Briefing-Mail nach dem Gegenwind-Wert je Etappe und Stunde.
- Färbung der WDir-Zelle in der Vergleichs-Mail nach dem Wind aus markierten Himmelsrichtungen je Ort (Übersicht und Stundentabelle).
- Gemeinsamer Wert-Helfer in `src/services/windrichtung.py` für beide Mail-Pfade; `AMPEL_ABGELEITET` in `src/app/ampel.py`.
- Erweiterung der beiden Mail-Validatoren gegen echt zugestellte Staging-Mail.

**Nicht drin (spätere Scheiben):**
- Modellfelder `wind_unerwuenscht_kmh` an `SegmentWeatherSummary`/`LocationResult`, `AMPEL_LESER`/`hat_ampel`-Ausbau, Alarm, Telegram, SMS, Premium-SMS (S3).
- Editor-Oberfläche für Modus und Himmelsrichtungen (S4).
- Nachtblöcke ohne Etappenbezug im Modus Gegenwind.

## Definition of Done

- Alle Acceptance Criteria AC-1 bis AC-11 durch Kern-Tests in `tests/tdd/test_feat_3228_*.py` grün nachgewiesen, Adversary mit Mutations-Gegenprobe VERIFIED.
- Mail-Modus-Matrix (`tests/tdd/test_issue_811_mode_matrix.py`) frisch grün, Alt-Trips ohne `modus` byte-gleich.
- `briefing_mail_validator.py` (Radtrip mit Gegenwind gefärbt) und `email_spec_validator.py` (Ortsvergleich Nordsektor gefärbt, Südwind-Ort ungefärbt) gegen echt zugestellte Staging-Mail mit Exit 0.
- Telegram-, SMS- und Premium-SMS-Ausgaben in den bestehenden Tests unverändert.
- Ausgeliefert auf Produktion, Selftest Exit 0, Issue #3228 geschlossen; Epic #3222 bleibt offen.

## Implementation Details

**Grundidee.** Die Spaltenanzeige der Windrichtung bleibt Grad bzw. Kompassbuchstabe. Gefärbt wird aber nach dem abgeleiteten km/h-Wert (`wind_unerwuenscht_kmh`), nicht nach Grad. Dieser Wert wandert stundenweise als Seitenkanal in die Zeile (`row["_wind_unerwuenscht_kmh"]`, analog zum vorhandenen `_wind_dir_deg`) und wird nur gesetzt, wenn der Modus nicht `aus` ist und ein Wert bestimmbar ist. Damit bleibt jede Mail ohne Windrichtungs-Einstellung strukturell unverändert.

**Gemeinsame Quelle.** Ein neuer Zeilen-Helfer in `src/services/windrichtung.py` (Eingabe: Ampel, Datenpunkt, Peilung; Ausgabe: km/h-Wert oder nichts) wird von beiden Zeilenpfaden genutzt (`trip_report._dp_to_row` und der Ortsvergleich). Die Peilung wird einmal je Segment berechnet (`segment_peilung_deg`) und beim Zeilenbau durchgereicht.

**Ampel-Zugriff ohne Leck in die Kurzkanäle.** `AMPEL_LESER` wird in S2 nicht erweitert. Stattdessen gibt es `AMPEL_ABGELEITET = {"wind_direction"}`; `schwellen_aus_ampel` liest `AMPEL_LESER | AMPEL_ABGELEITET`, `hat_ampel` bleibt unverändert (gibt für `wind_direction` weiter `False`).

**Merge-Fall (Standard).** Im Standard steht der Kompass in der Wind-Zelle (`should_merge_wind_dir`). Dann erhält die Wind-Zelle die höhere der beiden Stufen: Windstärke gegen Gegenwind/Sektor, nicht addiert. Das gilt einheitlich für Zellfarbe, Ampelpunkt (`fmt_val`) und Zeilenpunkt (`_row_risk`). Beispiel: Wind 25 km/h ergibt gelb, Gegenwindanteil 25 km/h ergibt orange, die Zelle ist orange.

**Roh-Modus.** Gibt es eine eigene WDir-Spalte, wird diese über den `wind_dir`-Zweig getönt, mit dem abgeleiteten km/h-Wert statt dem Gradwert.

**Ortsvergleich.** Der Wert wird live aus den Stundendaten des Ortes gebildet (Muster `_daily_summary` in `compare_html.py`); die Vergleichs-Engine kennt keine Ampel und bleibt unberührt. Es gibt nur `aus` oder `sektoren`. Erbt ein Ortsvergleich über die Vorlage `radtour` den Modus `gegenwind`, ergibt sich ohne Peilung kein Wert und damit keine Färbung.

**Gemessener Wert nach der Spalte.** Die Zelle zeigt weiterhin die Himmelsrichtung bzw. Grad; die Farbe sagt nur "für Sie ungünstig" in der Ampelsprache.

### Abweichungen von der Epic-Spec (technisch begründet)

1. **Kein Ausbau von `AMPEL_LESER`/`hat_ampel` in S2.** Die Epic-Spec sieht eine Erweiterung von `AMPEL_LESER` um `wind_direction` vor. Das würde alle Kurzkanäle (`narrow.py` mit `@h`, Tokens, Telegram) mitbetreffen, die mit dem Spaltenwert in Grad gegen km/h-Grenzen prüfen (350 Grad würde rot). Stattdessen `AMPEL_ABGELEITET`; die Kurzkanäle werden in S3 mit dem abgeleiteten Wert angeschlossen.
2. **Keine Modellfelder in S2.** `SegmentWeatherSummary.wind_unerwuenscht_kmh` und das Pendant in `LocationResult` entfallen hier und wandern nach S3, wo der Alarm sie braucht. Die Mail-Zellen sind Stundenzeilen; der Wert wird stundenweise im Renderer gebildet.
3. **`narrow.py` wandert nach S3.** Die Kurzform wirkt in S2 nicht auf die Mail und bleibt unverändert.
4. **Nachtblöcke ohne Segment** (`aggregate_night_block`) haben keine Fahrtrichtung: im Modus `gegenwind` kein Wert, also keine Färbung (bekannte Lücke, S3). Im Modus `sektoren` wäre ein Wert möglich, wird aber in S2 nicht umgesetzt.
5. **Exposition (Epic-AC-15):** Die Wind-Exposition wirkt nicht auf die Mail; deshalb wird in S2 nur abgesichert, dass die Zelle das Maximum der Ampelstufen zeigt und nichts addiert wird.

## Expected Behavior

- **Input:** Ampel-Einstellung `wind_direction` (Modus, Sektoren, Grenzen) des Nutzers, stündliche Winddaten (Richtung, Stärke), Segment-Geometrie (Trip) bzw. Orts-Stundendaten (Ortsvergleich).
- **Output:** Briefing-Mail und Vergleichs-Mail mit in Ampelfarbe getönter Wind- bzw. WDir-Zelle bei Gegenwind oder unerwünschter Himmelsrichtung ab der gelben Grenze; sonst unverändert.
- **Side effects:** Keine. Es werden keine Daten geschrieben, kein Modellfeld hinzugefügt, keine Kurzkanäle verändert.

## Test Plan

### Automated Tests (TDD RED)

Kern-Tests ohne Mock-Theater in `tests/tdd/test_feat_3228_*.py` (echte Renderer-Aufrufe mit echten Datenobjekten, deterministisch, ohne Netz):

- [ ] Test 1: GIVEN Rad-Trip (Vorlage `radtour`), Segment nach Norden, Wind 25 km/h aus N WHEN Briefing-HTML gerendert THEN Wind-/WDir-Zelle in Orange
- [ ] Test 2: GIVEN gleiche Etappe, Wind aus S bzw. aus O WHEN gerendert THEN Zelle ungefärbt
- [ ] Test 3: GIVEN Nordwind 5 km/h bzw. 10 km/h WHEN gerendert THEN ungefärbt bzw. gelb
- [ ] Test 4: GIVEN Rundkurs-Segment unter 300 m Luftlinie, 40 km/h Wind WHEN gerendert THEN ungefärbt, Nachbarsegment mit Gegenwind gefärbt
- [ ] Test 5: GIVEN Ortsvergleich mit Sektor N, Ort A Nordwind 30 km/h, Ort B Südwind 30 km/h WHEN Vergleichs-HTML gerendert THEN A gefärbt, B ungefärbt
- [ ] Test 6: GIVEN Ortsvergleich, der Modus `gegenwind` aus Vorlage `radtour` erbt WHEN gerendert THEN keine Färbung der Windrichtung (F002)
- [ ] Test 7: GIVEN Alt-Trip ohne `modus` WHEN gerendert THEN HTML byte-gleich zum Stand vor der Änderung
- [ ] Test 8: GIVEN Nutzer A mit `gegenwind` und Nutzer B mit `aus`, gleiche Etappe, gleiche Daten WHEN beide Briefings gerendert THEN A gefärbt, B ungefärbt (F003)
- [ ] Test 9: GIVEN Standard-Merge (Kompass in der Wind-Zelle), Windstärke gelb, Gegenwind orange WHEN gerendert THEN Zelle orange; bei Windstärke rot und Gegenwind gelb rot; Stufe nie höher als das Maximum
- [ ] Test 10: GIVEN Roh-Modus mit eigener WDir-Spalte, Wind aus N 25 km/h bei Nordkurs WHEN gerendert THEN WDir-Zelle nach km/h gefärbt (orange), nicht nach Grad (Wind aus 350 Grad ohne Gegenwind bleibt ungefärbt)
- [ ] Test 11: GIVEN `hat_ampel(..., "wind_direction")` WHEN geprüft THEN weiterhin `False` und `narrow`/SMS-Ausgabe für denselben Trip byte-gleich

Bestehende Gates, die grün und unverändert bleiben müssen: `tests/tdd/test_issue_811_mode_matrix.py` (frisch, sha-gebunden), `tests/test_briefing_modus_matrix_sprachen.py`, `test_channel_metric_matrix.py`, `test_compare_katalog_schwellen.py`, i18n-Wächter.

### Validatoren gegen echt zugestellte Staging-Mail

- `.claude/hooks/briefing_mail_validator.py`: erweitert um die Tönungsprüfung der Wind-Zelle des Rad-Trips (Nordwind orange, Südwind/Ostwind ungefärbt, 5 km/h ungefärbt, Rundkurs ungefärbt).
- `.claude/hooks/email_spec_validator.py`: erweitert um die Zellprüfung im Ortsvergleich (Skiort gefärbt, Vergleichsort ungefärbt).
- Exit 0 beider Validatoren gegen eine echt zugestellte Staging-Mail im Stalwart-Test-Postfach (kein Mock) ist Voraussetzung für das Renderer-Commit-Gate.

## Acceptance Criteria

- **AC-1:** Given ein Rad-Trip mit Vorlage `radtour` und einer nach Norden führenden Etappe / When die Briefing-Mail bei 25 km/h Wind aus Norden zugestellt wird / Then ist die Wind-Zelle der Etappe (mit der Windrichtung) in Orange gefärbt, entsprechend der Gegenwindkomponente von 25 km/h. (Bezug: Epic AC-1)
  - Test: Zugestellte Staging-Mail des Rad-Trips (Briefing-Validator): Wind-/WDir-Zelle trägt die Ampelfarbe orange.

- **AC-2:** Given dieselbe Rad-Etappe nach Norden / When der Wind mit 25 km/h aus Süden weht (Rückenwind) oder rein von der Seite kommt (Ostwind) / Then bleibt die Windrichtungs-Färbung aus, und die Anzeige der Zelle ist unverändert. (Bezug: Epic AC-2)
  - Test: Zugestellte Mail bei Südwind und bei Ostwind: Zelle ohne Richtungs-Ampelfarbe, Anzeige unverändert.

- **AC-3:** Given dieselbe Etappe mit Gegenwind-Richtung / When die Windstärke nur 5 km/h beträgt (unter der gelben Grenze von 10 km/h) / Then bleibt die Zelle ungefärbt; bei 10 km/h wird sie gelb. (Bezug: Epic AC-3)
  - Test: Zugestellte Mail bei 5 km/h Nordwind: keine Färbung; bei 10 km/h Nordwind: gelb.

- **AC-4:** Given ein Rundkurs-Segment, dessen Start und Ende weniger als 300 m auseinanderliegen / When starker Wind (40 km/h) weht / Then wird die Windrichtung dieses Segments nicht gefärbt, weil keine Fahrtrichtung bestimmbar ist, während ein angrenzendes Streckensegment mit Gegenwind gefärbt bleibt. (Bezug: Epic AC-5)
  - Test: Zugestellte Mail für Rundkurs-Segment bei 40 km/h Wind: keine Richtungsfärbung; angrenzendes Segment mit Gegenwind gefärbt.

- **AC-5:** Given ein Ortsvergleich mit markiertem Sektor N und ein Skiort mit 30 km/h Nordwind / When die Vergleichs-Mail zugestellt wird / Then ist die Windrichtungs-Zelle dieses Ortes entsprechend der Schwellen gefärbt, und ein Ort mit Südwind gleicher Stärke bleibt ungefärbt. (Bezug: Epic AC-6)
  - Test: Zugestellte Staging-Mail des Ortsvergleichs (Vergleichstabelle, `email_spec_validator.py`): Zelle Skiort gefärbt, Vergleichsort ungefärbt.

- **AC-6:** Given ein bestehender Trip ohne Feld `modus` in `ampel.metrics.wind_direction` (nicht Vorlage `radtour`) / When das Briefing nach dem Update zugestellt wird / Then ist die Mail inhaltlich identisch zu vorher, und die gespeicherte Konfiguration ist unverändert. (Bezug: Epic AC-8)
  - Test: Gerenderte Mail vor und nach der Änderung bei gleichen Wetterdaten ohne Unterschied; Modus-Matrix `test_issue_811_mode_matrix.py` grün und unverändert; gespeicherte Trip-Datei ohne neue Felder.

- **AC-7:** Given eine Etappe, bei der zugleich Windstärke und Gegenwind bewertet werden (Standardfall: Kompass steht in der Wind-Zelle) / When das Briefing gerendert wird / Then zeigt die Zelle die höhere der beiden Stufen, nicht eine addierte oder höhere Stufe; Zellfarbe, Ampelpunkt und Zeilenpunkt stimmen überein. (Bezug: Epic AC-15)
  - Test: Briefing mit Windstärke gelb und Gegenwind orange ergibt Zelle orange; Windstärke rot und Gegenwind gelb ergibt rot; nie höher als das Maximum beider Einzelstufen.

- **AC-8:** Given ein Ortsvergleich, der den Modus `gegenwind` über die Vorlage `radtour` erbt / When die Vergleichs-Mail gerendert wird / Then gibt es keine Windrichtungs-Färbung, weil Orte keine Fahrtrichtung haben, und es kommt kein Fehler. (Bezug: Zusatz, F002 aus S1)
  - Test: Vergleichs-Mail mit geerbter Vorlage `radtour` und 30 km/h Wind: Zelle ungefärbt, Mail wird vollständig erzeugt.

- **AC-9:** Given zwei verschiedene Nutzer, A mit Modus `gegenwind` und B mit Modus `aus`, jeweils mit derselben Etappe und denselben Winddaten / When beide ihr Briefing gerendert bekommen / Then ist das Briefing von A gefärbt und das von B ungefärbt, und keiner sieht die Einstellung des anderen. (Bezug: Zusatz, Epic AC-10-Teil, F003 aus S1)
  - Test: Zwei Briefings mit je eigener Nutzer-Einstellung aus dem Auth-Kontext: A orange, B ohne Richtungsfärbung; die Prüfung scheitert, wenn die Einstellung nutzerübergreifend gelesen wird.

- **AC-10:** Given ein Trip mit eigener WDir-Spalte (Roh-Modus, Kompass nicht in der Wind-Zelle) und Gegenwind von 25 km/h / When die Mail gerendert wird / Then wird die WDir-Zelle nach dem abgeleiteten km/h-Wert gefärbt und nicht nach der Gradzahl, sodass ein Wind aus 350 Grad ohne Gegenwind ungefärbt bleibt. (Bezug: Zusatz, Roh-Modus)
  - Test: Roh-Modus-Briefing: WDir-Zelle bei Nordkurs und Nordwind orange, bei Südwind (Gradzahl 180) und bei 350 Grad ohne Gegenwindanteil ungefärbt.

- **AC-11:** Given derselbe Trip mit Gegenwind / When Telegram, SMS und Premium-SMS in S2 gerendert werden / Then sind sie byte-gleich zum Stand vor S2, weil sie erst in S3 nachziehen, und `hat_ampel` meldet für die Windrichtung weiterhin keine Ampel. (Bezug: Zusatz, Kanalparität ADR-0095)
  - Test: Gerenderte Kurzkanal-Ausgaben vor und nach der Änderung identisch; `hat_ampel(..., "wind_direction")` ist `False`.

## Known Limitations

- Nur E-Mail: Telegram, SMS, Premium-SMS und Alarm folgen in S3; bis dahin sind die Kanäle in diesem Punkt nicht gleichwertig (bewusste Reihenfolge laut Epic-Plan).
- Nachtblöcke ohne Segment haben im Modus `gegenwind` keinen Wert und bleiben ungefärbt.
- Im Standard-Merge-Fall ist die Färbung der Wind-Zelle nicht einer einzelnen Ursache zuzuordnen (Windstärke oder Gegenwind); die Zelle zeigt die höhere der beiden Stufen.
- Segment-Peilung ist Luftlinie Start zu Ende (Grenze 300 m); bei Serpentinen oder sehr langen Segmenten grob.
- Der Ortsvergleich kennt kein Gegenwind; ein geerbter Modus `gegenwind` bleibt dort wirkungslos.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0126 (aus S1, keine neue Entscheidung)
- **Rationale:** Diese Scheibe setzt ADR-0126 (Windrichtung als abgeleitete Ampelgröße, Richtung wird vor der Ampel zu einem Skalar reduziert) in der Mail um und ändert `severity_from_thresholds` nicht (ADR-0106). Die technischen Abweichungen von der Epic-Spec (`AMPEL_ABGELEITET` statt `AMPEL_LESER`, Modellfelder in S3) betreffen die Reihenfolge der Umsetzung, nicht die Entscheidung, und brauchen daher kein eigenes ADR.

## Changelog

- 2026-11-20: Initial spec created (Scheibe S2 von Epic #3222, Issue #3228)
