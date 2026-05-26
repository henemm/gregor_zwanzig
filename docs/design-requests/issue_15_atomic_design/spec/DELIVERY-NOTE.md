# Delivery · Screen-JSX-Quellen für Phase 2 (Issue #15 · Tracking #385)

**Verfasser:** Claude Design (Sandbox `gregor-zwanzig`), als Tech Lead.
**Empfänger:** Claude Code (`henemm/gregor_zwanzig`), CC PO.
**Datum:** 2026-05-26.
**Bezug:** Anfrage 2026-05-26 (Phase-2-Migration der echten Screens).

---

## Inhalt dieses Ordners

```
spec/
├─ DELIVERY-NOTE.md           ← dieses Dokument
├─ screen-home.jsx            → Route /
├─ screen-trips.jsx           → Route /trips
├─ screen-trip-detail.jsx     → Route /trips/[id]  (+ /trips/[id]/edit)
├─ screen-trip-wizard.jsx     → Route /trips/new
├─ screen-compare.jsx         → Route /compare
├─ screen-archive.jsx         → Route /archiv      (sic — Live-Route heißt /archiv)
├─ organisms.jsx              → aktuelle Organism-API (post-#345)
├─ mock-data.jsx              ← Mock-Trips/Stages/Locations (nur Lesehilfe)
└─ mock-locations.jsx         ← Mock-Locations (nur Lesehilfe)
```

Die Mock-Files sind beigelegt, damit die Screen-JSX read-only zusammenhängend
lesbar ist. Sie sind **nicht Teil der Production-Migration** — Claude Code
verwendet stattdessen die echten SvelteKit-Stores / Loader.

---

## 1) Screen-Vorlagen — geliefert

Alle sechs Screens sitzen auf den Sandbox-Tokens (`--g-card #ffffff`,
`--g-paper #f6f4ee`, Brand-Akzent `#c45a2a`) und konsumieren — wo
verfügbar — die Bibliotheks-Bausteine aus `brand-kit.jsx`, `atoms.jsx`,
`molecules.jsx`, `organisms.jsx`.

### Caveat — Inline-Helper, die in Atome/Molecules wandern müssen

Die Screens wurden ursprünglich VOR dem Phase-1-Abschluss geschrieben.
Phase 1 hat danach Atoms/Molecules formalisiert, was bedeutet: einige
Inline-Helper in den Screens **duplizieren heute Bibliotheks-Bausteine**.
Während der Phase-2-Migration sind sie durch die kanonische API zu
ersetzen. Liste:

| Screen | Inline-Helper | Ersetzen durch (Library-Baustein) |
|---|---|---|
| `screen-trips.jsx` | `SummaryStat` | `Stat` (molecules) |
| `screen-trips.jsx` | `ActionBtn` | `Btn variant="quiet" size="xs"` (atoms) |
| `screen-trip-detail.jsx` | `StatusBadge` | `Pill` (atoms) — `tone` mapped auf `active/planned/paused/archived` |
| `screen-trip-detail.jsx` | `Tab` | `Segmented` (atoms) |
| `screen-trip-detail.jsx` | `ChannelDot` | `Dot` (atoms) oder `ChannelChip compact` (molecules) — siehe unten |
| `screen-trip-wizard.jsx` | `ProfileChip` | `Pill` (atoms) im selektierten/unselektierten Zustand |
| `screen-compare.jsx` | `ChipBtn` | `Pill` (atoms) — Toggle-Variante |
| `screen-compare.jsx` | `CompareField` | `Field` (molecules) |
| `screen-compare.jsx` | `FocusBadge` | `Pill` (atoms) — `tone="accent"` |
| `screen-archive.jsx` | `ArchiveSortTab` | `Segmented` (atoms) |
| `screen-archive.jsx` | `ArchiveAction` | `Btn variant="quiet"` (atoms) |

**Entscheidung als Tech Lead:** Keiner dieser Inline-Helper ist eine fehlende
Bibliotheks-Komponente — die Bibliotheks-API deckt jeden Fall ab. Die
JSX-Vorlagen bleiben as-is geliefert (Bausteinwahl-Referenz), aber bei
der Svelte-Portierung wird **nicht** der Inline-Helper portiert, sondern
direkt das Library-Atom verwendet. Claude Code: bitte in den Migrations-
PRs konsequent so umsetzen; bei Unklarheit über die korrekte Tone-/Variant-
Wahl pro Fundstelle gerne pingen.

### Page-lokale Komposita — bleiben page-lokal

Folgende Helper sind **bewusst** page-lokal und gehören nicht in die
Bibliothek (zu spezifisch, keine erkennbare Wiederverwendung außerhalb
ihres Screens):

- `TripRow` (trips), `StageRow` (trip-detail), `LocationRow` (compare),
  `SubRow` (compare), `GpxItem` (wizard), `ArchiveRow` (archive)
  — Tabellen-/Listenzeilen mit screen-spezifischer Spaltenwahl.
- `StepProfile`, `StepGpx`, `StepStages`, `StepBriefings`, `Stepper`,
  `MiniProfile` (wizard) — Wizard-Schritt-Inhalte.
- `FullProfile`, `MetricsPreview`, `ReportLine` (trip-detail) —
  Detail-Bühnen-spezifische Kompositionen.
- `CompareMatrix`, `MiniBarCell`, `HourlyMatrix`, `HourCell`,
  `RecommendationBanner`, `CompareLocationsRail`,
  `CompareSubscriptionsPanel` (compare) — Vergleich-Bühnen-Komposition.
- `ArchiveContent`, `AccuracyBar` (archive) — Archiv-spezifisch.

Diese sind in den JSX-Quellen 1:1 die Bausteinwahl-Referenz — Pill-Tone,
Stat-Layout, divider-Variante etc. sind dort verbindlich abgebildet.

### Hinweis zu `ChannelDot` / `Dot`

`screen-trip-detail.jsx` benutzt `ChannelDot` für eine Punkt-Reihe, die in
einer Briefing-Verlaufszeile darstellt, welche Kanäle aktiv waren. Es gibt
in der Bibliothek zwei Kandidaten:

- `Dot` (atoms) — neutraler Status-Dot, tone-basiert.
- `ChannelChip kind=… compact` (molecules) — 24×24-Tile mit Mono-Glyph
  pro Kanal.

**Empfehlung:** `ChannelChip compact` — die Kanal-Information ist
identifikatorisch (welcher Kanal?), nicht nur Status (an/aus). Glyph schlägt
Farb-Codierung.

---

## 2) `organisms.jsx` · Status gegen geschlossene #364

**Bestätigung mit Vorbehalt.**

Die mitgelieferte `organisms.jsx` ist der Stand der Sandbox-Konsolidierung
nach #345 und enthält die vollständige Editor-Familie:

| Export | Rolle |
|---|---|
| `WETTER_METRICS_CATALOG` / `WETTER_PRESETS` / `WETTER_CHANNELS` | Daten-Konstanten |
| `wetterAutoAssign`, `wetterDefaultHorizons`, `wetterDefaultScore`, `sampleWetterValue` | Helper |
| `PresetRail` | Linke Preset-Liste mit „Eigenes Profil"-Block |
| `MetricBucket` | Spalte- oder Detail-Sektion |
| `MetricOffShelf` | „Nicht im Briefing"-Aufklapper, gruppiert nach `group` |
| `ChannelPreviewStrip` | 4-Karten-Vorschau (Email/Telegram/Signal/SMS) |
| `MetricsEditorContextBar` | Header mit Kontext + Counts |
| `MetricsEditor` | **DIE konsolidierte Editor-Organism** |
| `MEModeToggle`, `METextBtn`, `MEIconArrow`, `MEHorizonChip` | Editor-interne Atom-Variants |
| `MetricEditorRow` | Eine Metrik-Zeile (auch von `MetricBucket` konsumiert) |

**Was bestätigt ist:**
- Die Vorlage bildet das Modell aus #345 ab (Spalte / Detail / Aus +
  Horizont-Slots HEUTE/MORGEN/ÜBERMORGEN im Tour-Kontext, ScoreToggle
  im Ort/Abo-Kontext).
- Der frühere `EditWeatherSection` ist entfernt — er existiert weder
  in `organisms.jsx` noch in `screen-metrics-editor.jsx`.
- Kanal-Constraints (Email ∞ / Telegram 8 / Signal 6 / SMS 0) sind über
  `WETTER_CHANNELS` und `ChannelPreviewStrip` abgebildet.

**Vorbehalt (Tech-Lead-Hinweis, bitte gegenprüfen):**
Issue #364 ist im Production-Repo geschlossen — ich habe von hier aus
keine Sicht auf die ausgelieferte Komponenten-API in `frontend/src/lib/`.
Falls #364 in der Endphase Komponenten-Namen, Props oder
Slot-Strukturen geändert hat, die hier nicht reflektiert sind (z. B.
geänderte Bucket-Namen, andere Horizont-API, anderer Preset-Slot-Vertrag),
bitte vor Migration der `screen-metrics-editor`-Route melden — ich
ziehe `organisms.jsx` dann nach. **Aktuelle Annahme:** API ist deckungsgleich,
weil organisms.jsx der direkten Extraktion aus dem Sandbox-Editor entspricht.

**Bekannter offener Punkt:**
`screen-metrics-editor.jsx` selbst konsumiert die `organisms.jsx`-API
**noch nicht** — der Screen führt weiterhin seine eigenen Inline-Helper
(`PresetRow`, `ActiveMetricRow`, `BucketSection`, `BucketSectionOff`,
`ChannelPreviewBlock`). Das war die in `RESPONSE-FROM-CLAUDE-DESIGN.md`
(D) angekündigte ME*-Aufräumung. Sie steht — und ist als
Sandbox-Hausaufgabe vor der Phase-2-Migration von `/metrics-editor`
nachzuholen. **Beeinflusst Phase-2-Reihenfolge:** `screen-metrics-editor`
wandert nach Issue #364 + nach dieser Aufräumung; bis dahin sind die
sechs hier gelieferten Screens dran (siehe Abschnitt 3).

---

## 3) Empfohlene Migrationsreihenfolge

**Abhängigkeitsgraph der sechs Screens:**

```
screen-home  ───┐                       (verlinkt → trips, compare, trip-detail)
                ├──→ KEINE Bibliotheks-Dep über Phase 1 hinaus
screen-trips ───┤                       (verlinkt → trip-detail, trip-wizard)
                │
screen-trip-detail ──→ benutzt MetricsPreview-Komposition (page-lokal)
                                          + StageRow-Listen
                                          + ReportLine-Verlauf
                                          + Tabs (→ Segmented)

screen-trip-wizard ──→ verwendet:
                       ChannelRow (molecules)         ← Phase 1, da
                       ChannelChip (molecules)        ← Phase 1, da
                       BriefingScheduleRow (molecules)← Phase 1, da
                       Field (molecules)              ← Phase 1, da
                       StagePill (molecules)          ← Phase 1, da

screen-compare ──→ verwendet:
                       ChannelChip, Stat, Field       ← Phase 1, da
                       + page-lokale CompareMatrix    (komplexes Grid)

screen-archive ──→ Phase 1 reicht aus
```

**Empfehlung (in dieser Reihenfolge migrieren):**

1. **`screen-home`** — kleinste Fläche, höchste Sichtbarkeit, primärer
   Einstiegs-Smoke-Test für den Phase-1-Stack. Nur Card/Pill/Btn/StagePill
   + ein Hero-Block. Wenn Home in Svelte sauber rendert, ist die
   Atom-/Molecule-Bridge verifiziert.
2. **`screen-trips`** — Tabellen-Layout mit `Btn`/`Pill`/`Stat`. Validiert
   Listen-Pattern + Action-Cluster.
3. **`screen-archive`** — strukturell verwandt mit `screen-trips`
   (Tabellen-Listen-Layout). Nach `screen-trips` als geringes
   Marginal-Risiko mitziehen.
4. **`screen-trip-detail`** — komplexere Bühne (Tabs, Etappen-Stack,
   Briefing-Verlauf). Validiert `Segmented`, `StatusBadge→Pill`-Mapping,
   `BriefingTimelineRow`, `ChannelChip`. Erst nach (1)–(3), weil dort
   die Tone-/Variant-Konventionen festgezurrt werden, an denen sich
   diese Seite orientiert.
5. **`screen-compare`** — größter Screen, viele Inline-Helper. Wartet,
   bis (1)–(4) die Atom-Verwendung kanonisch zementiert haben.
6. **`screen-trip-wizard`** — Wizard mit 4 Schritten + GPX-Reorder +
   KI-Vorschlägen + Schwellen-Editor. Höchste Form-Komplexität, baut
   maximal auf `Field`, `ChannelRow`, `BriefingScheduleRow`,
   `ThresholdRow`. **Zuletzt**, weil die Schritte (Stepper, StepGpx,
   StepStages, StepBriefings) page-lokal komponiert sind und der
   Validierungs-Stack (Wegpunkt-Editor, KI-Suggestions) eigene Komplexität
   mitbringt.

`screen-metrics-editor` ist **nicht Teil dieser Reihenfolge** — er wartet
auf #364-Abschluss + die ME*-Sandbox-Aufräumung (siehe Abschnitt 2,
offener Punkt) und kommt anschließend separat.

**Parallelisierbar:** (2) und (3) können nach (1) parallel laufen; (5)
und (6) sollten sequentiell bleiben (Compare-Patterns informieren Wizard-
Schritt 4, in dem Schwellen-Edits auf den Editor-Patterns aus Compare
aufsetzen).

---

## 4) Surface-Stack-Bestätigung

**Bestätigt.** Alle sechs Screens setzen auf:

```
--g-paper          #f6f4ee   (App-Background, warm Off-White)
--g-paper-deep     #ecead9   (gedämpfte Sektionen)
--g-card           #ffffff   (Cards / Tabellen — REINWEISS)
--g-card-alt       #faf8f1   (Zebra, sekundäre Karten)
--g-rule           #d8d3c2
--g-rule-soft      #e7e2d3
```

Verifiziert per Volltextscan: kein `#edeae1` / `#e8e5db` (alter beiger
Card-Wert) mehr in einem der sechs Files. Cards sind ausnahmslos
`var(--g-card)` oder explizit `#ffffff` (mit dem Sandbox-Token als
Quelle).

PO-Grundgesetz aus `CLAUDE.md` („Hoher Kontrast = Lesbarkeit, Cards = weiß
auf warmer Off-White-Page") ist eingehalten.

**Voraussetzung für die Phase-2-PRs:** Production-`app.css` muss vorher
auf die Sandbox-Werte umgestellt sein (Surface-Stack-Migration aus
`RESPONSE-FROM-CLAUDE-DESIGN.md` Abschnitt A2). Wenn die Migration noch
nicht durch ist, würden die Screens beim ersten Render auf beigen
Card-Werten landen — das Kantenkontrast-Problem aus A2 würde sofort
sichtbar. **Bitte vorher abklären / Issue verlinken**, sonst PR-Ablauf
unterbrechen.

---

## Offene Rückfragen an Claude Code

1. **#364-API-Diff** — gibt es Abweichungen zwischen der hier gelieferten
   `organisms.jsx` (Editor-Familie) und dem ausgelieferten Production-
   Editor? Wenn ja, kurze Diff-Liste, ich aktualisiere die Sandbox.
2. **Surface-Stack-Migration-Status** — ist der `app.css`-Wert-Tausch
   (Issue aus A2) schon eingetreten oder steht er noch aus? Davon hängt
   ab, ob die Phase-2-PRs auf weißen oder beigen Cards landen.
3. **Token-Rename-Status (A3)** — wenn der Rename `--g-paper → --g-surface-0`
   etc. inzwischen durch ist, müssen die hier gelieferten JSX-Quellen
   bei der Portierung mit umbenannt werden. Bitte signalisieren, ob
   Phase-2-PRs auf den alten oder neuen Namen committen.

---

## Hinweis zur Synchronität

Diese JSX-Quellen sind die **Sandbox-Wahrheit** zum Zeitpunkt der
Lieferung (2026-05-26). Wenn der PO oder ich nach Auslieferung dieses
Pakets eines der `screen-*.jsx`-Files im Sandbox-Projekt touchieren, ist
der Spec-Ordner hier **nicht** automatisch nachgezogen — er ist ein
eingefrorener Snapshot. Bei nennenswerten Änderungen liefere ich
explizit ein Re-Sync-Paket (DELIVERY-NOTE-v2 + neu kopierte Files).
