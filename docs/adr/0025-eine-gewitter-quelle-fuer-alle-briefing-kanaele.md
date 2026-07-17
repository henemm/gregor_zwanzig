# ADR-0025: Eine Gewitter-Quelle für alle Briefing-Kanäle — gleiche Rohdaten, gleiche Fensterung, gleiche Skala

- **Status:** Akzeptiert (PO-Freigabe „Go" am 2026-07-16)
- **Datum:** 2026-07-16
- **Bezug:** GitHub-Issue #1275 (zweiter Anlauf), Spec
  `docs/specs/bugfix/fix_1275_sms_thunder_today.md`, Kontext
  `docs/context/fix-1275-sms-thunder-today.md`. Vorgänger-Fix `e08a51c8`
  (`docs/specs/bugfix/fix_1275_sms_th_mismatch.md`), Lessons Learned in
  `docs/project/known_issues.md:26`.

## Kontext

Dieselbe fachliche Aussage — „gibt es auf dieser Etappe ein Gewitter, ab wann, wie stark" —
wird in drei Kanälen ausgegeben und dreimal unabhängig berechnet:

| Kanal | Ort | Rohdaten | Fensterung auf Wanderzeit |
|---|---|---|---|
| E-Mail (Prosa + Stundentabelle) | `email/helpers.py:1350-1367` | `dp.thunder_level` | ja (`trip_report.py:269-275`) |
| E-Mail (**Kopfzeile**, Kompakt-Summary, per Default sichtbar) | `compact_summary.py:332` (`_format_thunder`) | `summary.thunder_level_max` | **nein** — und die Stundenliste darunter fensterte zusätzlich **exklusiv** am Ende. **Vom Adversary gefunden, nicht von der Analyse** — s. Changelog |
| E-Mail (Trend-Block) | `email/helpers.py:759-871` via `render_threshold_peak_value()` | `hourly_thunder` aus dem Trend | ja |
| SMS (`TH:`/`TH+:`) | `sms_trip.py:70-166`, `:221-229` | **keine** — `dp.thunder_level` wird nie gelesen | (Fenster vorhanden, aber ungenutzt für Gewitter) |
| Telegram (Fußzeile) | `narrow.py:164-216` (`_tg_day_footer`) | `agg.thunder_level_max` | **nein** (`weather_metrics.py:596-598` rechnet ungefenstert) |
| Telegram (Übersicht) | `narrow.py:284-326` (`_overview_line`) | `seg_tables`-Rows aus `trip_report.py:_extract_hourly_rows` | ja — **war nie divergent**, s. Changelog |

Das Ergebnis war dreimal derselbe Fehlermodus:

- **#874** — `TH+` aus dem falschen Segment.
- **#1275, erster Anlauf** (`e08a51c8`, 2026-07-16 vormittags) — `TH+` aus der falschen
  Etappe. Behoben, indem `thunder_forecast` aus der Trend-Kette wiederverwendet wird. Die
  Spec dieses Fixes behauptet in AC-2, Telegram konsumiere denselben Pfad — **das war
  faktisch falsch** (`render_telegram_bubbles()`, `narrow.py:359-371`, hat kein solches
  Argument), und kein Test hat es geprüft.
- **#1275, zweiter Anlauf** (dieses ADR) — `TH:` (die berichtete Etappe) hat **gar keine
  Datenanbindung** und liefert strukturell immer `-`; die Stunde in `TH+` ist eine
  hartkodierte `12` (`sms_trip.py:227`).

Der Vorgänger-Fix lief durch Adversary, echte Staging-Testmail und Prod-Selftest — und fand
den Fehler trotzdem nicht. Grund: **Ein Adversary prüft gegen die Spec, nicht gegen die
Wirklichkeit.** Die Spec kannte den `TH:`-Pfad nicht und beschrieb den Telegram-Pfad falsch;
also konnte keine Prüfung sie widerlegen.

Verstärkt wurde das durch die Testlage: Kein einziger Test schickt eine echte
Wetter-Zeitreihe mit gesetztem `dp.thunder_level` durch `format_sms()`. Die Golden-Tests
(`tests/golden/test_sms_golden.py:63-122`) konstruieren `DailyForecast(thunder_hourly=…)`
**direkt** und speisen sie in den Token-Builder — sie überspringen genau die Glue-Schicht,
die defekt ist. Der Snapshot zeigt seit jeher `TH:M@16(H@18)`, die Produktion liefert `TH:-`.
**Grüne Tests über totem Code.**

Die Lehre stand seit dem Vormittag im Repo (`known_issues.md:26`):
> „Wenn mehrere Ausgabekanäle dieselbe fachliche Aussage treffen sollen, aber jeweils eine
> eigene Berechnung dafür haben, divergieren sie garantiert irgendwann."

Sie wurde am selben Tag ein zweites Mal bestätigt — weil sie als Prosa in einem
Known-Issues-Dokument stand und nicht als bindende Regel.

## Entscheidung

1. **Für die Gewitter-Aussage gibt es genau eine Rohdaten-Quelle:** `dp.thunder_level` aus
   `seg.timeseries`. Kein Kanal leitet Gewitter aus einem Aggregat, einem Zwischenformat
   oder einer eigenen Ableitung ab. `agg.thunder_level_max` ist für nutzersichtbare
   Kanal-Ausgaben **nicht** zulässig.
2. **Alle Kanäle fenstern identisch** auf die Wanderzeit der Etappe
   (`start_h <= h <= end_h`, Muster `sms_trip.py:106-110`). Ein Gewitter außerhalb des
   Wanderfensters ist für die Etappen-Aussage irrelevant — in **jedem** Kanal.
3. **Zwei Zahlenskalen existieren bewusst nebeneinander und werden nie vermischt:**
   - `thunder_ordinal()` — `{NONE:0, MED:1, HIGH:2}`, **Sortier-/Vergleichsordnung**
     (`metric_format.py:199-210`).
   - `thunder_label_value()` — `{NONE:0, MED:2, HIGH:3}`, **Render-Skala** für
     `tokens/metrics.LEVELS = {0:'-',1:'L',2:'M',3:'H'}`.

   Beide leben in `metric_format.py`, mit Docstrings, die gegeneinander abgrenzen. Lokale
   Dict-Literale für ThunderLevel (wie `_TH_VAL`, `sms_trip.py:221`) sind verboten.
   `LEVELS` wird **nicht** auf die Ordinalskala umgebaut — das bräche alle Golden-Snapshots
   ohne Sicherheitsgewinn.
4. **Uhrzeiten werden durchgereicht, nie erfunden.** Wenn eine Stunde nicht verfügbar ist,
   wird das Token ohne Stunde gerendert oder ganz weggelassen — aber **niemals** ein
   Platzhalter, der wie eine Vorhersage aussieht. `HourlyValue(12, …)` war genau das.
5. **Beweispflicht liegt beim Produktionspfad.** Ein Test, der eine Zwischenschicht direkt
   füttert und die Glue-Schicht überspringt, gilt **nicht** als Nachweis für eine
   Kanal-Aussage. Für jede nutzersichtbare Gewitter-Aussage muss mindestens ein Test durch
   die echte Einstiegsfunktion des Kanals laufen (`format_sms()`,
   `render_telegram_bubbles()`, `render_email()`) und mit echten Zeitreihen-Daten gespeist
   werden.

## Verworfene Alternativen

- **Nur `TH:` anbinden, Telegram später** — hätte den gemeldeten Fehler behoben und die
  dritte Divergenz (ungefenstertes Telegram) live gelassen, unentdeckt nur deshalb, weil der
  PO bisher SMS mit E-Mail verglich und nicht mit Telegram. Verworfen per PO-Entscheid
  („Ja, Telegram mit rein", 2026-07-16).
- **`LEVELS` auf die Ordinalskala umstellen** (eine Skala statt zwei) — bricht alle
  Golden-Snapshots, ohne einen realen Fehler zu verhindern: `LEVELS` wird ausschließlich vom
  SMS-Pfad gefüttert, und die Fixtures sind bereits auf `{0,2,3}` kalibriert. Zwei sauber
  benannte und dokumentierte Skalen sind billiger als eine erzwungene.
- **E-Mail-Prosa und SMS-Token auf einen gemeinsamen `first_and_peak_level()`-Helper heben** —
  `render_threshold_peak_value()` (`tokens/metrics.py:47-67`) und die Prosa-Schleife
  (`email/helpers.py:1350-1367`) sind **bereits nachweislich derselbe Algorithmus** (Peak
  strikt `>`, frühestes Maximum gewinnt; Threshold erster `>= 1`; `None` übersprungen). Die
  Kanäle divergierten nie im Algorithmus, nur in den Daten. Der Umbau berührte
  gate-geschützten, korrekten E-Mail-Code ohne belegbaren Gewinn → separates
  Hardening-Ticket.
- **Die Lehre erneut nur als Prosa in `known_issues.md` festhalten** — genau das ist am
  2026-07-16 vormittags geschehen und hat denselben Fehler am selben Tag nicht verhindert.

## Konsequenzen

- **Positiv:** Ein Gewitter-Wert, drei Kanäle — SMS, Telegram und E-Mail können sich über
  dieselbe Etappe nicht mehr widersprechen. Die Fensterung ist überall gleich, also
  verschwindet auch die stille Nacht-Gewitter-Divergenz in Telegram. Die Skalen sind benannt
  statt implizit; ein MED wird nie mehr versehentlich als `L` gerendert. Erfundene Uhrzeiten
  sind ausgeschlossen.
- **Negativ / Preis:** `narrow.py` (Telegram) wird angefasst, obwohl der PO dort keinen
  Fehler gemeldet hat — die Divergenz ist real, aber bisher unbemerkt; das Risiko einer
  Regression in einem funktionierenden Kanal wird bewusst in Kauf genommen.
  `sms_trip.py` löst `renderer_mail_gate` aus (`renderer_mail_gate.py:44`): jeder Commit
  braucht `test_issue_811_mode_matrix.py` grün **und** einen erfolgreichen
  `briefing_mail_validator.py`-Lauf gegen eine echte Staging-Testmail. Die Golden-Tests
  bleiben bestehen, testen aber weiterhin nur die Builder-Schicht — ihr blinder Fleck wird
  durch neue Tests kompensiert, nicht beseitigt.
- **Folgepflichten:**
  - Ein neuer Kanal, der Gewitter ausgibt, konsumiert `dp.thunder_level` gefenstert und die
    kanonischen Skalen-Helfer. Eine eigene Ableitung ist ein Review-Befund.
  - Wer eine Kanal-Aussage spezifiziert, prüft **am Aufrufbaum**, welche Renderer den
    beschriebenen Wert tatsächlich bekommen — nicht am Wunschdenken. Die falsche AC-2 des
    Vorgänger-Fixes ist die Referenz, wie es schiefgeht.
  - Ein Test, der die Glue-Schicht überspringt, darf nicht als Nachweis für eine
    Kanal-Aussage zitiert werden (Entscheidung 5).

## Changelog

- **2026-07-16 (initial):** ADR erstellt, mit der Spec zu #1275 vom PO freigegeben.
- **2026-07-17 (Faktenkorrektur, Kontext-Tabelle):** Die Behauptung, `_overview_line`
  (`narrow.py:284-326`) leite Gewitter aus `agg.thunder_level_max` ab, war **falsch** —
  sie stand gleichlautend in Analyse, Kontext-Dokument und dieser ADR und stammte aus dem
  Challenger-Bericht. Tatsächlich liest `_overview_line` die `seg_tables`-Rows
  (`r.get(key)`), die aus `trip_report.py:_extract_hourly_rows` kommen — **bereits
  gefenstert und bereits aus `dp.thunder_level` abgeleitet**. `_thunder_severity()` dient
  dort nur als Komparator zwischen Row-Werten. Verifiziert gegen den unveränderten Stand
  (`git show origin/main:src/output/renderers/narrow.py`). Der Developer-Agent hat den
  Fehler bei der Umsetzung gemeldet, statt die Zeile unnötig umzubauen.
  **Der einzige echte Telegram-Defekt war die Fußzeile** (`_tg_day_footer`, ungefenstertes
  Aggregat) — genau die wurde behoben. Die Entscheidungen 1-5 bleiben unberührt gültig.
- **2026-07-17 (vierter Rechenweg nachgetragen — der Adversary hat den Autor widerlegt):**
  Die Kontext-Tabelle kannte drei Gewitter-Rechenwege. Es waren **vier**: die
  **E-Mail-Kopfzeile** (`compact_summary.py:332`, `_format_thunder`) gated auf
  `summary.thunder_level_max` — dasselbe ungefensterte Aggregat, das Entscheidung 1
  verbietet. `show_compact_summary` steht per Default auf `True` (`models.py:743`),
  verdrahtet in `trip_report.py:124-126`; die Zeile ist Teil **jedes** Trip-Reports.
  Reproduziert: Gewitter nur um 02:00 → SMS `TH:-`, Telegram `⚡ kein`, **Kopfzeile
  `⚡ möglich`**. AC-5 war damit für die E-Mail widerlegt.
  **Wie es passieren konnte:** Der Autor dieser ADR hat `compact_summary.py` nach dem
  **Dateinamen** als „eigener Renderer, out of scope" eingestuft und dafür ein
  Folge-Ticket (#1294) aufgemacht — statt am Aufrufbaum nachzusehen, wer die Funktion
  aufruft. Das ist wörtlich der Verstoß gegen die Folgepflicht dieser ADR
  („prüft **am Aufrufbaum** … nicht am Wunschdenken"), begangen zwei Stunden nach dem
  Schreiben der Regel. Der Adversary hat es gefangen; #1294 wurde als in-scope geschlossen.
  **Zusätzlicher Fund dabei:** `_collect_hourly_data` fensterte **exklusiv** am Etappenende,
  SMS/E-Mail-Tabelle **inklusiv** — die Ankunftsstunde fiel in der Kopfzeile komplett heraus.
  Ein Gewitter um 17:00 am Etappenziel war dort unsichtbar. Behoben per `is_last`-Fensterung
  (Vorbild `email/helpers.py:1439-1452`): stur inklusiv hätte die Grenzstunde zwischen
  Folge-Segmenten doppelt gezählt und den #1146-Fehlermodus wiederbelebt — dieser Widerspruch
  kam vom Developer-Agent und wurde übernommen.
- **2026-07-17 (Präzisierung Entscheidung 3):** Die Formulierung, `_TH_VAL`
  (`sms_trip.py:221`) sei ein „Abweichler", traf nicht zu — die Skala `{NONE:0, MED:2,
  HIGH:3}` war **richtig** für `tokens/metrics.LEVELS`, und der Kommentar dort wies korrekt
  auf die abweichende Wertebedeutung von `thunder_ordinal()` hin. Das Problem war nicht die
  Skala, sondern dass die **richtige Skala nur lokal und unbenannt** existierte — jeder
  Umbau „auf die kanonische Ordnung" hätte MED still zu `L` gemacht. Genau das behebt
  `thunder_label_value()`: dieselben Werte, aber benannt, zentral und mit einem Docstring,
  der gegen `thunder_ordinal()` abgrenzt.
- **2026-07-17 (Vorschau-Pfad nachgerüstet, Fix #1297):** Die Entscheidungen 1-5 galten
  bisher nachweislich nur für den **Versandweg**. `PreviewService.render_sms_preview()`
  berechnete `thunder_forecast`/`multi_day_trend` nirgends und übergab beide als `None`
  an `format_email()` — die SMS-/E-Mail-Vorschau zeigte strukturell immer `TH+:-`,
  unabhängig vom tatsächlichen Wetter, während der Versand für dieselbe Etappe den echten
  Wert trug. Behoben in `src/services/preview_service.py`, indem `_build_report()`
  dieselben `TripReportSchedulerService`-Methoden aufruft wie der Versandweg
  (`_build_stage_trend()`, `_build_thunder_forecast_from_trend_or_fetch()`) — keine
  zweite Berechnung, reines Wiring. Spec: `docs/specs/bugfix/fix_1297_sms_preview_thunder.md`.
  Der Versandweg selbst bleibt unverändert. Damit gilt „eine Gewitter-Quelle" jetzt
  nachweislich für **alle** Aufrufer von `format_email()`/`format_sms()`, nicht nur den
  Scheduler-Versand.
