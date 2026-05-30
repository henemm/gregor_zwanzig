# Context: Issue #460 — Compare-E-Mail HTML-Template

## Request Summary

Das HTML-Template für den Compare-E-Mail-Versand soll vollständig zum Design-Bundle
(`screen-compare-email.jsx`) aufschließen: Winner-Banner mit Begründungs-Tags
(gut/warn/info), expliziter Header-Sektion (Zeitraum + Aktivitätsprofil) und korrekte
CE_PROFILES-Abbildung für alle 4 Aktivitätsprofile.

## Vorhandene Implementierung (Issue #253 ✅ geschlossen)

`src/output/renderers/email/compare_html.py` existiert bereits und ist voll integriert:

| Merkmal | Status |
|---------|--------|
| Pure Function `render_compare_html()` | ✅ implementiert |
| CE_PROFILES (4 Profile × primary/secondary) | ✅ implementiert |
| @media (max-width: 480px) Mobile-Layout | ✅ implementiert |
| Mobile-Karten (`.mobile-cards`, `.location-card`) | ✅ implementiert |
| Warnungs-Banner (G_WARNING) | ✅ implementiert |
| Dunkler Footer (G_INK) | ✅ implementiert |
| Profil-Eyebrow via `profile_signature()` | ✅ implementiert |
| Vergleichsmatrix mit Best-Value-Markierung | ✅ implementiert |
| Stunden-Verlauf Top-N | ✅ implementiert |
| Integration in `compare_subscription.py` | ✅ verdrahtet |
| Plain-Text-Fallback via `render_comparison_text()` | ✅ vorhanden |
| 9 Unit-Tests (alle grün) | ✅ passing |

## Lücken vs. Design-Bundle (Issue #460 Delta)

**1. Begründungs-Tags im Winner-Banner (NICHT implementiert)**
Das Design-Bundle (`screen-compare-email.jsx`) zeigt profilspezifische Tags im Winner-Banner:
```javascript
tags: [
  { tone: "good", label: "1 Ort über Wolken" },     // grün
  { tone: "warn", label: "Böen 26 km/h #2" },        // orange
  { tone: "info", label: "+12 cm Neuschnee #1" },    // neutral/blau
]
```
Die aktuelle `_render_winner_card()` zeigt nur Name + Score-Badge — keine Tags.

**2. Explizite Header-Sektion fehlt**
`screen-compare-email.jsx` hat einen prominenten Header-Block mit:
- Zeitraum: „9:00 – 16:00 Uhr" (time_window aus ComparisonResult)
- Aktivitätsprofil-Label: „Wintersport · Schnee" (aus profile_signature)
- Datum: Forecast-Datum

Aktuell zeigt der Renderer nur eine Eyebrow-Bar; Zeitraum erscheint nur im Footer.

**3. Profil-Mapping**
Design-Bundle: wintersport-glacier, alpine-touring, trail-running (kein Äquivalent zu WANDERN)
Python: WINTERSPORT, WANDERN, SUMMER_TREKKING, ALLGEMEIN
→ Mapping ist inhaltlich korrekt, Labels in der E-Mail sollten leserlich sein (z.B. "Wintersport · Schnee" statt roher Enum-String).

## Related Files

| Datei | Relevanz |
|-------|---------|
| `src/output/renderers/email/compare_html.py` | Hauptimplementierung — wird ERWEITERT |
| `src/output/renderers/email/design_tokens.py` | G_SUCCESS, G_WARNING, G_INK, G_SURFACE_1, G_PAPER |
| `src/output/renderers/email/profile_signature.py` | Liefert eyebrow-Text, icon_html, accent_hex |
| `src/output/renderers/email/html.py` | Muster (Trip-Briefing) — Strukturreferenz |
| `src/app/user.py:146` | LocationResult + ComparisonResult DTOs |
| `src/app/profile.py` | ActivityProfile Enum |
| `src/services/compare_subscription.py` | Versand-Orchestrierung (kein Änderungsbedarf) |
| `tests/tdd/test_compare_html_email.py` | 9 bestehende Tests + neue für Tags |
| `claude-code-handoff/soll-audit-2026-05-27/handoff-5/gregor-zwanzig/project/screen-compare-email.jsx` | Design-Referenz |

## Existing Patterns

- **Renderer-Pattern:** Pure Function → str (kein Netzwerk, keine Seiteneffekte), analog `html.py`
- **Token-Nutzung:** Alle Farben aus `design_tokens.py` (G_SUCCESS=#3a7d44, G_WARNING=#c8882a, G_INK=#1a1a18)
- **Tags-Tones:** `good` → G_SUCCESS-Hintergrund, `warn` → G_WARNING-Hintergrund, `info` → G_SURFACE_1-Hintergrund
- **Tags als Parameter:** Werden von `render_compare_html(..., winner_tags=[...])` übergeben (Backend berechnet sie, Renderer rendert nur)

## Dependencies

- **Upstream:** `ComparisonResult.winner`, `ComparisonResult.time_window`, `ActivityProfile`
- **Downstream:** `compare_subscription.py` ruft `render_compare_html()` auf (kein Änderungsbedarf)

## Existing Specs

- `docs/specs/compare_email.md` — v4.3 Gesamt-Spec (veraltet für HTML-Teil, Plain-Text noch gültig)
- `docs/specs/modules/issue_253_compare_email.md` — Modul-Spec v1.0 (Basis für #253-Impl.)

## Implementation Plan

1. **`_render_winner_card()`** erweitern: optionale `tags: list[dict]`-Parameter, jedes Tag rendert als Pill mit tone-abhängiger Farbe
2. **`render_compare_html()`** erweitern: neuer `winner_tags`-Parameter + explizite Header-Sektion (Zeitraum + Profil-Label)
3. **Neue Tests** für Begründungs-Tags und Zeitraum-Header
4. Kein Änderungsbedarf an `compare_subscription.py`

## Risks & Considerations

- Bestehende 9 Tests dürfen nicht brechen (tags-Parameter ist optional)
- `winner_tags`-Berechnung liegt außerhalb von #460 (kommt mit #457/#458)
- Design-Bundle hat kein "WANDERN"-Profil → WANDERN-Eyebrow-Label bleibt wie gehabt ("Wandern · Berge" oder ähnlich, kommt aus `profile_signature()`)
