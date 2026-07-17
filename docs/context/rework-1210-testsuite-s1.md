# Context: rework-1210-testsuite-s1

## Request Summary
Issue #1210 (Sammelprojekt #1196, Scheibe 1): Die pytest-Suite soll zuverlässig **terminieren und vollständig sammeln** — Hänger gaten, Collection-Fehler beheben, Marker-Hygiene. Ziel ist NICHT „alles grün" (das ist Scheibe 2, #1211).

## Befund-Update (2026-07-17, dieser Workflow — weicht vom Issue-Stand ab!)

| Issue-Behauptung (Vorarbeit 2026-07-09) | Stand heute |
|---|---|
| Collection-Blocker `test_issue_948_e2e_allowed_dir.py` (ModuleNotFoundError edit_gate) | **Datei existiert nicht mehr** — bereits gelöscht, Blocker weg |
| Collection-Blocker `test_issue_811_renderer_gate.py` (ImportError als `claude-gregor`) | Datei existiert; als `hem` sammelt sie sauber. Verhalten als `claude-gregor` noch zu verifizieren |
| `uv run pytest --collect-only -q` bricht ab | **Exit 0** — Collection läuft vollständig durch (Lauf 2026-07-17 im Worktree, aktuell zu origin/main 3e3124aa) |
| Hänger `test_issue_1009_1019_inbound_robustness.py` | **Unverändert scharf**: 5 Tests der Datei sind im Standard-Lauf selektiert; Datei hat KEINEN Modul-Marker |

Konsequenz: Der Scope verschiebt sich von „Collection reparieren" (weitgehend erledigt) auf **Hänger gaten + Marker-Hygiene in beide Richtungen** (Live-Zugriffe ohne Marker rein ins Gate; deterministische Tests hinter Modul-Markern raus aus dem Gate).

## Related Files

| File | Relevance |
|------|-----------|
| `pyproject.toml` `[tool.pytest.ini_options]` | Standard-Selektion `addopts = "-q -m 'not email and not live and not staging'"`; Marker-Registry (`tdd`, `email`, `live`, `staging`, `real_data_root`) |
| `tests/tdd/test_issue_1009_1019_inbound_robustness.py` | DER bekannte Hänger: `imaplib.IMAP4_SSL` (Z. 145-146), `while True` + `sleep(8)`-Poll (Z. 184-202), echter SMTP-Versand — ohne Modul-Marker. Nur der Telegram-Teil (ab Z. 350) ist per `GZ_TELEGRAM_LIVE`-skipif gegated |
| `tests/tdd/test_issue_811_renderer_gate.py` | Importiert Gate-Hook-Infrastruktur; Issue meldet ImportError als `claude-gregor` (Plugin unter `~hem/.claude/plugins/` unsichtbar). Kandidat: `importorskip`-Guard oder Löschen (prüft Infrastruktur außerhalb des Repos) |
| `tests/unit/test_model_metric_fallback.py` | Beispiel für zu grobe Marker: Modul-weit `live`, obwohl deterministische Teile (`TestFooterFallbackInfo`) existieren — Achtung: Datei wurde von #1302 (A1, `src/providers/merge.py`) gerade angefasst |
| 23 Module mit `pytestmark = pytest.mark.live` | Sweep-Kandidaten Richtung „feingranular": u. a. `tests/unit/test_openmeteo_endpoint_routing.py`, `tests/unit/test_metric_availability_probe.py`, `tests/unit/test_uv_air_quality.py`, `tests/integration/*` (8 Dateien), `tests/tdd/*` (11 Dateien) |
| 27 Dateien mit `imaplib`/`smtplib`-Bezug OHNE `pytestmark` | Sweep-Kandidaten Richtung „gaten oder als harmlos belegen" — darunter bekannte Echt-Versender wie `test_issue_1012_no_data_guard.py` (Memory: sendet echte Mails, MeteoAlarm live, 452/429-Falle). Differenzierung nötig: manche nutzen smtplib nur als Monkeypatch-Ziel/lokalen Dummy |
| 6 Dateien mit `while True` | Poll-Schleifen = potenzielle weitere Hänger hinter dem bekannten (Voll-Lauf der Vorarbeit kam nur bis 39 %): `test_issue_684_alert_email_guard.py`, `test_briefing_mail_inhalt.py`, `test_issue_1113_partial_outage_guard.py`, `test_issue_1007_heute_voll_briefing.py`, `test_issue_1012_no_data_guard.py`, `test_issue_1009_1019_inbound_robustness.py` |

Mengengerüst: 577 Testdateien gesamt, davon 472 in `tests/tdd/`.

## Existing Patterns
- **Opt-in-Marker-Muster:** `pytest.mark.email` / `live` / `staging` auf Modul- oder Klassenebene; Standard-Selektion schließt sie aus. Korrekt gemachtes Beispiel: Telegram-Teil in der Hänger-Datei (`skipif GZ_TELEGRAM_LIVE!=1`).
- **`real_data_root`-Marker (#1133):** Data-Root-Isolations-Fixture, Opt-out explizit.
- **Test-Politik zwei Schichten (CLAUDE.md):** Kern deterministisch (Commit-Gate, 100 % grün Pflicht) vs. Live-E2E (Marker, nur `/e2e-verify`). Scheibe 1 stellt genau diese Trennung mechanisch her.
- **Deadline-Muster für Polls:** Poll-Schleifen brauchen hartes Zeitlimit (Issue-Vorgabe: „der Poll-Schleife ein hartes Deadline-Limit geben").

## Dependencies
- Upstream: pytest 8.4.1 (uv dev-group), Marker-Definitionen in `pyproject.toml`.
- Downstream: **Commit-Gate/qa_gate** (liest Testausgaben — `-v -p no:warnings`-Falle #1281), CI-lose Lokal-Läufe aller parallelen Sessions, Scheibe 2 (#1211) setzt terminierende Suite voraus.

## Existing Specs
- Kein Modul-Spec; Politik-Referenz: CLAUDE.md „Test-Politik: Zwei Schichten" (PO-go 2026-07-09). Issue #1210 enthält AC-Entwürfe (AC-1 Collection Exit 0 · AC-2 Standard-Lauf terminiert · AC-3 deterministische Tests wieder in Selektion).

## Risks & Considerations
- **NIEMALS die Suite blind voll ausführen:** `tests/tdd/` versendet z. T. echte Mails und ruft MeteoAlarm live (Memory/CLAUDE.md); Läufe nur mit Standard-Selektion, gezielt, mit `timeout`, und Ausführungs-Proben nur auf nachweislich netzfreien Teilmengen.
- **Parallel-Sessions:** #1301-A (Provider/Merge) und fix-1296 fassen gerade `tests/unit/test_model_metric_fallback.py`, `test_provider_merge_contract.py`, Compare-Tests an → diese Dateien in dieser Scheibe NICHT umtaggen, um Merge-Konflikte zu vermeiden; im Zweifel auslassen und in Scheibe 2 nachziehen.
- **Marker-Lockerung ist gefährlicher als Marker-Setzen:** Einen `live`-Modul-Marker feingranular machen kann versehentlich Netz-Tests in den Standard-Lauf holen. Jede Lockerung braucht Nachweis der Netzfreiheit (Code-Inspektion + Offline-Probe).
- **`claude-gregor`-Perspektive:** Referenz-Repro des Issues läuft als `claude-gregor` im Hauptrepo; dieser Workflow arbeitet im Worktree als `hem`. AC-Nachweis muss beide Sichten berücksichtigen (mind. den 811-ImportError-Fall).
- **Kein Threshold-/Gate-Aufweichen:** Nur Marker/Deadlines/Löschungen nach Test-Politik; `addopts` selbst bleibt unverändert.

## Analysis

### Type
Rework/Bug (Infrastruktur der Testsuite; kein Produktverhalten betroffen — Ausnahme: `smtplib.SMTP`-Timeout in `email.py` wird bewusst NICHT in dieser Scheibe angefasst, s. u.)

### Kernbefunde (3 parallele Sweeps, 2026-07-17, alle mit Datei:Zeile belegt)

**B1 — Live-Leck im Standard-Lauf (schwerwiegender als im Issue beschrieben):** Es gibt keinen SMTP/IMAP-Netzblocker in `conftest.py` und kein `pytest-timeout` (fehlt in `uv.lock`). **10 Dateien** können im Standard-Lauf echte Mails senden / IMAP pollen, weil sie nur Laufzeit-Gates (`pytest.skip` bei fehlenden Creds, `can_send_email()`) statt der addopts-wirksamen Marker nutzen — und die Credentials liegen real in `.env`:
- Komplett ungegatet (nicht einmal skip): `test_issue_1113_partial_outage_guard.py`, `test_issue_1007_heute_voll_briefing.py`, `test_issue_1012_no_data_guard.py`
- Credential-Skip statt Marker: `test_issue_1009_1019_inbound_robustness.py` (der bekannte 39-%-Hänger), `test_773_alert_e2e.py`, `test_952_onset_alert_e2e.py`, `test_issue_684_alert_email_guard.py`, `test_issue_1087_trip_official_alerts.py`, `test_issue_1169_compare_alert_consumer.py`, `test_issue_972_974_975_tooling.py` (autouse-Fixture mit `assert` statt skip), `test_issue_1147_resend_recipient_invariant.py` (dialt echten `smtp.resend.com`)

**B2 — Hänger-Mechanik:** `imaplib.IMAP4_SSL(...)`/`smtplib.SMTP(...)` ohne `timeout=` → TCP/TLS-Connect kann endlos blockieren; Deadline-Checks stehen NACH dem Connect. Betrifft alle o. g. Dateien. False Positives (kein Fix nötig): `while True` in `test_briefing_mail_inhalt.py` (String-Parser, terminiert) und `test_issue_684` `_accept_and_close` (terminiert via `close()`).

**B3 — Footgun:** `tests/e2e/test_e2e_friendly_format_config.py::test_alert_enabled` wird trotz Docstring „NICHT als pytest" im Standard-Lauf gesammelt+ausgeführt und mutiert `data/users/default/trips/*.json` direkt (umgeht #1133-Isolation), ohne Restore.

**C — Zu grobe live-Marker:** 23 Module modul-weit `live`; ~85 Tests nachweislich deterministisch. Zweifelsfreie Ganz-Datei-Fälle: `tests/test_geosphere.py` (8/8, HTTP gemockt), `tests/test_providers_base.py` (8/8, kein HTTP). Große Teilbar-Fälle (`test_multi_day_trend.py` 21/21, `test_forecast_confidence_backend.py` 16/18, `test_openmeteo_endpoint_routing.py` 9/11 u. a.) → wegen Rot-Risiko (Commit-Gate aller Sessions!) NICHT in dieser Scheibe, Vorarbeit dokumentiert für #1211. `test_compare_provider_routing.py` nicht anfassen (#1301-A2 löscht das getestete `_select_provider_for_location`).

**A — Collection:** heute Exit 0 (Blocker 948 bereits gelöscht). Rest: `test_issue_811_renderer_gate.py` erroret nur als `claude-gregor` (Plugin unsichtbar) → `importorskip`-Guard.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `pyproject.toml` | MODIFY | `pytest-timeout` (dev-group) + `timeout`-Default als Sicherheitsnetz |
| `uv.lock` | MODIFY | Lockfile-Update (generiert, zählt nicht ins LoC-Limit) |
| 10 Test-Dateien (Liste B1) | MODIFY | `pytest.mark.email`-Marker auf Modul-/Klassen-/Funktionsebene; bestehende Skips bleiben als Defense-in-Depth; `timeout=` an `IMAP4_SSL`/`SMTP`-Aufrufe in Tests |
| `tests/e2e/test_e2e_friendly_format_config.py` | MODIFY | Aus Standard-Collection nehmen (Marker/Umbenennung) — stoppt Prod-Daten-Mutation |
| `tests/tdd/test_issue_811_renderer_gate.py` | MODIFY | `importorskip`-Guard für Plugin-Abhängigkeit |
| `tests/test_geosphere.py`, `tests/test_providers_base.py` | MODIFY | Modul-`live`-Marker entfernen (zweifelsfrei offline, vorher gezielt grün verifiziert) |

### Scope Assessment
- Files: ~15–17 · Estimated LoC: +60–90 (unter dem 250-Limit, sofern Granular-Lockerung der 21 Teilbar-Module draußen bleibt)
- Risk Level: MEDIUM (größtes Risiko: versehentlich zurückgeholter Netz-Test; zweitgrößtes: zurückgeholter roter Test blockiert Commit-Gate aller Sessions → Rückholung nur nach gezielter Grün-Probe)

### Technical Approach (Empfehlung Plan-Agent, übernommen)
Reihenfolge: (1) `pytest-timeout` + ini-Default → (2) Footgun-Gate friendly_format → (3) Live-Lecks marken (1147, 1009/1019, 1113/1007/1012, dann Rest) → (4) 811-Import-Guard → (5) geosphere/providers_base entmarkern (nach Einzel-Grün-Probe). **Nicht in dieser Scheibe:** `email.py`-Prod-Timeout (koppelt ans un-überspringbare #811-Renderer-Mail-Gate → eigener Workflow), Granular-Feinschnitt der 21 Teilbar-Module und jede Rot-Triage (→ #1211).

### Dependencies
- `pytest-timeout` nur dev-group — Prod-Deploy unberührt (Deploy macht kein `uv sync`, Kern importiert kein pytest).
- Live-/E-Mail-Läufe (`/e2e-verify`, Marker-Läufe) brauchen beim expliziten Aufruf einen Timeout-Override (`--timeout=…` hoch/0), Doku-Hinweis genügt.

### Open Questions
- [ ] Keine blockierenden — Scope-Schnitt (Teil A jetzt, Rest #1211) ist Empfehlung und wird über die AC-Freigabe entschieden.
