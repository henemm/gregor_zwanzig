<!-- gregor-zwanzig-handoff: stable_id=archive-pure-no-analytics -->
## Problem

Die Archiv-Seite hat eine **komplett erfundene Retro-Analytik-Schicht**, die nie spezifiziert wurde:

- „Forecast-Treffer" / Genauigkeit in % pro Trip, inkl. farbiger `AccuracyBar`
- Spalte „Was passiert ist" mit Headline-Texten
- Summen-Statistik oben: Briefings gesendet, Forecast-Treffer Ø, Alarme ausgelöst
- Sortierung nach „Genauigkeit"

> *„Das ist doch auch längst verworfen! Woher kommt das auf einmal. ‚Wie gut die Briefings getroffen haben' — diese Funktionalität war niemals spezifiziert. Du phantasierst hier irgendwelche Funktionen in das Produkt! Es ist einfach nur ein Archiv."*
> — Product Owner (Henning), 2026-06-05

Diese Auswertung gehört **nicht** ins Produkt. `gregor.zwanzig` ist ein Vorab-Einrichtungs- und Monitoring-Werkzeug — keine Forecast-Verifikations-Plattform. Das Archiv ist **nur ein Archiv**.

## Lösung (verbindlich = kanonisches Mockup)

Reines Archiv für **zwei** Objekttypen: **Trips UND Orts-Vergleiche**.

**Genau zwei Aktionen pro Eintrag:**
1. **Wieder aktivieren** — zurück in „Meine Trips" bzw. „Orts-Vergleiche"
2. **Löschen** — endgültig entfernen (mit Confirm)

**Tabellen-Spalten:** Name (+ Typ-Tag `Trip` / `Vergleich`) · Umfang (Trips: „N Etappen"; Vergleiche: „N Orte") · Archiviert (Datum) · Aktionen.

**Filter:** `Alle · Trips · Vergleiche` (mit Count-Badges). Suche über den Namen.

**Vollständig entfernt:** Forecast-Treffer / accuracy, `AccuracyBar`, Spalte „Was passiert ist" / Headlines, Summen-Statistik (Briefings / Treffer Ø / Alarme), Genauigkeits-Sortierung, sowie alle Datenfelder `accuracy`, `briefings`, `alerts`, `headline`.

Maßgeblich ist das kanonische JSX-Mockup `claude-code-handoff/current/jsx/screen-archive.jsx` (1:1-Quelle für Epic #575) und das SOLL-Bild `current/soll/H-archive.png`.

## Datenmodell

Ein archivierter Eintrag ist minimal:

```ts
type ArchiveEntry = {
  id: string;
  type: 'trip' | 'compare';
  name: string;
  detail: string;     // "13 Etappen" | "6 Orte"
  archived: string;   // ISO-Datum, Anzeige als YYYY-MM-DD
};
```

Keine weiteren Felder. Trips wandern nach ihrem Enddatum automatisch hierher; Vergleiche werden vom Nutzer archiviert.

## Files

- `src/routes/archiv/+page.svelte` (bzw. der bestehende Archiv-Route-Ordner — Route-Namen im Repo verifizieren)
- Falls vorhanden: `AccuracyBar`-Komponente und Archiv-spezifische Stat-Berechnungen **löschen** (toter Code).

## Required changes

1. **Analytik-Schicht ersetzen:** gesamte Retro-Auswertung (Stats-Leiste, `AccuracyBar`, „Was passiert ist", Genauigkeits-Sort) entfernen.
2. **Zwei Objekttypen** in einer Liste: `type: 'trip' | 'compare'` mit sichtbarem Typ-Tag (Pill, mono, uppercase). Vergleiche tragen einen abgesetzten Tag-Ton (grün), Trips neutral.
3. **Filter-Leiste** `Alle · Trips · Vergleiche` (Pill-Tabs mit Count), ersetzt die Sortier-Tabs.
4. **Aktions-Zelle:** genau `Wieder aktivieren` (ghost, mit „undo/reactivate"-Icon) + `Löschen` (danger, Trash-Icon, Confirm-Dialog).
5. **Reaktivieren-Logik:** Trip → Status zurück auf aktiv/geplant in „Meine Trips"; Vergleich → zurück in „Orts-Vergleiche". (Verdrängt die alte PO-Notiz „Trip kann NICHT zurück" — PO-Override 2026-06-05.)
6. Footer: „N von M Einträgen · Trips auto-archiviert nach Trip-Ende".

## Acceptance criteria

- [ ] **Keine** Genauigkeits-/Forecast-/Briefing-Statistik mehr — weder pro Zeile noch in einer Summen-Leiste.
- [ ] Keine `AccuracyBar`, keine „Was passiert ist"-Spalte.
- [ ] Liste enthält **beide** Typen (Trip + Vergleich) mit sichtbarem Typ-Tag.
- [ ] Filter `Alle / Trips / Vergleiche` mit korrekten Counts; Suche filtert über den Namen.
- [ ] Pro Zeile **genau zwei** Aktionen: „Wieder aktivieren" + „Löschen" (Confirm).
- [ ] Spalten: Name (+Tag) · Umfang · Archiviert · Aktionen.
- [ ] Bestehende Playwright `data-testid`s, soweit weiter sinnvoll, erhalten; entfernte Analytik-Testids dokumentiert entfernen.

## Edge cases

| Fall | Verhalten |
|---|---|
| Archiv leer | Leerzustand „Keine archivierten Einträge" |
| Suche ohne Treffer | „Keine archivierten Einträge für »…« gefunden." |
| Vergleich hat kein Enddatum | `archived` = Datum der manuellen Archivierung |
| Reaktivieren eines Trips, dessen Datum in der Vergangenheit liegt | Trip landet in „Meine Trips" (Status geplant/aktiv); Datums-Logik wie im Editor |

## Dedupe-Hinweis (CLAUDE.md Regel 6)

`status: "new"` — per Marker `archive-pure-no-analytics` ist noch kein Issue auf GitHub bekannt. **Trotzdem vor dem Anlegen prüfen**, ob unter Epic #575 bereits ein Archiv-Sub-Issue (#576–#588) existiert; falls ja → dort cross-linken bzw. Body dort aktualisieren statt ein zweites Issue anzulegen.

## 📎 Screenshots

**Soll: reines Archiv — Trips + Vergleiche, zwei Aktionen, keine Analytik**

![soll-archive-pure](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-archive-pure.png)
