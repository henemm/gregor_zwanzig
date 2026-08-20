---
entity_id: outlook_gehzeit_und_spanne
type: bugfix
created: 2026-08-20
updated: 2026-08-20
status: approved
version: "1.0"
tags: [outlook, trip, compare, gehzeit, "#1848"]
---

# Outlook: Gehzeit-Fenster und Spannen-Zelle (#1848 Scheibe A1)

## Approval

- [x] Approved — PO, 2026-08-20 („go"). Freigegeben wurden alle 10 ACs inklusive AC-9
      (Altform-Klartext wechselt auf den Schrägstrich; sichtbar auch ohne jede Nutzereinstellung).

## Purpose

Der 3-Tages-Ausblick (Trip UND Ortsvergleich) liest Temperatur und gefühlte Temperatur heute
aus dem Etappenaggregat statt aus dem Gehzeit-Fenster — derselbe Randbehandlungsfehler
(exklusive Ankunftsstunde), der #1417 für SMS/Telegram/Kachelzeile bereits behoben hat, nur
für den Ausblick übersehen. Zusätzlich zeigt der Ausblick Tief und Hoch bei gemeinsamer Auswahl
als zwei getrennte Spalten statt einer Spanne, und der Klartext der festen Altform nutzt einen
anderen Trenner als die SMS. A1 zieht alle drei Punkte auf den SMS-Ist-Zustand nach.

## Source

- **File:** `src/output/renderers/email/outlook.py`
- **Identifier:** `def build_outlook_row(...)` — geteilter Zeilenbauer für Trip UND Compare
  (Epic #1301 B4), Ansatzpunkt für Punkt 1 (Gehzeit-Wert) und Punkt 2 (Spannen-Zelle).

> **Schicht-Hinweis:** Reines Python-Core (`src/output/`, `src/services/`, `src/app/`) — kein
> Go-API-, kein Frontend-Code betroffen. Der Ausblick ist reine Server-Rendering-Logik.

## Estimated Scope

- **LoC:** ~180-220 (Produktivcode ~70-100, Golden-Fixture-Anpassungen ~10, neue Tests ~90-110)
  — **passt** unter das 250-LoC-Limit, aber knapp; bei Überschreitung
  `workflow.py set-field loc_limit_override 300` erwägen statt Test-Umfang zu kürzen.
- **Files:** 4 Produktivdateien (MODIFY), 2 Bestandstest-Dateien (MODIFY, Golden-Fixture), 1-2
  neue Testdateien (CREATE).
- **Effort:** medium (drei fachlich unabhängige Teiländerungen an einer gemeinsam genutzten
  Baustelle).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `collect_hiking_window_points()` | function, `src/output/renderers/day_window.py:186` | Gehzeit-gefensterte Rohpunkte (Ankunftsstunde beim letzten Segment inklusiv), einzige Quelle seit #1417 für SMS/Telegram/Kachelzeile |
| `hiking_field_min_max()` | function, `src/output/renderers/day_window.py:232` | Min/Max eines Feldes (`t2m_c`/`wind_chill_c`) aus den Gehzeit-Punkten; liefert `None` bei leerem Fenster (Fail-soft-Signal an den Aufrufer) |
| `build_outlook_row()` | function, `src/output/renderers/email/outlook.py` | Geteilter Zeilenbauer, aufgerufen von `trip_report_scheduler.py` (Trip) und `email/compare_html.py` (Ortsvergleich) |
| `outlook_columns()` / `format_outlook_value()` | functions, `src/output/renderers/compare_outlook_metric_ids.py:112`/`152` | Spalten-/Zellenaufbau für den konfigurierbaren Ausblick-Pfad (`metrics is not None`) — Ansatzpunkt für die Spannen-Zelle, wirkt geteilt auf Trip und Compare |
| `format_trend_tokens()` | function, `src/output/renderers/email/helpers.py` | Baut `temp_str` der festen Altform (Zeile 943, `f"{tl}–{th}°C"`) für den unkonfigurierten Pfad (`metrics is None`) |
| `#1841`-Diskriminator-Muster | Vorbild, `outlook.py:~612-639` | `trip_display_config is not None` als Unterscheidung Trip vs. Compare — dasselbe Muster gilt für Punkt 1 |

## Implementation Details

**Zwei Render-Pfade, in beiden muss der Wert stimmen.** `build_outlook_row()` liefert je nach
`metrics`-Parameter zwei unabhängige Wertequellen:

- **Fester Altform-Pfad** (`metrics is None`): `temp_lo`/`temp_hi` (Zeilen 503-504, aus
  `summary.temp_min_c`/`temp_max_c`) landen im Row-Dict und speisen über
  `format_trend_tokens()` den Klartext-Token `temp_str` (`helpers.py:943`).
- **Konfigurierbarer Pfad** (`metrics is not None`, aktiv sobald ein Trip eine
  `display_config` hat ODER der Ortsvergleich `outlook_metrics` gesetzt hat): die `cells`-Liste
  (Zeilen 643-655) liest **direkt** `getattr(summary, col["field"], None)` — für Temperatur
  `temp_min_c`/`temp_max_c`, für gefühlte Temperatur `wind_chill_min_c`/`wind_chill_max_c`
  (`metric_catalog.py:218`). `temp_lo`/`temp_hi` werden hier **nicht** gelesen. Dieser Pfad
  rendert sowohl die HTML-Tabelle (`outlook.py:128-155`) als auch den Klartext
  (`outlook.py:333-341`) aus derselben `cells`-Liste — eine Quelle für beide Formate.

  Gefühlte Temperatur hat **keinen** Altform-Weg — sie existiert nur im konfigurierbaren Pfad.
  Ein Fix, der nur `temp_lo`/`temp_hi` überschreibt, träfe daher Punkt 1 nur zur Hälfte
  (Temperatur ja, gefühlte Temperatur nein) und den in der Praxis überwiegend aktiven
  konfigurierbaren Pfad gar nicht.

**Punkt 1 — Ansatz:** `trip_report_scheduler.py` hat `seg_weather` (mit Zeitreihen) bereits
vorliegen (Zeile ~2270-2286, vor `aggregate_stage()`). Dort zusätzlich
`collect_hiking_window_points(seg_weather)` + `hiking_field_min_max(punkte, "t2m_c")` bzw.
`"wind_chill_c")` aufrufen (dieselben Funktionen, die `sms_trip.py:238-240` bereits nutzt) und
das Ergebnis als optionalen Overrides-Parameter an `build_outlook_row()` durchreichen.
`build_outlook_row()` wendet den Override an **beiden** Stellen an: bei der Ableitung von
`temp_lo`/`temp_hi` UND beim `getattr(summary, col["field"])`-Zugriff der `cells`-Schleife
(Felder `temp_min_c`/`temp_max_c`/`wind_chill_min_c`/`wind_chill_max_c`). Liefert
`hiking_field_min_max()` `None` (leeres Fenster), bleibt das jeweilige Feld beim
Etappenaggregat (Fail-soft, kein Override gesetzt). Diskriminator wie beim #1841-Vorbild:
`trip_display_config is not None` — der Ortsvergleich (`email/compare_html.py`) übergibt keine
Overrides und bleibt unverändert (er hat keine Gehzeit, vgl. `comparison_engine.py:43-86`).

**Punkt 2 — Ansatz:** Wenn `outlook_columns(metrics)` für dieselbe Größe sowohl eine
`min`- als auch eine `max`-Spalte enthält, werden die beiden Spalten zu einer zusammengeführt
(ein Spaltenkopf, ein `field`-Paar) und die zugehörigen zwei Werte beim Zellentext zu
`{min}/{max}` verbunden (Schrägstrich, kein Leerzeichen, vorhandenes Minuszeichen bleibt
unangetastet — `"-12/-4"`, nicht `"-1", "2/-4"`). Ist nur eine der beiden Auswertungen
ausgewählt, bleibt die bestehende Ein-Spalten-Logik unverändert (kein Merge, kein Schrägstrich).
Fehlt bei **beiden ausgewählten** Auswertungen einer der beiden Werte (Datenlücke, z. B. wenn
`hiking_field_min_max()` nur eine Seite liefert oder das Aggregat nur eine Seite trägt), zeigt
die Zelle die vorhandene Seite und `-` für die fehlende (`"13/-"`) — das ist ein anderer Fall
als „nur eine Auswertung gewählt" und darf nicht damit verwechselt werden. Die Umsetzung sitzt
in `outlook_columns()`/`format_outlook_value()` bzw. in der `cells`-Schleife von
`build_outlook_row()` — geteilt zwischen Trip und Compare, keine zweite Kopie (Trip/Compare-
Teilungsgebot, CLAUDE.md).

**Punkt 3 — Ansatz:** `helpers.py:943` (`f"{tl}–{th}°C"`) wird auf denselben Schrägstrich
gezogen. Betrifft ausschließlich den festen Altform-Pfad — dort verwendet sowohl Trip
(unkonfigurierte Fälle) als auch Ortsvergleich (`outlook_metrics` nicht gesetzt) dieselbe
Funktion. Golden-Fixtures mit dem alten Halbgeviertstrich müssen mitgezogen werden:
`tests/tdd/test_compare_outlook.py:205-206` (positiv, `"9–20°C"`/`"21–33°C"`) und `:397-398`
(positiv `"9–20°C" in text_on`), `tests/tdd/test_compare_outlook_metric_selection.py:265-267`
(negative Assertion, bleibt nach Trennerwechsel weiterhin wahr, sollte aber den neuen Trenner
im Kommentar/String führen, damit die Negativprobe nicht versehentlich gegen den alten Trenner
prüft).

## Expected Behavior

- **Input:** Trip mit Segmenten inkl. Zeitreihen; `display_config.outlook_metrics` wählt
  Temperatur min und/oder max (und optional gefühlte Temperatur min/max). Ortsvergleich analog
  über `outlook_metrics`, ohne Gehzeit.
- **Output:**
  - Trip-Ausblick zeigt für Temperatur/gefühlte Temperatur den Wert aus dem Gehzeit-Fenster
    (inkl. Ankunftsstunde), nicht mehr aus dem vollen Etappenfenster.
  - Sind bei einer Größe Tief und Hoch beide gewählt: eine Zelle `{min}/{max}` mit Schrägstrich,
    identisch in HTML und Klartext, in Trip und Ortsvergleich.
  - Ist nur eine Auswertung gewählt: unveränderter Einzelwert.
  - Der Klartext der festen Altform (Trip unkonfiguriert, Ortsvergleich ohne `outlook_metrics`)
    nutzt denselben Schrägstrich statt des Halbgeviertstrichs.
- **Side effects:** keine — reine Lesepfad-/Formatierungsänderung, kein Schreibzugriff auf
  Trip-/User-Daten, keine neuen Persistenzfelder.

## Acceptance Criteria

- **AC-1:** Given eine Etappe, deren Ankunftsstunde im vollen Etappenfenster nicht das
  Tageshoch trägt, aber im Gehzeit-Fenster schon (Sweep-Konstellation, Median-Differenz
  1,23 °C, gemessen) / When der Trip-Ausblick für diese Etappe gerendert wird / Then zeigt die
  Temperatur-Hoch-Spalte denselben Wert wie `hiking_field_min_max(collect_hiking_window_points(seg_weather), "t2m_c")` — und nicht mehr `summary.temp_max_c` des vollen Etappenfensters.
  - Test: Funktionsebene — `build_outlook_row()` mit denselben Segment-Daten aufrufen, die
    `sms_trip.py` für den `D`-Token derselben Etappe verwendet, und die Zahlen vergleichen
    (nicht „gleiche Mail", da Ausblick und Kachelzeile strukturell disjunkte Tagesmengen zeigen
    — `get_future_stages()` filtert `>`, Kachelzeile zeigt `target_date`).

- **AC-2:** Given ein Segment, dessen Gehzeit-Fenster keinen einzigen Datenpunkt mit
  `t2m_c` trägt (Provider-Lücke) / When der Trip-Ausblick für diese Etappe gerendert wird /
  Then fällt die Temperatur-Zelle fail-soft auf `summary.temp_min_c`/`temp_max_c` zurück statt
  „–" zu zeigen oder abzustürzen.
  - Test: `hiking_field_min_max()` liefert `None` (leere Punktliste) simulieren, prüfen dass
    `build_outlook_row()` denselben Wert wie vor dieser Änderung liefert.

- **AC-3:** Given `display_config.outlook_metrics` wählt `wind_chill` min und max / When der
  Trip-Ausblick gerendert wird / Then liest die gefühlte-Temperatur-Zelle ebenfalls aus
  `hiking_field_min_max(punkte, "wind_chill_c")` statt aus `summary.wind_chill_min_c`/
  `wind_chill_max_c` des vollen Etappenfensters — strukturell derselbe Fehler wie bei der
  gemessenen Temperatur (AC-1), eigener Test wegen eigenem Datenfeld und eigenem SMS-Token
  (`FK`/`FD`, `sms_trip.py:240`).
  - Test: analog AC-1, mit `wind_chill_c`-Feld statt `t2m_c`.

- **AC-4:** Given `outlook_metrics` wählt Temperatur min UND max für eine Etappe mit Werten
  -12 °C und -4 °C / When die Ausblick-Zelle gerendert wird / Then zeigt sie genau eine Zelle
  mit dem Text `-12/-4` — nicht zwei Spalten, kein verlorenes Minuszeichen an der Trennstelle.
  - Test: `outlook_columns()`/Zellentext mit negativen Min- und Max-Werten aufrufen, exakten
    String prüfen.

- **AC-5:** Given `outlook_metrics` wählt für Temperatur ausschließlich max (min nicht
  gewählt) / When die Ausblick-Zelle gerendert wird / Then zeigt sie weiterhin einen
  Einzelwert ohne Schrägstrich (z. B. `13`), identisch zum Verhalten vor dieser Änderung —
  eine reine Konfigurationsauswahl darf nicht mit einer Datenlücke verwechselt werden (AC-6).
  - Test: nur eine Aggregation in `outlook_metrics`, prüfen dass genau eine Spalte mit
    unverändertem Format entsteht.

- **AC-6:** Given `outlook_metrics` wählt Temperatur min UND max, aber für eine Etappe liegt
  nur der Hoch-Wert vor (z. B. Fail-soft-Rückfall liefert nur eine Seite) / When die
  Ausblick-Zelle gerendert wird / Then zeigt sie den vorhandenen Wert und einen Strich für die
  fehlende Seite, z. B. `13/-` — unterscheidbar vom Einzelwert-Fall aus AC-5 dadurch, dass hier
  beide Auswertungen ausgewählt waren.
  - Test: eine Seite auf `None` setzen, beide Aggregationen weiterhin in `outlook_metrics`,
    exakten Zellentext prüfen.

- **AC-7:** Given eine Trip-Mail mit gewählter Temperatur-Spanne / When HTML- und
  Klartext-Teil derselben Mail verglichen werden / Then zeigen beide dieselbe
  Schrägstrich-Zelle für dieselbe Etappe — keine Abweichung zwischen den Formaten (Muster
  `test_plain_outlook_shows_same_selection_as_html`, #1366-Fehlerklasse).
  - Test: HTML-Zelle und Klartext-Zeile derselben gerenderten Mail extrahieren, Zellentext
    vergleichen.

- **AC-8:** Given ein Ortsvergleich mit `outlook_metrics`, die Temperatur min UND max wählen,
  ohne Gehzeit (kein Trip, keine Segmente) / When der Ausblick für einen Ort gerendert wird /
  Then zeigt auch dort eine Zelle die Schrägstrich-Spanne — Punkt 2 gilt geräteübergreifend,
  Punkt 1 (Gehzeit) gilt dort nicht, weil der Ortsvergleich strukturell keine Gehzeit hat.
  - Test: `email/compare_html.py`-Pfad mit `outlook_metrics` min+max aufrufen, Zellentext
    prüfen; separat sicherstellen, dass keine Gehzeit-Funktion aufgerufen wird (kein Absturz
    mangels Segmenten).

- **AC-9:** Given ein Trip ohne `display_config` (Altform) oder ein Ortsvergleich ohne
  `outlook_metrics` mit Temperatur 9 °C bis 20 °C / When der Klartext-Ausblick gerendert wird /
  Then enthält er `9/20°C` statt `9–20°C` — Golden-Fixtures
  `tests/tdd/test_compare_outlook.py:205-206,397-398` sind auf den neuen Trenner gezogen.
  - Test: bestehende Golden-Fixture-Tests mit angepasstem Erwartungsstring, weiterhin grün.

- **AC-10:** Given der Wächtertest `tests/unit/test_gehzeit_metriken_bleiben_trip_exklusiv.py`
  aus Scheibe C / When diese Änderung eingespielt ist / Then bleibt er unverändert grün — A1
  führt keine neuen Registerkennungen ein und hängt der Kennung `temperature` keinen
  „(Gehzeit)"-Zusatz an; nur der Wert hinter der bestehenden Kennung ändert sich.
  - Test: bestehenden Wächtertest unverändert mitlaufen lassen, kein neuer Test nötig.

### Abdeckungstabelle (Zuschnitt A1 gegen ACs)

| Zuschnitt-Punkt | Abgedeckt durch |
|---|---|
| 1. Gehzeit-Fenster für Temperatur/gefühlte Temperatur | AC-1, AC-2, AC-3 |
| 2. Spannen-Zelle mit Schrägstrich (HTML+Klartext, Trip+Compare) | AC-4, AC-5, AC-6, AC-7, AC-8 |
| 3. Altform-Klartext auf denselben Trenner ziehen | AC-9 |
| Nicht-Ziel-Guard (Scheibe-C-Wächter unberührt) | AC-10 |

## Known Limitations

- **`avg` bleibt außen vor** (⇒ A3): der Compare-Katalog kennt für Temperatur nur `min`/`max`,
  keine `avg`-Spalte — diese Spec ändert daran nichts.
- **Neue Registerkennungen bleiben außen vor** (⇒ A2): die vier Gehzeit-Kennungen
  (`temperature_day_low` u. a.) werden weiterhin vom Compare-Katalog verworfen
  (`compare_outlook_metric_ids.py:62`); A1 ändert nur den Wert hinter der bestehenden Kennung
  `temperature`.
- **Wind/Böen-Fensterung bleibt unangetastet** (⇒ Sammel-Issue #1199): beide lesen weiterhin
  aus dem konfigurierten Tagesfenster bzw. den ungefensterten `_flat_points` — beides eigene
  Baustellen, keine Gehzeit-Fensterung.
- **Kanal-Modul im Ausblick bleibt außen vor** (⇒ A3): diese Spec ändert nicht, welche Größen
  wählbar sind, nur wie ein bereits gewähltes Paar dargestellt wird.
- **Kein Nachweis „in derselben Mail"**: der Ausblick zeigt strukturell nie den heutigen Tag
  (`get_future_stages()` filtert `s.date > from_date`), die Kachelzeile deckt `target_date` ab
  — beide Tagesmengen sind disjunkt. Der Bug-Nachweis (AC-1) läuft deshalb auf Funktionsebene,
  nicht als Mail-interner Widerspruch.

## 🔴 Abgelöste Entscheidung: die Paar-basierte Spalten-Sollmenge aus #1703 Scheibe 2

Beim Umsetzen von AC-4..AC-8 kollidierte der Merge mit einer bestehenden, testbewachten
Zusicherung — hier festgehalten, damit die Ablösung **nicht still** passiert.

**Vorher (Epic #1703 S2, PO-Entscheidung 2026-07-27 „keine zwei gleich beschrifteten Spalten"):**
`tests/tdd/test_channel_metric_matrix.py` baute die Soll-Spaltenmenge aus **Paaren**
(`metric_id` + `aggregation`). Wählte der Nutzer alles, erschienen `temperature:min` und
`temperature:max` als **zwei** Spalten mit den disambiguierten Überschriften „Temp Minimum" /
„Temp Maximum" (`compare_outlook_metric_ids.py:144-148`). 26 parametrisierte Tests bewachten das.

**Jetzt (PO-Entscheid 2026-08-20, diese Spec):** min+max desselben `metric_id` werden zu **einer**
Zelle zusammengeführt. Damit fällt die Paar-basierte Sollmenge.

**Warum das keine Aufweichung ist:** Der Testname lautet „jede wählbare **Größe** ergibt genau
eine Spalte" — die Sollmenge war aber über **Paare** gebaut. Nach dem Merge ergibt die Größe
`temperature` weiterhin genau **eine** Spalte; die Invariante im Sinne ihres Namens gilt
unverändert. Angepasst wurde die Soll**menge** (`tests/helpers/outlook_columns.py`), **nicht** die
Zusicherung — beide S2-Tests bleiben in Kraft, inklusive der Gegenrichtung
(`html_und_klartext_zeigen_dieselbe_spaltenmenge`).

**Was ausdrücklich BESTEHEN bleibt:**

- Die Disambiguierungs-Logik (`compare_outlook_metric_ids.py:144-148`) wird **nicht**
  zurückgebaut, obwohl sie durch den Merge vorerst ins Leere läuft (heute haben genau 2 von 29
  wählbaren Größen mehr als eine Auswertung). Kommt mit **A3** `avg` bei Temperatur dazu, hat die
  Größe drei Auswertungen: min+max mergen zur Spanne, `avg` bleibt eine eigene Spalte und braucht
  das Suffix wieder. Ein Rückbau müsste in der nächsten Scheibe zurückgedreht werden.
- Deshalb prüft die Vakuum-Gegenprobe in `test_ac_s2_3_*` seither einen **synthetischen**
  Katalog-Ausschnitt (dritte Auswertung simuliert) statt des realen Katalogs. Am realen Katalog
  wäre sie nach dem Merge **trivial wahr** geworden — der Ausschluss hätte die Bedingung erzeugt,
  mit der er begründet wird, und die Disambiguierung wäre totes, ungetestetes Recht. Der
  synthetische Ausschnitt ist **absichtlich** synthetisch und darf nicht auf den realen Katalog
  „zurückkorrigiert" werden.
- Die Anti-Vertauschungs-Prüfung (AC-S2-6/AC-S2-8) wurde **umgebaut, nicht abgeschwächt**: Die
  Zelle wird an `/` geteilt und **jede Seite** gegen ihren eigenen gerechneten Sollwert geprüft.
  Ohne diesen Umbau hätte die Prüfung nur noch die führende Zahl gelesen und wäre für eine
  Vertauschung strukturell **blind** geworden — ein Wächter, der dasteht und nichts mehr fängt.
  Wirksamkeit per Mutation belegt (vertauschte Zuweisungen ⇒ beide Tests rot).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues Entscheidungsfeld (Kanal, Provider, Datenmodell, Auth,
  Editor-Paradigma, Test-/Deploy-Strategie) — reine Fortsetzung des mit #1417 bereits
  getroffenen Musters (Gehzeit-Fenster statt Etappenaggregat) auf eine bis dahin übersehene
  Fläche, plus eine Formatangleichung an einen bereits bestehenden SMS-Trenner. Der geteilte
  Baustein `build_outlook_row()`/`outlook_columns()` bleibt architektonisch unverändert
  (weiterhin EIN Zeilenbauer für Trip und Compare, Epic #1301 B4) — keine neue
  Architekturentscheidung, nur deren konsequente Anwendung.

## Changelog

- 2026-08-20: Initial spec created (#1848 Scheibe A1)
- 2026-08-20: Ablösung der Paar-basierten Spalten-Sollmenge aus #1703 S2 dokumentiert; Umbau der
  Anti-Vertauschungs-Prüfung und der Vakuum-Gegenprobe festgehalten (beide wirksam belegt).
- 2026-08-20: Nach Adversary-Verdict VERIFIED eine Wache für die Scheduler-Verdrahtung ergänzt
  (`tests/tdd/test_outlook_scheduler_wires_hiking_window.py`). Grund: die Mutation
  `segments=seg_weather` → `None` blieb bei 625 Tests **grün** — die Zusicherung war dort geprüft,
  wo der Code steht, nicht dort, wo sie wirkt. Genau die Fehlerform, die A1 nötig machte (#1417
  stellte drei Kanäle um und übersah den Ausblick). Divergenz gemessen: Etappenaggregat 15,0 °C
  gegen Gehzeit-Fenster 22,0 °C; Mutation macht die Wache nachweislich rot.
