---
spec_file: docs/specs/modules/infra_3286_mcp_server_einrichtung.md
spec_sha256: 7fda557099b211b6a23b725ecd2a43d69d2cd3d77d62b10d4cb22ca2bf24e357
spec_frozen_sha256: dae26c110cee9d680d14ad924986514ded9d2eeb52d2842d7eaa95bb795c80f4
---

# PO-Briefing: infra-3286-mcp-server

- **Spec:** docs/specs/modules/infra_3286_mcp_server_einrichtung.md
- **Issue:** #3286
- **Erstellt:** 2026-11-24

## Was gebaut wird

Der Wetter-Konnektor für die Claude-App wird auf Staging erreichbar und freigeschaltet, anschliessend auch in Produktion.

## Definition of Done

Der PO verbindet „Gregor Wetter“ auf Staging in der Claude-App und erhält eine Wetterantwort; Produktion ist freigeschaltet, Selbsttest bestanden.

## Wie geprüft wird

Ein Prüfskript belegt von aussen Öffnung, Anmeldung und Ablehnung fremder Konten; Zeitlimit und Weitergabe der Client-Adresse bleiben ungemessen.

## Kritische Anmerkungen

- Abweichung: Staging wird für das Testkonto „default“ freigeschaltet, nicht für das Konto des PO per E-Mail.
- Zusätzlich gebaut: Prüfskript und Tests, rund 345 Zeilen in zwei Pull Requests, nicht verlangt.
- Die Anmeldeseite bleibt hinter der Zugangsschranke; ob die Claude-App das zulässt, ist offen (Ausweg Desktop-Browser).

## Freigabe-Frage

Darf Staging für das Testkonto „default“ statt für Ihr eigenes Konto freigeschaltet werden?

## Ampel

Ampel: rot
