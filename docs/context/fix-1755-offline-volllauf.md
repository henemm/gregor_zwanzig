# Context: fix-1755-offline-volllauf

## Request Summary
Issue #1755: Der dokumentierte Weg zu einem sicheren vollen Testlauf (`uv run pytest --disable-socket`,
Freigabe im `broad_test_run_gate`) ist praktisch unbenutzbar, weil pytest-socket auch lokale Verbindungen
sperrt. Ziel: ein voller Offline-Lauf, der nur echte Fehler zeigt und echten Ausgang trotzdem sicher sperrt.

## Messung 2026-11-08 (Stand `origin/main` c102b66cb, Branch `fix-1755-offline-volllauf`)

| Aufruf | Ergebnis | Dauer |
|---|---|---|
| `pytest --disable-socket --ignore=tests/red/` | 1391 FAILED+ERROR-Zeilen, davon 1228x `SocketBlockedError`, 18x `'_UnixSelectorEventLoop' has no attribute '_ssock'` | 44 min |
| `pytest --disable-socket --allow-unix-socket --ignore=tests/red/` | 472 failed + 411 errors (883), davon 878x `SocketBlockedError` („tried to use socket.socket“) | 42 min |
| `--allow-hosts=127.0.0.1,::1,localhost` (CI-Form) | **lokal bewusst NICHT gemessen**, siehe Risiko 1 | – |

Rohlogs: Scratchpad der Sitzung (`run_bare.txt`, `run_unix.txt`), nicht versioniert.

**Befund:** Gegenüber August (297/79) ist das Rauschen auf über 1.300 Zeilen gewachsen. `--allow-unix-socket`
allein reicht nicht: Rund 90 Testdateien starten lokale Test-Doubles (HTTP-Stub-Server auf `127.0.0.1`,
z. B. Telegram/seven.io-Attrappen). Unter `--disable-socket` ohne `--allow-hosts` ist schon das **Erzeugen**
eines AF_INET-Sockets gesperrt. Mit `--allow-hosts` schaltet pytest-socket auf einen `connect`-Wächter um
(`socket_allow_hosts`), dann sind Bind/Listen frei und nur Verbindungen zu nicht gelisteten Hosts gesperrt.

Nicht-Socket-Rote im Unix-Lauf (Kandidaten für echte Kern-Rote oder Zeitabhängigkeit, getrennt prüfen):
`tests/golden/test_inbound_golden.py` (3), `tests/tdd/test_issue_511_weekly_scheduler.py` (2),
`tests/unit/test_secret_output_gate_werkzeugname.py` (1).

Die vier im Issue genannten Tests: `test_issue_937_staging_rolling_trip.py` ist inzwischen per
`pytestmark = pytest.mark.staging` aus dem Kern (#2240). Die anderen drei existieren noch, ihr Offline-Verhalten
mit `--allow-hosts` ist ungemessen.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/broad_test_run_gate.py` | Gate: `_SAFE_FLAGS` enthält `--disable-socket` (Z. 66-71), Roh-Scan-Fallback (Z. 289), Hinweistext (Z. 263) |
| `tests/tdd/test_broad_test_run_gate_pytest_word_position.py` | bestehende Gate-Tests |
| `docs/reference/gates_und_ratschen.md` (Z. 202, 227) | dokumentiert `--disable-socket` als Freigabe |
| `.github/workflows/ci.yml` (Z. 59-66) | CI läuft bereits mit `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost` |
| `pyproject.toml` (Z. 65) | `addopts = "-q -m 'not email and not live and not staging'"` |
| `tests/conftest.py` (Z. 540-600) | `_egress_guard`-Autouse-Fixture (#1337) |
| `src/app/egress_guard.py` | Inventar; `_LOCALHOST_HOSTS = {"localhost","127.0.0.1"}` immer erlaubt; patcht nur httpx/smtplib/imaplib; `gateway.seven.io` und `api.telegram.org` sind `TEST_ACCESS` |
| `tests/tdd/test_issue_1014_live_optin.py`, `tests/tdd/test_trip_report_test_send_past_stage_clamp.py` | im Issue als echt netzabhängig benannt |
| `.github/ci_tdd_excludes.txt` | Ratsche offline-roter tdd-Dateien (aktuell 1 Eintrag) |
| `.venv/.../pytest_socket/__init__.py` | Plugin 0.8.0: `--allow-hosts` filtert nur nach Host/IP, **nicht nach Port**; Marker `allow_hosts` je Test möglich |

## Existing Patterns
- Viele Testdateien dokumentieren bereits ihren eigenen Offline-Aufruf, uneinheitlich:
  `--disable-socket`, `--allow-unix-socket`, `--allow-hosts=127.0.0.1`, `--allow-hosts=127.0.0.1,::1,localhost`.
- CI hat die Kombination `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost` als Standard.
- Lokale Test-Doubles als echte HTTP-Server auf zufälligem Port (Test-Politik: kein Mock-Theater).
- Echt netzabhängige Tests gehören per Marker `live`/`staging`/`email` aus dem Kern (addopts deselektiert sie).

## Dependencies
- Upstream: pytest-socket 0.8.0, `addopts`-Marker-Filter, Egress-Wächter.
- Downstream: das Breitlauf-Gate (#1477), alle Agenten, die einen Volllauf brauchen (Validator, `/60-validate`),
  CI-Testjob (unverändert, falls nur Gate/Doku/Lokal-Konfiguration angepasst wird).

## Existing Specs
- `docs/specs/modules/egress_guard.md` (+ `_go`, `_sms`, `_telegram`)
- `docs/specs/modules/fix_1478_teil1_gate_fehlalarme.md` (frühere Gate-Fehlalarme)

## Risks & Considerations
1. **Prod und Staging lauschen auf demselben Rechner auf Loopback** (8000/8001 Python-Core, 8090/8091 Go-API,
   3000/3001 Frontend, 3457 Claude-MQ, 5678 n8n u. a.). `--allow-hosts=127.0.0.1` lässt jeden Test diese
   Dienste erreichen; pytest-socket kann nicht nach Port filtern, und der Egress-Wächter erlaubt Loopback pauschal.
   Auf dem GitHub-Rechner (CI) ist das harmlos, hier nicht. Die im Issue geforderte Gegenprobe (externe Adresse
   bleibt gesperrt) deckt dieses Loch nicht ab. Ein Test, der z. B. `GZ_API_BASE`/`localhost:8090` ungemarkert
   anspricht, würde unter dem neuen Standard Produktion erreichen (Beispiele mit festen Ports:
   `test_issue_695_test_briefing_send.py`, `test_issue_1148_prod_send_gate.py`, `test_staging_messlauf.py`).
   Die Lösung muss das ausschließen (z. B. Loopback-Verbindungen nur zu Ports, die der Testprozess selbst
   gebunden hat, oder Sperrliste der bekannten Dienst-Ports) und es per Gegenprobe belegen.
2. **Ein Wächter, der nichts mehr fängt** (Issue-Gegenprobe): echter Ausgang zu externen Hosts muss rot bleiben.
3. **Laufzeit ~42-44 min** für den Volllauf: unabhängig vom Fix, relevant für die Nutzbarkeit.
4. Gate-Code = hohes Risiko → Adversary mindestens 2 Runden.
5. Die Nicht-Socket-Roten sind evtl. eigene Befunde (Nebenbefund-Triage #1199), nicht Teil dieses Fixes.

## Analysis

### Type
Bug (Werkzeug/Gate: dokumentierter sicherer Volllauf unbenutzbar und, in der naheliegenden Reparaturform, unsicher)

### Ursachen (korrigiert)
- ~500 der 1.391 Fehlerzeilen: asyncio-Self-Pipe (`socketpair`, AF_UNIX) wird gesperrt (`_ssock`-Fehler). `--allow-unix-socket` behebt das.
- ~880 Rest-Fehler: Tests starten lokale AF_INET-Stub-Server (HTTPServer o. ä. auf `127.0.0.1:0`). Unter `--disable-socket` ohne `--allow-hosts` ist schon das Erzeugen eines AF_INET-Sockets gesperrt.
- Nicht Ursache: Starlettes `TestClient` arbeitet im Prozess ohne TCP (Vermutung des Plan-Agenten verworfen).

### Sicherheitsbefund (heute schon akut, unabhängig von `--allow-hosts`)
Ungemarkerte Kern-Tests, die echte Dienste auf diesem Rechner ansprechen. Sie laufen heute in jedem Lauf mit benannter Datei OHNE Socket-Sperre gegen Produktion:

| Datei | Ziel | Weg |
|---|---|---|
| `tests/tdd/test_bug707_trip_datum_overwrite.py` | `GZ_API_BASE` Default `localhost:8090` (Prod-Go-API), Login per `GZ_SESSION_SECRET` | httpx im Testprozess |
| `tests/tdd/test_bug717_waypointspanel_spread_fix.py` | dto. | httpx im Testprozess |
| `tests/tdd/test_design_optimierungen.py` | `curl` register/login auf `127.0.0.1:8090`, Playwright auf `:3000` | **Kindprozess** (curl), kein Python-Wächter greift |

Geprüft und unkritisch (nur Strings, Env-Override oder gefakte `httpx.post`-Grenze): `test_go_internal_helper.py`, `test_issue_1148_prod_send_gate.py`, `test_telegram_chat_id_ownership.py`, `test_pii_log_maskierung_kanaele.py`, `test_egress_guard.py`. `test_staging_messlauf.py` nennt 8091/8001 als Konstanten; im Phase-6-Lauf beobachten. Alle übrigen Fundstellen sind markiert (`live`/`staging`).

### Varianten
| | A Port-Tracking (Loopback nur zu selbst gebundenen Ports) | B1 feste Port-Sperrliste | B2 `/proc/net/tcp`-Snapshot bei Session-Start | C nackte CI-Form `--allow-hosts=127.0.0.1,::1,localhost` |
|---|---|---|---|---|
| schließt Prod-Loch (Testprozess) | ja, Allow-Liste | nur bekannte Ports | ja, für beim Start lauschende | **nein** (bug707/717 träfen Prod) |
| Fragilität | mittel (Hook-Reihenfolge zu pytest-socket) | hoch | mittel (Linux-only, Race) | – |
| Aufwand | ~120 LoC + Tests | ~30 | ~60 | ~20 |
| Kindprozess-Server/-Clients | nicht erfasst | nicht erfasst | nicht erfasst | nicht erfasst |

### Technical Approach (Entscheidung: Variante A)
1. **Neues pytest-Plugin** `tests/_loopback_port_guard.py` (über `tests/conftest.py` geladen), aktiv nur mit eigener Option `--loopback-own-ports`:
   - Bind-Tracking ab `pytest_configure` (`socket.socket.bind`, bei Port 0 per `getsockname()`), damit Session-/Modul-Fixtures und Server in Threads erfasst werden.
   - Wickelt den von pytest-socket je Test gesetzten `connect` UND `connect_ex` (pytest-socket lässt `connect_ex` offen) nach dessen Setup (`trylast`) ein: Loopback (`127.0.0.0/8`, `::1`, `localhost`) nur zu Ports aus dem Bind-Set, sonst `SocketConnectBlockedError`; Nicht-Loopback geht weiter an pytest-socket (bleibt gesperrt).
   - Die Option verlangt `--disable-socket` und `--allow-hosts` ⊆ {127.0.0.1, ::1, localhost}, sonst Abbruch mit Fehlermeldung.
   - B2 (Snapshot) wird nicht umgesetzt: A ist eine Allow-Liste und schließt den Fall ab. Einen Kindprozess-Server, den der Testprozess per TCP anspricht, gibt es im Kern nicht (`test_core_bind_guard.py` startet uvicorn im Kindprozess, verbindet aber nicht per TCP). Keine Registrier-API nötig.
2. **Gate** `.claude/hooks/broad_test_run_gate.py`: bloßes `--disable-socket` aus `_SAFE_FLAGS` entfernen. Neue Positivprüfung: erlaubt nur `--disable-socket` + `--allow-unix-socket` (optional) + `--allow-hosts` nur Loopback + `--loopback-own-ports`. Abgelehnt: `--force-enable-socket`, `-p no:…`, CIDR/fremde Hosts, `-o addopts`/`-c`/`--override-ini`. Der Roh-Scan-Fallback (Z. 289) bekommt dieselbe Regel. Hinweistext Z. 263 und Docstring Z. 35 nennen den neuen Aufruf.
3. **Marker** für die 3 Dateien oben: `pytestmark = pytest.mark.staging` (bug707/717, brauchen die Go-API) bzw. `live` (design_optimierungen, Playwright gegen laufendes Frontend). Damit sind sie im Kern deselektiert, auch bei Läufen mit benannter Datei.
4. **Die im Issue genannten Tests** (`test_issue_1014_live_optin.py`, `test_trip_report_test_send_past_stage_clamp.py::TestAC3…`) nicht nach der August-Liste markieren. AC: unter der neuen Form grün, oder Marker mit Begründung. Messung in Phase 6 mit benannten Dateien.
5. **Doku**: `docs/reference/gates_und_ratschen.md` Z. 202/227 auf den neuen Aufruf. CI (`ci.yml`) bleibt unverändert (GitHub-Runner ohne Prod-Dienste).

### Affected Files
| File | Change Type | Description |
|---|---|---|
| `tests/_loopback_port_guard.py` | CREATE | Plugin: Option, Bind-Tracking, connect/connect_ex-Wächter |
| `tests/conftest.py` | MODIFY | Plugin laden (`pytest_plugins`) |
| `.claude/hooks/broad_test_run_gate.py` | MODIFY | Positivprüfung neue Form, `--disable-socket` allein nicht mehr sicher, Roh-Fallback, Hinweistext |
| `tests/tdd/test_loopback_port_guard_*.py` | CREATE | `pytester`-Läufe mit pytest-socket + Plugin zusammen |
| `tests/tdd/test_broad_test_run_gate_offline_form.py` | CREATE | Gate-Tests über `main()` |
| `tests/tdd/test_bug707_trip_datum_overwrite.py`, `test_bug717_waypointspanel_spread_fix.py`, `test_design_optimierungen.py` | MODIFY | Marker (je 1–2 Zeilen) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | neuer Aufruf |

### Scope Assessment
- Files: ~9
- Estimated LoC: +400/-10 (davon ~250 Tests)
- Risk Level: HIGH (Gate-Code + Sicherheitswächter), Adversary mindestens 2 Runden

### Testplan / Gegenproben (für die Spec)
- Nachweis dort, wo die Zusicherung wirkt: `pytester`-Lauf mit pytest-socket UND Plugin in derselben Sitzung (nicht nur Unit-Test der Wächterfunktion), weil pytest-socket `connect` je Test neu setzt.
- Externe Adresse (TEST-NET-1 `203.0.113.5`) rot. Loopback-Port, den der Testprozess nicht gebunden hat (Listener von außen simuliert), rot, auch via `connect_ex`, `::1`, `localhost`. Eigener Stub auf Port 0 grün, Session-Fixture-Server grün.
- Gate: neue Form erlaubt; `--disable-socket` allein, `--allow-hosts=0.0.0.0/0`, `--allow-hosts=8.8.8.8`, `--force-enable-socket`, `-p no:socket`, `-o addopts=`, Roh-Fallback `sh -c` jeweils blockiert.
- Phase 6: Volllauf mit neuer Form. Ziel: nur echte Rote (Kandidaten `test_inbound_golden.py`, `test_issue_511_weekly_scheduler.py`, `test_secret_output_gate_werkzeugname.py` → Nebenbefund-Triage #1199, nicht Teil des Fixes).

### Known Limitations
- Ausgang aus Kindprozessen (curl, Go-Binary, Playwright-Browser) ist nicht abgedeckt, weder von pytest-socket noch vom neuen Wächter. Das ist heute schon so, keine Verschlechterung; deshalb zusätzlich Schritt 3 (Marker). Die Spec darf „sicher“ nur mit diesem Vorbehalt behaupten.
- Laufzeit ~42 min bleibt.

### Open Questions
- keine an den PO (alle Entscheidungen sind technisch)
