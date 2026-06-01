# CLAUDE.md · Projekt-Memory für Gregor Zwanzig

Persistente Hinweise für jedes Chat in diesem Projekt. Lies das erst, bevor du
ans Werk gehst — die Lessons sind aus realen Handoff-Iterationen entstanden.

---

## Produkt-Grundverständnis (zuerst lesen, NIE vergessen)

**Wofür die Webseite da ist:** `gregor.zwanzig` ist ein **Vorab-Einrichtungs-
und Monitoring-Werkzeug** — KEIN tägliches Lese-Medium. Der User richtet Trips
und Orts-Vergleiche **vor** der Reise ein. Während der Reise konsumiert er die
Briefings in seinen **Messaging-Kanälen** (Email · Signal · Telegram · SMS),
nicht im Browser.

Belegt durch die eigene Wizard-Copy (`screen-compare-wizard.jsx`):
> „Die Webseite musst du im Urlaub nicht öffnen — alles kommt automatisch in
> dein Postfach."

Konsequenzen, die DARAUS folgen (gegen die ich schon mehrfach verstoßen habe):
- Die **Startseite** ist ein **Cockpit/Status** („Was geht raus", Alerts,
  aktiver Trip) — NICHT der Briefing-Reader.
- Ein Klick auf eine Liste/Kachel öffnet das **Setup/Detail** des Items
  (was konfiguriert ist + Aktionen), NICHT „die heutige Antwort im Browser".
- Die **Briefing-Vorschau** ist ein **Verifikations-Tool innerhalb des Setups**
  („sieht meine Mail richtig aus?"), kein Konsum-Surface und kein Klick-Ziel.
- Bei jeder Feature-Frage zuerst prüfen: dient das dem **Einrichten/Überwachen**
  (gehört in die App) oder dem **täglichen Lesen** (gehört in die Kanäle)?

---

## Arbeitsmodus

**Gregor ist Product Owner, nicht Tech Lead.** Wenn eine technische,
architekturelle oder Design-System-Entscheidung gefragt ist, agiere als
**Tech Lead** — entscheide selbst und begründe.

**Immer Empfehlung mitliefern.** Bei jeder Frage, jeder Option, jedem
Vergleich: nicht nur Optionen auflisten, sondern eine **konkrete Empfehlung**
aussprechen und begründen. Auch bei trivialen Entscheidungen. Wenn der PO
nicht widerspricht, gilt die Empfehlung. Optionen-ohne-Empfehlung ist
Workload-Verschiebung nach oben und unerwünscht.

---

## Design-Leitprinzipien (PO-bestätigt)

**Hoher Kontrast = Lesbarkeit.** Bei jedem Konflikt zwischen „weicher
Optik" / „warmer Atmosphäre" und „klarer Lesbarkeit von Inhalt" gewinnt
**Lesbarkeit**. Begründung des PO (2026-05-25): das Produkt ist ein
Briefing-Werkzeug für Wetter- und Trip-Entscheidungen — Inhalt muss in jeder
Lichtsituation und unter Zeitdruck verlässlich lesbar sein.

Konkrete Konsequenzen, die daraus folgen:
- **Cards = weiß** (`--g-card #ffffff`) auf warmer Off-White-Page
  (`--g-paper #f6f4ee`). Kein beiges Card-on-beige.
- **Text-Kontrast:** für echten Text mindestens WCAG-AA (4.5:1). `--g-ink-4`
  ist strikt für Placeholder/Disabled, nicht für Captions.
- **Akzent-Farben sparsam einsetzen** und nie als alleinigen Lesbarkeits-
  Träger — Form + Position + Mono-Strecke tragen mit.

Bei neuen Mockups: dieses Prinzip steht über ästhetischen Präferenzen.

---

## Claude-Code-Handoff-Workflow

Dieses Projekt liefert Design-Mockups an Claude Code aus. Das Handoff-Paket
liegt in `claude-code-handoff/` und enthält Issue-Bodies, Screenshots,
`issues.json`, `INSTRUCTIONS.md`, `PROMPT-FUER-CLAUDE-CODE.txt` und
`MANIFEST.txt`.

### Regeln beim Erweitern eines Handoffs

1. **Manifest IMMER als letzter Bau-Schritt regenerieren.**
   Insbesondere NACH jeder Bild-Komprimierung, NACH dem Schreiben der
   `MANIFEST.txt` und `check-manifest.sh` selbst. Sonst schlägt der eigene
   Integritäts-Check bei intaktem Paket fehl und trainiert den Empfänger,
   die Warnung zu ignorieren ("Schade-um-die-gute-Idee-Effekt").

   Reihenfolge: alle Inhalts-Änderungen → Bilder optimieren →
   `MANIFEST.txt` neu generieren.

2. **Stable-ID-Marker beibehalten.** Jeder Issue-Body beginnt mit
   `<!-- gregor-zwanzig-handoff: stable_id=<slug> -->`. Claude Code
   dedupliziert über `gh issue list --search "in:body gregor-zwanzig-handoff:
   stable_id=$id"`. Pattern hat sich in der Praxis bewährt — nicht ändern.

   Hinweis: Bei bestehenden GitHub-Issues ohne Marker muss der User die
   Marker händisch in offene Issues nachtragen. Geschlossene Issues ohne
   Marker sind unkritisch (Claude Code wertet sie korrekt als SKIP).

3. **Beim Hinzufügen eines Issues alle Verweise mitziehen**:
   - Count in `INSTRUCTIONS.md` (mehrere Stellen)
   - Label-Liste in `INSTRUCTIONS.md` (Step 3) — neue `area:`-Labels
     ergänzen, sonst schlägt `gh issue create` mit HTTP 422 fehl
   - `PROMPT-FUER-CLAUDE-CODE.txt`
   - Entry in `issues.json` mit `stable_id` und `status`
     (`"new"` oder `"existing-or-update"`)
   - Marker in den neuen Body-File einfügen
   - Veraltete "Fang mit X an"-Empfehlungen prüfen und ggf. entfernen

4. **Screenshot-URL-Konvention** ist
   `https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/<slug>.png`.
   Hat sich bewährt — User kann Bilder austauschen ohne Issues anzufassen.

5. **Status-Feld in `issues.json`**:
   - `"new"` — garantiert noch nicht auf GitHub
   - `"existing-or-update"` — wahrscheinlich schon angelegt; Claude Code
     dedupliziert via Marker

6. **Vor jedem neuen Handoff den GitHub-Stand prüfen.** Sandbox-Snapshots
   können „Issue #X gibt es noch nicht“ annehmen, obwohl Claude Code es
   im Repo schon längst angelegt oder als Epic-Untergliederung umgesetzt
   hat (gesehen Mai 2026: Issue #15 Atomic-Design existierte bereits als
   Epic #368 mit Unter-Issues #369–#374, davon zwei in Produktion).
   Konkret bedeutet das:
   - Vor dem Schreiben eines `body-XX.md` als `status: "new"`: per
     `gh issue list --search "in:body gregor-zwanzig-handoff: stable_id=<id>"`
     prüfen, ob es schon existiert. Falls ja → `status: "existing-or-update"`.
   - Bei thematischen Überlappungen (z. B. „Atomic Design“) auch ohne
     gleichen `stable_id` nach laufenden Epics suchen
     (`gh issue list --label epic`, `gh issue list --search "Atomic"`).
   - Wenn unklar → den User fragen, **bevor** ein redundantes Issue
     ins Handoff-Paket landet. Doppelte Issues stehlen Claude Code Zeit
     beim Dedupe und stiften Verwirrung.

### Beim Erstellen eines neuen Issues — Backend/Frontend-Architektur

Wenn das Issue (wie `body-14-output-layout-system.md`) eine
System-Architektur beschreibt, gehört in den Body:

- Datenmodell (TypeScript- oder Python-ähnliche Struktur)
- Algorithmus-Pseudocode für Renderer/Logik
- API-Endpoints
- Constraints C1, C2, … (nummeriert, validierbar)
- Heuristik-Defaults (z. B. `METRIC_PRIORITY`)
- Migration für Bestands-Daten
- Acceptance Criteria als Checkliste
- Edge Cases als Tabelle
- "Out of Scope" für Folge-Issues
- Identische Logik in Backend + Frontend dokumentieren (Live-Vorschau)

---

## Design-System

- Tokens: `tokens.css` (CSS-Variablen, drop-in für SvelteKit `app.css`)
- Schrift: Inter Tight + JetBrains Mono
- Akzent: Burnt Orange `#c45a2a`
- **Brand-Grundgesetz**: `brand-kit.jsx` — Wordmark (Lockup: Berg+Blitz-Glyph + Mono-lowercase »gregor · zwanzig«), Sidebar, UserBadge. Single-Source-of-Truth.
- Atoms: `atoms.jsx`
- Molecules: `molecules.jsx` *(in Migration — siehe `docs/atomic-design-inventory.md`)*
- Organisms: `organisms.jsx` *(in Migration)*
- Mobile-Bezel + Mobile-Atoms: `mobile-shell.jsx`
- Hauptcanvas: `Gregor 20 - Komponenten.html`
- Komponenten-Showcase: `screen-design-system.jsx`

## Atomic-Design-Disziplin

Vor JEDER neuen UI-Arbeit:

1. Lies `brand-kit.jsx`, `atoms.jsx`, `molecules.jsx`, `organisms.jsx`
   und (falls Mobile) `mobile-shell.jsx` vollständig.
2. Existiert das Element bereits → verwende es. **Keine Inline-Variante.**
3. Existiert es nicht → erst dort hinzufügen, dann verwenden.
4. Brauchst du eine Variante, die das Atom nicht abdeckt → **FRAGE** den User,
   ob das eine neue Prop wird oder eine bewusste Ausnahme.

**Naming-Konvention:**
- Atoms / Molecules / Organisms / Templates: sprechender Name, kein Prefix
- Brand-only:   `Brand*`  (BrandWordmark, BrandIcon, BrandSidebar)
- Mobile-only:  `M*`      (MBtn, MInput, MField, MSwitch)
- Templates:    `*Shell` oder `*Layout`

**Konflikt-Regel:** Bei Widerspruch gewinnt `brand-kit.jsx` (Grundgesetz). Dann `atoms.jsx`. Pages dürfen die Hierarchie niemals umkehren.

**Handoff-Spiegel:** Die Mobile-Dateien (`mobile-shell.jsx`, `screen-*-mobile.jsx`, `tokens.css`) im Projekt-Root sind **kanonisch**. Der Ordner `gregor-zwanzig-mobile/project/` ist der Handoff-Spiegel und MUSS vor jeder Übergabe an `gregor_zwanzig`-Repo mit den Wurzel-Versionen synchronisiert werden. Wenn du eine der Wurzel-Mobile-Dateien änderst, ziehe die Kopie im Handoff-Ordner mit (oder vermerke explizit, dass der Sync noch aussteht).

**Inventur-Referenz:** `docs/atomic-design-inventory.md` enthält den vollen Komponenten-Katalog, die Drift-Historie und die Migrations-Reihenfolge. Bei Unsicherheit dort nachschlagen, bevor du etwas Neues erfindest.

**Babel-Scope-Falle (wichtig!):** In `<script type="text/babel">` werden top-level `function X() {…}` zu `window.X`. Lokale Helper-Komponenten in einer `screen-*.jsx` mit demselben Namen wie ein Atom/Molecule/Organism **überschreiben** die kanonische Version global — und zwar im Lade-Reihenfolge-Sieger-Prinzip (die später geladene Datei gewinnt). Konsequenz:

- Lokale Helpers in Pages MÜSSEN Page-Prefix tragen: `WizardField`, `HomeStagePill`, `EditorIconArrow` etc.
- Vor jeder neuen Komponenten-Definition: prüfen, ob der Name in `brand-kit.jsx`, `atoms.jsx`, `molecules.jsx`, `organisms.jsx` schon existiert.
- Babel-`<script>`-Tags scopen NICHT wie ES-Modules.

**Babel-String-Falle (Unicode-Quotes):** Verschachtelte deutsche Anführungszeichen `„…"` innerhalb von JS-String-Literalen mit ASCII-`"` zerlegen den Babel-Parser stillschweigend zur Build-Zeit — `desc: "z.B. „11 °C"` kollidiert, weil Babel das schließende `"` vor `11` als String-Ende sieht und alles dahinter als Code wertet. Symptom: hartnäckiger `SyntaxError: Unexpected token` in Zeilen, die korrekt aussehen.

- Verschachtelte Quotes IMMER in Backticks setzen: `` desc: `z.B. „11 °C"` ``
- Oder konsistent eine Quote-Sorte: `desc: 'z.B. „11 °C"'`
- Faustregel: wenn die UI-Strings deutsche Druckanführungszeichen enthalten, niemals den umschließenden String mit `"` öffnen.

## User-Sprache (kein Fach-Slang in der UI)

Lernfest in mehreren Iterationen:

| Schlecht (Fach)          | Gut (User-Sprache)              |
|--------------------------|---------------------------------|
| Monospace-Tabelle        | Tabelle                         |
| Prosa-Zeile / Mono-Block | Detail / Detail-Zeile           |
| Bucket: primary/secondary/off | Spalte / Detail / Aus      |

## Output-Layout-System (Spalten / Detail / Aus + Kanal-Constraints)

Pro Trip eine Metriken-Konfiguration, vier Kanal-Renderer:

- Email: ∞ Spalten
- Telegram: max 8
- Signal: max 6
- SMS: 0 (alles flach, ≤ 140 Zeichen)

Spec: `claude-code-handoff/issue-bodies/body-14-output-layout-system.md`.
Editor: `screen-metrics-editor.jsx` (Desktop) mit Multi-Channel-Vorschau.
Constraint-Begründung: `Gregor 20 - Signal Layout.html`.

## Signal-Briefing-Layout

- Body-Ranges: Bold, Italic, Strike, Monospace, Spoiler (kein Markdown-Syntax)
- Bubble-Content-Breite ≈ 272 px → max 6 Mono-Spalten zuverlässig
- Anhänge möglich, aber für Wetter-Briefings nicht relevant
- Splittung in mehrere Bubbles (Quick-Read + N×Segment + Ziel + Outlook)
  ist bevorzugt — pro Bubble einzeln zitier- und reagierbar

## Mobile vs. Desktop

Default ist Desktop. Mobile-Adaption kommt später (V1.5). Bei neuen
Mockups: Desktop zuerst, Mobile als zweiter Schritt mit klarem Verweis.
