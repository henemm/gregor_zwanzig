# Spec: #1265-Datenpfad-Migration vervollständigen — 3 Services auf get_data_dir

- **Issue:** #1196 / #1265-Vervollständigung (aufgedeckt in #1197-Session)
- **Created:** 2026-07-16
- **Typ:** Konsistenz-Migration (verhaltens-erhaltend; schließt Test-Isolations-Lücke + latente Robustheits-Schuld)
- **ADR-Nr.:** keine
- **Dateien:** `src/services/user_tier.py`, `src/services/compare_radar_alert.py`, `src/services/compare_weather_snapshot.py`

## Problem

Drei per-User-Reader lesen weiter hartkodiert `data/users/{user_id}/…` statt über
`get_data_dir(user_id)` — inkonsistent zur #1265-Migration, bricht die pytest-
Isolation und ist latente Robustheits-Schuld.

## Lösung

Hartkodierte Pfade durch `get_data_dir(user_id) / "…"` ersetzen (Laufzeit-Auflösung,
Instanz-/Funktions-Ebene).

## Acceptance Criteria

**AC-1:** Given ein `user.json` mit einem Tier, der SMS erlaubt, liegt unter
`get_data_dir(user_id)` (isolierte Testwurzel), When `user_tier.sms_allowed(user_id)`
aufgerufen wird, Then liefert es das Ergebnis aus genau dieser Datei (nicht den
Default eines nicht gefundenen Profils).

**AC-2:** Given ein `user.json` mit gesetztem `daily_alert_limit` unter
`get_data_dir(user_id)` (isolierte Wurzel), When `user_tier.daily_alert_limit(user_id)`
aufgerufen wird, Then liefert es den Wert aus dieser Datei.

**AC-3:** Given eine isolierte Datenwurzel, When ein `CompareRadarAlertService` für
`user_id` konstruiert wird, Then zeigt seine Throttle-Datei auf
`get_data_dir(user_id) / "compare_radar_alert_throttle.json"` (unter der isolierten
Wurzel, nicht unter hartkodiertem `data/users`).

**AC-4:** Given eine isolierte Datenwurzel, When ein `CompareWeatherSnapshotService`
für `user_id` eine Snapshot speichert und wieder lädt, Then erfolgt beides unter
`get_data_dir(user_id) / "compare_weather_snapshots"` (Roundtrip unter der isolierten
Wurzel erfolgreich).

**AC-5 (verhaltens-erhaltend):** Given die Default-Datenwurzel (kein `GZ_DATA_DIR`,
`_DATA_ROOT` ungesetzt, cwd = Repo-Wurzel), When die migrierten Pfade aufgelöst
werden, Then sind sie identisch zu den bisherigen relativen `data/users/{user_id}/…`
(kein Verhaltenswechsel auf Prod/Staging).

**AC-6 (Zwei-Nutzer-Isolation):** Given zwei verschiedene `user_id` unter einer
isolierten Wurzel, When jeder ein eigenes `user.json` bzw. eine eigene Compare-
Snapshot/Throttle-Datei hat, Then greift jeder Service ausschließlich auf die Daten
seines eigenen `user_id` zu (kein Cross-User-Leck durch die Migration).

## Known Limitations

- `gpx_processing.py` (`_DEFAULT_UPLOAD_DIR`/`_GPX_UPLOAD_DIR`, Modul-Konstanten auf
  „default"-User) ist NICHT Teil dieser Migration — separater Folgebefund (#1196),
  da Import-Zeit-Konstante + eigene Multi-Tenancy-Frage.

## Changelog / Scope-Erweiterung (2026-07-16)

- Die 3 src-Migrationen brechen erwartungsgemäß Bestands-Tests, deren Fixtures die
  Nutzer-Dateien noch hart in den echten `data/users`-Baum schrieben. Als
  **notwendige Vervollständigung** der freigegebenen Migration wurden 7 gekoppelte
  Test-Dateien nachgezogen (service-geschriebene Artefakte + `user.json` →
  `get_data_dir`): `test_issue_1069_tier_channel_gating`, `test_issue_1070_daily_alert_limit`,
  `test_914_slice4_alert_sms_dispatch`, `test_952_onset_alert_fidelity`,
  `test_compare_radar_alert`, `test_compare_official_alert`, `test_issue_1169_compare_alert_consumer`.
- **Trennlinie (bewusst):** Compare-**Preset**-Fixtures bleiben beim echten Baum,
  weil `load_compare_presets(data_root="data")` die #1133-Isolation nicht honoriert
  (nur service-geschriebene Artefakte + user.json sind isoliert). Diese
  Preset-Inkonsistenz ist ein separater Folgebefund → #1196/#1199.
- **Pre-existing, NICHT durch diese Migration:** `test_952_onset_alert_fidelity`
  Onset-Preview-Fall bleibt rot (404) wegen der `app.loader` vs. `src.app.loader`-
  Doppel-Import-Namespace-Lücke in `api/routers/validator.py` (Isolationsfixture
  patcht das andere Modul-Objekt). Eigener Folgebefund #1199 (#1133-Klasse).

## Test-Politik

Kern-Schicht, deterministisch: die pytest-Isolationsfixture (#1133,
`tests/conftest.py`) setzt `_DATA_ROOT` auf ein tmp_path. Tests schreiben echte
`user.json`/Snapshot-/Throttle-Dateien unter `get_data_dir(user_id)` und prüfen,
dass die Services dort lesen/schreiben (kein Netz, kein Mock). Neue Datei
`tests/tdd/test_data_root_migration_services.py`.
