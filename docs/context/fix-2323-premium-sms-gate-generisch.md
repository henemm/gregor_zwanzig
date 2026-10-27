# Context: fix-2323-premium-sms-gate-generisch

## Request Summary

Issue #2323, überarbeitet nach PO-Grundsatzdiskussion (14.09.2026): Die Erkennung eingehender
Premium-SMS-Nachrichten (`GARMIN_MARKER = "inreachlink.com"`) prüft den falschen Sachverhalt —
einen abschaltbaren Garmin-Text statt der strukturell immer vorhandenen Zielnummer (`to`-Feld).
Das führt dazu, dass Nutzer mit deaktivierter Garmin-Kartenlink-Einstellung dauerhaft und
lautlos ignoriert werden (Ursprung #2322). Ziel: das Akzeptanz-Gate korrigieren, den
Verknüpfungscode auf ein leichter tippbares Format umstellen, und ADR-0049 entsprechend
ergänzen — OHNE eine neue Provider-Abstraktion zu bauen (die Architektur ist am
Transport-Layer bereits geräteneutral, sobald das Gate korrigiert ist).

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/inbound_sms_reader.py` | Enthält das fehlerhafte Gate (`GARMIN_MARKER not in text`, Zeile 212) und `split_link_code()` (Zeile 78-101), die den Verknüpfungscode vom Befehlstext trennt |
| `internal/handler/premium_sms_connect.go` | Go-Endpunkt `/api/internal/premium-sms-learn` — enthält die BEREITS VORHANDENE Auflösungslogik (Code-Match `resolvePremiumSmsTarget` Zeile 169-183, "frischer Treffer ohne Code" Zeile 71-83 mit bekannter Ambiguitäts-Lücke, separat unter #2154 gemeldet) |
| `internal/handler/premium_sms_link_code.go` | Definiert `premiumSmsLinkCodeAlphabet` (Zeile 36, aktuell 31 Zeichen, 7-stellig) — muss für das neue Format geändert werden |
| `internal/handler/premium_sms_ratelimit.go` | Globale, nie zurückgesetzte Ratebremse (10 Fehlversuche) — bei kleinerem Schlüsselraum wichtiger, siehe #2153 |
| `tests/unit/test_inbound_sms_reply_learning.py` | AC-2 (`test_message_without_marker_is_ignored`, Zeile 202-220) prüft explizit das AKTUELLE (zu ändernde) Verhalten: Nachricht ohne Marker löst KEINEN Lernaufruf aus. Muss im Zuge des Fixes umgeschrieben werden — testet sonst veraltetes Verhalten. Enthält bereits eine `_private_message`-Fixture mit `to=SERVICE_NUMBER`, aber Alltagstext ohne Code (Zeile 64-71) |
| `tests/tdd/test_premium_sms_kommandopfad.py` | 11/11 grün, echte Zwei-Nutzer-Tests für den Kommandopfad (Issue #2184). Nicht betroffen vom Gate-Fix selbst, aber Referenz für Testmuster (kein Mock-Theater, echte Objekte) |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | Zeile 28-29: feste Dienstnummer `4916092172595` als Absender, gelernte Rückadresse als Empfänger. Zeile 56: normale SMS nutzt diese Nummer nachweislich nie. Braucht Ergänzung zur Gate-Korrektur |
| `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` | v1.5, Zeile 173 enthält den ECHTEN gemessenen Produktions-Journal-Eintrag (`to":"4916092172595"`, Journal-ID `5283665`, 2026-08-10) — Primärbeleg für das `to`-Feld |
| `docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md` | Aktuelles 7-Zeichen-Code-Format, muss auf das neue Format aktualisiert werden |

## Der eigentliche Fix (verfeinert gegenüber der ersten Idee in #2323)

**Nicht nur** `GARMIN_MARKER`-Check durch `to == SERVICE_NUMBER`-Check ersetzen — das allein
würde `test_message_without_marker_is_ignored`s Gegenbeispiel (Alltagstext an dieselbe Nummer,
kein Code, unbekannter Absender) ungefiltert an den Lern-Endpunkt weiterreichen.

**Richtiger Schnitt:** Das Python-seitige Content-Gate (`GARMIN_MARKER not in text`) entfällt
ersatzlos für die Frage "wird überhaupt ein Lernaufruf versucht" — stattdessen entscheidet
weiterhin (wie heute schon für den Erfolgsfall) der **bereits vorhandene** Go-Endpunkt, ob die
Nachricht einem Konto zugeordnet werden kann (Code-Match ODER bekannte Rückadresse). Eine
Nachricht ohne gültigen Code und von unbekannter Nummer bekommt dort schon heute ein `409` und
wird als "abgelehnt" gezählt (Issue #2154 AC-11), OHNE eine Antwort-SMS auszulösen (kein
Kosten-/Abuse-Risiko durch zufällige Fremdnachrichten an die Nummer).

`message.get("to")` muss dennoch geprüft werden (Verteidigung, dass wirklich nur Nachrichten an
UNSERE Dienstnummer verarbeitet werden — auch wenn heute laut ADR-0049 keine andere Nummer auf
diesem seven.io-Konto empfangsfähig ist).

`split_link_code()`s Nutzung von `GARMIN_MARKER` zum reinen Text-Zerlegen (Link+Koordinaten vom
Befehl abschneiden) bleibt unverändert — das ist keine Zulassungsentscheidung, nur Textparsing,
und funktioniert auch ohne Marker im Text (dann bleibt der gesamte Text der Befehl).

## Code-Format-Änderung (PO-Entscheid 14.09.)

Alt: 7 Zeichen aus `A-HJKMNP-Z2-9` (`internal/handler/premium_sms_link_code.go:36`,
`inbound_sms_reader.py:75`).
Neu: fester Präfix `XX` (case-insensitive) + 3 Buchstaben (ohne I/L/O) + 3 Ziffern (ohne 0/1),
z.B. `XXdrt249`. Muss in BEIDEN Sprachen synchron geändert werden (Go generiert, Python matcht
per Regex). Der feste Präfix macht die RUHETAG/STRECKE-Sonderregel in `split_link_code`
überflüssig (kein reales Kommando beginnt mit "XX").

**Sequenzierung:** NICHT parallel zu PR #2324 (#2154 Scheibe B, Konto-UI für den ALTEN
7-Zeichen-Code, andere Session "thunder") — als Folge-Schnitt danach. Thunder wurde informiert
(SendMessage, 14.09.).

## Existing Specs

- `docs/adr/0049-premium-sms-vierter-kanal.md` — Grundsatzentscheidung Premium-SMS als vierter Kanal
- `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` v1.5 — Rückkanal-Grundmechanik
- `docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md` — aktuelles Code-Format
- `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md` — Kommandoverarbeitung (nicht betroffen)

## Dependencies

- Upstream: seven.io Journal-API (`journal/inbound`), liefert reale `to`/`from`/`text`-Felder
- Downstream: `TripCommandProcessor` (unverändert), `NotificationService.send_command_reply_premium_sms` (unverändert)
- Cross-Cutting: Go-Endpunkt `premium_sms_connect.go` bleibt einziger Schreiber von `user.json` (Projektkonvention)

## Analysis

### Type
Feature (Änderung an bestehendem Feature — Premium-SMS-Rückkanal, #1676/#2154/#2184).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/inbound_sms_reader.py` | MODIFY | Gate von `GARMIN_MARKER not in text` auf `message.get("to") != SERVICE_NUMBER` umstellen (Zeile 212); `_LINK_CODE_PATTERN` auf neues Format anpassen (Zeile 75) |
| `internal/handler/premium_sms_link_code.go` | MODIFY | `premiumSmsLinkCodeAlphabet`/Code-Generierung auf `XX`-Präfix + 3 Buchstaben + 3 Ziffern umstellen (Zeile 33-54) |
| `tests/unit/test_inbound_sms_reply_learning.py` | MODIFY | AC-2 (`test_message_without_marker_is_ignored`) umschreiben: erwartet künftig einen versuchten, aber abgelehnten Lernaufruf statt gar keinen |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | MODIFY | Ergänzung zur korrigierten Erkennungslogik (kein Ablösen der Kernentscheidung) |
| `docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md` | MODIFY | Code-Format-Abschnitt aktualisieren |
| `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` | MODIFY | Gate-Beschreibung aktualisieren (v1.6) |

### Scope Assessment
- Files: 6 (innerhalb Projektlimit ≤4-5 als Richtwert leicht überschritten durch die zwei Spec-Dateien — überwiegend Doku, zählt nicht gegen LoC-Limit)
- Geschätzte LoC: ~+60/-20 (Code), Doku separat
- Risk Level: **HOCH** (kritischer Pfad — Auth-/Zuordnungslogik des einzigen Rückkanals; Fehlverhalten könnte Nachrichten falsch zuordnen oder den Kanal komplett stilllegen)

### Technical Approach

1. Python-Gate umstellen: `to`-Feld statt Text-Marker (strukturell immer vorhanden, durch Produktionsmessung belegt).
2. JEDE Nachricht mit passendem `to` geht an den bestehenden Go-Lern-Endpunkt — dessen vorhandene Auflösungslogik (Code-Match/bekannte Rückadresse) entscheidet Annahme/Ablehnung, nicht mehr ein Python-seitiger Content-Filter.
3. Code-Format in Go UND Python synchron auf `XX`+3+3 ändern (geteiltes Muster, Team-Lead-Lehre aus #2154 D9: nur EINE Zerlegungsstelle).
4. ADR-0049 und betroffene Specs als Ergänzung (nicht Ablösung) aktualisieren.
5. NICHT Teil dieses Schnitts: Ambiguitäts-Lücke im "frischer Treffer"-Weg (#2154), `default`-Fallback-Härtung (#2151), GPS-Feature (#2327).

### Dependencies
Siehe Abschnitt "Dependencies" oben — keine Änderungen an `TripCommandProcessor` oder `NotificationService` nötig.

### Open Questions
- [x] Sequenzierung mit PR #2324 geklärt (danach, thunder informiert)
- [ ] Exakte neue AC-2-Formulierung (abgelehnt statt ignoriert) — wird in `/30-write-spec` als AC festgehalten

## Risks & Considerations

- **Testumschreibung nötig:** `test_message_without_marker_is_ignored` (AC-2) prüft aktuell explizit das zu ändernde Verhalten — muss durch einen Test ersetzt werden, der zeigt: Nachricht ohne Code/unbekannte Nummer wird versucht, aber abgelehnt (kein `learned`, kein Reply), nicht mehr "gar nicht erst versucht".
- **Bereits gemeldeter Nebenbefund #2154:** Die Ambiguitäts-Lücke im "frischer Treffer ohne Code"-Weg ist NICHT Teil dieses Schnitts — separat gemeldet, dort zu fixen.
- **Koordination mit PR #2324:** Code-Format-Änderung erst nach deren Merge.
- **ADR-0049 wird ergänzt, nicht abgelöst** — die Kernentscheidung (feste Dienstnummer als Absender, gelernte Rückadresse als Empfänger) bleibt, nur die Erkennungslogik wird korrigiert.
- **Rate-Limit-Interaktion:** Kleinerer Schlüsselraum (6,2 statt vorher 27,5 Mrd.) macht die globale, nie zurückgesetzte Ratebremse (#2153) wichtiger — kein Blocker für diesen Schnitt, aber in der Spec erwähnenswert.
