<!-- gregor-zwanzig-handoff: stable_id=editor-konsolidierung-phase4 -->

# Phase 4 — Editor-Konsolidierung: Layout- + Versand-Tab als geteilte Organismen (Epic #29)

**Sub-Issue von Epic #29 (`stable_id=briefing-abo-chassis`), Phase 4.**
PO-Auftrag Henning 2026-07-11. Baut auf Phase 1 (`stable_id=korridor-editor-phase1`)
— gleiches Muster: EIN Organism, `context="route" | "vergleich"`, Desktop +
`dense`-Mobile über dasselbe Component, Export auf `window`, **kein Fork je Editor**.

**Leitsatz:** hinterher ist das Projekt einfacher zu warten (kein Compare-vs-Trip-
Fork der Layout-/Versand-Logik), Migrationsaufwand minimal (kein neues Datenmodell).

Cross-Links (nicht duplizieren):
- **#29** (`briefing-abo-chassis`) — Epic. Phase 4 setzt Phase 3 (gemeinsame Entität) fachlich voraus; die UI-Konsolidierung ist aber unabhängig lieferbar.
- **#29a** (`korridor-editor-phase1`) — Referenz-Muster (Korridor-Editor). Phase 4 verschiebt die notify-Zustellung aus dem Wertebereiche-Tab in den Versand-Tab (siehe unten) — body-29a entsprechend als abgelöst markieren, nicht duplizieren.
- **#14** (`output-layout-system`) — das `layout{}`-Feld (Spalten/Detail/Aus je Kanal) wandert unverändert; Phase 4 ändert nur, WO der Editor sitzt (geteilter Organism), nicht das Datenmodell.
- **#23** (`config-change-flow`) — der Wetter-Metriken-Tab (Live-Mail + Diff) bleibt; nur sein Ausgabe-Teil (Reihenfolge + Kanal-Kappung + Vorschau) wird zum geteilten `LayoutTab`.

---

## Ziel

Zwei heute je Editor getrennt gebaute Tabs werden **je EIN** Organism, den Trip
UND Vergleich verwenden:

| heute (Fork) | wird zu |
|---|---|
| Trip: Ausgabe-Teil des Wetter-Metriken-Tabs (`WM2_Reihenfolge` + `WM2_MailPreview`) · Vergleich: `CE_LayoutTab` + `CE_LayoutPreview` | **`LayoutTab`** (`context="route" \| "vergleich"`) |
| Trip: `TE2_ZeitplanTab` (+ notify-Zustellung im Alerts-Tab) · Vergleich: `CE_VersandTab` | **`VersandTab`** (`context="route" \| "vergleich"`) |

**Wichtige Umverteilung (PO 2026-07-11):** Die **gesamte notify-Zustellung**
(Alert-Kanäle `AlertChannelPicker` + Cooldown + Stille Stunden + Beispiel-Warnung)
zieht in den **Versand-Tab**. Der Wertebereiche-Tab beider Editoren ist dadurch
**rein der Korridor-Editor** (`CorridorEditor` / `CorridorEditorMobile`) — EIN Ort
für alles, was rausgeht, kein Split zwischen Wertebereiche und Versand.

**Bewusst NICHT vereinheitlicht (E9, unverändert aus #29):** die beiden Briefing-
**Vorschau-Templates** bleiben zwei Templates über gemeinsame Primitiva:
- `route` → Stunden × Metrik-Tabelle (echtes Mail-Chrome: Email-Tabelle /
  Telegram-Bubble / SMS-Zeile).
- `vergleich` → Orte-als-Spalten-Tabelle (neutral, kein Rang, Idealbereich grün).
Geteilt sind Kanal-Umschalter, Kappungs-Logik (Email ∞ · Telegram 8 · SMS flach)
und die Cut-Line — **nicht** die Template-Bodies.

---

## Komponenten (Design geliefert — Referenz-Implementierung)

Verbindliche UI-Referenz liegt im Design-Projekt. Kein Fork je Editor.

### `LayoutTab` — `layout-tab.jsx` (Export auf `window`)

```
<LayoutTab context="route" dense? noScroll? bottomPad?
  state onMove onReorder onMode highlight telegramSuffix onSuffix />   // route: CONTROLLED
<LayoutTab context="vergleich" dense? pickedIds={string[]} />          // vergleich: self-contained
```

| Prop | Kontext | Wirkung |
|---|---|---|
| `context` | beide | `"route"` = Stunden×Metrik-Mail-Vorschau · `"vergleich"` = Orte-als-Spalten |
| `dense` | beide | `true` → Mobile-Layout (ein Scroll-Container statt Zwei-Spalten-Grid) |
| `noScroll` | beide | `true` → ohne eigenen `ScreenScroll`, wenn der Parent (Trip-Wetter-Tab Mobile) einen liefert |
| `bottomPad` | dense | Bottom-Padding für ein Floating-CTA des Parents |
| `state`,`onMove`,`onReorder`,`onMode`,`highlight`,`telegramSuffix`,`onSuffix` | route | Reihenfolge-Zustand + Handler — **identische Signatur wie der bestehende Wetter-Metriken-Tab** (`WM2_*`), daher migrationsarm |
| `pickedIds` | vergleich | Orts-IDs → Spaltenzahl der Vorschau + Kappungs-Rechnung |

Geteilte Primitiva (Export): `LT_ChannelPicker` (Kanal + Kappungs-Chip + Overflow-
Badge), `LT_CapNote` (Kappungs-Hinweis), `LT_CompareOrderList`, `LT_ComparePreview`
(vergleich), `LT_RoutePreview` + `LT_RouteOrderDense` (route). `LT_CHANNELS` =
`{email: ∞, telegram: 8, sms: 0}` — dieselbe Kappungs-Wahrheit wie #14.

### `VersandTab` — `versand-tab.jsx` (Export auf `window`)

```
<VersandTab context="route"     dense? channels? onChannels? tripEnd? onOpenStages? />
<VersandTab context="vergleich" dense? endDate? onEndDate? activation? />
```

Sektionen (Reihenfolge je Kontext):
- **route:** Briefing-Kanäle (an/aus) → Briefing-Zeitplan (Karten mit **editierbarer Uhrzeit** `<input type="time">`, gefiltert auf aktive Kanäle) → Laufzeit (read-only, aus Etappen abgeleitet) → Alert-Zustellung.
- **vergleich:** Briefing-Kanäle (an/aus) → Briefing-Zeitplan (**identisch zum Trip**: editierbare Uhrzeiten, Morgen-Briefing = heutiger Tag, Abend-Briefing = morgen) → Laufzeit (`CompareEndDateControl`, editierbar: „bis auf Weiteres | bis Datum") → Alert-Zustellung.

> **Modell-Korrektur (PO 2026-07-11, spät):** Der Vergleich-Versand hat **kein** rollierendes Zeitfenster und **keinen** Versandrhythmus mehr (waren erfundene Features). Er nutzt denselben `VT_SchedulePlan` wie der Trip — nur editierbare Briefing-Uhrzeiten. Die Uhrzeit ist in **beiden** Kontexten editierbar (`<input type="time">`). Siehe #28-Korrektur.-Zustellung → optional `activation`-Slot (Aktivieren-Banner des Create-Flows).

| Prop | Kontext | Wirkung |
|---|---|---|
| `context` | beide | Copy + Sektions-Reihenfolge |
| `dense` | beide | Mobile-Layout |
| `channels`/`onChannels` | beide (optional controlled) | Briefing-Kanäle an/aus; sonst self-managed. Default route `{email,telegram}`, vergleich `{email}` |
| `endDate`/`onEndDate` | vergleich | Laufzeit-Wert (nullable, endDate aus #29 Phase 2/C3) |
| `tripEnd`/`onOpenStages` | route | read-only Enddatum-Anzeige + Sprung zum Etappen-Tab |
| `activation` | beide (optional) | ReactNode am Ende (Compare-Aktivieren-Banner) |

Geteilte Bausteine (Export): `VT_BriefingChannels`,
`VT_SchedulePlan` (route **und** vergleich, context-diskriminiert, editierbare Uhrzeit),
`VT_LaufzeitRoute`/`VT_LaufzeitVergleich`,
`VT_AlertTiming` (Cooldown + Stille Stunden), `VT_AlertSample` (kontext-abhängiges
Subjekt: Etappe vs. Ort), `VT_AlertDelivery` (`AlertChannelPicker` + Timing + Beispiel).

**Laufzeit bei route (PO-offen, Empfehlung umgesetzt):** read-only, aus den Etappen
abgeleitet (Verweis auf Etappen-Tab). Editierbar nur bei `vergleich`.

---

## Wo die Tabs sitzen (im Design bereits verdrahtet — vier Editoren)

- **Compare Desktop** `screen-compare-editor.jsx`: `CE_LayoutTab` → `<LayoutTab context="vergleich" pickedIds>`, `CE_VersandTab` → `<VersandTab context="vergleich" activation>`. `CE_LayoutPreview` gelöscht (→ `LT_ComparePreview`).
- **Compare Mobile** `screen-compare-editor-mobile.jsx`: `CEM_LayoutTab`/`CEM_VersandTab` → dieselben Organismen mit `dense`.
- **Trip Desktop** `screen-trip-edit-v2-weather.jsx` (`WetterMetrikenTabV2`): Sektion 1+2 (Preset + Grundauswahl = Metrik-**Auswahl**) bleiben Trip-eigen; Sektion 3+4 + Live-Mail → `<LayoutTab context="route" …>`. Briefing-Kanäle an/aus wandern in den Versand-Tab. `screen-trip-edit-v2-main.jsx`: `TE2_ZeitplanTab` → `<VersandTab context="route">`; `TE2_AlertsTab` = pur `<CorridorEditor context="route"/>`.
- **Trip Mobile** `screen-trip-edit-v2-mobile.jsx`: `TM2_WetterTab` behält Auswahl + mountet `<LayoutTab context="route" dense noScroll>`; `zeitplan`-Tab → `<VersandTab context="route" dense>`; `TM2_AlertsTab` = pur `<CorridorEditorMobile context="route"/>`.

Showcase (Design-Review + soll-Screenshots): `Gregor 20 - Geteilte Editor-Tabs.html`
+ `… Mobile.html` (zeigt alle drei geteilten Tabs × beide Kontexte). Ersetzt das
Paar `Gregor 20 - Korridor-Editor(.html / Mobile.html)`.

---

## Migration (migrationsarm — C4)

**Kein neues Datenmodell.** `layout{}` (#14), `channels[]` und `alertChannels[]`
(#29a) bleiben unverändert. Diese Phase ist ein **UI-Refactor ohne Verhaltens-
änderung** — mit genau EINER absichtlichen UX-Verschiebung:

- Die notify-Zustellung (Alert-Kanäle + Cooldown + Stille Stunden + Beispiel-
  Warnung) erscheint jetzt im **Versand-Tab** statt im Wertebereiche/Alerts-Tab.
  Kein Datenfeld ändert sich; nur der Ort im UI. Migration = keine (reines Frontend-
  Re-Layout). In der SvelteKit-Umsetzung: die bestehenden Alert-Zustell-Controls in
  die Versand-Route verschieben, den Wertebereiche-Tab auf den reinen Korridor-Editor
  reduzieren.

**Constraint-Ableitungen:**
- **C6 (Playwright):** bestehende `data-testid` beider Editoren bleiben erhalten. Beim Verschieben der notify-Controls die `data-testid` mitnehmen (gleiche IDs, neuer Parent-Tab), damit bestehende Specs nur den Tab-Navigations-Schritt anpassen müssen, nicht die Selektoren.
- **C1 (Neutralität):** die `vergleich`-Layout-Vorschau bleibt neutral — Orte = Spalten, kein Score/Rang; Idealbereich nur grün markiert.
- **E9:** die zwei Vorschau-Templates bleiben getrennt; nur Kanal-Picker + Kappung + Cut-Line sind geteilt.

---

## Acceptance Criteria

- [ ] `LayoutTab` ist EIN Organism, von Compare- UND Trip-Editor verwendet (Desktop + `dense`-Mobile), `context`-diskriminiert; kein Fork der Layout-Logik mehr.
- [ ] `VersandTab` ist EIN Organism, von beiden Editoren verwendet; enthält Briefing-Kanäle, Briefing-Zeitplan mit **editierbarer Uhrzeit** (route + vergleich identisch: Morgen=heute · Abend=morgen), (route) Zeitplan-Karten bzw. (vergleich) editierbare Laufzeit, und die **gesamte** notify-Zustellung. Kein rollierendes Zeitfenster, kein Versandrhythmus (PO 2026-07-11).-Zustellung.
- [ ] Wertebereiche-Tab beider Editoren = rein `CorridorEditor`/`CorridorEditorMobile` (keine Alert-Kanäle/Cooldown/Stille-Stunden/Beispiel mehr dort).
- [ ] Kappungs-Logik (Email ∞ · Telegram 8 · SMS flach) einmal implementiert (`LT_CHANNELS`), von beiden Kontexten genutzt; Cut-Line/Overflow-Badge zeigt den engsten Tabellen-Kanal.
- [ ] Zwei Vorschau-Templates bleiben getrennt (route Mail-Chrome, vergleich Orte-Spalten) — E9.
- [ ] Kein neues Datenmodell; `layout{}`/`channels[]`/`alertChannels[]` unverändert.
- [ ] Bestehende `data-testid` erhalten (C6); Specs passen nur den Tab-Navigations-Schritt der notify-Controls an.
- [ ] Metrik-**Auswahl** (Preset + Grundauswahl) bleibt Trip-eigen im Wetter-Metriken-Tab — nicht in `LayoutTab` gezogen (Compare hat keine Auswahl, wählt über Aktivitätsprofil).

## Edge Cases

| Fall | Verhalten |
|---|---|
| route: kein Briefing-Kanal aktiv | Briefing-Zeitplan zeigt Warn-Hinweis, keine Zeitplan-Karten |
| vergleich: Telegram gewählt, Orte + Label > 8 | Overflow-Badge am Kanal + Kappungs-Warnung; kein Datenverlust, nur Vorschau |
| route: Laufzeit | read-only aus Etappen; Editieren nur über den Etappen-Tab |
| `notify` auf `vergleich` bzw. `mark` auf `route` | unverändert erlaubt (C1, aus #29a) — Alert-Zustellung im Versand-Tab gilt für beide |
| Mobile Trip-Wetter-Tab | Auswahl (1+2) + `LayoutTab dense noScroll` in EINEM Scroll-Container; Vorschau inline statt Bottom-Sheet |

## Out of Scope (Folge-Phasen)

- Gemeinsames `BriefingSubscription`-Schema + API-Konsolidierung → Epic #29 Phase 3.
- Lifecycle/`timeWindow`-Verdrahtung ans Datenmodell → Phase 2 (= #28).
- **Mobile-Editor-Konsolidierung** (Vereinheitlichung der Mobile-Editor-Shells und der übrigen Mobile-Tabs über die drei geteilten Organismen hinaus) → eigenes Issue nach Phase 4 (unverändert aus #29 Out-of-Scope).

## Screenshots (soll)

- https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-29b-desktop-layout-route.png (Desktop · Trip · Layout)
- https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-29b-desktop-layout-vergleich.png (Desktop · Vergleich · Layout)
- https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-29b-desktop-versand-route.png (Desktop · Trip · Versand)
- https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-29b-desktop-versand-vergleich.png (Desktop · Vergleich · Versand · Laufzeit)
- https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-29b-mobile.png (Mobile · beide Kontexte · Layout + Versand)
