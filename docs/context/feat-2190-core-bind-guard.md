# Context: feat-2190-core-bind-guard

## Request Summary
Issue #2190 (abgetrennt aus #2142, Epic #2138): Der Python-Core soll nachweislich nur auf
`127.0.0.1` lauschen, und diese Zusicherung soll im Code dieses Repos liegen, nicht allein in der
systemd-Unit im Repo `henemm-infra`. Ziel ist eine zweite Verteidigungslinie zum gemeinsamen
Geheimnis aus #2142 (`X-GZ-Core-Auth`).

Entwurf der Akzeptanz aus dem Issue (noch nicht freigegeben):
- Der Core verweigert den Start, wenn er auf eine andere Adresse als `127.0.0.1` gebunden würde.
- Die Zusicherung liegt im Code dieses Repos.
- `frontend/e2e/ci-stack.sh` startet weiterhin unverändert durch.

## Related Files
| File | Relevance |
|------|-----------|
| `api/main.py:91-101` (`lifespan`) | Einzige Stelle, die beim echten Prozessstart läuft (Egress-Guard, Telegram-Menü). Kandidat für einen Guard per Introspektion. Läuft unter `TestClient(app)` ohne `with` NICHT. |
| `api/main.py:104` | `app = FastAPI(...)` — Ziel aller Startpfade (`api.main:app`). |
| `api/main.py:131-188` | Core-Auth-Middleware aus #2142 (erste Verteidigungslinie, Muster für fail-closed). |
| `/home/hem/henemm-infra/systemd/gregor-python.service` | Prod: `uv run --no-sync uvicorn api.main:app --host 127.0.0.1 --port 8000`, User `claude-gregor`, WorkingDirectory `/home/hem/gregor_zwanzig`. Identisch mit `/etc/systemd/system/gregor-python.service` (root-owned, manuell installiert). |
| `/home/hem/henemm-infra/systemd/gregor-python-staging.service` | Staging: gleiche Form, Port 8001, WorkingDirectory `/home/hem/gregor_zwanzig_staging`. |
| `frontend/e2e/ci-stack.sh:59` | CI-Stack startet `uv run uvicorn api.main:app --host 127.0.0.1 --port "$PY_PORT"`; läuft nur im `e2e`-Job (`.github/workflows/ci.yml:383/504`). |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | Stoppt `gregor-python` vor dem Sync, `uv sync`, startet neu. Fasst Units NICHT an. |
| `/home/hem/henemm-infra/scripts/auto-deploy-gregor-staging.sh:294` | `sudo systemctl restart gregor-python-staging`. Fasst Units NICHT an. |
| `AGENTS.md:227`, `docs/specs/modules/go_proxy_binary.md:170` | Doku-Startbefehle `uvicorn api.main:app --host 127.0.0.1 --port 8000` (lokale Entwicklung). |

## Existing Patterns
- **Go-Vorbild (Issue #116, `docs/specs/bugfix/go_api_bind_localhost.md`):** Bind-Host über
  `GZ_HOST`, Default `127.0.0.1`, im Code des Repos festgelegt.
- **Fail-closed-Muster aus #2142:** fehlt die Voraussetzung, verweigert der Core (503) statt
  durchzulassen. Für den Bind-Guard analog: Startabbruch statt Warnung.
- **Lifespan-Hooks** (`install_egress_guard`) als Startpfad-Prüfung im echten Prozess.
- **Vorarbeit #2142** (`docs/context/fix-2142-core-auth-shared-secret.md`, R6/A7, Z.222): Die App kann
  ihre Bind-Adresse von innen auf drei Wegen erkennen (`sys.argv`, `gc`-Introspektion des
  uvicorn-`Server`-Objekts, `/proc/self/fd`). Nicht gemessen: `--reload`, Multi-Worker, IPv6.
  Empfehlung dort: saubere Bauform = repo-eigener Einstiegspunkt.

## Dependencies
- Upstream: uvicorn (CLI bzw. `uvicorn.run`/`uvicorn.Config`), FastAPI-Lifespan, `uv run`.
- Downstream: systemd-Units Prod/Staging (henemm-infra), `ci-stack.sh` (CI-`e2e`-Job), lokale
  Entwickler-Startbefehle in Doku, Go-API (`GZ_PYTHON_CORE_URL=http://localhost:8000`), Deploy-Skripte.

## Existing Specs
- `docs/specs/bugfix/core_shared_secret_auth.md` — Abschnitt „Abgetrennter Umfang" (Ursprung).
- `docs/specs/bugfix/go_api_bind_localhost.md` — strukturgleicher Vorgänger für Go.
- `docs/specs/modules/egress_guard.md` — Lifespan-Startpfad-Muster.
- ADR-0062 (Core-Auth, löst ADR-0015 Regel 2 teilweise ab); ADR-0015 Dual-Stack.

## Risks & Considerations
- **R1 Rollout über zwei Repos:** Wird die Unit auf einen neuen Einstiegspunkt umgestellt, bevor
  der Code deployt ist, crasht der Dienst (Modul fehlt). Reihenfolge: erst Code (abwärtskompatibel,
  alter Startbefehl funktioniert weiter), dann Unit-Umstellung, dann `daemon-reload` + Restart.
- **R2 Unit-Installation braucht root:** `/etc/systemd/system/*.service` ist root-owned und wird von
  keinem Deploy-Skript synchronisiert. Ob `sudo -n` für `cp`/`daemon-reload` verfügbar ist, ist offen
  (in der Analyse prüfen).
- **R3 Guard nur im neuen Einstiegspunkt** schützt nicht gegen jemanden, der weiter
  `uvicorn api.main:app --host 0.0.0.0` startet. Ein Guard im Lifespan (Introspektion) deckt beide
  Startwege ab, ist aber Introspektion eines fremden Objekts. Abwägen in der Analyse.
- **R4 Tests:** `TestClient` bindet nicht; ein Test muss den echten Startpfad (Subprozess oder
  Startfunktion ohne Netz) treffen, ohne Mock-Theater. Ein gebundener Port im Test darf keinen
  Prod-/Staging-Port belegen.
- **R5 IPv6/`localhost`:** Darf `::1` bzw. `localhost` erlaubt sein? Issue sagt strikt `127.0.0.1`.
  Go-Proxy spricht `http://localhost:8000` an — Auflösung auf `127.0.0.1` muss weiter funktionieren.
- **R6 Prod-Ausfall bei Fehlkonfiguration** ist gewollt (fail-closed), muss aber im Journal klar
  benannt sein, sonst sucht man lange (Monitoring meldet nur „python_core down").

## Analysis

### Type
Feature (Härtung, zweite Verteidigungslinie zu #2142).

### Messungen (2026-11-02, uvicorn 0.47.0 laut `uv.lock`, Probe-App mit Lifespan + `gc`-Introspektion)
Prüfung im Lifespan: alle `uvicorn.Config`-Objekte per `gc.get_objects()`, gefiltert auf die Config, deren
`loaded_app`-Kette (`.app`-Attribute der Middleware) auf genau die App zeigt, die der Lifespan bekommt.

| Startweg | Ergebnis | Exit | Socket je gelauscht (`ss -ltn`, 50-ms-Takt) |
|---|---|---|---|
| `--host 127.0.0.1` | startet, Config gefunden `('127.0.0.1', port)` | läuft | ja (gewollt) |
| `--host 0.0.0.0` | Start verweigert („Application startup failed. Exiting.") | 3 | **nein** |
| `--host localhost` | verweigert | 3 | nein |
| `--host ::1` | verweigert | 3 | nein |
| `--host 0.0.0.0 --workers 2` | Kinder scheitern, Master bindet VOR dem App-Start und respawnt | Master lebt | Master hält Socket |
| `--host 0.0.0.0 --reload` | Kind scheitert, Supervisor lebt weiter | Supervisor lebt | Supervisor hält Socket |
| fremde `Config(host="0.0.0.0")` im selben Prozess | ignoriert (Filter auf eigene App greift) | – | – |
| `with TestClient(app)` (kein uvicorn-Server) | keine eigene Config ⇒ Guard nicht anwendbar, Start ok | – | – |

Quellcode-Beleg: `uvicorn/server.py:104-105` `startup()` ruft `await self.lifespan.startup()` **vor**
`loop.create_server(...)` (Z. 144 ff.). Im Einzelprozess wird also vor dem Binden abgebrochen.

### Varianten
| Variante | deckt `uvicorn api.main:app --host X` ab | Infra-Unit-Änderung | Rollout über 2 Repos | Abhängigkeit von uvicorn-Interna |
|---|---|---|---|---|
| A: Guard im Lifespan (gc-Introspektion) | ja | nein | nein | ja (`Config.host`, `loaded_app`) |
| B: eigener Einstiegspunkt `python -m api.serve` (Host fest) | **nein** (alter Startbefehl bleibt möglich, R3) | ja (beide Units) | ja (R1-Reihenfolge) | nein |
| A+B | ja | ja | ja | ja |

### Befunde gegen den Plan (Variante A)
1. **`--workers`/`--reload`:** Der Master bzw. Supervisor bindet den Socket vor dem App-Start; der Guard
   verhindert dort nur, dass je eine Anfrage bearbeitet wird, nicht das Lauschen. Entscheidung: außerhalb
   des Umfangs, weil kein Betriebs-Startweg diese Flags nutzt (geprüft: beide Units, `ci-stack.sh`).
   Abgesichert durch einen Kern-Test, der die Startbefehle in `ci-stack.sh` und — falls lesbar —
   `/home/hem/henemm-infra/systemd/gregor-python*.service` auf `--workers`/`--reload` prüft und das
   Fehlen von `--host 127.0.0.1` meldet (# doc-compliance-test, ergänzend zum Verhaltenstest).
2. **Interna-Abhängigkeit:** Ein uvicorn-Update kann `Config`/`loaded_app` ändern. Gegenmittel:
   (a) uvicorn ist in `uv.lock` auf 0.47.0 gepinnt; (b) Guard ist fail-closed, wenn eine eigene Config
   gefunden wird, aber `host` nicht lesbar ist; (c) der Kern-Test startet echten uvicorn im Subprozess,
   ein Update färbt ihn rot; (d) der CI-`e2e`-Job startet den echten Stack über `ci-stack.sh`
   (`127.0.0.1`), ein kaputter Guard wird vor dem Deploy rot.
3. **Lücke andere ASGI-Server:** Wird keine uvicorn-Config gefunden (TestClient, fremder Server), greift
   der Guard nicht. Begründung: kein anderer ASGI-Server ist installiert (geprüft: kein hypercorn,
   gunicorn, daphne, granian in `.venv`); fail-closed hier würde alle `with TestClient(app)`-Tests brechen.
4. **Prod-Ausfall bei Fehlkonfiguration (R6):** gewollt. Unit hat `Restart=on-failure`, `RestartSec=10`
   ⇒ Crash-Loop alle 10 s, BetterStack meldet Ausfall. Meldung muss im Journal eindeutig sein:
   `logger.critical` mit tatsächlichem Host, Port und „#2190" vor dem Abbruch.

### Entscheidungen (selbst getroffen, Tech-Lead)
- **Variante A**, keine Änderung an `henemm-infra` (R1/R2 entfallen; R2 wäre lösbar: `hem` hat `NOPASSWD: ALL`).
- **Strikt `127.0.0.1`**: `localhost`, `::1`, `0.0.0.0`, `--uds`, `--fd` werden verweigert (Issue-Text;
  alle Betriebs-Startwege nutzen `127.0.0.1`; Go-Proxy erreicht den Core heute schon so).
- **Kein Override per Umgebungsvariable** (wäre selbst die Lücke).
- Guard läuft als **erster** Schritt im Lifespan, vor `install_egress_guard`.
- Prüflogik als reine Funktion (Host/UDS/FD ⇒ erlaubt/verweigert) plus Lookup-Funktion für die Config.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `api/bind_guard.py` | CREATE | Config-Lookup (gc + Filter auf eigene App), Prüfregel, Abbruch mit klarer Meldung |
| `api/main.py` | MODIFY | Lifespan ruft Guard als ersten Schritt |
| `tests/tdd/test_core_bind_guard.py` | CREATE | echter uvicorn-Subprozess auf freiem Port (nie 8000/8001): `0.0.0.0`/`localhost`/`::1` ⇒ Exit ≠ 0, Meldung mit Host + #2190, Port nie gelauscht; `127.0.0.1` ⇒ `/health` antwortet; fremde Config im Prozess wird ignoriert; TestClient-Lifespan läuft durch |
| `tests/tdd/test_core_startbefehle_loopback.py` | CREATE | Startbefehle ohne `--workers`/`--reload`, mit `--host 127.0.0.1` (doc-compliance) |
| `docs/specs/modules/core_bind_guard.md` | CREATE | Spec |
| `docs/specs/bugfix/core_shared_secret_auth.md` | MODIFY | Verweis „Abgetrennter Umfang" ⇒ #2190 erledigt |

### Scope Assessment
- Files: 6 (davon 2 Code, 2 Test, 2 Doku)
- Estimated LoC: +~60 Code / +~120 Tests / -0
- Risk Level: MEDIUM (Prod-Startpfad; ein Fehler im Guard legt den Core lahm — abgefangen durch Subprozess-Test und CI-`e2e`)

### Technical Approach
Lifespan-Guard (Variante A). Beim Start sucht `api/bind_guard.py` die uvicorn-Config, die genau diese App
bedient, prüft `host == "127.0.0.1"` und weder `uds` noch `fd`; sonst `logger.critical(...)` und
`RuntimeError` ⇒ uvicorn beendet mit Exit 3, bevor ein Socket lauscht. Keine eigene Config ⇒ kein
uvicorn-Netzserver ⇒ Guard nicht anwendbar (Debug-Log).

### Dependencies
uvicorn 0.47.0 (Pin), FastAPI-Lifespan. Keine Downstream-Änderung: Units, `ci-stack.sh`, Deploy-Skripte,
Go-API bleiben unverändert.

### Open Questions
- keine (alle Punkte oben selbst entschieden)
