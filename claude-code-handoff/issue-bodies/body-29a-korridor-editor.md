<!-- gregor-zwanzig-handoff: stable_id=korridor-editor-phase1 -->

# Phase 1 — Korridore: Alerts + Idealwerte vereinen (Epic Briefing-Abo-Chassis)

**Sub-Issue von Epic #29 (`stable_id=briefing-abo-chassis`), Phase 1.**
PO-Entscheidung Henning 2026-07-11 (zweite Runde). Herleitung E3′ in
`docs/konzept-vergleich-stehender-monitor.md` §7.

Cross-Links (nicht duplizieren, ablösen):
- **#687** (`stable_id=alerts-tab-687`) — der Empfindlichkeits-Presets-Alerts-Tab wird durch den Korridor-Editor **ersetzt**. Migration siehe unten.
- **#25** (`stable_id=compare-editor-progressive`) — der Idealwerte-Tab des Compare-Editors wird durch denselben Organism ersetzt.
- **#28** (`stable_id=compare-standing-monitor`) — Neutralität (C1) stammt von dort; Korridore dürfen sie nicht brechen.

---

## Ziel

Zwei heute getrennte Konzepte werden **eine** Datenstruktur mit zwei
unabhängigen Wirkungen:

| heute (getrennt) | wird zu |
|---|---|
| Trip · Alert-Schwellwert (Empfindlichkeit je Metrik) | `corridor.notify` — warnen, wenn Wert **außerhalb** |
| Vergleich · Idealbereich (Slider je Metrik) | `corridor.mark` — markieren, solange Wert **innerhalb** |

Ein Wertebereich ist **eine Geometrie** (`range: [min|null, max|null]`), aus der
beide Wirkungen lesen. Beidseitig geschlossen = Idealbereich; einseitig offen =
Schwellwert (C2). Beide Wirkungen sind auf beiden `kind`s frei kombinierbar (C1).

> **Naming (PO Henning 2026-07-11):** User-facing Label ist **„Wertebereich"**
> (Tab „Wertebereiche", kurz „Bereich" in der Zeile). Der **Code-/Datenterm
> bleibt `corridor`** (`corridors`, `corridorInside`, Epic #29, Backend) —
> Fachterm im Code, Klartext an der Oberfläche (analog „Tabelle" statt
> „Monospace-Tabelle" in CLAUDE.md). Nicht die Code-Bezeichner umbenennen.

---

## Datenmodell (aus Epic #29, hier der für Phase 1 relevante Ausschnitt)

```ts
interface Corridor {
  metric: string;                       // Metrik-Code (siehe metric-codes)
  range: [number | null, number | null]; // [min, max] · null = offene Seite (C2)
  notify: boolean;                        // Sofort-Meldung wenn AUSSERHALB
  mark: boolean;                          // im Briefing markieren wenn INNERHALB
  prio?: "hoch" | "mittel" | "niedrig";   // nur Reihenfolge, KEIN Rang (C1)
}
// Defaults beim Anlegen:  kind=route → notify=true, mark=false
//                         kind=vergleich → notify=false, mark=true
```

### C5 · Match-Logik — die Single-Source (Backend == Frontend)

Editor-Vorschau, Briefing-Renderer und Alert-Trigger MÜSSEN dieselbe Funktion
verwenden. Referenz-Implementierung (aus `corridor-editor.jsx`, verbatim):

```js
function corridorInside(value, min, max) {
  if (value == null) return null;               // kein Messwert → neutral
  if (min != null && value < min) return false; // unter dem Korridor
  if (max != null && value > max) return false; // über dem Korridor
  return true;                                  // im Korridor
}
```

Ableitungen:
- `mark` markiert einen Wert ⇔ `corridorInside(v, min, max) === true`.
- `notify` feuert ⇔ `corridorInside(v, min, max) === false` (plus Cooldown/Stille Stunden, unverändert aus #687).
- `null` (kein Messwert) löst **weder** mark noch notify aus.

---

## Komponente (Design geliefert — Referenz-Implementierung)

Der gemeinsame Editor-Organism liegt im Design-Projekt und ist die
verbindliche UI-Referenz. **Kein Fork je Editor** — ein Organism, zwei Kontexte.

**Desktop:** `corridor-editor.jsx`
```
<CorridorEditor context="route" | "vergleich" profileLabel?={string} />
<CompareEndDateControl value={string|null} onChange={fn} />   // gehört zu Phase 2, hier bereits gebaut
```
Exports (window): `corridorInside`, `corridorFmt`, `CorridorEditor`,
`CorridorBand`, `CorridorBound`, `CorridorEffect`, `CorridorPreviewChips`,
`CorridorRow`, `CompareEndDateControl`, `CORRIDOR_CTX`, `CORRIDOR_SEED`,
`CORRIDOR_POOL`.

**Mobile:** `corridor-editor-mobile.jsx` (Card je Metrik, Touch ≥ 44 px,
±-Stepper statt Tastatur, dual-handle Touch-Band)
```
<CorridorEditorMobile context="route" | "vergleich" profileLabel?={} footer?={ReactNode} />
<CompareEndDateControlMobile value={} onChange={} />
```
Der Mobile-Organism importiert Daten + Match-Logik aus dem Desktop-File
(`corridorInside`, `CORRIDOR_*`) — kein zweites Datenmodell.

### Props-Kontrakt

| Prop | Werte | Wirkung |
|---|---|---|
| `context` | `"route"` \| `"vergleich"` | wählt Copy (`CORRIDOR_CTX`), Defaults (notify/mark), Vorschau-Subjekte (Etappen vs. Orte) |
| `profileLabel` | string? | Anzeige im Header (z.B. Aktivitätsprofil) |
| `footer` (nur Mobile) | ReactNode? | Slot für notify-Zustell-Einstellungen (Cooldown/Stille Stunden/Beispiel) im selben Scroll-Container |

### Wo der Tab sitzt (bereits verdrahtet im Design)

- **Trip:** `screen-trip-edit-v2-main.jsx` / `-mobile.jsx` — Tab **„Alerts" → „Wertebereiche"**. Cooldown, Stille Stunden und Beispiel-Warnung bleiben (regeln die notify-Zustellung), auf Desktop unter dem Editor, auf Mobile im `footer`-Slot.
- **Vergleich:** `screen-compare-editor.jsx` / `-mobile.jsx` — Tab **„Idealwerte" → „Wertebereiche"**.

---

## Migration (C4 · verlustfrei, Dry-Run + Report)

### Trip-Alerts → `corridors(notify)`
Heutige Empfindlichkeits-Presets (#687) liefern je Metrik einen konkreten
Schwellwert. Mapping:

```
alertRule { metric, threshold, direction: "above" }  →  { metric, range: [null, threshold], notify: true,  mark: false }
alertRule { metric, threshold, direction: "below" }  →  { metric, range: [threshold, null], notify: true,  mark: false }
alertRule level "off"                                 →  Korridor mit notify: false (bleibt erhalten, inaktiv)
```
`direction` ergibt sich aus der Metrik-Semantik (Böen/Gewitter/Niederschlag =
Obergrenze; Temperatur-Min/Sicht = Untergrenze).

### Vergleich-Idealwerte → `corridors(mark)`
Heutige Idealbereiche sind bereits zweiseitige Slider:

```
ideal { metric, min, max }  →  { metric, range: [min, max], notify: false, mark: true }
ideal einseitig (nur min|max) →  range mit offener Gegenseite (C2)
```

### Report
- Zeile je migrierter Regel/Idealwert: `alt → neu`, plus Warnung bei nicht 1:1 abbildbaren Fällen (dürfen laut C4 nicht auftreten — falls doch: Abbruch, kein Teil-Commit).

---

## Alert-Kanäle (getrennter Zustellstrom · PO 2026-07-11)

Kanäle sind **output-abhängig**, nicht global. Zwei Ströme mit unterschiedlicher
Kanal-Eignung:

| Strom | natürlicher Kanal | wo konfiguriert |
|---|---|---|
| **Geplantes Briefing** (Tabelle: Etappen bzw. Orte) | **E-Mail** (Telegram nur ≤ 8 Spalten, SMS flach) | Trip: Briefing-Zeitplan · Vergleich: Versand |
| **Alerts** (`notify` aus den Wertebereichen) | **Telegram/SMS** (kurzer Push), E-Mail optional | beim notify-Zustellblock (Cooldown/Stille Stunden) |

Datenmodell — EIN neues Feld, kein zweites Kanal-Objekt:

```ts
interface BriefingSubscription {
  channels: ("email" | "telegram" | "sms")[];       // geplantes Briefing (bestehend)
  alertChannels: ("email" | "telegram" | "sms")[];  // NEU · Alerts (notify)
  // …
}
```

**Migration (migrationsarm, C4):** heute erben Alerts die Briefing-Kanäle. Setze
`alertChannels = channels` → **null Verhaltensänderung** für Bestandsdaten. Nur
der **Default für NEUE** Subscriptions verschiebt sich auf `["telegram","sms"]`.

**UI:** EIN geteilter Selektor `AlertChannelPicker` (in `corridor-editor.jsx`,
Export auf window; Desktop + `dense`-Mobile über dasselbe Component). Sitzt im
notify-Zustellblock beider Editoren (Trip: „Wann Warnungen rausgehen" · Vergleich:
Versand-Tab, unter den Briefing-Kanälen). Kein zweiter Selektor — Wartungs-Single-Source.

## Acceptance Criteria

- [ ] Trip-Editor: Tab heißt „Wertebereiche", nutzt `CorridorEditor context="route"` (Desktop) / `CorridorEditorMobile` (Mobile).
- [ ] Compare-Editor: Tab heißt „Wertebereiche", nutzt `context="vergleich"`.
- [ ] `corridorInside()` ist die einzige Match-Funktion in Backend + Frontend; Editor-Vorschau, Renderer-Markierung und Alert-Trigger rufen dieselbe Logik.
- [ ] Migrations-Skript mit `--dry-run`, Report, Abbruch bei nicht-1:1-Fällen; jede bestehende alertRule + jeder Idealwert wandert verlustfrei.
- [ ] Cooldown / Stille Stunden / Beispiel-Warnung bleiben funktional (notify-Zustellung, unverändert aus #687).
- [ ] Neutralität (C1): kein Score, kein Rang, keine Sortierung durch Wertebereiche — auch nicht bei `notify` auf kind=vergleich.
- [ ] Bestehende `data-testid` beider Editoren erhalten (C6).

## Edge Cases

| Fall | Verhalten |
|---|---|
| `notify=true` auf kind=vergleich | erlaubt — wirkt pro Ort/Metrik wie beim Trip |
| `mark=true` auf kind=route | erlaubt — grüne Markierung im Trip-Briefing |
| Korridor ohne obere UND untere Grenze | ungültig — mind. eine Grenze; Editor blockt Speichern |
| Wert genau auf der Grenze (`value == min`/`max`) | **innerhalb** (`corridorInside` nutzt `<`/`>`, nicht `<=`/`>=`) |
| Metrik ohne Messwert | `corridorInside` → `null`, weder mark noch notify |
| beide Wirkungen aus | Korridor bleibt gespeichert (inaktiv), Zeile abgedimmt |

## Out of Scope (Folge-Phasen)

- `endDate`/`timeWindow`-Lifecycle → Epic #29 Phase 2 (`CompareEndDateControl` ist hier bereits gebaut, aber Verdrahtung ans Subscription-Modell folgt in Phase 2/3).
- Gemeinsames `BriefingSubscription`-Schema → Phase 3.
- UI-Refactor der Layout-/Versand-Tabs zu geteilten Organismen → Phase 4.
- Mobile-Editor-Konsolidierung → eigenes Issue nach Phase 4.

## Screenshots (soll)

- https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-29-desktop-trip-korridore.png (Desktop · Trip · Korridore)
- https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-29-desktop-vergleich-korridore.png (Desktop · Vergleich · Korridore)
- https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-29-desktop-vergleich-laufzeit.png (Desktop · Vergleich · Laufzeit · endDate, Phase-2-Vorgriff)
- https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-29-mobile-korridore.png (Mobile · beide Kontexte + Laufzeit)
