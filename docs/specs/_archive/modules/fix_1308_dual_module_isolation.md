---
entity_id: fix_1308_dual_module_isolation
type: module
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
tags: [import-convention, module-isolation, data-isolation, issue-1308, bugfix, rot-triage-bundle-3]
---

<!-- Issue #1308 [triage:b] — Bundle 3 der Rot-Triage (dieselbe Rot-Triage
     wie #1306/#1211b). Tiefenanalyse (Laufzeit-Wahrheit, Zähltabellen,
     entschiedenes Fix-Design) in docs/context/fix-1308-dual-module-isolation.md
     — Single Source dieser Spec. -->

# Issue #1308 — Dual-Modul-Isolation: `app.X` vs. `src.app.X` sind zwei Objekte mit getrenntem Zustand

## Approval

- [ ] Approved

## Purpose

`app.X` und `src.app.X` werden von Python als zwei verschiedene Modulobjekte
geladen, weil sowohl der Editable-Install (`.pth` legt `src/` auf
`sys.path`) als auch das uvicorn-Startverzeichnis (Repo-Root, `src` als
Paket) gleichzeitig auflösbar sind. Die #1133-Test-Datenisolation
(`tests/conftest.py` patcht `app.loader._DATA_ROOT`) wirkt deshalb nur auf
den bare-Importpfad — jeder Code, der `src.app.loader` importiert, liest
weiterhin unisoliert echte Nutzerdaten. Das ist kein reines Testartefakt:
dieselbe Zweiobjekt-Situation besteht nachweislich auch in
Prod/Staging-Laufzeit (`a is b == False` im uvicorn-cwd-Kontext). Der Fix
vereinheitlicht die gesamte Produkt-Codebasis (`api/` + `src/`) auf die
strukturell garantierte bare-Importform und macht den verbleibenden
`src.`-Präfix per Kern-Test verboten.

## Source

- **File:** `src/app/loader.py`
- **Identifier:** `_DATA_ROOT` (Modul-Level-Zustand, Z.359), gelesen via
  `get_data_root()`/`get_data_dir()`
- **File:** `tests/conftest.py`
- **Identifier:** `_isolate_data_root`-Fixture (Z.83-97), patcht
  ausschließlich `app.loader._DATA_ROOT`

Betroffene Importzeilen (94 Zeilen, 36 Dateien, alle auf `src.`-Präfix,
verifiziert per Grep über `api/` + `src/`):

- `api/routers/validator.py:23-28` (6 Zeilen)
- `api/routers/preview.py:18-20` (3 Zeilen)
- `api/routers/notify.py:9` (1 Zeile)
- `api/routers/internal.py:19` (1 Zeile, inkl. erklärender Kommentar
  Z.11-18 zum bewusst unisolierten Legacy-Pfad)
- `src/` gesamt: 83 Zeilen in 32 Dateien, Schwerpunkt `src/output/**`
  (27 Zeilen selbstreferenziell, u. a. `src/output/__init__.py:2` importiert
  sich selbst über den `src.`-Präfix), außerdem `src/app/cli.py` (4),
  `src/app/loader.py:721` (1) und 4 `src/services/*`-Dateien

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/conftest.py::_isolate_data_root` | Pytest-Fixture (#1133) | Patcht `app.loader._DATA_ROOT` für Testdauer — Wirkung hängt am bare-Importpfad |
| `src/app/loader.py::_DATA_ROOT`/`get_data_root()`/`get_data_dir()` | Modul-Zustand | Einziger betroffener Zustandsträger im gesamten Fund |
| Editable-Install `.pth` (uv/pip) | Packaging-Mechanismus | Legt `src/` strukturell auf `sys.path` — Grund, warum bare-Form garantiert auflöst, unabhängig vom Launcher-cwd |
| uvicorn-Start (`api.main:app`, cwd=Repo-Root) | Laufzeit-Mechanismus | Repo-Root auf `sys.path` lässt zusätzlich `src` als Top-Level-Paket auflösen → Zweitobjekt in Prod/Staging |
| `api/routers/internal.py::/loaded`-Endpoint | Endpoint (#115) | Nutzt heute bewusst die unisolierte `src.`-Variante (Kommentar Z.11-18); nach Fix modulweit `real_data_root`-markiert |
| `tests/tdd/test_952_onset_alert_fidelity.py` | Test (#952) | Enthält den einzigen Verhaltens-Beweis (xfail Z.636) für die Isolationswirkung |
| `tests/tdd/test_internal_loaded_endpoint.py` | Test (#115) | Blast-Radius-Mitzug — verlässt sich heute auf den unisolierten Legacy-Pfad |
| `tests/tdd/test_issue_1087_trip_official_alerts.py` | Test (F001, #1087) | Blast-Radius-Mitzug — Identitätsvergleich via `importlib.import_module("src.…")` bricht nach der Umstellung, wenn die Strings nicht mitgezogen werden |
| `tests/integration/test_issue_918_alert_preview_4ch.py` | MODIFY | GREEN-Nachzug: verließ sich indirekt auf unisolierten validator.py-Pfad → `real_data_root`-Marker (Muster AC-3) |
| `tests/integration/test_issue_221_validator_endpoints.py` | MODIFY | GREEN-Nachzug: dito (eigener Docstring beschrieb die Unisoliertheit explizit) |
| `tests/integration/test_issue_448_validator_metrics_for_channel.py` | MODIFY | GREEN-Nachzug: dito |
| `tests/unit/test_trip_result_adapter.py` | MODIFY | GREEN-Nachzug: src.-Importe erzeugten nach Migration Klassen-Identitäts-Bruch (dto) → komplett bare |
| `tests/golden/email/conftest.py` | MODIFY | GREEN-Nachzug: _freeze-Patches griffen auf src.-Modulobjekte ins Leere → bare |
| `tests/golden/email/regenerate.py` | MODIFY | GREEN-Nachzug: dito |
| Renderer-Mail-Gate #811 (`renderer_mail_gate.py`) | Pre-Commit-Gate | Greift, weil `src/output/renderers/email/*.py` u. a. Mail-Inhalts-Dateien mechanisch umgestellt werden |
| fix-1317 (Parallel-Session) | Workflow (parallel) | Arbeitet an SMS/Warnungen in `src/output`-Nähe — Überlappungscheck vor Commit Pflicht |

## Estimated Scope

- **LoC:** ~94 Zeilen mechanische Import-Umstellung (`src.` → bare) über
  36 Dateien + ~10 Zeilen Testanpassungen (Marker, importlib-Strings,
  Kommentar) + ~15 Zeilen neuer Guard-Test
- **Files:** 4 `api/`-Router (MODIFY), 32 `src/`-Dateien (MODIFY, als
  Gruppe), 3 Testdateien (MODIFY), 1 neue Testdatei (CREATE)
- **Effort:** low (mechanisch, aber breiter Blast-Radius durch #811-Gate)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `api/routers/validator.py` | MODIFY | Z.23-28: 6 `from src.app.…`/`from src.services.…`-Importe auf bare (`from app.…`/`from services.…`) |
| `api/routers/preview.py` | MODIFY | Z.18-20: 3 `src.`-Importe auf bare |
| `api/routers/notify.py` | MODIFY | Z.9: 1 `src.`-Import auf bare |
| `api/routers/internal.py` | MODIFY | Z.19: `src.app.loader`-Import (`_legacy_load_all_trips`) auf bare umstellen; erklärender Kommentar Z.11-18 auf den neuen Zustand anpassen (Dual-Modul-Duplikat entfällt, `/loaded` liest künftig dasselbe isolierte Objekt wie `/loaded`-Nachbar-Router) |
| `src/output/**` (27 Zeilen, u. a. `src/output/__init__.py:2` Selbstreferenz, `tokens/*`, `renderers/*`, `adapters/*`) | MODIFY | Alle modulinternen `src.output.…`-Selbstreferenzen auf bare (`output.…`) |
| `src/app/cli.py` | MODIFY | 4 `src.`-Importe auf bare |
| `src/app/loader.py` | MODIFY | Z.721: 1 `src.`-Import auf bare |
| `src/services/preview_service.py`, `src/services/weather_change_detection.py`, `src/services/weather_metrics.py`, `src/services/day_comparison.py` | MODIFY | Je 1-3 `src.`-Importe auf bare (Gruppe: 4 Dateien, 7 Zeilen) |
| `tests/tdd/test_952_onset_alert_fidelity.py` | MODIFY | `xfail`-Marker Z.636 (`reason="#1308: …"`) entfernen — Test läuft nach dem Fix echt grün gegen den isolierten Zustand |
| `tests/tdd/test_internal_loaded_endpoint.py` | MODIFY | Modulweiter `pytestmark = pytest.mark.real_data_root` (rein lesende Tests gegen echte `data/users/default/`, etabliertes Muster in 8 bestehenden Dateien inkl. `tests/conftest.py`, `tests/tdd/test_issue_1133_testdata_cleanup.py`) |
| `tests/tdd/test_issue_1087_trip_official_alerts.py` | MODIFY | Z.283-326: alle `importlib.import_module("src.output.…")`-Strings auf bare (`"output.…"`) umstellen, damit die `is`-Identitätsvergleiche (F001, Z.303-324) strukturell korrekt bleiben statt zufällig durch die Bug-Situation zu bestehen |
| `tests/unit/test_import_convention.py` | CREATE | Neuer Collection-Guard `test_no_src_prefixed_imports_in_api_and_src` — Regex-Scan über `api/**.py` + `src/**.py`-Quelltexte, failt bei jeder verbleibenden `from src.`/`import src.`-Zeile |

## Implementation Details

**Mechanische Umstellung (94 Zeilen, 36 Dateien):** Jede Zeile der Form
`from src.<pfad> import …` bzw. `import src.<pfad>` wird auf die bare Form
(`from <pfad> import …` / `import <pfad>`) umgestellt. Semantisch
äquivalent, weil `src/` bereits über den Editable-Install auf `sys.path`
liegt — die bare Form löst exakt dasselbe Zielmodul auf, aber als
dasselbe Objekt wie jeder andere bare-Importeur. Reihenfolge: zuerst
`src/output/__init__.py` (Selbstreferenz, Z.2), danach die restlichen
`src/`-Dateien, zuletzt die 4 `api/`-Router (damit die Router-Tests, die
über `app.loader` isolieren, sofort konsistent laufen).

**Guard-Test statt Alias-Netz:** Der ursprünglich erwogene
`sys.modules`-Alias (`sys.modules["src.app.loader"] = app.loader`) wird
verworfen (Details siehe ADR). Stattdessen erzwingt ein neuer
Collection-Guard `tests/unit/test_import_convention.py::
test_no_src_prefixed_imports_in_api_and_src` die Konvention strukturell:
Er liest jede `.py`-Datei unter `api/` und `src/` (Text, kein Import) und
failt mit Datei:Zeile-Liste, sobald eine `from src.`/`import src.`-Zeile
gefunden wird. Der Test ist damit Teil des Kerns (deterministisch, kein
Netz) und läuft bei jedem Testlauf mit.

**Verhaltens-Beweis statt Identitätstest:** Ein triviales
`import app.loader as a; import src.app.loader as b; assert a is b` wäre
nach dem Fix trivial grün, weil kein Code mehr `src.app.loader` importiert
— ein Test, der es dennoch tut, würde selbst das zweite Modulobjekt neu
erzeugen und liefe strukturell immer grün (misst nichts). Der belastbare
Beweis ist stattdessen der bestehende
`tests/tdd/test_952_onset_alert_fidelity.py`: Er speichert einen Trip über
den isolierten `app.loader`-Pfad und liest ihn über einen API-Router
zurück, der vor dem Fix `src.app.loader` importierte. Grün nach Entfernen
des `xfail`-Markers beweist, dass beide Codepfade jetzt auf demselben
Modulobjekt (und damit demselben `_DATA_ROOT`) operieren.

**Blast-Radius-Mitzug 1 — `test_internal_loaded_endpoint.py`:** Dieser
Test prüft heute bewusst den unisolierten Legacy-Pfad (der erklärende
Kommentar in `api/routers/internal.py:11-18` beschreibt das explizit als
Feature, nicht als Bug — der `/loaded`-Endpoint sollte laut #115 echte
Daten zeigen). Nach dem Fix gibt es keinen unisolierten Pfad mehr, also
wird die Datei modulweit mit `pytest.mark.real_data_root` markiert (rein
lesende Tests, identisches Muster wie in den 8 bereits so markierten
Dateien) und der Kommentar in `internal.py:11-18` wird auf den neuen
Zustand angepasst (kein Dual-Modul-Duplikat mehr; `/loaded` liest bewusst
den echten `data/`-Bestand über den regulären isolierten Loader-Pfad,
Isolation wird pro Testfall über den Marker statt über einen zufälligen
Import-Stil gesteuert).

**Blast-Radius-Mitzug 2 — `test_issue_1087_trip_official_alerts.py`:**
Dieser Test (F001, email-markiert, nicht Teil des Kern-Laufs) prüft
Funktions-IDENTITÄT zwischen Compare- und Trip-Renderern über
`importlib.import_module("src.output.…")`. Nach der Umstellung binden
alle Renderer bare — ein weiterhin `src.`-präfixierter `importlib`-Aufruf
würde ein *drittes* Modulobjekt erzeugen und die `is`-Assertions ließen
sich nicht mehr erfüllen (False Negative, kein echter Regress). Die
`importlib`-Strings (Z.283, 288-291, 321) werden daher mit umgestellt,
damit der Test weiterhin dieselben Objekte vergleicht, die zur Laufzeit
tatsächlich gebunden sind.

## Expected Behavior

- **Input:** Jeder Import von Loader-/Output-/Service-Code in `api/` oder
  `src/`
- **Output:** Ausschließlich bare-Importe; genau ein Modulobjekt pro
  logischem Modul, unabhängig von cwd oder Aufrufreihenfolge
- **Side effects:** Testisolation (#1133) wirkt jetzt lückenlos auf jeden
  Codepfad, der über API-Router läuft; Prod-Laufzeitverhalten bleibt
  unverändert (Loader-Default `data/` bei `_DATA_ROOT=None`), da die
  bare-Form vorher schon der dominante Stil war (537 bare vs. 94 `src.`)

## Acceptance Criteria

- **AC-1:** Given der gesamte Produkt-Code unter `api/` und `src/`, When der Fix umgesetzt ist, Then existiert dort keine einzige `from src.`/`import src.`-Zeile mehr (94 Zeilen in 36 Dateien auf bare umgestellt, inkl. `src/output/__init__.py`-Selbstreferenz) — bewacht durch den neuen Kern-Test `test_no_src_prefixed_imports_in_api_and_src` (Collection-Guard über die Quelltexte).
  - Test: `uv run pytest tests/unit/test_import_convention.py -v` grün; zusätzlich `grep -rn "from src\.\|import src\." api/ src/` liefert keinen Treffer.

- **AC-2:** Given die #1133-Datenisolation (`tests/conftest.py` patcht `app.loader._DATA_ROOT`), When ein Test über `TestClient` einen `api`-Router aufruft, Then wirkt die Isolation auch dort — bewiesen durch `tests/tdd/test_952_onset_alert_fidelity.py`: `xfail(#1308)` entfernt und echt grün (Trip wird im isolierten Root gefunden, Endpoint liefert die Onset-Antwort).
  - Test: `uv run pytest tests/tdd/test_952_onset_alert_fidelity.py -v` grün ohne `xfail`-Decorator, kein `xpass`.

- **AC-3:** Given `tests/tdd/test_internal_loaded_endpoint.py` verließ sich auf den unisolierten Legacy-Pfad, When der Fix greift, Then trägt die Datei modulweit `pytest.mark.real_data_root` und alle ihre Tests bleiben grün (rein lesend, etabliertes Muster); der erklärende Kommentar in `api/routers/internal.py:11-18` ist auf den neuen Zustand angepasst.
  - Test: `uv run pytest tests/tdd/test_internal_loaded_endpoint.py -v` grün; `git diff api/routers/internal.py` zeigt den angepassten Kommentar und den bare-Import.

- **AC-4:** Given `tests/tdd/test_issue_1087_trip_official_alerts.py` prüft Renderer-Funktions-IDENTITÄT via `importlib("src.…")`, When die Renderer bare binden, Then sind die `importlib`-Strings der Datei auf bare umgestellt, sodass die `is`-Assertions strukturell korrekt bleiben (Datei ist email-markiert — Nachweis via gezieltem Collect + Code-Review, kein Ausführungslauf im Kern).
  - Test: `uv run pytest tests/tdd/test_issue_1087_trip_official_alerts.py --collect-only -q -m ""` Exit 0 (ohne Marker-Neutralisierung liefert die voll-deselektierte email-Datei Exit 5 — kein Fehler, Adversary-F002) (kein Collection-Error); `git diff tests/tdd/test_issue_1087_trip_official_alerts.py` zeigt ausschließlich `"src.output.…"` → `"output.…"` in den `importlib.import_module`-Aufrufen.

- **AC-5:** Given die Umstellung berührt Mail-Renderer-Dateien (#811-Gate), When committet wird, Then liegen frisch vor: `test_issue_811_mode_matrix` grün + `briefing_mail_validator.py` Exit 0 gegen echt zugestellte Mail; zusätzlich beweisen Vollimport-Proben (`pytest --collect-only` Exit 0 über die Suite + Import von `api.main`) und die Ziel-Suiten, dass keine der 94 mechanischen Umstellungen einen Importfehler hinterließ.
  - Test: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py -v` grün; `uv run python3 .claude/hooks/briefing_mail_validator.py` Exit 0; `uv run pytest --collect-only -q -m ""` Exit 0 (ohne Marker-Neutralisierung liefert die voll-deselektierte email-Datei Exit 5 — kein Fehler, Adversary-F002); `uv run python -c "import api.main"` Exit 0.

- **AC-6:** Given Produktion startet via `uvicorn api.main:app` aus dem Repo-Root, When der Fix deployt ist, Then ist das Laufzeitverhalten unverändert (Loader-Default `data/` bei `_DATA_ROOT=None`) — nachgewiesen durch Staging-Smoke + echten Staging-Mail-Versand (Rezept) + Prod-Selftest Exit 0 nach `/70-deploy`.
  - Test: Staging-Smoke (`/` → 200/302, `/api/health` → 200) + Testmail über `gregor-test@henemm.com` erfolgreich zugestellt; `python3 .claude/hooks/prod_selftest.py` Exit 0 nach Prod-Deploy.

## Known Limitations

- **Test-Konvention nicht Teil dieser Scheibe:** 83 Testdateien mit
  `src.`-Importen bleiben unangetastet — nach dem Fix harmlos (reine
  Funktionsimporte bzw. die 6 Compare-Tests mit etabliertem
  Doppel-Patch-Muster, das unverändert weiterfunktioniert). Der
  Konventions-Nachzug für `tests/` ist Folgearbeit ohne Verhaltensrisiko
  und wird als Sammel-Eintrag in #1199 geführt, nicht als eigenes Issue.
- **Voller Deploy-Zyklus nötig:** Die Umstellung betrifft Laufzeit-Code
  aller Dienste (nicht nur Testcode) — Staging-Mail-Beweis nach Deploy
  (Rezept analog #1306/#574), Attestation und `/70-deploy` sind
  zwingender Teil der Abnahme, kein optionaler Schritt.
- **Parallel-Session fix-1317:** Arbeitet zeitgleich an SMS/Warnungen in
  unmittelbarer `src/output`-Nähe. Vor Commit ist ein Fetch +
  Überlappungscheck (`git fetch && git log HEAD..origin/main --stat` auf
  `src/output/**`) Pflicht, um Merge-Konflikte oder gegenseitig
  überschriebene Importzeilen auszuschließen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (lokale Bugfix-Entscheidung im Rahmen der Rot-Triage
  #1211b/Bundle 3, keine neue Systemarchitektur)
- **Rationale:**
  1. **Bare als Vertrags-Konvention, nicht `src.`:** Die bare-Importform
     ist strukturell garantiert — der Editable-Install legt `src/` über
     ein `.pth`-File unabhängig von cwd oder Launcher auf `sys.path`. Die
     `src.`-Form hingegen funktioniert nur zufällig, weil das
     uvicorn-cwd zusätzlich den Repo-Root auf `sys.path` legt und `src`
     dort als Top-Level-Paket erscheint — ein Implementierungsdetail des
     aktuellen Start-Kommandos, kein garantierter Vertrag. Verworfene
     Alternative: `src.` zur Norm erklären und `app.`/`output.` verbieten
     — verworfen, weil das jeden Start ohne genau dieses cwd (z. B.
     zukünftige Container-Entrypoints, alternative Test-Runner) bricht.
     Die Konvention wird durch einen Guard-Test erzwungen statt durch ein
     Alias-Netz künstlich toleriert.
  2. **`sys.modules`-Alias-Netz verworfen:** Ein Alias
     (`sys.modules["src.app.loader"] = app.loader`) wurde erwogen und
     verworfen, weil (a) er lazy nachgeladene Submodule nicht schützt —
     genau `loader`/`config` werden bedarfsweise nachgeladen, ein
     statischer Alias zum Importzeitpunkt greift dann nicht zuverlässig;
     (b) in der Übergangszeit reales Zirkularitätsrisiko besteht, weil
     `src/output/__init__.py` sich selbst über den `src.`-Präfix
     importierte — ein Alias hätte diesen Zirkelimport aktiv verschärfen
     können statt ihn aufzulösen; (c) er nach vollständiger Umstellung
     ohnehin überflüssig ist, da kein Code mehr `src.`-präfixiert
     importiert.
  3. **`a is b`-Identitätstest verworfen:** Ein direkter Test der Form
     `import app.loader as a; import src.app.loader as b; assert a is b`
     wurde verworfen, weil der Test-Import selbst das zweite Modulobjekt
     erzeugt — der Test würde vor UND nach dem Fix in sich widersprüchlich
     laufen (vor dem Fix zuverlässig `False`, nach dem Fix triviales
     `True`, weil `b` durch den Test-Code selbst neu angelegt wird,
     nicht weil Produktcode konsistent ist). Strukturell unbestehbar als
     echter Regressionsschutz. Ersetzt durch Collection-Guard (Konvention)
     + `test_952`-Verhaltensbeweis (echte Wirkung über den API-Pfad).
  4. **83 Test-Dateien mit `src.`-Importen bleiben unangetastet:** Nach
     dem Fix sind diese Importe harmlos (keine geteilten Zustandsträger
     außer `loader._DATA_ROOT`, das ohnehin bereits durch die Fixture
     korrekt behandelt wird, sobald der Produktcode konsolidiert ist).
     Die 6 Compare-Tests mit etabliertem Doppel-Patch-Muster (sowohl
     `app.`- als auch `src.app.`-Objekt patchen, um beide potenziellen
     Importwege abzudecken) behalten dieses Muster bei — es bleibt
     funktionsfähig und ist nach dem Fix lediglich redundant, nicht
     falsch. Ein vollständiger Konventions-Nachzug über alle Testdateien
     ist Folgearbeit (#1199), kein Verhaltensrisiko dieser Scheibe.

## Changelog

- 2026-07-19: Initial spec erstellt — Issue #1308, Bundle 3 der Rot-Triage
  #1211b (Sammelprojekt #1196), verifiziert durch Tiefenanalyse in
  `docs/context/fix-1308-dual-module-isolation.md`.
