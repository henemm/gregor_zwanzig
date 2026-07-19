# Context: fix-1308-dual-module-isolation

## Request Summary
Issue #1308 [triage:b]: `app.X` und `src.app.X` sind ZWEI Modulobjekte mit getrenntem Zustand — die #1133-Test-Datenisolation patcht nur das bare Objekt, `src.`-Importe lesen unisoliert echte Daten. **Zweitrunden-Befund: Das Problem existiert auch in Produktion** (empirisch: `a is b == False` im Prod-cwd-Kontext), weil sowohl der Editable-Install (`.pth` → `src/` auf sys.path) als auch das uvicorn-cwd (Repo-Root → `src` als Paket) auflösen.

## Laufzeit-Wahrheit (Beleg-Kern)
- Start Prod/Staging: `cd /home/hem/gregor_zwanzig && uvicorn api.main:app …` (go_proxy_binary.md:170, go_api_setup.md:239). uvicorn setzt cwd immer auf sys.path (uvicorn/main.py:549-550, empirisch bestätigt).
- **Bare-Form ist strukturell garantiert** (Editable-`.pth` unabhängig von cwd/Launcher); `src.`-Form hängt am cwd-Zufall. → Vereinheitlichungs-Richtung: **bare**.

## Bestandsaufnahme
- Import-Stile: bare ~537 vs. `src.` 94 (Faktor 5,7:1). Die 94: **api/ 11 Zeilen in 4 Dateien** (validator.py:23-28, preview.py:18-20, notify.py:9, internal.py:19) + **src/ 83 Zeilen in 32 Dateien** (27 selbstreferenziell in src/output/**, inkl. src/output/__init__.py:2!; app/cli.py; app/loader.py:721; 4 services-Dateien).
- Zustandsträger: einzig `src/app/loader.py:359` `_DATA_ROOT` (gelesen via get_data_root/get_data_dir). #1133-Fixture patcht NUR bare (tests/conftest.py:89-97).
- scripts/ + .claude/hooks/ + Root: **0** src.-Importe. Dynamische Importe: nur 2 Testdateien (s. u.).

## Fix-Design (entschieden)
1. **Alle 94 `src.`-Importe in api/+src/ auf bare** (36 Dateien, mechanisch). Prod-Verhalten identisch (loader-Default bleibt `data/`); Test-Isolation wirkt danach auf ALLE Pfade.
2. **KEIN sys.modules-Alias-Netz** — Zweitrunden-Urteil NEIN mit Beleg: (a) schützt lazy nachgeladene Submodule (genau loader/config!) nicht; (b) reales Zirkularitätsrisiko in der Übergangszeit (src/output/__init__.py importiert sich selbst via src.); (c) nach dem Fix überflüssig.
3. **Regressionstest-Design (WICHTIG — Erstvorschlag war fehlerhaft):** Ein `import app.loader as a; import src.app.loader as b; assert a is b`-Test schlüge auch NACH dem Fix fehl, weil der Test-Import selbst das zweite Objekt erzeugt. Stattdessen: (i) **Collection-Guard** `test_no_src_prefixed_imports_in_api_and_src` (Regex über api/**+src/**-Quelltexte — Konventions-Invariante; bewusste Ausnahme: Verhaltensnachweis ist (ii)); (ii) **Verhaltens-Beweis** = tests/tdd/test_952_onset_alert_fidelity.py:636 xfail(#1308) entfernen — der Test speichert isoliert und liest über den API-Router: grün ⇔ ein Objekt wirksam.
4. **Blast-Radius-Mitzüge (beide belegt):**
   - `tests/tdd/test_internal_loaded_endpoint.py`: verlässt sich HEUTE auf den Bug (Legacy-/loaded-Endpoint bewusst unisoliert, api/routers/internal.py:11-19-Kommentar) → modulweit `pytestmark = pytest.mark.real_data_root` (rein lesende Tests, etabliertes Muster in 8 Dateien) + den erklärenden Kommentar in internal.py:11-18 auf den neuen Zustand anpassen.
   - `tests/tdd/test_issue_1087_trip_official_alerts.py:283-321`: lädt Renderer via `importlib.import_module("src.…")` und prüft Funktions-IDENTITÄT (`is`) — nach dem Fix binden die Renderer bare → Identität bricht. Datei ist email-markiert (nicht im Kern), MUSS aber mit umgestellt werden (importlib-Strings auf bare, ~6 Zeilen), sonst kippt der email-Lauf.
5. **NICHT in dieser Scheibe:** die 83 Testdateien mit src.-Importen (nach dem Fix harmlos: reine Funktionsimporte bzw. die 6 Compare-Tests mit etabliertem Doppel-Patch-Muster, das weiter funktioniert). Konventions-Nachzug der Tests = Folgearbeit (#1199-Eintrag), kein Verhaltensrisiko.

## Gates & Risiken
- **Renderer-Mail-Gate #811 GREIFT:** Die Import-Umstellung berührt src/output/renderers/email/*.py u. a. Mail-Inhalts-Dateien → vor Commit: mode_matrix grün + frischer briefing_mail_validator-Lauf (echte Mail).
- Voller Deploy-Zyklus (Laufzeit-Code aller Dienste): Staging-Mail-Beweis nach Deploy (Rezept #1306/#574), Attestation, /70-deploy.
- Größtes Risiko: Tippfehler in 94 mechanischen Zeilen → Absicherung: Vollimport-Proben (Collection Exit 0, api.main-Import, gezielte Suiten) + Adversary.
- Parallel-Sessions: fix-1317 arbeitet an SMS/Warnungen (src/output-Nähe!) — vor Commit fetch+ff+Überlappungscheck Pflicht.

## Existing Specs
Kein Modul-Spec; ADR-Kandidat: „Import-Konvention bare ist Vertrag; src.-Präfix in api/+src/ verboten (Guard)". test_952-xfail referenziert #1308.
