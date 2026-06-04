# Context: bug-592-593-trips-karte-navigation

## Request Summary
Zwei Navigations-Bugs auf der Trips-Liste (`/trips`): Mobile-Kartentipp öffnet Quick-Actions statt Trip-Detailseite (#592, critical), Desktop-Tabellenzeile ist nicht klickbar — nur der Namens-Link (#593, high).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/trips/+page.svelte` | Einzige betroffene Datei — enthält Mobile-Card-Stack (Z.320–373) und Desktop-Tabelle (Z.375–469) |

## Existing Patterns
- **Desktop (Z.386–468):** `<tr>` ohne `onclick`, nur `<a href="/trips/{trip.id}">` im Name-Cell (Z.390–392)
- **Mobile (Z.320–373):** `trip-card-content-btn` (Z.325–340) → `onclick` = toggle `expandedCardId`, NICHT navigate
- **Mobile Expansion (Z.350–373):** "Briefing senden" + "Vorschau" (→ `/trips/id`) + "Alerts" — "Vorschau" ist faktisch der Detail-Link, aber schlecht erkennbar
- **Mobile Action-Sheet (Z.506–556):** EllipsisVertical öffnet Sheet mit Bearbeiten/Alerts/Test/Löschen — KEIN "Briefing senden", KEIN Detailseite-Link

## Bugs im Code
- **#592 Mobile:** `trip-card-content-btn.onclick` = expand, nicht navigate. "Vorschau"-Button navigiert zwar, aber 2 Taps + missverständliches Label
- **#593 Desktop:** `<tr>` hat kein `onclick`/`cursor-pointer`. `trip-card-content-btn` liegt im `desktop:hidden`-Block → 0×0px auf Desktop

## Fix-Plan
- **#593:** `<tr>` mit `onclick={() => goto(\`/trips/${trip.id}\`)}` + `cursor-pointer` + `stopPropagation` in Aktionen-Cell
- **#592:** `trip-card-content-btn.onclick` auf `goto(\`/trips/${trip.id}\`)` umstellen; "Briefing senden" in Action-Sheet hinzufügen; Expansion entfernen (redundant mit Action-Sheet wenn Briefing senden dort ist)

## Dependencies
- Upstream: `$app/navigation.goto` (bereits importiert), Trip-Daten via SvelteKit loader
- Downstream: keine — reine UI-Änderung

## Existing Specs
- Kein dedizierter Spec für die Trips-Liste
