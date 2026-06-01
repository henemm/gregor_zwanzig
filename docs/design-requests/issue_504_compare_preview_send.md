# Antwort · Design-Request #504 — Ortsvergleich: Vorschau & Versand

**Status:** geplant · 2026-06-01 (Mockup-Bau folgt: Ortsvergleich-Hub)
**Bezug:** Issue #504 · Schwester zu #503 (Wegpunkt-Editor-Architektur)
**Mockup (Ziel):** `Gregor 20 - Desktop.html` → Sektion „Ortsvergleich" (Compare-Hub),
`Gregor 20 - Mobile.html` → Compare-Detail. CompareEmail-Quelle: `screen-compare-email.jsx`.

---

## TL;DR — Empfehlung

> **Vorschau und Versand sind zwei Tabs im Ortsvergleich-Hub — analog zum Trip-Hub.**
> Der Vergleich hat **eine** Detail-Fläche mit Tabs; „Vorschau" ist ein
> **Verifikations-Tab** (kein Konsum-Surface), „Versand" ist ein **Bearbeiten-Tab**.
> Die **CompareEmail** wandert als Inhalt des Vorschau-Tabs in den Hub — die
> bisherige Standalone-Sektion „Compare-Email" entfällt.

Eine Fläche pro Vergleich. Lesen passiert im Kanal, nicht in der App
(CLAUDE.md · Produkt-Grundverständnis).

---

## Einordnung ins kanonische Modell

Gleiches Drei-Rollen-Modell wie der Trip-Hub (`docs/.../canonical-ia`):

| Rolle | Wo im Compare-Hub |
|---|---|
| **Ansehen** | Tab „Übersicht" — Monitoring-Streifen (läuft / pausiert · nächster Versand · zuletzt raus · Kanal-Health) + Zusammenfassung |
| **Bearbeiten** | Tabs „Orte" · „Idealwerte" · „Layout" · „Versand" |
| **Verifizieren** | Tab „Vorschau" — CompareEmail zum Gegencheck |
| **Lesen** *(außerhalb der App)* | Email · Telegram · Signal · SMS |

**Charter §3 v1.1 bleibt gültig:** Kachel-Klick in der Übersichtsliste öffnet das
**Setup/Detail** (diesen Hub), **nicht** das Tages-Briefing.

---

## Tab-Set (kanonisch, exakt diese Reihenfolge)

`Übersicht · Orte · Idealwerte · Layout · Versand · Vorschau`

| # | Tab | Rolle | Inhalt |
|---|---|---|---|
| 1 | **Übersicht** | Ansehen | Monitoring-Streifen + kompakte Zusammenfassung (Orte-Anzahl, Profil, aktive Kanäle), je Sektion `Bearbeiten →`-Link |
| 2 | **Orte** | Bearbeiten | Verglichene Orte (Ranking-Reihenfolge), hinzufügen/entfernen/sortieren |
| 3 | **Idealwerte** | Bearbeiten | Was „gut" bedeutet — Score-Modell pro Metrik, profilabhängige Defaults |
| 4 | **Layout** | Bearbeiten | Spalten pro Kanal (Email ∞ · Telegram 8 · Signal 6 · SMS 0) |
| 5 | **Versand** | Bearbeiten | Rhythmus · Vorausschau · Kanäle · Aktivierung |
| 6 | **Vorschau** | Verifizieren | `CompareEmail` (profilabhängig). **Kein Klick-Ziel aus Listen.** |

Reuse der vorhandenen Compare-Domain-Molecules (`CompareLocationRow`,
`CompareIdealRow`, `CompareLayoutRow`, `CompareStatusPill`, `compareActions`,
`DetailRow`) — nichts neu erfinden.

---

## Vorschau (Tab 6) — Verhalten

- **Profil treibt Layout & Score.** `CompareEmail` rendert je `profileId`
  unterschiedliche Spalten und Score-Modell (Wintersport · Skitour · Trail-Running …).
  Der Hub mappt `sub.profileId` → einen gültigen CompareEmail-Profilschlüssel
  (Fallback, falls ein Profil noch kein CE-Datenset hat).
- **Kanal-Umschalter.** Email (Desktop-Inbox / iPhone-Mail) · Signal/Telegram-Bubble
  · SMS (Token-Format, ≤ 140 Z.). Gleiche Constraint-Logik wie beim Trip-Briefing
  (Organism #496) — Spalten, die ein Kanal nicht trägt, fallen weg.
- **Verifikation, nicht Konsum.** Klarer Hinweis: „So sieht dein Briefing aus —
  gelesen wird es unterwegs im Postfach, nicht hier." Plus „Test-Briefing jetzt senden".

## Versand (Tab 5) — Verhalten

- **Rhythmus** (z. B. „Sa 06:00", „tägl 07:00", „Fr 18:00") + **Vorausschau-Horizont**.
- **Kanäle** an/aus mit Health-Indikator (verifiziert / fehlt).
- **Aktivierung** als Schwelle: Entwurf → aktiv (Banner). Pausieren/Archivieren
  über die Hub-Header-Aktionen (analog Trip-Hub: Pausieren · Archivieren · Test senden).
- Versand erzeugt **kein** In-App-Reader-Surface — er schickt in die Kanäle.

---

## Abgrenzung Trip-Briefing ↔ Compare-Briefing

| | Trip-Briefing | Compare-Briefing |
|---|---|---|
| Frage | „Wie wird das Wetter auf **meiner Etappe**?" | „**Wo** ist es am besten?" |
| Zeilen | Stunden/Wegpunkte einer Route | Orte (Ranking, bester zuerst) |
| Score | — | profilabhängiges Ideal-Modell bestimmt das Ranking |
| Vorschau-Tab | Email/SMS des Tages-Briefings | CompareEmail mit Orts-Ranking |

Beide nutzen dieselbe Kanal-Constraint-Logik und dasselbe „Vorschau = Verifikation"-Prinzip.

---

## Umsetzungs-Schritte (für Claude Code)

1. **Compare-Detail → Hub:** `ScreenCompareDetail` (Desktop) + `ScreenCompareDetailMobile`
   auf die kanonische Tab-Leiste umstellen (6 Tabs, Query-Param `?tab=`).
2. **Vorschau-Tab** rendert `CompareEmail` (profil-gemappt) mit Kanal-Umschalter
   (Email/Signal/SMS), `viewport`-aware.
3. **Versand-Tab** aus den bestehenden Versand-/Kanal-Cards zusammensetzen
   (DetailRow + Channel-Pills + Aktivierungs-Banner).
4. **Standalone „Compare-Email"-Sektion entfernen**, sobald der Vorschau-Tab steht
   (Single-Source: CompareEmail im Hub).
5. **`COMPONENTS.md` / `SCREENS.json`** auf das neue Tab-Set ziehen
   (Vertrag: Mockup-Name = Code-Name = Katalog-Name).

---

## Acceptance Criteria

- [ ] Compare-Detail rendert genau die 6 kanonischen Tabs (Desktop + Mobile), `?tab=`-gesteuert.
- [ ] „Übersicht" ist read-only (Monitoring + Zusammenfassung + `Bearbeiten →`).
- [ ] „Vorschau" zeigt `CompareEmail` profilabhängig, mit Kanal-Umschalter; nirgends als Listen-Klick-Ziel verlinkt.
- [ ] „Versand" trägt Rhythmus · Horizont · Kanäle · Aktivierung; kein Reader-Surface.
- [ ] Kanal-Constraints (Email ∞ · Telegram 8 · Signal 6 · SMS 0) identisch zum Trip-Briefing.
- [ ] Standalone „Compare-Email"-Sektion existiert nicht mehr.
- [ ] Kachel-Klick (Liste) öffnet den Hub, nicht das Tages-Briefing (Charter §3).

---

## Out of Scope (Folge-Issues)

- Echtes Score-Tuning pro Profil (Backend-Daten-Logik).
- Pro-Kanal-Layout-Overrides (V2 — Default ist eine Config, die der Renderer kanalspezifisch kappt).
- Push-/Zustellungs-Logik der Kanäle.
