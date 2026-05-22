# Context: Issue #302 — Trip-Detail-Seite Redesign

## Request Summary

Die Trip-Detail-Seite `/trips/[id]` soll gemäß Soll-Mockup `soll-flow7B-trip-detail.png` vollständig ausgebaut werden: Neuer Header mit großem H1, Status-Row und 3 Aktions-Buttons, 5 umbenannte Tabs, Übersicht-Tab als 2×2 DetailCard-Grid, Danger-Zone am Fuß.

## Ist-Zustand (Stand 2026-05-21)

| Bereich | Ist | Soll |
|---------|-----|------|
| `+page.svelte` | Nutzt `TripHeader` + `TripTabs` — kein Leerproblem mehr | Wie jetzt, nur Header + Tabs aktualisiert |
| `TripHeader` | Breadcrumb + h2 (1.5rem) + StatusBadge + Pause/Archivieren-Buttons | Großes H1 (3-4rem), Status-Row "AKTIV · TAG N VON M", Datum+km+Höhe, 3 andere Buttons |
| Tab-Bezeichnungen | "Etappen & Wegpunkte", "Wetter-Metriken", "Briefing-Zeitplan", "Vorschau" | "Etappen [N]", "Wetter-Briefing", "Reports & Kanäle" — kein Vorschau-Tab |
| Overview-Tab | TripHero (TopoBg-Banner) + FullProfile + StageList + 4 rechte Preview-Cards | 2×2 Grid aus 4 `DetailCard`-Komponenten (neue Komponente) |
| Danger Zone | Nicht vorhanden | Am Seitenende: duplizieren + GPX + pausieren + Löschen |

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/trips/[id]/+page.svelte` | Entry-Point — aktuell: TripHeader + TripTabs |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Zu redesignen: h2 → H1, neue Status-Row, neue Buttons |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Umbenennung + Vorschau-Tab entfernen |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | Overview-Tab aktuell: TripHero + 2-Spalten-Layout → wird durch 2×2 Grid ersetzt |
| `frontend/src/lib/components/trip-detail/TripHero.svelte` | Bleibt erhalten, wird aber aus Overview-Tab entfernt (Inhalt wandert in Header) |
| `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` | Zeigt Reports-Info — wird zur Grundlage für "Was geht raus" DetailCard |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | Zeigt Alert-Regeln — wird zur Grundlage für "Wachhund-Schwellen" DetailCard |
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | Metriken-Preview — bleibt evtl. als 3. DetailCard |
| `frontend/src/lib/components/trip-detail/PreviewCard.svelte` | Vorschau-Links — evtl. 4. Card oder weg |
| `frontend/src/lib/components/trip-detail/FullProfile.svelte` | Stage-Übersicht — evtl. als "Route & Etappen" Card |
| `frontend/src/lib/components/trip-detail/index.ts` | Export-Index — neue Komponenten müssen ergänzt werden |
| `frontend/src/lib/utils/tripHero.ts` | Hat `getActiveStageDisplay()`, `formatDateRange()`, `getDaysLabel()` |
| `frontend/src/lib/utils/tripStatus.ts` | `deriveTripStatus()` |
| `frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte` | Hat km+Höhen-Berechnungslogik — in neue Utils extrahierbar |
| `frontend/src/routes/trips/+page.svelte` | Hat `runTestReport()` + Briefing-Vorschau-Logik → zu extrahieren |
| `frontend/src/lib/types.ts` | `Trip`, `Stage`, `Waypoint`, `AlertRule`, `ReportConfig` |

## Existing Patterns

- **Eyebrow-Pattern**: `<Eyebrow>TEXT</Eyebrow>` aus `$lib/components/ui/eyebrow`
- **Btn-Komponente**: `<Btn variant="outline|primary|accent" size="sm">` aus `$lib/components/ui/btn`
- **GCard**: `<GCard>` aus `$lib/components/ui/g-card` — bestehende Preview-Cards nutzen das
- **StatusBadge**: `<TripStatusBadge {trip} {now} />` aus `trip-detail`
- **Distanz-Berechnung**: Haversine-Logik in `StageCard.svelte:23-33` — muss in util extrahiert werden
- **Status-Ableitung**: `deriveTripStatus(trip, now)` gibt `'active'|'planned'|'paused'|'archived'`

## Dependencies

- **Upstream**: `Trip`-Typ aus `$lib/types.ts` — hat `stages`, `alert_rules`, `report_config`
- **Upstream**: API `/api/scheduler/trip-reports?hour=7|18` für Test-Briefing (POST, kein Body nötig)
- **Upstream**: `api.post()` aus `$lib/api` (verfügbar in trip-list, muss in Detail-Page importiert werden)
- **Downstream**: Keine anderen Komponenten hängen von `TripHeader` / `TripTabs` ab außer `+page.svelte`

## Scope der Änderungen

**Neue Komponente (zu erstellen):**
- `frontend/src/lib/components/trip-detail/DetailCard.svelte` — generische Karte mit eyebrow, title, rows (label+meta+dot), action-link

**Zu ändern:**
- `TripHeader.svelte` — komplett redesignen (kein Umbau — neues Markup)
- `TripTabs.svelte` — Tab-Labels umbenennen, Vorschau-Tab entfernen
- `TripOverview.svelte` — TripHero entfernen, 2×2 Grid mit 4 DetailCards
- `+page.svelte` — Test-Briefing senden + Briefing-Vorschau aus trips-list extrahieren, Danger-Zone hinzufügen

**Unberührt:**
- `TripHero.svelte` — wird nur aus dem Overview-Tab genommen, bleibt als Datei erhalten
- Alle Tab-Inhalte (WaypointsPanel, WeatherMetricsTab, AlertsTab, BriefingsTab, Preview) — unverändert
- Alle API-Endpunkte — keine Backend-Änderungen nötig

## Soll-Mockup Analyse

Aus `claude-code-handoff/screenshots/soll-flow7B-trip-detail.png`:

**Header-Bereich (über den Tabs):**
- Breadcrumb: "MEINE TOUREN › KHW 403" (monospace/uppercase)
- H1: "KHW 403 · Karnischer Höhenweg" (ca. 3-4rem, bold, mehrzeilig)
- Status-Zeile links: "AKTIV · TAG 1 VON 13" (Accent-Farbe, monospace)
- Meta-Zeile: "20.05 — 01.06.2026 · 167.4 km · ↑8 940 m" (kleiner)
- Buttons rechts (vertikal ausgerichtet zu H1): Briefing-Vorschau (outline), Bearbeiten (outline), Test-Briefing senden (primary/accent)

**Tab-Leiste:**
- Übersicht (aktiv, unterstrichen)
- Etappen 13 (Badge)
- Wetter-Briefing
- Reports & Kanäle
- Alarmregeln 5 (Badge)

**Übersicht-Tab (2 Spalten sichtbar):**
- Links: "REPORTS" eyebrow, "Was geht raus" title, Zeilen mit Dot (Abend-Briefing, Morgen-Update, Warnungen, Trend-Vorschau), "Reports anpassen →"
- Rechts: "ALARMREGELN · 5" eyebrow, "Wachhund-Schwellen" title, Regel-Zeilen, "Regeln verwalten →"

## Implementierungsstrategie

### Reihenfolge (sequenziell, wegen Abhängigkeiten)

1. **Phase A (unabhängig, parallel):** `DetailCard.svelte` (neu) + `tripStats.ts` (Util für km/Höhe aus Waypoints)
2. **Phase B:** `TripOverview.svelte` umbau — nutzt DetailCard aus Phase A
3. **Phase C:** `TripTabs.svelte` — Tab-Umbenennung (unabhängig)
4. **Phase D:** `TripHeader.svelte` — nutzt tripStats aus Phase A, beinhaltet Danger-Zone-Handling
5. **Phase E:** `[id]/+page.svelte` + `index.ts` — Danger-Zone ergänzen, DetailCard-Export

### LoC-Schätzung
| Datei | Erwartete LoC |
|-------|--------------|
| `tripStats.ts` (neu) | +40 |
| `DetailCard.svelte` (neu) | +80 |
| `TripTabs.svelte` | +4 |
| `TripOverview.svelte` | +30 |
| `TripHeader.svelte` | +50 (netto, nach Entfernen von Pause/Archiv) |
| `+page.svelte` | +80 (Danger-Zone) |
| `index.ts` | +1 |
| E2E-Tests anpassen | +40 |
| **Gesamt** | **~325 LoC** |

**→ loc_limit_override 350 nötig** (Redesign ist kohärent — Splitting würde halb-umgebauete UI erzeugen)

### Entscheidungen (ohne User-Input)

- **Vorschau-Tab**: Bleibt im Code als 6. Tab, "Briefing-Vorschau"-Button im Header navigiert zu `#preview`
- **"Datenstand"-Card**: Zeigt Trip-Stats (Etappenanzahl, km, Gesamthöhe) aus vorhandenen `trip.stages`-Daten — kein Extra-API-Call, Action-Link → `#stages`
- **Pause/Archivieren**: Wandern in Danger-Zone (testids bleiben identisch → kein Test-Break)
- **Tab-Tests**: `trip-detail-tabs.spec.ts` Zeilen 5-10 müssen gleichzeitig mit TripTabs geändert werden

## Risks & Considerations

- **km/elevation**: Trip-Typ hat keine aggregierten km/elevation-Felder — muss aus `stages[].waypoints` berechnet werden. Haversine-Logik bereits in StageCard.svelte vorhanden.
- **Vorschau-Tab-Entfernung**: Wenn Vorschau-Tab entfernt wird — prüfen ob irgendwo deeplinks darauf existieren (`#preview`)
- **Test-Briefing**: Aktuell in trips/+page.svelte — betrifft ALLE aktiven Trips (nicht nur diesen). Das muss in der UX klar kommuniziert werden oder API muss trip-spezifisch aufgerufen werden.
- **TripHero**: Bleibt als Datei erhalten — vielleicht wird er später in einer anderen Form wieder gebraucht (z.B. als großes Banner auf einer Landing-Page). Nicht löschen.
- **Bearbeiten-Button**: Navigiert zu `/trips/[trip.id]/edit` — Route existiert bereits.
