---
entity_id: fix_2323_premium_sms_gate_generisch
type: module
created: 2026-09-14
updated: 2026-09-14
status: draft
version: "1.0"
tags: [sms, inbound, premium, garmin, gate, seven-io]
---

<!-- Issue #2323 (ueberarbeitet nach PO-Grundsatzdiskussion 14.09.2026), Ursprung #2322.
     Nachfolger von fix_2154_premium_sms_verknuepfungscode.md (Scheibe A) -- baut auf
     dem dort eingefuehrten Code-Match/TTL-Mechanismus auf, aendert dessen Zulassungs-
     bedingung und Code-Format. Scheibe B von #2154 (Konto-UI, PR #2324) ist eine
     ANDERE Aenderung an derselben Datei (premium_sms_link_code.go) -- dieser Schnitt
     folgt erst NACH deren Merge (siehe "Known Limitations"). -->

# Premium-SMS Akzeptanz-Gate — generisch statt Garmin-Text-Marker

## Approval

- [ ] Approved

## Purpose

Der Eingangspfad für Premium-SMS-Antworten (`inbound_sms_reader.py`) prüft
heute einen abschaltbaren Garmin-Kartenlink-Text (`GARMIN_MARKER =
"inreachlink.com"`) statt der strukturell immer vorhandenen Zielrufnummer
(`to`-Feld, belegt durch echten Produktions-Journal-Eintrag). Nutzer, die
diesen Kartenlink in ihrer Garmin-Einstellung deaktiviert haben, werden
dadurch dauerhaft und lautlos ignoriert (Ursprung #2322). Diese Spec
korrigiert das Gate auf `to == SERVICE_NUMBER` und stellt gleichzeitig das
Verknüpfungscode-Format (aus #2154 Scheibe A) auf ein leichter tippbares
Muster um.

## Source

- **File:** `src/services/inbound_sms_reader.py`
  - Zeile 212: fehlerhaftes Content-Gate `GARMIN_MARKER not in text`
  - Zeile 75-101: `_LINK_CODE_PATTERN` und `split_link_code()`
- **File:** `internal/handler/premium_sms_link_code.go`
  - Zeile 36: `premiumSmsLinkCodeAlphabet` (Code-Generierung)

> **Schicht-Hinweis:** Gate-Korrektur und `_LINK_CODE_PATTERN` sind
> Python-Core (`src/services/`). Die Code-Erzeugung ist Go-API
> (`internal/handler/`). Beide Seiten müssen dasselbe Format synchron
> abbilden (eine Formatdefinition, zwei Implementierungen — Team-Lead-Lehre
> aus #2154 D9: nur eine Zerlegungsstelle für den Befehlstext). Die
> bestehende Zuordnungslogik (`internal/handler/premium_sms_connect.go
> ::resolvePremiumSmsTarget`) bleibt UNVERÄNDERT — sie ist Abhängigkeit,
> nicht Änderungsgegenstand dieser Spec (siehe Dependencies).

## Estimated Scope

- **LoC:** ~+60/-20 (Produktivcode + Tests), Doku separat
- **Files:** 6 (2 Code, 1 Test, 3 Doku)
- **Effort:** medium — Risk Level laut Analyse **HOCH** (kritischer Pfad:
  einziger Rückkanal des Premium-SMS-Kanals; Fehlverhalten könnte Nachrichten
  falsch zuordnen oder den Kanal komplett stilllegen)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/inbound_sms_reader.py` | MODIFY | Gate von `GARMIN_MARKER not in text` auf `message.get("to") != SERVICE_NUMBER` (Zeile 212); `_LINK_CODE_PATTERN` auf neues Format anpassen (Zeile 75) |
| `internal/handler/premium_sms_link_code.go` | MODIFY | `premiumSmsLinkCodeAlphabet`/Code-Generierung auf `XX`-Präfix + 3 Buchstaben (ohne I/L/O) + 3 Ziffern (ohne 0/1) umstellen (Zeile 33-54) |
| `tests/unit/test_inbound_sms_reply_learning.py` | MODIFY | `test_message_without_marker_is_ignored` (Zeile 202-220) umschreiben: erwartet künftig einen versuchten, aber abgelehnten Lernaufruf statt gar keinen Aufruf |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | MODIFY | Ergänzung zur korrigierten Erkennungslogik (kein Ablösen der Kernentscheidung) |
| `docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md` | MODIFY | Code-Format-Abschnitt auf `XX`+3+3 aktualisieren |
| `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` | MODIFY | Gate-Beschreibung aktualisieren (v1.6) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/premium_sms_connect.go::resolvePremiumSmsTarget` | module | bereits vorhandene Auflösungslogik (Code-Match/bekannte Rückadresse) entscheidet künftig ALLEIN über Annahme/Ablehnung — kein Python-seitiger Content-Filter mehr davor. Bleibt unverändert |
| `internal/handler/premium_sms_ratelimit.go` | module | globale Ratebremse gegen Fehlversuche; bei kleinerem Schlüsselraum (siehe Known Limitations) wichtiger, aber kein Blocker dieses Schnitts |
| seven.io Journal-API (`journal/inbound`) | Upstream | liefert reale `to`/`from`/`text`-Felder, Primärbeleg: `feat_1676_s1_premium_sms_rueckkanal.md:173` (Journal-ID 5283665, `to":"4916092172595"`) |
| `TripCommandProcessor`, `NotificationService.send_command_reply_premium_sms` | Downstream | unverändert |
| PR #2324 (#2154 Scheibe B, Konto-UI) | Sequenzierung | dieser Schnitt folgt ERST nach deren Merge — beide ändern `premium_sms_link_code.go` |

## Implementation Details

### Gate-Korrektur (Python)

Das Content-Gate `GARMIN_MARKER not in text` (Zeile 212) entfällt für die
Frage "wird überhaupt ein Lernaufruf versucht" und wird durch
`message.get("to") != SERVICE_NUMBER` ersetzt. Jede Nachricht mit passendem
`to` geht an den bestehenden Go-Lern-Endpunkt weiter — dessen vorhandene
Logik (Code-Match ODER bekannte, frische Rückadresse) entscheidet
Annahme/Ablehnung. Eine Nachricht ohne gültigen Code von unbekannter Nummer
bekommt dort bereits heute `409` (Issue #2154 AC-11), ohne Antwort-SMS und
ohne Datenschreiben — kein neues Kosten-/Abuse-Risiko.

`split_link_code()`s Nutzung von `GARMIN_MARKER` zum reinen Text-Zerlegen
(Link+Koordinaten vom Befehl abschneiden) bleibt unverändert — das ist keine
Zulassungsentscheidung, nur Textparsing, und funktioniert auch ohne Marker
im Text (dann bleibt der gesamte Text der Befehl).

### Code-Format-Änderung (Go + Python, PO-Entscheid 14.09.)

Alt: 7 Zeichen aus `A-HJKMNP-Z2-9` (31 Zeichen Alphabet, `31⁷ ≈ 2,75·10¹⁰ ≈
27,5 Mrd.` Schlüsselraum). Neu: fester Präfix `XX` (case-insensitive) + 3
Buchstaben (ohne I/L/O) + 3 Ziffern (ohne 0/1), z.B. `XXdrt249` — Schlüsselraum
ohne den festen Präfix `23³ · 8³ ≈ 6,23 Mio.` (kleiner als vorher, siehe
Known Limitations zur Ratebremse). Muss in Go (Generierung,
`premiumSmsLinkCodeAlphabet`) und Python (`_LINK_CODE_PATTERN`, Regex-Match)
synchron geändert werden.

**Entscheidung RUHETAG/STRECKE-Sonderregel:** Der feste Präfix `XX` macht die
bisherige Sonderbehandlung in `split_link_code()` (die verhinderte, dass ein
Befehl wie „RUHETAG" fälschlich als Code gelesen wird) überflüssig, weil kein
reales Kommando mit `XX` beginnt. Diese Spec entscheidet: die Sonderregel
wird **entfernt** (nicht nur ungenutzt gelassen) — das Codemuster wird über
den `XX`-Präfix eindeutig, ein separater Kommando-Ausschluss ist toter Code
und würde bei künftigen Kommandonamen stillschweigend falsch greifen können.
AC-6 sichert das Ergebnis unabhängig vom internen Weg ab.

## Expected Behavior

- **Input:** eingehende SMS im seven.io-Journal mit `to`, `from`, `text`
- **Output:** bei `to == SERVICE_NUMBER` wird IMMER ein Lernaufruf an den
  Go-Endpunkt versucht; bei `to != SERVICE_NUMBER` wird die Nachricht
  vollständig ignoriert (kein Lernaufruf-Versuch). Der Go-Endpunkt
  entscheidet unverändert über Annahme (Code-Match/bekannte Rückadresse) oder
  Ablehnung (409)
- **Side effects:** keine ausgehende Antwort-SMS und kein Datenschreiben bei
  Ablehnung; bei Annahme unverändertes Verhalten aus #2154

## Acceptance Criteria

- **AC-1:** Given eine Nachricht mit korrektem `to` (Dienstnummer) trägt
  einen gültigen, neu erzeugten Verknüpfungscode und stammt von einer bisher
  unbekannten Absenderadresse / When die Nachricht verarbeitet wird / Then
  wird der Code über den Go-Endpunkt aufgelöst und die Rückadresse für den
  zugehörigen Nutzer gelernt (`premium_sms_reply_to`/`-at` gesetzt).
  - Test: Fixture mit `to=SERVICE_NUMBER`, gültigem Code eines Nutzers,
    unbekannter `from`-Nummer; `user.json` danach auf gesetzte Rückadresse
    prüfen (echtes Nutzerverhalten, kein Dateiinhalt-Check am Quelltext).

- **AC-2:** Given eine Nachricht mit korrektem `to`, ohne Code, stammt von
  genau der einen Nummer, die bereits eindeutig als frische Rückadresse eines
  Nutzers gelernt ist (keine Mehrdeutigkeit, s. Known Limitations zu #2154)
  / When die Nachricht verarbeitet wird / Then wird sie als Befehl an
  `TripCommandProcessor` für genau diesen Nutzer weitergereicht.
  - Test: Fixture mit frischer, eindeutiger gespeicherter Rückadresse für
    einen Nutzer, Nachricht ohne Code von exakt dieser Nummer; prüfen, dass
    der Befehl mit der `user_id` dieses Nutzers verarbeitet wird.

- **AC-3:** Given eine Nachricht mit korrektem `to`, ohne Code, stammt von
  einer unbekannten Absenderadresse (kein Code-Match, keine gelernte
  Rückadresse) / When die Nachricht verarbeitet wird / Then wird sie an den
  Go-Endpunkt weitergereicht, dort mit 409 abgelehnt, es erfolgt KEINE
  Antwort-SMS und KEIN Schreiben in `user.json`.
  - Test: Fixture mit `to=SERVICE_NUMBER`, kein Code, unbekannte `from`; ein
    zählender Test-Double am Go-Lern-Endpunkt (kein Mock, der nur die eigene
    Annahme zurückspiegelt) muss GENAU EINEN Aufruf verzeichnen, der mit 409
    beantwortet wird; zusätzlich ausbleibenden Versand und unverändertes
    `user.json` prüfen. Ersetzt den bisherigen Test
    `test_message_without_marker_is_ignored`, der das alte, jetzt falsche
    Verhalten (kein Lernaufruf-Versuch) geprüft hat.

- **AC-4:** Given eine Nachricht trägt ein `to`, das NICHT der
  Dienstnummer entspricht / When die Nachricht verarbeitet wird / Then wird
  sie vollständig ignoriert — es wird kein Lernaufruf-Versuch am Go-Endpunkt
  unternommen.
  - Test: Fixture mit abweichendem `to`, beliebigem Text; derselbe zählende
    Test-Double wie in AC-3 muss hier GENAU NULL Aufrufe verzeichnen — der
    einzige Unterschied zwischen AC-3 (Aufruf erfolgt, wird abgelehnt) und
    AC-4 (kein Aufruf) ist damit an derselben Beobachtungsstelle geprüft.

- **AC-5:** Given ein neuer Verknüpfungscode wird erzeugt (Go) und das
  Python-seitige Erkennungsmuster (`_LINK_CODE_PATTERN`) soll ihn
  unabhängig von Groß-/Kleinschreibung matchen / When beide Seiten getrennt
  gegen das vereinbarte Format geprüft werden / Then erzeugt Go
  ausschließlich Codes im Format `XX`+3 Buchstaben (ohne I/L/O)+3 Ziffern
  (ohne 0/1), und Python akzeptiert gültige Codes in beiden Schreibweisen
  sowie lehnt Formatverstöße ab.
  - Test (Go, `internal/handler/premium_sms_link_code_test.go`): N erzeugte
    Codes gegen eine Formregel prüfen (Präfix `XX`, 3 Zeichen aus dem
    Buchstaben-, 3 Zeichen aus dem Ziffern-Alphabet) — Shape-Assertion über
    reale Generierungsaufrufe, kein Blick in den Quelltext.
  - Test (Python, `tests/unit/test_inbound_sms_reply_learning.py`):
    `_LINK_CODE_PATTERN` gegen eine Tabelle literaler Werte prüfen — akzeptiert
    `XXabc249` und `xxABC249` (Groß-/Kleinschreibung ignorieren); lehnt
    `XXabc0249` (zu lang), `XXab249` (zu kurz), `XXilo249` (verbotene
    Buchstaben I/L/O) und `XXabc019` (verbotene Ziffern 0/1) ab.

- **AC-6:** Given eine eingehende Nachricht enthält ausschließlich den
  Befehlstext `RUHETAG` oder `STRECKE` (kein Verknüpfungscode voran) / When
  der Befehlstext von der Code-Erkennung verarbeitet wird / Then wird der
  gesamte Text weiterhin korrekt als Befehl erkannt und nicht fälschlich als
  Verknüpfungscode interpretiert oder abgeschnitten — unabhängig davon, ob
  ein Code vorangestellt ist oder nicht.
  - Test: Zwei Fälle — Text `"RUHETAG"` ohne Code und Text
    `"XXabc249 RUHETAG"` mit Code; in beiden Fällen muss der an
    `TripCommandProcessor` übergebene Befehlstext exakt `"RUHETAG"` sein
    (keine Codereste, keine Fehlinterpretation als Code).

## Known Limitations

- **Ambiguitäts-Lücke im "frischer Treffer ohne Code"-Weg ist NICHT Teil
  dieses Schnitts** — separat gemeldet und zu fixen in **#2154**. AC-2 dieser
  Spec setzt deshalb explizit eine eindeutige, unmehrdeutige gelernte
  Rückadresse voraus.
- **`default`-Fallback-Härtung** ist NICHT Teil dieses Schnitts — siehe
  **#2151**.
- **GPS-Feature** ist NICHT Teil dieses Schnitts — siehe **#2327**.
- **Rate-Limit-Interaktion:** Der neue Schlüsselraum (~6,23 Mio. ohne
  Präfix, vorher ~27,5 Mrd.) macht die globale, nie zurückgesetzte
  Ratebremse (**#2153**) wichtiger als bisher — kein Blocker für diesen
  Schnitt, aber als Anschlussrisiko dokumentiert.
- **Sequenzierung mit PR #2324 ist ein hartes Sequenz-Constraint:** Die
  Code-Format-Änderung in `internal/handler/premium_sms_link_code.go` darf
  erst NACH dem Merge von PR #2324 (#2154 Scheibe B, Konto-UI für das ALTE
  7-Zeichen-Format, andere Session „thunder") umgesetzt werden — beide
  Änderungen betreffen dieselbe Datei. Vor Implementierung prüfen, ob #2324
  bereits gemerged ist.
- **Staging kann `premium_sms`-Kommandopfade strukturell nicht auslösen**
  (Herkunftssperre, siehe Betriebswissen) — der Nachweis liegt vollständig
  im Kern (Go- und Python-Tests), siehe Test Plan.

## Test Plan

Kern-Schicht (deterministisch, kein Netz, kein echtes inReach):

- `tests/unit/test_inbound_sms_reply_learning.py` (MODIFY):
  - Test für AC-1 (Code-Match, unbekannte Nummer wird gelernt)
  - Test für AC-2 (bekannte, eindeutige Rückadresse wird ohne Code als
    Befehl verarbeitet)
  - `test_message_without_marker_is_ignored` wird ersetzt durch einen Test
    für AC-3 (Lernaufruf-Versuch erfolgt, wird abgelehnt, kein Schreiben,
    kein Versand)
  - Test für AC-4 (falsches `to`, kein Lernaufruf-Versuch — zählender
    Test-Double wie in AC-3)
  - Test für AC-5 (`_LINK_CODE_PATTERN` gegen Akzeptanz-/Ablehnungstabelle)
  - Test für AC-6 (RUHETAG/STRECKE mit und ohne vorangestelltem Code)
- `internal/handler/premium_sms_link_code_test.go` (MODIFY):
  - Test für AC-5 (Shape-Assertion über generierte Codes)

Live-E2E: **entfällt für diesen Schnitt** — `premium_sms`-Kommandowege sind
auf Staging strukturell nicht extern auslösbar (Herkunftssperre #1476/#1676
AC-7). `/e2e-verify` prüft nur HTTP-Erreichbarkeit, nicht das
Gate-Verhalten selbst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0049 (keine Ablösung, nur Ergänzung)
- **Rationale:** ADR-0049 legt Premium-SMS als vierten Kanal fest (feste
  Dienstnummer als Absender, gelernte Rückadresse als Empfänger) — diese
  Spec ändert nur die technische Erkennungslogik, welche eingehenden
  Nachrichten überhaupt zur Auflösung vorgelegt werden, sowie das
  Code-Format. Die Kernentscheidung des ADR bleibt unverändert, daher kein
  neues ADR; ADR-0049 wird um den Hinweis auf die korrigierte
  `to`-Feld-Prüfung ergänzt.

## Changelog

- 2026-09-14: Initial spec erstellt — Issue #2323, überarbeitet nach
  PO-Grundsatzdiskussion (Ursprung #2322)
