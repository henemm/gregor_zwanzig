#!/bin/bash
# Epic-Issues auf GitHub anlegen
# Ausfuehren mit: bash docs/project/create_epic_issues.sh
# Voraussetzung: gh CLI installiert und authentifiziert

REPO="henemm/gregor_zwanzig"

echo "Erstelle 5 Epic-Issues auf GitHub..."

gh issue create --repo "$REPO" --label "enhancement" \
  --title "Epic: Low-Connectivity Delivery (SMS/Satellite)" \
  --body "$(cat <<'BODY'
## Ziel

Wetter-Reports ueber SMS und Satellit zustellen — fuer Situationen ohne Internet.

## Business Value

Auf GR20/GR221 oft nur GSM verfuegbar, kein Internet. SMS ist Game-Changer. Garmin inReach ermoeglicht Empfang ueber Baumgrenze.

## Feature-Issues

- [ ] #10 — F1: SMS-Kanal
- [ ] #18 — F9: Satellite Messenger (Garmin inReach)

## Dependencies

- Kompakt-Summary (F2) — done (Enabler fuer alle Kanaele)
BODY
)"
echo "Epic: Low-Connectivity Delivery erstellt"

gh issue create --repo "$REPO" --label "enhancement" \
  --title "Epic: Enhanced Trip Reports" \
  --body "$(cat <<'BODY'
## Ziel

Reports mit mehr Kontext — Trends, Biwak-Details, Trip-Briefing.

## Business Value

Mehrtages-Strategie und Ruhetag-Planung. Zelter bekommen relevante Nacht-Details. Trip-Briefing am Vorabend gibt Gesamtueberblick.

## Feature-Issues

- [ ] #15 — F4: Trip-Briefing (Kompakt-Tabelle)
- [ ] #16 — F5: Biwak-/Zelt-Modus
BODY
)"
echo "Epic: Enhanced Trip Reports erstellt"

gh issue create --repo "$REPO" --label "enhancement" \
  --title "Epic: Asynchrone Trip-Steuerung" \
  --body "$(cat <<'BODY'
## Ziel

Trip unterwegs per Kommando anpassen — ohne Web-UI.

## Business Value

Innovativstes Feature. Asynchrone Steuerung per SMS/Email-Reply. Passt perfekt zum Low-Connectivity-Paradigma.

## Feature-Issues

- [ ] #17 — F6: Trip-Umplanung per Kommando

## Dependencies

- #10 (F1: SMS-Kanal) fuer SMS-Reply
- Email-Reply als Einstieg
BODY
)"
echo "Epic: Asynchrone Trip-Steuerung erstellt"

gh issue create --repo "$REPO" --label "enhancement" \
  --title "Epic: Advanced Risk & Terrain Analysis" \
  --body "$(cat <<'BODY'
## Ziel

Terrain-bewusste Warnungen und Lawinen-Daten fuer Skitouren.

## Business Value

Lawinen-Integration fuer die naechste Wintersaison. SLF/EAWS Adapter.

## Feature-Issues

- [ ] #19 — F10: Lawinen-Integration (SLF/EAWS)

## Bereits erledigt

- Wind-Exposition / Grat-Erkennung (F7) — done
- Risk Engine Daten-Layer (F8) — done
BODY
)"
echo "Epic: Advanced Risk & Terrain erstellt"

gh issue create --repo "$REPO" --label "enhancement" \
  --title "Epic: Tech Stack Migration (Python/NiceGUI → Go/SvelteKit)" \
  --body "$(cat <<'BODY'
## Ziel

Tech-Stack von Python/NiceGUI auf Go (Backend) + SvelteKit (Frontend) migrieren.

## Business Value

AI-gestuetzte Entwicklung produziert mit Go signifikant weniger Fehler (Compile-Time Safety, konsistente Trainingsdaten). SvelteKit loest Multi-User als Nebenprodukt.

## Feature-Issues

- [ ] #12 — F13: Multi-User mit Login (wird durch M5 geloest)
- [ ] #21 — BUG-TZ-01: Timezone Mismatch (wird durch M2 geloest)
- [ ] #22 — M1: Go-Backend Setup
- [ ] #23 — M2: Provider portieren
- [ ] #24 — M3: Risk Engine portieren
- [ ] #25 — M4: Formatter + Scheduler portieren
- [ ] #26 — M5: SvelteKit Frontend Setup + Auth
- [ ] #27 — M6: Frontend Pages portieren
- [ ] #28 — M7: Cutover

## Referenzen

- Story: docs/project/backlog/stories/sveltekit-migration.md
BODY
)"
echo "Epic: Tech Stack Migration erstellt"

echo ""
echo "Fertig! 5 Epic-Issues erstellt."
