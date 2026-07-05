# Architektur-Analyse Gregor Zwanzig

**Datum:** 2026-07-05 (Revision 2, gegengecheckt)
**Analyst (Rev. 1):** Kimi Code CLI
**Gegencheck & Korrektur (Rev. 2):** Claude (Tech Lead) — jede Kernbehauptung wurde direkt am Code
verifiziert (Zeilen-/Dateizählungen, Import-Greps, `svelte-check`-Lauf, Probeläufe der
ausgeschlossenen Tests, Abgleich mit ADRs und `.claude/`-Gate-System).
**Ziel:** Bewertung der aktuellen Architektur hinsichtlich Wartbarkeit, Abweichungen zur
Dokumentation (Drifts) und Handlungsempfehlungen.

**Legende:** ✓ = in Rev. 2 verifiziert · ✗ = in Rev. 2 korrigiert · ➕ = in Rev. 2 ergänzt

---

## 1. Fazit

Gregor Zwanzig funktioniert produktiv, ist aber technisch unübersichtlicher als die Dokumentation
es nahelegt. Die größten Risiken sind nicht einzelne Bugs, sondern **strukturelle Drifts**.

**➕ Wichtigste Korrektur der Revision 2:** Die strukturellen Drifts sind überwiegend **Symptome
einer auf halbem Weg stehengebliebenen Migration** (ADR-0001: Python/NiceGUI → Go/SvelteKit).
Die ADR sagt ausdrücklich: zwei Stacks parallel, „bis das Python-Backend abgelöst ist". Dieser
Endzustand wurde nie erreicht — das Python-Backend trägt weiterhin die gesamte Wetter-Pipeline
(Provider, Risk Engine, Renderer, Scheduler, Alerts), das Go-Backend ist API/Auth/Store/Proxy.
**Bevor in Refactoring investiert wird, muss die Zielarchitektur entschieden werden** (siehe
`docs/project/architektur-roadmap-2026-07.md`, Entscheidung E-0). Ohne diese Entscheidung riskiert
man, Wochen in eine Schicht zu investieren, die laut ADR abgelöst werden soll.

Drei technische Bereiche dominieren:

1. **Verkehrte Schicht-Zuordnung** zwischen Go-API und Python-Core (Doku-Drift, Symptom von E-0).
2. **Verwobene Geschäfts- und Ausgabelogik** im Python-Backend.
3. **GitHub-CI deckt nur einen Teil ab** — allerdings ist GitHub-CI in diesem Projekt bewusst
   *nicht* das primäre Qualitäts-Gate (Korrektur, siehe 3.4).

---

## 2. Dokumentierte Ziel-Architektur

Laut `AGENTS.md`, `docs/features/architecture.md` und `docs/specs/_template.md` soll das System so
aufgeteilt sein:

| Schicht | Dokumentierter Pfad | Zuständigkeit |
|---------|---------------------|---------------|
| **Frontend / User-UI** | `frontend/src/...` | SvelteKit-Web-Oberfläche |
| **Go-API** | `api/`, `internal/`, `cmd/` — **✗ falsch, siehe 3.1** | REST-API auf Port 8090 |
| **Python-Backend / Core** | `src/services/`, `src/app/`, `src/providers/` | FastAPI-Core über `api.main:app` auf Port 8000 |
| **Renderer / Kanäle** | `src/output/renderers/`, `src/outputs/` | E-Mail, HTML, Telegram, SMS |

Wichtige Architektur-Prinzipien aus den ADRs:

- **ADR-0001:** Migration von Python/NiceGUI zu Go/SvelteKit — **inkrementell**, Python bleibt
  produktiv „bis das Python-Backend abgelöst ist". ➕ Diese Ablösung ist nie erfolgt; der heutige
  Dual-Stack ist der in der ADR beschriebene (eigentlich temporäre) Übergangszustand.
- **ADR-0003:** Konsequente Mandantentrennung, kein `"default"`-Fallback **in authentifizierten
  Pfaden** (➕ Präzisierung — der Geltungsbereich ist in der ADR ausdrücklich so eingeschränkt).
- **ADR-0007:** Daten statt Empfehlungen.
- **ADR-0011:** Ein kanonischer Alert-Renderer als Single Source.
- **ADR-0014:** Telegram als Multi-Bubble-Tabellenformat.

---

## 3. Schwerwiegendste Architektur-Drifts

### 3.1 `api/` ist Python, nicht Go ✓

**Drift:** `AGENTS.md:8` und `docs/specs/_template.md` ordnen `api/` der Go-API zu. Tatsächlich
enthält `api/main.py` einen FastAPI-Wrapper (Python, Port 8000). Die Go-API startet in
`cmd/server/main.go` auf Port 8090 und proxied den Python-Core (`internal/handler/proxy.go`).

**Verifiziert:** ✓ `api/main.py` ist FastAPI; `AGENTS.md:8` behauptet „Go-API: `api/`,
`internal/`, `cmd/`".

**Risiko:** Neue Features und Specs werden falsch verortet; Agenten und Entwickler verstehen das
System falsch.

**Empfehlung:** Dokumentation korrigieren (`api/` = Python-Core, `cmd/server/` + `internal/` =
Go-API). ➕ Zusätzlich: Die Ursache (unfertige Migration) als Entscheidung E-0 an den PO — siehe
Roadmap.

---

### 3.2 Python-Services importieren direkt Presentation-Layer ✓ (untertrieben)

**Drift:** Services sollten kanalagnostische DTOs liefern. Stattdessen importieren sie direkt
E-Mail-, Telegram- und SMS-Renderer bzw. -Transporte.

**Betroffene Dateien (✗ Rev. 1 nannte 5–6, tatsächlich sind es 7):**

| Datei | Importiert |
|-------|------------|
| `src/services/trip_report_scheduler.py` | `formatters.trip_report`, `output.renderers.email.design_tokens`, `outputs.email/sms/telegram` |
| `src/services/trip_alert.py` | `formatters.trip_report`, `outputs.email/telegram/sms`, `output.renderers.email.helpers`, `output.renderers.alert.*` |
| `src/services/inbound_email_reader.py` | `outputs.email` |
| `src/services/inbound_telegram_reader.py` | `outputs.telegram` |
| `src/services/comparison_renderers.py` | `output.renderers.email.design_tokens`, `output.renderers.email.profile_signature` |
| ➕ `src/services/compare_subscription.py` | `output.renderers.email.compare_html` |
| ➕ `src/services/preview_service.py` | `src.formatters.sms_trip` |

**Risiko:** Business-Logik ist mit Rendering verwoben; Kanal-Änderungen beeinflussen Berechnungen;
Tests werden aufwändiger; neue Kanäle lassen sich schwer ergänzen.

**Empfehlung:** Services liefern DTOs; ein zentraler `NotificationService` koordiniert Renderer und
Transport. ➕ **Aber erst nach Entscheidung E-0** — diese Investition lohnt nur, wenn der
Python-Core offiziell Bestand hat.

---

### 3.3 Zwei Output-Pakete und Vermischungsebene ✓

- `src/output/` = Renderer und Templates.
- `src/outputs/` = Transport-Kanäle (SMTP, Telegram-Bot, SMS).
- `src/formatters/` = weitere Rendering-Ebene mit Domain-Logik.

**Risiko:** Namensverwirrung (`output` vs. `outputs`); keine klare Trennung Darstellung/Versand;
`formatters/` ist weder Fisch noch Fleisch.

**Empfehlung:** Umbenennen (`src/renderers/` + `src/channels/`) oder unter `src/output/` klar
trennen; `formatters/` auflösen. Änderungen an diesen Pfaden erfordern laut `AGENTS.md` einen ADR.

---

### 3.4 GitHub-CI deckt nur einen Teil ab — ✗ Einordnung in Rev. 1 irreführend

**Fakten (alle ✓ verifiziert):**

- `ci.yml` ignoriert `tests/tdd/` (318 Dateien), `tests/red/`, `tests/refactor/` und 7
  Unit-Dateien.
- Go: 102 Testdateien, laufen nicht in GitHub-CI. Frontend: 126 Unit-Testdateien (✗ Rev. 1: 114)
  + 123 Playwright-Specs, laufen nicht in GitHub-CI.
- Lint-Job hat `continue-on-error: true` (darf fehlschlagen).
- `mypy` ist in `pyproject.toml` konfiguriert (`strict = true`), aber **nicht installiert** (nicht
  in `uv.lock`, Import schlägt fehl) und läuft nirgends.

**✗ Korrektur der Bewertung:** Rev. 1 folgerte „Produktionsdeployments ohne echte
Qualitätskontrolle". Das stimmt nicht:

1. **GitHub-CI ist hier nicht das primäre Gate.** Die eigentliche Qualitätssicherung läuft im
   OpenSpec-Workflow: TDD-RED-Pflicht, Adversary-Validierung, Mail-Validatoren gegen echt
   zugestellte Staging-Mails, `/e2e-verify` gegen Staging, `prod_selftest` als hartes
   Deploy-Gate. Der CI-Deploy-Job selbst enthält Staging-Wait + Smoke-Test + Verdict-Schreiben
   (`ci.yml`, Job `deploy`) — auch das fehlte in der Rev.-1-Beschreibung.
2. **Der Ausschluss von `tests/tdd/` ist strukturell zwingend, kein Versehen.** Projektregel ist
   „KEINE MOCKED TESTS": Diese Tests brauchen echte Staging-Umgebung, echte IMAP-/Telegram-Creds.
   Sie können in GitHub Actions nicht laufen, ohne Secrets dorthin zu geben.

**Was trotzdem stimmt und billig zu holen ist:** Go-Tests, Frontend-Unit-Tests und `svelte-check`
brauchen **keine** Secrets und könnten sofort in die CI. `mypy` gehört installiert oder die
Konfiguration entfernt. Lint-Pflicht erst nach einmaliger Bereinigung (sonst dauerhaft rot).

---

### 3.5 Go-Handler enthalten Domain-Logik ✓ (Risiko-Teil ✗)

**Drift:** Handler enthalten Validierung, Berechnung, Wetter-Aggregation und ID-Generierung
(`validateTrip()`, `computeStageWeather()`, `normalizeMetricsPayload()` etc. — Beispiele aus
Rev. 1 bestätigt).

**✗ Korrektur:** Rev. 1 nannte „75 Handler-Dateien / 51 Testdateien". Tatsächlich: **24
Handler-Dateien + 51 Testdateien** (75 ist die Summe). 51 Testdateien für 24 Handler ist ein
*gutes* Verhältnis — die Behauptung „Handler werden schwer testbar" ist durch den Ist-Zustand
nicht gedeckt; sie **sind** getestet. Das Argument für eine Service-Schicht ist Wiederverwendbarkeit
und Lesbarkeit, nicht fehlende Tests.

**Empfehlung:** Service-Schicht (`TripService`, `SubscriptionService`, …), Handler dünn halten —
inkrementell beim Anfassen, kein Big-Bang.

---

### 3.6 Monolithischer Store und überladene `main.go` ✓

- `internal/store/store.go`: **831 Zeilen** ✓ — verwaltet User, Trip, Subscription, Location,
  MetricPreset, ComparePreset.
- `cmd/server/main.go`: **272 Zeilen** gesamt, überwiegend chi-Routing-Definition und
  Inline-Handler ✓ (Rev. 1: „~180 Zeilen Routing" — plausibel).

**Empfehlung:** Store in entitätsbezogene Dateien aufteilen (reine Dateiorganisation, risikoarm);
Router nach `internal/router/` auslagern.

---

### 3.7 Frontend-Architektur bröckelt ✓ (alle Zahlen bestätigt)

- `src/routes/+page.svelte`: 966 Zeilen ✓; `TripNewEditor.svelte`: 1061 ✓;
  `WeatherMetricsTab.svelte`: 845 ✓; größte Routen 966/809/739 ✓.
- `svelte-check`: **exakt 40 Fehler, 159 Warnings** ✓ (in Rev. 2 selbst ausgeführt).
- 20 Dateien definieren redundant `const API = () => env.GZ_API_BASE ?? 'http://localhost:8090'` ✓.
- `components/atoms/` sind größtenteils Re-Export-Wrapper auf `components/ui/` ✓.

**Empfehlung:** API-Base zentralisieren (schneller, risikoarmer Gewinn), `svelte-check`-Fehler auf 0
und dann in CI verankern, große Komponenten beim Anfassen splitten. UI-Architektur-Entscheidungen
(Atoms-Layer) liegen bei Claude Design (`docs/design-system/`).

---

### 3.8 Testpyramide — ✗ „invertiert" ist eine bewusste Entscheidung, kein Drift

**Fakten:** `tests/tdd/` 318 Dateien vs. `tests/unit/` 36 ✓.

**✗ Korrektur:** Die Dominanz issue-bezogener End-to-End-Tests folgt direkt aus der Projektregel
„KEINE MOCKED TESTS" (echte Beweise statt Mock-Theater) — eine dokumentierte PO-Entscheidung,
kein Wildwuchs. Kritikwürdig bleibt: **Test-Drift** (dauerhaft rote Tests auf `main`, siehe
Issues #984, #971, #979) und tote Altlasten.

**✗ Korrektur zu „ignorierte Unit-Tests reaktivieren":** Die 7 in CI ausgeschlossenen
Unit-Dateien sind **rot** (in Rev. 2 probeweise ausgeführt: `test_segment_builder.py` schlägt
heute fehl) bzw. Altlasten der NiceGUI-Ära (`test_gpx_upload_page` u. ä.). „Reaktivieren" heißt
real: **reparieren oder löschen** — das ist Teil des Test-Drift-Audits (#984), kein Umlegen eines
Schalters.

---

## 4. Dokumentationsabweichungen

| Dokument | Behauptet | Tatsächlich | Status |
|----------|-----------|-------------|--------|
| `AGENTS.md` | `api/` = Go-API | `api/` = Python FastAPI | ✓ bestätigt |
| `docs/specs/_template.md` | `api/` gehört zur Go-API-Schicht | `api/` ist Python-Core | ✓ bestätigt |
| `docs/features/architecture.md` | Signal via Callmebot (Z. 10) | Signal app-weit entfernt (Issue #610) | ✓ bestätigt |
| `docs/features/architecture.md` | CLI-Datenfluss als Produktivpfad | Python-Core-Pipeline via Scheduler/API ist der Produktivpfad | ✓ bestätigt |
| `pyproject.toml` `[tool.mypy]` | `strict = true` | mypy nicht installiert, läuft nirgends | ✓ bestätigt |
| ~~ADR-0003 vs. architecture.md~~ | ~~Kein `"default"`-Fallback~~ | **✗ gestrichen:** Der Fallback in `architecture.md` Z. 91/101 beschreibt die **Inbound-Handler** (nicht-authentifizierter Pfad). ADR-0003 verbietet den Fallback nur in **authentifizierten** Pfaden — kein Widerspruch. Der echte Befund steckt im Code, siehe 5.2. | ✗ korrigiert |

---

## 5. ➕ Übersehene Befunde (Rev. 2)

### 5.1 Strategische Wurzel: ADR-0001-Migration steht auf halbem Weg

Fast alle Drifts in Abschnitt 3 sind Symptome davon, dass der in ADR-0001 beschriebene Endzustand
(„Python-Backend abgelöst") nie erreicht wurde. Die fällige Entscheidung (Migration abschließen
**oder** Dual-Stack offiziell als Zielarchitektur beschließen) ist **Voraussetzung** für jede
größere Refactoring-Investition → Entscheidung E-0 in der Roadmap.

### 5.2 Inbound-`"default"`-Fallback im Code (Sicherheits-Prüfauftrag)

`src/services/inbound_email_reader.py:240` und `src/services/inbound_telegram_reader.py:338`
fallen bei **unbekanntem Absender** auf `user_id = "default"` zurück. Zu klären: Was antwortet das
System einem Fremden, der die Inbox anschreibt bzw. den Bot kontaktiert? Grenzt an die jüngsten
Test-Isolations-Arbeiten (#1013/#1014). → eigenes Issue.

### 5.3 Test-Fixtures im Produktiv-Datenverzeichnis

Im Prod-Working-Tree liegen untrackt Dutzende Test-User-Verzeichnisse (`data/users/tdd-*`,
`userA/`, `userB/`, …) neben echten Nutzerdaten — dasselbe Leck-Muster, das #1013/#1014 auf
Telegram-Ebene adressiert haben. Die Datenhaltung (flaches JSON-Dateisystem pro User) wurde in
Rev. 1 gar nicht betrachtet.

### 5.4 Das eigentliche Qualitätssystem liegt in `.claude/`

Adversary-Validierung, Staging-Gates (`staging_gate.py`, `e2e_verified.json`), Mail-Validatoren,
`renderer_mail_gate`, `prod_selftest` — wer die Qualitätslage dieses Projekts beurteilt, muss
dieses System mitbewerten. Rev. 1 hat nur `ci.yml` gelesen.

---

## 6. Quantifizierung (Rev. 2, korrigiert)

| Bereich | Messgröße | Wert |
|---------|-----------|------|
| Python-Service-Verletzungen | Services mit direktem Output/Formatter-Import | **7** Dateien (✗ Rev. 1: 6) |
| API-Router-Verletzungen | Router mit direktem Output/Formatter-Import | 4 Dateien ✓ (`scheduler`, `validator`, `debug`, `notify`; `debug.py` importiert sogar ein gelöschtes Modul → #977) |
| Go-Handler | Handler-Dateien / Testdateien | **24 / 51** (✗ Rev. 1: „75 / 51") |
| Go-Monolith | `internal/store/store.go` | 831 Zeilen ✓ |
| Frontend-Routen | Größte Routen | 966 / 809 / 739 Zeilen ✓ |
| Frontend-Komponenten | Größte Komponenten | 1061 / 845 / 799 Zeilen ✓ |
| Tests | `tests/tdd/` vs. `tests/unit/` | 318 vs. 36 Dateien ✓ |
| Frontend-Tests | Unit-Testdateien / Playwright-Specs | **126** / 123 (✗ Rev. 1: 114) |
| Frontend-Type-Qualität | `svelte-check` | 40 Fehler, 159 Warnings ✓ (exakt) |
| Code-Duplikate | `degrees_to_compass` / `haversine` | 5 / 3 Definitionen ✓ |

---

## 7. Roadmap

Die Rev.-1-Roadmap (Phasen A–E) ist durch die korrigierte Fassung ersetzt:
**`docs/project/architektur-roadmap-2026-07.md`** — mit der vorgelagerten PO-Entscheidung E-0
(Zielarchitektur), begründeter Empfehlung und Issue-basierter Umsetzung.

Kernabweichungen zur Rev.-1-Roadmap:

- **Phase B (Python-Schichtung) wird zurückgestellt**, bis E-0 entschieden ist — sonst
  Investition in eine offiziell zur Ablösung vorgesehene Schicht.
- **CI-Ausbau differenziert:** nur secrets-freie Tests (Go, Frontend-Unit, `svelte-check`) in
  GitHub-CI; `tests/tdd/` bleibt strukturell staging-gebunden.
- **„Unit-Tests reaktivieren" → „Test-Drift-Audit"** (reparieren oder löschen, zusammen mit #984).
- **„Verwaiste Dateien entfernen":** `src/web/` ist bereits aus Git entfernt (Issue #129); auf der
  Platte liegen nur untrackte Reste — Festplatten-Hygiene, kein Refactoring.

---

## 8. Quellen

Rev. 1: `AGENTS.md`, `docs/features/architecture.md`, `docs/specs/_template.md`,
`docs/adr/0001…0014`, `api/main.py`, `.github/workflows/ci.yml`, `pyproject.toml`,
`internal/handler/*.go`, `internal/store/store.go`, `cmd/server/main.go`, `src/services/*.py`,
`frontend/src/**`.

Rev. 2 zusätzlich: eigene Verifikationsläufe (`wc -l`, Import-Greps, `svelte-check`,
`pytest tests/unit/test_gpx_parser.py tests/unit/test_segment_builder.py`, `git log -- src/web/`),
`docs/adr/0003-multi-tenant-isolation.md` (Geltungsbereich), `.claude/`-Gate-System,
GitHub-Issues #984, #977, #971, #987, #1013, #1014.
