---
entity_id: alert_metric_channels
type: module
created: 2026-09-22
updated: 2026-11-03
status: draft
version: "1.2"
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

**Scheibe S3a (Issue #1895, Backend und Vertrag, für Nutzer noch nicht sichtbar):** S3a macht die
Schicht tragfähig, bevor eine Oberfläche sie anbietet. Vier Teile: (1) der Leser fällt auf den
Satz ohne Metrik-Arm zurück, wenn der Metrik-Arm **nach** den Tarif-Sperren leer ist (ein
gewählter Kanal kann den Alarm dann nicht mehr ins Leere schicken); (2) ein Nachtrag zu
ADR-0077 hält Schlüsselmenge, Rückfall und „null = erbt" fest; (3) ein neuer Lese-Endpunkt
`GET /alert-metric-channel-keys` (Go-Proxy `GET /api/alert-metric-channel-keys`) ist die
**einzige** Quelle dafür, welche Alarm-Zeile auf welchen Speicherschlüssel abbildet; (4) ein
Top-Level-`null` auf `alert_metric_channels` löscht beim Ortsvergleich nicht mehr die ganze
Map (Angleichung an den Trip). Es gibt dafür **keine Oberfläche** (Prod-Bestand: 0 Briefings
mit `alert_metric_channels`); das Verhalten ist für Nutzer erst mit S3b sichtbar. Die Oberfläche
(Block „Kanäle je Wettergröße", Hinweise) ist ausdrücklich **nicht** Teil von S3a.

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
| `src/services/alert_channels.py` | MODIFY | Fünfte Eingabe `metric_channel_sets` im reinen Kern (Schleifen-Form aus `:56-60`, umgeschlüsselt auf Metrik statt Regel); Adapter lesen `alert_metric_channels`; Leer-Rückfall-Guard vor den Tier-Gates (seit S3a/AC-25: nach den Tier-Gates); `metrics=None`-Default im Dispatcher, damit die acht metrikfreien Aufrufstellen unverändert bleiben |
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

### Affected Files (S3a)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `src/services/alert_channels.py` | MODIFY | `resolve_alert_channels`: Rückfall auf den Satz ohne Metrik-Arm, wenn der Metrik-Arm **nach** den Tier-Gates leer ist (AC-25); Docstring Schritt 4/5 anpassen (Satz „kein Fall für den Rückfall" entfällt) |
| `src/services/weather_change_detection.py` | MODIFY | Neben den Summary-Feld-Tabellen die **eine** Funktion `alert_metric_channel_keys()` (Zeile → sortierte Liste der Speicherschlüssel aus Lesersicht, akzeptierte Menge); keine zweite Zeile-zu-Schlüssel-Liste |
| `api/routers/config.py` | MODIFY | Neuer Endpunkt `GET /alert-metric-channel-keys`; `get_metrics` bleibt **unverändert** |
| `internal/router/router.go` | MODIFY | Proxy `GET /api/alert-metric-channel-keys` → `/alert-metric-channel-keys`, gleiche Auth-Gruppe und Zeilenmuster wie `/api/metrics` (`:235`) |
| `internal/handler/briefing_subscription.go` | MODIFY | `mergeBriefingPatch`: Top-Level-`null` für **genau** `alert_metric_channels` überspringen (No-Op); alle anderen Felder behalten ihre Semantik (AC-36/AC-37) |
| `docs/reference/api_contract.md` | MODIFY | SSOT: neuer Endpunkt samt Antwortform und Hinweis „null = erbt" am Feld (`tests/test_api_contract_drift.py` bleibt grün) |
| `docs/adr/0077-metrik-genaue-kanal-schicht-als-top-level-map.md` | MODIFY | Nachtrag „S3a" (kein neues ADR, kein Status-Wechsel; `docs/adr/README.md` bleibt unverändert, `tests/test_adr_index_drift.py` prüft nur Datei↔Index-Konsistenz und Status) |
| `tests/tdd/test_alert_metric_channel_reader.py` | MODIFY | `test_ac12_tier_gate_darf_nach_nicht_leerem_metrik_arm_auf_leer_fuehren` (`:511`) wird **umgekehrt**: nach Tier-Gate-Kürzung greift der Rückfall (AC-25) |
| `tests/tdd/test_alert_metric_channel_keys.py` | CREATE | Endpunkt-Abbildung, zeilenweiser Wirk-Test, Migrations-Schlüsselmenge (AC-30 bis AC-34) |
| `internal/handler/compare_preset_alert_metric_channels_test.go` | MODIFY | Null-Angleichung, Gegenprobe, je-Metrik-`null`, zwei Nutzer (AC-36 bis AC-39) |
| `internal/handler/trip_alert_metric_channels_test.go` | MODIFY | Trip-Regressionsfall: Top-Level-`null` bleibt No-Op (AC-36) |
| `internal/router/alert_metric_channel_keys_route_test.go` | CREATE | Proxy-Route und Auth (AC-35) |

**Nicht angefasst (S3a):** alles unter `frontend/` (keine UI), `src/app/loader.py` (Migration
und ihr Tie-Break bleiben unverändert, AC-33 prüft nur die Verträglichkeit), `split_by_threshold`
(`trip_alert.py`, `compare_alert.py`), `internal/handler/trip.go` (Trip-Verhalten schon korrekt,
nur Regressions-Test), `/api/metrics`-Antwort, `has_active_rules`, `alert_rules` als Entität.

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

### Estimated Scope (S3a)

- **LoC:** ca. **+75 / −10** produktiv (Rückfall ~10, Schlüssel-Funktion ~20, Endpunkt ~15,
  Go-Proxy 1, Go-Null-Skip ~8, Rest Docstring). Limit 250 je Workflow; `docs/`, `*.md`, ADR und
  Tests zählen nicht.
- **Files:** 5 produktiv + 4 Test + 2 Doku (Spec/ADR-Nachtrag zählen nicht mit)
- **Effort:** medium (Risiko MITTEL: ändert die Versand-Auflösung, aber nur auf einem Zweig, den
  heute kein Bestand erreicht — 0 Briefings mit Feld)

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
   Tier-Gates (durch S3a/AC-25 abgelöst: Rückfall jetzt nach den Tier-Gates). `effective_alert_channels(subscription, settings, user_id, metrics=None)` —
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
- Den Leer-Rückfall-Guard entfernen → muss AC-12 rot färben. (Die S2-Mutation „Guard hinter
  die Tier-Gates verschieben" ist seit S3a überholt: S3a schreibt genau diese Lage vor; die
  Gegen-Mutation „Rückfall wieder vor die Gates" steht in der Mutations-Gegenprobe (S3a).)
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

### Implementation Details (S3a)

1. **Rückfall nach den Tier-Gates (E7).** In `resolve_alert_channels` wird der bisherige
   Leer-Rückfall-Guard (Schritt 4, vor den Gates) durch eine Auswertung **nach** den Gates
   ersetzt: Zuerst die Tier-Gates auf den Metrik-Arm-Satz anwenden. Ist das Ergebnis leer,
   gilt der Satz ohne Metrik-Arm (Ergebnis aus override/Regel-Union/geerbt), ebenfalls nach
   denselben Tier-Gates. Die Gates selbst (`sms_allowed`, `premium_sms_allowed`) bleiben
   unverändert und werden weiterhin genau einmal je Satz angewandt (SMS/Premium-SMS ohne
   Tarif bleiben gestrichen — vereinbar mit #2279 S1 AC-4). Ist auch der Satz ohne Metrik-Arm
   nach den Gates leer, bleibt das Ergebnis leer (heutiges Verhalten des Abo-Satzes).
   Docstring Schritt 4/5 entsprechend umschreiben.
2. **Kanal-Schwelle bleibt dahinter (Entscheidung).** `split_by_threshold` (ADR-0046) läuft bei
   den Aufrufern (`trip_alert.py`, `compare_alert.py`) **nach** der Auflösung und bleibt
   unverändert; der Rückfall wird **nicht** dahinter gezogen. Die Schwelle je Kanal ist eine
   bewusste Nutzerwahl, und dasselbe Verhalten gilt heute schon für den Abo-Satz. Das ist ein
   benanntes Restrisiko (Known Limitations S3a), kein Fehler dieser Scheibe.
3. **Eine Funktion für die Schlüssel-Zuordnung (E2/E3).** `alert_metric_channel_keys()` in
   `weather_change_detection.py` leitet je `AlertMetric` die Speicherschlüssel **aus der Sicht
   des Lesers** ab: die Summary-Felder, die der Detektor für diese Zeile scharf stellt
   (`_ALERT_METRIC_TO_SUMMARY_FIELD` bzw. `_ALERT_DELTA_METRIC_TO_FIELDS`), werden über die
   Leser-Primitive `alert_channels._metric_id_for_summary_key` aufgelöst; der Wert je Zeile ist
   die **sortierte Liste** dieser Schlüssel. Damit gibt es keine zweite Zeile-zu-Schlüssel-Liste
   (Wächter #1480) und keine handgepflegte Ausnahme: Was der Leser liest, bietet der Endpunkt
   an. Gemessen 2026-11-03 (Detektor real, Regeln aus `expand_per_metric_levels`): 14 Zeilen
   tragen genau einen Schlüssel, **`wind_change` trägt zwei** (`["gust", "wind"]`), weil die
   Windänderung `wind_max_kmh` **und** `gust_max_kmh` beobachtet und der Leser das Böen-Feld als
   `gust` liest. `snowfall_limit` ist Legacy-Schlüssel und kommt in `keys` **nie** vor (der
   Detektor meldet `snow_line` über `freezing_level_m`); eine einzige benannte Konstante
   `_LEGACY_ONLY_CHANNEL_KEYS = {"snowfall_limit"}` nimmt ihn in `accepted` auf, weil die
   Legacy-Migration ihn schreibt. Rückgabe: `keys` (AlertMetric-Wert → sortierte Liste der
   Schlüssel) und `accepted` (sortierte Liste = Vereinigung aller Listen in `keys` ∪
   `_LEGACY_ONLY_CHANNEL_KEYS`). Beispiele: `wind_gust→[gust]`, `wind_change→[gust, wind]`,
   `temperature_min`/`temperature_max`/`temperature_change→[temperature]`,
   `thunder_level`/`thunder_onset→[thunder]`, `precipitation_sum`/`precipitation_change`/
   `precipitation_heavy_onset→[precipitation]`, `snow_line`/`freezing_level→[freezing_level]`,
   `cape→[cape]`, `fresh_snow→[fresh_snow]`, `visibility→[visibility]`. `humidity` hat kein Summary-Feld (ADR-0010) und fehlt. Der Wählbarkeits-
   Tie-Break der Migration (`loader.py::_katalog_ids_fuer_alarm_metrik`) bleibt, wo er ist —
   die Schlüssel-Funktion braucht ihn nicht mehr, AC-33 prüft die Verträglichkeit beider.
4. **Endpunkt statt `aggregations[]`.** `aggregations[]` in `/api/metrics` wird vom Wertebereiche-
   Editor als wählbare Auswertung gelesen, und `cape` (`selectable=False`) fehlt dort ganz;
   die Antwort bleibt daher unverändert. Neu: `GET /alert-metric-channel-keys` →
   `{"keys": {…}, "accepted": […]}`, Go-Proxy `GET /api/alert-metric-channel-keys` in
   derselben Auth-Gruppe wie `/api/metrics`. Die Antwort hängt von keinem Nutzer ab.
5. **Keine Go-Schreibvalidierung (E3).** Go besitzt keinen Katalog (eine Kopie wäre Drift),
   ADR-0077 Punkt 3 warnt vor Bestandsbruch, der Leser ist fail-soft (unbekannter Schlüssel ⇒
   erbt). Die Prüfung der Schlüsselmenge geschieht ausschließlich durch den zeilenweisen
   Wirk-Test (AC-32), nicht durch eine Laufzeit-Validierung.
6. **`null` (E4/E8).** Je Metrik bedeutet `{"gust": null}` „erbt" (persistiert als `null`,
   `config_merge.go:18-20`; Leser behandelt ihn als kein Eintrag). Top-Level
   `"alert_metric_channels": null` ist beim Trip No-Op (`handler/trip.go:375`, Pointer-DTO) und
   wird beim Ortsvergleich in `mergeBriefingPatch` (`briefing_subscription.go:200`, von
   `applyComparePresetPatch` für beide Ortsvergleichs-PUT-Wege genutzt) für **genau dieses
   Feld** übersprungen. Keine allgemeine „null = No-Op"-Regel: für andere Top-Level-Felder (z. B.
   `activity_profile: null`) überschreibt `null` den Bestandswert wie bisher (`base[k] = v`, AC-37).
7. **ADR-0077-Nachtrag „S3a"** (kein neues ADR): (a) gültige Schlüsselmenge und ihre einzige
   Definition (`alert_metric_channel_keys()`), (b) Rückfall nach Tier-Gates (ersetzt die
   S2-Aussage „kein Fall für den Rückfall", die nur in S2-Spec und Docstring stand; ADR-0077
   selbst enthielt keine Aussage zum Tier-Gate-Verhalten), (c) `null`-Eintrag je Metrik =
   „erbt", (d) keine Go-Schreibvalidierung samt Begründung. Statuszeile und Index-Eintrag
   bleiben unverändert.

#### Mutations-Gegenprobe (S3a, Pflicht in `/50-implement`)

Mindestens folgende gezielte Verfälschungen müssen jeweils mindestens einen Test rot färben:

- Den Rückfall wieder **vor** die Tier-Gates verschieben (alter Guard) → muss AC-25 rot färben.
- Den Rückfall auch das Tier-Gate des Rückfall-Satzes überspringen lassen (SMS ohne Tarif
  rutscht über den Rückfall wieder hinein) → muss AC-26 rot färben.
- Den Rückfall entfernen (leer bleibt leer) → muss AC-25 und AC-28 rot färben.
- Die Endpunkt-Abbildung `snow_line→[snowfall_limit]` statt `→[freezing_level]` → muss AC-30
  und AC-32 rot färben.
- `humidity` oder `snowfall_limit` als Ziel in `keys` aufnehmen → muss AC-31 rot färben.
- Die Schlüssel-Funktion durch eine handgeschriebene zweite Liste ersetzen, in der eine Zeile
  abweicht → muss AC-32 rot färben (zeilenweise Mengengleichheit, keine ⊆-Kette).
- `wind_change` auf nur einen Schlüssel kürzen (`[wind]`, das Böen-Feld fällt weg) → muss
  AC-30 und AC-32 rot färben.
- Die Migration einen Schlüssel schreiben lassen, der nicht in `accepted` liegt → muss AC-33
  rot färben.
- Go: das `null`-Überspringen auf **alle** Top-Level-Felder ausdehnen → muss AC-37 rot färben
  (ein anderes Feld mit `null`, z. B. `activity_profile`, bliebe dann unverändert).
- Go: das `null`-Überspringen entfernen → muss AC-36 rot färben.
- Go: den Proxy aus der Auth-Gruppe nehmen → muss AC-35 rot färben.
- `/api/metrics` um die Schlüssel-Zuordnung erweitern (`aggregations[]` verändern) → muss
  AC-34 rot färben.

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
  gebildet wird, Then gilt der Satz ohne Metrik-Arm — ein explizit leeres `override`
  ersetzt dabei weiterhin vollständig auch ins Leere (`alert_channels.py:49-50`).
  **Seit S3a gilt der Zeitpunkt des Rückfalls nach AC-25 (nach den Tier-Gates);** die
  frühere S2-Fassung „vor den Tier-Gates, ein nachgelagertes Tier-Gate darf die Menge danach
  auf leer führen" ist durch AC-25 abgelöst.
  - Test: Fall mit nicht-leerem Ergebnis ohne Metrik-Arm und leerendem Metrik-Arm prüft
    Rückfall; Fall mit explizit leerem `override` bleibt unverändert leer. Der frühere
    S2-Fall „Tier-Gate-Kürzung nach nicht-leerem Metrik-Arm bleibt leer" wird in S3a
    umgekehrt (siehe AC-25).

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

### Acceptance Criteria (S3a — Rückfall, Schlüssel-Quelle, Go-Angleichung)

Nummerierung setzt AC-24 (S2) fort. Alle ACs dieser Scheibe sind Backend-/Vertrags-ACs;
nutzerseitig sichtbar wird nichts (kein Frontend in S3a).

- **AC-25:** Given der Metrik-Arm einer Auflösung ist nicht leer, wird aber durch die
  Tier-Gates vollständig gestrichen (z. B. Eintrag `{sms}` bei Nutzer ohne SMS-Tarif, oder
  `{premium_sms}` ohne Premium-SMS-Tarif), und der Satz ohne Metrik-Arm (override/Regel-Union/
  geerbt) ist nach den Gates nicht leer, When die Kanalmenge gebildet wird, Then gilt der Satz
  ohne Metrik-Arm nach den Tier-Gates — der Alarm bleibt zustellbar, statt leer zu werden.
  - Testart: Kern (reiner Python-Test, kein Netz). Prüfling: `resolve_alert_channels` in
    `src/services/alert_channels.py`; der bisherige S2-Test
    `test_ac12_tier_gate_darf_nach_nicht_leerem_metrik_arm_auf_leer_fuehren` wird umgekehrt
    und prüft genau diesen Rückfall (Metrik-Arm `{sms}`, kein Tarif, geerbt `{email}` ⇒
    `{email}`).

- **AC-26:** Given der Rückfall nach AC-25 greift und der Satz ohne Metrik-Arm enthält selbst
  einen tarifgesperrten Kanal (`sms` oder `premium_sms` ohne Tarif), When die Kanalmenge
  gebildet wird, Then bleibt dieser Kanal gestrichen; ist der Satz ohne Metrik-Arm nach den
  Gates ebenfalls leer, bleibt das Ergebnis leer (heutiges Abo-Satz-Verhalten, unverändert),
  und ein explizit leeres `override` ersetzt weiterhin vollständig ins Leere.
  - Testart: Kern. Prüfling: `resolve_alert_channels`; Fälle: geerbt `{sms}` ohne Tarif ⇒
    leer; Metrik-Arm `{sms}` + geerbt `{sms}` ohne Tarif ⇒ leer; leeres `override` ⇒ leer;
    mit Tarif bleibt `sms` erhalten (Regression zu #2279 S1 AC-4).

- **AC-27:** Given der Metrik-Arm ist nach den Tier-Gates nicht leer (z. B. `{telegram}`),
  When die Kanalmenge gebildet wird, Then ersetzt er den Satz ohne Metrik-Arm weiterhin
  vollständig (S2 AC-10/AC-11) — der Rückfall greift nur bei leerem Metrik-Arm nach den Gates,
  und der Fall ohne Metrik-Arm-Eingabe (die acht metrikfreien Aufrufstellen, AC-13) bleibt
  byte-gleich zu vorher.
  - Testart: Kern. Prüfling: `resolve_alert_channels`, bestehende S2-Tests
    (`tests/tdd/test_alert_metric_channel_reader.py`, `test_alert_channel_resolution_parity.py`)
    bleiben grün.

- **AC-28:** Given ein Trip bzw. Ortsvergleich trägt für die auslösende Metrik einen Eintrag
  `{sms}`, der Nutzer hat keinen SMS-Tarif und der geerbte Satz ist `{email}`, When der
  Abweichungsalarm tatsächlich versendet wird (`trip_alert.py:2509` bzw. die Ortsschleife
  `compare_alert.py:286-293`), Then geht er über `email` und nicht an niemanden.
  - Testart: Kern. Prüfling: Trip-Versandpfad und Vergleichs-Ortsschleife (am Versand
    gemessen, nicht nur an `resolve_alert_channels`); Parität beider Flächen.

- **AC-29:** Given der Rückfall nach AC-25 liefert einen Kanalsatz und ein Kanal darin hat eine
  Kanal-Schwelle (ADR-0046), die über der Dringlichkeit des Alarms liegt, When der Alarm
  verteilt wird, Then wirkt `split_by_threshold` unverändert **nach** der Auflösung — der
  Rückfall wird nicht dahinter gezogen (bewusste Nutzerwahl der Schwelle; benanntes
  Restrisiko, Known Limitations S3a).
  - Testart: Kern. Prüfling: bestehende Schwellen-Tests (`trip_alert.py`, `compare_alert.py`)
    bleiben unverändert grün; ein Test hält fest, dass die Auflösung ihre Kanalmenge
    **ohne** Kenntnis der Schwelle liefert.

- **AC-30:** Given der Python-Core läuft, When `GET /alert-metric-channel-keys` aufgerufen
  wird, Then enthält `keys` je Alarm-Zeile die sortierte Liste ihrer Speicherschlüssel —
  mindestens `wind_gust→[gust]`, `wind_change→[gust, wind]` (die Windänderung beobachtet auch
  die Böen, und der Leser ordnet das Böen-Feld `gust` zu),
  `temperature_min`/`temperature_max`/`temperature_change→[temperature]`,
  `thunder_onset→[thunder]`, `precipitation_heavy_onset→[precipitation]`,
  `snow_line→[freezing_level]`, `cape→[cape]`, `fresh_snow→[fresh_snow]`,
  `visibility→[visibility]` — und `accepted` ist die sortierte Liste aller
  Schlüssel aus `keys` zuzüglich `snowfall_limit`.
  - Testart: Kern (FastAPI-`TestClient`, kein Mock). Prüfling: `api/routers/config.py`
    (`/alert-metric-channel-keys`) gegen `alert_metric_channel_keys()`; zusätzlich Staging-API
    (`/api/alert-metric-channel-keys` mit Login) nach Deploy.

- **AC-31:** Given die Antwort aus AC-30, When ihre Ziele geprüft werden, Then fehlt
  `humidity` (keine Alarm-Identität) in `keys`, und `snowfall_limit` ist **nie** Wert in `keys`
  (nur Element von `accepted`, weil die Legacy-Migration es schreibt).
  - Testart: Kern (`TestClient`). Prüfling: Antwort von `/alert-metric-channel-keys`.

- **AC-32:** Given eine beliebige Alarm-Zeile (jeder `AlertMetric`-Wert in `keys`), When der
  Detektor für diese Zeile bei Bewegung **aller** von ihr beobachteten Werte seine
  `WeatherChange`s emittiert und `_metric_id_for_summary_key` jeden Summary-Key auflöst, Then
  ist die Schlüsselliste aus dem Endpunkt **gleich** der Menge der aufgelösten Schlüssel —
  geprüft **zeilenweise auf Mengengleichheit** (keine ⊆-Kette, die z. B. einen im Trip-Pfad nie
  ausgelösten `snowfall_limit` grün durchließe oder bei `wind_change` den Böen-Schlüssel
  verschwiege).
  - Testart: Kern (reines Python, Endpunkt über `TestClient`, Detektor real, kein Mock).
    Prüfling: `alert_metric_channel_keys()`/Endpunkt gegen `weather_change_detection.py` und
    `alert_channels._metric_id_for_summary_key`. Der Test liest **keine** `.ts`-Datei ein
    (kein Dateiinhalt-Check).

- **AC-33:** Given die Legacy-Migration (S2 AC-18) läuft für Regeln aller `AlertMetric`-Werte
  mit gesetzten Kanälen, When `alert_metric_channels` entsteht, Then liegt jeder geschriebene
  Schlüssel in `accepted` aus dem Endpunkt (`snow_line`-Regeln schreiben `snowfall_limit` und
  `freezing_level`, beide akzeptiert).
  - Testart: Kern. Prüfling: `_migrate_rule_channels_to_metric_channels` in
    `src/app/loader.py` gegen die Antwort des Endpunkts.

- **AC-34:** Given der Endpunkt aus AC-30 existiert, When `GET /metrics` aufgerufen wird, Then
  ist die Antwort unverändert: `aggregations[]` enthält keine neuen Einträge (kein Onset,
  keine Alarm-Zeile), und `cape` fehlt weiterhin, weil `selectable=False`.
  - Testart: Kern (`TestClient`). Prüfling: `get_metrics` in `api/routers/config.py`; Vergleich
    gegen die Auswahl-Semantik des Wertebereiche-Editors (nur Verhalten der API, kein
    Frontend-Dateiinhalt).

- **AC-35:** Given ein angemeldeter bzw. ein nicht angemeldeter Aufruf, When
  `GET /api/alert-metric-channel-keys` gegen die Go-API gerichtet wird, Then wird der Aufruf
  nur mit gültiger Anmeldung an den Python-Core weitergereicht (gleiche Auth-Gruppe wie
  `/api/metrics`) und ohne Anmeldung mit 401 abgelehnt.
  - Testart: Go-Test (Router-Test). Prüfling: `internal/router/router.go`; nach Deploy
    zusätzlich Staging-API.

- **AC-36:** Given ein gespeicherter Ortsvergleich trägt `alert_metric_channels`
  (`{"gust": {"email": true}}`), When ein Teil-PUT (`PUT /api/briefings/{id}?kind=vergleich`
  und `PUT /api/compare/presets/{id}`) `"alert_metric_channels": null` sendet, Then bleibt die
  gespeicherte Map unverändert — wie beim Trip (`handler/trip.go:375`).
  - Testart: Go-Test. Prüfling: `mergeBriefingPatch` (`briefing_subscription.go`) /
    `applyComparePresetPatch` (`compare_preset.go`), über die HTTP-Schicht beider PUT-Wege;
    Trip-Pendant als Regressions-Fall.

- **AC-37:** Given derselbe Teil-PUT sendet für ein **anderes** Top-Level-Feld `null` (z. B.
  `activity_profile: null`), When er verarbeitet wird, Then ist das gespeicherte Ergebnis für
  dieses Feld exakt dasselbe wie vor S3a (`null` überschreibt den Bestandswert, `base[k] = v`) —
  die Angleichung gilt nur für `alert_metric_channels`. Der Test hält zuerst fest, dass das
  gewählte Feld vor der Änderung tatsächlich durch `null` verändert wird (sonst ist die
  Gegenprobe wertlos), und wählt notfalls ein anderes Feld, für das das gilt.
  - Testart: Go-Test gegen dieselben PUT-Wege. Prüfling: `mergeBriefingPatch`.

- **AC-38:** Given ein Teil-PUT sendet `{"alert_metric_channels": {"gust": null}}`, When er
  gespeichert und wieder geladen wird, Then ist `gust` als `null` persistiert (andere Metriken
  unverändert, `mergeConfigMap`), und der Leser behandelt `null` wie „kein Eintrag" — die
  Metrik erbt (Trip und Ortsvergleich).
  - Testart: Go-Test (Persistenz) plus Kern (Leser: `null`-Eintrag ⇒ geerbter Satz).
    Prüfling: `mergeConfigMap`, `alert_channels._metric_channel_sets`.

- **AC-39:** Given zwei verschiedene Nutzer A und B haben je einen Ortsvergleich mit eigenem
  `alert_metric_channels`, When Nutzer B Teil-PUTs mit `null` bzw. mit einer Metrik sendet
  (AC-36/AC-38) und Nutzer A liest, Then bleiben die Daten von A vollständig unverändert und B
  sieht und ändert nichts von A; `user_id` kommt aus dem Auth-Kontext, nie `"default"`. Der
  Endpunkt aus AC-30 liefert beiden Nutzern dieselbe, nutzerunabhängige Antwort.
  - Testart: Go-Test mit zwei Nutzern (ADR-0003). Prüfling: `UpdateBriefingHandler`/
    `UpdateComparePresetHandler`; `tests/test_user_id_default_guard.py` bleibt grün.

- **AC-40:** Given S3a ist umgesetzt, When die Dokumentation geprüft wird, Then beschreibt
  `docs/reference/api_contract.md` den Endpunkt samt Antwortform und die Semantik „null =
  erbt", und ADR-0077 trägt den Nachtrag „S3a" (Schlüsselmenge, Rückfall nach Tier-Gates,
  `null` = erbt, keine Go-Schreibvalidierung) bei unverändertem Status.
  - Testart: Kern, `# doc-compliance-test`: ein eigener Test prüft, dass ADR-0077 einen
    Abschnitt „S3a" mit den vier Punkten enthält und `api_contract.md` den Pfad
    `/api/alert-metric-channel-keys` samt `keys`/`accepted` nennt; zusätzlich bleiben
    `tests/test_api_contract_drift.py` und `tests/test_adr_index_drift.py` grün.

## Known Limitations / Nicht-Ziele

Diese Scheibe (S1) liefert ausschließlich Feld, Persistenz, Roundtrip, Doku und ADR.
Ausdrücklich **nicht** Teil von S1:

- **Kein Leser im Alarm-Pfad.** Das Feld wirkt in S1 auf nichts — das ist Absicht
  (Risiko R2 „stille Kanal-Abschaltung" kann ohne Leser strukturell nicht feuern). Ein
  Leser folgt erst in S2.
- **Keine Migration** von `alert_rules[].channels` in das neue Feld — folgt in S2,
  direkt neben dem Code, der das Feld erst maßgeblich macht.
- **Keine Frontend-/`.svelte`-Änderung, keine Editor-Spalte.** Folgt in S3b (Oberfläche;
  S3 ist in S3a/S3b geteilt, siehe Scheibenschnitt unten), und S3 darf laut ADR-0043 erst
  nach S2 kommen (eine Bedienfläche ohne wirkende Aufrufstelle wäre eine
  Konfigurationsfläche ohne sichtbare Wirkung).
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
  unangetastet — die Editor-Spalte folgt in S3b (ADR-0043: erst nach S2).
- **Kein Rückbau von `alert_rules`.** Die Entität bleibt bestehen; `alert_rules[].channels`
  wird kopiert, nicht verschoben oder geleert — folgt in S4, erst wenn der Eintrags-Arm
  trägt.
- **Keine Validierung der Metrik-Schlüssel.** S2 legt das Lese-Vokabular fest (Katalog-
  `metric_id`, wählbarkeitsdisambiguiert, unbekannt ⇒ erbt), aber prüft nicht, ob
  Bestandsdaten „falsche" Schlüssel tragen — die verbindliche Schlüsselmenge (eine
  Definition, zeilenweiser Wirk-Test, ADR-0077-Nachtrag) liefert S3a; eine
  Go-Schreibvalidierung gibt es bewusst nicht (E3). Bestandsprüfung erledigt: 0 Briefings
  mit `alert_metric_channels`, 0 Regeln mit `channels` in Prod.
- **`has_active_rules` bleibt unangetastet** — wie in S1, unverändert gültig für S2–S4.
- **`split_by_threshold` wird nicht gebraucht.** Die Union je Metrik braucht keine
  Partitionsstelle; Drosselung, Tages-Obergrenze und der Doppel-Alarm-Guard bleiben
  dadurch unberührt.

### Known Limitations / Nicht-Ziele (S3a)

**Scheibenschnitt (löst die frühere Einteilung „S3 = Editor-Spalte" ab):**

| Scheibe | Inhalt | Workflow |
|---|---|---|
| S3a | Backend und Vertrag: Leser-Rückfall nach Tier-Gates, ADR-0077-Nachtrag, Schlüssel-Endpunkt, Go-Angleichung Top-Level-`null` | dieser Workflow |
| S3b | Oberfläche: Block „Kanäle je Wettergröße" in Trip- und Vergleichs-Editor samt Anlegemasken, Payload, Snapshot/Rollback, DE/EN-Texte, Hinweise | eigener späterer Workflow unter #1895 |
| S4 | Rückbau `alert_rules` | später, setzt S3b voraus |

Ausdrücklich **nicht** Teil von S3a:

- **Keine Oberfläche, für Nutzer unsichtbar.** Block „Kanäle je Wettergröße" (E1), „erbt"-Zustand
  und Abwahl aller Kanäle (E4/E5), freie Kanalwahl mit Tarif-Sperre (E6), Hinweistext für
  metrikfreie Alarme (E9) und Anlegemasken (E10) sind S3b. Bis dahin schreibt kein Nutzer das
  Feld (Prod-Bestand: 0 Briefings), die Rückfall-Änderung wirkt auf keinen Bestand.
- **Kanal-Schwelle (benanntes Restrisiko).** `split_by_threshold` (ADR-0046) läuft nach der
  Auflösung und bleibt unverändert. Ein Metrik-Arm `{sms}` mit SMS-Schwelle „hoch" unterdrückt
  eine niedrigere Warnung, auch wenn der Abo-Satz sie zugestellt hätte. Das gilt heute schon
  gleich für den Abo-Satz; S3a macht es nicht schlechter. S3b zeigt dafür einen sichtbaren
  Hinweis.
- **Fehlender Empfänger (benanntes Restrisiko).** `resolve_alert_channels` kennt keine
  Empfänger; ein gewählter Kanal ohne Empfänger (z. B. Telegram ohne verknüpften Chat) wird vom
  Rückfall nicht erfasst. S3b zeigt dafür einen sichtbaren Hinweis.
- **Windänderung hängt an zwei Schlüsseln.** Ein Windänderungs-Alarm, der über die Böen
  ausgelöst wird, folgt der Kanalwahl unter `gust`, einer über den Mittelwind der unter `wind`
  (so liest der S2-Leser heute, gemessen 2026-11-03). Der Endpunkt sagt das ehrlich
  (`wind_change→[gust, wind]`); wie die Oberfläche diese Kopplung zeigt, entscheidet S3b.
- **Metrikfreie Alarme unberührt.** Radar-/Regen-Alarme und amtliche Warnungen übergeben keinen
  Metrik-Parameter und gehen unverändert über den Abo-Satz (AC-13).
- **Nebenbefund außerhalb des Umfangs.** `compare_alert.py:70-80` bildet `temp_min_c` auf
  `temperature_cold` ab, `alert_channels.py` auf `temperature`; betroffen ist nur der
  Deaktivieren-Filter, nicht die Kanal-Map. Wird als Nebenbefund (#1199) geführt, nicht hier
  geändert.
- **Keine Go-Schreibvalidierung** der Metrik-Schlüssel (E3) und **keine allgemeine
  „null = No-Op"-Regel** im Go-Merge (E8): nur `alert_metric_channels`.
- **`/api/metrics` unverändert**; kein Rückbau von `alert_rules`; `has_active_rules` unangetastet.

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
- 2026-11-03: Scheibe S3a ergänzt (Backend und Vertrag: Leser-Rückfall nach Tier-Gates,
  Schlüssel-Endpunkt `GET /alert-metric-channel-keys`, Go-Angleichung Top-Level-`null`,
  ADR-0077-Nachtrag, AC-25 bis AC-40), Analyse-Grundlage
  `docs/context/feat-1895-s3-kanal-spalte.md` Sektion `## Analysis` (E1–E10). S2 AC-12 als
  „teilweise abgelöst durch AC-25" vermerkt; Scheibenschnitt auf S3a/S3b/S4 umgeschrieben.
  Oberfläche (S3b) ausdrücklich nicht enthalten.
- 2026-11-03 (Nachfreigabe aus `/40-tdd-red`): Detektor-Probe zeigte, dass `wind_change` auch
  `gust_max_kmh` meldet und der Leser es als `gust` liest — AC-30/AC-32 in der alten Form
  (ein Schlüssel je Zeile, Gleichheit je Zeile) waren zusammen mit AC-33 nicht erfüllbar.
  Korrektur: `keys` liefert je Zeile die sortierte Schlüsselliste aus Lesersicht, AC-32 prüft
  Mengengleichheit; Implementation Details §3, Affected Files (Tie-Break bleibt in `loader.py`),
  Mutations-Gegenprobe und Known Limitations entsprechend angepasst.
