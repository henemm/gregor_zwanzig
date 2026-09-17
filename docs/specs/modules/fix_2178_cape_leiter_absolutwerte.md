---
entity_id: fix_2178_cape_leiter_absolutwerte
type: fix
created: 2026-09-16
updated: 2026-09-16
status: draft
version: "1.0"
tags: [gewitter, cape, model-registry, issue-2178]
---

# CAPE-Leiter: MED/HIGH auf feste NWS/SPC-Absolutwerte statt regional hochgerechneter Verhältniswerte (Issue #2178)

## Approval

- [ ] Approved

## Purpose

`cape_ladder_thresholds_jkg()` (`src/app/model_registry.py:253-268`) liefert heute für `med`/`high`
keine eigenständig belegten Zahlen, sondern rechnet sie proportional (2,5×/4×) aus der bereits
regional/modellgeeichten `low`-Schwelle hoch (`cape_delta_threshold_jkg()` mit den Nominalwerten
`CAPE_LEITER_MED_NOMINAL_JKG=2500.0`/`CAPE_LEITER_HIGH_NOMINAL_JKG=4000.0`). Für `icon_d2`/`DE_ALPEN`
ergibt das aktuell `(300.0, 750.0, 1200.0)` — deutlich unter den publizierten NWS/SPC-Grenzen ("Weak
instability: less than 1000 J/kg, Moderate: 1000 to 2500, Strong: 2500-4000").

Diese Fix-Scheibe stellt `med`/`high` auf die feste, belegte NWS/SPC-Einteilung um (1000.0 J/kg bzw.
2500.0 J/kg), unabhängig von Modell/Region. `low` bleibt unverändert regional/modellgeeicht über
`cape_threshold_jkg()` — sie ist nicht Teil dieser Fix-Scheibe.

**PO-Entscheid (2026-09-16, verbindlich, nicht erneut vorlegen):** Umstellung auf Absolutwerte JA.
Akzeptierter Preis: das 31.08.-Ereignis (schwaches Gewitter, 2h, 1,8mm) fällt von einer
"mittel"-artigen Einstufung auf "leicht" zurück. #1896 (CIN-Kalibrierung für ICON, hängt an
derselben Stelle) bleibt ein separates Ticket — **bewusst nicht Teil dieser Spec.**

## Source

- **File:** `src/app/model_registry.py`
- **Identifier:** `cape_ladder_thresholds_jkg()` (Zeile 253-268), Konstanten
  `CAPE_LEITER_MED_NOMINAL_JKG`/`CAPE_LEITER_HIGH_NOMINAL_JKG` (Zeile 249-250, werden umbenannt/
  umgewidmet)

**Schicht:** ausschließlich Python-Core (`src/app/model_registry.py`) — reine Kalibrierungs-Konstante
einer internen Fusionsfunktion, kein Go, kein Frontend, keine wählbare Metrik betroffen (CAPE ist
`selectable=False`, #1585).

## Estimated Scope

- **LoC:** ~15-20 Quellcode (`model_registry.py`: zwei Konstanten umbenennen/neu setzen,
  Funktionskörper vereinfachen, Kommentar aktualisieren) + ~10-15 Test (Anpassung der hartcodierten
  Erwartungswerte in `tests/tdd/test_cape_cin_pairing.py`) ≈ **~30 gesamt** — weit unter dem
  250-LoC-Workflow-Limit. Doku-Update in `docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md`
  zählt nicht mit (Doku).
- **Files:** 2 geändert (1 Quellcode, 1 Testdatei) + 1 Doku-Datei (Spec-Update).
- **Effort:** low — Austausch einer Berechnung gegen zwei feste Konstanten, keine neue Logik, keine
  neuen Aufrufstellen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `cape_threshold_jkg()` (`model_registry.py:135-141`) | Upstream, unverändert | liefert weiterhin `low`; einzige Quelle, `cape_ladder_thresholds_jkg()` verankert `low` unverändert daran |
| `cape_delta_threshold_jkg()` (`model_registry.py:223-239`) | bleibt bestehen, wird hier NICHT mehr aufgerufen | zweiter, unabhängiger Aufrufer bleibt unangetastet: `src/services/weather_change_detection.py:811,817` (Änderungsalarm-Presets 1200/600/200, `fix_1592_c3_cape_delta_alarme.md`) |
| `src/providers/thunder_enrichment.py:305` → `_fuse_thunder_levels()` → `src/output/metric_format.py:436-489` (`thunder_level_from_signals`) | Downstream, unverändert im Code | erhält `(low, med, high)` unverändert als Tupel; Wirkung ist eine geänderte Alarmstufe im Briefing (alle vier Kanäle gleichermaßen, zentral bestimmt) — kein Bestandteil dieser Codeänderung |
| `docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md` | zu aktualisieren | Hauptspec der Leiter begründet aktuell die proportionale Skalierung (Implementation Details Punkt 1, Known Limitations) — muss auf die neue absolute Herleitung umgestellt werden |
| #1896 (CIN-Kalibrierung ICON) | explizit AUSSER Scope | separates Ticket, PO-Entscheid 2026-09-16 |

## Implementation Details

```python
# CAPE-Leiter (Issue #1679, CIN-Teil; Issue #2178: MED/HIGH auf Absolutwerte
# umgestellt). Belegt: NWS/SPC, mehrfach unabhaengig publiziert -- "Weak
# instability: less than 1000 J/kg, Moderate: 1000 to 2500, Strong:
# 2500-4000, Extreme: greater than 4000" (Gesamtkonzept 3.5b).
#
# MED/HIGH sind ab #2178 die publizierten Absolutwerte selbst, NICHT mehr
# proportional aus der geeichten LOW-Schwelle hochgerechnet -- die
# Umrechnung (2,5x/4x auf `low`) unterschaetzte MED/HIGH fuer alle
# Modell-/Gebiets-Kombinationen mit `low` < 1000 J/kg systematisch (z.B.
# DE_ALPEN/icon_d2: 750.0/1200.0 statt der publizierten 1000.0/2500.0).
# `cape_delta_threshold_jkg()` bleibt als Funktion bestehen -- sie wird
# weiterhin von `weather_change_detection.py` fuer die (unabhaengigen)
# Aenderungsalarm-Presets genutzt, hier aber NICHT mehr aufgerufen.
CAPE_LEITER_MED_ABSOLUT_JKG = 1000.0
CAPE_LEITER_HIGH_ABSOLUT_JKG = 2500.0


def cape_ladder_thresholds_jkg(
    model_id: Optional[str], region: Optional[str]
) -> Optional[Tuple[float, float, float]]:
    """(low, med, high)-CAPE-Leiter fuer (``model_id``, ``region``). ``low``
    ist unveraendert ``cape_threshold_jkg()`` (regions-/modellgeeicht).
    ``med``/``high`` sind feste, publizierte NWS/SPC-Absolutwerte,
    unabhaengig von Modell/Region (#2178).

    ``None``, wenn keine Kalibrierung fuer die Kombination vorliegt --
    identisch zu ``cape_threshold_jkg()``: fehlt ``low``, liefert die
    GESAMTE Leiter ``None``, nicht ``(None, 1000.0, 2500.0)``."""
    low = cape_threshold_jkg(model_id, region)
    if low is None:
        return None
    return (low, CAPE_LEITER_MED_ABSOLUT_JKG, CAPE_LEITER_HIGH_ABSOLUT_JKG)
```

**Testanpassung** (`tests/tdd/test_cape_cin_pairing.py:71-97`): die Parametrisierung von
`test_ac1_cape_ladder_thresholds_jkg_proportional_zur_kalibrierung` erwartet aktuell
`(300.0, 750.0, 1200.0)` für `("icon_d2", "DE_ALPEN")` und `(420.0, 1050.0, 1680.0)` für
`("ecmwf_ifs04", "EU_REST")`. Beide Erwartungswerte werden auf `(low, 1000.0, 2500.0)` geändert —
`low` bleibt je Kombination unterschiedlich (`300.0`/`420.0`), `med`/`high` werden für BEIDE
Kombinationen identisch `(1000.0, 2500.0)` — das ist der beobachtbare Beweis, dass die Umstellung
tatsächlich modellunabhängig ist (Test- und Funktionsname ändern sich entsprechend, `_proportional_`
→ z. B. `_absolut_gegen_kalibrierte_low_schwelle`). `test_ac1_cape_ladder_low_stimmt_mit_...` und
`test_ac2_..._unbekannte_kombination_liefert_none` bleiben inhaltlich unverändert (prüfen weiterhin
`low`-Identität bzw. die None-Invariante, beides von dieser Änderung nicht betroffen).

## Expected Behavior

- **Input:** `model_id`, `region` (z. B. `"icon_d2"`, `"DE_ALPEN"`).
- **Output:** `(low, med, high)` mit `low` weiterhin modell-/gebietsspezifisch, `med`/`high` fest
  `(1000.0, 2500.0)` für JEDE kalibrierte Kombination — oder `None`, wenn `low` nicht kalibriert ist.
- **Side effects:** keine. Reine Konstanten-/Berechnungsänderung, keine neuen Abrufe, keine
  Signaturänderung an `cape_ladder_thresholds_jkg()` oder ihren Aufrufern.

## Acceptance Criteria

- **AC-1:** Given zwei verschiedene, kalibrierte Modell-/Gebiets-Kombinationen mit unterschiedlicher
  `low`-Schwelle (z. B. `("icon_d2", "DE_ALPEN")` mit `low=300.0` und `("ecmwf_ifs04", "EU_REST")`
  mit `low=420.0`) / When `cape_ladder_thresholds_jkg(model_id, region)` für beide aufgerufen wird /
  Then liefert sie `(300.0, 1000.0, 2500.0)` bzw. `(420.0, 1000.0, 2500.0)` — `low` bleibt
  unterschiedlich, `med`/`high` sind für BEIDE Kombinationen identisch `1000.0`/`2500.0` (fest, nicht
  mehr proportional zu `low`).
  - Test: `test_ac1_cape_ladder_thresholds_jkg_proportional_zur_kalibrierung` in
    `tests/tdd/test_cape_cin_pairing.py:71-97` wird auf die festen Erwartungswerte umgestellt
    (Parametrisierung mit den zwei genannten Kombinationen bleibt bestehen).
  - Gegenprobe: Würde `med`/`high` weiterhin über `cape_delta_threshold_jkg()` proportional zu `low`
    berechnet, ergäben die zwei Kombinationen UNTERSCHIEDLICHE `med`/`high`-Werte
    (`750.0`/`1200.0` vs. `1050.0`/`1680.0`) statt der identischen `1000.0`/`2500.0` — der Test muss
    das fangen.

- **AC-2:** Given eine Kombination ohne Kalibrierung (fehlendes `model_id`, fehlende `region`, oder
  eine Modell-/Gebiets-Kombination ohne Eintrag in `CAPE_THRESHOLDS_JKG`, z. B.
  `("icon_d2", "EU_REST")`) / When `cape_ladder_thresholds_jkg()` aufgerufen wird / Then liefert sie
  für die GESAMTE Leiter `None` — nicht `(None, 1000.0, 2500.0)` mit teilweise gefüllten
  Absolutwerten.
  - Test: `test_ac2_cape_ladder_thresholds_jkg_unbekannte_kombination_liefert_none` in
    `tests/tdd/test_cape_cin_pairing.py:113-138` bleibt unverändert grün (bereits vorhanden, prüft
    genau diese Invariante) — dient als Regressionsanker für die Umstellung.
  - Gegenprobe: Läge nach der Umstellung fälschlich ein Rückfall auf die festen Absolutwerte auch
    ohne kalibrierte `low`-Schwelle vor (z. B. `(None, 1000.0, 2500.0)`), würde dieser Test ein
    Tupel statt `None` sehen und rot werden — das ist der bestehende Schutz, der durch diese Fix
    nicht brechen darf.

- **AC-3:** Given die `low`-Schwelle einer beliebigen kalibrierten Kombination (z. B.
  `("icon_d2", "DE_ALPEN")`) / When `cape_ladder_thresholds_jkg()` und `cape_threshold_jkg()`
  unabhängig für dieselbe Kombination aufgerufen werden / Then ist das erste Element der Leiter
  (`low`) identisch zum Rückgabewert von `cape_threshold_jkg()` — die Umstellung von `med`/`high`
  ändert an `low` nichts.
  - Test: `test_ac1_cape_ladder_low_stimmt_mit_cape_threshold_jkg_ueberein` in
    `tests/tdd/test_cape_cin_pairing.py:100-110` bleibt unverändert grün (bereits vorhanden).
  - Gegenprobe: Würde beim Vereinfachen des Funktionskörpers versehentlich auch `low` durch einen
    festen Wert ersetzt oder falsch durchgereicht, wiche `ladder[0]` von `cape_threshold_jkg()` ab —
    der Test muss das fangen.

## Known Limitations

- **31.08.-Ereignis fällt zurück:** ein schwaches, kurzes Gewitter (2h, 1,8mm) wurde mit den alten
  proportionalen Werten "mittel"-artig eingestuft, fällt mit den neuen, höheren Absolutwerten
  (1000.0/2500.0 statt z. B. 750.0/1200.0 in DE_ALPEN) auf "leicht" zurück. PO-akzeptierter Preis der
  Umstellung (2026-09-16) — kein Bug, keine Regression, nicht erneut vorlegen.
- **#1896 (CIN-Kalibrierung für ICON) bleibt bewusst außerhalb dieser Fix-Scheibe**, obwohl sie an
  derselben Stelle (`cape_ladder_thresholds_jkg()`/CAPE-Fusion) ansetzt — separates Ticket laut
  PO-Entscheid.
- **`med`/`high` sind jetzt für ALLE Modelle/Gebiete identisch** (1000.0/2500.0 J/kg) — anders als
  `low`, die weiterhin regional/modellspezifisch bleibt. Das ist beabsichtigt (NWS/SPC-Einteilung ist
  nicht modellabhängig publiziert), bedeutet aber, dass die Leiter ab jetzt zwei fachlich
  unterschiedlich hergeleitete Sprossen kombiniert (eine geeichte, zwei feste) — dokumentiert in
  `docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md`, die in derselben PR aktualisiert wird.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — reine Kalibrierungskorrektur, keine neue Architektur-Entscheidungsfläche.
- **Rationale:** ADR-0048 ("modellabhängige Schwellen statt einer Zahl") bleibt inhaltlich gültig für
  `low` (weiterhin `CAPE_THRESHOLDS_JKG`-Tabelle) und alle anderen Schwellen-Tabellen im Modul (LPI).
  Diese Fix-Scheibe tauscht nur die Herleitung von ZWEI Sprossen EINER Leiter aus — von "proportional
  aus der geeichten LOW-Schwelle abgeleitet" zu "direkt aus der publizierten NWS/SPC-Quelle
  übernommen" — kein neues Muster, keine Entscheidung über Kanäle, Provider, Datenmodell/Persistenz,
  Auth, Editor-Paradigma oder Test-/Deploy-Strategie. Die betroffene Doku
  (`feat_1679_cin_paarung_cape_leiter.md`) wird in derselben PR aktualisiert statt durch ein neues
  ADR abgelöst, da keine Grundsatzentscheidung revidiert wird, sondern eine dort dokumentierte
  Herleitung durch eine belegtere ersetzt wird.

## Changelog

- 2026-09-16: Initial spec created (Issue #2178).
