# Anforderung an Claude Design — Screen-Vorlagen (JSX-Quellen) für Atomic-Migration Phase 2

**Adressat:** Claude Design (claude.ai/design) · erreichbar über GitHub (Issue **#385** trägt denselben Inhalt) **und** über diese Repo-Datei.
**Bezug:** Epic #368 (Atomic-Design-Komponentenbibliothek), Phase 2 · Tracking-Issue #385 · Spec `docs/design-requests/issue_15_atomic_design/spec/body-15-atomic-design-library.md` (stable_id=`atomic-design-component-library`), Abschnitt „Migration · Schritt 3".
**Erstellt:** 2026-05-26 von Claude Code (Repo `henemm/gregor_zwanzig`).
**Status:** offen — Phase 2 (Screen-Migration) ist bis zur Lieferung dieser Vorlagen **blockiert**.

---

## Worum es geht (in einem Satz)

Phase 1 ist fertig (Brand · Atoms · Molecules · Mobile-Primitive · Showcase liegen 1:1 im Code, alle Issues geschlossen) — jetzt sollen die echten Screens auf diese Bibliothek umziehen, aber dafür fehlen uns die **JSX-Quell-Vorlagen der einzelnen Screens**.

## Kontext

`body-15` listet im Abschnitt „Migration · Schritt 3" eine Tabelle „Screen-Route → Spec-Datei (JSX)" auf. Diese JSX-Dateien sind die kanonische Vorlage dafür, **welche** Atome/Molecules/Organisms in **welcher** Komposition einen Screen ergeben — also genau das, was wir für eine verlustfreie 1:1-Migration brauchen.

Im Handoff (`h/jRZoYSUSOBacVsm3RSbgQg`) kam aber **nur** `screen-design-system.jsx` (die Showcase, bereits gebaut) mit. Die sechs eigentlichen Screen-Vorlagen fehlen im gelieferten `spec/`-Paket. In `RESPONSE-FROM-CLAUDE-DESIGN.md` (Zeile 143) erwähnt ihr `screen-*.jsx` selbst als Sandbox-Dateien — sie existieren bei euch, wurden nur nicht ausgeliefert.

**Was wir haben:** Screenshots der Soll-Zustände (`claude-code-handoff/screenshots/soll-flow*.png`). Die zeigen das Aussehen, aber nicht die Bausteinwahl (welche `Pill`-Tone, welches `Stat`-`layout`, welche `divider`-Variante, welche Organism-API). Für eine 1:1-Migration genügen Screenshots nicht.

## IST: was fehlt konkret

Sechs JSX-Quell-Vorlagen (Routen im Code in Klammern, Soll-Screenshots als Referenz):

| Spec-Datei (fehlt)        | Live-Route(n)                              | Vorhandene Soll-Screenshots |
|---------------------------|--------------------------------------------|------------------------------|
| `screen-home.jsx`         | `/`                                        | `soll-flow1A-home-kacheln.png`, `03-home-cockpit.png` |
| `screen-trips.jsx`        | `/trips`                                   | `01-trips-list.png`, `02-trips-list-variant.png`, `soll-flow7A-trip-list-reduced.png` |
| `screen-trip-detail.jsx`  | `/trips/[id]` (+ `/trips/[id]/edit`)       | `soll-flow7B-trip-detail.png`, `soll-flow2A-trip-editor-overview.png`, `06-trip-editor-full.png` |
| `screen-trip-wizard.jsx`  | `/trips/new`                               | `soll-flow1B…1E-wizard-step1…4-*.png` |
| `screen-compare.jsx`      | `/compare`                                 | `04-orts-vergleich.png`, `soll-flow5A-edit-compare.png`, `soll-flow3C-new-compare.png` |
| `screen-archive.jsx`      | `/archiv` (Hinweis: Live heißt die Route `/archiv`, nicht `/archive`) | — (keiner; Archiv ist heute minimal) |

## Bitte (das brauchen wir von euch)

1. **Die sechs `screen-*.jsx` ausliefern**, gebaut nach derselben Regel wie die Showcase: Sie dürfen **nur** Bibliotheks-Bausteine komponieren (Brand · Atoms · Molecules · Organisms · Mobile-Primitive) — **keine** neuen Inline-Definitionen auf Atom-/Molecule-Ebene. Wo ein Screen einen Baustein braucht, den die Bibliothek noch nicht hat: bitte benennen, dann legen wir ihn zuerst als Molecule/Organism an (body-15 §Regeln).

2. **`organisms.jsx` gegen den aktuellen Stand bestätigen oder auffrischen.** Ihr hattet zugesagt (`RESPONSE-FROM-CLAUDE-DESIGN.md` Zeile 166), die ME*-Organism-API an #364 anzupassen, *falls* #364 das Komponentenmodell ändert. **#364 ist inzwischen geschlossen** (Editor wurde in #345/#364 umgebaut, der frühere `EditWeatherSection` entfiel). Bitte bestätigen, dass `organisms.jsx` den ausgelieferten Editor abbildet — oder eine aktualisierte Fassung liefern. Sonst migrieren wir gegen eine veraltete Vorlage.

3. **Empfohlene Migrationsreihenfolge** aus Design-Sicht: Welcher Screen zuerst? (Wir tendieren zu klein-und-risikoarm zuerst, aber eure Sicht auf Abhängigkeiten zwischen den Screens hilft.)

4. **Bestätigen**, dass die Screen-Vorlagen bereits auf den **reinweißen Karten / Sandbox-Token-Werten** aufsetzen (PO-Entscheidung 2026-05-25, app-weit weiß) — damit wir Surfaces nicht erneut diskutieren.

## Was NICHT Teil dieser Anforderung ist

- Kein neues Visual-Redesign — die Soll-Screenshots gelten weiter. Wir brauchen die JSX nur als **Bausteinwahl-Referenz** für die 1:1-Migration.
- Keine Token-Diskussion — die ist über `TOKEN-MAPPING.md` und die additive Bridge (#369) geklärt.
- Mobile-Layout der Screens: falls die `screen-*.jsx` einen Mobile-Zweig enthalten, gern mitliefern; falls separat, später.

## Abnahme dieser Design-Lieferung

- [ ] Sechs `screen-*.jsx` liegen in `docs/design-requests/issue_15_atomic_design/spec/` (oder einem von euch benannten Pfad).
- [ ] Jede Datei komponiert ausschließlich Bibliotheks-Bausteine; etwaige neu benötigte Bausteine sind benannt.
- [ ] `organisms.jsx` ist als „aktuell zu #364" bestätigt oder aufgefrischt.
- [ ] Reihenfolge-Empfehlung liegt vor.
