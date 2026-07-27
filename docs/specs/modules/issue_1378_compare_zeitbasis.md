---
entity_id: issue_1378_compare_zeitbasis
type: bugfix
created: 2026-07-27
updated: 2026-07-27
status: draft
version: "1.0"
workflow: fix-1378-compare-zeitbasis
tags: [compare, timezone, ortsvergleich, mail, sms, bugfix, epic-1372]
---

# Ortsvergleichs-Mail rechnet in Serverzeit statt Ortszeit (Issue #1378, S3 Scheibe C von Epic #1372)

## Approval

- [ ] Approved

## Purpose

Die Ortsvergleichs-Mail beschriftet und befüllt ihre Stundenzeilen mit der
Serverzeit (UTC) des Datenpunkts statt mit der Ortszeit des jeweiligen Ortes.
An einer echt zugestellten Staging-Mail vom 2026-07-27 belegt: Wer im Preset
„9 bis 16 Uhr" einstellt, bekommt für einen Ort in `Europe/Vienna`
ziffernweise die Werte von 11 bis 18 Uhr Ortszeit, beschriftet als „9 bis
16 Uhr" (+2h Versatz, Sommerzeit). Dieses Modul zieht Ortsvergleich auf
denselben Ortszeit-Weg, den das Trip-Briefing bereits nutzt: **ein**
Zeitzonen-Auflöser für Stundenauswahl, HTML-Beschriftung, Klartext-
Beschriftung, 3-Tage-Ausblick (inkl. dessen Tagesgrenze), die
„Erstellt"-Kopfzeile beider Mail-Teile und den SMS-Warn-Marker.

## Source

- **File:** `src/utils/timezone.py` — bestehendes, bereits an anderer Stelle
  etabliertes Modul (`tz_for_coords`, `local_hour`, `local_fmt`); bekommt eine
  neue, kleine Auflöse-Funktion, die `SavedLocation.timezone` (falls gesetzt)
  vor `tz_for_coords(lat, lon)` bevorzugt — **einziger** Aufrufweg für alle
  sieben betroffenen Stellen (kein zweiter oder dritter Auflöser mehr).
- **File:** `src/services/comparison_engine.py` —
  `_filter_by_target_date_and_window()` (Zeile 40-61) filtert aktuell über
  `dp.ts.hour` (rohe UTC-Stunde); muss auf die Ortszeit-Stunde des jeweiligen
  Ortes umgestellt werden. Aufrufpunkt: `ComparisonEngine.run()`, innerhalb
  der Pro-Ort-Schleife (Zeile 102ff.), wo `loc.lat`/`loc.lon` bereits
  verfügbar sind.
- **File:** `src/output/renderers/email/compare_html.py` —
  `_render_hour_row()` (Zeile 639-661, konkret Zeile 644) beschriftet über
  `dp.ts.strftime("%H")`; `_build_location_outlook_rows()` (Zeile 741-761,
  konkret Zeile 750) löst die Zeitzone bisher über
  `getattr(loc.location, "timezone", None) or "UTC"` auf; `_group_by_calendar_day()`
  (Zeile 732-738) gruppiert die Ausblick-Datenpunkte über `dp.ts.date()`
  (UTC-Kalendertag statt Ortstag); `_render_header()` (Zeile 817ff., konkret
  Zeile 834) zeigt `datetime.now().strftime("%H:%M")` als „Erstellt"-Zelle.
- **File:** `src/output/renderers/comparison.py` — Klartext-Stundenzeile
  (Zeile 227-229, konkret `dp.ts.strftime("%H:%M")`); Klartext-Kopfzeile
  „Erstellt: …" (Zeile 175, `created_at.strftime('%d.%m.%Y %H:%M')`);
  `_sms_location_part()` (Zeile 524-557, konkret Zeile 549) löst die
  Zeitzone für den `@Stunde`-Warn-Marker bisher über `ZoneInfo(loc_result
  .location.timezone) if loc_result.location.timezone else None` auf —
  dritter Auflöser neben Punkt 1 (Fensterfilter) und Punkt 4 (Ausblick).
- **Identifier:** neue Funktion in `src/utils/timezone.py` (Arbeitstitel
  `resolve_location_tz(location)` oder gleichwertig — Entscheidung liegt beim
  Developer-Agenten, Signatur muss `SavedLocation`-Vorrang + Koordinaten-
  Fallback abbilden), `ComparisonEngine._filter_by_target_date_and_window`,
  `compare_html._render_hour_row`, `compare_html._build_location_outlook_rows`,
  `compare_html._group_by_calendar_day`, `compare_html._render_header`,
  `comparison.render_comparison_text` (Stunden- und Kopfzeilen-Abschnitt),
  `comparison._sms_location_part`.

> **Schicht-Hinweis:** Ausschließlich Python-Core
> (`src/services/`, `src/output/renderers/`, `src/utils/`), Prozess
> `gregor-python`. Kein Go-Anteil, kein Frontend-Anteil — Mail und SMS werden
> serverseitig gerendert, es gibt keine UI-Oberfläche für dieses Verhalten.

## Estimated Scope

- **LoC:** ~110-170 (neue Auflöse-Funktion in `timezone.py` ~15-20;
  `comparison_engine.py`-Fensterfilter-Umstellung ~15-25;
  `compare_html.py` vier Stellen [Stunden, Ausblick-Aufloesung,
  Ausblick-Tagesgrenze, Kopfzeile] ~40-55; `comparison.py` drei Stellen
  [Klartext-Stunden, Klartext-Kopfzeile, SMS-Marker] ~30-45;
  Kopfzeilen-Kürzel-Formatierung ggf. geteilter Helfer ~10-15)
- **Files:** 4 Produktionsdateien geändert (kein Neuanlage einer Datei nötig,
  die Auflöse-Funktion kommt in das bestehende `timezone.py`); Tests kommen
  in Phase 4 (TDD RED) dazu
- **Effort:** medium — kleine Diff-Fläche, aber sieben Call-Sites in zwei
  Renderern plus dem Engine-Filter müssen konsistent bleiben; Renderer-
  Commit-Gate #811 greift auf `compare_html.py` und `comparison.py`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `utils.timezone.tz_for_coords` | reused | Koordinaten-basierter Fallback-Auflöser (TimezoneFinder), bereits genutzt von `alert/project.py`, `notification_service.py` (6x), `trip_alert.py` |
| `utils.timezone.local_hour`, `utils.timezone.local_fmt` | reused | Bestehende Konvertierungshelfer, unverändert — nur die neue Auflöse-Funktion ist neu |
| `output.renderers.day_window` | Vorbild | Trip-Pfad filtert das Tagesfenster bereits über `local_hour(dp.ts, tz)` statt `dp.ts.hour` — dieselbe Umstellung wird hier für Compare nachgezogen (Trip/Compare-Teilungs-Invariante) |
| `output.renderers.email.helpers` (`extract_hourly_rows`, Zeile 93/142) | Vorbild | Trip-Beschriftung über `local_hour`/`local_fmt` statt `strftime` auf naiver UTC |
| `app.user.SavedLocation.timezone` | upstream | Optionales, nutzerseitig gesetztes Zeitzonen-Feld (Zeile 64) — hat Vorrang vor `tz_for_coords`, wenn gesetzt; bei den drei Staging-Referenzorten aktuell `None` |
| `services.comparison_engine.ComparisonEngine.run` | Source | Pro-Ort-Schleife, in der `loc.lat`/`loc.lon` für die Auflösung verfügbar sind; Downstream für Web-UI und alle Renderer (ein Fix wirkt auf beide) |
| `services.report_config_resolver.resolve_compare_time_window` | upstream, unverändert | Liefert weiterhin nur `(start_hour, end_hour)` aus dem Preset — die Interpretation dieser Stunden als Ortszeit passiert erst in der Engine, nicht im Resolver |
| `services.compare_preview_service.order_locations_by_ids`, `email.compare_html.location_render_order` | upstream, unverändert | `order_locations_by_ids()` baut die vom Nutzer konfigurierte Orts-Reihenfolge aus `preset["location_ids"]` (Issue #1359 Scheibe 2); `location_render_order()` reicht diese Reihenfolge beim Rendern unverändert durch — **keine** alphabetische Sortierung mehr. Der erste Ort der Kopfzeile (AC-4) ist der erste Ort dieser Reihenfolge. |
| `output.renderers.alert.official_alerts.official_alerts_to_sms_entries` | upstream, unverändert | Nimmt `tz: Optional[ZoneInfo]` entgegen; `tz=None` lässt den Stunden-Teil des SMS-Markers ersatzlos entfallen (dokumentierte, budget-getriebene SMS-Konvention) — nach dem Fix liefert `_sms_location_part` hier die aufgelöste Zeitzone statt `None`, sobald Koordinaten auflösbar sind |
| `output.renderers.email.compare_html`, `output.renderers.comparison` | Downstream | Beide Mail-Renderer (HTML + Klartext) sowie der SMS-Renderer teilen sich `ComparisonResult`/`LocationResult` aus derselben Engine — ein Auswahlfix wirkt auf alle drei Kanäle gleichzeitig |
| `renderer_mail_gate.py` (#811) | Gate | Blockiert den Commit auf `compare_html.py`/`comparison.py`, bis `test_issue_811_mode_matrix.py` grün ist UND ein frischer `briefing_mail_validator.py`-Lauf vorliegt |

## Implementation Details

**Eine Auflöse-Funktion, sieben Aufrufstellen.** Die neue Funktion in
`timezone.py` bekommt einen Ort (oder `lat`/`lon` + optionales
`stored_timezone`) und liefert eine `ZoneInfo`: `SavedLocation.timezone`
(wenn gesetzt und gültig) hat Vorrang, sonst `tz_for_coords(lat, lon)`
(Fallback UTC bei Auflösungsfehler, wie bisher in `tz_for_coords`). Alle
Stellen unten rufen ausschließlich diese eine Funktion auf — kein Ort
implementiert seine eigene Kopie der Vorrang-Logik.

1. **Stundenauswahl** (`comparison_engine.py`): Die Pro-Ort-Schleife in
   `ComparisonEngine.run()` löst die Zeitzone einmal je Ort auf (mit
   `loc.lat`/`loc.lon`) und übergibt sie an
   `_filter_by_target_date_and_window()`. Der Vergleich `start_hour <=
   dp.ts.hour <= end_hour` wird durch den Vergleich gegen
   `local_hour(dp.ts, tz)` ersetzt — analog dem bereits bestehenden
   Mitternachts-Wrap-Zweig, der unverändert erhalten bleibt (nur die
   Stunden-Quelle ändert sich, nicht die Fenster-Arithmetik aus #1361 S1b).
   Der Kalendertag-Vergleich (`dp.ts.date() == target_date`) muss ebenfalls
   auf das lokale Datum bezogen werden, sonst kann ein Datenpunkt am
   Ortszeit-Tagesanfang/-ende falsch dem Vortag/Folgetag zugeordnet werden.

2. **HTML-Stundenbeschriftung** (`compare_html._render_hour_row`): `hh =
   dp.ts.strftime("%H")` wird durch `local_hour(dp.ts, tz)` (formatiert als
   zweistellige Stunde) ersetzt. Die Zeitzone kommt aus demselben Ort wie
   die bereits gefilterten `hourly_data` — kein zweiter Fetch, keine zweite
   Auflösung je Zeile.

3. **Klartext-Stundenbeschriftung** (`comparison.render_comparison_text`):
   `ts = dp.ts.strftime("%H:%M")` (Zeile 229) wird durch dieselbe
   Ortszeit-Auflösung ersetzt wie Punkt 2 — **eigener** Umsetzungsschritt,
   weil der Pflicht-Validator (`email_spec_validator.py`) laut
   `docs/reference/mail_validators.md` nur den HTML-Teil liest; dieser Teil
   ist ohne eigenständige Prüfung blind (Scheibe-B-Erfahrung, #1366).

4. **3-Tage-Ausblick — Zeitzonen-Auflösung** (`compare_html
   ._build_location_outlook_rows`): Die bisherige Ad-hoc-Logik
   `getattr(loc.location, "timezone", None) or "UTC"` +
   `ZoneInfo(tz_name)`-try/except wird durch einen Aufruf der neuen
   Auflöse-Funktion ersetzt. Das behebt den in der Analyse belegten
   zweiten Auflöser: bisher lief der Ausblick auf dem „richtigen" Feld
   (`Location.timezone`), bekam aber bei allen drei Staging-Referenzorten
   `None` und fiel hart auf UTC zurück, statt wie jetzt auf
   `tz_for_coords` auszuweichen.

5. **3-Tage-Ausblick — Tagesgrenze** (`compare_html
   ._group_by_calendar_day`): Derselbe Defekt in einer zweiten Dimension —
   die Gruppierung der Ausblick-Datenpunkte nach Kalendertag läuft aktuell
   über `dp.ts.date()` (UTC-Datum). Selbst nach Punkt 4 (Ortszeit-Stunden
   in den Zeilen) bliebe die Tagesgrenze Mitternacht UTC: bei einem
   UTC+2-Ort zählen die Stunden 22:00-23:59 UTC eines Ortstages fälschlich
   zum nächsten Ortstag, die „Mo/Di/Mi"-Zeilen verschieben sich gegenüber
   der tatsächlichen Ortszeit-Tagesgrenze. `_group_by_calendar_day`
   gruppiert künftig über `dp.ts.astimezone(tz).date()` mit derselben
   Zeitzone wie Punkt 4 (ein Aufruf der Auflöse-Funktion je Ort genügt,
   `tz` wird für beide Schritte 4 und 5 wiederverwendet).

6. **„Erstellt"-Kopfzeile** (beide Mail-Teile): HTML
   (`compare_html._render_header`, Zeile 834, `datetime.now().strftime(...)`)
   und Klartext (`comparison.py`, Zeile 175, `created_at.strftime(...)`)
   zeigen die Erzeugungszeit künftig in der Ortszeit des **erstgenannten**
   Ortes — erster Ort der vom Nutzer konfigurierten Orts-Reihenfolge
   (`location_ids` im Preset, aufgelöst über `order_locations_by_ids()` und
   unverändert durchgereicht von `location_render_order()`, Issue #1359
   Scheibe 2 — **nicht** alphabetisch, diese Sortierung wurde damit
   abgelöst) — plus einem erkennbaren Zeitzonen-Kürzel oder -Offset (z. B.
   `06:58 (MESZ)` oder `06:58 (UTC+2)` — konkrete Formatierung liegt beim
   Developer-Agenten, Pflicht ist nur die erkennbare Angabe der Zeitbasis,
   nicht ein bestimmtes Kürzel-Format).

7. **SMS-Warn-Marker** (`comparison._sms_location_part`, Zeile 549): `tz =
   ZoneInfo(loc_result.location.timezone) if loc_result.location.timezone
   else None` wird durch denselben Aufruf der neuen Auflöse-Funktion
   ersetzt wie an den Stellen oben — E3 verlangt genau EINEN Auflöser,
   kein dritter Weg. Für Orte mit auflösbaren Koordinaten erscheint der
   `@Stunde`-Teil des `!`-Warn-Markers künftig in Ortszeit, auch ohne
   gesetztes `SavedLocation.timezone`. Für Orte, deren Koordinaten sich
   keiner Zeitzone zuordnen lassen, bleibt die bestehende, budget-
   getriebene SMS-Konvention erhalten: der Stunden-Teil entfällt weiterhin
   ersatzlos (kein Platzhalter) — das ist eine bewusste SMS-Eigenheit
   (140-Zeichen-Budget), keine stille Serverzeit-Anzeige, und daher kein
   Widerspruch zu AC-7 (die dort verlangte sichtbare UTC-Markierung gilt
   für die Mail, nicht für die SMS-Budget-Konvention).

**Interne Pipeline bleibt UTC.** `dp.ts` bleibt naive UTC (Hausnorm
#1345, `models.py:146-157`) — die Umrechnung passiert ausschließlich an den
sieben genannten Render-/Filter-Stellen, nicht in der Datenhaltung oder im
Provider-Fetch.

## Expected Behavior

- **Input:** Ein Compare-Preset mit Tagesfenster (`day_window_start_hour`,
  `day_window_end_hour`) und mindestens einem Ort mit bekannten
  Koordinaten (`lat`/`lon`), optional mit gesetztem `SavedLocation.timezone`.
- **Output:** Eine zugestellte Vergleichs-Mail (HTML + Klartext), deren
  Stundenzeilen je Ort exakt die Ortszeit-Stunden des eingestellten
  Fensters zeigen — sowohl in der Auswahl der Datenpunkte als auch in deren
  Beschriftung —, deren 3-Tage-Ausblick dieselbe Ortszeit inklusive
  korrekter Ortszeit-Tagesgrenze verwendet, deren „Erstellt"-Kopfzeile
  (beide Mail-Teile) die Ortszeit des erstgenannten Ortes mit erkennbarem
  Zeitzonen-Kürzel trägt, und deren Compare-SMS-Warn-Marker den
  `@Stunde`-Teil in Ortszeit zeigt, sobald die Ort-Koordinaten eine
  Zeitzone ergeben.
- **Side effects:** Bei Orten mit positivem UTC-Versatz verschiebt sich der
  intern angefragte Rohdaten-Zeitraum effektiv nach vorn (das eingestellte
  Fenster in Ortszeit liegt später in UTC-Uhrzeit) — `COMPARE_FORECAST_HOURS`
  (96h) muss diesen verschobenen Bereich weiterhin abdecken (siehe Risiken).

## Was sich NICHT ändern darf

- **Trip-Briefing-Pfad bleibt unberührt.** `day_window.py`, `email/helpers.py`
  und alle Trip-Renderer werden nicht angefasst — sie rechnen bereits korrekt
  in Ortszeit.
- **Übersichtstabelle, Metrik-Auswahl, Orts-Reihenfolge bleiben unverändert.**
  Die in #1359/#1366 frisch gelieferte Reihenfolgen- und
  Metrik-Auswahl-Logik (`_ordered_rows`, `order_locations_by_ids`,
  `location_render_order`, `_visible_hour_metrics`) wird nicht verändert —
  nur die Zeitbasis der bereits gewählten Stunden-Metriken.
- **Fensterarithmetik (Mitternachts-Wrap, ADR-0035/#1361 S1b) bleibt
  strukturell erhalten.** Es ändert sich nur, auf welcher Stunden-Quelle
  (UTC vs. Ortszeit) der Vergleich `start_hour <= h <= end_hour` läuft.
- **SMS-Budget-Konvention bleibt erhalten.** Fehlt eine Zeitzone weiterhin
  (unauflösbare Koordinaten), entfällt der `@Stunde`-Teil im SMS-Marker
  ersatzlos wie bisher — es wird kein Platzhalter/Kennzeichen ergänzt, das
  Zeichenbudget bliebe sonst unnötig belastet.
- **Interne Pipeline bleibt 100% UTC.** Keine Umstellung von `dp.ts`,
  `target_date` oder anderen intern gespeicherten Zeitstempeln auf
  Ortszeit — Umrechnung ausschließlich beim Rendern/Filtern.

## Acceptance Criteria

- **AC-1:** Given ein Vergleichspreset mit Tagesfenster 9-16 Uhr und einem
  Ort in einer Zeitzone mit UTC+2-Versatz (z. B. Europe/Vienna im Sommer),
  When die Vergleichs-Mail für diesen Ort erzeugt wird, Then enthält die
  Stundentabelle genau die Datenpunkte der Ortszeit-Stunden 9 bis 16 — nicht
  die Serverzeit-Stunden 9 bis 16, die inhaltlich den Ortszeit-Stunden 11
  bis 18 entsprächen.
  - Test: Gegenprobe der Temperaturwerte in den ausgewählten Zeilen gegen
    eine unabhängige Ortszeit-Referenzabfrage (analog dem Staging-Nachweis
    vom 2026-07-27) — kein Dateiinhalt-Check.

- **AC-2:** Given eine zugestellte Vergleichs-Mail mit HTML-Teil, When eine
  Zeile der Stundentabelle die Werte einer bestimmten Ortszeit-Stunde zeigt,
  Then trägt genau diese Zeile die Beschriftung dieser Ortszeit-Stunde
  (ziffernweise Übereinstimmung zwischen Beschriftung und unabhängig
  abgefragter Ortszeit, keine +2h/-2h-Verschiebung).
  - Test: Zugestellte Mail per IMAP abrufen, HTML-Stundenzeile gegen
    Ortszeit-Referenzwerte prüfen (Vorbild: Nachweis-Tabelle im
    Kontext-Dokument).

- **AC-3:** Given dieselbe zugestellte Vergleichs-Mail, When der Klartext-Teil
  (nicht der HTML-Teil) seine Stundenzeilen zeigt, Then tragen auch dort die
  Zeilen die Ortszeit-Stunde als Beschriftung, identisch zu den
  entsprechenden Werten und Beschriftungen im HTML-Teil derselben Mail.
  - Test: Eigenständige Prüfung des Klartext-Teils (der Pflicht-Validator
    liest nur HTML) — Stundenzeilen-für-Stundenzeile-Vergleich zwischen
    Klartext- und HTML-Teil derselben zugestellten Mail.

- **AC-4:** Given die Vergleichs-Mail wird erzeugt, When die
  „Erstellt"-Kopfzeile im HTML-Teil und im Klartext-Teil betrachtet wird,
  Then zeigen beide Teile die Ortszeit des erstgenannten Ortes (erster Ort der
  vom Nutzer konfigurierten Orts-Reihenfolge, `order_locations_by_ids`,
  #1359 — NICHT alphabetisch) zusammen mit einem für den Empfänger
  erkennbaren Zeitzonen-Hinweis (Kürzel oder Offset) — nicht die
  unkommentierte Serverzeit.
  - Test: Zugestellte Mail, „Erstellt"-Wert in HTML und Klartext gegen die
    tatsächliche Ortszeit des erstgenannten Ortes zum Sendezeitpunkt
    geprüft.

- **AC-5:** Given ein Ort ohne gespeicherte Zeitzone
  (`SavedLocation.timezone` ist `None`) aber mit bekannten Koordinaten, When
  der 3-Tage-Ausblick für diesen Ort gerendert wird, Then wird die Ortszeit
  über dieselbe koordinatenbasierte Auflösung ermittelt wie für die
  Stundentabelle desselben Ortes — kein stiller Rückfall auf UTC, solange
  die Koordinaten eine Zeitzone ergeben.
  - Test: Ausblick-Wochentag/-Zeitbezug für einen Ort ohne gesetzte
    Zeitzone gegen die aus den Koordinaten erwartete Ortszeit geprüft.

- **AC-6:** Given ein Vergleich enthält zwei Orte in unterschiedlichen
  Zeitzonen mit demselben eingestellten Tagesfenster, When die Mail erzeugt
  wird, Then zeigt jeder Ortsblock die Datenpunkte und Beschriftungen
  seiner EIGENEN Ortszeit-Stunden im eingestellten Fenster — auch wenn die
  absoluten (UTC-)Zeitpunkte der beiden Ortsblöcke dadurch voneinander
  abweichen.
  - Test: Zwei Orte mit unterschiedlichem UTC-Versatz im selben Preset,
    Stundenbeschriftung je Block gegen die jeweils eigene Ortszeit geprüft
    (nicht gegen eine gemeinsame absolute Uhrzeit).

- **AC-7:** Given ein Ort, dessen Koordinaten sich keiner Zeitzone zuordnen
  lassen und der keine gespeicherte Zeitzone hat, When die Vergleichs-Mail
  für diesen Ort erzeugt wird, Then fällt die Anzeige erkennbar auf UTC
  zurück (z. B. durch ein sichtbares UTC-Kennzeichen an der betroffenen
  Stelle), statt unmarkiert eine falsche Ortszeit vorzutäuschen.
  - Test: Auflösungsfehler simulieren (nicht auflösbare Koordinaten), Mail
    prüfen, dass die betroffene Stelle als UTC erkennbar ist, nicht
    stillschweigend als vermeintliche Ortszeit erscheint.

- **AC-8:** Given eine zugestellte Vergleichs-Mail für einen einzelnen Ort,
  When Stundenzeile, 3-Tage-Ausblick und „Erstellt"-Kopfzeile derselben Mail
  gegenübergestellt werden, Then nennen alle drei Elemente dieselbe
  Zeitbasis (dieselbe Ortszeit-Zone) — es gibt keine Stelle, die noch
  Serverzeit zeigt, während eine andere Stelle derselben Mail bereits
  Ortszeit zeigt.
  - Test: Gegenprobe an einer einzigen zugestellten Mail — Zeitzonen-Bezug
    von Stundenzeile, Ausblick und Kopfzeile auf Übereinstimmung geprüft.

- **AC-9:** Given ein Ort mit UTC+2-Versatz und ein Datenpunkt zwischen
  22:00 und 23:59 UTC, When der 3-Tage-Ausblick für diesen Ort gerendert
  wird, Then wird dieser Datenpunkt dem Ortstag zugeordnet, in dessen
  Ortszeit-Mitternachtsfenster (00:00-23:59 Ortszeit) er tatsächlich liegt
  — nicht dem UTC-Kalendertag, der ihn bei UTC+2 fälschlich noch dem
  vorangehenden Ortstag zuschlagen würde.
  - Test: Datenpunkt nahe der Mitternachtsgrenze (z. B. 22:30 UTC bei
    einem UTC+2-Ort) gegen die erwartete Ortstag-Zuordnung der
    Ausblick-Zeile geprüft (Wochentag-Label und Tages-Aggregation der
    betroffenen Zeile).

- **AC-10:** Given ein Ort ohne gespeicherte Zeitzone
  (`SavedLocation.timezone` ist `None`) aber mit auflösbaren Koordinaten
  und einer amtlichen Warnung ab Stufe orange, When die Compare-SMS für
  diesen Ort erzeugt wird, Then erscheint der `@Stunde`-Teil des
  Warn-Markers in der aus den Koordinaten aufgelösten Ortszeit — nicht
  ersatzlos entfallend wie bisher.
  - Test: Deterministischer Kern-Test — Ort ohne `timezone`-Feld, aber mit
    Koordinaten, plus simulierter amtlicher Warnung ab Stufe orange;
    SMS-Text auf vorhandenen, korrekten `@Stunde`-Anteil geprüft. **Kein
    Live-SMS-Versand** — echte SMS kosten Kontingent, dieser AC wird
    ausschließlich im deterministischen Kern verifiziert.

## Risiken

1. **Fensterverschiebung kann den Rohdaten-Horizont sprengen.** Das Fenster
   wird auf Ortsstunden angewandt; bei UTC+2 verschiebt sich der effektiv
   benötigte Rohdatenbereich um 2 Stunden nach hinten (in UTC-Uhrzeit
   gerechnet). `COMPARE_FORECAST_HOURS` (96h) deckt das im Normalfall ab,
   ist aber bei der Implementierung explizit zu prüfen, nicht nur
   anzunehmen.
2. **Übersichts-Tageswerte beruhen nach diesem Fix auf ortsweise
   verschobenen Fenstern.** Zwei Orte in unterschiedlichen Zeitzonen
   vergleichen künftig fachlich korrekt je ihre eigenen 9-16-Uhr-Werte,
   aber diese sind dann nicht mehr zeitgleich — das ist laut PO-Entscheidung
   E1 gewollt (Vor-Ort-Urlauber denkt in Ortszeit), muss aber im Review
   nicht mit dem alten Verhalten (ein gemeinsames absolutes Fenster)
   verwechselt werden.
3. **Klartext bleibt Prüf-blind.** `email_spec_validator.py` liest nur den
   HTML-Teil (`docs/reference/mail_validators.md`). Ohne eigenständige
   Klartext-Prüfung (AC-3) hätte Scheibe C exakt die Lücke aus #1366
   wiederholt.
4. **Renderer-Commit-Gate #811.** `compare_html.py` und `comparison.py`
   gehören zu den vom Gate erfassten Dateien — Commit ist erst möglich,
   wenn `tests/tdd/test_issue_811_mode_matrix.py` grün ist UND ein
   frischer `briefing_mail_validator.py`-Lauf vorliegt.
5. **open-meteo-Kontingent (#1329).** Der Live-Nachweis auf Staging darf nur
   EINEN Versand auslösen, danach ausschließlich per IMAP auswerten.
6. **Kopfzeilen-Formatierung ist nicht per Regex/String vorgeschrieben.**
   Die ACs verlangen ein erkennbares Zeitzonen-Kürzel/-Offset, aber kein
   festes String-Format — der Adversary-Dialog sollte prüfen, dass die
   gewählte Formatierung für einen Laien tatsächlich erkennbar ist, nicht
   dass ein bestimmter Text exakt vorkommt.
7. **SMS-Testkosten.** Ein realer SMS-Versand kostet Kontingent (Absender
   Callmebot). AC-10 wird ausschließlich deterministisch im Kern getestet —
   die Live-Verifikation dieser Scheibe bleibt strikt auf die E-Mail
   beschränkt, kein SMS-Versand im Testplan.

## Testplan

### Kern-Schicht (deterministisch, echte aufgezeichnete Fixtures)

- Neuer/erweiterter Test für `ComparisonEngine`: Ort mit UTC+2-Zeitzone und
  Tagesfenster 9-16 Uhr liefert die Datenpunkte der Ortszeit-Stunden 9-16,
  nicht der UTC-Stunden 9-16 (Erweiterung von
  `tests/tdd/test_comparison_engine_midnight_window.py` oder neue Datei
  nach Verhalten benannt, z. B. `test_comparison_engine_local_timezone_window.py`
  — NICHT `test_issue_1378_*.py`, Gate `test_naming_gate.py`).
- Neuer Test für `compare_html._render_hour_row`: HTML-Stundenbeschriftung
  entspricht der Ortszeit-Stunde des Datenpunkts, nicht `dp.ts.strftime("%H")`
  auf UTC.
- Neuer Test für `comparison.render_comparison_text`: Klartext-
  Stundenbeschriftung entspricht derselben Ortszeit-Stunde wie der
  HTML-Test oben, für denselben Datenpunkt.
- Neuer Test für `_build_location_outlook_rows`: Ort ohne
  `SavedLocation.timezone`, aber mit Koordinaten, die eine Zeitzone
  ergeben, liefert Ausblick-Zeilen in dieser aufgelösten Zeitzone (nicht
  UTC-Fallback).
- Neuer Test für `_group_by_calendar_day`: ein Datenpunkt zwischen 22:00
  und 23:59 UTC bei einem UTC+2-Ort landet in der Ausblick-Zeile des
  richtigen Ortstages, nicht des UTC-Kalendertages (AC-9).
- Neuer Test für die „Erstellt"-Kopfzeile (HTML + Klartext): Zeitwert
  entspricht der Ortszeit des erstgenannten Ortes (konfigurierte
  Orts-Reihenfolge, nicht alphabetisch) plus erkennbarem Kürzel.
- Neuer Test für den Fallback-Fall (AC-7): nicht auflösbare Koordinaten,
  keine gespeicherte Zeitzone → Anzeige markiert erkennbar UTC.
- Neuer Test für `_sms_location_part` (AC-10): Ort ohne `timezone`-Feld,
  aber mit Koordinaten, plus amtliche Warnung ab orange → `@Stunde`-Teil
  des Warn-Markers erscheint in der aufgelösten Ortszeit. Rein
  deterministisch, kein SMS-Versand.
- Alle neuen Kern-Tests: 100% grün vor Commit (Kern-Schicht-Regel, keine
  "vorbestehend rot"-Ausnahme).

### Live-E2E (Staging, ein Versand, nur E-Mail)

- Ein Versand des bereits genutzten Nachweis-Presets (Innsbruck/Stubai/
  Zillertal, `Europe/Vienna`) über den Einzelversand-Endpoint.
- Zustellung per IMAP abrufen; **beide** Mail-Teile (HTML und Klartext)
  eigenständig gegen eine unabhängige Ortszeit-Referenzabfrage prüfen
  (Muster: Nachweis-Tabelle im Kontext-Dokument).
- Pflicht-Validator `email_spec_validator.py` (Marker `X-GZ-Mail-Type:
  compare`) muss Exit 0 liefern, bevor „E2E bestanden" gesagt werden darf —
  deckt aber laut `docs/reference/mail_validators.md` nur den HTML-Teil ab,
  der Klartext-Teil wird zusätzlich manuell/skriptgestützt geprüft (AC-3).
- **Kein Live-SMS-Versand.** AC-10 (SMS-Warn-Marker) wird ausschließlich im
  deterministischen Kern verifiziert, nicht über einen echten
  Staging-SMS-Versand — reale SMS kosten Kontingent.

## Out of Scope

- **Klartext-Kopfzeile Wochentag englisch** (`comparison.py:173`,
  `strftime('%A')` ohne deutsche Locale) — bereits als Nebenbefund erfasst,
  gehört in Sammel-Issue #1199, nicht in diesen Fix.
- **Trip-seitige `dp.ts.hour`-Filter** in `email/helpers.py:130,1493` — nicht
  Teil dieses Fixes; der Trip-Pfad ist hier nur Vorbild, nicht Änderungsziel.

## Known Limitations

- Die konkrete String-Formatierung des Zeitzonen-Kürzels in der
  „Erstellt"-Kopfzeile ist nicht festgelegt (siehe Risiko 6) — sie muss nur
  erkennbar sein, nicht einem bestimmten Muster folgen.
- Bei einer noch nicht in `timezonefinder` erfassten Koordinate (extrem
  selten, offene See o.ä.) bleibt der UTC-Fallback bestehen (Verhalten von
  `tz_for_coords`, unverändert) — AC-7 verlangt nur, dass dieser Fall
  erkennbar bleibt, nicht dass er vermieden wird.
- Der Compare-SMS-`@Stunde`-Teil entfällt weiterhin ersatzlos (kein
  UTC-Kennzeichen), wenn Koordinaten sich keiner Zeitzone zuordnen lassen —
  das ist die bestehende, budget-getriebene SMS-Konvention (140-Zeichen-
  Limit) und weicht bewusst von der mail-spezifischen AC-7-Pflicht auf ein
  sichtbares Kennzeichen ab; keine neue Einschränkung dieses Fixes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0035 (`docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md`)
  hat bereits entschieden, dass Trip und Ortsvergleich ein gemeinsames
  Tagesfenster-Modell teilen.
- **Rationale:** Dieser Fix führt keine neue Architektur-Entscheidung ein —
  er behebt eine Abweichung zwischen der bereits getroffenen Entscheidung
  (ein geteiltes, ortszeitbasiertes Tagesfenster) und der tatsächlichen
  Compare-Implementierung, die bisher in UTC statt in Ortszeit filterte und
  beschriftete. Trip-seitig (`day_window.py`) war ADR-0035 bereits korrekt
  umgesetzt.

## Changelog

- 2026-07-27: Initial spec created
- 2026-07-27: Korrektur nach Koordinator-Review — Kopfzeilen-Reihenfolge ist
  die konfigurierte Orts-Reihenfolge (nicht alphabetisch, #1359 Scheibe 2);
  Ausblick-Tagesgrenze (`_group_by_calendar_day`) in Scope genommen (neu:
  AC-9); SMS-Compare-`@Stunde`-Marker in Scope genommen (neu: AC-10,
  deterministischer Kern-Test, kein Live-SMS-Versand); Estimated Scope
  entsprechend nachgezogen
