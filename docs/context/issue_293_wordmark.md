# Context: Issue #293 — Wordmark "gregor.zwanzig"

## Request Summary
Ersetzt den Plain-Text-Header "Gregor 20" (Inter-Tight bold) durch eine neue `<Wordmark />`-Komponente mit JetBrains Mono, Punkt in `--g-ink-faint` und "zwanzig" in `--g-accent`. Außerdem Dokumenttitel in `app.html` von "Gregor 20" auf "Gregor Zwanzig" ändern.

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte:55` | Desktop-Sidebar-Header `<h1>Gregor 20</h1>` → `<Wordmark size="md" />` |
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte:33` | Mobile-Top-Bar `<span>Gregor 20</span>` → `<Wordmark size="sm" />` |
| `frontend/src/app.html` | Kein `<title>`-Tag — muss `<title>Gregor Zwanzig</title>` erhalten |
| `frontend/src/lib/components/ui/wordmark/Wordmark.svelte` | **NEU** — Wordmark-Komponente (existiert noch nicht) |
| `frontend/src/lib/components/ui/sidebar/index.ts` | Export ggf. erweitern (falls Wordmark auch dort exportiert wird) |

## Weitere "Gregor 20"-Vorkommen (außerhalb AC)
- `frontend/src/routes/login/+page.svelte:12` — `<h1>Gregor 20</h1>` (Login-Seite, nicht in Issue-AC, aber naheliegend zu aktualisieren)
- `frontend/src/routes/trips/[id]/+page.svelte:20` — `<title>{trip.name} — Gregor 20</title>` (Seiten-Titel, nicht in AC)

## Vorhandene Design-Tokens (alle verfügbar)
- `--g-font-data` → `'JetBrains Mono', ui-monospace, monospace`
- `--g-font-ui`   → `'Inter Tight', system-ui, sans-serif`
- `--g-ink`       → `#1a1a18`
- `--g-ink-faint` → `#9c9a90`
- `--g-accent`    → `#c45a2a`
- JetBrains Mono bereits in `app.html` via Google Fonts geladen (weight 400;500;600)

## Komponentenstruktur (Variante B laut Issue)
```
<a href="/" aria-label="...">
  <span class="row">
    <span>gregor</span><span class="sep">.</span><span class="second">zwanzig</span>
  </span>
  <span class="sub">v0.20 · wetter-briefing</span>  ← nur bei size md/lg
</a>
```

Größen: sm (14px, kein Subtitle), md (18px, mit Subtitle), lg (24px, mit Subtitle)

## Risiken & Hinweise
- **Kein wordmark/-Verzeichnis vorhanden** — muss angelegt werden
- **app.html hat keinen `<title>`** — muss hinzugefügt werden (Svelte-Head-Hierarchie: app.html → +layout → +page)
- **Login-Seite und trip-Detailseite** haben auch "Gregor 20" — AC deckt sie nicht explizit ab, aber sollte in Spec geklärt werden
- Dark Mode: Sidebar-Farben werden per CSS-Var inline gesetzt — Wordmark-Tokens greifen korrekt in beiden Modi
- Keine Backend-Änderungen nötig — rein frontend
