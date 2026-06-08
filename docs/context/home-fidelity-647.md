# Context: home-fidelity-647

## Request Summary
Folge-Issue zu #579 (Epic #575): drei bei #579 bewusst zurückgestellte Home-Screen-Fidelity-Punkte abarbeiten — (1) Planning-Modus 1:1 gegen `screen-home-planning.jsx` inkl. DOM-Verifikation in leerem Konto-Zustand, (2) Trip-Modus-Empty/Archiv-Bereich echt per DOM auf Staging beweisen, (3) Compare-Outbox-Card: Platzhalter durch echte Versand-Timeline ersetzen + Hero-Untertitel „Vorhersage {horizon}" definieren oder streichen.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/+page.svelte` | Home-Screen, alle drei Modi (trip/compare/planning). Compare-Outbox-Platzhalter Z.606-608; Compare-Hero „Nächster Versand: —" hardcodiert Z.498; Planning-Archiv NICHT in Card Z.809-818 |
| `frontend/src/routes/+page.server.ts` | Loader: lädt trips, presets (`/api/compare/presets`), cockpitStatus. Preset enthält `letzter_versand` |
| `frontend/src/lib/utils/cockpitHelpers568.ts` | **`deriveNextSend(preset, now)` existiert bereits** — berechnet nächsten Versand aus schedule/hour_from/weekday |
| `frontend/src/lib/components/molecules/CompareStatusRow.svelte` | Nutzt `deriveNextSend` + `formatNextSend` bereits live (Vorbild für Timeline) |
| `frontend/src/lib/components/molecules/BriefingTimelineRow.svelte` | Zeilen-Komponente (when/kind/channels/status sent\|planned/etappe) — exakt das JSX-Timeline-Format |
| `frontend/src/routes/_home/cockpitHelpers.ts` | `plannedBriefings`, `archivedTrips` — Home-Helfer |
| `claude-code-handoff/.../jsx/screen-home.jsx` | SOLL Compare-Modus: `homeCompareTimeline(sub)` (Z.27-34) = Zuletzt/Nächster-Zeilen; Hero-Untertitel „· Vorhersage {sub.horizon}" (Z.97) |
| `claude-code-handoff/.../jsx/screen-home-planning.jsx` | SOLL Planning-Modus (Banner, Weiter einrichten, Schnell anlegen, Laufende Vergleiche, **Archiv in `<Card padding={20}>`**) |

## Existing Patterns
- **Versand-Timeline:** JSX `homeCompareTimeline(sub)` baut 2 Zeilen: `Zuletzt · {lastSent}` (status sent) + `Nächster · {nextSend}` (status scheduled), je mit channels + „N Orte · {region}". Svelte hat dafür `BriefingTimelineRow` + `deriveNextSend` schon fertig.
- **lastSent-Quelle:** `ComparePreset.letzter_versand` (ISO-8601) ist echte Historie — kein Mock nötig. `top_ort_letzter_versand` als Top-Ort.
- **nextSend-Quelle:** `deriveNextSend(preset, now)` → Date; `formatNextSend()` → Anzeige-String. Bereits in CompareStatusRow im Einsatz.
- **Modus-Logik:** `mode = activeLiveTrip ? 'trip' : activePresets.length>0 ? 'compare' : 'planning'` (Z.49-51). Test-Konto auf Staging hat aktive Presets → immer `compare`-Modus → planning/trip nie live erreichbar (= der #579-Verifikations-Blocker).

## Dependencies
- Upstream: `deriveNextSend`/`formatNextSend` (cockpitHelpers568), `BriefingTimelineRow`, `letzter_versand`-Feld aus `/api/compare/presets`.
- Downstream: nur die Home-Seite rendert diese Outbox; keine weiteren Konsumenten.

## Existing Specs
- `docs/specs/modules/issue_579_home_screen.md` — Vorgänger-Spec (30%-Threshold-Divergenz dokumentiert)
- `docs/specs/modules/issue_571_home_cockpit_hero.md` — Compare-Hero + CompareStatusRow + `deriveNextSend`

## Befund je Punkt
- **Punkt 3 (Timeline):** Option (a) voll umsetzbar — alle Bausteine existieren. Platzhalter „Versand läuft automatisch gemäß Zeitplan." (Z.606-608) → 2 echte `BriefingTimelineRow` (Zuletzt aus `letzter_versand`, Nächster aus `deriveNextSend`). No-History-Fall: nur „Nächster"-Zeile (keine Fake-Daten). Compare-Hero „Nächster Versand: —" (Z.498) ebenfalls mit `formatNextSend` füllen.
- **Punkt 3 (horizon):** **Kein `ComparePreset.horizon`-Feld.** (`horizons` existiert nur pro Metrik, reduziert sich nicht auf einen Hero-Label.) Svelte omittet es heute bereits. AC: definieren oder ersatzlos streichen → **PO-Entscheidung.**
- **Punkt 1 (Planning-Fidelity):** Reale Divergenz: Archiv-Block ohne Card-Wrapper (JSX wrappt in `<Card padding={20}>`). Topbar-Divergenz (JSX „Guten Morgen, Gregor."/„vor der Reise" vs. unified PageHeader) ist bewusste #579-AC-7-Entscheidung → bleibt. SetupResumeCard-Eyebrow Anreicherung (Start-Countdown) optional.
- **Punkt 1 & 2 (Verifikation):** Eigentlicher Blocker — Staging-Test-Konto erreicht weder planning noch trip-Modus. Lösung: dedizierte Daten-Zustände auf Staging seeden (frisches/leeres Konto = planning; Konto mit heute-überspannendem Trip + abgeschlossenen Trips = trip-Modus), damit staging-validator echten DOM-Proof liefern kann.

## Risks & Considerations
- **Keine Fake-Daten:** Timeline nur aus echtem `letzter_versand`/berechnetem nextSend; fehlt Historie → Zeile weglassen.
- **Desktop byte-identisch halten** wo nicht Teil des Fix (Adversary char-by-char wie #636).
- **LoC-Limit 250:** Code-Anteil klein (Timeline-Helfer + Outbox-Wiring + Planning-Card ~80-120 LoC); Verifikations-Seeding ist Tooling/Test.
- **Multi-User:** Seeding-Konten müssen mandantengetrennt sein (eigene user_id), nie `default`.
