---
spec_file: docs/specs/modules/inbound_command_channels.md
spec_sha256: fdf94506340cc9de8bbadf9e6f1bb7c49f75fb82b2cc5032ff24f883e471a955
spec_frozen_sha256: d69ef94f1abd26d0257fc76847aaa3d76bdf19df6cb8615a443743ea5f59c31d
---

# PO-Briefing: fix-2252-spf-scope

- **Spec:** docs/specs/modules/inbound_command_channels.md
- **Issue:** #2252
- **Erstellt:** 2026-11-02

## Was gebaut wird

Die Absenderprüfung für Trip-Befehle per E-Mail wird so gehärtet, dass gefälschte Absender keine Befehle mehr auslösen können.

## Definition of Done

Gefälschte Mails fremder Absender werden stumm abgewiesen und ändern keinen Trip, echte Befehle von Nutzern funktionieren weiterhin, auch über Resend.

## Wie geprüft wird

Automatische Tests mit echten Server-Headern und zwei Nutzern prüfen Annahme und Abweisung; ob jeder Anbieter durchkommt, zeigt nur der Live-Test.

## Kritische Anmerkungen

- Strenger als bisher: Absender, deren Anbieter die Domain nicht sauber bestätigt (etwa manche Weiterleitungen), werden abgewiesen. Bewusst dokumentiert.
- Live-Gegenprobe gibt es nur für den Einschleus-Weg, nicht für die fremde Domain; diese ist nur per Test abgedeckt.
- Das Ticket wurde bewusst erweitert (Domain-Abgleich zusätzlich zum ursprünglichen Fehler); Ursprungsticket selbst nicht gelesen, nur die Analyse.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
