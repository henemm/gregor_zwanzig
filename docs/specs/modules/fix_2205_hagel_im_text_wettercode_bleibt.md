---
entity_id: fix_2205_hagel_im_text_wettercode_bleibt
type: module
created: 2026-09-15
updated: 2026-09-15
status: draft
version: "1.0"
tags: [gewitter, hagel, alarm, wettercode, nowcast, workflow-fix-2205-wettercode-zwischenstufe]
---

<!-- Issue #2205, Workflow fix-2205-wettercode-zwischenstufe. Ursprüngliche
     Ticket-Prämisse (95/96/99 → HIGH sei fehlerhaft) wurde durch Messung
     widerlegt: 24.08. (falsch) und 31.08. (echt) sind nach Code und Dauer
     identisch, keine Zuordnungs- oder Mindestdauerregel trennt sie. PO-
     Entscheid 15.09.: heutiges Alarmverhalten bleibt, Hagel wird im Text
     unterschieden. -->

# Hagel im Alarmtext unterscheiden, Wettercode-Stufenzuordnung bleibt

## Approval

- [ ] Approved

## Purpose

WMO-Wettercode 95 ("Gewitter, schwach oder mäßig", ohne Hagel) und 96/99
("Gewitter mit Hagel") heben beide `ThunderLevel.HIGH` — das bleibt, denn
die Nachmessung zeigt: keine Zuordnungs- oder Mindestdauerregel trennt den
24.08. (falscher Alarm) vom 31.08. (echter Gewitteralarm), beide tragen
identischen Code und identische Dauer. Was fehlt, ist nicht die Stufe,
sondern die **Hagel-Aussage im Text** an fünf Stellen, die heute 95 und
96/99 gleich behandeln: Stufen-/Korridor-Änderungsalarm (alle vier Kanäle),
Nowcast/Radar-Label, Nacht-Halbsatz, Mail-Hervorhebung und Glance-Kommando.
Diese Spec ergänzt an genau diesen Stellen die bestehende
Hagel-Formulierung (`format_hail_note` bzw. SMS-Suffix `+HL`) — ohne neuen
Wortlaut-Pfad und ohne die Stufenzuordnung anzufassen.

## Source

- **File:** `src/output/renderers/alert/model.py` (`AlertEvent`),
  `src/output/renderers/alert/project.py`, `src/output/renderers/alert/render.py`,
  `src/services/radar_service.py`, `src/app/day_window.py`,
  `src/services/trip_report_scheduler.py` (Nacht-Halbsatz-Bau),
  `src/services/trip_command_processor.py`, `src/output/renderers/narrow.py`
- **Identifier:** `AlertEvent`, `format_hail_note`, `INTENSITY_CONVECTIVE`,
  `_is_convective_weathercode`

> **Schicht-Hinweis:** Python-Core (`src/output/`, `src/services/`,
> `src/app/`) — alle fünf Flächen liegen in der Domain-/Renderer-Schicht,
> keine Go-API- und keine Frontend-Berührung. `internal/provider/openmeteo/models.go`
> wird **nicht** angefasst (Stufenzuordnung bleibt unverändert).

## Estimated Scope

- **LoC:** ~200–300 Code/Test (Doku-Anteil ADR + Konzept-Nachtrag zählt
  laut CLAUDE.md nicht) — `loc_limit_override 500` vorgesehen
- **Files:** ~10–12 (5 Produktivflächen + zugehörige Tests + ADR +
  `docs/adr/README.md` + Konzept-Doc-Nachtrag)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `notification_service.py:1584-1589` | Upstream | befüllt `AlertEvent`, hier kommt das neue Hagelfeld hinzu |
| `weather_metrics.py:826-839` (`_compute_hail_flag`/`hail_priority`) | Upstream | liefert das Hagel-Aggregat über dieselbe Punktmenge wie `thunder_max` — Quelle für alle fünf Flächen |
| `metric_format.format_hail_note` | Bestehend | einzige Wortlautquelle für Mail/Telegram-Hagelaussagen, wird wiederverwendet, nicht neu geschrieben |
| `tokens/builder.py` (Suffix `+HL`) | Bestehend | einzige Wortlautquelle für SMS/Premium-SMS, wird wiederverwendet |
| `tests/tdd/test_thunder_level_low_ordinal_and_render.py:77`, `internal/provider/openmeteo/provider_test.go:159-166` | Invariante | sichern bereits „95/96/99 bleibt HIGH" — hier **nicht** erneut geprüft |

## Implementation Details

```
Fläche 1 — Stufen-/Korridor-Änderungsalarm (alle 4 Kanäle):
  AlertEvent bekommt Hagelfeld (befüllt aus demselben Aggregat wie die
  Stufe, alert/project.py). render.py reicht es für Mail/Telegram über
  format_hail_note in den Text, für SMS/Premium-SMS (gemeinsamer
  sms_body) als Token-Suffix "+HL". Korridor-Alarm läuft über denselben
  render.py-Pfad (Z. 430-453) und bekommt die Aussage automatisch mit.

Fläche 2 — Nowcast/Radar-Label (radar_service.py):
  INTENSITY_CONVECTIVE differenziert künftig: Code 95 -> "Gewitter" ohne
  Hagelbegriff, Code 96/99 -> Label mit Hagelbegriff (bestehender
  Wortlaut aus format_hail_note-Familie, kein Neutext). Ersetzt die
  bisherige pauschale "Starker Hagel/Gewitter"-Aussage für 95.

Fläche 3 — Nacht-Halbsatz (day_window.py:267):
  Halbsatz "nachts starkes Gewitter ab HH:00" bekommt bei 96/99 im
  betrachteten Nachtfenster den bestehenden Hagelzusatz, bei 95 bleibt
  er wie heute ohne Hagelaussage.

Fläche 4 — Mail-Hervorhebung: ENTFÄLLT (Messung 15.09., TDD-RED).
  Die Zeile "Gewitter möglich ab ..." (src/output/renderers/trip_report.py
  _compute_highlights) erreicht die Mail seit #790 nicht mehr
  (render_email verwirft highlights=). Die tatsächlich zugestellte
  Tages-Pille (email/helpers._pill_for_metric) unterscheidet bereits:
  96 -> "... · Hagel: ja", 95 -> ohne. Kein Code-Eingriff.

Fläche 5 — Glance-Kommando + Telegram-Metrikzeile
  (trip_command_processor.py:1586-1591/~1709, narrow.py:522-526):
  agg["hail_flag"] liegt an dieser Stelle bereits vor (Z. 1536/1556) --
  Timeline und Telegram-Metrikzeile werten es künftig aus statt es zu
  ignorieren.

UNVERÄNDERT: _parse_thunder_level/THUNDER_CODES (Python + Go-Spiegel),
Alarm-Auslöselogik/Presets, thunder_branch.py:222,233 (Kompakt-Ausblick).
```

## Expected Behavior

- **Input:** Stundenreihe mit mindestens einer Stunde auf der jeweiligen
  Spitzenstufe (HIGH), deren Wettercode 95, 96 oder 99 ist — dieselbe
  Stundenmenge, aus der auch Stufe und Onset berechnet werden.
- **Output:** Gerenderter Kanaltext (Mail-HTML/Plain, Telegram, SMS-Body,
  Premium-SMS-Body, Nowcast-Label, Nacht-Halbsatz, Mail-Hervorhebung,
  Glance-Text) enthält bei 96/99 die bestehende Hagelaussage
  (`format_hail_note`-Wortlaut bzw. `+HL`-Suffix), bei reinem 95 nicht.
- **Side effects:** keine Änderung an Stufe, Onset, Alarm-Auslösung,
  Risikopunkt oder Ortsvergleich-Scoring.

## Acceptance Criteria

- **AC-1:** Given eine Stufenänderung auf hoch, deren Spitzenstunde Wettercode 96 oder 99 trägt / When der Stufen-Änderungsalarm für die Kanäle E-Mail und Telegram gerendert wird / Then enthalten beide Texte die bestehende Hagelaussage aus `format_hail_note`.
  - Test: `tests/tdd/test_hagel_im_alarmtext.py` — Alarm-Renderer mit Fixture-Timeseries (Stunde mit `hail_flag=True`, Code 96/99) rendert Mail- und Telegram-Alarmtext und prüft die Hagelaussage im Fließtext, nicht am Datenmodell.

- **AC-2:** Given eine Stufenänderung auf hoch, deren Spitzenstunde ausschließlich Wettercode 95 trägt / When derselbe Stufen-Änderungsalarm für E-Mail und Telegram gerendert wird / Then enthält keiner der beiden Texte eine Hagelaussage.
  - Test: `tests/tdd/test_hagel_im_alarmtext.py` — identischer Fixture-Aufbau mit `hail_flag=False`/Code 95, Assertion auf Abwesenheit der Hagelformulierung im gerenderten Text.

- **AC-3:** Given dieselbe Stufenänderung mit Code 96 oder 99 in der Spitzenstunde / When der Stufen-Änderungsalarm für SMS und Premium-SMS gerendert wird / Then trägt der gemeinsame `sms_body` beider Kanäle das bestehende Token-Suffix `+HL`.
  - Test: `tests/tdd/test_hagel_im_sms_token.py` — SMS- und Premium-SMS-Ausgabe desselben Alarmereignisses auf identisches `sms_body` mit `+HL`-Suffix geprüft.

- **AC-4:** Given dieselbe Stufenänderung mit ausschließlich Code 95 in der Spitzenstunde / When SMS und Premium-SMS gerendert werden / Then fehlt das Suffix `+HL` im `sms_body` beider Kanäle.
  - Test: `tests/tdd/test_hagel_im_sms_token.py` — Fixture mit Code 95, Assertion auf fehlendes Suffix bei gleichzeitig unveränderter Stufenangabe (`TH:M->H@15` bleibt erhalten).

- **AC-5:** Given ein Korridor-Alarm (Streckenabschnitt statt Tagesstufe) mit Spitzenstunde Code 96 oder 99 / When der Korridor-Alarmtext gerendert wird / Then enthält er dieselbe Hagelaussage wie der Stufen-Änderungsalarm desselben Renderer-Pfads.
  - Test: `tests/tdd/test_hagel_im_korridor_alarmtext.py` — Korridor-Alarm-Fixture über `render.py`-Korridorpfad (Z. 430-453) gerendert, Hagelaussage im Text geprüft.

- **AC-6:** Given ein Korridor-Alarm mit ausschließlich Code 95 in der Spitzenstunde / When der Korridor-Alarmtext gerendert wird / Then fehlt die Hagelaussage im Text.
  - Test: `tests/tdd/test_hagel_im_korridor_alarmtext.py` — identischer Fixture-Aufbau mit Code 95, Assertion auf Abwesenheit.

- **AC-7:** Given eine Nowcast-Stunde mit Wettercode 96 oder 99 / When das Radar-Intensitäts-Label für diese Stunde ermittelt wird / Then enthält das Label einen Hagelbegriff.
  - Test: `tests/tdd/test_hagel_im_nowcast_label.py` — `radar_service`-Label-Funktion mit Code 96/99 aufgerufen, Rückgabestring auf Hagelbegriff geprüft.

- **AC-8:** Given eine Nowcast-Stunde mit ausschließlich Wettercode 95 / When das Radar-Intensitäts-Label für diese Stunde ermittelt wird / Then enthält das Label das Wort „Gewitter", aber keinen Hagelbegriff.
  - Test: `tests/tdd/test_hagel_im_nowcast_label.py` — gleicher Aufruf mit Code 95, Assertion dass „Hagel" nicht im Label vorkommt und „Gewitter" vorkommt (Fang für die pauschale Alt-Formulierung „Starker Hagel/Gewitter").

- **AC-9:** Given ein Nachtfenster mit einer Stunde auf Code 96 oder 99 / When der Nacht-Halbsatz für dieses Fenster gerendert wird / Then enthält der Halbsatz die bestehende Hagelaussage.
  - Test: `tests/tdd/test_hagel_im_nachthalbsatz.py` — `day_window`-Halbsatzfunktion mit Nachtfenster-Fixture (Code 96/99), Hagelaussage im Halbsatztext geprüft.

- **AC-10:** Given ein Nachtfenster mit ausschließlich Code 95 / When der Nacht-Halbsatz für dieses Fenster gerendert wird / Then enthält der Halbsatz keine Hagelaussage.
  - Test: `tests/tdd/test_hagel_im_nachthalbsatz.py` — identischer Fixture-Aufbau mit Code 95, Assertion auf Abwesenheit.

> **AC-11 und AC-12 entfallen** (Messung 15.09. in TDD-RED): die Hervorhebungszeile ist seit #790 toter Code und erreicht keine Mail; die zugestellte Tages-Pille unterscheidet Hagel bereits (siehe Nicht-Ziele/Invarianten). Nummern bleiben zur Referenzstabilität stehen, es gibt keine Tests dazu.

**AC-11 (entfällt):** Given eine Etappe mit Spitzenstunde Code 96 oder 99, für die eine Mail-Hervorhebungszeile „Gewitter möglich ab ..." erzeugt wird / When die Trip-Mail gerendert wird / Then enthält die Hervorhebungszeile die bestehende Hagelaussage.
  - Test: `tests/tdd/test_hagel_in_mail_hervorhebung.py` — `trip_report`-Hervorhebungsfunktion mit Fixture-Etappe (Code 96/99) gerendert, Hagelaussage in der Hervorhebungszeile geprüft.

**AC-12 (entfällt):** Given eine Etappe mit ausschließlich Code 95 in der Spitzenstunde / When die Trip-Mail gerendert wird / Then enthält die Hervorhebungszeile keine Hagelaussage.
  - Test: `tests/tdd/test_hagel_in_mail_hervorhebung.py` — identischer Fixture-Aufbau mit Code 95, Assertion auf Abwesenheit.

- **AC-13:** Given ein Trip, dessen Tagesaggregat Gewitterstufe hoch mit Code 96 oder 99 trägt (`agg["hail_flag"]` wahr) / When das Glance-Kommando („⛈ Gewitter: …") und die HEUTE/MORGEN-Timeline als Kommandoantwort gerendert werden / Then enthalten beide Antworttexte die bestehende Hagelaussage.
  - Test: `tests/tdd/test_hagel_in_kommando_und_metrikzeile.py` — Kommandoantwort aus `trip_command_processor` mit Fixture-Aggregat gerendert, Hagelaussage im Antworttext beider Kommandos geprüft.

- **AC-14:** Given dasselbe Tagesaggregat mit ausschließlich Code 95 (`agg["hail_flag"]` falsch) / When Glance-Kommando und HEUTE/MORGEN-Timeline gerendert werden / Then enthält keiner der beiden Antworttexte eine Hagelaussage.
  - Test: `tests/tdd/test_hagel_in_kommando_und_metrikzeile.py` — identischer Aufbau mit Code 95, Assertion auf Abwesenheit.

- **AC-15:** Given eine Etappe mit Gewitterstufe hoch, deren Spitzenstunde Code 96 oder 99 trägt / When die Telegram-Metrikzeile der Etappe gerendert wird / Then enthält die Metrikzeile eine Hagelkennzeichnung.
  - Test: `tests/tdd/test_hagel_in_kommando_und_metrikzeile.py` — Telegram-Renderer (`narrow.py`) mit Fixture-Etappe, Prüfung am gerenderten Zeilentext.

- **AC-16:** Given dieselbe Etappe mit ausschließlich Code 95 in der Spitzenstunde / When die Telegram-Metrikzeile gerendert wird / Then enthält die Metrikzeile keine Hagelkennzeichnung.
  - Test: `tests/tdd/test_hagel_in_kommando_und_metrikzeile.py` — identischer Aufbau mit Code 95, Assertion auf Abwesenheit.

## Known Limitations

- Codes 91–94/97 (0 Vorkommen in 230k gemessenen Stunden) bleiben auf
  `ThunderLevel.NONE`, werden nicht behandelt — nur im ADR vermerkt.
- Der fehlende `"radar"`-Eintrag in `THUNDER_SIGNAL_LABEL_DE` ist ein
  eigenständiger Nebenbefund (→ #1199), nicht Teil dieser Spec.

## Nicht-Ziele / Invarianten

- **Mail-Tages-Pille unterscheidet Hagel bereits** (`email/helpers._pill_for_metric`):
  Code 96 → „Gewitter hoch ab 14:00 · stärkste 14:00 · Hagel: ja", Code 95 ohne
  Hagel. Die tote Hervorhebungszeile (`_compute_highlights`, AC-11/12) wird nicht
  wiederbelebt.
- **Mehr-Orte-Onset-Kopf `render.py:781` („Gewitter/Hagel" bei jedem konvektiven
  Ort)** läuft nur im Ortsvergleich-Bündelpfad (zurückgestellt) → Sammel-Issue #1199.

- **Stufenzuordnung WMO 95/96/99 → `ThunderLevel.HIGH` bleibt unverändert**
  in `_parse_thunder_level`/`THUNDER_CODES` (Python) und im Go-Spiegel
  (`internal/provider/openmeteo/models.go`). Diese Invariante ist bereits
  durch `tests/tdd/test_thunder_level_low_ordinal_and_render.py:77` und
  `internal/provider/openmeteo/provider_test.go:159-166` gesichert — kein
  neuer Test in dieser Spec, nur Verweis im ADR.
- **Alarm-Auslöselogik/Presets** (`alert_preset.py:114-118`,
  `weather_change_detection.py:~973-990`) bleiben unverändert — nur der
  Text der bereits ausgelösten Alarme ändert sich.
- **Kompakt-Ausblick** (`thunder_branch.py:222,233`) bleibt bewusst ohne
  Hagelaussage (PO-Entscheid, im Docstring dokumentiert) — nicht anfassen.
- **Codes 91–94/97**: kein Fix, nur ADR-Vermerk (0 Vorkommen).
- **Nicht Teil dieses Tickets:** #2182 (ADR-0048/CAPE-Deckel), #2206
  (CAPE-Zeitpunkt), #2178 (CAPE-Leiter), #16 (Übernachtungsart je Etappe/
  Nacht-Gewitter-Warnung — eigenes Ticket, keine offene Frage hier).
- **`"radar"`-Label-Nebenbefund** → Sammel-Issue #1199, kein eigenes AC.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neu, `docs/adr/0069-wettercode-95-96-99-bleibt-hoechste-stufe.md`
- **Rationale:** Nachmessung (24.08. falscher Alarm, 31.08. echter Alarm —
  identischer Code, identische Dauer) zeigt: keine Zuordnungs- oder
  Mindestdauerregel trennt beide Fälle. 95→LOW (Konzeptwert aus
  `docs/features/gewitter-gesamtkonzept.md:345`) scheitert an ADR-0064
  („leicht" ist keine Gewitteransage mehr); 95→MED oder eine
  Persistenzregel ≥2h verlieren beide den 31.08.-Standard-Alarm; Code 99
  kommt außerhalb ICON-D2 praktisch nie vor. Der Trade-off wird zugunsten
  des heutigen Alarmverhaltens aufgelöst (PO-Entscheid 15.09.), die
  Hagel-Information wird stattdessen im Text nachgezogen. Eintrag in
  `docs/adr/README.md` (gesichert durch `tests/test_adr_index_drift.py`);
  `docs/features/gewitter-gesamtkonzept.md:345` wird im selben Zug als
  bewusst nicht umgesetzt nachgetragen. Kein Konflikt mit
  `feat_1474_gewitter_befund_stufen.md` AC-4 (dort ebenfalls 95→HIGH).

## Changelog

- 2026-09-15: Initial spec created (Issue #2205, PO-Entscheid: Alarmverhalten bleibt, Hagel im Text unterscheiden)
- 2026-09-15 (TDD-RED): AC-11/12 entfallen — Hervorhebungszeile ist seit #790 toter Code, zugestellte Tages-Pille unterscheidet bereits. AC-5/6 um Korridor-SMS (`!TH…` + `+HL`, Premium-SMS über gemeinsamen sms_body) ergänzt. Source-Pfade korrigiert (`renderers/narrow.py`). Implementierungshinweis: acht Alttests prüfen den Wortlaut „Starker Hagel/Gewitter" und sind an das neue Nowcast-Label anzupassen (veraltetes Verhalten, nicht „vorbestehend rot").
- 2026-09-15 (GREEN): Vorschauzeile Mail — Tages-Hagel steht im Text vor dem Nacht-Halbsatz, Nacht-Hagel im Halbsatz, je genau einmal (plain.py/html.py-Suffix entfernt); SMS-Folgetag +HL jetzt tagesfensterbezogen wie TH+. Nowcast-Label: 95 „Gewitter", 96/99 „Starker Hagel/Gewitter".
