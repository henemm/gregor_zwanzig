# Context: Issue #90 — Trip-Übersicht Icons gruppieren

## Request Summary

In der Trip-Übersicht (Tabelle aller Trips) gibt es pro Zeile 6 Aktions-Icons. User-Wunsch: visuelle Gruppierung der drei Aktionsklassen (3× Editieren, 2× Verschicken, 1× Löschen) durch Trennung — aktuell stehen alle 6 Icons mit gleichem 2 px-Gap direkt nebeneinander, die Aktionsklassen sind nicht erkennbar.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/trips/+page.svelte` (Z. 257–266) | Enthält die Icon-Leiste pro Trip-Zeile, einziger Änderungsort |

## Ist-Zustand (Z. 258–265)

```svelte
<div class="inline-flex flex-wrap justify-end gap-0.5">
  <Btn variant="outline" ... title="Report-Konfiguration"><BellIcon /></Btn>
  <Btn variant="outline" ... title="Wetter-Konfiguration"><CloudSunIcon /></Btn>
  <Btn variant="outline" ... title="Test Morgen-Report"><PlayIcon /></Btn>
  <Btn variant="outline" ... title="Test Abend-Report"><PlayIcon /></Btn>
  <Btn variant="ghost"   ... title="Bearbeiten"><PencilIcon /></Btn>
  <Btn variant="ghost"   ... title="Löschen"><Trash2Icon /></Btn>
</div>
```

## Zuordnung der 6 Icons zu den drei Gruppen (laut User)

| Gruppe | Icons | Aktion |
|--------|-------|--------|
| **Editieren (3)** | BellIcon, CloudSunIcon, PencilIcon | Report-Konfig öffnen, Wetter-Konfig öffnen, Trip bearbeiten |
| **Verschicken (2)** | PlayIcon (7), PlayIcon (18) | Test-Morgen-Report senden, Test-Abend-Report senden |
| **Löschen (1)** | Trash2Icon | Trip löschen |

Aktuelle Reihenfolge im DOM stimmt **nicht** mit dieser Gruppierung überein — `Bell + CloudSun` (Edit) stehen vor `Play + Play` (Send), dann `Pencil` (Edit), dann `Trash` (Delete). `Pencil` springt also durch die Send-Gruppe.

## Existing Patterns

- **Button-Varianten** als sekundäre Differenzierung schon vorhanden: `outline` für Bell/CloudSun/Play, `ghost` für Pencil/Trash. Konflikt: das stimmt nicht mit der semantischen 3-Gruppen-Aufteilung überein (Pencil ist semantisch Edit, hat aber Ghost-Variante).
- **Layout-Container:** `inline-flex flex-wrap justify-end gap-0.5`. Wrap nötig, weil bei kleineren Breiten Icons in zweite Zeile rutschen können.
- **Responsive Hiding:** `hidden sm:inline-flex` für Play, Play, Trash — auf Mobile nur Bell/CloudSun/Pencil sichtbar.
- **Separator-Komponente** vorhanden: `frontend/src/lib/components/ui/separator/` (shadcn-svelte-Standard), kann mit `orientation="vertical"` als visueller Divider verwendet werden.

## Dependencies

- **Upstream:** Btn-Komponente (`$lib/components/ui/button`), Icons aus `@lucide/svelte`, Table-Komponenten.
- **Downstream:** Keine — die Icon-Leiste ist End-Knoten im UI-Baum, nichts liest ihre Struktur.

## Existing Specs

Keine vorhandene Spec für die Trip-Übersicht-Aktionsleiste. Verwandte UI-Specs:
- `docs/reference/design_system.md` — Design-System v2 mit Token-System. Vor Layout-Änderungen konsultieren.

## Risks & Considerations

1. **Responsive-Verhalten:** Auf Mobile (sm-Breakpoint) sind 3 von 6 Icons versteckt (`hidden sm:inline-flex` auf Play/Play/Trash). Gruppierung muss in beiden Breakpoints sinnvoll aussehen — wenn nur Bell/CloudSun/Pencil sichtbar sind, gibt es nur eine Gruppe (Edit), Divider wären sinnlos.
2. **Reihenfolge im DOM:** Pencil steht aktuell zwischen Send und Delete, gehört aber semantisch zu Edit. Bei sauberer Gruppierung muss Pencil zu Bell/CloudSun wandern → Test-IDs (`data-testid="trip-edit-btn"`) bleiben gleich, aber Playwright-Tests sollten geprüft werden.
3. **Wrap-Verhalten:** Bei sehr schmalen Viewports wrappt die Leiste. Gruppen sollten als ganzes wrappen, nicht mitten in einer Gruppe brechen → ggf. innere Gruppen-Container brauchen eigenes `inline-flex` ohne wrap.
4. **Button-Varianten konsistent:** Aktuell mischt Edit-Gruppe outline (Bell, CloudSun) und ghost (Pencil). Sollten wir das im Zuge der Gruppierung harmonisieren? → Frage für die Analyse-Phase.
5. **Touch-Targets / Accessibility:** Größere Gap zwischen Gruppen kann Touch-Bedienung verbessern (klarere Trennung), aber nicht zu groß werden (Icons müssen erreichbar bleiben).
