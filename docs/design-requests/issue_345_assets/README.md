# Design-Quellen — Wetter-Editor Konsolidierung (#345 / Epic #304)

Diese JSX-Dateien sind das **Handoff-Bundle von Claude Design** (claude.ai/design) zur
Wetter-Editor-Konsolidierung, exportiert am 2026-05-24. Es sind **React/JSX-Prototypen**
(Mockup-Welt), keine Produktions­komponenten — die Umsetzung erfolgt in SvelteKit, visuell
getreu, aber unter Wiederverwendung bestehender Svelte-Komponenten.

| Datei | Inhalt |
|-------|--------|
| `screen-weather-consolidation.jsx` | Page-Komposition: Empfehlungs-Übersicht + alle Kontexte/Entscheidungen (Einstieg) |
| `organisms.jsx` | `MetricsEditor`, `PresetRail`, `MetricBucket`, `MetricOffShelf`, `ChannelPreviewStrip`, `MetricsEditorContextBar` |
| `molecules.jsx` | `HorizonChips`, `ScoreToggle`, `MetricEditorRow`, `ChannelLimitChip`, `ChannelPreviewCard` |
| `atoms.jsx` | `Segmented` u. a. Atome |
| `tokens.css` | Design-Tokens (abgleichen mit `frontend` / Design-System) |

## Kern-Idee

Eine kanonische `MetricsEditor`-Komponente mit drei Kontexten:
`context="tour"` (HorizonChips heute/morgen/übermorgen) · `context="ort"` / `context="abo"`
(ScoreToggle „im Score / nicht im Score" statt Horizonte).

## Was zu #345 gehört (Konsolidierungs-Kern, etappenweise)

1. Innere Editor-Komponente extrahieren (DRY-Kern aus `WeatherMetricsTab`).
2. Bearbeiten-Maske entkoppeln: Wetter read-only + Link „Im Wetter-Tab bearbeiten →",
   `EditWeatherSection.svelte` löschen.
3. Schnell-Fenster (`WeatherConfigDialog`) streichen → Wetter-Profil-Chip auf der Kachel.
4. Kontext-Bewusstsein tour/ort/abo (Horizonte bei Ort/Abo ausblenden).

## Was NICHT zu #345 gehört (eigene Folge-Issues)

Das Design führt drei **neue** Konzepte ein, die Schema-Migrationen bzw. andere Epics berühren —
festgehalten als eigene Issues (siehe GitHub, verlinkt aus #345):

- **3-Stufen-Auswahl** (Spalte / Detail / Aus) + frei sortierbare Spalten-Reihenfolge.
- **Score-Zugehörigkeit pro Metrik** für Orte/Abos (greift in Compare-Scoring ein).
- **Kanal-Vorschau** (Spalten-Limits Email/Signal/Telegram/SMS; baut auf Output-Layout #360 auf).

Das vollständige Bundle (12 Chat-Transkripte, alle Screens, Screenshots) wurde nicht eingecheckt;
relevante Wetter-Dateien liegen hier.
