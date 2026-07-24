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

## Durchsetzung (Stand 2026-07-22, #1343)

- **Spec-Pflichtfeld** (Plugin-Workflow `workflow.py` `_validate_transition`): Specs mit
  `created >= 2026-06-25` lassen sich nur freigeben, wenn die Sektion
  `## Architektur-Entscheidung (ADR)` ausgefüllt ist (ADR-Nr. oder „keine"). Ältere Specs
  sind grandfathered. Dieser Mechanismus ist AKTIV (227 Specs tragen die Sektion).
- **Commit-Gate:** Das frühere `adr_guard.py`-Gate (Issue #885) ist ENTFERNT — siehe
  ADR-0027. Auf Datei-Ebene gilt Konvention, nicht Mechanik.
- **Index-Drift-Test** (`tests/test_adr_index_drift.py`, `# doc-compliance-test`): erzwingt,
  dass jede ADR-Datei im Index steht und der Index-Status zur Status-Zeile der Datei passt —
  der Index ist vor #1343 zweimal nachweislich gedriftet (issue_1165, ADR-0002).
- **Einstiegsfläche:** CLAUDE.md → „Architektur-Entscheidungen (ADRs)" verweist hierher.

## Status-Werte

- **Vorgeschlagen** — zur Diskussion, noch nicht verbindlich
- **Akzeptiert** — gilt
- **Abgelöst durch ADR-XXXX** — durch eine spätere Entscheidung ersetzt
- **Zurückgezogen** — verworfen, ohne Ersatz

## Index

| ADR | Titel | Status |
|-----|-------|--------|
| [0001](0001-go-sveltekit-migration.md) | Migration Python/NiceGUI → Go/SvelteKit | Akzeptiert |
| [0002](0002-met-vs-mosmix-forecast-source.md) | Wetterquelle: MET Norway als Standard, MOSMIX nur als enge Ausnahme | Abgelöst durch ADR-0029 |
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
| [0013](0013-alert-threshold-ist-delta-sensitivitaet.md) | Alert-Renderer: `threshold` ist immer Δ-Sensitivitätsschwelle, nie Absolutwert-Referenz | Akzeptiert |
| [0014](0014-telegram-multi-bubble-format.md) | Telegram-Ausgabe: Multi-Bubble-Tabellenformat ersetzt Prosa | Akzeptiert |
| [0015](0015-dual-stack-zielarchitektur.md) | Dual-Stack (Go + Python) als dauerhafte Zielarchitektur — präzisiert 0001 | Akzeptiert |
| [0016](0016-amtliche-warnungen-additiver-typ.md) | Amtliche Warnungen als additiver externer Alert-Typ (Nachtrag im Index) | Akzeptiert |
| [0017](0017-output-paket-konsolidierung.md) | Ein Output-Paket: `src/output/` mit `renderers/` + `channels/`; `formatters/`+`outputs/` aufgelöst | Akzeptiert |
| [0018](0018-provider-fallback-ohne-kaschieren.md) | Modell-Fallback bei Wetter-Quell-Ausfall — mit Ausweichen, aber ohne Kaschieren | Akzeptiert |
| [0019](0019-nullgradgrenze-eine-alert-metrik.md) | Nullgradgrenze als eine Alert-Metrik | Akzeptiert |
| [0020](0020-node-test-frontend-unit-runner.md) | node:test ist der kanonische Frontend-Unit-Test-Runner (kein vitest) | Akzeptiert |
| [0021](0021-shared-deviation-alert-engine.md) | Gemeinsame `DeviationAlertEngine` für Trip- und künftige Compare-Alarme | Akzeptiert |
| [0022](0022-ascii-faltung-via-anyascii.md) | ASCII-Faltung via `anyascii` statt handgepflegter Transliterations-Tabellen | Akzeptiert |
| [0023](0023-briefing-subscription-shared-model.md) | Gemeinsames `BriefingSubscription`-Modell (`kind`-Diskriminator) + `briefings/`-Persistenz | Akzeptiert |
| [0024](0024-ein-sortier-baustein-svelte-dnd-action.md) | Ein geteilter Sortier-Baustein auf svelte-dnd-action; Pfeil-Buttons weichen dem eingebauten Tastatur-Pfad | Akzeptiert |
| [0025](0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md) | Eine Gewitter-Quelle für alle Briefing-Kanäle — gleiche Rohdaten, gleiche Fensterung, gleiche Skala | Akzeptiert |
| 0026 | — (Nummer nie vergeben; Lücke dokumentiert 2026-07-22, kein Dokument) | — |
| [0027](0027-adr-commit-guard-entfernt.md) | Lokales ADR-Commit-Gate (`adr_guard.py`) entfernt — tot seit Plugin-Migration, ADR-Praxis bleibt bestehen | Akzeptiert |
| [0028](0028-e2e-prod-network-unreachable-admin-loses-never-delete.md) | Prod-Datenbaum wird für E2E netzwerkseitig unerreichbar; `admin` verliert den NEVER_DELETE-Schutz aus #1265 | Akzeptiert |
| [0029](0029-openmeteo-standard-provider.md) | Open-Meteo als Standard-Wetterdaten-Provider (löst 0002 ab) | Akzeptiert |
| [0030](0030-session-auth-hmac-cookie.md) | Session-Auth über HMAC-signiertes Cookie (kein JWT, keine Session-Tabelle) | Akzeptiert |
| [0031](0031-persistenz-dateibasiert-data-users.md) | Dateibasierte JSON-Persistenz unter `data/users/{user_id}/` (keine Datenbank) | Akzeptiert |
| [0032](0032-wizard-abschaffung-progressive-editoren.md) | Multi-Step-Wizards abgeschafft — progressive Tab-Editoren mit Auto-Save | Akzeptiert |
| [0033](0033-warn-karte-nur-betroffene-segmente.md) | Amtliche Warn-Karte zeigt nur betroffene Segmente, kein Vollrouten-Gitter (löst #1233/#1216 ab) | Akzeptiert |
| [0034](0034-herkunftsfusszeile-reale-datenquelle.md) | Herkunfts-Fußzeile zeigt die reale Datenquelle statt Renderer-Pfad + Commit-Hash (löst #1241 ab) | Akzeptiert |
