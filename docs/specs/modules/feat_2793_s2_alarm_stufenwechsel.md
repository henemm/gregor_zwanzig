---
entity_id: feat_2793_s2_alarm_stufenwechsel
type: module
created: 2026-11-08
updated: 2026-11-08
status: approved
version: "1.0"
tags: [alarm, ampel, abweichung, migration, dringlichkeit, sms, telegram, mail, i18n, epic-2791]
---

# Alarm nach Stufenwechsel der Ampel oder großem Sprung, mit Abbildung der alten Stufen (S2, #2793)

## Approval

- [x] Approved (PO-Freigabe 2026-11-08 per Rückfrage: „Freigabe“)

## Purpose

Heute entscheidet über einen Abweichungs-Alarm eine eigene Δ-Stufe je Metrik (`metric_alert_levels`: off/entspannt/standard/sensibel), unabhängig von der Profil-Ampel, die seit S1 das Briefing färbt. S2 macht die Ampel zum Auslöser: Je Metrik gilt „Alarm ab: Nie · Gelb · Orange · Rot“ (`ampel.metrics.<id>.alarm_ab`, seit S1 gespeichert, bisher ungelesen). Ein Alarm kommt, wenn die Farbe gegenüber dem Anker auf oder über diese Stufe steigt oder innerhalb einer solchen Stufe ein sehr großer Sprung passiert. Eine Entwarnung kommt, wenn die Farbe unter die Stufe fällt. Die alten Stufen werden einmalig nach ADR-0106 P3 überführt, ohne Datenverlust.

Entscheidungsgrundlage: ADR-0106 (Akzeptiert, P1 CAPE, P2 Gewitter „leicht“, P3 Altstufen); ADR-0013 Nachtrag (Δ bleibt als Sprung-Schwelle); PO-Entscheidungen 2026-11-08 (Rückfrage in dieser Sitzung): **D1** Sprung-Schwelle = heutige Spalte „standard“, **D2** Entwarnung nur beim Fallen unter „Alarm ab“, **D3** Dringlichkeit aus der Farbe, **D4** Nullgradgrenze und Beginn-Verschiebung laufen bis S7 wie heute. Code-Befunde: `docs/context/feat-2793-s2-alarm-stufenwechsel.md`.

**Nicht Teil von S2:** neue Bedienoberfläche „Alarm ab“ (S3a #2794), Kanal-Vorbelegungen (S9 #2801), Radar-Alarm für Trips (S8 #2800), Ampel für Nullgradgrenze/Schneefallgrenze/Schneehöhe/Nacht-Tiefsttemperatur (S7 #2799), Rückbau von `alert_rules` und seiner Kanal-Union (Übergabe #1895 bleibt offen, siehe Known Limitations).

## Source

- **Python-Core:** `src/services/deviation_alert_engine.py`, `src/services/weather_change_detection.py`, `src/services/alert_preset.py`, `src/services/alert_urgency.py`, `src/services/trip_alert.py`, `src/services/compare_alert.py`, `src/app/ampel.py`, `src/output/renderers/alert/{model,project,render}.py`, `src/i18n/messages/{de,en}/alarm.json`, `scripts/migrate_2793_alarm_ab.py` (neu)
- **Go-API:** `internal/handler/ampel.go` (Gewitter-Prüfung)
- **Frontend:** `frontend/src/lib/components/alerts-tab/AlertMetricLevelRow.svelte`, `AlertMetricLevelTable.svelte`, `frontend/src/lib/components/shared/AlarmeTab.svelte` (`context="route"|"vergleich"`)

> Querschnitt: Trip und Orte nutzen dieselbe `DeviationAlertEngine` (ADR-0021) und dieselben Frontend-Bausteine, keine neue Komponente mit Pendant. Alle vier Kanäle (E-Mail · Telegram · SMS · Premium-SMS) tragen dieselbe Aussage. Die Migration bewegt Nutzerdaten ⇒ Test mit zwei Nutzern.

## Estimated Scope

- **LoC:** ~650 Code + ~900 Tests (über zwei PRs, siehe Schnitt)
- **Files:** ~20
- **Effort:** high

**Schnitt (zwei PRs, Reihenfolge verbindlich):**
- **S2a — Migration und Prüfung, ohne Wirkung:** Migrationsskript, Gewitter-Prüfung `alarm_ab` in Python und Go. Nach dem Merge: Probelauf, `--execute`, Kontroll-Lauf „Nichts zu tun“ auf Staging und Prod. `alarm_ab` wird noch nicht gelesen, also ändert sich für Nutzer nichts.
- **S2b — Umschalten:** Engine, Dringlichkeit, Texte aller vier Kanäle, Frontend nur lesbar, Doku. **Gate:** Prod-Deploy von S2b erst, wenn der Kontroll-Lauf der Migration auf Prod „Nichts zu tun“ meldet (unmittelbar vor dem Deploy erneut prüfen).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.ampel.resolve_ampel`, `ampel_stufe`, `thunder_color` | Funktion (S1) | Farbe eines Werts je Abo, Vorlagen-Rückfall |
| `app.ampel_templates` | Daten (S1) | Vorgabe `alarm_ab` je Vorlage und Metrik (für P3) |
| `DeviationAlertEngine` | Klasse (ADR-0021) | geteilte Auslösung Trip und Orte |
| `alert_preset._PRESET_TABLE` | Daten | Spalte „standard“ wird Sprung-Schwelle (D1) |
| `alert_channel_threshold.split_by_threshold` | Funktion (ADR-0046) | Kanal-Schwelle, unverändert, liest neue Dringlichkeit |
| `scripts/migrate_2792_profil_ampel.py` | Skript (S1) | Vorbild für Ablauf, Sicherung, Sperre |
| #2794 (S3a) | Folgearbeit | Oberfläche „Alarm ab“, Erklärsätze der Metrik-Zeile |
| #2799 (S7) | Folgearbeit | Ampel für Nullgradgrenze, Schneefallgrenze, Schneehöhe, Nacht |

## Implementation Details

### 1. Welche Metriken nach der Ampel alarmieren

| Katalog-ID | Feld der Zusammenfassung | Seite | Sprung-Schwelle (D1, Spalte „standard“) | heute aus |
|---|---|---|---|---|
| `temperature` | `temp_max_c` (oben), `temp_min_c` (unten) | beidseitig | oben 6 °C, unten 5 °C | `temperature_max/min`, `temperature_change` |
| `wind` | `wind_max_kmh` | oben | 25 km/h | `wind_change` |
| `gust` | `gust_max_kmh` | oben | 20 km/h | `wind_gust` |
| `precipitation` | `precip_sum_mm` | oben | 10 mm | `precipitation_sum`, `precipitation_change` |
| `fresh_snow` | `snow_new_sum_cm` | oben | 8 cm | `fresh_snow` |
| `visibility` | `visibility_min_m` | unten | kein Sprung-Zweig | `visibility` (Unterschreiten) |
| `uv_index` | `uv_index_max` | oben | kein Sprung-Zweig | – (alle Vorlagen „Nie“) |
| `thunder` | `thunder_level_max` | Stufe | kein Sprung-Zweig | `thunder_level` |

- **Bleiben bis S7 auf der heutigen Δ-Logik (D4):** `freezing_level`/`snow_line` (Nullgradgrenze) und die Beginn-Verschiebung `thunder_onset`, `precipitation_heavy_onset`. Sie lesen weiter `metric_alert_levels` (migrierter Altwert bleibt in der Datei; ohne Eintrag „standard“ wie heute), mit heutiger Dringlichkeit und heutigem Text.
- **Entfallen als eigener Auslöser:** CAPE (ADR-0106 P1, geht über die Gewitterstufe ein) und die Delta-Metriken `temperature_change`, `wind_change`, `precipitation_change` (gehen in der Ampel-Metrik derselben Größe auf, ihr Δ ist die Sprung-Schwelle).
- **Nie Auslöser:** Vorboten nach ADR-0010 (`wind_chill`, `dewpoint`, `humidity`, `rain_probability`, `cloud_total`, `pressure`) und reine Anzeigegrößen, auch wenn in der Datei `alarm_ab` ≠ `never` steht. `temperature_night`, `snow_depth`, `snowfall_limit` haben in S2 noch keinen Ampel-Leser und alarmieren über die Ampel erst mit S7.
- **Aktivierung bleibt:** Eine Metrik prüft nur, wenn sie im Reiter Wetter aktiv ist (`is_alert_metric_active`, wie heute) **und** `alarm_ab` ≠ `never`.

### 2. Entscheidung je Metrik und Segment/Ort

Rangfolge der Farben: grün 0 < gelb 1 < orange 2 < rot 3; `alarm_ab` als Rang: yellow 1, orange 2, red 3, never = nie. Farbe von Anker- und Neuwert über `ampel_stufe` bzw. `thunder_color` der **Abo-Ampel** (die Seite, auf der der Wert liegt; beidseitige Metriken bekommen die Farbe ihrer Seite). Für `temperature` werden `temp_max_c` (Hitze) und `temp_min_c` (Kälte) getrennt geprüft, mit demselben `alarm_ab`.

| Fall | Bedingung | Ergebnis |
|---|---|---|
| **Verschärfung** | Rang neu > Rang Anker **und** Rang neu ≥ `alarm_ab` | Alarm „von {alt} auf {neu} gestiegen“ |
| **Sprung** | Rang neu = Rang Anker ≥ `alarm_ab` **und** Änderung in Richtung „schlechter“ (oben: steigt, unten: fällt) **und** `|neu − Anker|` ≥ Sprung-Schwelle | Alarm „weiter {Farbe}, großer Sprung“ |
| **Entwarnung** | Rang Anker ≥ `alarm_ab` **und** Rang neu < `alarm_ab` | Entwarnung „von {alt} auf {neu} zurückgegangen“ |
| sonst | u. a. Rückgang innerhalb des Alarmbereichs (D2), Anstieg unterhalb von `alarm_ab`, unveränderter Wert, Sprung nach unten | kein Alarm |

- **Gewitter:** Ordinal über `thunder_color` (keins grün, „leicht“ fest gelb, mittel/hoch nach `ampel.thunder`, Wassersport mittel = rot). „Leicht“ alarmiert nie (P2): da `alarm_ab` bei Gewitter nie `yellow` ist, ergibt sich das aus der Tabelle.
- **Prüfung `alarm_ab` bei Gewitter** (Lücke aus S1): erlaubt sind `never`, `orange`, `red`; `yellow` wird in Go beim Speichern mit `ampel_ungueltig` abgelehnt und in Python beim Laden protokolliert und durch die Vorgabe der Vorlage ersetzt (wie jede ungültige Ampel).
- **Gate:** Das bestehende Gate „Abo hat eine aktive Alarmquelle“ (`trip_alert.py:686-700`, `:1187-1219`; Gate-Fälle 1–4 der #1895-Übergabe) bleibt unverändert. Zusätzlich: Hat keine aktive, alarmfähige Metrik ein `alarm_ab` ≠ `never` und ist keine D4-Metrik aktiv, entsteht kein Alarm.
- **Anker, Ruhezeit, Cooldown, Tageslimit, Stille Stunden, „Briefing steht bevor“, amtliche Warnungen, Radar-Alarm:** unverändert.
- **Dedup feldselektiv:** Ein Ereignis gilt als schon gemeldet, wenn für `metric:segment_id` zuletzt dieselbe Farbe gemeldet wurde und `|neu − zuletzt gemeldet|` < Sprung-Schwelle (ohne Sprung-Zweig: dieselbe Farbe). So meldet derselbe Stufenwechsel nie zweimal.
- `AlertEvent` trägt zusätzlich `stufe_von`, `stufe_bis` (Protokoll-Token `green|yellow|orange|red`) und `art` (`verschaerfung|sprung|entwarnung`); `threshold` ist bei Ampel-Ereignissen die Sprung-Schwelle (ADR-0013 Nachtrag).

### 3. Dringlichkeit (D3)

- Verschärfung und Sprung: Farbe **neu** (gelb = gering, orange = mittel, rot = hoch).
- Entwarnung: Farbe des **Ankers**, also die verlassene Farbe (rot → gelb = hoch, orange → grün = mittel). Ersetzt die heutige Regel „Entwarnung immer hoch“ (`tests/tdd/test_alert_change_urgency_grading.py` AC-5/6 werden umgekehrt).
- Mehrere Ereignisse: die höchste. D4-Metriken behalten die heutige Dringlichkeit.
- Kanal-Schwelle (ADR-0046), Sperrzeit-Durchbruch und Protokoll lesen diese Dringlichkeit unverändert weiter.

### 4. Texte (alle vier Kanäle, DE/EN über den Katalog)

- **E-Mail und Telegram (rich):** Kopfzeile je Ereignis über neue Schlüssel in `alarm.json`, Platzhaltermengen DE = EN:
  - `alarm.ampel.gestiegen`: DE „{label} von {farbe_von} auf {farbe_bis} gestiegen: {von} → {bis}“ · EN „{label} rose from {farbe_von} to {farbe_bis}: {von} → {bis}“
  - `alarm.ampel.sprung`: DE „{label} weiter {farbe}, großer Sprung: {von} → {bis}“ · EN „{label} still {farbe}, large jump: {von} → {bis}“
  - `alarm.ampel.entwarnung`: DE „Entwarnung {label}: von {farbe_von} auf {farbe_bis} zurückgegangen ({von} → {bis})“ · EN „All clear {label}: back from {farbe_von} to {farbe_bis} ({von} → {bis})“
  - Farbwörter `alarm.ampel.farbe.{green,yellow,orange,red}`: DE grün/gelb/orange/rot · EN green/yellow/orange/red. Bei `temperature` nennt `{label}` die Seite (bestehende Labels Tageshöchst/Tagestief).
  - Der Bezug „seit dem Briefing von {Zeit}“ bleibt (ADR-0056, bestehende Fußzeile/`alarm.mail.verglichen`).
  - Das Urteil „Änderung über/unter deiner Alarm-Schwelle ({schwelle})“ (`alarm.abweichung.urteil`) entfällt für Ampel-Ereignisse; es bleibt für D4-Metriken. Stundenzeilen (#1737) unverändert.
- **SMS, Premium-SMS, Telegram-Kurzform** (ein Text aus `render_sms`): Am bestehenden Ereignis-Token `{code}{von}->{bis}` hängt das Farbpaar als `:{X}>{Y}` mit `G/Y/O/R` für grün/gelb/orange/rot, z. B. Verschärfung `G40->55:Y>O`, Sprung `G65->95:R>R`, Entwarnung `G55->35:O>Y`. Nie übersetzt (ADR-0104), GSM-7, vor der Zeitspanne `@HH-HH`. Gewitter behält sein Stufen-Token `TH:M->H` ohne Farbpaar. Im Ortsvergleich-Pfad (`{sign}{code}{bis}`) gilt dasselbe Suffix. Länge ≤ Limit (Alarm 140, Premium-SMS 153, absolut 160); das Suffix gehört zum Token und fällt nicht vor dem Token weg.
- **Wortlaut-Verträge nachziehen:** `docs/reference/renderer_email_spec.md` (Abweichungs-Alarm), `sms_format.md` neuer Abschnitt §3.4h, `telegram_format.md`, `premium_sms_format.md`, Glossar `docs/reference/i18n_glossar.md` (Farbwörter, „großer Sprung“, „Entwarnung“).

### 5. Migration der Altstufen (S2a, ADR-0106 P3)

`scripts/migrate_2793_alarm_ab.py`, Aufbau wie `migrate_2792_profil_ampel.py` (`--root` Pflicht, `--backup-dir`, `--execute`; ohne `--execute` Probelauf; tar.gz je Nutzer vor dem Schreiben; Schreiben unter `exclusive_lock` mit Inhaltsvergleich und atomarem Ersetzen; Bericht je Datei; „Nichts zu tun“; Exit 1 bei offenen Dateien).

- **Erfasst:** `data/users/<uid>/briefings/*.json` (Trips und Orts-Vergleiche) mit `display_config.metric_alert_levels`. Altschlüssel werden zuerst wie im Loader normalisiert (`_ALT_ALERT_LEVEL_KEYS`, `loader.py:780-819`).
- **Abbildung je Altschlüssel → Katalog-ID:** `wind_gust`→`gust`; `precipitation_sum`, `precipitation_change`→`precipitation`; `temperature_min`, `temperature_max`, `temperature_change`→`temperature`; `wind_change`→`wind`; `thunder_level`→`thunder`; `visibility`→`visibility`; `fresh_snow`→`fresh_snow`.
- **Regel P3, relativ zur Vorgabe `V` der aufgelösten Vorlage** (`resolve_ampel`, Vorlagen-Rückfall wie S1): `off` → `never` · `standard` → `V` · `sensibel` → eine Stufe empfindlicher als `V` (orange → yellow, red → orange, never → red), höchstens `yellow`, bei Gewitter höchstens `orange` · `entspannt` → `red`.
- **Mehrere Altschlüssel auf dieselbe Katalog-ID** (z. B. `temperature_min: sensibel`, `temperature_max: entspannt`): Es gilt der empfindlichste Wert; der Bericht nennt den Konflikt.
- **Geschrieben** wird nur `display_config.ampel.metrics.<id>.alarm_ab`, per Read-Modify-Write mit Merge: Fehlt `ampel` oder die Metrik-Zeile, wird sie aus der Vorlage angelegt und nur `alarm_ab` abweichend gesetzt. Grenzen, `enabled`, `template`, alle übrigen Felder und **`metric_alert_levels` selbst bleiben unverändert** (wird von D4-Metriken weiter gelesen).
- **Nicht abgebildet, nur berichtet:** `cape` (P1), D4-Schlüssel (`freezing_level`, `snow_line`, `thunder_onset`, `precipitation_heavy_onset`: bleiben wirksam), Vorboten, unbekannte Schlüssel oder Werte (z. B. `robust`).
- **Wiederholbar:** Merker `display_config.alarm_ab_migration: "2793"` (außerhalb von `ampel`, damit die Ampel-Prüfung unberührt bleibt); Dateien mit Merker werden übersprungen. Zweiter Lauf: „Nichts zu tun“.
- **Abos ohne `metric_alert_levels`:** unverändert; sie bekommen `alarm_ab` aus der Vorlage (entspricht P3 „standard → Vorgabe“ und dem heutigen impliziten „standard“).

### 6. Frontend bis S3a (S2b)

Die alte Tabelle „Alarm-Empfindlichkeit“ (`AlertMetricLevelTable`/`AlertMetricLevelRow` im `AlarmeTab`, Trip und Vergleich, Desktop und Mobil) wirkt nach S2b für Ampel-Metriken nicht mehr. Nach PO-Entscheid E2 (S1) darf nichts still wirkungslos sein, deshalb wird sie wie die Altfelder in S1c-3 **nur lesbar**:
- Je Zeile steht statt des Reglers die wirksame Stufe „Alarm ab: Gelb/Orange/Rot/Nie“ aus `ampel.metrics.<id>.alarm_ab` (Vorboten: „kein Alarm (Vorbote)“, A3). D4-Metriken zeigen ihre heutige Stufe, ebenfalls nur lesbar.
- Einmal oben ein Hinweis (Katalog, DE/EN): DE „Wird gerade umgebaut: Alarme folgen jetzt der Ampel. Einstellbar wird ‚Alarm ab‘ mit dem neuen Reiter Wetter.“ · EN „Being rebuilt: alerts now follow the traffic light. ‘Alert from’ becomes adjustable with the new Weather tab.“
- Speichern anderer Einstellungen lässt `metric_alert_levels`, `ampel` und den Merker unverändert (nie leeren, nie überschreiben).

## Expected Behavior

- **Input:** Anker- und Neuwerte je Segment/Ort, Abo-Ampel mit `alarm_ab` je Metrik, Kanal-Schwellen des Abos.
- **Output:** Abweichungs-Alarm bzw. Entwarnung in allen Alarm-Kanälen des Abos, deren Dringlichkeits-Schwelle die Farb-Dringlichkeit erreicht, mit Farbpaar im Text.
- **Side effects:** einmalige Migration der Altstufen in `alarm_ab` (Sicherung je Nutzer); Alarm-Protokoll trägt Farbpaar und Art.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Vorlage „Allgemein“ (Böen gelb ab 30, orange ab 45, rot ab 60), Böen „Alarm ab Orange“ und einem Anker von 40 km/h (gelb) / When die neue Prognose 55 km/h (orange) liefert / Then geht ein Alarm an jeden Alarm-Kanal des Abos, dessen Dringlichkeits-Schwelle „mittel“ zulässt, und mit „Alarm ab Rot“ geht bei denselben Werten kein Alarm
  - Test: Engine-Lauf über den Trip-Einstieg mit beiden Einstellungen; versendete Kanäle bzw. kein Versand werden beobachtet.

- **AC-2:** Given Böen „Alarm ab Orange“ und ein Anker von 65 km/h (rot) / When die Prognose 95 km/h liefert (Sprung 30 ≥ 20) / Then kommt ein Alarm „weiter rot, großer Sprung“, und bei einer Prognose von 80 km/h (Sprung 15) kommt keiner
  - Test: zwei Läufe mit gleichem Anker, Zusicherung auf Alarm bzw. keinen Alarm.

- **AC-3:** Given Böen „Alarm ab Orange“ und ein Anker von 50 km/h (orange) / When die Prognose 35 km/h (gelb) liefert / Then kommt eine Entwarnung „von orange auf gelb zurückgegangen“ mit Dringlichkeit „mittel“
  - Test: Lauf mit Zusicherung auf Art `entwarnung`, Text und Dringlichkeit.

- **AC-4:** Given Böen „Alarm ab Orange“ / When die Prognose von 70 km/h (rot) auf 50 km/h (orange) oder von 95 auf 65 km/h (beides rot) zurückgeht / Then kommt kein Alarm und keine Entwarnung (D2)
  - Test: zwei Läufe, kein Versand, kein Eintrag „gesendet“ im Alarm-Protokoll.

- **AC-5:** Given Böen „Alarm ab Orange“ / When die Prognose von 20 km/h (grün) auf 40 km/h (gelb) steigt oder unverändert bleibt / Then kommt kein Alarm
  - Test: zwei Läufe ohne Versand.

- **AC-6:** Given ein Abo, in dessen Datei bei `wind_chill` und `rain_probability` `alarm_ab: "orange"` steht / When beide Werte von grün auf rot springen / Then kommt nie ein Alarm (Vorboten, ADR-0010)
  - Test: Lauf über den Trip- und den Vergleichs-Einstieg ohne Versand.

- **AC-7:** Given Gewitter „Alarm ab Orange“ in Vorlage „Allgemein“ (mittel = orange) / When die Stufe von „keins“ auf „mittel“ steigt / Then kommt ein Alarm, mit „Alarm ab Rot“ nicht; und in Vorlage „Wassersport“ (mittel = rot) kommt mit „Alarm ab Rot“ ein Alarm; ein Anstieg auf „leicht“ meldet nie
  - Test: vier Läufe über die Engine mit den jeweiligen Vorlagen.

- **AC-8:** Given ein Speicherversuch mit Gewitter `alarm_ab: "yellow"` über die Go-API für Trip, Vergleich und eigene Vorlage / When gespeichert wird / Then antwortet die API mit HTTP 400 `ampel_ungueltig` und Meldung in der Anfragesprache (DE/EN), die gespeicherte Ampel bleibt unverändert, und eine solche Datei wird beim Laden in Python durch die Vorgabe der Vorlage ersetzt und protokolliert
  - Test: Go-Handler-Test mit zwei Nutzern (Nutzer B unverändert), Python-Loader-Test.

- **AC-9:** Given ein Abo mit Kanal-Schwelle E-Mail „gering“ und SMS „hoch“ / When eine Verschärfung von gelb auf orange auslöst / Then erhält nur die E-Mail den Alarm und das Protokoll vermerkt SMS mit `below_channel_threshold`; und eine Entwarnung von rot auf gelb erreicht beide Kanäle (Dringlichkeit „hoch“)
  - Test: Versand-Lauf mit beobachtetem Kanal-Set und Protokolleintrag.

- **AC-10:** Given zwei Abos mit identischen Wetterdaten, eines mit Vorlage „Skitouren“ (Temperatur oben gelb ab 3, orange ab 8 °C), eines mit „Allgemein“ (oben gelb ab 28, orange ab 31 °C), beide Temperatur „Alarm ab Orange“ / When das Tageshöchst von 2 auf 10 °C steigt / Then alarmiert nur das Skitouren-Abo, und das gilt gleichermaßen für einen Trip und für einen Orts-Vergleich
  - Test: Wirkungstest über den Trip- und den Vergleichs-Einstieg, beide Reihenfolgen.

- **AC-11:** Given Temperatur „Alarm ab Orange“ in Vorlage „Allgemein“ (unten gelb unter 0, orange unter −5 °C) / When das Tagestief von 1 °C auf −7 °C fällt / Then kommt ein Alarm, dessen Text das Tagestief nennt und „von grün auf orange“ sagt
  - Test: Lauf mit Zusicherung auf Text (DE und EN) und Farbpaar.

- **AC-12:** Given ein Trip mit Nullgradgrenze „standard“ (heute Δ 400 m) und aktivem Gewitterbeginn-Alarm / When die Nullgradgrenze um 450 m fällt bzw. das Gewitter 2 h früher beginnt / Then kommen dieselben Alarme mit derselben Dringlichkeit und demselben Text wie vor S2 (D4)
  - Test: Vorher-Nachher-Vergleich der Ausgabe für beide Fälle.

- **AC-13:** Given CAPE steigt von 300 auf 1500 J/kg, ohne dass sich die Gewitterstufe ändert / When der Alarm-Lauf prüft / Then kommt kein Alarm (ADR-0106 P1)
  - Test: Lauf ohne Versand.

- **AC-14:** Given ein Abo, bei dem alle aktiven alarmfähigen Metriken `alarm_ab: "never"` haben und keine Nullgradgrenze oder Beginn-Verschiebung aktiv ist / When die Werte von grün auf rot springen / Then kommt kein Alarm
  - Test: Lauf ohne Versand.

- **AC-15:** Given ein Bestands-Trip mit Vorlage „Allgemein“ und `metric_alert_levels` `{wind_gust: sensibel, precipitation_sum: standard, thunder_level: sensibel, temperature_min: sensibel, temperature_max: entspannt, cape: sensibel, freezing_level: entspannt}` / When die Migration mit `--execute` läuft / Then stehen in `ampel.metrics` Böen „yellow“, Niederschlag „orange“ (Vorgabe), Gewitter „orange“ (gekappt), Temperatur „yellow“ (empfindlichster, Konflikt im Bericht), CAPE und Nullgradgrenze sind im Bericht als „nicht abgebildet“ genannt, und alle übrigen Felder einschließlich `metric_alert_levels` sind byte-gleich erhalten
  - Test: Migrationstest auf Fixture-Verzeichnis, Vergleich vorher/nachher je Feld.

- **AC-16:** Given eine Vorlage mit Vorgabe „Nie“ für eine Metrik (z. B. Wintersport `fresh_snow`) und Altwert „sensibel“ bzw. „off“ / When migriert wird / Then steht „red“ bzw. „never“; und ein zweiter Lauf meldet „Nichts zu tun“, eine während des Laufs geänderte Datei wird übersprungen und im Bericht genannt, vor dem Schreiben liegt je Nutzer eine tar.gz-Sicherung vor
  - Test: Migrationstest mit zwei Läufen und simulierter Änderung zwischen Planen und Schreiben.

- **AC-17:** Given zwei Nutzer A und B mit je einem Trip und einem Orts-Vergleich mit Altstufen / When die Migration läuft / Then werden die Dateien beider Nutzer je nach eigener Vorlage migriert, jede Sicherung enthält nur die Dateien ihres Nutzers, und kein Wert von A taucht in Dateien von B auf
  - Test: Migrationstest mit zwei Nutzern.

- **AC-18:** Given eine Verschärfung Böen 40 → 55 km/h (gelb → orange) und eine Entwarnung 55 → 35 km/h / When der Alarm in allen vier Kanälen gerendert wird (DE und EN) / Then nennen E-Mail und Telegram (rich) Farbpaar, Werte und den Bezug auf das Briefing von {Zeit}, SMS, Premium-SMS und Telegram-Kurzform tragen `G40->55:Y>O` bzw. `G55->35:O>Y` in GSM-7 innerhalb der Längengrenzen, und Protokoll-Token sind in beiden Sprachen gleich
  - Test: Renderer-Test je Kanal und Sprache, Längen- und Zeichensatzprüfung.

- **AC-19:** Given ein Trip und ein Orts-Vergleich mit gespeicherten Altstufen, Desktop und Mobil, DE und EN / When der Nutzer den Reiter mit der Alarm-Empfindlichkeit öffnet und eine andere Einstellung speichert / Then sieht er je Zeile „Alarm ab …“ nur lesbar und den Hinweis „Wird gerade umgebaut …“, und nach dem Speichern sind `metric_alert_levels`, `ampel` und der Migrations-Merker unverändert
  - Test: Playwright-E2E auf Staging für Trip und Vergleich, Datei-/API-Zustand vorher/nachher.

- **AC-20:** Given ein Böen-Alarm von gelb auf orange wurde zugestellt / When der nächste Lauf dieselben Werte oder 57 km/h (weiter orange, Sprung 2) liefert / Then wird nicht erneut gemeldet; liefert er 78 km/h (rot), kommt ein neuer Alarm „von orange auf rot gestiegen“
  - Test: drei aufeinanderfolgende Läufe mit fortgeschriebenem Alarm-Zustand.

## Known Limitations

- **Bis S3a kann niemand „Alarm ab“ ändern:** Die alte Tabelle ist nur lesbar, die neue Oberfläche kommt mit S3a. Wirksam ist der migrierte Wert bzw. die Vorgabe der Vorlage.
- **Die Abbildung der Altstufen ist eine Annäherung** (ADR-0106 P3): Die alten Stufen meinten eine Δ-Größe, die neuen eine erreichte Farbe. Wer „sensibel“ gewählt hatte, bekommt eine Stufe empfindlicher als die Vorlage, nicht dasselbe Verhalten.
- **Rückgänge innerhalb des Alarmbereichs bleiben stumm** (D2), z. B. rot → orange bei „Alarm ab Orange“. Gewollt.
- **`temperature_night`, `snow_depth`, `snowfall_limit`** tragen `alarm_ab`, alarmieren über die Ampel aber erst mit S7; die Nullgradgrenze läuft bis S7 auf Δ (D4).
- **Kein Validator für Abweichungs-Alarm-Mails:** `briefing_mail_validator.py` überspringt `deviation-alert` ausdrücklich (No-Op, kein Pass). Der Staging-Nachweis läuft über echt zugestellte Alarme aus der Validator-Render-Route (`api/routers/validator.py`) und Renderer-Tests; ein eigener Validator ist Nebenbefund (#1199).
- **`alert_rules`-Gate und Kanal-Union bleiben** (Übergabe #1895, Gate-Fälle 1–4). Rückbau erst, nachdem die Regel-`channels` frisch auf Prod gemessen sind; nicht Teil von S2.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. ADR-0106 (Akzeptiert) trägt die Entscheidung inkl. P3; ADR-0013 ist bereits als „teilweise abgelöst, `threshold` bleibt Sprung-Schwelle“ markiert. Nachzutragen in ADR-0106: D1–D4 als Präzisierung P4 (Sprung-Schwelle = Spalte „standard“, Entwarnung nur unter „Alarm ab“, Dringlichkeit aus der Farbe, Nullgradgrenze/Beginn bis S7 auf Δ); in ADR-0046 ein Satz, dass die Dringlichkeit eines Abweichungs-Alarms aus der Farbe kommt.
- **Rationale:** Die Grundentscheidung ist getroffen; S2 legt nur die vom ADR offen gelassenen Parameter fest.

## Changelog

- 2026-11-08: v1.0 Entwurf mit PO-Entscheidungen D1–D4 (Rückfrage in der Sitzung)
- 2026-11-08: v1.0 vom PO freigegeben
