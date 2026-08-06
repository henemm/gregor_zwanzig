# Kontext: #923b — SMS-Fidelity-Fix an die live gerenderte Komponente anschließen

## Vorgeschichte

#923 wurde gegen `frontend/src/lib/components/trip-detail/ChannelFidelitySMS.svelte`,
`ChannelPreviewCard.svelte` und `ChannelPreviewBlock.svelte` implementiert, spezifiziert,
getestet, adversary-verifiziert (VERIFIED) und gemergt (PR #1540, main-Commit 45af714e).
Die Staging-Verifikation (Playwright, echter Klickpfad) fand danach: **keine dieser drei
Dateien wird von irgendeiner Route importiert.** Sie sind toter Code, verwaist seit #587
("Wetter-Metriken-Tab — funktionaler Editor, Detail-Zeile entfernt"), der die Anzeige auf
einen neuen Tab umgestellt hat, ohne die Altdateien zu löschen. Nur `organisms/index.ts`
re-exportiert sie (täuscht Lebendigkeit vor — bekanntes Muster, siehe
`reference_trip_detail_dead_overview_components` in der Memory).

Die tatsächlich live gerenderte Komponente im Wetter-Metriken-Tab (eingebunden in
`TripEditView.svelte` UND `TripNewEditor.svelte` über `shared/WeatherMetricsTab.svelte`) ist:

**`frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2MailPreview.svelte`**

Diese Datei hat exakt den ursprünglichen, in #923 beschriebenen Fehler weiterhin:
- Eigenes hartcodiertes `SMS_TOK`-Dict (Zeile 131)
- Hartcodiertes 140-Zeichen-Limit (Zeile 265: `{smsLine.length}/140 Zeichen`)
- Erfundener Präfix/Anhang (`Z:WATCH`, Zeile 142)

Live auf Staging bestätigt (2026-08-06): sichtbarer Text
`BSPTOUR: N8 D11 W12@11(24@13) G25@12(43@14) R3.2 TH5%@12 Z:WATCH`, Anzeige `64/140 Zeichen`.

## Was aus #923 wiederverwendet werden kann

Der Backend-Teil ist solide und braucht KEINE Änderung (isoliert auf Staging getestet,
AC-1/2/3/5 PASS):
- `POST /api/_validator/sms-fidelity-preview` (`api/routers/validator.py`)
- `render_sms_fidelity_preview()`/`build_sms_fidelity_specs()`
  (`src/services/validator_render_service.py`)
- `render_line_with_survivors()` (`src/output/tokens/render.py`)
- Go-Proxy-Route (`internal/router/router.go`, `internal/handler/proxy.go`)

## Neuer Befund: AC-4-Verletzung im Backend (unabhängig vom Verdrahtungsfehler)

`temperature_night` (aus dem parallel gemergten #1484) hat in `src/app/metric_catalog.py`
kein `sms_code` (leer), erscheint aber trotzdem in `carried_ids` der Endpoint-Antwort, weil
`SMS_SYMBOL_BY_METRIC`/`SMS_MULTI_SYMBOLS_BY_METRIC` (`src/output/renderers/sms_trip.py:120`)
das Symbol "N" dafür führt, ohne dass der Katalog das spiegelt. Zwei Quellen widersprechen
sich. AC-4 verlangt: eine Metrik ohne `sms_code` darf nicht in `carried_ids` erscheinen.

## Delta für #923b

1. **`WeatherV2MailPreview.svelte`**: eigene `SMS_TOK`/Kürzungslogik/140-Konstante entfernen,
   stattdessen den bestehenden Endpoint `POST /api/_validator/sms-fidelity-preview` aufrufen
   (Muster aus #923: `ChannelFidelitySMS.svelte` als Vorlage für das Lade/Fehler-Pattern,
   ggf. `loadSmsFidelityPreview()` aus `smsFidelityPreview.ts` wiederverwenden — prüfen ob
   diese Utility-Datei WeatherMetricsTab-kompatibel ist oder angepasst werden muss).
2. **Tote Dateien aufräumen**: `ChannelFidelitySMS.svelte`, `ChannelPreviewCard.svelte`,
   `ChannelPreviewBlock.svelte` sowie deren Re-Exports in `organisms/index.ts` — löschen statt
   liegen lassen (Projektkonvention: kein halb-fertiger/verwaister Code). Zugehörige Tests aus
   #923 (`channel_sms_fidelity_backend_render.test.ts`, Teile von
   `sms_fidelity_preview_fetch.test.ts`) migrieren auf die neue Zielkomponente oder anpassen.
3. **Backend-Fix AC-4**: `temperature_night` in `src/app/metric_catalog.py` mit passendem
   `sms_code` versehen (oder alternative Lösung — z. B. `carried_ids`-Filterung zusätzlich
   gegen Katalog-`sms_code` statt nur gegen `SMS_SYMBOL_BY_METRIC` prüfen — Root-Cause-
   Entscheidung Teil der Spec-Phase).

## Betroffene Dateien (vorläufig, Spec verfeinert)

1. `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2MailPreview.svelte`
2. `frontend/src/lib/components/trip-detail/ChannelFidelitySMS.svelte` (löschen)
3. `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte` (löschen)
4. `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` (löschen)
5. `frontend/src/lib/components/organisms/index.ts` (Re-Exports entfernen)
6. `src/app/metric_catalog.py` (AC-4-Fix) ODER `src/services/validator_render_service.py`
   (alternative Root-Cause-Lösung)
7. Testdateien migrieren/anpassen

## Out of scope

- Der Backend-Endpoint selbst (bereits korrekt, keine Änderung nötig außer AC-4-Fix).
- `ChannelFidelityEmail.svelte`/`ChannelFidelityBubble.svelte` — falls diese ebenfalls tot
  sind, ist das ein separater Fund, nicht Teil dieser Scheibe (prüfen, aber nicht in dieser
  Spec beheben, außer der Prüfschritt zeigt dieselbe Verdrahtungslücke am selben Ort).
