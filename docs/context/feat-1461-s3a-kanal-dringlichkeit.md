# Context: feat-1461-s3a-kanal-dringlichkeit

Issue: [#1461](https://github.com/henemm/gregor_zwanzig/issues/1461) — Alerts S3:
Dringlichkeits-Schwelle je Kanal (Satelliten-SMS vs. E-Mail). Scheibe 3 von 5 im Epic
[#1458](https://github.com/henemm/gregor_zwanzig/issues/1458).
Track: **Full Process** (Intake-Score 5: Umfang High · Auswirkung High · Unsicherheit Medium).

**Scheiben-Zuschnitt (PO-go 2026-08-04):** Diese Scheibe ist **S3a — die Schwelle wirkt**.
Bedienoberfläche (`AlertChannelPicker.svelte`) ist ausdrücklich **S3b** und NICHT Teil dieser
Arbeit. Voreinstellung von S3a muss das heutige Verhalten unverändert lassen.

## Request Summary

Bedingung (a) des Relevanz-Filters aus #1458: *der Nutzer will darüber **auf diesem Kanal**
informiert werden.* Eine Satelliten-SMS kostet Geld und Akku, eine E-Mail nichts — dieselbe
Wetterlage rechtfertigt auf dem einen Kanal eine Nachricht und auf dem anderen nicht. Heute
bekommen **alle** eingeschalteten Kanäle denselben Strom.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/notification_service.py:1048` `_dispatch_alert_message()` | Versandpunkt für **zwei der drei Quellen**. Vier Aufrufer: 484 Trip-Δ · 563 Compare-Δ · 634 Compare-Radar · 1038 Trip-Radar |
| `src/services/notification_service.py:644` `send_official_alert()` · `:840` `send_multi_location_official_alert()` | 🔴 **Zweiter Versandpunkt.** Amtliche Warnungen laufen am gemeinsamen Punkt VORBEI und haben eigene Kanal-Zweige (E-Mail :695, Telegram :707, SMS :731) |
| `src/services/trip_alert.py:1156` `_effective_alert_channels()` | Liefert das Kanal-Set. Braucht **keine** Änderung: die Schwelle entscheidet je Kanal, nicht welche Kanäle es gibt |
| `src/services/alert_log.py:124` `append_entry()` | Geteilte Protokoll-Schreibfunktion (#1459). Führt bereits `severity` und trennt `entries` / `not_delivered` |
| `src/services/deviation_alert_engine.py:245` `_highest_severity()` | Vorhandener Baustein „höchste Dringlichkeit einer Meldung" → `"LOW"`/`"MODERATE"`/`"HIGH"` |
| `src/app/models.py:469` `ChangeSeverity` | `minor`/`moderate`/`major` — Dringlichkeit je einzelner Änderung |
| `src/app/models.py:850` `AlertSeverity` | `info`/`warning`/`critical` — Dringlichkeit je Alarm-Regel |
| `src/services/weather_change_detection.py:216-218` | **Die Abbildung zwischen beiden existiert bereits**: INFO↔MINOR, WARNING↔MODERATE, CRITICAL↔MAJOR |
| `src/output/renderers/alert/model.py:65` `AlertMessage` | Kanonische Nachricht über alle Kanäle — **trägt heute KEINE Dringlichkeit** |
| `internal/store/log.go:48` `AlertLogEntry` | Protokoll-Struktur mit Feld `Severity string` |
| `internal/model/trip.go:137-142` `AlertChannels *AlertChannelsConfig` | Zeiger-Muster (nil = erben). Vorbild für ein neues Schwellen-Feld |
| `src/services/trip_alert.py:526-536` | Fallback-Pfad mit dem im Issue-Kommentar gemeldeten Doppelzähl-Randfall |

## Existing Patterns

- **Geteilter Versandpunkt für Änderung und Radar** (ADR-0021, ADR-0011): Der Ortsvergleich
  geht durch dieselbe Funktion wie der Trip — eine Schwelle dort wirkt für beide. Das erfüllt
  die Teilungs-Vorgabe **innerhalb dieser zwei Quellen**; der amtliche Weg ist davon getrennt
  (s. Befund 6).
- **Zeiger-Muster für vererbbare Einstellungen**: `AlertChannels *AlertChannelsConfig`,
  `json:"…,omitempty"`, `nil` = erben (#1258 S3). Read-Modify-Write beim Speichern.
- **Fail-soft-Protokoll**: `append_entry()` entscheidet die Ziel-Liste selbst; leeres
  Kanal-Set ⇒ gar kein Eintrag.

## Gemessene Befunde (nicht aus dem Issue übernommen)

1. **Die Dringlichkeit ist am Versandpunkt nicht verfügbar.** `AlertMessage` trägt sie nicht —
   sie geht bei der Projektion von `WeatherChange` in die Nachricht verloren. Damit die
   Schwelle an der einen richtigen Stelle greifen kann, muss die Dringlichkeit dort ankommen
   (additives Feld auf `AlertMessage` oder eigener Parameter). Ohne das bliebe nur die
   Entscheidung bei den **vier** Aufrufern — genau die Vervierfachung, die #1481 verhindern
   soll.

2. **Es gibt EIN Protokoll-Vokabular, aber es ist nicht durchgängig abgeleitet.**
   `_highest_severity()` liefert `LOW`/`MODERATE`/`HIGH`; alle vier Schreibstellen benutzen
   dieses Vokabular. **Aber zwei der drei Quellen setzen eine Konstante statt eines
   gemessenen Werts:**

   | Quelle | Schreibstelle | Wert |
   |---|---|---|
   | Vorhersage-Änderung (Trip) | `trip_alert.py:282` | abgeleitet über `_highest_severity()` |
   | Vorhersage-Änderung (Vergleich) | `compare_alert.py:194` | abgeleitet über `_highest_severity()` |
   | Nowcast/Radar (Trip) | `trip_alert.py:872` | **fest `"HIGH"`** |
   | Nowcast/Radar (Vergleich) | `compare_radar_alert.py:137` | **fest `"HIGH"`** |
   | Amtliche Warnung (Trip) | `trip_alert.py:1141` | **fest `"MODERATE"`** |
   | Amtliche Warnung (Vergleich) | `compare_official_alert.py:151` | **fest `"MODERATE"`** |

   🔴 **Die gefährlichste Folge:** Eine amtliche Unwetterwarnung der höchsten Stufe zählt
   heute pauschal als `MODERATE`. Wer auf der Satelliten-SMS „nur höchste Dringlichkeit"
   einstellt, bekäme sie **nicht** — obwohl sie genau der Fall ist, für den der teure Kanal da
   ist. Eine Schwelle auf diese Skala zu setzen, ohne die amtliche Warnstufe durchzureichen,
   baut den #638-Fehler nach: die Einstellung täte das Gegenteil ihres Versprechens.

3. **Das Briefing liest das Alarm-Protokoll heute NICHT.** Weder `trip_report_scheduler.py`
   noch ein Renderer greift auf `alert_log`/`not_delivered` zu (gemessen: null Treffer). Die
   Pflicht 2 des Issues („was ein Kanal nicht bekam, wird im nächsten Briefing sichtbar") hat
   damit **keinen Anknüpfungspunkt** — sie ist Neubau, nicht Erweiterung. Umfangsrelevant.

4. **Go liest das Feld `Severity` nicht aus.** In `internal/handler/cockpit.go` kommt es nicht
   vor — die Dringlichkeit steht im Protokoll, wird aber nirgends angezeigt.

5. **`_effective_alert_channels()` braucht keine Änderung.** Es beantwortet „welche Kanäle",
   nicht „wie dringend". Die Schwelle ist eine zweite, unabhängige Frage.

6. 🔴 **Es gibt ZWEI Versandpunkte, nicht einen** (Korrektur der ersten Fassung dieses
   Dokuments — nachgemessen über die Funktionsgrenzen in `notification_service.py`).
   `_dispatch_alert_message()` bedient Vorhersage-Änderung und Radar (4 Aufrufer: 484, 563,
   634, 1038). **Amtliche Warnungen laufen daran vorbei**: `send_official_alert()` (:644) und
   `send_multi_location_official_alert()` (:840) haben eigene Kanal-Zweige. Eine Schwelle
   allein am gemeinsamen Punkt erfasst ausgerechnet die Meldungsart nicht, für die ein teurer
   Kanal am ehesten gerechtfertigt ist.

7. 🔴 **Eine Dringlichkeits-Schwelle je Kanal EXISTIERT BEREITS — fest verdrahtet.**
   `src/output/tokens/hazard_symbols.py:37`: `MIN_SMS_LEVEL = 3`, Kommentar „Sicherheits-Filter:
   nur orange (3) und rot (4) erreichen SMS/Telegram". In Gebrauch an vier Stellen
   (`renderers/alert/official_alerts.py:388`, `renderers/narrow.py:369`,
   `renderers/comparison.py:656`, Import `official_alerts.py:25`). Sie greift als **Render**-
   Filter, nicht als Versandentscheidung, gilt nur für amtliche Warnungen und ist nicht
   einstellbar. Genau die Frage, die #1461 dem Nutzer geben will, ist hier bereits beantwortet —
   nur unveränderlich. **Die neue Schwelle muss diese Stelle aufnehmen, nicht daneben treten**
   (sonst zwei Schwellen für dieselbe Frage — die Wiederholungs-Klasse aus #1481).

8. **Amtliche Warnungen tragen eine echte Stufe.** `OfficialAlert.level: int` 1–4
   (`src/services/official_alerts/models.py:16-22`), in **allen sechs** Quellen aus der
   Behördenangabe abgeleitet (Vigilance `vigilance.py:132`, MeteoAlarm `meteoalarm.py:634`,
   GeoSphere `geosphere_warn.py:142`, DPC `dpc.py:202`, Météo des forêts `meteo_forets.py:113`,
   Massiv-Sperre `massif_closure.py:68`). Sie überlebt bis in alle Renderer (Farbe, Wort,
   SMS-Buchstabe) — verloren geht sie nur bei der Kanalwahl und im Protokoll.

9. **Radar-Alarme tragen ebenfalls eine Abstufung — sie wird nur nicht gelesen.**
   `NowcastResult.intensity_label` ist vierstufig (`radar_service.py:123-140`: kein Nieder-
   schlag / leicht / mäßig / stark, plus `is_convective` → „Starker Hagel/Gewitter"), und beide
   Werte liegen am Protokoll-Aufruf im `OnsetEvent` vor
   (`src/output/renderers/alert/model.py:37-38`). Die Auslösung selbst ist binär
   (`trip_alert.py:75-78`: Regenbeginn ≤ 20 Min, ab 0,1 mm/h). **Folge:** leichter Nieselregen
   in 19 Minuten wird heute als `HIGH` gebucht, eine amtliche Unwetterwarnung als `MODERATE` —
   und dieser Unterschied ist im Cockpit als Farbpunkt sichtbar
   (`frontend/src/routes/+page.svelte:400-404`).

10. **Der Trip-Radar-Alarm hat keine Nutzer-Steuerung.** `radar_alert_enabled` existiert nur am
    ComparePreset (`src/app/models.py:966`, `internal/model/compare_preset.go:60`), bedient über
    `AlarmeTab.svelte:323-331`, sichtbar nur im Kontext „vergleich"
    (`alarme-tab/alarmeTabSections.ts:27-30`). Beim Trip läuft der Radar-Alarm, sobald irgendein
    Kanal aktiv ist. Für S3a nur als Randbedingung wichtig: die Kanal-Schwelle wird beim Trip
    die **einzige** inhaltliche Steuerung des Radar-Alarms.

## Dependencies

- **Upstream:** `ChangeSeverity` (models.py) → `_highest_severity()` → `EvaluationResult.severity`
  → `alert_log.append_entry()`. Amtliche Warnungen: `OfficialAlert` → `build_official_alert_notices()`.
- **Downstream:** alle vier Alarmwege (Trip-Δ, Trip-Radar, Trip-amtlich, Compare-Δ/-Radar/-amtlich),
  `NotificationResult.sent_channels`/`failed_channels`, Cockpit-Kachel und Archiv-Statistik
  (lesen `entries`, nicht `not_delivered`).
- **Persistenz:** neues Feld auf Trip **und** ComparePreset ⇒ Go-Modell, Python-Modell,
  TypeScript-Typ. Read-Modify-Write-Pflicht (CLAUDE.md „Daten-Schema-Reworks").

## Existing Specs & ADRs

- `docs/specs/modules/feat_1459_alert_protokoll.md` — Scheibe 1, die Sicherheitsleine
- `docs/specs/modules/rework_1460_t1_relevanzfilter.md` — Scheibe 2, drei Quellen / ein Filter
- `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` — Scheibe 2 Teil 2 (Reste offen)
- `docs/specs/modules/feat_864_859_alert_presets.md` — Empfindlichkeitsstufen je Metrik
- `docs/specs/modules/compare_official_alert_channels.md` — Kanäle im amtlichen Compare-Pfad
- **ADR-0009** Alerts sind Abweichungs-Wächter, keine absoluten Schwellen ·
  **ADR-0013** `threshold` ist Δ-Sensitivität · **ADR-0016** amtliche Warnungen als additiver
  Typ · **ADR-0021** geteilte Deviation-Alert-Engine · **ADR-0011** ein Backend-Renderer

## Risks & Considerations

1. 🔴 **Rote Linie #638 — gewolltes vs. ungewolltes Stummschalten.** Am 2026-06-09 wurde die
   Dringlichkeits-Auswahl aus der Oberfläche entfernt, weil „Info" intern `MINOR` bedeutete und
   der Filter erst ab `MODERATE` versendete: der Nutzer stellte einen Alarm ein und bekam nie
   einen. Befund 2 oben zeigt, dass **derselbe Fallstrick heute noch liegt** — nur an anderer
   Stelle (amtliche Warnung pauschal `MODERATE`).
2. 🔴 **Nie spurlos verschwinden.** Liegt eine Meldung auf *allen* Kanälen unter der Schwelle,
   muss sie protokolliert **und** sichtbar werden. Befund 3: der Sichtbarkeits-Teil ist Neubau.
3. **Voreinstellung muss verhaltensneutral sein.** S3a ohne Bedienoberfläche darf für keinen
   bestehenden Nutzer etwas ändern — nachzuweisen, nicht zu behaupten.
4. **Doppelzählung im Protokoll** (Issue-Kommentar 2026-08-02): Vorhersage-Änderung + amtliche
   Warnung + Versandausfall gleichzeitig ⇒ zwei `not_delivered`-Einträge für eine Meldung,
   Ursache `trip_alert.py:526-536`. Wer für die Schwelle auswertet, zählt doppelt.
5. **Mandantentrennung:** neues persistiertes Feld ⇒ Pflichttest mit **zwei** verschiedenen
   Nutzern (CLAUDE.md).
6. **Zeilen-Limit 250.** Backend + Datenfeld in drei Sprachen + Sichtbarkeit im Briefing liegt
   hart an der Grenze. Falls die Sichtbarkeit den Rahmen sprengt, ist sie der Kandidat für eine
   eigene Scheibe — aber **nicht** ersatzlos streichen: sie ist die Sicherheitsleine gegen #638.
7. **Teilungs-Gate:** Der Versandpunkt ist geteilt — jede Compare-eigene Lösung wäre ein
   Verstoß gegen die mehrfach bekräftigte PO-Vorgabe (#1170 als Anti-Pattern).

## Analysis

### Type
Feature (Epic-Scheibe), kein Bug.

### Der Befund, der den Zuschnitt ändert

Die Schwelle soll entscheiden „ist diese Meldung dringend genug für diesen Kanal?". Gemessen
(Befunde 8–9): **Zwei der drei Meldungsarten sind heute falsch eingestuft** — Radar pauschal
`HIGH`, amtlich pauschal `MODERATE`, beides Konstanten. Konkret bedeutet das: leichter
Nieselregen in 19 Minuten steht als `HIGH` im Protokoll, eine amtliche Unwetterwarnung (rot,
Stufe 4) als `MODERATE`.

Eine Schwelle auf diese Einstufung würde bei „nur das Dringendste auf die Satelliten-SMS"
**den Nieselregen durchlassen und die Unwetterwarnung unterdrücken**. Das ist nicht ein
Schönheitsfehler der Umsetzung, sondern die Wiederholung von #638 mit umgekehrtem Vorzeichen:
eine Einstellung, die das Gegenteil ihres Versprechens tut.

⇒ **Die Einstufung muss vor der Schwelle stimmen.** Sie ist keine Vorarbeit, die man mitnehmen
kann — sie ist die Voraussetzung dafür, dass die Schwelle überhaupt eine sinnvolle Aussage
trifft.

### Empfohlener Zuschnitt (Abweichung vom Intake — PO-Entscheidung nötig)

| Scheibe | Inhalt | Wirkung nach außen |
|---|---|---|
| **S3a (diese)** | Die Dringlichkeit wird wahr: EINE geteilte Ableitung für alle drei Quellen (amtlich aus `OfficialAlert.level`, Radar aus `intensity_label`/`is_convective`/`onset_minutes`, Änderung unverändert aus `_highest_severity()`). Protokoll trägt den echten Wert statt zweier Konstanten. | **Kein Alarm ändert sich** — weder ob noch wohin noch wann. Nutzersichtbar ändert sich allein die **Farbe des Punkts im Cockpit**, und zwar von falsch nach richtig. |
| **S3b** | Die Schwelle wirkt und wird bedienbar: Datenfeld je Kanal, Entscheidung an **beiden** Versandpunkten, `MIN_SMS_LEVEL` geht darin auf, Sicherheitsleine, `AlertChannelPicker.svelte`. | Der Nutzer kann Kanäle nach Dringlichkeit trennen. |

**Warum dieser Schnitt besser ist als der ursprüngliche:** S3a ist klein (~100 statt ~250
Zeilen), vollständig verhaltensneutral im Versand, und liefert für sich genommen bereits einen
echten Nutzen (das Cockpit sagt die Wahrheit). Vor allem: Er macht die #638-Falle
**unmöglich**, statt sie in der Spezifikation abfangen zu müssen.

### Technischer Ansatz für S3a

1. **Neues Modul `src/services/alert_urgency.py`** — eine reine Funktion je Quelle, die auf das
   bestehende Vokabular `LOW`/`MODERATE`/`HIGH` abbildet. Projektmuster: genau wie
   `alert_log.py` (geteilte Schreibfunktion, #1459) und `compare_alert_guard.py` (geteilter
   Riegel, #1467 AG6) — **ein** Modul, sechs Aufrufer, keine Kopie.
2. **Sechs Aufrufstellen** ersetzen ihre Konstante durch den Aufruf: `trip_alert.py:872`
   (Radar), `:1141` (amtlich), `compare_radar_alert.py:137`, `compare_official_alert.py:151`;
   `compare_alert.py:194` bleibt inhaltlich gleich, geht aber ebenfalls durch das neue Modul.
   **Korrektur (nachgemessen 2026-08-04):** `trip_alert.py:282` bleibt **nicht** inhaltlich
   gleich — `eval_result.severity` ignoriert dort die mitgebündelten amtlichen Warnungen
   (`notification_service.py:1106`). Nach E5 („höchste gewinnt") ändert sich der
   protokollierte Wert, sobald `official_notices` nicht leer sind. Im Versand bleibt es
   neutral; nur die Einstufung wird richtig.
3. **Die amtliche Abbildung nutzt die bereits vorhandene Zuordnung**
   `LEVEL_LETTERS = {2: "L", 3: "M", 4: "H"}` (`hazard_symbols.py:34`, in Gebrauch bei
   `renderers/alert/official_alerts.py:395`). Sie ist bitgenau unsere Abbildung, nur mit
   anderen Wörtern — es entsteht **keine** zweite Zahlenreihe für Stufengrenzen. `MIN_SMS_LEVEL`
   ist davon unberührt der *Filter* und bleibt in S3a unverändert in Kraft (Ablösung in S3b).
4. **Die Radar-Labels werden benannte Konstanten** in `radar_service.py` (Quelle:
   `intensity_to_text()`, `:123-140`), gegen die `alert_urgency.py` vergleicht — nicht gegen
   Zeichenketten. Grund (nachgemessen): Der Trip-Pfad senkt den ersten Buchstaben
   (`trip_alert.py:826-827`: `_label[:1].lower() + _label[1:]`), der Compare-Pfad reicht
   Title-Case durch. Ein naiver Vergleich hätte im Trip-Pfad **nie** getroffen und wäre still
   auf die niedrigste Stufe gefallen — ohne dass ein Test anschlägt.

### Affected Files (S3a)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/alert_urgency.py` | CREATE | Geteilte Ableitung Quelle → `LOW`/`MODERATE`/`HIGH` |
| `src/services/trip_alert.py` | MODIFY | zwei Konstanten (`:872`, `:1141`) durch Aufruf ersetzen |
| `src/services/compare_radar_alert.py` | MODIFY | Konstante `:137` ersetzen |
| `src/services/compare_official_alert.py` | MODIFY | Konstante `:151` ersetzen |
| `src/services/compare_alert.py` | MODIFY | `:194` auf das geteilte Modul umstellen |
| `tests/tdd/test_alert_urgency.py` | CREATE | Ableitung je Quelle, inkl. Grenzfälle |

**Kein** Go, **kein** Frontend, **keine** Persistenz-Änderung, **keine** Migration.

### Scope Assessment
- Dateien: 6 (1 neu, 4 geändert, 1 Testdatei)
- Geschätzte Zeilen: **+110 / −20** — deutlich unter der 250er-Grenze
- Risiko: **NIEDRIG** (kein Versandverhalten berührt, keine Persistenz)

### Open Questions (für die Spec)
- [ ] Abbildung amtliche Stufe → Dringlichkeit: `2=gelb→LOW`, `3=orange→MODERATE`,
      `4=rot→HIGH`? (Stufe 1 kommt in Alarmen nicht vor — die Quellen filtern <2 weg.)
- [ ] Abbildung Radar → Dringlichkeit: entlang `is_convective` (Gewitter/Hagel ⇒ `HIGH`) und
      `intensity_label`? Zählt die Vorlaufzeit (`onset_minutes`) mit, oder ist Stärke allein
      maßgeblich?
- [ ] Trägt eine Meldung mit mehreren Quellen (Änderung **und** amtliche Warnung im selben
      Lauf, `notification_service.py:1106`) die höchste der beteiligten Dringlichkeiten?
