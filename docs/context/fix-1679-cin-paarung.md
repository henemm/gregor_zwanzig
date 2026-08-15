# Context: CIN-Paarung fuer CAPE (Issue #1679, Rest-Scope)

## Request Summary

Issue #1679 hat zwei Teile: die LPI-Schwellenleiter (1/30/50 J/kg, DE_ALPEN) ist bereits live
(`8cd43763`, adversary-VERIFIED). Offen bleibt die **CIN-Paarung**: CAPE ist heute pauschal bei
`ThunderLevel.LOW` gedeckelt und eskaliert nie, weil die Gegengroesse (Konvektionshemmung CIN)
bisher fehlte. Seit #1531 (heute gemergt) steht `cin_ml` als `dp.convective_inhibition_jkg` zur
Verfuegung. Diese Scheibe ersetzt die pauschale Deckelung durch eine CIN-abhaengige CAPE-Leiter.

## Related Files

| File | Relevance |
|---|---|
| `src/output/metric_format.py::thunder_level_from_signals()` | Fusionsfunktion, CAPE-Zweig (Zeile ~362-363) heute binaer (`>= threshold -> LOW sonst NONE`) |
| `src/output/metric_format.py::_thunder_level_from_ladder()` | geteilte 3-Schwellen-Uebersetzung, WIRD WIEDERVERWENDET fuer die neue CAPE-Leiter |
| `src/app/model_registry.py` | `cape_threshold_jkg()`, `cape_delta_threshold_jkg()`, `CAPE_REFERENZ_NIVEAU_JKG=1000.0` (Issue #1592) — Skalierungs-Infrastruktur, die fuer die CAPE-Leiter WIEDERVERWENDET werden kann |
| `src/app/thunder_scale.py::thunder_ordinal()` | kanonische Ordnung NONE=0/LOW=1/MED=2/HIGH=3 — noetig fuer "eine Stufe weniger" und "hoechstens leicht" |
| `src/providers/thunder_enrichment.py::_fuse_thunder_levels()`/`enrich_thunder()` | Aufrufstelle, muss `dp.convective_inhibition_jkg` zusaetzlich durchreichen |
| `src/app/models.py:113,173` | `cape_jkg` (Bestandsfeld) und `convective_inhibition_jkg` (#1531, J/kg, i.d.R. <= 0) |
| `docs/features/gewitter-gesamtkonzept.md` Abschnitt 3.5/3.7 | **die vollstaendige, bereits PO-finalisierte Rechenvorschrift** (s.u.) |
| `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` | Vorbild-Spec (LPI-Teil desselben Issues, identisches Muster: Region-Tabelle, keyword-only ohne Default) |
| `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` (AC-6) | **wird durch diese Scheibe fachlich ueberschrieben**: "CAPE gedeckelt bei LOW, eskaliert nie" gilt danach nur noch fuer die Faelle grosser/unbekannter Hemmung, nicht mehr generell |
| `docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md` | Referenz-ADR, keine neue ADR noetig (gleiches Prinzip, zweite Anwendung nach LPI) |

## Die bereits fertige Zielvorschrift (Gesamtkonzept Abschnitt 3.5 + 3.7 Schritt 1/2)

**CAPE-Leiter (NWS/SPC, mehrfach unabhaengig belegt):** schwach < 1000 · maessig 1000-2500 ·
stark 2500-4000 · extrem > 4000 J/kg — heute nur die unterste Schwelle genutzt (binaer).

**CIN-Baender (Penn State/COMET + SPC, belegte Eckpunkte -25/-50/-100/-200):**

| Hemmung (CIN, J/kg) | CAPE darf hoechstens |
|---|---|
| 0 bis -25 (schwacher Deckel) | **voll wirken** — volle Leiter 1000/2500/4000 |
| -25 bis -50 (moderat) | **eine Stufe weniger** als die volle Leiter ergeben wuerde |
| -50 bis -100 (grosser Deckel) | **hoechstens "leicht"** (= heutiges Verhalten) |
| unter -100 (Deckel haelt) | **kein Beitrag** (NONE) |
| Hemmung unbekannt (`None`) | **hoechstens "leicht"** — heutige Notbremse bleibt sicherer Rueckfall |

Ausdruecklich (Gesamtkonzept): CIN ist ein **Ausloese-Filter**, kein Schweremass (Rasmussen &
Blanchard 1998) — sie darf **daempfen, nie anheben**.

Abschnitt 10.2 bestaetigt explizit: "Keine offenen Grundsatzfragen mehr. Was bleibt, ist Arbeit,
nicht Entscheidung." Diese Scheibe ist damit vollstaendig spezifiziert, keine offene
Produktentscheidung noetig.

## Existing Patterns (wiederzuverwendende Infrastruktur)

1. **Skalierung ohne neue Kalibrierung:** `model_registry.cape_delta_threshold_jkg(nominal,
   model_id, region)` skaliert bereits einen nominalen Wert (z.B. 1200/600/200 fuer
   Delta-Alarme) proportional zur geeichten Modell-/Gebiets-Schwelle
   (`nominal * cape_threshold_jkg(...) / 1000.0`). **Dieselbe Funktion liefert die MED/HIGH-Stufe
   der neuen CAPE-Leiter** (`cape_delta_threshold_jkg(2500.0, ...)`,
   `cape_delta_threshold_jkg(4000.0, ...)`) — keine neue Kalibrierung, keine erfundene Zahl:
   `cape_threshold_jkg(model_id, region)` selbst bleibt die LOW-Schwelle (identisch zu
   `cape_delta_threshold_jkg(1000.0, ...)`, da `CAPE_REFERENZ_NIVEAU_JKG == 1000.0`).
2. **`_thunder_level_from_ladder()`** bleibt unveraendert (DRY-Pflicht #1481) — die CAPE-Leiter
   nutzt sie wie LPI/Blitzdichte.
3. **`thunder_ordinal()`** liefert die kanonische Ordnung fuer "eine Stufe runter" (Ordinal - 1,
   Boden bei NONE) und "hoechstens leicht" (min(Ordinal, LOW-Ordinal)).
4. **Keyword-only ohne Default** ist das durchgaengige Muster seit #1592 C1 (`cape_threshold_jkg`)
   und #1679-LPI (`lpi_low_min` etc.) fuer jeden neuen Schwellen-Parameter an
   `thunder_level_from_signals()` — kein stiller Rueckfall auf der GANZEN Kette
   (`_fuse_thunder_levels()` UND `thunder_level_from_signals()`).

## Dependencies

- **Upstream:** `cin_ml` (`dp.convective_inhibition_jkg`, #1531, heute gemergt) — Blocker ist
  gefallen. `cape_threshold_jkg()`/`cape_delta_threshold_jkg()`/`effective_cape_model_id()`
  (#1592, `model_registry.py`) — unveraendert wiederverwendet.
- **Downstream:** `risk_engine.py::_check_thunder()` liest nur `agg.thunder_level_max` — keine
  Aenderung noetig, profitiert automatisch von praeziserer Fusion. SMS-/Mail-Renderer lesen
  `thunder_level`/`thunder_ordinal()` — ebenfalls unveraendert.
- **FR-Gebiet bleibt de facto unveraendert:** Météo-France/AROME liefert kein CIN
  (Gesamtkonzept 3.7 Tabelle: "CAPE ja, Hemmung nein ⇒ bleibt gedeckelt") — `cin_ml` ist dort
  strukturell `None`, faellt also automatisch in die "unbekannt"-Zeile (hoechstens "leicht"),
  identisch zum heutigen Verhalten. Kein Sonderfall-Code noetig.

## Existing Specs

- `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` — Bauplan/Formatvorbild
- `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md` — Ursprung von
  `cape_threshold_jkg()`/keyword-only-Muster
- `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` — traegt das zu revidierende AC-6

## Risks & Considerations

- **AC-6-Revision ist eine dokumentierte Abweichung, keine stille Aenderung** — muss in der neuen
  Spec explizit als "ersetzt AC-6 fuer den Fall bekannter, schwacher Hemmung" benannt werden
  (CLAUDE.md: dokumentierte Entscheidung nie still rueckgaengig machen). Referenz auf ADR-0048
  reicht (gleiches Architekturprinzip wie bei LPI), keine neue ADR noetig — analog zur
  #1679-LPI-Spec.
- **Scope-Korrektur wie beim LPI-Teil wahrscheinlich:** `_fuse_thunder_levels()` bekommt einen
  weiteren Pflichtparameter (`cin_ml_jkg` bzw. eine vorab aufgeloeste CAPE-Leiter) — alle
  Testdateien, die diese Funktion direkt aufrufen, brauchen eine mechanische Ergaenzung (Liste in
  der #1679-LPI-Spec als Vorlage, aber gegen den AKTUELLEN Code neu zu pruefen — die Datei kann
  seit der letzten Spec bereits weitere Aufrufer bekommen haben).
- **Kein neues Raster:** CIN-Baender sind global (nicht regionsabhaengig) — nur die CAPE-Leiter
  selbst ist regions-/modellskaliert (ueber `cape_delta_threshold_jkg`).
- **`cin_ml` ist nur fuer DE_ALPEN/EU_REST (DWD) verfuegbar**, nicht fuer FR — s. Dependencies.

## Naechster Schritt

Kontext + Analyse sind fuer den Standard-Track kombiniert. Weiter mit `/30-write-spec`.
