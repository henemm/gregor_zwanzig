---
entity_id: issue_646_compare_detail_fidelity
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [frontend, design-compliance, compare]
---

# Compare-Detail-Hub Fidelity v2 (#646)

## Approval
- [x] Approved (PO 2026-06-07)

## Purpose
Verifikation, dass der Live-Compare-Detail-Hub `/compare/[id]` der aktuellen
(Signal-freien) Design-Quelle `screen-compare-detail.jsx` entspricht. Substanz ist
seit #582 live; #643 war wegen veralteter Vorlagen (Signal + altes Einseiten-Layout)
nicht prüfbar. SOLL wurde aus der kanonischen JSX neu gerendert.

## Source
- JSX (kanonisch, Signal-frei): `claude-code-handoff/current/jsx/screen-compare-detail.jsx`
- Frischer SOLL: `claude-code-handoff/current/soll/G-compare-detail.png`

## Acceptance Criteria

**AC-1:** Gegeben ein eingeloggter Nutzer mit mindestens einem Vergleich, wenn er auf `/compare` eine Vergleichs-Kachel anklickt, dann landet er auf dem Detail-Hub `/compare/[id]` (NICHT auf `/login`) — Erreichbarkeit per Klick.

**AC-2:** Gegeben der Detail-Hub ist offen, wenn die Seite rendert, dann zeigt der Kontext-Header die Breadcrumb „ORTS-VERGLEICHE / HUB", den Vergleichsnamen als Überschrift, eine Status-Pill und den Untertitel „Region · Profil · N Orte".

**AC-3:** Gegeben der Detail-Hub ist offen, wenn die Tab-Leiste rendert, dann sind die sechs Tabs „Übersicht · Orte (N) · Idealwerte · Layout · Versand · Vorschau" sichtbar und der aktive Tab ist unterstrichen.

**AC-4:** Gegeben der Übersicht-Tab ist aktiv, wenn er rendert, dann zeigt der Status-Streifen die vier Kennzahlen „Status", „Nächster Versand", „Zuletzt raus", „Kanäle" und darunter vier Zusammenfassungs-Karten („Orte", „Idealwerte", „Layout pro Kanal", „Versand") je mit „Bearbeiten →".

**AC-5:** Gegeben irgendein Tab des Hubs, wenn der Nutzer ihn betrachtet, dann erscheint nirgends der Kanal „Signal" — Kanäle sind ausschließlich Email/Telegram/SMS (#610).

**AC-6:** Gegeben ein eingeloggter Nutzer öffnet `/compare/[id]` per direktem Deep-Link (Adresszeile), dann erreicht er den Detail-Hub (NICHT `/login`). Klärt das in der Voruntersuchung beobachtete „Detail → Login"-Bounce: ist es reproduzierbar, ist es ein eigener Bug.
