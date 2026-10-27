# Context: feat-1992-geosphere-health-journal

## Request Summary

Issue #1992 (ursprünglich ein TLS-Befund, gemessen widerlegt — der Audit testete den
falschen Host, der Code nutzt `dataset.api.hub.geosphere.at`, das mit gültigem
Zertifikat 200 liefert) ist umgeschnitten auf den echten Rest-Befund: Fällt GeoSphere
wirklich aus, laufen mehrere Pfade fail-soft still leer, ohne dass das nach außen sichtbar
wird. Aufgabe: die noch unbeobachteten GeoSphere-Fehlerfälle beobachtbar machen.

**Wichtigster Fund dieser Phase: Issue #1581 ist BEREITS GELIEFERT** (Spec
`docs/specs/modules/fix_1581_enrichment_health.md`, Status `approved`, PO-Freigabe
2026-08-19) und hat exakt dieses Muster für zwei der drei betroffenen Pfade schon gebaut
— `MEMORY.md` ("🔴 #1581 LÄUFT") ist an dieser Stelle veraltet. #1992 baut also **kein
neues Journal**, sondern schließt eine **Lücke innerhalb** des bestehenden.

## Related Files

| File | Relevance |
|------|-----------|
| `src/providers/geosphere.py:374-375` | `fetch_snowgrid` — `except httpx.HTTPStatusError: return None, None`, stumm, kein Log |
| `src/providers/geosphere.py:391-426` | `fetch_thunder_signals_named` — `except (HTTPStatusError, TimeoutException, RequestError): return {"cape": {}, "cin": {}}`, stumm |
| `src/providers/geosphere.py:486-489` | `fetch_nowcast` — `except httpx.HTTPStatusError: return None`, stumm |
| `src/providers/thunder_enrichment.py:376-418` | `_hole_eintraege` ruft `provider.fetch_thunder_signals_named(...)` auf — bekommt bei echtem Ausfall `{"cape": {}, "cin": {}}` statt einer Exception |
| `src/providers/thunder_enrichment.py:509-519` | Klassifiziert eine leere Antwort als **Erfolg** (`log_enrichment_call(PATH_THUNDER, OUTCOME_OK)`) — Kommentar: „kein Gewitter in Sicht". Ein echter GeoSphere-Ausfall sieht in dieser Kette **identisch** aus wie ruhiges Wetter |
| `src/services/radar_service.py:337, 371-401` | `_fetch_geosphere_inca` — `except Exception: logger.warning(...); return []`. Nur echte, *nicht* von `fetch_nowcast` intern geschluckte Exceptions erreichen dieses Log; danach fällt die Aufrufkette (`_fetch_frames_with_fallback:326-355`) leise zum nächsten Radar-Quellenkandidaten durch |
| `src/services/radar_service.py:225-240` | Journal-Schreibweg für `radar_nowcast` — klassifiziert `throttled`/`data_unavailable`/sonst `OK`; ob ein via `fetch_nowcast`-internem `except HTTPStatusError` verschluckter GeoSphere-Fehler hier korrekt als `data_unavailable` statt `OK` landet, ist ungeklärt (Folgefrage für Analyse) |
| `src/providers/openmeteo.py:466-486` | `_enrich_snow` — SNOWGRID-Anreicherung, **zweite, eigene** Silent-Swallow-Schicht: `except Exception: pass`, **kein** `log_enrichment_call`, kein `PATH_SNOWGRID` existiert überhaupt |
| `src/providers/openmeteo.py:1091-1096` | `at_direct`-Cross-Provider-Fallback (ADR-0047) — `except (ProviderNotImplementedError, ProviderRequestError, ProviderNotFoundError): pass`, dann `raise last_error` — Fallback-Fehlschlag komplett stumm |
| `src/providers/enrichment_health.py` | Bestehendes Journal aus #1581: `PATH_THUNDER`, `PATH_RADAR_NOWCAST`, Outcomes `ok/fallback/unavailable/self_throttled`, `log_enrichment_call()` schreibt JSONL nach `<DataRoot>/diagnostics/enrichment_calls.jsonl` |
| `src/providers/call_log.py:44` | Anderer, älterer Journal-Mechanismus (`briefing_health`/`openmeteo_calls.jsonl`) — kennt nur `("_fetch_openmeteo_clouds", "geosphere_clouds")`, protokolliert dort aber den Open-Meteo-Host, nicht GeoSphere |
| `internal/scheduler/enrichment_health.go` | Go-Aggregator für `enrichment_calls.jsonl`, gruppiert nach `path` (geschlossenes Vokabular `PATH_THUNDER`/`PATH_RADAR_NOWCAST`), liefert `last_attempt_at`/`last_success_at`/`last_fallback_at`/`self_throttled` je Pfad, `journal_read_error`-Flag bei kaputter Datei |
| `internal/scheduler/scheduler.go:830-833` | Einhängepunkt: `"enrichment_health": s.EnrichmentHealth()` als Top-Level-Schlüssel neben `briefing_health`/`warn_service_health`/`forecast_budget` in `/api/scheduler/status` |
| `internal/scheduler/warn_service_health.go` | Schwesterpfad (ZAMG-Warnungen), analoges Muster, eigenes Journal (`warn_service_calls.jsonl`) — bewusst **kein** gemeinsames Journal mit `enrichment_health` |
| `docs/adr/0018-provider-fallback-ohne-kaschieren.md` | Verlangt für jeden degradierbaren Pfad ein „wachsendes Health-Signal" — Referenz-ADR für #1581 UND für diesen Rest-Befund |
| `docs/adr/0047-gewitter-vertretung-zwischen-direktquellen.md` | `at_direct`/Vertretungslogik — GeoSphere bekommt laut Spec-Scope-Abgrenzung **bewusst keinen** Vertretungs-Eintrag |
| `docs/specs/modules/fix_1581_enrichment_health.md` | Vollständige Spec des bereits gelieferten Journals — Vorlage für Format/Struktur eines Amendments |

## Existing Patterns

- **Ein** gemeinsamer Schreibweg pro Journal-Familie: `log_warn_service_call` (ZAMG-Warnungen) bzw. `log_enrichment_call` (#1581, Gewitter-Direktquellen + Radar-Nowcast) — bewusst getrennte Journale, kein gemeinsames Format, aber gleiches Grundschema (`ts`, Pfad-Schlüssel, Outcome-Vokabular, `detail`/optional).
- Go-Seite: reines Lesen/Aggregieren, **keine** Schwellenentscheidung im Code — „wächst mit der Ausfalldauer" ist Aufgabe des externen `check-gregor20.sh`, nicht des Aggregators.
- Journalpfad wird bei **jedem** Aufruf frisch über `app.loader.get_data_root()` aufgelöst (Falle #1633: eine beim Import gebundene Konstante zeigt an Test-Isolationsfixtures vorbei).
- Fehlklassifikation als Kernrisiko bereits im bestehenden Code erkannt und explizit kommentiert (`_fetch_primaerquelle:509-513`): „Als Ausfall gebucht meldete jede ruhige Wetterlage einen Dauerausfall" — das Spiegelbild dieses Risikos ist die hier gefundene Lücke: „Als Erfolg gebucht meldete jeder echte Ausfall ruhiges Wetter."

## Dependencies

- **Upstream:** `httpx`-Exceptions aus `GeoSphereProvider._request`/Direktaufrufen (`HTTPStatusError`, `TimeoutException`, `RequestError`, `ConnectError`) — heute an drei Stellen in `geosphere.py` gefangen, bevor sie den Aufrufer erreichen.
- **Downstream:** `internal/scheduler/enrichment_health.go` (liest `path`-Werte aus einem geschlossenen Vokabular — jede neue Konstante braucht Go-Gegenstück), `/api/scheduler/status` (öffentlicher, auth-freier Endpoint — neues Feld ist ein additiver API-Vertrag), `check-gregor20.sh` (externes Monitoring, henemm-infra) — würde einen dritten Pfad `snowgrid` (falls hinzugefügt) automatisch mitlesen, sobald der Schlüssel im JSON auftaucht.

## Existing Specs

- `docs/specs/modules/fix_1581_enrichment_health.md` — direktes Vorbild, deckt `thunder`+`radar_nowcast` bereits ab. Diese Arbeit ist ein **Amendment/Nachfolge-Scheibe**, keine Neuanlage.

## Risks & Considerations

- **Scope-Frage für Analyse:** Zwei mögliche Schnitte — (a) nur die drei stummen `except`-Blöcke in `geosphere.py` so umbauen, dass ein echter Fehler eine Exception statt `None`/`{}` liefert (dann klassifizieren die *bestehenden* Aufrufer in `thunder_enrichment.py`/`radar_service.py` automatisch richtig — ggf. minimal-invasiv), vs. (b) zusätzlich `PATH_SNOWGRID` als dritten Journal-Pfad einführen (SNOWGRID hat aktuell **gar keine** Journalanbindung, doppelt stumm über zwei Dateien hinweg).
- **`radar_nowcast` braucht Verifikation:** unklar, ob ein von `fetch_nowcast` (intern) verschluckter `HTTPStatusError` in der Aufrufkette am Ende korrekt `data_unavailable=True` setzt oder als stiller Fallback zur nächsten Radar-Quelle (`ARPAE`/`AROME`/`ICON-D2`/`minutely_15`) landet und dabei als `OK` erscheint.
- **`at_direct` (ADR-0047) bewusst außerhalb des `enrichment_health`-Vokabulars** — die Spec zu #1581 grenzt das ausdrücklich aus („GeoSphere bekommt bewusst KEINEN Vertretungs-Eintrag"). Ob dieser Fallback-Fehlschlag (`openmeteo.py:1091-1093`) in den Scope von #1992 gehört oder ein eigenes, drittes Thema ist, ist eine offene Frage für die Analyse-Phase.
- **`radar_service.py:458`** (`_fetch_openmeteo_15`) ist entgegen einem Hinweis der Parallelsession zu #1991 **kein** GeoSphere-Aufruf, sondern ein reiner Open-Meteo-Fallback (`api.open-meteo.com`) — Korrektur für die Analyse, damit dieser Pfad nicht fälschlich in den GeoSphere-Scope gezogen wird. Bleibt als benachbarte, aber separate Beobachtbarkeitslücke (nicht Teil dieses Tickets).
- **LoC-Budget:** #1581 hatte ein angehobenes Limit (900 statt 250) für einen deutlich größeren Neubau (11 Dateien, 13 ACs). Dieses Amendment sollte kleiner sein — Umfang in der Analyse-Phase abschätzen, ggf. reicht das Standard-Limit von 250.
- **Abgrenzung zu #1991** (Parallelsession, `_fetch_openmeteo_clouds`/`ForecastMeta.model_elevation_m`): bewusst getrennt geklärt — deren Feld beschreibt Parameter-Wirksamkeit, nicht Pfad-Ausfall, kein Konflikt mit `enrichment_health`.

## Analysis

### Type
Feature (Amendment zu einem bestehenden Journal, kein Bugfix im engeren Sinn — kein Nutzer-Symptom, sondern eine Beobachtbarkeitslücke).

### Kernergebnis der strategischen Bewertung

Der ursprünglich erwogene minimal-invasive Schnitt ("nur die drei `except`-Blöcke in `geosphere.py` auf Exception umstellen") **erreicht das Ticket-Ziel für zwei der drei Pfade NICHT** und öffnet zusätzlich ein Regressionsrisiko:

1. **SNOWGRID hat keinen Journal-Pfad.** Weder Exception-Werfen noch -Schlucken macht das sichtbar — es fehlt schlicht `PATH_SNOWGRID` in `enrichment_health.py`.
2. **🔴 Regressionsrisiko:** `fetch_snowgrid` wird in `fetch_combined:597` **ungeschützt** aufgerufen (kein try/except). Würde `fetch_snowgrid` bei echtem HTTP-Fehler künftig eine Exception werfen statt `(None, None)`, propagiert sie durch `fetch_combined` bis in `fetch_forecast`s äußeres `except httpx.HTTPStatusError:268` — dort wird sie zu `ProviderRequestError`, und die **komplette Grundvorhersage** schlägt fehl, obwohl nur die optionale Schneeanreicherung betroffen war. Aus "Schneetiefe fehlt" würde "GeoSphere insgesamt nicht erreichbar". **`fetch_combined` braucht ein eigenes try/except um den `fetch_snowgrid`-Aufruf**, das den Fehler journalt und ohne Schnee weiterläuft.
3. **Thunder-Pfad läuft für GeoSphere NIE über die "Primärquelle"-Klassifikation** (`_fetch_primaerquelle`/`thunder_enrichment.py:509-519`, der im Kontextdokument zitierte Kernfund). GeoSphere ist laut `thunder_routing.py:75` ausschließlich additive Zusatzquelle (`DE_ALPEN → ("geosphere",)`), läuft durch den additiven Zweig `thunder_enrichment.py:589-605`, der **überhaupt kein** `log_enrichment_call` schreibt — weder bei Erfolg noch bei Fehler (nur `logger.warning`). Eine Exception in `fetch_thunder_signals_named` allein ändert daran nichts (`except Exception: continue` bei 594 schluckt weiterhin ohne Journaleintrag). **Braucht eine `log_enrichment_call`-Anbindung direkt im additiven Zweig.**
4. **`radar_nowcast` verifiziert falsch:** `_derive_result` (`radar_service.py:543-604`) berechnet `data_unavailable` ausschließlich aus `_openmeteo_unavailable_this_call` — einem Flag, das nur der *letzte* Fallback (Open-Meteo 15-Min) setzt. Ein INCA/GeoSphere-Fehlschlag, dem die Fallback-Kette danach eine funktionierende Ersatzquelle findet (wahrscheinlich, ICON-D2 deckt die INCA-Bbox meist mit ab), bleibt `data_unavailable=False` → Journal schreibt `OUTCOME_OK`. **Braucht ein eigenes Flag** (analog `_openmeteo_unavailable_this_call`) für INCA-spezifische Fehlschläge.
5. **`at_direct`-Fallback (ADR-0047) bleibt außerhalb des Scopes**: Ein Fehlschlag dort eskaliert bereits sichtbar (`raise last_error` nach dem stummen `except`) — kein stiller Ausfall im Sinne des Tickets, nur fehlende Journal-Granularität. Zusätzlich hatte #1581 GeoSphere hier bewusst ausgeschlossen ("kein Vertretungs-Eintrag") — das wäre ein Rückgriff auf eine bereits getroffene Scope-Entscheidung, kein Bestandteil dieses Amendments.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `src/providers/geosphere.py` | MODIFY | 3 stumme `except`-Blöcke (`fetch_snowgrid:374-375`, `fetch_thunder_signals_named:424-425`, `fetch_nowcast:488-489`) journalen statt schlucken |
| `src/providers/geosphere.py::fetch_combined` | MODIFY | eigenes try/except um `fetch_snowgrid`-Aufruf (~597) — verhindert Eskalation zum Totalausfall der Grundvorhersage |
| `src/providers/enrichment_health.py` | MODIFY | neue Konstante `PATH_SNOWGRID` |
| `src/providers/openmeteo.py::_enrich_snow` | MODIFY | `except Exception: pass` (486-487) um `log_enrichment_call(PATH_SNOWGRID, ...)` ergänzen |
| `src/providers/thunder_enrichment.py` | MODIFY | additiver Zweig (589-605) um `log_enrichment_call`-Anbindung ergänzen (Scope-Frage für Spec: unter `PATH_THUNDER` mit `detail=quelle`, oder neuer Pfad für additive Quellen) |
| `src/services/radar_service.py` | MODIFY | `_fetch_geosphere_inca` (371-401) + `_derive_result` (543-604): eigenes Unavailable-Flag für INCA-spezifischen Fehlschlag |
| `internal/scheduler/enrichment_health.go` | MODIFY | Go-Gegenstück für `PATH_SNOWGRID` (geschlossenes Vokabular) |
| Tests (mehrere) | MODIFY/CREATE | `tests/tdd/test_snowgrid.py`, `test_geosphere_thunder_signals_fetch.py`, `test_issue_1161_inca_convective.py`, ggf. neue `test_*_enrichment_health_snowgrid.py` |

### Scope Assessment
- Files: ~8 (Python 6, Go 1, Tests mehrere)
- Estimated LoC: +300/-20 (grobe Schätzung, inkl. Tests) — **Standard-Limit 250 reicht vermutlich knapp nicht**, ähnlich wie bei #1581 (dort auf 900 angehoben). In der Spec-Phase eher genau schätzen, `loc_limit_override` ggf. moderat anheben (z.B. 400-450), nicht pauschal auf 900.
- Risk Level: **MEDIUM** (kein Absturzrisiko bei den geprüften Aufrufern außer dem beschriebenen `fetch_combined`-Fall, der aber explizit mitadressiert wird; Blast Radius touched den GeoSphere-Kernpfad `fetch_forecast`, deshalb Sorgfalt bei der `fetch_combined`-Änderung)

### Geprüfte Aufrufer (kein blindes `None`/`{}`-Weiterrechnen gefunden außer `fetch_combined`)
- `fetch_snowgrid`: `openmeteo.py:477` (bereits `except Exception` abgesichert), `geosphere.py::fetch_combined:597` (**ungeschützt — s.o.**), `src/validation/geosphere_validator.py:168` (Diagnosetool, unkritisch)
- `fetch_nowcast`: einziger Aufrufer `radar_service.py:380`, bereits in `except Exception` — kein Absturzrisiko, aber Journal-Wirkung braucht Zusatzänderung (s. Punkt 4)
- `fetch_thunder_signals_named`: einziger Aufrufer `thunder_enrichment.py:401` via `_hole_eintraege`, in zwei Kontexten (Primärquelle — für GeoSphere praktisch nie erreicht; additiv — kein Absturzrisiko, aber kein Journal-Log)

### Open Questions (für Spec-Phase)
- [ ] Additiver Thunder-Zweig: Journal unter bestehendem `PATH_THUNDER` mit `detail=quelle`, oder neuer eigener Pfad für additive Zusatzquellen?
- [ ] LoC-Limit: genaue Schätzung nach TDD-RED, `loc_limit_override` voraussichtlich nötig

