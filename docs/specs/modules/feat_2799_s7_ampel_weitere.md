---
entity_id: feat_2799_s7_ampel_weitere
type: feature
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
issue: 2799
epic: 2791
workflow: feat-2799-ampel-weitere
tags: [ampel, vorlagen, relative-metriken, nullgradgrenze, schneefallgrenze, schneehoehe, alarm, stufenwechsel, kanal-paritaet, i18n, epic-2791]
---

# Einstellungen neu S7: Ampel für weitere Metriken, relative Höhenmetriken und Alarm (#2799)

## Approval

- [ ] Approved

## Purpose

Die Profil-Ampel aus der Vorlage (ADR-0106 Punkt 5 und 6) färbt bisher nur die Metriken der ersten Scheiben. S7 dehnt sie auf Bewölkung, tiefe Wolken, Taupunkt, Sonnenstunden, Schneehöhe, Nacht-Tiefsttemperatur sowie auf Nullgrad- und Schneefallgrenze aus. Die beiden Grenzen werden relativ zur höchsten Stelle der Etappe bzw. zur Ortshöhe bewertet. Nullgradgrenze, Schneefallgrenze, Schneehöhe und Nacht-Tiefsttemperatur alarmieren per Stufenwechsel; die alte Δ-Logik (D4) und ihre Reste aus #2222 werden abgebaut. Alles gilt gleich in allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS; ADR-0095).

Dies ist die **Gesamt-Spec mit Lieferplan** nach Epic-Konvention (wie `feat_2794_s3a_reiter_wetter.md`). Jeder Teil-PR bekommt vor seiner Implementierung eine eigene Teil-Spec oder einen Nachtrag zu dieser Spec, der die hier zugeordneten ACs referenziert und konkretisiert.

Entscheidungsgrundlage: ADR-0106 (P5, P6, D4), ADR-0010 (Vorboten), ADR-0019 (Nullgradgrenze als Alert-Metrik), ADR-0122 (Hochlage-Normalisierung tiefer Wolken), ADR-0095 (Kanal-Parität), ADR-0104 (zweisprachig), ADR-0042 (Kürzel unübersetzt), ADR-0101 (Read-Modify-Write), ADR-0126 (Windrichtung-Modi, bleibt unverändert). Analyse: `docs/context/feat-2799-ampel-weitere.md`; Konzept: `docs/context/einstellungen_neu.md` §4.2, §4.4.

**PO-Entscheidungen 2026-11-28 (AskUserQuestion):**
- **E1 Mittlere Wolken:** bleiben reine Anzeige (kein ADR-Nachtrag). Begründung: Die Open-Meteo-Bänder (tief bis 3 km, mittel 3 bis 8 km, hoch ab 8 km; ECMWF 700/500 hPa) beginnen für die meisten Routen oberhalb der Etappe; „Gipfel in Wolken“ trägt `cloud_low`. Wiedervorlage, falls ein Provider eine Wolkenuntergrenze liefert.
- **E2 Anzeigewert Nullgrad-/Schneefallgrenze:** relativ als Hauptwert, absolut in Klammern in E-Mail und Telegram; SMS und Premium-SMS kurz mit Vorzeichen.

## Source

- **Python-Core:** `src/app/ampel.py` (`AMPEL_LESER`, `schwellen_aus_ampel`, `_stufe`, neu `ampel_mit_bezug`, `bezug_fuer`), `src/app/ampel_templates.py` (nur lesen, Zahlen unverändert), `src/app/metric_catalog.py` (`AMPEL_METRIC_IDS`, `_REITER_WETTER`), `src/output/metric_format.py`, `src/services/ampel_alarm.py` (`AMPEL_FELDER`, `AmpelFeld.seite`), `src/services/trip_alert.py`, `src/services/deviation_alert_engine.py`, `src/app/alert_preset.py`, `src/services/trip_report_scheduler.py` (`_compute_stage_stats`), `src/app/models.py` (`SegmentWeatherSummary`).
- **Renderer und Kanäle:** `src/output/renderers/email/{html,helpers,plain,compact,outlook,compare_html,comparison,compact_compare}.py`, `src/output/renderers/narrow.py` (Telegram), `src/output/tokens/builder.py`, `src/output/tokens/orte_sms.py`, `src/output/tokens/sms_trip.py`.
- **Frontend:** `frontend/src/lib/components/shared/wetter-tab/{ampelModell.ts,MetrikZeile.svelte,AmpelLeiste.svelte,GrenzenEditor.svelte,ampelLeiste.ts}`, `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts`, `frontend/src/lib/i18n/messages/{de,en}/wetter.json`.
- **Go-API:** voraussichtlich unverändert (`internal/handler/ampel.go` validiert bereits alle Metrik-IDs der Vorlagen); falls ein Teil sie berührt, nennt die Teil-Spec es.
- **Validatoren und Doku:** `.claude/hooks/briefing_mail_validator.py`, `.claude/hooks/email_spec_validator.py`, `docs/reference/{sms_format,premium_sms_format,telegram_format,renderer_email_spec,mail_validators,i18n_glossar}.md`, `docs/adr/0019-nullgradgrenze-eine-alert-metrik.md`.

> **Schicht-Hinweis:** Bewertung, Bezugshöhe, Alarm und Renderer sind Python-Core. Reiter Wetter ist Frontend. Die Go-API reicht die Ampel nur durch (Vorlagen-Daten liegen schon in `ampel_templates.py`).
>
> **Trip/Ortsvergleich-Teilung (PFLICHT, #1170):** Die Bezugshöhe kommt je Kontext aus einer Quelle (`bezug_fuer`: Trip = höchster Wegpunkt der Etappe, Orte = `SavedLocation.elevation_m`); die Bewertung selbst (`ampel_mit_bezug`) ist EIN Code für beide. Im Frontend bleiben die Bausteine unter `shared/` mit `context="route"|"vergleich"`, es entsteht keine neue Komponente mit Pendant.
>
> **Mandantentrennung:** Erwartet wird kein neuer datenbewegender Endpunkt. Fügt ein Teil dennoch einen hinzu oder liest Nutzerdaten über einen neuen Pfad, gilt ein Zwei-Nutzer-Test mit `user_id` aus dem Auth-Kontext (nie `"default"`). Alle Alarm-Tests laufen mit zwei Nutzern, deren Etappen verschiedene Höhen haben (AC-24).
>
> **Kanäle:** Jede Metrik dieser Spec erscheint mit derselben Stufe in E-Mail (Trip und Orte), Telegram, SMS und Premium-SMS (AC-23).

## Estimated Scope

- **LoC:** gesamt ca. 1800 inkl. Tests; Produktivcode je Teil ≤250 LoC
- **Files:** je Teil ≤5 Produktiv-Dateien, zehn Teil-PRs
- **Effort:** high (alle Kanäle plus Alarm; durch Vorbau und Aktivierung getrennt beherrschbar)

## Scope

**In Scope:**
- **Ampel aus der Vorlage** für `cloud_total` (Bewölkung, Vorbote), `cloud_low` (tiefe Wolken), `dewpoint` (Taupunkt, Vorbote, nur oben), `sunshine` (Sonnenstunden, nur unten, nur der Tageswert), `snow_depth` (Schneehöhe absolut in cm, je Vorlage), `temperature_night` (Nacht-Tiefsttemperatur; die Specs S1, S2 und S3a verschieben sie nach S7).
- **Relative Metriken** `freezing_level` und `snowfall_limit`: Grenzen der Vorlage sind Meter über der höchsten Stelle der Etappe (`max_elevation_m` aus den Wegpunkten) bzw. über der Ortshöhe (`SavedLocation.elevation_m`), negativ heißt darunter.
- **Ohne Bezugshöhe:** keine Färbung der relativen Metrik, dafür ein Hinweis in allen Kanälen, nie eine falsche Farbe; im Alarm: kein Alarm für diese Metrik.
- **Anzeigewert** der relativen Metriken (E2), siehe „Anzeigeformat“.
- **Alarm per Stufenwechsel** (Engine `src/services/ampel_alarm.py`, Seite „beidseitig“) für Nullgradgrenze, Schneefallgrenze, Schneehöhe, Nacht-Tiefsttemperatur nach `alarm_ab` der Vorlage. D4-Δ für `freezing_level` wird stillgelegt.
- **Abbau der Δ-Reste aus #2222** (Teil S7d).
- **Reiter Wetter** (Teil S7e): Einheit „m rel.“ und Hinweis.
- **Glossar und ADR-0019-Nachtrag** (Teil S7f).

**Reine Anzeige (keine Ampel, kein Alarm):** Luftfeuchte, Luftdruck, Windrichtung (außer Modus nach ADR-0126), Niederschlagsart, mittlere und hohe Wolken (`cloud_mid`, `cloud_high`).

**Kein Alarm trotz Ampel:** Vorboten Taupunkt und Bewölkung (ADR-0010); Sonnenstunden und tiefe Wolken haben in allen Vorlagen `alarm_ab` = nie.

**Out of Scope:**
- Ampel für `cloud_mid`/`cloud_high` und jede Wolkenuntergrenze (Wiedervorlage bei Provider-Datenlage, E1).
- Neue Grenzwerte oder Vorlagen: Zahlen in `ampel_templates.py` bleiben unverändert.
- Neu entworfene Frontend-Oberflächen; S7e ergänzt nur Einheit und Hinweis der bestehenden Zeilen.
- Premium-SMS-Protokoll jenseits des Tokens `FZ`/`SL` (Kanal-Auswahl aus ADR-0049 bleibt).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| S1 #2792, S3a #2794 (geschlossen) | Vorarbeit | Vorlagen-Ampel, `resolve_ampel`, Reiter Wetter |
| S2 #2793 | Vorarbeit | Stufenwechsel-Engine `ampel_alarm.py` |
| ADR-0106 | ADR | P5/P6 Vorgabe; D4 wird in S7c1 beendet |
| ADR-0010 | ADR | Vorboten ohne Alarm |
| ADR-0019 | ADR | Nachtrag: Schneefallgrenze eigenständige Alarm-Metrik (S7f, vor S7c1) |
| ADR-0122 | ADR | Hochlage-Normalisierung; nur Abgrenzung, keine Änderung |
| ADR-0126 | ADR | Windrichtung-Modi gegenwind/sektoren; Färbung bleibt unverändert (Abgrenzung AC-8) |
| ADR-0042 | ADR | Kürzel `FZ`/`SL` bleiben unübersetzt |
| `tests/tdd/test_ampel_vorlagen_gleich_einstellungen_doku.py` | Ratsche | Vorlagenzahlen gegen Doku |
| `briefing_mail_validator.py`, `email_spec_validator.py` | Validatoren | echte Staging-Mail je Mail-Teil |
| Renderer-Commit-Gate | Gate | Modus-Matrix-Test und Validator frisch grün bei Mail-Inhalt |

## Implementation Details

### Technischer Ansatz (Variante A)

1. **Ableitung statt Drift.** Alle heute getrennten Listen (`AMPEL_METRIC_IDS`, `_AMPEL_CAPABLE_METRIC_IDS`, `_PILL_NEUTRAL_TONE`, `AMPEL_METRIK_JE_KUERZEL`, `_AMPEL_SPALTEN` des Validators, Orte-Übersicht-`sev`) werden aus `AMPEL_LESER` abgeleitet (S7a1, ohne sichtbare Änderung). Danach schaltet das Aufnehmen einer Metrik in `AMPEL_LESER` (S7a2, S7a3, S7b2) alle Kanäle zugleich um.
2. **Bezugshöhe als reine Funktion.** `ampel_mit_bezug(ampel, bezug_m)` rechnet die relativ gespeicherten Grenzen von `freezing_level` und `snowfall_limit` in absolute um (`bezug_m + Offset`). Ohne `bezug_m` entfernt sie die beiden Metriken, `hat_ampel` ist dann falsch und alle Kanäle bleiben neutral (Parität durch Konstruktion). Der Hinweis „keine Höhe“ wird an einer Stelle erzeugt. `bezug_fuer(...)` liefert die Bezugshöhe für Trip (Etappe) und Orte. Der Aufruf geschieht einmal je Render-Einstieg und je Alarm-Segment.
3. **Sonnenstunden** sind eine Tagessumme: gefärbt wird nur der Tageswert (Pille, Tagesübersicht, SMS-`SU`), nie eine Stundenzelle.
4. **Alarm:** `AmpelFeld` bekommt die Seite „beidseitig“ und die Felder `freezing_level_m`, `snowfall_limit_m`, `snow_depth_cm`, Nacht-Tiefsttemperatur (eigenes Feld, nicht `temp_min_c`). Die Bezugshöhe je Segment kommt aus einer Segment-zu-Etappe-Karte im Trip-Alarmdienst. Der Stufenvergleich nutzt die absolut umgerechneten Grenzen der Etappe. Segment ohne Höhe: kein Alarm für die relative Metrik.
5. **D4 stilllegen:** `freezing_level` verlässt `D4_ALERT_METRICS` und `_select_d4_detector`; es gibt nie zwei Alarme für dasselbe Ereignis.

### Schwellensemantik (verbindlich, aus `ampel_templates.py`)

Unten: `Wert < Grenze` (rot < orange < gelb), oben: `Wert >= Grenze` (gelb, orange, rot). Eine offene Seite (`–`) hat keine Grenze; keine Grenze auf beiden Seiten heißt „immer grün“. Beispiele: Alpen-Trekking `freezing_level` unten (−300, 0, 300): relativer Wert −100 ist `< 0` und nicht `< −300`, also **orange**; +100 ist `< 300` und nicht `< 0`, also **gelb**; +300 oder mehr ist grün. Skitouren `snow_depth` unten (15, 30, 50): 25 cm ist `< 30`, nicht `< 15`, also **orange**.

### Anzeigeformat (E2)

- **E-Mail und Telegram:** relativ als Hauptwert, absolut in Klammern. DE: „+250 m über höchster Stelle (2650 m)“ bzw. bei Orten „+250 m über Ortshöhe (2650 m)“; negativ „−120 m unter höchster Stelle (2280 m)“ (DE) bzw. „−120 m unter Ortshöhe (…)“. EN analog: „+250 m above highest point (2650 m)“, „+250 m above location elevation (2650 m)“, „−120 m below highest point (2280 m)“. Texte nur über den Katalog (ADR-0104).
- **SMS und Premium-SMS:** Token `FZ` (Nullgradgrenze) und `SL` (Schneefallgrenze) mit Pflicht-Vorzeichen und ganzen Metern relativ zur Bezugshöhe: `FZ+250`, `SL-120`; Wert 0 als `FZ+0`. Kürzel bleiben unübersetzt (ADR-0042). Das ist eine **Formatänderung** gegenüber dem bisherigen absoluten Wert. Ein vorhandener Zeit-Anhang des Tokens bleibt unverändert. Ohne Bezugshöhe entfällt das Token nicht stumm, sondern der absolute Wert steht wie bisher (neutral, ungefärbt) und die Mail trägt den Hinweis. Die Formatänderung wird im jeweiligen Teil in `docs/reference/sms_format.md` und `premium_sms_format.md`, `telegram_format.md` und `renderer_email_spec.md` nachgezogen (S7b2).
- **Ohne Bezugshöhe:** Text „keine Höhe bekannt, nicht bewertet“ (EN: „no elevation known, not rated“), ungefärbt, in allen vier Kanälen.

### Lieferplan (Teil-PRs; jeder ≤5 Dateien und ≤250 LoC Produktivcode)

Vorbau ohne sichtbare Änderung, dann Aktivierung in allen vier Kanälen gleichzeitig. Mail-Teile haben den Validator im Umfang (`briefing_mail_validator.py` für Trip, `email_spec_validator.py` für Orte-Vergleich). Jeder Teil bekommt vor seinem PR eine eigene Teil-Spec oder einen Nachtrag zu dieser Spec, der die zugeordneten ACs referenziert. Jeder Teil hat eigene CI (6 Checks), eigenes Staging und `/e2e-verify`.

| Teil | Inhalt | Risiko | ACs |
|---|---|---|---|
| S7a1 | Vorbau ohne sichtbare Änderung: Ampel-Listen aus `AMPEL_LESER` abgeleitet (Pillen, Tabellenzellen, Orte-Übersicht-sev generisch, SMS-Kürzelkarte, Validator-Spalten) | mittel | AC-22 |
| S7a2 | Aktivierung Bewölkung, tiefe Wolken, Taupunkt, Sonnenstunden (Tageswert) in allen vier Kanälen + Validator-Fälle, Ratschen-Tests | hoch (Mail) | AC-4 bis AC-8, AC-18, AC-23 |
| S7a3 | Nacht-Tiefsttemperatur und Schneehöhe (absolut, je Vorlage) färben (alle Kanäle) | mittel | AC-2, AC-3 (Färbung), AC-15 (Färbung), AC-23 |
| S7b1 | `ampel_mit_bezug` + `bezug_fuer` + Durchreichung Trip/Orte zu allen Renderern, noch nicht aktiv | mittel | AC-22 |
| S7b2 | Aktivierung Nullgrad-/Schneefallgrenze relativ in allen Kanälen, Hinweis ohne Höhe, Anzeigewert (PO-Entscheid), Validator | hoch | AC-1, AC-9 bis AC-12, AC-23 |
| S7c1 | Alarm Nullgrad-/Schneefallgrenze per Stufenwechsel, D4 freezing_level aus | mittel-hoch | AC-13, AC-14, AC-17, AC-19, AC-24 |
| S7c2 | Alarm Schneehöhe + Nacht-Tiefsttemperatur | mittel | AC-15, AC-16, AC-24 |
| S7d | Abbau Δ-Reste #2222 (#961-Backfill, `_has_active_alert_metric`, `_detect_all_changes`, Gate + Spiegel `hubUebersichtModell.ts`) | mittel | AC-20 |
| S7e | Reiter Wetter: Einheit „m rel.“, Hinweis ohne Höhe, i18n de/en | niedrig | AC-21 |
| S7f | Glossar (Nullgradgrenze, „über höchster Stelle“, „m rel.“), ADR-0019-Nachtrag (Schneefallgrenze alarmfähig) | keins | AC-25 |

Reihenfolge: S7a1, S7a2, S7a3, S7b1, S7b2, **S7f-ADR-Nachtrag vor S7c1**, S7c1, S7c2, S7d, S7e, S7f (Rest). Kippende Bestandstests (`tests/tdd/test_renderer_katalog_schwellen.py:299-312`, `tests/helpers/metrik_listen_scan.py`, Ratsche `test_ampel_vorlagen_gleich_einstellungen_doku.py`) werden in S7a2 mit umgestellt.

### Entscheidung zum Gate in S7d

Das Gate (`trip_alert.py:713-718`) und sein Spiegel (`hubUebersichtModell.ts:166-187`) bleiben nur so weit bestehen, wie Bestands-Trips ohne Ampel-Alarmquelle sie brauchen; alles Übrige entfällt. Verbindlich ist das Verhalten aus AC-20: Ein Bestands-Trip mit `alert_on_changes=False` bekommt nach S7d weiter keinen Alarm, ein Trip mit Ampel-Alarmquelle alarmiert weiter.

## Expected Behavior

- **Input:** Wetterdaten je Segment bzw. Ort, aufgelöste Ampel des Abos, Bezugshöhe (Etappe bzw. Ort).
- **Output:** Gleiche Farbstufe und gleicher Wert je Metrik und Zeitpunkt in E-Mail, Telegram, SMS, Premium-SMS; Alarme nach Stufenwechsel.
- **Side effects:** SMS-Token `FZ`/`SL` ändern sich von absolut auf relativ mit Vorzeichen; D4-Alarm für Nullgradgrenze entfällt; keine Datenmigration (Ampel-Daten liegen bereits in Abos und Vorlagen).

## Acceptance Criteria

- **AC-1:** Given eine Etappe, deren höchster Wegpunkt auf 2400 m liegt, die Vorlage Alpen-Trekking (Nullgradgrenze unten rot unter −300, orange unter 0, gelb unter 300 m relativ) und eine Nullgradgrenze von 2300 m / When das Briefing erzeugt wird / Then ist die Nullgradgrenze (−100 m relativ) orange, und zwar in E-Mail, Telegram, SMS (`FZ-100`) und Premium-SMS
  - Test: Trip-Briefing über alle vier Renderer mit echten Etappen-Wegpunkten; Staging-Mail durch `briefing_mail_validator.py`.

- **AC-2:** Given Vorlage Skitouren (Schneehöhe unten rot unter 15, orange unter 30, gelb unter 50 cm) und eine Schneehöhe von 25 cm / When das Briefing erzeugt wird / Then ist die Schneehöhe orange in allen vier Kanälen
  - Test: Renderer-Test je Kanal mit echtem Vorlagen-Ampel-Objekt; Trip-Mail über den Validator.

- **AC-3:** Given Vorlage Allgemein (Schneehöhe ohne Grenze) und eine Schneehöhe von 80 cm, die der Nutzer ins Briefing aufgenommen hat / When das Briefing erzeugt wird / Then bleibt die Schneehöhe grün bzw. neutral (immer grün, keine Grenze gesetzt) und löst keinen Alarm aus
  - Test: Renderer- und Alarm-Test mit Vorlage Allgemein plus Metrik hinzugefügt.

- **AC-4:** Given Vorlage Wandern (Sonnenstunden unten orange unter 1 h, gelb unter 3 h) und ein Tageswert von 0,5 Sonnenstunden / When das Briefing erzeugt wird / Then ist der Tageswert orange in allen vier Kanälen, und es entsteht trotz Stufenwechsel kein Alarm (Alarm ab nie)
  - Test: Renderer-Test je Kanal; Alarm-Lauf mit Stufenwechsel grün auf orange, beobachtet wird kein Versand.

- **AC-5:** Given Vorlage Alpen-Trekking (Taupunkt oben gelb ab 16, orange ab 18, rot ab 21 °C) und ein Taupunkt von 19 °C / When das Briefing erzeugt wird / Then ist der Taupunkt orange in allen vier Kanälen, und auch ein Sprung von grün auf orange erzeugt keinen Alarm (Vorbote, ADR-0010)
  - Test: Renderer-Test je Kanal; Alarm-Lauf ohne Versand.

- **AC-6:** Given Vorlage Allgemein (Bewölkung oben gelb ab 60, orange ab 85 %) und eine Bewölkung von 70 % / When das Briefing erzeugt wird / Then ist die Bewölkung gelb in allen vier Kanälen und löst nie einen Alarm aus
  - Test: Renderer-Test je Kanal; Alarm-Lauf ohne Versand (Vorbote).

- **AC-7:** Given Vorlage Skitouren (tiefe Wolken oben gelb ab 40, orange ab 70, rot ab 90 %) und tiefe Wolken von 75 % / When das Briefing erzeugt wird / Then sind die tiefen Wolken orange in allen vier Kanälen, und es entsteht kein Alarm (Alarm ab nie)
  - Test: Renderer-Test je Kanal; Alarm-Lauf ohne Versand.

- **AC-8:** Given Mittlere Wolken, hohe Wolken, Luftfeuchte, Luftdruck, Windrichtung (außer in den Modi gegenwind/sektoren nach ADR-0126, deren Färbung unverändert bleibt) und Niederschlagsart im Briefing / When das Briefing in einem beliebigen Kanal erzeugt wird / Then bleiben diese Werte ungefärbt und lösen nie einen Alarm aus
  - Test: Renderer-Test je Kanal mit extremen Werten (Wolken mittel 100 %, Feuchte 100 %); Ratsche gegen die Reine-Anzeige-Liste.

- **AC-9:** Given ein Orts-Briefing mit einem Ort ohne Höhe (`elevation_m` fehlt) / When die Nullgradgrenze berichtet wird / Then bleibt sie ungefärbt, der Hinweis „keine Höhe bekannt, nicht bewertet“ (EN „no elevation known, not rated“) steht in E-Mail, Telegram, SMS und Premium-SMS, und keine falsche Farbe erscheint
  - Test: Orte-Briefing mit zwei Orten (einer ohne Höhe) über alle Kanäle; Staging-Mail durch `email_spec_validator.py`.

- **AC-10:** Given eine Etappe mit höchstem Wegpunkt 2400 m und Nullgradgrenze 2650 m / When das Briefing erzeugt wird / Then zeigt die E-Mail und Telegram „+250 m über höchster Stelle (2650 m)“ (EN „+250 m above highest point (2650 m)“), bei einem Ort mit 1800 m Höhe „über Ortshöhe“ bzw. „above location elevation“
  - Test: Renderer-Tests je Sprache und Kontext; Staging-Mail durch den jeweiligen Validator.

- **AC-11:** Given dieselbe Etappe (2400 m) und Nullgradgrenze 2650 m bzw. Schneefallgrenze 2280 m / When SMS und Premium-SMS erzeugt werden / Then lauten die Token `FZ+250` und `SL-120`, mit Vorzeichen und ganzen Metern, in beiden Sprachen identisch, und `docs/reference/sms_format.md` und `premium_sms_format.md` beschreiben die Formatänderung
  - Test: Token-Builder-Test (DE und EN) auf exakte Zeichenfolge; Zeichenbudget-Test der SMS bleibt grün; Doku-Ratsche `# doc-compliance-test` für die neuen Beispiele.

- **AC-12:** Given ein Trip mit mehreren Etappen unterschiedlicher Höchststelle (z. B. 1800 m und 2400 m) bei derselben Vorlage / When das Briefing erzeugt wird / Then wird jede Etappe gegen ihre eigene höchste Stelle bewertet, und derselbe Absolutwert kann in beiden Etappen verschiedene Farben ergeben
  - Test: Trip-Briefing mit zwei Etappen über alle Kanäle.

- **AC-13:** Given Vorlage Alpen-Trekking (Nullgradgrenze Alarm ab Orange) und eine Etappe mit höchster Stelle 2400 m, bei der die Nullgradgrenze von 2500 m (+100 m, gelb) auf 2300 m (−100 m, orange) fällt / When der Alarm-Lauf prüft / Then wird ein Alarm mit Stufe orange auf allen vier Kanälen zugestellt, Entwarnung folgt erst beim Fallen unter „Alarm ab“, und ein unveränderter Wert meldet nie
  - Test: Alarm-Lauf mit Zeitreihe gelb, orange, gelb über die Alarm-Pipeline; Versand je Kanal beobachtet.

- **AC-14:** Given dasselbe Ereignis wie AC-13 / When der Alarm-Lauf nach S7c1 prüft / Then kommt genau ein Alarm für die Nullgradgrenze, nicht zusätzlich einer aus der alten Δ-Logik (D4)
  - Test: Alarm-Lauf zählt gesendete Alarme je Kanal (genau 1); `freezing_level` ist nicht mehr in `D4_ALERT_METRICS` (Verhaltenstest über das Ergebnis, nicht über Dateiinhalt).

- **AC-15:** Given Vorlage Wandern (Nacht-Tiefsttemperatur unten rot unter −8, orange unter −3, gelb unter 0 °C; Alarm ab Orange) und eine Nacht-Tiefsttemperatur von −4 °C / When das Briefing erzeugt wird / Then ist sie orange in allen vier Kanälen; bei einem Stufenwechsel von gelb (−1 °C) auf orange (−4 °C) kommt ein Alarm, und die Vorlage Wintersport (Alarm ab nie) bleibt gefärbt, aber stumm
  - Test: Renderer-Test je Kanal; Alarm-Läufe mit beiden Vorlagen.

- **AC-16:** Given Vorlage Skitouren (Schneehöhe unten rot unter 15, orange unter 30, Alarm ab Orange) und ein Stufenwechsel der Schneehöhe von 35 cm (gelb) auf 25 cm (orange) / When der Alarm-Lauf prüft / Then kommt ein Alarm mit Stufe orange auf allen vier Kanälen, bei Vorlage Allgemein (keine Grenze) kommt kein Alarm
  - Test: Alarm-Lauf je Vorlage, Versand je Kanal beobachtet.

- **AC-17:** Given Vorlage Alpen-Trekking (Schneefallgrenze unten rot unter −500, orange unter 0, gelb unter 300 m relativ; Alarm ab Orange) und eine Etappe mit höchster Stelle 2400 m, bei der die Schneefallgrenze von 2500 m (+100 m) auf 2300 m (−100 m) fällt / When der Alarm-Lauf prüft / Then kommt ein Alarm mit Stufe orange auf allen vier Kanälen als eigenständige Alarm-Metrik Schneefallgrenze (ADR-0019-Nachtrag)
  - Test: Alarm-Lauf über die Pipeline, Versand je Kanal beobachtet.

- **AC-18:** Given die Vorlagen-Zahlen in `ampel_templates.py` und die Doku `docs/context/einstellungen_neu.md` / When die Ratsche läuft / Then stimmen die Grenzen aller aktivierten Metriken überein, und `AMPEL_LESER`, die Pillen- und Tabellenlisten, die SMS-Kürzelkarte und die Validator-Spalten enthalten dieselben Metriken (keine Drift)
  - Test: pytest-Ratsche über die abgeleiteten Listen; bestehende Doku-Ratsche bleibt grün.

- **AC-19:** Given ein Segment, dessen Etappe keine Wegpunkt-Höhe hat, oder ein Ort ohne Höhe / When sich dort die Nullgrad- oder Schneefallgrenze stark ändert / Then kommt für diese relative Metrik kein Alarm, andere Metriken desselben Segments alarmieren weiter, und es entsteht kein Fehler im Lauf
  - Test: Alarm-Lauf mit Segment ohne Höhe; Versand für Böen weiter beobachtet, für Nullgradgrenze nicht.

- **AC-20:** Given ein Bestands-Trip mit `alert_on_changes=False` und ohne Ampel-Alarmquelle sowie ein Trip mit mindestens einer aktiven Metrik mit „Alarm ab“ ungleich nie / When nach S7d (Abbau der Δ-Reste #2222) Werte auf Alarmfarbe springen / Then bekommt der erste Trip weiterhin keinen Alarm, der zweite alarmiert weiterhin, und der #961-Backfill sowie `_has_active_alert_metric` sind ohne Verhaltensänderung für beide entfernt
  - Test: Alarm-Lauf mit beiden Trips vor und nach S7d (gleiches Ergebnis); Frontend-Modelltest `hubUebersichtModell` zeigt für beide Trips dieselbe Alarm-Aussage wie die Backend-Entscheidung.

- **AC-21:** Given der Reiter Wetter eines Trips und eines Orts-Briefings mit Nullgrad- und Schneefallgrenze / When der Nutzer die Zeilen und „Grenzen ändern“ öffnet / Then steht die Einheit „m rel.“ an den Grenzzahlen und der Hinweis „m über höchster Stelle“ (Trip) bzw. „m über Ortshöhe“ (Orte), auf Englisch „m above highest point“ bzw. „m above location elevation“, und die Reihenfolge-Prüfung der Grenzen gilt unverändert
  - Test: Playwright auf Staging je Kontext und Sprache; `node --test` für `ampelModell.ts` (Einheit und Hinweis).

- **AC-22:** Given die Vorbau-Teile S7a1 und S7b1 (Aktivierung noch nicht erfolgt) / When Briefings und Alarme erzeugt werden / Then sind alle Ausgaben aller Kanäle byte-gleich zum Stand vor dem Teil (keine sichtbare Änderung), und `ampel_mit_bezug` liefert ohne Bezugshöhe eine Ampel ohne die beiden relativen Metriken, mit Bezugshöhe absolute Grenzen
  - Test: Golden-Vergleich der Renderer-Ausgaben vor und nach dem Teil; Unit-Test `ampel_mit_bezug` mit 2400 m und ohne Höhe.

- **AC-23:** Given dieselbe Metrik aus dieser Spec (Bewölkung, tiefe Wolken, Taupunkt, Sonnenstunden, Nacht-Tiefsttemperatur, Schneehöhe, Nullgrad-, Schneefallgrenze) und derselbe Zeitpunkt in einem Trip- und einem Orte-Briefing / When E-Mail, Telegram, SMS und Premium-SMS erzeugt werden / Then tragen alle vier Kanäle dieselbe Farbstufe (Parität), Zeitpunkte ohne Stundenwert (Sonnenstunden) werden nur als Tageswert gefärbt, und die Validatoren `briefing_mail_validator.py` und `email_spec_validator.py` bestehen gegen echt zugestellte Staging-Mails
  - Test: Paritätstest über die vier Renderer mit identischen Eingaben; Validator-Läufe in `/e2e-verify` je Mail-Teil.

- **AC-24:** Given zwei verschiedene Nutzer A und B mit je einem Trip, deren Etappen verschiedene Höchststellen haben (A 2400 m, B 1600 m), bei derselben Nullgradgrenze von 2300 m / When der Alarm-Lauf für beide prüft / Then wird je Nutzer gegen die eigene Etappenhöhe bewertet, ein Alarm geht nur an die Empfänger des Nutzers mit Stufenwechsel, und es gibt keinen Fallback auf `"default"`
  - Test: Alarm-Lauf mit zwei Nutzern und getrennten Datenverzeichnissen; Empfänger je Nutzer beobachtet.

- **AC-25:** Given die Teile S7f und S7c1 / When ein Prüfer die ADR-Lage vor S7c1 prüft / Then enthält ADR-0019 den Nachtrag „Schneefallgrenze ist eigenständige Alarm-Metrik (Spec feat_2799_s7_ampel_weitere)“, und das Glossar enthält Nullgradgrenze, „über höchster Stelle“ und „m rel.“ in DE und EN
  - Test: `tests/test_adr_index_drift.py` bleibt grün; Glossar-Test `# doc-compliance-test` auf die Begriffe.

## Known Limitations

- Mittlere Wolken bleiben Anzeige (E1); Wiedervorlage, falls ein Provider eine Wolkenuntergrenze liefert. Bezug der Open-Meteo-Bänder (Boden oder Meer) ist nicht dokumentiert, vermutlich über Meer (Schluss, nicht Quelle).
- Tiefe Wolken werden ab 2500 m Standorthöhe nach ADR-0122 normalisiert; die Ampel liest den normalisierten Wert, eine eigene Höhenlogik kommt nicht dazu.
- Sonnenstunden werden nur als Tageswert gefärbt; Stundenzellen bleiben ungefärbt.
- Die Bezugshöhe einer Etappe ist der höchste Wegpunkt, nicht das Geländeprofil zwischen den Wegpunkten.
- Segmente ohne Höhe liefern keinen Alarm für relative Metriken (still, getestet); Hinweis im Briefing statt im Alarm.
- Der Wechsel von absoluten zu relativen SMS-Werten ist eine Formatänderung; Empfänger, die `FZ` bisher als absolute Höhe lasen, sehen jetzt ein Vorzeichen-Delta.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0019-Nachtrag (Schneefallgrenze eigenständige Alarm-Metrik), Lieferung in S7f vor S7c1; sonst keine neue ADR.
- **Rationale:** ADR-0019 verlangt für eine eigenständige Schneefallgrenze-Alert-Metrik eine neue Spezifikation; diese Spec ist sie. ADR-0106 P5/P6 und D4 werden umgesetzt, nicht geändert; die Mittlere-Wolken-Entscheidung weicht nicht von ADR-0106 P5 ab und braucht keinen Nachtrag.

## Changelog

- 2026-11-28: Initial spec created (Gesamt-Spec mit Lieferplan S7a1 bis S7f, PO-Entscheidungen E1 und E2 vom 2026-11-28)
