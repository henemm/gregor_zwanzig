---
entity_id: feat_2420_befehle_anzeigen
type: module
created: 2026-10-19
updated: 2026-10-19
status: implemented
version: "1.0"
tags: [befehle, hilfe, email, telegram, premium-sms, ortsvergleich, kanal-paritaet, epic-2506]
---

# Befehle anzeigen: STARTDATUM/REPORT angeboten, Ortsvergleichs-Mail mit Befehlsliste (#2420)

## Approval

- [ ] Approved

## Purpose

Die PO-Frage „Werden alle verfügbaren Befehle angezeigt?" ist nach #2417 an zwei Stellen mit Nein beantwortet: (1) Die Befehlsverarbeitung versteht `STARTDATUM` und `REPORT`, aber Hilfe, E-Mail-Tabelle, Telegram-Menü und Premium-SMS-Kurzhilfe bieten sie nicht an, und per Premium-SMS werden sie als Alleinwort gar nicht erkannt. (2) Die Ortsvergleichs-Mail hat keine Befehlsliste, die Trip-Briefing-Mail hat die Tabelle „Antwort-Kommandos". Diese Spec schließt beide Lücken nach der Epic-Vorgabe #2506: **jeder Kanal beantwortet dieselbe Frage mit demselben Inhalt**, kein Kanal ist nachrangig.

Entscheidungen (PO/Analyse, hier nicht neu aufgeworfen):

- **ABBRUCH** ist kein eigener Befehl, sondern der interne Schlüssel von `STOP`. Er erscheint als Alias in der STOP-Beschreibung, nicht als eigener Eintrag.
- **COLUMNS** wird nicht angeboten (Button-Callback, Spalten gibt es nur im Frontend-Editor).
- **STARTDATUM** und **REPORT** werden mit `kinds=route` angeboten, nachdem der Eingang sie in allen Kanälen als Alleinwort erkennt.
- Die **Ortsvergleichs-Mail** bekommt einen Befehlsblock aus **einem** geteilten Baustein (Parameter `kind`), gefiltert auf `kind="vergleich"` (= Befehle von `_show_help_for_kind("vergleich")`: PAUSE, WEITER, HILFE, KUERZEL), in HTML und Klartext.
- Nur Daten, keine Handlungsempfehlungen. Immer „Trip".

## Source

- **Files:**
  - `src/services/trip_command_processor.py` (`_COMMAND_SPECS`, `_BARE_KEYWORD_MAP`, `command_rows`, `hilfe_kurzform`, `_show_help_for_kind`, `_dispatch_compare`)
  - `src/output/renderers/email/plain.py` (Trip-Klartext-Block, Zeile ~365)
  - `src/output/renderers/email/html.py` (`_render_kommandos_section`, Zeile ~474)
  - `src/output/renderers/email/compare_html.py` (Blockreihenfolge ~1735)
  - `src/output/renderers/comparison.py` (Klartext-Ende ~414)
  - `src/output/channels/telegram.py` (`BOT_COMMANDS`)
  - `frontend/src/lib/i18n/messages/de.json` und `en.json` (`hilfe.befehle.*`)
- **Neu:** `src/output/renderers/email/command_block.py` (geteilter Baustein `render_commands_plain(kind)` / `render_commands_html(kind)`)
- **Identifier:** siehe Implementation Details.

> Schicht-Hinweis: alles im Python-Core (`src/services/`, `src/output/`) plus die statische Hilfeseite im Frontend (nur Textkopie, Drift-Test). Keine Go-Änderung.

## Estimated Scope

- **LoC:** produktiv ca. +130/-25 (Goldens, Tests und `de.json`/`en.json`-Texte zählen laut Regel nicht gegen das 250er-Limit; vorher `workflow.py status` fragen)
- **Files:** 7 produktiv (MODIFY) + 1 produktiv (CREATE `command_block.py`), 2 i18n-Dateien, Goldens neu aufzeichnen, 3 neue Testdateien, 4 bestehende anpassen
- **Effort:** medium. **Risiko:** MITTEL (Compare-Mail-Template ⇒ Renderer-Commit-Gate; STARTDATUM schreibt Persistenz; REPORT löst echten Versand aus)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_COMMAND_SPECS` | Upstream | EINE Quelle des Befehlssatzes; wächst von 13 auf 15 Einträge |
| `bare_keywords()` / `split_link_code` | Upstream | Premium-SMS trennt den Verknüpfungscode über die Alleinwort-Liste; folgt `_BARE_KEYWORD_MAP` automatisch |
| `resolve_command_target` (`trip_selection.py`) | Upstream | `report`/`startdatum` sind weder `ZIELLOS` noch `_BEIDE_KINDS_ONLY` ⇒ gehen in den Trip-only-Zweig (Antwort an Trip, L3 Trip, L4/L5 „kein aktives Ziel"); bleibt unverändert |
| `send_test_report_outcome` + `send_lock` | Upstream | Wiederholungsschutz von REPORT (Frage 1) |
| `tests/tdd/_befehl_e2e_fixtures.py::sms_segments` | Upstream | Messung des SMS-Zeichenbudgets (Frage 2) |
| `test_hilfe_befehle_drift.py`, `test_befehlsangebot_vollstaendig.py`, `test_kommandoliste_einzelquelle.py`, `test_kurzform_befehle_englisch.py` | Downstream | zählen/vergleichen den Befehlssatz, müssen mitwachsen |
| `tests/golden/email/*-plain.txt`, `*-html.txt` | Downstream | Trip-Befehlsblock wächst um 2 Zeilen ⇒ neu aufzeichnen |
| `feat_2417_befehle_e2e_echter_eingang.md` | Vorgänger | Matrix Befehl × Lage gilt unverändert; `startdatum`/`report` sind dort „`_ROUTE_ONLY`" |
| `feat_2282_ortsvergleich_eingangskanaele.md` | Vorgänger | REPORT am Ortsvergleich bleibt Übergangsantwort (S2/S3 offen, #2345 P5) |

## Beantwortung der zwei offenen Fragen

### Frage 1: REPORT per SMS — Wiederholung / Mehrfachversand

Es wird **nichts Neues** erfunden. Der Pfad ist schon geschützt: `_trigger_report` ruft `TripReportSchedulerService.send_test_report_outcome`, das vor dem Versand `try_acquire_send_lock(user_id, trip_id, report_type)` nimmt (`send_lock.py`, Schlüssel enthält immer `user_id`). Verhalten damit:

- **Zweites REPORT während der erste Versand noch läuft** (gleicher Nutzer, gleicher Trip, gleicher Typ): Ergebnis `already_in_progress`, vorhandene Antwort „Morning Report nicht gesendet: ein Versand läuft bereits." (englisch: „… a delivery is already in progress."). Es geht **kein** zweiter Versand raus.
- **REPORT nach Abschluss des ersten Versands:** der Lock ist frei, der Befehl ist eine neue, bewusste Anforderung und versendet erneut. Das ist gewollt: der Nutzer hat wieder REPORT geschickt. Eine zusätzliche Drosselung (Zeitfenster, Tageslimit) wird **nicht** eingeführt.
- `morning` und `evening` sperren sich nicht gegenseitig; zwei Nutzer sperren sich nie (Schlüssel enthält `user_id`).
- Der Lock gilt innerhalb eines Prozesses (dokumentierte Grenze aus #1756; der Python-Core läuft als ein Prozess).
- Die Antwort „Report wird jetzt gesendet" bzw. „… nicht gesendet: <Grund>" kommt über denselben Kanal zurück, über den der Befehl kam (Premium-SMS: englische Kurzform). Der Briefing-Versand selbst geht an die konfigurierten Kanäle des Trips.

Die Spec verlangt dafür nur den **Nachweis über den neuen Eingang** (REPORT als Alleinwort per Premium-SMS führt zum selben Lock-Verhalten), keinen neuen Schutzcode.

### Frage 2: STARTDATUM/REPORT in der Kurzhilfe — Zeichenbudget

Gemessen (`hilfe_kurzform("route")`, GSM-7, `sms_segments` aus #2417): Die Premium-SMS-Kurzhilfe hat heute **402 Zeichen = 3 Segmente** (1 Segment = 160, Mehrteil 153 je Segment ⇒ Grenze 3 Segmente = **459 Zeichen**). Die „160 Zeichen" der Analyse sind überholt: die Kurzhilfe ist seit #2417 mehrteilig, hartes Ziel aus #2417 ist **≤ 3 Segmente**. Verbleibendes Budget: **57 Zeichen** für die zwei neuen Zeilen samt Zeilenumbrüchen. Die Vergleichs-Kurzhilfe (`kind="vergleich"`, 111 Zeichen) bleibt unverändert, weil beide Befehle `kinds=route` haben.

Festlegung (beide Befehle bleiben in der Kurzhilfe, kein Befehl wird weggelassen, kürzer wird die Wirkungsbeschreibung):

| Zeile | Zeichen |
|---|---|
| `STARTDATE date - move start` | 27 |
| `REPORT [evening] - send now` | 27 |
| + 2 Zeilenumbrüche | 2 |
| Summe neu | 56 ⇒ Gesamt **458 ≤ 459** |

Realisiert über `wort_en="startdate"`, `arg_en="date"`, `wirkung_en="move start"` bzw. `wort_en="report"`, `arg_en="[evening]"`, `wirkung_en="send now"`. Die Marge ist 1 Zeichen: Die Messung ist deshalb **Pflicht-Test** (AC-9), und die Spec legt fest, was bei Überschreitung passiert: das Segmentziel (≤ 3) ist verbindlich, der Entwickler kürzt die `wirkung_en` der neuen Einträge weiter (nicht die Befehle, nicht die bestehenden Zeilen). Alle Zeichen bleiben GSM-7 (kein `–`, `→`, Umlaute nur in deutschen Texten, nicht in der Kurzform). Das Datumsformat in der Kurzhilfe heißt bewusst nur `date`; die genaue Form `JJJJ-MM-TT` steht in der Langhilfe (E-Mail, Telegram) und in der Fehlantwort bei fehlendem/ungültigem Datum.

## Implementation Details

```
trip_command_processor.py
  _BARE_KEYWORD_MAP += {"startdatum": "startdatum", "report": "report"}
      (vor dem .update() für wort_en -> startdate/report ergeben sich aus _COMMAND_SPECS)
  _COMMAND_SPECS += _Befehl("startdatum", "startdate", "JJJJ-MM-TT",
        "Startdatum des Trips setzen, alle Etappen verschieben",
        "move start", _ROUTE_ONLY, "date")
                    _Befehl("report", "report", "[morning / evening]",
        "Briefing jetzt senden (Standard: morning)",
        "send now", _ROUTE_ONLY, "[evening]")
  stop-Beschreibung: "Briefings dauerhaft deaktivieren (auch ABBRUCH)"
  command_rows(kind="route") -> filtert auf  kind in s.kinds;
      beim Ortsvergleich PAUSE ohne Dauer (wie _show_help_for_kind, AC-29 #2417)
  _dispatch_compare: Sonderfall "key is None and erstes Wort == report" entfällt
      (report ist jetzt Alleinwort), Verhalten identisch (Übergangsantwort).

command_block.py   (NEU, EIN Baustein, kein Trip-/Compare-Duplikat)
  render_commands_plain(kind) -> "── Antwort-Kommandos ──" + Zeilen aus command_rows(kind)
  render_commands_html(kind)  -> bisheriger Block aus html.py::_render_kommandos_section,
                                 Zeilen aus command_rows(kind)
  Aufrufer: plain.py/html.py (kind="route"), comparison.py/compare_html.py (kind="vergleich")
  Platzierung Compare: direkt NACH Legende/Abo-Hinweis, VOR App-Footer (HTML) bzw. VOR "---" (Klartext)

telegram.py BOT_COMMANDS (Literal bleibt, prod_selftest liest per ast.literal_eval)
  += startdatum, startdate, report (Beschreibungen = Kopie aus _COMMAND_SPECS)

de.json / en.json:  hilfe.befehle.startdatum.{befehl,text}, hilfe.befehle.report.{befehl,text},
                    stop.text nennt ABBRUCH.   Goldens neu aufzeichnen.
```

Nutzerseitig unverändert: `### startdatum: JJJJ-MM-TT` / `### report: morning|evening` (E-Mail), Freitextwort (Telegram), neu Alleinwort per Premium-SMS (`STARTDATUM 2026-10-20`, `REPORT`, `REPORT evening`, englisch `STARTDATE …`). Die Fehlantworten bei fehlendem/ungültigem Datum nennen die kanalneutrale Form `STARTDATUM JJJJ-MM-TT` (nicht mehr nur `### startdatum: …`, die in SMS/Telegram nicht zutrifft).

## Expected Behavior

- **Input:** Befehlsworte `STARTDATUM`, `REPORT` (neu als Alleinwort in allen Kanälen), Antwort-Befehle auf eine Ortsvergleichs-Mail.
- **Output:** Hilfe/Tabelle/Menü/Kurzhilfe führen STARTDATUM und REPORT; Ortsvergleichs-Mail zeigt ihre vier Befehle; Befehle wirken über jeden Kanal.
- **Side effects:** STARTDATUM schreibt die Etappendaten des Trips (Read-Modify-Write über `_speichere`, unverändert). REPORT löst einen echten Briefing-Versand aus (unverändert, durch Send-Lock geschützt).

## Acceptance Criteria

**AC-1:** Given ein Nutzer mit einem aktiven Trip / When er per E-Mail `HILFE` sendet / Then die Antwort listet `STARTDATUM JJJJ-MM-TT` und `REPORT [morning / evening]` mit Beschreibung, und die STOP-Zeile nennt „auch ABBRUCH"; `ABBRUCH` und `COLUMNS` erscheinen nicht als eigene Zeilen.
  - Test: echte Antwort der `HILFE`-Verarbeitung aus dem E-Mail-Eingang (Test-Eingang wie `test_befehle_email_e2e.py`); Zeilen per Wortvergleich, nicht per Dateiinhalt.

**AC-2:** Given ein Nutzer mit einem aktiven Trip / When er in Telegram `hilfe` sendet und das Befehlsmenü (`/`) öffnet / Then Langhilfe und `BOT_COMMANDS` enthalten `startdatum` und `report` (englisch zusätzlich `startdate`), und jeder Menüeintrag erfüllt die Bot-API-Regeln (Name `^[a-z0-9_]{1,32}$`, Beschreibung ≤ 256 Zeichen).
  - Test: `BOT_COMMANDS` gegen `_COMMAND_SPECS` (Vollständigkeit, Wortmenge identisch) plus `hilfe` durch den Telegram-Eingang; `prod_selftest._load_bot_commands()` liest das Literal weiterhin.

**AC-3:** Given ein Nutzer mit Premium-SMS und genau einem aktiven Trip / When er per Premium-SMS `REPORT` oder `REPORT evening` sendet / Then wird der Befehl erkannt (nicht „Unbekannter Befehl"), der Verknüpfungscode wird dabei nicht mit dem Befehl verwechselt, und die Antwort per Premium-SMS meldet in englischer Kurzform „Morning Report is being sent now" bzw. den konkreten Nicht-Versand-Grund.
  - Test: durch den echten Premium-SMS-Eingang (`inbound_sms_reader._verarbeite_befehl`, Muster `test_befehle_premium_sms_e2e.py`) bis zur versendeten Antwort; mit und ohne vorangestellten Verknüpfungscode.

**AC-4:** Given ein Nutzer mit Premium-SMS und einem Trip / When er `STARTDATUM 2026-10-20` (oder englisch `STARTDATE 2026-10-20`) per Premium-SMS sendet / Then verschiebt sich der erste Etappentag auf den 20.10.2026, alle weiteren Etappen um dieselbe Differenz, die Antwort nennt die alten und neuen Daten; ohne Datum oder mit ungültigem Datum bleibt der Trip unverändert und die Antwort nennt die Form `STARTDATUM JJJJ-MM-TT`.
  - Test: Premium-SMS-Eingang, danach Trip neu laden und Etappendaten vergleichen (Schreibweg real, nicht gemockt, Lehre #2387).

**AC-5:** Given die Matrix Befehl × Lage aus #2417 / When `STARTDATUM` oder `REPORT` in Lage L4/L5 (kein Trip, nur Ortsvergleich) per Telegram oder Premium-SMS kommt / Then lautet die Antwort „kein aktives Ziel" und es wird nichts geschrieben oder versendet; in Lage L3 (Trip + Ortsvergleich) wirkt der Befehl am Trip ohne Rückfrage; bei einem vorangestellten Ortsvergleichsnamen antwortet `REPORT` mit der bekannten Übergangsantwort „bitte nutze die Web-App", `STARTDATUM` mit „gibt es beim Ortsvergleich nicht".
  - Test: SOLL_MATRIX aus `_befehl_e2e_fixtures.py` um die Schlüssel `startdatum`/`report` erweitern; Telegram und Premium-SMS laufen durch dieselbe Matrix.

**AC-6:** Given Nutzer A und Nutzer B, beide mit einem Trip und beide Premium-SMS-verknüpft / When A `STARTDATUM 2026-10-20` und `REPORT` sendet / Then ändern sich nur A's Etappendaten und nur A erhält den Versand; B's Etappendaten und Postfach bleiben unberührt, und ein gleichzeitiges `REPORT` von B wird nicht durch A's Lauf als „läuft bereits" abgewiesen.
  - Test: Zwei-Nutzer-Test (CLAUDE.md-Pflicht für datenbewegende Befehle) auf `data/users/<user_id>/` mit zwei Testmandanten; Lock-Schlüssel enthält `user_id`.

**AC-7:** Given ein `REPORT` für einen Trip läuft noch (Lock belegt) / When derselbe Nutzer erneut `REPORT` (gleicher Typ) per Premium-SMS sendet / Then geht kein zweiter Versand raus und die Antwort lautet „Morning Report not sent: a delivery is already in progress."; sobald der erste Versand beendet ist, versendet ein weiteres `REPORT` wieder normal.
  - Test: Lock vorab belegen bzw. Versand blockieren (Zähler am echten Sendeweg), zweites `REPORT` durch den SMS-Eingang, danach Lock freigeben und erneut senden; geprüft wird die Anzahl tatsächlich versendeter Briefings (1 statt 2, dann 2).

**AC-8:** Given ein Trip-Briefing in der E-Mail / When die Mail erzeugt wird (HTML und Klartext) / Then zeigt der Block „Antwort-Kommandos" 15 Zeilen inklusive `STARTDATUM JJJJ-MM-TT` und `REPORT [morning / evening]`, in derselben Reihenfolge wie `_COMMAND_SPECS`, und die STOP-Zeile nennt ABBRUCH.
  - Test: `render_trip_email`/Plain und HTML gegen `command_rows("route")`; aufgezeichnete Goldens neu; `briefing_mail_validator.py` an einer echten Staging-Mail (Exit 0).

**AC-9:** Given die Premium-SMS-Kurzhilfe (`HELP` per Premium-SMS) / When der Nutzer `HELP` sendet / Then enthält die Antwort `STARTDATE date - move start` und `REPORT [evening] - send now`, alle Zeichen sind GSM-7, und die Antwort umfasst höchstens 3 Segmente (≤ 459 Zeichen, erwartet 458); die Vergleichs-Kurzhilfe bleibt bei 111 Zeichen ohne die zwei Zeilen.
  - Test: `sms_segments()` am tatsächlich versendeten Text durch den Eingang; `assert_gsm7_clean`; Obergrenze als harte Zahl, damit ein künftiger Befehl das Budget sichtbar sprengt.

**AC-10:** Given ein Ortsvergleich-Briefing in der HTML-Mail / When die Mail erzeugt wird / Then enthält sie einen Block „Antwort-Kommandos" mit genau den vier Zeilen PAUSE (ohne Dauer), WEITER, HILFE, KUERZEL samt Beschreibung und dem Hinweis „Antworte auf diese E-Mail mit einem Schlüsselwort.", zwischen Abo-Hinweis und App-Fußzeile; `STARTDATUM`, `REPORT`, `HEUTE` u. a. erscheinen dort nicht.
  - Test: `render_compare_html` gegen `command_rows("vergleich")`; Gegenprobe: Zeilenmenge identisch mit der Hilfe-Antwort `_show_help_for_kind("vergleich")`. `email_spec_validator.py` an echter Staging-Mail mit `X-GZ-Mail-Type: compare` (Exit 0).

**AC-11:** Given ein Ortsvergleich-Briefing als Klartext / When die Mail erzeugt wird / Then enthält der Klartext vor der Fußzeile `---` denselben Block „── Antwort-Kommandos ──" mit denselben vier Zeilen wie die HTML-Fassung.
  - Test: `render_compare_text` gegen HTML-Zeilen (gleiche Quelle, gleiche Menge); die Reihenfolge der Blöcke vor `---` ist geprüft.

**AC-12:** Given der Trip-Block und der Ortsvergleichs-Block / When ein Befehl in `_COMMAND_SPECS` ergänzt, entfernt oder umbenannt wird / Then ändert sich der Block in Trip- UND Ortsvergleichs-Mail (HTML und Klartext) gleichzeitig; es gibt genau einen Baustein, den beide Mail-Arten aufrufen (Pendant-Regel).
  - Test: Mutations-Gegenprobe, siehe unten; zusätzlich Test, dass Trip- und Compare-Renderer dieselbe Funktion aus `command_block.py` aufrufen (Verhalten: beide Mails ändern sich, wenn `_COMMAND_SPECS` zur Laufzeit verändert wird).

**AC-13:** Given ein Nutzer, der auf die Ortsvergleichs-Mail antwortet / When er `HILFE`, `PAUSE`, `WEITER` oder `KUERZEL` sendet (E-Mail, `[Ortsvergleichsname]` im Betreff) / Then wirken genau diese vier Befehle wie in der Mail angeboten, und `REPORT`/`STARTDATUM` werden dort weiter mit Übergangs- bzw. Ablehnungsantwort beantwortet (kein Versprechen ohne Wirkung).
  - Test: Antwort-Mail durch den E-Mail-Eingang (`inbound_email_reader._process_single`) für alle vier angebotenen Wörter bis zur versendeten Antwort.

**AC-14:** Given die statische Hilfeseite `/hilfe` und das englische Pendant / When ein Nutzer sie öffnet / Then stehen `STARTDATUM` und `REPORT` mit Befehlsform und Text in `de.json` und `en.json`, und die STOP-Beschreibung nennt ABBRUCH; `tests/test_hilfe_befehle_drift.py` ist grün (keine Kopie weicht von `_COMMAND_SPECS` ab).
  - Test: bestehender Drift-Test (Wort-/Formvergleich, kein Dateiinhalt-Check als Verhaltensnachweis).

**AC-15:** Given alle bestehenden Kanalwege (E-Mail, Telegram, SMS, Premium-SMS) / When der Befehlssatz auf 15 Einträge wächst / Then bleiben alle bisherigen Befehle unverändert erreichbar (`test_befehlsangebot_vollstaendig`, `test_kurzform_befehle_englisch`, `test_premium_sms_kommandopfad`, `test_kommandoliste_einzelquelle` grün, Zähler und Erwartungen auf 15 angepasst).
  - Test: genannte Bestandstests; Zählerstand-Änderung ist Teil der Spec, kein Weglassen von Erwartungen.

## Mutations-Gegenprobe (für den Adversary, per String-Ersetzung mit externer Sicherungskopie)

Leitfrage: Ist die Zusicherung dort geprüft, wo sie WIRKT? Zu verfälschen und zu melden, ob ein Test rot wird:

1. `"report": "report"` / `"startdatum": "startdatum"` aus `_BARE_KEYWORD_MAP` entfernen ⇒ AC-3/AC-4 (Premium-SMS) müssen rot werden, nicht nur der Processor-Test.
2. Eintrag `report` oder `startdatum` aus `_COMMAND_SPECS` streichen ⇒ AC-1, AC-2, AC-8, AC-14 rot (Drift in `BOT_COMMANDS`, `de.json`, Mail).
3. `kinds` von `startdatum`/`report` auf `_BEIDE_KINDS` ändern ⇒ AC-10/AC-11 (Vergleichs-Block) und die Vergleichs-Kurzhilfe müssen rot werden.
4. Compare-Renderer nutzt `kind="route"` statt `"vergleich"` ⇒ AC-10/AC-11/AC-12 rot.
5. Compare-Klartext ruft den Baustein nicht auf (nur HTML) ⇒ AC-11 rot (HTML-/Klartext-Gleichheit).
6. Block im Compare-HTML nur im `body_html`-Tupel entfernt ⇒ AC-10 rot.
7. Send-Lock-Aufruf in `send_test_report_outcome` entfernen ⇒ AC-7 rot (Zahl der Versände 2 statt 1).
8. Lock-Schlüssel ohne `user_id` ⇒ AC-6 rot (Nutzer B wird abgewiesen).
9. `wirkung_en` der neuen Einträge verlängern ⇒ AC-9 rot (> 3 Segmente).
10. `STARTDATUM`-Datumsfehlerweg: Mutation der Datum-Validierung ⇒ AC-4 rot (Trip unverändert nur bei Ablehnung).
11. SOLL_MATRIX ohne `startdatum`/`report`-Schlüssel ⇒ AC-5 darf nicht vakuum-grün werden (Rückdreh-Gegenprobe: Zeile hinzufügen, Test rot, wenn Reader den Befehl falsch klassifiziert).

## Geplante Tests (nach Verhalten benannt)

| Datei | Zweck | ACs |
|---|---|---|
| `tests/tdd/test_befehle_startdatum_report_alleinwort.py` (CREATE) | Eingang je Kanal (Premium-SMS, Telegram, E-Mail), Zwei-Nutzer-Test, Wiederholung mit Lock, Matrix-Lagen | AC-3..7 |
| `tests/tdd/test_befehlsblock_trip_und_vergleich_mail.py` (CREATE) | Befehlsblock Trip + Vergleich, HTML + Klartext, geteilte Quelle, Mutationstest zur Laufzeit | AC-8, AC-10..12 |
| `tests/tdd/test_vergleichs_mail_antwortbefehle.py` (CREATE) | Antwort auf Vergleichs-Mail mit allen vier angebotenen Wörtern | AC-13 |
| `tests/tdd/test_befehlsangebot_vollstaendig.py`, `test_kurzform_befehle_englisch.py`, `test_kommandoliste_einzelquelle.py`, `test_hilfe_befehle_drift.py` (MODIFY) | Zähler 15, Kurzhilfe-Budget (AC-9), Drift-Prüfung | AC-1, 2, 9, 14, 15 |
| `tests/tdd/_befehl_e2e_fixtures.py` (MODIFY) | SOLL_MATRIX-Schlüssel `startdatum`/`report` | AC-5 |
| `tests/golden/email/*` (RE-RECORD) | Trip-Block mit 15 Zeilen | AC-8 |

Kein Mock-Theater: Eingang, Lock, Persistenz und Renderer laufen real; nur Netz-Versand wird am Sendeweg gezählt.

## Renderer-Gate und Staging-Verifikation

- **Renderer-Commit-Gate:** `compare_html.py`, `comparison.py`, `html.py`, `plain.py` sind Mail-Inhalts-Dateien ⇒ Modus-Matrix-Test und Validator müssen vor dem Commit frisch grün sein (`docs/reference/gates_und_ratschen.md`).
- **Compare-Mail:** `uv run python3 .claude/hooks/email_spec_validator.py` an echt zugestellter Staging-Mail (`X-GZ-Mail-Type: compare`, Postfach `gregor-test@henemm.com`). Exit 0 ist Pflicht für „E2E bestanden".
- **Trip-Briefing:** `uv run python3 .claude/hooks/briefing_mail_validator.py` (`X-GZ-Mail-Type: trip-briefing`, `full` und `compact`). Staging-Briefing-Mail nur über Wegwerf-Nutzer `gregor-test+…`.
- Staging-Verifikation je Kanal: `HILFE` per E-Mail/Telegram/Premium-SMS (zweite seven.io-Nummer), `REPORT`/`STARTDATUM` an einem Test-Trip, nie als Sammelversand über alle Trips.

## Known Limitations

- `REPORT` am Ortsvergleich bleibt Übergangsantwort, bis #2282 S2/S3 (#2345 P5) geliefert sind; deshalb dort nicht angeboten.
- Der Send-Lock wirkt nur im Prozess (bekannte Grenze aus #1756).
- Die Kurzhilfe hat 1 Zeichen Marge zum Drei-Segment-Limit; jeder weitere Befehl braucht ein neues Budget (Test macht es sichtbar).
- `COLUMNS` bleibt ein reiner Telegram-Button ohne Befehlswort.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweiterung der bestehenden Einzelquelle `_COMMAND_SPECS` (ADR-konform, #2134) und Anwendung der Trip/Ortsvergleich-Teilungsregel; keine Grundsatzentscheidung wird verändert.

## Changelog

- 2026-10-19: Initial spec created (Epic #2506, Workflow feat-2420-befehle-anzeigen)
