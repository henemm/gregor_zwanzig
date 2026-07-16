# Nachzieh-Hinweis an Claude Design: Sortier-Bedienung im Layout-Tab

**Bezug:** Issue #1272, ADR-0024, Spec `docs/specs/modules/issue_1272_shared_sortable.md`
**Datum:** 2026-07-16 · **Kein Blocker** — #1272 wird auf PO-Entscheid hin bereits umgesetzt.

## Worum es geht

Beim Vereinheitlichen der Sortier-Bedienung ist eine Abweichung zwischen Handoff-4-JSX
und laufendem Code aufgefallen. Wir bitten um Nachziehen der JSX an **einer** Stelle.

## Der Widerspruch

Das JSX beschreibt für die zwei Sortier-Listen des Layout-Tabs unterschiedliche Bedienungen:

| Kontext | JSX-Quelle | Bedienung laut JSX |
|---|---|---|
| `vergleich` — `LT_CompareOrderList` | `claude-code-handoff/current/jsx/layout-tab.jsx:111` | Griff `⋮⋮` (`cursor: "grab"`), **keine** Pfeile |
| `route` — `WM2_ReihenfolgeRow` | `claude-code-handoff/current/jsx/screen-trip-edit-v2-weather.jsx:148-150` + `:164-165` | Punkte-Griff-SVG **und** ▲/▼ (`WM2_Arrow`) nebeneinander |

Der laufende Code der Route-Fläche (`frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte`)
hat die Pfeile dagegen **nicht** — Kommentar Zeile 6: „Issue #848 — Drag & Drop ersetzt
Pfeiltasten." Das Punkte-SVG stimmt dabei pixelgenau mit dem JSX überein (10×14, sechs
Punkte, r=1.1); abweichend sind ausschließlich die ▲/▼.

## PO-Entscheid (2026-07-16)

**#848 gilt, das JSX ist an dieser Stelle stale.** Der Trip bleibt griff-only, die Pfeile
kehren nicht zurück. Grund: Ziel von #1272 ist eine durchgängige Sortier-Bedienung; die
Pfeile im Route-Zweig wären der einzige verbleibende Sonderweg.

Die Tastatur-Bedienung, für die die Pfeile ursprünglich standen
(`docs/specs/modules/issue_433_layout_dnd.md:21`), geht nicht verloren: sie wandert auf den
Griff selbst (Space/Enter → Sortier-Modus, Pfeiltasten → verschieben), getragen vom
eingebauten Tastatur-Support von `svelte-dnd-action@0.9.69`.

## Bitte

`WM2_ReihenfolgeRow` in `screen-trip-edit-v2-weather.jsx` so nachziehen, dass der
Route-Zweig dem Vergleich-Zweig entspricht: Griff ja, ▲/▼ nein (`WM2_Arrow` entfällt dort
ersatzlos). Damit sind JSX und Code wieder deckungsgleich und die Regel „JSX ist die
Wahrheit" bleibt ohne Ausnahme anwendbar.

## Offene Design-Frage (gerne mitbeantworten)

`layout-tab.jsx:111` zeigt den Griff nur bei `!dense` — auf Mobil (`dense`) also **kein**
Griff. Ist das Absicht? Falls ja: Wie soll auf Mobil sortiert werden? Wir bauen den Griff
vorerst auch im dichten Modus ein, weil sonst dort gar keine Sortierung möglich wäre.
