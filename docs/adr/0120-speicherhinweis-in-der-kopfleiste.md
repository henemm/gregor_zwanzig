# ADR-0120: Speicherhinweis als Text in der Kopfleiste statt festes Overlay

- **Status:** Akzeptiert
- **Datum:** 2026-11-15
- **Bezug:** GitHub-Issue #2954 (Arbeitsplan #2913), Spec `docs/specs/modules/fix_2954_speicherhinweis_kopfleiste.md`, Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (Fassung 3). **Löst für den Hub ab:** die Entscheidung „fixes Overlay unten rechts, nie unsichtbar" aus #880 (`docs/specs/modules/feat_880_autosave_overlay.md`) und #2284 S2 AC-10 (Speicher-Chip vom `SubscriptionHeader` unter dem Titelblock gerendert, `docs/specs/modules/feat_2284_s2_trip_kopf.md`). Verwandt: [ADR-0110](0110-hub-kopf-und-anlege-rahmen-ein-baustein.md) (geteilter Hub-Kopf), [ADR-0111](0111-design-vorgaben-bereinigt-audit-2026-11.md) (Mockup Fassung 3 als Maßstab), [ADR-0118](0118-handy-reiter-unterstrich-und-akzent-aktion.md) (Kopfleiste).

## Kontext

Der Speicherhinweis („Gespeichert", „Speichere …", Fehler, Konflikt) schwebte seit #880 als
festes Overlay (`position: fixed`) unten rechts über dem Inhalt aller Hub-Reiter und sollte nie
unsichtbar werden. Die Messung in #2913 zeigte, dass er dort Bedienelemente verdeckt (bei 1024 px
an fast jeder Scroll-Position, bei 390 px ebenso). Das Mockup Fassung 3 (ADR-0111) zeigt den
Hinweis dagegen als schlichten Text in der Kopfleiste links vor dem Drei-Punkte-Menü.

## Entscheidung

1. **Ort:** Der Speicherhinweis (`SaveIndicator`) steht im geteilten `HubKopf` als erstes Kind
   der rechtsbündigen Aktionsgruppe (`.hub-actions`), vor Kebab und Hauptknopf — für Trip und
   Ortsvergleich gleich, auch im Vergleich-Entwurf („Setup abschließen"). Der `SubscriptionHeader`
   rendert ihn nicht mehr; kein Overlay, kein `position: fixed`. Ist die Kopfleiste schmal, steht
   der Text in eigener Zeile rechtsbündig unter Kebab und Hauptknopf, statt den Brotkrumenpfad zu
   quetschen: unter ca. 480 px Leistenbreite steht jeder Zustand in eigener Zeile, unter ca. 1020 px
   Fehler und Konflikt (Container-Abfrage `hub-leiste` auf die Leiste, nicht auf das Fenster).
2. **Form:** Inline-Text ohne Hintergrund, 12,5 px; Erfolg in `--g-good`, Fehler und Konflikt in
   `--g-danger-fg`. Nur Tokens, jeder Zustandstext ≥ 4,5:1 gegen den Kopfgrund (hell und dunkel).
3. **Erfolg:** „Gespeichert" verschwindet 5 Sekunden nach dem Speichern (JS-Timer ab `savedAt`);
   jeder neue Speichervorgang startet die Frist neu. Beim Öffnen ohne Speichern ist die Region leer.
4. **Zwischenzustände:** „nicht gespeichert" und „Speichere …" stehen, solange der Zustand gilt.
5. **Fehler/Konflikt:** dauerhaft sichtbar (beim Konflikt mit „Nochmal speichern") — bewusste
   Abweichung vom Mockup, damit ein Speicherfehler nie unbemerkt bleibt (#880 AC-4 gilt weiter).
6. **Barrierefreiheit:** Das Element ist eine stabile Region mit `aria-live="polite"`, bleibt immer
   im DOM und trägt `data-testid="save-indicator"` und `data-state` wie bisher. Die Ansage ersetzt
   die #880-Regel „nie unsichtbar".

## Verworfene Alternativen

- **Overlay behalten, nur verschieben** — verdeckt an anderer Stelle weiter Inhalt.
- **Dauerhaft sichtbares „Gespeichert"** — beim Öffnen ohne Speichern eine unwahre Aussage; das
  Mockup startet leer.
- **Ausblenden per CSS-Animation** — startet bei idle → idle nicht neu, die 5-s-Frist ließe sich
  nicht je Speichervorgang verlängern.
- **Reservierte Mindestbreite in der Kopfleiste** — kostet am Handy Platz.

## Konsequenzen

- **Positiv:** Kein Bedienelement im Inhalt wird mehr verdeckt; Trip und Ortsvergleich zeigen den
  Hinweis über einen Mount im geteilten Kopf.
- **Negativ / Preis:** Fehler und Konflikt erhöhen die Leiste unter ca. 1020 px Leistenbreite um
  ihre eigene Zeile (Text bricht in der Breite der Aktionen um), am Handy auch „Gespeichert" um
  wenige Pixel. Bei sehr langem Namen kann der inline stehende kurze Hinweis den Pfad eine Zeile
  mehr umbrechen lassen. Nach 5 s trägt nur die Region den Status.
- **Folgepflichten:** Kebab und Hauptknopf dürfen sich beim Erscheinen/Verschwinden des Hinweises
  nicht verschieben (Gruppe rechtsbündig); Farben nur über Tokens.
