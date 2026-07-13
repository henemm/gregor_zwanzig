# Design-Request: Offene Fragen zu den Orts-Vergleich-Screens (Issue #1256, Handoff-4)

Kontext: Umsetzung der Compare-Screens 1:1 aus `claude-code-handoff/current/jsx/`
(Handoff-4, 2026-07-13). Beim Soll-Ist-Abgleich (Kommentar in gregor_zwanzig#1256)
sind folgende Punkte offen, die Claude Design klären bzw. nachliefern müsste.

## 1. Veraltete SOLL-Bilder für Liste + Detail-Hub

`current/soll/G-compare-uebersicht-kacheln.png`, `G-compare-detail.png` (und
`screenshots/soll-ortsvergleich-{uebersicht-kacheln,detail}.png`) zeigen noch
**Ranking-Spalte, Empfehlungs-Copy und Signal-Kanal** — alles PO-seitig verworfen
(2026-06-05 Signal, 2026-07-11 Neutralität). Die JSX sind aktuell, die PNGs nicht.

**Bitte:** `current/soll/` für `screen-compare-list.jsx` und
`screen-compare-detail.jsx` (alle 6 Tabs) neu rendern und den Sync-Hinweis in
`SOLL-COVERAGE.md` nachziehen. Bis dahin prüfen wir gegen die JSX-Struktur ohne
Pixel-Referenz (fresh-eyes bekommt nur JSX-Strukturbeschreibung statt SOLL-Bild).

## 2. `screen-compare-email.jsx` (Mobile-Projekt) trägt noch das Score/Rang-Modell

Datei ist selbst als `⚠ DEPRECATED (PO 2026-07-11)` markiert, enthält aber
weiterhin Score-Spalten, `rank`, „Winner / Empfehlung · Rang 1", „sortiert nach
Score". Sie wird von den App-Screens nicht importiert — Verwechslungsgefahr bei
künftigen Handoffs bleibt trotzdem.

**Bitte:** Datei entfernen oder durch einen neutralen V2-Mail-Screen ersetzen
(deckungsgleich mit `CompareBriefingPreview` / CompareEmailV2).

## 3. Mobile-Liste: Suchfeld ohne Funktion

`screen-compare-list-mobile.jsx` rendert `MInput` ohne value/onChange — Desktop
filtert nach Name. Absicht (Suche mobil rein dekorativ?) oder Lücke?

**Bitte:** klarstellen; falls Suche mobil funktional sein soll, Verhalten
spezifizieren (Filter identisch Desktop?).

## 4. Mobile-Detail: Monitoring 2×2 ohne „Briefings"-Kachel

Desktop-Hub zeigt 5 Stats (inkl. „Briefings" mit Uhrzeiten), Mobile-Detail nur 4
(`screen-compare-detail-mobile.jsx:80`). Da die Briefing-Uhrzeiten das zentrale
Versand-Versprechen sind (PO 2026-07-11): bewusst weggelassen oder Platzgrund?

**Bitte:** bestätigen oder 5. Kachel/alternative Platzierung vorgeben.

## 5. Editor-Tab „Alarme" — Zielbild laut 29a/29b: KEIN eigener Tab (Rest-Config?)

Nachgesichtet: Im neuesten Modell (body-29a/29b) existiert für den Vergleich
kein eigener „Alarme"-Tab — `notify` läuft über den geteilten
Wertebereiche-Tab (Korridore) + `AlertChannelPicker` im **Versand**-Tab. Die
App hat aber heute einen 6. Editor-Tab „Alarme" (#1170) mit Zusatz-Config, die
in Wertebereiche/Versand kein Zuhause hat: Cooldown-Minuten, Ruhezeiten
(quiet hours), Radar-Alert-Toggle, amtliche-Warnungen-Toggle.

**Bitte:** bestätigen, dass der Alarme-Tab im Zielbild entfällt, und festlegen,
wo die Rest-Config (Cooldown/Ruhezeiten/Radar/amtliche Warnungen) landen soll
(Versand-Tab-Sektion? eigene Karte im Hub?). (PO-Frage parallel in
gregor_zwanzig#1256.)

## 6. Neutralitäts-Grauzone in der Live-Vergleichsansicht

Der Hub-/Vorschau-Bereich der App nutzt heute `CompareMatrix` mit
„Best-Value"-Hervorhebung (+ `HourlyMatrix` „Top-3") aus #251 — positions-, nicht
score-basiert, aber optisch eine Auszeichnung EINES Ortes. Die Soll-Vorschau
(`CompareBriefingPreview`, `LT_ComparePreview`) markiert dagegen NUR
Idealbereich-Treffer (grün), ohne einen „besten" Ort hervorzuheben.

**Bitte:** bestätigen, dass Best-Value-/Top-N-Hervorhebungen entfallen und die
neutrale Markierungs-Logik die einzige Auszeichnung ist (C1/C3-Konsequenz).

## 7. Widerspruch: Fluss-Prototyp vs. `mode="edit"` im Editor-JSX

`Gregor 20 - Ortsvergleich Fluss.html` (verdrahteter Klick-Prototyp, Z.70-77)
legt fest: **„Kein separater Anzeige-/Edit-Screen"** — Detail-Tabs = Ansehen +
Inline-Editieren, der Editor wird ausschließlich mit `mode="create"`
instanziiert. `screen-compare-editor.jsx` dokumentiert und implementiert aber
weiterhin einen vollwertigen `mode="edit"` (alle Tabs frei,
Speichern/Verwerfen), den der Fluss nie aufruft.

**Bitte:** klarstellen, ob `mode="edit"` (a) Alt-Bestand ist und entfernt werden
kann (Fluss = Wahrheit, Bearbeiten nur inline im Hub) oder (b) ein bewusster
zweiter Bearbeiten-Weg bleiben soll (wofür? welcher Einstieg?). Unsere
Arbeits-Annahme bis zur Antwort: Fluss gewinnt — App-Umsetzung staffelt den
separaten `/edit`-Screen aus, sobald die Hub-Tabs Inline-Edit-Parität haben.

Nachgesichtet (stützt die Annahme): body-20 „Kanonische IA" sagt in der
Reconciliation-Note wörtlich, „derselbe Wizard im Edit-Modus" sei VERWORFEN —
Bearbeiten läuft über die Hub-Tabs, `/vergleich/[id]/bearbeiten` leitet auf
`?tab=…` um. Einzige Quelle, die den Wizard-Edit-Modus noch behauptet, ist
`nav-map.jsx` (Z.266/283/288) — offenbar nach der Reconciliation nicht
nachgezogen. **Bitte nav-map.jsx entsprechend bereinigen.**

## 8. SOLL-COVERAGE.md ist für Compare veraltet

Stand 2026-06-04: referenziert das gelöschte `screen-compare-wizard.jsx`, kennt
weder `screen-compare-editor(-mobile).jsx` noch `corridor-editor`/`layout-tab`/
`versand-tab` und nicht die Neutralisierung. **Bitte** beim Neu-Rendern der
Soll-Bilder (Frage 1) auch das Coverage-Mapping nachziehen.
