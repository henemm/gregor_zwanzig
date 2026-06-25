# ADR-0008: Lesbarkeit/Kontrast vor weicher Optik

- **Status:** Akzeptiert
- **Datum:** 2026-05-25
- **Bezug:** `CLAUDE.md` → „Design-Leitprinzipien"; `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md`

## Kontext

Das Produkt ist ein **Briefing-Werkzeug für Wetter-/Tourenentscheidungen**. Inhalte werden oft
unter Zeitdruck und in schlechten Lichtsituationen (draußen, Sonne, kleines Display) gelesen. Es gab
wiederkehrende Gestaltungs-Konflikte zwischen „warmer, weicher Optik" und „klarer Lesbarkeit".

## Entscheidung

Bei **jedem** Konflikt zwischen weicher Optik/Atmosphäre und klarer Lesbarkeit **gewinnt
Lesbarkeit**. Konkrete, verbindliche Konsequenzen:

- **Karten = weiß** (`--g-card #ffffff`) auf warmer Off-White-Page (`--g-paper #f6f4ee`) — kein
  beiges Card-on-beige.
- **Text-Kontrast:** echter Text mindestens WCAG-AA (4.5:1). `--g-ink-4` ist **nur** für
  Placeholder/Disabled, nie für Captions/Help-Text/Daten-Labels (nur 2,85:1 auf Weiß).
- **Akzentfarben sparsam** und nie als alleiniger Lesbarkeits-Träger — Form, Position und
  Mono-Strecke tragen mit.

## Verworfene Alternativen

- **Durchgängig warme, beige Flächen** (Card-on-beige) — verworfen: zu geringer Kontrast, Inhalt
  unter realen Außenbedingungen schwer lesbar.
- **Ästhetik über Lesbarkeit** im Einzelfall abwägen — verworfen: führt zu inkonsistenten
  Entscheidungen; das Prinzip steht **über** ästhetischen Präferenzen.

## Konsequenzen

- **Positiv:** Verlässliche Lesbarkeit in jeder Lichtsituation; klare, nicht verhandelbare Regel
  für Design-Reviews.
- **Negativ / Preis:** Weniger gestalterischer Spielraum für „weiche" Optik.
- **Folgepflichten:** Vor jeder Frontend-Arbeit gilt das Design-System (`docs/design-system/`) als
  Autorität. Ein Kontrast-Audit (#16) begleitet die Umsetzung. Token-Bedeutungen (z. B. `--g-ink-4`)
  dürfen nicht zweckentfremdet werden.
