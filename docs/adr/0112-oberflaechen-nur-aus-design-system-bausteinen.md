# ADR-0112: Oberflächen entstehen nur aus Design-System-Bausteinen und Tokens — ein Wächter blockt Verstöße beim Merge

- **Status:** Akzeptiert (PO 2026-11-10, Freigabe Spec `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md`)
- **Datum:** 2026-11-10
- **Bezug:** Issue #2913 (Neustart „Einstellungen neu“, Epic #2791); ergänzt ADR-0111 (Design-Vorgaben bereinigt, Design-Gate außer Dienst) und ADR-0109/0110; macht AP-006, AP-007 und AP-008 in `docs/design-system/ANTI-PATTERNS.md` zur Pflicht mit Wächter.

## Kontext

Es gab keine verbindliche Regel, dass Seiten nur aus Design-System-Bausteinen gebaut werden. Die Folge zeigt die Bestandsaufnahme zu Issue #2913: In den Reitern des Hubs liegt der Anteil der Bausteine aus `atoms/molecules/organisms` praktisch bei null. Jede Seite stylt lokal (eigenes `<style>`, `style=`, Tailwind-Klassen, rohe `<button>`), auch die Bausteine selbst enthalten harte Pixel- und Farbwerte. Die Anti-Patterns AP-006 bis AP-008 standen als Empfehlung im Katalog, aber nichts hat sie durchgesetzt; das Design-Gate (`pre_issue_close_design_gate.py`) ist seit ADR-0111 außer Dienst, weil es mit Soll-Bildern maß.

Vor dem Neubau der Seite „Einstellungen neu“ (Scheiben a bis e) braucht es deshalb erst die Regel und einen Wächter, der sie beim Merge erzwingt.

## Entscheidung

1. **Nur Bausteine:** Jede Oberfläche entsteht ausschließlich aus Bausteinen in `frontend/src/lib/components/atoms`, `molecules` und `organisms` (bzw. ausdrücklich freigegebenen Kompositionen). Seiten und Reiter setzen Bausteine zusammen; sie stylen nicht selbst.
2. **Fehlt ein Baustein, wird er zuerst im Design-System gebaut** — nie in der Seite. Ein fehlender Baustein ist ein eigener Arbeitsschritt (eigene Spec bzw. eigener Folge-Workflow), danach nutzt ihn die Seite.
3. **Nur Tokens:** Kein Styling außerhalb der Tokens. Farbe, Abstand, Größe, Radius, Schrift und Schatten laufen über `var(--g-*)`; erlaubt sind daneben `0`, 1-px-Rahmen, `%`, `fr`, `auto`, Viewport-Einheiten und `calc()/min()/max()` über Tokens.
4. **Ein Wächter blockt Verstöße beim Merge:** `frontend/src/lib/__tests__/bausteine_waechter.test.ts` (Regeln in `bausteine_waechter_regeln.ts`) läuft im CI-Job `frontend-test`, der für den Merge grün sein muss. Er prüft:
   - **Regel (a) Aufbau** für alle Dateien in `SEITEN_SCOPE` (Opt-in; jede Scheibe trägt ihre neuen Seiten ein): kein `<style>`, kein `style=` und keine `style:`-Direktive, keine Tailwind-Utility-Klassen (statisch, im Ausdruck, per `class:`-Direktive, auch auf Komponenten), keine rohen `<button>`, `<input>`, `<select>`, `<textarea>`, `<table>`, Komponenten-Importe nur aus den drei Baustein-Ordnern. Geprüft wird über den Svelte-AST (`svelte/compiler`).
   - **Regel (b) Tokens** für alle Dateien in den Baustein-Ordnern: `<style>`, `style=`, `style:`-Direktiven und Tailwind-Arbitrary-Werte nur über Tokens. Die Ratsche `AUSNAHMEN` hält den Ist-Stand je Bestandsdatei fest und darf nur sinken; neue Baustein-Dateien starten bei 0.
   - **Neue-Datei-Regel:** Jede `.svelte` unter `routes/` oder `lib/components/**` außerhalb der Baustein-Ordner steht in `SEITEN_SCOPE` oder in der Bestandsliste `BESTAND`. Die Bestandsliste hat eine feste Obergrenze und darf nur sinken; neue Dateien gehen in `SEITEN_SCOPE` und damit unter Regel (a).
   - Ausnahme nur mit `audit:exempt` und Begründung in derselben Zeile oder der Zeile davor; ohne Begründung bleibt der Wächter rot.

Der Bestand wird nicht nachträglich umgebaut: Der Wächter startet als Ratsche und bricht keine heutige Seite.

## Regel-Budget

Der Wächter ersetzt das seit ADR-0111 außer Dienst gestellte Design-Gate (keine zusätzliche Pflicht-Regel). **Prüfdatum 2027-02-08.** **Löschbedingung (Rückbau):** Gibt es bis dahin keinen nachweisbaren Fang (kein Merge, den der Wächter mit einem echten Verstoß aufgehalten hat, und keine Scheibe, die durch ihn einen fehlenden Baustein zuerst ins System gebracht hat), wird er zurückgebaut oder mit neuem Prüfdatum begründet verlängert.

## Konsequenzen

- Jede Scheibe von „Einstellungen neu“ trägt ihre neuen Seiten-/Reiter-Dateien in `SEITEN_SCOPE` ein; fehlende Bausteine (z. B. Ampel-Tokens `--g-ampel-*`, Metrik-Zeile, Vorlage-Karte, Kanal-Tabelle) entstehen vorher in einem eigenen Bausteine-Workflow.
- Wird eine Bestandsdatei bereinigt, sinkt ihr `AUSNAHMEN`-Eintrag bzw. fällt sie aus `BESTAND`; ein höherer Ist-Stand oder eine neue, nicht erfasste Datei macht den Merge rot.
- Ergänzend zur Code-Regel gibt es die Elementliste aus dem Mockup (`docs/context/einstellungen_neu/elementliste.json`, Staging-Abgleich) und den Prüf-Agenten `mockup-bildpruefer`: „fertig“ heißt „Elementliste lückenlos und Prüf-Agent ohne Befund“, nicht nur „Tests grün“.
- Bekannte Restlücken des Wächters (dokumentiert in `docs/reference/gates_und_ratschen.md`): Klassen und Spreads aus reinen Variablen ohne String-Literal, dynamische Komponenten (`<svelte:component>`, Komponente aus einer Variablen), dynamische `import()`, Komponenten aus npm-Paketen und unitlose Zahlen (Schriftgewicht, Zeilenhöhe) erkennt er nicht; die Tailwind-Erkennung arbeitet über eine Präfixliste, Farbnamen über eine feste Liste. Geschlossen sind `<svelte:element>`, `<style>` in `<svelte:head>`, `{@html}`, Spread mit `class`/`style`, Pfad-Tricks mit `..`, Barrel-Importe und Importe im `<script module>`.

## Verworfene Alternativen

- **Nur Doku-Regel (Anti-Patterns ohne Wächter):** so war es bisher; der Atomic-Anteil blieb bei null.
- **Wächter sofort für alle Seiten:** würde den gesamten Bestand rot machen und einen Großumbau erzwingen, den die Spec ausdrücklich nicht will. Opt-in plus Ratsche bricht nichts und lässt keinen neuen Verstoß durch.
- **Soll-Bild-Vergleich (altes Design-Gate):** misst Pixel statt Aufbau, wurde mit ADR-0111 aus gutem Grund außer Dienst gestellt.
