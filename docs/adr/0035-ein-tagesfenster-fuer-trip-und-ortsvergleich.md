# ADR-0035: Ein Tagesfenster für Trip und Ortsvergleich — wirksam auf Anzeige und Bewertung

- **Status:** Akzeptiert
- **Datum:** 2026-07-25
- **Bezug:** GitHub-Issue #1361 (Befund 1), Epic #1372 (Etappe S1b), Dach #1374,
  Spec `docs/specs/modules/compare_shared_day_window.md`. Nimmt die Festlegung aus
  #1268 für den Ortsvergleich zurück.

## Kontext

Der Ortsvergleich richtet sich an den Vor-Ort-Urlauber: jemand ist bereits in einer
Region und entscheidet kurzfristig, an welchen von mehreren nahen Orten er heute
oder morgen fährt. Für diese Entscheidung zählen die Stunden, in denen er
tatsächlich draußen ist — nicht der Wert um drei Uhr nachts.

Zum Zeitfenster existierten drei Vorstellungen nebeneinander:

1. **Ortsvergleich:** `hour_from`/`hour_to` am Preset — gespeichert, aber
   **wirkungslos**. Beide Aufrufer ersetzten das Fenster hart durch den ganzen Tag
   (`scheduler_dispatch_service.py`, `compare_preview_service.py`), Begründung
   #1268: „Bewertung = ganzer Tag, kein Editor-Feld mehr". Auch die Bedienfläche
   wurde damals entfernt.
2. **Trip:** `report_config.day_window_start_hour/_end_hour`, Voreinstellung 4–19,
   bedient im Versand-Reiter, aufgelöst über `day_window.resolve_configured_window()`
   — ausdrücklich als „eine Quelle für die effektiven Fenster-Grenzen" gebaut
   (Epic #1319 Scheibe B).
3. **Trip-Etappen:** die Etappenzeiten selbst, die über `extract_hourly_rows()` die
   Stundentabelle begrenzen — inklusive Mitternachts-Übergang (Bug #399).

Im Code stand der Grund für die Trennung wörtlich: Die Tagesfenster-Bedienung war
als „nur Route" markiert, mit dem Vermerk „Compare hat sein eigenes". Dieses
„eigene" war der tote Pfad. Der PO meldete das Ergebnis aus Nutzersicht: Das
eingestellte Fenster (9–16 Uhr) hatte in neun gemessenen Mails keinerlei Wirkung,
die Stundentabelle zeigte durchgehend 24 Zeilen.

## Entscheidung

1. **Es gibt ein Tagesfenster**, gemeinsam für Trip und Ortsvergleich: ein Feld,
   ein Auflöser (`resolve_configured_window()`), eine Bedienfläche mit
   `context="route"|"vergleich"`. `hour_from`/`hour_to` entfallen ersatzlos aus
   Bedienung und Auflösung.
2. **Das Fenster wirkt auf beides:** welche Zeilen die Stundentabelle zeigt **und**
   aus welchen Stunden die Werte der Vergleichstabelle berechnet werden
   (Höchst-/Tiefstwerte, Summen, Mittel). Für den Ortsvergleich nimmt das die
   Festlegung „Bewertung = ganzer Tag" aus #1268 zurück.
3. **Die Bedienfläche liegt im Reiter Wetter-Metriken**, nicht im Versand-Reiter.
   Welche Stunden bewertet werden, ist eine Inhaltsfrage; Versand regelt wer, wann
   und über welche Kanäle. Beim Trip zieht die Fläche entsprechend um, der
   gespeicherte Wert bleibt erhalten.
4. **Voreinstellung 4 bis 19 Uhr für beide Seiten** — ein Standard, überall gleich.
5. **Fenster über Mitternacht sind zulässig** (z. B. 22–2 Uhr). Die gemeinsame
   Auflösung akzeptiert sie, statt sie auf den Standard zurückzusetzen; die
   Bedienfläche macht erkennbar, dass das Fenster über Mitternacht geht.

## Verworfene Alternativen

- **Die Einstellung ersatzlos entfernen** (konsequent zu #1268). Verworfen: Der
  Nutzungskontext verlangt sie — die Entscheidung „wohin fahre ich heute" hängt an
  den Stunden, in denen man unterwegs ist. #1361 ist genau diese Meldung.
- **Nur die Stundentabelle kürzen, Bewertung weiter über den ganzen Tag.**
  Verworfen: Dann zeigt die Tabelle den Nachmittag, während die Höchsttemperatur
  darüber aus der Nacht stammt — zwei Wahrheiten in einer Mail.
- **Die Altwerte der Vergleiche übernehmen** (9–16 bzw. 7–22). Verworfen: Das sind
  Reste einer früheren Vorbelegung, kein geäußerter Nutzerwille. Ein gemeinsamer,
  erklärbarer Standard ist ehrlicher.
- **Ein zweites, compare-eigenes Fenster sauber bauen.** Verworfen: Das ist der
  Sonderweg, den dieses Programm gerade abbaut (Invariante „geteilt bauen", #1374).

## Konsequenzen

- **Positiv:** Ein Begriff, ein Feld, ein Auflöser. Die Stundentabelle wird so
  lang, wie der Nutzer sie braucht. Ein Sonderweg des Ortsvergleichs weniger.
  Trip und Vergleich verhalten sich erklärbar gleich.
- **Negativ / Preis:** Bestehende Vergleiche ändern **einmalig** ihre Werte — sie
  rechneten bisher über den ganzen Tag, künftig über 4–19 Uhr. Beim Trip wandert
  eine gewohnte Bedienfläche an eine andere Stelle. Die Freigabe von
  Mitternachts-Fenstern berührt gemeinsamen Code, der bisher solche Paare abwies.
- **Folgepflichten:** Neue Ausgaben (Kanäle, Tabellen) beziehen ihr Zeitfenster aus
  derselben Quelle — kein weiterer Auflöser. Normale Fenster (Start vor Ende)
  müssen sich verhalten wie bisher; die bestehenden Trip-Tagesfenster-Tests sind
  die Regressionsgrenze. Was eine **leere Metrik-Auswahl** bedeutet, ist hiervon
  unberührt und wird gesondert entschieden (Etappe S3, #1366).
- **Konsument Ziel-Segment (#1584):** Das Ziel-Segment einer Etappe
  (`src/services/trip_segments.py::convert_trip_to_segments()`) nutzt seit #1584
  die ortszeit-aufgelöste `day_window_end_hour` statt `arrival_time + 2 Stunden`.
  Damit ziehen die Alarmpfade (`weather_change_detection.py`, `trip_alert.py`)
  und die Aggregation (`segment_weather.py`) denselben Zeitbegriff wie Anzeige
  und Bewertung — die Folgepflicht wird auf diesen Konsumenten angewandt.
  **Grenze:** Tagesfenster über Mitternacht (`start_hour > end_hour`) werden am
  Zielsegment nicht abgebildet; dort greift ein Mindestfenster von einer Stunde
  (PO-Entscheidung 2026-08-08, Spec `docs/specs/modules/fix_1584_alarm_zeitfenster.md`).
- **Randstunden-Semantik (#1599, PO-Entscheidung 2026-08-17):** Die Obergrenze
  `day_window_end_hour` ist **inklusiv** — „bis 19" heißt, die Stunde 19 zählt
  vollständig mit. Zeitlich entspricht das inklusive Stundenband
  `[start_h .. end_h]` dem halboffenen Intervall `[start_h:00, (end_h+1):00)`.
  Genau diese Festlegung fehlte hier bisher, und genau deshalb lief die Kante
  auseinander: die Anzeige las durchgehend inklusiv, die drei Alarm-Stellen
  (`trip_segments.py`, `compare_location_weather_source.py`,
  `compare_official_alert.py`) rechneten exklusiv — ein Gewitter um 19:30
  erschien im Briefing, löste aber keinen Alarm aus. Die Umrechnung
  „Stundenzahl → Zeitgrenze" gehört seither **einmal** nach
  `app/day_window.py::window_end_utc_exclusive()`; die konfigurierten
  Stundenzahlen selbst (`resolve_configured_window()`) bleiben unberührt. Die
  sichtbare Ausgabe bleibt unverändert — dafür sorgt
  `app/day_window.py::display_end_time()`, das die gewonnene Randstunde
  ausschließlich am Ziel-Segment aus der Anzeige heraushält
  (Spec `docs/specs/modules/fix_1599_tagesfenster_randstunde.md`).
