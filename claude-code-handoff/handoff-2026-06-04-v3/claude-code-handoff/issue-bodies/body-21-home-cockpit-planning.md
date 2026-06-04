<!-- gregor-zwanzig-handoff: stable_id=home-cockpit-planning -->

# Startseite — prioritätsbasiertes Einzel-Hero-Cockpit (Trip ODER Orts-Vergleich) + Planungs-/Leerzustand + QuickAction/SetupResumeCard

**Typ:** feature · design-compliance
**Stable-ID:** `home-cockpit-planning`
**Areas:** `area:home`, `area:components`, `area:compare`, `area:mobile`
**PO-Reviews:**
- 2026-06-03 (Henning) · Startseiten-Nutzen, Etappen-Verlauf, Szenario-Schärfung → Cockpit + Leerzustand
- 2026-06-03 (Henning) · **Modell-Schärfung:** Trip- und Vergleichs-Modus sind faktisch exklusiv → **ein** prioritätsbasierter Hero; „Was geht raus" ehrlich auf den aktiven Kontext gescopet; Überlappungs-Fall als schlanke Zeile.

> **⚠️ Dedupe vor Anlegen (CLAUDE.md-Workflow).** Dieses Issue berührt
> bewusst Themen, die schon laufen. **Vor dem Anlegen prüfen und ggf.
> cross-linken statt duplizieren:**
> - **Epic #368** (Atomic-Design-Komponentenbibliothek, Unter-Issues
>   #369–#374): Die neuen Molecules (`QuickAction`, `SetupResumeCard`,
>   optional `CompareStatusRow`) gehören in dieses Epic. Falls ein passendes
>   Unter-Issue existiert → dort einhängen; sonst als neues Unter-Issue von
>   #368 anlegen und hier referenzieren.
> - **#10 `ortsvergleich-wizard`** (Startseite-Kacheln für Orts-Vergleiche):
>   Der Vergleich erscheint auf der Startseite jetzt NICHT mehr als großes
>   Kachel-Grid, sondern als **Hero (wenn aktiver Kontext)** oder als schlanke
>   **„Außerdem beobachtet"-Zeile**. Das **verfeinert** #10 — Body von #10
>   nicht überschreiben, cross-linken.
>
> `gh issue list --search "in:body gregor-zwanzig-handoff: stable_id=home-cockpit-planning"`
> sowie `gh issue list --label epic` und `gh issue list --search "Startseite"`
> laufen lassen, bevor entschieden wird.

---

## Problem

Die Startseite war ursprünglich ein **Briefing-Reader** (heutige/morgige Etappe
mit Höhenprofil-Sparkline + Prosa, dazu ein Etappen-Pillstreifen). Das
widerspricht dem Produkt-Grundverständnis:

> Die Webseite wird zu ~90 % **vor** dem Trip benutzt (Einrichten). Während der
> Reise konsumiert Gregor die Briefings in seinen **Kanälen** (Email · Signal ·
> Telegram · SMS), nicht im Browser. Greift er unterwegs doch auf die Seite zu,
> dann mit **zwingendem Grund**: etwas Dringendes ändern (Pausentag, Wetter-
> Metriken, Zeitplan) oder prüfen, ob ein Fehler vorliegt — bei schlechtem
> Empfang, in wenigen Klicks.

Die erste Cockpit-Iteration (Tag-X/Y statt Reader, Schnellaktionen) war richtig,
hatte aber drei konzeptionelle Lücken, die der PO-Review 2026-06-03 aufgedeckt
hat:

1. **„Was geht raus" war heimlich trip-scoped.** Der Titel klang wie ein
   globales Postausgangs-Fach („Versand · heute · Alle Kanäle ok"), zeigte aber
   ausschließlich Trip-Briefings. Wo und wann **Vergleichs**-Briefings
   rausgehen, stand nirgends.
2. **Zwei parallele Ströme, obwohl die Modi exklusiv sind.** In der Praxis ist
   man entweder mitten in einem Multiday-Trip **oder** auf einer Hütte / im
   Skigebiet und nutzt einen Orts-Vergleich. Die Startseite versuchte beides
   gleichrangig zu zeigen (großes Trip-Cockpit **und** Vergleichs-Kachel-Grid)
   statt den **einen aktiven Kontext** in den Vordergrund zu stellen.
3. **Streck-Artefakt.** Die Aktiv-Trip-Karte saß in einem `1.4fr/1fr`-Grid mit
   `flex-column` + `margin-top:auto`-Footer und wurde auf die Höhe der rechten
   (höheren) Spalte gestreckt → ein großes leeres Loch zwischen Fortschritts-
   balken und Kanal-Footer. Las sich wie ein Render-Fehler.

## Lösung — prioritätsbasiertes Einzel-Hero-Cockpit

**Kernprinzip:** Es gibt zu jedem Zeitpunkt **einen aktiven Kontext**, keinen
gemischten globalen Strom. Die Startseite stellt genau diesen Kontext als Hero
dar und scopt alles Statushafte ehrlich auf ihn.

### Hero-Priorität

| Bedingung | Hero | „Was geht raus" zeigt |
|---|---|---|
| Läuft ein Trip (heute ∈ `[startDate, endDate]`) | **aktiver Trip** | Trip-Briefings |
| Kein Trip live, aber ≥ 1 aktiver Orts-Vergleich | **erster aktiver Vergleich** | dessen Vergleichs-Briefings |
| Nichts live (90-%-Normalfall) | — (kein Hero) | Planungs-/Leerzustand (Abschnitt B) |

### A · Cockpit · Hero = aktiver Trip (`mode="trip"`)
1. **Läuft alles?** — Status-Grid (`align-items: start`, behebt das Streck-Loch):
   - **Hero-Karte (links):** Live-Pill **Tag X von Y** + Fortschrittsbalken,
     Name, Kanal-Gesundheit-Footer (Dots je Kanal). Wird nur so hoch wie ihr
     Inhalt — **kein** Stretch.
   - **Rechts:** Karte **„Was geht raus · KHW 403"** (Kontextname im Titel) +
     Karte **„Alerts · letzte 24 h"**.
2. **Überlappung — „Außerdem beobachtet"** *(nur wenn zusätzlich aktive
   Vergleiche laufen)*: schlanke, klickbare Status-Zeilen unter dem Cockpit —
   je Vergleich Name · Region · **nächster Versand** · Kanäle · `→`. **Keine**
   Hero-Behandlung, **kein** großes Kachel-Grid. (PO: „Es kann immer den Fall
   geben, dass man zusätzlich zum Trip ein paar Einzelorte beobachten will.")
3. **Schnell eingreifen** — `QuickAction`-Reihe (4×) → Editor-Tabs des Trips:
   *Pausentag → Etappen & Wegpunkte · Wetter-Metriken → Wetter-Metriken ·
   Briefing-Zeitplan → Briefing-Zeitplan · Vorschau prüfen → Vorschau*
   (kanonische Tab-Namen aus #20).
4. **Einrichten** — Archiv-Absprung (frühere Trips).

### A2 · Cockpit · Hero = aktiver Orts-Vergleich (`mode="compare"`)
Gleiche Grammatik, anderer Kontext (man ist auf der Hütte / im Skigebiet, kein
Trip live):
1. **Hero-Karte:** Aktiv-Pill, Vergleichs-Name, Region, `N Orte · Horizont`,
   zwei Mono-Kacheln **Zeitplan** + **Nächster Versand**, Kanal-Footer.
2. **Rechts:** **„Was geht raus · &lt;Vergleichs-Name&gt;"** (synthetisiert aus
   `lastSent`/`nextSend`) + Alerts (kontextspezifisch; „Keine" mit Erklärtext,
   wenn keine Schwelle überschritten).
3. **„Außerdem beobachtet"** = die übrigen aktiven Vergleiche (alle außer dem
   Hero).
4. **Schnell eingreifen** — `QuickAction` → Vergleichs-Editoren:
   *Orte bearbeiten → Verglichene Orte · Ideal-Werte ändern → Ideal-Profil ·
   Briefing-Zeitplan → Zeitplan & Kanäle · Vorschau prüfen → Vorschau*.
5. **Einrichten** — „Kein Trip geplant" + CTA **Neuer Trip** + Archiv.

### B · Planungs-/Leerzustand (gar nichts live — der 90-%-Normalfall)
Unverändert gegenüber der ersten Iteration, lebt separat in
`screen-home-planning(.jsx|-mobile.jsx)`:
1. Ehrlicher Hinweis „Aktuell läuft kein Trip — Briefings kommen automatisch in
   die Kanäle, sobald die nächste Reise startet."
2. **Weiter einrichten** — zwei `SetupResumeCard` (nächster geplanter Trip +
   Vergleichs-Entwurf), je Setup-Fortschritt + **„Setup fortsetzen"**.
3. **Schnell anlegen** — Neuer Trip / Neuer Orts-Vergleich / Test-Briefing.
4. Archiv.

**Entfernt aus dem Cockpit:** Heute-/Morgen-Lesefläche (Sparkline + Prosa), der
Etappen-Pillstreifen **und** das große „Aktive Orts-Vergleiche"-Kachel-Grid
(durch Hero bzw. „Außerdem beobachtet" ersetzt).

## Neue / betroffene Atomic-Design-Bauteile (gehören zu Epic #368)

**`QuickAction` (Molecule)** — Schnellaktions-Kachel: Glyph-Tile + Label +
Ziel-Sublabel + Chevron. Klick-Ziel = genau **ein** Editor/Tab. Props:
`glyph` (`pause|metrics|clock|bell|send|eye|route`), `label`, `sub`, `tone`
(`default|accent`), `size` (`md` Desktop · `lg` Mobile, Touch-Target ≥ 44 px),
`onClick`. KEIN Lese-Surface. *(Bereits im Mockup vorhanden.)*

**`SetupResumeCard` (Molecule)** — Planungs-Karte „mach weiter, wo du
aufgehört hast": Setup-Fortschritt (Trip ODER Vergleich) als Schritt-Checkliste
(`steps: [{ label, done }]`) + Balken, CTA springt in den ersten offenen
Wizard-Schritt. *(Bereits im Mockup vorhanden.)*

**`CompareStatusRow` (Molecule · empfohlen, neu)** — die schlanke
„Außerdem beobachtet"-Zeile: Dot · Name · `N Orte · Region` · **Nächster
Versand** (Mono) · Kanal-Chips · `→`. Klick = Vergleichs-Detail. Im Desktop-
Mockup als `HomeAlsoWatchedRow`, im Mobile-Mockup als `MHomeAlsoWatchedRow`
umgesetzt (Touch ≥ 44 px). **Empfehlung (Tech-Lead):** beim Bau zu **einer**
kanonischen `CompareStatusRow` mit `dense`-Prop vereinheitlichen — analog zu
`CompareTile`/`BriefingTimelineRow` — statt zwei Page-Varianten. Falls eine
bestehende kompakte Compare-Zeile aus #10 das abdeckt, diese wiederverwenden.

> **Babel-Scope-Hinweis (CLAUDE.md):** Page-lokale Helfer in `screen-home*.jsx`
> tragen Page-Prefix (`HomeHeroTrip`, `MHomeHeroCompare`, …), damit sie keine
> kanonischen Atoms/Molecules global überschreiben. Beim Heben in die
> Bibliothek den Prefix entfernen.

## Datenmodell-Hinweise (Frontend)

- **Hero-Entscheidung:** `liveTrip = trips.find(t => today ∈ [startDate,endDate])`.
  `mode = liveTrip ? "trip" : "compare"`. Im Compare-Modus ist der Hero
  `activeCompares[0]`; „Außerdem beobachtet" = die restlichen aktiven Vergleiche.
  Im Trip-Modus = **alle** aktiven Vergleiche.
- **Tag X von Y:** aus `trip.startDate`/`endDate` + heutigem Datum ableiten.
- **„Was geht raus"-Scope:** strikt der aktive Kontext. Titel trägt dessen
  Namen (`Was geht raus · <trip.shortName | sub.name>`). Trip-Briefings aus dem
  Versand-Plan; Vergleichs-Briefings aus `sub.lastSent`/`sub.nextSend`
  (`schedule`, `channels`).
- **„Nächster Versand" je Vergleich:** `sub.nextSend` (vorhanden im Datenmodell).
- **Identische Hero-/Scope-Logik in Backend + Frontend** dokumentieren, falls
  ein Server-gerendertes Cockpit existiert (Single-Source der Priorität).

## Acceptance Criteria

- [ ] Startseite zeigt **kein** Briefing-Lese-Surface (keine Sparkline, keine
      Etappen-Prosa) und **keinen** Etappen-Pillstreifen.
- [ ] Cockpit hat **genau einen Hero** nach Priorität: aktiver Trip, sonst
      aktiver Orts-Vergleich. Bei gar nichts live → Planungs-/Leerzustand.
- [ ] **„Was geht raus" trägt den Kontextnamen** im Titel und zeigt
      ausschließlich Briefings des aktiven Kontexts (kein irreführender
      globaler Anstrich).
- [ ] **Überlappungsfall:** Laufen zusätzlich zum Trip Vergleiche, erscheinen
      sie als schlanke **„Außerdem beobachtet"-Zeile** mit sichtbarem
      *Nächster Versand* — nicht als Hero, nicht als großes Kachel-Grid.
- [ ] **Compare-Hero-Zustand existiert** (kein Trip live): Hero zeigt
      Zeitplan + Nächster Versand, Schnellaktionen zielen auf Vergleichs-
      Editoren.
- [ ] **Kein Streck-Artefakt:** die Hero-Karte ist nur so hoch wie ihr Inhalt
      (`align-items: start` im Status-Grid), kein leeres Loch.
- [ ] `QuickAction`, `SetupResumeCard` (und idealerweise `CompareStatusRow`)
      liegen als wiederverwendbare Molecules in der Komponentenbibliothek
      (Epic #368), nicht inline.
- [ ] Mobile spiegelt alle Zustände (Trip-Hero, Compare-Hero, Planung);
      Schnellaktionen / Status-Zeilen ≥ 44 px Touch.
- [ ] Kontrast WCAG-AA (PO-Leitprinzip „hoher Kontrast = Lesbarkeit").
- [ ] Jedes interaktive Element verlinkt exakt gemäß Routing-Tabelle
      (Tab-Ziele = kanonisches #20-Tab-Set); keine erfundenen Routen.

## Referenz-Mockups (kanonisch im Design-Projekt)

- **Desktop:** `Gregor 20 - Desktop.html` · Artboards `home` (Trip-Hero +
  „Außerdem beobachtet"), `home-compare` (Vergleich-Hero), `home-planning`
  (Leerzustand) · Screens `screen-home.jsx` (Prop `mode="trip"|"compare"`),
  `screen-home-planning.jsx`
- **Mobile:** `Gregor 20 - Mobile.html` · Artboards `m-home`, `m-home-compare`,
  `m-home-planning` · Screens `screen-home-mobile.jsx` (Prop `mode`),
  `screen-home-planning-mobile.jsx`
- **Molecules:** `molecules.jsx` → `QuickAction`, `QuickActionGlyph`,
  `SetupResumeCard` (+ geplant `CompareStatusRow`)

## Verlinkung / Routing — was zeigt wohin (verbindlich)

> **Anker:** Alle Tab-Ziele referenzieren das **kanonische Tab-Set aus #20
> (`canonical-ia-navigation` / `nav-map.jsx`)**. Der konkrete Router-Pfad ist
> Eigentum von #20 / des Repo-Routers — dieses Issue legt nur Quell-Element →
> Ziel-Screen + Tab/Schritt fest. Im Mockup sind die Handler No-ops.

### Cockpit · Hero = aktiver Trip
| Quell-Element | Ziel-Screen | Tab / Zustand |
|---|---|---|
| Schnellaktion **Pausentag einplanen** | `screen-trip-detail` (`-mobile`) | Tab **Etappen & Wegpunkte** (`screen-waypoint-editor`) |
| Schnellaktion **Wetter-Metriken ändern** | `screen-trip-detail` | Tab **Wetter-Metriken** (`screen-metrics-editor`) |
| Schnellaktion **Briefing-Zeitplan** | `screen-trip-detail` | Tab **Briefing-Zeitplan** |
| Schnellaktion **Vorschau prüfen** | `screen-trip-detail` | Tab **Vorschau** (Verifikation, kein Konsum) |
| Hero-Karte · **Trip öffnen →** / Klick | `screen-trip-detail` | Tab **Übersicht** (read-only) |
| „Was geht raus"-Karte | `screen-trip-detail` | Tab **Briefing-Zeitplan** |
| Alerts-Karte · **Schwellen →** | `screen-trip-detail` | Tab **Alerts** (`screen-alert-config`) |
| **„Außerdem beobachtet"-Zeile** · Klick | `screen-compare-detail` (`-mobile`) | Setup/Übersicht (NICHT Tages-Briefing) |
| **„Außerdem beobachtet"** · „Alle Vergleiche →" | `screen-compare-list` (`-mobile`) | Liste |

### Cockpit · Hero = aktiver Orts-Vergleich
| Quell-Element | Ziel-Screen | Tab / Zustand |
|---|---|---|
| Hero-Karte · **Vergleich öffnen →** / Klick | `screen-compare-detail` | Setup/Übersicht |
| Schnellaktion **Orte bearbeiten** | `screen-compare-detail` / `screen-location-new` | Abschnitt **Verglichene Orte** |
| Schnellaktion **Ideal-Werte ändern** | `screen-compare-wizard` (`mode="edit"`) | Schritt **Idealwerte** |
| Schnellaktion **Briefing-Zeitplan** | `screen-compare-detail` | Abschnitt **Zeitplan & Kanäle** |
| Schnellaktion **Vorschau prüfen** | `screen-compare-detail` | Abschnitt **Vorschau** |
| „Was geht raus"-Karte | `screen-compare-detail` | Abschnitt **Zeitplan & Kanäle** |
| **„Außerdem beobachtet"-Zeile** · Klick | `screen-compare-detail` | Setup/Übersicht |
| **Neuer Trip** (Einrichten) | `screen-trip-wizard` | Schritt 1 (frisch) |

## Topbar — gleichrangige Erstellungs-Pfade (PO 2026-06-03)

Trip und Orts-Vergleich sind im Produktmodell **co-equal** (COPY.md führt
„+ Neuer Trip" **und** „+ Neuer Vergleich" als gleichwertige CTAs). Die Topbar
zeigte aber nur **„+ Neuer Trip"** prominent — die Asymmetrie hat der PO als
irritierend markiert.

- **Desktop** (`screen-home.jsx`, `screen-home-planning.jsx`): in der Topbar
  **zwei gleich gewichtete** Outline-Buttons (`Btn variant="ghost"` mit `+`):
  **„Neuer Trip"** und **„Neuer Vergleich"**. Bewusst **kein** dunkler
  Primary-Button für nur einen der beiden (das reproduziert die Schieflage).
  „Test senden" rutscht auf `variant="quiet"` (Tertiär) — zugleich die
  COPY.md-konforme Kurzform statt „Test-Briefing senden".
- **Mobile** (`screen-home-mobile.jsx`, `screen-home-planning-mobile.jsx`):
  ein Platz weniger → das **„+"-IconBtn** öffnet ein **Bottom-Sheet
  (`Sheet snap="peek"`) als Create-Chooser** mit beiden Pfaden gleichrangig
  (Helper `MHomeCreateOption`, Touch ≥ 64 px). Kein zweites, mehrdeutiges
  Plus-Icon.

**Routing der Topbar-Aktionen:**

| Quell-Element | Ziel-Screen | Tab / Schritt |
|---|---|---|
| Topbar **Neuer Trip** | `screen-trip-wizard` (`-mobile`) | Schritt 1 (frisch) |
| Topbar **Neuer Vergleich** | `screen-compare-wizard` (`mode="create"`) | Schritt 1 (frisch) |
| Topbar **Test senden** | aktiver Kontext (Trip- bzw. Vergleichs-Vorschau) | Verifikation, kein Konsum |

**„Test senden" — Eindeutigkeit (PO 2026-06-03).** Das kurze Label ließ offen,
*welches* Briefing und *an wen* gesendet wird (die heikle Frage: an mich oder an
die echten Empfänger?). Lösung ohne das DS-kurze Label zu verlängern:
- **Klick öffnet ein Confirm** (Desktop: Popover unter dem Button `HomeTestSend`;
  Mobile: `Sheet snap="peek"`), das explizit sagt: „Sendet das aktuelle Briefing
  von **&lt;Kontext&gt;** einmalig an **deine eigenen Kanäle** — die echten
  Empfänger und der Zeitplan sind nicht betroffen." + Kanal-Chips des Kontexts +
  Primär-CTA **„Jetzt an mich senden"**.
- **Scope = aktiver Kontext.** „Test senden" erscheint nur im **Cockpit**
  (Trip- oder Vergleich-Hero). Im **Planungs-/Leerzustand entfällt es in der
  Topbar** (nichts aktiv); die Verifikation läuft dort über die Body-QuickAction
  „Test-Briefing prüfen → Vorschau".

> Akzeptanz-Ergänzung: Startseite bietet **beide** Erstellungs-Pfade
> gleichrangig sichtbar an (Desktop: zwei Buttons; Mobile: Create-Chooser-
> Sheet). Kein Pfad ist visuell privilegiert.

### Planungs-/Leerzustand
| Quell-Element | Ziel-Screen | Tab / Schritt |
|---|---|---|
| SetupResumeCard **Trip** · „Setup fortsetzen" | `screen-trip-wizard` (`-mobile`) | erster **offener** Schritt (`steps.find(!done)`) |
| SetupResumeCard **Vergleich** · „Setup fortsetzen" | `screen-compare-wizard` (`mode="edit"`) | erster offener Schritt |
| Schnell anlegen · **Neuer Trip** | `screen-trip-wizard` | Schritt 1 (frisch) |
| Schnell anlegen · **Neuer Orts-Vergleich** | `screen-compare-wizard` (`mode="create"`) | Schritt 1 (frisch) |

**Globale Navigation** (Sidebar/Bottom-Nav) bleibt unverändert: Heute · Trips ·
Ortsvergleich · Archiv (siehe `nav-map.jsx`).

## Out of Scope (Folge-Issues)

- Reale Wizard-Schritt-Persistenz / Resume-Routing (nur Mockup-CTA hier).
- „Nächste 48 h Versand-Plan"-Widget im Cockpit (separat diskutieren).
- Mehrere gleichzeitig laufende Trips (heute genau einer live angenommen).
- Reale Versand-Logs statt der aus `lastSent`/`nextSend` synthetisierten
  Vergleichs-Timeline (eigenes Daten-Thema).
