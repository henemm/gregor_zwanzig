# Context: Issue #280 — Home Topbar Polish

## Request Summary

Issue #280 fordert UI-Polish für die Home-Seite: Datum als Eyebrow, TopoBg-Opacity reduzieren, Test-Briefing-Button als Ghost-Variante, Briefing-Status mit `--g-success`-Token, Empty-State-Link in Akzent-Orange.

## Stand nach #294-Implementierung

Issue #294 (Cockpit → Kachel-Übersicht, commit `27ce24f`) hat die Home-Seite grundlegend umgebaut. Dabei wurden die meisten #280-Anforderungen implizit erledigt:

| #280 Requirement | Status | Grund |
|-----------------|--------|-------|
| Datum als Eyebrow | ✅ Erledigt | `<Eyebrow>` in `+page.svelte` verwendet |
| H1 `text-3xl` | ✅ Erledigt | `.home__title` nutzt `--g-text-3xl` |
| TopoBg Opacity 0.10–0.15 | ✅ N/A | `TopoBg` komplett entfernt |
| Test-Briefing als ghost/xs | ✅ N/A | Button komplett entfernt |
| Briefing-Status `--g-success` | ✅ N/A | Status-Logik komplett entfernt |
| Empty-State Link `--g-accent` | ✅ Erledigt | `EmptyKachel` nutzt `var(--g-accent)` als Background |

## Verbleibende offene Punkte

### 1. H1 Text: "Guten Tag" vs. "Startseite"

| | Aktuell (`+page.svelte:24`) | Issue #280 | Anmerkung |
|--|--|--|--|
| Text | `Startseite` | `Guten Tag` | Produkt-Entscheidung |

Kein Nutzername in den Page-Daten (`+page.server.ts` liefert nur `trips[]` und `subscriptions[]`). "Guten Tag" wäre ein generischer Gruß ohne Personalisierung.

### 2. H1 `tracking-tight` fehlt

```css
/* aktuell (frontend/src/routes/+page.svelte:62) */
.home__title { font-size: var(--g-text-3xl); font-weight: 600; margin: 0; }

/* gefordert laut #280 */
.home__title { font-size: var(--g-text-3xl); font-weight: 600; letter-spacing: -0.025em; margin: 0; }
```

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/+page.svelte` | H1-Text + tracking-tight |
| `frontend/src/routes/_home/EmptyKachel.svelte` | ✅ bereits korrekt (kein Tailwind-Primary) |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | ✅ korrekt |
| `frontend/src/app.css` (Zeile 339) | ✅ Eyebrow-Token korrekt |

## Abhängigkeiten

- Kein Backend-Change nötig (kein Nutzername)
- Kein neues Token nötig (`letter-spacing` ist direkter CSS-Wert)
- `tracking-tight` in Tailwind = `letter-spacing: -0.025em`

## Risiken

- "Guten Tag" als H1 ist ungewöhnlich für eine App-Startseite — könnte Screen-Reader-Usern die Orientierung erschweren ("Guten Tag" ist kein Page-Titel)
- Falls später Personalisierung gewünscht wird ("Guten Tag, Henning"), muss `+page.server.ts` den Nutzernamen aus der Session laden

## Offene Produkt-Frage

Soll der H1 `Guten Tag` oder `Startseite` bleiben? Beide Optionen erfordern nur eine Zeile Code. Dieser Entscheid sollte vor der Implementierung geklärt werden.

## Existing Patterns

- Eyebrow-Einsatz: `frontend/src/routes/trips/+page.svelte`, `frontend/src/routes/compare/+page.svelte`
- `letter-spacing` in H1s: `frontend/src/routes/trips/+page.svelte` (prüfen ob dort auch tracking-tight)

## Changelog

- 2026-05-21: Kontext erstellt für Issue #280 — Stand: 1 AC offen (tracking-tight), 1 Frage offen (H1-Text)
