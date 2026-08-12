---
entity_id: fix_1744_alarm_format_angleichen
type: module
created: 2026-08-12
updated: 2026-08-12
status: partial
version: "1.2"
tags: [alerts, renderer, email, subject]
---

> **Liefer-Stand 2026-08-12:** Scheibe **A1** (AC-1 bis AC-7) ist ausgeliefert und live —
> PR #1781, Merge `942fc778`, in Produktion über `0861a9a8`. Adversary VERIFIED nach vier
> Runden (drei Findings behoben), Staging VERIFIED 7/7 an echt zugestellten Mails.
> Scheibe **A2** (AC-8 bis AC-14, Mail-Körper) ist **offen**. #1744 bleibt deshalb offen.
>
> **Nachtrag 2026-08-12 (Version 1.2), aus der Vermessung vor A2:** Drei Präzisierungen —
> (1) die amtliche Warn-Mail hat **keinen eigenen Klartext-Teil**, er wird aus dem HTML
> gestrippt; sie bekommt einen (PO-Entscheid, AC-13). (2) AC-11 nannte die falsche Testdatei,
> korrigiert. (3) Der Warn-Mail-Wächter prüft **CSS-Klassen** und lehnt den Umbau sonst ab —
> AC-14 neu. A1-ACs unverändert.

# Alarm-Format angleichen: eine Ortssprache für alle Trip-Alarme (#1744 Scheibe A)

## Approval

- [x] Approved — PO-Freigabe 2026-08-12 („go"), ACs auf Deutsch vorgelegt

## Purpose

Zwei Alarm-Mails zum selben Ereignis nennen den Ort heute in zwei verschiedenen Sprachen
(`km 8–8` gegen `🏁 Ziel`) und sind auch im Aufbau kaum als verwandt zu erkennen. Diese Spec
gibt allen Trip-Alarmen **eine** Ortssprache — die Segment-Kennung — und **einen** Mail-Aufbau.

Nicht Gegenstand: die quellenübergreifende Entdopplung mehrerer Alarme zum selben Ereignis
(Scheibe B, gebucht an #1467 S4).

## Source

- **Datei:** `src/output/renderers/alert/render.py`, `src/output/renderers/alert/official_alerts.py`,
  `src/output/renderers/alert/model.py`, `src/output/renderers/alert/project.py`
- **Identifier:** `_km_str`, `_km_str_onset`, **`_km_str_events`**, `render_subject`,
  `format_segment_reference`, `AlertEvent`, `OnsetEvent`, `to_alert_message`

🔴 **Es sind DREI km-Bauer, nicht zwei** (in der RED-Phase 2026-08-12 nachgemessen):
`_km_str` (`render.py:100-107`), `_km_str_onset` (`render.py:110-111`) und
**`_km_str_events` (`render.py:386-388`)**. Der dritte speist die Zeile „Wo & wann" der
Abweichungsmail (`render.py:379`) — also genau die Stelle, die AC-6 regelt. Wer nur die beiden
erstgenannten umstellt, lässt AC-6 rot. (Ein vierter, `_corridor_when` bei `render.py:117-121`,
gehört zum toten Korridor-Pfad und bleibt außen vor.)

Schicht: **Python-Core** (Renderer + Projektion). Keine Go-Änderung, keine Frontend-Änderung.

## Estimated Scope

Zwei Liefer-Scheiben, ein gemeinsames Zielbild.

| Scheibe | Inhalt | LoC (Produktiv) | Dateien |
|---|---|---|---|
| **A1** | Ortsangabe + Betreff | ~90 | 6 |
| **A2** | Mail-Körper (HTML + Klartext) | ~170 | 4 |

- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `format_segment_reference` | Funktion | bestehende Ortsformatierung der amtlichen Warnung — wird zur gemeinsamen |
| `TripSegment.segment_id` | Feld | Quelle der Kennung (`1..N` oder `"Ziel"`) |
| ADR-0033 | Entscheidung | Warn-Karte nennt nur betroffenen Umfang — bleibt inhaltlich bindend |
| `warnmail_official_alert_display.md` AC-3 | Spec | ehrliche Sammelangabe bei gemischtem Umfang — bleibt bindend |
| PO-Entscheid 2026-08-04 (#1467 S2 AG3b) | Entscheidung | Kurznachrichten nennen keinen Ort — bleibt bindend |

## Implementation Details

### Woher die Segment-Kennung kommt

Sie ist an beiden Stellen bereits zur Hand und wird nur nicht weitergereicht:

```
Abweichungsalarm: project.py:88   match = _find_segment(segments, ch.segment_id)
                                  → heute nur match.segment.start_point.distance_from_start_km
                                  → künftig zusätzlich match.segment.segment_id

Nowcast:          trip_alert.py:1098  active.start_point.distance_from_start_km
                                  → künftig zusätzlich active.segment_id
                                  → über RadarAlertRequest nach notification_service.py:1234
```

### Eine Formatierung, zwei Aufrufer

`format_segment_reference()` (heute `official_alerts.py:262-289`) zieht in ein eigenes Modul um
und wird von **beiden** Renderern importiert. Weder `render.py` noch `official_alerts.py`
importieren einander heute — der Umzug ist zyklenfrei.

Auflösungsreihenfolge der Ortsangabe (eine Funktion, alle Alarmarten):

```
1. location_label gesetzt      → Ortsname               (Ortsvergleich, unverändert)
2. Segment-Kennung vorhanden   → format_segment_reference()
3. sonst                       → km {von}–{bis}          (Rückfall, z.B. Altdaten)
```

### Gemeinsamer Mail-Aufbau (A2)

Beide Mailtypen folgen derselben Reihenfolge. Typ-eigene Bausteine sitzen an **festen**
Positionen, statt den Aufbau zu verdoppeln:

```
Kennzeichen (Alarmart)          beide
Überschrift (Kernaussage)       beide
Warnstufen-Skala                nur amtliche Warnung
Datenzeilen                     beide   ← hier gleicht sich die amtliche Warnung an
Sperrzeit-Hinweis               nur Nowcast
Stand-Zeile                     beide
Herkunfts-Fußzeile              beide
```

Die Warnstufen-Skala (GELB · ORANGE · ROT mit „niedrigste von drei") bleibt als **Skala**
erhalten und wandert nicht in eine Textzeile: sie trägt eine Einordnung, die eine bloße
Wortangabe verliert. Alles Übrige der amtlichen Warnung (Gefahrenart, Gültigkeitsfenster,
Ortsbezug, Quelle) wird zu Datenzeilen im Aufbau des Nowcasts.

### Was A2 vorfindet (vermessen 2026-08-12, `docs/context/fix-1744-a2-alarm-mailkoerper.md`)

Zwei Bauformen für dieselbe Sache:

- **Nowcast:** je Datenzeile eine `<table role="presentation">`, Label links, Wert rechtsbündig
  — `_datarow_html`, `render.py:403-417`. Die Tabellenform ist Absicht (Outlook), nicht Zufall.
- **Amtliche Warnung:** ein CSS-Grid-`<div class="warn">` mit einem einzigen Facts-Block, in dem
  Label und Wert als `<span class="k">Gültig:</span> … <br>` inline stehen —
  `official_alerts.py:1107-1132,1143-1177`.

Ein Baustein steht **zusätzlich** im Ist-Zustand und fehlt in der Zielreihenfolge oben: die
**Quelle-Box** (`_standalone_src_html`, `official_alerts.py:1285-1315`). Sie wird zur Datenzeile
„Quelle" — mit der Randbedingung aus AC-14.

### 🔴 Der Klartext der amtlichen Warn-Mail (PO-Entscheid 2026-08-12)

Die amtliche Warn-Mail hat **keinen bewusst gebauten Klartext-Teil**:
`send_official_alert` ruft `EmailOutput.send(...)` ohne `plain_text_body`
(`notification_service.py:859-861`), woraufhin `output/channels/email.py:350-358` den Text per
Regex aus dem HTML strippt — aus einem CSS-Grid wird dabei Zeilensalat. Der Nowcast dagegen baut
`html` und `plain` in derselben Funktion aus denselben Label-Wert-Tupeln und übergibt den
Klartext ausdrücklich (`notification_service.py:1322,1400-1405`).

**Entscheid:** A2 schließt diese Lücke mit (AC-13). Begründung: Die Label-Wert-Zeilen entstehen
für das HTML ohnehin neu; der Klartext fällt aus denselben Tupeln ab. Ihn später nachzuziehen
hieße, dieselbe Struktur ein zweites Mal aufzubrechen.

`render_official_alert_notice_plain` (`official_alerts.py:615-662`) ist **nicht** dieser
Klartext — sie bedient den in eine andere Mail eingebetteten Warnblock und bleibt unangetastet.

### 🔴 Der Wächter prüft CSS-Klassen, nicht nur Text

`.claude/hooks/official_alert_mail_validator.py` verlangt in S-1 (`:73`, `:160-165`) die Klassen
`{"verdict", "warn", "src", "body-foot"}` im HTML-Körper. **`src` ist die Quelle-Box** — wird sie
zur Datenzeile, lehnt der Wächter eine sachlich korrekte Mail ab. Ebenso zählt S-2 (`:74-76`,
`:167-174`) genau zwei erlaubte Skalen-Darstellungen auf (`stufe-line` bzw. `stacked`/`meter`).

Das ist dieselbe Falle wie in A1 (`_SEGMENT_RE` kannte `🏁 Ziel` nicht): Ein Wächter, der gültige
Formen aufzählt, lehnt jede neue ab. Behandlung wie damals — **additiv erweitern, nie lockern**
(AC-14). Pflicht-Literale, die im Text überleben müssen: `"Quelle:"`, `"abgerufen bei"`
(P-4 `:203-207`), `"Stand: heute"` (P-5 `:209-210`), Wochentag+Datum in der „Gültig:"-Zeile
(P-3 `:62-69,188-201`).

Am Commit verlangt `renderer_mail_gate.py` **zwei** frische Validator-Nachweise, weil A2 beide
Renderer anfasst: `*_radar_alert_validation.yaml` **und** `*_official_alert_validation.yaml`.

### Architektur-Entscheidung

Der geänderte Aufbau wird in **ADR-0052** festgehalten (nächste freie Nummer; höchste vergebene
ist ADR-0051). Es verweist auf **ADR-0033** als weiterhin bindend — geändert wird nur der Träger
der Zusicherung, nicht die Zusicherung.

## Expected Behavior

- **Input:** Trip-Alarme aller Arten (Abweichung, Nowcast, amtliche Warnung), Ortsvergleich-Alarme.
- **Output:** Betreff, E-Mail (HTML + Text) und Telegram-Langform nennen den Ort in derselben
  Sprache; beide Mailtypen haben denselben Aufbau.
- **Side effects:** keine. Reine Darstellungs- und Projektionsänderung, keine Auslöselogik,
  keine Persistenz, kein Kanal-Routing.

## Acceptance Criteria

### Scheibe A1 — Ortsangabe und Betreff

- **AC-1:** Given ein Trip-Nowcast-Alarm für das Ziel-Segment / When die Alarm-Mail versendet
  wird / Then nennt die Betreffzeile `🏁 Ziel` statt `km 8–8`, und der Betreff einer amtlichen
  Warnung für dasselbe Segment nennt denselben Text — die beiden Mails sind als derselbe Ort
  erkennbar.
  - Test: beide Mails für denselben Trip und dasselbe Segment rendern und die Ortsangabe der
    beiden Betreffzeilen auf Gleichheit prüfen. Der Test muss rot werden, wenn nur einer der
    beiden Pfade umgestellt ist.

- **AC-2:** Given ein Trip-Abweichungsalarm, der die Segmente 3, 4 und 5 betrifft / When der
  Betreff gerendert wird / Then steht dort `Segment 3–5` — dieselbe Zusammenfassung, die eine
  amtliche Warnung über dieselben drei Segmente erzeugt.
  - Test: Abweichungsalarm über drei zusammenhängende Segmente rendern und mit der Ausgabe der
    amtlichen Warnung über dieselben Segment-Kennungen vergleichen.

- **AC-3:** Given irgendein Trip-Alarm mit Ortsangabe / When die Ortsangabe gebildet wird /
  Then geschieht das über **genau eine** Funktion: eine Verfälschung dieser Funktion (z.B.
  `Segment` → `Etappe`) muss den Nowcast-Test, den Abweichungstest UND den Test der amtlichen
  Warnung gleichzeitig rot machen.
  - Test: Mutations-Gegenprobe. Bleibt einer der drei grün, existiert noch eine zweite
    Formatierung — das ist ein Verstoß gegen die Teilungsregel.

- **AC-4:** Given ein Alarm im Ortsvergleich (ein Ort oder mehrere) / When Betreff, Mail und
  Telegram gerendert werden / Then erscheinen weiterhin die Ortsnamen, unverändert zu heute —
  die Segment-Kennung greift dort nicht.
  - Test: die bestehenden Golden-Vergleiche des Ortsvergleichs laufen unverändert grün
    (`tests/tdd/test_issue_1169_compare_alert_consumer.py`).

- **AC-5:** Given ein Trip-Abweichungs- oder Nowcast-Alarm / When die Kurznachricht (SMS und
  Premium-SMS) über `render_sms` gerendert wird / Then nennt sie weiterhin **keinen** Ortsbezug
  und bleibt innerhalb von 140 Zeichen — der PO-Entscheid vom 2026-08-04 bleibt unangetastet.
  - Test: Kurznachricht für einen Trip-Alarm mit Ziel-Segment rendern; sie darf weder `Ziel`
    noch `Segment` enthalten, und ihre Länge bleibt ≤ 140.
  - **Abgrenzung (in der RED-Phase gemessen):** Die Kurznachricht der **amtlichen Warnung** ist
    davon NICHT betroffen — sie trägt seit jeher einen eigenen Kurz-Ortsbezug
    (`render_official_alert_sms` → `sms_scope`, `official_alerts.py:1960-1967`), gemessene
    Ist-Ausgabe `KHW403 AMT GELB1/3: TH Mi14-22, nur Ziel`. Das ist Bestand aus #1318 und in
    `sms_official_alert_tokens.md` geregelt. AC-5 gilt ausschließlich für `render_sms`; wer den
    amtlichen SMS-Pfad „mit angleicht", bricht eine andere Spec.

- **AC-6:** Given eine Alarm-Mail mit Ortsangabe im Betreff / When der Mail-Körper gerendert
  wird / Then nennt die Zeile „Wo & wann" **denselben** Ortstext wie der Betreff — innerhalb
  einer Mail gibt es keine zwei Ortssprachen mehr.
  - Test: Betreff und Datenzeile derselben gerenderten Mail gegeneinander prüfen.

- **AC-7:** Given ein Trip-Alarm, dessen Etappe keine Segment-Kennung trägt (Altdaten) / When
  die Ortsangabe gebildet wird / Then fällt sie auf die km-Spanne zurück, statt leer zu bleiben
  oder den Versand abzubrechen.
  - Test: Alarm ohne Segment-Kennung rendern; Ortsangabe ist nicht leer und der Versand läuft.

### Scheibe A2 — Mail-Körper

- **AC-8:** Given je eine Nowcast-Mail und eine amtliche Warn-Mail / When beide gerendert werden /
  Then haben sie dieselbe Reihenfolge der Bausteine (Kennzeichen, Überschrift, Datenzeilen,
  Stand-Zeile, Fußzeile), und die Fakten der amtlichen Warnung stehen in Datenzeilen derselben
  Bauform wie beim Nowcast.
  - Test: beide Mails rendern und die Abfolge der Bausteine vergleichen.

- **AC-9:** Given eine amtliche Warnung der Stufe GELB / When die Mail gerendert wird / Then ist
  die Warnstufe weiterhin als **Skala** erkennbar (GELB · ORANGE · ROT mit der Einordnung
  „niedrigste von drei") und nicht auf ein einzelnes Wort reduziert.
  - Test: gerenderte Mail enthält alle drei Stufenbezeichnungen und die Einordnung.

- **AC-10:** Given eine amtliche Warnung im neuen Aufbau / When die Mail gerendert wird / Then
  enthält sie unverändert Gefahrenart, Gültigkeitsfenster, Ortsbezug und Quelle — durch den
  Umbau geht keine Information verloren.
  - Test: jede Angabe der heutigen Mail einzeln im neuen Aufbau nachweisen.

- **AC-11:** Given ein Trip mit 63 Segmenten und einer Warnung für 1 Segment / When die Mail
  gerendert wird / Then erscheinen weiterhin **keine** nicht betroffenen Segmente — ADR-0033
  bleibt gewahrt.
  - Test: der bestehende ADR-0033-Test bleibt grün —
    `tests/tdd/test_official_alert_warn_section.py::test_ac11_trip_path_shows_only_affected_segment_chips`
    (`:332-361`, zitiert ADR-0033 wörtlich).
  - 🔴 **Korrektur 2026-08-12:** Hier stand `tests/tdd/test_official_alert_template_render.py`.
    Nachgemessen: Diese Datei legt zwar `free_chips`-Fixtures an, prüft die ADR-0033-Zusicherung
    aber **nicht**. Wer nur sie grün hält, hat ADR-0033 nicht nachgewiesen — Prüfort ≠ Wirkort.

- **AC-12:** Given mehrere amtliche Warnungen mit **verschiedenem** Umfang / When der Betreff
  gerendert wird / Then steht dort weiterhin die ehrliche Sammelangabe („mehrere Segmente") und
  nicht ein einzelnes Segment — AC-3 der Warnmail-Spec (#1248) bleibt gewahrt.
  - Test: der bestehende Test bleibt grün
    (`tests/tdd/test_official_alert_subject_compact.py`).

- **AC-13:** Given eine amtliche Warn-Mail / When sie versendet wird / Then trägt sie einen
  **eigens gebauten Klartext-Teil** mit denselben Datenzeilen und derselben Reihenfolge wie ihr
  HTML — nicht mehr den aus dem HTML gestrippten Text.
  - Test: die zugestellte Mail auf ihren `text/plain`-Teil prüfen. Er enthält die Datenzeilen
    als Label-Wert-Zeilen (Gefahrenart, Gültigkeitsfenster, Ortsbezug, Quelle), die Stand-Zeile
    und die Herkunfts-Fußzeile — in derselben Reihenfolge wie die Nowcast-Mail ihre Zeilen.
  - **Mutations-Gegenprobe:** Wird die Übergabe des Klartexts an den Mailer entfernt, muss der
    Test rot werden. Bleibt er grün, prüft er den gestrippten Text und nicht den gebauten —
    genau der Fehler, den dieses AC beseitigt.

- **AC-14:** Given der Umbau löst die Quelle-Box auf und der Warn-Mail-Wächter verlangt die
  CSS-Klasse `src` / When eine sachlich korrekte Mail im neuen Aufbau geprüft wird / Then
  besteht sie den Wächter, weil dessen Formen-Aufzählung **additiv erweitert** wurde — keine
  bestehende Alternative wurde entfernt oder gelockert.
  - Test: eine Mail **ohne** jede Quellenangabe wird weiterhin beanstandet. Ohne diesen
    Negativfall belegt der Positivfall nur, dass der Wächter nichts mehr prüft.
  - Nachweis am Ende: `official_alert_mail_validator.py` und `radar_alert_mail_validator.py`
    laufen je mit Exit 0 gegen eine **echt zugestellte** Staging-Mail.

## Was sich ausdrücklich NICHT ändert

- Auslösung, Cooldown, Kanal-Routing, Empfängerauflösung, Ruhezeiten, Tageslimit.
- Die Kurznachricht (SMS, Premium-SMS) — weder Ortsangabe noch Aufbau.
- Der Ortsvergleich — dort ist die Ortssprache bereits einheitlich.
- Der Korridor-/Schwellen-Renderer — toter Code seit `8f2053f9` (#1460 P1a), siehe #1199.

## Risiken

1. **Golden-Tests brechen absichtlich.** Mindestens vier Testdateien sichern die heutigen
   Betreffe byte-genau und müssen mit dem Produktivfix zusammen umgestellt werden — nie vorher,
   sonst beweist der Test nichts.
2. **Renderer-Commit-Gate greift.** Jeder Commit an `src/output/renderers/alert/*.py` blockt, bis
   `tests/tdd/test_issue_811_mode_matrix.py` grün ist und ein `briefing_mail_validator.py`-Lauf
   bestanden hat.
3. **A2 berührt ADR-0033-Fläche.** Die Entscheidung selbst (nur betroffener Umfang) bleibt gültig;
   geändert wird nur ihr Träger. **ADR-0052** hält den geänderten Aufbau fest und verweist auf
   ADR-0033 als weiterhin bindend.
4. **Struktur-Prüfer brechen absichtlich.** `tests/tdd/test_official_alert_standalone_render.py`
   prüft per BeautifulSoup auf `.verdict/.stufe/.warns/.facts/.mono/.seg/.route-note` und ist der
   direkteste Gegenspieler des Umbaus; dazu `test_warn_block_render.py`,
   `test_official_alert_warn_section.py`, `test_957_alert_mail_literal_structure.py`. Der einzige
   byte-genaue Vergleich der Nowcast-Mail steht **inline** im Modul
   (`test_multi_location_onset_alert.py::test_single_onset_email_and_subject_byte_identical`),
   nicht in einer Golden-Datei. Alle nur **zusammen mit** dem Produktivfix umstellen.
5. 🔴 **Vier Testdateien laufen still gar nicht.** `pyproject.toml:65` filtert
   `-m 'not email and not live and not staging'`; modulweites `pytestmark` macht daraus ein
   lautloses „deselected": `test_952_onset_alert_e2e.py`, `test_issue_1169_compare_alert_consumer.py`,
   `test_alert_sms_location_positions.py`, `test_issue_1087_trip_official_alerts.py`. Wer eine
   davon als Nachweis benennt, benennt einen Test, der nicht läuft — in A1 genau so passiert.
6. **Briefing-Goldens hängen mit dran.** `tests/golden/email/corsica-vigilance-{html,plain}.txt`
   sichern byte-genau die Briefing-Mail mit eingebettetem Warn-Badge über die geteilten
   `render_official_alerts_html/plain`. Wer diese Helfer anfasst, bricht sie mit.
