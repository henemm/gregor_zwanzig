# ADR-0090: Entwarnung bei amtlichen Warnungen

- **Status:** Akzeptiert
- **Datum:** 2026-10-16
- **Bezug:** GitHub-Issue #1441 Scheibe S2, Spec `docs/specs/modules/feat_1441_s2_entwarnung.md`;
  ergänzt ADR-0016 (additiver Warntyp), ADR-0043 (Grundsatz Entwarnung, bisher nur
  hauseigene Wetterwerte), ADR-0089 (Lawinen-Lagebericht, zweite Skala); nutzt ADR-0046
  (Kanal-Schwelle), ADR-0082 („nicht bestimmbar ≠ Entwarnung"), ADR-0086 (Erfolg = Zustellung)

## Kontext

Beide Alarm-Flächen (Trip und Ortsvergleich) meldeten bei amtlichen Warnungen nur „neu"
oder „gestiegen". Sank oder endete eine Warnung, blieb es still, und das Melde-Gedächtnis
behielt den Höchstwert. Der PO hat am 13.10.2026 entschieden: Entwarnung für ALLE amtlichen
Quellen, über alle vier Kanäle, in beiden Flächen — mit der Dringlichkeit des ALTEN Werts.
Am 15.10.2026: hat ein zugestelltes Briefing die niedrigere Lage schon gezeigt, gilt der
Nutzer als informiert.

Eine Schein-Entwarnung ist sicherheitskritisch: der Wanderer läuft in eine fortbestehende
Gefahr. Die Aggregat-Kennung „nicht abrufbar" gleicht Teilausfall aus (eine leere zweite
Quelle kompensiert den Ausfall der meldenden), der Gedächtnis-Schlüssel enthält den
Zeitraum (Neuausgabe = neuer Schlüssel), und das Abfragefenster verschiebt sich (vergangene
Etappe, Tagesfenster-Ende).

## Entscheidung

1. **Variante C (Pro-Quelle-Gesundheit):** `get_official_alerts_with_sources()` liefert
   `{quelle: (ok, alerts)}` vor dem Quellen-Merge, nach dem Fensterfilter. `ok` nur ohne
   Exception, `fetch_failed`, `not_covered` und `fetch_incomplete`. Die Alarm-Pfade holen
   das Pro-Quelle-Ergebnis aus DEMSELBEN Abruf über einen Kontext-Rückkanal
   (`collect_source_queries`). Verglichen wird auf dem Satz der MELDENDEN Quelle; ein
   Wechsel der besten Quelle ist nie eine Entwarnung.
2. **Gedächtnis-Schema (abwärtskompatibel):** Einträge tragen zusätzlich `source`
   (Registry-Name), `scope` (Orte der Meldung: gerundete Koordinate im Trip, Orts-ID im
   Ortsvergleich), `level` (alte Stufe der Dringlichkeits-Skala), `absent_since`, `ended_at`.
   Einträge ohne `source` oder `scope` (Alt-Bestand) erzeugen nie eine Entwarnung.
3. **Erkennung über Identität + Gefahr + Überlappung** (nicht über den vollen Schlüssel),
   nur am selben Ort und nur im aktuell abgefragten Fenster: „gesenkt" sofort, wenn die
   meldende Quelle eine niedrigere Stufe liefert; **Variante D** „vorzeitig beendet" erst,
   wenn die gesunde Quelle die Warnung in zwei aufeinanderfolgenden Läufen nicht mehr
   liefert (`absent_since`). Taucht sie dazwischen wieder auf, wird `absent_since` gelöscht.
4. **Planmäßiger Ablauf ist keine Entwarnung** (Tech-Lead-Entscheid): `valid_to` erreicht →
   still; ein GC entfernt abgelaufene `official_alert:`-Einträge.
5. **Dringlichkeit nach altem Wert** an der Wirkstelle (`split_by_threshold`):
   `urgency_from_official_transition(alt, neu)`; Ortsvergleich Stapel-Max über Warnungen und
   alte Stufen. Retry-Backoff mit eigener Kennung; das Ereignis-Identitäts-Gate filtert nur
   Warnungen, nie Entwarnungen.
6. **Schreibweg nach Zustellung** (ADR-0086), getrennt vom Revision-Merge (der weiter `max`
   behält): „gesenkt" senkt `last_reported_value`/`level`, „beendet" setzt den Tombstone
   (`ended_at`, Rang 0). Zugestellt heißt: ein Kanal, dessen Nachricht die Entwarnung
   tatsächlich enthielt (SMS-Kürzung kann sie verdrängen), hat zugestellt.
7. **Briefing senkt das Gedächtnis** (PO 15.10.): nach Zustellung (nie Ad-hoc) und nur bei
   gesunder meldender Quelle senkt das Briefing auf die gezeigte Stufe bzw. setzt den
   Tombstone; eine noch gezeigte Warnung löscht `absent_since`. Dieselbe Erkennung wie im
   Alarm-Pfad, ohne Zwei-Lauf-Bestätigung (das Briefing hat informiert).
8. **Darstellung nur als Daten:** Mail-Abschnitt „Entwarnung" nach den Warnungen
   („Stufe 4 → 2" bzw. „beendet"), Betreff mit „Entwarnung", Telegram gleich, SMS/Premium-SMS
   eigener GSM-7-Block `+` mit `>` (`+TS:H>L`, `+AV4>2`, `+TS:H>0`). Keine Handlungsempfehlung.
9. **MeteoAlarm `AllClear` bleibt verworfen:** die Entwarnung trägt allein das Verschwinden
   bei gesunder Quelle bzw. die explizite Absenkung.

## Konsequenzen

- Alt-Einträge vor S2 bekommen einmalig keine Entwarnung (bewusst still).
- „Beendet" kommt ein Prüfintervall später als „gesenkt".
- Der Ortsvergleich-Briefing-Pfad erhält die Pro-Quelle-Gesundheit nicht aus der parallel
  rechnenden Vergleichs-Engine; er fragt sie nach Zustellung erneut ab (gecachte Abrufe) und
  verknüpft sie mit dem Aggregat „nicht abrufbar" — zeigte das Briefing „nicht abrufbar",
  senkt es nie.
- Erfolgreich-aber-fälschlich-leere Antworten über zwei Läufe sind nicht erkennbar; das
  Restrisiko ist durch die Zwei-Läufe-Bestätigung klein, nicht null.
