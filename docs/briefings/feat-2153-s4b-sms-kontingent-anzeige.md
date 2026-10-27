---
spec_file: docs/specs/modules/sms_daily_usage_anzeige.md
spec_sha256: 531a12b4266ea2a5fad5e50ec4a1ac318703c2854c1e6c3a4c989dcb37d1fe25
---

# PO-Briefing: feat-2153-s4b-sms-kontingent-anzeige

- **Spec:** docs/specs/modules/sms_daily_usage_anzeige.md
- **Issue:** #2412 (Sammel-Issue #2153)
- **Erstellt:** 2026-09-25

## Was gebaut wird

Nutzer sehen auf ihrer Kontoseite ihr tagesaktuelles SMS- und Premium-SMS-Kontingent als "X von Y".

## Definition of Done

Kontoseite zeigt korrekten Verbrauch beider Kanäle an, bleibt aber vollständig nutzbar, wenn der interne Server ausfällt.

## Wie geprüft wird

Echte Testabrufe mit zwei Nutzern und vorbereiteten Zählerständen belegen korrekte, getrennte Anzeige — nicht die Optik selbst.

## Kritische Anmerkungen

- Angezeigte Zahl ist das volle Limit, nicht das tatsächlich für Briefings nutzbare Kontingent — ein Zusatztext erklärt den Unterschied.
- Bei gesperrtem Kanal (z.B. Gratis-Tarif) erscheint gar kein Hinweis — sieht aus wie ein Fehler.
- Anzeige aktualisiert sich nicht automatisch — nach einer SMS bleibt der alte Stand sichtbar bis zum Neuladen.

## Freigabe-Frage

Sind diese drei Entscheidungen so richtig: volles statt nutzbares Kontingent zeigen, gesperrte Kanäle ohne Hinweis, keine Live-Aktualisierung?
