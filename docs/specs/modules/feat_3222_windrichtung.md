---
entity_id: feat_3222_windrichtung
type: feature
created: 2026-11-20
updated: 2026-11-20
status: approved
version: "1.0"
workflow: feat-3222-windrichtung
tags: [ampel, windrichtung, gegenwind, alarm, kanaele]
---

# Windrichtung bewerten (Gegenwind / unerwünschte Himmelsrichtungen)

## Approval

- [x] Approved (2026-11-20, PO-Freigabe per AskUserQuestion: nur Gegenwind/unerwünschte Richtung bewerten)

## Purpose

Die Windrichtung wird bisher nur angezeigt (Spalte WDir, Token `WD:`), nie gefärbt und nie alarmiert. Dieses Feature macht sie bewertbar: im Trip als Gegenwind relativ zur Bewegungsrichtung der Etappe bzw. des Segments (Rad: Gegenwind kostet Kraft), im Ortsvergleich (optional auch im Trip) über markierte unerwünschte Himmelsrichtungen (Ski: Windrichtung als Kältefaktor). Ohne nennenswerte Windstärke gibt es keine Färbung.

Kontext und Fakten mit Datei:Zeile: `docs/context/feat-3222-windrichtung.md` (Abschnitte A-G). Konvention: `wind_direction_deg` ist die Richtung, AUS der der Wind kommt (0 = N, 90 = O; `src/app/models.py:113`).

## Source

- **File:** `src/app/ampel.py`, `src/app/ampel_templates.py`, `src/services/ampel_alarm.py`, `src/services/windrichtung.py` (neu), `src/utils/geo.py`
- **Identifier:** `resolve_ampel`, `_verschmelzen`, `deviation_count`, `AMPEL_LESER`, `AMPEL_FELDER`, `bearing_deg` (neu), `wind_unerwuenscht_kmh` (neu, abgeleitetes Feld)

> **Schicht-Hinweis:** Fachkern, Aggregat, Renderer und Alarm liegen im Python-Core (`src/`); Validierung der Form zusätzlich in der Go-API (`internal/handler/ampel.go`); Editor im SvelteKit-Frontend (`frontend/src/lib/components/...`). Es gibt keine Server-Templates für die UI.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Ein Baustein `molecules/RichtungsWahl.svelte` im gemeinsamen Reiter Wetter mit `context="route"|"vergleich"`. Kein Pendant, keine einseitige Neuanlage. Compare-eigen bleibt nur die Beschränkung der Modi (kein Gegenwind), gesteuert über den Kontext-Parameter.
> - **Mandantentrennung:** Einstellung liegt in `display_config.ampel` je Nutzer (`data/users/<user_id>/`). `user_id` aus dem Auth-Kontext, nie `"default"`. Test mit zwei verschiedenen Nutzern (AC-12).
> - **Kanäle:** E-Mail, Telegram, SMS, Premium-SMS benannt (siehe Entscheidung 6); Alarme erreichen alle konfigurierten Kanäle (ADR-0095).

## Estimated Scope

- **LoC:** ca. 720 Code gesamt, verteilt auf vier Scheiben je höchstens 250 LoC Code (Tests, Doku, Mockup zählen nicht)
- **Files:** ca. 28
- **Effort:** high (vier Scheiben, S1 bis S4 nacheinander)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app/ampel.py` (`resolve_ampel`, `_verschmelzen`, `deviation_count`, `AMPEL_LESER`) | module | Ampel-Auflösung, Abweichungszählung, Leser-Liste; muss neue Felder tragen |
| `output/metric_format.py` (`severity_from_thresholds`) | module | Bleibt UNVERÄNDERT; bewertet das abgeleitete Skalar mit oberen Grenzen |
| `app/ampel_templates.py` | module | Vorlage `radtour` bekommt Default `gegenwind` |
| `services/ampel_alarm.py` (`AMPEL_FELDER`, `_PRESET_TABLE` in `alert_preset`) | module | Alarm bei Stufenwechsel für das neue Feld |
| `utils/geo.py` | module | neue `bearing_deg`; Nachbar von `haversine_km` |
| `app/models.py` (`TripSegment`, `GPXPoint`, `SegmentWeatherSummary`, `wind_direction_deg`) | module | Segment-Geometrie, stündliche Winddaten, neues abgeleitetes Aggregatfeld |
| `output/email/narrow.py`, `output/email/helpers.py`, `output/email/compare_html.py` | module | Zellfärbung WDir in Trip-Briefing und Ortsvergleich-Tabelle |
| Telegram-Renderer, SMS-/Premium-SMS-Renderer, Katalog (`metric_catalog.py`, i18n-Katalog) | module | Wortlabel, `@h`-Marke, Alarmtext |
| `internal/handler/ampel.go` (`validateAmpel`, `ampelMetrikGueltig`) | module | Go-Validierung identisch zu Python |
| `frontend/.../shared/wetter-tab/ampelModell.ts`, `MetrikZeile.svelte`, `GrenzenEditor.svelte` | module | TS-Spiegel, Einbettung des neuen Moleküls |
| `docs/context/einstellungen_neu/elementliste.json` | doc | Mockup-Elementliste nach ADR-0112 |
| ADR-0095, ADR-0101, ADR-0104, ADR-0106, ADR-0108, ADR-0112 | adr | Kanalparität, Merge, i18n, Ampel als einzige Bewertung, Vorlage/Tempo getrennt, Bausteine |
| `services/wind_exposition.py` (F7) | module | Bleibt getrennt; Regel "höchste Stufe gewinnt" |

## Implementation Details

**Skalarreduktion (Tech-Lead-Entscheidung 1).** Es entsteht das abgeleitete Feld `wind_unerwuenscht_kmh` (je Stunde, daraus Segment-/Ort-Aggregat als Maximum der Stunden):
- Modus `gegenwind` (nur Trip): Gegenwindkomponente = Windstärke x cos(Winkel zwischen Herkunftsrichtung und Fahrtpeilung), nur wenn > 0, sonst 0. Rückenwind und Seitenwind ergeben 0 und bleiben neutral.
- Modus `sektoren`: volle Windstärke in km/h, wenn die Herkunftsrichtung im markierten Sektor liegt, sonst 0.
- Das Feld wird mit den normalen oberen Schwellen (yellow/orange/red in km/h) über den bestehenden Ampel-, Alarm- und Renderer-Pfad bewertet. Keine Sonderlogik in `severity_from_thresholds`, ADR-0106 bleibt gültig. Die Mindeststärke steckt automatisch in der gelben Grenze (in km/h).

**Modell (Entscheidung 2).** `ampel.metrics.wind_direction` erhält zusätzlich `modus: "aus"|"gegenwind"|"sektoren"` und `sektoren: [..]` (zulässig N, NO, O, SO, S, SW, W, NW) neben `enabled`, `upper`, `alarm_ab`. Validierung in Python und Go mit denselben Regeln: unbekannter Modus oder Sektor wird abgelehnt; `sektoren` ist nur bei `modus="sektoren"` nicht leer; im Ortsvergleich ist `gegenwind` unzulässig. Pflicht-Erweiterungen: `_verschmelzen` (kopiert heute nur lower/upper/enabled/alarm_ab), `deviation_count` samt Fixture `tests/fixtures/ampel_deviation_cases.json`, TS-Spiegel `ampelModell.ts`. Bestand additiv: fehlendes Feld bedeutet `aus`; Read-Modify-Write mit Merge (ADR-0101, #102), Bestandsdaten bleiben unverändert (`omitempty` in Go).

**Vorlage `radtour` (Entscheidung 3).** Default `modus=gegenwind`, Grenzen 10/20/30 km/h, `alarm_ab` orange. Alle anderen Vorlagen: `aus`. Kopplung pro Ampel-Eintrag, nicht über `tempo.fortbewegung` (ADR-0108). Der Nutzer kann "Gegenwind automatisch" in jedem Trip einschalten.

**Peilung (Entscheidung 4).** `bearing_deg(lat1, lon1, lat2, lon2)` in `src/utils/geo.py`; Fahrtpeilung = Luftlinie Segment-Start zu Segment-Ende. Bei Luftlinie unter 300 m (z. B. Rundkurs-Segment) gibt es keine Richtung, also Wert 0 und keine Färbung. Die Windrichtung wird stundenbasiert verrechnet; wo ein Segment-Mittel nötig ist, wird ein vektorielles Winkelmittel verwendet, nie ein arithmetisches (Wrap 359/1 Grad muss stimmen). Neues Modul `src/services/windrichtung.py`.

**Ortsvergleich (Entscheidung 5).** Nur `aus` oder `sektoren`; Orte sind Punkte ohne Bewegungsrichtung. `gegenwind` wird weder im Editor angeboten noch von der API akzeptiert.

**Kanäle (Entscheidung 6, ADR-0095: gleicher Inhalt, kanalgerechte Form).**
- E-Mail: Zelle WDir (Trip-Briefing und Ortsvergleich-Tabelle) in Ampelfarbe; `AMPEL_LESER` um `wind_direction` erweitert, Einhängen an den Stellen `narrow.py:623`, `compare_html.py:477`, `helpers.py:741/758` samt `schlimmster_index`.
- Telegram: Wortlabel aus dem Katalog ("Gegenwind" / EN "headwind" bzw. "Wind aus unerwünschter Richtung" / EN Entsprechung), nur über den Katalog.
- SMS und Premium-SMS: Protokoll-Token `WD:{Sektor}` unverändert, kein neues Token, Zeichenbudget unberührt; die bestehende `@h`-Hervorhebungsmarke erscheint ab gelb.
- Alarm: bestehende Stufenwechsel-Logik (`ampel_alarm.py`), neues `AmpelFeld("wind_direction", "wind_unerwuenscht_kmh", seite "oben")`, Eintrag in `_PRESET_TABLE` (Sprung-Schwelle ohne Sonderwert), Versand an alle konfigurierten Kanäle über die geteilte Kanal-Auflösung (#1533/#1701), Alarmtext nennt Gegenwind bzw. unerwünschte Richtung.

**Frontend (Entscheidung 7).** `molecules/RichtungsWahl.svelte` im gemeinsamen Reiter Wetter, eingebettet in `MetrikZeile`/`GrenzenEditor`; Trip: "Aus / Gegenwind automatisch / Himmelsrichtungen"; Ortsvergleich: "Aus / Himmelsrichtungen". Nur Design-System-Bausteine (ADR-0112), Mockup und Elementliste (`elementliste.json`, Trip und Orte, Normal- und Lückenzustand), i18n DE/EN ausschließlich über den Katalog. Mockup-Freigabe vor S4 klären.

**Wind-Exposition F7 (Entscheidung 8).** Bleibt getrennt (Risk-Engine, Höhe/km); bei Überschneidung (Gegenwind auf dem Grat) gewinnt die höchste Stufe, es wird nicht addiert. Die Eskalationsregel der Exposition wird nicht mitgenutzt.

**Scheiben (Entscheidung 9), je höchstens 250 LoC Code, Reihenfolge S1, S2, S3, S4.**
- **S1 Fachkern + Modell (ca. 150 LoC):** `bearing_deg`, Gegenwindkomponente, Sektor-Zuordnung, Winkelmittel, `windrichtung.py`, Modell-Felder, Validierung Python + Go, `_verschmelzen`, `deviation_count`, Vorlage `radtour`.
- **S2 Aggregat + Mail-Färbung (ca. 200 LoC):** `wind_unerwuenscht_kmh` in Segment/Ort, `AMPEL_LESER`, Zellfärbung Briefing + Ortsvergleich, `schlimmster_index`; Mail-Modus-Matrix und Validator gegen Staging-Mail.
- **S3 Alarm + Telegram/SMS/Premium-SMS (ca. 150 LoC):** `AMPEL_FELDER`, `_PRESET_TABLE`, Telegram-Wortlabel, `@h`, Alarmtext, Format-Doku (`sms_format.md`, `telegram_format.md`, `premium_sms_format.md`).
- **S4 Frontend (ca. 220 LoC):** `RichtungsWahl.svelte`, `MetrikZeile`/`GrenzenEditor`, `ampelModell.ts`, i18n, Mockup + Elementliste, Bausteine-Wächter grün.

### Affected Files

| File | Change Type | Description | Scheibe |
|------|-------------|-------------|---------|
| `src/utils/geo.py` | MODIFY | `bearing_deg` | S1 |
| `src/services/windrichtung.py` | CREATE | Gegenwindkomponente, Sektor, Winkelmittel, 300-m-Regel | S1 |
| `src/app/ampel.py` | MODIFY | `_verschmelzen`, `deviation_count`, `AMPEL_LESER`, Validierung | S1/S2 |
| `src/app/ampel_templates.py` | MODIFY | `radtour` Default gegenwind | S1 |
| `internal/handler/ampel.go` | MODIFY | Validierung modus/sektoren | S1 |
| `internal/model/*` (Ampel-Durchreichung) | MODIFY | Felder additiv, `omitempty` | S1 |
| `tests/fixtures/ampel_deviation_cases.json` | MODIFY | Paritätsfälle neue Felder | S1 |
| `src/app/models.py` | MODIFY | `SegmentWeatherSummary.wind_unerwuenscht_kmh` | S2 |
| Aggregation (`weather_extractor.py`/`segment_weather.py`) | MODIFY | Feld befüllen, Winkelmittel | S2 |
| `src/output/email/narrow.py`, `helpers.py`, `compare_html.py` | MODIFY | WDir-Zelle färben | S2 |
| `src/services/ampel_alarm.py`, `alert_preset` | MODIFY | `AmpelFeld`, Preset-Eintrag | S3 |
| Telegram-/SMS-/Premium-Renderer, Katalog | MODIFY | Wortlabel, `@h`, Alarmtext | S3 |
| `docs/reference/sms_format.md`, `telegram_format.md`, `premium_sms_format.md` | MODIFY | Ausdrucksform dokumentieren | S3 |
| `frontend/src/lib/components/molecules/RichtungsWahl.svelte` | CREATE | Auswahl Modus + 8 Sektoren | S4 |
| `frontend/.../organisms/wetter-tab/MetrikZeile.svelte`, `GrenzenEditor.svelte` | MODIFY | Einbettung | S4 |
| `frontend/.../shared/wetter-tab/ampelModell.ts`, `ampelSchreiben.ts` | MODIFY | Spiegel, Speichern | S4 |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | Neue Elemente Trip + Orte | S4 |
| `tests/...`, `internal/handler/ampel_test.go`, Frontend-Tests | CREATE | Tests je Scheibe | S1-S4 |

## Expected Behavior

- **Input:** Ampel-Einstellung `wind_direction` (modus, sektoren, upper, alarm_ab), stündliche Winddaten (Richtung, Stärke), Segment-Geometrie (Trip) bzw. markierte Sektoren (Ortsvergleich).
- **Output:** Gefärbte WDir-Zelle in Trip-Briefing und Ortsvergleich-Tabelle, `@h` in SMS/Premium-SMS ab gelb, Wortlabel in Telegram, Alarm bei Stufenwechsel.
- **Side effects:** Neues Feld in `display_config.ampel` (additiv). Keine Änderung an Bestandsdaten.

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1: GIVEN Rad-Trip-Segment Fahrtpeilung Nord, Wind 25 km/h aus N WHEN Briefing gerendert THEN WDir-Zelle in Ampelfarbe orange
- [ ] Test 2: GIVEN gleiche Etappe, Wind aus S WHEN gerendert THEN WDir-Zelle ungefärbt
- [ ] Test 3: GIVEN Wind 5 km/h aus Fahrtrichtung WHEN gerendert THEN ungefärbt
- [ ] Test 4: GIVEN Peilung 359 Grad, Wind aus 1 Grad (und umgekehrt) WHEN bewertet THEN nahezu volle Gegenwindkomponente
- [ ] Test 5: GIVEN Rundkurs-Segment Luftlinie < 300 m WHEN bewertet THEN keine Färbung
- [ ] Test 6: GIVEN Ortsvergleich, Sektor N markiert, Wind 30 km/h aus N WHEN Mail gerendert THEN Zelle des betroffenen Ortes gefärbt
- [ ] Test 7: GIVEN Ortsvergleich WHEN `modus=gegenwind` per API gesendet THEN 4xx; Editor bietet die Option nicht an
- [ ] Test 8: GIVEN Alt-Trip ohne Feld WHEN Briefing gerendert THEN Mail byte-gleich zu vorher
- [ ] Test 9: GIVEN ungültiger Sektor/Modus WHEN an Go-API und Python-Validierung gesendet THEN gleiche Ablehnung
- [ ] Test 10: GIVEN zwei Nutzer WHEN jeder eigene Einstellung speichert THEN keine gegenseitige Sichtbarkeit
- [ ] Test 11: GIVEN Wechsel von gelb auf orange WHEN Alarmlauf THEN Alarm in allen konfigurierten Kanälen
- [ ] Test 12: GIVEN Warnstufe gelb+ WHEN SMS/Premium-SMS gerendert THEN `WD:{Sektor}` plus `@h`, kein neues Token
- [ ] Test 13: GIVEN Sprache DE bzw. EN WHEN Telegram gerendert THEN Wortlabel in der Nutzersprache
- [ ] Test 14: GIVEN Editor WHEN Auswahl gespeichert und Seite neu geladen THEN Auswahl bleibt (Trip und Ortsvergleich)

## Acceptance Criteria

- **AC-1 (S2):** Given ein Rad-Trip mit Vorlage `radtour` und einer nach Norden führenden Etappe / When die Briefing-Mail bei 25 km/h Wind aus Norden zugestellt wird / Then ist die WDir-Zelle der Etappe in Orange gefärbt (Gegenwindkomponente 25 km/h).
  - Test: Zugestellte Staging-Mail des Rad-Trips (Briefing-Validator): WDir-Zelle trägt die Ampelfarbe orange.

- **AC-2 (S2):** Given dieselbe Rad-Etappe nach Norden / When der Wind mit 25 km/h aus Süden weht (Rückenwind) oder rein von der Seite kommt / Then bleibt die WDir-Zelle ungefärbt.
  - Test: Zugestellte Mail bei Südwind und bei Ostwind: WDir-Zelle ohne Ampelfarbe, Anzeige unverändert.

- **AC-3 (S2):** Given dieselbe Etappe mit Gegenwind-Richtung / When die Windstärke nur 5 km/h beträgt (unter der gelben Grenze von 10 km/h) / Then bleibt die Zelle ungefärbt.
  - Test: Zugestellte Mail bei 5 km/h Nordwind: keine Färbung; bei 10 km/h Nordwind: gelb.

- **AC-4 (S1):** Given eine Etappe mit Fahrtpeilung 359 Grad / When der Wind aus 1 Grad kommt, und spiegelbildlich Peilung 1 Grad bei Wind aus 359 Grad / Then wird in beiden Fällen die volle Windstärke (cos 2 Grad, gerundet) als Gegenwind bewertet und nicht als Seitenwind.
  - Test: Beide Fälle liefern nach Rendern der Briefing-Mail dieselbe Ampelfarbe wie reiner Nordwind bei Nordkurs; ein arithmetisches Mittel würde 180 Grad ergeben und die Färbung verfehlen.

- **AC-5 (S2):** Given ein Rundkurs-Segment, dessen Start und Ende weniger als 300 m auseinanderliegen / When starker Wind (40 km/h) weht / Then wird die WDir-Zelle dieses Segments nicht gefärbt, weil keine Fahrtrichtung bestimmbar ist.
  - Test: Zugestellte Mail für Rundkurs-Segment bei 40 km/h Wind: keine Färbung; angrenzendes Streckensegment mit Gegenwind bleibt gefärbt.

- **AC-6 (S2):** Given ein Ortsvergleich mit markiertem Sektor N und ein Skiort, an dem 30 km/h Nordwind vorhergesagt sind / When die Vergleichs-Mail zugestellt wird / Then ist die WDir-Zelle dieses Ortes entsprechend der Schwellen gefärbt, ein Ort mit Südwind gleicher Stärke bleibt ungefärbt.
  - Test: Zugestellte Staging-Mail des Ortsvergleichs (Vergleichstabelle, `email_spec_validator.py`): Zelle Skiort gefärbt, Vergleichsort ungefärbt.

- **AC-7 (S4):** Given der Editor-Reiter Wetter eines Ortsvergleichs / When der Nutzer die Windrichtung einstellt / Then werden nur "Aus" und "Himmelsrichtungen" angeboten, "Gegenwind automatisch" fehlt, und die API lehnt `modus=gegenwind` für einen Ortsvergleich mit einem Fehler ab.
  - Test: Editor im Browser (Ortsvergleich) zeigt zwei Optionen; direkter API-Aufruf mit `gegenwind` für einen Ortsvergleich gibt 4xx, Trip-Editor zeigt drei Optionen.

- **AC-8 (S2):** Given ein bestehender Trip ohne Feld `modus` in `ampel.metrics.wind_direction` (nicht Vorlage `radtour`) / When das Briefing nach dem Update zugestellt wird / Then ist die Mail inhaltlich identisch zu vorher und die gespeicherte Konfiguration unverändert.
  - Test: Zugestellte Mail vor und nach Update bei gleichen Wetterdaten ohne Unterschied in WDir; gespeicherte Trip-Datei enthält keine neuen Felder, andere Einstellungen bleiben erhalten (Merge).

- **AC-9 (S1):** Given ein Speicherversuch mit ungültigem Sektor (z. B. "NNO") oder ungültigem Modus (z. B. "rueckenwind") / When er an die Go-API und an die Python-Validierung geht / Then lehnen beide ihn mit derselben Fehlerklasse und gleichem Grund ab, und nichts wird gespeichert.
  - Test: Paritätstest mit denselben Fehlfällen gegen Go-Endpoint und Python-Validator; gespeicherte Einstellung nach Ablehnung unverändert.

- **AC-10 (S1):** Given zwei verschiedene Nutzer, A mit `gegenwind` und B mit `aus` / When beide ihre Einstellung speichern und laden / Then sieht jeder nur seine eigene Einstellung, und das Briefing von B bleibt ungefärbt.
  - Test: Zwei Sessions gegen die Go-API: GET der Einstellung liefert je Nutzer den eigenen Wert; Briefing B ohne Färbung; Zugriff auf fremde Daten wird verweigert.

- **AC-11 (S3):** Given ein Trip mit `alarm_ab` orange und Gegenwind, der von gelb auf orange wechselt / When der Alarmlauf läuft / Then erhält der Nutzer genau einen Alarm über alle konfigurierten Kanäle (E-Mail, Telegram, SMS, Premium-SMS) mit Text, der Gegenwind nennt; ohne Stufenwechsel kommt kein weiterer Alarm.
  - Test: Alarmlauf gegen Staging mit vier konfigurierten Kanälen: je Kanal ein Alarm mit Stichwort Gegenwind; zweiter Lauf ohne Wechsel erzeugt keinen neuen Alarm.

- **AC-12 (S3):** Given Gegenwind der Stufe gelb oder höher / When die SMS und die Premium-SMS gerendert werden / Then lautet das Token weiterhin `WD:{Sektor}` (z. B. `WD:N`), die bestehende `@h`-Marke erscheint, und es gibt kein neues Token; bei Stufe grün erscheint keine `@h`-Marke.
  - Test: Gerenderte SMS und Premium-SMS (<= 160 Zeichen): Token-Format unverändert, `@h` nur ab gelb; Formatprüfung gegen `sms_format.md`.

- **AC-13 (S3):** Given Gegenwind ab gelb / When das Telegram-Briefing für einen Nutzer mit Sprache DE und einen mit EN gerendert wird / Then steht bei DE "Gegenwind" und bei EN "headwind"; bei Sektor-Modus steht die Entsprechung für "Wind aus unerwünschter Richtung" in der Nutzersprache, das Kürzel `WD` bleibt unübersetzt.
  - Test: Gerenderte Telegram-Nachricht je Sprache enthält das Label aus dem Katalog; Sprachwechsel am Nutzer ändert nur den Text, nicht das Token.

- **AC-14 (S4):** Given der Editor-Reiter Wetter eines Trips und eines Ortsvergleichs / When der Nutzer Modus und Himmelsrichtungen wählt, speichert und die Seite neu lädt / Then ist dieselbe Auswahl wieder sichtbar, und die nächste Mail spiegelt sie wider.
  - Test: Browser-Test (Trip: "Gegenwind automatisch" und Sektor-Auswahl; Ortsvergleich: Sektoren N und NO) mit Speichern, Reload, Auslesen über die API; Mail nach Änderung gefärbt gemäß Auswahl.

- **AC-15 (S2):** Given eine Etappe, auf der die Wind-Exposition (Grat) das Windrisiko erhöht und zugleich Gegenwind herrscht / When das Briefing gerendert wird / Then gilt die höchste der beiden Stufen, sie werden nicht addiert.
  - Test: Zugestellte Mail mit Grat-Etappe und Gegenwind: Gesamtstufe gleich dem Maximum beider Einzelstufen.

## Known Limitations

- Nur Gegenwind bzw. unerwünschte Richtung werden bewertet; Rückenwind und Seitenwind bleiben neutral (Seitenwind ggf. später, benötigt zweiten Grenzwertsatz und Mockup-Fläche).
- Segment-Peilung ist Luftlinie Start zu Ende; bei Serpentinen oder sehr langen Rad-Segmenten ist sie grob. Feinere Peilung je Stunde über den GPX-Track ist eine spätere Scheibe.
- Unter 300 m Luftlinie keine Richtung, daher keine Färbung.
- Der Ortsvergleich kennt kein Gegenwind, weil Orte Punkte ohne Bewegungsrichtung sind.
- SMS und Premium-SMS tragen die Bewertung nur über `@h` und Alarmtext, nicht über ein eigenes Token (Protokoll-Stabilität, 160 Zeichen).
- Himmelsrichtungs-Kürzel (N, NO, O, SO, S, SW, W, NW) sind deutsche Protokoll-Token und werden nicht geändert.

### Offene PO-Entscheidung (Empfehlung, PO bestätigt bei Freigabe)

Es werden nur Gegenwind bzw. unerwünschte Richtung bewertet; Rückenwind und Seitenwind bleiben neutral. Empfehlung: so umsetzen; Seitenwind später als eigene Scheibe, falls Radfahrer ihn vermissen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neues ADR empfohlen (nur benennen, nicht Teil dieser Spec): "Profil-Ampel bewertet eine abgeleitete Richtungsgröße (`wind_unerwuenscht_kmh`) als Skalar" (voraussichtlich ADR-0126, nächste freie Nummer)
- **Rationale:** ADR-0106 legt fest, dass die Profil-Ampel die einzige Bewertung ist; das Feature erweitert ihr Datenmodell um eine abgeleitete, nicht direkt gemessene Größe samt Modus und Sektoren und legt fest, dass Richtungslogik VOR der Ampel zu einem Skalar reduziert wird (keine Sonderlogik in `severity_from_thresholds`). Das ist eine dauerhafte Modellentscheidung mit Folgen für Alarm, Kanäle und Parität Python/Go/TS und nach CLAUDE.md eine Entscheidungsfläche (Datenmodell, Kanäle). Das ADR ergänzt ADR-0106, ersetzt es nicht ("Abgelöst durch" entfällt).

## Changelog

- 2026-11-20: Initial spec created
