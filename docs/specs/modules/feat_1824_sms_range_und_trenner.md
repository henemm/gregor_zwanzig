---
entity_id: feat_1824_sms_range_und_trenner
type: module
created: 2026-08-13
updated: 2026-08-13
status: draft
version: "1.0"
tags: [sms, premium-sms, token, format, wire-format]
---

# SMS-Format: Temperatur-Bereichs-Token + Trennzeichen bei Buchstaben-Werten (#1824)

## Approval

- [ ] Approved

## Purpose

Ändert das SMS-/Premium-SMS-Wire-Format (`docs/reference/sms_format.md`) in zwei unabhängigen
Punkten, beide aus der Lektüre eines echten KHW-Briefings entstanden: (A) die Temperatur-Paare
Tiefst/Höchst (`K13 D27`) verschmelzen zu einem einzigen Bereichs-Token (`D13/27`), (B) Token mit
Buchstaben-Wert ohne Trenner (`WDNW`, `PTS`) bekommen denselben Doppelpunkt-Trenner, den `TH:`/`HR:`
bereits tragen (`WD:NW`, `PT:S`). Ziel: kompaktere, konsistent lesbare Kurzform ohne neue
Formatregeln — beide Änderungen wenden ein im Code bereits vorhandenes Muster konsequent an,
statt ein neues zu erfinden.

## Source

- **File:** `src/output/tokens/builder.py` (Haupt-Prüfling: Temperatur-Schleife `build_token_line()`
  Zeile 316-355, `PRIORITY` Zeile 47-65, `POSITIONAL` Zeile 88-109, Klasse-(c)-Schleife Zeile 407-422)
- **Identifier:** `build_token_line()`, `PRIORITY`, `POSITIONAL`
- Vollständige Dateiliste (Produktivpfad + Katalog + Konsumenten) siehe „Implementation Details"
  und „Estimated Scope".

> **Schicht-Hinweis:** Alles Betroffene liegt in der Python-Core-Schicht
> (`src/output/tokens/`, `src/app/metric_catalog.py`, `src/output/renderers/`, `api/routers/config.py`)
> plus einer rein abgeleiteten Frontend-Anzeige (`WeatherMetricsTab.svelte` liest nur
> `/api/sms-symbols`, führt keine eigene Kürzel-Liste). Kein Go-Code betroffen.

## Estimated Scope

- **LoC:** Produktivcode ~70-100 — deutlich kleiner als eine erste interne Einschätzung vermuten
  ließ, weil (A) nach dem PO-Entscheid (`K`/`D` bleiben eigenständig, nur der „beide
  gewählt"-Fall verschmilzt) als reiner Merge-Schritt NACH der bestehenden, unveränderten
  Sichtbarkeitslogik implementierbar ist: `builder.py` ~30-40 (ein Zusammenführungs-Schritt in der
  Temperatur-Schleife, sonst keine Änderung — `PRIORITY`/`POSITIONAL` bleiben unangetastet),
  `trip_report.py` **unverändert** (`_AGG_GATE_SYMBOLS` bleibt exakt wie heute, s. Implementation
  Details), `render.py` **unverändert** für (A), ~5 für (B) (`DROP_ORDER`-Literale `WD:`/`PT:`),
  `metric_catalog.py` ~5-10 (nur (B): `SMS_SYMBOL_GRAMMAR`-Ergänzung), `builder.py` zusätzlich
  ~5-10 für (B) (Klasse-(c)-Tupel-Literale, `PRIORITY`/`POSITIONAL`-Schlüssel `WD:`/`PT:`). Dazu
  Test-Änderungen über ~27 Dateien (Blast Radius laut Analyse: 24 für (A), 3 für (B), teils
  überlappend), meist kleine Diffs (Symbol-Ersetzung in Assertions/Fixtures) plus 6 Golden-Dateien
  (5× `tests/golden/sms/*.txt` + 1× `tests/golden/text_report/stubaier-skitour-evening.txt`), die
  NEU ERZEUGT und geprüft werden müssen (nicht von Hand editiert). `docs/reference/sms_format.md`
  (§2/§3.2/§3.2a/§4/§6/§9/§12, ca. 15 Stellen) zählt nicht gegen das LoC-Limit (Doku-Ausnahme).
- **Files:** ~5-6 Produktivdateien, 1 bindende Referenz-Doku, 1 abzulösende Modul-Spec
  (`fix_1660b_sms_token_wiring.md`), ~27 Testdateien, 6 Golden-Fixtures.
- **Effort:** medium. Die Produktivlogik ist klein und gut eingegrenzt; der Aufwand kommt aus der
  Breite der Test-/Golden-/Doku-Berührungspunkte, nicht aus der Komplexität der Änderung selbst.
  Das Workflow-LoC-Budget (250) reicht für den Produktivcode voraussichtlich aus; ob es inklusive
  Testdateien reicht, hängt vom tatsächlichen Diff ab — im Zweifel `workflow.py set-field
  loc_limit_override 500` vor Implementierung setzen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/reference/sms_format.md` | Reference (bindend) | Single Source of Truth für das Wire-Format — §2/§3.2/§3.2a/§4/§6/§9/§12 müssen mit dieser Spec synchron bleiben |
| `docs/specs/modules/fix_1660b_sms_token_wiring.md` | Module-Spec | AC-6/AC-7 fordern wörtlich `WDNW`/`PTS` — durch (B) abgelöst, siehe „Known Limitations" |
| `docs/specs/modules/fix_1677_sms_reihenfolge.md` | Module-Spec | POSITIONAL-Sortierung behandelt `K`/`D`/`FK`/`FD`/`WD`/`PT` als unabhängige Einzelanker — Anker-Menge bleibt für (A) unverändert (`K`/`FK` bleiben bestehen, PO-Entscheid 2026-08-13), nur `WD`/`PT`-Symbole ändern sich auf `WD:`/`PT:` (B) |
| `docs/specs/modules/trip_min_temp_and_felt_shortforms.md` (#1410) | Module-Spec | Ursprung der Kürzel `K`/`D`/`FK`/`FD` — Namensgebung bleibt vollständig gültig, keines der vier Kürzel wird zurückgezogen; (A) ergänzt lediglich eine zusätzliche Kombinationsform bei doppelter Auswertungswahl |
| `SMS_MULTI_SYMBOLS_BY_METRIC` (`src/app/metric_catalog.py`) | Code | Bleibt für (A) **unverändert** (`K`/`D`/`FK`/`FD`/`WC` bleiben alle eingetragen, PO-Entscheid 2026-08-13) |
| `SMS_SYMBOL_GRAMMAR` (`src/app/metric_catalog.py`) | Code (Single Source) | (B) läuft über diesen bereits etablierten Ableitungs-Mechanismus (Präzedenz `"thunder": "TH:"`) — kein neuer Mechanismus nötig |
| `MetricConfig.aggregations` (#1357, Wirkung in SMS seit #1660 Scheibe A) | Feature | Bestimmt je Trip, ob Tiefst-/Höchstwert/beide/keins gewählt sind — steuert die vier Zustände in (A) |

## Implementation Details

### (A) Range-Token — Trennzeichen-Entscheidung

**Trennzeichen ist `/`** (Tech-Lead-Entscheid 2026-08-13, vom PO nicht widersprochen). Ein
Bindestrich scheidet aus: `D-12--4` (Wintertag, `min=-12`, `max=-4`) wäre mit `-` gleichzeitig
Trenner UND Vorzeichen — nicht eindeutig parsbar. Mit `/` gilt EINE Regel ohne Ausnahme:
`D13/27` bzw. `D-12/-4`. `/` ist GSM-7-sicher (1 Septet) und im gesamten Token-Format bisher
unbenutzt (kollidiert mit keinem bestehenden Trenner: Doppelpunkt für Grammatik-Symbole, `@` für
Stunden, `()` für Peak-Klammern, `,` für Fire-IDs). Der En-Dash `–` des E-Mail-Renderers
(`email/helpers.py:945,1473`) ist NICHT GSM-7 und würde die SMS still auf UCS-2 zwingen (halbe
Zeichenkapazität) — als SMS-Trenner unbrauchbar, unabhängig von dieser Spec.

**`K`/`D` (bzw. `FK`/`FD`) bleiben unverändert die Kürzel für Einzelwerte.** Ein Bereichs-Token
entsteht AUSSCHLIESSLICH, wenn BEIDE Auswertungen (Tiefst- UND Höchstwert) gewählt sind — dann
ersetzt EIN Token unter dem Kürzel `D` (bzw. `FD`) die bisherigen zwei separaten Token
`K{min} D{max}`. `N`/`FN` (Nacht-Tiefsttemperatur am Schlafplatz) sind davon **nicht** betroffen —
eigene Metriken ohne Auswertungswahl, PO-Vorgabe wörtlich: „Bei Nachttemperatur bleibt es aber bei
der Tiefsttemperatur." `WC` (Wintersport-Tageskennzahl) ist ebenfalls kein Teil dieses Merges und
bleibt unverändert eigenständig — es hängt an `wind_chill_c`, nicht an der Auswertungswahl von
`K`/`D`, und trägt ohnehin keinen Buchstaben-Folgewert, den (B) beträfe.

🔴 **PO-Entscheid 2026-08-13, überstimmt eine frühere Eigenentscheidung dieser Spec-Fassung** (s.
Changelog): eine erste Fassung dieser Spec schlug vor, bei „nur Tiefstwert gewählt" ebenfalls den
Anker `D` wiederzuverwenden (`D13` statt `K13`), mit der Begründung, `K` verschwinde sonst
konsistent als eigenständiges Symbol. Der PO hat dem widersprochen: `D` steht im Format an jeder
anderen Stelle für den HÖCHSTWERT — ein `D13`, das in Wahrheit den Tiefstwert zeigt, ist auf einem
tourenentscheidungs-relevanten Kanal **Falschinformation**, nicht nur überraschend. Die geltende
Regel ist die einfachere: `K`/`FK` bedeuten immer Tiefstwert, `D`/`FD` bedeuten Höchstwert ODER —
nur wenn beide Auswertungen gewählt sind — den Bereich von Tiefst- bis Höchstwert.

**Vier Auswertungs-Zustände (`MetricConfig.aggregations` je Metrik `temperature`/`wind_chill`,
Werte `min`/`max`/`avg`, Wirkung in der SMS seit #1660 Scheibe A über `_AGG_GATE_SYMBOLS` in
`trip_report.py:420-430`):**

| Auswertungswahl | Ausgabe (gemessen) | Ausgabe (gefühlt) | Änderung ggü. heute |
|---|---|---|---|
| min UND max gewählt | `D13/27` | `FD13/27` | **NEU:** ein Token statt zwei |
| nur max gewählt | `D27` | `FD27` | unverändert (heutige Einzelform) |
| nur min gewählt | `K13` | `FK13` | unverändert (heutige Einzelform) |
| weder min noch max (nur `avg`) | kein Token | kein Token | unverändert — `avg` kennt die SMS nicht (#1660 Scheibe A DEC-1) |

Der einzige Verhaltens-Unterschied zu heute ist also exakt der Fall „beide Auswertungen gewählt" —
die drei anderen Zustände sind bereits heute exakt so, wie sie in der Tabelle stehen (seit #1660
Scheibe A, `_AGG_GATE_SYMBOLS`), und bleiben durch diese Spec unangetastet.

**Null-/Lücken-Kombinationen des Range-Tokens** (gilt nur für den „beide gewählt"-Fall). Jede Hälfte (min-Teil, max-Teil) kann unabhängig
einen Wert tragen, geprüft-aber-kein-Wert (`-`) oder Datenlücke (`?`) sein — vollständige 3×3-Matrix:

| min-Teil ↓ / max-Teil → | Wert (`27`) | `-` | `?` |
|---|---|---|---|
| **Wert (`13`)** | `D13/27` | `D13/-` | `D13/?` |
| **`-`** | `D-/27` | `D-/-` ⚠️ | nicht erreichbar ⁽¹⁾ |
| **`?`** | `D?/27` | nicht erreichbar ⁽¹⁾ | `D?/?` ⚠️ |

⁽¹⁾ **Reachability-Hinweis:** `_gap_or()` (`builder.py:149-159`) entscheidet die `-`/`?`-Wahl heute
anhand EINES tagesweiten Flags (`today.has_data_gap`), das für beide Hälften identisch übergeben
wird. Beide gleichzeitig fehlenden Hälften zeigen deshalb heute IMMER dieselbe Null-/Lücken-Form
(`D-/-` oder `D?/?`), nie eine gemischte (`D-/?` bzw. `D?/-`). Diese Spec führt **kein** Konzept
eines pro-Hälfte-Gap-Flags ein — die beiden markierten Zeilen (⚠️) sind die tatsächlich
erreichbaren „beide fehlen"-Fälle. Die volle 3×3-Matrix ist dennoch der korrekte
Render-**Kontrakt** (Token.render() macht ohnehin keine Fallunterscheidung, s.u.) und beschreibt,
was ein Konsument der Token-Zeile syntaktisch akzeptieren muss — nur Testfixtures können die zwei
„nicht erreichbar"-Zellen mit dem heutigen Mechanismus nicht künstlich erzeugen.

**Rendering braucht keine Sonderbehandlung.** `Token.render()` (`dto.py:130-135`) bleibt
unverändert: `if self.value == "-": return f"{symbol}-"` greift nur bei der alten
Bare-Null-Form; ein Range-Wert wie `"-/-"` ist ungleich `"-"` und fällt in den `else`-Zweig
(`f"{symbol}{value}"`), liefert also korrekt `D-/-`.

**Implementierung im Builder — minimaler, gut eingegrenzter Eingriff.** Die bestehende
Temperatur-Schleife (`build_token_line()`, `builder.py:316-355`) berechnet heute für `K` und `D`
(bzw. `FK`/`FD`) UNABHÄNGIG je einen Token-oder-nichts über dieselbe Sichtbarkeits-/
`needs_spec`-Logik wie bisher — **das bleibt unverändert**. NEU ist ausschließlich ein
Zusammenführungs-Schritt NACH dieser Berechnung: existieren nach den bestehenden Prüfungen sowohl
ein `K`- als auch ein `D`-Token (bzw. `FK`+`FD`), werden sie zu EINEM Token verschmolzen —
`Token(symbol="D", value=f"{k_token.value}/{d_token.value}", ...)` — statt beide unabhängig an die
Token-Liste angehängt zu werden. Existiert nur einer von beiden (oder keiner), ändert sich nichts —
der bestehende Pfad läuft exakt wie heute weiter. Diese Kapselung hat einen wichtigen Nebeneffekt:
**kein anderer Teil von `builder.py` und kein anderer Konsument muss angefasst werden.**

- **`PRIORITY`** (Zeile 47-65) und **`POSITIONAL`** (Zeile 88-109): **keine Änderung.** Die
  Einträge `"K": 6`/`"FK": 4` bzw. `("K", "forecast")`/`("FK", "forecast")` bleiben bestehen und
  werden weiterhin gebraucht — bei „nur min gewählt" entsteht weiterhin ein eigenständiges
  `K`/`FK`-Token, das über `PRIORITY[sym]` (Zeile 352, ungeschützter Zugriff) seine Priorität
  bezieht.
- **Kürzungsreihenfolge** (`render.py:84-99`): **kein Code-Änderungsbedarf** — die Literal-Tupel
  `("FN", "FK", "FD")` und `("K", "D", "N")` bleiben unverändert gültig. Die Atomarität des
  Range-Tokens (AC-16) ergibt sich automatisch aus der Merge-Konstruktion: im „beide
  gewählt"-Fall existiert nach dem Merge nur noch EIN Token mit Symbol `D` in der Token-Liste (das
  `K`-Token wurde nie separat angehängt) — `_drop_first(tokens, "K")` findet dadurch nichts
  (No-op), `_drop_first(tokens, "D")` entfernt den kompletten Bereichs-Token in einem Schritt.
  **Eine Nebenwirkung, kein Bug:** die Kürzung verliert dadurch im „beide gewählt"-Fall eine
  Granularitätsstufe gegenüber heute — heute konnte `K` allein fallen (ein Kürzungsschritt) und
  `D` danach separat (zweiter Schritt); künftig fällt der Bereichs-Token als EIN Schritt (s.
  „Known Limitations"). In den Fällen „nur min"/„nur max" ändert sich an der Kürzung nichts, weil
  dort ohnehin nur je ein Token existiert(e).
- **`SMS_MULTI_SYMBOLS_BY_METRIC`** (`metric_catalog.py:700-706`): **keine Änderung** —
  `"temperature": ("K", "D")` und `"wind_chill": ("FK", "FD", "WC")` bleiben exakt wie heute. Die
  Editor-Kürzel-Badges (`/api/sms-symbols` → `WeatherMetricsTab.svelte`) zeigen dadurch weiterhin
  BEIDE Kürzel je Metrik — nach dem PO-Entscheid ist das korrekt, weil beide real vorkommen können
  (s. AC-17).
- **`_kurzform_kuerzel()`** (`metric_catalog.py:728-745`, nimmt `mehrfach[0]` = `K` bzw. `FK`):
  **keine Änderung nötig.**

### (B) Trennzeichen bei Buchstaben-Werten

🔴 **Exakt wie bei `TH:` umsetzen — keine neue Regel.** Der Doppelpunkt wird Teil des
Symbol-Strings, nicht des Werts, genau wie `FORECAST_TH = "TH:"` (`builder.py:17`),
`VIGI_HR = "HR:"` (`:29`), `"Z:"`/`"M:"` (`:250,256`). `Token.render()` (`dto.py:130-135`) macht
für diesen Fall bereits alles Nötige, ohne jede Änderung:

- Wertform: `symbol="WD:"`, `value="NW"` → `f"{symbol}{value}"` = `WD:NW`
- Leerform: `symbol="WD:"`, `value="-"` → trifft `if self.value == "-": return f"{symbol}-"` →
  `WD:-` (belegtes Präzedenzverhalten: `TH:` rendert ebenso `TH:-`, `sms_format.md:122,382`)
- Lückenform: `symbol="WD:"`, `value="?"` → `f"{symbol}{value}"` = `WD:?`

Analog `PT:` / `PT:S` / `PT:-` / `PT:?`.

**Einziger Änderungsort:** `SMS_SYMBOL_GRAMMAR` in `metric_catalog.py:661` — bereits exakt der
Mechanismus, der `"thunder": "TH:"` trägt (Kommentar dort: „Benannte Ausnahme von der
Register-Ableitung"). Ergänzung um `"wind_direction": "WD:", "precip_type": "PT:"`. Das propagiert
automatisch über `SMS_SYMBOL_BY_METRIC` (abgeleitet, `metric_catalog.py:665-668`) in:

- `build_extended_metric_specs()` (`sms_trip.py:66-91`) — `MetricSpec.symbol` wird `"WD:"`/`"PT:"`
- `trip_report.py:336-338` (Schwellwert-Dict, `SMS_SYMBOL_BY_METRIC[mid]: sms_threshold`)
- `api/routers/config.py:48-54` (`/api/sms-symbols`, `_symbols_for()` ruft bereits
  `.rstrip(":")` auf — Editor-Badge zeigt weiterhin `"WD"`/`"PT"` ohne Doppelpunkt, **keine
  sichtbare Änderung** in `WeatherMetricsTab.svelte`)
- `_kurzform_kuerzel()` (`metric_catalog.py:728-745`) — `.rstrip(":")` am Rückgabewert, gleiche
  Rückrechnung, `compact_label` bleibt `"WD"`/`"PT"`

**Zwei Stellen in `builder.py`/`render.py` müssen den neuen Symbol-STRING kennen** (der Wert kommt
korrekt über `by_sym.get(sym)`/`SMS_SYMBOL_BY_METRIC`, aber Konstanten-Tabellen, die das Symbol als
Literal führen, müssen den Literal-String ändern):

1. **`builder.py` Klasse-(c)-Schleife** (Zeile 409-411): Tupel-Literale `("WD", ...)`/`("PT", ...)`
   → `("WD:", ...)`/`("PT:", ...)`.
2. **`PRIORITY`** (Zeile 63): Schlüssel `"WD": 2, "PT": 2` → `"WD:": 2, "PT:": 2`.
3. **`POSITIONAL`** (Zeile 97-98): `("WD", "forecast")`/`("PT", "forecast")` →
   `("WD:", "forecast")`/`("PT:", "forecast")`.
4. **`render.py::DROP_ORDER`** (Zeile 16): `"WD"`/`"PT"` in der Liste → `"WD:"`/`"PT:"` (sonst
   matcht `_drop_first()` das neue Symbol nicht mehr und `WD:`/`PT:` fallen unter Kürzungsdruck
   NIE mehr — stiller Kürzungs-Regressionsfall).

**Rand-Bestätigung (PO-bestätigt, aus der Analyse):** `DBG[...]` beginnt mit `[`, nicht mit einem
Buchstaben-Wert im Sinne dieser Regel — unberührt. `CL` (amtliches `access_ban`-Flag) hat gar
keinen Wert (`sms_format.md:244`: „erscheint als blankes `CL` ohne Doppelpunkt und ohne Stufe") —
unberührt. Beide bleiben exakt wie heute.

### Testhelfer — Wurzel des Blast Radius

`tests/tdd/_min_temp_felt_fixtures.py:207,223` und `tests/tdd/_hiking_window_fixtures.py:484,506-515`
parsen Temperatur-Token strukturell über `fullmatch(rf"{symbol}(-?\d+|-|\?)$")`. Dieses Pattern
matcht `D13/27` NICHT (der `/` fällt aus `-?\d+|-|\?` heraus) — die Helfer müssen um eine
Range-fähige Variante ergänzt werden (z.B. `(-?\d+(/-?\d+|/-|/\?)?|-|\?)$` oder ein zweites
Extraktions-Pattern für die Zwei-Hälften-Form). **Diese zwei Helfer werden angepasst, nicht jeder
der ~24 Aufrufer einzeln** — sie sind laut Analyse die Wurzel des Blast Radius, alle
Golden-/Aufrufer-Tests lesen Token-Werte über diese gemeinsame Funktion.

## Expected Behavior

- **Input:** `NormalizedForecast`/`DailyForecast` (Provider-Werte `temp_min_c`/`temp_max_c` bzw.
  `wind_chill_min_c`/`wind_chill_max_c`, `wind_direction_sector`, `precip_type_dominant`),
  `MetricConfig.aggregations` je Trip-Metrik (`temperature`, `wind_chill`).
- **Output:** Veränderte Token-Zeile (`TripReport.sms_text`) für SMS **und** Premium-SMS
  (gemeinsamer Renderer, ADR-0049/D8) — E-Mail-Tabellen und Telegram-Kurzübersicht sind NICHT
  betroffen (eigene Darstellung, nicht die Token-Zeile). Netto-Zeicheneffekt an einer echten
  Briefing-Zeile mit beiden Auswertungen gewählt gemessen: −3 Zeichen (Bereich, `K`/`FK` entfallen
  in genau diesem Fall) + 2 Zeichen (zwei neue Doppelpunkte aus (B)) = **−1 Zeichen** gesamt — real
  geltende Grenze bleibt **160 Zeichen** (`trip_report.py:446`, `dto.py`-Default), NICHT 153
  (unverdrahtete Konstante) und NICHT 140 (PDU-Byte-Limit, keine Zeichengrenze). Bei „nur
  min"/„nur max" gewählt ändert sich die Zeichenzahl NICHT (unveränderte Einzelform).
- **Side effects:** `/api/sms-symbols`-Antwort ändert sich NICHT sichtbar — (A) lässt
  `SMS_MULTI_SYMBOLS_BY_METRIC` unverändert (beide Kürzel je Metrik bleiben gelistet, s. AC-17),
  (B) ändert nur das interne Symbol (`WD:`/`PT:`), das `.rstrip(":")` vor der Ausgabe wieder auf
  `WD`/`PT` zurückführt (s. AC-18); 6 Golden-Fixtures müssen neu erzeugt werden;
  `docs/reference/sms_format.md` (§2/§3.2/§3.2a/§4/§6/§9/§12) und
  `fix_1660b_sms_token_wiring.md` (AC-6/AC-7, s. Known Limitations) müssen mitgezogen werden.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Metrik „Temperatur" und BEIDEN Auswertungen „Tiefstwert" und
  „Höchstwert" gewählt, Gehzeit-Tiefstwert 13°C, Gehzeit-Höchstwert 27°C / When das Briefing als
  SMS gerendert wird / Then enthält die SMS das Token `D13/27` und NICHT die Token `K13`/`D27`
  getrennt.
  - Test: SMS-Rendering mit realistischem Fixture, Assertion auf exakten Token-String im
    gerenderten `sms_text`, UND dass die Zeichenfolge `K13` in DIESEM Fixture (beide Auswertungen
    gewählt) nirgends vorkommt — gilt ausschließlich für den „beide gewählt"-Fall, s. AC-4 für den
    Gegenfall „nur min gewählt", wo `K13` weiterhin erscheint.

- **AC-2:** Given dieselbe Konfiguration wie AC-1, aber mit negativen Werten (Tiefst −12°C,
  Höchst −4°C, reales Wintersport-Golden-Fixture) / When die SMS gerendert wird / Then enthält
  die SMS das Token `D-12/-4` (Minuszeichen bleibt Vorzeichen, `/` bleibt der einzige Trenner,
  keine Verwechslung zwischen Trenner und Vorzeichen).

- **AC-3:** Given ein Trip mit Metrik „Temperatur" und NUR der Auswertung „Höchstwert" gewählt,
  Höchstwert 27°C / When die SMS gerendert wird / Then enthält die SMS das Token `D27`
  (unverändert — identisch zum heutigen Verhalten seit #1660 Scheibe A, kein `/`).

- **AC-4:** Given ein Trip mit Metrik „Temperatur" und NUR der Auswertung „Tiefstwert" gewählt,
  Tiefstwert 13°C / When die SMS gerendert wird / Then enthält die SMS das Token `K13`
  (unverändert — identisch zum heutigen Verhalten seit #1660 Scheibe A; PO-Entscheid 2026-08-13:
  KEIN Wechsel auf `D13`, weil `D` sonst überall den Höchstwert bedeutet).

- **AC-5:** Given ein Trip mit Metrik „Temperatur" und NUR der Auswertung „Mittelwert" gewählt
  (weder „Tiefstwert" noch „Höchstwert") / When die SMS gerendert wird / Then enthält die SMS
  WEDER `D...` NOCH `K...` — kein Temperatur-Token, unverändertes heutiges Verhalten.

- **AC-6:** Given beide Auswertungen gewählt, aber der Höchstwert im Gehzeit-Fenster nicht ermittelbar
  (kein Datenausfall, schlicht kein Wert über der Vergleichsbasis) während der Tiefstwert 13°C
  beträgt / When die SMS gerendert wird / Then enthält die SMS das Token `D13/-`.

- **AC-7:** Given beide Auswertungen gewählt und eine echte Datenlücke im ausgewerteten Fenster
  betrifft beide Hälften (kein Tiefst- UND kein Höchstwert ermittelbar, `has_data_gap=True`) /
  When die SMS gerendert wird / Then enthält die SMS das Token `D?/?` (nicht `D-/-`).

- **AC-8:** Given beide Auswertungen gewählt, kein Datenausfall, weder Tiefst- noch Höchstwert
  vorhanden / When die SMS gerendert wird / Then enthält die SMS das Token `D-/-`.

- **AC-9:** Given ein Trip mit Metrik „Gefühlte Temperatur" und BEIDEN Auswertungen gewählt,
  gefühlter Tiefstwert 10°C, gefühlter Höchstwert 20°C / When die SMS gerendert wird / Then
  enthält die SMS das Token `FD10/20` (Parität zu AC-1, gefühltes Pendant) und NICHT `FK10`/`FD20`
  getrennt.

- **AC-10:** Given ein Trip mit Metrik „Nacht-Tiefsttemperatur" (Abendbriefing) und Nachtwert 9°C
  / When die SMS gerendert wird / Then enthält die SMS unverändert das Einzelwert-Token `N9` — kein
  Merge, keine Range-Form, unabhängig von der Auswertungswahl der Metrik „Temperatur".

- **AC-11:** Given ein Trip mit aktivem Wintersport-Profil und `wind_chill_c`-Wert −22°C / When die
  SMS gerendert wird / Then enthält die SMS unverändert das eigenständige Token `WC-22`, ohne
  Trenner und ohne Zusammenführung mit `FD`.

- **AC-12:** Given ein Trip mit gewählter Metrik „Windrichtung" und dominantem Sektor Nordwest /
  When die SMS gerendert wird / Then enthält die SMS das Token `WD:NW` (mit Doppelpunkt), NICHT
  `WDNW`.

- **AC-13:** Given ein Trip mit gewählter Metrik „Windrichtung" ohne ermittelbaren Tageswert (kein
  Datenausfall) / When die SMS gerendert wird / Then enthält die SMS die Leerform `WD:-`, NICHT
  `WD-`.

- **AC-14:** Given ein Trip mit gewählter Metrik „Windrichtung" und einer echten Datenlücke im
  Fenster / When die SMS gerendert wird / Then enthält die SMS die Lückenform `WD:?`.

- **AC-15:** Given ein Trip mit gewählter Metrik „Niederschlagsart" und dominantem Typ SNOW / When
  die SMS gerendert wird / Then enthält die SMS das Token `PT:S` (mit Doppelpunkt), NICHT `PTS`;
  Leer- (`PT:-`) und Lückenform (`PT:?`) verhalten sich analog zu AC-13/AC-14.

- **AC-16:** Given eine Token-Zeile mit Range-Token `D13/27` (beide Auswertungen gewählt), die
  unter Kürzungsdruck (>160 Zeichen) so weit gekürzt werden muss, dass die gemessenen
  Temperatur-Token fallen müssen / When die Kürzung läuft / Then fällt `D13/27` als EINE atomare
  Einheit — es gibt keinen Zwischenzustand, in dem nur `D13` oder nur `D27` in der Zeile übrig
  bleibt (Ursache: der Range-Wert steckt in einem einzigen Token-Objekt, `K` wurde beim Merge nie
  separat an die Token-Liste angehängt).

- **AC-17:** Given ein Trip, dessen SMS-Kürzel-Katalog über `/api/sms-symbols` abgefragt wird, mit
  Metrik „Temperatur" / When der Endpoint antwortet / Then enthält die Symbol-Liste für
  `temperature` unverändert BEIDE Kürzel `["K", "D"]`, analog `wind_chill` unverändert
  `["FK", "FD", "WC"]` — Regressionsschutz (PO-Entscheid 2026-08-13): der Touren-Editor zeigt
  weiterhin sowohl die `K`- als auch die `D`-Badge, weil beide Kürzel real vorkommen können (je
  nach Auswertungswahl `K13`, `D27` oder gemeinsam als `D13/27`).

- **AC-18:** Given dieselbe Endpoint-Abfrage für die Metriken „Windrichtung"/„Niederschlagsart" /
  When der Endpoint antwortet / Then bleibt die angezeigte Badge unverändert `"WD"`/`"PT"` (ohne
  Doppelpunkt) — die interne Symbol-Änderung auf `WD:`/`PT:` ist für den Editor unsichtbar.

- **AC-19:** Given alle 6 betroffenen Golden-Fixtures (5× `tests/golden/sms/*.txt`, 1×
  `tests/golden/text_report/stubaier-skitour-evening.txt` — alle enthalten heute `K`+`D`-Paare) /
  When sie nach der Implementierung neu erzeugt werden / Then enthält keines der 6 Fixtures mehr
  die Zeichenfolgen `K\d` oder `FK\d` (Regex-Gegenprobe), und jedes enthält stattdessen die
  erwartete Range- bzw. Einzelform gemäß AC-1/AC-2.

## Known Limitations

- **Kürzungsgranularität sinkt um einen Schritt** (s. Implementation Details Punkt 3/AC-16): vor
  dieser Änderung konnte `K` einzeln vor `D` fallen (bzw. `FK` vor `FD`); danach ist der
  Range-Token atomar. Akzeptierte Nebenwirkung, kein offener Punkt.
- **Zwei der neun Null-/Lücken-Kombinationen des Range-Tokens sind mit dem heutigen
  tagesweiten `has_data_gap`-Flag nicht erzeugbar** (`D-/?`, `D?/-` — s. Implementation Details).
  Der Render-Kontrakt erlaubt sie dennoch strukturell; ein künftiges pro-Hälfte-Gap-Konzept liegt
  außerhalb dieser Spec.
- **`WC` bleibt vorerst bestehen und bekommt keinen Trenner** — Issue #1728 (ersatzloser Wegfall
  von `WC`, weil es denselben Wert wie `FK`/künftig `FD` doppelt trägt) ist ein separates, noch
  offenes Issue und NICHT Teil dieser Spec.
- **Erledigt, zur Historie:** eine erste Fassung dieser Spec sah für „nur Tiefstwert gewählt" `D13`
  statt `K13` vor (Anker-Wiederverwendung, Begründung: Konsistenz). Der PO hat das am 2026-08-13
  überstimmt — `K`/`FK` bleiben eigenständige Kürzel, ein Bereichs-Token entsteht ausschließlich
  bei doppelter Auswertungswahl (s. Implementation Details, Changelog). Diese Zeile dokumentiert
  die Historie, ist aber kein offener Punkt mehr.
- **`fix_1660b_sms_token_wiring.md` AC-6/AC-7 werden durch diese Spec abgelöst** — sie fordern
  wörtlich die Token `WDNW`/`PTS`, die es nach (B) nicht mehr gibt. Diese Spec ersetzt sie
  funktional durch AC-12/AC-15 oben; `fix_1660b` sollte bei Implementierung einen entsprechenden
  Abgelöst-Vermerk bekommen (Muster: „Löst DEC-2 aus … ab", bereits an anderer Stelle im Repo
  etabliert).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Beide Änderungen wenden ein bereits etabliertes Muster konsequent an, statt ein
  neues zu erfinden. (B) ist eine Kürzel-Grammatik-Änderung (Doppelpunkt wandert ins Symbol) nach
  demselben Muster wie `TH:`/`HR:`/`Z:`/`M:` — kein neues Grammatik-Konzept, vergleichbar mit der
  Kürzel-Migration in #1435 E3b (Schnee-Kürzel) und #1703 Scheibe 6 (`W?`→`X?`). (A) führt (nach
  dem PO-Entscheid 2026-08-13) gar keine Kürzel-Migration mehr durch — `K`/`D`/`FK`/`FD` bleiben
  bestehende Einzelwert-Kürzel, lediglich eine zusätzliche Kombinationsform (beide gleichzeitig →
  ein Token) kommt hinzu. Kein neues Architekturprinzip in beiden Fällen, daher kein ADR nötig —
  die Single Source of Truth bleibt `docs/reference/sms_format.md`.

## Changelog

- 2026-08-13: Initial spec created (Issue #1824)
- 2026-08-13: PO-Entscheid übernommen — „nur Tiefstwert gewählt" bleibt `K13` (nicht `D13`, wie in
  der Erstfassung vorgeschlagen). `K`/`FK` bleiben eigenständige Kürzel für Einzelwerte; ein
  Bereichs-Token entsteht ausschließlich bei gleichzeitig gewähltem Tiefst- UND Höchstwert.
  Begründung des PO: `D` bedeutet im Format sonst immer Höchstwert — ein `D13` mit tatsächlichem
  Tiefstwert wäre auf einem tourenentscheidungs-relevanten Kanal Falschinformation. Betrifft
  Implementation Details ((A), Konstanten-Liste, Vier-Zustände-Tabelle), Estimated Scope (LoC
  deutlich kleiner, weil `SMS_MULTI_SYMBOLS_BY_METRIC`/`PRIORITY`/`POSITIONAL`/
  `_AGG_GATE_SYMBOLS` jetzt unverändert bleiben), AC-3/AC-4/AC-16/AC-17, Known Limitations.
