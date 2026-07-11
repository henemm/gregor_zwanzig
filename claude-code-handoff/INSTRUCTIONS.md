# Claude Code Handoff — Gregor Zwanzig Design + Spec Alignment

This folder contains **25 issues** for `henemm/gregor_zwanzig`.

> **Modell-Entscheidung 2026-07-11 (PO Henning): Orts-Vergleich = stehender
> Monitor.** Kein Proto-Trip, keine Konversion, kein Enddatum-Zwang. Rollierendes
> Zeitfenster („jeden Do 18:00 → Briefing für Fr–So"), Briefing neutral (kein
> Score/Rang/Empfehlung — konsistent mit CompareEmailV2, PO 2026-07-08).
> Neu: **#28** zieht die App-Screens nach. Herleitung:
> `docs/konzept-vergleich-stehender-monitor.md` im Design-Projekt.
>
> **Zweite Runde am selben Tag: Briefing-Abo-Chassis (Epic #29).** PO-Auftrag
> Wartungsaufwand → EIN Datenmodell für Trip + Vergleich (`kind`-diskriminiert),
> Korridor-Konzept vereint Alert-Schwellwerte + Idealwerte (`notify`/`mark`),
> `endDate` nullable. Zwei UI-Bereiche und zwei Briefing-Templates bleiben.
> #28 = Phase 2 des Epics.

> **⚠️ Kanal-Korrektur 2026-06-05 (PO Henning): Signal ist als Kanal entfernt.**
> Kanäle sind jetzt nur noch **Email · Telegram · SMS**; Telegram (max 8) ist der
> engste Tabellen-Kanal. Neu in dieser Runde: **#23** baut den Wetter-Metriken-
> Editor als sauberen Änderungs-Flow mit Live-Mail-Vorschau um.
>
> **Modell-Entscheidung 2026-06-06 (PO Henning):** Body #14 wurde bereinigt.
> Kanonisches Modell: **zwei Buckets** (`spalte` / `aus`), **zwei Modi** (`raw` /
> `indicator`). Kein Detail-Bucket, keine Formate Skala/Symbol. Signal entfernt.
> Body #496 nennt noch „Detail-Zeile" — als Folge-Aufgabe bereinigen.

---

## ⚠️ Regression-Fix 2026-06-05 (Trips-Liste + Archiv) — zuerst lesen

PO Henning hat am 2026-06-05 zwei **Regressionen** in den Mockups gemeldet: die
Trips-Liste war auf das alte **6-Icon-Geschwader** pro Zeile zurückgefallen, und
das Archiv hatte eine **nie spezifizierte Forecast-/Genauigkeits-Analytik**.

**Der eigentliche Fix ist NICHT primär ein Issue, sondern der Snapshot:**
Die kanonischen 1:1-Quellen `current/jsx/screen-trips.jsx` und
`current/jsx/screen-archive.jsx` wurden korrigiert, ebenso die SOLL-Bilder
`current/soll/E-trips-list-variant.png` und `current/soll/H-archive.png`.
Epic #575 baut beide Screens 1:1 daraus — mit dem korrigierten Snapshot
produziert der 1:1-Build automatisch das richtige Layout.

Konkret für Claude Code:
1. Sicherstellen, dass im Repo die **aufgelösten** Snapshot-Dateien (current/jsx
   ist ein Symlink → tatsächliche Datei unter `handoff-2026-06-04-v3/…`) den
   neuen Stand tragen. Falls der Symlink-Zielordner abweicht: dort angleichen.
2. **#04** (Trips, `stable_id=screen-trips-list`) — Body wurde aktualisiert
   (Overflow-`⋯`-Menü + inline „Briefing senden" nur aktiv + ganze Zeile
   klickbar). Per Marker-Lookup Body angleichen.
3. **#22** (Archiv, `stable_id=archive-pure-no-analytics`) — NEU, siehe unten.
4. Prüfen, ob die Epic-#575-Sub-Issues für Trips und Archiv noch offen sind →
   falls geschlossen (mit altem Layout umgesetzt), als Regression neu öffnen.

Stand Mai 2026: Das ursprüngliche „Atomic-Design-Komponentenbibliothek“-Issue ist auf GitHub bereits als Epic #368 mit Unter-Issues #369–#374 angelegt; #369 (Token-Bridge) und #370 (Brand-Bibliothek inkl. Berg+Blitz-Glyph) sind abgeschlossen und in Produktion. Dieser Handoff dupliziert das Epic NICHT, sondern ergänzt die Folge-Issues, die sich aus der Mai-2026-Design-Runde ergeben haben.

---

## Kanonische Design-Quelle für Epic #575 (1:1-Frontend-Reimplementierung)

Epic #575 baut alle Frontend-Screens **1:1 aus der Claude-Design-Vorgabe** neu (keine Interpretation, keine eigenen Design-Entscheidungen). Die bindende Quelle liegt in diesem Handoff:

- **`claude-code-handoff/current/jsx/`** — kanonische JSX-Screens + `atoms.jsx`, `molecules.jsx`, `organisms.jsx`, `brand-kit.jsx`, `tokens.css`. **Quelle der Wahrheit** für die Übersetzung nach Svelte.
- **`claude-code-handoff/current/soll/`** — visuell bindende SOLL-Screenshots pro Sub-Issue (#576–#588), dazu:
  - **`SOLL-COVERAGE.md`** — Mapping Issue → JSX-Datei → SOLL-Bild → offene Lücken + die Punkte, die JSX nicht abbildet (ASCII-Glyph-Verbot, Daten-Bugs, Layout-Entscheidungen).
  - **`D-home-VISUAL-QA.md`** — messbare Pass/Fail-Checkliste (V1–V13) fürs SOLL-IST-Gate von #579 Home.

**Reihenfolge:** Phase 1 Fundament (#576 Tokens → #577 Atoms → #578 Molecules/Organisms), dann Phase 2 Screens (#579–#588) parallel. Pro Screen: JSX lesen → 1:1 nach Svelte → Playwright-Screenshot → `fresh-eyes-inspector` SOLL-IST → PASS.

Diese Ordner sind **Schnappschüsse** der Projekt-Wurzel — bei Änderungen an Wurzel-`screen-*.jsx`/`atoms.jsx`/`tokens.css` mitziehen (Sync-Hinweis in `current/soll/SOLL-COVERAGE.md`). Letzte PO-Entscheidung 2026-06-04: Home-Schnellaktionen stehen vertikal in der linken Hero-Spalte inkl. kontextbezogenem Test-Versand; die kontextlose Topbar-Aktion „Test an mich" wurde entfernt.

---

**Diese Runde — neu (`status: "new"`):**
- #10 Orts-Vergleich · **Startseite-Kacheln + Übersicht (Kachel-Grid) + Detail-Seite + Wizard (Create/Edit) — inkl. Mobile**. **breaking-change** — ersetzt das vorher geplante Master-Detail-Layout (Gruppen-Sidebar / Auto-Reports-Grid) durch *Liste (Kachel-Grid) → Detail-Seite → 5-Schritt-Wizard* parallel zum Trip-Wizard, plus einen Kachel-Einstieg auf der Startseite. Desktop **und** Mobile teilen die Atomic-Bauteile (`CompareTile` etc.) über `dense`/`compact`. Umsetzung von **Charter §3 v1.1** (2026-05-31). PO-Reviews 2026-05-28 + 2026-05-31. Stable-ID: `ortsvergleich-wizard`.
- #17 Surface-Stack-Migration — weiße Cards auf warmer Off-White-Page. **Foundation/High Priority**, Blocker für die noch offenen Unter-Issues von Epic #368. Tauscht NUR Werte in `app.css`, nicht Namen.
- #18 Etappen-Datum bearbeiten — editierbares Datum in der Etappen-Detail-Ansicht (normale Etappe + Pausentag) statt eingefrorenem GPX-Import-Datum, plus inline Kaskaden-Vorschlag beim Verschieben der ersten Etappe (Tourstart). Empfohlene dünne Wrapper-Komponente `StageDateField.svelte` um native `<input type="date">`. Quelle: `docs/design-requests/stage_date_edit.md`. Stable-ID: `stage-date-edit`. **Hinweis:** als `new` markiert, aber NICHT per `gh` gegen GitHub verifiziert — Marker-Dedupe (Step 3) ist maßgeblich; falls bereits vorhanden → Body aktualisieren statt neu anlegen.
- #20 Kanonische Navigations-Architektur — **Foundation/IA-Spec.** Löst die Tab-Set-Drift auf (drei divergierende Trip-Detail-Tab-Sets) und legt das Modell *Erstellen (Wizard) · Ansehen (Trip-Detail, Tab Übersicht) · Bearbeiten (übrige Tabs)* fest, plus das analoge Compare-Modell. Verbindliches 6-Tab-Set: `Übersicht · Etappen & Wegpunkte · Wetter-Metriken · Briefing-Zeitplan · Alerts · Vorschau`. **Ersetzt die Tab-Benennung in #11** und verwirft den separaten Edit-Host (`screen-trip-edit-tabs.jsx`). Quelle: `nav-map.jsx`. Stable-ID: `canonical-ia-navigation`. **Hinweis:** als `new` markiert, aber NICHT per `gh` verifiziert — Marker-Dedupe (Step 3) ist maßgeblich. Bei thematischer Nähe zu #11 ggf. cross-referenzieren statt duplizieren.
- #21 Startseite — **prioritätsbasiertes Einzel-Hero-Cockpit (Trip ODER Orts-Vergleich) + Planungs-/Leerzustand** + Molecules (`QuickAction`, `SetupResumeCard`, empfohlen `CompareStatusRow`). Macht die Startseite vom Briefing-Reader zum Status-/Steuer-Cockpit (Tag-X/Y statt Etappen-Pillstreifen, Schnellaktionen → Editor-Tabs, kein Lese-Surface). **Modell-Schärfung 2026-06-03:** Trip- und Vergleichs-Modus sind faktisch exklusiv → **ein** Hero nach Priorität (Trip, sonst aktiver Vergleich); „Was geht raus" ehrlich auf den aktiven Kontext gescopet (Name im Titel); der Überlappungsfall (Vergleiche laufen nebenher zum Trip) als schlanke **„Außerdem beobachtet"-Zeile** mit nächstem Versand; Streck-Artefakt der Hero-Karte behoben (`align-items:start`). Ergänzt den fehlenden **Leerzustand** (gar nichts live → „Setup fortsetzen"). PO-Reviews Henning 2026-06-03. Stable-ID: `home-cockpit-planning`. **Hinweis (CLAUDE.md Regel 6):** thematisch an **Epic #368** (die Molecules gehören dort hinein) und an **#10** (Startseiten-Vergleichs-Darstellung, jetzt Hero/„Außerdem beobachtet" statt Kachel-Grid) — vor dem Anlegen prüfen und **cross-linken statt duplizieren**; nicht per `gh` verifiziert, Marker-Dedupe ist maßgeblich.
- #22 Archiv entrümpeln — **reines Archiv für Trips UND Vergleiche**, genau zwei Aktionen pro Eintrag (**Wieder aktivieren · Löschen**). Entfernt die nie spezifizierte Forecast-/Genauigkeits-Analytik (AccuracyBar, „Was passiert ist", Treffer-Ø-Stats, Genauigkeits-Sort). PO Henning 2026-06-05. Stable-ID: `archive-pure-no-analytics`. **Hinweis (Regel 6):** vor dem Anlegen prüfen, ob unter Epic #575 bereits ein Archiv-Sub-Issue (#576–#588) existiert → dort cross-linken/aktualisieren statt duplizieren.
- #23 Wetter-Metriken-Tab — **4-Abschnitte-Layout + Live-Mail + Kanal-Verbindung** (Desktop + Mobile).
- #26 Briefing-Email · **Render-Drift gegen Design beheben + Tageslage-Lead / Vortag-Vergleich integrieren**. Die ausgelieferte Email ist von `screen-output-preview.jsx` abgedriftet: Header fehlt fast komplett (nur nacktes Datum), die gruppierte 2-stufige Tabelle (TEMP/WIND/NIEDERSCHLAG/SICHT·UV/HÖHE) ist zu einer flachen 15-Spalten-Tabelle mit englischen Kürzeln degeneriert, Risiko-Ampel-Spalte + Tausender-Trennzeichen fehlen. Zusätzlich: die zwei Build-Boxen (blauer Summary-Banner + „Vergleich zum Vortag") werden zu **einem** Akzent-Bar-Lead (`Tageslage` + dezente `vs. Gestern`-Mono-Zeile, `EmailVortag`) gebündelt — löst auch den Einrückungs-Versatz. Stirnlampe-Sektion bleibt entfernt. Renderer-only (`trip_report.py` + Live-Vorschau). Quelle: `screen-output-preview.jsx`. Stable-ID: `briefing-email-render-drift`. **Hinweis (Regel 6):** als `new` markiert, NICHT per `gh` verifiziert — thematische Nähe zu #664 (Metriken-Pills) und #561 (Mehrtages-Trend); Marker-Dedupe maßgeblich, bei Überschneidung cross-linken statt duplizieren.
- #27 Alert-Nachricht · **generisches Render-System** (Betreff + Email · Telegram · SMS). Baut das Format der ausgelösten Alert-Mail aus — abgegrenzt von #687 (das die *Konfiguration* baut, nicht die Nachricht). Vier reine Renderer projizieren `AlertEvent[]` in alle Kanäle: Betreff führt mit **Trip · km · Richtung · Metrik**, Werte als **Tabellen-Kürzel** (CAPE statt Langform), Richtung als Pfeil (Email/Telegram) bzw. Vorzeichen `+`/`-` (SMS). **Neue SMS-Codes** für bisher code-lose Metriken (`CP` CAPE, `SN` Neuschnee, `SL` 0°-Grenze, `VS` Sicht, `HU` Feuchte) — jede alert-fähige Metrik MUSS einen Code haben. Mehrere Metriken werden nach **Schwere** (normierter Schwellwert-Abstand) sortiert; SMS bleibt ASCII/GSM-7 ≤140 mit `+k`-Überlauf. **Strikt: keine Interpretation der Wetterdaten, keine Handlungsempfehlung** (CLAUDE.md-Leitprinzip) — nur Richtung/Delta/Schwellwert-Bezug, rein rechnerisch. Renderer backend- + frontend-identisch (Versand + Live-Vorschau). Quelle: `Gregor 20 - Alert Mail Vorschläge.html`. Stable-ID: `alert-message-render`. **Hinweis (Regel 6):** als `new` markiert, NICHT per `gh` verifiziert — Nähe zu #687 (Alerts-Tab) und #14 (Output-Layout); Marker-Dedupe maßgeblich, cross-linken statt duplizieren.
- #24 Neue Tour anlegen — **Progressive Tab Editor** (kein separater Wizard). `screen-trip-wizard.jsx` deprecated. Gleiche Tab-Struktur wie Trip-Edit, sequenziell freigeschaltet. GPX je Etappe, Startdatum im Route-Tab, Wegpunkte-Tab optional (`ScreenWaypointEditor embedded`). `breaking-change` — ersetzt #407/#422-Wizard-Flow. Stable-ID: `trip-new-progressive-editor`. PO-Korrektur 2026-06-05: kein eigenständiger Meta-Editor mehr, sondern der **Tab „Wetter-Metriken" im bestehenden Trip-Edit-Screen** (5 Tabs: Übersicht · Etappen & Wegpunkte · Wetter-Metriken · Briefing-Zeitplan · Alerts). Wetter-Metriken hat 4 klare Abschnitte (Profil · Grundauswahl · Reihenfolge & Darstellung · Kanäle) + **Live-Mail rechts sticky** mit Diff-Highlight. Telegram-Schnittlinie nach Spalte 8 direkt im Editor sichtbar. **Briefing-Zeitplan liest aktive Kanäle aus Wetter-Metriken; Alerts erben Kanal-Vorbelegung.** Enthält Signal-Entfernung (Telegram = 8, PRIMARY_SLOTS = 8). Design: `Gregor 20 - Trip bearbeiten.html`. Baut auf #14 · #496 · #20 · #503. Stable-ID: `config-change-flow`. **Hinweis (Regel 6):** Nähe zu Epic #575-Editor-Sub-Issue prüfen → cross-linken statt duplizieren.
- #28 Orts-Vergleich = **stehender Monitor** — Neutralisierung (kein Score/Rang/Empfehlung) + **rollierendes Zeitfenster** (`timeWindow` statt `horizon`) in den App-Screens (Liste · Hub · Editor). Übersicht nach V2-Modell: Orte = Spalten, Metriken = Zeilen; Telegram-Cap gilt für Ort-Spalten (Label + N Orte ≤ 8, Rechnung live im Editor); Idealwerte = Markierung (grün im Korridor), keine Bewertung; Versand = Rhythmus + Zeitfenster + Tageszeit, kein Enddatum. PO Henning 2026-07-11, Herleitung `docs/konzept-vergleich-stehender-monitor.md`. Stable-ID: `compare-standing-monitor`. **Hinweis (Regel 6):** als `new` markiert, NICHT per `gh` verifiziert — Nähe zu #10 (Compare-Struktur), #25 (Compare-Editor) und CompareEmailV2-Arbeiten; Marker-Dedupe maßgeblich, bei Überschneidung Bodies der Nachbar-Issues cross-linken statt duplizieren.
- #29 **Epic: Briefing-Abo-Chassis** — gemeinsames Datenmodell für Trip + Vergleich (`kind: route | vergleich`); **Korridor-Konzept** vereint Alert-Schwellwerte + Idealwerte (`range [min?, max?]` + Wirkungen `notify`/`mark`); `endDate` nullable (Vergleich: „bis auf Weiteres" oder Datum → Auto-Pause). 4 Phasen als Sub-Issues: Korridore · Lifecycle+Fenster (= #28) · gemeinsame Entität · Editor-Organismen. Bewusst getrennt bleiben: Briefing-Templates, Navigation, Editor-Eintrittspunkte. PO Henning 2026-07-11 (zweite Runde), Herleitung `docs/konzept-vergleich-stehender-monitor.md` §7. Stable-ID: `briefing-abo-chassis`. **Hinweis (Regel 6):** berührt #14 (layout-Feld wandert unverändert) und #687 (Alerts-Tab → Korridor-Editor in Phase 1) — cross-linken, nicht duplizieren.
- #29b **Phase 4 des Epics #29 — Editor-Konsolidierung.** Layout- und Versand-Tab werden je **EIN** geteilter Organism (`LayoutTab` in `layout-tab.jsx`, `VersandTab` in `versand-tab.jsx`), den Trip- UND Vergleich-Editor über eine `context`-Prop (`route | vergleich`) verwenden — dasselbe Muster wie der Korridor-Editor (#29a): Export auf `window`, Desktop + `dense`-Mobile über dasselbe Component, **kein Fork je Editor**. `LayoutTab` = Metrik-/Orts-Reihenfolge + Kanal-Kappung (Email ∞ · Telegram 8 · SMS flach) + Live-Vorschau; **zwei Preview-Templates über gemeinsame Primitiva** (route = Stunden×Metrik-Mail-Chrome, vergleich = Orte-als-Spalten) — die Briefing-Templates selbst bleiben getrennt (E9). `VersandTab` = Briefing-Kanäle + (route) Rhythmus/Zeitplan bzw. (vergleich) Zeitfenster + Laufzeit (`CompareEndDateControl`; bei route read-only aus den Etappen) + die **gesamte** notify-Zustellung (`AlertChannelPicker` + Cooldown + Stille Stunden + Beispiel-Warnung). Damit ist der **Wertebereiche-Tab beider Editoren rein der Korridor-Editor** (kein Split mehr). Die Metrik-**Auswahl** (Preset + Grundauswahl) bleibt Trip-eigen im Wetter-Metriken-Tab. **Migrationsarm (C4):** kein neues Datenmodell — `layout{}` (#14), `channels[]` und `alertChannels[]` (#29a) unverändert, nur der Ort im UI ändert sich; bestehende `data-testid` erhalten (C6). Design geliefert Desktop + Mobile, Showcase `Gregor 20 - Geteilte Editor-Tabs.html` + `… Mobile.html`. Stable-ID: `editor-konsolidierung-phase4`. **Hinweis (Regel 6):** Sub-Issue von #29, setzt Phase 1 (#29a) fort; NICHT per `gh` verifiziert — Marker-Dedupe (Step 3) maßgeblich. Mobile-Editor-Konsolidierung bleibt laut #29 ein eigenes Folge-Issue nach Phase 4 (nicht Teil dieses Issues).
- #29a **Phase 1 des Epics #29 — Wertebereiche.** Gemeinsamer Editor-Organism ersetzt Trip-Alerts-Tab (#687) + Compare-Idealwerte-Tab (#25): EINE Geometrie `range [min?, max?]`, zwei Wirkungen `notify` (außerhalb warnen) / `mark` (innerhalb markieren), Defaults route→notify · vergleich→mark. **Naming-Entscheidung (PO 2026-07-11):** UI-Label ist **„Wertebereiche"** (Tab), der **Code-/Datenterm bleibt `corridor`** — Fachterm im Code, Klartext an der Oberfläche (analog „Tabelle" statt „Monospace-Tabelle"). Body enthält Komponenten-API (`CorridorEditor` Desktop / `CorridorEditorMobile` Mobile), die C5-Single-Source `corridorInside()` (Editor-Vorschau + Renderer + Alert-Trigger) und das verlustfreie Migrations-Mapping (`alertRule→notify`, `ideal→mark`, Dry-Run + Report). Cooldown/Stille Stunden/Beispiel-Warnung bleiben. Design geliefert Desktop + Mobile. Stable-ID: `korridor-editor-phase1`. **Hinweis (Regel 6):** Sub-Issue von #29, ersetzt/cross-linkt #687 + Idealwerte-Teil von #25 — nicht duplizieren; nicht per `gh` verifiziert, Marker-Dedupe maßgeblich.

**Diese Runde — bestätigt vorhanden (`status: "existing-or-update"`):**
- #16 Contrast-Audit der Ink-Skala (auf GitHub: Issue #377) — Folgewerk zum PO-Leitprinzip „hoher Kontrast = Lesbarkeit“.
- #496 „Pro Kanal“-Vorschau neu denken — der 4-Mini-Kachel-Strip im Wetter-Metriken-Editor wird durch **Konsequenz-Leiste (klickbar) + ehrliche Ein-Kanal-Vorschau** ersetzt (Email Desktop **und** iPhone, Signal/Telegram-Bubble, **SMS striktes Token-Format**). Issue #496 existiert bereits auf GitHub (Quelle der Design-Request) — Body via Marker-Lookup anhängen/aktualisieren, Titel unverändert lassen. Stable-ID: `issue-496-channel-preview`.
- #407 + #422 Trip-Wizard auf 5 Schritte umbauen — Body **ersetzt** die ursprünglichen 4-Step-Specs durch die 5-Step-Re-Strukturierung (PO-Review 2026-05-27, Layout-Schritt neu, AUTARK-Pill weg, Mehrtages-Trend wird Toggle). Stable-ID: `wizard-screens-update-407-422`.
- #04, #11, #14 — Bestands-Issues, falls Updates an den Bodies nötig werden. **#04 (Trips-Liste) wurde diese Runde aktualisiert** (Regression-Fix 2026-06-05: Overflow-`⋯`-Menü statt Icon-Geschwader, ganze Zeile klickbar, inline „Briefing senden" nur aktiv) — Body per Marker `screen-trips-list` angleichen.
- #503 Wegpunkt-Editor — wo gehört die Karte hin? **Entscheidung Option B** (PO 2026-06-01): die Karte kommt in den **bestehenden** Etappen-Tab, der zu **„Etappen & Wegpunkte"** umbenannt wird; `WaypointEditorPage` wird **gelöscht** (toter Code, Inhalt wandert in `EditStagesPanelNew`). Plus PO-Korrektur: **keine Auto/Manuell-Unterscheidung** mehr (kein dashed-Pin, kein „Vorschlag"-Badge, kein „KI"-Marker — auch nicht im Briefing). Bestehende Atoms wiederverwenden, nichts neu erfinden. **Hinweis (wie #407):** Issue #503 existiert auf GitHub bereits **ohne Marker** — Marker-Suche matcht nicht; Body per Nummer an **#503 anhängen** (Titel beibehalten), **#506 cross-linken** statt ungeprüft schließen. Stable-ID: `wegpunkt-editor-tab-503`.
- #561 F3: Multi-Day Trend — 3-Tage-Vorschau im Abendbericht (E-Mail). Kompakter „Nächste Etappen"-Block am Ende der Abend-E-Mail (zwischen Gewitter-Vorschau und Highlights). Design-Entscheidungen: **Spalten-Layout (2-zeilig), leicht abgesetzt (Paper-Tint + Haarlinie), Heading „Nächste Etappen"**. Tech-Lead-Flag: **keine Wetter-Emoji in den fluchtenden Spalten** (Mono-Bruch in Outlook/Gmail) — Gewitter-Ampel = Farb-Quadrat + Wort. Atomic: bestehende `UpcomingRow` (Morgen-Briefing) auf `variant="metrics"` **vereinheitlichen**, nicht neu erfinden. Renderer-only (`trip_report.py`). Issue #561 existiert bereits auf GitHub (Quelle der Design-Request) — Body via Marker-Lookup anhängen/aktualisieren, Titel unverändert. Stable-ID: `issue-561-multiday-trend`.

**Each issue body starts with a stable-ID marker** that survives across
handoffs:

```
<!-- gregor-zwanzig-handoff: stable_id=<slug> -->
```

Use the marker to dedupe (Step 3 below).

## Quick start (paste this prompt into Claude Code)

> Read `claude-code-handoff/INSTRUCTIONS.md` and execute it. **Do not blindly
> create 8 issues** — first dedupe against existing GitHub issues by
> stable-ID marker, then only create what is missing and edit bodies of
> what already exists. Ask before pushing if anything is ambiguous.
>
> **Acht** Issues in diesem Handoff haben `"status": "new"`:
> #10 Orts-Vergleich (`stable_id=ortsvergleich-wizard`),
> #17 Surface-Stack-Migration (`stable_id=surface-stack-migration`),
> #18 Etappen-Datum bearbeiten (`stable_id=stage-date-edit`),
> #20 Kanonische Navigations-Architektur (`stable_id=canonical-ia-navigation`),
> #21 Startseite · Einzel-Hero-Cockpit (Trip ODER Vergleich) + Planungs-/Leerzustand (`stable_id=home-cockpit-planning`),
> #22 Archiv entrümpeln · reines Archiv für Trips + Vergleiche, nur „Wieder aktivieren" + „Löschen" (`stable_id=archive-pure-no-analytics`),
> #23 Wetter-Briefing ändern · sauberer Flow mit Live-Mail-Vorschau, Signal-Kanal entfernt (`stable_id=config-change-flow`) und
> #24 Neue Tour anlegen · Progressive Tab Editor, kein separater Wizard (`stable_id=trip-new-progressive-editor`).
> Alle anderen sind `existing-or-update` und sollen via Marker-Lookup
> verifiziert werden — insbesondere #407 + #422 (Wizard) sind bereits
> auf GitHub vorhanden; der Body in diesem Handoff **ersetzt** die
> ursprüngliche 4-Step-Spec durch die 5-Step-Re-Strukturierung.

## What's in here

```
claude-code-handoff/
├── INSTRUCTIONS.md           ← THIS file (full plan + commands)
├── PROMPT-FUER-CLAUDE-CODE.txt ← One-line prompt to paste into Claude Code
├── create-issues.sh          ← Optional CLI fallback if you want to run it yourself
├── issues.json               ← Machine-readable index: 25 Issues (17 new, 8 existing-or-update)
├── issue-bodies/
│   ├── body-04.md            ← #295-Refresh: Trips-Liste (offen, existing-or-update)
│   ├── body-10.md            ← NEW: Orts-Vergleich · Startseite-Kacheln + Übersicht (Kachel-Grid) + Detail + Wizard — breaking-change
│   ├── body-11.md            ← Trip-Detail-Seite (offen, existing-or-update)
│   ├── body-14-output-layout-system.md
│   ├── body-16-contrast-audit-ink-scale.md   ← GitHub #377 (existing-or-update)
│   ├── body-17-surface-stack-migration.md    ← NEW: Foundation/High — Surface-Werte umstellen
│   ├── body-18-stage-date-edit.md            ← NEW: Etappen-Datum editierbar + Kaskaden-Vorschlag
│   ├── body-20-canonical-ia-navigation.md    ← NEW: Foundation/IA — ein Trip-Detail-Tab-Set, Erstellen/Ansehen/Bearbeiten
│   ├── body-21-home-cockpit-planning.md       ← NEW: Einzel-Hero-Cockpit (Trip ODER Vergleich) + „Außerdem beobachtet" + Planungs-/Leerzustand + QuickAction/SetupResumeCard
│   ├── body-22-archive-pure.md               ← NEW: Archiv entrümpeln — reines Archiv (Trips + Vergleiche), nur Wieder aktivieren + Löschen, erfundene Forecast-Analytik raus
│   ├── body-23-config-change-flow.md         ← NEW: Wetter-Briefing ändern — Live-Mail-Vorschau + Diff + Katalog (Desktop+Mobile), Signal-Kanal entfernt
│   ├── body-496-channel-preview.md           ← #496 (existing-or-update): Pro-Kanal-Vorschau A+B · SMS-Token-Format
│   ├── body-24-trip-new-progressive-editor.md ← NEW: Neue Tour anlegen als Progressive Tab Editor (kein Wizard)
│   ├── body-26-briefing-email-render-drift.md ← NEW: Briefing-Email Render-Drift beheben + Tageslage-Lead/Vortag-Vergleich
│   ├── body-27-alert-message-render.md       ← NEW: Alert-Nachricht · generisches Render-System (Betreff + Email · Telegram · SMS), neuer SMS-Code CP
│   ├── body-28-compare-standing-monitor.md   ← NEW: Orts-Vergleich = stehender Monitor — kein Score/Ranking, rollierendes Zeitfenster (App-Screens)
│   ├── body-29-briefing-abo-chassis.md       ← NEW: Epic · Briefing-Abo-Chassis — ein Datenmodell Trip+Vergleich, Korridore, 4 Phasen
│   ├── body-29a-korridor-editor.md           ← NEW: Phase 1 des Epics — Wertebereiche (UI) / corridors (Code) vereinen Alerts + Idealwerte, Desktop+Mobile
│   ├── body-29b-editor-konsolidierung.md      ← NEW: Phase 4 des Epics — Layout- + Versand-Tab als geteilte Organismen (context route|vergleich), Desktop+Mobile
├── body-407-422-wizard-update.md         ← #407 + #422 (existing-or-update): 5-Step-Wizard, neuer Layout-Step
│   ├── body-503-wegpunkt-editor-tab.md       ← #503 (existing-or-update, Marker noch nicht auf GitHub): Karte in Tab „Etappen & Wegpunkte"
│   └── body-561-multiday-trend-email.md      ← #561 (existing-or-update): Mehrtages-Trend im Abend-Report · Spalten + Plain-Text
└── screenshots/
    ├── 01-…-11-*.png         ← Ist-Screenshots (current implementation)
    └── soll-*.png            ← Soll-Mockups (target designs from Soll-Mockups.html)
```

Each issue body references screenshots by URL pointing at
`https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/<slug>.png`.
**So the screenshots must be committed and pushed to `main` before the issues are created**, otherwise the images won't render. Order matters — see step 2 below.

## Plan for Claude Code to follow

### 1. Verify environment

```bash
cd /path/to/gregor_zwanzig
git status                                      # clean working tree expected
gh auth status                                   # gh CLI must be authenticated
git rev-parse --abbrev-ref HEAD                  # confirm we're on main (or branch off)
```

If `gh` is not authenticated, stop and ask the user to run `gh auth login`.

### 2. Commit screenshots first

Copy `screenshots/*.png` from this handoff folder into the repo at
`.github/issue-assets/`, then commit and push:

```bash
mkdir -p .github/issue-assets
cp /path/to/claude-code-handoff/screenshots/*.png .github/issue-assets/
git add .github/issue-assets/
git commit -m "chore(design): add design-compliance issue screenshots"
git push origin main
```

After push, verify one URL resolves with curl:

```bash
curl -fsI "https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1A-home-kacheln.png" | head -1
# expect: HTTP/2 200
```

If it 404s, GitHub may take ~30 seconds to propagate. Retry.

### 3. Dedupe against existing GitHub issues

For each entry in `issues.json`, check if a GitHub issue with that
`stable_id` already exists:

```bash
stable_id="foundation-css-tokens"
gh issue list --repo henemm/gregor_zwanzig --state all --search \
  "in:body gregor-zwanzig-handoff: stable_id=$stable_id" --json number,title,state
```

- **Match found, state=closed** → issue is done. Skip silently. Do NOT reopen.
- **Match found, state=open** → issue exists. Update body if changed
  (`gh issue edit <num> --body-file ...`). Update labels if `issues.json`
  lists labels not yet on the issue. Do NOT change the title.
- **No match** → create the issue (next step). This is the only case where
  the entry with `status: "new"` should land; for `status: "existing-or-update"`
  entries without a match, ask the user before creating — may have been
  deleted intentionally.

**Sonderfall · `wizard-screens-update-407-422`:** Dieser Marker ist neu,
aber die Issues #407 + #422 existieren auf GitHub bereits ohne Marker. Die
Marker-Suche wird daher NICHT matchen. Behandlung:

1. **#407** öffnen, Body durch `body-407-422-wizard-update.md` ersetzen
   (inkl. dem Stable-ID-Kommentar in Zeile 1):
   ```bash
   gh issue edit 407 --repo henemm/gregor_zwanzig \
     --body-file claude-code-handoff/issue-bodies/body-407-422-wizard-update.md
   ```
2. **#422** als Duplikat von #407 schließen (der neue Body deckt beide
   Issues ab — Schritte 4-5 sind jetzt Layout + Reports):
   ```bash
   gh issue comment 422 --repo henemm/gregor_zwanzig \
     --body "Aufgegangen in #407 — der neue Body deckt 5 Schritte ab (Schritt 4 Layout-Editor neu, Schritt 5 Reports). Siehe #407."
   gh issue close 422 --repo henemm/gregor_zwanzig --reason "not planned"
   ```
3. Labels in #407 ggf. ergänzen aus `issues.json` (`area:output` ist neu).

Nicht stattdessen ein neues Issue anlegen.

**Sonderfall · `wegpunkt-editor-tab-503`:** Analog zu #407 — Issue #503
existiert auf GitHub bereits **ohne** Marker, die Marker-Suche matcht daher
nicht. **Nicht** als neues Issue anlegen und **nicht** in den
„existing-or-update ohne Match → ASK"-Pfad fallen lassen:

1. **#503** öffnen, Body durch `body-503-wegpunkt-editor-tab.md` ersetzen
   (inkl. Stable-ID-Kommentar in Zeile 1), Titel beibehalten:
   ```bash
   gh issue edit 503 --repo henemm/gregor_zwanzig \
     --body-file claude-code-handoff/issue-bodies/body-503-wegpunkt-editor-tab.md
   ```
2. **#506** (verwandt) **nicht ungeprüft schließen** — nur cross-linken:
   ```bash
   gh issue comment 506 --repo henemm/gregor_zwanzig \
     --body "Design-Entscheidung in #503 (Option B: Karte in Tab „Etappen & Wegpunkte\")."
   ```
3. Labels in #503 ggf. aus `issues.json` ergänzen (`area:editor`, `area:mobile`).

Report at the end: how many issues were created, updated, skipped (closed),
or flagged for user-decision.

### 4. Create only the truly new issues

Iterate over `issues.json` and run for each entry:

```bash
gh issue create \
  --repo henemm/gregor_zwanzig \
  --title "<title from json>" \
  --label "<label1>" --label "<label2>" --label … \
  --body-file "claude-code-handoff/<body_file from json>"
```

**Labels:** Some labels in `issues.json` may not exist yet in the repo. Create them first if needed:

```bash
gh label list --repo henemm/gregor_zwanzig
# create missing ones (idempotent — failures are OK if exists):
for spec in \
  "design-compliance:c45a2a:Design system compliance issue" \
  "foundation:8c3e1a:Foundational change — do first" \
  "feature:2a6cb3:New feature" \
  "backend-coordination:6b675c:Requires backend changes" \
  "breaking-change:a83232:Breaking change to existing UX" \
  "epic:6b46c1:Übergreifendes Mehrphasen-Vorhaben mit Sub-Issues" \
  "ux:c08a1a:UX improvement" \
  "bug:a83232:Bug fix" \
  "priority:high:a83232:" \
  "priority:medium:c08a1a:" \
  "area:tokens:9a958a:" \
  "area:home:9a958a:" \
  "area:trips:9a958a:" \
  "area:editor:9a958a:" \
  "area:alerts:9a958a:" \
  "area:reports:9a958a:" \
  "area:compare:9a958a:" \
  "area:mobile:9a958a:" \
  "area:sidebar:9a958a:" \
  "area:weather:9a958a:" \
  "area:output:9a958a:Briefing-Output · Spalten/Detail/Aus-Layout" \
  "area:components:9a958a:Atoms / Molecules / Templates" \
  "area:archive:9a958a:Archiv-Seite" \
  "accessibility:2a6cb3:WCAG-Konformität, Kontrast, Tastatur, Screenreader"; do
  name="${spec%%:*}"; rest="${spec#*:}"; color="${rest%%:*}"; desc="${rest#*:}"
  if [ -n "$desc" ]; then
    gh label create "$name" --color "$color" --description "$desc" --repo henemm/gregor_zwanzig 2>/dev/null || true
  else
    gh label create "$name" --color "$color" --repo henemm/gregor_zwanzig 2>/dev/null || true
  fi
done
```

Or use the included `create-issues.sh` which handles this.

### 5. Report back

Print a per-issue summary (created / updated / skipped-closed / asked-user)
with URLs where applicable. Example:

```
Dedupe summary (15 entries in issues.json):
  CREATED  #58  Output-Layout-System            https://github.com/henemm/gregor_zwanzig/issues/58
  UPDATED  #44  Replace native checkboxes       https://github.com/henemm/gregor_zwanzig/issues/44
  SKIPPED  #42  Fix dangling CSS variables      (closed, already merged)
  ASKED    —    Sidebar logo                    (no match, status=existing-or-update)
```

### 6. No "start with X" recommendation

Unlike earlier handoffs, the user's repo state is now mixed (several issues
done, others in flight). Do not recommend a starting point. Only the new
issue (`status: "new"`) is a fresh work item; everything else is
user-prioritized.

## Manifest · packet integrity

Before starting, verify the handoff packet arrived intact. Expected file
count in `claude-code-handoff/` matches `MANIFEST.txt`:

```bash
bash claude-code-handoff/check-manifest.sh   # or eyeball the count
wc -l claude-code-handoff/MANIFEST.txt
```

If counts don't match, the upload was truncated — ask the user for a fresh
zip and stop.

## Edge cases & notes

- **Issue 00 / body-00.md** is the highest-impact foundation fix. Do it first.
- **Issue 01 / body-01.md** depends on no other issues but provides `<Checkbox>` and
  `<Select>` components that issues 07, 08, 09, 10 reference. If you implement
  the issues sequentially, do 00 → 01 first.
- The bodies contain code blocks with `var(--g-*)` references that map to
  tokens defined in `frontend/src/app.css` (`@layer base { :root { ... } }`).
- Tests: every issue's acceptance criteria notes the relevant `data-testid` /
  Playwright selectors that must be preserved.

## If something fails

- **`gh issue create` fails with HTTP 422 on labels:** the label doesn't exist; create it (step 3).
- **Screenshots show as broken images in GitHub:** Confirm step 2 push succeeded and the URL is reachable with curl. Sometimes raw.githubusercontent.com takes 1-2 min to propagate.
- **Title is too long:** GitHub caps at 256 chars. None of these should hit that, but if they do, truncate to 250 + "…".
- **User wants to skip a screen:** Ask the user before creating. They may have a specific subset in mind.
