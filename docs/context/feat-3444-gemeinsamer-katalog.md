# Kontext: feat-3444-gemeinsamer-katalog

## Request Summary

Issue #3444 (PO-Entscheidung 2026-11-27 in #2993, Variante C „Gemeinsamer Katalog"): Texte, die in Go-API **und**
Python-Core wortgleich vorkommen, kommen aus **einer** Quelle statt aus zwei per Fixture gleich gehaltenen Kopien.
Reihenfolge laut Issue: (1) ADR zuerst (ADR-0104 fortschreiben: Ort der Quelle, Einbettung/Laden, Deploy-Kopplung),
(2) erste Scheibe `kind_required` (Ziel von #2993), (3) Folgescheiben übrige Gleichtexte. Deutsch bleibt byte-gleich.
Frontend-Katalog (`fehler.code.*`) ist ausgenommen. Ersetzt #2993.

Vorarbeit (Analyse, Fundstellen, Varianten A–E): `docs/context/feat-2993-kind-required-katalog.md`.

## Heutige Gleichtexte Go ↔ Python (DE, Stand 2026-11-27)

| Gruppe | Go (`internal/i18n/messages/<lang>/`) | Python (`src/i18n/messages/<lang>/`) | Verwender |
|---|---|---|---|
| kind_required | `fehler.json` `fehler.kind_required` | `versand.json` `versand.ergebnis.kind_required` | Go `WriteError` (briefing_send/preview/placements), Py `services/send_outcomes.py:18` → `briefings_send.py`, `placements.py` |
| Radar-Intensität | `alarm.json` `alarm.radar.intensitaet.{trocken,leicht,maessig,stark,gewitter,hagel_gewitter}` (6) | `alarm.json` gleichnamig + zusätzlich `hagel`, `regen` (nur Python) | Go `internal/mcp/werkzeuge.go`; Py `radar_service.py`, `alert/render.py`, `mcp_nowcast.py`, Radar-Mail-Validator |
| MCP-Fehler | `mcp.json` `mcp.fehler.bis_vor_von`, `mcp.fehler.feld_unbekannt` (Platzhalter `{feld}`, `{gueltig}`) | `api.json` `api.fehler.mcp_bis_vor_von`, `api.fehler.mcp_feld_unbekannt` | Go `internal/handler/mcp_wetter.go`, `internal/mcp/werkzeuge.go`; Py `api/routers/mcp_wetter.py` |

Gleichlauf-Zwang heute: nur für `kind_required` per Fixture `tests/fixtures/send_detail_parity/faelle.json`
(Tests `tests/tdd/test_briefings_send_endpoint.py:417`, `internal/handler/briefing_send_test.go:514`).
Radar und MCP haben **keinen** Gleichlauf-Wächter → können heute unbemerkt driften.

Schlüsselnamen unterscheiden sich zwischen den Schichten (`fehler.` vs. `versand.ergebnis.`, `mcp.fehler.` vs.
`api.fehler.mcp_`) → die gemeinsame Quelle braucht entweder einen eigenen Schlüsselraum oder eine Abbildung.

## Related Files

- Go-Loader `internal/i18n/catalog.go`: `//go:embed messages`, `NewCatalog(fsys)` walkt `messages/<lang>/<bereich>.json`,
  prüft Schlüssel-Präfix `<bereich>.`; Paritätstest `internal/i18n/katalog_paritaet_test.go`; Hardcode-Ratsche
  `internal/i18n/hardcode_guard_test.go`. Go-`embed` kann nur Dateien **unterhalb des Paketordners** einbetten (keine `..`).
- Python-Loader `src/i18n/catalog.py`: `MESSAGES_DIR` relativ zu `src/i18n`, feste Liste `BEREICHE`, `_lade_sprache`
  liest je Bereich eine Datei; `get_catalog()` cached je Ordner. Paritätstests: `tests/unit/test_i18n_katalog_paritaet.py`,
  `tests/test_i18n_api_katalog_paritaet.py`, `tests/test_i18n_inbound_katalog_paritaet.py`.
- Doku: `docs/reference/i18n_konventionen.md` (Abschnitt 2 Namensräume-Tabelle; `tests/test_i18n_glossar_und_vertrag.py:139`
  prüft dort den Pfadwortlaut), ADR `docs/adr/0104-zweisprachigkeit-de-en.md`, ADR-Index `docs/adr/README.md`
  (Drift-Test `tests/test_adr_index_drift.py`). Letzte ADR-Nummer: 0129.
- Spec mit Fixture-Lösung: `docs/specs/modules/feat_2280_handversand_endpoint.md:182`.

## Existing Patterns (schichtübergreifendes Lesen)

- Kein Laufzeitcode liest heute den Katalog einer anderen Schicht.
- **Nur Tests** tun es: Frontend-Drift-Wächter lesen den Python-Katalog per `uv run python3` (CI-Kommentar
  `.github/workflows/ci.yml:108`), E2E-Abgleich `frontend/e2e/elementliste_abgleich_logik.ts` liest `src/i18n/messages`.
- Vorbild „erzeugte Kopie + Drift-Ratsche": `tests/fixtures/metric_tokens_frozen.json` (Einfrieren), ADR-0127 (ein Katalog
  für Metrik-Wissen).

## Deploy-Kopplung (belegt, `~/Developer/henemm-infra/scripts`)

- Staging (`auto-deploy-gregor-staging.sh`) und Prod (`deploy-gregor-prod.sh`) arbeiten je auf **einem** Repo-Checkout
  (`/home/hem/gregor_zwanzig_staging` bzw. `/home/hem/gregor_zwanzig`): Fast-Forward auf denselben Commit, `uv sync`,
  `go build ./cmd/server` aus demselben Baum, Neustart Python → Go → Frontend. Go und Python sind damit immer auf
  demselben Stand; eine Datei im Repo ist für beide zur Laufzeit vorhanden (Go zusätzlich zur Build-Zeit eingebettet).
- **Leserechte:** Prod setzt `chgrp -R claude-gregor` nur auf `.venv` und `src/` (Zeile 413–416); Staging setzt ACLs per
  `setup-gregor-staging-user.sh acl-code`. Ob der Python-Dienstnutzer Dateien unter `internal/` lesen darf, ist **nicht
  belegt** → Risiko für die Variante „Python liest Datei im Go-Paket zur Laufzeit".
- CI: Python- und Go-Jobs laufen auf demselben Checkout; `go build` / `go test ./...` sehen nur eingebettete Dateien.

## Lösungsrichtungen (für die Analyse, nicht entschieden)

1. **Quelle im Go-Paket, Python liest zur Laufzeit** (z. B. `internal/i18n/messages/<lang>/geteilt.json`): Go bettet
   nativ ein; Python ergänzt den Loader um einen zweiten Ordner. Risiko Leserechte `internal/` auf dem Server, Python
   hängt an Go-Pfad.
2. **Quelle neutral (z. B. `i18n/geteilt/<lang>.json` im Repo-Wurzel), Go bekommt erzeugte Kopie** im Paket plus
   Drift-Ratsche (Test vergleicht byte-gleich) oder `go generate`. Zwei Dateien, aber eine Quelle und mechanischer Zwang.
3. **Quelle im Python-Baum, Go-Kopie erzeugt** — spiegelbildlich, Leserechte `src/` schon gesetzt.
4. **Eigenes kleines Go-Paket `internal/i18n/geteilt`** mit Datei, die Python liest — wie 1, nur abgegrenzt.

Offene Analysepunkte: gemeinsamer Schlüsselraum (Bereichsname, z. B. `geteilt.*`) vs. Beibehaltung der heutigen
Schlüssel; Lookup-Reihenfolge in Go (`WriteError`-Suchkette) und Python; was passiert mit den alten Schlüsseln
(Konvention „Schlüssel werden nie umbenannt oder gelöscht" vs. Ziel „nicht doppelt"); Rolle der Fixture.

## Dependencies / Dependents

- Go: `internal/i18n` (embed, Bereichsprüfung `checkKey`, Parität), `internal/handler/httperr.go` (`WriteError`-Suchkette
  `fehler.` → `auth.fehler.` → `konto.fehler.` → `fach.fehler.`), MCP-Werkzeuge.
- Python: `src/i18n/catalog.py` (`BEREICHE`, `MESSAGES_DIR`), `services/send_outcomes.py` (Schlüssel je Code), Radar-
  Renderer/Service, MCP-Router, Mail-Validatoren (`.claude/hooks/radar_alert_mail_validator.py` lesen Python-Katalog).
- Tests: alle Paritäts- und Golden-Tests beider Schichten, Fixture `send_detail_parity`, Hardcode-Ratschen.

## Existing Specs

- `docs/specs/modules/feat_2280_handversand_endpoint.md` (Fixture-Lösung F004), i18n-Specs #2660/#2671/#2675,
  Radar-MCP #3398, MCP-Konnektor #3281.

## Risks

- **ADR-pflichtig** (i18n-Datenmodell, ADR-0104): Abweichung von „je Schicht ein Katalog" nur per neuem ADR.
- Laufzeit-Leserechte auf dem Server (nur `src/` und `.venv` explizit für `claude-gregor` freigegeben).
- Go-`embed` erlaubt keine Pfade außerhalb des Pakets → neutrale Quelle bedingt erzeugte Kopie.
- Deutsch byte-gleich (Golden-Tests Go, Python, Mail-Validatoren).
- Scope: drei Gruppen, mehrere Scheiben; je Scheibe ≤ 4–5 Dateien / ±250 LoC einhalten. Radar-Gruppe ist auf
  Python-Seite größer als auf Go-Seite (`hagel`, `regen` nur Python).
- Löschen alter Schlüssel kollidiert mit Konventionssatz „nie umbenannt oder gelöscht" → im ADR klären.

## Analysis

**Type:** Feature (Architektur/Aufräumen, ADR-pflichtig), kein Bug. Nutzerwirkung nur: geteilte Texte können nicht mehr auseinanderlaufen.

### Befunde (3 Explore-Agenten + Plan-Agent + eigene Gegenprobe)

- **Alle Gleichtexte sind heute identisch** (eigene Gegenprobe 2026-11-27, Diff beider Kataloge): `kind_required`, 6× `alarm.radar.intensitaet.*`, 2× MCP-Fehler, jeweils DE **und** EN byte-gleich → kein Wortlaut-Zielkonflikt, keine PO-Frage.
- **Leserechte Prod:** Python-Dienst `claude-gregor` bekommt nur `.venv` und `src/` freigegeben (`henemm-infra/scripts/deploy-gregor-prod.sh:413-417`); `internal/` oder ein neuer Wurzelordner ist zur Laufzeit **nicht gesichert** (Staging-ACL deckt alles, `setup-gregor-staging-user.sh:37-41`). Dienst `systemd/gregor-python.service:7`, `WorkingDirectory=/home/hem/gregor_zwanzig`; `ProtectHome=read-only` blockt Lesen nicht.
- **Go-Modul:** `go.mod` liegt in der Repo-Wurzel (`module github.com/henemm/gregor-api`) → ein Go-Paket in `src/i18n/` ist legal (Importpfad `github.com/henemm/gregor-api/src/i18n`); `//go:embed` darf Dateien im eigenen Ordner und darunter einbetten. `src/i18n` hat heute keine `.go`-Datei; Python ignoriert sie.
- **Go-Loader:** `checkKey` (`internal/i18n/catalog.go:83-94`) verlangt Präfix = Bereichsname → `geteilt.*` nur in `geteilt.json`; keine feste Bereichsliste im Loader, aber Präsenzliste im Test `katalog_paritaet_test.go:44`. Fehlersuchkette `errorPrefixes` (`internal/i18n/errorbody.go:5`), Kopie in `internal/handler/fehlercode_katalog_waechter_test.go:28`. `duplicateCodes` (`catalog.go:189-206`) verbietet denselben Code unter zwei Präfixen → altes `fehler.kind_required` muss im selben Commit weg.
- **Python-Loader:** feste `BEREICHE` (`src/i18n/catalog.py:18-21`), exakt geprüft in `tests/unit/test_i18n_katalog_paritaet.py:15-34`; `_form_fehler` verlangt Präfix = Bereich. `send_outcomes.py:15-36` bildet `versand.ergebnis.{code}`; `error_body` (:75-82) nimmt `text_key`-Override.
- **Tests zu kind_required:** Fixture-Paar `tests/tdd/test_briefings_send_endpoint.py:417-430` ↔ `internal/handler/briefing_send_test.go:492-541`; `tests/test_versand_zweisprachig.py:173-177` erwartet `t("versand.ergebnis.kind_required", lang)` (→ neuer Schlüssel); `internal/i18n/uebersetzung_test.go:143` erwartet `Has("fehler.kind_required")` (→ neuer Schlüssel); übrige prüfen nur Code/Status.
- Keine Ratsche erzwingt „Schlüssel nie löschen" (nur Konventionssatz in `i18n_konventionen.md`).

### Varianten

| | V1 Quelle im Go-Paket, Python liest | V2 Quelle in `src/`, Go-Kopie generiert + Drift-Ratsche | V3 neutrale Wurzel + 2 Kopien | **V4 Quelle `src/i18n/messages/<lang>/geteilt.json`, Go bettet per `src/i18n/embed.go` ein** |
|---|---|---|---|---|
| Physische Dateien je Text | 1 | 2 | 3 | **1** |
| Prod-Leserecht Python | nicht gesichert (Infra-Änderung im Fremd-Repo) | ok | ok | **ok** |
| Drift möglich | nein | ja (Ratsche nötig) | ja | **nein** |
| Zusatz-Code | Py-Loader ~30 LoC | Generator + Test ~80 LoC | mehr | **embed.go ~10 + Go-Merge ~15 LoC** |
| LoC Scheibe 1 | ~150 | ~230 | >250 | **~130–150** |

### Empfehlung / Technical Approach: V4

- **Eine Datei je Sprache:** `src/i18n/messages/{de,en}/geteilt.json`, Bereich `geteilt`, Schlüssel `geteilt.<gruppe>.<element>` (z. B. `geteilt.fehler.kind_required`). Gepflegt nur dort.
- **Python:** `geteilt` in `BEREICHE` aufnehmen — normaler Bereich, keine neue Loader-Mechanik.
- **Go:** neue Datei `src/i18n/embed.go` (Paket unter `src/i18n`), `//go:embed messages/de/geteilt.json messages/en/geteilt.json`, exportiert ein `embed.FS`. **Nur** die geteilten Dateien einbetten, nicht `messages` ganz (sonst Python-Bereiche in Go). `internal/i18n` lädt beim Standardkatalog beide FS (Merge-Helfer ≤ 20 LoC; `loadFile`/`checkKey` unverändert, Pfadlayout `messages/<lang>/<bereich>.json` passt).
- **Fehlersuchkette:** `geteilt.fehler.` in `errorPrefixes` (+ Kopie im Wächtertest); Python `send_outcomes` für `kind_required` → `geteilt.fehler.kind_required`.
- **Alte Schlüssel** `fehler.kind_required` (Go) und `versand.ergebnis.kind_required` (Python) **löschen** (Go-`duplicateCodes` erzwingt es; Behalten wäre wieder eine zweite Quelle). ADR hält die Ausnahme von „nie löschen" fest: gilt für das Umziehen nach `geteilt`.
- **Fixture `send_detail_parity`:** bleibt als reiner Verhaltenswächter (HTTP-Ausgabe beider Schichten = deutscher Wortlaut), nicht mehr als Gleichlauf-Zwang; Hinweistext anpassen.
- **Wächter:** Go-Test, dass Bereich `geteilt` nicht unter `internal/i18n/messages` liegt (nur aus dem `src`-FS).
- **ADR:** neues ADR-0130 „Gemeinsamer Textkatalog Go/Python" (schreibt ADR-0104 fort: „je Schicht ein Katalog" + Ausnahme Bereich `geteilt`), ADR-Index, `i18n_konventionen.md` (Namensräume-Tabelle + Regel „geteilt nur in `src/i18n/messages`"). Deploy-Kopplung belegt: Staging und Prod bauen Go und starten Python aus demselben Checkout/Commit (`auto-deploy-gregor-staging.sh:261`, `deploy-gregor-prod.sh`).

### Scope / Reihenfolge (Tech-Lead-Entscheidung)

- **Dieser Workflow = ADR + Mechanismus + Scheibe 1 `kind_required`.** Code-Dateien: `src/i18n/embed.go` (neu), `internal/i18n/catalog.go`, `internal/i18n/errorbody.go`, `src/i18n/catalog.py`, `src/services/send_outcomes.py` (5); dazu reine Daten-JSON (`geteilt.json` ×2 neu, Schlüssel raus aus `fehler.json` ×2 und `versand.json` ×2), Tests, ADR/Doku. ~150 LoC Code+Tests, Rest Daten/Doku. Go-Löschung und neuer Schlüssel im selben Commit (`duplicateCodes`).
- **Folge-Issues (eigene Workflows, je ~100–120 LoC), beim Abschluss anlegen:** (2) Radar-Intensität 6 Schlüssel → `geteilt.radar.intensitaet.*` (4 Segmente ok; Python behält `hagel`, `regen`; Radar-Mail-Validator mitziehen); (3) MCP-Fehler 2 Texte → `geteilt.fehler.mcp_*` (Go nutzt direkt `T()`, Python baut `f"api.fehler.{code}"` in `api/fehler.py:39` → Zuordnung nötig).

### Risks

- `go test ./...`/`go vet` sehen neues Paket `src/i18n` (ohne Tests, unkritisch). Go-Build in CI und Deploy läuft im vollen Checkout (`ci.yml:339`) → `src/` vorhanden.
- Deutsch byte-gleich: Text wird nur verschoben, nicht geändert; Fixture-Tests beider Schichten belegen es.

### Open Questions

- Keine PO-Frage: Richtung „gemeinsamer Katalog" ist PO-entschieden, Wortlaute sind identisch, der Rest ist Technik.

## TDD-RED: verbindliche API für die Implementierung

- Go-Paket `github.com/henemm/gregor-api/src/i18n` in `src/i18n/embed.go`, `var Messages embed.FS` mit nur `messages/de/geteilt.json`, `messages/en/geteilt.json`.
- `internal/i18n`: `func NewCatalogFrom(fsys ...fs.FS) (*Catalog, error)` (führt mehrere FS zusammen); Standardkatalog = `NewCatalogFrom(embedded, srci18n.Messages)`.
- `internal/i18n`: `func CheckNoSharedAreaInternal(fsys fs.FS) error` — Fehler, wenn `messages/<lang>/geteilt.json` im FS liegt; Test ruft ihn mit `embedded` auf.
- `"geteilt.fehler."` in `errorPrefixes` (`internal/i18n/errorbody.go`).
- `internal/i18n/katalog_paritaet_test.go:44` bleibt unverändert (Liste der internen Bereiche; `geteilt` gehört dort gerade nicht hin).
- RED-Tests: `tests/unit/test_3444_gemeinsamer_katalog.py`, `internal/i18n/geteilt_3444_test.go`; angepasst: `tests/test_versand_zweisprachig.py`, `tests/unit/test_i18n_katalog_paritaet.py`, `internal/i18n/uebersetzung_test.go`, `internal/handler/fehlercode_katalog_waechter_test.go`.
