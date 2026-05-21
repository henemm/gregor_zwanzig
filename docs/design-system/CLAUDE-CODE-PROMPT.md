# Claude-Code · Standard-Prompt für Implementierungs-Aufträge

> **So nutzt du diese Datei:** Bei jedem neuen Issue / Auftrag an Claude Code schreibst du nur:
> > Befolge `docs/design-system/CLAUDE-CODE-PROMPT.md`, dann mach Issue #N.
>
> Der komplette Kontext steckt hier drin.

---

## Pflicht-Lektüre · vor jeder Implementierung

Bevor du irgendetwas implementierst, lies in dieser Reihenfolge:

1. **`docs/design-system/README.md`** — Index + die drei Regeln (Single-Source, No-Drift, Charter > Code).
2. **`docs/design-system/CHARTER.md`** — verbindliche Design-Entscheidungen. 11 Sektionen, eine Aussage pro Zeile.
3. **`docs/design-system/COMPONENTS.md`** — Komponenten-Katalog. **Das ist deine einzige erlaubte Bauteilliste.**
4. **`docs/design-system/COPY.md`** — Terminologie-Dictionary. Verwende nur Strings, die hier stehen.
5. **`docs/design-system/ANTI-PATTERNS.md`** — Negativliste mit 20 nummerierten AP-Regeln + Grep-Befehlen.
6. **`docs/design-system/TOKENS.md`** — Design-Token-Referenz (Spiegel von `tokens.css`).
7. **`docs/design-system/SCREENS.json`** — pro Screen: Route, Layout, Komponenten, Copy, Compliance-Checks, zugehöriger Mockup-Frame.

---

## Pflicht-Schritt-0 · Drift-Audit

Bevor du Code schreibst, **führe die Audit-Befehle aus `ANTI-PATTERNS.md` Sektion „Selbst-Audit-Befehle"** auf dem aktuellen Codebase aus. Damit kennst du den Ist-Zustand. Beispiele:

```bash
# AP-001 — native Form-Controls
grep -rn 'type="checkbox"' frontend/src/
grep -rn '<select' frontend/src/

# AP-007 — Inline-Hex-Farben (außerhalb tokens.css)
grep -rn -E '#[0-9a-fA-F]{3,6}' frontend/src/ \
  | grep -v 'tokens.css' | grep -v '\.md:'

# AP-008 — Magic-Pixel-Spacing
grep -rnE '(padding|margin|gap):\s*[0-9]+px' frontend/src/

# AP-009 — Emojis im UI
grep -rnP '[\x{1F300}-\x{1F9FF}]|✓|✗|⚠|🟢|🔴|📍|🗺' frontend/src/

# AP-014 — Tabu-Wörter aus COPY.md §9
grep -rwni -E 'Trip|Trips|Stage|Account|Notification|Cockpit|Editieren|Erstellen' \
  frontend/src/ | grep -v '\.svelte-kit/'
```

**Wenn die Befehle Treffer liefern, dokumentiere sie** in deinem Plan vor der Implementierung, damit der Reviewer weiß, was du gefunden hast und was du davon mit-fixt.

---

## Visuelle Referenz

`Soll-Mockups.html` im Repo-Root. Öffne lokal im Browser.

- **Ganz oben:** „Audit · Konsistenz-Status" — Tabelle aller Screens × Charter-Regeln. Rot = Drift, Grün = compliant. Identifiziere zuerst, ob dein Ziel-Screen bereits grün ist (= Mockup ist verbindlich) oder rot (= Mockup muss in deinem PR mit-aktualisiert werden).
- **Section „Design System · Page-Chrome":** Beweis-Frames, wie die kanonischen Bausteine aussehen — `<PageHeader>`, `<PageTileGrid>`, `<Tile>`, `<PageEmpty>`.
- **Section „① Trip anlegen", "②", … :** Konkrete Screens. Den passenden Frame findest du in `SCREENS.json` unter `mockup_frames.desktop` / `mockup_frames.mobile`.

---

## Implementierungs-Regeln · die zehn Gebote

1. **Komponenten-Name = Vertrag.** Eine Komponente heißt im Code GENAU so wie in `COMPONENTS.md`. `<PageHeader>` ist `<PageHeader>`, nicht `<MyHeader>` oder `<TripsHeader>`.

2. **Erfinden ist verboten.** Wenn du einen Baustein brauchst, der nicht im Katalog steht: **erst `COMPONENTS.md` ergänzen** (mit Begründung, in derselben Commit-Welle), dann nutzen. Niemals silent eine lokale Variante bauen (AP-006).

3. **Copy nur aus dem Dictionary.** Tabu-Wörter (siehe `COPY.md §9`) erscheinen nirgendwo (AP-014). Wenn du einen neuen String brauchst, **ergänze ihn in `COPY.md`** (mit Kontext-Notiz).

4. **Layout-Pattern aus `SCREENS.json` befolgen.** Drei Patterns: `kachel-grid` (Listen) · `master-detail` (Sammlungen mit Gruppen) · `wizard` (Anlege-Prozesse). Keine Tabellen für Touren/Vergleiche/Archiv/Templates (AP-003).

5. **Genau eine Primäraktion pro Screen** (AP-004). Sekundäre Aktionen leben im `<DropdownMenu>`. Kein FAB (AP-012).

6. **Keine nativen Form-Controls** (AP-001). Nutze `<Checkbox>`, `<Switch>`, `<Select>`, `<DateInput>`, `<TimeInput>` aus dem Katalog.

7. **Nur Tokens, nie Inline-Hex** (AP-007). Nur Spacing-Tokens, nie Magic-Pixel (AP-008). Nur Type-Scale-Tokens, nie Magic-Font-Sizes (AP-017).

8. **Klick auf Listen-Item-Name = Detail-Navigation** (AP-005). Keine Icon-Buttons-Soup auf Listen-Zeilen.

9. **Wetter ist Drill-Down, keine eigene Seite** (AP-013). `/weather` ist tot. Wetter erscheint als Slide-Panel (Desktop) oder Bottom-Sheet (Mobile) aus Trip-Detail oder Compare.

10. **Keine Emojis im UI** (AP-009). Mathematische Zeichen und Pfeile sind erlaubt.

---

## Vorgehen pro Issue

1. **Issue parsen.** Welcher Screen? Welche Datei in `SCREENS.json`?
2. **Mockup öffnen.** Frame in `Soll-Mockups.html` lokalisieren via `mockup_frames`-Eintrag. Pixel-Genauigkeit ist Ziel.
3. **Komponenten-Liste extrahieren.** `SCREENS.json[id].components` zeigt dir, welche Bausteine der Screen verwenden MUSS.
4. **Copy-Strings extrahieren.** `SCREENS.json[id].copy` ist die verbindliche User-facing-Sprache.
5. **Drift-Audit laufen lassen** (siehe oben).
6. **Implementieren.**
7. **Audit nochmal laufen lassen.** Keine neuen Treffer? Gut.
8. **Audit-Dashboard-Eintrag aktualisieren** in `soll-mockups/audit.jsx` → `AUDIT_SCREENS` — wenn dein Screen jetzt eine Regel erfüllt, die er vorher nicht erfüllt hat, drehe `false` auf `true`.

---

## Was tun, wenn …

### … ein Issue mit der Charter konfligiert?

**Frage.** Implementiere nicht beides parallel. Bevorzugt nimmst du die Charter; falls der Issue Recht hat, ändere zuerst die Charter, dann implementiere.

### … du eine neue Komponente brauchst?

1. Ergänze sie in `docs/design-system/COMPONENTS.md` mit Props-Tabelle und Verwendungs-Notiz.
2. Implementiere sie in `frontend/src/lib/components/<group>/<Name>.svelte`.
3. Implementiere ein Mockup-Pendant in `soll-mockups/page-chrome.jsx` (oder passender Datei).
4. Füge einen Proof-Frame in `Soll-Mockups.html` hinzu.
5. Erst dann verwende sie im Ziel-Screen.

### … ein Mockup falsch aussieht?

Sage es klar im PR / Issue. Mockups sind nicht heilig — sie sind die Proof-Layer der Charter. Wenn ein Mockup vom Soll abweicht, ist entweder das Mockup falsch oder die Charter unklar. Erst klären, dann implementieren.

### … du in einer bestehenden Datei Drift findest?

Drei Optionen:

- **Im Scope:** Wenn dein Issue es berührt, mit-fixen.
- **Neuer Issue:** Drift-Fixes als separaten Issue dokumentieren, mit AP-Referenz.
- **Audit-Update:** In `audit.jsx` rot markieren, damit es nicht vergessen wird.

---

## Definition of Done · für jeden PR

Ein PR ist erst fertig, wenn:

- [ ] Alle Audit-Befehle aus `ANTI-PATTERNS.md` keine neuen Treffer liefern.
- [ ] Der implementierte Screen verwendet die `components`-Liste aus `SCREENS.json` (1:1).
- [ ] Alle Copy-Strings stammen aus `COPY.md`.
- [ ] Es gibt genau eine `variant="primary"`/`variant="accent"`-Button-Instanz pro Screen.
- [ ] Mockup-Frame in `Soll-Mockups.html` wurde gegen die Implementierung visuell verglichen (Screenshot-Vergleich).
- [ ] `audit.jsx` ist aktualisiert (wenn sich Compliance-Status geändert hat).
- [ ] Charter-Konflikte sind dokumentiert oder gelöst.

---

## Anti-Halluzination · was du NICHT tust

- Keine eigenen Page-Header-Implementierungen (AP-011).
- Keine ad-hoc Card- / Toast- / Dropdown-Komponenten (AP-006).
- Kein eigenes "Cockpit"-Dashboard (AP-010).
- Keine `/weather`-Standalone-Seite (AP-013).
- Keine Magic-Pixel-Werte (AP-008), Inline-Hex (AP-007) oder Emoji (AP-009).
- Keine Lat/Lon-Eingabefelder (AP-002).
- Keine Tabelle für Touren/Vergleiche/Archiv (AP-003).

Wenn du dich bei einer Entscheidung unsicher bist: **frage zurück**, bevor du implementierst. Das System ist explizit, damit du nicht raten musst.

---

## Versionierung

| Version | Datum | Anmerkung |
|---|---|---|
| v1.0 | 2026-05-21 | Initialer Prompt — Design-System v1.0 Foundation |
