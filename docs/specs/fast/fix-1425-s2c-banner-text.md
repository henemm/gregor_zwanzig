# Mini-Spec: fix-1425-s2c-banner-text

**Issue:** #1425 Schritt 2 Teil 2, **Scheibe C** — der Wertebereiche-Reiter verspricht eine Wirkung, die es dort nicht gibt.

## Approval

- [x] Approved (PO, 2026-07-31)

## Problem (belegt)

Der geteilte Korridor-Editor verspricht in **beiden** Kontexten: „außerhalb = **Warnung** … Verlässt ein Wert den Bereich, bekommst du zwischen den Briefings eine **Sofort-Meldung**."

- **Kein Dienst liest `corridor.notify`** — einziger Treffer außerhalb von Tests ist der Loader-Roundtrip (`src/app/loader.py:1513`). Go persistiert nur durch (`internal/model/trip.go:74`).
- **Die Sofort-Meldung existiert aber wirklich** — nur an anderer Stelle: `display_config.metric_alert_levels` ist laut `src/services/trip_alert.py:136,297` die **einzige** Alarm-Quelle und wird tatsächlich ausgewertet. Bedient wird sie im Reiter *Alarme*, seit #1371 nicht mehr im Wertebereiche-Reiter.
- Von den zwei versprochenen Wirkungen existiert im Wertebereiche-Reiter also nur „markiert" — und die seit Scheibe A für 20 der 23 Größen.

Der Text ist damit nicht nur ungenau, er schickt Nutzer an die falsche Stelle.

## Was sich ändert

**Trip-Kontext (`context === 'route'`), Desktop + Mobil:**

| Stelle | vorher | nachher |
|---|---|---|
| Eyebrow | `Wertebereiche · Warn-Schwellen` | `Wertebereiche` |
| Überschrift | `Sag mir, wenn das Wetter aus dem Rahmen läuft` | `Sag mir, welche Werte für dich passen` |
| Lead | `… Verlässt ein Wert den Bereich, bekommst du zwischen den Briefings eine Sofort-Meldung.` | `… Werte im Bereich werden im Briefing hervorgehoben. Warnungen zwischen den Briefings stellst du im Reiter Alarme ein.` |

**Legende (beide Kontexte, Desktop + Mobil):**

| Stelle | vorher | nachher |
|---|---|---|
| Zeile 2 | `außerhalb = **Warnung**` | entfällt ersatzlos |
| Note | `Beide Wirkungen je Metrik frei kombinierbar.` | entfällt (es gibt nur eine Wirkung) |
| Zeile 1 | `im Bereich = **markiert**` | bleibt unverändert |

**Zähler unter der Tabelle:** `{markN} × Markieren` zählt heute auch gesetzte Marken auf den drei Tages-Summen mit, deren Schalter seit Scheibe A unsichtbar ist. Künftig zählt er nur Zeilen, für die `supportsMark(metric, context)` wahr ist — die Zahl entspricht dann dem, was der Nutzer sieht und was wirkt.

## Was sich NICHT ändert

- Der **Compare-Lead** ist bereits ehrlich („grün markiert — kein Score, kein Ranking, nur eine Lese-Hilfe") und bleibt wörtlich.
- **Keine Datenänderung.** `corridor.notify` wird weiter geschrieben und gelesen wie bisher — der Default (`true` im Trip, `alarmCapable && wasActive` im Vergleich) bleibt unangetastet. Begründung: Datenerhalt (#102); ein stiller, ungelesener Wert richtet keinen Schaden an, seine Änderung könnte einen späteren Leser überraschen. Als Sammel-Eintrag notiert.
- **`display_config.ideal_ranges`** (historische Zweitkopie neben `corridors[]`) bleibt unangetastet — Datenmodell-Arbeit, gehört nicht in eine Textkorrektur.
- Der Reiter *Alarme* selbst wird nicht angefasst.

## Acceptance Criteria

_Nachgetragen bei der Umsetzung (Formvorgabe AC-N). Reine Umformulierung der oben
vom PO freigegebenen Tabellen — kein zusätzlicher Umfang._

- **AC-1:** Given ein Trip-Wertebereiche-Reiter (`context === 'route'`), When der Nutzer ihn öffnet (Desktop oder Mobil), Then lautet der Eyebrow `Wertebereiche`, die Überschrift `Sag mir, welche Werte für dich passen` und der Einleitungstext endet mit `Werte im Bereich werden im Briefing hervorgehoben. Warnungen zwischen den Briefings stellst du im Reiter Alarme ein.` — von einer Sofort-Meldung ist nirgends mehr die Rede.

- **AC-2:** Given der Wertebereiche-Reiter in einem beliebigen Kontext (Trip oder Ortsvergleich, Desktop oder Mobil), When die Legende angezeigt wird, Then enthält sie nur noch `im Bereich = markiert` — die Zeile `außerhalb = Warnung` und die Note `Beide Wirkungen je Metrik frei kombinierbar.` sind ersatzlos entfallen.

- **AC-3:** Given ein Trip mit einer markierten Tages-Summe (Schalter seit Scheibe A unsichtbar) und einer markierten wirksamen Größe, When der Zähler unter der Tabelle gerendert wird, Then nennt er nur die wirksame Größe — gezählt wird ausschließlich, was `supportsMark(metric, context)` zulässt.

- **AC-4:** Given der Wertebereiche-Reiter im Ortsvergleich (`context === 'vergleich'`), When er geöffnet wird, Then sind Eyebrow, Überschrift und Einleitungstext wörtlich unverändert und der Zähler zählt weiterhin jede markierte Größe.

- **AC-5:** Given ein gespeicherter Trip bzw. Ortsvergleich, When der Reiter geöffnet und wieder gespeichert wird, Then bleiben `corridor.notify` und `display_config.ideal_ranges` unverändert erhalten (reine Textkorrektur, keine Datenänderung).

## Manuelle Test-Schritte

1. Trip öffnen → Reiter *Wertebereiche*: Überschrift und Einleitungstext versprechen keine Sofort-Meldung mehr und verweisen auf den Reiter *Alarme*.
2. Legende zeigt nur noch „im Bereich = markiert", keine Warn-Zeile.
3. Ortsvergleich öffnen → Reiter *Wertebereiche*: Einleitungstext unverändert, Legende ebenfalls ohne Warn-Zeile.
4. Schmaler Viewport (390px): beide Punkte gelten auch mobil.
5. Trip mit einer markierten Tages-Summe (z. B. Sonnenstunden) und einer markierten wirksamen Größe: Der Zähler nennt nur die wirksame.

## Inline-Test (wird während der Umsetzung geschrieben)

- [ ] Ein Test hält fest, dass der Editor in keinem Kontext eine Sofort-Meldung oder eine „außerhalb = Warnung"-Wirkung behauptet — und dass der Trip-Text auf den Reiter *Alarme* verweist. Damit fällt ein künftiges Wiedereinführen des Versprechens auf, solange `corridor.notify` keinen Leser hat.
- [ ] Ein Test hält fest, dass der Markieren-Zähler nur zählt, was `supportsMark` zulässt.
