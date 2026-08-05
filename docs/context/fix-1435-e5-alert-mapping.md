# Context: fix-1435-e5-alert-mapping

## Request Summary

Issue #1435, Etappe E5: Die Zuordnung „Katalog-Metrik-ID → alarmfähige AlertMetric(s)"
existiert dreifach handgepflegt — in Go (`internal/model/trip.go`), Python
(`src/services/weather_change_detection.py`) und TypeScript
(`frontend/.../corridorEditorState.ts`). Nur zwei der drei Kopien (Python↔TS) sind
gegeneinander automatisiert geprüft; die Go-Kopie ist eine von Hand gespiegelte
Kopie ohne Wächter — und ihr eigener Kommentar behauptet fälschlich, geprüft zu
sein. E5 soll diese letzte handgepflegte Dublette auflösen (laut Ticket: „wird eine").

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/model/trip.go:226-288` | Go-Kopie `catalogIDToAlertMetrics` (7 Einträge, unbewacht), `AlertableMetrics` (Go-Vokabular), `ActiveAlertableMetricIDs()` — übersetzt `display_config.metrics[]` beim Trip-Speichern/-Laden für `SyncAlertRules()` |
| `src/services/weather_change_detection.py:82-136` | Python-Master-Dict `_ALERT_METRIC_TO_CATALOG_ID` (13 Einträge, Rückwärtsrichtung AlertMetric→Katalog-ID(s)), abgeleitete Vorwärtsfunktion `catalog_id_to_alert_metrics()`, gefiltert auf `_ALERTABLE_METRIC_VALUES` (hand-gespiegeltes Go-Vokabular, 6 Werte) |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:84-127` | TS-Kopie `ROUTE_CORRIDOR_CATALOG_IDS` (5 Einträge + 2 dokumentierte, bewachte Ausnahmen: `temperature_cold`, `thunder`); Kommentarblock benennt die Dreifachkopie bereits explizit (Issue #1387) |
| `tests/tdd/test_alert_metric_mapping_parity.py` (358 Zeilen) | Bestehender Wächter, prüft **nur** Python↔TS (parst TS-Quelltext gegen `catalog_id_to_alert_metrics()`); führt selbst eine vierte Handkopie des Go-Vokabulars (`_ALERTABLE_METRIC_VALUES`, Zeile 30-38) |
| `src/app/metric_catalog.py` (968 Zeilen) | Zentrales Namensregister, SSoT-Kandidat für Katalog-Metrik-IDs; wird über `GET /api/metrics` ausgeliefert, die Register→Alarm-Mapping selbst ist **nicht** Teil dieser Auslieferung |
| `internal/router/router.go:122` | Go proxied `/api/metrics` bereits 1:1 zum Python-Core (`handler.ProxyHandler`) — belegt, dass Go zur Laufzeit HTTP-Calls zum Python-Core macht, aber bislang nicht für dieses Mapping |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:280-303` | Verwandte, aber **bewusst andere** vierte Tabelle `CATALOG_TO_ALERT_METRICS` (23 Einträge, anderer Zweck: Alerts-Tab-Sensitivität inkl. Delta-Metriken) — nicht Teil der Dreifachkopie, aber bei Vereinheitlichung zu berücksichtigen/abzugrenzen |
| `internal/model/trip.go:184-198` | `AlertableMetrics` — das Go-seitige Alarm-Vokabular selbst, wird in Python (`weather_change_detection.py`) und im Test (`test_alert_metric_mapping_parity.py`) je einmal von Hand gespiegelt |

## Existing Patterns

- **Register-getriebene Ableitung statt Zweitliste** (E1a-1, E3a, E3b, ADR-0037): wiederholt erfolgreich angewendetes Muster — eine Eigenschaft wird im zentralen Python-Register deklariert und von Python/Frontend über die bestehende `/api/metrics`-Auslieferung abgeleitet, nie ein zweites Mal hartkodiert.
- **Schichtgrenze mit Ratsche statt Import-Aufweichung** (E3b, `src/output/tokens/`): wenn eine Schicht bewusst keine direkte Abhängigkeit zu einer anderen eingehen darf, sichert eine Testschicht-Ratsche die Übereinstimmung ab, statt die Architekturgrenze aufzuweichen.
- **Wirksamkeits-Wächter statt Vollständigkeits-Wächter** (E1a-1): ein neuer Wächter muss nachweislich etwas fangen — mit einer echten Mutation belegt, nicht nur behauptet.
- **Go proxied Python-Core-Endpunkte zur Laufzeit** (`/api/metrics`, `/api/compare/metrics`) — es gibt bereits eine Infrastruktur „Go ruft Python-Core per HTTP", aber kein Beispiel dafür, dass ein synchroner Persistenzpfad (`store.SaveTrip`/`LoadTrip`) einen solchen Call macht.
- **Kein Codegen-Muster im Repo** (geprüft): keine „DO NOT EDIT — generated" Go-Datei, keine Buildstep-Generierung aus Python-Quelltext.

## Dependencies

- **Upstream:** `src/app/metric_catalog.py` (Katalog-IDs), `AlertMetric`-Enum (Python `src/app/models.py`, Go `internal/model/trip.go`, TS `alertMetricTable.ts` o.ä.) — das Alarm-Vokabular selbst ist ebenfalls in mehreren Sprachen dupliziert (aber außerhalb des E5-Scopes, der nur die Katalog-ID→AlertMetric-**Zuordnung** betrifft, nicht das Vokabular selbst).
- **Downstream:**
  - Go: `store.SaveTrip`/`LoadTrip` → `ActiveAlertableMetricIDs()` → `SyncAlertRules()` (synchroner Persistenzpfad, kein HTTP-Trigger)
  - Python: `catalog_id_to_alert_metrics()` wird laut Docstring „vom Go-Persistenzpfad gebraucht" (historischer Kommentar aus #1257 — tatsächlich nutzt Go seine eigene Kopie, nicht diese Funktion direkt; zu verifizieren, ob Python die Funktion selbst produktiv nutzt oder nur für Paritätsprüfung vorhält)
  - TS: `corridorEditorState.ts::buildRoutePool()` — steuert, welche Wertebereich-Korridore im Trip-/Compare-Editor wählbar sind

## Existing Specs

- `docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md` — E1a, Vorläufer-Muster (Register lernt Alarmfähigkeit)
- `docs/specs/modules/feat_1435_e1a2_alarme_reiter_register.md` — E1a-2
- `docs/specs/modules/feat_1435_e3a_uebersicht_wetter_block.md`, `fix_1435_e3b_sms_kuerzel.md` — E3a/E3b
- `docs/adr/0015-dual-stack-zielarchitektur.md` — **zentral relevant**: legt die Zuständigkeitsgrenze Go/Python fest, Regel 1 („neue Domain-Logik entsteht im Python-Core, nicht in Go") und Regel 3 („keine Logik-Duplizierung zwischen den Stacks — pro Fall EINE Seite als Owner bestimmen, andere abbauen")
- `docs/specs/modules/go_risk_engine.md` — dokumentiert eine frühere, bewusste Entscheidung: „MetricCatalog Port — nicht nötig, Schwellenwerte als Go-Konstanten" (anderer Kontext: Risk Engine, nicht die Alarm-Mapping-Tabelle — aber Präzedenzfall für „Go bekommt keinen Katalog-Port")
- `docs/adr/0011-alert-render-single-backend-renderer.md`, `0021-shared-deviation-alert-engine.md` — Alarm-Architektur allgemein

## Bereits bekannter/verwandter Vorfall

**Issue #1387 (geschlossen)** hat exakt diese Dreifachkopie bereits einmal als Ursache eines Nutzerfehlers dokumentiert: „Nullgradgrenze" bot keinen Schneefallgrenzen-Wertebereich an, weil die TS-Kopie von Go/Python abdriftete. Der Fix hat die fehlende Zeile ergänzt und den Paritätstest auf Python↔TS ausgeweitet — **Go blieb bewusst außen vor** („dort muss weiterhin manuell nachgezogen werden", laut damaligem Ticket-Text). E5 ist also nicht die Erstentdeckung, sondern der angekündigte Nachlauf.

## Analysis

### Type
Feature (geplante Architektur-Etappe aus #1435, kein gemeldeter Bug — anders als der verwandte, bereits geschlossene Vorfall #1387).

### Verworfene Zwischenoption
Erste Analyse-Runde (3 parallele Explore-Agenten + Plan/Sonnet) empfahl zunächst nur, den bestehenden Paritätstest (`tests/tdd/test_alert_metric_mapping_parity.py`, bisher Python↔TS) um Go zu erweitern — drei Handkopien bleiben, aber alle drei werden geprüft. Begründung war ein vermeintliches Laufzeit-Risiko: Go bräuchte die Zuordnung synchron innerhalb `store.SaveTrip`/`LoadTrip` (bestätigt: kein Async-Offload, HTTP-Request-Pfad), ein Live-HTTP-Abruf beim Python-Core an dieser Stelle wäre ein neues Ausfallrisiko.

**Diese Prämisse war unvollständig.** Recherche zu Cross-Language-Datenteilung (quicktype, protobuf/JSON-Schema-Codegen — Industriestandard für genau dieses Problem) zeigt: „echte Zusammenlegung" erfordert keinen Live-Abruf. Ein aus Python generiertes Artefakt, das Go **beim Kompilieren** via `//go:embed` fest einbindet (Go 1.25, im `go.mod` bestätigt, Standardbibliothek, kein externes Werkzeug nötig), hat exakt null Laufzeit-Kopplung — dieselbe Sicherheit wie die heutige Handkopie, aber ohne die Kopie von Hand zu pflegen.

### PO-Entscheidung (2026-08-05)
**Echte Zusammenlegung über ein generiertes, eingebettetes Artefakt** — nicht nur ein nachgerüsteter Paritätstest. Python bleibt einzige Quelle (`_ALERT_METRIC_TO_CATALOG_ID` / `catalog_id_to_alert_metrics()`). Ein Skript erzeugt daraus eine Datei; Go bindet sie über `go:embed` beim Bauen fest ein; ein Frische-Prüfer (Ratchet-Test, Vorbild `tests/test_adr_index_drift.py` / `test_sms_token_symbol_register_ratchet.py`) schlägt fehl, wenn die generierte Datei nicht mehr zur Python-Quelle passt.

### Offene Gestaltungsfragen für die Spec-Phase
- **TypeScript-Seite:** analog über dieselbe generierte Datei lösen (Vite/SvelteKit kann JSON-Module direkt importieren) — ersetzt `ROUTE_CORRIDOR_CATALOG_IDS` — oder vorerst beim bestehenden Python↔TS-Regex-Parity-Test belassen und nur Go umstellen? Tech-Lead-Empfehlung für die Spec: möglichst beide Verbraucher (Go + TS) auf dieselbe generierte Datei umstellen, damit wirklich EINE Quelle entsteht statt zweier Mechanismen (Embed für Go, Regex-Parity für TS).
- **Die zwei dokumentierten Ausnahmen** (`temperature_cold` fehlt bewusst, `thunder` seit #1425 S2 bewusst nicht mehr geführt) müssen im generierten Artefakt sauber abgebildet werden — nicht stillschweigend verschwinden.
- **Die vierte Handkopie im bestehenden Test** (`_ALERTABLE_METRIC_VALUES` in `test_alert_metric_mapping_parity.py`, spiegelt Go's `AlertableMetrics`) gehört in dieselbe Betrachtung, ist aber ein eigenes Vokabular (das Alarm-Vokabular selbst, nicht die Katalog-ID-Zuordnung) — Abgrenzung in der Spec explizit klären.
- **Ablageort des generierten Artefakts:** eingecheckt in git (reviewbar im Diff, Vorbild `schemas/normalized_timeseries.schema.json`) vs. Build-Zeit-generiert-und-verworfen. Eingecheckt + Frische-Prüfer folgt dem bestehenden Ratchet-Muster des Projekts am engsten.
- **Direktimporteure des Python-Master-Dicts** (`deviation_alert_engine.py`, `alert_preset.py`, `compare_alert.py`) bleiben unverändert, solange nur die Auslieferung an Go/TS umgestellt wird, nicht die Python-interne Struktur selbst.

### Scope Assessment (revidiert)
- Dateien: neues Erzeuger-Skript (Python) · neue generierte/eingecheckte Artefakt-Datei · Go-Embed-Loader ersetzt `catalogIDToAlertMetrics` · TS-Konsument umgestellt oder Parity-Test angepasst · Frische-Prüfer (neu oder Umbau des bestehenden Paritätstests) · Kommentare in `trip.go`/`weather_change_detection.py` aktualisiert
- Geschätzt 6-8 Dateien geändert/neu, keine der 23 Verbraucherdateien (Aufrufer von `ActiveAlertableMetricIDs`, `SyncAlertRules`, den 3 Python-Services) muss ihre eigene Logik ändern — nur die Bezugsquelle der Mapping-Tabelle wechselt
- Risk Level: MEDIUM (neuer, aber im Projekt unüblicher Baustein: generiertes Artefakt + Embed; kein Laufzeitrisiko, da compile-time)

### Technical Approach
Python-Master-Dict bleibt Quelle → Erzeuger-Skript schreibt generiertes Artefakt (eingecheckt) → Go embedded es compile-time (`go:embed`), ersetzt die Handkopie → TS-Seite auf dieselbe Datei umgestellt (Ziel) → Frische-Ratchet-Test ersetzt den heutigen Python↔TS-Regex-Parity-Test.

### Dependencies
- Upstream: `_ALERT_METRIC_TO_CATALOG_ID` (Python, bleibt unverändert als Quelle)
- Downstream: alle 23 zuvor identifizierten Verbraucherdateien bleiben unangetastet, da nur die Erzeugung der jeweiligen sprachspezifischen Kopie ersetzt wird, nicht deren Nutzung

### Open Questions
- [ ] TS-Konsument auf generierte Datei umstellen oder Parity-Test-Ansatz für TS vorerst behalten? (Tech-Lead-Empfehlung: umstellen)
- [ ] Ablageort/Dateiformat des generierten Artefakts (JSON, eingecheckt)?
- [ ] Wie werden die zwei dokumentierten Ausnahmen im generierten Artefakt kodiert?

## Risks & Considerations

- **Architekturfrage, keine reine Aufräumarbeit:** `ActiveAlertableMetricIDs()` läuft im synchronen Go-Persistenzpfad (`store.SaveTrip`/`LoadTrip`). Ein Laufzeit-HTTP-Call zum Python-Core an dieser Stelle wäre ein neues Kopplungs-/Fehlermodus-Risiko (Python-Core down beim Trip-Speichern), abweichend vom bisherigen Nur-Proxy-Muster für GET-Endpunkte.
- **ADR-0015 Regel 3 fordert einen klaren Owner** — die Analyse-Phase muss entscheiden, wer die Zuordnung besitzt (Python, da Domain-Owner laut ADR) und wie Go/TS sie ohne neue Handkopie bekommen (Laufzeit-Call, Generierung, oder ein anderer Mechanismus).
- **Vierte Handkopie im Test selbst:** `test_alert_metric_mapping_parity.py::_ALERTABLE_METRIC_VALUES` (Zeile 30-38) spiegelt das Go-Vokabular `AlertableMetrics` bereits ein weiteres Mal von Hand — bei einer Neugestaltung mitzudenken, sonst wandert die Drift nur in den Wächter selbst.
- **Verwandte, aber bewusst getrennte vierte Tabelle** `alertMetricTable.ts::CATALOG_TO_ALERT_METRICS` (23 Einträge) — laut TS-Kommentar ausdrücklich NICHT identisch mit der Dreifachkopie (anderer Filterzweck). Nicht versehentlich mit vereinheitlichen.
- **Zwei dokumentierte, bewusste Ausnahmen** in der TS-Kopie (`temperature_cold`, `thunder`) müssen bei jeder Neugestaltung erhalten bleiben oder bewusst neu entschieden werden — beide sind fachlich begründet (E1a-Datenmodell bzw. #1425 S2).
- **Kein sichtbarer Nutzerfehler heute bekannt** (anders als #1387) — E5 ist reine Drift-Prävention. Scope/Nutzen sollte in der Spec explizit benannt werden, damit die Etappe nicht als „Aufräumaktion ohne Ticket-Trigger" gegen die Nebenbefund-Triage-Regel verstößt (ist hier aber bereits als eigene E5-Etappe in #1435 mit PO-Entscheid vom 2026-07-31 freigegeben).
