# Mini-Spec: #941 — isDirty-State bei Tab-Wechsel erhalten

## Was ändert sich

- `TripNewEditor.svelte` (Desktop + Mobile): WeatherMetricsTab nicht per `{:else if activeTab === 'metriken'}` bedingt rendern, sondern immer gemountet lassen und per `style:display` ausblenden.
- Gilt für beide Renderäste: `.tn-desktop` und `.tn-mobile`.

**Vorher:**
```svelte
{:else if activeTab === 'metriken'}
  <WeatherMetricsTab ... />
```

**Nachher:**
```svelte
<div style:display={activeTab === 'metriken' ? '' : 'none'}>
  <WeatherMetricsTab ... />
</div>
```

## Was darf sich nicht ändern

- Alle anderen Tabs (Route, Zusammenfassung) bleiben unverändert
- WeatherMetricsTab-Props bleiben identisch
- Edit-Modus (TripEditView / TripDetail) ist nicht betroffen

## Manuelle Test-Schritte (auf Staging)

1. /trips/new → Aktivitätstyp "Wandern" wählen
2. Etappe + GPX hochladen → Metriken-Tab entsperrt
3. Metriken-Tab öffnen → wandern-Metriken vorausgewählt
4. Temperatur manuell deaktivieren
5. Route-Tab öffnen
6. Aktivitätstyp auf "Trekking" ändern
7. Metriken-Tab öffnen → **Temperatur bleibt deaktiviert** (nicht überschrieben)

## Inline-Test

- [ ] AC-4: manuelle Metrik-Änderung bleibt nach Aktivitätstyp-Wechsel und Tab-Navigation erhalten
