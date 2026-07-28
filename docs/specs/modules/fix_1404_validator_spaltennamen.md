---
entity_id: fix_1404_validator_spaltennamen
type: bugfix
created: 2026-07-28
updated: 2026-07-28
status: draft
workflow: fix-1404-validator-spaltennamen
version: "1.0"
tags: [compare, mail-validator, gate, metric-catalog, naming, trip-compare-sharing]
---

# Fix #1404: Der Pflicht-Prüfer der Vergleichs-Mail übersteht die Umbenennung ihrer Spalten

## Approval

- [x] Approved — PO Henning, 2026-07-28 („Go"): die fünf Acceptance Criteria
  sowie ausdrücklich die Verschiebung des Scharfschaltens („unbekannte
  Beschriftung = lauter Befund") auf die Lieferung nach #1401 A2b, gekoppelt
  an den Rückbau der Übergangs-Union (s. Known Limitations).

## Purpose

Der Pflicht-Prüfer für die Ortsvergleichs-Mail (`.claude/hooks/email_spec_validator.py`)
kennt die Spaltenüberschriften der Mail wörtlich, an zwei Stellen mit
unterschiedlicher Strenge: Die Stundentabellen-Allowlist lehnt jede nicht
gelistete Spalte hart ab (Exit 1, blockiert jeden Commit über das
Renderer-Commit-Gate #811); die Übersichtstabellen-Prüfung überspringt jede
nicht gelistete Zeile lautlos. Sobald #1401 Scheibe A2b die Spaltenüberschriften
auf das zentrale Namensregister umstellt, würde die erste Prüfung die dann
korrekte Mail hart ablehnen — und die zweite läuft schon **heute**, unabhängig
von A2b, an 19 von 24 möglichen Übersichtszeilen lautlos vorbei. Diese
Lieferung macht die Stundentabellen-Prüfung übergangsfähig für beide
Beschriftungs-Fassungen (alt und A2b-neu) und schließt die bereits bestehende
stille Prüflücke der Übersichtstabelle — ohne A2b selbst vorwegzunehmen oder
den Renderer-Commit-Gate zu blockieren.

Vorbedingung für Ticket #1401 Scheibe A2b (siehe
`docs/specs/modules/fix_1401_a2_mailtabellen.md`, Abschnitt "Known
Limitations"): A2b kann seinen eigenen Commit nicht abschließen, solange der
unveränderte Validator die neue Mail ablehnt.

## Source

- **File:** `.claude/hooks/email_spec_validator.py`
- **Identifier:** `_HOUR_COLUMNS_V2` (Zeilen 221-223), `_OVERVIEW_METRIC_CHECKS`
  (Zeilen 240-246), `validate_structure()` (Verwendung Zeilen 394-400),
  `validate_plausibility()`/`validate_format()` (Verwendung Zeilen 462-464,
  494-496)

> **Schicht-Hinweis:** Kein Produktcode einer der drei Laufzeit-Schichten
> (Frontend/Go-API/Python-Core). `.claude/hooks/email_spec_validator.py` ist
> ein Pflicht-Gate-Skript, das der Renderer-Commit-Gate (#811,
> `.claude/hooks/renderer_mail_gate.py`) für den Compare-Mailpfad als
> Nachweisquelle verlangt. Betroffen ist ausschließlich dieses Skript sowie
> seine Testabdeckung — keine Datei unter `src/`, `internal/`, `frontend/`.

## Ausgangslage (gemessen, s. `docs/context/fix-1404-validator-spaltennamen.md`)

| Prüfung | Heutiges Verhalten bei unbekannter Spalte/Zeile | Wirkung |
|---|---|---|
| `_HOUR_COLUMNS_V2` (Stundentabelle, `validate_structure`) | Harter Fehler, `main()` endet mit Exit 1 | Pflichtteil des Renderer-Commit-Gates #811 — blockiert **jeden** Commit an `compare_html.py`, sobald A2b die Spaltennamen ändert |
| `_OVERVIEW_METRIC_CHECKS` (Übersichtstabelle, `validate_plausibility`/`validate_format`) | Stilles `continue`, kein Fehler, kein Log | Schon **heute** laufen 19 von 24 möglichen Zeilen ungeprüft durch — unabhängig von A2b |

Gemessen (`compare_html.py:232-294`): `CV2_METRICS` führt 27 Einträge (1
`kind:"warn"`-Zeile ohne numerischen Wert + 26 Metrik-Zeilen). Von den 26
sind 2 kategorial und haben kein Zahlenformat (`thunder_max` = "Gewitter",
`precip_type` = "Niederschlagsart" — beides Enum-Werte, kein `f"{value:.0f}"`
möglich). Die verbleibenden 24 sind numerisch prüfbar; `_OVERVIEW_METRIC_CHECKS`
kennt heute nur 5 davon.

Die Warn-Zeile ("Amtliche Warnungen") läuft heute selbst durch den stillen
`continue`-Pfad — `validate_plausibility`/`validate_format` iterieren über
`rows[1:]`, was die Warn-Zeile einschließt, und finden für sie keinen
Eintrag in `_OVERVIEW_METRIC_CHECKS`. Das ist heute folgenlos, weil "kein
Eintrag" für sie korrekt ist — aber es ist ein Zufallstreffer, keine
ausdrückliche Entscheidung, und das Muster für eine **ausdrückliche**
Nicht-Prüfung existiert im selben Modul bereits: `_OVERVIEW_WARN_LABEL`
(Zeile 212) markiert genau diese Zeile schon an anderer Stelle als
Sonderfall.

## Estimated Scope

- **LoC:** ~180-260 (Rechenweg unten) — **liegt am oder knapp über dem
  250-Zeilen-Deckel**, je nachdem, wie viel bestehende Test-Fixture-Logik
  wiederverwendet werden kann. Keine Schönrechnung: siehe Empfehlung am Ende
  dieses Abschnitts.
- **Files:** 1 Produktivdatei, 2 Testdateien (1 bestehend erweitert, 1 neu)
- **Effort:** low-medium

### Rechenweg

**Produktivcode — `.claude/hooks/email_spec_validator.py`:**

| Änderung | Netto-Zeilen |
|---|---|
| `_HOUR_COLUMNS_V2`: Liste von 10 auf 16 Einträge (Übergangs-Union alt ∪ neu) + Kommentarblock mit Prüfdatum und Rückbau-Auftrag (Vorbild `nebenbefund_gate.py:1-21`) | ~15-25 |
| `_OVERVIEW_METRIC_CHECKS`: 19 neue Einträge (Format-Regex + Wertebereich je Zeile, s. Implementation Details) + Docstring-Update | ~25-35 |
| `_OVERVIEW_NO_CHECK_LABELS` (neu, ausdrückliche Ausnahme-Menge nach Vorbild `_OVERVIEW_WARN_LABEL`) — dokumentiert die 3 bewusst ausgenommenen Zeilen als Wert, nicht als Zufall fehlender Dict-Einträge | ~5-15 |

**Produktivcode-Summe:** ~45-75 Netto-Zeilen.

**Tests:**

| Test | Inhalt | Netto-Zeilen |
|---|---|---|
| `tests/unit/test_compare_mail_validator_column_order.py` (bestehend, MODIFY) | 3 neue Testfunktionen für AC-1, AC-2, AC-5 — nutzt die bereits vorhandenen Fixture-Helfer (`compare_mail()`, `_hour_table()`, `_load_validator()`) dieser Datei weiter, statt sie in einer neuen Datei zu duplizieren | ~65-85 |
| `tests/unit/test_compare_mail_overview_plausibility_coverage.py` (neu) | AC-3, AC-4 — braucht **keine** Stundentabellen-/ORT-Fixtures (die geprüften Funktionen finden die Übersichtstabelle allein über `extract_table_rows()`), daher eine schlanke eigene Minimal-Fixture statt Wiederverwendung des schwereren Apparats aus der Nachbardatei | ~70-95 |

**Test-Summe:** ~135-180 Netto-Zeilen.

**Gesamt:** ~180-260 Netto-Zeilen.

### Empfehlung zur Deckel-Einhaltung

Die Erweiterung der bestehenden Datei `test_compare_mail_validator_column_order.py`
statt einer dritten, fixture-duplizierenden Testdatei ist die konkrete
Stellschraube, um näher am unteren Ende der Spanne zu bleiben — der volle
Fixture-Apparat für `validate_structure()` (Overview + Location-Sections +
Hour-Table) existiert dort bereits und muss nicht erneut gebaut werden.
Landet die Umsetzung dennoch über 250 Zeilen, ist ein PO-Override
(`workflow.py set-field loc_limit_override 500`) die richtige Reaktion, kein
weiterer inhaltlicher Schnitt: Die Änderung ist bereits auf das
Mindestmaß reduziert (zwei Datenstrukturen erweitern, keine neue Logik), ein
Split würde nur eine der beiden bereits benannten Lücken (harter Bruch,
stiller Bruch) länger offen lassen, ohne einen erkennbaren Vorteil.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/fix_1401_a2_mailtabellen.md` | READ | Quelle der A2b-Zielbeschriftungen (Stundentabelle: Abschnitt "Ziel-Beschriftung Stundentabelle"; Übersichtstabelle: Abschnitt "Ziel-Beschriftung je Zeile") |
| `src/output/renderers/email/compare_html.py` (`CV2_METRICS`, `HOUR_METRICS`) | READ | Quelle der heutigen (Ist-)Beschriftungen, gegen die `_OVERVIEW_METRIC_CHECKS` erweitert wird |
| `.claude/hooks/renderer_mail_gate.py` | PROZESS | Macht einen bestandenen `email_spec_validator.py`-Lauf zur Commit-Pflicht für `compare_html.py` (Pfad-Muster `_COMPARE_PATTERNS`) — unverändert von dieser Lieferung, aber der Grund, warum #1401 A2b ohne #1404 nicht committen kann |
| `.claude/hooks/nebenbefund_gate.py` (Zeile 21, 72-73) | REFERENZ (Vorbild) | Prüfdatum-Konvention für befristete Übergangszustände (`EXPIRY`-Konstante + Kommentar, kein Verhaltens-Umschalten am Datum selbst) |
| `tests/unit/test_compare_mail_validator_column_order.py` | MODIFY | Trägt bereits die Fixture-Helfer, die für AC-1/AC-2/AC-5 wiederverwendet werden |
| Issue #1401 Scheibe A2b | DOWNSTREAM | Erst nach dieser Lieferung commit-fähig (Renderer-Commit-Gate #811 verlangt einen bestandenen Validator-Lauf für jeden Commit an `compare_html.py`) |

## Implementation Details

**1. Übergangs-Union der Stundentabellen-Allowlist (`_HOUR_COLUMNS_V2`):**
Vereinigung aus den 10 heutigen und den 6 tatsächlich abweichenden
A2b-Zielspalten (Zeit/Temp/Wind/UV heißen in beiden Fassungen gleich und
tauchen nur einmal auf):

```
alt (10):  Zeit, Temp, Gef., Wind, Böen, Regen, UV, Gew., Regen-W., Sicht
neu (6):   Feels, Gust, Rain, Thdr, Rain%, Visib
Union (16): Zeit, Temp, Gef., Wind, Böen, Regen, UV, Gew., Regen-W., Sicht,
            Feels, Gust, Rain, Thdr, Rain%, Visib
```

Die Liste trägt einen Kommentar mit einem maschinenlesbaren Prüfdatum
(`created` + 90 Tage, Regel-Budget-Konvention: 2026-07-28 → 2026-10-26) und
einem benannten Rückbau-Auftrag: sobald #1401 A2b geliefert ist, werden die 6
alten Labels (`Gef., Böen, Regen, Gew., Regen-W., Sicht`) aus der Liste
entfernt — Zielzustand exakt die 10 A2b-Spalten aus
`fix_1401_a2_mailtabellen.md`. **Anders als bei `nebenbefund_gate.py` schaltet
das Prüfdatum kein Verhalten um** — es ist ein reiner Erinnerungs-Marker für
eine menschliche Review, kein Code-Zweig. Ein automatisches Verengen der
Liste am Stichtag wäre falsch: Verzögert sich A2b, würde die dann korrekte
neue Mail wieder hart abgelehnt — genau der Fehler, den diese Lieferung
verhindern soll.

**2. `_OVERVIEW_METRIC_CHECKS` von 5 auf 24 heutige Labels erweitern:**
Nutzt ausschließlich die **heutigen** (Ist-)Beschriftungen aus `CV2_METRICS`
— keine A2b-Kopplung, da dies eine reine Plausibilitäts-/Format-Prüfung ist,
kein Commit-Blocker. Format und Wertebereich je Zeile, hergeleitet aus
`_fmt_metric()`/den jeweiligen `fmt`-Funktionen in `compare_html.py`:

| Zeilen-Label (heute) | Format-Regex | Wertebereich (geschätzt) |
|---|---|---|
| Regen | `^\d+\.\d mm$` | 0–300 |
| Regenwahrscheinlichkeit | `^\d+%$` | 0–100 |
| Sicht min | `^\d+\.\d km$` | 0–200 |
| Schneehöhe | `^\d+ cm$` | 0–1000 |
| Neuschnee | `^\d+ cm$` | 0–300 |
| Temp min | `^-?\d+°C$` | -40–55 |
| Böen | `^\d+ km/h$` | 0–300 |
| CAPE | `^\d+ J/kg$` | 0–6000 |
| Nullgradgrenze | `^\d+ m$` | 0–6000 |
| Windrichtung | `^\d+ °$` | 0–360 |
| Gefühlte Temp. min | `^-?\d+°C$` | -50–50 |
| Gefühlte Temp. max | `^-?\d+°C$` | -50–55 |
| Wolken tief | `^\d+%$` | 0–100 |
| Wolken mittel | `^\d+%$` | 0–100 |
| Wolken hoch | `^\d+%$` | 0–100 |
| Luftfeuchtigkeit Ø | `^\d+%$` | 0–100 |
| Taupunkt Ø | `^-?\d+°C$` | -40–35 |
| Luftdruck Ø | `^\d+ hPa$` | 500–1085 |
| Schneefallgrenze | `^\d+ m$` | 0–5000 |

Zusammen mit den 5 bereits vorhandenen ("Temp max", "Wind", "Sonne",
"Wolken", "UV max") ergeben sich 24 geprüfte Zeilen.

**3. `_OVERVIEW_NO_CHECK_LABELS` (neu):** explizite Menge
`{"Amtliche Warnungen", "Gewitter", "Niederschlagsart"}` — Vorbild
`_OVERVIEW_WARN_LABEL`. 24 geprüfte + 3 ausdrücklich ausgenommene Zeilen =
27 = die volle Zeilenzahl von `CV2_METRICS`. Ein Test muss belegen, dass
keine vierte Zeile unbenannt durch beide Mengen fällt (s. AC-4).

## Expected Behavior

- **Input:** Eine echte Ortsvergleichs-Mail (HTML-Body) wird an
  `validate_structure()`, `validate_plausibility()` und `validate_format()`
  übergeben — entweder mit den heutigen Spaltenbeschriftungen oder mit den
  künftigen A2b-Beschriftungen (Stundentabelle) bzw. mit einem
  unplausiblen/falsch formatierten Wert in einer der 24 numerisch geprüften
  Übersichtszeilen (Übersichtstabelle).
- **Output:** Eine Mail mit ausschließlich bekannten Stundentabellen-Spalten
  (alt **oder** neu) erzeugt keinen Struktur-Fehler. Eine Mail mit einer
  weder alt noch neu bekannten Spalte erzeugt weiterhin genau den Fehler, den
  sie heute schon erzeugt. Eine Übersichtszeile mit unplausiblem Wert oder
  falschem Format erzeugt für alle 24 geprüften Zeilen einen benannten
  Befund — auch für die 19, die vor dieser Lieferung lautlos durchliefen.
  Die 3 ausdrücklich ausgenommenen Zeilen bleiben unbewertet, aber als
  bewusste Ausnahme nachweisbar.
- **Side effects:** Keine — der Prüfer bleibt ein reines Analyse-Skript ohne
  Schreibzugriff auf Mail-Inhalte, Renderer oder Persistenz.

## Acceptance Criteria

- **AC-1:** Given eine Vergleichs-Mail zeigt die Stundentabelle entweder mit
  den heutigen oder mit den künftigen A2b-Spaltenüberschriften (oder einer
  Mischung, sofern mail-weit einheitlich) / When der Struktur-Check läuft /
  Then meldet der Prüfer keinen Fehler wegen unbekannter Spalten — eine
  inhaltlich korrekte Mail wird unabhängig davon angenommen, ob sie schon auf
  die neue oder noch auf die alte Beschriftung zeigt.
  - Test: `tests/unit/test_compare_mail_validator_column_order.py` (MODIFY)
    — neue Testfunktion, die `validate_structure()` einmal mit der reinen
    A2b-Zielspaltenfolge (`Zeit, Temp, Feels, Wind, Gust, Rain, UV, Thdr,
    Rain%, Visib`) und einmal mit der heutigen Spaltenfolge aufruft und in
    beiden Fällen `errors == []` erwartet.

- **AC-2:** Given eine Stundentabellen-Spalte, die weder in der heutigen noch
  in der künftigen A2b-Beschriftung vorkommt (Tippfehler oder erfundene
  Spalte) / When der Struktur-Check läuft / Then meldet der Prüfer weiterhin
  genau einen Fehler, der die unbekannte Spalte benennt — die
  Übergangsfassung bleibt eine Prüfung, keine Durchreiche.
  - Test: `tests/unit/test_compare_mail_validator_column_order.py` (MODIFY)
    — neue Testfunktion, analog zu `test_ac2_unknown_column_is_rejected_and_named`
    dieser Datei, mit einer erfundenen Spalte (z. B. "Mond") neben einer
    Mischung aus alten und neuen bekannten Spalten.

- **AC-3:** Given die Übersichtstabelle einer Vergleichsmail zeigt für eine
  der jetzt 24 numerisch geprüften Zeilen (davon 19 vor dieser Lieferung
  ungeprüft) einen Wert außerhalb des plausiblen Wertebereichs oder in
  falschem Format / When Plausibilitäts- und Format-Check laufen / Then
  meldet der Prüfer einen benannten Befund für genau diese Zeile.
  - Test: `tests/unit/test_compare_mail_overview_plausibility_coverage.py`
    (neu) — Wirkungsnachweis analog `test_compare_metric_catalog_consistency.py::test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row`:
    ein Wert für eine der 19 neu geprüften Zeilen (z. B. "Windrichtung" =
    "450 °", außerhalb 0–360) muss die Prüfung tatsächlich rot werden
    lassen; derselbe Aufbau vor dieser Lieferung (Zeile nicht in
    `_OVERVIEW_METRIC_CHECKS`) hätte keinen Befund erzeugt.

- **AC-4:** Given die drei nicht-numerischen Übersichtszeilen ("Amtliche
  Warnungen", "Gewitter", "Niederschlagsart") / When Plausibilitäts- und
  Format-Check über alle 27 Zeilen von `CV2_METRICS` laufen / Then bleiben
  genau diese drei Zeilen unbewertet, und keine der 24 numerischen Zeilen
  fällt versehentlich mit in diese Ausnahme.
  - Test: `tests/unit/test_compare_mail_overview_plausibility_coverage.py`
    (neu) — prüft für eine vollständige Zeilenliste, dass jede der 27
    `CV2_METRICS`-Labels entweder eine geprüfte Zeile oder eine der drei
    genannten Ausnahmen ist, und dass keine Zeile in keiner der beiden
    Mengen auftaucht (Vollständigkeits-Nachweis 24+3=27).

- **AC-5:** Given die Übergangs-Union der Stundentabellen-Spalten ist eine
  bewusst befristete Zwischenlösung / When das Validator-Modul geladen wird
  / Then trägt es ein maschinenlesbares Datum, bis zu dem geprüft werden
  muss, ob die alten Spaltennamen aus der Union entfernt werden können — die
  Übergangsregelung verfällt nicht stillschweigend für immer.
  - Test: `tests/unit/test_compare_mail_validator_column_order.py` (MODIFY)
    — prüft, dass das Modul ein Prüfdatum-Attribut für die
    Stundentabellen-Übergangs-Union exponiert und dass dieses Datum
    innerhalb der projektüblichen 90-Tage-Spanne ab `created` liegt (Vorbild:
    `nebenbefund_gate.py:21` EXPIRY-Konstante, Test-Pattern
    `test_nebenbefund_gate_false_positives.py::test_ac8_after_expiry_passes`
    — hier ohne das dortige Selbstdeaktivierungs-Verhalten, s. Implementation
    Details 1).

## Known Limitations

- **„Unbekannte Beschriftung = lauter Befund" ist NICHT Teil dieser
  Lieferung.** Das Ticket nennt diese Verschärfung den eigentlichen
  Härtungsgewinn, sie würde aber **jetzt** scharfgeschaltet A2b selbst zum
  harten Blocker machen: A2b ändert **alle 26** Übersichts-Beschriftungen
  gleichzeitig, und ihr Kollisions-Zusatz ist auswahlabhängig ("Temp" **oder**
  "Temp max"/"Temp min", je nachdem was gleichzeitig sichtbar ist) — der
  Validator müsste dieselbe Fragilität nachbauen, die #1381 gerade erst
  behoben hat. Zusätzlich läuft die Warn-Zeile heute selbst durch den
  stillen Pfad (s. Ausgangslage); ein Scharfschalten ohne die in dieser
  Lieferung eingeführte `_OVERVIEW_NO_CHECK_LABELS`-Ausnahme würde bei
  **jeder** Vergleichsmail sofort einen neuen Fehler erzeugen. Diese
  Verschärfung wandert in ein Folge-Ticket, das zusammen mit dem Rückbau
  nach A2b läuft (s. Implementation Details 1).
- **`_OVERVIEW_METRIC_CHECKS` ist NICHT union-basiert wie `_HOUR_COLUMNS_V2`.**
  Es prüft ausschließlich die heutigen deutschen Labels. Sobald #1401 A2b
  die Übersichts-Beschriftungen auf die englische Kurzform umstellt, greift
  keine der 24 hier ergänzten Prüfungen mehr — der `continue`-Pfad lässt sie
  wieder lautlos durch, bis jemand die Labels in `_OVERVIEW_METRIC_CHECKS`
  auf die A2b-Zielwerte aktualisiert. Das ist bewusst so entkoppelt (diese
  Lieferung braucht keine A2b-Vorwegnahme), muss aber bei oder unmittelbar
  nach A2b nachgezogen werden, sonst öffnet sich exakt die stille Lücke
  erneut, die diese Lieferung gerade schließt.
- **Wertebereiche der 19 neu geprüften Zeilen sind physikalisch plausibel
  geschätzt, nicht gegen historische Wetterdaten belegt.** Für einen
  Plausibilitäts-Check (kein statistisches Modell) ist das vertretbar,
  bleibt aber eine bekannte Grenze — insbesondere „Luftdruck Ø" (500-1085
  hPa) muss sowohl Meereshöhe als auch hochalpine Stationsdrücke abdecken
  und ist entsprechend breit gewählt.
- **Zwei Wertebereiche wurden während der Umsetzung geweitet bzw. verengt**
  (Tech-Lead-Entscheid, s. Changelog 2026-07-28b): „CAPE" von 0-6000 auf
  **0-10000 J/kg**, weil ein Wächter, der einen echten Extremwert als
  unplausibel meldet, ausgerechnet bei der Wetterlage Fehlalarm gibt, für die
  dieses Produkt gebaut ist. „Sicht min" von 0-200 auf **0-100 km**, weil 200
  km jenseits jedes Modellwerts liegt und damit nichts fing.
- **Drei der 24 Prüfungen leisten nach eigener Messung wenig:** „Schneehöhe"
  (0-1000 cm), „Böen" (0-300 km/h) und „Luftdruck Ø" (500-1085 hPa) sind so
  breit, dass sie praktisch nur noch Faktor-1000- und Einheitenfehler fangen.
  Die untere Grenze bei „Gefühlte Temp. max" (-50 °C) ist geschätzt und ließ
  sich nicht am Code belegen, weil `wind_chill_max` im Renderer keine
  Severity-Schwelle hat. Alle vier melden im Zweifel **zu wenig**, nie
  fälschlich zu viel — für einen commit-blockierenden Wächter die richtige
  Richtung, aber ihr Nutzen ist gering und sie sind Rückbau-Kandidaten, falls
  sie bis zum Prüfdatum nichts gefangen haben.
- **Die neuen Tests werden bei #1401 A2b planmäßig rot** —
  `test_ac4_exemption_set_is_declared_and_complete` und der Abdeckungs-Sweep
  hängen an den heutigen deutschen Labels. Das ist **kein Regress, sondern der
  beabsichtigte Wächter**: er zwingt A2b, `_OVERVIEW_METRIC_CHECKS`
  mitzuziehen, statt die stille Lücke erneut zu öffnen. In der A2b-Spec und im
  Übergabezettel als erwarteter Folgeschritt vermerkt.
- **Renderer-Commit-Gate #811 bleibt unverändert.** `compare_html.py` löst
  weiterhin zusätzlich den Matrix-Test-Nachweis
  (`tests/tdd/test_issue_811_mode_matrix.py`) und ggf. den
  Trip-`briefing_mail_validator.py`-Nachweis aus (pfadbasiert, nicht
  inhaltsbasiert) — diese Lieferung ändert nur, WAS der
  compare-spezifische `email_spec_validator.py` prüft, nicht das Gate
  selbst.
- **Keine Änderung an `src/output/renderers/comparison.py`** (Klartext-Zwilling,
  Ziel von A2b). Der gemessene Nebenbefund, dass dessen Änderungen allein
  keinen `_MAIL_PATTERNS`-Treffer auslösen, ist unabhängig von #1404 und
  gehört in die Gate-Sammelstelle (#1199), nicht in diese Spec.

## ADR-Bezug

- **ADR-Nr.:** keine
- **Rationale:** Diese Lieferung ändert Prüfdaten (Allowlist, Format-/
  Wertebereichs-Tabellen) eines bestehenden Pflicht-Gate-Skripts, führt aber
  keinen neuen Mechanismus und keine neue Grundsatzentscheidung ein. Weder
  Kanäle noch Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma noch
  die Test-/Deploy-Strategie sind betroffen — der Renderer-Commit-Gate #811
  und die Zwei-Schichten-Testpolitik bleiben unverändert in Kraft, diese
  Spec setzt nur seine Prüfdaten aktuell.

## Changelog

- 2026-07-28b (während der Umsetzung, keine AC-Änderung): Zwei Wertebereiche
  gegenüber der Spec-Tabelle korrigiert — „CAPE" 0-6000 → **0-10000 J/kg**,
  „Sicht min" 0-200 → **0-100 km** (Begründung s. Known Limitations). Auslöser
  war die Herleitung am Renderer: die CAPE-Obergrenze hätte einen echten
  Extremwert als unplausibel gemeldet, die Sicht-Obergrenze fing nichts.
  Umfang tatsächlich: +110/-6 am Validator, +150 in der erweiterten und 213 in
  der neuen Testdatei — deutlich über der Schätzung (~180-260), PO-Freigabe
  für eine angehobene Grenze eingeholt.
- 2026-07-28: Initial spec created (Fix #1404, Vorbedingung für #1401
  Scheibe A2b). Umfangsschätzung ~180-260 Netto-Zeilen (am oder knapp über
  dem 250-Zeilen-Deckel); konkrete Empfehlung zur Deckel-Einhaltung
  (Wiederverwendung der Fixture-Helfer in `test_compare_mail_validator_column_order.py`
  statt einer dritten, fixture-duplizierenden Testdatei) statt Schönrechnung
  dokumentiert.
