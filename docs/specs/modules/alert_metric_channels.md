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

### Affected Files (S2)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `src/app/metric_catalog.py` | MODIFY | Rückwärts-Lookup `summary_field → Kandidaten` als **eine** Primitive (Katalog besitzt `summary_fields` bereits); Wählbarkeits-Tie-Break (bei mehreren Kandidaten gewinnt `selectable=True`, bei genau einem Kandidaten gewinnt dieser) |
| `src/services/alert_channels.py` | MODIFY | Fünfte Eingabe `metric_channel_sets` im reinen Kern (Schleifen-Form aus `:56-60`, umgeschlüsselt auf Metrik statt Regel); Adapter lesen `alert_metric_channels`; Leer-Rückfall-Guard vor den Tier-Gates; `metrics=None`-Default im Dispatcher, damit die acht metrikfreien Aufrufstellen unverändert bleiben |
| `src/services/trip_alert.py` | MODIFY | Nur `:2509` (`_send_alert`) reicht die Metriken der `changes` durch; `:552` bleibt unberührt (reine Protokoll-Zierde, kein Versand) |
| `src/services/compare_alert.py` | MODIFY | **Nicht** `:601` — dort sind die auslösenden Metriken noch unbekannt. Der metrik-bewusste Aufruf gehört in die bestehende Ortsschleife `:286-293`, inklusive Fix der `ids_by_channel`-Vorbelegung (AC-17) |
| `src/app/loader.py` | MODIFY | Migration `alert_rules[].channels` → `alert_metric_channels`, Read-Modify-Write nach Muster `:741-753` (`snow_line`→`freezing_level`) |
| `src/output/renderers/alert/project.py` | MODIFY | `_resolve_metric_id` + `_resolve_corridor_metric_id` delegieren auf die Katalog-Primitive aus `metric_catalog.py` statt eine zweite Kopie zu halten (#1481, ADR-0021). Diese Änderung fällt unter das Renderer-Mail-Gate (`renderer_mail_gate.py:45/56`) und verlangt vor „E2E bestanden" einen frischen Nachweis mit **`radar_alert_mail_validator.py`** gegen eine **echt zugestellte Staging-Mail** aus dem Stalwart-Test-Postfach (`gregor-test@henemm.com`) — entschieden: Weg (i), kein zweiter Rückwärts-Lookup |
| `docs/reference/api_contract.md` | MODIFY | Semantik-Nachtrag am schon dokumentierten Feld (`:925-940`) — `tests/test_api_contract_drift.py` bleibt grün |
| `docs/adr/0077-*.md` | MODIFY | Ergänzung an Punkt 3: „Das Lese-Vokabular legt S2 fest (Katalog-`metric_id`, wählbarkeitsdisambiguiert, unbekannt ⇒ erbt); die verbindliche, validierte Menge samt Editor-Anzeige bleibt S3." Keine Statusänderung, kein neues ADR — `tests/test_adr_index_drift.py` bleibt unberührt |
| `tests/tdd/test_alert_metric_channel_reader.py` | CREATE | Leser, Tie-Break, Leer-Rückfall, metrikfreie Immunität, Trip/Vergleich-Parität |
| `tests/tdd/test_alert_metric_channel_migration.py` | CREATE | Migrations-Fallen (eins-zu-viele, Kollisionen, leere Liste, deaktivierte Regeln) + Roundtrip über Go-Handler und Python-Lader |

**Nicht angefasst (S2):** alles unter `frontend/`, `internal/`, `cmd/`; `has_active_rules`;
`alert_rules` als Entität (Rückbau folgt S4); `split_by_threshold` (die Union braucht keine
Partitionsstelle).

## Estimated Scope

- **LoC:** +40 bis +90 produktiv (Doku/`*.md`/Tests zählen nicht)
- **Files:** 7 produktiv + 2 Doku + Tests
- **Effort:** medium

### Estimated Scope (S2)

- **LoC:** ca. **+180 / −15** produktiv — eng am 250er-Limit. Vor `/40-tdd-red` erst
  `workflow.py status` lesen; wird es knapp, `workflow.py set-field loc_limit_override 500`
  setzen, statt die RED-Abdeckung eigenmächtig auf eine Teilmenge der ACs zu verengen.
  `docs/`, `*.md` und ADR-Änderungen zählen nicht mit.
- **Files:** 6 produktiv + 2 Test + 3 Doku
- **Effort:** high (Risiko MITTEL-HOCH: Verhaltensänderung an Bestandsdaten, Persistenz-
  Migration mit Pre-Snapshot-Hook, Fläche ist der Alarm-Versand, Asymmetrie der zwei
  Aufrufstellen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #1230 | Epic | Rahmen-Issue, dessen letzte offene Substanz diese Scheibe liefert |
| #2293 | Folge-Abstimmung | definiert dieselbe Fläche (`ComparePreset.AlertChannels`, Schicht 2 je Abo); wird nach dieser Spec gegen die hier festgelegte Zielform neu geschnitten. Beide Felder existieren nebeneinander: #2293 bleibt Schicht "je Abo", dieses Feld ist die neue Schicht "je Metrik". |
| ADR-0043 | Architekturentscheidung | verbietet eine Konfigurationsfläche ohne sichtbare Wirkung — begründet den Scheibenschnitt (S2 vor S3) |
| ADR-0046 | Architekturentscheidung | Kanal-Schwelle regelt AUF WELCHEM WEG eine Meldung ankommt, nicht OB — diese Spec schreibt ADR-0046 fort |

### Grün bleiben müssen (S2)

Diese sechs Wächter dürfen durch S2 an keiner Stelle rot werden:

- `tests/test_adr_index_drift.py`
- `tests/test_api_contract_drift.py`
- `tests/test_user_id_default_guard.py`
- `tests/test_router_user_id_required.py`
- `tests/tdd/test_alert_channel_resolution_parity.py`
- `tests/tdd/test_compare_alert_channels.py` — am kritischsten, weil er die
  Delegations-Nachweise für alle vier Vergleichs-Konsumenten führt und S2 genau die
  Datei ändert, die diese Delegation trägt (`compare_alert.py`).

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

### Implementation Details (S2)

1. **Reiner Kern bleibt primitiv** (`src/services/alert_channels.py`): fünfte Eingabe
   `metric_channel_sets: dict[str, set[str]] | None`, umgeschlüsselte Fassung derselben
   Schleife wie `:56-60` (Union je Metrik statt je Regel), Leer-Rückfall-Guard **vor** den
   Tier-Gates. `effective_alert_channels(subscription, settings, user_id, metrics=None)` —
   der neue Parameter existiert nur am Dispatcher; die acht metrikfreien Aufrufstellen
   ändern sich nicht und können den neuen Arm bauartbedingt nicht auslösen (AC-13).
2. **Katalog-Primitive** (`src/app/metric_catalog.py`): Rückwärts-Lookup
   `summary_field → Kandidaten` plus Wählbarkeits-Tie-Break (bei mehreren Kandidaten
   gewinnt `selectable=True`, bei genau einem Kandidaten gewinnt dieser — deckt `cape` ab).
   Fail-soft-Hülle um `_resolve_metric_id`/`_resolve_corridor_metric_id`: unbekannt oder
   mehrdeutig ohne eindeutigen Tie-Break ⇒ kein Eintrag ⇒ erbt (AC-15), niemals `KeyError`
   oder `ValueError` in den Alarm-Pfad durchlassen.
3. **Trip-Seite:** nur `trip_alert.py:2509` (`_send_alert`) reicht `changes`-Metriken
   durch. `:552` bleibt unberührt — dort wird `eval_result.channels` nirgends
   weiterverwendet und erscheint nur im Protokoll (`trip_alert.py:730`); ein Test, der
   bei `:552` grün wird, beweist folglich nichts über den tatsächlichen Versand.
4. **Vergleichs-Seite — Asymmetrie:** `compare_alert.py:601` (`_build_eval_config`) bleibt
   unverändert und liefert weiter den preset-weiten Startwert; die auslösenden Metriken
   sind dort noch nicht bekannt. Der metrik-bewusste Aufruf gehört in die bestehende
   Ortsschleife `:286-293`, wo `t["changes"]` je Ort vorliegt (AC-16). Dabei muss die
   Vorbelegung von `ids_by_channel` (heute nur aus `config.channels`) auch Kanäle
   abdecken, die erst durch einen Metrik-Eintrag hinzukommen — sonst wirft `:293` einen
   `KeyError` und der ganze Vergleichs-Alarm für den Ort fällt aus (AC-17).
5. **Migration** (`src/app/loader.py`, Muster `:741-753`): je aktiver, **aktivierter**
   Regel die Metrik(en) über `_ALERT_METRIC_TO_CATALOG_ID` auflösen (eins-zu-viele bei
   `TEMPERATURE_MIN`/`SNOW_LINE`, Wählbarkeits-Tie-Break bei `TEMPERATURE_MIN` ⇒ nur
   `temperature`), Kollisionen auf derselben `metric_id` unionieren, leere Regel-
   Kanallisten erzeugen **keinen** Schlüssel (kein `{}`), deaktivierte Regeln liefern
   keinen Beitrag, ein Trip ohne migrationsfähige Regel-Kanäle bekommt kein Feld
   (`omitempty` bleibt wirksam). Read-Modify-Write mit Merge — bestehende
   `alert_metric_channels`-Einträge und alle anderen Felder bleiben unangetastet
   (BUG-DATALOSS-GR221, #102).
6. **Renderer-Gate-Weg (i), entschieden:** `src/output/renderers/alert/project.py` wird
   angefasst und auf die Katalog-Primitive aus Schritt 2 umgestellt (keine zweite Kopie,
   #1481/ADR-0021). Das löst das Renderer-Mail-Gate aus; der Nachweis läuft über
   **`radar_alert_mail_validator.py`** gegen eine echt zugestellte Staging-Mail aus dem
   Stalwart-Test-Postfach — nicht `briefing_mail_validator.py` und nicht
   `email_spec_validator.py`.
7. **ADR-0077 Punkt 3 wird ergänzt, nicht abgelöst:** Zusatz „Das Lese-Vokabular legt S2
   fest (Katalog-`metric_id`, wählbarkeitsdisambiguiert, unbekannt ⇒ erbt); die
   verbindliche, validierte Menge samt Editor-Anzeige und Bestandsdaten-Prüfung bleibt
   S3." Kein neues ADR, kein Status-Wechsel — `tests/test_adr_index_drift.py` bleibt
   unberührt.

#### Mutations-Gegenprobe (S2, Pflicht in `/50-implement`)

Mindestens folgende gezielte Verfälschungen müssen jeweils mindestens einen Test rot
färben:

- Ein Metrik-Argument an einer der acht metrikfreien Aufrufstellen (z. B. Radar oder
  amtliche Warnung) ergänzen → muss AC-13 rot färben. **Vorbedingung an der Fixture:**
  `alert_metric_channels` muss einen Eintrag für eine Metrik tragen, die im
  Radar-/amtlichen Alarm nicht vorkommt, und dieser Eintrag muss von der abo-weiten
  Kanalmenge abweichen — sonst ist die Mutation bei leerem oder deckungsgleichem
  `alert_metric_channels` strukturell unbeobachtbar und bleibt grün.
- Den Leer-Rückfall-Guard entfernen oder hinter die Tier-Gates verschieben → muss AC-12
  rot färben.
- Den Migrations-/Lese-Arm auf die heutige preset-weite Regel-Union (ohne Metrik-Filter)
  umstellen → muss AC-10/AC-11/AC-23 rot färben (S2 hätte sonst keine Wirkung, ADR-0043).
- Die `ids_by_channel`-Vorbelegung in der Ortsschleife auf reines `config.channels`
  zurücksetzen → muss AC-17 rot färben (`KeyError`).
- Den Wählbarkeits-Tie-Break entfernen, sodass `temp_min_c` auf `temperature_cold` statt
  `temperature` mappt → muss AC-14 rot färben.
- Eine deaktivierte Regel in die Migration einschließen → muss AC-20 rot färben.
- Eine leere Regel-Kanalliste als `{}` statt als weggelassenen Schlüssel migrieren → muss
  AC-19 rot färben.
- An der neuen Lesestelle `user_id` durch `"default"` ersetzen → muss AC-24 und
  `tests/test_user_id_default_guard.py` rot färben.

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

### Acceptance Criteria (S2 — Leser + Migration)

- **AC-10:** Given ein Abweichungsalarm für einen Trip trägt mehrere ausgelöste Metriken
  (`changes`) und für mindestens eine dieser Metriken existiert ein Eintrag in
  `alert_metric_channels`, When der Alarm bei `trip_alert.py:2509` (`_send_alert`)
  tatsächlich versendet wird, Then enthält die dort verwendete Kanalmenge für jede
  ausgelöste Metrik `m` genau `Eintrag(m)` falls vorhanden, sonst die Kanäle der aktiven
  Regel(n) dieser Metrik, sonst den geerbten Satz — als Vereinigung über alle ausgelösten
  Metriken, nicht als das bisherige preset-weite Ergebnis.
  - Test: Trip mit Eintrag `{telegram}` für Metrik X, keinem Eintrag für Metrik Y,
    geerbtem Satz `{email, telegram}` — ein Alarm über X **und** Y liefert bei
    `trip_alert.py:2509` den versandten Satz `{email, telegram}` (Y's Anteil zieht ihn
    nach oben); derselbe Alarm ausschließlich über X liefert dort `{telegram}`. Gemessen
    an `trip_alert.py:2509`, ausdrücklich **nicht** an `:552` — ein Test, der dort grün
    wird, beweist über den tatsächlichen Versand nichts, weil `:552` nur protokolliert
    und der Versand bei `:2509` unabhängig neu auflöst.

- **AC-11:** Given ein Vergleichs-Abweichungsalarm löst für einen Ort mehrere Metriken
  aus und für mindestens eine dieser Metriken existiert ein Eintrag in
  `alert_metric_channels`, When der Alarm bei `compare_alert.py:335`
  (`send_multi_location_deviation_alert`) tatsächlich versendet wird, Then trägt die für
  diesen Ort verwendete Kanalmenge dieselbe dreiarmige Union je Metrik wie beim Trip
  (AC-10) — als Parität zur Trip-Seite, nicht das unveränderte preset-weite
  `config.channels`, das `compare_alert.py:601` weiterhin nur als Startwert liefert.
  - Test: Preset mit `config.channels={email}` und Metrik-Eintrag `{telegram}` für Metrik
    X, kein Eintrag für Metrik Y — ein Ort löst über X **und** Y aus: der versandte Satz
    für diesen Ort ist `{email, telegram}` (Y erbt `config.channels`, die Union hebt X's
    Verengung wieder an). Gemessen an `compare_alert.py:335`, nicht an `:601` allein.

- **AC-12:** Given die dreiarmige Union je Metrik ergibt für einen Alarm eine leere
  Kanalmenge, während dieselbe Kanalmenge ohne den Metrik-Arm (Ergebnis der bisherigen
  drei Schritte override/Regel-Union/geerbt) nicht leer wäre, When die Kanalmenge
  gebildet wird, Then gilt vor den Tier-Gates der Satz ohne Metrik-Arm — ein explizit
  leeres `override` ersetzt dabei weiterhin vollständig auch ins Leere
  (`alert_channels.py:49-50`), und ein nachgelagertes Tier-Gate darf die Menge danach
  weiterhin auf leer führen, ohne dass das gegen diese Regel verstößt.
  - Test: Fall mit nicht-leerem Ergebnis ohne Metrik-Arm und leerendem Metrik-Arm prüft
    Rückfall; Fall mit explizit leerem `override` bleibt unverändert leer; Fall mit
    Tier-Gate-Kürzung nach einer nicht-leeren Metrik-Arm-Menge bleibt leer.

- **AC-13:** Given `alert_metric_channels` trägt einen Eintrag für eine Metrik, die in
  einem Radar-/Nowcast-Alarm oder einer amtlichen Warnung strukturell nicht vorkommt, und
  dieser Eintrag weicht von der abo-weiten Kanalmenge ab, When ein Radar-Alarm
  (`trip_alert.py:1671`, `compare_radar_alert.py:168`) oder eine amtliche Warnung
  (`trip_alert.py:2726`, `compare_official_alert.py:472`) versendet wird, Then bleibt die
  dabei verwendete Kanalmenge exakt die abo-weite Menge von vor dieser Scheibe, weil
  diese acht Aufrufstellen den Metrik-Parameter der Auflösung nicht übergeben.
  - Test: Mutations-Gegenprobe mit der in „Implementation Details (S2)" benannten
    Fixture-Vorbedingung (abweichender, nicht im Radar-/amtlichen Pfad vorkommender
    Metrik-Eintrag) — sonst ist die Mutation strukturell unbeobachtbar.

- **AC-14:** Given ein Alarm meldet eine Änderung mit dem rohen Summary-Key
  `temp_min_c`, When der Kanal-Schlüssel für diese Metrik aufgelöst wird, Then lautet der
  Schlüssel `temperature` — der wählbare Katalog-Eintrag — und niemals
  `temperature_cold`; derselbe Summary-Key liefert auf der Trip-Seite und auf der
  Vergleichs-Seite denselben Kanal-Schlüssel.
  - Test: Erweiterung der bestehenden 16er-Paritätsmatrix
    (`test_alert_channel_resolution_parity.py:225`) um den `temp_min_c`-Fall, geprüft in
    beiden Flächen.

- **AC-15:** Given ein Summary-Key lässt sich keiner Katalog-`metric_id` eindeutig
  zuordnen (unbekannt, oder mehrdeutig ohne eindeutigen Wählbarkeits-Tie-Break), When die
  Kanal-Auflösung für diese Metrik versucht wird, Then wirft sie weder `KeyError` noch
  `ValueError`, sondern behandelt die Metrik wie eine ohne Eintrag — sie erbt den
  abo-weiten Satz.
  - Test: unbekannten und mehrdeutigen Summary-Key gegen die Auflösung fahren, Ergebnis
    ist der geerbte Satz, kein geworfener Fehler.

- **AC-16:** Given zwei Orte desselben Vergleichs-Alarms lösen unterschiedliche Metriken
  mit unterschiedlichen Einträgen in `alert_metric_channels` aus (Ort 1 nur Metrik X mit
  Eintrag `{telegram}`, Ort 2 nur Metrik Z mit Eintrag `{sms}`, beide ohne Tier-Sperre),
  When der Vergleichs-Alarm versendet wird, Then erhält Ort 1 den Kanalsatz `{telegram}`
  und Ort 2 unabhängig davon `{sms}` — zwei verschiedene Kanalsätze im selben Alarmlauf.
  Das ist nur möglich, wenn die metrik-bewusste Auflösung **je Ort** in der Ortsschleife
  (`compare_alert.py:286-293`, wo `t["changes"]` je Ort vorliegt) geschieht, nicht einmal
  preset-weit bei `compare_alert.py:601` (`_build_eval_config`), wo die ausgelösten
  Metriken noch unbekannt sind und `:601` weiterhin nur den unveränderten Startwert
  liefert.
  - Test: Vergleichs-Alarm mit den zwei oben beschriebenen Orten versenden und prüfen,
    dass Ort 1 ausschließlich über `telegram` und Ort 2 ausschließlich über `sms`
    erreicht wird — nicht beide über die Vereinigung `{telegram, sms}`.

- **AC-17:** Given ein Metrik-Eintrag in `alert_metric_channels` fügt für einen Ort einen
  Kanal hinzu, der nicht in `config.channels` enthalten ist, When `ids_by_channel` in der
  Ortsschleife (`compare_alert.py:286-293`) für diesen Kanal beschrieben wird, Then löst
  das keinen `KeyError` aus, und der Vergleichs-Alarm für diesen Ort fällt dadurch nicht
  komplett aus.
  - Test: Preset mit `config.channels={email}` und Metrik-Eintrag `{telegram}` für die
    auslösende Metrik eines Orts — Alarm für diesen Ort wird versendet, kein
    unbehandelter `KeyError`.

- **AC-18:** Given eine aktive, aktivierte Regel mit `AlertMetric`-Wert
  `TEMPERATURE_MIN` oder `SNOW_LINE` bildet laut `_ALERT_METRIC_TO_CATALOG_ID` auf
  mehrere Katalog-`metric_id`s ab, und mehrere aktivierte Regeln bilden auf dieselbe
  `metric_id` ab, When die Migration `alert_rules[].channels` → `alert_metric_channels`
  läuft, Then entsteht für `TEMPERATURE_MIN` nur der wählbare Eintrag `temperature`
  (Tie-Break aus AC-14), für `SNOW_LINE` entstehen beide Einträge `snowfall_limit` und
  `freezing_level`, und bei mehreren Regeln auf derselben `metric_id` enthält der
  migrierte Eintrag die Vereinigung aller ihrer Kanäle.
  - Test: Migrations-Lauf mit je einer `TEMPERATURE_MIN`- und einer `SNOW_LINE`-Regel
    sowie zwei Regeln auf derselben `metric_id` mit unterschiedlichen Kanälen.

- **AC-19:** Given eine aktive, aktivierte Regel hat eine leere Kanalliste (bedeutet
  „erbt"), When die Migration für die Metrik(en) dieser Regel läuft, Then erzeugt die
  Migration dafür **keinen** Schlüssel in `alert_metric_channels` — insbesondere schreibt
  sie kein `{}` —, weil ein leeres Dict laut `alert_channels.py:49-50` als vollständiges
  Override ins Leere gelesen würde.
  - Test: Regel mit leerer Kanalliste migrieren, anschließend prüfen, dass die
    zugehörige Metrik in `alert_metric_channels` keinen Schlüssel trägt.

- **AC-20:** Given eine Regel mit gesetzten Kanälen ist deaktiviert (`enabled=False`),
  When die Migration läuft, Then wandern die Kanäle dieser Regel nicht in
  `alert_metric_channels` — eine heute wirkungslose Regel darf durch die Migration nicht
  aktiv werden.
  - Test: deaktivierte Regel mit Kanälen migrieren, anschließend prüfen, dass die
    zugehörige Metrik in `alert_metric_channels` keinen Eintrag aus dieser Regel trägt.

- **AC-21:** Given ein Trip hat keine aktive, aktivierte Regel mit gesetzten Kanälen,
  When die Migration läuft, Then bleibt `alert_metric_channels` für diesen Trip
  ungesetzt — kein leeres Objekt, `omitempty` bleibt wirksam.
  - Test: Trip ohne migrationsfähige Regel-Kanäle migrieren, JSON-Antwort auf Abwesenheit
    des Schlüssels prüfen.

- **AC-22:** Given ein Trip trägt bereits andere gespeicherte Felder (u. a. einen
  bestehenden `alert_metric_channels`-Eintrag einer anderen Metrik), When die Migration
  für diesen Trip läuft, Then bleiben alle anderen Felder und bereits vorhandenen
  Einträge per Read-Modify-Write mit Merge vollständig erhalten (BUG-DATALOSS-GR221,
  #102) — nachgewiesen per Roundtrip sowohl über den Go-Handler als auch über den
  Python-Lader.
  - Test: Trip mit Bestandsfeldern und vorhandenem `alert_metric_channels`-Eintrag durch
    Go-Handler-Roundtrip UND separat durch Python-Lader-Roundtrip schicken, danach beide
    Ergebnisse auf Vollständigkeit prüfen.

- **AC-23:** **🔴 Bestandsdaten-Verengung, PO-freigabepflichtig.** Given ein Bestands-Trip
  hat heute eine aktive Regel A mit Kanal `telegram` auf Metrik X und eine aktive Regel B
  mit Kanal `email` auf Metrik Y, sodass ein Alarm, der ausschließlich Metrik X auslöst,
  vor der Migration `telegram ∪ email` erreicht (heutige regelübergreifende Union,
  unabhängig von der auslösenden Metrik, `_trip_channel_inputs:92`), When die Migration
  läuft und anschließend ein Alarm ausschließlich über Metrik X ausgelöst wird, Then
  erreicht dieser Alarm nur noch `telegram` — die Kanalmenge verengt sich für
  Bestandsnutzer dadurch bewusst und ohne jede Nutzerhandlung auf die tatsächlich zur
  auslösenden Metrik gehörenden Kanäle. Das ist die Reparatur des in #1895 gemeldeten
  Fehlers (die Kanalzuordnung hing an der falschen Entität), keine Regression.
  - Test: Bestandsdaten mit den beiden beschriebenen Regeln anlegen, Migration
    ausführen, danach einen Alarm ausschließlich über Metrik X simulieren und prüfen,
    dass die versandte Kanalmenge exakt `{telegram}` ist, nicht `{telegram, email}`.

- **AC-24:** Given zwei verschiedene Nutzer A und B haben je eigene Trips mit
  unterschiedlichen `alert_metric_channels`-Einträgen und unterschiedlichen aktiven
  Regeln, When die neue Kanal-Auflösung bzw. die Migration für Nutzer A ausgeführt wird,
  Then verwendet sie ausschließlich die echte `user_id` von Nutzer A und liest oder
  schreibt an keiner Stelle Daten von Nutzer B oder unter dem Platzhalter `"default"`.
  - Test: Auflösung und Migration unabhängig für Nutzer A und für Nutzer B ausführen,
    beide Ergebnisse tragen ausschließlich die eigenen Daten; zusätzlich bewacht durch
    `tests/test_user_id_default_guard.py` (ADR-0003).

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

### Known Limitations / Nicht-Ziele (S2)

Diese Scheibe (S2) liefert Leser + Migration. Ausdrücklich **nicht** Teil von S2:

- **Kein Frontend/`.svelte`.** Alles unter `frontend/`, `internal/`, `cmd/` ist
  unangetastet — die Editor-Spalte folgt in S3 (ADR-0043: erst nach S2).
- **Kein Rückbau von `alert_rules`.** Die Entität bleibt bestehen; `alert_rules[].channels`
  wird kopiert, nicht verschoben oder geleert — folgt in S4, erst wenn der Eintrags-Arm
  trägt.
- **Keine Validierung der Metrik-Schlüssel.** S2 legt das Lese-Vokabular fest (Katalog-
  `metric_id`, wählbarkeitsdisambiguiert, unbekannt ⇒ erbt), aber prüft nicht, ob
  Bestandsdaten „falsche" Schlüssel tragen — die verbindliche, validierte Menge samt
  Bestandsdaten-Prüfung bleibt S3 (ADR-0077-Ergänzung).
- **`has_active_rules` bleibt unangetastet** — wie in S1, unverändert gültig für S2–S4.
- **`split_by_threshold` wird nicht gebraucht.** Die Union je Metrik braucht keine
  Partitionsstelle; Drosselung, Tages-Obergrenze und der Doppel-Alarm-Guard bleiben
  dadurch unberührt.

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
- 2026-09-22: Scheibe S2 ergänzt (Leser im Alarm-Pfad + Migration
  `alert_rules[].channels` → `alert_metric_channels`, AC-10 bis AC-24), Analyse-Grundlage
  `docs/context/feat-1895-s2-kanal-leser.md` Sektion `# Analysis`. S1-Inhalte (AC-1 bis
  AC-9, Approval-Block) unverändert.
