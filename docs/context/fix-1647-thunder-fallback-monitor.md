# Context: fix-1647-thunder-fallback-monitor

## Request Summary

Issue #1647 hat nach der Messung vom 09.09.2026 einen neuen Inhalt: Der Météo-France-Zugang
trägt, der Dauer-401 ist nicht reproduzierbar — aber **ein dauerhafter Rückfall der
Gewitter-Direktquelle auf die Vertretung `eu_direct` ist im Betrieb unsichtbar**. Er steht im
Journal und im Status-Endpunkt, löst aber keinen Alarm aus. Ziel: den Betreiber-Alarm bauen,
den Spec #1581 ausdrücklich an `henemm-infra/scripts/check-gregor20.sh` delegiert hat — und
der dort nie angekommen ist.

## Befund (gemessen 2026-09-17)

| Ebene | Stand | Fundstelle |
|---|---|---|
| Schreibseite Python | ✅ vorhanden — `outcome=fallback`, `detail=<Ersatzquelle>` | `src/providers/thunder_enrichment.py:561` |
| Aggregation Go | ✅ vorhanden — `last_attempt_at`/`last_success_at`/`last_fallback_at`/`self_throttled` je Pfad; **`detail` wird gelesen, aber NICHT ausgegeben** | `internal/scheduler/enrichment_health.go:35-40, 152-171` |
| Status-Endpunkt | ✅ `enrichment_health` als Top-Level-Schlüssel in `/api/scheduler/status` | Prod-Abfrage 17.09.: Pfade `thunder`, `thunder_additive`, `radar_nowcast`, `snowgrid`, `forecast_capture` |
| Nutzer-Sichtbarkeit | ✅ Vertretungshinweis in Mail/Telegram (#1492 S2b) | `src/output/renderers/fallback_notice.py` |
| **Betreiber-Alarm** | ❌ **fehlt** — `check-gregor20.sh` enthält keinen einzigen Treffer für `enrichment` | `henemm-infra/scripts/check-gregor20.sh` |
| Ticket in infra | ❌ keins (`gh issue list -R henemm/henemm-infra --search enrichment` leer) | — |

Die Go-Datei sagt in ihrem eigenen Kommentar (`enrichment_health.go:143-151`): *„no threshold decision
… formed by check-gregor20.sh, exactly like the existing warn_service_health pattern."* Die
Spec #1581 (Known Limitations, Z. 347-353) legt fest: *„Die Auswerteregel in check-gregor20.sh
ist NICHT Teil dieser Spec … geht per MQ an die infra-Instanz."* Es gibt keine Spur, dass diese
Nachricht je gesendet oder umgesetzt wurde. Die Kette ist damit seit 2026-08-20 an der letzten
Stelle unterbrochen.

## Related Files

| File | Relevance |
|------|-----------|
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` (Block 2d, Z. 417-540) | **Vorbild und Einbauort**: `warn_service_health`-Auswertung mit CORE/EXT/SOFT-Klassen, `age_hours()`, 3-h-Fenster, `attempt_age > 3 → continue` |
| `/home/hem/henemm-infra/tests/test_check_gregor20_logparse.py` | Testharness-Muster: extrahiert Skripttext per Regex, prüft gegen die ECHTE Funktion, `python3 -m pytest tests/…` |
| `internal/scheduler/enrichment_health.go` | Aggregat; Kandidat für `last_fallback_detail` (Ersatzquelle mit ausgeben) |
| `internal/scheduler/enrichment_health_test.go` | 11 Tests, Muster für neuen Feldtest |
| `internal/scheduler/warn_service_health.go:163` | `nilIfEmpty` — geteilter Helfer |
| `src/providers/enrichment_health.py` | Journal-Schreiber, Vokabular `ok/fallback/unavailable/self_throttled`, `detail` |
| `src/providers/thunder_enrichment.py:495-565` | alle Ausgänge schreiben eine Journalzeile; Fallback mit `aktive_quelle` |
| `src/providers/thunder_routing.py:176-186` | `_VERTRETUNG`: `de_direct→eu_direct`, `fr_direct→eu_direct`, `eu_direct→None` |
| `docs/reference/api_contract.md` | Feldbeschreibung `enrichment_health` — bei neuem Feld nachziehen |

## Existing Patterns

- **Block 2d in `check-gregor20.sh`**: Inline-Python liest `SCHED_RESPONSE`, gibt drei Zeilen
  `CORE_FAIL:/CORE_OK`, `EXT_FAIL:/EXT_OK`, `SOFT_WARN:/SOFT_OK` aus; die Shell zählt
  `CORE_ERRORS`/`EXT_ERRORS`. Regel: **Anbieterausfall → EXT**, `journal_read_error` → **CORE**
  („das ist unser Fehler"). Fehlender Block = Normalfall, nie Fehler. Frische entscheidet über
  Zeitstempel, nie über kumulative Zähler (Fallstricke 1-3 im Kommentar).
- **Fenster**: Warn-Dienst 3 h (briefing-kritisch). Spec #1581 empfiehlt für Anreicherung
  **24-48 h** — sie ist nicht briefing-kritisch, das Briefing läuft mit Vertretung weiter.
- **Go-Aggregat ohne Schwelle**: `EnrichmentHealth()` gibt nur Rohzeitstempel; „wächst mit der
  Ausfalldauer" ist Eigenschaft von `jetzt − last_success_at`, gebildet außen.
- **Infra-Test**: `_extract_function()` holt Shell-Funktionen wörtlich aus dem Skript. Für den
  Inline-Python-Block muss analog der Python-Text zwischen den Anführungszeichen extrahiert und
  mit synthetischem JSON auf stdin ausgeführt werden.

## Dependencies

- **Upstream** (was der Check liest): `/api/scheduler/status` → `enrichment_health.<path>`
  mit `last_attempt_at`, `last_success_at`, `last_fallback_at`, `self_throttled`;
  optional `journal_read_error`. Nach dieser Arbeit zusätzlich `last_fallback_detail`.
- **Downstream** (wer den Check konsumiert): BetterStack-Heartbeats CORE/EXT — `EXT_ERRORS > 0`
  lässt den EXT-Heartbeat ausbleiben → E-Mail-Alert an den PO.

## Existing Specs

- `docs/specs/modules/fix_1581_enrichment_health.md` — Health-Signal (Schreib-/Leseseite),
  Known Limitation zur Auswerteregel (Z. 347-353) — **das ist die Lücke**
- `docs/specs/modules/feat_1992_geosphere_health_amendment.md` — Z. 310-317, gleiche Empfehlung
  für `snowgrid`/`thunder_additive`: langes Fenster, EXT statt CORE
- `docs/specs/modules/feat_1492_s2a_thunder_vertretung.md` / `_s2b_fallback_sichtbarkeit.md` —
  Vertretung + Nutzerhinweis
- `docs/specs/fast/mess-1647-mf-coverage.md` — Messscheibe 09.09. (Zugang trägt)
- ADR-0018 (Nicht-Kaschieren, wachsendes Health-Signal), ADR-0047 + Addendum (Vertretung, Schwelle außerhalb des Repos)

## Risks & Considerations

- **Zwei Repos.** Der Alarm lebt in `henemm-infra`, das Zusatzfeld in `gregor`. Die
  infra-Änderung wird selbst ausgeführt (gleicher Server, gleicher User) — keine MQ. Der
  gregor-Workflow-Gate bewacht den infra-Commit nicht; Nachweis dort über den pytest-Harness.
- **Prod kann den Fall gerade nicht zeigen**: `thunder.last_attempt_at` = 05.09. (Tourende
  KHW, kein aktiver Trip). Nachweis nur synthetisch (JSON in den Inline-Block) + Mutationsprobe
  (Fenster/Bedingung verfälschen → Test muss rot werden).
- **Pfad-Aggregation kennt keine Region.** `thunder` mischt DE- und FR-Abrufe. Ein DE-Trip mit
  Erfolg hält `last_success_at` frisch, während FR dauerhaft auf `eu_direct` läuft — der Alarm
  bliebe stumm. Bekannte Grenze (Spec #1581: „Ausfall sichtbar, nicht welche Quelle"); im
  Ein-Touren-Betrieb irrelevant, für Multi-Region als Known Limitation festhalten.
- **`detail` heißt Ersatzquelle, nicht Primärquelle.** `last_fallback_detail=eu_direct` sagt
  „läuft auf DWD Europa", nicht ob `fr_direct` oder `de_direct` ausfiel. Reicht für den Alarm.
- **Fehlalarm-Falle**: Ohne `attempt_age`-Bedingung würde jeder tourlose Zeitraum alarmieren.
  Bedingung muss sein: Versuch innerhalb des Fensters UND kein `ok` innerhalb des Fensters.
- **Ticket-Titel** von #1647 trifft den Ist-Stand nicht mehr — Umbenennung ist Teil der Lieferung.

## Analysis

### Type
Bug — die mit #1581 versprochene Alarmkette (ADR-0018 „wachsendes Health-Signal") endet vor
dem Betreiber: `check-gregor20.sh` wertet `enrichment_health` nicht aus.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/enrichment_health.go` | MODIFY | `lastFallbackDetail` im Aggregat (jüngste Ersatzquelle), Ausgabe `last_fallback_detail` |
| `internal/scheduler/enrichment_health_test.go` | MODIFY | Test: Feld trägt die jüngste Ersatzquelle, `nil` ohne Fallback |
| `docs/reference/api_contract.md` | MODIFY | Feldbeschreibung `enrichment_health.<path>.last_fallback_detail` |
| `henemm-infra/scripts/check-gregor20.sh` | MODIFY | Block **2e** nach Muster 2d: generisch über alle Pfade, Fenster 48 h, EXT/CORE-Zuordnung |
| `henemm-infra/tests/test_check_gregor20_enrichment_health.py` | CREATE | Extraktion des Inline-Python-Blocks aus der echten Skriptquelle + 6 Fälle |

### Scope Assessment
- gregor: 3 Dateien, ~+35 LoC (Go + Test; Doku zählt nicht) — weit unter 250
- infra: 2 Dateien, ~+80 Skript / ~+110 Test
- Risk Level: MEDIUM (Alarmpfad; Fehler = Fehlalarm oder Blindheit)

### Technical Approach
1. **Go zuerst**: Feld `last_fallback_detail` (Ersatzquelle der jüngsten `fallback`-Zeile,
   `nil` ohne Fallback). Reihenfolge ist technisch unkritisch, weil das Skript das Feld
   defensiv liest (`info.get(...)`), aber so gibt es nie eine Phase mit generischem Text.
2. **Block 2e in `check-gregor20.sh`** direkt nach 2d (vor dem Heartbeat-Gate Z. 1276-1284),
   derselbe `EXT_ERRORS`/`ERRORS`-Zähler mit `(( … )) || true`-Idiom (`set -euo pipefail`, Z. 17),
   try/except-Mantel wie 2d. Iteration `for name, info in eh.items()` — neue Pfade erscheinen
   automatisch (Go-Aggregator ist bereits generisch, #1992 AC-8).
   Bedingung je Pfad: `attempt_age None or > 48 → continue` (kein aktiver Trip = kein Alarm);
   sonst `success_age None or > 48 → EXT_FAIL`. Text: `fallback_age ≤ 48` →
   „läuft seit Xh nur über Vertretung (<last_fallback_detail>)"; sonst „kein Signal seit Xh
   (Anbieter nicht erreichbar | Gregor bremst sich selbst (Kontingent))". `journal_read_error`
   → CORE. Fehlendes `enrichment_health` (alter Scheduler) → still leer, nie Fehler.
3. **Fenster 48 h** (Spec-#1581-Empfehlung 24–48 h): `thunder` wird nur je Tick bei aktivem
   Trip abgerufen; bei ~1 Abruf/Tag plus Jitter fiele `attempt_age` mit 24 h zwischen zwei
   Ticks in die `continue`-Blindheit — genau dann stumm, wenn der Alarm greifen soll. Kosten:
   bis zu 1 Tag spätere Erkennung; Anreicherung ist nicht briefing-kritisch (Briefing läuft mit
   Vertretung weiter), Warn-Dienst hat bewusst 3 h, weil dort das Briefing hängt.
4. **Test im infra-Repo**: Inline-Block per Regex `python3 -c "((?:[^"\\]|\\.)*)"` (DOTALL)
   aus der echten Skriptquelle holen (innere `"` sind als `\"` escaped), `subprocess.run`
   mit synthetischem JSON auf stdin. Fälle: (a) frischer Fallback → Vertretungstext mit Detail,
   (b) Dauerausfall ohne Fallback → „kein Signal", (c) gesund trotz altem Fallback → EXT_OK,
   (d) kein aktiver Trip → EXT_OK trotz altem Fallback (Blindheits-Gegenbeweis),
   (e) `journal_read_error` → CORE, nicht EXT, (f) `self_throttled` → „Kontingent".
   Mutationsprobe: Fenster verkleinern → (a) rot; Erfolgs-Bedingung invertieren → (c) rot.
5. Ticket #1647 umbenennen (Ist-Stand: „Dauerhafter Gewitter-Rückfall auf `eu_direct` ohne Alarm").

### Dependencies
- Upstream: `/api/scheduler/status.enrichment_health` (Go, gregor) — additive Erweiterung
- Downstream: BetterStack-EXT-Heartbeat (bleibt aus bei `EXT_ERRORS > 0`)
- Deploy: gregor per PR → Staging → Prod; infra per Commit auf `main` (Cron zieht das Skript)

### Open Questions
- keine — Fenster (48 h) und Zuordnung (EXT/CORE) folgen der bereits in Spec #1581 dokumentierten Empfehlung
