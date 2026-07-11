<!-- gregor-zwanzig-handoff: stable_id=compare-standing-monitor -->

# Orts-Vergleich = stehender Monitor — Neutralisierung (App-Screens)

**PO-Entscheidung Henning, 2026-07-11.** Konzept-Herleitung:
`docs/konzept-vergleich-stehender-monitor.md` im Design-Projekt.

> **⚠️ Modell-Korrektur (PO Henning 2026-07-11, spät) — Versand:** Das
> ursprünglich hier beschriebene **rollierende Zeitfenster** („Do 18:00 →
> Fr–So"), der **Versandrhythmus** und die **„Tageszeit bewertet"**-Angabe sind
> **verworfen** — erfundene Features, nicht gewollt. Der Vergleich-Versand
> funktioniert **identisch zum Trip**: der Nutzer wählt nur die
> **Briefing-Uhrzeiten** (editierbar), Prinzip wie beim Trip — **Morgen-Briefing
> = heutiger Tag, Abend-Briefing = morgen**. Kein `timeWindow`, kein `schedule`-
> Rhythmus. Umgesetzt in `versand-tab.jsx` (`VT_SchedulePlan`), verdrahtet über
> #29b. Die Neutralisierung (kein Score/Rang/Empfehlung) + „Orte = Spalten"
> **bleiben** gültig; nur der Versand-Teil dieses Issues ist ersetzt. Stellen
> unten, die noch „Zeitfenster/Rhythmus" nennen, sind entsprechend zu lesen.

> **Einordnung (2026-07-11, zweite Runde):** Dieses Issue ist **Phase 2** des
> Epics `stable_id=briefing-abo-chassis` (gemeinsames Datenmodell Trip +
> Vergleich, Korridor-Konzept, endDate nullable). Es bleibt eigenständig
> umsetzbar; bei Umsetzung dort abhaken.

**Design Reference (kanonisch, `claude-code-handoff/current/jsx/`):**
- `screen-compare-editor.jsx` (`CE_`) — Layout-Tab + neutrale Vorschau + Versand-Tab
- `screen-compare-detail.jsx` (`CHub_`) — Monitoring-Streifen + Versand (Briefing-Uhrzeiten)
- `screen-compare-list.jsx` — Intro-Copy
- `mock-locations.jsx` — Datenmodell-Referenz (`timeWindow`, Layouts ohne Rang)
- Screenshots:
  - https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-compare-standing-monitor.png (Editor · Layout-Tab · neutrale Vorschau)
  - https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-compare-standing-monitor-versand.png (Hub · Versand · Rhythmus & Zeitfenster)

## Modell

Der Orts-Vergleich ist **kein Proto-Trip** und konvertiert nie in einen Trip.
Er ist ein **stehender Monitor**: dieselben Orte, **kein Enddatum-Zwang** —
läuft bis pausiert/gelöscht. Der **Versand funktioniert wie beim Trip**: nur
editierbare **Briefing-Uhrzeiten** (Morgen = heutiger Tag, Abend = morgen),
kein rollierendes Fenster, kein Rhythmus (s. Korrektur oben). Das Briefing ist
**neutral**: kein Score, kein Rang, keine Empfehlung (deckungsgleich mit
CompareEmailV2, PO 2026-07-08). Idealwerte sind **Markierungen** (Wert im
Idealbereich → grün), keine Bewertung.

## Datenmodell (Änderung)

```ts
interface CompareSubscription {
  id: string;
  name: string;
  region?: string;
  profileId: string;                    // Aktivitätsprofil
  status: "draft" | "active" | "paused" | "archived";
  locationIds: string[];                // ≥ 2 · Reihenfolge = Spalten im Briefing
  channels: ("email" | "telegram" | "sms")[];

  // Versand — wie Trip: editierbare Briefing-Uhrzeiten, KEIN Rhythmus/Fenster
  // (PO 2026-07-11, spät — rollierendes timeWindow + schedule.rhythm verworfen):
  briefings: {
    id: "morning" | "evening";          // Morgen = heutiger Tag · Abend = morgen
    time: string;                        // "HH:MM", vom Nutzer editierbar
    on: boolean;
    channels: ("email" | "telegram" | "sms")[];
  }[];
  // (dayStart/dayEnd „bewertete Tageszeit" ebenfalls gestrichen — keine
  //  Bewertungs-Semantik an der Oberfläche, Neutralitäts-Prinzip.)

  // Bewertung — NUR Markierung:
  ideals: { metric: string; ideal: string; corridor: [number, number];
            weight: "hoch" | "mittel" | "niedrig" /* = Priorität für Übersicht */ }[];

  // Übersicht = Orte als Spalten, Metriken als Zeilen (V2):
  layout: { [channel: string]: string[] };  // Metrik-ZEILEN je Kanal, ohne "Rang"/"Ort"
}
```

**Migration Bestands-Daten:** `horizon`/`timeWindow` entfernt — Versand auf
editierbare **Briefing-Uhrzeiten** (morning = heute / evening = morgen, wie Trip)
umstellen. `layout`-Arrays: Einträge `"Rang"` und `"Ort"` entfernen.
Composite-Score/Rank-Felder aus Renderer-Datenpfaden streichen.

## Constraints

- **C1** Kein Feld, keine Anzeige, kein Sortierlauf für Composite-Score oder Rang — in App-Screens UND Renderern (Email/Telegram/SMS).
- **C2** Übersichtstabelle: Orte = Spalten, Metriken = Zeilen. Kanal-Cap gilt für **Ort-Spalten**: Telegram `1 (Metrik-Label) + N Orte ≤ 8`. Editor zeigt die Rechnung live („5 Orte + Label = 6 Spalten · passt").
- **C3** Wert im Idealbereich (`corridor`) → Markierung (grün/fett). Kein Aggregat, keine Zeilen-/Spalten-Sortierung danach.
- **C4** SMS: flacher Fließtext ≤ 140 Zeichen, alle Orte nacheinander in User-Reihenfolge, ohne Rangfolge-Kennzeichen.
- **C5** Ort-Reihenfolge (`locationIds`) = Spalten-Reihenfolge in allen Kanälen (drag-to-sort im Hub, Tab „Orte").
- **C6** Vergleich hat kein Enddatum. Lifecycle: draft → active ⇄ paused → archived (manuell). Kein Auto-Archiv.
- **C7** Versand in User-Sprache: editierbare **Briefing-Uhrzeiten**, „Morgen-Briefing = heute · Abend-Briefing = morgen" — nie „+48 h"/„Horizont"/„rollierendes Zeitfenster".
- **C8** Idealwerte existieren NUR am Vergleich, nicht am Trip (PO/Tech-Lead 2026-07-11 — Trips haben Alerts).

## Betroffene Copy (alt → neu)

| Stelle | Alt | Neu |
|---|---|---|
| Liste Intro | „…eine Empfehlung mitliefern (heute ist Ort X am besten)" | „Stehende Monitore … Werte nebeneinander, ohne Ranking — du entscheidest selbst." |
| Hub · Orte | „Reihenfolge = Ranking-Tiebreak" | „Reihenfolge = Spalten im Briefing" |
| Hub · Idealwerte | „X Metriken bestimmen das Ranking" | „X Metriken mit Idealbereich — im Briefing pro Wert markiert. Kein Score, kein Ranking." |
| Hub · Versand | „Rhythmus & Vorausschau" · „Vorausschau-Horizont" | „Briefing-Zeiten" · editierbare Uhrzeiten (Morgen=heute · Abend=morgen) |
| Editor · Idealwerte | „Diese Werte definieren den täglichen Score." | „Dein Idealbereich wird im Briefing pro Wert markiert — kein Score, kein Ranking." |
| Editor · Layout | „Score (Gesamt)"-Spalte (fix) | entfällt ersatzlos |
| Editor · Versand | „Versand 06:30 · Horizont +48 h" | „Morgen-Briefing 07:00 · Abend-Briefing 18:00" (editierbar) |

## Acceptance Criteria

- [ ] `CompareSubscription` trägt `briefings[]` (editierbare Uhrzeiten, morning = heute / evening = morgen); `horizon`/`timeWindow` entfernt.
- [ ] Kein Score/Rang in: Compare-Liste, Hub (alle 6 Tabs), Editor (alle 5 Tabs), Email-/Telegram-/SMS-Renderer.
- [ ] Editor Layout-Tab zeigt Metrik-ZEILEN (an/aus + Reihenfolge) und die Ort-Spalten-Rechnung je Kanal (C2).
- [ ] Editor-Vorschau rendert transponierte neutrale Tabelle mit Idealbereich-Markierung (C3) — identische Logik Backend + Frontend (Live-Vorschau).
- [ ] Versand-Tab: Rhythmus + Zeitfenster als zwei Controls; Hinweis „kein Enddatum — läuft bis du pausierst". (Tageszeit-„bewertet"-Karte 2026-07-11 vom PO gestrichen.)
- [ ] Hub · Übersicht: Monitoring-Streifen enthält Stat „Briefings" (Uhrzeiten).
- [ ] SMS-Render ≤ 140 Zeichen, neutral (C4), Zeichen-Zähler in der Vorschau.
- [ ] Playwright: bestehende `data-testid` der Compare-Screens bleiben erhalten.

## Edge Cases

| Fall | Verhalten |
|---|---|
| Telegram: 8+ Orte gewählt | Editor warnt „zu breit — Orte reduzieren"; Renderer kappt auf 7 Orte + Label und vermerkt „+N weitere" |
| Wert = null (Metrik am Ort nicht verfügbar) | „—" rendern, nie 0; keine Idealbereich-Markierung |
| Alle Werte außerhalb Idealbereich | Tabelle normal, keine Markierung — KEINE Warnung erfinden |
| Zeitfenster-Wochentage über Wochenende hinweg (Sa→Mo) | erlaubt; Render „Sa – Mo" |
| rhythm=daily + weekday_span | valide (tägliches Update fürs kommende Fenster) |
| 1 Ort übrig (nach Löschen) | Status fällt auf draft zurück; Versand pausiert; Hub-Banner erklärt |

## Out of Scope (Folge-Issues)

- Mobile-Screens (`screen-compare-*-mobile.jsx`) — Desktop-Spec zuerst, Mobile folgt als eigenes Issue.
- Neutralisierung des V1-Fallback-Renderers `screen-compare-email.jsx` (CompareEmail) — deprecaten, sobald V2 überall rendert.
- Signal-Reste in Bodies #14/#496 (bekannte Folge-Aufgabe).
- Mehrere Zeitfenster pro Vergleich („Sa vs. So") — PO-verworfen 2026-07-11.
