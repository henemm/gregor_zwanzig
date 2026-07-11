<!-- gregor-zwanzig-handoff: stable_id=canonical-ia-navigation -->
# Issue 20 · Kanonische Navigations-Architektur — ein Trip-Detail-Tab-Set + Erstellen/Ansehen/Bearbeiten-Modell (Desktop + Mobile)

**Type:** Foundation · Information-Architecture · Spec
**Priority:** High — Referenz-Spec, der #10 (Compare), #11 (Trip-Detail) und #407 (Wizard) folgen müssen

**Design Reference:**
- Sandbox-Source (kanonische Map): `nav-map.jsx` (`<NavMap platform="desktop|mobile" />`), gerendert als Sektion **„00 · Navigations-Karte"** in `Gregor 20 - Desktop.html` und `Gregor 20 - Mobile.html`
- Produkt-Grundgesetz: `CLAUDE.md` § „Produkt-Grundverständnis" — Einrichtungs- & Monitoring-Werkzeug, **nicht** Lese-Medium
- Betroffene Bestands-Issues: #11 (`trip-detail-page`), #10 (`ortsvergleich-wizard`), #407 (`wizard-screens-update-407-422`)

---

## Problem

Die Informations-Architektur ist an mehreren Stellen widersprüchlich verdrahtet — der PO findet sich nicht zurecht, und Implementierungen landen an der falschen Stelle:

1. **Drei divergierende Trip-Detail-Tab-Sets** für denselben Trip:
   - Sandbox `screen-trip-detail.jsx`: `Übersicht · Etappen & Wegpunkte · Wetter-Metriken · Briefing-Zeitplan · Alerts · Vorschau` (6)
   - Sandbox `screen-trip-edit-tabs.jsx`: `Route · Etappen & Wegpunkte · Wetter · Reports · Alarmregeln` (5)
   - Handoff `body-11.md`: `Übersicht · Etappen · Wetter · Reports · Alarme` (5)
2. **Der Wegpunkt-Editor wirkt wie eine eigene Seite** (eigene Canvas-Sektion „04"), ist aber konzeptionell der **Inhalt eines Tabs** — wo genau, war nie kanonisch festgelegt.
3. **„Ansehen" vs. „Bearbeiten" ist unscharf:** Es ist unklar, was eine read-only-Übersicht zeigt und was ein Editor ist. Folge: Editoren werden als Lese-Surfaces missverstanden, und die Briefing-Vorschau wird fälschlich als Konsum-Surface behandelt.

Dieses Issue legt **ein** Modell fest, an das sich alle Trip- und Compare-Screens halten.

---

## Das kanonische Modell

Pro Trip gibt es **genau drei** Oberflächen-Typen. Briefings werden **nicht in der App** gelesen, sondern in den Kanälen.

| Rolle | Was | Wo |
|---|---|---|
| **Erstellen** | Einmaliger, linearer Aufbau | Wizard (Vollbild) |
| **Ansehen** | Read-only Cockpit: was ist konfiguriert + Status | Trip-Detail · Tab „Übersicht" |
| **Bearbeiten** | Pro Aspekt genau ein Editor | Trip-Detail · die übrigen Tabs |
| **Lesen** *(außerhalb der App)* | Tägliche Briefings konsumieren | Email · Telegram · Signal · SMS |

**Grundregel für jede Feature-Frage:** dient es dem *Einrichten/Überwachen* → App. Dient es dem *täglichen Lesen* → Kanal. Die Briefing-**Vorschau** ist ein **Verifikations-Werkzeug innerhalb des Setups** („sieht meine Mail richtig aus?"), kein Konsum-Surface und kein Klick-Ziel von Listen.

---

## Kanonisches Trip-Detail-Tab-Set (Drift aufgelöst)

**Verbindlich, exakt diese sechs Tabs in dieser Reihenfolge:**

| # | Tab | Rolle | Inhalt | Sandbox-Mockup | Ziel (SvelteKit) |
|---|---|---|---|---|---|
| 1 | **Übersicht** | Ansehen | Read-only Cockpit. Gesamt-Höhenprofil, Etappenliste (read-only), Metriken-Chips, Briefing-Status, letzte Alerts. **Jede Sektion hat einen `Bearbeiten →`-Link in den passenden Tab.** | `screen-trip-detail.jsx` | `routes/trips/[id]/+page.svelte` (`?tab=overview`) |
| 2 | **Etappen & Wegpunkte** | Bearbeiten | Wegpunkt-Editor: Karte + Höhenprofil + Wegpunkt-Sidebar, drag-sortierbarer Etappen-Strip, Pausentage, KI-Wegpunkte. **Keine Lat/Lon-Inputs.** | `screen-waypoint-editor.jsx` / `screen-waypoint-editor-mobile.jsx` | `?tab=stages` |
| 3 | **Wetter-Metriken** | Bearbeiten | Spalten / Detail / Aus + Reihenfolge + Roh/Skala + Multi-Channel-Vorschau (Organism #496). | `screen-metrics-editor.jsx` / `screen-metrics-editor-mobile.jsx` | `?tab=metrics` |
| 4 | **Briefing-Zeitplan** | Bearbeiten | Morgen / Abend / Alert-Zeiten + Kanal-Zuordnung. Sendet in die Kanäle. | (in `screen-trip-detail.jsx` angerissen) | `?tab=schedule` |
| 5 | **Alerts** | Bearbeiten | Schwellwerte (Δ vs. absolut). | `screen-alert-config.jsx` / `screen-alert-config-mobile.jsx` | `?tab=alerts` |
| 6 | **Vorschau** | Verifizieren | Briefing-Check im Setup. **Kein Konsum-Surface.** | `screen-output-preview*.jsx` | `?tab=preview` |

**Konsequenzen für Bestands-Issues:**
- **#11 (`trip-detail-page`):** Das dort skizzierte Set (`Übersicht · Etappen · Wetter · Reports · Alarme`) wird durch das obige **ersetzt**. „Reports" → **„Briefing-Zeitplan"**, „Alarme" → **„Alerts"**, „Wetter" → **„Wetter-Metriken"**, und **„Vorschau"** kommt als 6. Tab hinzu. Etappen-Tab heißt voll **„Etappen & Wegpunkte"**.
- **`screen-trip-edit-tabs.jsx` (Edit-Host-Mockup):** wird **nicht** als separater Screen/Route geführt. Es gibt **keinen eigenen `/trips/[id]/edit`-Modus mit eigener Tab-Leiste** — Bearbeiten passiert in denselben Tabs des Trip-Details. Das Set `Route/Wetter/Reports/Alarmregeln` wird auf das kanonische Set gemappt und verworfen.

---

## Wizard = nur Erstellen

Der Trip-Wizard (`screen-trip-wizard*.jsx`, Ziel `routes/trips/neu`) ist **ausschließlich** der einmalige Aufbau, 5 Schritte: **Route → Etappen → Wetter → Layout → Reports** (Spec #407). Nach Abschluss landet der User im **Trip-Detail**. Der Wizard ist **kein** Bearbeiten-Surface — Änderungen an einem bestehenden Trip laufen über die Detail-Tabs, nicht über einen erneuten Wizard-Durchlauf.

- Wizard Schritt 2 „Etappen" ist die **leichte** Etappen-Liste (Reihenfolge/Vorlagen). Die **volle** Karten-/Wegpunkt-Bearbeitung lebt danach in Tab 2 des Trip-Details. Bewusste Arbeitsteilung, kein Duplikat.

---

## Ortsvergleich · analoges Modell (Compare-Hub, Issue #504)

Der Ortsvergleich nutzt **dasselbe Drei-Rollen-Skelett wie der Trip-Hub**: eine
Fläche pro Vergleich mit kanonischer Tab-Leiste. Bearbeiten passiert **in den
Tabs**, nicht über einen erneuten Wizard-Durchlauf (revidiert ggü. der früheren
„Wizard-im-Edit-Modus"-Skizze — siehe Hinweis unten).

| Rolle | Wo | Mockup | Ziel |
|---|---|---|---|
| Erstellen | Compare-Wizard (5 Schritte: Benennen → Orte → Idealwerte → Layout → Versand) | `screen-compare-wizard.jsx` | `routes/vergleich/neu` |
| Ansehen | Compare-Hub · Tab „Übersicht" (Monitoring + Zusammenfassung, read-only) | `screen-compare-detail.jsx` / `-mobile.jsx` | `routes/vergleich/[id]?tab=overview` |
| Bearbeiten | Compare-Hub · Tabs „Orte" · „Idealwerte" · „Layout" · „Versand" | `screen-compare-detail.jsx` / `-mobile.jsx` | `?tab=…` |
| Verifizieren | Compare-Hub · Tab „Vorschau" (CompareEmail profil-gemappt, Kanal-Umschalter) | `screen-compare-email.jsx` (im Hub gerendert) | `?tab=preview` |

**Kanonisches Compare-Hub-Tab-Set — exakt diese sechs Tabs in dieser Reihenfolge:**

| # | Tab | Rolle | Inhalt | Ziel |
|---|---|---|---|---|
| 1 | **Übersicht** | Ansehen | Monitoring-Streifen (läuft/pausiert · nächster/letzter Versand · Kanal-Health) + Zusammenfassung, je Sektion `Bearbeiten →` | `?tab=overview` |
| 2 | **Orte** | Bearbeiten | Verglichene Orte (Ranking-Reihenfolge), hinzufügen/entfernen/sortieren | `?tab=locations` |
| 3 | **Idealwerte** | Bearbeiten | Score-Modell pro Metrik, profilabhängige Defaults | `?tab=ideals` |
| 4 | **Layout** | Bearbeiten | Spalten pro Kanal (Email ∞ · Telegram 8 · Signal 6 · SMS 0) | `?tab=layout` |
| 5 | **Versand** | Bearbeiten | Rhythmus · Vorausschau · Kanäle (Health) · Aktivierung | `?tab=send` |
| 6 | **Vorschau** | Verifizieren | `CompareEmail` profilabhängig + Kanal-Umschalter. **Kein Klick-Ziel aus Listen.** | `?tab=preview` |

`sub.profileId` → gültiger CompareEmail-Profilschlüssel via `ceProfileFor`
(Fallback `wintersport-glacier`, falls ein Profil noch kein CE-Datenset hat).

**Charter §3 v1.1:** Kachel-Klick in der Übersicht öffnet den **Hub (Übersicht)**,
**nicht** das Tages-Briefing. (Deckungsgleich mit #10.)

> **Reconciliation (2026-06-01, Issue #504):** Die frühere Compare-Edit-Variante
> „Derselbe Wizard im Edit-Modus (`routes/vergleich/[id]/bearbeiten`)" ist
> **verworfen**. Bearbeiten läuft jetzt — exakt wie beim Trip — über die Hub-Tabs.
> Ein evtl. vorhandenes `/vergleich/[id]/bearbeiten` leitet auf `?tab=locations`
> (oder den passenden Tab) um. `screen-compare-wizard.jsx (mode="edit")` bleibt nur
> als Direkt-Sprung-Komfort beim *Erst*-Setup gültig, ist aber kein Edit-Surface
> eines bestehenden, aktiven Vergleichs.

---

## Plattform-Chrome (gleiches Skelett, andere Mechanik)

| | Desktop | Mobile |
|---|---|---|
| Globale Navigation | Sidebar links (persistent) | Bottom-Nav (4 Ziele, ≥44px) + Drawer (Kanäle/Einstellungen/Account) |
| Trip-Detail-Tabs | Tab-Leiste | Pill-Tab-Scroller (sticky) |
| Editor-Öffnung | Tab-Inhalt inline | Bottom-Sheet / Accordion (siehe Mobile-Readme) |
| Wizard | Vollbild-Schritte | Vollbild-Screens, Bottom-Nav ausgeblendet, sticky Action-Bar |

Beide Maps sind in `nav-map.jsx` (`platform`-Prop) als Single-Source gepflegt.

---

## Constraints

| ID | Constraint |
|---|---|
| C1 | Exakt **ein** Trip-Detail-Tab-Set, exakt diese 6 Labels in dieser Reihenfolge. Keine zweite Tab-Leiste, kein separater Edit-Route mit eigener Tab-Leiste. |
| C2 | Tab-State steckt im Query-Param (`?tab=overview|stages|metrics|schedule|alerts|preview`), damit `Bearbeiten →`-Links und Deep-Links funktionieren. Default = `overview`. |
| C3 | Tab „Übersicht" ist **read-only**: enthält Status + Zusammenfassungen + `Bearbeiten →`-Links, **keine** Eingabe-Controls. |
| C4 | Editoren (Tabs 2–5) sind die **einzigen** Schreib-Surfaces eines bestehenden Trips. Der Wizard schreibt nur bei der Erst-Erstellung. |
| C5 | Tab „Vorschau" und die Multi-Channel-Vorschau im Metriken-Editor sind Verifikation — **niemals** Klick-Ziel aus einer Liste, niemals als „heutiges Briefing im Browser" verlinkt. |
| C6 | Wegpunkt-Editor ohne Lat/Lon-Formularfelder (Karten-Pins + Profil-Klick) — Bestätigung von #296, nur die „Karte ganz entfernen"-Zeile ist revidiert. |
| C7 | Mobile nutzt **dieselben** Tab-IDs/Reihenfolge wie Desktop (nur kürzere Labels erlaubt: `Etappen`, `Metriken`, `Briefings`, `Vorschau`). |

---

## Acceptance Criteria

- [ ] `routes/trips/[id]/+page.svelte` rendert genau die 6 kanonischen Tabs in der definierten Reihenfolge, gesteuert über `?tab=`.
- [ ] „Übersicht" enthält keine Eingabe-Controls; jede Sektion hat einen `Bearbeiten →`-Link auf den passenden Tab (C3).
- [ ] Es existiert **keine** separate Edit-Route mit eigener Tab-Leiste; ein evtl. vorhandenes `/trips/[id]/edit` leitet auf `?tab=stages` (oder den passenden Tab) um.
- [ ] Tab „Etappen & Wegpunkte" hostet den Karten-/Wegpunkt-Editor (kein Lat/Lon-Formular).
- [ ] Tab „Vorschau" ist nirgends als Klick-Ziel einer Trip-/Compare-Liste verlinkt.
- [ ] Ortsvergleich: Kachel-Klick → Compare-Hub (Tab „Übersicht"), **nicht** das Tages-Briefing; „Bearbeiten →" springt in den passenden Hub-Tab.
- [ ] Compare-Hub rendert genau die 6 kanonischen Tabs (`overview · locations · ideals · layout · send · preview`), `?tab=`-gesteuert, Default `overview` (Desktop + Mobile).
- [ ] Compare-Tab „Vorschau" rendert `CompareEmail` profil-gemappt (`ceProfileFor`) mit Kanal-Umschalter und ist nirgends als Listen-Klick-Ziel verlinkt.
- [ ] Mobile-Tab-Scroller verwendet dieselben Tab-IDs/Reihenfolge wie Desktop (C7).
- [ ] `body-11.md`-Tab-Namen sind im Code auf das kanonische Set migriert (Reports→Briefing-Zeitplan, Alarme→Alerts, +Vorschau).
- [ ] Eine kurze `docs/architecture/navigation.md` hält das Modell + die Tab-Tabelle fest (aus diesem Issue übernommen), damit es nicht erneut driftet.

---

## Edge Cases

| Fall | Erwartetes Verhalten |
|---|---|
| Deep-Link auf `?tab=stages` bei noch leerem Trip | Editor öffnet leer/erst nach GPX-Import; kein Crash. |
| User klickt in „Übersicht" auf „Bearbeiten →" einer Metrik | Wechsel zu `?tab=metrics`, nicht in ein Modal. |
| Pausentag im Etappen-Tab | Read-only-Datum durch editierbares Feld ersetzt, keine Wegpunkte (siehe #18). |
| Trip ist „Archiviert" | Detail bleibt erreichbar, Editoren read-only/disabled; „Übersicht" zeigt retrospektiven Stand. |
| Alter Bookmark auf `/trips/[id]/edit` | 301/Redirect auf `routes/trips/[id]?tab=stages`. |
| SMS-Kanal in „Vorschau" | Zeigt flaches Token-Format (≤140 Z.), keine Tabelle — Verifikation, kein Konsum. |

---

## Out of Scope (eigene Folge-Issues)

- Konkretes visuelles Layout der einzelnen Tabs (liegt in #11, #14, #496, #18, #407) — dieses Issue legt nur **Struktur + Benennung + Rollen** fest.
- Routing-Library-Details / Guards für Archiv-Read-only.
- Inhaltliche Briefing-Render-Logik (liegt in #14 Output-Layout-System).

---

## 📎 Screenshots

**Soll · Navigations-Karte Desktop (Single-Source `nav-map.jsx`)**

![soll-ia-navigation-desktop](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-ia-navigation-desktop.png)

**Soll · Navigations-Karte Mobile**

![soll-ia-navigation-mobile](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-ia-navigation-mobile.png)
