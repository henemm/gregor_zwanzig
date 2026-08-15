---
entity_id: fix_1703_s6_form_waechter
type: module
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [sms, tokens, grammar-classes, matrix-test, epic-1703, safety-fix]
---

<!-- Epic #1703 (Folgearbeit aus #1514), Scheibe 6. Deckt Sonderstrecken S2+S6
     und teilweise Flaeche 8 aus docs/reference/metric_output_matrix.md §3/§4/§6
     (Form-Waechter ueber SMS-Symbol-Grammatik-Klassen). Anders als Scheibe 1-5
     iteriert diese Achse ueber SYMBOLE, nicht ueber Metrik-IDs. Enthaelt EINEN
     gezielten, sicherheitsrelevanten Produktivcode-Fix (UNAVAILABLE_SYMBOL),
     alles Uebrige ist reine Charakterisierung. -->

# Form-Wächter über Grammatik-Klassen (#1703 Scheibe 6)

## Approval

- [ ] Approved

## Purpose

Die SMS-Symbol-Register (`PRIORITY`/`POSITIONAL` in `tokens/builder.py`,
`SMS_MULTI_SYMBOLS_BY_METRIC`/`SMS_SYMBOL_BY_METRIC` in `metric_catalog.py`,
`HAZARD_SMS_SYMBOLS` in `tokens/hazard_symbols.py`) sind heute nur teilweise
gegeneinander geprüft: der bestehende Ratschen-Test
(`tests/unit/test_sms_token_symbol_register_ratchet.py`) deckt ausschließlich
den Wintersport-Block + `SMS_SYMBOL_BY_METRIC` gegen `get_sms_code()` — er
importiert `HAZARD_SMS_SYMBOLS` an keiner Stelle, prüft `PRIORITY`/`POSITIONAL`
nicht als Ganzes und kennt `SMS_MULTI_SYMBOLS_BY_METRIC` nicht. Diese Scheibe
schließt diese Lücke mit einer neuen, eigenständigen Testdatei
(`tests/unit/test_sms_symbol_grammar_classes.py`) — PO-vorentschieden in
`metric_output_matrix.md` §7b: „Form-Dimension als eigene Achse, **nicht** in
die Hauptmatrix gemischt", weil `SMS_MULTI_SYMBOLS_BY_METRIC` (Sonderstrecke S6)
eine Metrik auf mehrere Kürzel abbildet (1:n) und die Hauptmatrix („1 Zeile = 1
Metrik") das strukturell nicht ausdrücken kann.

**Diese Scheibe ist überwiegend Charakterisierung — mit EINER benannten
Ausnahme.** Die Vollständigkeits-/Positions-/Kollisionsprüfung (AC-S6-1 bis
AC-S6-5) hält den gemessenen Ist-Zustand fest, ohne ihn zu verändern — analog
zu Scheibe 1/4/5. AC-S6-6 ist die Ausnahme: ein verifizierter, **live
erreichbarer** Fund — ein Wind-Datenausfall kann bytegleich mit dem
dedizierten „amtliche Warnungen nicht abrufbar"-Marker kollidieren — wird
**behoben**, nicht nur dokumentiert, weil er laut CLAUDE.md-Nebenbefund-Triage
Kriterium (b) ein Sicherheitsrisiko ist (kann verschleiern, dass amtliche
Warnungen ausgefallen sind), nicht bloß kosmetisch wie der Em-Dash/Hyphen-Fund
aus Scheibe 5. Der Fix selbst ist ein winziger, gezielter
Ein-Zeilen-Produktivcode-Edit außerhalb des sonst reinen
Charakterisierungs-Musters dieser Epic-Scheiben — bewusste Ausnahme, keine
Abweichung vom Muster.

### Korrektur gegenüber dem Context-Dokument: `POSITIONAL` hat 38 Einträge, nicht 37

`docs/context/fix-1703-s6-form-waechter.md` beziffert `POSITIONAL` mit „37
`(symbol, category)`-Paare". Nachgezählt (Zeilen 78–99, jede Tupel-Zeile
einzeln erfasst inkl. der über Konstanten referenzierten Einträge
`FORECAST_TH`/`FORECAST_THP`/`VIGI_HR`/`VIGI_TH`/`UNAVAILABLE_SYMBOL`): **38**
Tupel. Die Rechnung, die das erklärt: `PRIORITY` hat 36 Schlüssel (nachgezählt,
Zeilen 47–65); jedes davon hat mindestens einen `POSITIONAL`-Eintrag, plus
`UNAVAILABLE_SYMBOL` (`"W?"`, category `unavailable`) — das trägt **keinen**
`PRIORITY`-Schlüssel (eigene Konstante `UNAVAILABLE_PRIORITY`, s. Purpose oben)
— macht 37 Symbole, die insgesamt eine Priorität/Position brauchen. `POSITIONAL`
hat aber 38 Tupel, weil `TH:` (Symbol) **zweimal** vorkommt: einmal Kategorie
`forecast` (`FORECAST_TH`), einmal Kategorie `vigilance` (`VIGI_TH`) — beide
Tupel sind wegen der unterschiedlichen Kategorie als `POS_INDEX`-Schlüssel
eindeutig, teilen sich aber denselben `PRIORITY`-Eintrag (`PRIORITY` ist nur
über den Symbol-String indiziert, nicht über `(Symbol, Kategorie)`). Rechnung:
37 „braucht Priorität/Position"-Symbole + 1 Doppeleintrag für `TH:` = 38
`POSITIONAL`-Tupel. Diese Korrektur ändert nichts an den Empfehlungen des
Context-Dokuments, nur an der Zählung — Lehre aus Scheibe 2/5 F001: falsche
Prämissen in Zahlen sind der teuerste Fehlertyp, deshalb hier vor dem Schreiben
der ACs am Code nachgezählt statt aus dem Context-Dokument übernommen.

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/output/tokens/`,
> `src/app/metric_catalog.py`), ausschließlich Testcode plus ein
> Ein-Zeilen-Produktivcode-Fix. Kein Frontend, keine Go-Beteiligung.

- **File (Prüfling 1 — Priorität/Position):** `src/output/tokens/builder.py` —
  `PRIORITY` (:47–65, 36 Schlüssel), `POSITIONAL`/`POS_INDEX` (:78–100, 38
  Tupel), `_POSITION_SORTABLE_CATEGORIES` (:110), `UNAVAILABLE_SYMBOL`/
  `UNAVAILABLE_PRIORITY` (:74–75, **Fix-Ziel**), `_unavailable()` (:225–231),
  `_gap_or()` (:139–149), Wind-Token-Konstruktion (:346–361, ruft `_mk_metric()`
  → `_gap_or()`)
- **File (Prüfling 2 — Katalog-Register):** `src/app/metric_catalog.py` —
  `SMS_SYMBOL_BY_METRIC` (:665–668, 22 Symbole, aus `_SMS_SYMBOL_METRIC_IDS`
  :637–650), `SMS_MULTI_SYMBOLS_BY_METRIC` (:700–706, 5 Metrik-IDs → 9
  eindeutige Symbole)
- **File (Prüfling 3 — Hazard-Register):** `src/output/tokens/hazard_symbols.py`
  — `HAZARD_SMS_SYMBOLS` (:15–26, 10 Einträge), `LEVELLESS_HAZARDS` (:70,
  `frozenset({"access_ban"})`)
- **File (Renderpfad, nur zur Verifikation der Diskriminanz):**
  `src/output/tokens/dto.py::Token.render()` (:130–135), `src/output/tokens/
  render.py` (`!`-Warnblock-Fusion, Prüfling nur zur Charakterisierung, KEIN
  Edit)
- **File (Wächter, CREATE):** `tests/unit/test_sms_symbol_grammar_classes.py`
- **Files (Migration, kleine Byte-String-Anpassung wegen AC-S6-6):**
  `tests/tdd/test_sms_trip_unavailable_marker.py` (`_MARKER = "W?"`, Zeile 25
  — einziger Änderungspunkt),
  `tests/tdd/test_sms_user_metric_order.py` (`_exact_token_index(sms, "W?")`,
  Zeile 364, Testfunktion
  `test_ac7_wintersport_metric_can_precede_forecast_metric_but_stays_before_system_blocks`)
- **File (Doku, Definition of Done, nicht LoC-relevant):**
  `docs/reference/sms_format.md` (§3.4d, Zeilen 45/64/262/265/267/270/273 —
  wire-format-Legende und Marker-Beschreibung), `docs/reference/
  metric_output_matrix.md` (§3/§4/§6, Scheibe-6-Zeile auf erledigt umtragen)

**Ausdrücklich UNVERÄNDERT (reine Prüfziele, kein Edit):** `PRIORITY`,
`POSITIONAL`, `POS_INDEX`, `_POSITION_SORTABLE_CATEGORIES`, `UNAVAILABLE_PRIORITY`,
`_unavailable()`, `_gap_or()`, `SMS_SYMBOL_BY_METRIC`, `SMS_MULTI_SYMBOLS_BY_METRIC`,
`HAZARD_SMS_SYMBOLS`, `LEVELLESS_HAZARDS`, `Token.render()`, der gesamte
`!`-Warnblock-Fusionsmechanismus in `render.py`. Einziger Produktivcode-Edit:
der Literalwert von `UNAVAILABLE_SYMBOL` (`builder.py:74`, s. AC-S6-6).

## Estimated Scope

- **LoC:** ~180-230 Testcode (neue Datei, 6 ACs) + **1 Zeile**
  Produktivcode-Delta (`builder.py:74`, plus erweiterter Code-Kommentar
  darüber, ~+6 Zeilen Kommentar) + je ~2 Zeilen Migrations-Anpassung in den
  zwei Bestandstestdateien (Byte-String-Umstellung, kein Verhaltenswechsel
  dieser Tests). `docs/`-Aktualisierungen zählen nicht ins Limit.
- **Files:** 6 (neue Testdatei CREATE, Spec CREATE, `builder.py` MODIFY klein,
  2 Bestandstestdateien MODIFY klein, `docs/reference/sms_format.md` +
  `docs/reference/metric_output_matrix.md` MODIFY als DoD-Schritt).
- **Effort:** medium — kleiner als Scheibe 4/5 (die Symbolmenge ist klein,
  keine 26er-Metrik-Vollparametrisierung nötig), aber mit einem echten,
  sicherheitsrelevanten Fix statt reiner Charakterisierung tendenziell am
  oberen Ende der ursprünglich vom Matrix-Dokument geschätzten Spanne
  „niedrig-mittel/klein-mittel".

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `src/output/tokens/builder.py::PRIORITY`/`POSITIONAL`/`POS_INDEX` | Prüfling | Kürzungs-Priorität + Sortier-Position aller Grammatik-Klassen |
| `src/output/tokens/builder.py::UNAVAILABLE_SYMBOL` | Prüfling + Fix-Ziel | einziger Produktivcode-Edit dieser Scheibe |
| `src/app/metric_catalog.py::SMS_SYMBOL_BY_METRIC`/`SMS_MULTI_SYMBOLS_BY_METRIC` | Soll-Quelle | „rechnen statt tippen" — Katalog-Union als Soll-Menge |
| `src/output/tokens/hazard_symbols.py::HAZARD_SMS_SYMBOLS`/`LEVELLESS_HAZARDS` | zweites, unabhängiges Register | Kollisionsprüfung |
| `tests/unit/test_sms_token_symbol_register_ratchet.py` | Vorbild (Bauprinzipien) | echte Importe statt Regex, Vakuum-Schutz, keine handgepflegte Symbolliste |
| `tests/tdd/test_sms_trip_unavailable_marker.py`, `tests/tdd/test_sms_user_metric_order.py` | Migration (AC-S6-6) | referenzieren den Byte-String `"W?"` für den `UNAVAILABLE_SYMBOL`-Zweck, müssen mitgezogen werden |
| `docs/reference/metric_output_matrix.md` §3 (S2, S6), §7b | Auftragsquelle | PO-Vorentscheidung „eigene Achse", Sonderstrecken-Definition |
| Issue #1199 | Ziel für Nebenbefund | residuales Restrisiko der Fix-Wahl (s. Known Limitations 6), kein eigenes Issue |

## Implementation Details

### Die Soll-Menge (gemessen, nicht getippt)

```python
# Katalog-Union: alle Symbole, die eine waehlbare Metrik im SMS-Kanal traegt.
katalog_union = (
    set(SMS_SYMBOL_BY_METRIC.values())
    | {sym for tpl in SMS_MULTI_SYMBOLS_BY_METRIC.values() for sym in tpl}
)
# -> 22 (Single) + 9 (Multi) - 1 Ueberschneidung ("TH:", gehoert zu BEIDEN
#    Registern -- "thunder" ist by design in _SMS_SYMBOL_METRIC_IDS UND in
#    SMS_MULTI_SYMBOLS_BY_METRIC; api/routers/config.py:49-54 dokumentiert
#    dieselbe Dopplung mit einer Vorrang-Regel, Fix #1613) = 30 eindeutige
#    Katalog-Symbole.

system_symbols = {"DBG", "AV", "HR:", "M:", "MAX", "Z:"}
# -> 6 Symbole ohne Katalog-Metrik (Debug/Lawine/Vigilance/Fire).

assert katalog_union | system_symbols == set(PRIORITY.keys())  # 30 + 6 = 36
```

Dieses Gleichungspaar (30 Katalog + 6 System = 36 `PRIORITY`-Schlüssel, exakt)
ist der Kern von AC-S6-3/AC-S6-4 — es macht sowohl eine „Waise" (Katalogsymbol
ohne `PRIORITY`-Eintrag) als auch ein „unerklärtes Symbol" (`PRIORITY`-Eintrag,
der weder aus dem Katalog noch aus der benannten Systemliste stammt) sofort
sichtbar, ohne dass der Test eine eigene Symbolliste pflegt.

### Die HAZARD-Kollision — Diskriminanz ist der `!`-Präfix, nicht der Namensraum

`HAZARD_SMS_SYMBOLS.values()` = `{TH, FL, HR, W, SN, IC, HT, CD, FR, CL}` (roh,
ohne Doppelpunkt). Textuelle Überschneidung mit `PRIORITY`/`POSITIONAL`:

| Hazard-Kürzel | Kollidierendes Weather-Symbol | Live erreichbar? | Warum keine Verwechslung |
|---|---|---|---|
| `W` | `W` (Wind-Vorhersage) | ja | jeder Vorhersage-Token trägt IMMER einen Wert-Suffix (Zahl/`-`/`?`), jede geleveltee Hazard-Warnung trägt IMMER `:{Stufe}` — reines Byte-Präfix-Match ohne Suffix kommt bei `W` auf keiner Seite vor |
| `CL` | `CL` (Wolken tief, Vorhersage) | ja | `access_ban` ist der EINZIGE levellose Hazard (`LEVELLESS_HAZARDS`) und rendert bar `"CL"` ohne Suffix; kein Vorhersage-Token rendert je ein bares `"CL"` (immer Zahl/`-`/`?`-Suffix) — die Zeichenketten wären nur gleich, wenn beide bar wären |
| `HR`/`TH` | `HR:`/`TH:` (Vigilance, NICHT der Hazard-Renderpfad selbst) | **nein** — toter Pfad, s. Known Limitations 1 | kein Test nötig |

**Die tragende Zusicherung ist damit nicht „getrennter Namensraum", sondern
eine Format-Invariante:** der `!`-Block-Marker steht **exakt einmal** vor dem
ersten `official_alert`-Token (`_official_alerts()`-Docstring, `builder.py:212–214`)
und wird **keinem** anderen Kategorie-Token vorangestellt. Solange kein
Nicht-`official_alert`-Token selbst mit `"!"` beginnt, bleibt jede
Symbol-Kollision (auch eine künftige, heute nicht vorhergesehene) am
`!`-Präfix unterscheidbar. AC-S6-5 prüft genau das — generisch, nicht nur für
`W`/`CL` einzeln.

### Der Fix (AC-S6-6) — `UNAVAILABLE_SYMBOL` von `"W?"` auf `"X?"`

**Verifizierte Kollision:** Ein Wind-Datenausfall (`DailyForecast.has_data_gap
= True`, leere `wind_hourly`-Samples) lässt `render_threshold_peak_value()`
`"-"` liefern; `_gap_or("-", True)` (`builder.py:139–149`) macht daraus `"?"`;
`_mk_metric("W", ...)` (aufgerufen aus der Kernschleife `builder.py:346–361`)
baut `Token(symbol="W", value="?", ...)`; `Token.render()` (`dto.py:130–135`)
gibt `f"{symbol}{value}"` = **`"W?"`** zurück. **Bytegleich** mit
`UNAVAILABLE_SYMBOL = "W?"` (`builder.py:74`), das bei
`fc.official_alerts_unavailable = True` unabhängig von jedem Wind-Datenwert
erscheint (`_unavailable()`, `builder.py:225–231`). Beide Flags
(`DailyForecast.has_data_gap`, `NormalizedForecast.official_alerts_unavailable`)
sind strukturell unabhängige Booleans auf unterschiedlichen DTO-Ebenen — jede
Kombination ist möglich. Die resultierende SMS-Zeile ist für den Leser NICHT
unterscheidbar, ob „Wind-Daten fehlten" oder „amtliche Warnungen waren nicht
abrufbar" gemeint ist — sicherheitsrelevant, weil Letzteres ein aktiver
Ausfall der Warnungs-Kette ist, den ein Nutzer nicht mit einer bloßen
Wind-Datenlücke verwechseln darf.

**Gewählter Ersatzwert: `"X?"`.** Begründung:

1. **Länge bleibt bei 2 Zeichen.** `docs/reference/sms_format.md` §3.4d
   dokumentiert den Marker explizit als „2 Zeichen, GSM-7-sicher" — ein
   dokumentierter Design-Constraint (SMS-Zeichenbudget, keine
   Mehrfach-Segment-Kosten durch GSM-7-Sonderzeichen). Ein längeres Kürzel
   (z. B. `"AW?"`, `"WARN?"`) würde diesen Constraint verletzen und das
   ohnehin knappe 160-Zeichen-Budget zusätzlich belasten.
2. **Kollisionsfrei gegen das gesamte heutige Register**, verifiziert gegen
   `PRIORITY`, `POSITIONAL`, `SMS_SYMBOL_BY_METRIC`,
   `SMS_MULTI_SYMBOLS_BY_METRIC`, `HAZARD_SMS_SYMBOLS`: kein einziges Symbol
   in einem dieser fünf Register beginnt mit `"X"` (das gesamte
   Wetter-Kürzel-Alphabet nutzt `R, PR, W, G, N, K, D, FN, FK, FD, TH, HU, DP,
   WD, CP, PT, CT, CL, CM, CH, VS, SU, UV, HP, NL, SD, NS, SL, AV, WC, Z, MAX,
   M, HR, DBG` — kein `X`).
3. **`"!W?"` wurde geprüft und verworfen:** ein literal ins Symbol
   eingebettetes `"!"` würde beim Rendern wie ein zweiter,
   eigenständiger `!`-Block-Marker aussehen (`"...!TH:H@14 !W?..."`) — ein
   Leser könnte das als **zweite** amtliche Warnung lesen. Das verschärft
   genau die Ambiguität, die dieser Fix beheben soll, statt sie aufzulösen.
4. **Restrisiko, benannt statt verschwiegen:** „strukturell kollisionsfrei
   für alle Zeiten" ist nicht erreichbar, solange Symbol und Wert denselben
   Zeichenraum teilen — würde künftig eine Katalog-Metrik das Kürzel `"X"`
   erhalten UND über `_gap_or()` einen Gap-Wert `"?"` rendern können, entstünde
   dieselbe Kollisionsklasse erneut. Der Vollständigkeits-Wächter dieser
   Scheibe (AC-S6-1/3/4) würde eine neue Katalog-Metrik `"X"` selbst nicht
   automatisch als Kollision mit `"X?"` erkennen (verschiedene Dict-Schlüssel:
   `"X"` vs. `"X?"`) — deshalb trägt der Produktivcode-Kommentar an
   `UNAVAILABLE_SYMBOL` eine ausdrückliche Reservierungs-Notiz („`X` ist für
   `UNAVAILABLE_SYMBOL` reserviert, kein Katalog-Kürzel darf `X` werden").
   Nebenbefund-Eintrag #1199 für den Fall, dass dieses Risiko je eintritt.

**Migrations-Umfang (verifiziert per Grep, kein weiterer Fund):** genau zwei
Bestandstestdateien referenzieren den Byte-String `"W?"` **für den
`UNAVAILABLE_SYMBOL`-Zweck** (nicht für den davon unabhängigen
Wind-Gap-`"W?"`, der unverändert `"W?"` bleibt, weil er vom Wind-Symbol `"W"`
kommt, nicht von der Konstante):

- `tests/tdd/test_sms_trip_unavailable_marker.py:25` — `_MARKER = "W?"`, EIN
  Änderungspunkt (Modulkonstante), alle vier Testfunktionen referenzieren nur
  `_MARKER`.
- `tests/tdd/test_sms_user_metric_order.py:364` — `_exact_token_index(sms,
  "W?")` in `test_ac7_wintersport_metric_can_precede_forecast_metric_but_
  stays_before_system_blocks`; Kommentar in derselben Funktion (:348–349)
  ebenfalls anzupassen.

Beide Änderungen sind mechanisch (Byte-String-Austausch), ändern kein
Testverhalten und sind Teil des Fix-Umfangs von AC-S6-6, keine eigene AC.

## Bindende Test-Architektur-Entscheidung (Prüfort = Wirkort)

Alle ACs dieser Scheibe lesen die Register über **echten Import** der
Produktivmodule (`from output.tokens.builder import PRIORITY, POSITIONAL,
POS_INDEX, UNAVAILABLE_SYMBOL, _POSITION_SORTABLE_CATEGORIES`, `from
app.metric_catalog import SMS_SYMBOL_BY_METRIC, SMS_MULTI_SYMBOLS_BY_METRIC`,
`from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS,
LEVELLESS_HAZARDS`) — **kein Regex über Quelltext**, **keine handgepflegte
Symbolliste** außer der ausdrücklich benannten und kommentierten
Systemzeichen-Ausnahmeliste (Vorbild:
`tests/unit/test_sms_token_symbol_register_ratchet.py`, Modul-Docstring
„Bauprinzipien"). AC-S6-6 (der Fix) rendert zusätzlich über den ECHTEN
Token-Pfad (`build_token_line()`) mit realen `NormalizedForecast`/
`DailyForecast`-Objekten — kein isolierter `Token(...)`-Konstruktoraufruf,
sonst würde der Test nicht beweisen, dass die Kollision im tatsächlichen
Renderpfad entsteht (Lehre aus Scheibe 3/4: isolierte Direktaufrufe
umgehen den echten Choke-Point).

## Expected Behavior

- **Input:** die fünf Produktivregister unverändert (bis auf den
  Ein-Zeilen-Fix an `UNAVAILABLE_SYMBOL`), zwei gezielt konstruierte
  `NormalizedForecast`/`DailyForecast`-Fixtures für AC-S6-6 (eine mit
  Wind-Datenausfall, eine mit `official_alerts_unavailable=True`), keine
  echten PO-Daten.
- **Output:** eine neue, grüne Testdatei
  `tests/unit/test_sms_symbol_grammar_classes.py`, die Vollständigkeit,
  Kollisionsfreiheit und die Fix-Wirkung der Grammatik-Klassen-Register
  absichert; ein Ein-Zeilen-Produktivcode-Edit an `builder.py:74`; zwei kleine
  Migrations-Edits in Bestandstests.
- **Side effects:** keine über den benannten Fix hinaus. Kein neues
  Pflicht-Gate (neue, aber budgetierte Testdatei im bereits etablierten
  `tests/unit/`-Kern, läuft auf jedem Testlauf/Commit-Gate wie jeder andere
  Kern-Test).

## Acceptance Criteria

- **AC-S6-1 (Vollständigkeit `PRIORITY` ↔ `POSITIONAL`, bidirektional):**
  Gegeben die Menge aller Symbole, die eine Priorität ODER eine Position
  brauchen (`PRIORITY.keys()` ∪ `{UNAVAILABLE_SYMBOL}`, gerechnet 37), wenn
  sie gegen `POSITIONAL` gehalten wird, dann hat JEDES dieser 37 Symbole
  mindestens einen `POSITIONAL`-Eintrag, UND jedes Symbol, das in
  `POSITIONAL` auftaucht, ist entweder ein `PRIORITY`-Schlüssel oder
  `UNAVAILABLE_SYMBOL` — keine Waise in beide Richtungen.
  - Test: beide Mengen aus den echten Produktivkonstanten gerechnet (kein
    getipptes Literal außer `UNAVAILABLE_SYMBOL` selbst als Import),
    Vakuum-Schutz `len(...) >= 30` auf beiden Seiten, damit ein leer
    gewordenes Register nicht versehentlich „vollständig" erscheint.

- **AC-S6-2 (`TH:`-Doppeleintrag ist bewusst, Sortier-Kategorie schützt
  davor):** Gegeben `TH:` erscheint zweimal in `POSITIONAL` (Kategorie
  `forecast` UND `vigilance`), wenn `POS_INDEX` und
  `_POSITION_SORTABLE_CATEGORIES` gegen diese Struktur geprüft werden, dann
  sind beide `("TH:", "forecast")`/`("TH:", "vigilance")`-Tupel als
  eigenständige `POS_INDEX`-Schlüssel vorhanden, und `_POSITION_SORTABLE_
  CATEGORIES` enthält `"vigilance"` NICHT (nur `{"forecast", "wintersport"}`)
  — eine `MetricSpec.position`-Sortierung kann den Vigilance-Eintrag
  strukturell nicht erreichen.
  - Test: reine Struktur-Assertion auf den Konstanten selbst (kein Rendering,
    keine Ausführung des toten Vigilance-Pfads — Prüfung der DATEN, nicht des
    Laufwegs, analog zur Charakterisierung toter Pfade in Scheibe 1).

- **AC-S6-3 (Katalog-Vollständigkeit — 30 eindeutige Katalog-Symbole, alle in
  `PRIORITY`):** Gegeben die Vereinigung aus `SMS_SYMBOL_BY_METRIC.values()`
  (22 Symbole) und den geflatteten `SMS_MULTI_SYMBOLS_BY_METRIC.values()` (9
  eindeutige Symbole, `"TH:"` überlappt mit der Single-Tabelle — by design,
  s. Implementation Details), wenn diese Vereinigung (30 eindeutige Symbole)
  gegen `PRIORITY.keys()` gehalten wird, dann ist JEDES Katalog-Symbol ein
  `PRIORITY`-Schlüssel — kein Katalogsymbol fällt fälschlich als „Waise"
  durch, weil BEIDE Register (nicht nur eines) als Soll-Quelle dienen.
  - Test: `katalog_union.issubset(set(PRIORITY.keys()))`, Vakuum-Schutz
    `len(katalog_union) == 30` als exakte, aus dem Code gerechnete Zahl (nicht
    getippt: `len(set(SMS_SYMBOL_BY_METRIC.values()) | {s for t in
    SMS_MULTI_SYMBOLS_BY_METRIC.values() for s in t})`).

- **AC-S6-4 (System-Ausnahmeliste geschlossen — 36 = 30 Katalog + 6 System,
  keine unerklärten Symbole):** Gegeben die benannte, kommentierte
  Systemzeichen-Ausnahmeliste (`{"DBG", "AV", "HR:", "M:", "MAX", "Z:"}` — 6
  Symbole ohne Katalog-Metrik), wenn `PRIORITY.keys()` minus (Katalog-Union
  ∪ Systemzeichen-Ausnahmeliste) gebildet wird, dann ist die Differenzmenge
  LEER — jedes `PRIORITY`-Symbol ist entweder katalogrückführbar oder auf der
  Ausnahmeliste, keine dritte, unerklärte Kategorie.
  - Test: `set(PRIORITY.keys()) - (katalog_union | system_symbols) == set()`,
    UMGEKEHRT auch `system_symbols.isdisjoint(katalog_union)` (die
    Ausnahmeliste darf sich nicht mit dem Katalog überschneiden — sonst wäre
    sie keine echte Ausnahme).

- **AC-S6-5 (Format-Invariante — `!`-Präfix als einziger Diskriminator
  gegenüber `HAZARD_SMS_SYMBOLS`):** Gegeben ein vollständig gerenderter
  Token-Line-Durchlauf über alle Nicht-`official_alert`-Kategorien
  (`forecast`, `wintersport`, `fire`, `vigilance`-Konstanten als reine
  Struktur, `unavailable`, `debug`), wenn jedes gerenderte Token-Ergebnis
  (`Token.render()`) geprüft wird, dann beginnt KEIN einziges mit dem
  Zeichen `"!"` — der `!`-Block-Marker bleibt exklusiv dem
  `official_alert`-Fusionsmechanismus vorbehalten und ist damit der einzige
  verlässliche Diskriminator gegenüber jedem textuell kollidierenden
  Hazard-Kürzel (konkret verifiziert für `W`/`CL`, s. Implementation
  Details-Tabelle).
  - Test: echtes Rendering eines vollen `build_token_line()`-Durchlaufs mit
    allen wählbaren Metriken aktiviert (kein Wind-/Warn-Ausfall, damit
    `UNAVAILABLE_SYMBOL` hier nicht mitmischt — das ist AC-S6-6), Assertion
    `not any(tok.render().startswith("!") for tok in ...)`; zusätzlich
    gezielte Stichprobe: `access_ban`-Hazard rendert bar `"CL"`, forecast-`CL`
    (Wolken tief) rendert nie bar (immer mit Zahl/`-`/`?`-Suffix) — beide
    Renderformen werden bytegenau verglichen und dürfen sich NIE decken.

- **AC-S6-6 (DER FIX — `UNAVAILABLE_SYMBOL`-Kollision mit dem
  Wind-Gap-Marker behoben, TDD-RED):** Gegeben zwei unabhängige Zustände —
  (a) ein Wind-Datenausfall (`DailyForecast.has_data_gap=True`, leere
  `wind_hourly`) OHNE amtlichen Warnungs-Ausfall, (b) ein amtlicher
  Warnungs-Ausfall (`NormalizedForecast.official_alerts_unavailable=True`)
  OHNE Wind-Datenausfall — wenn beide Szenarien über den echten
  `build_token_line()`-Pfad gerendert werden, dann sind die jeweils
  resultierenden Marker-Token-Strings NIEMALS bytegleich.
  - **Vorher (heute, ROT):** Szenario (a) rendert `"W?"` (Wind-Symbol + Gap),
    Szenario (b) rendert `"W?"` (`UNAVAILABLE_SYMBOL`, unverändert) — beide
    Strings sind identisch, der Test schlägt fehl. Das ist der einzige rote
    Anteil dieser Scheibe (analog zum Gewitter-Prozentzeichen-Fix in Scheibe
    1, AC-5).
  - **Nachher (nach dem Fix, GRÜN):** `UNAVAILABLE_SYMBOL` ist auf `"X?"`
    geändert (`builder.py:74`, s. Implementation Details für die Begründung
    der Wahl); Szenario (a) bleibt unverändert `"W?"`, Szenario (b) liefert
    jetzt `"X?"` — beide Strings sind verschieden, der Test wird grün.
  - Test: zwei echte `build_token_line()`-Aufrufe (nicht isolierter
    `Token(...)`-Konstruktor), Assertion auf Ungleichheit der beiden
    Marker-Strings; zusätzlich Regressions-Assertion, dass Szenario (a)s Wert
    unverändert `"W?"` bleibt (der Fix darf NICHT den Wind-Token selbst
    verändern) UND dass Szenario (b)s Marker weiterhin `!`-frei bleibt
    (Anschluss an AC-S6-3 aus dem ursprünglichen `feat_1349_sms_unavailable.md`
    AC-3, unverändert).

## Known Limitations

1. **`TH:`/`HR:`-Vigilance-Kollision bleibt strukturell tot, kein Fix, kein
   Test.** `_vigilance()` (`builder.py:199–208`) liest `fc.provider !=
   "meteofrance"` und liefert sonst `[]`. Verifiziert: **kein** produktiver
   `NormalizedForecast(...)`-Konstruktoraufruf im gesamten `src/` setzt
   `provider="meteofrance"` — `trip_result.py:84` und `sms_trip.py:498` lassen
   den Default `"open-meteo"` (`dto.py:76`) stehen. Analog zu
   `CorridorEvent`/`OnsetEvent` aus Scheibe 1: „Ein Wächter über einen toten
   Pfad bewacht nichts" — die Kollision bleibt dokumentiert (s. Implementation
   Details-Tabelle), aber unbewacht.
2. **AC-S6-5 hält eine Format-Invariante fest, keine strukturelle
   Namensraum-Trennung.** Ein künftiger Formatwechsel — z. B. würde
   `access_ban` seine `LEVELLESS_HAZARDS`-Eigenschaft verlieren, oder ein
   Vorhersage-Token würde je einen leeren Wert ohne Suffix rendern — könnte
   die heutige Sicherheit stillschweigend aufheben. AC-S6-5s generische
   `!`-Präfix-Prüfung fängt genau diese Klasse von Regression (jede
   Verletzung des `!`-exklusiv-für-official_alert-Prinzips wird rot), aber
   NICHT jede denkbare neue Formatverletzung außerhalb dieses Mechanismus.
3. **`format_modes`/`default_format_mode` (1:1-Katalogfelder) sind NICHT
   Gegenstand dieser Scheibe.** Laut `metric_output_matrix.md` §5 Punkt 1
   gehören sie in die Hauptmatrix (S1-S5-Achse), nicht in diesen
   Symbol-Wächter — nur die 1:n-Grammatik (`SMS_MULTI_SYMBOLS_BY_METRIC`)
   sprengt die Hauptmatrix und braucht diese eigene Achse.
4. **Fläche 8 (`metric_output_matrix.md` §4, „Einheiten und Nachkommastellen
   je Kanal") wird nur „teilweise" gedeckt, wie das Dokument selbst
   einschränkt** — diese Scheibe prüft Symbol-Register-Konsistenz, nicht
   Dezimalstellen/Einheiten-Formatierung (das ist bereits separat über
   AC-S5-4 in Scheibe 5 für den Compare-Pfad behandelt; ein SMS-seitiges
   Pendant ist NICHT Gegenstand hier).
5. **Scheibe 1-5 (Metrik-ID-basierte Achsen) sind ausdrücklich NICHT
   Gegenstand.** Diese Scheibe iteriert bewusst über Symbole/Grammatik-Klassen,
   nicht über Metrik-IDs — kein Duplikat der bestehenden Achsen in
   `tests/tdd/test_channel_metric_matrix.py`.
6. **Scheibe 7 (Reihenfolge jenseits E-Mail/Telegram-rich) und Scheibe 8
   (Compare-Kanal-Tabs Frontend) sind NICHT Gegenstand.** Scheibe 7 ist laut
   Matrix-Dokument bis zur PO-Entscheidung 7a blockiert; Scheibe 8 ist ein
   eigenes, großes Vorhaben (Datenmodell/Persistenz/Editor), keine
   Test-Scheibe. Diese Scheibe (6) ist laut Abhängigkeitsbild „jederzeit
   parallel" zu beiden.
7. **Die Wahl von `"X?"` ist nicht für alle Zeiten garantiert
   kollisionsfrei** (s. Implementation Details, Punkt 4 der Begründung) —
   eine künftige Katalog-Metrik mit Kürzel `"X"` und Gap-fähigem Rendering
   würde dieselbe Kollisionsklasse reproduzieren. Der Code-Kommentar an
   `UNAVAILABLE_SYMBOL` reserviert `"X"` ausdrücklich; ein automatischer Fang
   einer künftigen Verletzung dieser Reservierung ist NICHT Teil dieser
   Scheibe (AC-S6-1/3/4 prüfen Dict-Schlüssel-Gleichheit, nicht
   Render-Zeit-Kollisionen zwischen unterschiedlich langen Strings) →
   Nebenbefund-Eintrag #1199, falls es je eintritt.
8. **Die zwei migrierten Bestandstests (`test_sms_trip_unavailable_marker.py`,
   `test_sms_user_metric_order.py`) werden NICHT umbenannt oder
   umstrukturiert** — nur der Byte-String-Literalwert wird angepasst. Eine
   Konsolidierung dieser Dateien in die neue Testdatei ist NICHT Gegenstand
   (CLAUDE.md „kein Big-Bang-Reorg des Bestands").

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie WIRKT —
oder nur dort, wo der Code steht?** Konkret: AC-S6-5/AC-S6-6 MÜSSEN gegen den
ECHTEN `build_token_line()`-Renderpfad laufen, nicht gegen isolierte
`Token(...)`-Konstruktoraufrufe — sonst beweist der Test nur, dass ein
konstruiertes Objekt sich so verhält, wie der Test es konstruiert hat.

**Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer
Sicherungskopie — nie `git checkout/stash/reset`):**

- Einen Schlüssel aus `PRIORITY` entfernen (z. B. `"CH"` streichen) — MUSS
  AC-S6-1 rot werden lassen (Waise in `POSITIONAL`, die keine `PRIORITY` mehr
  hat).
- Einen zusätzlichen `POSITIONAL`-Eintrag ohne `PRIORITY`-Pendant einfügen
  (z. B. `("QQ", "forecast")`) — MUSS AC-S6-1 rot werden lassen (unerklärte
  Position ohne Priorität).
- Ein Symbol aus `SMS_MULTI_SYMBOLS_BY_METRIC["thunder"]` entfernen (z. B.
  `"TH+:"` streichen) — MUSS AC-S6-4 rot werden lassen (die 36=30+6-Gleichung
  kippt: `"TH+:"` bleibt in `PRIORITY`, fällt aber aus der Katalog-Union
  heraus und landet als unerklärtes Symbol in der Differenzmenge).
- `UNAVAILABLE_SYMBOL` versehentlich zurück auf `"W?"` setzen (den Fix
  rückgängig machen) — MUSS **genau AC-S6-6** rot werden lassen. Das ist der
  wichtigste Fang dieser Scheibe: er beweist, dass der Fix wirklich geprüft
  wird, nicht nur behauptet.
- Einen Forecast-Token testweise mit führendem `"!"` rendern lassen (z. B.
  `_mk_metric()`s `symbol`-Parameter für `"W"` durch `"!W"` ersetzen) — MUSS
  AC-S6-5 rot werden lassen.

## Definition of Done

- [ ] AC-S6-1 bis AC-S6-6 grün
- [ ] Adversary-Verdict VERIFIED, alle fünf Pflicht-Mutationen gefangen
- [ ] `docs/reference/sms_format.md` §3.4d + Legende (Zeilen 45/64/262/265/267/
      270/273) von `"W?"` auf `"X?"` umgetragen — die Wire-Format-Spec darf dem
      Code nach dem Fix nicht widersprechen
- [ ] `docs/reference/metric_output_matrix.md` §3 (Sonderstrecken S2/S6), §4
      (Fläche 8, „teilweise") und §6 (Scheibe 6) auf erledigt/referenziert
      umgetragen
- [ ] Issue #1703 Scheiben-Checkbox gesetzt, Ergebnis kommentiert (inkl. Hinweis
      auf den Sicherheits-Fix, nicht nur „Wächter ergänzt")

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Neue, eigenständige Testdatei nach expliziter
  PO-Vorentscheidung (`metric_output_matrix.md` §7b), aber kein neuer
  Pflicht-Gate-Mechanismus — läuft im bereits etablierten `tests/unit/`-Kern
  wie jeder andere Kern-Test (Option C im weiteren Sinne: Erweiterung der
  bereits budgetierten Epic-#1703-Testinitiative, nur als eigene Datei statt
  als Achse in `test_channel_metric_matrix.py`, weil die 1:n-Struktur die
  Hauptmatrix sprengen würde). Der `UNAVAILABLE_SYMBOL`-Fix ist keine neue
  Entscheidungsfläche (kein Kanal-, Provider-, Datenmodell-, Auth- oder
  Editor-Paradigma-Wechsel) — er korrigiert einen bytegleichen
  Kollisionsfehler innerhalb eines bereits bestehenden, PO-entschiedenen
  Markers (#1349).

## Changelog

- 2026-08-12: Initial spec created (Epic #1703, Scheibe 6). Vollständigkeits-
  und Kollisionswächter über die SMS-Symbol-Grammatik-Klassen spezifiziert
  (AC-S6-1 bis AC-S6-5, reine Charakterisierung); die verifizierte,
  sicherheitsrelevante `UNAVAILABLE_SYMBOL`/Wind-Gap-Kollision wird als
  einzige Ausnahme dieser Scheibe gefixt (AC-S6-6, `"W?"` → `"X?"`),
  begründet über CLAUDE.md-Nebenbefund-Triage Kriterium (b). Korrektur der
  `POSITIONAL`-Zählung gegenüber dem Context-Dokument (38 statt 37 Einträge,
  nachgerechnet). Migrationsumfang für zwei Bestandstestdateien benannt.
