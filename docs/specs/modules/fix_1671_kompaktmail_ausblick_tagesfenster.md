---
entity_id: fix_1671_kompaktmail_ausblick_tagesfenster
type: bugfix
created: 2026-08-14
updated: 2026-08-14
status: approved
version: "1.0"
tags: [gewitter, ausblick, tag-nacht, compact, issue-1671]
---

<!-- Issue #1671. Grundlage: PFLICHTLEKTUERE
     docs/context/fix-1671-compact-gewitter-tagesfenster.md (am Stand
     `e2b5269b` gemessen, nicht aus dem Ticket uebernommen). Vorbilder:
     docs/specs/modules/fix_1653_ausblick_tag_nacht_trennung.md (Muster:
     Tag/Nacht-Trennung, drei Kanaele) und
     docs/specs/modules/feat_1680_s5a_gewitter_herkunft_ausblick.md
     (AC-13, die hier bewusst NICHT abgeloest wird). -->

# #1671 — Kurzformat-Mail: Gewitterspalte des Ausblicks liest das falsche Fenster

## Approval

- [x] Approved — PO-go 2026-08-14 (Klartext-Freigabe der ACs auf Deutsch).
      Zugleich freigegeben: LoC-Limit dieses Workflows auf 500 angehoben.

## Purpose

Der Ausblick-Block „Naechste Etappen" existiert in vier Ausgabeorten. Drei
davon (HTML-Ausblick-Tabelle, Klartext-Mail-Ausblick, Telegram-Trendblock)
wurden mit #1653 auf `thunder_day_token`/`thunder_night_token` — das
Tagesfenster derselben Stundenreihe — umgestellt. Die **Kurzformat-Mail**
(`X-GZ-Format: compact`, `src/output/renderers/email/compact.py:230-236`)
baut ihre Gewitterspalte weiterhin aus `tok['thunder_plain']`, dem auf die
Gehzeit geklemmten 24-Stunden-Aggregat — der vierte, bei #1653 vergessene
Ausgabeort. Folge: die Kurzformat-Zeile kann ein reales Tagesgewitter
verschweigen (falsch-negativ) oder ein nicht vorhandenes behaupten
(falsch-positiv), und eine Nachtangabe fehlt dort strukturell ganz.

Diese Scheibe stellt die Kurzformat-Mail auf dieselbe Quelle
(`thunder_day_token`/`thunder_night_token`) um wie die drei anderen Kanäle —
mit eigenem, dem ASCII-Format der Kurzformat-Mail angepasstem
Darstellungsformat — und beseitigt dabei die Ursache (drei fast identische
Zweig-Entscheidungen), statt eine vierte Kopie zu schreiben.

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core
> (`src/output/renderers/email/`). Kein Frontend, keine Go-Beteiligung, kein
> neuer Endpoint, keine neuen Persistenz-Felder.

- **File:** `src/output/renderers/email/compact.py` — `render_compact()`,
  Ausblick-Schleife Z. 227–238 (**der Prüfling**).
- **File:** `src/output/renderers/email/helpers.py` — `format_trend_tokens()`
  (liefert `thunder_day_token`/`thunder_night_token`/`thunder_plain`
  unverändert); neuer Entscheidungs-Helfer wird hier ergänzt.
- **File:** `src/output/renderers/email/outlook.py` —
  `render_outlook_plain()` Z. 358–414 (Vorbild Darstellungsformat,
  Refactoring-Ziel für den geteilten Entscheidungs-Helfer),
  `_thunder_token_parts()` Z. 43–59 (Token-Zerlegung, wiederverwendet).
- **File:** `src/output/renderers/narrow.py` — `_outlook_lines()`
  Z. 571–609 (Refactoring-Ziel für denselben Entscheidungs-Helfer).

## Estimated Scope

- **LoC:** ~50–70 Produktivcode (neuer Helfer in `helpers.py`, Ausblick-
  Logik in `compact.py`, Refactoring der bestehenden Zweige in `outlook.py`
  und `narrow.py` auf den Helfer) + ~150–220 Testcode (Kern-Suite,
  Mutations-Gegenproben, Nullfall/Fall-A/Fall-B-Fixtures analog #1653) —
  voraussichtlich in Summe **über dem 250-Zeilen-Workflow-Limit**;
  `workflow.py set-field loc_limit_override 500` bei Bedarf in
  `/50-implement` einholen (identische Einschätzung wie #1653).
- **Files:** 4 Produktivdateien (MODIFY: `compact.py`, `helpers.py`,
  `outlook.py`, `narrow.py`), 1 neue Testdatei (CREATE).
- **Effort:** medium.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `output.renderers.email.helpers.format_trend_tokens()` | vorhanden, unverändert | Liefert `thunder_day_token`, `thunder_night_token`, `thunder_plain`, `thunder_day_origin` — alle nötigen Token bereits vorhanden |
| `_thunder_token_parts()` | vorhanden, **wandert nach `helpers.py`** | Zerlegt einen Token (`leicht@5(hoch@15)`) in (Wort, Stunde, Peak-Zusatz). Steht heute in `outlook.py:43`; mit dem dritten Verbraucher (`compact.py`) gehört sie neben `format_trend_tokens()`, das diese Token baut. **Nur die Definition wandert** — `outlook.py` importiert sie aus `helpers.py`, seine vier Aufrufstellen bleiben unverändert. Kein Cross-Modul-Import einer privaten Funktion aus einem Schwester-Renderer |
| `output.renderers.email.helpers._THUNDER_MAP["NONE"]["plain"]` | vorhanden, wiederverwendet | Explizites „kein Gewitter"-Label, wenn Stundenreihe im Tagesfenster leer ist |
| neues Modul: `output.renderers.email.thunder_branch` | NEU (diese Scheibe) | Trägt `resolve_thunder_day_branch()` (einmalige Zweigwahl day/none/plain) **und** das hierher verschobene `_thunder_token_parts()` samt `_THUNDER_TOKEN_RE`. Genutzt von `compact.py`, `outlook.py`, `narrow.py` |

**Zielort geändert gegenüber der freigegebenen Fassung (2026-08-14, Tech-Lead-Entscheid).**
Ursprünglich war `helpers.py` vorgesehen. Diese Datei war durch das Datei-Claim-Gate
von einer Parallel-Session belegt (verwaister Rest abgeschlossener #1801-Arbeit; die
Eigentümer-Session hat das schriftlich bestätigt, ein Zurücknehmen der Belegung ist
im Gate nicht vorgesehen, der Notausgang technisch aus einer laufenden Sitzung nicht
erreichbar). Statt eine Stunde auf den 4-Stunden-Verfall zu warten, liegen die
Funktionen nun in einem eigenen Modul — **kein AC ist davon berührt**, der Zielort
war reines Implementierungsdetail. Zwei Nebeneffekte, beide günstig: `helpers.py`
(ohnehin ein überladenes Sammelmodul) bleibt unverändert, und der zusätzliche
Compare-Mail-Nachweis entfällt (s. „Nachweis vor Commit").

## Am Code gemessen

Nachgemessen am Stand `e2b5269b` (== `origin/main`, 2026-08-14):

1. **`compact.py:230-236` liest ausschließlich `tok['thunder_plain']`.**
   Keine Tag/Nacht-Trennung, kein Zugriff auf `thunder_day_token`/
   `thunder_night_token`. Bestätigt die Kernbehauptung des Issues.

2. **Die Zweiglogik existiert bereits zweimal fast identisch:**
   `outlook.py:373-386` (`render_outlook_plain`) und `narrow.py:588-601`
   (`_outlook_lines`) prüfen in derselben Reihenfolge:
   (a) `tok.get("thunder_day_token", "-") != "-"` → Wort aus dem Tages-Token
   via `_thunder_token_parts()`; (b) sonst, wenn `stage.get("hourly_thunder")`
   gefüllt ist → explizites „kein Gewitter" (`_THUNDER_MAP["NONE"]["plain"]`,
   Stundenreihe da, im Tagesfenster aber leer); (c) sonst (keine Stundenreihe,
   Alt-Aufrufer/Compare) → `tok["thunder_plain"]` unverändert.

3. **`render_outlook_table()` (HTML-Zelle) hat eine strukturell andere
   Zweigwahl** (Z. 233-248: dritter Zweig fällt auf das rohe Aggregat-Level
   zurück statt auf `thunder_plain`, und es gibt keine explizite
   „kein Gewitter"-Textausgabe, nur ein leeres `day_part`). Sie wird daher
   **nicht** auf den neuen Entscheidungs-Helfer umgestellt — nur die beiden
   strukturell identischen Klartext-Zweige (`outlook.py` Klartext,
   `narrow.py`).

4. **Beide bestehenden Zweige hängen zusätzlich `tok.get("thunder_day_origin")`
   an, wenn Branch (a) greift** (`outlook.py:381-383`, `narrow.py:595-597`,
   aus #1680 S5a). Der neue Entscheidungs-Helfer entscheidet nur den Zweig
   (day/none/plain), NICHT ob die Herkunft angehängt wird — das bleibt
   Aufrufer-Formatierung. `compact.py` ruft die Herkunft **nicht** ab (s.
   „Vom PO entschieden", Punkt 1).

5. **Nachtformat in `outlook.py:398-401`:**
   `line += f" · nachts {_nm[0]} @{_nm[1]}{_nm[2]}"` — Leerzeichen vor `@`,
   Peak-Zusatz in Klammern falls vorhanden. Dies ist das Zielformat für die
   Kurzformat-Mail (PO-Entscheidung 2), nicht `narrow.py`s Variante
   (`f" · nachts {nt}"`, roher Token ohne Leerzeichen vor `@`).

6. **`compact.py`s ASCII-Faltung läuft NACH dem Zeilenbau:** `_ASCII_MAP`
   (Z. 49-54) übersetzt `⚡`→`T`, `·`→`-`, `–`→`-`; anschließend
   `fold_ascii()` faltet Umlaute (Z. 60-61). `_ascii()` wird auf die
   fertige Zeile angewendet (Z. 237: `lines.append(_ascii(line))`).
   Beispiel: `⚡leicht · nachts hoch @2` → `Tleicht - nachts hoch @2`.

7. **`renderer_mail_gate.py` stuft `helpers.py` als „geteilten Helfer" ein**
   (`_SHARED_HELPER_PATTERNS`, `.claude/hooks/renderer_mail_gate.py:76-78`):
   `src/output/renderers/email/(helpers|design_tokens|profile_signature)\.py$`.
   Da diese Scheibe `helpers.py` staged, verlangt das Gate **zusätzlich**
   zum Briefing-Nachweis (Matrix-Test + `briefing_mail_validator.py`) auch
   den **Compare**-Nachweis (`email_spec_validator.py`) — nicht nur, weil
   `compact.py` (Briefing-Pfad) betroffen ist, sondern weil der geteilte
   Helfer potenziell auch den Compare-Pfad berühren könnte. Das ist eine
   Ergänzung gegenüber dem ursprünglichen Auftrag, gemessen am Gate-Code
   selbst, nicht vermutet.

8. **`compact.py` zeigt heute keinen Hagel-Zusatz** in der Ausblick-Zeile
   (kein `_format_hail_note`/`format_hail_note`-Aufruf im gelesenen
   Ausschnitt Z. 227-238). Diese Scheibe führt keinen ein — reiner
   Tag/Nacht-Fix, kein Feature-Zuwachs (s. „Nicht in dieser Scheibe").

## Vom PO entschieden (2026-08-14) — gesetzt, nicht Teil der Freigabefrage

1. **Kein Herkunfts-Zusatz im Kurzformat.** `thunder_day_origin` wird NICHT
   gelesen. `feat_1680_s5a` AC-13 sichert zu, dass der Kompakt-Ausblick
   zeichengleich bleibt und keine der vier Zutat-Bezeichnungen nennt
   (PO-go 2026-08-13). Diese Zusicherung wird **nicht** abgelöst — der
   bestehende Wächter `tests/tdd/test_thunder_origin_outlook.py::test_ac13_kompaktmail_bleibt_zeichengleich`
   MUSS nach dieser Scheibe weiterhin grün sein. Die *Begründung* der
   Zusicherung („liest ohnehin nur `thunder_plain`") entfällt mit dieser
   Scheibe faktisch — die Zeile liest ab jetzt `thunder_day_token`/
   `thunder_night_token` — die *Zusicherung selbst* bleibt jedoch in Kraft:
   keine Herkunft in der Kurzformat-Mail. Eine Ablösung von AC-13 wäre ein
   eigenes Ticket.

   ⚠️ **Nachtrag 2026-08-18 — dieses Ticket ist #1493.** Der
   Zeichengleichheits-Teil von `feat_1680_s5a` AC-13 ist durch
   `docs/specs/modules/feat_1493_gewitter_onset_sichtbar.md` AC-4 abgelöst:
   der Kompakt-Ausblick trägt jetzt die Onset-Stunde im Tagesteil
   (`Tleicht@16`). Der oben festgehaltene PO-Entscheid selbst gilt
   unverändert weiter — **kein Herkunfts-Zusatz im Kurzformat**;
   `thunder_day_origin` wird in `_compact_thunder_field()` nach wie vor nicht
   gelesen und `test_ac13_kompaktmail_bleibt_zeichengleich` bleibt grün.
   Ursprünglicher Wortlaut zur Historie: „Diese Zusicherung wird **nicht**
   abgelöst … Eine Ablösung von AC-13 wäre ein eigenes Ticket."

2. **Darstellungsformat folgt der Klartext-Mail, nicht Telegram.**
   Tagesteil ohne Uhrzeit (Wort + optionaler Peak-Zusatz, wie
   `render_outlook_plain` Z. 373-383, aber ohne den Herkunfts-Zusatz aus
   Punkt 1), Nachtteil als Zusatz MIT Uhrzeit
   (`· nachts <stufe> @<h>[<peak>]`, identisch zu `outlook.py:398-401`).
   Die ACs formulieren die Erwartung an der **zugestellten, ASCII-
   gefalteten** Zeile (nach `_ascii()`), nicht an einem Zwischenstand.

3. **Geteilter Entscheidungs-Helfer statt viertem Duplikat.** Neue Funktion
   `resolve_thunder_day_branch(tok: dict, stage: dict) -> str` in
   `helpers.py`, Rückgabewerte `"day"` / `"none"` / `"plain"` — reine
   Zweigwahl, KEINE Formatierung. `compact.py`, `outlook.py`
   (`render_outlook_plain`) und `narrow.py` (`_outlook_lines`) rufen ihn
   auf; jeder Aufrufer formatiert das Ergebnis weiterhin selbst (Wort mit/
   ohne Uhrzeit, mit/ohne Herkunft, mit/ohne Emoji-Präfix). `render_outlook_table()`
   (HTML-Zelle) wird **nicht** umgestellt (s. „Am Code gemessen", Punkt 3).

## Implementation Details

### 1. Neuer Entscheidungs-Helfer (`helpers.py`)

```python
def resolve_thunder_day_branch(tok: dict, stage: dict) -> str:
    """Waehlt die Datenquelle fuer das Tages-Gewitterwort (#1671).

    Reine Zweigwahl, KEINE Formatierung -- die drei Aufrufer (compact.py,
    outlook.py Klartext, narrow.py) stellen das Ergebnis unterschiedlich
    dar, entscheiden aber identisch. Ersetzt die bis #1671 dreifach fast
    identisch kopierte if/elif-Kette.

    Returns:
        "day"   -- tok["thunder_day_token"] traegt einen Wert (!= "-"):
                   Wort+Uhrzeit aus dem Tagesfenster verwenden.
        "none"  -- Stundenreihe vorhanden, im Tagesfenster aber leer:
                   explizites "kein Gewitter" zeigen (_THUNDER_MAP["NONE"]).
        "plain" -- keine Stundenreihe (Alt-Aufrufer/Compare): auf das
                   ungefilterte 24h-Aggregat (tok["thunder_plain"]) zurueckfallen.
    """
    if tok.get("thunder_day_token", "-") != "-":
        return "day"
    if stage.get("hourly_thunder"):
        return "none"
    return "plain"
```

### 2. `compact.py` — Ausblick-Zeile umgestellt

Ersetzt `tok['thunder_plain']` (Z. 235) durch eine neue lokale
Formatierungsfunktion, die den Entscheidungs-Helfer nutzt:

```python
from output.renderers.email.helpers import (
    ..., resolve_thunder_day_branch, _thunder_token_parts,
)

def _compact_thunder_field(tok: dict, stage: dict) -> str:
    branch = resolve_thunder_day_branch(tok, stage)
    if branch == "day":
        _d = _thunder_token_parts(tok.get("thunder_day_token", "-"))
        field = f"⚡{_d[0]}{_d[2]}"  # Wort + Peak-Zusatz, KEINE Uhrzeit,
                                     # KEINE Herkunft (PO-Entscheidung 1)
    elif branch == "none":
        field = _THUNDER_MAP["NONE"]["plain"]
    else:
        field = tok["thunder_plain"]

    _n = _thunder_token_parts(tok.get("thunder_night_token", "-"))
    if _n:
        field += f" · nachts {_n[0]} @{_n[1]}{_n[2]}"
    return field
```

Aufruf in der Ausblick-Schleife (ersetzt Z. 235):

```python
thunder_field = _compact_thunder_field(tok, stage)
line = (
    f"{weekday:<3} {name:<26} {tok['temp_str']:<8} "
    f"{tok['precip_str']:<5} {tok['wind_str']:<5} {thunder_field}"
)
```

Die anschließende `_ascii(line)`-Faltung (unverändert) übersetzt `⚡`→`T`,
`·`→`-`: Beispielzeile `⚡leicht · nachts hoch @2` wird zu
`Tleicht - nachts hoch @2`.

### 3. `outlook.py` und `narrow.py` — Refactoring auf den Helfer

Die bestehenden if/elif-Ketten (`outlook.py:373-386`, `narrow.py:588-601`)
werden durch `branch = resolve_thunder_day_branch(tok, stage)` ersetzt; die
je-Kanal-Formatierung (mit/ohne Herkunft, mit/ohne `⚡`-Präfix) bleibt
unverändert. Byte-Parität zum heutigen Stand ist Pflicht (s. Testplan).

## Expected Behavior

- **Input:** `stage`-Dict wie bisher (`hourly_thunder`, optional
  `day_window_start_hour`/`day_window_end_hour`), `tok` = Ergebnis von
  `format_trend_tokens(stage)`.
- **Output:** Die Kurzformat-Mail-Ausblick-Zeile zeigt dieselbe
  Tagesfenster-Stufe wie HTML-Tabelle, Klartext-Mail und Telegram (statt
  des 24h-Aggregats), plus — neu für diesen Kanal — eine Nachtangabe mit
  Uhrzeit, falls vorhanden. Kein Herkunfts-Zusatz.
- **Side effects:** keine — reine Rendering-Funktionen, kein Netz-, kein
  DB-Zugriff.

## Acceptance Criteria

- **AC-1:** Given eine Etappe mit Tagesgewitter „leicht" um 16 Uhr
  innerhalb des Tagesfensters und einem 24h-Aggregat, das „NONE" zeigt
  (Fall: Aggregat und Tagesfenster widersprechen sich) / When die
  Kurzformat-Mail gerendert wird / Then zeigt die Ausblick-Zeile das
  Tagesgewitter „leicht" — nicht das leere Aggregat.

- **AC-2:** Given dieselbe Konstellation umgekehrt (Aggregat zeigt „HIGH",
  Tagesfenster ist leer, das Ereignis liegt vollständig in der Nacht) /
  When die Kurzformat-Mail gerendert wird / Then zeigt der Tagesteil der
  Zeile explizit „kein Gewitter" (ASCII-gefaltet: „T-" bzw. das gefaltete
  `_THUNDER_MAP["NONE"]["plain"]`), nicht das fälschlich übernommene
  Aggregat-„HIGH".

- **AC-3:** Given eine Etappe mit Tagesgewitter „mittel" 14 Uhr UND
  Nachtgewitter „hoch" 0 Uhr / When die Kurzformat-Mail gerendert wird /
  Then enthält die zugestellte, ASCII-gefaltete Zeile sowohl den Tagesteil
  als auch einen Nachtzusatz der Form `- nachts hoch @0` (Bindestrich statt
  `·` nach der Faltung) — eine Nachtangabe, die im Kompaktformat vor dieser
  Scheibe strukturell nie erschien.

- **AC-4:** Given eine Etappe ganz ohne Gewitter (Tag und Nacht `NONE`,
  Stundenreihe vorhanden) / When die Kurzformat-Mail gerendert wird / Then
  zeigt die Zeile das explizite „kein Gewitter"-Zeichen ohne Nachtzusatz —
  kein leerer oder abweichender Ausdruck.

- **AC-5:** Given eine Ausblick-Zeile ohne jede Stundenreihe (Alt-Fixture,
  `hourly_thunder` fehlt) / When die Kurzformat-Mail gerendert wird / Then
  bleibt die Ausgabe byte-identisch zum Stand vor dieser Änderung
  (Rückfall auf `thunder_plain`, Zweig „plain"). Referenz ist eine **vor der
  Implementierung aufgezeichnete** Soll-Zeile (Konstante im Test oder Datei
  unter `tests/fixtures/`), **nicht** ein zweiter Aufruf desselben Codes im
  selben Lauf — ein Vorher/Nachher-Vergleich innerhalb eines Laufs ändert
  sich mit dem Code mit und beweist nichts (Begründung wörtlich aus
  `tests/tdd/test_trip_outlook_parity.py`).

- **AC-6:** Given ein Trip-Briefing im Kompaktformat / When die Mail
  gerendert wird / Then enthält der Ausblick-Block **keine** der vier
  Zutat-Bezeichnungen (CAPE, Blitzdichte, Blitzpotenzial, Superzellen) —
  `thunder_day_origin` wird nicht gelesen. Der bestehende Wächter
  `tests/tdd/test_thunder_origin_outlook.py::test_ac13_kompaktmail_bleibt_zeichengleich`
  bleibt unverändert grün.

- **AC-7:** Given dieselben Gewitterdaten / When HTML-Ausblick-Tabelle UND
  Klartext-Ausblick der Trip-Vollmail (nicht die Kurzformat-Mail) gerendert
  werden / Then bleiben beide byte-identisch zum Stand vor dieser Scheibe —
  nachgewiesen über den unveränderten Bestandswächter
  `tests/tdd/test_trip_outlook_parity.py` samt seiner Golden-Dateien unter
  `tests/fixtures/outlook_trip_parity/`, die NICHT neu erzeugt werden.
  Der Telegram-Trendblock (`narrow.py`) bleibt in Inhalt und Format
  ebenfalls unverändert.

## Nicht in dieser Scheibe

- **Herkunfts-Zusatz im Kurzformat** — bewusste PO-Entscheidung 1, bleibt
  ausdrücklich draußen.
- **SMS / Premium-SMS** — erreichen den Ausblick baulich nicht
  (`SMSTripFormatter` sieht `multi_day_trend` nie, belegt in
  `feat_1680_s5a`, „Am Code gemessen" Punkt 6; hier nicht erneut
  hergeleitet, nur referenziert).
- **Compare-Ausblick** — teilt sich den `outlook.py`-Baustein, hat aber
  keine Stundenreihe (`hourly_thunder` fehlt im Compare-Pfad); der Zweig
  „plain" greift dort unverändert, kein Compare-spezifisches Verhalten
  wird eingeführt oder geändert.
- **Hagel-Zusatz in der Kurzformat-Mail** — existiert dort heute nicht und
  wird von dieser Scheibe nicht eingeführt (s. „Am Code gemessen",
  Punkt 8).
- **`render_outlook_table()` (HTML-Zelle)** — hat eine strukturell andere
  Zweigwahl (s. „Am Code gemessen", Punkt 3) und wird nicht auf den neuen
  Helfer umgestellt.
- **Der Metrik-Zweig des Trip-Ausblicks (#1841)** — nachgetragen 2026-08-14
  nach dem Rebase auf `2ceadc9d`: mit #1720 S1 (heute gemergt) hat der
  **Trip**-Ausblick einen zweiten Renderpfad bekommen. Ist eine
  Ausblick-Spaltenauswahl gesetzt, rendern HTML-Tabelle und Klartext die
  `row["cells"]` und überspringen den gesamten Token-Zeilenbau per
  `continue` (`outlook.py:155-162` bzw. `348-356`); die Gewitterstufe kommt
  dort aus `summary.thunder_level_max` — dem Gehzeit-Aggregat —, eine
  Nachtangabe existiert nicht. **Dieselbe Fehlerklasse, ein weiterer
  Ausgabeort**, als eigenes Issue **#1841** gebucht. Die Kurzformat-Mail
  kennt diesen Zweig nicht (`compact.py` liest keine `cells`), diese Scheibe
  bleibt davon unberührt. Die Aussage „die Klasse ist mit vier Ausgabeorten
  vollständig ausgezählt" im Kontext-Doc gilt für den Token-Pfad — der
  Metrik-Pfad ist eine fünfte Stelle, die dort noch nicht existierte.

## Testplan

Kern-Schicht, deterministisch, keine Mocks — echte Domänen-Objekte
(`stage`-Dicts wie in `_build_stage_trend()` produziert) und echte
Renderer-Aufrufe (`format_trend_tokens()` → `render_compact()` bzw. die
neue `_compact_thunder_field()`). Neue Testdatei nach Verhalten benannt:
`tests/tdd/test_kompaktmail_ausblick_tagesfenster.py` (NICHT nach
Issue-Nummer — `test_naming_gate.py` blockt issue-nummerierte
Testdateinamen beim Commit).

| AC | Test (mindestens) |
|---|---|
| AC-1 | `test_tagesgewitter_erscheint_trotz_leerem_24h_aggregat` — Fixture mit Tagesstunde „leicht", 24h-Aggregat „NONE"; prüft die von `render_compact()` zurückgegebene, ASCII-gefaltete Zeile |
| AC-2 | `test_kein_tagesgewitter_trotz_aggregat_high` — Fixture mit Tagesfenster leer, Nachtstunde „hoch"; Tagesteil zeigt explizit „kein Gewitter", nicht „HIGH" |
| AC-3 | `test_nachtgewitter_erscheint_mit_uhrzeit_im_kompaktformat` — Fall B (Tag „mittel" 14, Nacht „hoch" 0); geprüft wird die ZUGESTELLTE Zeile nach `_ascii()`, inkl. `- nachts hoch @0` |
| AC-4 | `test_kein_gewitter_tag_und_nacht_zeigt_explizites_none` |
| AC-5 | `test_ohne_stundenreihe_bleibt_kurzformat_unveraendert` — Alt-Fixture ohne `hourly_thunder`, Vergleich mit dem heutigen (Vor-Fix) Rendering-Ergebnis |
| AC-6 | Bestehender Test `tests/tdd/test_thunder_origin_outlook.py::test_ac13_kompaktmail_bleibt_zeichengleich` läuft unverändert grün; zusätzlich `test_kompaktmail_ohne_herkunfts_zusatz` mit Fixture, die im HTML-/Klartext-Pfad nachweislich eine Herkunft erzeugen WÜRDE (Gegenprobe, sonst vakuum-grün) |
| AC-7 | Bestehender `tests/tdd/test_trip_outlook_parity.py` läuft unverändert grün, Golden-Dateien unangetastet |

## Mutations-Gegenprobe

Jede Mutation nur per String-Ersetzung mit externer Sicherungskopie — nie
`git checkout`/`stash`/`reset`.

- **(a)** In `_compact_thunder_field()` den Branch-Aufruf durch
  `branch = "plain"` (fest verdrahtet) ersetzen → AC-1 und AC-2 müssen rot
  werden (das Tagesfenster-Wort verschwindet zugunsten des Aggregats).
- **(b)** Den Nachtzusatz-Block in `_compact_thunder_field()` entfernen →
  AC-3 muss rot werden.
- **(c)** `tok.get("thunder_day_origin")` zusätzlich an den `"day"`-Zweig
  von `_compact_thunder_field()` anhängen → AC-6 UND der bestehende
  `test_ac13_kompaktmail_bleibt_zeichengleich` müssen rot werden. **Diese
  Mutation prüft die Zusicherung an der Stelle, an der sie WIRKT** — der
  Test liest die von `render_compact()` zurückgegebene, ASCII-gefaltete
  Zeile, nicht `_compact_thunder_field()` isoliert; eine Prüfung, die nur
  die Helper-Funktion isoliert testet, würde die Mutation ebenfalls fangen,
  aber NICHT belegen, dass die Herkunft auch nicht in der zugestellten Mail
  landet (z. B. weil eine spätere ASCII-Faltung sie unbemerkt verschluckt
  oder ein zweiter Aufrufpfad existiert) — deshalb ist der Test auf
  `render_compact()`-Ebene Pflicht, nicht nur auf Helper-Ebene.
- **(d)** In `resolve_thunder_day_branch()` die Reihenfolge der Prüfungen
  vertauschen (`hourly_thunder`-Check vor dem `thunder_day_token`-Check) →
  AC-1 muss rot werden (eine gefüllte Stundenreihe mit leerem Tagesfenster,
  aber vorhandenem Nachtwert, würde fälschlich „none" statt „day" liefern,
  sobald der Tagesteil selbst einen Wert trägt — Testfixture mit beidem
  gleichzeitig gefüllt nötig).
- **(e)** Das Leerzeichen vor `@` im Nachtzusatz entfernen
  (`f" · nachts {_n[0]}@{_n[1]}{_n[2]}"` statt mit Leerzeichen) → AC-3 muss
  rot werden, WEIL der Test exakt den zugestellten Wortlaut prüft, nicht
  nur die Anwesenheit von „nachts" und der Stufe (Beleg, dass AC-3 nicht
  über eine zu grobe Teilstring-Prüfung vakuum-grün ist).

Kommt eine Mutation durch, ist das ein Finding, kein Nebenbefund.

## Nachweis vor Commit

`renderer_mail_gate.py` (#811, un-überspringbar) blockiert jeden Commit,
der eine Mail-Inhalts-Datei staged, bis die passenden Nachweise frisch
vorliegen. Diese Scheibe staged sowohl `compact.py` (Briefing-Pfad) als
auch `helpers.py` (als „geteilter Helfer" eingestuft, s. „Am Code
gemessen", Punkt 7). Damit sind **beide** Nachweisstränge fällig:

1. **Briefing-Nachweis** (wegen `compact.py`): frischer Lauf von
   `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` (grün) UND ein
   erfolgreicher `uv run python3 .claude/hooks/briefing_mail_validator.py`-
   Lauf gegen eine echt zugestellte Staging-Mail im Kurzformat
   (`X-GZ-Format: compact`).
2. ~~**Compare-Nachweis** (wegen `helpers.py`, Shared-Helper-Muster)~~ —
   **entfällt** (2026-08-14): `helpers.py` wird nicht mehr angefasst, s.
   „Zielort geändert" unter Dependencies. Am Gate-Code nachgemessen:
   `_SHARED_HELPER_PATTERNS` (`renderer_mail_gate.py:76-78`) nennt
   ausschließlich `helpers|design_tokens|profile_signature` — das neue Modul
   `thunder_branch.py` matcht dort **nicht**. Es matcht aber sehr wohl das
   breite Mail-Inhalts-Muster `src/output/renderers/email/.*\.py$`
   (`renderer_mail_gate.py:43`), der Briefing-Nachweis aus Punkt 1 bleibt
   also fällig — er war es über `compact.py` ohnehin.

Beide Läufe nur bei Exit 0 als „E2E bestanden" verbuchen — kein Mock, kein
Gmail, gegen Stalwart-Test-Postfach (`GZ_IMAP_*`).

## Known Limitations

- Der neue Entscheidungs-Helfer `resolve_thunder_day_branch()` entscheidet
  ausschließlich den Zweig, nicht die Formatierung — bei einer künftigen
  vierten Darstellungsvariante ist weiterhin je-Kanal-Code nötig, nur die
  Zweigwahl selbst dedupliziert.
- `render_outlook_table()` (HTML-Zelle) bleibt bei ihrer eigenen,
  strukturell abweichenden Zweigwahl (s. „Am Code gemessen", Punkt 3) —
  keine vollständige Vereinheitlichung aller vier Ausgabeorte, nur der
  beiden Klartext-artigen (Kurzformat, Klartext-Mail) plus Telegram.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — reine Rendering-/Konsistenz-Korrektur analog
  #1653, keine neue Grundsatzentscheidung.
- **Rationale:** Die Umstellung der Kurzformat-Mail auf dieselbe
  Tagesfenster-Quelle wie die drei anderen Kanäle ist eine Bugfix-Angleichung
  an ein bereits etabliertes Muster (#1653), keine neue Architektur-
  Entscheidung.

## Offene Punkte für den PO

Keine — die drei PO-Entscheidungen aus dem Auftrag sind vollständig in
diese Spec übernommen. Einzige Ergänzung gegenüber dem ursprünglichen
Auftrag ist eine am Gate-Code gemessene Tatsache (s. „Am Code gemessen",
Punkt 7): weil `helpers.py` als geteilter Baustein angefasst wird, verlangt
`renderer_mail_gate.py` zusätzlich zum Briefing-Nachweis auch den
Compare-Nachweis (`email_spec_validator.py`). Das ist keine
Entscheidungsfrage, sondern eine Pflicht des bestehenden, un-
überspringbaren Gates — hier zur Kenntnis, nicht zur Freigabe.

## Changelog

- 2026-08-14: Initial spec created
