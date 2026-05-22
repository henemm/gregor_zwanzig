# Context: Bug #273 — Trip-Edit Koordinatenfelder Mobile

## Request Summary

Koordinaten-Inputs im Trip-Bearbeiten-View sollen auf iOS die numerische Dezimal-Tastatur öffnen (`inputmode="decimal"`). Das responsive Layout wurde bereits bei Bug #283 implementiert.

## Ist-Zustand (nach Bug #283)

`EditStagesSection.svelte` hat bereits:
- **Mobiles Layout:** `flex flex-col` (<640px) — Felder stacken vertikal, volle Breite
- **Desktop-Layout:** `sm:grid sm:grid-cols-[1fr_88px_88px_88px_32px]` (≥640px) — unverändert
- **Mobile Trash-Button:** 44×44px Touch-Target, Desktop-Button versteckt
- **Spaltenköpfe:** `hidden sm:grid` — korrekt auf Mobile ausgeblendet

## Verbleibendes Problem (Issue #273)

Alle 3 Koordinaten-Inputs fehlt `inputmode="decimal"`:

| Input | `data-testid` | Zeile |
|-------|--------------|-------|
| Latitude | `wp-lat` | 138–146 |
| Longitude | `wp-lon` | 147–155 |
| Elevation | `wp-ele` | 157–163 |

Ohne `inputmode="decimal"` öffnet iOS Safari das alphanumerische Standard-Keyboard statt des Dezimal-Pads.

## Relevante Datei

| Datei | Relevanz |
|-------|---------|
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | Einzige Änderung nötig — 3 Input-Elemente |

## Bestehende Muster

- `inputmode` ist in anderen Teilen des Projekts noch nicht verwendet (kein Präzedenzfall)
- `type="number"` auf den Inputs ist bereits gesetzt — `inputmode="decimal"` ergänzt das korrekt
- iOS-Safari-Fix (font-size 16px, aus Bug #272) ist in `app.css` vorhanden und bleibt unberührt

## Abhängigkeiten

- Upstream: `Input`-Komponente (`frontend/src/lib/components/ui/input/`) — muss `inputmode` als Attribut durchreichen (Svelte restProps)
- Downstream: keine

## Risiken

- Keines — rein additives HTML-Attribut, keine Logik-Änderung

## Checklist Issue #273 (Ist-Stand)

- [x] `grid-cols-3` → stacked flex-col auf Mobile (Bug #283)
- [ ] `inputmode="decimal"` auf Lat/Lon/Elevation → **OFFEN**
- [x] Mindestbreite ≥ 120px → flex-col gibt volle Breite
- [x] Desktop-Layout unverändert
