# Context: fix-1581-anreicherung-health

Issue #1581 · beide Scheiben (Gewitter-Direktquellen + Radar-Nowcast) · Full Process
Basis `21ace02e` · Worktree `intake-1493`

## Request Summary

Zwei degradierbare Datenpfade tragen zwar einen Marker in den Daten, aber es gibt keine
Stelle, an der ein **andauernder** Ausfall auffällt — die von ADR-0018 geforderte zweite
Hälfte („wachsendes Health-Signal") fehlt. Beide Pfade sollen ein Signal bekommen, das
mit der Ausfalldauer wächst und über `/api/scheduler/status` nach außen führt — ohne die
Unterscheidung „Kern-Briefing vs. Anreicherung" zu beschädigen.

## Ist-Zustand: die beiden blinden Pfade

| Pfad | Marker in den Daten | Ausfall heute sichtbar durch | Diagnose-Journal |
|---|---|---|---|
| Gewitter-Direktquellen (`de_direct`/`fr_direct` → `eu_direct`) | `ForecastMeta.fallback_model` / `_reason` / `_metrics` | nur `logger.warning` (`thunder_enrichment.py:281`) | **keins** |
| Radar-Nowcast | `NowcastResult.data_unavailable` (`radar_service.py:567-571`) | nur `logger.warning` | **keins** |

Beide Behauptungen des Issues sind verifiziert: weder `thunder_enrichment.py` noch
`radar_service.py` schreiben einen `call_log`-Eintrag. `call_log.py` protokolliert
ausschließlich Open-Meteo-Abrufe.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/providers/thunder_enrichment.py:377-439` | `_fetch_primaerquelle()` — **die** Vertretungsstelle: `except ThunderSourceUnavailableError` (Z. 405) → `thunder_vertretung_for(quelle)` (Z. 406). Genau ein Ansatzpunkt, kein verteilter Fall |
| `src/providers/thunder_enrichment.py:281` | der bekannte `logger.warning` — heute einziger Beobachtungspunkt, selbst unbewacht (F003 in #1199) |
| `src/providers/thunder_routing.py:50, :73-77, :178-182` | Regionen (KHW namentlich in Z. 50, fällt in `DE_ALPEN` → Primärquelle `de_direct`), Vertretungstabelle `_VERTRETUNG` |
| `src/services/radar_service.py:559, :567-571` | trennt bereits **eigene Drosselung** (`throttled`) von **echtem Anbieterausfall** (`data_unavailable`) — fachlich dieselbe Unterscheidung wie `self_throttled` im Vorlagemuster |
| `src/services/radar_service.py:201-207, :427, :442` | Cache-Hit/-Miss und Budget-Gate — bestimmt, wann überhaupt ein echter Abruf stattfindet |
| `src/services/official_alerts/warn_egress.py:186-192, :304-346` | **Vorlage Schreibseite:** `log_warn_service_call()`, fail-soft, Pfad über `get_data_root()` |
| `internal/scheduler/warn_service_health.go:35-40, :81-159, :262-310` | **Vorlage Leseseite:** Aggregation und Ausgabe-Map |
| `internal/scheduler/briefing_health.go:24-35, :51-59` | `coreBriefingSources` + `isBriefingProviderError()` — die Grenze, die nicht verletzt werden darf |
| `internal/scheduler/briefing_health.go:404, :416-474` | `provider_error_streak_since` — zweites, konkurrierendes Muster (Streak-Rechnung in Go, Gap-Schwelle 2 h) |
| `internal/scheduler/scheduler.go:830-831` | wo das Signal in `/api/scheduler/status` eingehängt wird |
| `henemm-infra/scripts/check-gregor20.sh:411-554` | externe Eskalationsleiter (CORE blockt Heartbeat / EXT / Soft-WARN), 3 h-Frischefenster |

## Existing Patterns

### Das Vorlagemuster (`warn_service_health`) end-to-end

1. **Schreiben:** `log_warn_service_call()` schreibt bei **jedem** Durchlauf eine JSONL-Zeile
   (`ts, service, host, status, cache_hit, retry_after, ok, self_throttled`), fail-soft —
   jeder Schreibfehler wird geschluckt, Diagnose darf den Abruf nie beeinträchtigen.
   Bemerkenswert: `ok` ist eine **fachliche** Aussage, kein HTTP-Status — ein 404
   „nicht zuständig" zählt als Erfolg (`warn_egress.py:565`).
2. **Aggregieren:** `aggregateWarnServiceCalls()` liest das Journal, verwirft Cache-Hits und
   Alt-Zeilen ohne `ok`-Feld, gruppiert auf kanonische Servicenamen und liefert je Dienst
   `last_attempt_at` / `last_success_at` (`nil`, nie `""`) plus Fahnen.
   Fehlende Datei ≠ Fehler; nur ein echter Lesefehler setzt `journal_read_error`.
3. **Auswerten:** außerhalb dieses Repos, in `check-gregor20.sh`.

### Test-Vorbilder

- Go: `internal/scheduler/briefing_health_test.go` — Helfer `newBriefingHealthTestScheduler()`
  (Z. 28-51), `writeDiagnosticsLog()` (Z. 261-272), `callStatusEndpoint()` (Z. 70-87).
  Die Tests schreiben echte JSONL-Zeilen in ein `t.TempDir()` und gehen per `httptest` durch
  den echten Endpunkt — kein Mock-Theater, direkt kopierbar.
- Go: `internal/scheduler/warn_service_health_test.go:52-430` — insbesondere
  „Dienst ohne Abruf taucht gar nicht auf" (Z. 88-103) und „unlesbares Journal ≠ fehlendes
  Journal" (Z. 404-430).
- Python: `tests/tdd/test_warn_service_health_journal.py:84-196` — sechs Tests, die die
  Semantik von `ok`/`self_throttled` festnageln (Anbieterfehler vs. Selbstdrosselung).

## Dependencies

- **Upstream (was wir benutzen):** `app.loader.get_data_root()` für den Journalpfad;
  `thunder_routing.thunder_vertretung_for()` für die Ersatzquelle; das Budget-Gate im
  Radar-Dienst für die Drosselungs-Unterscheidung.
- **Downstream (was uns benutzt):** `/api/scheduler/status` → `check-gregor20.sh` in
  `henemm-infra` → BetterStack-Heartbeat. Eine Änderung an den Schlüsselnamen wirkt
  **repo-übergreifend**; die Auswerteregel dort muss nachgezogen werden (MQ an `infra`).

## Existing Specs & ADRs

- `docs/adr/0018-provider-fallback-ohne-kaschieren.md:29-33` — die Folgepflicht selbst,
  **inklusive ausdrücklicher Warnung**, die Gewitterquelle nicht in `coreBriefingSources`
  einzutragen.
- `docs/adr/0047-gewitter-vertretung-zwischen-direktquellen.md:137-140` — vertagt die Pflicht
  und benennt #1581 namentlich. Hier gehört die Entscheidung als Ergänzung hinein.
- `docs/specs/modules/feat_1492_s2a_thunder_vertretung.md:397-406` — Known Limitations 2,
  der ursprüngliche Vertagungsvermerk.

## Risks & Considerations

1. **🔴 Zwei konkurrierende Vorbilder — muss in Phase 2 entschieden werden.**
   Der Issue-Text (Punkt 3) verlangt „mit der Ausfalldauer wachsen: analog
   `provider_error_streak_since`" — das rechnet den Streak **in Go**.
   Der PO-Kommentar (AC-S2-4) verlangt „Schwellenwert-Auswertung bleibt außerhalb dieses
   Repos (Muster `warn_service_health`)" — das liefert nur **Rohdaten**.
   Beides zugleich geht nicht wörtlich. Auflösung und Empfehlung gehören in die Analyse.
2. **Die Grenze Kern/Anreicherung ist scharf bewacht** — und das ist gut so:
   `TestBriefingHealthEnrichmentSourceIsNotBriefingOutage`
   (`briefing_health_test.go:458-484`) prüft per echtem HTTP-Roundtrip, dass ein 503 auf
   `ensemble`/`vergleich` **keinen** Briefing-Ausfall meldet. Dieser Test darf nicht
   aufgeweicht werden; AC-S2-2 baut auf ihm auf.
3. **Ein gemeinsamer Baustein für zwei Pfade (AC-S2-3)** — die Pfade sind ungleich:
   Gewitter kennt „Primärquelle weg, Vertretung sprang ein", Radar kennt „gar keine Daten".
   Der gemeinsame Nenner ist „Abruf einer Anreicherungsquelle: gelungen / gescheitert /
   selbst gedrosselt". Genau dieser Dreischnitt existiert im Vorlagemuster bereits.
4. **Fail-soft ist Pflicht.** Beide Pfade liegen im Live-Briefing- und Alarm-Weg
   (Gewitter: jeder Briefing- und Alarm-Abruf; Radar: `/jetzt` plus Alarm-Polling).
   Eine Diagnose, die eine Ausnahme wirft, wäre schlimmer als gar keine.
5. **Frequenz-Verzerrung durch Cache.** Der Radar-Dienst beantwortet viele Anfragen aus dem
   Cache. Zählt man Cache-Hits mit, sieht ein Dauerausfall harmlos aus. Das Vorlagemuster
   löst das über das Feld `cache_hit` plus Filterung auf der Leseseite — übernehmen.
6. **Journal-Wachstum.** Ein weiteres append-only JSONL im Datenverzeichnis; Rotation/Größe
   ist in Phase 2 zu prüfen (wie hält es `warn_service_calls.jsonl`?).
7. **Nachbarschaft zu #1948 S4:** dieselbe Datei `radar_service.py` wird dort gelesen
   (`onset_time`, ~Z. 274). Zeitformat und `onset_minutes` bleiben unberührt — abgestimmt.
8. **Nebenbefund aus #1197 (von Peer gemeldet):** `staging_gate.py` stuft Backend-Änderungen
   gelegentlich fälschlich als `docs-only` ein. Beim Deploy Scope selbst gegenprüfen.
