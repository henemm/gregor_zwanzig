# Context: fix-1658-inca-fehlerstatus

Issue #1658, Scheibe **S2**. S4 desselben Tickets ist durch #1581 bereits geliefert
(Journal `radar_nowcast` + Go-Aggregation + `/api/scheduler/status`) und gehört nicht
in diesen Workflow.

## Request Summary

Der INCA-Primärabruf des Radar-Nowcast-Pfades schluckt jeden HTTP-Fehlerstatus still.
Dadurch bleibt nicht nur die Logzeile aus (der ursprüngliche Ticket-Text) — der in
#1581 gebaute Gesundheits-Wächter bucht einen INCA-Ausfall fälschlich als `ok` und
ist damit für genau den Fall blind, für den er gebaut wurde.

## Die Kette (verifiziert)

| Schritt | Ort | Was passiert |
|---|---|---|
| 1 | `src/providers/geosphere.py:495-496` | `except httpx.HTTPStatusError: return None` — Statuscode wird verworfen |
| 2 | `src/services/radar_service.py:747-749` | `if not ts or not ts.data: return []` — früher Ausstieg, kein Merkzeichen |
| 3 | `src/services/radar_service.py:766-769` | `except Exception` setzt `_inca_unavailable_this_call = True` — **wird nie erreicht** |
| 4 | `src/services/radar_service.py:534-541` | `elif self._inca_unavailable_this_call` bleibt falsch ⇒ es wird `OUTCOME_OK` gebucht |

Ergebnis: Der Pfad weicht still auf Open-Meteo aus, und `/api/scheduler/status`
schreibt `last_success_at` fort statt `last_fallback_at`. Ein wochenlanger
INCA-Ausfall sieht gesund aus.

**Nur der Fehlerstatus ist betroffen.** Netzwerkfehler (`httpx.ConnectError`,
`RequestError`) und eine strukturell leere Antwort (`_parse_nowcast_response`
wirft `ValueError`, `geosphere.py:777-778`) propagieren bereits nach oben und werden
korrekt als Ausfall gebucht. Damit ist der `None`-Rückgabepfad von `fetch_nowcast`
heute **ausschließlich** der verschluckte Fehlerstatus.

## Related Files

| File | Relevance |
|------|-----------|
| `src/providers/geosphere.py:477-496` | `fetch_nowcast` — die Schluckstelle |
| `src/providers/geosphere.py:369-382` | `fetch_snowgrid` — Vorbild „Fehler sichtbar machen", aber andere Semantik (siehe Risiken) |
| `src/services/radar_service.py:736-769` | `_fetch_geosphere_inca` — Aufrufer, Merkzeichen, Warn-Logzeile |
| `src/services/radar_service.py:484-541` | Reset des Merkzeichens, Cache-Zweig, zentrale Health-Buchung |
| `src/providers/enrichment_health.py:26-62` | Vokabular `ok`/`fallback`/`unavailable`/`self_throttled`, Bedeutung von `detail` |
| `internal/scheduler/enrichment_health.go:92-150` | Go-Aggregation: `ok` → `last_success_at`, `fallback` → `last_fallback_at` |

## Existing Patterns

- **Zentrale Bewertung, nicht verteiltes Loggen.** Der Nowcast-Pfad bewertet seinen
  Ausgang an *einer* Stelle (`radar_service.py:534-541`), weil erst dort feststeht,
  ob nach dem INCA-Fehlschlag eine Vertretung geliefert hat (`fallback`) oder gar
  nichts (`unavailable`). `fetch_snowgrid` bucht dagegen direkt an der Fehlerstelle —
  das geht dort, weil Snowgrid keine Fallback-Kette hat.
- **`detail` bei `fallback`** trägt den Namen der tatsächlich verwendeten Ersatzquelle
  (`thunder_enrichment.py:541`, `radar_service.py:539` → `source`, z.B. `"minutely_15"`).
- **HTTP-Antworten in Tests werden gescriptet, nicht gemockt**: `_ScriptedClient`
  (`tests/unit/test_radar_upstream_failure.py:83-105`, wiederverwendet in
  `tests/tdd/test_radar_nowcast_health_journal.py:98-127` und
  `tests/tdd/test_snowgrid_enrichment_health.py`) liefert echte `httpx.Response`-Objekte.

## Dependencies

- **Upstream:** GeoSphere-NOWCAST-Endpunkt; `_request()` (`geosphere.py:319-327`) mit
  Retry auf 502/503/504, danach `raise_for_status()`.
- **Downstream:** genau **ein** Produktivaufrufer von `fetch_nowcast`
  (`radar_service.py:747`). Dessen `try/except Exception` (743-769) fängt eine
  durchgereichte Ausnahme bereits korrekt ab und setzt das Merkzeichen.
- **Externe Leser:** `/home/hem/henemm-infra/scripts/check-gregor20.sh` liest
  `enrichment_health` **nicht** aus (nur `briefing_health`, `tier_request_health`) —
  eine Umbuchung `ok` → `fallback` erzeugt dort keinen Alarm.

## Existing Specs

- `docs/adr/0018-provider-fallback-ohne-kaschieren.md` — verlangt „Marker in Daten
  **+ wachsendes Health-Signal**"; der hier behandelte Fall unterläuft die zweite Hälfte.
- Spec/Tests aus #1581 (`tests/tdd/test_radar_nowcast_health_journal.py`) und dem
  #1992-Amendment (`tests/tdd/test_radar_inca_fallback_journal.py`).

## Risks & Considerations

- **Der bestehende Wächter ist selbst blind.**
  `test_radar_inca_fallback_journal.py` (AC-6) ersetzt `GeoSphereProvider.fetch_nowcast`
  komplett durch eine Funktion, die `RuntimeError` wirft. Er springt damit über die
  Schluckstelle hinweg und ist heute grün, obwohl der Bug existiert. Ein neuer Test
  muss auf **HTTP-Ebene** ansetzen (gescriptete Fehler-Response), nicht durch Ersetzen
  der Methode — sonst wiederholt er denselben Blindfleck.
- **Kein zweiter Buchungsort.** Ein `log_enrichment_call` direkt in `fetch_nowcast`
  (Snowgrid-Muster) erzeugte eine zweite, widersprüchliche Journalzeile pro Aufruf und
  unterliefe die zentrale `elif`-Kette. Die Sichtbarkeit muss über das bestehende
  Merkzeichen laufen.
- **Abgrenzung wahren:** „INCA antwortet regulär, meldet aber keinen Niederschlag"
  muss weiterhin `ok` bleiben. Das ist die korrekte Auskunft „für diesen Punkt nichts
  zu melden" (ADR-0041 Muster B) und darf weder loggen noch als Ausfall zählen.
- **Testkoordinate:** Der bestehende Health-Test nutzt eine Atlantik-Koordinate
  außerhalb der INCA-Box und läuft deshalb gar nicht über GeoSphere. Ein Test für
  diesen Fix braucht einen Punkt **innerhalb** `_within_inca()`
  (`radar_service.py:1151-1152`).
- **Nebenbefund (kein Teil dieser Scheibe):** `_inca_unavailable_this_call` ist ein
  Instanzattribut ohne Sperre; zwei gleichzeitige `get_nowcast()`-Aufrufe auf derselben
  Instanz könnten es gegenseitig überschreiben. Nicht neu durch diesen Fix, nicht
  belegt als produktiv auftretend → Sammel-Issue, nicht hier.
