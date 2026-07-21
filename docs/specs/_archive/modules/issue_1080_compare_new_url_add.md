---
entity_id: issue_1080_compare_new_url_add
type: module
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
tags: [frontend, compare, location, bug]
---

<!-- Issue #1080 — compare/new: Ort per URL hinzufügen bleibt unsichtbar + kein Benennen -->

# Issue 1080 — compare/new: Ort per URL hinzufügen sichtbar machen + benennen

## Approval

- [x] Approved

## Purpose

Auf `/compare/new` bleibt ein per URL (z.B. `https://maps.app.goo.gl/…`) aufgelöster und
über „＋ Zum Vergleich hinzufügen" angelegter Ort unsichtbar: Er landet nie in der
„Im Vergleich"-Liste. Ursache ist, dass die angezeigte Auswahl-Liste die IDs gegen einen
beim Seiten-Load eingefrorenen Orts-Prop auflöst, in dem der frisch angelegte Ort fehlt —
er wird still herausgefiltert. Zusätzlich wird bei URL-Import mangels erkanntem Namen die
rohe URL als Ortsname gespeichert, und es gibt keine Möglichkeit, den Ort vor dem
Hinzufügen zu benennen.

Ziel: Der neu angelegte Ort erscheint sofort sichtbar in der Vergleichsliste, und der
Nutzer kann ihn vor dem Hinzufügen benennen (sinnvoller Default statt roher URL).

## Source

- **File:** `frontend/src/lib/components/compare/steps/Step2Orte.svelte` (MODIFY) —
  neu angelegte Location lokal in die resolvbare Liste aufnehmen, gegen die
  `pickedLocations` auflöst; Benennungsfeld in der „Erkannt"-Vorschau; Default-Name =
  Koordinaten statt URL.
- **File:** `frontend/e2e/` bzw. `frontend/src/lib/components/compare/__tests__/` (CREATE) —
  E2E-Test, der den Bug aus Nutzersicht reproduziert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `compareWizardState.svelte` (`ws.pickedIds`) | intern | Auswahlliste der zu vergleichenden Orte |
| `$lib/api` (`POST /api/locations`) | intern | Anlegen der Location, liefert `Location` mit `id` zurück |
| `$lib/types` `Location` | intern | Typ der aufgelösten/angelegten Orte |
| `POST /api/locations/resolve` | intern | Auflösen der URL/Koordinaten zur Vorschau (unverändert) |

## Implementation Details

- `Step2Orte` hält eine lokale, reaktive Liste aller resolvbaren Orte, initialisiert aus dem
  `locations`-Prop. Bei jedem erfolgreichen Create (regulärer Pfad **und** Koordinaten-Fallback)
  wird das vom Backend zurückgegebene `loc`-Objekt dieser Liste hinzugefügt, **bevor** die ID in
  `ws.pickedIds` geschoben wird. `pickedLocations` löst gegen diese lokale Liste auf.
- Die „Erkannt"-Vorschau erhält ein editierbares Namensfeld. Vorbelegung: erkannter Name, falls
  vorhanden; sonst ein Koordinaten-String (z.B. `43.0421, 6.1049`), **nie** die eingegebene URL.
  Dieser Name wird an `POST /api/locations` als `name` übergeben.
- Bestehende Bibliotheks-Auswahl (`togglePick`) und Zähler bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer auf `/compare/new` mit noch leerer Vergleichsliste /
  When er eine Google-Maps-Kurz-URL (`https://maps.app.goo.gl/…`) aufgelöst hat und auf
  „＋ Zum Vergleich hinzufügen" klickt / Then erscheint der Ort unmittelbar als Eintrag in der
  „Im Vergleich"-Liste und der Zähler „Im Vergleich · N" erhöht sich um 1.

- **AC-2:** Given die „Erkannt"-Vorschau eines per URL aufgelösten Ortes ohne erkannten Namen /
  When der Nutzer die Vorschau ansieht / Then ist ein editierbares Namensfeld sichtbar, das mit
  einem Koordinaten-Default vorbelegt ist (nicht mit der eingegebenen URL), und ein vom Nutzer
  eingegebener Name wird beim Hinzufügen als Ortsname des Eintrags in der „Im Vergleich"-Liste
  übernommen.

- **AC-3:** Given ein Nutzer nutzt den manuellen Koordinaten-Fallback (Breiten-/Längengrad) /
  When er auf „Hinzufügen" klickt / Then erscheint auch dieser Ort sofort sichtbar in der
  „Im Vergleich"-Liste (kein stilles Verschwinden).

- **AC-4:** Given ein per URL hinzugefügter Ort ist in der Liste / When der Nutzer keinen eigenen
  Namen vergeben hat / Then ist der angezeigte Name der Koordinaten-Default und **nicht** die rohe
  URL.

## Known Limitations

- Kein serverseitiges Geocoding für einen menschenlesbaren Ortsnamen aus reinen Koordinaten;
  ohne Nutzereingabe bleibt der Koordinaten-String der Name.
- Umbenennen eines bereits hinzugefügten Eintrags ist nicht Teil dieses Fixes (nur Benennen vor
  dem Hinzufügen).

## Test Plan

- **E2E (Playwright, eingeloggt gegen Staging):** `/compare/new` → URL `https://maps.app.goo.gl/6d8LWy1hEjTcVUPG7`
  ins Smart-Import-Feld → „Auflösen" → Namensfeld füllen → „＋ Zum Vergleich hinzufügen" →
  assert: Eintrag in Picked-Liste sichtbar mit vergebenem Namen, Zähler = 1. Rot vor Fix
  (Liste bleibt leer), grün nach Fix. Deckt AC-1, AC-2, AC-4 ab.
- **E2E:** Koordinaten-Fallback → „Hinzufügen" → Eintrag sichtbar (AC-3).
