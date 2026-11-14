# Context: fix-2069-alert-preview-echte-segmente

## Request Summary
Issue #2069: `POST /api/trips/{id}/alert-preview` soll den Abweichungs-Zweig (`changes`) mit den
**echten** Segmenten des Trips rendern statt mit Platzhalter-Segmenten, im Zweig `official` die
gemessene km-Spanne (`segment_km`) durchreichen und eine Vorschau, deren `segment_id`s im Trip nicht
auflösbar sind, nicht mehr still akzeptieren. Ziel: die Vorschau zeigt, was auch versendet würde
(erklärtes #918-Ziel), und kein Black-Box-Validator schließt mehr aus einem selbst erzeugten Fehlen
auf „Implementierung kaputt" (#2036, #2020 S2).

## Ist-Stand (origin/main b67cad4dd, 2026-11-13)

Seit Issue-Anlage (2026-08-22) teilweise überholt:
- **#1737** hat einen echten Pfad eingeführt: `_deviation_preview_message`
  (`src/services/validator_render_service.py:274`) nimmt Anker + frische Reihe über
  `trip_preview_series` (`src/services/alert_preview_hours.py:57`) — dann echte Segmente MIT
  Stundenreihe. Nur wenn kein tagesgleicher Anker existiert (Trip läuft heute nicht, Cache leer,
  Abruf scheitert/Zeitlimit), fällt er auf `_stub_segment()` zurück (`:296`).
- **#2219 C5-18** hat dem Stub die Lage des ersten Wegpunkts statt 0/0 gegeben
  (`validator_render_service.py:89`) — Distanz/Höhenmeter/`distance_measured` bleiben 0/False.
- **`official`-Zweig** (`_render_official_preview`, `:313`) ruft
  `build_official_alert_notices(trip_obj, tagged)` weiterhin **ohne** `segment_km`
  (Signatur `official_alerts.py:2476`, Versand übergibt `measured_segment_km(segments)` in
  `trip_alert.py:3543`).
- **ID-Prüfung** `_reject_unknown_segment_id` (`api/routers/validator.py:434`) ist bei leerer Menge
  ein No-Op (`if real_ids and …`) — bewusst so eingeführt (fix-1948-s2), damit die vielen Tests mit
  `stages: []` nicht brechen. `_real_segment_ids_for_today` (`:421`) und `_synthesize_segment_times`
  (`:531`) nutzen beide **nur heute** (`trip_local_today`).

## Wichtiger Befund: der Endpoint ist nutzersichtbar

Die Beispiel-Warnung im Alarme-Reiter (Trip) ruft genau diesen Endpoint:
`frontend/src/lib/components/alerts-tab/alertPreviewHelpers.ts:61` `buildAlertPreviewPayload`
(`segment_id: '1'`, `segment_times 08:00–17:00`) → `POST /api/briefings/{id}/alert-preview?kind=route`
→ Delegate auf `alert_preview` (`validator.py:382`). Typischer Nutzerfall: Trip wird **geplant**, läuft
heute also nicht. Vorschlag 3 des Issues wörtlich („keine Etappe heute ⇒ 422") würde die
Beispiel-Warnung jedes nicht heute laufenden Trips abschalten — Regression für den Nutzer.

## Lösungsansatz (Tech-Lead-Entscheidung)

**Bezugstag statt „heute":** Eine Funktion bestimmt den Tag, dessen echte Segmente die Vorschau
nutzt: heute, wenn der Trip heute eine Etappe hat; sonst die nächste kommende Etappe; sonst (Trip
vorbei) die letzte. Dieselbe Funktion speist ID-Prüfung, `segment_times`-Synthese und Rendering
(eine Quelle, kein Drift).

1. `changes`-Rückfallpfad: statt `_stub_segment` die echten `TripSegment`s des Bezugstags
   (`convert_trip_to_segments`) — Distanz, Höhenmeter, Koordinaten, `distance_measured`,
   km-Spanne echt. `segment_times` des Payloads überschreiben nur Start/Ende (Datum = Bezugstag).
   Stundenreihe bleibt leer (der #1737-Pfad mit Anker liefert sie, wenn vorhanden) — das bleibt
   dokumentierte Grenze, aber nicht mehr still: siehe Punkt 4.
2. `official`-Zweig: `segment_km=measured_segment_km(<echte Segmente des Bezugstags>)`.
3. ID-Prüfung gegen den Bezugstag; leer nur noch, wenn der Trip **gar keine** auswertbaren
   Etappen/Wegpunkte hat → dann 422 mit eigenem Code (z. B. `trip_ohne_segmente`), sobald der Payload
   eine `segment_id` nennt (changes / official mit nicht-leerer `segment_ids`). Kein stilles
   Akzeptieren erfundener IDs mehr.
4. Offen für die Spec: ob die Antwort kenntlich macht, dass keine Stundenreihe vorlag (z. B. Feld
   `stundenreihe: false` / Bezugstag) — hilft Validatoren, „nicht beobachtbar" von „fehlt" zu
   unterscheiden. Additiv, bricht keine Clients.

Nicht im Zuschnitt: `onset`-Zweig (`km_from/km_to` aus dem Payload) — dort ist der Payload das
synthetische Ereignis selbst; Plausibilisierung gegen die Trip-Länge wäre ein eigenes Thema.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/validator_render_service.py` | `_stub_segment`, `_deviation_preview_message`, `_render_official_preview` — Kernänderung |
| `api/routers/validator.py` | `_real_segment_ids_for_today`, `_reject_unknown_segment_id`, `_synthesize_segment_times`, Endpoint `alert_preview` |
| `src/services/trip_segments.py` | `convert_trip_to_segments`, `measured_segment_km` (Quelle) |
| `src/services/trip_day.py` | `trip_local_today` (Ortstag) |
| `src/output/renderers/alert/official_alerts.py:2476` | `build_official_alert_notices(..., segment_km=…)` — nur aufrufen (#1929-Sperrzone) |
| `src/i18n/messages/{de,en}/api.json` | neuer Fehlercode, Katalog-Parität (`tests/test_i18n_api_katalog_paritaet.py`) |
| `frontend/.../alertPreviewHelpers.ts` | Nutzer-Aufrufer, bleibt unverändert |
| `docs/reference/api_contract.md` | Alarm-Vorschau-Vertrag (SSOT) |
| `docs/specs/modules/issue_221_validator_observability_endpoints.md` | Stub ist dort spezifiziert (Z. 48, 190, Rückgabeform Z. 248 veraltet) — Zuschnittsgrenze mitziehen |
| `.claude/agents/external-validator.md` | Warnung zum Messaufbau; nach Fix anpassen |

## Existing Patterns
- Echte Segmente + Zeitüberschreibung: `_synthesize_segment_times` (`validator.py:531`).
- Gemessene km-Spanne: `measured_segment_km(segments)` wie im Versand (`trip_alert.py:3543`).
- Fehler-Codes: `api_fehler(422, "<code>", user_id, …)` + Katalog de/en.

## Dependencies
- Upstream: `convert_trip_to_segments`, `measured_segment_km`, `trip_local_today`, Renderer `to_alert_message`.
- Downstream: Alarme-Reiter-Beispielwarnung (Trip), External-/Staging-Validator, ~13 Testdateien mit
  `stages: []`-Trips (u. a. `test_alert_preview_payload_exclusivity.py`,
  `test_issue_221_validator_endpoints.py`, `test_alert_preview_input_validation.py`,
  `test_alert_preview_official_render.py`, `test_alert_preview_no_side_effects.py`).

## Risks & Considerations
- **Testmigration:** Tests mit `stages: []` + `segment_id` im `changes`/`official`-Payload brauchen
  einen Trip mit Etappe (Hilfsfunktion `tests/helpers/ortstag.py`), sonst 422. Erwartet, kein Bruch
  von Verhalten — der alte No-Op war genau der Defekt.
- **Datum der Segmente:** Bezugstag ≠ heute verändert ggf. Wochentags-/Tagesbezug im Alarmtext
  (Beginn „morgen"/Wochentag). Muss in der Spec festgelegt und getestet werden.
- **Kein Netz in der Kern-Schicht:** `convert_trip_to_segments` ist rein rechnerisch — gut.
- **Kanalparität:** alle vier Ausgaben (Mail/Telegram/SMS/Betreff) aus demselben Nachrichtenobjekt — unverändert.
- **Mandantentrennung:** Trip kommt bereits user-scoped (`_load_trip_for_validator`); Zwei-Nutzer-Test bestehend (`test_preview_alert_preview_reject_foreign_trip_id.py`).

## Analysis

### Type
Bug (Messwerkzeug zeigt ein selbst erzeugtes Fehlen; stille Annahme erfundener Segment-IDs). Fachlich
eine Erweiterung der #221-Zuschnittsgrenze (Stub war damals spezifiziert, siehe Issue-Kommentar).

### Verifiziert am Code (origin/main b67cad4dd)
- Rückfallpfad `_deviation_preview_message` → `_stub_segment` (Distanz/Höhenmeter 0, `distance_measured`
  False, Datum = UTC-heute) bestätigt.
- `_render_official_preview` ruft `build_official_alert_notices` ohne `segment_km` — bestätigt.
- `_real_segment_ids_for_today` / `_synthesize_segment_times` nur `trip_local_today` — bestätigt;
  `convert_trip_to_segments(trip, d)` liefert leer, wenn `get_stage_for_date(d)` keine Etappe hat.
- Segment-IDs sind „1..N" je Tag; das Frontend sendet fest `'1'` → passt zu jedem Bezugstag mit ≥2 Wegpunkten.
- Frontend `AlertPreviewCard.svelte` zeigt für Ortsvergleich ohne Orte einen Hinweis statt 422
  (`alert-preview-no-locations`); für einen Trip ohne Etappen fehlt das Pendant.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `api/routers/validator.py` | MODIFY | `_real_segment_ids_for_today` → Bezugstag-Variante; `_reject_unknown_segment_id` ohne No-Op (leer ⇒ 422 `trip_ohne_segmente`); `_synthesize_segment_times` auf Bezugstag |
| `src/services/validator_render_service.py` | MODIFY | Rückfall rendert echte `TripSegment`s des Bezugstags (Zeiten aus `segment_times` überschreiben Start/Ende); `official` mit `segment_km=measured_segment_km(...)`; `_stub_segment` entfällt oder nur noch für Compare-freie Altfälle |
| `src/services/trip_day.py` (oder neues Helferlein in `trip_segments.py`) | MODIFY | `preview_reference_date(trip, now)`: heute → nächste Etappe → letzte Etappe |
| `src/i18n/messages/{de,en}/api.json` | MODIFY | Code `trip_ohne_segmente` (Parität) |
| `frontend/.../AlertPreviewCard.svelte` + i18n | MODIFY | Hinweis „Trip hat noch keine Etappen mit Wegpunkten" statt Fehlertext (Pendant zu no-locations, gleiche Komponente) |
| `tests/tdd/test_alert_preview_*.py`, `tests/integration/test_issue_221_validator_endpoints.py` | MODIFY | Fixtures mit `stages: []` + `segment_id` auf Trip mit Etappe umstellen |
| `tests/tdd/test_alert_preview_echte_segmente.py` | CREATE | RED: km-Spanne/Distanz im changes- und official-Zweig sichtbar; erfundene ID bei nicht-heute-Trip ⇒ 422; Trip ohne Etappen ⇒ 422 `trip_ohne_segmente` |
| `docs/reference/api_contract.md`, `docs/specs/modules/issue_221_validator_observability_endpoints.md`, `.claude/agents/external-validator.md` | MODIFY | Vertrag/Zuschnitt nachziehen (Rückgabeform Z. 248 aktualisieren) |

### Scope Assessment
- Files: ~8 Code/Test + 3 Doku
- Estimated LoC: +180/-60 (davon ~100 Tests)
- Risk Level: MEDIUM — nutzersichtbare Beispiel-Warnung im Alarme-Reiter hängt am selben Endpoint;
  Datumswechsel des Segments (Bezugstag statt heute) kann den Tagesbezug im Text („morgen", Wochentag) ändern.

### Technical Approach
Wie im Lösungsansatz oben (Bezugstag als EINE Quelle für ID-Prüfung, Zeitsynthese und Rendering).
Ergänzungen aus der Verifikation:
- Rendering-Rückfall: Segmente aus `convert_trip_to_segments(trip, bezugstag)`, nur die im Payload
  genannten IDs, Start/Ende aus `segment_times` auf das Datum des Bezugstags in Trip-Zone gesetzt
  (nicht UTC wie heute im Stub). Leere Stundenreihe bleibt (Anker-Pfad #1737 unverändert).
- `official`: `segment_km` aus denselben Bezugstag-Segmenten; `segment_ids=[]` bleibt erlaubt.
- `onset` und Compare-Zweig unverändert (nicht im Zuschnitt).
- Antwort additiv um `bezugstag` (ISO-Datum) und `stundenreihe: bool` erweitern, damit Validatoren
  „nicht beobachtbar" von „fehlt" unterscheiden — Tech-Lead-Entscheidung: ja, additiv, kein Bruch.
- Frontend: 422 `trip_ohne_segmente` vorab vermeiden (Trip ohne Etappe mit ≥2 Wegpunkten ⇒ Hinweis,
  kein Abruf), gleiche Komponente, keine neue.

### Dependencies
`convert_trip_to_segments`, `measured_segment_km`, `trip_local_today`, `Trip.get_stage_for_date`,
`to_alert_message`, `build_official_alert_notices` (nur Aufruf, #1929-Sperrzone).

### Open Questions
- Keine Produktfrage offen: Bezugstag-Regel und Hinweis bei Trip ohne Etappen sind technische
  Konsequenzen, die die Beispiel-Warnung für geplante Trips erhalten (sonst Regression). Wird in der Spec
  als AC festgehalten und mit der Spec freigegeben.
