# Context: #581 — Design-Fidelity Trip-Detail 1:1 nach JSX

## Request Summary
Trip-Detail (5 Screens) 1:1 aus der JSX-Vorlage neu bauen, Pixel-Diff-Gate < 10 % gegen
`current/soll/F-trip-detail-*.png`. Wieder geöffnet im Zuge der Epic-#575-Drift-Korrektur
(Pilot #582 maß 51,5 % Drift).

## Zentrale Erkenntnis: SOLL **und** JSX-Quelle sind veraltet
Das Handoff-Paket (`claude-code-handoff/current/`, alle Dateien 6. Juni) liegt **vor** mehreren
neueren PO-Entscheidungen. Konkrete Widersprüche:

| Artefakt | Zeigt | Widerspricht |
|----------|-------|--------------|
| `screen-trip-detail.jsx` Z. 97/99/135/137/179/319 | `signal`-Kanäle, „SMS / Signal" | #610 (Signal app-weit raus, 6.6.) |
| `F-trip-detail-reports-collapsed.png` | Kanal **Signal** („Signal-Nummer fehlt") | #610 |
| `F-trip-detail-reports-expanded.png` / `…-wetter.png` | Alarmregeln mit **Severity-Badge** „warning" | #638 (Severity-Spalte wird entfernt — Falle) |
| `F-trip-detail-overview.png` | getrennte **„TRIP BEARBEITEN"-Ansicht** (Abbrechen/Speichern, Tabs) | #616 (EINE Trip-Seite, /edit stillgelegt) |
| `F-trip-detail-wetter.png` | zeigt **Alarmregeln**, nicht Wetter (Fehlbeschriftung) | #587/#632 (Wetter-Tab v2, eigenes neueres SOLL `F-trip-detail-wetter-v2.png` vom 7.6.) |

→ #581 wörtlich umzusetzen würde **Signal und Severity-Badges wieder einführen** und die alte
getrennte Edit-Ansicht zurückbringen — also #610/#638/#616 rückgängig machen.

## Bereits ausgelieferte Trip-Detail-Arbeit (Epic #575)
| Issue | Was | Status |
|-------|-----|--------|
| #616 | EINE Trip-Seite `/trips/[id]`, /edit stillgelegt | ✅ live |
| #587 + #632 | Wetter-Tab v2, fidelity-gated 6,72 % gegen `F-trip-detail-wetter-v2.png` | ✅ live |
| #617 | Briefing-Zeitplan Kanal-Verkettung | ✅ live |
| #629 | Format-Modell Roh/Einfach | ✅ live |
| #610 | Signal als Kanal entfernt | ✅ live |
| #638 | Alerts Karten-Modell + Severity raus + Kanal pro Alert | offen (aus #617 ausgegliedert) |

## Related Files (aktuelle Implementierung)
| File | Relevance |
|------|-----------|
| `frontend/src/routes/trips/[id]/+page.svelte` | Unified Trip-Seite (Container, #616) |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | Übersicht (2-Spalten-Grid FullProfile + Sidebar) |
| `frontend/src/lib/components/trip-detail/HubSchedule.svelte` | Zeitplan-Karten + ChannelDots |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Container |
| `frontend/src/lib/components/trip-detail/WeatherV2*.svelte` | Wetter-Tab v2 (#587, gated) |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | Reports/Zeitplan (#617/#619/#621) |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Alarmregeln (Umbau → #638) |

## Tooling-Lage
- `design_fidelity_diff.py` mappt **alle** `F-trip-detail-*` auf `/trips` (Liste!), nicht auf
  `/trips/[id]`. Echte Trip-Detail-Messung bräuchte ein eigenständiges Wegwerf-Script
  (Memory `feedback_shared_fidelity_tool.md`: geteiltes Tool NICHT umbauen, keine hart-codierte Trip-ID).
- `pre_issue_close_design_gate.py` blockt Issue-Close ohne PASS-Artefakt.

## Präzedenzfall #582 (Schwester-Issue)
PO-Entscheidung 2026-06-07: pro Screen splitten, KEIN Wizard mehr, **SOLL teils veraltet** (Signal raus).
Alte „done"-Memory war falsch. → Gleiche Logik trifft auf #581 zu.

## Risks & Considerations
- **Premise-Bruch:** Issue verlangt 1:1 zu Artefakten, die aktuellen Produktentscheidungen widersprechen.
- Blindes Befolgen = Regression (#610/#638/#616 rückgängig).
- Diff-Gate < 10 % gegen stale SOLL ist nicht erreichbar/sinnvoll.
- Echte Fidelity-Lücken der **aktuellen** Seite sind separat zu messen (neues SOLL nötig).
