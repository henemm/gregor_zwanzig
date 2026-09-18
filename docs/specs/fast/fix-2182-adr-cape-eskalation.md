# Mini-Spec: ADR-0048-Bruch bereinigen (#2182)

## Ausgangslage (Recherche abgeschlossen)

ADR-0048 (08.08.) hielt fest: „CAPE misst Energie, kein Ereignis, und eskaliert nie über LOW."
Commit `937bba52` (#1679, 11.08.) hat genau das per CIN-Kopplung aufgehoben — dokumentiert in
Code-Kommentar und Modul-Spec (`feat_1679_cin_paarung_cape_leiter.md`), aber **nie als eigene
ADR**. ADR-0064 (#2176, 08.09.) hat später nur den LOW-Darstellungssatz aus ADR-0048 abgelöst,
nicht die Eskalationsfrage selbst. Issue #2178 (17.09., gemergt) hat die Leiter-Absolutwerte
nochmal geändert (1000/2500 J/kg statt proportional 750/1200) — ebenfalls ohne ADR.

**Punkt 3 des Tickets** (feat_1474 AC-6 nachziehen) ist bereits erledigt — die Spec trägt seit
#1679 den Revisionsvermerk. Es wird hier **nichts neu entschieden** — nur der bereits gelebte
Ist-Zustand in `docs/adr/` sichtbar gemacht, wie CLAUDE.md es verlangt („Eine dokumentierte
Entscheidung wird nie still rückgängig gemacht").

## Was ändert sich

- Neue ADR `docs/adr/00XX-cape-eskaliert-ueber-low-bei-schwacher-konvektionshemmung.md`,
  die die #1679-Entscheidung (CIN-Bänder bestimmen CAPE-Eskalation bis MED/HIGH) und die
  #2178-Nachschärfung (feste Absolutwerte 1000/2500 J/kg für med/high statt proportional
  hochgerechnet) als **Ist-Zustand** dokumentiert — löst den betroffenen Satz aus ADR-0048 ab.
- In ADR-0048 wird an der betroffenen Stelle (Abschnitt „Unberührt bleibt...") ein Verweis-Block
  ergänzt, analog zum bestehenden `[Abgelöst durch ADR-0064, ...]`-Muster.
- Neuer Zeileneintrag in `docs/adr/README.md` (Index).

## Was sich nicht ändert

- Kein Code — `model_registry.py`, `thunder_level_from_signals()` bleiben unangetastet.
- ADR-0048 bleibt für die übrigen Regeln (modellabhängige Schwellentabelle) unverändert
  **Akzeptiert** — nur der eine Eskalations-Satz wird zusätzlich als abgelöst markiert.
- ADR-0064 bleibt unverändert (deckt nur die Darstellungsfrage LOW, nicht die Eskalation ab).

## Manuelle Test-Schritte

1. `docs/adr/README.md` öffnen — neuer Eintrag zeigt auf die neue ADR-Datei, Datei existiert.
2. `docs/adr/0048-...md` öffnen — der Eskalations-Satz trägt jetzt einen Ablöse-Verweis.
3. `python3 -m pytest tests/test_adr_index_drift.py` — grün (Index↔Datei-Konsistenz).

## Inline-Test (wird während Implementierung geprüft)

- [ ] `tests/test_adr_index_drift.py` bleibt grün nach dem neuen Index-Eintrag.
