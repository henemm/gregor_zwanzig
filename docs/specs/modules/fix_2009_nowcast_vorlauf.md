---
entity_id: fix_2009_nowcast_vorlauf
type: bugfix
created: 2026-08-20
updated: 2026-08-20
status: approved
version: "1.0"
tags: [alerts, radar, nowcast, trip, compare]
---

# Nowcast-Vorlauf: geteilte Onset-Schwelle 20 → 55 Minuten (Issue #2009)

## Approval

- [x] Approved — PO-Freigabe 2026-08-20 („approved"), AC-1 bis AC-6 auf Deutsch vorgelegt.

## Purpose

Der Radar-/Nowcast-Gewitteralarm meldet praktisch immer „in 8 Min" Vorlauf — nicht weil das
Wetter das hergibt, sondern weil Scheduler-Takt (`7,22,37,52`), 15-Minuten-Datenraster und die
hartkodierte Onset-Schwelle `20` zusammen genau diesen Wert erzwingen (siehe
`docs/context/fix-2009-nowcast-vorlauf.md`, Root-Cause-Tabelle). Diese Spec hebt die Schwelle auf
einen bewusst gewählten, erreichbaren Rasterwert (55 Min) an, führt sie als **eine** geteilte
Konstante statt zweier Literale, und behebt die drei Begleitschäden, die eine größere
Vorlaufzeit erst sichtbar macht: Mitternachts-Mehrdeutigkeit des Onset-Zeitpunkts, fehlender
Segment-Bezug im Trip-Pfad, und eine Testsuite, die bislang nie prüft, dass `onset_minutes`
überhaupt variieren kann.

## Source

- **File:** `src/services/radar_service.py`, `src/services/trip_alert.py`,
  `src/services/compare_radar_alert.py`, `src/output/renderers/alert/model.py`,
  `src/output/renderers/alert/project.py`, `src/output/renderers/alert/render.py`
- **Identifier:** `radar_alert_due()`, `TripAlertService.check_radar_alerts()`,
  `CompareRadarAlertService._collect_triggered()`, `OnsetEvent`,
  `to_multi_location_onset_alert_message()`, `_render_email_onset()`, `_render_telegram_onset()`,
  `_render_sms_onset()`
- **Schicht:** Python-Core (`src/services/`, `src/output/renderers/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** Produktiv ~+55/-15, Tests ~+170 (drei neue Testdateien + zwei angepasste
  Bestandstests). Deutlich über der `~7 Dateien`-Grobschätzung aus der Analysephase, weil der
  Datumsbezug drei Renderer-Kanäle (E-Mail, Telegram, SMS) UND das gemeinsame Datenmodell
  (`OnsetEvent`) berührt — dort wo die Analyse „1 Renderer" zählte, sind es real drei Dateien.
  Trotzdem klar unter dem 250-LoC-Workflow-Limit (Doku-Dateien zählen laut CLAUDE.md ohnehin
  nicht mit).
- **Files:** 7 Produktivdateien, 5 Testdateien (2 modifiziert, 3 neu), 2 reine Doku-Dateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.radar_service.NOWCAST_HORIZON_MIN` | constant | Etablierter Alias-Präzedenzfall (Issue #1439) — dieselbe Bauform wird für die neue Schwelle wiederverwendet |
| `services.trip_alert.radar_alert_due` | function | Reine Entscheidungsfunktion, von Trip- UND Compare-Pfad genutzt (ADR-0021) |
| `services.alert_gate.check_event_identity_gate` | function | Ereignis-Identitäts-Sperre (±180 Min Fenster) — bleibt unverändert, bestimmt aber die Known-Limitation dieser Spec |
| `utils.timezone.local_fmt` | function | Reines `%H:%M`-Format ohne Datum — Ursache der Mitternachts-Mehrdeutigkeit, wird NICHT verändert, sondern an den beiden Aufrufstellen um Tagesbezug ergänzt |
| `output.renderers.alert.model.OnsetEvent` | model | Kanonisches Datenmodell des Onset-Ereignisses, additive Erweiterung um ein Tages-Offset-Feld |
| `services.notification_service` | service | Teilt den SMS-Renderer zwischen Standard-SMS und Premium-SMS — eine Änderung an `_render_sms_onset` erreicht automatisch beide Kanäle |

## Implementation Details

### 1. Geteilte Schwelle statt zweier Literale

Neue benannte Konstante in `src/services/radar_service.py`, direkt neben
`_NOWCAST_HORIZON_MIN`/`NOWCAST_HORIZON_MIN` (identisches, bereits etabliertes Muster aus
Issue #1439 — privates Literal + öffentlicher Alias):

```
_RADAR_ONSET_THRESHOLD_MIN = 55
# Issue #2009: einzige Quelle der Onset-Alarmschwelle, ersetzt die bisher
# doppelt gepflegten Literale in trip_alert.py und compare_radar_alert.py
# (ADR-0021 — Trip und Ortsvergleich teilen den Code).
RADAR_ONSET_THRESHOLD_MIN = _RADAR_ONSET_THRESHOLD_MIN
```

`src/services/trip_alert.py:1270` (`radar_alert_due(result, threshold_min=20)`) und
`src/services/compare_radar_alert.py:53` (`_RADAR_ONSET_THRESHOLD_MIN = 20`, Aufruf `:346`)
importieren künftig `RADAR_ONSET_THRESHOLD_MIN` aus `radar_service` statt eigener Literale.

**Wert 55, nicht höher:** Am Cron-Takt `7,22,37,52` und dem 15-Minuten-Datenraster sind
ausschließlich die Onset-Werte 8, 23, 38, 53, 68, 83, 98 … erreichbar. 55 liegt knapp oberhalb
von 53 — lässt also 8/23/38/53 durch (bis zu ~53 Min Vorlauf) und schließt 68+ aus. Die Schwelle
muss knapp oberhalb eines erreichbaren Rasterwerts liegen, sonst wiederholt sich der
#1945-Fehler (eine Grenze, die kein Frame je erfüllt). Nicht weiter: INCA ist ein
Extrapolationsprodukt, jenseits ~60 Min sinkt die Ortsschärfe deutlich; jede Fehlwarnung kostet
beim Satelliten-Nutzer (KHW-Hütte, nur Premium-SMS) Geld und Vertrauen.

### 2. Datumsbezug am Onset-Zeitpunkt

`OnsetEvent` (`src/output/renderers/alert/model.py:38-56`) bekommt ein additives, defaultetes
Feld, z. B. `onset_day_offset: int = 0` (0 = heute, 1 = morgen), berechnet dort, wo `onset_time`
heute bereits mit `local_fmt(..., "%H:%M")` gebaut wird:

- `src/services/trip_alert.py:1353` (`_onset_time_str = local_fmt(now_utc + timedelta(minutes=result.onset_minutes), tz)`)
- `src/output/renderers/alert/project.py:392-394` (`to_multi_location_onset_alert_message`, Compare-Bündel-Pfad)

Berechnung: lokales Kalenderdatum von `now` vs. lokales Kalenderdatum von `now + onset_minutes`
in derselben Zeitzone `tz` — unterscheiden sie sich, ist `onset_day_offset = 1`.

Renderer-seitig (`src/output/renderers/alert/render.py`) wird der Offset genutzt, um den
bestehenden `%H:%M`-String eindeutig zu machen — additiv, byte-identisch im unveränderten
Normalfall (`onset_day_offset == 0`):

- E-Mail (`_render_email_onset:371`, `_render_email_onset_multi:316`): „Wo & wann" bzw. „ab
  {onset_time}" bekommt bei Offset 1 das Präfix „morgen " (z. B. „ab morgen 00:23").
- Telegram (`_render_telegram_onset:414-420`): zweite Zeile analog.
- SMS/Premium-SMS (`_sms_onset_time`/`_render_sms_onset:423-463`, geteilter Renderer über
  `notification_service.py:23`): kompaktes Suffix `+1` am Token, z. B. `TH@0:23+1` statt
  `TH@0:23` — GSM-7-verträglich (`+`, Ziffern), erhöht das Token um 2 Zeichen, bleibt innerhalb
  der 160-Zeichen-Grenze (bestehender `limit`-Parameter, Default 140).

### 3. Segment-Ende-Guard (nur Trip-Pfad)

In `src/services/trip_alert.py`, direkt nach dem Schwellen-Check (`:1270-1271`) und vor dem
Briefing-Vergleich (`:1273ff`, dort wird `_onset_dt` bereits für den Briefing-Abgleich gebraucht
— die Berechnung wird für den Guard vorgezogen bzw. wiederverwendet): liegt
`now_utc + timedelta(minutes=result.onset_minutes)` NACH `active.end_time`, wird der Alarm
unterdrückt (analog dem bestehenden `continue`-Muster der Nachbar-Guards, mit eigenem
Log-Grund).

**Ortsvergleich hat keinen Segment-Bezug.** Compare-Presets arbeiten auf `location_ids`, nicht
auf Etappen/Segmenten (bereits dokumentiert in `compare_radar_alert.py:13-16`,
„keine Etappen/Segmente ... kein Vortags-Rückgriff"). Ein Segment-Ende-Guard ist dort
gegenstandslos, nicht vergessen — die Asymmetrie ist **sachlich begründet und kein
ADR-0021-Verstoß**: ADR-0021 verlangt geteilten Code für geteilte Konzepte; „Segment" ist im
Compare-Modell schlicht nicht vorhanden. Siehe Abschnitt „Architektur-Entscheidung (ADR)".

## Expected Behavior

- **Input:** `NowcastResult.onset_minutes` aus `RadarNowcastService.get_nowcast()` (Trip- und
  Compare-Pfad identisch), Scheduler-Tick alle 15 Min.
- **Output:** Radar-Alarm löst bei jedem der Rasterwerte 8/23/38/53 Min aus (statt nur bei 8),
  bleibt bei 68/83/98+ Min weiterhin stumm. Onset-Zeitpunkt in allen vier Kanälen eindeutig,
  auch bei Mitternachts-Überlauf. Trip-Pfad unterdrückt Alarme für bereits verlassene Segmente.
- **Side effects:** Keine neuen Persistenz-Felder, keine Migration (`OnsetEvent` ist reine
  Rendering-Struktur, nicht persistiert). Bestehende `alert_log`/`AlertStateService`-Einträge
  unverändert im Format.

## Acceptance Criteria

- **AC-1:** Given `RADAR_ONSET_THRESHOLD_MIN` ist in `src/services/radar_service.py` als einzige
  Quelle definiert (Wert 55) / When `trip_alert.py` und `compare_radar_alert.py` `radar_alert_due()`
  aufrufen / Then verwenden beide denselben importierten Wert — kein Literal `20` oder eigenes
  `_RADAR_ONSET_THRESHOLD_MIN` bleibt an den Aufrufstellen bestehen.
  - Test: `tests/tdd/test_radar_onset_threshold_variance.py::test_ac1_shared_threshold_drives_both_paths`
    — **Drift-Wächter statt Identitätsprüfung.** Ein `is`-Vergleich auf den Wert taugt nicht:
    55 ist ein zwischengespeicherter Kleinganzzahl-Wert, ein unabhängig hingeschriebenes
    Literal `55` bestünde die Prüfung ebenfalls. Stattdessen wird die geteilte Konstante zur
    Laufzeit auf einen Fremdwert (z. B. 30) umgesetzt und geprüft, dass **beide** Pfade
    daraufhin ihr Auslöseverhalten ändern (Onset 38: vorher Alarm in beiden, nachher in
    keinem). Nur eine echt geteilte Quelle besteht das; eine wieder eingeschlichene lokale
    Kopie fällt durch.

- **AC-2:** Given ein Trip mit heutiger Etappe und Radar-Frames an den erreichbaren Rasterwerten
  8/23/38/53/68/83 Minuten / When `TripAlertService.check_radar_alerts()` läuft / Then wird bei
  8/23/38/53 genau ein Alarm versendet, bei 68/83 keiner.
  - Test: `tests/tdd/test_radar_onset_threshold_variance.py::test_ac2_trip_variance_over_grid_values`
    — parametrisiert über die sechs Werte, echter `check_radar_alerts()`-Lauf mit realem
    `frame_source`-Doppelgänger (Muster `CountingFrameSource`), Zustellung über den
    `mail_sink`-Zähler wie in AC-3 — **kein echter Versand**: dies ist ein Kern-Test, er läuft
    im Commit-Gate und darf keine Postfächer berühren (#1477). Kein Mock der
    Entscheidungslogik. Schließt die dokumentierte
    Blindstelle (`nowcast_gate_fixtures.py:179,193` maskiert `onset_minutes` bislang mit
    Default 8 suiteweit).

- **AC-3:** Given ein Compare-Preset mit `radar_alert_enabled=true` und Radar-Frames an denselben
  sechs Rasterwerten / When `CompareRadarAlertService.check_all_compare_presets()` läuft / Then
  ist das Auslöseverhalten identisch zu AC-2 (8/23/38/53 lösen aus, 68/83 nicht) — Parität
  zwischen Trip- und Ortsvergleich-Pfad.
  - Test: `tests/tdd/test_radar_onset_threshold_variance.py::test_ac3_compare_variance_over_grid_values`
    — dieselbe Parametrisierung, echter `check_all_compare_presets()`-Lauf, `mail_sink`-Zähler
    statt echtem Versand (Muster `test_compare_radar_alert.py`), kein Mock der Entscheidungslogik.

- **AC-4:** Given ein Onset-Zeitpunkt, der wegen der neuen Schwelle über Mitternacht rutscht
  (z. B. `now`=23:30 lokal, `onset_minutes`=53 → 00:23 Folgetag) / When E-Mail- oder
  Telegram-Text gerendert wird / Then enthält der Text einen eindeutigen Tagesbezug (z. B.
  „morgen 00:23") statt der nackten, mehrdeutigen Uhrzeit „00:23"; bei einem Onset ohne
  Tageswechsel bleibt der Text exakt wie bisher (kein „heute"-Zusatz, byte-identisch).
  - Test: `tests/tdd/test_alert_onset_day_rollover.py::test_ac4_email_and_telegram_show_day_on_rollover`
    — echte `render_email`/`render_telegram`-Aufrufe mit konstruiertem `AlertMessage` bei
    Mitternachts-Overlap UND bei einem Kontrollfall ohne Overlap (Regressionsschutz), Text-Assert
    auf das sichtbare Ergebnis, kein Dateiinhalt-Check.

- **AC-5:** Given denselben Mitternachts-Überlauf-Fall / When die Kurznachricht (SMS und
  Premium-SMS, geteilter Renderer) gerendert wird / Then trägt der Token ein zeichensparendes
  Tages-Suffix (z. B. `TH@0:23+1`), bleibt GSM-7-verträglich und unter der 160-Zeichen-Grenze;
  ohne Tageswechsel bleibt der Token exakt wie bisher.
  - Test: `tests/tdd/test_alert_onset_day_rollover.py::test_ac5_sms_token_carries_day_suffix` —
    echter `_render_sms_onset`-Aufruf (bzw. der öffentliche SMS-Renderer-Einstieg), Assert auf
    Token-Inhalt, Zeichenlänge ≤ 160, ausschließlich GSM-7-Zeichen (`^[A-Za-z0-9@:+\- ]+$`
    o. ä. auf den konkreten Token, kein pauschaler Datei-Grep).

- **AC-6:** Given ein Trip, dessen aktives Segment vor dem berechneten Onset-Zeitpunkt endet
  (z. B. Segment endet 18:00, Onset läge bei 18:53) / When `check_radar_alerts()` läuft / Then
  wird kein Alarm versendet und ein Unterdrückungs-Log-Eintrag mit erkennbarem Grund geschrieben;
  liegt der Onset dagegen VOR dem Segmentende, löst derselbe Trip weiterhin regulär aus
  (Kontrollfall, Regressionsschutz).
  - Test: `tests/tdd/test_radar_alert_segment_end_guard.py::test_ac6_segment_end_guard_suppresses_late_onset`
    — echter Trip mit realer Etappe (`end_time` gesetzt), echter Frame bei Onset nach
    Segmentende → `alerts_sent == 0`; Kontrollfall mit Onset vor Segmentende → `alerts_sent == 1`
    im selben Testlauf, kein Mock des Gates.

## AC-Test-Mapping (Test-Plan)

| AC | Testdatei | Testfunktion |
|----|-----------|--------------|
| AC-1 | `tests/tdd/test_radar_onset_threshold_variance.py` | `test_ac1_shared_threshold_drives_both_paths` |
| AC-2 | `tests/tdd/test_radar_onset_threshold_variance.py` | `test_ac2_trip_variance_over_grid_values` |
| AC-3 | `tests/tdd/test_radar_onset_threshold_variance.py` | `test_ac3_compare_variance_over_grid_values` |
| AC-4 | `tests/tdd/test_alert_onset_day_rollover.py` | `test_ac4_email_and_telegram_show_day_on_rollover` |
| AC-5 | `tests/tdd/test_alert_onset_day_rollover.py` | `test_ac5_sms_token_carries_day_suffix` |
| AC-6 | `tests/tdd/test_radar_alert_segment_end_guard.py` | `test_ac6_segment_end_guard_suppresses_late_onset` |

### Bekannte Test-Kollisionen (MODIFY, keine neuen ACs — Bestandssemantik erhalten)

- `tests/tdd/test_feature_656_radar_nowcast.py:233-243` — die drei
  `radar_alert_due(..., threshold_min=20)`-Asserts wechseln auf den importierten
  `RADAR_ONSET_THRESHOLD_MIN`; der `later`-Fall (`onset_minutes=45`) muss auf einen Wert
  **oberhalb** von 55 angehoben werden (z. B. 100), sonst kippt er von „löst nicht aus" zu
  „löst aus" und der Test verliert seine ursprüngliche Aussage. Vorgehen analog
  `fix_1945_nowcast_horizon.md:72-78`.
- `tests/tdd/test_compare_radar_alert.py:400-436` — `_wet_frame(45)` im Negativtest
  (`assert sent == 0`) wird auf einen Wert oberhalb von 55 angehoben (z. B. 100), Testsemantik
  „später Onset löst nicht aus" bleibt erhalten.

### Doku-Nachzug (docs-only, kein Code)

| Datei | Änderung |
|---|---|
| `docs/specs/modules/radar_nowcast.md:19,75,94` | „Onset ≤ Schwelle (Default 20 min)" → „Default 55 min" |
| `docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md:344` | „Regen-Onset ≤ 20 min inhärent 'jetzt'" trägt bei 55 min nicht mehr unverändert — Zahl anheben, Fußnote: die Mitternachts-Mehrdeutigkeit ist jetzt über AC-4/AC-5 dieser Spec abgedeckt, kein Tagesfenster-Bezug im Sinne des dortigen Zeitfenster-Bausteins |
| `src/output/renderers/email/starkregen_hint.py:1-27` | Docstring behauptet „60-Minuten-Nowcast-Fenster" — vorbestehende #1945-Drift (Horizont ist seit #1945 180 Min), wird hier mitgezogen weil dieser Fix denselben Nowcast-Kontext dokumentiert |
| `src/services/radar_service.py:292-293` | „In den nächsten 2 Stunden kein Regen erwartet" → „3 Stunden" (konsistent mit `NOWCAST_HORIZON_MIN=180`), ebenfalls vorbestehende #1945-Drift |

## Explizit AUSGESCHLOSSEN

- **Zweiter Akut-Alarm zusätzlich zur Vorwarnung (Variante V2).** Dreifach strukturell
  blockiert: (1) die Sperrzeit (`check_nowcast_gate`) läuft VOR der Schwellen-Prüfung und würde
  eine Vorwarnung sofort verbrauchen; (2) `urgency_from_radar(is_convective=True)` gibt für
  Gewitter — den Ticket-Kernfall — immer `"HIGH"` zurück, der Eskalations-Durchbruch in
  `alert_gate.py:605-606` (nur bei höherer Dringlichkeit) ist damit unerreichbar; (3) dieselbe
  Dringlichkeit speist `split_by_threshold` (ADR-0046) — eine onset-getriebene Anhebung würde
  die vom Nutzer gesetzten Kanal-Schwellen still überschreiben. Eigenes Folgeticket, geschätzt
  drei Scheiben (Annäherungs-Zweig im Identitäts-Gate, Sperrzeit-Durchbruch, Doppel-Alarm-Guard).

- **Laufender Frame ausgeschlossen** (`radar_service.py:556`, `f.timestamp >= now`). Eigenständiger
  Korrektheitsdefekt („es regnet bereits, gemeldet wird 'in 8 Min'"), nicht Teil dieser Schwelle.
  Eine Änderung hier erzeugt zusätzlich den neuen Textfall „in 0 Min", der eigene
  Renderer-Behandlung bräuchte — eigenes Ticket.

- **Briefing-Unterdrückung #818 trifft bei größerem Fenster häufiger.** Der bestehende
  #883-Konvektions-Override (`trip_alert.py:1288`) schützt weiterhin den Gewitterfall
  (Ticket-Kern); nicht-konvektiver Regen wird bei größerem Vorlauf öfter unterdrückt, weil er
  häufiger eine bereits im Briefing angekündigte Stunde trifft. Bestehendes, unverändertes
  Verhalten — keine neue Regel in dieser Spec.

- **Entdopplung gegen den #1468-Verschiebungs-Alarm.** Es gibt heute keine gemeinsame
  Entdopplung zwischen dem Nowcast-Onset-Alarm und dem stundenvorhersage-basierten
  Verschiebungs-Alarm; diese Spec ändert daran nichts.

- **Nutzerseitige Einstellbarkeit der Schwelle.** `metric_alert_levels` ist pro Metrik
  organisiert (`alert_preset.py:183`); der Radar-`OnsetEvent` ist strukturell metriklos
  (`docs/reference/metric_output_matrix.md:212-223`) und erscheint nicht im Alarme-Reiter
  (`api_contract.md:3543-3549`). Ein Niveau darauf wäre ein Knopf, den niemand drehen kann —
  UI-Scheibe erst, wenn der PO die Schärfe wirklich einstellen will.

## Known Limitations

- **Eine Meldung pro Zelle, keine zweite Erinnerung.** Wegen der Ereignis-Identitäts-Sperre
  (`alert_gate.py:559-628`, Fenster ±180 Min um den Onset-Zeitpunkt) bleibt es bei genau einer
  Meldung pro Zelle — der Alarm wandert nach vorn (~53 statt ~8 Minuten Vorlauf), er verdoppelt
  sich nicht. Die späte Erinnerung kurz vor dem tatsächlichen Einschlag entfällt damit. Das ist
  der bewusste Handel dieser Spec (Vorlauf statt zwei Meldungen); ein zweiter, echter Akut-Alarm
  ist explizit ausgeschlossen (s. o.) und bräuchte ein eigenes Folgeticket.
- **Weiterhin nur 15-Minuten-Rastergenauigkeit.** Die absolute Genauigkeit des Onset-Zeitpunkts
  bleibt durch das Datenraster der Quelle begrenzt — mit der höheren Schwelle verteilen sich die
  gezeigten Werte nur über mehr Rasterpunkte (8/23/38/53), werden aber nicht "krummer" (gleiche
  Beobachtung wie in `fix_1945_nowcast_horizon.md`).
- 🔴 **Der Segment-Ende-Guard (AC-6) ist eine Ausgleichsmaßnahme mit Verfallsdatum.** Er
  unterdrückt Alarme, deren Onset nach dem Ende des aktiven Segments liegt — richtig **nur**,
  solange der Nowcast am **Startpunkt** des aktiven Segments abgefragt wird
  (`trip_alert.py:1256-1259`). Der Guard gleicht also einen falschen Messpunkt aus, er behebt
  ihn nicht. Sobald **#2017** den Abrufpunkt auf den interpolierten Aufenthaltsort zum
  Onset-Zeitpunkt umstellt, kehrt sich seine Wirkung um: Der Onset läge dann per Konstruktion
  dort, wo der Nutzer tatsächlich sein wird, und der Guard würde **korrekte** Alarme verwerfen.
  **Er ist mit dem Merge von #2017 ersatzlos zu entfernen**, zusammen mit AC-6 und
  `tests/tdd/test_radar_alert_segment_end_guard.py`. Das ist hiermit dokumentiert und daher
  **kein** stiller Spec-Widerruf, sondern der vorgesehene Weg. Gemessene Grundlage für #2017:
  Segmentdauer Median 69 Min, Ortsfehler während der Gehphasen Median 2,68 km, in 68 % der
  Geh-Minuten liegt der Onset nicht mehr im abgefragten Segment.
- **Ortsvergleich bleibt ohne Segment-Ende-Guard**, weil Compare-Presets strukturell keine
  Etappen/Segmente kennen — kein Implementierungsversäumnis, sondern Abbildung des
  Datenmodells (s. Implementation Details Punkt 3, Architektur-Entscheidung unten).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0021 (Trip und Ortsvergleich teilen den Code) — angewendet, kein neues ADR
  nötig.
- **Rationale:** ADR-0021 verlangt geteilten Code für geteilte Konzepte (hier: Onset-Schwelle,
  `radar_alert_due()`, Datumsbezug-Logik in den Renderern) — das setzt diese Spec konsequent um
  (Punkt 1 und 2 der Implementation Details betreffen beide Flächen identisch). Der
  Segment-Ende-Guard (Punkt 3) ist bewusst **nicht** geteilt, weil "Segment" im
  Ortsvergleichs-Datenmodell nicht existiert (Compare-Presets adressieren `location_ids`, keine
  Etappen — bereits dokumentiert in `compare_radar_alert.py:13-16`). Eine fehlende Funktion für
  ein nicht vorhandenes Konzept ist keine Asymmetrie im Sinne von ADR-0021; ein Verstoß läge nur
  vor, wenn beide Flächen dasselbe Konzept hätten und es nur auf einer Seite behandelt würde.

## Changelog

- 2026-08-20: Initial spec created (Issue #2009)
