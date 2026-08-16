# Context: #1765 B1b — Versand + Sofortvergleich parallel

**Workflow:** `fix-1765-b1b-versand-parallel` · **Issue:** #1765 (B1b schliesst es) ·
**Erstellt:** 2026-08-16 · **Basis:** `098226ae` (B1 live)

## Request Summary

Die beiden verbliebenen Aufrufstellen von `ComparisonEngine.run()` — **Versand**
(`src/services/scheduler_dispatch_service.py:451`, laeuft auch unbeaufsichtigt per Cron)
und **Sofortvergleich** (`api/routers/compare.py:71`) — auf den in Scheibe B1 gelieferten,
signaturgleichen Baustein `run_comparison_parallel()` umstellen. Damit verarbeiten alle
drei Wege die Orte gleichzeitig statt nacheinander; der 60-s-nginx-Timeout aus #1765
faellt auch fuer Versand (gemeldet: 504 bei 4 Orten) und Sofortvergleich.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/comparison_parallel.py` | Der Baustein (B1, live). Signaturgleich zu `ComparisonEngine.run` + keyword-only `call_source`. `MAX_PARALLEL_LOCATIONS = 4` (Z.42) |
| `src/services/scheduler_dispatch_service.py:350-572` | `send_one_compare_preset()` — Versandpfad, **Aufrufstelle 1** (Z.451) |
| `api/routers/compare.py:26-77` | `run_comparison()` (`GET /api/compare`) — **Aufrufstelle 2** (Z.71), bereits plain `def` |
| `src/services/compare_preview_service.py:144,170-178` | Vorlage: so ruft B1 den Baustein auf (`call_source="vergleich"`, lokaler Import) |
| `src/services/official_alerts/warn_egress.py:296-379` | `cached_fetch()` — geteilter Kern **aller 7** Amtswarn-Quellen, **ohne Sperre** |
| `src/services/official_alerts/meteoalarm.py:280-322,768` | `_country_store()`/`_merge_into_store()` — Read-Modify-Write **ohne Sperre**, Schluessel `country:slot:page` deckt **AT** und IT |
| `src/services/comparison_engine.py:319-335` | Ruft `get_official_alerts_with_status()` **je Ort** — der Weg, ueber den die Amtswarn-Caches nebenlaeufig erreicht werden |
| `src/services/dispatch_orchestrator.py:229` | Presets werden weiterhin **sequentiell** dispatcht — diese Scheibe parallelisiert nur *innerhalb* eines Presets |

## Dependencies

- **Upstream (was wir benutzen):** `run_comparison_parallel()` → `ComparisonEngine.run(locations=[ein_ort])`
  je Worker-Thread → Provider-Registry (seit `28b40448` gesperrt), Wetter-/Radar-/Gewitter-Caches
  (gesperrt), Zeitzonen-Singleton (gesperrt), **Amtswarn-Quellen (NICHT gesperrt)**.
- **Downstream (was uns benutzt):** Versand → `_dispatch_due_preset()` → `CompareDispatchStrategy.dispatch_one()`
  → `run_briefing_dispatch()`; Cron-Endpunkt `POST /api/scheduler/compare-presets-daily`
  (stuendlich), Einzelversand `POST /api/scheduler/compare-presets/{id}/send`.
  Sofortvergleich → Go-Proxy `internal/router/router.go:156` (Timeout 60 s, Auth-Block).

## Existing Patterns

- **Ortsreihenfolge:** beide Wege garantieren die **konfigurierte** Reihenfolge
  (`comparison_engine.py:383-386` bzw. `comparison_parallel.py:99-100`, Ergebnis landet ueber
  den Index). `result.locations` ist **nicht** score-sortiert.
- **Fehlerform:** einzelner Ortsfehler → `LocationResult(error=…)` an seiner Position;
  **alle** Orte scheitern → erste Ausnahme wird erneut geworfen (AC-8 aus B1).
- **Aufruf-Journal:** `call_source` muss explizit gesetzt werden — ein `ThreadPoolExecutor`
  reicht den `ContextVar`-Kontext nicht weiter (`providers/call_log.py:58-84`).
- **Lazy-Init-Absicherung:** doppelt geprüfte Sperre **plus separates Fertig-Flag**
  (`src/providers/base.py:191-282`) — das Vorbild aus B1.

## Existing Specs

- `docs/specs/modules/fix_1765_b1_compare_vorschau_parallel.md` — Scheibe B1 (Baustein, AC-1…AC-9)
- `docs/specs/modules/fix_1765_1839_sa_vorschau_entblockung.md` — Scheibe A (13 Handler `async def` → `def`)
- `docs/context/fix-1765-compare-vorschau-parallel.md` — Analyse B1
- `docs/reference/decision_matrix.md:231-254` — Meteo-France: 100 Anfragen/Min, geteiltes Konto, ungedrosselt

## Risks & Considerations

### R1 — Amtswarn-Caches: WIDERLEGT, kein Handlungsbedarf ✅

**Ursprungsverdacht (aus dem Bestandsscan):** ungesicherter Read-Modify-Write in
`meteoalarm._merge_into_store()` koenne bei paralleler Ortsverarbeitung Warnungen
verschlucken. Daraus entstand Issue #1890.

**Nachgemessen am laufenden System — der Verdacht traegt nicht.** `_REGISTERED_SOURCES`
enthaelt zur Laufzeit sieben Quellen; `MeteoAlarmSource` (die Klasse mit diesem Code) ist
**nicht darunter** — sie wird seit #1445 S3 nicht mehr registriert (`__init__.py:31-34`:
„Code bleibt bestehen, dient nur noch dem Aequivalenznachweis"). Im Produktivcode nirgends
instanziiert, nur in Tests. Der aktive AT/IT-Pfad ist `meteoalarm_feed.py`.

Suche nach Iteration ueber veraenderlichen Modul-Zustand (`.items()`/`.values()`/`.keys()`/
`del`/`.pop()`/`.setdefault()`/`.update()`) ueber alle 7 registrierten Quellen plus
`warn_egress.py` und `base.py`: **null Treffer**; Positivkontrolle gegen das tote
`meteoalarm.py` mit demselben Muster: 8 Treffer. `cached_fetch()` macht nur
`cache.get(key)` (Z.351) und `cache[key] = {…}` (Z.375) — unter der GIL atomar.

Ebenfalls ausgeraeumt: die `ContextVar` `_fetch_failure_sink` (`warn_egress.py:55`) wird in
`base.py:146` **im selben Worker-Thread** gesetzt und gelesen (jeder Ort laeuft komplett in
seinem Thread) — korrekt isoliert. Und `MeteoAlarmBudgetGate` (100 Abrufe/Tag) haengt
ausschliesslich am toten `meteoalarm.py`; der aktive Feed-Pfad kennt kein Budget-Gate, ein
doppelter Abruf kann dort also kein Kontingent reissen.

**Rest:** bei zeitgleichem Cache-Miss auf denselben Schluessel entstehen redundante
HTTP-Abrufe (`meteoalarm_feed._cache` schluesselt auf `country`, also ein Eintrag fuer alle
AT-Orte). Reine Hoeflichkeit gegenueber dem Fremddienst, kein Datenverlust — als Zeile in
**#1199** gebucht. #1890 geschlossen.

⚠️ **Merksatz:** Ein Bestandsscan liefert Verdachtsstellen, keine Befunde. Zwischen „im Code
steht ungesicherter gemeinsamer Zustand" und „dieser Zustand ist auf dem Live-Pfad
erreichbar" liegt eine Messung. Eine grobe Sperre um `cached_fetch()` waere hier ausserdem
schaedlich gewesen — sie haette die Parallelitaet aus B1 wieder serialisiert.

### R2 — ENTSCHAERFT: die Bestands-Tests brauchen keine Anpassung ✅

**Nachgemessen** (`grep -n "score\|temp_max"` ueber alle sieben Dateien): Die gestaffelten
Werte erscheinen **ausschliesslich in den Definitionszeilen** der Fake-Engines
(`channel_fanout.py:158-159`, `failed_tally.py:168-169`, `anchor_survives:148`,
`anchor_and_memory_reset:257`) — **keine einzige Assertion** liest `.score` oder
`.temp_max`. Ausserdem fuehren fast alle Presets dieser Tests nur **einen** Ort, womit `i`
ohnehin 0 bleibt wie bisher.

⇒ **Kein Test wird rot, keine Anpassung noetig.** Die urspruengliche Einschaetzung
(„sieben Tests muessen nachgezogen werden") war zu pessimistisch.

**Was stattdessen bleibt — der eigentliche Befund:** Diese Tests bewachen die
Orts-Staffelung **gar nicht**. Waere der Swap fehlerhaft und alle Orte bekaemen identische
Wetterwerte, faenge das **kein** Bestands-Test. Das ist kein Blocker, sondern die
Begruendung fuer AC-4 (s. Spec): der Nachweis, dass jeder Ort im Versandpfad seine
**eigenen** Werte in die Mail bekommt, muss neu gebaut werden.

Details zur Patch-Mechanik: vier Dateien nutzen Direktzuweisung statt `monkeypatch`
(`mail_marker:118`, `fixed_window:108`, `test_issue_1040_alerts_toggle:302`,
`test_issue_764_compare_forecast_hours_consume:118`). Unkritisch, weil die Zuweisung **vor**
dem Thread-Start und der Reset **nach** dessen Abschluss liegt. Keine der insgesamt 14
gefundenen Fake-Engines haelt gemeinsamen veraenderlichen Zustand — alle bauen ihr Ergebnis
rein aus den Aufrufargumenten.

### R2-alt — urspruengliche Annahme (widerlegt, zur Nachvollziehbarkeit)

`_run_one_location()` ruft `ce_mod.ComparisonEngine.run(locations=[EIN Ort])`. Die
Fake-Engines der Bestands-Tests bauen ihre Werte aber ueber `enumerate(locations)` mit
gestaffelten Groessen (`score=90-7*i`, `temp_max=22.0+i`) — gedacht fuer **einen** Aufruf mit
der vollen Liste. Nach dem Swap ist `i` bei jedem Aufruf 0 ⇒ **alle Orte bekommen identische
Werte**. Kein bestehender Assert prueft diese Werte, die Tests bleiben also gruen, waehrend
ihr Mail-Inhalt nicht mehr das prueft, was er zu pruefen vorgibt.

Betroffen: `test_compare_dispatch_failed_tally.py:185`, `test_compare_dispatch_mail_marker.py:118`,
`test_compare_dispatch_fixed_window.py:108`, `test_compare_dispatch_channel_fanout.py:175`,
`test_compare_briefing_anchor_survives_dispatch_failure.py:159`,
`test_compare_briefing_anchor_and_memory_reset.py:268` (Modul-Attribut-Patch) sowie
`test_versandpfade_folgen_ortszone.py:676` (Klassen-Patch, bleibt gueltig, da `target_date`
ortsunabhaengig ist).

Zwei der sechs patchen **ohne** `monkeypatch` (direkte Zuweisung mit `finally`-Reset) —
das ueberlebt einen Thread-Abbruch nicht sauber.

### R3 — Neue Test-Stubs brauchen Thread-Sicherheit

Die sechs vorhandenen Fake-Engines sind zustandslos pro Aufruf, daher aktuell kein Rennen.
Jeder **neue** Test mit gemeinsamem Aufruf-Zaehler/Protokoll braucht ab jetzt eine Sperre —
sonst wiederholt sich das B1-Muster (gruener Test, abgestuerzter Worker-Thread; pytest
meldet Thread-Ausnahmen nur als **Warnung**).

### R4 — Cron-Ueberlagerung ueber Nutzer hinweg (aus dem Issue uebernommen)

Der Cron-Endpunkt laeuft je `user_id` bereits nebeneinander. Mit Ortsparallelitaet
addieren sich die Abrufe **ueber Nutzer hinweg** gegen das gemeinsame, ungedrosselte
Meteo-France-Kontingent (100/Min). Presets werden innerhalb eines Laufs weiterhin
sequentiell abgearbeitet (`dispatch_orchestrator.py:229`), die Obergrenze je Preset ist 4.

### R5 — `top_ort` ist unkritisch, aber nutzersichtbar persistiert

`top_ort = result.locations[0].location.name` (Z.460) ist der **erste konfigurierte** Ort,
nicht der Sieger. Beide Wege garantieren dieselbe Reihenfolge ⇒ der Swap aendert nichts.
Der Wert wird als `top_ort_letzter_versand` persistiert und als API-Feld `winner`
zurueckgegeben (im Frontend derzeit nirgends gerendert). Braucht laut Issue trotzdem einen
eigenen Nachweis im Versandpfad.

### R6 — `GET /api/compare` ignoriert den `user_id` (Nebenbefund, eigenes Issue)

Die Go-API haengt den echten `user_id` an (`internal/handler/proxy.go:73-101`), aber
`run_comparison()` hat keinen `user_id`-Parameter und ruft `load_all_locations()` **ohne
Argument** → Rueckfall auf den `"default"`-Nutzer. Verstoss gegen die Mandantentrennungs-
Pflicht. **Nicht Teil dieser Scheibe**, aber relevant: ein Fix wuerde dieselbe Aufrufstelle
anfassen. Der Endpunkt hat ausserdem **kein Limit** auf die Ortsanzahl.

### R7 — Ausserhalb der Engine ist nichts reihenfolgeabhaengig

`first_resolvable_tz(locations, …)` (Z.441) und `target_date` werden **vor** dem
Engine-Aufruf ausgewertet. Die Δ-Anker `f"{preset_id}:{loc.id}"` (Z.514-527) bilden eine
**Menge**. `_write_compare_alert_snapshots()` (Z.611-667) bleibt eine sequentielle Schleife
und schreibt je Ort eine **eigene** Datei. `letzter_versand` wird nur im Erfolgsfall
geschrieben (Z.570). Kein Handlungsbedarf.

## Analysis

### Type
Bug (Fortsetzung von #1765; B1b schliesst das Ticket)

### Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/services/scheduler_dispatch_service.py` | MODIFY | Z.451 `ComparisonEngine.run(…)` → `run_comparison_parallel(…, call_source="vergleich")`, lokaler Import |
| `api/routers/compare.py` | MODIFY | Z.71 dieselbe Ersetzung |
| `tests/unit/test_compare_versand_parallel.py` | CREATE | Nachweis Versandpfad (Gleichzeitigkeit, Reihenfolge, `top_ort`, Ortswerte, Fehlerformen) |
| `tests/unit/test_sofortvergleich_parallel.py` | CREATE | Nachweis Sofortvergleich |

**Keine** Aenderung an den 14 Bestands-Test-Dateien mit Engine-Stub (gemessen, s. R2).
**Keine** Aenderung an `comparison_engine.py` und `comparison_parallel.py`.

### Scope Assessment

- Produktiv: 2 Dateien, **~12 LoC**
- Test: 2 neue Dateien, **~350-450 LoC** (Erfahrungswert aus B1: Testanteil ×3-4, weil bei
  Nebenlaeufigkeit jedes Kriterium einen eigenen Aufbau braucht, der sich nicht teilen laesst)
- **LoC-Limit 250 wird gerissen** → Override auf 500 noetig, PO-Freigabe erforderlich
- Risiko: **MEDIUM** — Mechanismus in B1 bewiesen und live, aber erstmals auf einem
  unbeaufsichtigten, zustandsschreibenden Pfad

### Technical Approach

Reiner Aufrufweg-Tausch, kein neuer Mechanismus. `run_comparison_parallel()` ist
signaturgleich; `call_source="vergleich"` wird explizit gesetzt, weil ein
`ThreadPoolExecutor` den `ContextVar`-Kontext nicht an seine Worker vererbt und die
Stack-Marker-Liste (`call_log.py:43-55`) im Worker-Thread ins Leere liefe.

Der Nachweis ist die eigentliche Arbeit und folgt den in B1 bewaehrten Regeln:
Gleichzeitigkeit ueber `threading.Barrier`, **nie** ueber Wanduhr-Dauer; Pflichtmutation
`max_workers=1` (muss rot werden); Thread-Ausnahmen einsammeln und den Test daran scheitern
lassen (pytest meldet sie sonst nur als Warnung).

### Dependencies

Keine neuen. `run_comparison_parallel` ist seit `098226ae` live und auf dem Vorschau-Pfad
in Betrieb.

### Open Questions

- [x] Amtswarn-Sperren noetig? → **Nein**, R1 widerlegt
- [x] Bestands-Tests anpassen? → **Nein**, R2 gemessen
- [x] Cron-Ueberlagerung drosseln? → **Nein**: 2 Nutzer in der Produktions-Datenwurzel,
      Presets laufen sequentiell (`dispatch_orchestrator.py:229`), Obergrenze 4 je Preset
      ⇒ hoechstens 8 gleichzeitige Ortsverarbeitungen gegen 100 Anfragen/Minute
- [ ] LoC-Override auf 500 — braucht PO-Freigabe

## Entscheidung nach der Nachmessung

R1 ist widerlegt (s.o.), damit entfaellt die Frage nach einer vorgezogenen Scheibe.
**B1b laeuft unveraendert weiter.** Der Arbeitsschwerpunkt liegt auf R2 (die sieben
Bestands-Tests, deren Fake-Engines nach dem Swap still identische Werte liefern) und R3
(Thread-Sicherheit neuer Test-Stubs) — nicht auf zusaetzlichen Sperren im Produktivcode.
