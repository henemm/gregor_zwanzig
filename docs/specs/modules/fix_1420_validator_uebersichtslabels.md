---
entity_id: fix_1420_validator_uebersichtslabels
type: bugfix
created: 2026-07-29
updated: 2026-07-29
status: draft
workflow: fix-1420-validator-uebersichtslabels
version: "1.0"
tags: [compare, mail-validator, gate, metric-catalog, naming, trip-compare-sharing]
---

# Fix #1420: Der Pflicht-Prüfer der Übersichtstabelle übersteht die A2b-Umbenennung

## Approval

- [x] Approved — PO Henning, 2026-07-29 („Go"): die sieben Acceptance
  Criteria und das für diese Lieferung einmalig angehobene Zeilen-Limit
  (Schätzung ~227-313 gegen einen Deckel von 250; Präzedenz #1404).

## Purpose

Der Pflicht-Prüfer für die Ortsvergleichs-Mail (`.claude/hooks/email_spec_validator.py`)
kennt in `_OVERVIEW_METRIC_CHECKS` heute nur die 24 numerisch prüfbaren
Übersichtstabellen-Zeilen in ihrer **heutigen deutschen** Beschriftung. #1401
Scheibe A2b stellt alle 26 Metrik-Zeilen auf die englische Kurzform aus dem
zentralen Namensregister um (`col_label`). Ohne Vorarbeit würden mit A2b 24 der
24 Plausibilitäts-/Format-Prüfungen sofort wieder lautlos in den stillen
`continue`-Pfad zurückfallen — exakt die Lücke, die #1404 gerade erst für die
Stundentabelle geschlossen hat, nur diesmal für die Übersichtstabelle. Diese
Lieferung erweitert `_OVERVIEW_METRIC_CHECKS` und `_OVERVIEW_NO_CHECK_LABELS`
additiv auf Alt∪Neu — Muster `_HOUR_COLUMNS_V2` aus #1404 — und schließt damit
`tests/unit/test_compare_mail_overview_plausibility_coverage.py::test_ac4_*`
vor der A2b-Umstellung ab, statt danach rot zu werden.

Direkte Fortsetzung von #1404 (Vorbedingung war dort bereits als offene
Known-Limitation für die Übersichtstabelle vermerkt), selbst Vorbedingung für
#1401 Scheibe A2b: A2b kann seinen eigenen Commit nicht abschließen, solange
der unveränderte Validator die dann korrekte Mail für 24 Zeilen unbemerkt
lautlos durchwinkt, statt sie zu prüfen (Renderer-Commit-Gate #811 verlangt
für `compare_html.py` einen erfolgreichen `email_spec_validator.py`-Lauf,
aber der stille `continue`-Pfad meldet dabei nie einen Fehler — das eigentliche
Risiko ist hier nicht ein blockierter A2b-Commit, sondern ein A2b-Commit, der
unbemerkt 24 Plausibilitätsprüfungen wieder abschaltet).

## Source

- **File:** `.claude/hooks/email_spec_validator.py`
- **Identifier:** `_OVERVIEW_METRIC_CHECKS` (Zeilen 576-613),
  `_OVERVIEW_NO_CHECK_LABELS` (Zeilen 615-637), Verwendung in
  `validate_plausibility()` (Zeilen 841-873) und `validate_format()`
  (Zeilen 876-903)

> **Schicht-Hinweis:** Kein Produktcode einer der drei Laufzeit-Schichten
> (Frontend/Go-API/Python-Core). `.claude/hooks/email_spec_validator.py` ist
> dasselbe Pflicht-Gate-Skript wie bei #1404, das der Renderer-Commit-Gate
> (#811, `.claude/hooks/renderer_mail_gate.py`) für den Compare-Mailpfad als
> Nachweisquelle verlangt. Betroffen ist ausschließlich dieses Skript sowie
> seine Testabdeckung — keine Datei unter `src/`, `internal/`, `frontend/`.

## Ausgangslage (gemessen)

| Menge | Heute (nach #1404) | Nach dieser Lieferung |
|---|---|---|
| `_OVERVIEW_METRIC_CHECKS` (geprüfte Labels) | 24 (nur heutige deutsche Beschriftung) | 46 (24 heutige + 20 A2b-Umbenennungen + 2 Kollisionsformen `"Temp"`/`"Feels"`) |
| `_OVERVIEW_NO_CHECK_LABELS` (ausgesprochene Ausnahmen) | 3 (`Amtliche Warnungen`, `Gewitter`, `Niederschlagsart`) | 5 (zusätzlich `Thdr`, `PType`) |
| Zeilen von `CV2_METRICS` (tatsächlich, unverändert) | 27 | 27 (unverändert — diese Lieferung fasst `compare_html.py` nicht an) |

Die Union ist damit — wie schon `_HOUR_COLUMNS_V2` bei #1404 — eine
**Übergangs-Allowlist**, die größer ist als die heute tatsächlich existierende
Zeilenmenge. Das hat eine unmittelbare Konsequenz für den bestehenden
Vollständigkeits-Test (`test_ac4_exemption_set_is_declared_and_complete`),
s. „Der heikelste Punkt" unten.

## Ziel-Abbildung (aus `fix_1401_a2_mailtabellen.md`, „Ziel-Beschriftung je
Zeile", PO-freigegeben 2026-07-28) — Regex/Bereich unverändert vom alten
Eintrag übernommen

| Alte Beschriftung | Neue Beschriftung | Format-Regex (unverändert) | Wertebereich (unverändert) |
|---|---|---|---|
| Sonne | Sun | `^\d+\.\d h$` | 0–24 |
| Wolken | Cloud | `^\d+%$` | 0–100 |
| UV max | UV | `^\d+$` | 0–16 |
| Regen | Rain | `^\d+\.\d mm$` | 0–300 |
| Regenwahrscheinlichkeit | Rain% | `^\d+%$` | 0–100 |
| Sicht min | Visib | `^\d+\.\d km$` | 0–100 |
| Schneehöhe | SnowH | `^\d+ cm$` | 0–1000 |
| Neuschnee | NewSn | `^\d+ cm$` | 0–300 |
| Böen | Gust | `^\d+ km/h$` | 0–300 |
| Nullgradgrenze | 0°Line | `^\d+ m$` | 0–6000 |
| Windrichtung | WDir | `^\d+ °$` | 0–360 |
| Gefühlte Temp. min | Feels min | `^-?\d+°C$` | -50–50 |
| Gefühlte Temp. max | Feels max | `^-?\d+°C$` | -50–55 |
| Wolken tief | CldLow | `^\d+%$` | 0–100 |
| Wolken mittel | CldMid | `^\d+%$` | 0–100 |
| Wolken hoch | CldHi | `^\d+%$` | 0–100 |
| Luftfeuchtigkeit Ø | Humid | `^\d+%$` | 0–100 |
| Taupunkt Ø | Cond° | `^-?\d+°C$` | -40–35 |
| Luftdruck Ø | hPa | `^\d+ hPa$` | 500–1085 |
| Schneefallgrenze | SnowL | `^\d+ m$` | 0–5000 |

**Bleiben unverändert (keine neue Zeile nötig):** `Temp max`, `Temp min`,
`Wind`, `CAPE` — hier ist die A2b-Zielbeschriftung Zeichen für Zeichen
identisch mit der heutigen, also existiert der Eintrag schon.

**Kollisionsvarianten (Pflicht, s. Implementation Details):**

| Beschriftung | Format-Regex | Wertebereich | Herleitung |
|---|---|---|---|
| `Temp` (ohne Zusatz) | `^-?\d+°C$` | -40–55 | identisch mit `Temp max`/`Temp min` (beide bereits -40–55) |
| `Feels` (ohne Zusatz) | `^-?\d+°C$` | -50–55 | untere Grenze von `Feels min` (-50), obere Grenze von `Feels max` (55) |

**Ausnahme-Menge (`_OVERVIEW_NO_CHECK_LABELS`), unverändert non-numerisch:**
`Gewitter` bekommt `Thdr` dazu, `Niederschlagsart` bekommt `PType` dazu;
`Amtliche Warnungen` bleibt allein (keine A2b-Gegenform, die Warn-Zeile ist
keine `metric_id`-Zeile).

**`ZIEL_LABELS_A2B` (Testkonstante, s. Implementation Details 4/AC-5):** die
20 Umbenennungen + 2 Kollisionsformen aus den beiden Tabellen oben (22
Prüf-Labels) plus `Thdr`/`PType` aus der Ausnahme-Menge (2 Labels) — zusammen
genau die 24 Labels, die mit dieser Lieferung neu hinzukommen.

## Der heikelste Punkt: zwei getrennte Probleme, nicht eins

**1. Auswahlabhängiger Kollisions-Zusatz (vom Auftrag benannt):** A2b hängt
den Auswertungs-Zusatz nur an, wenn zwei Zeilen mit demselben `col_label`
gleichzeitig sichtbar sind. Ist nur eine Auswertung gewählt, heißt die Zeile
`Temp` bzw. `Feels` — ohne Zusatz. Beide Formen müssen deshalb im Prüfer
stehen (s. Tabelle oben), sonst fällt genau der häufigste Fall (nur eine von
zwei Auswertungen gewählt) durch den stillen `continue`-Pfad.

**2. Die Union sprengt die bestehende Exakt-Gleichung des
Vollständigkeits-Tests (nicht vom Auftrag benannt, aber eine zwingende Folge
derselben Union-Mechanik).** `test_ac4_exemption_set_is_declared_and_complete`
prüft heute `checked | exempt == all_labels` mit `all_labels = {m["label"]
for m in CV2_METRICS}` (27, ausschließlich heutige deutsche Labels) und
zusätzlich `len(checked) == len(NUMERIC_LABELS)`. Sobald `checked` auf 46 und
`exempt` auf 5 wächst, ist `checked | exempt` (51 Elemente) zwangsläufig
**größer** als `all_labels` (27) — die Gleichheit gegen `all_labels` allein
ist strukturell nicht mehr erfüllbar, unabhängig davon, wie sorgfältig die
neuen Einträge sind. Ohne Anpassung wäre der Coverage-Test nach dieser
Lieferung selbst rot — nicht erst nach A2b.

**Die Anpassung erweitert die Soll-Menge, sie lockert die Gleichung nicht
(Tech-Lead-Korrektur 2026-07-29b, s. Changelog).** Naheliegend wäre `all_labels <= checked |
exempt`; das wird hier bewusst nicht getan, weil damit die Richtung „nichts
Überflüssiges steht in der Tabelle" verloren ginge — und genau die fängt den
wahrscheinlichsten Fehler beim Eintragen von 22 neuen Schlüsseln, den
Tippfehler **neben** dem korrekten Eintrag (z. B. `"Gsut"` neben `"Gust"`).
Eine reine Teilmengen-Prüfung beanstandet so einen zusätzlichen, falschen
Eintrag nie. Stattdessen führt der Test die A2b-Zielbeschriftungen als
benannte Konstante `ZIEL_LABELS_A2B` und vergleicht weiterhin exakt:
`checked | exempt == all_labels | ZIEL_LABELS_A2B` (Begründung ausführlich in
Implementation Details 4). `checked.isdisjoint(exempt)` bleibt unverändert.

Der Unterschied zu `_HOUR_COLUMNS_V2` (#1404): dort gab es nie eine
Exakt-Gleichung, weil die Stundentabelle immer schon als Allowlist geprüft
wurde. Die Übersichtstabelle hatte die schärfere Prüfung — und behält sie.

## Estimated Scope

- **LoC:** ~227-313 Netto-Zeilen (Rechenweg unten) — **liegt über dem
  250-Zeilen-Deckel**, keine Schönrechnung. Wie schon bei #1404 ist ein
  inhaltlicher Split hier kein echter Gewinn (eine Datenstruktur additiv
  erweitern + die Soll-Menge einer bestehenden Test-Invariante mitwachsen
  lassen ist derselbe Vorgang — getrennt committet, bliebe der
  Coverage-Test dazwischen rot) — Empfehlung: PO-Override
  (`workflow.py set-field loc_limit_override 500`) analog zum
  #1404-Präzedenzfall; PO-Freigabe holt der Orchestrierer ein, Zahl bleibt
  auf ausdrückliche PO-Weisung stehen.
- **Files:** 1 Produktivdatei (`.claude/hooks/email_spec_validator.py`), 1
  bestehende Testdatei (MODIFY, keine neue Testdatei nötig).
- **Effort:** low-medium.

### Rechenweg

**Produktivcode — `.claude/hooks/email_spec_validator.py`:**

| Änderung | Netto-Zeilen |
|---|---|
| `_OVERVIEW_METRIC_CHECKS`: 22 neue Einträge (20 Umbenennungen + 2 Kollisionsformen, Regex/Bereich unverändert übernommen) + Docstring-Update (24→46) | ~40-50 |
| `_OVERVIEW_NO_CHECK_LABELS`: 2 neue Einträge (`Thdr`, `PType`) + Kommentar-Update (3→5, Rechnung 46+5=51 statt 24+3=27) | ~10-15 |
| Neues Prüfdatum-Attribut `_OVERVIEW_METRIC_CHECKS_REVIEW_DATE` (Vorbild `_HOUR_COLUMNS_V2_REVIEW_DATE`), reiner Erinnerungsmarker ohne Verhaltenszweig, + Kommentarblock | ~12-18 |
| `validate_plausibility()`/`validate_format()` Docstring-Update (Zeilenzahl, Verweis auf diese Spec) | ~6-10 |

**Produktivcode-Summe:** ~68-93 Netto-Zeilen.

**Tests — `tests/unit/test_compare_mail_overview_plausibility_coverage.py` (MODIFY):**

| Änderung | Netto-Zeilen |
|---|---|
| `EXEMPT_LABELS`: 2 neue Einträge (`Thdr`, `PType`) | ~2-3 |
| Neuer Hilfsbaustein `_overview_mail_from_rows()`: baut eine Übersichtstabelle aus frei übergebenen (Label, Wert)-Paaren statt aus `CV2_METRICS` zu enumerieren — nötig, weil die Kollisionsformen und die A2b-Zielbeschriftungen heute (vor A2b) in `CV2_METRICS` gar nicht vorkommen | ~20-28 |
| Konstruierte A2b-Zielwerte-Tabelle (Label → plausibler, renderer-typischer Zellwert für alle 22 neuen Labels) | ~24-30 |
| Neue Testfunktion(en) AC-1: alle 22 neuen Labels werden bei plausiblem Wert nicht beanstandet UND bei kaputtem Wert benannt beanstandet (Wirkungsnachweis wie #1404 AC-3) | ~40-55 |
| Neue Testfunktion AC-3 (Kollisionsformen `Temp`/`Feels` einzeln, kaputter Wert) | ~25-35 |
| `test_ac4_exemption_set_is_declared_and_complete` (AC-5): Soll-Menge um die benannte Konstante `ZIEL_LABELS_A2B` erweitert, Exakt-Gleichung bleibt (s. „Der heikelste Punkt") | ~15-22 |
| Neue Testfunktion AC-6 (Prüfdatum-Attribut, Vorbild `test_1404_ac5_transition_union_carries_a_review_date`) | ~18-25 |
| Neue Testfunktion AC-7 (echt fremdes Label bleibt unbewertet, befristeter Regressionsnachweis, s. Known Limitations) | ~15-22 |

**Test-Summe:** ~159-220 Netto-Zeilen.

**Gesamt:** ~227-313 Netto-Zeilen — realistisch eher die obere Hälfte dieser
Spanne, weil Wirkungsnachweis-Tests (kaputter Wert muss tatsächlich einen
Befund erzeugen) systematisch mehr Code brauchen als reine Positiv-Assertions
(gleiche Erfahrung wie #1404, Changelog 2026-07-28b). PO-Vorgabe: Zahl bleibt
stehen, keine weitere Verkleinerung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/fix_1401_a2_mailtabellen.md` | READ | Quelle der A2b-Zielbeschriftungen, Abschnitt „Ziel-Beschriftung je Zeile" |
| `docs/specs/modules/fix_1404_validator_spaltennamen.md` | READ (Vorbild) | Begründung der Union-Mechanik, Prüfdatum-Konvention, Wertebereichs-Herkunft |
| `.claude/hooks/nebenbefund_gate.py` (Zeile 21) | REFERENZ (Vorbild) | Prüfdatum-Konvention (`EXPIRY`-Konstante) — **hier ohne** dessen Selbstabschaltungs-Verhalten, s. Known Limitations |
| `src/output/renderers/email/compare_html.py` (`CV2_METRICS`) | READ (unverändert) | Quelle der heutigen (Ist-)Beschriftungen; bildet zusammen mit `ZIEL_LABELS_A2B` die Soll-Menge des Vollständigkeits-Tests |
| `tests/unit/test_compare_mail_validator_column_order.py` | READ (unverändert, NICHT anfassen) | Bestandsschutz aus #1404 — bleibt unabhängig von dieser Lieferung grün |
| `.claude/hooks/renderer_mail_gate.py` | PROZESS | verlangt einen bestandenen `email_spec_validator.py`-Lauf für `compare_html.py` — Grund, warum #1401 A2b ohne diese Lieferung nicht sicher committen kann |
| Issue #1401 Scheibe A2b | DOWNSTREAM | erst nach dieser Lieferung commit-fähig, ohne dass die Übersichts-Plausibilitätsprüfung unbemerkt verstummt |

## Implementation Details

**1. `_OVERVIEW_METRIC_CHECKS` additiv auf 46 Einträge erweitern:** 20 neue
Schlüssel (A2b-Zielbeschriftung) mit **unverändert** aus dem jeweiligen alten
Eintrag übernommenem Regex und Wertebereich (Tabelle oben) plus 2
Kollisionsform-Schlüssel `"Temp"` (-40–55) und `"Feels"` (-50–55). Für die
zusatzlose Form gilt der jeweils **weitere** der beiden Einzelbereiche, weil
zur Prüfzeit nicht bekannt ist, welche Auswertung hinter der Zeile steckt
(bei „Feels" ist die untere Grenze von „Feels min" und die obere von
„Feels max" maßgeblich). Alte Schlüssel bleiben unverändert bestehen (rein
additiv, kein bestehender Schlüssel entfällt oder ändert Regex/Bereich).

**2. `_OVERVIEW_NO_CHECK_LABELS` additiv auf 5 Einträge erweitern:** `"Thdr"`
und `"PType"` ergänzen die bestehenden drei — beide sind wie ihre alten
Gegenstücke kategoriale Enum-Werte ohne Zahlenformat, „keine Prüfung" bleibt
für sie richtig, muss aber wie beim Vorbild ausgesprochen sein statt aus
einem fehlenden Dict-Eintrag zu folgen.

**3. Prüfdatum ohne Verhaltenszweig:** `_OVERVIEW_METRIC_CHECKS_REVIEW_DATE
= date(2026, 10, 27)` (Regel-Budget: `created` 2026-07-29 + 90 Tage). Wie bei
`_HOUR_COLUMNS_V2_REVIEW_DATE` schaltet dieses Datum **kein** Verhalten um —
eine Selbstverengung am Stichtag würde eine dann korrekte, bereits auf A2b
umgestellte Mail wieder ablehnen, falls sich A2b verzögert. Reiner
Erinnerungsmarker für eine menschliche Review (Rückbau der 20 alten Labels,
sobald A2b geliefert ist).

**4. Vollständigkeits-Test: Soll-Menge erweitern, NICHT die Gleichung
lockern (PO-verschärft 2026-07-29b).** Die Union macht `checked | exempt`
(51) zu einer echten Obermenge von `all_labels` (27, aus `CV2_METRICS`,
unverändert) — die bisherige Gleichung `checked | exempt == all_labels` ist
damit strukturell nicht mehr erfüllbar.

Der naheliegende Ausweg wäre, sie auf `all_labels <= checked | exempt`
abzuschwächen. **Das wird hier bewusst nicht getan.** Die Gleichung hat zwei
Richtungen, und nur eine davon wäre gerettet: „jede echte Zeile ist
abgedeckt" bliebe, „nichts Überflüssiges steht in der Tabelle" ginge
verloren. Genau diese zweite Richtung fängt aber den Fehler, der beim
Eintragen von 22 neuen Schlüsseln am wahrscheinlichsten ist — einen
Tippfehler, der **neben** dem korrekten Eintrag stehen bleibt (`"Gsut"`
neben `"Gust"`). Ein solcher Eintrag prüft nie eine echte Zeile und fiele
bei einer reinen Teilmengen-Prüfung nie auf. Tippfehler zu fangen ist der
erklärte Zweck dieser Prüftabelle (s. #1404, Docstring
`_OVERVIEW_METRIC_CHECKS`) — die Lockerung würde ihn an der empfindlichsten
Stelle aufgeben.

Stattdessen wächst die **Soll-Seite** mit: der Test führt die
A2b-Zielbeschriftungen als eigene benannte Konstante `ZIEL_LABELS_A2B`
(22 Prüf- + 2 Ausnahme-Labels, Herkunftskommentar auf
`fix_1401_a2_mailtabellen.md`) und vergleicht weiterhin exakt:

```
checked | exempt == all_labels | ZIEL_LABELS_A2B
```

Das erlaubt die Union genauso, hält aber beide Richtungen am Leben: fehlt ein
Eintrag, schlägt der Test an; steht einer zu viel darin, ebenso. `checked`
und `exempt` bleiben zusätzlich disjunkt. Die bisherige Zusatz-Aussage
`len(checked) == len(NUMERIC_LABELS)` entfällt — sie ist unter der neuen,
schärferen Gleichung redundant.

**5. Hilfsbaustein für Zeilen außerhalb von `CV2_METRICS`:** Die
Kollisionsformen (`"Temp"`, `"Feels"`) und die 20 A2b-Zielbeschriftungen
existieren heute (vor A2b) in keiner echten Renderer-Ausgabe — sie lassen
sich nicht über `_overview_mail()` (das über `CV2_METRICS` enumeriert)
erzeugen, ohne `compare_html.py` anzufassen (das ist #1401 A2b, nicht
dieses Ticket). Ein neuer Hilfsbaustein `_overview_mail_from_rows(rows)`
baut die Übersichtstabelle stattdessen direkt aus einer übergebenen Liste
von `(Label, Zellwert)`-Paaren — dasselbe Markup-Skelett wie `_overview_mail()`,
aber ohne die Kopplung an `CV2_METRICS`. Damit lässt sich sowohl die
A2b-Zielfassung als auch jede Kollisionsform testen, ohne den Renderer
vorwegzunehmen.

**6. Fremd-Beschriftung: Status quo, keine neue Ablehnung.** Eine Zeile mit
einer Beschriftung, die weder in Alt noch in Neu noch in der Ausnahme-Menge
vorkommt, bleibt **unbewertet** (stiller `continue`-Pfad wie heute) — diese
Lieferung führt für die Übersichtstabelle **keine** Ablehnungsmechanik ein
(s. Known Limitations). Geprüft wird hier nur, dass die Union diesen
Status quo nicht versehentlich verändert (weder fälschlich als geprüft noch
als Ausnahme einordnet). Dieser Nachweis (AC-7) ist ausdrücklich befristet —
s. Known Limitations.

## Expected Behavior

- **Input:** Eine Ortsvergleichs-Mail (HTML-Body) mit einer
  Übersichtstabellen-Zeile, deren Beschriftung entweder der heutigen
  deutschen Fassung, der künftigen A2b-Kurzform oder einer ihrer
  Kollisionsformen entspricht.
- **Output:** Für alle 46 numerisch geprüften Beschriftungen (24 alt + 22
  neu) erzeugt ein unplausibler oder falsch formatierter Wert einen benannten
  Befund; ein plausibler, korrekt formatierter Wert erzeugt keinen. Die 5
  ausgenommenen Beschriftungen bleiben unbewertet. Eine Beschriftung, die in
  keiner der beiden Mengen vorkommt, bleibt wie heute unbewertet (kein neues
  Verhalten). Der Vollständigkeits-Test erkennt sowohl eine fehlende als auch
  eine zusätzliche, unbeabsichtigte Beschriftung in `_OVERVIEW_METRIC_CHECKS`/
  `_OVERVIEW_NO_CHECK_LABELS`.
- **Side effects:** Keine — der Prüfer bleibt ein reines Analyse-Skript ohne
  Schreibzugriff auf Mail-Inhalte, Renderer oder Persistenz.

## Acceptance Criteria

- **AC-1:** Given eine Übersichtstabellen-Zeile trägt eine der 20 künftigen
  A2b-Kurzbeschriftungen (z. B. „Sun", „Cloud", „Rain%", „Feels max") mit
  einem renderer-typisch formatierten, plausiblen Wert / When Plausibilitäts-
  und Format-Check laufen / Then meldet der Prüfer keinen Befund — die
  Prüfung wirkt bereits, bevor #1401 A2b selbst ausgeliefert ist.
  - Test: `tests/unit/test_compare_mail_overview_plausibility_coverage.py`
    (MODIFY) — neue parametrisierte Testfunktion über alle 20 umbenannten
    Labels, konstruiert je eine Zeile über `_overview_mail_from_rows()` mit
    einem plausiblen Wert, erwartet `validate_plausibility() == []` und
    `validate_format() == []`.

- **AC-2:** Given dieselbe A2b-Zielbeschriftung trägt stattdessen einen
  unplausiblen oder falsch formatierten Wert / When dieselben Prüfungen
  laufen / Then meldet der Prüfer einen Befund, der genau diese Zeile
  benennt — keine der 20 neuen Zeilen fällt durch den stillen
  `continue`-Pfad, obwohl sie in der echten Renderer-Ausgabe heute noch gar
  nicht vorkommt.
  - Test: dieselbe parametrisierte Testfunktion wie AC-1, zweiter Fall mit
    kaputtem Zellwert je Label, erwartet eine nicht-leere Befundliste, die
    das Label nennt (Wirkungsnachweis analog #1404 AC-3).

- **AC-3:** Given die beiden Kollisionsformen „Temp" und „Feels" (ohne
  Auswertungs-Zusatz), die A2b genau dann zeigt, wenn nur eine der beiden
  möglichen Auswertungen gleichzeitig sichtbar ist / When ein kaputter Wert
  in einer dieser Zeilen steht / Then meldet der Prüfer einen benannten
  Befund für genau diese Zeile.
  - Test: `tests/unit/test_compare_mail_overview_plausibility_coverage.py`
    (MODIFY) — neue Testfunktion, konstruiert je eine Zeile `"Temp"` bzw.
    `"Feels"` mit kaputtem Wert über `_overview_mail_from_rows()`, erwartet
    einen Befund je Zeile, der das jeweilige Label nennt.

- **AC-4:** Given die heutigen 24 numerisch geprüften Zeilen und die 3
  ausgenommenen Zeilen der echten `CV2_METRICS`-Ausgabe (Bestandsschutz aus
  #1404) / When dieselben Prüfungen unverändert laufen / Then bleibt ihr
  Verhalten exakt wie vor dieser Lieferung — kein bislang geprüftes Label
  verliert seine Prüfung, keine bislang ausgenommene Zeile wird plötzlich
  bewertet.
  - Test: die bestehenden Testfunktionen
    `test_renderer_conform_overview_produces_no_findings`,
    `test_ac3_every_numeric_row_is_actually_checked` (parametrisiert über
    die 24 heutigen Labels), `test_ac3_out_of_range_value_is_reported_per_location`
    und `test_ac4_exempt_rows_stay_unevaluated` bleiben unverändert grün.

- **AC-5:** Given `_OVERVIEW_METRIC_CHECKS`/`_OVERVIEW_NO_CHECK_LABELS` sind
  jetzt eine auf Alt∪Neu erweiterte Übergangs-Union / When der
  Vollständigkeits-Test läuft / Then enthält die Union **exakt** die
  Vereinigung aus den 27 heutigen `CV2_METRICS`-Zeilen und der deklarierten
  A2b-Zielmenge — nichts fehlt und nichts Drittes steht darin. Ein
  Tippfehler beim Eintragen eines neuen Schlüssels (`"Gsut"` neben `"Gust"`)
  schlägt damit fehl, statt unbemerkt zu bleiben.
  - Test: `test_ac4_exemption_set_is_declared_and_complete` (MODIFY) — die
    Exakt-Gleichung bleibt erhalten, nur die Soll-Seite wächst:
    `checked | exempt == all_labels | ZIEL_LABELS_A2B`, wobei
    `ZIEL_LABELS_A2B` als benannte Konstante im Test steht (22 Prüf- + 2
    Ausnahme-Labels, Quelle `fix_1401_a2_mailtabellen.md`). Zusätzlich
    bleiben `checked` und `exempt` disjunkt.

- **AC-6:** Given die Übergangs-Union der Übersichtstabellen-Beschriftungen
  ist eine bewusst befristete Zwischenlösung (Muster `_HOUR_COLUMNS_V2`) /
  When das Validator-Modul geladen wird / Then trägt es ein
  maschinenlesbares Prüfdatum, das innerhalb der projektüblichen
  90-Tage-Spanne ab `created` liegt und **kein** Verhalten umschaltet.
  - Test: neue Testfunktion analog
    `test_1404_ac5_transition_union_carries_a_review_date` — prüft, dass
    `_OVERVIEW_METRIC_CHECKS_REVIEW_DATE` (oder eine der üblichen
    Namensvarianten) existiert, ein `date`-Objekt ist und in
    `(2026-07-29, 2026-10-27]` liegt.

- **AC-7:** Given eine Übersichtszeile trägt eine Beschriftung, die weder in
  der heutigen noch in der A2b-Zielfassung noch in der Ausnahme-Menge
  vorkommt (Tippfehler, z. B. „Mond") / When Plausibilitäts- und Format-Check
  laufen / Then bleibt diese Zeile unbewertet — die Union verändert den
  heutigen Status quo für echte Fremd-Beschriftungen nicht (kein neuer
  Ablehnungsmechanismus, s. Known Limitations). Dieser Nachweis ist
  ausdrücklich befristet (s. Known Limitations) und entfällt/kehrt sich um,
  sobald das Folge-Ticket „unbekannte Beschriftung = lauter Befund" geliefert
  wird.
  - Test: neue Testfunktion, konstruiert eine Zeile mit erfundenem Label und
    kaputtem Wert über `_overview_mail_from_rows()`, erwartet
    `validate_plausibility() == []` und `validate_format() == []`
    (Regressionsnachweis: die Erweiterung schafft keine falsche Bewertung).

## Known Limitations

- **„Unbekannte Beschriftung = lauter Befund" ist weiterhin NICHT Teil
  dieser Lieferung** (identisch zu #1404, aus derselben Begründung: A2b
  ändert alle 26 Übersichts-Beschriftungen gleichzeitig, ihr
  Kollisions-Zusatz ist auswahlabhängig — eine Ablehnungsmechanik für echte
  Fremd-Beschriftungen müsste dieselbe Fragilität handhaben und gehört in
  ein Folge-Ticket zusammen mit dem Rückbau nach A2b). AC-7 sichert nur den
  heutigen Status quo (unbewertet bleibt unbewertet), führt aber keine neue
  Ablehnung ein.
- **Widerspruch im Auftrag, hier aufgelöst:** Der ursprüngliche Auftrag
  verlangt eine Testrichtung „Prüfer lehnt eine Beschriftung, die in keiner
  der beiden Fassungen vorkommt, weiterhin namentlich ab." Für die
  Übersichtstabelle existiert **keine** solche Ablehnungsmechanik — weder
  heute noch nach dieser Lieferung; unbekannte Zeilen werden dort seit je her
  lautlos übersprungen (`continue`), nicht benannt abgelehnt (das ist exakt
  die aus #1404 übernommene, hier bewusst NICHT verschärfte Lücke). Eine
  echte „lehnt namentlich ab"-Mechanik existiert im Validator nur für die
  **Stundentabelle** (`_HOUR_COLUMNS_V2`, #1404 AC-2), die von diesem Ticket
  nicht angefasst wird. AC-7 dieser Spec prüft deshalb bewusst die schwächere,
  aber tatsächlich zutreffende Aussage (unbewertet bleibt unbewertet) statt
  einer Ablehnung, die es für die Übersichtstabelle nicht gibt und laut
  Known-Limitations-Absatz oben auch nicht geben soll.
- **AC-7 ist bewusst befristet (Tech-Lead-Korrektur 2026-07-29b, s. Changelog).** Er nagelt
  fest, dass eine unbekannte Beschriftung unbewertet bleibt — das ist heute
  richtig, wird aber vom geplanten Folge-Ticket („unbekannte Beschriftung =
  lauter Befund", nach A2b) gezielt umgedreht. AC-7 und sein Test fallen mit
  dieser Verschärfung **weg** und dürfen dann **nicht** als
  Regressionsargument gegen sie angeführt werden. Wer die Verschärfung
  umsetzt, löscht ihn.
- **Rückbau der Union und die aufgeschobene Verschärfung gehören in ein
  Folge-Ticket nach A2b**, zusammen mit dem bereits für `_HOUR_COLUMNS_V2`
  vorgesehenen Rückbau (#1404, Known Limitations).
- **Keine Änderung an `src/output/renderers/email/compare_html.py` oder
  `src/output/renderers/comparison.py`** — das ist #1401 A2b, eigener
  Workflow.
- **Wertebereiche der 20 umbenannten Zeilen sind unverändert aus #1404
  übernommen**, tragen also dieselben dort dokumentierten Grenzen (inkl. der
  bewusst breiten Fälle „CAPE" 0-10000, „Sicht min"/„Visib" 0-100). Diese
  Lieferung bewertet die Grenzen selbst nicht neu.
- **Der Vollständigkeits-Test behält seine Exakt-Gleichung** — sie wird
  nicht gelockert, sondern gegen eine erweiterte Soll-Menge geführt
  (`all_labels | ZIEL_LABELS_A2B`, s. Implementation Details 4). Preis
  dieser Entscheidung: `ZIEL_LABELS_A2B` ist eine im Test gepflegte Liste,
  die bei einer Änderung der A2b-Zielbeschriftungen mitgezogen werden muss.
  Das ist gewollt — genau dieses Mitziehen soll auffallen. Mit dem Rückbau
  der Union nach A2b fällt die Konstante ersatzlos weg und die Gleichung
  steht wieder allein auf `all_labels`.
- **`_OVERVIEW_METRIC_CHECKS_REVIEW_DATE` schaltet kein Verhalten um** —
  reiner Erinnerungsmarker, identische Begründung wie
  `_HOUR_COLUMNS_V2_REVIEW_DATE` (#1404): eine Selbstverengung am Stichtag
  würde eine dann korrekte, bereits auf A2b umgestellte Mail wieder ablehnen,
  falls sich A2b verzögert.
- **Renderer-Commit-Gate #811 bleibt unverändert** — diese Lieferung ändert
  nur, WAS der compare-spezifische `email_spec_validator.py` prüft, nicht
  das Gate selbst oder die zusätzlich vom Gate verlangten Nachweise
  (Matrix-Test, Trip-`briefing_mail_validator.py`).

## ADR-Bezug

- **ADR-Nr.:** keine
- **Rationale:** Diese Lieferung ändert Prüfdaten (Allowlist,
  Format-/Wertebereichs-Tabellen, eine Testinvariante) eines bestehenden
  Pflicht-Gate-Skripts nach demselben bereits etablierten Muster wie #1404,
  führt aber keinen neuen Mechanismus und keine neue Grundsatzentscheidung
  ein. Weder Kanäle noch Provider, Datenmodell/Persistenz, Auth,
  Editor-Paradigma noch die Test-/Deploy-Strategie sind betroffen.

## Changelog

- 2026-07-29b (Tech-Lead-Korrektur vor der Freigabe): AC-5 und
  Implementation Details 4 verschärft. Die zuerst vorgesehene Umstellung von
  `checked | exempt == all_labels` auf die Teilmengen-Bedingung
  `all_labels <= checked | exempt` hätte die Richtung „nichts Überflüssiges
  in der Prüftabelle" aufgegeben — ein Tippfehler, der **neben** dem
  korrekten neuen Schlüssel stehen bleibt („Gsut" neben „Gust"), wäre
  unsichtbar geworden, obwohl das Fangen von Tippfehlern der erklärte Zweck
  dieser Tabelle ist. Stattdessen bleibt die Exakt-Gleichung und die
  Soll-Menge wächst (`all_labels | ZIEL_LABELS_A2B`). Zusätzlich: AC-7 ist
  in Known Limitations ausdrücklich als befristet markiert — er fällt mit
  der Verschärfung im Folge-Ticket und darf nicht gegen sie ins Feld geführt
  werden. Umfangsschätzung geprüft und unverändert bestätigt (~227-313
  Netto-Zeilen, über dem Deckel, auf PO-Weisung stehen gelassen).
- 2026-07-29: Initial spec created (Fix #1420, direkte Fortsetzung von
  #1404, Vorbedingung für #1401 Scheibe A2b). Umfangsschätzung ~227-313
  Netto-Zeilen (über dem 250-Zeilen-Deckel, PO-Override empfohlen wie schon
  bei #1404). Widerspruch zwischen Auftrag und tatsächlichem
  Validator-Verhalten bei „Fremd-Beschriftung ablehnen" aufgelöst (s. Known
  Limitations) — die Übersichtstabelle kennt keine Ablehnungsmechanik, nur
  die Stundentabelle. Zusätzlich identifiziert und in die Spec aufgenommen:
  die bestehende Exakt-Gleichung des Vollständigkeits-Tests ist gegen
  `all_labels` allein nicht mehr erfüllbar, sobald die Union wächst (im
  Auftrag nicht ausdrücklich benannt, aber zwingende Folge derselben
  Union-Mechanik, die der Auftrag verlangt). Wie sie angepasst wird, regelt
  der Eintrag 2026-07-29b oben.
