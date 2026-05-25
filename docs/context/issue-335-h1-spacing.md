# Context: issue-335-h1-spacing

## Request Summary
Im Tour-Kopf auf `/trips/[id]` rendert die H1 als `"KHW ·Karnischer Höhenweg"` — das
Leerzeichen **nach** dem Trenn-Mittelpunkt fehlt (asymmetrisch). Soll:
`"KHW · Karnischer Höhenweg"`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte:69` | Die fehlerhafte H1-Zeile mit shortcode + ` · ` + name |
| `docs/specs/modules/issue_302_trip_detail_page.md:148` | Spec-Soll: `{trip.shortcode} · {trip.name}` (Leerzeichen beidseitig) |

## Root Cause
```svelte
{#if trip.shortcode}<span class="h1-shortcode">{trip.shortcode}</span> · {/if}{trip.name}
```
Svelte trimmt das nachgestellte Leerzeichen des Text-Nodes `" · "` direkt vor dem
`{/if}`-Block-Ende. Gerendert wird `"KHW ·" + "Karnischer..."`.

## Existing Patterns
- **Zeile 80 (meta-line)** nutzt dasselbe Muster (`{#if dateRange}<span>...</span> · {/if}...`),
  ist aber **nicht** betroffen: Container `.meta-line` ist `display:flex; gap:0.25rem;` — der
  bare Text-Node `·` wird zum anonymen Flex-Item, Abstand kommt aus dem Gap. Die H1 ist ein
  normaler Inline-Block ohne Flex → dort wirkt das getrimmte Leerzeichen sichtbar.
- Fix-Ansatz laut Issue: `&nbsp;` nach dem Mittelpunkt (geschütztes Leerzeichen entgeht dem
  Whitespace-Trimming) oder Separator als eigenes Element.

## Dependencies
- Upstream: `Trip.shortcode`, `Trip.name` (Datenmodell, optional shortcode)
- Downstream: nur visuelle Darstellung der H1 — keine Logik, kein Backend

## Existing Specs
- `docs/specs/modules/issue_302_trip_detail_page.md` — definiert die H1-Struktur (Zeile 148)

## Risks & Considerations
- **Minimal-Fix**, reine Frontend-Kosmetik, keine Logik-/Backend-Änderung.
- **Kein** existierender TripHeader-Test — Fix sollte mit einem RED-Test abgesichert werden,
  der die korrekte H1-Textausgabe `"KHW · …"` prüft (kein getrimmtes Leerzeichen).
- **Parallel-Session-Hygiene:** Tree enthält uncommittete Fremd-Arbeit (`ChannelPreviewBlock.svelte`
  = #376, golden-emails, e2e_verified). Beim Commit NUR `TripHeader.svelte` stagen, niemals `git add -A`.
- Zeile 80 (meta-line) NICHT „mit-fixen“ — funktioniert dank Flex korrekt; unnötige Änderung vermeiden.
