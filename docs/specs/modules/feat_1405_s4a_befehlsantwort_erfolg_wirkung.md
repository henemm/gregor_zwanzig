---
entity_id: feat_1405_s4a_befehlsantwort_erfolg_wirkung
type: module
created: 2026-10-14
updated: 2026-10-14
status: implemented
version: "1.0"
tags: [befehle, antwort, erfolg-heisst-wirkung, waechter, issue-1405, trip-command-processor]
---

<!-- Issue #1405 Scheibe S4a (Wächter 2, "Erfolg heißt Wirkung"), Unterart B für Befehlsantworten.
     Kontext + Analyse (verbindlich): docs/context/feat-1405-s4a-command-result.md
     Vorgänger-Stil: docs/specs/modules/fix_1405_s1_alarm_zustellung.md
     Wächter-Spec: docs/specs/modules/waechter_1405_erfolg_wirkung.md -->

# Befehlsantwort: Erfolg heißt Wirkung — Scheibe S4a

## Approval

- [ ] Approved

## Purpose

Wenn ein Nutzer einen Befehl schickt (zum Beispiel `pause`, `skip`, `heute`, `jetzt`, `strecke`),
bekommt er eine Antwort per E-Mail, SMS, Premium-SMS oder Telegram. Heute kann diese Antwort
etwas behaupten, was nicht stimmt: Sie sagt "pausiert", obwohl das Speichern gescheitert ist; und
wenn im Befehlsablauf ein Programmfehler auftritt, bekommt der Nutzer auf **allen vier Kanälen gar
keine Antwort** (Mail-Leser, SMS-Leser und Telegram-Eingang fangen den Fehler nur im Log ab).
Der interne Statuswert `success` der Befehlsantwort wird in Produktion von **niemandem gelesen**
(gemessen 2026-10-14) — ihn allein umzusetzen ändert für den Nutzer nichts. Diese Scheibe sorgt
deshalb dafür, dass **die Antwort selbst** die Wahrheit sagt, und macht den Status damit
konsistent zur Antwort. Sie repariert die 21 Trip-Funde des Wächters `tests/test_success_status_guard.py`
in `src/services/trip_command_processor.py` (Restliste gesamt vorher: 31 Erfolg + 22 Auflösung;
diese Scheibe nimmt die 21 Funde aus dem Trip-Befehlsprozessor). Gezählt wird je Fundschlüssel, nicht je
Funktion: `_handle_query` trägt vier Schlüssel (`::0–::3`), `_show_strecke` drei — die Klassenzahlen
7 + 11 + 3 sind Schlüssel.

**Alle vier Kanäle sind gleichrangig:** jede Regel unten gilt für E-Mail, SMS, Premium-SMS und
Telegram gleichermaßen (Premium-SMS wird wie SMS über denselben Leser verarbeitet).

## Source

- **Files (Python-Core):**
  `src/services/trip_command_processor.py` (alle produktiven Änderungen),
  `tests/test_success_status_guard.py` (Wächter-Pflege / Ratsche),
  `tests/tdd/test_befehlsantwort_erfolg_heisst_wirkung.py` (NEU, Verhaltenstests),
  bestehende `tests/tdd/test_*` mit Erwartung `success is True` auf Ohne-Daten-Pfaden (gezielt umgestellt),
  `docs/specs/modules/waechter_1405_erfolg_wirkung.md` (Begründung Klasse C, Stand Restliste)
- **Identifier:** `TripCommandProcessor.process`, `CommandResult`, `_speichere` (+ neue Exception
  `_SpeicherFehler`), `_apply_pause`, `_apply_skip`, `_apply_ruhetag`, `_cancel_trip`, `_resume_trip`,
  `_apply_compare_pause`, `_resume_compare`, `_handle_query`, `_handle_drilldown`,
  `_handle_hours_drilldown`, `_handle_metric_drilldown`, `_show_now`, `_show_strecke`,
  `_show_help`, `_show_help_for_kind`, `_show_status`
- **Nicht angefasst:** die Leser `inbound_email_reader.py`, `inbound_sms_reader.py`,
  `inbound_telegram_reader.py`, `api/routers/webhook.py` (Parallelsitzung #2439 ändert den SMS-Leser;
  Abstimmung 2026-10-14). Kein Frontend, keine Go-API-Änderung.

## Estimated Scope

- **LoC:** Quelle +130…180 / −40, Tests ~+200 plus Bestandstests umgestellt. Das überschreitet das
  Standard-Limit von 250 → **`workflow.py set-field loc_limit_override 500`** ist vorgesehen
  (erwarteter Schritt, nicht abspalten: alle 21 Funde gehören in einen Workflow, sonst verrutschen
  die Schlüssel-Nummern `::0..::3` der Ratsche).
- **Files:** 1 produktiv, 2 Test-Dateien (Wächter + neue Datei), ~5 Bestandstests, 1 Wächter-Spec
- **Effort:** high (zentraler Befehlspfad aller vier Kanäle; Risiko MITTEL)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `update_trip` / `save_trip` (`src/app/loader.py`) | Speichern | meldet Fehler per Exception (`LockTimeout`, `LoaderError`, `TripFileCorrupt`, OSError), nicht per Rückgabewert |
| `save_compare_preset_pause`, `resume_compare_preset` (`scheduler_dispatch_service.py:310/:348`) | Speichern Ortsvergleich | liefern `False` bzw. einen Status-Text (`resumed`, `lock_timeout`, nicht pausiert) |
| `RadarNowcastService.get_nowcast`, `backfill_stage_distances` | Wetter / Nowcast | bisher unbewacht — Ausfall wirft |
| `WeatherExtractor.drilldown`, `_fmt_glance/_fmt_gewitter/_fmt_timeline` | Wetterabruf | Prädikat "Daten vorhanden" (`timeline.available`) |
| Mail-/SMS-/Telegram-Leser | Aufrufer von `process()` | verschicken jede Antwort unabhängig von `success` — UNVERÄNDERT |
| `INTENTIONAL_CONSTANT_SUCCESS`, `_APPROVED_EXCEPTIONS`, `KNOWN_VIOLATIONS`, `SPEC_LISTED_FINDINGS` | Wächter-Ratsche | werden im selben Commit nachgezogen |

## Implementation Details

**Zwei ehrlich zulässige Reparaturformen** (aus der gemessenen Scanner-Regel,
`tests/test_success_status_guard.py:576-664`; der Scanner flaggt ein `return` mit konstantem
Erfolgswert, wenn davor ein Nicht-Log-Aufruf steht, außer ein `except`-Handler in derselben
Funktion gibt einen anderen Wert zurück):

- **F1 — Ein-Return mit Prädikat:** EIN `return CommandResult(success=<prädikat>, ...)`, bei dem
  dasselbe Prädikat auch den Text wählt (Ohne-Daten-Text ↔ Daten-Text). Zur Laufzeit nicht konstant.
- **F2 — Divergierender `except`:** ein echter Fehlerpfad im selben Funktionsrumpf, der die
  Fehlerantwort zurückgibt.

**Verboten (Scanner-Gaming, vom Adversary als BROKEN zu werten):**
`p = save_trip(...); success = p is not None` oder `fehler is None` hinter einem Early-Return
(zur Laufzeit konstant, `save_trip` meldet per Exception); Verlagerung der Prüfung in einen Helfer
nur damit der Scanner nichts mehr sieht; Early-Return plus konstantes `True` am Ende; ein Guard,
der nur loggt und weiterläuft. `_is_pure_computation_call` wird **nicht** erweitert (Gate-Code,
würde den Wächter repo-weit lockern).

**1. Zentraler Fang in `process()` (:978).** Neu: `except Exception` um den Handler-Aufruf →
`logger.exception(...)` (Programmfehler bleiben im Log sichtbar) und
`CommandResult(success=False, ...)` mit kurzer Antwort (≤160 Zeichen, DE/EN über `self._t`),
`suppress_email_reply=False`. Der Text darf **nicht** pauschal "bitte erneut senden" sagen —
`skip`, `ruhetag` (nach dem Speichern) und `heute`/`morgen` (Briefing evtl. schon verschickt) sind
nicht wiederholungsfest. Sinngemäß (DE): "Befehl konnte nicht sicher ausgeführt werden. Bitte mit
STATUS prüfen, bevor du ihn erneut sendest." (EN analog). Keine Leser-Änderung nötig, weil alle
drei Wege `process()` aufrufen und dessen Antwort ohnehin verschicken.

**2. Klasse A (7 Funktionen: Speichern).** `_speichere` (:3108) wirft künftig eine eigene Exception
`_SpeicherFehler`, die die bisherige Fehler-Antwort trägt; jeder Handler:
`try: self._speichere(...) except _SpeicherFehler as e: return e.result` (F2). Reihenfolge der
Funktionen unverändert. Ruhetag-Sonderfall: Log-Eintrag/Snapshot-Löschen **nach** erfolgreichem
Speichern in eigenen Schutz stellen — Fehler dort → Warn-Log, Antwort bleibt "Ruhetag gesetzt".
Compare-Pause: Wrapper um `save_compare_preset_pause`, der bei `False` wirft (F2).
`_resume_compare`: `fortgesetzt = (status == "resumed")` wählt Text **und** `success` (F1);
`lock_timeout` bleibt eigener Zweig.

**3. Klasse B (11 Funktionen: Wetterabruf).** Prädikat = genau das, was heute schon den
Ohne-Daten-Text wählt (`timeline.available` bzw. "Tagespunkte vorhanden"; `_traegt_werte` bei den
Metrik-Drilldowns). Ohne-Daten- und Daten-Zweig werden zu **einem** Return zusammengelegt (F1).
Antworttext bleibt unverändert; nur `success` wird konsistent `False`. `_show_now`: `get_nowcast`
in `try/except` (F2) → Antwort "Nowcast nicht verfügbar" statt keiner Antwort. `_show_strecke`:
`backfill_stage_distances` bewachen (F2) und "keine Daten" über F1; liefern **alle** Punkte `None`,
wird nicht mehr "Kein Regen erkannt" behauptet.

**4. Klasse C (3 Funktionen: reiner Text).** `_show_help`, `_show_help_for_kind`, `_show_status`
werden **nicht** repariert, sondern als genehmigte Ausnahmen geführt (siehe AC-18).

**5. Ratschen-Nachzug (im selben Commit wie die Reparatur, Funktionen immer GANZ):**
`KNOWN_VIOLATIONS` (:1587-1699): alle 21 Trip-Schlüssel raus. `SPEC_LISTED_FINDINGS`
(:1851-1871): 10 Trip-Funktionen / 13 Treffer raus; Längenanker (:1946) von `len == 19 and sum == 22`
auf `len == 9 and sum == 9` — `_show_status` fliegt mit raus, Präzedenz: die genehmigten Ausnahmen
`_show_columns_info`/`_show_config` stehen ebenfalls nicht in `SPEC_LISTED_FINDINGS`. `INTENTIONAL_CONSTANT_SUCCESS` (:1736) + `_APPROVED_EXCEPTIONS` (:3411): +3.
Veraltete Docstrings beim Vorbeigehen korrigieren (:1908-1916, :1717-1734).

## Expected Behavior

- **Input:** Befehl eines Nutzers über E-Mail, SMS, Premium-SMS oder Telegram.
- **Output:** Eine Antwort, die zur Wirkung passt: nicht gespeichert → "nicht ausgeführt"; keine
  Daten → "keine Daten"; Programmfehler → kurze Fehlermeldung statt Schweigen.
- **Side effects:** Programmfehler werden weiter protokolliert; Status `success` wird zu
  "Antwort bestätigt die Wirkung" (weiterhin ohne Produktions-Leser, kein neuer Konsument).

## Acceptance Criteria

### A. Zentraler Fang: der Nutzer bekommt immer eine Antwort

- **AC-1:** Given ein Nutzer schickt einen gültigen Befehl (z. B. `pause`), und im Ablauf des Befehls tritt ein unerwarteter Programmfehler auf / When der Befehl verarbeitet wird / Then bekommt der Nutzer auf dem Kanal, über den er geschrieben hat, eine Fehlerantwort statt gar keiner Antwort, und der Status der Antwort ist "nicht erfolgreich" (`success=False`).
  - Test: pro Kanal ein Fall über den echten Eingang — Mail-Leser, SMS-Leser (`sms` UND `premium_sms`), Telegram `_process_update`; ein echter Handler wird per echter Fehlerquelle (z. B. beschädigte Trip-Datei) zum Werfen gebracht, kein `patch()` der Antwort. Es wird geprüft, dass wirklich eine Antwort ausgeliefert wird.

- **AC-2:** Given die Fehlerantwort aus AC-1 / When sie beim Nutzer ankommt / Then ist sie höchstens 160 Zeichen lang (passt in eine SMS und Premium-SMS), ist je nach Spracheinstellung Deutsch oder Englisch, und gilt auf allen vier Kanälen sinngemäß gleich.
  - Test: Länge ≤160 für DE und EN, je Kanal die tatsächlich versendete Nachricht gemessen.

- **AC-3:** Given die Fehlerantwort aus AC-1 / When der Nutzer sie liest / Then rät sie **nicht** pauschal "bitte erneut senden", sondern sagt sinngemäß "Befehl konnte nicht sicher ausgeführt werden. Bitte mit STATUS prüfen, bevor du ihn erneut sendest." (EN: entsprechend) — weil `skip`, `ruhetag` (nach dem Speichern) und `heute`/`morgen` nicht gefahrlos wiederholt werden können.
  - Test: Wortlaut-Prüfung auf "STATUS" und Abwesenheit von "erneut senden" als alleinige Handlung; DE und EN.

- **AC-4:** Given ein Programmfehler wie in AC-1 / When die Fehlerantwort verschickt wird / Then steht der Fehler mit seinem technischen Hergang (Traceback) weiterhin im Protokoll, sodass der Programmfehler nicht verschleiert wird.
  - Test: Log-Aufnahme enthält den Fehler auf Ebene "Fehler mit Traceback"; Antwort an den Nutzer enthält keinen Traceback.

### B. Klasse A: Speichern scheitert — die Antwort meldet es

- **AC-5:** Given ein Trip ist gerade gesperrt (Speichern läuft in einen `LockTimeout`) / When der Nutzer `pause`, `skip`, `ruhetag`, `cancel` oder `resume` schickt / Then meldet die Antwort, dass der Befehl **nicht ausgeführt** wurde (inkl. Hinweis, es erneut zu versuchen), und behauptet **nicht** "pausiert", "übersprungen", "Ruhetag gesetzt", "abgebrochen" bzw. "fortgesetzt"; `success=False`.
  - Test: je Befehl ein Fall über die echten Eingänge aller vier Kanäle (Mail, SMS, Premium-SMS, Telegram) mit echter Sperre auf der Trip-Datei; die Trip-Datei bleibt unverändert.

- **AC-6:** Given das Speichern des Trips scheitert mit einem Lade-/Dateifehler (`LoaderError`) / When der Nutzer `pause`, `skip`, `ruhetag`, `cancel` oder `resume` schickt / Then lautet die Antwort sinngemäß "Nicht gespeichert" (wie bisher bereits für den Fehlerzweig formuliert) und nicht eine Erfolgsmeldung; `success=False`.
  - Test: beschädigte/nicht schreibbare Trip-Datei; je Befehl und Kanal die tatsächliche Antwort geprüft.

- **AC-7:** Given der Befehl `ruhetag` hat den Ruhetag bereits erfolgreich gespeichert, und erst **danach** wirft das Schreiben des Befehls-Logs oder das Löschen des Wetter-Snapshots / When die Antwort entsteht / Then meldet die Antwort den Ruhetag als gesetzt (kein Fehler, kein Hinweis auf Nicht-Ausführung), und im Protokoll steht eine Warnung über den Nebenschaden.
  - Test: Trip-Datei enthält den Ruhetag nach dem Befehl; Antwort sagt "gesetzt"; Log-Aufnahme enthält Warnung. Fehlerquelle ist echt (nicht schreibbares Log-Verzeichnis), kein `patch()` der Antwort.

- **AC-8:** Given ein Ortsvergleich ist gesperrt, sodass `save_compare_preset_pause` scheitert / When der Nutzer den Vergleich pausiert (`pause` auf einem Ortsvergleich) / Then meldet die Antwort "nicht ausgeführt, bitte erneut senden" statt "pausiert"; `success=False`.
  - Test: echter gesperrter Vergleich, alle vier Kanäle.

- **AC-9:** Given ein Ortsvergleich ist **nicht** pausiert / When der Nutzer `resume` darauf schickt / Then lautet die Antwort "ist nicht pausiert" und `success=False`; bei erfolgreich fortgesetztem Vergleich bleibt die Bestätigung und `success=True`; bei `lock_timeout` bleibt der bisherige eigene Antwort-Zweig.
  - Test: drei Zustände (pausiert / nicht pausiert / gesperrt) mit jeweils der erwarteten Antwort.

### C. Klasse B: Wetterabruf liefert nichts — Antwort und Status stimmen überein

- **AC-10:** Given ein Trip ohne gespeicherten Wetter-Snapshot, und der Abruf neuer Daten scheitert / When der Nutzer `heute`, `morgen`, `gewitter`, `timeline` o. ä. (alle Abfrage-Befehle von `_handle_query`) schickt / Then ist der Antworttext unverändert ("Kein Wetter-Snapshot verfügbar") und `success=False`; liefert der Abruf dagegen Daten, bleibt `success=True` mit dem Datentext.
  - Test: je Abfrage-Befehl beide Zustände, über alle vier Kanäle.

- **AC-11:** Given für einen Drilldown-Befehl (Stunden-/Werte-Abruf) liegen keine stündlichen Daten vor (alle Spalten/Werte fehlen) / When der Nutzer ihn schickt (`_handle_drilldown`, `_handle_hours_drilldown`, `_handle_metric_drilldown`) / Then lautet die Antwort unverändert "Keine stündlichen Daten" (bzw. der bisherige Ohne-Werte-Text), `success=False`; liegen Daten vor, `success=True`.
  - Test: je Drilldown beide Zustände, je Kanal.

- **AC-12:** Given der Nowcast (Regenradar-Kurzfrist) ist ausgefallen und die Abfrage wirft / When der Nutzer `jetzt` schickt (`_show_now`) / Then bekommt er die Antwort "Nowcast nicht verfügbar" statt gar keiner Antwort; `success=False`.
  - Test: echte Nowcast-Quelle ausgefallen (Fake-Server verweigert); Antwort kommt auf allen vier Kanälen an.

- **AC-13:** Given der Nowcast liefert für **alle** Punkte des Befehls `strecke` keinen Wert (alle Punkte leer, inkl. Startpunkt; auch bei nur einem Punkt) / When der Nutzer `strecke` schickt (`_show_strecke`) / Then lautet die Antwort "Nowcast nicht verfügbar" und **nicht** "Kein Regen erkannt" — fehlende Daten dürfen nicht als gutes Wetter gelesen werden; `success=False`.
  - Test: alle Punkte `None` → Antwort enthält "nicht verfügbar", enthält nicht "Kein Regen"; Gegenprobe: mindestens ein echter Wert 0 mm → "Kein Regen erkannt" bleibt korrekt. Verdacht stiller Ersatz wird in `/40` zuerst per Test reproduziert (rot vor Fix).

- **AC-14:** Given `backfill_stage_distances` (Streckenlängen nachtragen) scheitert bei `strecke` / When der Nutzer `strecke` schickt / Then bekommt er die Antwort "Nowcast nicht verfügbar" (bzw. gleichwertige Fehlerantwort) statt keiner Antwort; `success=False`.
  - Test: echter Fehler beim Nachtragen; Antwort kommt an, je Kanal.

### D. Klasse C: genehmigte Ausnahmen

- **AC-15:** Given die Befehle `hilfe`/`help`, die Hilfe zu einer Metrik-Art (`_show_help_for_kind`) und `status` (`_show_status`) / When der Nutzer sie schickt / Then antworten sie wie bisher mit Text aus der Trip-Konfiguration (kein Wetterabruf, kein Schreiben), und ihr Status ist `success=True` — **begründet** als genehmigte Ausnahmen im Wächter: es gibt keinen Fehlerausgang, den `success` abbilden könnte (Präzedenz `_show_columns_info`, `_show_config`). `_show_status` nutzt nur das Tagesdatum und die Etappenliste.
  - Test: Antworten aller drei Befehle über die echten Eingänge unverändert; `INTENTIONAL_CONSTANT_SUCCESS` und `_APPROVED_EXCEPTIONS` enthalten genau diese drei Funktionen mit Begründung (Ausnahmeliste wächst von 3 auf 6, genau +3).

### E. Wächter-Ratsche (kein Scanner-Gaming)

- **AC-16:** Given der Wächter `tests/test_success_status_guard.py` / When die Scheibe fertig ist / Then sind alle 21 Trip-Schlüssel aus `KNOWN_VIOLATIONS` entfernt (Liste schrumpft um 21), aus `SPEC_LISTED_FINDINGS` sind alle 10 Trip-Funktionen (13 Treffer, inkl. `_show_status`) entfernt und der Längenanker steht auf `len == 9 and sum == 9`, und `test_known_violations_only_shrink` sowie `test_scanner_finds_every_spec_listed_finding` sind grün.
  - Test: Wächter-Testdatei komplett grün; Abgleich der Zahlen mit dem tatsächlichen Scannerbefund.

- **AC-17:** Given die Reparaturen der Klassen A und B / When der Adversary sie prüft / Then nutzt keine Funktion eine der verbotenen Formen (`success = x is not None` / `fehler is None` hinter einem Early-Return, Early-Return plus konstantes `True` am Ende, nur loggender Guard, Verlagerung in einen Helfer nur zur Scanner-Umgehung), und `_is_pure_computation_call` ist unverändert.
  - Test: Mutations-Gegenprobe (AC-19) beweist, dass die Prüfung an der Antwort wirkt; Diff-Prüfung auf `_is_pure_computation_call`.

- **AC-18:** Given die Ausnahmeliste (`_APPROVED_EXCEPTIONS`) / When die Scheibe fertig ist / Then ist sie genau um die drei Klasse-C-Funktionen gewachsen (Sperre `test_intentional_exception_list_cannot_grow` bleibt als Spec-Entscheidung belegt durch diese Spec), und keine weitere Funktion wurde zusätzlich als Ausnahme eingetragen.
  - Test: Differenz der Ausnahmeliste gegenüber `origin/main` = genau diese drei Namen.

### F. Mutations-Gegenprobe und Tests über die echten Eingänge

- **AC-19:** Given die Verhaltenstests dieser Scheibe / When der Adversary die Implementierung gezielt verfälscht (a) den zentralen Fang in `process()` entfernt, (b) je Klasse-A/B-Funktion zurück auf konstantes `success=True` dreht, (c) einen der Texte der Fehler-/Nicht-verfügbar-Antworten wieder durch die alte Erfolgs-/"Kein Regen"-Behauptung ersetzt / Then wird je Verfälschung mindestens ein **Verhaltenstest** rot, der an der ankommenden Antwort misst (nicht nur der Wächter-Scanner).
  - Test: Mutationen per String-Ersetzung mit externer Sicherungskopie (nie `git checkout/stash/reset`); gemeldet wird, welcher Test rot wurde; wird keiner rot, ist das ein Finding.

- **AC-20:** Given die neuen Verhaltenstests / When sie ausgeführt werden / Then laufen sie durch die **echten Eingänge** aller vier Kanäle (Mail-Leser, SMS-Leser mit `sms` und `premium_sms`, Telegram `_process_update`) und prüfen, dass eine Antwort **rausgeht** und den richtigen Inhalt trägt — nicht nur den Rückgabewert von `process()`.
  - Test: `tests/tdd/test_befehlsantwort_erfolg_heisst_wirkung.py`; Kernschicht ohne Netz (Fake-Server/aufgezeichnete Daten); uhrzeitabhängige Befehle (Briefing-Sperre #1594) außerhalb des Fensters gemessen.

- **AC-21:** Given bestehende Tests, die auf Ohne-Daten-Pfaden bisher `success is True` erwarten (Kandidaten u. a. `test_issue_651_telegram_query_glance.py`, `test_issue_704_telegram_interactive_navigation.py`, `test_timeline_tagesgenaue_quellen.py`, `test_feature_656_radar_nowcast.py`, `test_stundenabruf_teilluecken.py`) / When die Scheibe fertig ist / Then sind genau diese Erwartungen **bewusst** auf `False` umgestellt (Erwartungsänderung, in dieser Spec benannt), und Tests mit `pytest.raises` gegen `process(` sind geprüft und angepasst, weil der zentrale Fang das Verhalten bewusst ändert.
  - Test: Liste der umgestellten Tests im Commit dokumentiert; keine stille Anpassung, kein anderer Test verändert.

## Bewusste Erwartungsänderungen (Alt-Tests)

Bestehende Tests, die auf Ohne-Daten-Pfaden (kein Snapshot / keine stündlichen Daten) `success is True`
erwarten, werden ausdrücklich auf `success is False` geändert. Antworttexte bleiben unverändert.
Tests mit `pytest.raises` gegen `process(` müssen auf das neue Verhalten ("Fehlerantwort statt
Exception") umgestellt werden. Die genaue Liste wird in `/40` per Suche ermittelt und im Commit genannt.

## Known Limitations

- `CommandResult.success` hat weiterhin **keinen Produktions-Leser**. Diese Scheibe liefert
  "Status konsistent zur Antwort" und die zentrale Fehlerantwort als Nutzerwert; ein neuer Konsument
  (z. B. Reader-Statistik) ist nicht Teil der Scheibe.
- Reader (Mail/SMS/Telegram) bleiben unverändert — die Parallelsitzung #2439 ändert `inbound_sms_reader.py`.
  Sollte S4a doch einen Leser anfassen müssen, vorher per `SendMessage` Bescheid geben.
- Die übrigen 53 Funde der Restliste außerhalb des Trip-Befehlsprozessors gehören nicht zu S4a.
- `_show_status` prüft nur über `date.today()` bzw. Etappenliste (Wächter-Spec "Offene Punkte" 3) —
  risiko-blinde Klasse-1-Signatur bleibt dort offen und ist hier als Ausnahme geführt.

## Risiken

- **Mittel:** zentraler Befehlspfad aller vier Kanäle; der Wortlaut der Fehlerantwort muss in 160
  Zeichen passen und darf keinen Wiederholungs-Fehler provozieren (Idempotenz, AC-3).
- Viele Bestandstests betroffen (AC-21); Schlüssel `::0..::3` verrutschen, wenn eine Funktion nur
  teilweise repariert wird → Funktionen immer ganz.
- Staging-Gate: Kommando-Pfad ist live-relevant — Staging-Verifikation braucht den Telegram-Live-Test
  und einen echten Mail-Eingang (Wegwerf-Nutzer `gregor-test+…`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reparatur-Scheibe innerhalb der bestehenden Wächter-Entscheidung „Erfolg heißt Wirkung"
  (#1405). Keine Entscheidungsfläche berührt (Kanäle, Provider, Datenmodell, Auth, Editor, Test-/Deploy-
  Strategie bleiben unverändert); die Ausnahmeliste wächst nach bestehender Präzedenz
  (`_show_columns_info`/`_show_config`).

## Changelog

- 2026-10-14: v1.0 — erste Fassung (spec-writer), Grundlage `docs/context/feat-1405-s4a-command-result.md`.
