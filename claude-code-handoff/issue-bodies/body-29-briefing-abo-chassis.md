<!-- gregor-zwanzig-handoff: stable_id=briefing-abo-chassis -->

# Epic: Briefing-Abo-Chassis — gemeinsames Datenmodell für Trip + Orts-Vergleich

**PO-Entscheidung Henning, 2026-07-11 (zweite Runde).** Herleitung + revidierte
Entscheidungen E1′/E3′/E8/E9: `docs/konzept-vergleich-stehender-monitor.md` §7
im Design-Projekt.

**Motivation (PO):** Wartungsaufwand für zwei parallele Stacks ist zu hoch —
die Drift ist belegt (Signal-Reste, V1-vs-V2-Renderer). Trip und Vergleich
teilen ~80 % ihrer Struktur; nur die Punkte-Anordnung unterscheidet sich
(seriell entlang Zeit vs. parallel im selben Zeitfenster).

## Ziel-Modell

**Ein Datenmodell, zwei Ausprägungen.** Kein „Vergleich ist ein Trip", sondern:
beide sind ein **Briefing-Abo**.

```ts
interface BriefingSubscription {
  id: string;
  kind: "route" | "vergleich";          // bestimmt Renderer-Template + UI-Bereich
  name: string;
  profileId: string;                    // Aktivitätsprofil
  status: "draft" | "active" | "paused" | "archived";
  channels: ("email" | "telegram" | "sms")[];
  schedule: { rhythm: "daily" | "weekly"; weekday?: 0|1|2|3|4|5|6; time: string };

  // ── kind-spezifisch (einziger Struktur-Unterschied) ──
  points:
    | { kind: "route";     stages: Stage[] }          // seriell: Datum → Ort, GPX
    | { kind: "vergleich"; locationIds: string[] };   // parallel: Reihenfolge = Spalten
  // Versand für BEIDE kinds: editierbare Briefing-Uhrzeiten (morning = heutiger
  // Tag · evening = morgen, wie Trip). KEIN timeWindow, kein Rhythmus
  // (PO 2026-07-11 verworfen — s. #28-Korrektur).

  // ── Lifecycle vereinheitlicht (E8) ──
  endDate: string | null;               // route: Pflicht (aus Etappen abgeleitet)
                                        // vergleich: null = „bis auf Weiteres",
                                        // Datum = Auto-PAUSE danach (kein Auto-Löschen)

  // ── Korridore vereinen Alerts + Idealwerte (E3′) ──
  corridors: {
    metric: string;
    range: [number | null, number | null];  // einseitig offen erlaubt (Schwellwert)
    notify: boolean;                         // Warnung raus (bisheriger Trip-Alert)
    mark: boolean;                           // im Briefing markieren (bisheriger Idealwert)
  }[];                                       // Defaults: route → notify, vergleich → mark
                                             // beide Wirkungen auf beiden kinds erlaubt

  layout: { [channel: string]: string[] };   // Metrik-Konfig je Kanal (Output-Layout-System, #14)
}
```

**Bewusst NICHT vereinheitlicht (E9):**
1. **Briefing-Templates** — Etappen-Zeilen (route) vs. transponierte
   Orte-Spalten (vergleich, V2) bleiben zwei Templates über gemeinsamen
   Primitiva: Tabellen-Renderer, Kanal-Kappung (Email ∞ · Telegram 8 · SMS
   flach ≤ 140), Korridor-Markierung.
2. **Navigation** — zwei UI-Bereiche (Trips · Orts-Vergleiche), PO-bestätigt.
3. **Editor-Screens** — zwei Eintrittspunkte, aber gemeinsames
   Progressive-Tab-Framework und gemeinsame Tab-Organismen
   (Orte/Route · Korridore · Layout · Versand).

## Phasen (Sub-Issues, jeweils unabhängig auslieferbar)

- [ ] **Phase 1 — Korridore:** `alertRules` (Trip) → `corridors(notify)`;
      `ideals` (Vergleich) → `corridors(mark)`. Daten-Reshape + gemeinsamer
      Korridor-Editor-Organism. Renderer: Markierungs-Logik einmal implementieren.
- [ ] **Phase 2 — Lifecycle:** `endDate` nullable auf beiden kinds.
      `timeWindow`/rollierendes Fenster ist **verworfen** (PO 2026-07-11) — Versand =
      editierbare Briefing-Uhrzeiten wie Trip (s. `stable_id=compare-standing-monitor`,
      dort abhaken, nicht doppeln).
- [ ] **Phase 3 — Gemeinsame Entität:** Trip- und Compare-Subscription auf
      `BriefingSubscription` mit `kind`-Diskriminator migrieren; Renderer wählt
      Template per kind; API-Endpoints konsolidieren.
- [ ] **Phase 4 — Editor-Konsolidierung:** gemeinsame Tab-Organismen für beide
      Editoren (UI-Refactor ohne Verhaltensänderung). Hier liegt der größte
      Wartungsgewinn (Drift-Vermeidung).

## Constraints

- **C1** Neutralität bleibt: kein Score, kein Rang, keine Empfehlung — Korridore erzeugen nur `notify`/`mark`, nie Aggregation oder Sortierung.
- **C2** `range` einseitig offen erlaubt: `[null, 60]` = „warne über 60" (deckt heutige Alert-Schwellwerte verlustfrei ab).
- **C3** `endDate` erreicht (kind=vergleich) → Status `paused` + Hinweis im Hub; kein Löschen, kein Archivieren ohne User-Aktion.
- **C4** Migration verlustfrei: jede bestehende alertRule und jeder Idealwert muss 1:1 als Korridor abbildbar sein — Migrations-Skript mit Dry-Run + Report.
- **C5** Identische Korridor-Logik in Backend + Frontend (Live-Vorschau im Editor).
- **C6** Playwright: bestehende `data-testid` beider Editoren bleiben je Phase erhalten.

## Acceptance Criteria (Epic-Ebene)

- [ ] 4 Sub-Issues angelegt (je Phase eines), Epic verlinkt sie.
- [ ] Nach Phase 3: genau EIN Subscription-Schema in der DB, `kind`-diskriminiert; kein paralleler Trip-/Compare-Stack mehr im Backend.
- [ ] Nach Phase 4: Korridor-, Layout- und Versand-Tab sind je EIN Organism, von beiden Editoren verwendet.
- [ ] Kein Verhaltens-Unterschied für den User außer den in #28 + E8 spezifizierten (Zeitfenster, endDate-Option).

## Edge Cases

| Fall | Verhalten |
|---|---|
| Korridor mit notify=true auf kind=vergleich | erlaubt — z.B. „warne, wenn alle Orte außerhalb" ist NICHT gemeint; notify wirkt pro Ort/Metrik wie beim Trip |
| Korridor mit mark=true auf kind=route | erlaubt — Markierung erscheint im Trip-Briefing (grün im Korridor) |
| Migration: alertRule ohne oberen/unteren Grenzwert | einseitiger range, C2 |
| endDate in der Vergangenheit gesetzt | Validierungsfehler im Editor |
| kind nachträglich ändern | NICHT unterstützt — kein Konvertieren (PO 2026-07-11, erste Runde) |

## Out of Scope

- Konversion Vergleich → Trip (PO-verworfen).
- Zusammenlegen der Navigations-Bereiche oder der Briefing-Templates (E9).
- Touren/GPX als Vergleichs-Kandidaten.
- Mobile-Editor-Konsolidierung — folgt nach Phase 4 als eigenes Issue.

## Abhängigkeiten / Reihenfolge

`compare-standing-monitor` (#28) ist **Phase 2 dieses Epics** — zuerst oder
parallel umsetzbar. Phase 1 ist unabhängig. Phase 3 setzt 1+2 voraus, Phase 4
setzt 3 voraus. Berührt #14 (Output-Layout-System: `layout`-Feld wandert
unverändert ins gemeinsame Schema) und #687 (Alerts-Tab: wird in Phase 1 zum
Korridor-Editor — cross-linken, nicht duplizieren).
