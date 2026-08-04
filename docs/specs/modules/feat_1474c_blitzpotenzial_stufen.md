---
entity_id: feat_1474c_blitzpotenzial_stufen
type: feature
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [gewitter, dwd, lpi, s3, issue-1474, issue-1419]
---

# DWD-Blitzpotenzial wird viertes Signal in der Gewitterstufen-Fusion (Issue #1474, letzter Restpunkt zu #1419)

## Approval

- [ ] Approved

## Purpose

`lightning_potential_lpi_jkg` (DWD-Blitzpotenzial, J/kg, seit #1457 S2b/S2c aus ICON-D2 bzw.
ICON-EU befüllt) fließt bisher NICHT in die Gewitterstärke ein — S2b hat das bewusst
ausgespart (AC-8: „keine Stufenbildung in dieser Scheibe"). Diese Scheibe hebt genau diese
Aussparung auf: Das Blitzpotenzial wird das **vierte Signal** in
`thunder_level_from_signals()`, mit einer **eigenen** Schwellentabelle, weil es eine andere
Größe auf einer anderen Skala ist als die Blitzdichte (#1419 Abs. 3.1, ADR-0025). Letzter
offene Restpunkt zu Epic #1419.

## Source

- **File:** `src/output/metric_format.py`, `src/providers/thunder_enrichment.py`
- **Identifier:** `thunder_level_from_signals()` (bekommt vierten Parameter), neue geteilte
  Leiter-Funktion (Name durch Implementierung, Vorschlag `_thunder_level_from_ladder()`),
  `_fuse_thunder_levels()`, `enrich_thunder()`-Docstring (Zeilen um 125-128)

**Schicht:** ausschließlich Python-Core (`src/output/`, `src/providers/`). Kein Go, kein
Frontend — die drei Wortkopien im Frontend sind #1488, nicht Teil dieser Scheibe.

## Estimated Scope

- **LoC:** ~40-70 Quellcode (geteilte Leiter-Funktion, zwei neue Schwellenkonstanten, vierter
  Parameter samt Aufrufstelle, zwei Docstring-Aktualisierungen) + ~150-220 Tests ≈ **190-290
  gesamt** — nah am 250-LoC-Workflow-Limit. Reißt es beim Implementieren, entscheidet der PO
  über `workflow.py set-field loc_limit_override 500`; keine Selbst-Anhebung.
- **Files:** 2 geändert (0 neu im Produktivcode), 1 Testdatei erweitert, 2 Testdateien neu, 1
  Bestands-Testdatei bewusst unverändert als Regressionsanker (s. AC-7).
- **Effort:** low-medium — der Andockpunkt existiert bereits vollständig (Docstring von
  `thunder_level_from_signals()` verspricht ausdrücklich „damit ein künftiges Signal mit
  derselben Struktur andockt"); die eigentliche Schwierigkeit liegt nicht im Codeumfang,
  sondern im europaweiten Blast Radius (s. Known Limitations) und der Beweispflicht am
  Produktionspfad (AC-4).

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` | Vorgänger-Scheibe | führt `ThunderLevel.LOW`, `thunder_level_from_signals()`, `max_thunder()` und die Regel „None ≠ NONE" ein — diese Scheibe erweitert additiv, baut nichts neu |
| `docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md` | Vorgänger-Scheibe | vereinheitlicht die Erwähnungsschwelle über `thunder_ordinal()` — bleibt unberührt, profitiert aber automatisch von einem vierten Signal, sobald es die Stufe anhebt |
| `docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md` | Vorgänger-Scheibe | AC-8 dort („keine Stufenbildung") **fällt** mit dieser Scheibe für `lightning_potential_lpi_jkg`; für `hail_potential_grau_gsp` bleibt sie unverändert gültig |
| `docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md` | Vorgänger-Scheibe | Known Limitation 4/6 dort hält fest, dass ICON-EU dasselbe Feld mit anderer Bildungsvorschrift (60-Min-Maximum statt Momentanwert) befüllt — Grund für Known Limitation 2 unten. AC-10 dort („keine Stufenbildung, keine Ausgaben-Änderung durch ICON-EU") **fällt ebenfalls** mit dieser Scheibe — ICON-EU befüllt dasselbe Feld `lightning_potential_lpi_jkg` wie ICON-D2, also wirkt die Aufhebung von AC-8 (S2b) zwangsläufig auch auf ICON-EU-Gebiete. Dieser Zusammenhang war beim Erstellen dieser Spec übersehen worden (Regression, s. Changelog 2026-08-04) und ist jetzt hier festgehalten. |
| `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md` | bindende Vorgabe | Entscheidung 5 „Beweispflicht liegt beim Produktionspfad" — AC-4 setzt das für diese Scheibe um |
| `tests/tdd/test_thunder_level_from_signals_fusion.py` | Regressions-Anker | 8 Bestandstests (Blitzdichte/CAPE/„keine Aussage"/„schärfstes Signal") — müssen nach dieser Scheibe **unverändert grün** bleiben (AC-7) |
| `tests/tdd/test_thunder_enrichment_fuses_level_shared_path.py` | Erweiterungsstelle | trägt bereits das Muster „Produktionspfad, kein Mock" für die Fusion — AC-4 folgt demselben Muster mit einer DWD- statt Météo-France-Fixture |
| `tests/fixtures/dwd/icon_d2_alpen_lpi_2026080315_024.grib2.bz2` | Fixture | echte ICON-D2-Aufzeichnung, Zelle 46,40 N/12,52 O trägt `lpi = 48,1562` (aus S2b-Recherche) — Grundlage für AC-4 |

## Implementation Details

**1. Geteilte Leiter-Funktion (DRY-Pflicht, #1481) — ersetzt NICHT die bestehende
Blitzdichte-Leiter, sondern hebt ihre Logik in eine gemeinsame Funktion:**

```python
def _thunder_level_from_ladder(
    value: float, low_min: float, med_min: float, high_min: float,
) -> ThunderLevel:
    """Uebersetzt EINEN Messwert anhand einer Drei-Schwellen-Leiter in ein
    ThunderLevel (>=high_min -> HIGH, >=med_min -> MED, >=low_min -> LOW,
    sonst NONE). Geteilt von Blitzdichte UND Blitzpotenzial (Issue #1474c,
    DRY-Pflicht #1481) -- jedes Signal bringt nur seine eigenen vier
    Schwellenwerte mit, die Leiter selbst existiert genau einmal, damit ein
    kuenftiges fuenftes Signal mit derselben Struktur andockt, ohne eine
    weitere Kopie der if/elif-Kette zu erzeugen."""
    if value >= high_min:
        return ThunderLevel.HIGH
    if value >= med_min:
        return ThunderLevel.MED
    if value >= low_min:
        return ThunderLevel.LOW
    return ThunderLevel.NONE
```

Die bestehende Blitzdichte-Übersetzung (`metric_format.py:338-346`) wird auf diese Funktion
umgestellt (`_thunder_level_from_ladder(lightning_density, _LIGHTNING_LOW_MIN,
_LIGHTNING_MED_MIN, _LIGHTNING_HIGH_MIN)`) — bit-identisches Verhalten, weil die
Vergleichsreihenfolge (`>=` an jeder Schwelle, absteigend geprüft) exakt übernommen wird
(s. AC-7, Regressionsanker).

**2. Neue Schwellenkonstanten, PO-freigegeben 2026-08-04, unverändert übernommen:**

```python
# Blitzpotenzial-Schwellen (DWD ICON-D2/ICON-EU LPI, J/kg). Aeussere Grenzen
# BELEGT: 5 J/kg = betrieblicher DWD-Schwellenwert (Blitz-ja/nein), 50 J/kg
# = oberes Ende der publizierten Verifikationsspanne (dort ~90% Blitz-
# wahrscheinlichkeit). Quellen: https://asr.copernicus.org/articles/19/29/2022/
# und https://www.dwd.de/EN/ourservices/reports_on_icon/pdf_einzelbaende/2022_10.pdf
# 20 J/kg ("leicht"->"mittel") ist NICHT publiziert, sondern innerhalb der
# belegten Spanne interpoliert -- s. Spec Known Limitations.
_LIGHTNING_POTENTIAL_LOW_MIN = 5.0
_LIGHTNING_POTENTIAL_MED_MIN = 20.0
_LIGHTNING_POTENTIAL_HIGH_MIN = 50.0
```

| Blitzpotenzial (J/kg) | Stufe |
|---|---|
| unter 5 | `ThunderLevel.NONE` |
| 5 bis unter 20 | `ThunderLevel.LOW` |
| 20 bis unter 50 | `ThunderLevel.MED` |
| ab 50 | `ThunderLevel.HIGH` |

**3. Vierter Parameter an `thunder_level_from_signals()`, additiv mit Default (bricht keinen
Bestandsaufruf):**

```python
def thunder_level_from_signals(
    wettercode_level: Optional[ThunderLevel],
    lightning_density: Optional[float],
    cape_jkg: Optional[float],
    lightning_potential_jkg: Optional[float] = None,
) -> Optional[ThunderLevel]:
    ...
    if lightning_potential_jkg is not None:
        signals.append(_thunder_level_from_ladder(
            lightning_potential_jkg, _LIGHTNING_POTENTIAL_LOW_MIN,
            _LIGHTNING_POTENTIAL_MED_MIN, _LIGHTNING_POTENTIAL_HIGH_MIN,
        ))
```

Fusion (`max_thunder()` über die Nicht-`None`-Signale) bleibt unverändert — das vierte
Signal reiht sich in die bestehende Liste ein, kein Sonderfall.

**4. `_fuse_thunder_levels()` reicht das Feld durch (`thunder_enrichment.py:96-98`):**

```python
fused = thunder_level_from_signals(
    dp.thunder_level, dp.lightning_density_per_km2_3h, dp.cape_jkg,
    dp.lightning_potential_lpi_jkg,
)
```

`hail_potential_grau_gsp` wird **nicht** übergeben — Hagel bleibt draußen (S5/#1475, s.
Known Limitations, AC-6).

**5. Docstring-Korrektur in `enrich_thunder()` (Zeilen um 125-128):** Der Satz „Diese
Rohwerte gehen BEWUSST nicht in die Stufen-Fusion unten ein (S2b AC-8: keine Stufenbildung
in dieser Scheibe)" gilt nach dieser Scheibe nur noch für Hagel, nicht mehr für
Blitzpotenzial. Wird umformuliert, z. B.: „Das Blitzpotenzial (`lightning_potential_lpi_jkg`)
geht seit #1474c zusätzlich in die Stufen-Fusion unten ein (S2b AC-8 ist damit für dieses
Feld aufgehoben). Das Hagelsignal (`hail_potential_grau_gsp`) bleibt weiterhin außen vor —
das ist S5/#1475." (AC-5, doc-compliance-test).

**Achtung — Nachtrag 2026-08-04 (Regressions-Fix):** Der `enrich_thunder()`-Dispatch wird von
`tests/tdd/test_thunder_named_signals_enrichment.py::test_ac9_der_kern_dispatch_kennt_keine_quelle_und_kein_einzelnes_signal`
per `inspect.getsource()` bewacht (S2a AC-8, S2c AC-9: der Kern-Dispatch darf weder eine Quelle
noch ein einzelnes Signal beim Namen kennen) — dieser Wächter liest den kompletten Quelltext
der Funktion **inklusive Docstring** und verbietet dort die Teilzeichenketten `"lpi"` und
`"grau_gsp"`. Die technischen Feldnamen `lightning_potential_lpi_jkg` und
`hail_potential_grau_gsp` enthalten beide Teilzeichenketten — der Docstring-Text darf sie
deshalb **nicht** wörtlich zitieren. Die Aussage von AC-5 bleibt dieselbe, nur ohne die
technischen Feldnamen: „Das Blitzpotenzial geht seit #1474c zusätzlich in die Stufen-Fusion
ein, das Hagelsignal bleibt weiterhin außen vor."

## Expected Behavior

- **Input:** ein Datenpunkt mit gesetztem `lightning_potential_lpi_jkg` (aus DWD ICON-D2 oder
  ICON-EU, via `enrich_thunder()`)
- **Output:** `dp.thunder_level` spiegelt das schärfste Signal aus Wettercode, Blitzdichte,
  CAPE UND Blitzpotenzial — wo bisher nur die ersten drei zählten
- **Side effects:** keine neuen Abrufe, keine neuen Felder — reine Verwertung eines bereits
  produktiv befüllten Werts. Wirkungsbereich europaweit (s. Known Limitations 3), da
  `eu_direct` seit S2c die Catch-all-Zuständigkeit für Gewittersignale trägt.

## Acceptance Criteria

- **AC-1 (Blitzpotenzial-Dreiteilung nach PO-Tabelle, mit Plausibilitätsankern):** Given die
  Blitzpotenzial-Werte 4,9 / 5,0 / 19,9 / 20,0 / 49,9 / 50,0 sowie die beiden PO-Messwerte vom
  2026-08-02 (GR20/Refuge de Petra Piana 88,2 J/kg; Zillertal, ruhiges Wetter, 0,9 J/kg) / When
  `thunder_level_from_signals()` mit jeweils NUR diesem Signal (Wettercode, Blitzdichte, CAPE
  alle `None`) aufgerufen wird / Then liefert sie der Reihe nach `NONE` / `LOW` / `LOW` /
  `MED` / `MED` / `HIGH`, und die beiden Messwerte liefern `HIGH` (88,2) bzw. `NONE` (0,9) —
  konsistent mit der realen Gewitterlage bzw. Ruhe an diesem Tag.
  - Test: acht Aufrufe mit den genannten Werten, Rückgaben gegen die PO-Tabelle (5/20/50)
    geprüft.
  - Gegenprobe: Liest die Implementierung fälschlich die Blitzdichte-Schwellen (0,003/0,015/
    0,075) statt der eigenen Blitzpotenzial-Schwellen, liefert bereits 4,9 fälschlich `HIGH`
    (weit über 0,075) — der Test muss das fangen.

- **AC-2 (DRY — eine geteilte Leiter-Funktion, keine Kopie, #1481):** Given die
  Schwellen-Übersetzung für Blitzdichte UND Blitzpotenzial / When beide Zweige in
  `thunder_level_from_signals()` ausgeführt werden / Then rufen beide dieselbe benannte
  Leiter-Funktion `(wert, low_min, med_min, high_min) -> ThunderLevel` auf — es gibt in der
  Datei genau eine Stelle, die die Vier-Wege-Fallunterscheidung `>= high / >= med / >= low /
  sonst` implementiert, nicht zwei unabhängige Kopien.
  - Test: ein struktureller Test liest den Quelltext von `thunder_level_from_signals()` per
    AST (nicht per Textsuche) und zählt die Aufrufe der geteilten Funktion — erwartet genau
    zwei Aufrufstellen (Blitzdichte, Blitzpotenzial). Ergänzt um einen Verhaltens-Beleg: beide
    Signale liefern an ihrer jeweils UNTEREN Schwelle (Wert exakt gleich `low_min`)
    übereinstimmend `LOW` — Beweis, dass beide über denselben Vergleichsoperator (`>=`)
    laufen.
  - Gegenprobe: Fügt die Implementierung eine zweite, kopierte if/elif-Leiter für das
    Blitzpotenzial direkt in `thunder_level_from_signals()` ein statt die geteilte Funktion zu
    nutzen, sinkt die per AST gezählte Aufrufzahl der geteilten Funktion auf 1 (nur
    Blitzdichte) — der Test muss das fangen.

- **AC-3 (None ≠ NONE für das vierte Signal):** Given `lightning_potential_jkg=None` (kein
  Signal) UND alle anderen Signale `None` / When `thunder_level_from_signals()` aufgerufen
  wird / Then liefert sie `None` (keine Aussage). Given STATTDESSEN
  `lightning_potential_jkg=0.0` (aktiv geprüft, unter 5) bei sonst `None` / Then liefert sie
  `ThunderLevel.NONE` (geprüft, unauffällig) — die beiden Fälle unterscheiden sich.
  - Test: zwei Aufrufe `(None, None, None, None)` → `None`; `(None, None, None, 0.0)` →
    `ThunderLevel.NONE`.
  - Gegenprobe: Behandelt die Implementierung `None` und `0.0` beim vierten Signal gleich
    (z. B. weil intern ein Default `0.0` statt `None` verwendet wird), liefern beide Aufrufe
    `ThunderLevel.NONE` — der Test muss das fangen.

- **AC-4 (Wirkungs-Nachweis über den Produktionspfad — die Aussparung aus S2b AC-8 fällt):**
  Given eine Position im ICON-D2-Zuständigkeitsgebiet (Karnischer Höhenweg, 46,40 N / 12,52 O)
  mit einem aufgezeichneten ICON-D2-Blitzpotenzial-Wert 48,1562 J/kg
  (`icon_d2_alpen_lpi_2026080315_024.grib2.bz2`, unveränderte S2b-Fixture) UND einer
  Grundvorhersage ohne Gewittercode/CAPE-Auslöser / When eine Vorhersage über den **regulären**
  Weg (`OpenMeteoProvider.fetch_forecast` → `thunder_enrichment.enrich_thunder()`) abgerufen
  wird / Then trägt mindestens ein Datenpunkt `ThunderLevel.MED`, wo derselbe Weg vor dieser
  Scheibe `ThunderLevel.NONE` lieferte.
  - Test: lokaler HTTP-Server für Open-Meteo (Wettercode 1, CAPE 0, Muster
    `test_thunder_enrichment_fuses_level_shared_path.py`) UND ein lokaler HTTP-Server für DWD
    ICON-D2 (`providers.dwd.BASE_URL`, Muster `test_dwd_thunder_signal_fetch.py`), der die
    genannte Fixture ausliefert; der komplette Weg wird durchgespielt, `dp.thunder_level` für
    46,40/12,52 geprüft.
  - Gegenprobe (Verfälschung am Produktivcode, MUSS diesen Test rot machen): Wird in
    `_fuse_thunder_levels()` das vierte Argument `dp.lightning_potential_lpi_jkg` wieder
    entfernt — also die Aussparung aus S2b AC-8 wiederhergestellt —, liefert der Datenpunkt
    erneut `NONE`. Der Test MUSS rot werden. Wird zusätzlich der vierte Parameter aus
    `thunder_level_from_signals()` entfernt, ebenfalls rot.
  - **Warum der Nachweis zwingend über `enrich_thunder()` laufen muss:** Ein Test, der
    `thunder_level_from_signals()` isoliert mit 48,1562 füttert, bliebe bei genau dieser
    Verfälschung GRÜN — die Aussparung sitzt im Aufrufer, nicht in der Fusion. ADR-0025
    Entscheidung 5; in #1457 erzeugte die isolierte Variante dreimal ein grünes AC ohne
    Wirkung.

- **AC-5 (doc-compliance-test — Docstring folgt dem neuen Verhalten):** Given der Docstring
  von `thunder_enrichment.enrich_thunder()` behauptete bisher, Blitzpotenzial UND Hagel gingen
  „BEWUSST nicht in die Stufen-Fusion" ein (S2b AC-8) / When der Docstring nach dieser Scheibe
  gelesen wird / Then behauptet er das für Blitzpotenzial **nicht mehr** — er hält stattdessen
  fest, dass Blitzpotenzial seit #1474c einfließt und ausschließlich Hagel weiterhin
  ausgespart bleibt. Die Formulierung nennt dabei **keine** technischen Feldnamen, die die
  Teilzeichenketten `lpi` oder `grau_gsp` enthalten (s. Nachtrag in Implementation Details 5) —
  „Blitzpotenzial"/„Hagelsignal" tragen dieselbe Aussage ohne den gesperrten Wortlaut.
  - Test: `# doc-compliance-test` — liest `enrich_thunder.__doc__`, prüft, dass „Blitzpotenzial"
    nicht mehr im selben Satz wie „nicht ... Stufen-Fusion" auftaucht, und dass „Hagel" bzw.
    `hail_potential_grau_gsp` weiterhin ausdrücklich als ausgespart benannt wird.
  - Gegenprobe: Bleibt der alte Satz unverändert stehen, während das Verhalten (AC-4) bereits
    geändert ist, steht eine falsche Zusicherung im Code — der Test muss das fangen.

- **AC-6 (Abgrenzung — Hagel bleibt draußen, S5/#1475):** Given `hail_potential_grau_gsp` ist
  für einen Datenpunkt gefüllt, `lightning_potential_lpi_jkg` ist `None` / When die Fusion über
  den regulären Weg läuft / Then bleibt `dp.thunder_level` identisch zum selben Fall OHNE
  gesetztes Hagelfeld — Hagel liefert weiterhin keinen eigenen Beitrag zur Stufe.
  - Test: zwei Fixtures (mit/ohne `hail_potential_grau_gsp` gesetzt, alle anderen Felder
    identisch inkl. `lightning_potential_lpi_jkg=None`) werden durch `_fuse_thunder_levels`
    geschleust, `dp.thunder_level` beider Fälle verglichen.
  - Gegenprobe: Fließt `hail_potential_grau_gsp` versehentlich als fünftes Signal in die Fusion
    ein, unterscheiden sich die beiden Ergebnisse — der Test muss das fangen.

- **AC-7 (Regressions-Anker — Bestandsverhalten für Blitzdichte und CAPE bleibt exakt
  gleich):** Given die 8 Bestandstests aus `tests/tdd/test_thunder_level_from_signals_fusion.py`
  (Blitzdichte-Dreiteilung, CAPE-Deckelung, „keine Aussage" ≠ „keine Gefahr", „schärfstes
  Signal gewinnt") / When sie nach dieser Scheibe **unverändert** ausgeführt werden / Then
  bleibt **jeder einzelne Testfall grün mit demselben Ergebnis** wie vor dieser Scheibe —
  trotz des vierten Parameters und der Extraktion der geteilten Leiter-Funktion.
  - Test: `uv run pytest tests/tdd/test_thunder_level_from_signals_fusion.py` läuft ohne
    Code-Änderung an dieser Datei vollständig grün.
  - Gegenprobe: Verschiebt die Extraktion der geteilten Leiter-Funktion versehentlich die
    Vergleichsreihenfolge (z. B. `>` statt `>=` an einer Schwelle), wird die Mutation
    gefangen — **nachgemessen jedoch nicht zwingend durch diese Datei selbst**: Die
    Bestandswerte hier (0,0 / 0,004 / 0,02 / 0,15) liegen an keiner der Blitzdichte-Schwellen
    (0,003 / 0,015 / 0,075) exakt an der Grenze, ein `>`/`>=`-Wechsel bleibt für diese Datei
    isoliert unsichtbar. Gefangen wird die Mutation durch den Grenzwert-Test in
    `tests/tdd/test_thunder_ladder_shared_across_signals.py`
    (`test_ac2_beide_signale_liefern_an_der_unteren_schwelle_uebereinstimmend_low`), der
    beide Signale exakt AN `low_min` prüft. AC-7 selbst („bleibt unverändert grün") bleibt
    davon unberührt — nur die Behauptung, *welcher* Test die Mutation fängt, war falsch
    (Adversary-Befund F002).

## Known Limitations

- **20 J/kg ist interpoliert, nicht publiziert.** Belegt sind nur die äußeren Grenzen (5 J/kg
  betrieblicher DWD-Wert, 50 J/kg oberes Ende der publizierten Verifikationsspanne). Die
  Trennung „leicht"/"mittel" bei 20 J/kg liegt innerhalb der belegten Spanne, ist aber keine
  eigene publizierte Grenze — analog zu `_LIGHTNING_HIGH_MIN = 0.075` bei der Blitzdichte
  (dieselbe Art Limitation, dieselbe Transparenz-Pflicht).
- **Ein Feld, zwei Modelle mit unterschiedlicher Bildungsvorschrift.** ICON-D2 liefert `lpi`
  als Momentanwert (2,2 km Maschenweite), ICON-EU liefert `lpi_con_max` als 60-Minuten-Maximum
  (~6,5 km, `src/providers/dwd_eu.py:42-45`) — beide landen im selben Feld
  `lightning_potential_lpi_jkg` (S2c-Entscheidung). Ein Stundenmaximum liegt systematisch über
  einem Momentanwert; dieselbe Schwelle lässt ICON-EU-Gebiete tendenziell eher eskalieren als
  ICON-D2-Gebiete bei vergleichbarer tatsächlicher Gewitterlage. Gemessene Wertebereiche liegen
  dennoch nah beieinander (ICON-D2 bis ~225, ICON-EU 0…269) — die Verzerrung ist real, aber
  nicht grob. Nicht Gegenstand dieser Scheibe, hier nur benannt statt verschwiegen.
- **Wirkungsbereich ist europaweit — das eigentliche Risiko dieser Scheibe.** Seit #1457 S2c
  ist `eu_direct` die Catch-all-Zeile der Gewitter-Zuständigkeitstabelle; das Blitzpotenzial
  liegt damit für nahezu jeden europäischen Ort an. Über `max_thunder()` kann das die
  Gewitterstufe flächendeckend anheben und dadurch Alarme auslösen, die vor dieser Scheibe
  nicht ausgelöst hätten (via `ORDINAL_LEVEL_BOUNDS`, `fix_1474b`-Erwähnungsschwelle). Kein
  Fehler dieser Scheibe, aber der Grund, warum ihr Blast Radius größer ist als ihr Codeumfang
  vermuten lässt. **Konkret bestätigt:** Dieselbe Aufhebung gilt für ICON-EU-Gebiete (s. AC-4,
  Dependencies-Zeile zu S2c), was in der ursprünglichen Fassung dieser Spec übersehen wurde und
  dort einen bestehenden Test (S2c AC-10) unerwartet rot machte — die Zusicherung „keine
  Stufenbildung, keine Ausgaben-Änderung durch ICON-EU" ist mit dieser Scheibe ebenfalls
  aufgehoben, s. Nachtrag in Implementation Details 5.
- **Kein Hagel in der Fusion.** `hail_potential_grau_gsp` bleibt außen vor — das ist S5/#1475
  (AC-6 sichert das ab).
- **Kein Onset („Gewitter ab 14:00").** Das ist S7/#1493, nicht Teil dieser Scheibe.
- **Kein Nachfüllen in der Ausfallkette.** Fällt eine Gewitterquelle aus, bleibt das Signal
  `None` — kein Rückgriff auf eine andere Quelle. Das ist S4/#1492, zurückgestellt.
- **Keine neue Datenbeschaffung.** Diese Scheibe verwertet ausschließlich bereits produktiv
  befüllte Werte — kein zusätzlicher Open-Meteo- oder DWD-Abruf, kein Kontingent-Verbrauch
  (#1329).
- **Kein Katalogeintrag.** `metric_catalog.py` kennt weder `lightning_density` noch
  `lightning_potential` — beide sind keine wählbaren Metriken. Modulkonstanten mit
  Quellenbeleg (wie bei der Blitzdichte) bleiben das etablierte Muster; kein Katalog-Eintrag
  entsteht hier.
- **Keine Frontend-Änderung.** Die drei Wortkopien im Frontend sind #1488, außerhalb dieser
  Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Referenz auf **ADR-0025**.
- **Rationale:** Diese Scheibe bewegt sich vollständig innerhalb bestehender, bindender
  Entscheidungen. `thunder_level_from_signals()` wurde mit `feat_1474_gewitter_befund_stufen`
  ausdrücklich als Andockpunkt für „ein künftiges Signal mit derselben Struktur" entworfen —
  das vierte Signal ist eine additive Erweiterung dieses bereits etablierten Musters, keine
  neue Architektur-Entscheidungsfläche. ADR-0025 Entscheidung 5 („Beweispflicht liegt beim
  Produktionspfad") verlangt bereits genau das, was AC-4 hier umsetzt — es entsteht keine
  neue Regel, nur eine weitere Anwendung einer bestehenden. Die getrennte Skala pro Signal
  (#1419 Abs. 3.1) ist ebenfalls keine neue Entscheidung, sondern dieselbe, die bereits für
  Blitzdichte vs. CAPE galt und hier ein drittes Mal angewendet wird.

## Changelog

- 2026-08-04: Initial spec created (Issue #1474, letzter Restpunkt zu Epic #1419).
- 2026-08-04: Regressions-Nachtrag — S2c AC-10 (ICON-EU) fällt ebenfalls mit dieser Scheibe,
  war in der Erstfassung übersehen; Docstring-Formulierung darf keine `lpi`/`grau_gsp`-
  Teilzeichenketten enthalten (S2a AC-8/S2c AC-9-Wächter in `enrich_thunder()`).
