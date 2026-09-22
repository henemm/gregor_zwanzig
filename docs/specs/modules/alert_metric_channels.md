---
entity_id: alert_metric_channels
type: module
created: 2026-09-22
updated: 2026-09-22
status: draft
version: "1.0"
tags: [alerts, channels, datamodel]
---

# Alert Metric Channels

## Approval

- [ ] Approved

## Purpose

Diese Spec legt die Zielform eines neuen, additiven Feldes `alert_metric_channels` auf
`Trip` und `ComparePreset` fest — Ablageort, Go-Typ und Merge-Verhalten — damit spätere
Scheiben (Metrik-genaue Kanal-Auflösung, Editor-Spalte) darauf aufbauen können, ohne beim
Speichern Kanäle einer anderen Metrik zu verlieren. Diese Scheibe (S1) ist reine
Verrohrung: Das Feld wird persistiert und übersteht Speichern/Laden, wirkt aber auf
nichts — es gibt in S1 noch keine Stelle, die es liest.

## Source

- **File (Go-Modell):** `internal/model/trip.go`, `internal/model/compare_preset.go`
- **File (Go-Handler):** `internal/handler/trip.go`
- **File (Python-Domäne):** `src/app/trip.py`, `src/app/loader.py`
- **File (Doku):** `docs/reference/api_contract.md`, `docs/adr/0077-*.md`
- **Identifier:** `Trip.AlertMetricChannels`, `ComparePreset.AlertMetricChannels`,
  `tripUpdateRequest.AlertMetricChannels`, `Trip.alert_metric_channels` (Python-Dataclass)

### Affected Files (S1)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `internal/model/trip.go` | MODIFY | Feld `AlertMetricChannels map[string]interface{}` mit `json:"alert_metric_channels,omitempty"` + Docstring (Muster `AlertChannels`, `:151-163`) |
| `internal/model/compare_preset.go` | MODIFY | dito (Muster `AlertChannelThresholds`, `:91-98`) |
| `internal/handler/trip.go` | MODIFY | DTO-Feld in `tripUpdateRequest` + `mergeConfigMap`-Zeile im RMW-Block, analog `:334-336` |
| `internal/handler/compare_preset.go` | — | **unberührt**, läuft generisch über `mergeBriefingPatch` — aber das Struct-Feld ist trotzdem Pflicht (typisierter Unmarshal verwirft sonst den Key, s. Implementation Details) |
| `internal/store/trip.go` | — | **unberührt, nachgemessen 2026-09-22:** `SaveTrip` marshalt das Struct transparent (`:272`), `LoadTrip`/`LoadTrips` unmarshalen transparent (`:197`/`:141`). Ein neues Struct-Feld fließt ohne Registrierung mit; die `snow_line`→`freezing_level`-Legacy-Migration (`:314-330`) ist feldspezifisch und berührt es nicht. |
| `src/app/trip.py` | MODIFY | Dataclass-Feld `alert_metric_channels: Optional[dict] = None` (Muster `alert_channels`, `:221`) |
| `src/app/loader.py` | MODIFY | `KNOWN_TOP_LEVEL`-Eintrag + Konstruktor-`data.get(...)` + bedingtes Schreiben in `_trip_to_dict` (Muster `:652,695,1625-1626`) |
| `src/app/models.py` | MODIFY | optionales typisiertes `ComparePreset`-Feld (Parität). **Für die Persistenz nicht nötig, nachgemessen:** `compare_preset_to_dict` liefert `preset.raw` unverändert zurück (`src/app/loader.py:345-352`) — jeder Key übersteht den Python-Roundtrip ohne Codeänderung. Das Feld dient S2 als benannter Leser. |
| `docs/reference/api_contract.md` | MODIFY | **Pflicht, sonst CI rot** — siehe AC-8 |
| `docs/adr/0077-*.md` + `docs/adr/README.md` | CREATE/MODIFY | ADR-0077 (Fortschreibung ADR-0046), Index-Eintrag (`tests/test_adr_index_drift.py`) |
| `tests/…` Roundtrip + `internal/store/…_test.go` | CREATE/MODIFY | Roundtrip-Nachweis beide `kind`-Werte, zwei Nutzer |

## Estimated Scope

- **LoC:** +40 bis +90 produktiv (Doku/`*.md`/Tests zählen nicht)
- **Files:** 7 produktiv + 2 Doku + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #1230 | Epic | Rahmen-Issue, dessen letzte offene Substanz diese Scheibe liefert |
| #2293 | Folge-Abstimmung | definiert dieselbe Fläche (`ComparePreset.AlertChannels`, Schicht 2 je Abo); wird nach dieser Spec gegen die hier festgelegte Zielform neu geschnitten. Beide Felder existieren nebeneinander: #2293 bleibt Schicht "je Abo", dieses Feld ist die neue Schicht "je Metrik". |
| ADR-0043 | Architekturentscheidung | verbietet eine Konfigurationsfläche ohne sichtbare Wirkung — begründet den Scheibenschnitt (S2 vor S3) |
| ADR-0046 | Architekturentscheidung | Kanal-Schwelle regelt AUF WELCHEM WEG eine Meldung ankommt, nicht OB — diese Spec schreibt ADR-0046 fort |

## Implementation Details

1. **Go-Struct-Feld auf beiden Entitäten**, Typ `map[string]interface{}`, JSON-Tag
   `alert_metric_channels,omitempty`:
   - `internal/model/trip.go`: Feld `AlertMetricChannels map[string]interface{}` mit
     `json:"alert_metric_channels,omitempty"` + Docstring, analog zum Muster
     `AlertChannels` (`internal/model/trip.go:151-163`).
   - `internal/model/compare_preset.go`: dasselbe Feld, analog zum Muster
     `AlertChannelThresholds` (`internal/model/compare_preset.go:91-98`).
2. **Trip-PUT-DTO ergänzen UND die `mergeConfigMap`-Zeile setzen — beide zusammen**,
   sonst fällt das Feld beim Trip-PUT still raus (Feld fehlt im DTO) oder ersetzt beim
   Speichern blind alle Metriken (Feld im DTO, aber ohne Merge-Zeile):
   - `internal/handler/trip.go`: DTO-Feld in `tripUpdateRequest` + eine Zeile
     `existing.AlertMetricChannels = mergeConfigMap(existing.AlertMetricChannels, *req.AlertMetricChannels)`
     im Read-Modify-Write-Block, analog zum bestehenden Muster für `DisplayConfig`
     (`internal/handler/trip.go:334-336`).
   - `internal/handler/compare_preset.go` bleibt **unberührt** — der Vergleich-PUT läuft
     bereits generisch über `mergeBriefingPatch` (`internal/handler/briefing_subscription.go:188-196`)
     und mergt jeden Top-Level-Key mit Objekt-Wert automatisch eine Ebene tief. Das
     Go-Struct-Feld aus Schritt 1 ist trotzdem Pflicht: Ohne modelliertes Feld verwirft
     der anschließende typisierte `json.Unmarshal(merged, &p)`
     (`internal/handler/compare_preset.go:292-300`) den Key wieder.
3. **Python: alle drei Stellen zusammen**, nie nur eine oder zwei davon:
   - `src/app/trip.py`: Dataclass-Feld `alert_metric_channels: Optional[dict] = None`,
     analog zum Muster `alert_channels` (`src/app/trip.py:221`).
   - `src/app/loader.py`: Eintrag in `KNOWN_TOP_LEVEL` + `data.get(...)` im Konstruktor +
     bedingtes Zurückschreiben in `_trip_to_dict`, analog zum bestehenden Muster
     (`src/app/loader.py:652,695,1625-1626`). Wird nur der `KNOWN_TOP_LEVEL`-Eintrag
     gesetzt, ohne Dataclass-Feld und Rückschreiben, geht ein zuvor persistierter
     Bestandswert beim nächsten Speichern verloren (Falle `loader.py:657-658`) — daher
     müssen alle drei Stellen in einem Zug entstehen.
   - `src/app/models.py`: optionales typisiertes Feld am `ComparePreset` für Parität.
     Für die Persistenz selbst nicht erforderlich (`compare_preset_to_dict` liefert
     `preset.raw` unverändert zurück, `src/app/loader.py:345-352`), dient aber S2 als
     benannter Leser.
4. **`docs/reference/api_contract.md`** um das neue JSON-Tag `alert_metric_channels`
   ergänzen (beide Entitäten) — Pflicht, sonst wird `tests/test_api_contract_drift.py`
   rot.
5. **ADR-0077** als Fortschreibung von ADR-0046 anlegen: Ablageort (Top-Level auf Trip
   UND ComparePreset), Go-Typ (`map[string]interface{}`), Schlüsselmenge (Analyse-Notiz,
   keine Validierung in S1), Regel „kein Eintrag = erbt den Abo-weiten Kanal-Satz",
   Reihenfolge-Zwang „S2 muss vor S3 kommen" — plus Eintrag in `docs/adr/README.md`.
6. **Tests:** Roundtrip auf beiden `kind`-Werten (Trip, ComparePreset) mit zwei
   verschiedenen Nutzern; Teil-PUT ohne das Feld löscht es nicht; Teil-PUT mit einer
   Metrik löscht die anderen Metriken nicht. Die Trip-Teil-PUT-Tests laufen zwingend auf
   der HTTP-Schicht (`UpdateTripHandler`), nicht gegen `store.SaveTrip` — Begründung
   siehe AC 3/4.

### Mutations-Gegenprobe (Pflicht in `/50-implement`)

Mindestens folgende gezielte Verfälschungen müssen jeweils mindestens einen Test rot
färben:

- `omitempty` am Feld entfernen
- `mergeConfigMap` im Trip-PUT-Handler durch einen Blind-Replace ersetzen (muss AC-4 rot
  färben, sonst ist der Teil-PUT-Test wertlos)
- `KNOWN_TOP_LEVEL`-Eintrag in `src/app/loader.py` entfernen
- `_trip_to_dict`-Rückschreibe-Zeile in `src/app/loader.py` entfernen
- Feld aus dem Trip-DTO (`tripUpdateRequest`) entfernen

## Expected Behavior

- **Input:** Trip-PUT bzw. Vergleich-PUT mit optionalem Feld `alert_metric_channels`
  (Objekt, Schlüssel = Metrikname, Wert = beliebige Kanal-Repräsentation, in S1
  unvalidiert).
- **Output:** Persistierter Trip bzw. ComparePreset trägt das Feld unverändert weiter;
  ein Teil-PUT ohne das Feld oder mit nur einer Metrik lässt die übrigen bereits
  gespeicherten Metriken unangetastet.
- **Side effects:** Keine — S1 hat keinen Leser im Alarm-Pfad. Bestandstrips ohne das
  Feld serialisieren dank `omitempty` weiterhin keinen entsprechenden JSON-Schlüssel.

## Acceptance Criteria

- **AC-1:** Given ein Trip eines Nutzers A wird mit dem neuen Feld
  `alert_metric_channels` gespeichert, When der Trip anschließend neu geladen wird,
  Then enthält der geladene Trip exakt dieselben Metrik-Kanal-Zuordnungen wie beim
  Speichern — geprüft für zwei verschiedene Nutzer A und B, damit ausgeschlossen ist,
  dass Daten zwischen Mandanten vermischt werden.
  - Test: HTTP-Roundtrip (Trip anlegen/PUT mit Feld → GET) für Nutzer A und getrennt für
    Nutzer B; beide Antworten enthalten unabhängig voneinander genau ihre eigenen
    gespeicherten Werte, keine Vermischung zwischen den beiden Nutzern.

- **AC-2:** Given ein Ortsvergleich (`ComparePreset`) eines Nutzers wird mit dem neuen
  Feld `alert_metric_channels` gespeichert, When der Vergleich anschließend neu geladen
  wird, Then enthält er dieselben Metrik-Kanal-Zuordnungen wie beim Speichern — geprüft
  für zwei verschiedene Nutzer, als Parität zum Trip-Verhalten aus AC-1.
  - Test: HTTP-Roundtrip (ComparePreset anlegen/PUT mit Feld → GET) für zwei
    unterschiedliche Nutzer; beide erhalten unabhängig genau ihre eigenen Werte zurück.

- **AC-3:** Given ein Trip hat bereits gespeicherte Metrik-Kanal-Zuordnungen, When ein
  weiterer Trip-PUT geschickt wird, der das Feld `alert_metric_channels` gar nicht
  enthält, Then bleiben die zuvor gespeicherten Zuordnungen nach diesem PUT unverändert
  erhalten — ein Teil-Update löscht das Feld nicht.
  - Test: Auf HTTP-Ebene über `UpdateTripHandler` (nicht gegen `store.SaveTrip`, da der
    Merge in `internal/handler` sitzt und der Store das Struct nur transparent
    durchreicht): Trip mit Feld anlegen, dann PUT ohne dieses Feld im Body senden,
    anschließend per GET prüfen, dass die ursprünglichen Metrik-Kanal-Zuordnungen noch
    vollständig vorhanden sind.

- **AC-4:** Given ein Trip hat gespeicherte Kanal-Zuordnungen für mehrere Metriken
  (z. B. Regen und Wind), When ein Trip-PUT nur die Zuordnung einer einzelnen Metrik
  (z. B. Regen) ändert, Then bleiben die Zuordnungen der übrigen, im PUT nicht genannten
  Metriken (z. B. Wind) unverändert erhalten.
  - Test: Auf HTTP-Ebene über `UpdateTripHandler` (aus demselben Grund wie AC-3): Trip
    mit Zuordnungen für mindestens zwei Metriken anlegen, PUT senden, das nur eine der
    beiden Metriken im Feld `alert_metric_channels` enthält, anschließend per GET
    prüfen, dass die nicht genannte Metrik weiterhin ihren ursprünglichen Wert trägt.

- **AC-5:** Given ein Ortsvergleich hat gespeicherte Kanal-Zuordnungen für mehrere
  Metriken, When ein Vergleich-PUT nur die Zuordnung einer einzelnen Metrik ändert,
  Then bleiben die Zuordnungen der übrigen Metriken unverändert erhalten. **Hinweis:**
  Diese AC charakterisiert vorbestehendes, generisches Verhalten des
  Vergleich-PUT-Pfads (`mergeBriefingPatch` mergt jeden Top-Level-Key mit Objekt-Wert
  bereits automatisch) — sie bewacht keinen für diese Spec neu geschriebenen Merge,
  sondern das in Schritt 1 hinzugefügte Go-Struct-Feld selbst: Ohne dieses Feld würde
  der anschließende typisierte Unmarshal den Schlüssel `alert_metric_channels` beim
  Laden wieder verwerfen.
  - Test: Auf HTTP-Ebene über den Vergleich-PUT-Handler (nicht gegen den Store):
    ComparePreset mit Zuordnungen für mindestens zwei Metriken anlegen, PUT senden, das
    nur eine der beiden Metriken enthält, anschließend per GET prüfen, dass die nicht
    genannte Metrik weiterhin ihren ursprünglichen Wert trägt.

- **AC-6:** Given ein Trip wurde vor dieser Änderung bereits mit einem Wert im Feld
  `alert_metric_channels` in der Python-Datenhaltung gespeichert (vorbefüllter
  Bestandswert), When dieser Trip von der Python-Schicht geladen und anschließend wieder
  zurückgeschrieben wird, Then bleibt der Wert erhalten — das bewacht, dass alle drei
  Python-Stellen (`KNOWN_TOP_LEVEL`-Eintrag, Dataclass-Feld, Rückschreiben in
  `_trip_to_dict`) gemeinsam gesetzt sind und keine davon fehlt.
  - Test: Eine Trip-Datei mit vorbefülltem `alert_metric_channels`-Wert direkt in der
    Python-Datenhaltung ablegen, den Trip über den Python-Lade-/Speicherpfad laden und
    zurückschreiben, danach die Datei erneut lesen und prüfen, dass der Wert
    unverändert vorhanden ist.

- **AC-7:** Given ein Trip wurde ohne das Feld `alert_metric_channels` angelegt (Feld
  nicht gesetzt), When der Trip als JSON serialisiert wird, Then enthält die Ausgabe
  keinen Schlüssel `alert_metric_channels` — Bestandstrips bleiben dadurch byte-gleich
  zum Zustand vor dieser Änderung, das neue Feld ist verhaltensneutral.
  - Test: Einen Trip ohne das Feld über die HTTP-Schicht anlegen/laden und die
    JSON-Antwort auf Abwesenheit des Schlüssels `alert_metric_channels` prüfen (dies ist
    kein Dateiinhalt-Check auf Quellcode, sondern eine Prüfung des tatsächlich
    ausgelieferten API-Antwortkörpers).

- **AC-8:** Given das neue JSON-Tag `alert_metric_channels` existiert an `Trip` und
  `ComparePreset`, When `tests/test_api_contract_drift.py` läuft, Then findet der Test
  eine passende Erwähnung des Tags in `docs/reference/api_contract.md` und bleibt grün.
  - Test: `tests/test_api_contract_drift.py::test_every_model_json_tag_is_documented`
    ausführen und auf Exit-Code 0 prüfen.

- **AC-9:** Given ADR-0077 wurde als Fortschreibung von ADR-0046 angelegt und in
  `docs/adr/README.md` verlinkt, When `tests/test_adr_index_drift.py` läuft, Then bleibt
  der Test grün, weil Datei und Index-Eintrag übereinstimmen.
  - Test: `tests/test_adr_index_drift.py` ausführen und auf Exit-Code 0 prüfen.

## Known Limitations / Nicht-Ziele

Diese Scheibe (S1) liefert ausschließlich Feld, Persistenz, Roundtrip, Doku und ADR.
Ausdrücklich **nicht** Teil von S1:

- **Kein Leser im Alarm-Pfad.** Das Feld wirkt in S1 auf nichts — das ist Absicht
  (Risiko R2 „stille Kanal-Abschaltung" kann ohne Leser strukturell nicht feuern). Ein
  Leser folgt erst in S2.
- **Keine Migration** von `alert_rules[].channels` in das neue Feld — folgt in S2,
  direkt neben dem Code, der das Feld erst maßgeblich macht.
- **Keine Frontend-/`.svelte`-Änderung, keine Editor-Spalte.** Folgt in S3, und S3 darf
  laut ADR-0043 erst nach S2 kommen (eine Bedienfläche ohne wirkende Aufrufstelle wäre
  eine Konfigurationsfläche ohne sichtbare Wirkung).
- **Kein Rückbau** von `alert_rules` — folgt in S4.
- **Keine Validierung** der Metrik-Schlüssel oder Kanalwerte. Go validiert heute weder
  Metrik-Keys noch Stufenwerte; eine neue Validierung wäre Scope-Creep und würde
  Bestandsdaten mit dem abgelösten Schlüssel `snow_line` brechen.
- **`has_active_rules` bleibt unangetastet.** Weder S1 noch S2–S4 fassen es an — ein
  Wegfall würde Trip-Verhalten ändern (überstimmt `alert_on_changes=False`) und wäre
  nicht verhaltensneutral.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0077, Fortschreibung von ADR-0046 (`0046-alarm-kanal-schwelle.md`)
- **Rationale:** ADR-0046 legt fest, dass die Kanal-Schwelle regelt, AUF WELCHEM WEG
  eine Meldung ankommt, nicht OB. ADR-0077 schreibt das fort, indem es die Zielform der
  neuen, metrik-genauen Kanal-Schicht festlegt: Ablageort (Top-Level auf `Trip` UND
  `ComparePreset`, Parität ab S1), Go-Typ (`map[string]interface{}`, damit der
  bestehende `mergeConfigMap`-Mechanismus greift und kein atomarer Ersatz der ganzen Map
  entsteht — Muster `DisplayConfig`), Schlüsselmenge (Analyse-Entscheidung für S3, in S1
  nicht validiert), die Regel „kein Eintrag = erbt den Abo-weiten Kanal-Satz" (Feld ist
  in S1 dadurch verhaltensneutral) sowie den Reihenfolge-Zwang „S2 muss vor S3 kommen"
  (ADR-0043-Konsequenz: keine Bedienfläche ohne wirkende Aufrufstelle).

## Changelog

- 2026-09-22: Initial spec created (Scheibe S1 von #1895-F2, Analyse-Grundlage
  `docs/context/feat-1895-kanalzuordnung-je-metrik.md` Sektion `# Analysis`).
