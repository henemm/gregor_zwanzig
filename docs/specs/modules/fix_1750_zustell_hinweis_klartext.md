---
entity_id: fix_1750_zustell_hinweis_klartext
type: bugfix
created: 2026-08-15
updated: 2026-08-15
status: draft
version: "1.0"
tags: [alerts, briefing, email, epic-1458, issue-1750, issue-1800]
---

# Briefing-Hinweis "nicht angekommen" wird verständlich (#1750, #1800)

## Approval

- [x] Approved — PO, 2026-08-15 („freigabe"). Ausdrücklich mitfreigegeben: die Änderung an
  AC-6 aus `feat_1461_s3b1_briefing_sichtbarkeit.md` (Deckelung 5 Zeilen gilt ab jetzt JE BLOCK
  statt für die Gesamtliste) und die ASCII-Faltung `ZURUeCKGEHALTEN` in der Kurzfassung.
  Beleg: Gesprächsverlauf zu #1750, Entscheidungen E1–E7 im Kontext-Dokument.

## Purpose

Der Briefing-Abschnitt „NICHT BEI DIR ANGEKOMMEN" nennt heute den technischen Kanalnamen
`premium_sms` roh, verwendet für Sperrgründe die Wörter „Ruhezeit"/„Sperrzeit", die zu **keiner**
Beschriftung in der Oberfläche passen, und behauptet mit „nicht zugestellt" pauschal einen
Fehler — obwohl vier von sechs Gründen planmäßige, vom Nutzer selbst eingestellte
Unterdrückungen sind. Diese Spec trennt „hier ist etwas schiefgegangen" (Fehler) von „das hast
du dir so eingestellt" (Absicht) in zwei eigene Blöcke, übernimmt für die zwei Sperrgründe die
Wörter aus der Oberfläche, ergänzt den fehlenden Premium-SMS-Kanalnamen und fasst wiederholte
gleichartige Vorfälle zu einer Zeile zusammen — damit eine echte zweite amtliche Warnung nicht
mehr hinter Regenradar-Zeilen aus der Deckelung fällt (gemessener Schaden, Mail vom 11.08.).

## Source

- **Datei (geändert, einzige Produktivdatei):**
  `src/output/renderers/email/undelivered_hint.py`
- **Identifier:** `_CHANNEL_LABELS`, `_REASON_LABELS`, `_line()`, `render_undelivered_plain()`,
  `render_undelivered_html()`, Modul-Docstring (fünfter Aufrufer nachtragen)
- **Schicht:** Python-Core (`src/output/renderers/email/`). Keine Go-Änderung, keine
  Frontend-Änderung, keine Änderung an `src/services/alert_log.py` oder
  `src/services/alert_gate.py`.
- **Fünf Aufrufer (unverändert in Signatur, nur der Inhalt ändert sich):**
  `src/output/renderers/email/html.py:1636`, `plain.py:360`, `compact.py:285`,
  `compare_html.py:1668`, **`src/output/renderers/comparison.py:396`** (Vergleichs-Klartext —
  im heutigen Modul-Docstring nicht genannt, wird mit dieser Änderung nachgetragen).
- **Testdateien (geändert, keine neue Datei):** `tests/tdd/test_alert_undelivered_hint.py`
  (Haupt-Suite + neue Wächter-Tests), `tests/tdd/test_alert_channel_threshold.py`,
  `tests/tdd/test_compare_alert_channel_threshold.py` (beide importieren `_hint_lines`/
  `LINE_MARKER` aus der Haupt-Suite und ein Testliteral, s. „Implementation Details").

## Estimated Scope

- **LoC:** ~150–190 Produktivcode (eine Datei) · ~350–450 Testcode (drei bestehende Dateien
  angepasst, keine neue Testdatei — neue Fälle ergänzen `test_alert_undelivered_hint.py`)
- **Files:** 1 Produktivdatei geändert, 3 Testdateien geändert, 0 neu
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_1459_alert_protokoll` | liest (unverändert) | `REASON_*`-Konstanten, `_ALL_CHANNELS` als SSoT für die Katalog-Wächter |
| `feat_1461_s3b1_briefing_sichtbarkeit` | ändert AC-6 | Deckelung „5 Zeilen" gilt ab dieser Spec je Block, nicht mehr gesamt (PO-Entscheidung E6) |
| `feat_1461_s3b2a_kanal_schwelle` | erfüllt AC-5 | „deutscher Grund, kein interner Bezeichner" — B1/B2 aus dem Kontext-Dokument beheben genau diesen Verstoß |
| ADR-0049 (Premium-SMS vierter Kanal) | befolgt | Außen-Schreibweise „Premium-SMS" |
| Issue #1701 (Premium-SMS D5) | liest | `blocked_reason_codes` → Sperrcodes `premium_sms_no_reply_address`/`premium_sms_reply_address_stale` aus `src/output/channels/premium_sms.py:41-42` |
| `src/output/renderers/email/design_tokens.py` | nutzt (nur bestehende Tokens) | `G_BOX_DANGER_BG`/`G_DANGER` (Failed, unverändert), `G_BOX_INFO_BG`/`G_INFO` (Withheld, neu verwendet) |
| Pendant-Sperre #1481 B | befolgt | Datei bleibt ohne `trip_`/`compare_`-Präfix, bedient Trip **und** Ortsvergleich |

## Implementation Details

### Datenfluss bleibt unverändert

`services.alert_log.read_undelivered()` liefert weiterhin genau die Vorfälle, die bereits über
das `DEDUP_WINDOW` (2 Min, protokoll-zeit-basiert) zusammengefasst sind — **daran wird nichts
geändert**. Alles Neue in dieser Spec (Blockaufteilung, Wortlaute, Wiederholungs-Zusammenfassung,
Deckelung je Block) ist reine **Anzeigelogik** in `undelivered_hint.py`, so wie schon heute
`MAX_UNDELIVERED_LINES` dort und nicht in `alert_log.py` sitzt.

### Neue/geänderte Modulkonstanten

Überschriften und Deckelung (Ersatz für `UNDELIVERED_HEADING`/`MAX_UNDELIVERED_LINES`):

```python
HEADING_FAILED = "FEHLGESCHLAGEN — da ist etwas schiefgegangen"
HEADING_WITHHELD = "ZURÜCKGEHALTEN — so hast du es eingestellt"
# UNDELIVERED_HEADING entfaellt ersatzlos (E1)

MAX_LINES_PER_BLOCK = 5   # gleicher Wert wie vorher, jetzt JE BLOCK ausgewertet

_CHANNEL_LABELS = {
    "email": "E-Mail", "telegram": "Telegram", "sms": "SMS",
    "premium_sms": "Premium-SMS",   # NEU (B1)
}
```

Grund-Wortlaute (drei bestehende Einträge unverändert im Wortlaut, vier neu/geändert):

```python
_REASON_LABELS = {
    "delivery_failed": "Versand fehlgeschlagen",                    # unveraendert
    "quiet_hours": "Stille Stunden",                                # NEU, war "Ruhezeit"
    "daily_limit": "Tageslimit",                                    # unveraendert
    "cooldown": "Cooldown",                                         # NEU, war "Sperrzeit"
    "below_channel_threshold": "unter deiner Schwelle",             # NEU, war "unter Schwelle"
    "premium_sms_no_reply_address": "keine Rückadresse gelernt",    # NEU (B1)
    "premium_sms_reply_address_stale": "Rückadresse veraltet",      # NEU (B1)
}
```

Einsortierung je Grund in einen der zwei Blöcke (E2-Tabelle als Code):

```python
_REASON_BLOCK = {
    "delivery_failed": "failed",
    "premium_sms_no_reply_address": "failed",
    "premium_sms_reply_address_stale": "failed",
    "quiet_hours": "withheld",
    "cooldown": "withheld",
    "daily_limit": "withheld",
    "below_channel_threshold": "withheld",
    # unbekannter Code -> _REASON_BLOCK.get(reason, "failed"): E2 letzte Zeile
}
```

`_REASON_LABELS`/`_REASON_BLOCK` bekommen KEINEN Eintrag für `channel_disabled` — der Grund
erreicht diesen Baustein weiterhin gar nicht (`alert_log.py:376` filtert ihn beim Lesen heraus,
unverändert).

### Wortwahl-Begründung (Pflichtangabe der PO-Entscheidung)

„Stille Stunden" und „Cooldown" sind exakt die Beschriftungen, unter denen der Nutzer diese
Werte in der Oberfläche einstellt (`frontend/src/lib/components/alerts-tab/
AlertQuietHoursCard.svelte:32` bzw. `AlertCooldownCard.svelte:11`); „Cooldown" steht zusätzlich
bereits so in der Alarm-Mail (`src/output/renderers/alert/render.py:201`). Die Mail führt damit
zur selben Einstellung zurück, die den Fall verursacht hat — das war vorher bei keinem der zwei
Wörter der Fall.

### Zeilenformat (E3)

`_line()` verliert die Formulierung „nicht zugestellt" komplett; die Blocküberschrift trägt die
Aussage jetzt:

```
{wann} · {worum} · {kanäle} · {grund}
```

Bei genau einem Vorfall bleibt das die einzige Form (kein „(1×)"-Suffix).

### Blockaufteilung + Reihenfolge

Je Rendering werden die gelesenen Vorfälle nach `_REASON_BLOCK` (Mehrheits-/Vereinigungs-Regel:
enthält `inc.reasons` mindestens einen Grund mit Block `"failed"`, zählt der ganze Vorfall als
`failed` — ein Vorfall mit gemischten Gründen ist damit nie „nur halb ein Fehler") in zwei Listen
sortiert. Jeder Block wird nur gerendert, wenn seine Liste nicht leer ist. **Reihenfolge, wenn
beide vorhanden sind: Fehlgeschlagen vor Zurückgehalten** — die dringlichere, handlungsrelevante
Information zuerst, konsistent mit der bestehenden Rot-vor-Neutral-Konvention des Bausteins.

### Wiederholungen zusammenfassen (E5)

Innerhalb eines Blocks werden Vorfälle mit identischem **Fünftupel**
`(inc.metrics, inc.hazards, inc.trigger, frozenset(inc.reasons), frozenset(inc.channels))` zu
einer Zeile zusammengefasst. `inc.metrics`/`inc.hazards`/`inc.trigger` sind bewusst die
**zugrundeliegenden Werte**, aus denen `_subject()` den angezeigten Text ableitet — **nicht**
der angezeigte Text selbst. Das ist keine kosmetische Feinheit: zwei amtliche Warnungen mit
unterschiedlicher Gefahrenart rendern beide als „Amtliche Warnung" (`_subject()` gibt bei jedem
`hazards`/`official_alert`-Vorfall denselben generischen Text zurück), sind aber **unterschiedliche
reale Ereignisse**. Eine Gruppierung nach angezeigtem Text würde genau den Fehler, den diese Spec
behebt, an anderer Stelle neu einführen: eine echte zweite Warnung verschwände hinter einem
Zähler statt hinter einer Deckelung. Deshalb AC-10.

Format bei `n > 1`: `{spanne} · {worum} ({n}×) · {kanäle} · {grund}`. Zeitspanne = ältester bis
jüngster Zeitpunkt der Gruppe:

- gleicher Kalendertag: `TT.MM. HH:MM–HH:MM` (ein Datum), z. B. `11.08. 04:07–17:37`
- Spanne über Mitternacht: `TT.MM. HH:MM–TT.MM. HH:MM` (Datum an beiden Enden), z. B.
  `10.08. 23:50–11.08. 00:15`

Sortierung innerhalb eines Blocks bleibt „jüngster Vorfall zuerst" (bestehende Zusicherung aus
`feat_1461_s3b1`); für eine zusammengefasste Zeile zählt dafür das jüngste Einzelmitglied der
Gruppe. (Das Beispiel in der PO-Vorgabe demonstriert Blocktrennung, Zeilenformat, Zähler- und
Zeitspannen-Schreibweise — nicht zwingend die exakte Zeilen-Reihenfolge für dieses synthetische
Beispiel; s. „Bekannte Grenzen".)

### Deckelung je Block (E6, Änderung an `feat_1461_s3b1` AC-6)

`MAX_LINES_PER_BLOCK` wird **separat für jeden der beiden Blöcke** ausgewertet (vorher: eine
gemeinsame Grenze über die ganze Liste). Rest-Hinweis „und N weitere" bleibt wortgleich, erscheint
aber gegebenenfalls in **beiden** Blöcken unabhängig. Bewusste Abweichung von der bisherigen
PO-Freigabe 2026-08-05 (galt für die Gesamtliste): so kann ein echter Fehler nie von planmäßigen
Unterdrückungen verdrängt werden — genau das ist am 11.08. mit der zweiten amtlichen Warnung
passiert.

### Farbgebung (E7)

Der Block „Fehlgeschlagen" bleibt der bestehende Danger-Kasten (`G_BOX_DANGER_BG`/`G_DANGER`,
unverändert). Der Block „Zurückgehalten" verwendet das bereits vorhandene neutrale Tokenpaar
`G_BOX_INFO_BG`/`G_INFO` (bislang für den Compact-Summary-Akzent genutzt, hier zweitverwendet —
kein neues Token). Inhaltszeilen bleiben in beiden Blöcken `G_INK` (Design-Leitprinzip: kein
`G_INK_FAINT` für Inhalt).

### ASCII-Sicherheit (Nebenbedingung 2)

`render_undelivered_plain(..., ascii_safe=True)` faltet weiterhin auf reines ASCII
(`str.isascii()`). Die zwei neu hinzukommenden Sonderzeichen bekommen dieselbe explizite
Vorbehandlung wie die bestehenden `"·"`/`"…"` (Zeile vor `fold_ascii()`):
`.replace("–", "-").replace("×", "x")` — Halbgeviertstrich der Zeitspanne wird zum ASCII-Bindestrich,
das Multiplikationszeichen des Zählers zum Buchstaben `x` (z. B. `12x` statt `12×`).

**Gemessen 2026-08-15** (`fold_ascii` auf den neuen Zeichen, damit die Umsetzung nicht rät):

| Zeichen | `fold_ascii` allein | Bewertung |
|---|---|---|
| `—` (Geviertstrich, in beiden Überschriften) | `-` | trägt schon, kein eigener Replace nötig |
| `–` (Halbgeviertstrich, Zeitspanne) | `-` | trägt schon; der Replace bleibt trotzdem, weil er die Absicht sichtbar macht (gleiche Bauform wie bei `·`/`…`) |
| `×` (Zähler) | **`*`** | **trägt NICHT** — ohne den Replace stünde `12*` in der Kurzfassung. Der Replace ist hier keine Kosmetik, sondern Pflicht |
| `Ü` (in `ZURÜCKGEHALTEN`) | `Ue` | bindende Digraph-Regel (`docs/reference/sms_format.md:27`) — die Kurzfassung zeigt `ZURUeCKGEHALTEN`, konsistent mit jedem anderen Umlaut dort |

### Fünf Aufrufer bleiben signaturgleich

`has_undelivered()`, `render_undelivered_plain()`, `render_undelivered_html()` behalten Name und
Parameter — nur ihr Ergebnis-Text ändert sich intern. Keiner der fünf Aufrufer muss angefasst
werden; der Modul-Docstring wird um den fünften Aufrufer (`comparison.py`) korrigiert.

### Testinfrastruktur-Anpassung (Nebenbedingung 4)

`LINE_MARKER = "nicht zugestellt"` (`test_alert_undelivered_hint.py:91`) verliert seinen Anker,
weil die Formulierung aus der Zeile verschwindet (E3). Ersatz: `_hint_lines()` sammelt alle
nicht-leeren, mit zwei Leerzeichen eingerückten Zeilen (bestehende Konvention) zwischen einer der
beiden neuen Überschriften (`HEADING_FAILED`/`HEADING_WITHHELD`) und der nächsten Leerzeile —
Rückgabe bleibt eine flache Liste aus **beiden** Blöcken, damit bestehende Aufrufer, die nur
`len(zeilen)`/Inhalt prüfen, unverändert funktionieren. Betroffen sind alle drei Testdateien
(`test_alert_undelivered_hint.py` selbst sowie die beiden Importeure
`test_alert_channel_threshold.py`, `test_compare_alert_channel_threshold.py`) — beide Importeure
ziehen `_hint_lines`/`LINE_MARKER` per `from tests.tdd.test_alert_undelivered_hint import ...`,
eine lokale Änderung genügt.

Testliterale, die zusätzlich mitgezogen werden müssen: `test_alert_channel_threshold.py:1018`
(`"unter Schwelle"` → `"unter deiner Schwelle"` enthält den alten String NICHT mehr als
zusammenhängendes Teilwort, Assertion muss auf den neuen Wortlaut umgestellt werden),
`test_alert_channel_threshold.py:1023` (verbietet `"Versand fehlgeschlagen"` — bleibt gültig,
unverändert). `test_compare_alert_channel_threshold.py:1043` erwartet nur die lose Teilzeichenkette
`"Schwelle"` — bleibt ohne Änderung erfüllt, da `"unter deiner Schwelle"` sie weiterhin enthält.

## Expected Behavior

- **Input:** Alarm-Protokoll des Nutzers (unverändertes Schema), Briefing-Zeitzone — identisch zu
  `feat_1461_s3b1`.
- **Output:** Null, ein oder zwei Blöcke in HTML- und Klartext-Mail (Trip `full`, Trip `compact`,
  Ortsvergleich HTML **und** Klartext). Jede Zeile trägt Zeitpunkt/Zeitspanne, Anlass (ggf. mit
  Wiederholungszähler), Kanäle mit deutschem Namen, deutschen Grund.
- **Side effects:** Keine. Reine Umformulierung/Umsortierung bestehender Eingabedaten; am
  Alarm-Protokoll, am Versandverhalten und an `alert_briefing_anchor` ändert sich nichts.

## Acceptance Criteria

- **AC-1:** Given ein Protokoll enthält sowohl einen `delivery_failed`- als auch einen
  `quiet_hours`-Vorfall seit dem letzten Briefing / When das Briefing gerendert wird / Then
  enthält der Text beide Überschriften „FEHLGESCHLAGEN — da ist etwas schiefgegangen" und
  „ZURÜCKGEHALTEN — so hast du es eingestellt", und die erste Überschrift steht im Text vor der
  zweiten.
  - Test: Zwei reale Protokolleinträge mit den genannten Gründen anlegen, Briefing über den
    echten Versandpfad erzeugen, Position beider Überschriften im erzeugten Klartext vergleichen.

- **AC-2:** Given ein Protokoll enthält ausschließlich einen `cooldown`-Vorfall (keinen
  fehlgeschlagenen) / When das Briefing gerendert wird / Then erscheint ausschließlich die
  Überschrift „ZURÜCKGEHALTEN — so hast du es eingestellt" — „FEHLGESCHLAGEN" kommt im Text
  nicht vor.
  - Test: Ein Protokolleintrag mit Grund `cooldown`, Briefing rendern, beide Überschriften-Strings
    auf An-/Abwesenheit prüfen.

- **AC-3:** Given seit dem letzten Briefing wurde jede Meldung auf jedem eingeschalteten Kanal
  zugestellt / When das Briefing erzeugt wird / Then enthält es keinen der beiden neuen
  Blöcke — auch keine Überschrift, keine Zeile.
  - Test: Protokoll nur mit vollständig zugestellten Einträgen; weder „FEHLGESCHLAGEN" noch
    „ZURÜCKGEHALTEN" kommt im erzeugten Text vor (Regressionstest zu `feat_1461_s3b1` AC-3).

- **AC-4:** Given ein Vorfall betrifft den Kanal `premium_sms` (z. B. Grund `cooldown`) / When
  die Briefing-Zeile erzeugt wird / Then nennt sie den Kanal als „Premium-SMS" — der rohe Wert
  `premium_sms` kommt als eigenständiges Wort nicht vor.
  - Test: Protokolleintrag mit `channels_not_sent=[{premium_sms, cooldown}]`, Zeile im erzeugten
    Text prüfen: „Premium-SMS" vorhanden, `"premium_sms"` (klein, mit Unterstrich) nicht.

- **AC-5:** Given ein Vorfall trägt den Grund `quiet_hours` / When die Zeile erzeugt wird / Then
  steht darin „Stille Stunden" — weder „Ruhezeit" noch der rohe Code kommen vor.
  - Test: Protokolleintrag mit Grund `quiet_hours` (Nowcast-Pfad, `append_suppressed_entry`),
    Briefing rendern, Wortlaut in der Zeile prüfen.

- **AC-6:** Given ein Vorfall trägt den Grund `cooldown` / When die Zeile erzeugt wird / Then
  steht darin „Cooldown" — weder „Sperrzeit" noch der rohe Code kommen vor.
  - Test: Protokolleintrag mit Grund `cooldown`, Briefing rendern, Wortlaut in der Zeile prüfen.

- **AC-7:** Given ein einzelner nicht zugestellter Vorfall liegt vor / When die Zeile erzeugt
  wird / Then hat sie exakt die Form `{wann} · {worum} · {kanäle} · {grund}` ohne die
  Formulierung „nicht zugestellt" und ohne Klammern um den Grund.
  - Test: Ein Vorfall, erzeugte Zeile per Trennzeichen `·` in vier Teile zerlegen, jeden Teil
    gegen die erwarteten Werte prüfen; `"nicht zugestellt"` kommt im ganzen Mailtext nicht vor.

- **AC-8:** Given ein Protokolleintrag trägt einen Grund-Code, der in keinem der beiden
  Wortlisten-Wörterbücher vorkommt (simuliert künftigen, noch nicht katalogisierten Code) / When
  das Briefing gerendert wird / Then erscheint die Zeile im Block „FEHLGESCHLAGEN", nicht im
  Block „ZURÜCKGEHALTEN".
  - Test: Protokolldatei mit `channels_not_sent=[{email, "unbekannter_code_x"}]` real anlegen,
    Briefing rendern, Position der resultierenden Zeile relativ zu den zwei Überschriften prüfen.

- **AC-9:** Given zwölf Regenradar-Vorfälle mit identischem Register-Paar, identischen Gründen
  (`quiet_hours`) und identischen Kanälen (E-Mail, Telegram) liegen über mehrere Stunden verteilt
  vor / When das Briefing gerendert wird / Then steht dafür genau eine Zeile mit „(12×)" im
  Anlass-Teil und einer Zeitspanne vom ältesten bis zum jüngsten Zeitpunkt.
  - Test: Zwölf reale Protokolleinträge (Radar-Pfad, gleiches Register-Paar) mit Zeitstempeln über
    mehrere Stunden anlegen, Briefing rendern, genau eine Zeile im Withheld-Block mit „(12×)" und
    beiden Randzeitpunkten nachweisen.

- **AC-10:** Given zwei amtliche Warnungen mit unterschiedlicher Gefahrenart (`hazards`), aber
  gleichem angezeigtem Anlasstext „Amtliche Warnung", gleichem Kanal und gleichem Grund
  (`below_channel_threshold`) liegen vor / When das Briefing gerendert wird / Then stehen dafür
  **zwei** separate Zeilen, nicht eine zusammengefasste mit „(2×)".
  - Test: Zwei Protokolleinträge mit `hazards=["thunderstorm"]` bzw. `hazards=["flood"]` (oder
    vergleichbar unterschiedlich), sonst identischem Kanal/Grund; Anzahl der Zeilen im
    Withheld-Block muss zwei sein — Kern-Anti-Regressions-Test gegen den in E5 beschriebenen
    Fehlschluss.

- **AC-11:** Given eine Gruppe wiederholter Vorfälle beginnt an einem Kalendertag und endet am
  nächsten / When die zusammengefasste Zeile erzeugt wird / Then trägt die Zeitspanne an beiden
  Enden ein Datum (`TT.MM. HH:MM–TT.MM. HH:MM`).
  - Test: Zwei gruppierbare Vorfälle mit Zeitstempeln 23:50 und 00:15 des Folgetags anlegen,
    erzeugte Zeitspannen-Zeichenkette gegen das Muster mit zwei Datumsangaben prüfen.

- **AC-12:** Given seit dem letzten Briefing liegen sechs unterschiedliche (nicht gruppierbare)
  fehlgeschlagene Vorfälle **und** ein zurückgehaltener Vorfall vor / When das Briefing gerendert
  wird / Then zeigt der Block „FEHLGESCHLAGEN" fünf Zeilen plus „und 1 weitere", **und** der
  zurückgehaltene Vorfall erscheint vollständig im Block „ZURÜCKGEHALTEN" — er wird von der
  Deckelung des anderen Blocks nicht verdrängt.
  - Test: Sechs `delivery_failed`-Einträge (verschiedene Anlässe, keine E5-Gruppierung möglich)
    plus einen `cooldown`-Eintrag real anlegen, Briefing rendern; Withheld-Zeile im Text
    nachweisen (reproduziert direkt den am 11.08. gemeldeten Schaden — vorher hätte sie gefehlt).

- **AC-13:** Given ein Vorfall wurde wegen einer fehlenden Premium-SMS-Rückadresse
  (`premium_sms_no_reply_address`) bzw. einer veralteten Rückadresse
  (`premium_sms_reply_address_stale`) blockiert / When die Zeile erzeugt wird / Then nennt sie
  „keine Rückadresse gelernt" bzw. „Rückadresse veraltet" und steht im Block „FEHLGESCHLAGEN".
  - Test: Zwei Protokolleinträge über `blocked_reason_codes={"premium_sms": <Code>}` (via
    `alert_log.append_entry`) real anlegen, Briefing rendern, Wortlaut UND Blockzugehörigkeit je
    Fall prüfen.

- **AC-14:** Given je ein Vorfall aus jedem Block liegt vor / When die HTML-Mail gerendert wird /
  Then trägt der Kasten des Blocks „FEHLGESCHLAGEN" die Hex-Werte von `G_BOX_DANGER_BG`/
  `G_DANGER`, der Kasten des Blocks „ZURÜCKGEHALTEN" die Hex-Werte von `G_BOX_INFO_BG`/`G_INFO`,
  und keiner der beiden Inhaltszeilen-Stile enthält den Hex-Wert von `G_INK_FAINT` (`#9c9a90`).
  - Test: `render_undelivered_html(...)` aufrufen und die vier Hex-Werte je Kasten per
    Substring-Suche im erwarteten `<div>`-Ausschnitt nachweisen; `#9c9a90` wird **im Rückgabewert
    dieses Bausteins** verneint, NICHT in der ganzen Briefing-Mail — `G_INK_FAINT` ist dort an
    sechs weiteren Stellen legitim in Gebrauch (`html.py`, gemessen 2026-08-15), eine Prüfung
    gegen die Gesamtausgabe wäre strukturell nie erfüllbar.

- **AC-15:** Given eine zusammengefasste Zeile mit Zeitspanne und Wiederholungszähler liegt vor /
  When die Kurzfassungs-Mail (`compact.py`, `ascii_safe=True`) gerendert wird / Then ist der
  erzeugte Text vollständig `str.isascii()`, der Halbgeviertstrich der Spanne erscheint als `-`
  und das Multiplikationszeichen des Zählers als `x`.
  - Test: Gruppierbare Vorfälle mit Zeitspanne über zwei Zeitpunkte real anlegen,
    `render_undelivered_plain(..., ascii_safe=True)` aufrufen, `str.isascii()` und die
    konkreten Ersatzzeichen im Text prüfen.

- **AC-16:** Given ein und dieselbe Protokoll-Lage mit Vorfällen in beiden Blöcken / When Trip
  HTML, Trip Klartext (`full`), Trip Kurzfassung, Ortsvergleich HTML **und** Ortsvergleich
  Klartext (`comparison.py`) gerendert werden / Then enthalten **alle fünf** Ausgaben beide
  Blöcke mit denselben deutschen Wortlauten.
  - Test: Dieselbe Protokolldatei über alle fünf Renderpfade rendern (inkl. des bisher im
    Docstring fehlenden `comparison.py`-Pfads), je Ausgabe beide Überschriften und mindestens
    eine Beispiel-Formulierung („Premium-SMS", „Stille Stunden") nachweisen.

- **AC-17:** Given für jeden Kanal aus `services.alert_log._ALL_CHANNELS` (Single Source of
  Truth) liegt ein Vorfall vor, der genau diesen Kanal betrifft / When das Briefing gerendert
  wird / Then erscheint für jeden Kanal sein deutsches Label aus `_CHANNEL_LABELS`, und keiner
  der vier rohen Kanalnamen (`email`, `telegram`, `sms`, `premium_sms`) kommt als eigenständiges,
  klein geschriebenes Wort im erzeugten Text vor.
  - Test: Wächter-Test parametrisiert über `alert_log._ALL_CHANNELS`, baut je Kanal einen realen
    Protokolleintrag, rendert das Briefing, prüft am erzeugten Text (nicht am Wörterbuch) sowohl
    das erwartete deutsche Label als auch die Abwesenheit des rohen Kanalnamens per
    Wortgrenzen-Suche (verhindert Fehlalarm durch `"sms"` als Teilstring von `"Premium-SMS"`).

- **AC-18:** Given für jede `REASON_*`-Konstante aus `services.alert_log` (außer
  `REASON_CHANNEL_DISABLED` und den drei Auslöser-Konstanten `REASON_FORECAST_CHANGE`/
  `REASON_NOWCAST`/`REASON_OFFICIAL_ALERT`) sowie für jeden Sperrcode aus
  `output.channels.premium_sms` (`BLOCK_REASON_NO_REPLY_ADDRESS`,
  `BLOCK_REASON_REPLY_ADDRESS_STALE`) liegt ein Vorfall mit genau diesem Grund vor / When das
  Briefing gerendert wird / Then erscheint für jeden Grund ein deutsches Label, und die Zeile
  steht im laut Einsortierungs-Tabelle (E2) richtigen Block.
  - Test: Wächter-Test parametrisiert über die SSoT-Konstanten, baut je Grund einen realen
    Protokolleintrag, rendert das Briefing, prüft am erzeugten Text sowohl das deutsche Label als
    auch die Blockzugehörigkeit (Position relativ zu `HEADING_FAILED`/`HEADING_WITHHELD`).

## Nachweis

**Renderer-Commit-Gate #811 (un-überspringbar):** `undelivered_hint.py` liegt unter
`src/output/renderers/email/` — der Commit blockt, bis im aktiven Workflow beide frisch
vorliegen: (1) `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` grün, (2) ein
erfolgreicher Lauf von `uv run python3 .claude/hooks/briefing_mail_validator.py` gegen eine echt
zugestellte Staging-Mail mit Marker-Header `X-GZ-Mail-Type: trip-briefing`.

„E2E bestanden" darf für dieses Feature erst nach Exit 0 des Validators behauptet werden — gegen
echte Zustellung ins Stalwart-Test-Postfach, kein Mock, kein Gmail.

## Nicht in dieser Scheibe

- **O3 — Protokoll-Lücke bei Vorhersage-Änderung und amtlicher Warnung** (`alert_log.py:281-284`,
  `trip_alert.py:247`, `compare_alert.py:159`): diese beiden Pfade protokollieren ihre
  Unterdrückungen weiterhin **gar nicht**. Diese Spec kann nur anzeigen, was im Protokoll steht —
  sie erzeugt keine neuen Schreibstellen. Eigener Befund, nicht Teil von #1750/#1800.
- Änderungen an der Oberfläche (Alarme-Tab). Die Mail folgt der Oberflächen-Wortwahl, nicht
  umgekehrt — keine Frontend-Datei wird angefasst.
- Änderungen an `DEDUP_WINDOW`, `alert_log.append_entry()`/`append_suppressed_entry()` oder dem
  Protokoll-Schema.
- Neue Konfigurierbarkeit für den Nutzer (z. B. Blöcke ein-/ausblendbar machen). Beide Blöcke sind
  unbedingt, kein Setting.
- Sichtbarkeit in Telegram-/SMS-Kurznachrichten. AC-10 aus `feat_1461_s3b1` (Zeichenidentität
  ungeachtet vorliegender Vorfälle) bleibt unverändert Ziel dieser Spec (hier als AC weitergeführt
  über die Kurzfassungs-ASCII-Prüfung); eine **neue** Sichtbarkeit dort wird nicht eingeführt.
- Neue Design-Tokens. `G_BOX_INFO_BG`/`G_INFO` sind bereits vorhanden und werden nur
  zweitverwendet.

## Known Limitations

- **Sortierreihenfolge bei verschränkten Einzel-/Gruppen-Zeitstempeln:** Wenn eine zusammengefasste
  Zeile eine Zeitspanne trägt, die einen einzelnen (nicht gruppierten) Vorfall zeitlich umschließt,
  ist die exakte Zeilen-Reihenfolge zwischen beiden nicht Gegenstand eines eigenen ACs — es gilt
  „jüngster Vorfall zuerst", wobei für eine Gruppe deren jüngstes Mitglied zählt. Das
  Beispiel in der PO-Vorgabe illustriert Format und Blocktrennung, nicht zwingend eine
  bindende Zeilen-Reihenfolge für exakt dieses synthetische Beispiel.
- **Unbekannter Grund-Code zeigt weiterhin den rohen Code als Wortlaut** — es gibt strukturell
  keine deutsche Übersetzung für einen Code, den niemand kennt. AC-8 sorgt nur dafür, dass er im
  richtigen (roten) Block landet, nicht dafür, dass er hübsch aussieht. Die Katalog-Wächter
  (AC-17/AC-18) machen diesen Fall für alle heute bekannten Codes unerreichbar, garantieren aber
  nichts für künftig neu eingeführte Codes vor dem nächsten Testlauf.
- **Innerhalb eines Blocks bleibt die Deckelung bei 5 Zeilen** (E6 ändert nur die Reichweite der
  Deckelung — Block statt Gesamtliste — nicht ihre Höhe). Bei mehr als 5 nicht gruppierbaren
  Vorfällen in einem Block greift weiterhin „und N weitere".
- **E5-Gruppierung wirkt nur innerhalb eines Blocks.** Da der Grund den Block eindeutig bestimmt
  (`_REASON_BLOCK`), können zwei Vorfälle mit identischem Fünftupel nie in unterschiedlichen
  Blöcken landen — eine block-übergreifende Sonderregel ist nicht nötig.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Wortwahl und Layout eines Briefing-Bausteins verschieben keine
  Entscheidungsfläche (Kanäle, Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie). Der Kanalname „Premium-SMS" ist bereits durch ADR-0049 festgelegt und
  wird hier nur an einer bislang übersehenen Stelle nachgezogen.

## Changelog

- 2026-08-15 (v1.0a): Redaktionelle Angleichung ohne Bedeutungsänderung — der
  Beispiel-Codeblock schrieb `"keine Rueckadresse gelernt"`/`"Rueckadresse veraltet"` in
  ASCII, während das verbindliche AC-13 „Rückadresse" mit Umlaut zusichert. Der Codeblock
  folgt jetzt dem AC. Aufgefallen in der TDD-RED-Phase; die Kurzfassung faltet den Umlaut
  ohnehin über `fold_ascii` (s. Messtabelle oben), eine ASCII-Schreibweise im Label wäre also
  auch fachlich falsch gewesen.
- 2026-08-15 (v1.0): Initial spec created, auf Basis von
  `docs/context/fix-1750-sperrzeit-wortwahl.md`. Ändert AC-6 aus
  `feat_1461_s3b1_briefing_sichtbarkeit.md` (Deckelung jetzt je Block statt gesamt, PO-begründet)
  und erfüllt AC-5 aus `feat_1461_s3b2a_kanal_schwelle.md` (deutscher Grund statt interner
  Bezeichner) auch für `premium_sms`.
