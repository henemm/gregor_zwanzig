# Architecture Decision Records (ADR)

Dieses Verzeichnis hält **wichtige Architektur- und Produkt-Grundsatzentscheidungen** des
Projekts fest — jeweils ein kurzes, nummeriertes Dokument pro Entscheidung.

## Wozu ADRs?

Entscheidungen waren früher über `CLAUDE.md`, `docs/project/strategic-directions.md` und
diverse Specs verstreut. Ein ADR beantwortet an **einer auffindbaren Stelle**:

- **Was** wurde entschieden?
- **Warum** — welcher Kontext/Druck führte dazu?
- **Welche Alternativen** wurden verworfen, und warum?
- **Welche Konsequenzen** hat die Entscheidung (auch die unangenehmen)?

Der Hauptnutzen: Schon getroffene Entscheidungen werden nicht versehentlich rückgängig
gemacht. (Genau das war bei Issue #710 passiert — eine bewusst entfernte Funktion wurde
unbemerkt wieder eingebaut.)

## Wann ein neues ADR schreiben?

Immer wenn eine Entscheidung **schwer umkehrbar** ist oder **mehrere Teile** des Systems
betrifft. Faustregeln:

- Ein Kanal/Provider/Framework wird eingeführt oder entfernt
- Eine bewusste Produkt-Grenze wird gezogen ("Funktion X gibt es absichtlich nicht")
- Ein Datenmodell- oder Persistenz-Prinzip wird festgelegt
- Eine Test- oder Deploy-Strategie wird verbindlich

Kleine, lokale Implementierungsentscheidungen gehören **nicht** hierher — die stehen im Code
bzw. in den Specs unter `docs/specs/`.

## Format & Workflow

1. Nächste freie Nummer nehmen (vierstellig, fortlaufend).
2. `_template.md` kopieren nach `NNNN-kurzer-titel.md`.
3. Ausfüllen, Status auf **Akzeptiert** setzen, hier im Index eintragen.
4. Wird eine Entscheidung später revidiert: das alte ADR **nicht löschen**, sondern Status auf
   **Abgelöst durch ADR-XXXX** setzen und ein neues ADR schreiben. Die Historie bleibt damit
   nachvollziehbar.

## Durchsetzung (mechanisch, seit Issue #885)

ADRs sind nicht nur Konvention, sondern werden erzwungen:

- **Commit-Gate** (`.claude/hooks/adr_guard.py`, eingehängt in `bash_gate.py`): Wer eine
  *entscheidungs-tragende* Datei staged (Kanäle, Provider/Quellenwahl, Metrik-Sichtbarkeit,
  Gate-/Guard-Hooks), muss im selben Commit **entweder** ein `docs/adr/*.md` mitliefern **oder**
  bewusst `[no-adr]` in die Commit-Message schreiben — sonst blockiert der Commit.
- **Spec-Pflichtfeld** (`workflow.py` `_validate_transition`): Specs mit `created >= 2026-06-25`
  lassen sich nur freigeben, wenn die Sektion `## Architektur-Entscheidung (ADR)` ausgefüllt ist
  (ADR-Nr. oder „keine"). Ältere Specs sind grandfathered.

## Status-Werte

- **Vorgeschlagen** — zur Diskussion, noch nicht verbindlich
- **Akzeptiert** — gilt
- **Abgelöst durch ADR-XXXX** — durch eine spätere Entscheidung ersetzt
- **Zurückgezogen** — verworfen, ohne Ersatz

## Index

| ADR | Titel | Status |
|-----|-------|--------|
| [0001](0001-go-sveltekit-migration.md) | Migration Python/NiceGUI → Go/SvelteKit | Akzeptiert |
| [0002](0002-met-vs-mosmix-forecast-source.md) | Wetterquelle: MET Norway als Standard, MOSMIX nur als enge Ausnahme | Akzeptiert |
| [0003](0003-multi-tenant-isolation.md) | Konsequente Mandantentrennung, kein `"default"`-Fallback | Akzeptiert |
| [0004](0004-signal-channel-removed.md) | Signal als Briefing-Kanal entfernt | Akzeptiert |
| [0005](0005-confidence-not-selectable-metric.md) | Confidence ist keine pro-Etappe wählbare Metrik | Akzeptiert |
| [0006](0006-no-mocked-tests-e2e-staging.md) | Keine gemockten Tests; echte E2E-Verifikation gegen Staging | Akzeptiert |
| [0007](0007-daten-statt-empfehlungen.md) | Daten statt Empfehlungen — keine paternalistische Bewertung | Akzeptiert |
| [0008](0008-kontrast-vor-optik.md) | Lesbarkeit/Kontrast vor weicher Optik | Akzeptiert |
| [0009](0009-alerts-als-abweichungs-waechter.md) | Alerts sind Abweichungs-Wächter, keine absoluten Schwellen | Akzeptiert |
| [0010](0010-vorboten-metriken-kein-alert-ausloeser.md) | Vorboten-Metriken sind keine Alert-Auslöser | Akzeptiert |
| [0011](0011-alert-render-single-backend-renderer.md) | Alert-Render-System — ein Backend-Renderer, Registry als Single Source | Akzeptiert |
| [0012](0012-telegram-parse-mode-html.md) | Telegram-Formatierung — parse_mode=HTML statt Markdown/MarkdownV2 | Akzeptiert |
| [0013](0013-node-test-frontend-unit-runner.md) | node:test ist der kanonische Frontend-Unit-Test-Runner (kein vitest) | Akzeptiert |
| [0014](0014-telegram-multi-bubble-format.md) | Telegram-Ausgabe: Multi-Bubble-Tabellenformat ersetzt Prosa | Akzeptiert |
| [0014](0014-nullgradgrenze-eine-alert-metrik.md) | Nullgradgrenze als eine Alert-Metrik (Nummern-Kollision; war bisher nicht im Index) | Akzeptiert |
| [0015](0015-dual-stack-zielarchitektur.md) | Dual-Stack (Go + Python) als dauerhafte Zielarchitektur — präzisiert 0001 | Akzeptiert |
| [0016](0016-amtliche-warnungen-additiver-typ.md) | Amtliche Warnungen als additiver externer Alert-Typ (Nachtrag im Index) | Akzeptiert |
| [0017](0017-output-paket-konsolidierung.md) | Ein Output-Paket: `src/output/` mit `renderers/` + `channels/`; `formatters/`+`outputs/` aufgelöst | **Vorgeschlagen** (#1026) |
