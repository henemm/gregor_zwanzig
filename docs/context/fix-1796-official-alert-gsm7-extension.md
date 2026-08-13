# Context: fix-1796-official-alert-gsm7-extension

## Request Summary
GSM-7-Extension-Zeichen (`^{}[]~|\€`, formal `\x0c^{}\[~]|€`) im Trip-Namen laufen
unverändert durch `_ascii()` in `src/output/renderers/alert/render.py`, weil dessen
Faltung (`fold_ascii()`) nur *Buchstaben* behandelt — Extension-Zeichen sind aber
bereits ASCII. Ein einziges solches Zeichen im gerenderten Text schaltet den
gesamten SMS-Versand still auf UCS-2 um (67 statt 153 Zeichen je Teil), betrifft
amtliche Alarme über SMS UND Premium-SMS.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/render.py:709-714` | `_ascii()` — der Fix-Ort. Ersetzt heute nur vier feste Zeichen (`–`, `−`, `°`, `↑`/`↓`) + `fold_ascii()`; muss um die 9 GSM-7-Extension-Zeichen erweitert werden |
| `src/output/renderers/alert/official_alerts.py:1971-2054` | `render_official_alert_sms()` — ruft `_ascii()` auf `head` (enthält `sms_prefix` = gefalteten Trip-Namen), `tokens`, `suffix`, `lead_*` |
| `src/services/notification_service.py:873, 892, 911` | Drei Aufrufstellen von `render_official_alert_sms(sms_prefix=trip.name.replace(" ", ""))`: Telegram-Kurzform (873, GSM-7 dort irrelevant, aber gleicher Codepfad), SMS (892), Premium-SMS (911) |
| `tests/tdd/_gsm7_charset.py` | Geteilter Prüf-Helfer `assert_gsm7_clean()`/`_first_non_gsm7_char()`; kennt bereits `GSM7_EXTENDED_TWO_SEPTET_CHARS = "\x0c^{}\\[~]|€"` als eigene (nicht im Kern-Alphabet enthaltene) Konstante — das ist die maßgebliche Zeichenliste für den Fix |
| `tests/tdd/test_trip_sms_gsm7_charset.py:230` | Trägt den Kommentar „AC-3 (Extension-Zeichen aus dem Trip-Namen) entfernt, s. Issue #1796.“ — genau hier gehört der reaktivierte Test hin |
| `src/output/renderers/comparison.py:592-621` | Analoges, bereits produktives Muster: `_SMS_GSM7_UNSAFE_REPLACEMENTS` (Tupel-Liste) + `_sms_gsm7_safe()` (Ersetzungsschleife) für den Compare-SMS-Pfad. Vorbild für die Umsetzung hier |
| `src/utils/ascii_fold.py` | `fold_ascii()` — NFKD-Faltung für Buchstaben (Kategorien Ll/Lu/Lt/Lo/Lm). Extension-Zeichen sind keine Buchstaben, deshalb strukturell nicht erreichbar durch diese Funktion — kein Fix hier nötig/sinnvoll |
| `docs/specs/modules/feat_1533_s4_generalprobe.md` | Ursprungs-Spec: AC-3 (GSM-7-Extension-Zeichen) wurde dort in der RED-Phase bestätigt (3/3 rot), dann per PO-Entscheidung nach #1796 ausgelagert — Test-Code ist dort dokumentiert, kann als Vorlage dienen |

## Existing Patterns
- **Compare-SMS-Pfad (`comparison.py`)**: feste Tupel-Liste `(bad, good)` +
  Ersetzungsschleife, mit Kommentar zur Herkunft jedes Eintrags (Issue-Nummer,
  Adversary-Runde). Extension-Zeichen könnten analog als
  `_ASCII_EXTENSION_REPLACEMENTS`-Tupel in `alert/render.py` ergänzt werden,
  angewendet VOR oder NACH `fold_ascii()` innerhalb von `_ascii()`.
- **Geteilter Prüf-Helfer**: `tests/tdd/_gsm7_charset.py` existiert explizit,
  damit Compare-, Trip-Briefing- und amtlicher-Alarm-Wächter dieselbe
  Zeichensatz-Definition prüfen (Lehre aus früherem Fund: „zwei getrennt
  gepflegte Tabellen können beide grün sein und trotzdem verschiedene Welten
  prüfen“). `GSM7_EXTENDED_TWO_SEPTET_CHARS` dort ist die Quelle der Wahrheit
  für die zu behandelnden Zeichen — keine neue Liste erfinden.
- **`_ascii()` wird ausschließlich für SMS-Text verwendet** (alle Aufrufstellen
  in `render.py` sind `_render_sms_*`-Funktionen bzw. `render_official_alert_sms`
  in `official_alerts.py`) — Mail/Telegram-Volltext-Pfade nutzen andere
  Formatierungsfunktionen und sind vom Fix nicht betroffen (bis auf die
  Telegram-Kurzform, die bewusst denselben SMS-Renderer wiederverwendet).

## Dependencies
- **Upstream:** `fold_ascii()` (`src/utils/ascii_fold.py`) für Buchstaben;
  `unicodedata.category()`-Klassifikation entscheidet, was gefaltet wird.
- **Downstream:** `render_official_alert_sms()` wird von drei Stellen in
  `notification_service.py` aufgerufen (Telegram-Kurzform, SMS, Premium-SMS —
  alle drei Kanäle profitieren vom Fix, auch wenn nur SMS/Premium-SMS ein
  echtes Kostenproblem haben).

## Existing Specs
- `docs/specs/modules/feat_1533_s4_generalprobe.md` — dokumentiert AC-3 als
  ausgelagert nach #1796, keine aktive Spec für diesen Fix.
- Kein bestehendes Modul-Spec-Dokument für `alert/render.py`/`_ascii()`
  selbst; nächstliegendes Referenzdokument ist `docs/reference/mail_validators.md`
  (Renderer-Gate #811).

## Risks & Considerations
- **Renderer-Commit-Gate #811 ist un-überspringbar** (`renderer_mail_gate.py`):
  `alert/render.py` UND `alert/official_alerts.py` liegen unter
  `src/output/renderers/alert/*.py` — vor Commit müssen
  `tests/tdd/test_issue_811_mode_matrix.py` grün sein UND ein frischer
  erfolgreicher `briefing_mail_validator.py`-Lauf gegen Staging vorliegen.
- **Blast Radius eng, aber Pfad kritisch:** Nur Trips mit einem der neun
  Zeichen im Namen sind betroffen — aber der Pfad trägt amtliche
  Wetter-/Unwetter-Alarme für Weitwanderer (lebenswichtig, s. KHW-Kontext).
  Reale Auswirkung auf laufende Touren vor dem Fix prüfen (KHW-Trip-Name laut
  Issue noch zu verifizieren).
- **Reihenfolge der Ersetzung:** `_ascii()` ruft aktuell erst feste
  Einzelersetzungen auf, dann `fold_ascii()`. Da Extension-Zeichen keine
  Buchstaben sind, ist die Reihenfolge relativ zu `fold_ascii()` unkritisch —
  wichtig ist nur, dass die Ersetzung nicht versehentlich VOR den bestehenden
  Einzelersetzungen ein bereits ersetztes Zeichen erneut trifft (z.B. `€` vs.
  bestehende `°`-Behandlung — keine Überschneidung vorhanden).
- **Kein Pendant-Gate-Konflikt:** `alert/render.py`/`official_alerts.py` sind
  weder unter `compare*` noch `trip_*` präfigiert und keine Neuanlage —
  `pendant_gate.py` greift hier nicht.
- **Test-Reaktivierung:** Der AC-3-Test aus der #1533-S4-RED-Phase ist laut
  Issue „bereits geschrieben und lauffähig“ — sollte wiederverwendet statt neu
  erfunden werden (Parametrisierung über `["KHW [Test]", "Tour~Nord",
  "Weg|Nord"]` oder besser: alle neun Zeichen aus
  `GSM7_EXTENDED_TWO_SEPTET_CHARS` einzeln parametrisiert, für vollständige
  Abdeckung statt nur der drei im Issue genannten Beispiele).
  **Verifiziert:** Der Test wurde nie committet (nur 2 Commits berühren
  `test_trip_sms_gsm7_charset.py`: `61cf21ef` feat #1533, `83580fd3` fix
  #1703 S6 — kein Removal-Commit dazwischen), er existierte nur innerhalb der
  unkommitteten RED-Phase. Muss also aus der Spec-Dokumentation
  (`feat_1533_s4_generalprobe.md`) bzw. neu geschrieben werden, nicht aus der
  Git-Historie rekonstruiert.

## Analysis

### Type
Bug (bestätigter, reproduzierter Fund — kein Verdacht).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/render.py` | MODIFY | `_ascii()` (Zeilen 709-714) um Behandlung der 9 GSM-7-Extension-Zeichen (`^{}[]~|\€` + ggf. Form-Feed `\x0c`) erweitern — Ersetzung analog `comparison.py`s `_SMS_GSM7_UNSAFE_REPLACEMENTS`/`_sms_gsm7_safe()` |
| `tests/tdd/test_trip_sms_gsm7_charset.py` | MODIFY | AC-3-Test (Extension-Zeichen im Trip-Namen) an Zeile 230 reaktivieren, idealerweise über alle Zeichen aus `GSM7_EXTENDED_TWO_SEPTET_CHARS` parametrisiert statt nur die 3 Issue-Beispiele |

Keine weiteren Aufrufstellen von `_ascii()`/`render_official_alert_sms()` außerhalb der bereits bekannten drei Kanäle (Telegram-Kurzform, SMS, Premium-SMS) gefunden.

### Scope Assessment
- Files: 2
- Estimated LoC: +15/-2 (kleine Konstante + Ersetzungsaufruf in `render.py`, erweiterter Testblock)
- Risk Level: **LOW** — isolierte Zeichen-Ersetzung, bewährtes Muster aus `comparison.py` bereits produktiv, abgesichert durch un-überspringbares Renderer-Commit-Gate #811 (Mode-Matrix-Test + Staging-Mail-Validator vor Commit) und den bereits bestätigten Regressionstest.

### Technical Approach
In `_ascii()` (`alert/render.py:709-714`) vor oder nach `fold_ascii()` eine feste
Ersetzungstabelle für die GSM-7-Extension-Zeichen ergänzen (Vorbild:
`comparison.py:592-621`). Zwei Bausteine:
1. Neue modul-lokale Konstante, z.B. `_ASCII_EXTENSION_REPLACEMENTS`, mit den
   9 Zeichen aus `GSM7_EXTENDED_TWO_SEPTET_CHARS`
   (`tests/tdd/_gsm7_charset.py:42`) — Produktionscode darf NICHT aus
   `tests/` importieren, die Zeichenliste muss dort dupliziert werden (mit
   Kommentar-Verweis auf die Testdatei als Quelle der Wahrheit).
2. Jedes Zeichen bekommt eine sichtbare Entsprechung im GSM-7-Basisalphabet
   (z.B. `[`/`{`→`(`, `]`/`}`→`)`, `\`/`|`/`~`→`-`, `€`→`EUR` oder Entfernen)
   oder wird ersatzlos entfernt, wo keine sinnvolle visuelle Entsprechung
   existiert (Form-Feed `\x0c`) — die genaue Zuordnung ist eine
   Freigabe-Entscheidung für `/30-write-spec` (AC), kein technisches Risiko.

### Dependencies
- Upstream: `fold_ascii()` bleibt unverändert (Buchstaben-Faltung, strukturell
  nicht zuständig für Extension-Zeichen).
- Downstream: Alle drei Aufrufer in `notification_service.py` (873/892/911)
  profitieren automatisch, kein Aufrufer-seitiger Änderungsbedarf.
- Gate: Renderer-Commit-Gate #811 (`renderer_mail_gate.py`) —
  `test_issue_811_mode_matrix.py` grün + frischer `briefing_mail_validator.py`-
  Lauf gegen Staging vor Commit zwingend.

### Empfehlung
Fix wie oben beschrieben umsetzen — bewährtes, risikoarmes Muster, keine
offene technische Frage. Einzige Entscheidung für die Spec-Phase: die exakte
Zeichen-zu-Zeichen-Zuordnung (visuelle Entsprechung vs. Entfernen), die als
AC formuliert und vom PO freigegeben wird.

### Open Questions
- [ ] Exakte Ersetzungstabelle je Extension-Zeichen (Vorschlag oben) — PO-
      Freigabe im Rahmen der Spec, keine Blockade für den weiteren Ablauf.
