---
entity_id: core_bind_guard
type: feature
created: 2026-11-02
updated: 2026-11-02
status: draft
version: "1.0"
workflow: feat-2190-core-bind-guard
tags: [security, python-core, networking, uvicorn, issue-2190, epic-2138]
---

# Core-Bind-Guard (Python-Core lauscht nur auf 127.0.0.1)

## Approval

- [ ] Approved

## Purpose

Der Python-Core (FastAPI, `api.main:app`) verweigert beim Start jede Bind-Adresse ausser `127.0.0.1`, damit er nie direkt aus dem Netz erreichbar ist. Die Zusicherung liegt im Code dieses Repos und nicht allein in der systemd-Unit im Repo `henemm-infra`; sie ist die zweite Verteidigungslinie neben dem gemeinsamen Geheimnis `X-GZ-Core-Auth` aus #2142.

Bezug: Issue #2190 (abgetrennt aus #2142), Epic #2138, Vorgaenger-Spec `docs/specs/bugfix/core_shared_secret_auth.md` (Abschnitt „Abgetrennter Umfang"), strukturgleiches Go-Vorbild `docs/specs/bugfix/go_api_bind_localhost.md` (#116), Lifespan-Muster `docs/specs/modules/egress_guard.md`.

## Source

- **File:** `api/bind_guard.py` (neu), eingehaengt in `api/main.py` (`lifespan`)
- **Identifier:** Pruefregel, Config-Lookup und Abbruch in `api/bind_guard.py`; Aufruf als erster Schritt von `lifespan` vor `install_egress_guard`

> **Schicht-Hinweis:** Python-Core (`api/`). Keine Aenderung in Frontend, Go-API oder `henemm-infra`.
> **Querschnitts-Pruefpunkte:** Kein Trip/Ortsvergleich-Pendant (reine Startpfad-Pruefung). Keine Nutzerdaten betroffen (keine Mandantentrennung noetig). Kein Briefing-/Alarm-Inhalt, Kanaele nicht betroffen.

## Estimated Scope

- **LoC:** ca. +60 Code, +120 Tests
- **Files:** 6 (2 Code, 2 Tests, 2 Doku)
- **Effort:** medium (Risiko MEDIUM: Prod-Startpfad)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `api/bind_guard.py` | CREATE | Config-Lookup (gc + Filter auf die eigene App), Pruefregel, Abbruch mit klarer Meldung |
| `api/main.py` | MODIFY | `lifespan` ruft den Guard als allerersten Schritt, vor `install_egress_guard` |
| `tests/tdd/test_core_bind_guard.py` | CREATE | Verhaltenstests mit echtem uvicorn-Subprozess auf freiem Port |
| `tests/tdd/test_core_startbefehle_loopback.py` | CREATE | `# doc-compliance-test`: Startbefehle ohne `--workers`/`--reload`, mit `--host 127.0.0.1` |
| `docs/specs/modules/core_bind_guard.md` | CREATE | Diese Spec |
| `docs/specs/bugfix/core_shared_secret_auth.md` | MODIFY | „Abgetrennter Umfang": Verweis auf #2190 / diese Spec |

### Estimated Changes

- Files: 6
- LoC: +~180 / -0

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| uvicorn 0.47.0 (Pin in `uv.lock`) | external | `uvicorn.Config` (`host`, `uds`, `fd`, `loaded_app`) wird per `gc` gefunden; `Server.startup()` ruft den Lifespan vor `create_server` |
| FastAPI-Lifespan (`api/main.py`) | module | einziger Hook, der im echten Prozess vor dem Binden laeuft |
| `install_egress_guard` | module | Reihenfolge: Bind-Guard laeuft davor |
| Core-Auth-Middleware (#2142) | module | erste Verteidigungslinie; Bind-Guard ist die zweite |
| `frontend/e2e/ci-stack.sh` | script | startet `uvicorn api.main:app --host 127.0.0.1`; bleibt unveraendert |
| `gregor-python.service`, `gregor-python-staging.service` (henemm-infra) | systemd | starten mit `--host 127.0.0.1`; bleiben unveraendert |

## Implementation Details

Entscheidung: **Variante A**, Guard im FastAPI-Lifespan per `gc`-Introspektion der uvicorn-Config, die genau diese App bedient.

Ablauf im Lifespan, als erster Schritt vor `install_egress_guard`:

1. Alle `uvicorn.Config`-Objekte per `gc.get_objects()` sammeln und auf die Config filtern, deren `loaded_app`-Kette (`.app`-Attribute der Middleware) auf genau die App zeigt, die der Lifespan bekommt. Fremde Configs im selben Prozess werden ignoriert.
2. Keine eigene Config gefunden (z. B. `with TestClient(app)`): Guard nicht anwendbar, Debug-Log, Start ok.
3. Eigene Config gefunden: erlaubt ist ausschliesslich `host == "127.0.0.1"` ohne `uds` und ohne `fd`. Verweigert werden `localhost`, `::1`, `0.0.0.0`, jede andere Adresse, `--uds`, `--fd`. Ist die eigene Config da, aber `host` nicht lesbar: fail-closed (verweigern).
4. Bei Verweigerung: `logger.critical` mit tatsaechlichem Host, Port und „#2190", danach `RuntimeError`. uvicorn beendet mit Exit 3, bevor ein Socket lauscht (`uvicorn/server.py`: `startup()` ruft `lifespan.startup()` vor `loop.create_server`).

Pruefregel als reine Funktion (Host/UDS/FD ergibt erlaubt/verweigert) plus eigene Lookup-Funktion, damit beides getrennt testbar ist.

Keine Umgebungsvariable und kein Flag zum Aufweichen: ein Override waere selbst die Luecke.

### Messbasis (2026-11-02, uvicorn 0.47.0)

`--host 127.0.0.1` startet; `0.0.0.0`, `localhost`, `::1` brechen mit Exit 3 ab und lauschen nie (`ss -ltn`, 50-ms-Takt); eine fremde `Config(host="0.0.0.0")` im selben Prozess wird ignoriert; `with TestClient(app)` laeuft durch. Details: `docs/context/feat-2190-core-bind-guard.md`.

### Verworfene Variante

- **B: eigener Einstiegspunkt `python -m api.serve`:** deckt den alten Startbefehl `uvicorn api.main:app --host 0.0.0.0` nicht ab, braucht Unit-Umstellung in `henemm-infra` und Rollout ueber zwei Repos mit Crash-Risiko bei falscher Reihenfolge.

### Bewusst ausserhalb des Umfangs

- **`--workers` / `--reload`:** Master bzw. Supervisor binden den Socket vor dem App-Start; der Guard verhindert dort nur, dass je eine Anfrage bearbeitet wird, nicht das Lauschen. Kein Betriebs-Startweg nutzt diese Flags (geprueft: beide Units und `ci-stack.sh`). Abgesichert durch den Doc-Compliance-Test der Startbefehle.
- **Andere ASGI-Server:** keiner installiert (kein hypercorn, gunicorn, daphne, granian in `.venv`). Fail-closed bei fehlender Config wuerde ausserdem alle `with TestClient(app)`-Tests brechen.
- **Eigener Einstiegspunkt (Variante B):** siehe oben.

## Expected Behavior

- **Input:** Start von `api.main:app` mit uvicorn und einer Bind-Adresse.
- **Output:** `127.0.0.1` ergibt normalen Start, `/health` antwortet. Jede andere Adresse (oder UDS/FD) ergibt Exit-Code 3, ohne dass der Port je lauscht.
- **Side effects:** Bei Verweigerung eine `CRITICAL`-Zeile im Journal mit Host, Port und „#2190".

## Test Plan

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_core_bind_guard.py`: GIVEN uvicorn-Subprozess mit `--host 0.0.0.0` (analog `localhost`, `::1`) auf freiem Port (nie 8000/8001) WHEN gestartet THEN Exit ungleich 0, Port wird waehrend der Laufzeit nie gelauscht, Ausgabe nennt den Host und „#2190".
- [ ] GIVEN Subprozess mit `--host 127.0.0.1` WHEN gestartet THEN `GET /health` antwortet.
- [ ] GIVEN im selben Prozess eine fremde `uvicorn.Config(host="0.0.0.0")` WHEN der Lifespan der App laeuft THEN wird sie ignoriert, Start ok.
- [ ] GIVEN `with TestClient(app)` WHEN der Lifespan laeuft THEN kein Abbruch.
- [ ] GIVEN gesetzte Umgebungsvariablen (z. B. `GZ_HOST`, `GZ_ALLOW_ANY_BIND`) WHEN mit `--host 0.0.0.0` gestartet THEN weiterhin Verweigerung.
- [ ] `tests/tdd/test_core_startbefehle_loopback.py` (`# doc-compliance-test`): Startbefehle in `frontend/e2e/ci-stack.sh` und, falls lesbar, `/home/hem/henemm-infra/systemd/gregor-python*.service` enthalten `--host 127.0.0.1` und weder `--workers` noch `--reload`.

Mutations-Gegenprobe (Pflicht, `implementation-validator`): Guard-Aufruf entfernen, Hostvergleich lockern oder Reihenfolge vor `install_egress_guard` aendern muss mindestens einen Test rot machen.

## Acceptance Criteria

- **AC-1:** Given der Core wird mit `--host 0.0.0.0` gestartet / When uvicorn die App startet / Then bricht der Start mit Exit-Code ungleich 0 (uvicorn: 3) ab und der Port lauscht zu keinem Zeitpunkt.
  - Test: Subprozess auf freiem Port, Port-Abfrage im Takt waehrend der Laufzeit, Exit-Code geprueft.

- **AC-2:** Given der Core wird mit `--host localhost` oder `--host ::1` gestartet / When uvicorn die App startet / Then verweigert der Core den Start wie bei `0.0.0.0` (strikt nur `127.0.0.1`, kein Socket, Exit ungleich 0).
  - Test: zwei Subprozess-Laeufe, Exit-Code und nie gelauschter Port.

- **AC-3:** Given ein Betreiber startet den Core mit einer verbotenen Adresse / When der Dienst abbricht / Then nennt die Journal-Meldung (`CRITICAL`) den tatsaechlichen Host, den Port und „#2190", sodass die Ursache ohne Suche erkennbar ist.
  - Test: Ausgabe des Subprozesses enthaelt Host, Port und „#2190".

- **AC-4:** Given der Core wird mit `--host 127.0.0.1` gestartet / When der Dienst hochgefahren ist / Then antwortet `GET /health` und der Egress-Guard wird danach wie bisher installiert.
  - Test: Subprozess auf freiem Port, HTTP-Abfrage von `/health`.

- **AC-5:** Given im selben Prozess existiert eine fremde uvicorn-Config mit `host="0.0.0.0"`, die eine andere App bedient / When der Lifespan von `api.main:app` laeuft / Then wird die fremde Config ignoriert und der Start nicht verweigert.
  - Test: fremde Config im Prozess anlegen, Lifespan der echten App durchlaufen lassen.

- **AC-6:** Given Tests nutzen `with TestClient(app)` ohne uvicorn-Server / When der Lifespan laeuft / Then gilt der Guard als nicht anwendbar und der Start laeuft durch.
  - Test: `with TestClient(app)` und ein Request gegen `/health` ohne Abbruch.

- **AC-7:** Given `frontend/e2e/ci-stack.sh` und die Prod-/Staging-Units starten den Core / When ihre Startbefehle geprueft werden / Then enthalten sie `--host 127.0.0.1` und weder `--workers` noch `--reload`, laufen also unveraendert weiter.
  - Test: Doc-Compliance-Test liest die Startbefehle (Units nur, falls lesbar).

- **AC-8:** Given in der Umgebung sind beliebige Variablen gesetzt (z. B. `GZ_HOST`) / When der Core mit `--host 0.0.0.0` gestartet wird / Then verweigert er den Start trotzdem, weil es keinen Override gibt.
  - Test: Subprozess mit gesetzten Variablen, Exit ungleich 0.

## Known Limitations

- **Abhaengigkeit von uvicorn-Interna** (`Config.host`, `loaded_app`): Gegenmittel sind der Pin 0.47.0 in `uv.lock`, fail-closed bei eigener Config mit nicht lesbarem Host, der Subprozess-Test (ein Update macht ihn rot) und der CI-`e2e`-Job ueber `ci-stack.sh`.
- **`--workers` / `--reload`:** nicht abgedeckt (siehe oben), nur per Startbefehl-Test bewacht.
- **Andere ASGI-Server:** kein Schutz, aber keiner installiert.
- **Prod-Ausfall bei Fehlkonfiguration ist gewollt:** `Restart=on-failure`, `RestartSec=10` ergibt einen Crash-Loop alle 10 s, BetterStack meldet den Ausfall, die `CRITICAL`-Zeile benennt die Ursache.
- Der Go-Proxy erreicht den Core weiter ueber `http://localhost:8000`; das loest auf den Loopback auf und ist vom Bind-Guard unberuehrt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ergaenzt ADR-0062, Core-Auth)
- **Rationale:** Die Entscheidung setzt die Linie von ADR-0062 (Core nur ueber Loopback plus Geheimnis erreichbar) im Code durch; keine Abweichung von bestehenden ADRs, daher kein neues ADR.

## Changelog

- 2026-11-02: Initial spec created (Issue #2190, Epic #2138, Vorgaenger #2142)
