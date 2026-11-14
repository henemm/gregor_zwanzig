# ADR-0118: Handy-Reiter als Text-Reiter mit Unterstrich, „Test schicken ▾“ als Akzent-Hauptaktion, Kennzahlenzeile am Handy entfällt

- **Status:** Akzeptiert
- **Datum:** 2026-11-13
- **Bezug:** GitHub-Issue #2980 (Fix-Loop Bildabgleich Runde 1 der Scheibe c2, Arbeitsplan #2913, Epic #2791), Spec `docs/specs/modules/feat_2913_c2_seitenkopf.md` (AC-16 bis AC-31), Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (Z. 34–71, 228–245); PO-Entscheidungen vom 13.11.2026. **Löst teilweise ab:** [ADR-0109](0109-reiterstruktur-wetter-zustellung.md) (Punkt 7, Satz „Mobil bleibt die freigegebene Pill-Leiste“), [ADR-0110](0110-hub-kopf-und-anlege-rahmen-ein-baustein.md) (Punkt 2 „Hauptaktion = Ink“ für den Knopf „Test schicken ▾“, Punkt 3 Zurück-Pfeil mobil und Kürzel im Breadcrumb, Punkt 6 Mobil-Kennzahl-Kacheln), [ADR-0111](0111-design-vorgaben-bereinigt-audit-2026-11.md) (Punkt 1 „Am Handy bleibt die Pill-Leiste“ und inaktiver Reiter `--g-ink`, Punkt 3 „Handy Pillen“, Punkt 6 „Hauptaktion Ink“ für diesen Knopf). Verwandt: ADR-0097 (Teilung Trip/Vergleich), ADR-0112 (nur Bausteine und Tokens), #2879 (Accent als Fläche unter Text = `--g-accent-deep`).

## Kontext

Der `mockup-bildpruefer` fand nach der ersten Umsetzung der Scheibe c2 acht optische Abweichungen zwischen dem angenommenen Mockup (Fassung 3) und Staging. Drei davon stehen im Widerspruch zu bestehenden ADRs:

- **Handy-Reiter:** Das Mockup zeigt auf allen Breiten Text-Reiter mit Unterstrich. ADR-0109 Punkt 7 und ADR-0111 Punkte 1 und 3 hielten am Handy die Pill-Leiste fest (aktiver Reiter als gefüllte Pille).
- **Hauptaktion:** Das Mockup zeigt „Test schicken ▾“ als orangen Akzent-Knopf (`.btn.accent`, Fläche `#c45a2a`, weiße Schrift). ADR-0110 Punkt 2 und ADR-0111 Punkt 6 legen „Hauptaktion = Ink“ fest. Weiß auf `#c45a2a` erreicht nur etwa 4,3:1 und verfehlt WCAG-AA (4,5:1 für kleinen Text).
- **Kennzahlenzeile:** Am Handy zeigte der Trip-Kopf seit #416 die Zeile „Etappe · Briefing · Start in“. Das Mockup kennt sie nicht; ADR-0110 Punkt 6 zählte sie zu den fachlich verschiedenen Teilen des Trips.

Der PO hat am 13.11.2026 entschieden: Handy-Reiterleiste wie im Mockup, Kennzahlenzeile am Handy entfällt.

## Entscheidung

1. **Handy-Reiter sind Text-Reiter mit Unterstrich, keine Pillen.** `MTabBar` sieht am Handy aus wie am Computer: inaktiv `--g-ink-3` mit Gewicht 500, aktiv `--g-ink` mit Gewicht 600 und 2-px-Unterstrich in `--g-accent`, darunter eine durchgehende Grundlinie `--g-rule`. Am Handy bleiben das wischbare Band (Scroll-Snap, Fade), die Tippfläche von mindestens 44 px (#2284) und das Einscrollen des aktiven Reiters. Gilt für Trip und Ortsvergleich (ein Baustein, ADR-0097).
2. **„Test schicken ▾“ ist die Akzent-Hauptaktion (`Btn variant="accent"`) mit Fläche `--g-accent-deep`.** Nicht das Mockup-Orange `--g-accent`: helle Schrift auf `--g-accent-deep` erreicht im Hellmodus etwa 7,4:1 und im Dunkelmodus (dunkle Schrift auf hellem Akzent) ebenfalls mehr als 4,5:1, also WCAG-AA (Design-Leitprinzip „hoher Kontrast gewinnt“, PO-bestätigt 2026-05-25, #2879). Die Farbabweichung zum Mockup ist bewusst, in der Ausnahmenliste des Abgleichs (`elementliste_besitzer.json`, Liste `ausnahmen`) vermerkt und im Soll/Ist-Bild für den PO offen genannt. Andere Hauptaktionen (z. B. „Setup abschließen“, Anlege-Rahmen) bleiben bei ADR-0110.
3. **Die Kennzahlenzeile #416 am Handy entfällt.** Der Trip-Kopf zeigt am Handy keine Zeile „Etappe · Briefing · Start in“ mehr; die Meta-Zeile (Datum, Etappen, km, ↑m) bleibt auf allen Breiten. Die Anforderung aus #416 ist damit abgelöst.

Im selben Fix-Loop folgen aus dem Mockup ohne Widerspruch zu einem ADR: Kopfband Mono 11 px in Großschrift (nur per CSS) mit vollem Namen statt Kürzel und ohne Zurück-Pfeil (Elternteil des Breadcrumbs ist der Weg zur Liste), Kebab als Ghost-Knopf mit Rahmen `--g-rule`, Meta-Zeile Mono 13 px `--g-ink-3`, Status-Pill gefüllt ohne Rahmen (aktiv grün, sonst neutral), Vorlage-Karte und Abschnittskopf Wetter nach Mockup-Maßen.

## Abgelehnte Alternativen

- **Handy-Pillen behalten:** widerspricht der PO-Entscheidung vom 13.11.2026 und dem angenommenen Mockup; zwei Optiken für dieselbe Leiste.
- **Knopf im Mockup-Orange `--g-accent`:** verfehlt WCAG-AA (etwa 4,3:1).
- **Knopf weiter in Ink:** weicht sichtbar vom Mockup ab, obwohl es eine AA-konforme Akzent-Fläche gibt.
- **Kennzahlenzeile am Handy behalten:** vom PO verworfen; das Mockup kennt sie nicht.

## Konsequenzen

- **Positiv:** Hub-Kopf und Reiterleiste entsprechen auf allen Breiten dem Mockup; ein Aussehen für Trip und Ortsvergleich; Kontrast bleibt AA.
- **Negativ / Preis:** Bestandstests auf Pillen, Ink-Knopf, Zurück-Pfeil und Kennzahlenzeile werden auf das neue Soll gezogen bzw. entfernt (`TripHeader.mobile-metrics.test.ts`). Die Pillen-AC der Spec `docs/specs/modules/mobile_tab_leisten_mtabbar.md` ist überholt.
- **Prüfung:** Komponenten-Tests mit aufgelösten Tokens (`frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_bildabgleich.test.ts`), Staging-Aufnahmen `frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts`, Bildprüfer Runde 2.
