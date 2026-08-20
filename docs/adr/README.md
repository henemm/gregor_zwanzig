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
| [0009](0009-alerts-als-abweichungs-waechter.md) | Alerts sind Abweichungs-Wächter, keine absoluten Schwellen | Teilweise abgelöst durch ADR-0056 |
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
| [0035](0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md) | Ein Tagesfenster für Trip und Ortsvergleich — wirksam auf Anzeige und Bewertung (nimmt #1268 für den Vergleich zurück) | Akzeptiert |
| [0036](0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md) | Nebenläufigkeitsschutz über Inhalts-Fingerabdruck statt Versionsfeld (Issue #1395 S1/S2) | Akzeptiert |
| [0037](0037-datengetriebener-ausblick-aus-metrik-katalog.md) | 3-Tages-Ausblick der Vergleichs-Mail datengetrieben aus dem Metrik-Katalog statt fester Sieben-Spalten-Liste (Issue #1361 Befund 2 + #1368, S3 Scheibe A von Epic #1372) | Akzeptiert |
| [0038](0038-zeitgrenze-je-nutzerlauf-unter-aufrufer-wartezeit.md) | Jeder wiederkehrende Job-Lauf bekommt eine Zeitgrenze unter der Wartezeit seines Aufrufers (Issue #1447) | Akzeptiert |
| [0039](0039-amtliche-warnungen-aus-kontingentfreiem-feed.md) | Amtliche Warnungen kommen aus dem kontingentfreien MeteoAlarm-Feed statt aus der mengenbegrenzten EDR-Index-API (Issues #1445, #1397) | Akzeptiert |
| [0040](0040-schwellen-alarm-additiver-alarm-typ.md) | Der nutzerkonfigurierte Schwellen-Alarm ist ein additiver zweiter Alarm-Typ neben dem Abweichungs-Wächter (Issue #1444) | Abgelöst durch 0043 |
| [0041](0041-zustaendigkeit-warn-quellen-drei-muster.md) | Zuständigkeit einer Warn-Quelle wird nach Art des Endpunkts bestimmt — drei Muster statt einheitlicher Geometrie (Issues #1397 Defekt 2, #1400, #1445) | Akzeptiert |
| [0042](0042-namensform-folgt-der-platzgrenze.md) | Die Namensform einer Wettergröße folgt der Platzgrenze, nicht einer pauschalen Sprachpräferenz — Protokoll-Token nie übersetzen, Anzeige-Namen nach Platz (Issues #1453, #862/#849 bestätigt) | Akzeptiert |
| [0043](0043-empfindlichkeitsstufe-als-niveau-statt-zweiter-alarm-typ.md) | Die Empfindlichkeitsstufe ist der einzige Alarm-Regler — bei Gefahrenstufen-Größen wirkt sie über das erreichte Niveau (löst 0040 ab, Issue #1460) | Akzeptiert |
| [0044](0044-kalendertage-folgen-der-ortszeit.md) | „Heute" und „morgen" bestimmen sich nach der Ortszeit der Tour, nicht nach Weltzeit — Dauern bleiben davon unberührt (ergänzt 0035, Issue #1470) | Akzeptiert |
| [0045](0045-generiertes-eingebettetes-artefakt-fuer-cross-stack-abbildung.md) | Ein generiertes, kompilierzeit-eingebettetes Artefakt (`go:embed` + Erzeuger-Skript) löst Cross-Stack-Duplikate — nicht nur ein erweiterter Paritätstest (ergänzt 0015 Regel 3, Issue #1435 Etappe E5) | Akzeptiert |
| [0046](0046-alarm-kanal-schwelle.md) | Kanal-Schwelle regelt AUF WELCHEM WEG eine Meldung ankommt — nicht OB (ergänzt 0043, Issue #1461 S3b-2a) | Akzeptiert |
| [0047](0047-gewitter-vertretung-zwischen-direktquellen.md) | Gewitter-Vertretung zwischen Direktquellen bei echtem Dienstausfall — dehnt 0018 auf die Gewitter-Domäne aus, grenzt sich von 0025 ab (Issue #1492 Scheibe 2a) | Akzeptiert |
| [0048](0048-modellabhaengige-schwellen-statt-einer-zahl.md) | Feste Schwellen werden nie über Modellgrenzen getragen — CAPE-Schwelle je Modell × Gebiet, geeicht am 95. Perzentil der Modellklimatologie (mind. 300 J/kg); unbekannte Herkunft heißt „keine Aussage" (Issue #1592 Scheiben B0+C0+C1) | Akzeptiert |
| [0049](0049-premium-sms-vierter-kanal.md) | Premium-SMS (Garmin inReach) ist ein vierter, eigenständiger Kanal `premium_sms` — kein SMS-Sonderfall (schreibt 0004 fort, Issue #1676 S2a) | Akzeptiert |
| [0050](0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md) | Die Metrik-Kaskade ist eine Verfeinerung, nicht eine Ersetzung — die Grundauswahl ist das Maximum, Kanal-Ebenen dürfen nur abwählen (Issue #1719 S1) | Akzeptiert |
| [0051](0051-drei-zeitbegriffe-zone-an-den-daten.md) | Drei Zeitbegriffe statt einem (Zeitpunkt / Kalenderzeit / Zone); die Zone gehört an die Daten, nicht an den Server; keine Umgebungsuhr — ordnet 0044 als Spezialfall ein, 0035 unberührt (Analyse `docs/analysis/zeitzonen-architektur-2026-08.md`) | Vorgeschlagen |
| [0052](0052-warnmail-nowcast-bauform-eigener-klartext.md) | Amtliche Warn-Mail übernimmt die Nowcast-Datenzeilen-Bauform und bekommt einen eigenen Klartext-Teil (schreibt 0033 fort, Issue #1744 Scheibe A2) | Akzeptiert |
| [0053](0053-compare-kanal-eigene-metrikauswahl-uebersicht.md) | Der Ortsvergleich bekommt kanal-eigene Metrikauswahl für die Übersichtstabelle zurück — ganze Kette statt Oberfläche allein (löst #1287/#1291/#1351 ab, schreibt 0050 fort, Issue #1703 Scheibe 8) | Akzeptiert |
| [0054](0054-playwright-e2e-in-ci-ampel-positivliste.md) | Playwright-E2E-Klickpfade in die CI-Ampel — isolierter Stack, Positivliste statt Ausschlussliste (schreibt 0006/0028 fort, Issue #1771 Scheibe 2) | Akzeptiert |
| [0055](0055-trip-ausblick-waehlbare-spalten.md) | Die 3-Tages-Vorschau des Trip-Briefings bekommt wählbare Spalten — global ohne Kanal-Ebene, an die Grundauswahl gebunden, EINE Auflösung statt drei (löst 0037 Punkt 2 ab, schreibt 0050 fort, Issue #1720 Scheibe 1) | Akzeptiert |
| [0056](0056-rollierender-alarm-anker-statt-briefing-only-snapshot.md) | Der Δ-Vergleichsanker ist nicht mehr ausschließlich an einen erfolgreichen Briefing-Versand gebunden, sondern rollt zusätzlich bei jedem Alarmversand und bei Überschreiten einer Alterungs-Ceiling nach (löst Teil von 0009 ab, Issue #1916) | Akzeptiert |
| [0057](0057-mehrere-gewitter-signalquellen-je-gebiet.md) | Mehrere Gewitter-Signalquellen je Gebiet sind additiv erlaubt — GeoSphere (cape/cin) ergänzt für Österreich den DWD, ohne ihn zu verdrängen (ergänzt 0025/0047, Issue #1758) | Akzeptiert |
| [0058](0058-wegpunkt-hoehe-an-provider-api.md) | Wegpunkt-Höhe wird an die Provider-Schnittstelle durchgereicht — keine eigene Höhenphysik, kein Transparenzhinweis im Briefing (schreibt 0018 fort, Issue #1991) | Akzeptiert |
