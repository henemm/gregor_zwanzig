# Context: fix-3283-wsw-optik

## Request Summary
Issue #3283 (Epic #3122): Sieben Optik-Befunde der Bildprüfung (ADR-0112, Runde 1 aus #3154) an der Karte „Was steht wo“ (Reiter Wetter) beheben. Fertig, wenn die Bildprüfung (Trip, drei Orte, ein Ort; DE und EN) keinen dieser Befunde mehr meldet und der Text-Abgleich `--strict` grün bleibt (PO-Entscheidung 23.11.2026, aus AC-13 von feat_3154).

## Befunde → Ursache

| # | Befund | Ursache (file:line) | Ort |
|---|--------|--------------------|-----|
| 1 | Abgeschnittene Beispielwerte (`61 …`, `Wolken …`, `freundl…`) | `.et-beispiel` mit ellipsis, `EinstellTabelle.svelte:217-227`; schmale Spalten fest 120px (`:82`), Kanalspalten `minmax(120px,1fr)`; Mockup: Kanäle `minmax(150px,1fr)`, Zusatzspalten 118px | Frontend |
| 2 | Beispielwerte in Stundenverlauf/Ausblick und SMS-Fensterwerte (`D14/18`, `FN12`) | Zellen werden für `schmal`-Spalten nicht anders behandelt (`EinstellTabelle.svelte:124-133`); Backend liefert Beispiele: `_trip_ausblick` `placements_view_service.py:465-482`, SMS-Fenster `_trip_sms_werte` `:407-432`, Orte `_spalten_beispiel` `:756-758`. Mockup Fassung 4: Zusatzspalten nur Haken + Roh/Einfach (`xcell` :698ff); SMS-Fensterwerte leer, nur `temperature_night` → `N10` | Backend + Frontend |
| 3 | E-Mail-Beispiel ohne Spaltenkürzel | `_html_stundentabelle` `:539-546` / `_spalten_beispiel` `:518-530` nehmen nur td-Text; `_col_labels` `:533` hätte `Temp`/`Gust`. Mockup `exCell` :605ff: `${COLL[id]} ${wert}`, reine Symbole ohne Präfix | Backend |
| 4 | Telegram „nur Tageswert“ zu früh (Gewitter, Gefühlte) | `_trip_nur_tageswert` `:448-462` markiert jede Metrik ohne Telegram-Spalte; Soll (ADR-0124 Nr. 3, AC-28 feat_3122): erst ab der achten Metrik (Mockup `tgCut = slice(7)` :686) | Backend |
| 5 | „● Gespeichert“ ragt über Kartenrand | Nicht die Karte: `ui/SaveIndicator.svelte:66-70` `position:fixed; bottom/right 16px`, eingebunden in `SubscriptionHeader.svelte:190-192`; liegt im Element-Screenshot über der Karte | Frontend (Prüfaufbau/Indicator) |
| 6 | Einfach-Symbole E-Mail klein/kontrastarm | Symbol steht als Text in `.et-beispiel` (xs, ink-2) | Frontend |
| 7 | Legende: lange Kürzel kleben, fett | `WasStehtWoKarte.svelte:336-357` flex + `dt min-width 60px; font-weight 600`; Mockup :668: `dl` Grid `auto 1fr`, gap `4px 14px`, `dt` Mono normal | Frontend |

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/molecules/EinstellTabelle.svelte | Zellaufbau, Spaltenbreiten, Beispiel-/Ampel-CSS |
| frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte | Legende, Karte |
| frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts | `zelleAus` reicht `example`/`marke` durch, `schmal: s.abgesetzt` |
| frontend/src/lib/components/ui/SaveIndicator.svelte | fixes Etikett |
| src/services/placements_view_service.py | Beispielwerte, Marke nur_tageswert |
| src/services/placements_beispiel.py | `VERSION` der Beispielwerte |
| docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html + bilder-fassung4/was-steht-wo-*.png | Soll-Bild |

## Existing Patterns
- Frontend-Tests `node:test` (`npm test -- <datei>`), Karte: `organisms/__tests__/was_steht_wo_karte.test.ts`.
- Backend: `tests/tdd/test_placements_*.py`.
- Text-Abgleich: `cd frontend && npm run elementliste:abgleich -- --scope wetter --strict [--sprache en]`.
- Bildabgleich-Vorlage: `frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts`; Bildprüfer-Agent `.claude/agents/mockup-bildpruefer.md`.

## Dependencies
- Upstream: Placements-API (Python) → Go-Proxy → Karte.
- Downstream: EinstellTabelle wird auch von anderen Einstellkarten genutzt (Spaltenbreite/Beispiel-CSS-Änderung muss geprüft werden); Beispiel-Version wirkt auf Cache/Speicherung.

## Existing Specs
- docs/specs/modules/feat_3122_was_steht_wo.md (Teil B Nr. 11, AC-21, AC-28, AC-33)
- docs/adr/0124-was-steht-wo-eine-tabelle.md (Nr. 3)
- docs/specs/modules/feat_3154_karte_abgleich (Abschluss-AC-13)

## Risks & Considerations
- Kein Produktkonflikt offen: Befund 2/3/4 lassen sich am Soll-Bild Fassung 4 + ADR-0124 + AC-28 entscheiden (Karte angleichen, nicht Soll nachziehen).
- Befund 5: SaveIndicator ist global; Fix darf andere Seiten nicht verschlechtern.
- EinstellTabelle geteilt (Trip/Vergleich-Teilung) — Änderungen gelten für beide Kontexte, das ist gewollt.
- Bildprüfung ein Ort fehlt im bestehenden Skript; Screenshots DE+EN für drei Kontexte nötig.
- Befund „Kürzel L doppelt“ gehört zu #3284, nicht hier.

## Analysis

### Type
Feature/Angleichung an Soll-Bild Fassung 4 (Bildprüfer-Befunde, kein Laufzeitfehler)

### Entscheidungen (Tech Lead, Grundlage: Soll-Bild Fassung 4, ADR-0124, AC-28 feat_3122)
- **B1** Kanalspalten `minmax(150px,1fr)`, Zusatzspalten 118px (Mockup :207f), nur über Tokens (`--g-size-*`, ggf. neu anlegen).
- **B2** Zusatzspalten (Stundenverlauf, Ausblick = `schmal`) zeigen nur Haken + Roh/Einfach, kein Beispielwert: Frontend unterdrückt `et-beispiel` bei `schmal` (Endpoint liefert weiter `example` — `test_placements_tabelle_endpoint.py` verlangt es, Datenwahrheit bleibt). SMS-Spalte: Beispiel nur für Metriken mit eigenem SMS-Token laut Mockup `TF`; abgeleitete Fenster-Kinder (`temperature_day_low/high`, `wind_chill_*`) ohne Beispiel, außer `temperature_night` (`N10`). Filter nur im Beispiel-Dict (`_trip_muster` "sms"), **nicht** in `sms_werte` (sonst bricht `_trip_sms_fehlt`).
- **B3** Trip-E-Mail-Beispiel mit Spaltenkürzel davor (`Temp 14.4`), nur wenn Wert Buchstaben/Ziffern enthält; reine Symbole ohne Präfix; Orte unverändert. Kürzel = `col_label` (sprachunabhängig).
- **B4** Befund: Karte ist heute ehrlich — `_trip_nur_tageswert` nutzt dieselbe Rechnung wie der Renderer. Der Renderer (`channel_layout.py:148`) nimmt aber nur `bucket=="primary"`; `telegram_metric_configs` (`email/helpers.py:1284`) erbt `bucket` aus der alten Grundauswahl. Gewitter/Gefühlte mit `secondary` bekommen deshalb keine Spalte, obwohl ADR-0124 Nr. 3 / AC-28 „ab der achten Metrik“ festlegen (eine Reihenfolge für alle Stellen; `bucket` ist Altbegriff, im neuen Editor nicht bedienbar). → `telegram_metric_configs` setzt `bucket="primary"`; Telegram-Nachricht und Karte folgen dann beide der Zählregel. Wirkt auf echte Telegram-Ausgabe (gewollt laut ADR); Telegram-Renderer-/Golden-Tests laufen lassen.
- **B5** „● Gespeichert“ ist der globale `SaveIndicator` (fixed, unten rechts), kein Karteninhalt. Komponente bleibt; Bildprüf-Aufbau blendet ihn aus.
- **B6** Reine Symbol-Beispiele (kein Buchstabe/Ziffer) größer (`--g-text-sm`) und in `ink` statt `ink-2` (Kontrast AA).
- **B7** Legende als Grid `auto 1fr`, gap 4px/14px, `dt` Mono, Gewicht normal, ohne `min-width`.
- **Prüfaufbau:** Screenshot-Spec Trip / drei Orte / ein Ort × DE/EN gegen Mockup-PNG (Vorlage `frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts`), dann `mockup-bildpruefer`; Text-Abgleich `--strict` DE+EN.

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| frontend/src/lib/components/molecules/EinstellTabelle.svelte | MODIFY | Spaltenbreiten, kein Beispiel bei `schmal`, Symbol-Klasse |
| frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts | MODIFY | Kennzeichen „nur Symbol“ |
| frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte | MODIFY | Legende Grid |
| Token-Datei (`--g-size-150px/118px`) | MODIFY | falls fehlend |
| src/services/placements_view_service.py | MODIFY | E-Mail-Präfix, SMS-Beispielfilter |
| src/output/renderers/email/helpers.py | MODIFY | `telegram_metric_configs` bucket primary |
| tests/tdd/test_placements_tabelle_endpoint.py | MODIFY | AC-16 Ausnahme Fenster-Kinder; neue Tests B3/B4 |
| frontend/.../__tests__ (Karte, EinstellTabelle) | MODIFY | B1/B2/B6/B7 |
| frontend/e2e/was-steht-wo-bildabgleich.staging.spec.ts | CREATE | Screenshots 3 Kontexte × DE/EN, SaveIndicator ausgeblendet |

### Scope Assessment
- Files: ~9, LoC ~ +150/-20, Risk MEDIUM (echte Telegram-Ausgabe ändert sich bei Trips mit `secondary`-Metriken)

### Open Questions
- keine Produktfrage offen (alle über Soll-Bild/ADR-0124/AC-28 entschieden)
