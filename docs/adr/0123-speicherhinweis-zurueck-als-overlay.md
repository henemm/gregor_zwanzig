# ADR-0123: Speicherhinweis wieder als festes Overlay unten rechts

- **Status:** Akzeptiert
- **Datum:** 2026-11-17
- **Bezug:** PO-Vorgabe 2026-11-17 (Rücknahme von #2954). **Löst ab:** [ADR-0120](0120-speicherhinweis-in-der-kopfleiste.md). Es gilt wieder #880 (`docs/specs/modules/feat_880_autosave_overlay.md`) und #2284 S2 AC-10 (`docs/specs/modules/feat_2284_s2_trip_kopf.md`).

## Kontext

ADR-0120 (#2954) hatte den Speicherhinweis aus dem festen Overlay unten rechts in die Kopfleiste
links vor Kebab und Hauptknopf verlegt, weil das Overlay Bedienelemente im Inhalt verdecken
konnte. Im Gebrauch zeigte sich: Die Kopfleiste scrollt mit, beim Bearbeiten weiter unten auf der
Seite liegt sie meistens außerhalb des sichtbaren Bereichs. Der Hinweis „Gespeichert" (und vor
allem ein Speicherfehler) ist dann nicht zu sehen; zusätzlich verschwand „Gespeichert" nach 5 s.

## Entscheidung

1. Die Umsetzung von #2954 wird vollständig zurückgenommen: Der `SaveIndicator` ist wieder ein
   festes Overlay (`position: fixed`) unten rechts, gerendert vom `SubscriptionHeader`, und nie
   unsichtbar (nach Ruhe zurückgenommen, aber lesbar; Kontrastregel aus #2400 gilt weiter).
2. Der `HubKopf` rendert keinen Speicherhinweis mehr; die Container-Regeln für die Hinweiszeile
   entfallen.
3. Die Spec von #2954 und ADR-0120 bleiben als Historie stehen (Status „Abgelöst").

## Verworfene Alternativen

- **Hinweis in der Kopfleiste lassen und die Kopfleiste fixieren (sticky)** — größere Änderung am
  Seitenrahmen; der PO hat ausdrücklich die Rücknahme verlangt.
- **Overlay an anderer Ecke** — verdeckt an anderer Stelle Inhalt; nicht verlangt.

## Konsequenzen

- **Positiv:** Speicherzustand und Speicherfehler sind an jeder Scroll-Position sichtbar.
- **Negativ / Preis:** Das Overlay kann wie vor #2954 Bedienelemente unten rechts teilweise
  verdecken (Befund aus #2913); bewusst in Kauf genommen.
- **Folgepflichten:** Eine erneute Verlegung des Hinweises braucht ein neues ADR, das das
  Sichtbarkeitsproblem beim Scrollen löst.
