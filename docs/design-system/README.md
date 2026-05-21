# Gregor Zwanzig · Design System

> Single Source of Truth für UI-Entscheidungen, Komponenten und Copy.
>
> **Konsument:** Claude Code bei der SvelteKit-Implementierung.
> **Beweis-Layer:** `Soll-Mockups.html` rendert jeden hier deklarierten Baustein als visueller Reference-Frame.

---

## 📚 Dokument-Index

| Datei | Inhalt | Wann lesen |
|---|---|---|
| **[CLAUDE-CODE-PROMPT.md](./CLAUDE-CODE-PROMPT.md)** | Standard-Prompt für Implementierungs-Aufträge. Pflicht-Lektüre + 10 Gebote + DoD. | Vor JEDEM neuen Implementierungs-Auftrag. |
| **[CHARTER.md](./CHARTER.md)** | Verbindliche Design-Entscheidungen. Eine Aussage pro Zeile. | Vor JEDEM neuen Screen, Feature oder Refactor. |
| **[COMPONENTS.md](./COMPONENTS.md)** | Komponenten-Katalog mit Props, Slots, Verwendung. | Wenn du UI baust — welche Komponente passt? |
| **[COPY.md](./COPY.md)** | Terminologie-Dictionary, kanonische Begriffe + Tabu-Liste. | Vor jedem User-facing String. |
| **[ANTI-PATTERNS.md](./ANTI-PATTERNS.md)** | Negativliste. Was NICHT gebaut wird, und warum. | Bei jedem PR-Review, vor jedem Commit. |
| **[TOKENS.md](./TOKENS.md)** | Design-Token-Referenz (Farben, Spacing, Typo). Spiegelt `tokens.css`. | Wenn du Farbe / Spacing / Schrift wählst. |
| **[SCREENS.json](./SCREENS.json)** | Maschinenlesbares Screen-Manifest mit Compliance-Checks. | Pro Screen-Implementierung als Vorlage. |

---

## 🔒 Die drei Regeln

1. **Single-Source:** Komponenten-Name im Mockup = im Code = im Katalog. Identisch.
2. **No Drift:** Lokale Re-Implementierung von katalogisierten Komponenten ist ein Bug (siehe AP-006).
3. **Charter > Code:** Wenn Implementierung der Charter widerspricht, gewinnt die Charter — oder die Charter wird in derselben Welle geändert.

---

## 🧭 Wie Claude Code dieses System nutzt

### Beim Bauen eines neuen Screens

1. **CHARTER** lesen: Welches Layout-Pattern (Kachel-Grid / Master-Detail / Wizard)?
2. **COMPONENTS** scannen: Welche Bausteine existieren? Nutze sie buchstäblich.
3. **COPY** durchsuchen: Sind die geplanten Strings im Dictionary?
4. **ANTI-PATTERNS** abgleichen: Verstoße ich gegen eine Regel?
5. **TOKENS** referenzieren: Alle Farben / Abstände / Schriften als CSS-Variablen.
6. **Soll-Mockups.html** öffnen: Gibt es einen Reference-Frame? Wenn ja: Pixel-Vergleich.

### Beim Review eines PRs

```bash
# AP-Audit-Befehle laufen lassen (s. ANTI-PATTERNS.md Sektion 'Selbst-Audit-Befehle')
grep -rn 'type="checkbox"' frontend/src/    # AP-001
grep -rn -E '#[0-9a-fA-F]{3,6}' frontend/src/ | grep -v tokens.css  # AP-007
grep -rwni -E 'Trip|Account|Cockpit' frontend/src/    # AP-014
```

### Beim Hinzufügen einer neuen Komponente

1. **Eintrag in COMPONENTS.md** (Name, Props, Was-sie-tut).
2. **Mockup-Implementierung** in `soll-mockups/page-chrome.jsx` (oder passendem File).
3. **Reference-Frame** in `Soll-Mockups.html` als Proof.
4. **Svelte-Implementierung** in `frontend/src/lib/components/<group>/<Name>.svelte`.
5. **Verwendung** in mindestens einem Screen-Mockup.

---

## 🧪 Mockup-Code-Map

| Mockup-Datei | Inhalt |
|---|---|
| `tokens.css` | Token-Definitionen (≙ TOKENS.md) |
| `brand-kit.jsx` | Brand-Komponenten (Wordmark, Sidebar, Shell, UserBadge) |
| `atoms.jsx` | Btn, Pill, Eyebrow, Card, KV, WIcon, Dot, ElevSparkline |
| `mobile-shell.jsx` | PhoneFrame, MobileShell, MBtn, MInput, MTab, ScreenScroll, Sheet, Toast, Drawer |
| `soll-mockups/page-chrome.jsx` | **PageHeader, PageSection, PageTileGrid, Tile, PageEmpty, PageActions** (NEU Runde 1) |
| `soll-mockups/primitives.jsx` | Spec-Karten für Toast / Dropdown / Segmented / Switch / Sheet |
| `soll-mockups/flow-*.jsx` | Konkrete Screens, jeweils zusammengesetzt aus den oben genannten Bausteinen |

**Anti-Pattern in dieser Map:** Wenn `flow-*.jsx`-Files eigene Page-Header / Cards / Buttons implementieren statt aus `page-chrome.jsx` / `atoms.jsx` zu importieren, ist das Drift und MUSS in Runde 2 konsolidiert werden.

---

## 🛣 Was als Nächstes passiert (Runde 2)

Diese Runde 1 hat das Fundament geschaffen. Runde 2:

1. **Bestehende `flow-*.jsx`-Files refactoren** → nutzen nur noch `<PageHeader>` etc. aus `page-chrome.jsx`.
2. **Trip-Liste als Kachel-Pilot** — `Flow7_ListReduced` wird von Tabelle auf `<PageTileGrid> + <Tile>` umgestellt.
3. **`SCREENS.json` generieren** — pro Screen ein Manifest mit verwendeten Komponenten + Copy-Strings (für Claude Code als Implementierungs-Vorlage).
4. **Audit-Section im Canvas** — Mini-Thumbnails aller Screens + Rot/Grün-Checkliste pro Charter-Regel.

---

## 📝 Änderungs-Disziplin

Jede Änderung an einer dieser Dateien ist ein Vertragswechsel. Konsequenz:

- **Mockups + Code MÜSSEN in derselben Welle nachgezogen werden.**
- **Begründung MUSS im Diff stehen** (Issue-Link / kurze Inline-Begründung).
- **Versionierungs-Tabellen am Ende jedes Files MÜSSEN aktualisiert werden.**

Wenn ein PR eines der Files ändert, ohne die abhängigen anzupassen: PR wird zurückgewiesen.

---

## Versionierung

| Version | Datum | Anmerkung |
|---|---|---|
| v1.0 | 2026-05-21 | Runde 1 — Fundament komplett. CHARTER + COMPONENTS + COPY + ANTI-PATTERNS + TOKENS + page-chrome.jsx |
