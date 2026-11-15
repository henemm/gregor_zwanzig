# Context: fix-2946-sichtweite-einheit

## Request Summary
Im Wetter-Reiter (Trip und Orts-Briefing) zeigt die Zeile „Sichtweite" Meter-Grenzwerte mit der Einheit „km" („unter 300 km", „grün: ab 1000 km", Untertitel „km"). Soll laut Mockup `mockup-hub-fassung3.html`: „m" (Untertitel „m · Minimum"), DE und EN.

## Ursache (belegt)
- `api/routers/config.py:131` — `GET /metrics` liefert `"unit": m.display_unit if m.display_unit else m.unit`. Für `visibility` ist `unit="m"`, `display_unit="km"` (`src/app/metric_catalog.py:55`, `:646`) ⇒ API-Feld `unit` = „km".
- `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts:78` übernimmt `k.unit` in `MetrikEigenschaften.unit`.
- Dieselbe `unit` setzt die Einheit in `gruenZeile` (Z. 252), `untertitel` (Z. 289) und `erklaersatz` (Z. 313). Die Ampel-Grenzwerte (Vorlagen/Abo, `lower.yellow` usw.) sind aber in der Speicher-Einheit (Meter) gespeichert ⇒ Zahl in m, Einheit km.
- Test schreibt den Fehler fest: `frontend/src/lib/components/shared/wetter-tab/__tests__/ampelModell.test.ts:200` erwartet `{ ab: 2000, einheit: 'km' }`.
- Ampel-Leiste (`AmpelLeiste.svelte`/`ampelLeiste.ts`) zeigt nur Zahlen, keine Einheit ⇒ nicht betroffen.

## Related Files
| File | Relevance |
|------|-----------|
| `api/routers/config.py` (~Z. 131) | Liefert `unit` = Anzeige-Einheit; hier zusätzliche Grenzwert-Einheit ergänzen |
| `src/app/metric_catalog.py` | `unit` (Speicher) vs. `display_unit` (Anzeige); nur visibility hat `display_unit` |
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | `eigenschaftenAusKatalog`, `gruenZeile`, `untertitel`, `erklaersatz` |
| `frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte` | Zeigt die drei Texte an |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte`, `wetterTabLaden.ts`, `routes/_home/homeHeroProps.ts` | Weitere Aufrufer von `eigenschaftenAusKatalog` |
| `__tests__/ampelModell.test.ts` | Falsche Erwartung Z. 200 |
| `docs/reference/api_contract.md` Z. 276 | Zeile `/api/metrics`: neues Feld dokumentieren |

## Existing Patterns
- `unit` aus `/api/metrics` ist bewusst die **Anzeige-Einheit** für Layout/Spaltenköpfe (Mail zeigt Sichtweite in km): Abnehmer `ActiveMetricRow.svelte`, `BucketSectionOff.svelte`, `MetricOffShelf.svelte`, `WeatherV2Reihenfolge.svelte`, `WeatherConfigDialog.svelte`, `TablePreview`. Dort ist „km" korrekt ⇒ `unit` nicht ändern.
- Additive API-Felder sind übliche Praxis (`label_de`/`label_en` #2662).
- `src/output/metric_format.py` `_UNIT_CONVERSION` (m→km, Faktor 0,001) ist das Python-Muster der Umrechnung.

## Dependencies
- Upstream: Python-Katalog `metric_catalog.py`, Go-Proxy `internal/router/router.go:280` (reiner Durchreicher, keine Struct ⇒ neues Feld kommt durch).
- Downstream: alle Wetter-Reiter-Zeilen (Trip + Orts-Briefing teilen `shared/wetter-tab`), Übersicht (HubOverview) nutzt nur Eigenschaften, keine Einheit im Text.

## Lösungsrichtung (für Analyse)
Neues additives Feld je Metrik in `GET /api/metrics`, z. B. `threshold_unit` = `m.unit` (Einheit der Ampel-Grenzwerte). `eigenschaftenAusKatalog` liest es (Rückfall auf `unit`), Grünzeile/Untertitel/Erklärsatz nutzen es. Ergebnis wie Mockup: Meter durchgehend. Alternative (km mit Umrechnung) widerspricht dem Mockup und erzeugt Bruchzahlen (0,3 km).

## Existing Specs
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md`, `feat_2794_s3a_teil3_wetter.md`, `feat_2913_scheibe_c_wetter_rest.md` (Wetter-Reiter, Herkunft #2913)

## Risks & Considerations
- `unit` darf sich für die anderen Abnehmer nicht ändern (Layout zeigt km für Sichtweite).
- Alle anderen Metriken: `threshold_unit == unit`, also keine Verhaltensänderung.
- Test aus Nutzersicht: Erwartung im Modell-Test auf „m" korrigieren und mit echtem Katalog-Fixture (API-Antwort) rot nachweisen, nicht mit handgeschriebener Eigenschaft (sonst wieder Mock-Theater).
- Python-Test für das neue API-Feld (visibility ⇒ `threshold_unit="m"`, `unit="km"`).

## Analysis

### Type
Bug

### Verifikation (Phase 2, 15.11.2026)
Ursache im Code bestätigt: `api/routers/config.py:131` liefert `unit = display_unit or unit`; nur `visibility` hat `display_unit="km"` (`src/app/metric_catalog.py:654`). `ampelModell.ts` nutzt `eig.unit` an genau drei Stellen (Z. 252 Grünzeile, Z. 289 Untertitel, Z. 313 Erklärsatz); weitere Nutzer von `MetrikEigenschaften.unit` gibt es nicht. Ampel-Leiste zeigt keine Einheit. Der Korridor-/Vergleichs-Editor (`compareMetricCatalogLoader.ts`, Metrik `visibility_min_m`) läuft über einen eigenen Katalog und ist nicht betroffen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `api/routers/config.py` | MODIFY | additives Feld `threshold_unit: m.unit` je Metrik in `GET /api/metrics` |
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | MODIFY | `MetrikEigenschaften.threshold_unit`; `eigenschaftenAusKatalog` liest es (Rückfall `unit`); Grünzeile/Untertitel/Erklärsatz nutzen die Grenzwert-Einheit |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/ampelModell.test.ts` | MODIFY | Erwartung Z. 200 auf `m`; neuer Test aus Katalog-Antwort (visibility unit=km, threshold_unit=m ⇒ „m“ in allen drei Texten) |
| `tests/…` (Python, bestehender `/metrics`-Test oder neu) | MODIFY/CREATE | visibility ⇒ `unit="km"`, `threshold_unit="m"`; alle anderen Metriken `threshold_unit == unit` |
| `docs/reference/api_contract.md` | MODIFY | neues Feld `threshold_unit` dokumentieren |

### Scope Assessment
- Files: 5
- Estimated LoC: +40/-5
- Risk Level: LOW (additives Feld; `unit` bleibt für Layout/Mail-Spaltenköpfe unverändert; nur visibility verhält sich anders)

### Technical Approach
Option A (empfohlen): Meter durchgehend wie Mockup, über additives API-Feld `threshold_unit` (Einheit, in der die Ampel-Grenzwerte gespeichert sind = Katalog-`unit`). Frontend nutzt es für alle drei Texte, Rückfall auf `unit` bei älterer Antwort.
Verworfen: B (km mit Umrechnung) – widerspricht Mockup, Bruchzahlen (0,3 km), Umrechnung auch bei Eingabe nötig. C (im Frontend `visibility` hart auf „m“) – Sonderfall-Hartkodierung statt Katalog als Quelle.
Sprachen: Einheiten-Token „m“ ist sprachneutral (nicht übersetzt) ⇒ DE und EN automatisch korrekt.

### Dependencies
Go-Proxy `internal/router/router.go:280` reicht die Antwort ohne Struct durch ⇒ kein Go-Change. Aufrufer `wetterTabLaden.ts`, `HubOverview.svelte` bekommen das Feld automatisch über `eigenschaftenAusKatalog`.

### Open Questions
- keine (Mockup legt Meter fest)
