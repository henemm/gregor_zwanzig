# Context: fix-1133-testdata-cleanup

**Issues:** #1133 (Testdaten-Verschmutzung) + Baustein-B-Rest aus #1147 (Cleanup Kunst-User)

## Request Summary

Test-Residuen aus Prod- und Staging-`data/users/` entfernen (mit Backup + Positivliste
echter Nutzer) und die Ursache beheben: Python-Tests schreiben in den echten
`data/users/`-Baum, weil der Daten-Root nicht umlenkbar ist.

## Datenlage (erhoben 2026-07-09)

### Prod (`/home/hem/gregor_zwanzig/data/users/`, 139 Verzeichnisse)

- **Echte Nutzer (Positivliste):** `admin`, `default`, `henning`, `steffi`
- **124 Test-Residuen:** `tdd-*` (Mehrzahl), `prodverify1082-1783518721` (issue-explizit
  in #1147 genannt), `bug663usera`, `bug670user[ab]`, `__bug89_*`, `userA`, `userB`
- **Aktive Verschwendung:** `userA`/`userB` erhalten bis heute täglich Wetter-Snapshots
  vom Prod-Scheduler (Fan-out über alle User) — API-Quota + Rechenzeit
- **Grenzfall `validator-issue110`:** 8 realistisch aussehende Trips (ortler-2025,
  dachstein-2023, venediger-2024, khw-402, stubai-2024, gardasee-2024, zillertal-2025,
  rofan-2025) — womöglich echte Alt-Daten aus früher Projektphase. NICHT blind löschen;
  PO-Entscheid nötig (archivieren vs. löschen). Zugleich ist `validator-issue110` der
  nginx-Basic-Auth-Name in `.claude/validator.env` (nur Namensgleichheit, Basic-Auth
  nutzt htpasswd, keine App-User).
- **Residuen INNERHALB echter Nutzer:** `admin` und `default` enthalten `e2e-*`- und
  `adv-test-*`-Trips; `henning/weather_snapshots/` enthält `validator-*`-/`test-trip`-Reste.

### Staging (`/home/hem/gregor_zwanzig_staging/data/users/`, 153 Verzeichnisse)

- **Echte Nutzer:** nur `default` (App-Login `GZ_AUTH_USER=default`, auch für
  E2E-Verify). Kein `henning`/`steffi`/`admin` auf Staging.
- Rest: `e2e*`, `extval*`, `val*`, `reg_v_*`, `tdd-*`, `compare*/planning*/trip647*` u.ä.

## Root Cause (Explore-Analyse)

**Python-Daten-Root ist nicht umlenkbar.** `get_data_dir()` in `src/app/loader.py:774`
baut hart `Path("data/users") / user_id` — relativ, ohne Env/Setting-Override. Das
Modul-Global `_DATA_ROOT` (`loader.py:206`) wird NUR vom `compare_subscriptions`-Pfad
respektiert (`loader.py:1292-1298`), nicht von `get_data_dir()`.

- ~37 Testdateien rufen `save_trip()` ohne `data_dir=` auf → echter Baum
- ~23 Testdateien konstruieren `Path("data/users/...")` direkt (Überschneidung)
- ~10 davon schreiben in den **echten `default`-User** (z.B.
  `tests/tdd/test_issue_612_report_on_demand.py:289`, `test_inbound_gate_errors.py:99`)
- Nur 6 Dateien isolieren korrekt via `save_trip(trip, data_dir=tmp_path)` (Issue #303)
- **Keine zentrale conftest-Fixture** für den Daten-Root; `tests/tdd/conftest.py:48-56`
  hartkodiert sogar den echten Baum (punktueller Throttle-Cleanup für `tdd-638-*`)
- Vorhandene Teardowns (~30 Dateien, `rmtree`/`unlink`) sind best-effort — laufen bei
  Abbruch nicht; Beleg: liegengebliebene Residuen
- Hartkodierte `Path("data/users/...")` auch in Services: `src/services/trip_alert.py:79,556,821`,
  `trip_report_scheduler.py:257,330,937`, `user_tier.py:6,22`, `alert_daily_limit.py:23`,
  `gpx_processing.py:37-38`, `src/app/config.py:259`
- **Go ist sauber:** `internal/config/config.go:9` (`DATA_DIR`-Env, injiziert), alle
  Store-Tests nutzen `t.TempDir()`

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/loader.py:774-791` | `get_data_dir()`/`get_trips_dir()` — hier Root-Override einbauen |
| `src/app/loader.py:206,1292-1298` | vorhandener `_DATA_ROOT`-Mechanismus (Vorbild) |
| `tests/conftest.py:18` | autouse-Fixture-Vorbild (`_use_fixture_provider`) — hier Data-Root-Fixture ergänzen |
| `tests/tdd/conftest.py:48-56` | hartkodierter echter Baum — anpassen/entschärfen |
| `src/services/*.py` (s.o.) | hartkodierte Pfade — optional auf zentrale Auflösung umstellen |

## Existing Patterns

- `_DATA_ROOT`-Override für compare_subscriptions (`loader.py:1296-1298`) — exakt das
  Muster, das `get_data_dir()` übernehmen soll
- `save_trip(..., data_dir=)` seit #303 — Parameter existiert, wird kaum genutzt
- Go: `DATA_DIR`-envconfig + `t.TempDir()` — Zielbild
- Backup-Muster: `data_schema_backup.py` (tar.gz nach `.backups/`, Retention 20);
  Daten-Migration als per-Host-Deploy-Schritt, als `claude-gregor`, idempotent+Backup

## Dependencies

- **Upstream:** Prod-/Staging-Scheduler iterieren `data/users/*` (Fan-out) — Residuen
  mit Trips erzeugen täglich Arbeit; Empfänger-Invariante #1147 (Baustein A) blockt
  Test-Postfach-Sends über Resend hart (Fehlerfall statt Leak)
- **Downstream:** `test_ac9`-Roundtrip-Test iteriert `data/users/*/trips/*.json`
  (verrauscht durch Residuen, Motivation von #1133)

## Risks & Considerations

1. **Löschung in produktiven Datenbäumen** — Datenverlust-Historie (#102). Zwingend:
   tar.gz-Backup vor Löschung, Positivliste statt Negativmuster als letzte Instanz,
   als `claude-gregor` ausführen, idempotent.
2. **`validator-issue110`** könnte echte Alt-Daten enthalten → PO-Frage in Spec.
3. **Trip-Residuen in echten Usern** (`admin`, `default`, `henning`): Löschen einzelner
   Trips ist riskanter als ganzer User-Verzeichnisse — konservative Liste, PO-Freigabe.
4. **Autouse-Data-Root-Fixture** ändert Verhalten ALLER Python-Tests — Live-/Staging-
   HTTP-Tests (Kategorie a) treffen echte Server und bleiben bewusst unberührt;
   Tests, die absichtlich den echten Baum lesen (z.B. `test_ac9`), brauchen Opt-out.
5. Staging-Cleanup parallel zum Auto-Deploy-Cron (`*/5`) — kein Konflikt erwartet
   (Daten sind gitignored), aber Scheduler-Läufe beachten.
6. Baustein-B-Prozessteil (Playbook + Memory) ist bereits live (#1147, `f6cda847`) —
   dieser Workflow liefert nur noch Cleanup + Ursachen-Fix.
