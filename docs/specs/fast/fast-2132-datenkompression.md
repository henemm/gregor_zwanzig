# Mini-Spec: #2132 Datenverbrauch messen + Kompression der Daten-Nachladungen einschalten

## Was ändert sich
- Vorher-Messung: Netzwerk-Mitschnitt einer typischen Handy-Sitzung gegen Produktion
  (Login → Trip öffnen → Briefing ansehen → Ortsvergleich öffnen), übertragene Bytes summiert
  und im Ticket #2132 dokumentiert (Bezugszahl).
- `henemm-infra/nginx/nginx.conf`: `gzip_types` aktivieren (Zeile 53 ist auskommentiert und
  enthält bereits `application/json` — der für die Daten-Nachladungen relevante Content-Type).
  Selbst committen in `henemm-infra` (keine MQ-Nachricht an `infra` — [[reference_all_parallel_sessions_are_claude_code]]).
  BREACH-Abwägung wird im Commit/Ticket sichtbar dokumentiert (Kompression bei
  Anmelde-Bezug ist theoretisch angreifbar, hier aber nicht ausnutzbar, da kein Angreifer
  eigenen Inhalt in unsere Antworten einschleusen kann).
- Nachher-Messung: dieselbe Sitzung, dieselbe Methode, Vergleichszahl im Ticket #2132.

## Was darf sich nicht ändern
- Programmdateien-Caching (`cache-control: public,max-age=31536000,immutable`, Brotli) bleibt
  unangetastet — bereits gut, siehe Ticket.
- Keine Kompression auf der Strecke Go-Dienst ↔ Frontend (localhost) — dort wirkungslos,
  nicht Gegenstand dieser Änderung.
- Kein Code in `gregor_zwanzig` selbst (weder `src/`, `api/`, `internal/`, `frontend/`).

## Manuelle Test-Schritte
1. Vorher-Mitschnitt: Login + Trip öffnen + Briefing ansehen + Ortsvergleich öffnen gegen
   Produktion (`https://gregor20.henemm.com`), Netzwerk-Bytes der Daten-Antworten summieren.
2. `gzip_types` in `henemm-infra/nginx/nginx.conf` aktivieren, `nginx -t` + reload, in
   `henemm-infra` committen.
3. Nachher-Mitschnitt: identische Schrittfolge, Bytes summieren, `Content-Encoding: gzip` an
   den Daten-Antworten in den Response-Headern verifizieren.
4. Vorher/Nachher-Zahlen ins Issue #2132 eintragen.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Kein automatisierter Test — reine Infrastruktur-/Messaufgabe ohne Code in diesem Repo.
  Nachweis ist die dokumentierte Vorher/Nachher-Messung (siehe manuelle Test-Schritte).
