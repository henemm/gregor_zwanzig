---
entity_id: fix_1755_offline_volllauf
type: module
created: 2026-11-08
updated: 2026-11-08
status: draft
version: "1.0"
tags: [testing, gate, pytest-socket, sicherheit, issue-1755]
---

# Sicherer Offline-Volllauf (Loopback nur zu selbst gebundenen Ports)

## Approval

- [ ] Approved

## Purpose

Der dokumentierte Weg zu einem sicheren vollen Testlauf (`uv run pytest --disable-socket`, im `broad_test_run_gate` freigegeben) ist unbenutzbar: pytest-socket sperrt auch lokale Test-Doubles (Messung 2026-11-08: 1391 Fehlerzeilen, davon 1228x `SocketBlockedError`). Die naheliegende Reparatur (`--allow-hosts=127.0.0.1`) wäre auf diesem Rechner unsicher, weil Prod und Staging auf Loopback lauschen und pytest-socket nicht nach Port filtert. Diese Spec führt einen Offline-Volllauf ein, der Loopback-Verbindungen nur zu Ports erlaubt, die der Testprozess selbst gebunden hat, und jeden echten Ausgang weiterhin sperrt.

## Source

- **File:** `tests/_loopback_port_guard.py` (neu), `.claude/hooks/broad_test_run_gate.py`
- **Identifier:** pytest-Plugin mit Option `--loopback-own-ports`; Gate-Funktion(en) für die Freigabe der Offline-Form (`_SAFE_FLAGS`-Prüfung, Roh-Scan-Fallback)

Schicht: reines Test-/Gate-Werkzeug (Python, `tests/` und `.claude/hooks/`). Weder Frontend noch Go-API noch Python-Core-Produktivcode sind betroffen.

> **Querschnitts-Prüfpunkte:** Trip/Ortsvergleich-Teilung: nicht betroffen (kein Editor-/UI-Baustein). Mandantentrennung: nicht betroffen (keine Nutzerdaten bewegt). Kanäle: nicht betroffen (kein Briefing-/Alarm-Inhalt).

## Scope

**Im Scope:**
- Neues pytest-Plugin `tests/_loopback_port_guard.py` (Option `--loopback-own-ports`), geladen über `tests/conftest.py`
- Breitlauf-Gate `.claude/hooks/broad_test_run_gate.py`: neue Positivprüfung der Offline-Form, `--disable-socket` allein nicht mehr frei, Roh-Scan-Fallback, Hinweistext
- Marker `staging`/`live` für die drei Prod-ansprechenden Testdateien (`test_bug707_…`, `test_bug717_…`, `test_design_optimierungen.py`)
- Messung und ggf. begründeter Marker für die zwei im Issue genannten Tests
- Doku `docs/reference/gates_und_ratschen.md` auf den neuen Aufruf

**Außerhalb des Scopes:**
- CI (`.github/workflows/ci.yml`) bleibt unverändert
- Ausgang aus Kindprozessen (curl, Go, Playwright)
- Reparatur der Nicht-Socket-Roten (gehen in die Nebenbefund-Triage #1199)
- Laufzeit-Optimierung des Volllaufs

## Estimated Scope

- **LoC:** ca. +400/-10 (davon ca. 250 Tests)
- **Files:** ca. 9
- **Effort:** high (Gate-Code und Sicherheitswächter; Adversary mindestens 2 Runden)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| pytest-socket 0.8.0 | Fremdplugin | `--disable-socket`, `--allow-hosts`, setzt `socket.connect` je Test neu; filtert nur nach Host, nicht nach Port |
| `tests/conftest.py` | Modul | lädt das neue Plugin über `pytest_plugins` |
| `.claude/hooks/broad_test_run_gate.py` | Hook | Breitlauf-Gate (#1477), `_SAFE_FLAGS`, Roh-Scan-Fallback, Hinweistext |
| `src/app/egress_guard.py` / `_egress_guard`-Fixture | Modul | bestehender Wächter (#1337), erlaubt Loopback pauschal; bleibt unverändert |
| `pyproject.toml` `addopts` | Konfiguration | deselektiert `email`/`live`/`staging` |
| `.github/workflows/ci.yml` | CI | läuft bereits mit `--allow-hosts=127.0.0.1,::1,localhost`; **bleibt unverändert** (siehe Implementation Details 6) |

## Implementation Details

Entscheidung: Variante A (Port-Tracking). B1 (feste Port-Sperrliste) ist fragil und nur für bekannte Ports wirksam; B2 (`/proc/net/tcp`-Snapshot) ist Linux-only und race-anfällig; C (nackte CI-Form) ließe `bug707`/`bug717` Produktion erreichen. A ist eine Allow-Liste und schließt den Fall im Testprozess ab.

1. **Plugin `tests/_loopback_port_guard.py`**, über `tests/conftest.py` geladen, nur aktiv mit der Option `--loopback-own-ports`:
   - Bind-Tracking ab `pytest_configure`: `socket.socket.bind` wird umhüllt; bei Port 0 wird der tatsächliche Port per `getsockname()` nach dem Bind ins Bind-Set aufgenommen. So werden auch Session-/Modul-Fixtures und Server in Threads erfasst.
   - Nach dem Setup von pytest-socket je Test (`trylast`-Hook) werden `connect` UND `connect_ex` umhüllt (pytest-socket lässt `connect_ex` offen). Loopback-Ziele (`127.0.0.0/8`, `::1`, `localhost`) sind nur zu Ports aus dem Bind-Set erlaubt, sonst `SocketConnectBlockedError`. Nicht-Loopback-Ziele gehen unverändert an pytest-socket und bleiben gesperrt.
   - Startprüfung: Die Option verlangt `--disable-socket` und `--allow-hosts` ⊆ {`127.0.0.1`, `::1`, `localhost`}; andernfalls Abbruch mit Fehlermeldung (`pytest.UsageError`).
2. **Gate `.claude/hooks/broad_test_run_gate.py`:** bloßes `--disable-socket` wird aus `_SAFE_FLAGS` entfernt. Neue Positivprüfung: freigegeben nur `--disable-socket` + (optional) `--allow-unix-socket` + `--allow-hosts` nur Loopback + `--loopback-own-ports`. Abgelehnt: `--disable-socket` allein, `--force-enable-socket`, `-p no:socket` (und andere `-p no:…`), CIDR/fremde Hosts in `--allow-hosts`, `-o addopts=…`/`-c`/`--override-ini`. Der Roh-Scan-Fallback (`sh -c …`) bekommt dieselbe Regel. Hinweistext und Modul-Docstring nennen den neuen Aufruf.
3. **Marker für Prod-ansprechende Kern-Tests** (heute schon ein Sicherheitsproblem, unabhängig vom Lauf): `tests/tdd/test_bug707_trip_datum_overwrite.py` und `tests/tdd/test_bug717_waypointspanel_spread_fix.py` erhalten `pytestmark = pytest.mark.staging` (brauchen die Go-API auf `localhost:8090`), `tests/tdd/test_design_optimierungen.py` erhält `pytestmark = pytest.mark.live` (curl und Playwright gegen laufende Dienste). Damit sind sie im Kern auch bei benannter Datei deselektiert.
4. **Die im Issue genannten Tests** `test_issue_1014_live_optin.py` und `test_trip_report_test_send_past_stage_clamp.py::TestAC3…` werden nicht pauschal nach der August-Liste markiert, sondern in Phase 6 mit benannten Dateien unter der neuen Form gemessen: grün, oder Marker mit schriftlicher Begründung.
5. **Doku:** `docs/reference/gates_und_ratschen.md` (bisher `--disable-socket` als Freigabe) nennt den neuen Aufruf:
   `uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/`
6. **CI unverändert:** Der GitHub-Runner hat keine Prod-/Staging-Dienste auf Loopback, die Gefahr aus Risiko 1 besteht dort nicht. Ein Wechsel auf `--loopback-own-ports` brächte nur Risiko für die 6 Pflicht-Checks ohne Sicherheitsgewinn.

## Expected Behavior

- **Input:** ein pytest-Lauf mit `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports`; sowie Gate-Aufrufe (`main()` des Hooks) mit verschiedenen Kommandozeilen.
- **Output:** Verbindungen zu selbst gebundenen Loopback-Ports gelingen; Verbindungen zu fremden Loopback-Ports und zu externen Adressen schlagen mit `SocketConnectBlockedError` fehl. Das Gate gibt nur die neue Form frei.
- **Side effects:** keine Änderung am Produktivcode, an CI oder an Nutzerdaten. Drei Testdateien verlassen den Kern-Lauf (Marker).

## Acceptance Criteria

- **AC-1:** Given ein Testprozess mit pytest-socket (`--disable-socket --allow-hosts=127.0.0.1,::1,localhost`) und dem Plugin mit `--loopback-own-ports`, und ein Test startet selbst einen HTTP-Stub-Server auf Port 0 (einmal im Test, einmal als Session-Fixture bzw. in einem Thread) / When der Test oder ein Folgetest per `connect` darauf zugreift / Then gelingt die Verbindung und die Antwort des Stubs kommt an, ohne `SocketBlockedError`.
  - Test: `pytester`-Lauf in einer Sitzung mit pytest-socket UND Plugin (nicht nur Unit-Test der Wächterfunktion); beobachtet wird der echte HTTP-Roundtrip zum Stub, auch zu einem Port, der in einer Session-Fixture gebunden wurde.

- **AC-2:** Given derselbe Lauf, und auf dem Loopback lauscht ein Listener, den der Testprozess nicht gebunden hat (z. B. von außen als eigener Prozess gestartet, simuliert Prod auf 8090) / When ein Test per `socket.connect`, per `socket.connect_ex`, zu `127.0.0.1`, zu `::1` und zu `localhost` darauf zugreift / Then wird jede dieser Verbindungen mit `SocketConnectBlockedError` abgelehnt und der Listener sieht keine Verbindung.
  - Test: `pytester`-Lauf mit pytest-socket und Plugin; der fremde Listener zählt eingehende Verbindungen, erwartet wird 0 bei allen vier Zielformen und beiden Aufrufarten (`connect` und `connect_ex`).

- **AC-3:** Given derselbe Lauf / When ein Test eine externe Adresse (TEST-NET-1 `203.0.113.5`) per `connect` oder `connect_ex` anspricht / Then bleibt sie blockiert (Gegenprobe aus dem Issue: der Wächter fängt echten Ausgang weiterhin).
  - Test: `pytester`-Lauf mit pytest-socket und Plugin; erwartet `SocketConnectBlockedError` für `203.0.113.5` in beiden Aufrufarten.

- **AC-4:** Given ein pytest-Aufruf mit `--loopback-own-ports` / When `--disable-socket` fehlt, oder `--allow-hosts` einen Nicht-Loopback-Eintrag enthält (z. B. `8.8.8.8` oder `0.0.0.0/0`) / Then bricht pytest beim Start mit einer verständlichen Fehlermeldung ab (Exit-Code ≠ 0, kein Test läuft); mit gültiger Kombination startet der Lauf normal.
  - Test: `pytester`-Läufe mit den ungültigen Kombinationen (Exit-Code und Fehlertext prüfen) und einer gültigen Kombination (Lauf startet).

- **AC-5:** Given das Breitlauf-Gate `broad_test_run_gate.py` / When `main()` mit verschiedenen Kommandozeilen aufgerufen wird / Then wird die neue Form (`--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports`) freigegeben, und blockiert werden: `--disable-socket` allein, `--allow-hosts=0.0.0.0/0`, `--allow-hosts=8.8.8.8`, `--force-enable-socket`, `-p no:socket`, `-o addopts=`, `-c <datei>`, `--override-ini`, sowie der Roh-Fallback `sh -c "uv run pytest …"` mit unsicherer Form; die Blockmeldung nennt den neuen Aufruf.
  - Test: Aufruf von `main()` des Hooks mit Hook-Eingabe (stdin-JSON) je Kommandozeile; geprüft werden Exit-Code und Ausgabetext (inklusive Hinweistext mit dem neuen Aufruf, der damit zugleich den dokumentierten Aufruf in der Doku absichert). Kein Dateiinhalt-Check.

- **AC-6:** Given die drei Testdateien, die Prod-Dienste ansprechen (`test_bug707_trip_datum_overwrite.py`, `test_bug717_waypointspanel_spread_fix.py`, `test_design_optimierungen.py`) / When der Kern-Lauf mit der Standardkonfiguration (`addopts`) und diesen Dateien benannt gestartet wird / Then werden alle Tests dieser Dateien deselektiert und keiner läuft.
  - Test: `pytest --collect-only` bzw. Lauf mit den drei Dateien als Argumente; erwartet 0 ausgewählte, alle deselektiert (Marker `staging` bzw. `live`).

- **AC-7:** Given ein Volllauf mit der neuen Form auf `origin/main` plus diesem Fix (Messung in Phase 6) / When der Lauf beendet ist / Then enthält er keine `SocketBlockedError`-Fehlalarme für selbst gebundene Ports mehr (Vorher: 878 bis 1228 Zeilen); jedes verbleibende Rot ist ein echter Befund und wird in die Nebenbefund-Triage (#1199) gegeben, nicht in diesem Fix repariert. Die im Issue genannten Tests `test_issue_1014_live_optin.py` und `test_trip_report_test_send_past_stage_clamp.py::TestAC3…` sind unter der neuen Form grün, oder tragen einen Marker mit schriftlicher Begründung.
  - Test: Volllauf `uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/` (ca. 42 min), Ergebnis nach Fehlerklassen ausgewertet (0x `SocketBlockedError` bei Zugriffen auf selbst gebundene Ports; Restliste mit Zuordnung), plus benannte Läufe der zwei Issue-Tests. Kandidaten für echte Rote (Triage, nicht Teil des Fixes): `test_inbound_golden.py`, `test_issue_511_weekly_scheduler.py`, `test_secret_output_gate_werkzeugname.py`.

## Test Plan

| AC | Testart | Datei (geplant) | Nachweis |
|---|---|---|---|
| AC-1 bis AC-4 | `pytester`-Läufe mit pytest-socket UND Plugin in derselben Sitzung | `tests/tdd/test_loopback_port_guard_offline_lauf.py` | echter Stub-Roundtrip grün; fremder Listener zählt 0 Verbindungen; `203.0.113.5` blockiert; ungültige Optionskombinationen brechen ab |
| AC-5 | Aufruf von `main()` des Hooks mit stdin-JSON | `tests/tdd/test_broad_test_run_gate_offline_form.py` | Exit-Code und Meldungstext je Kommandozeile |
| AC-6 | `pytest --collect-only` mit den drei Dateien benannt | in `test_loopback_port_guard_offline_lauf.py` oder eigener Datei | 0 ausgewählt, alle deselektiert |
| AC-7 | Volllauf mit der neuen Form (Phase 6) plus benannte Läufe der zwei Issue-Tests | – (Messlauf) | Auswertung nach Fehlerklassen, Restliste mit Zuordnung zu #1199 |

Gegenproben (Mutation, Phase 5/6): Wächter für `connect_ex` entfernen ⇒ AC-2 rot; Bind-Tracking für Port 0 entfernen ⇒ AC-1 rot; Gate-Regel für `--loopback-own-ports` entfernen ⇒ AC-5 rot. Adversary mindestens 2 Runden (Gate-Code).

## Definition of Done

- AC-1 bis AC-6 durch automatische Tests belegt, die Kern-Schicht ist grün
- AC-7 durch einen Volllauf mit der neuen Form belegt; Ergebnis im Issue #1755 dokumentiert, Rest-Rote in #1199 eingetragen
- Gegenprobe aus dem Issue erbracht: externe Adresse bleibt gesperrt (AC-3), fremder Loopback-Port bleibt gesperrt (AC-2)
- Doku `docs/reference/gates_und_ratschen.md` nennt den neuen Aufruf
- Adversary-Verdict VERIFIED, alle 6 CI-Checks grün, PR gemergt

## Known Limitations

- **UDP `sendto`/`sendmsg` ist nicht abgedichtet:** verbindungslose Sendungen laufen wie bei pytest-socket selbst (das nur `connect` sperrt) am Wächter vorbei. Bewusst nicht Teil dieses Fixes (Adversary-Befund F002, LOW).
- **Kindprozess-Ausgang ist nicht abgedeckt:** `curl`, Go-Binaries und Playwright-Browser aus Tests heraus unterliegen weder pytest-socket noch dem neuen Wächter. Das war schon vorher so (keine Verschlechterung); deshalb zusätzlich der Marker-Schritt für die drei Dateien. „Sicher“ gilt nur mit diesem Vorbehalt und nur für Verbindungen aus dem Testprozess.
- **Laufzeit ca. 42 min** bleibt; der Fix macht den Lauf nutzbar, nicht schneller.
- **Nicht-Socket-Rote sind außerhalb des Scopes** (z. B. `test_inbound_golden.py`, `test_issue_511_weekly_scheduler.py`, `test_secret_output_gate_werkzeugname.py`); sie gehen in die Nebenbefund-Triage #1199.
- Ein Kindprozess-Server, den der Testprozess per TCP anspricht, würde vom Bind-Tracking nicht erfasst und blockiert; im Kern gibt es das heute nicht (`test_core_bind_guard.py` verbindet nicht per TCP). Eine Registrier-API ist bewusst nicht Teil dieser Spec.
- `test_staging_messlauf.py` nennt Staging-Ports als Konstanten; im Phase-6-Lauf beobachten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Berührt ist allenfalls ADR-0094 (zwei Test-Schichten: deterministischer Kern ohne Netz plus Live-E2E). Diese Spec setzt die dort getroffene Entscheidung nur durch (Werkzeug und Gate, die „ohne Netz“ tatsächlich lauffähig und sicher machen) und ändert weder Test-Strategie noch Deploy-Strategie. Der Mock-Theater-Verbot bleibt unberührt (echte Stub-Server, kein Mocking). Die Variantenwahl A ist eine Implementierungsentscheidung innerhalb dieser Spec.

## Changelog

- 2026-11-08: Initial spec created (Issue #1755, Variante A: Port-Tracking)
- 2026-11-08 (Phase 6, Umsetzungs-Nachtrag zu Implementation Details 1): Statt `connect`/`connect_ex` je Test per `trylast`-Hook zu umhüllen, ersetzt das Plugin ab `pytest_configure` dauerhaft `pytest_socket._true_connect` (die Funktion, die pytest-socket nach seiner Host-Prüfung aufruft und beim Aufräumen zurücksetzt) durch die Port-Prüfung; `connect_ex` wird einmal auf Klassenebene umhüllt und lehnt Nicht-Loopback selbst ab. Grund: pytest baut Fixtures innerhalb seines eigenen `pytest_runtest_setup` auf, ein `trylast`-Hook griffe erst danach, Verbindungen aus dem Fixture-Setup kämen zum fremden Port durch (AC-2-Test prüft genau das).
- 2026-11-08 (Fix-Loop 1): Gate prüft jedes Argument der Offline-Form per Positivliste `[\w./:=,@+-]+` und lehnt Backtick/`$(` im Kommando ab (F001: `--ignore=x;pytest` startete ein nacktes pytest). UDP `sendto`/`sendmsg` als bekannte Grenze dokumentiert (F002).
