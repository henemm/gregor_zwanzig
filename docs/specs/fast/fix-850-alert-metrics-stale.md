# Mini-Spec: fix-850-alert-metrics-stale

Issue: #850

## Root Cause

`WeatherMetricsTab.svelte` ignoriert die Antwort des `PUT /api/trips/{id}`-Aufrufs
(der den vollständigen Trip inkl. serverberechneter `alert_rules` zurückgibt) und
konstruiert den `onTripUpdate`-Payload manuell — ohne die neuen `alert_rules`.
Wenn der Nutzer danach zum Alerts-Tab wechselt, sieht `AlertsTab` stale (leere)
`alert_rules` und zeigt fälschlich „Keine alert-fähigen Wetter-Metriken aktiv".

## Acceptance Criteria

**AC-1:** Given WeatherMetricsTab speichert die Wetter-Metriken / When PUT /api/trips/{id} antwortet mit dem vollen Trip inkl. alert_rules / Then wird onTripUpdate mit dem Server-Response-Trip aufgerufen (nicht mit einem manuell konstruierten Objekt ohne alert_rules)

**AC-2:** Given AlertPreviewCard zeigt die No-Metrics-Meldung / When der Text „im Tab Wetter-Metriken" im DOM vorhanden ist / Then ist er ein Link mit href="?tab=weather" und data-testid="alert-preview-no-metrics-link"

**Kein Backend-Change** — `UpdateTripHandler` gibt bereits den vollen Trip zurück.

## Was darf sich nicht ändern

- `PUT /api/trips/{id}/weather-config` Aufruf bleibt erhalten (speichert display_config)
- Keine Änderung am Auto-Save-Timing oder Controller-Logik
- Auto-Save-Inkonsistenz über alle Tabs → separates Issue (nicht in diesem Fix)
- `AlertsTab` lokaler `alertRules`-State bleibt `$state` (kein `$derived`) — Tab wird
  bei jedem Wechsel neu gemountet, daher ausreichend

## Manuelle Test-Schritte

1. Trip öffnen → Tab „Inhalt" (Wetter-Metriken) → mindestens eine alert-fähige
   Metrik aktivieren (z.B. Windböen) → Speichern
2. Tab „Alerts" öffnen → es erscheint KEINE „Keine alert-fähigen Metriken"-Meldung
   mehr; stattdessen ist mindestens eine Alert-Karte sichtbar
3. Im Alerts-Tab: Link „Wetter-Metriken" klicken → Tab wechselt zu „Inhalt"

## Inline-Test (wird während Implementierung geschrieben)

- [ ] AC-1: Nach handleSave wird onTripUpdate mit dem server-returned Trip aufgerufen
      (alert_rules enthält die vom Backend berechneten Regeln, nicht leer)
- [ ] AC-2: Hinweistext enthält Element mit `data-testid="alert-preview-no-metrics-link"`
      das beim Klick zur weather-tab-URL navigiert
