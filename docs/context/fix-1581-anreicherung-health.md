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

---

## Analysis (Phase 2)

### Type
Bug (fehlende Folgepflicht aus ADR-0018) — umzusetzen als additive Beobachtbarkeit.

### Entscheidung 1: eigener Top-Level-Kanal `enrichment_health`

**Empfehlung: eigener Kanal**, strukturell wie `warn_service_health` — ein neues
Top-Level-Feld in `internal/scheduler/scheduler.go:830f`, eigener Aggregator, eigenes
Journal. NICHT als zusätzliche Schlüssel innerhalb von `briefing_health`.

Begründung: `check-gregor20.sh` liest `briefing_health` als „ist das Briefing gesund".
Zusätzliche Schlüssel dort zwingen jeden künftigen Leser, zwischen briefing-kritischen und
nicht-kritischen Schlüsseln **innerhalb desselben Objekts** zu unterscheiden — die
Vermengung, vor der ADR-0018 warnt. Ein eigenes Objekt macht die Trennung strukturell statt
konventionell. Präzedenzfall existiert: `warn_service_health` ist genau so ein eigener
Kanal für einen nicht-briefing-kritischen Dienst.

Wichtig: **keine eigene Schwere-Berechnung in Go.** Sonst gäbe es drei Muster für dieselbe
Frage („wie lange schon degradiert").

### Entscheidung 2: Rohdaten — der Widerspruch im Ticket ist auflösbar

Der Issue-Text („analog `provider_error_streak_since`") und AC-S2-4 („Schwellen bleiben
außerhalb") widersprechen sich nur scheinbar. „Mit der Ausfalldauer wachsen" ist eine
Aussage über die **Wirkung**, nicht über die **Bauart**: `last_success_at` wächst
automatisch, sobald außen `jetzt − last_success_at` gebildet wird — genau das tut
`check-gregor20.sh:495-497` heute für `warn_service_health`.

**Empfehlung: Rohdaten** (`last_attempt_at`, `last_success_at`, `last_fallback_at`,
`self_throttled`), keine Streak-Rechnung in Go. Der Streak-Bauart steckt eine feste
2 h-Lücken-Schwelle **innen** (`briefing_health.go:404`); die ist beim Briefing sinnvoll,
beim Radar mit seinem Cache aber schwer zu wählen und nur per Deploy korrigierbar.

Preis: „wächst mit der Dauer" ist dann keine in diesem Repo testbare Eigenschaft mehr,
sondern eine der externen Auswertung. Genau das verlangt AC-S2-4.
Diese Auflösung gehört als Entscheidungssatz ins ADR-0047-Addendum, sonst wird der
scheinbare Widerspruch bei der nächsten Lesung erneut aufgemacht.

### Entscheidung 3: eigenes Journal, kein `call_log.py`-Ausbau

`call_log.py` ist an HTTP-Abrufe gegen Open-Meteo gebunden: Quellenerkennung über
Aufrufer-Stack-Marker (Z. 44-56), Schema `{ts, endpoint, status, source, error}`.
Weder die Gewitter-Vertretung (kein Open-Meteo-Request) noch der Radar-Fall (fünf Quellen
über verschiedene Fetch-Pfade) passen hinein. Schwerwiegender: `call_log` schreibt nach
`openmeteo_calls.jsonl` — **dieselbe Datei, die `briefing_health` liest**. Ein Ausbau dort
würde `coreBriefingSources` berühren und genau die Vermengung erzeugen, die vermieden
werden soll.

Stattdessen neues Modul analog `warn_egress.py:304-346`, Journal
`data/diagnostics/enrichment_calls.jsonl`, Pfad bei **jedem** Aufruf über
`get_data_root()` aufgelöst (Falle #1633: Modulkonstante bindet vor der Testfixture).

### Der gemeinsame Baustein (AC-S2-3)

Ein Schreibweg, zwei Aufrufer:

```
log_enrichment_call(path, outcome, detail=None)
  path:    "thunder" | "radar_nowcast"
  outcome: "ok" | "fallback" | "unavailable" | "self_throttled"
```

Der Dreischnitt „gelungen / gescheitert / selbst gedrosselt" existiert in beiden Pfaden
bereits fachlich — Radar trennt ihn heute schon (`radar_service.py:559` vs. `:567-571`),
Gewitter kennt zusätzlich „Vertretung sprang ein".

Go-Seite: `internal/scheduler/enrichment_health.go` mit `aggregateEnrichmentCalls()` und
`EnrichmentHealth()`, gruppiert nach `path`, Schema 1:1 wie `WarnServiceHealth()`
(`nilIfEmpty`, fehlende Datei ≠ Fehler, `journal_read_error` nur bei echtem Lesefehler).

### 🔴 Befund beim Gegenprüfen: ein stiller Rückzug, den das Ticket nicht kennt

`thunder_enrichment.py:406-409` — fällt die Primärquelle aus und ist **keine** Vertretung
verfügbar (oder die Vertretung wurde bereits befragt), kehrt die Funktion **wortlos**
zurück: kein Marker, kein `fallback_model`, **nicht einmal ein `logger.warning`**.
Der im Issue genannte `logger.warning` (Z. 281) greift nur, wenn eine Ausnahme bis nach
außen propagiert — also wenn die Vertretung es *versucht* und scheitert.

Damit ist der blindeste Fall nicht der beschriebene, sondern dieser. Er gehört als
`outcome="unavailable"` ins Journal.

Die Funktion hat fünf Ausgänge, nicht drei: stiller Rückzug (Z. 407-409), leere Antwort
(Z. 414), nichts gefüllt (Z. 418), Erfolg mit Primärquelle (Z. 421-426), Erfolg über
Vertretung (Z. 428-441) — plus die nach außen propagierende Ausnahme.

### Zwei Fallen, gegengeprüft und bestätigt

1. **Cache-Verzerrung im Radar-Pfad ist real.** `_derive_result()` wird bei Cache-Hit
   (`radar_service.py:205`) **und** Cache-Miss (`:219`) aufgerufen. Ein dort platzierter
   Journal-Aufruf würde jeden Cache-Hit als „ok" buchen — ein Dauerausfall, der aus dem
   Cache weiterbedient wird, sähe lebendig aus. Der Aufruf gehört in `get_nowcast()` in
   den Miss-Zweig, nicht in `_derive_result()`.
2. **Fail-soft braucht einen eigenen inneren Fang.** Läuft der Journal-Aufruf im
   bestehenden `except Exception` von `enrich_thunder()` (Z. 279-281) mit, verschleiert ein
   Diagnosefehler einen echten Anreicherungsfehler. Eigener `try/except Exception: pass`
   je Schreibaufruf, wie `warn_egress.py:329-347`.

### 🔴 Ehrliche Einschätzung zu AC-S2-2

In der empfohlenen Bauart ist AC-S2-2 („ein Ausfall meldet nicht Briefing-Ausfall")
**strukturell trivial wahr**: getrennte Journale und getrennte Aggregatoren haben gar
keinen gemeinsamen Codepfad, über den sich das eine ins andere durchschlagen könnte.
Ein Test, der das prüft, bewacht nichts.

Vorschlag für einen Test, der wirklich etwas fängt: ein Wächter über `coreBriefingSources`
selbst — die Map enthält **genau** `{briefing, briefing_nacht}`. Trägt jemand später eine
Anreicherungsquelle dort ein, wird er rot. Das ist die Mutation, die im Betrieb wehtut,
und der einzige Weg, auf dem die Grenze noch fallen kann.

### Scope

| Datei | Aktion | LoC (ca.) | Scheibe |
|---|---|---|---|
| `src/providers/enrichment_health.py` | CREATE | 60-80 | 1 |
| `src/providers/thunder_enrichment.py` | MODIFY (5 Ausgänge) | 20-25 | 1 |
| `tests/tdd/test_thunder_enrichment_health_journal.py` | CREATE | 120-150 | 1 |
| `internal/scheduler/enrichment_health.go` | CREATE | 130-160 | 1 |
| `internal/scheduler/enrichment_health_test.go` | CREATE | 150-200 | 1 |
| `internal/scheduler/briefing_health_test.go` | MODIFY (Wächter über `coreBriefingSources`) | 20-30 | 1 |
| `internal/scheduler/scheduler.go` | MODIFY (ein Schlüssel) | 1-2 | 1 |
| `src/services/radar_service.py` | MODIFY (Miss-Zweig) | 15-25 | 2 |
| `tests/tdd/test_radar_nowcast_health_journal.py` | CREATE | 100-140 | 2 |
| `internal/scheduler/enrichment_health_test.go` | MODIFY (Radar-Fälle) | 60-80 | 2 |
| `docs/adr/0047-*.md`, `docs/adr/0018-*.md` | MODIFY (Addendum) | 30-45 | 1+2 |

**Summe ohne Doku: ~700-900 LoC.** Das Limit von 500 reicht nicht; auf 900 anzuheben ist
ehrlicher, als den Nachweis zu verkürzen. Der Löwenanteil sind Tests.

Reihenfolge: Scheibe 1 bringt den **vollständigen** gemeinsamen Baustein; Scheibe 2 fügt
nur den zweiten Aufrufer und Testfälle hinzu — kein zweiter Mechanismus.

### Repo-übergreifend

`henemm-infra/scripts/check-gregor20.sh` braucht einen eigenen Abschnitt. Anreicherung ist
**nicht** briefing-kritisch, also:
- `fallback` erfolgreich / `self_throttled` → höchstens Soft-WARN, kein Heartbeat-Block
- `unavailable` über ein **langes** Frischefenster (24-48 h, nicht die 3 h des
  Warn-Dienstes) → EXT-FAIL, sichtbar, aber ohne „Gregor ist down"
- CORE nur bei `journal_read_error` (unser eigener Fehler, analog `warn_service_health`)

Das lange Fenster ist fachlich begründet: der Issue-Text nennt selbst „drei Tage
Dauerausfall sind ein Befund" — Tage, nicht Stunden.

Die Änderung dort geht per MQ an `infra`, inhaltlich nach Scheibe 1 abgestimmt, final nach
Scheibe 2.

### Open Questions (PO)

- [ ] Entscheidungen 1-3 bestätigen
- [ ] AC-S2-2 durch den `coreBriefingSources`-Wächter ersetzen?
- [ ] LoC-Limit auf 900
