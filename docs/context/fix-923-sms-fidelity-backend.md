# Kontext: Issue #923 — Briefing-SMS-Fidelity über Backend-Feed

## Issue

**#923** — Briefing-SMS-Fidelity (`ChannelFidelitySMS.svelte`) über Backend-Feed statt hartcodiertem SMS_TOK.

Abgespalten aus #918 (Slice 3). `frontend/src/lib/components/trip-detail/ChannelFidelitySMS.svelte`
rendert SMS-Tokens hartcodiert in TypeScript (`SMS_TOK`/`smsRender`, Prefix `KHW03:`) —
verstößt gegen ADR-0011 (kein zweiter Renderer im Frontend). Die TS-Kürzungslogik ist zudem
sachlich ungenau: das echte SMS-Format (`docs/reference/sms_format.md` v2.18) ist ein festes
Positions-Template mit fester Prioritäts-Kürzungsreihenfolge (§6), nicht abhängig von der
Nutzer-Auswahlreihenfolge wie heute suggeriert.

## Ist-Zustand

- `ChannelFidelitySMS.svelte`: eigenes `SMS_TOK`-Dict (6 Metriken), eigene `smsRender()`-Kürzung
  nach 140-Zeichen-Budget in Auswahlreihenfolge `[...primary, ...secondary]`.
- `ChannelPreviewCard.svelte` (Zähler-Kachel "X als Code" / "X fallen weg"): **zweite, wörtlich
  gespiegelte Kopie** derselben `SMS_TOK`/Kürzungslogik (Code-Kommentar: "gespiegelt aus
  ChannelFidelitySMS.svelte"). Berechnet nur zwei Zahlen: `carried.length` und `dropped`
  (+ Ampel-Farbe warn/ok).
- Vorbild aus #918: `POST /api/trips/{id}/alert-preview` (`api/routers/validator.py:243`) —
  Frontend schickt Beispiel-Payload, Backend rendert mit dem echten Renderer, Frontend zeigt nur
  an. Kein `user_id` nötig — zustandslos, beispielwertbasiert, keine Trip-/Nutzerdaten.
- `GET /api/preview/{trip_id}/sms?demo=true` (Epic #140) passt NICHT: rendert die **gespeicherte**
  `display_config`, die Editor-Vorschau braucht aber die **live editierte, ungespeicherte**
  primary/secondary-Auswahl.
- `sms_code` liegt beiden Frontend-Komponenten bereits über `/api/metrics` →
  `metricById[id]?.sms_code` vor (`api/routers/config.py:81`, `frontend/src/lib/types.ts:175`).
- `render_line()` (`src/output/tokens/render.py`) kürzt intern bereits nach der echten
  Prioritäts-Logik, gibt aber nur den fertigen String zurück — welche Token-Symbole überlebt
  haben, geht verloren.

## PO-Entscheidungen (2026-08-05)

1. Vorschau bleibt nur Abend-Version, kein Morgen/Abend-Umschalter — kein Delta.
2. **"Verlinken statt kopieren"**: `ChannelPreviewCard.svelte` bekommt KEINE eigene Kopie der
   Kürzungslogik, sondern ruft denselben neuen Backend-Endpoint auf und leitet ihre zwei Zahlen
   aus `carried_ids` ab (`dropped = angefragte_ids − carried_ids`, "kein Code" vs. "Zeichenlimit"
   über bereits vorhandenes `sms_code`). Damit wird die Fundstelle ins Delta aufgenommen statt in
   #1199 vermerkt.

## Delta / geplante Umsetzung

Neuer stateless Endpoint `POST /api/_validator/sms-fidelity-preview` in `api/routers/validator.py`,
Body `{"metric_ids": [...]}` (= `[...primary, ...secondary]` aus dem Editor). Antwort:
`{line, char_count, max_length, carried_ids}`.

Dahinter: neue Funktion in `src/services/validator_render_service.py`, die eine feste
Beispiel-`SegmentWeatherData` baut (Werte wiederverwendbar aus bereits vorhandenen
`SAMPLE_BY_ID`/`SAMPLE_HOURS`-Konstanten in `ChannelFidelityEmail.svelte`/
`ChannelFidelityBubble.svelte`), daraus `disabled_specs` ableitet und `build_token_line()`
(`src/output/tokens/builder.py` — dieselbe Assemblierungsfunktion wie der Versand) direkt aufruft.
**Kein Umbau von `src/output/renderers/sms_trip.py`** (Versand-Renderer bleibt unangetastet).

`src/output/tokens/render.py` bekommt eine zweite, kleine additive Funktion (~10 Zeilen), die
dieselben privaten Kürzungs-Helfer wie `render_line()` wiederverwendet und zusätzlich die
überlebenden Token-Symbole zurückgibt. Bestehendes Verhalten von `render_line()` bleibt
unangetastet — kein Risiko für Produktivpfade E-Mail/Telegram/SMS-Versand.

`ChannelFidelitySMS.svelte`: `SMS_TOK`/`smsRender`/`SMS_TOKEN_MEANING` raus, `api.post(...)`
nach dem Lade/Fehler-Pattern von `AlertPreviewCard.svelte`, Anzeige der Backend-Zeile +
Zeichenzähler.

`ChannelPreviewCard.svelte`: eigenes `SMS_TOK`/`smsCounters` raus, eigener `api.post(...)` an
denselben Endpoint, Zahlen aus `carried_ids`/Gesamtzahl abgeleitet.

`ChannelPreviewBlock.svelte` (gemeinsamer Elternteil) wird NICHT angefasst — beide Kinder rufen
unabhängig denselben zustandslosen Endpoint auf (zwei Requests statt einem, bewusst in Kauf
genommen, um keine dritte Datei für Parent-State-Sharing zu brauchen; Zusammenlegen ist ein
trivialer Folge-Schritt, kein Blocker).

## Betroffene Dateien (5, im Scoping-Limit)

1. `api/routers/validator.py` — neuer Endpoint
2. `src/services/validator_render_service.py` — neue Funktion
3. `src/output/tokens/render.py` — additive Funktion für überlebende Symbole
4. `frontend/src/lib/components/trip-detail/ChannelFidelitySMS.svelte`
5. `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte`

LoC-Schätzung: grob neutral bis leicht rückläufig (beide Svelte-Komponenten verlieren mehr Zeilen
Kürzungslogik als sie an Fetch-Code gewinnen; Backend-Ergänzungen klein und additiv). Weit unter
dem +/-250-LoC-Limit.

## Mandantenfähigkeit / user_id

Neuer Endpoint braucht **keine** `user_id` — zustandslos, beispielwertbasiert, kein Zugriff auf
Trip- oder Nutzerdaten. Konsistent mit dem bestehenden `alert-preview`/`compare-email-preview`-
Muster. Kein Cross-User-Risiko.

## Pendant-Gate / Trip-Compare-Teilung

Kein Compare-Pendant-Problem: beide geänderten Komponenten liegen unter `trip-detail/`, nicht
unter `compare*`/`trip-new`. `pendant_gate` greift hier nicht (reine Änderung, keine Neuanlage).

## Out of scope

Alert-Vorschau (= #918, bereits umgesetzt), Versandlogik (`sms_trip.py` unangetastet).

## Implementierungshinweis (nicht scope-relevant)

Mit Backend-Anbindung entsteht ein Ladezustand bei jedem Checkbox-Toggle der Metrik-Auswahl
(heute ist die Vorschau clientseitig instant). Empfehlung: einfaches Debounce (250–400ms) auf
Primary/Secondary-Änderungen beim Bauen berücksichtigen — kein Blocker für die Spec, aber relevant
für `/40-tdd-red`/`/50-implement`.
