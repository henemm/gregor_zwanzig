---
entity_id: fix_1491_gewitter_ampelkreis
type: bugfix
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [gewitter, mail, ampel, renderer, issue-1491, issue-1474, issue-1419]
---

# Gewitter-Spalte wird eine reguläre Ampel-Spalte — der Widerspruch in der Stundentabelle verschwindet (Issue #1491)

## Approval

- [x] Approved — PO-Freigabe („go") 2026-08-04

## Purpose

In derselben Briefing-Mail meldeten Kurzfassung und Prosa-Satz ein Gewitter, während die
Stundentabelle für dieselbe Stunde einen Strich zeigte. Ursache: `fmt_val()`
(`src/output/renderers/email/helpers.py:618-635`) kennt im `thunder`-Zweig nur die Stufen
`MED` und `HIGH` und behandelt die mit #1474 eingeführte Stufe `LOW` wie `NONE`. Diese
Arbeit schließt die Lücke nicht additiv, sondern macht die Gewitter-Spalte zu einer
regulären Ampel-Spalte wie Wind, Böen, Regen, Regenwahrscheinlichkeit und CAPE — mit
Ampel-Kreis (einfache Ansicht) bzw. Wort (Text-Fassung) für alle vier Stufen.

## Source

- **File:** `src/output/metric_format.py`, `src/output/renderers/email/helpers.py`,
  `src/output/renderers/email/html.py`, `src/output/renderers/email/compare_html.py`
- **Identifier:** `fmt_val()` (Zweig `thunder`), `_thunder_risk_level()`, `_THUNDER_SEV`,
  neue Funktion `thunder_ampel_band()` (Name vorgeschlagen, Python-Core)

**Schicht:** ausschließlich Python-Core (`src/output/`). Kein Go, kein Frontend — das
Frontend wird in #1488 separat behandelt (dieselbe Stufen-Verschiebung, aber dort geht es
um die Oberfläche, nicht um die Mail).

## Estimated Scope

- **LoC:** ~+80/−30
- **Files:** 4 Produktivdateien geändert, 2 Testdateien (1 geändert, 1 neu)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` | Vorgänger-Spec | führt `ThunderLevel.LOW` ein — Ursache der Lücke, die hier geschlossen wird |
| `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md` | bindende Vorgabe | Gewitter-Skala und -Fensterung leben zentral, nicht je Renderer dupliziert |
| `_ampel_dot_css` / `_AMPEL_DOT_COLORS` (`helpers.py:483-497`) | wiederzuverwenden | fertiger CSS-Kreis für die vier Ampelfarben green/yellow/orange/red |
| `severity_for` / `severity_from_thresholds` (`metric_format.py:107/118`) | Vorbild, nicht direkt nutzbar | erwarten eine Zahl + Katalog-Schwellen; Gewitter liefert eine Stufe — braucht eine eigene Zuordnung nach demselben Muster |
| `THUNDER_LABEL_DE` (`metric_format.py`) | wiederzuverwenden | liefert die vier deutschen Wörter kein/leicht/mittel/hoch für die Text-Fassung |
| `_thunder_risk_level()` (`html.py:155-186`) | zu ersetzende Altlogik | kennt heute nur zwei Warnstufen (risk/watch) für Zell-Tönung — LOW und MED erhalten identische orange Tönung |
| `_THUNDER_SEV` (`compare_html.py:174`) | teilt künftig die Ordnung | eigenes Wörterbuch `{LOW:"caution", MED:"warn", HIGH:"danger"}`, beschreibt dieselbe Ordnung wie die neue Trip-Zuordnung unter anderen Namen |
| `tests/tdd/test_issue_811_mode_matrix.py` | Bestandsschutz | prüft `fmt_val`-Zweig `thunder` über echtes Rendern für `MED`/`HIGH`/`NONE` — **kein Fall für `LOW`**, deshalb ist die Lücke durchgerutscht |
| Renderer-Mail-Gate #811 | Commit-Gate | blockiert Commits, die `email/helpers.py`/`html.py` verändern, bis Modus-Matrix-Test und `briefing_mail_validator.py` frisch grün gelaufen sind |

## Problem (gemessen)

| Stelle in der Mail | liest | Verhalten bei Stufe „leicht" (`LOW`) |
|---|---|---|
| Kurzfassung (Etappenzeile) | `dp.thunder_level != NONE` | meldet „⚡ möglich" |
| Prosa-Pille | `dp.thunder_level` + `thunder_ordinal()` | meldet „Gewitter ab …" |
| Stundentabelle, Spalte `Thdr` | `dp.thunder_level` → `fmt_val()` | zeigt „–" (Symbol-Modus) bzw. „kein" (Roh-Modus) |

Die Zelle war dabei bereits orange eingefärbt (`_thunder_risk_level` kennt `LOW` bei der
Tönung korrekt) — nur ihr Inhalt blieb leer. Eine orange Warnzelle mit einem Strich darin
ist der Widerspruch in Reinform.

## Was gebaut wird

Die Gewitter-Spalte der Stundentabelle wird eine **reguläre Ampel-Spalte**:

| Stufe | Einfache Ansicht (HTML) | Text-Fassung (Klartext-Mail, schmale Darstellung) |
|---|---|---|
| kein (`NONE`) | grüner Ampel-Kreis | `kein` |
| leicht (`LOW`) | gelber Ampel-Kreis | `leicht` |
| mittel (`MED`) | oranger Ampel-Kreis | `mittel` |
| hoch (`HIGH`) | roter Ampel-Kreis | `hoch` |

Blitz-Symbole (`⚡`, `⚡⚡`) und das Wort `mögl.` entfallen aus dieser Spalte. `mögl.` ist ein
Wort der Wahrscheinlichkeits-Achse, eingesetzt für eine Stärke-Stufe — die beiden Achsen
dürfen nicht vermischt werden (#1419, siehe auch Known Limitations).

**Fehlender Wert bleibt ein Strich.** Liegt gar keine Gewitterstufe vor (`dp.thunder_level
is None`), zeigt die Zelle weiterhin `–` — nie einen grünen Kreis. „Keine Aussage" ist
nicht „keine Gefahr" (dieselbe Sicherheitsinvariante wie bei anderen Metriken, z. B. #1328).

**Zell-Tönung und Kreis kommen aus EINER Quelle** (Regel aus #888: Punkt und Tönung aus
derselben Quelle). Die neue Stufe→Ampelband-Zuordnung wohnt in `src/output/metric_format.py`
— dort wohnt bereits die Gewitter-Skala (ADR-0025) — statt als Sonderlogik im Renderer. Der
Ortsvergleich hat mit `_THUNDER_SEV` bereits eine zweite, parallele Zuordnung derselben
Ordnung unter anderen Namen (`caution`/`warn`/`danger` statt `yellow`/`orange`/`red`); diese
soll ihre Reihenfolge künftig aus der neuen geteilten Stelle beziehen statt aus einem
eigenen Wörterbuch (Trip/Ortsvergleich-Teilungsvorgabe, CLAUDE.md).

**Im Ortsvergleich gibt es keinen Fehler** — die Stufe „leicht" wird dort bereits korrekt
angezeigt. Sein Aussehen (Label „leicht", Ampel-Einstufung `caution`) bleibt in dieser
Arbeit unangetastet; nur die Herkunft der Ordnung wird auf die geteilte Stelle umgestellt.

## Implementation Details

```
metric_format.py:
  neue Funktion, z.B. thunder_ampel_band(level: Optional[ThunderLevel]) -> Optional[str]
    None            -> None   (keine Aussage -- Aufrufer zeigt "-")
    ThunderLevel.NONE -> "green"
    ThunderLevel.LOW  -> "yellow"
    ThunderLevel.MED  -> "orange"
    ThunderLevel.HIGH -> "red"

email/helpers.py, fmt_val(), Zweig "thunder":
  mode == "raw"  -> THUNDER_LABEL_DE[val] wenn val gesetzt, sonst "-"
  sonst (html)   -> band = thunder_ampel_band(val); "-" wenn band None,
                    sonst _ampel_dot_css(band) (bestehender Baustein, kennt
                    bereits green/yellow/orange/red)

email/html.py, Zell-Toenung (ersetzt den "thunder"-Sonderzweig um Zeile 787):
  cell_bg = _AMPEL_CELL_BG.get(thunder_ampel_band(raw_val))
  (dieselbe {"yellow":..,"orange":..,"red":..}-Palette wie die anderen
  Ampel-Spalten; "green" bleibt ungetoent, wie bei den anderen Metriken auch)

email/compare_html.py, _THUNDER_SEV:
  Werte aus thunder_ampel_band() ableiten statt hartcodiert, z.B. ueber eine
  kleine lokale Uebersetzungstabelle band -> compare-eigenes Vokabular
  (green->ok, yellow->caution, orange->warn, red->danger) -- Aussehen des
  Ortsvergleichs bleibt dadurch unveraendert.
```

Die genaue Funktionssignatur/-benennung ist ein Implementierungsdetail des Developer-Agents
und kein Freigabegegenstand dieser Spec — bindend sind die Zuordnung (Tabelle oben) und
„eine Quelle für Kreis und Tönung, eine Quelle für Trip und Ortsvergleich".

## Expected Behavior

- **Input:** ein gerenderter Trip-Report (E-Mail voll/kompakt, Klartext-Teil, schmale
  Darstellung) mit einer Stundenreihe, die alle vier `ThunderLevel`-Stufen sowie `None`
  enthält.
- **Output:** Stundentabelle zeigt je Stufe den passenden Ampel-Kreis bzw. das passende
  Wort; `None` bleibt `–`; keine Stelle der Mail widerspricht einer anderen für dieselbe
  Stunde.
- **Side effects:** keine — reine Formatierungsänderung, `dp.thunder_level` selbst wird
  nicht verändert.

## Acceptance Criteria

- **AC-1 (wichtigstes AC — fehlender Wert bleibt ein Strich, wird NIEMALS zu „kein
  Gewitter"):** Given eine Stunde ohne jede Gewitteraussage (`dp.thunder_level is None`) /
  When die Briefing-Mail (einfache HTML-Ansicht) gerendert wird / Then zeigt die
  Stundentabelle für diese Stunde in der Gewitter-Spalte einen Strich (`–`) — **niemals**
  einen grünen Ampel-Kreis. „Keine Aussage" darf nirgends wie „keine Gefahr" aussehen.
  - Test: eine Mail mit einer Stunde `thunder_level=None` echt rendern (kein Netz), die
    Gewitter-Zelle dieser Stunde auf Strich prüfen und explizit ausschließen, dass dort ein
    grüner Kreis steht.

- **AC-2 (ruhige Stunde zeigt grünen Kreis statt Strich):** Given eine Stunde mit geprüfter
  Entwarnung (`dp.thunder_level == ThunderLevel.NONE`) / When dieselbe Mail gerendert wird /
  Then zeigt die Gewitter-Spalte für diese Stunde einen grünen Ampel-Kreis — nicht mehr den
  bisherigen Strich.
  - Test: dieselbe gerenderte Mail, Zelle einer `NONE`-Stunde auf grünen Kreis geprüft,
    unterscheidbar von der Strich-Zelle aus AC-1 (Gegenprobe: AC-1 und AC-2 dürfen nicht
    dasselbe Ergebnis liefern).

- **AC-3 (alle vier Stufen als Ampel-Kreis, kein Blitzsymbol mehr):** Given vier Stunden mit
  je einer der Stufen kein/leicht/mittel/hoch / When die Mail gerendert wird / Then zeigt
  jede Stunde den zugehörigen Ampel-Kreis (grün/gelb/orange/rot) in der Gewitter-Spalte, und
  in keiner der vier Zellen erscheint ein Blitzsymbol (`⚡`) oder das Wort `mögl.`.
  - Test: vier gerenderte Zellen (eine je Stufe) auf die jeweilige Kreisfarbe geprüft, plus
    Abwesenheitsprüfung von `⚡` und `mögl.` in der Gewitter-Spalte.

- **AC-4 (Text-Fassung zeigt die vier Wörter, keine Blitzsymbole, kein „mögl."):** Given
  dieselben vier Stufen / When der Klartext-Teil der Mail bzw. die schmale Darstellung
  gerendert wird / Then steht in der Gewitter-Spalte das jeweilige Wort `kein`/`leicht`/
  `mittel`/`hoch`, nirgends ein Blitzsymbol oder `mögl.`.
  - Test: Klartext-Rendering für alle vier Stufen, Wortsuche in der Gewitter-Spalte je
    Stufe, Abwesenheitsprüfung von `⚡`/`mögl.`.

- **AC-5 (Zell-Tönung widerspricht dem Kreis nie mehr):** Given eine Stunde mit Stufe
  `LOW` und eine mit Stufe `MED` / When die HTML-Mail gerendert wird / Then hat die
  `LOW`-Zelle eine andere Hintergrundfarbe als die `MED`-Zelle (gelb-Ton vs. orange-Ton) —
  die beiden Stufen sind nicht mehr farblich ununterscheidbar getönt.
  - Test: Hintergrundfarbe der `LOW`- und der `MED`-Zelle aus dem gerenderten HTML
    extrahieren und auf Ungleichheit prüfen (bisher: beide identisch orange).

- **AC-6 (Widerspruchsfreiheit an der ganzen gerenderten Mail — der eigentliche Bug):**
  Given eine Etappe, deren einzige Gewitterstunde `LOW` trägt (Kurzfassung und Prosa-Pille
  melden dadurch ein Gewitter für diese Stunde) / When die vollständige Briefing-Mail
  gerendert wird / Then meldet die Stundentabelle für exakt dieselbe Stunde NICHT `–`/`kein`
  — sie zeigt den gelben Ampel-Kreis bzw. das Wort `leicht`, konsistent mit Kurzfassung und
  Prosa-Pille.
  - Test: vollständige Mail rendern, für die betroffene Stunde parallel prüfen: Kurzfassung
    erwähnt ein Gewitter UND die Stundentabellen-Zelle derselben Stunde zeigt NICHT `–`.
    Genau dieser kombinierte Test hätte den ursprünglichen Bug gefangen — ein isolierter
    Aufruf des Zellformatierers allein hätte das nicht getan.

- **AC-7 (Ortsvergleich: unverändertes Aussehen, geteilte Herkunft):** Given eine
  Ortsvergleich-Mail mit den Stufen leicht/mittel/hoch / When sie gerendert wird / Then
  zeigt sie exakt dieselben Wörter **und dieselben Zell-Tönungsfarben** wie vor dieser
  Änderung — kein am gerenderten Ergebnis ablesbarer Unterschied zum bisherigen
  Ortsvergleich.
  - Test: Ortsvergleich-Mail für alle drei Stufen rendern, sichtbares Wort und
    Zell-Hintergrundfarbe gegen die bisherigen Werte prüfen (`leicht`/`#fbeeb8`,
    `mittel`/`#fad6b8`, `hoch`/`#f6c5bf`).
  - *Korrigiert 2026-08-04 nach Adversary-Finding F003 und unabhängiger Spec-Prüfung:* Die
    ursprüngliche Fassung verlangte, dass intern weiterhin die Wörter `caution`/`warn`/
    `danger` geführt werden. Die stehen nirgends in der gerenderten Mail und sind damit von
    außen nicht prüfbar — ein AC muss die **Wirkung** prüfen, nicht die Innenbezeichnung.
    Der Test tat von Anfang an das Richtige; nur der AC-Text hinkte hinterher.

## Nachtrag aus der Umsetzung (2026-08-04)

**Eine fünfte Produktivdatei kam dazu: `src/output/renderers/narrow.py`.**

Der Adversary-Lauf und die anschließende Messung deckten auf, dass die Umstellung der
Text-Fassung eine **falsche Entwarnung** erzeugte: `fmt_val()` wird auch von der
Telegram-Kurzübersicht benutzt, und dort bedeutete der bisherige Strich „keine Aussage".
Nach der Umstellung stand dort `kein` — eine Entwarnung, die niemand gegeben hat
(dieselbe Fehlerklasse wie #1328). Isoliert per A/B gegen `c31f777c` belegt an
`test_sms_daywindow_aggregation.py` und zwei Tests aus
`test_notification_service.py::TestComputeHasGapRealSendPath`.

Behoben in `_overview_line()`: bei „schlimmster beobachteter Wert ist `NONE` **und**
Datenlücke" steht `?` statt `kein` — nach dem bereits vorhandenen Muster der Fußzeile
(`_tg_day_footer`, `narrow.py:242-248`), kein neu erfundener Mechanismus.

Die Änderung ist von AC-1 gedeckt („keine Aussage" darf nie wie „keine Gefahr"
aussehen), war in der ursprünglichen Dateiliste aber nicht vorhergesehen.

**Ebenfalls nachgezogen (Testebene, keine Verhaltensänderung):** zehn gespeicherte
Muster-Mails unter `tests/golden/email/` sowie veraltete Erwartungen in
`test_thunder_risk_dot_and_tint.py`, `test_trip_report_formatter_v2.py`,
`test_ampel_css_dots.py` und `test_issue_1001_telegram_bubbles.py`. Die Muster-Mails
wurden nach dem Erneuern maschinell gegengeprüft: außerhalb der Gewitter-Zelle sind sie
zeichengleich.

## Nachtrag 2 — drei CI-Wächter nach dem Prod-Deploy (2026-08-04, Commit `99da3131`)

Drei Wächter liefen durch den #1196-Ratschen-Ausbau **erstmals auf CI** und schlugen erst
**nach** der Auslieferung an. Alle drei per A/B gegen `c31f777c` gemessen: gegen den
Ausgangsstand grün, mit dieser Arbeit rot — also echte Rückschritte.

**1. Der Ortsvergleich war doch nicht unverändert (AC-7 verletzt).**
`compare_html._sev_thunder(ThunderLevel.NONE)` lieferte `'ok'` statt `None`. Vorher hatte
`_THUNDER_SEV` schlicht **keinen** `NONE`-Eintrag, `.get()` gab `None` → keine Markierung.
Über die neue geteilte Zuordnung lief `NONE` → `"green"` → `"ok"`, wodurch **jede ruhige
Vergleichszelle** eine grüne Markierung bekommen hätte.

🔴 **Warum es niemand fand:** Adversary, Spec-Prüfung und der AC-7-Test prüften alle nur
`leicht`/`mittel`/`hoch`. Den mit Abstand **häufigsten** Fall — „kein Gewitter" — prüfte
keiner. Ein AC, das nur die Ausnahmefälle abdeckt, deckt das Normalverhalten nicht ab.

**Festlegung, damit sie nicht wieder verlorengeht:** Die Stundentabelle des Trips zeigt bei
„kein Gewitter" einen **grünen Kreis** (PO-Entscheidung, s.o. AC-2); der Ortsvergleich lässt
dieselbe Stufe **unmarkiert**. Das ist eine bewusste Unterscheidung, kein Versehen, und
steht als Kommentar an der Stelle im Code.

**2. Gefahren-Zelle konnte ihren Warnhintergrund verlieren (#911 AC-10).**
Trägt eine Zeile statt der Stufe einen **Zahlenwert** (#1425), lieferte
`thunder_ampel_band()` `None` → gar kein Hintergrund. Der alte Zweig hatte über
`_thunder_risk_level()` einen Zahlen-Rückfall (`> 20` → rot). Eine Gefahren-Zelle ohne
Warnfarbe verletzt das Design-Leitprinzip „Kontrast vor Optik". Der Zweig unterscheidet
jetzt Stufe (vierstufig) von Zahl (bisheriger Rückfall) — **ein** Dispatch.

**3. Golden-Wächter kannte die alten Prüfsummen.**
`test_compare_hourly_trip_parity.GOLDEN_HASHES` auf die berechtigt erneuerten Muster-Mails
nachgezogen, mit Datum und Grund im Kommentar. Der Wächter bleibt scharf. Vor dem
Nachziehen zeichenweise geprüft: in allen zehn Dateien weicht **ausschließlich** die
`Thdr`-Spalte ab.

**Lehre für den nächsten Umbau einer Darstellungsskala:** Der Normalfall („nichts los")
gehört genauso in die Prüfung wie die Warnfälle — er ist der Fall, den der Nutzer fast
immer sieht.

## Known Limitations

- **Frontend nicht Teil dieser Arbeit.** #1488 behandelt dieselbe Stufen-Verschiebung in der
  Oberfläche — eigenes Ticket.
- **SMS unverändert.** Gemessen: kennt `LOW` bereits korrekt, ist von dieser Arbeit nicht
  betroffen.
- ⚠️ **Telegram doch betroffen — Korrektur dieser ursprünglichen Annahme.** Die erste Fassung
  behauptete hier „Telegram-Kurzformen unverändert". Das war falsch: die Telegram-Kurzübersicht
  benutzt denselben Zellformatierer und hätte durch diese Arbeit eine **falsche Entwarnung**
  bekommen. Siehe „Nachtrag aus der Umsetzung" — der Eingriff in `narrow.py` repariert
  Schaden, den diese Arbeit sonst angerichtet hätte, und ist damit von AC-1 gedeckt. Er ist
  kein Zusatzwunsch und keine Erweiterung des Funktionsumfangs.
- **Übersichts-Matrix des Ortsvergleichs bleibt optisch unverändert** — nur die interne
  Herkunft der Ampel-Ordnung wird geteilt, keine sichtbare Umgestaltung.
- **AC-7 ist strenger formuliert als prüfbar** (Adversary-Finding F003): Der AC verlangt
  wörtlich, dass der Ortsvergleich intern weiterhin `caution`/`warn`/`danger` führt. Diese
  internen Wörter sind von außen nicht beobachtbar — eine Vertauschung `caution`↔`warn`
  bliebe unentdeckt, weil am Ende nur die Farbe zählt. Geprüft und belegt ist deshalb das
  **beobachtbare** Verhalten (Label + Farbe unverändert). Kein Implementierungsmangel; der
  AC hätte von vornherein auf die Wirkung statt auf die Innenbezeichnung zielen müssen.
- **Widerspruch zwischen Telegram-Kurzübersicht und Fußzeile bleibt** (Adversary-Finding
  F004): Beide rechnen über verschiedene Zeiträume — Kurzübersicht nur Gehzeit, Fußzeile
  Tagesfenster inklusive `night_weather`. Ein Gewitter nach der Ankunft erzeugt dadurch
  „⚡ ?" über „⚡ leicht" in derselben Nachricht. Strukturell seit #1001, durch diese Arbeit
  **entschärft** (vorher stand dort fälschlich „kein"), nicht verursacht. PO-Entscheidung
  2026-08-04: eigenes Ticket → **#1498**.
- **Die Erwähnungsschwelle wird nicht angefasst.** Der Prosa-Satz „Gewitter ab HH:00"
  feuert seit #1474b ab Stufe „leicht" (`helpers.py:1573-1588`, Schwelle aus derselben
  Trip-Einstellung wie SMS/Telegram, Vorgabewert 1.0 = „ab leicht") — genau deshalb
  entstand der gemeldete Widerspruch. Diese Arbeit ändert nur, WIE die Stundentabelle eine
  bereits vorliegende Stufe darstellt, nicht ab WELCHER Stufe eine Aussage gemacht wird.
  Wer die Schwelle verschieben will, dreht am Regler aus #1474b — nicht hier.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Arbeit bewegt sich innerhalb ADR-0025 (Gewitter-Skala lebt zentral in
  `metric_format.py`, gilt für alle Briefing-Kanäle) und wendet die bestehende
  Trip/Ortsvergleich-Teilungsvorgabe (CLAUDE.md) auf eine bereits vorhandene, doppelt
  geführte Zuordnung an (`_THUNDER_SEV` vs. die neue Trip-Zuordnung). Kein neuer
  Architektur-Entscheidungsraum.

## Changelog

- 2026-08-04: Initial spec created (Issue #1491).
