# Context: fix-2981-vorlage-name-en

## Request Summary
Issue #2981 (Teil von #2913): Bei Sprache EN zeigt die Vorlage-Karte im Reiter Wetter die
eingebauten Vorlagennamen deutsch („Wandern" statt „Hiking"). Eingebaute Vorlagennamen
müssen über den Katalog laufen (ADR-0104).

## Ursache (belegt)
- `src/app/metric_catalog.py:1353` `WEATHER_TEMPLATES` liefert je Systemvorlage ein festes
  deutsches `label` (7 IDs: alpen-trekking, wandern, skitouren, wintersport, radtour,
  wassersport, allgemein). `/api/templates` reicht es unverändert durch.
- `frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts:49` (`vorlagenListe`)
  übernimmt `t.label` ungefiltert in `VorlageEintrag.label`.
- `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte:38,71,94,115,81`
  zeigt dieses Label (Kopfzeile, Picker-Optionen, „Auf ‚…' zurücksetzen", Verlust-Text,
  Rückfrage `{neu}` über `waehlen(v.id, v.label, …)`).

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts | Ort der Übernahme des Server-Labels |
| frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte | Anzeige |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | Katalog `wetter.vorlage.*` (Ziel für neue Schlüssel) |
| frontend/src/lib/i18n/messages/{de,en}/trip.json | Vorbild `trip.aktivitaet.{alpen_trekking,wandern,skitouren}` |
| frontend/src/lib/components/compare/subscriptionHelpers.ts:193 | Vorbild ID→Katalogschlüssel-Map (`PROFILE_LABELS`) |
| frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte | Alter Wetter-Metriken-Tab, zeigt `t.label` ebenso deutsch (gleiche Ursache) |
| internal/handler/metric_preset.go:48 | Namensschutz Systemvorlagen (deutsche Namen) — unberührt |

## Existing Patterns
- ID → `MessageKey`-Map im Frontend, Anzeige per `$t`/`tr` (subscriptionHelpers `PROFILE_LABELS`).
- Server-Label bleibt deutsch (Protokoll/Python-SSOT), Übersetzung nur in der Anzeige.

## Dependencies
- Upstream: `/api/templates` (id, label, ampel).
- Downstream: VorlageKarte, WetterTabInhalt; `vorlagenListe`-Tests in `shared/wetter-tab/__tests__`.

## Existing Specs
- `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` (Vorlage-Karte)
- `docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md`
- `docs/reference/i18n_konventionen.md`

## Risks & Considerations
- Unbekannte/neue Vorlagen-ID: Fallback auf Server-Label (nie leer).
- Eigene Vorlagen (Nutzername) dürfen NICHT übersetzt werden.
- DE muss unverändert bleiben (`deutsch_unveraendert.test.ts` listet DE-Schlüssel).
- Katalog-Paritätstests DE/EN: neue Schlüssel in beiden Sprachen.
- Englische Begriffe: an `trip.aktivitaet.*` angleichen („Alpine trekking", „Hiking", „Ski touring"...).

## Analysis

### Type
Bug (EN-Lücke, ADR-0104)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/shared/wetter-tab/vorlageName.ts | CREATE | Map Systemvorlagen-ID → Katalogschlüssel `wetter.vorlage.name.<id>` (7 IDs) + Funktion `vorlageNameKey(id)`; unbekannte ID → `null` (Fallback Server-Label) |
| frontend/src/lib/i18n/messages/de/wetter.json | MODIFY | 7 Schlüssel `wetter.vorlage.name.*` mit den heutigen deutschen Labels (DE unverändert) |
| frontend/src/lib/i18n/messages/en/wetter.json | MODIFY | 7 Schlüssel EN: Alpine trekking, Hiking, Ski touring, Winter sports, Cycling tour, Water sports, General (an `trip.aktivitaet.*` / `bausteine.profil.*` angeglichen) |
| frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte | MODIFY | Anzeige von Kopfzeile, Picker-Option, Zurücksetzen-Knopf, Verlust-Text und Rückfrage-`{neu}` über `$t(key)` statt `v.label`, reaktiv bei Sprachwechsel |
| frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte | MODIFY | Gleiche Ursache im alten Wetter-Metriken-Tab (noch in Trip-/Vergleich-Anlegen-Editor eingebunden): Chip-Text und title über denselben Helfer |
| frontend/src/lib/components/shared/wetter-tab/__tests__/ (neu) | CREATE | Test: EN liefert „Hiking“ für `wandern`, DE „Wandern“, unbekannte ID → Server-Label, eigene Vorlage unübersetzt |

### Scope Assessment
- Files: ~6
- Estimated LoC: +60/-8
- Risk Level: LOW (reine Anzeige, Server-Label/Protokoll unverändert)

### Technical Approach
Übersetzung nur in der Anzeige (Muster `PROFILE_LABELS` in subscriptionHelpers): Server liefert weiter das deutsche
Label als Fallback; das Frontend ordnet bekannten Systemvorlagen-IDs einen Katalogschlüssel zu und übersetzt per `$t`
(reaktiv). `vorlagenListe` bleibt unverändert (`label` = Server-Fallback). Eigene Vorlagen (Nutzername) werden nie
übersetzt. Python `WEATHER_TEMPLATES` und Go-Namensschutz (`metric_preset.go`) bleiben unberührt.

### Dependencies
`/api/templates` (id, label). Konsumenten: VorlageKarte (WetterTabInhalt), WeatherV2PresetBar (WeatherMetricsTab).
Katalog-Paritätstest DE/EN und `deutsch_unveraendert.test.ts` müssen grün bleiben.

### Open Questions
- keine (Begriffswahl EN technisch an vorhandene Katalogbegriffe angeglichen)

## Nachtrag Phase 5 (TDD RED): Schnittstelle des Helfers

Die RED-Tests (`frontend/src/lib/components/shared/wetter-tab/__tests__/vorlageName.test.ts`) erwarten in `vorlageName.ts` zwei Exporte:

- `vorlageNameKey(id: string): MessageKey | null` — Map der 7 Systemvorlagen auf `wetter.vorlage.name.<id>`; unbekannte ID (auch Prototyp-Namen wie `constructor`) → `null`.
- `vorlageAnzeigename(lang: Lang | undefined, id: string, serverLabel: string | undefined): string` — bekannter Schlüssel → `trFor(lang, key)`, sonst Server-Label, ist das leer/fehlend → die ID. Die Svelte-Stellen nutzen dieselbe Funktion reaktiv mit `$locale` (z. B. `vorlageAnzeigename($locale, v.id, v.label)`), damit AC-6 ohne Neuladen wirkt.
