---
entity_id: trip_shortcode_routing
type: module
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [inbound, email, trip, shortcode, routing, bug-775]
---

# Trip-Shortcode-Routing & robuster Inbound-Trip-Lookup

## Approval

- [x] Approved (PO 'go', 2026-06-12)

## Purpose

Macht die Zuordnung „Antwort-Mail → Trip" robust. Heute trägt der Mail-Betreff den
freien Trip-Namen; durch RFC-2047-Q-Encoding (ausgelöst vom Em-Dash `—` im Betreff)
werden Leerzeichen zu Unterstrichen, wodurch der exakte Namensvergleich scheitert
(„Trip nicht gefunden", Bug #775). Diese Spec dekodiert den Inbound-Betreff korrekt,
macht den Namensvergleich tolerant und führt einen kurzen, pro Nutzer eindeutigen
`GZ#`-Shortcode als primären, kollisionsarmen Routing-Key ein.

## Source

- **File:** `src/services/inbound_email_reader.py`
- **Identifier:** `InboundEmailReader._process_single`, `_extract_trip_name`, `_find_trip_id`
- **File:** `src/services/trip_command_processor.py`
- **Identifier:** `TripCommandProcessor._find_trip`
- **File:** `src/app/trip.py` — `Trip` (Feld `shortcode`)
- **File:** `src/app/loader.py` — `load_trip_from_dict`, `save_trip` (Persistenz `shortcode`)
- **File:** `src/output/subject.py` — `build_email_subject` (Shortcode im Betreff-Präfix)

> Schicht: **Python-Backend** (`src/services/`, `src/app/`, `src/output/`). Das
> Go-Modell `internal/model/trip.go` besitzt das Feld `Shortcode` bereits inkl.
> Serialisierung (`json:"shortcode,omitempty"`) — es wird hier **nicht** geändert,
> nur in Python gespiegelt, damit Python load→save den Wert nicht verliert.

## Estimated Scope

- **LoC:** ~150–230
- **Files:** 5 (inbound_email_reader, trip_command_processor, trip, loader, subject) + neuer Shortcode-Helfer
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `inbound_command_channels.md` v1.1 | spec | Bestehender Inbound-Reader-Vertrag (Betreff `[Trip] …`) |
| `output_subject_filter.md` | spec | Betreff-Erzeugung (`build_email_subject`, 78-Zeichen-Kaskade) |
| `internal/model/trip.go` | code | `Shortcode`-Feld (bereits vorhanden, Serialisierung) |

## Implementation Details

```
1) RFC-2047-Dekodierung (Inbound)
   _process_single: subject = msg.get("Subject","")
     → subject = str(make_header(decode_header(subject)))   # vor _extract_trip_name
   (Muster aus #768 / 7a28a95d)

2) Toleranter Namensvergleich (shared helper)
   norm(s) = re.sub(r"\s+", " ", s.replace("_", " ")).strip().lower()
   Lookup: norm(trip.name) == norm(query)
   Anwenden in BEIDEN: inbound_email_reader._find_trip_id UND
   trip_command_processor._find_trip.

3) Shortcode-Generierung (neuer Helfer, z.B. src/app/shortcode.py)
   base = "".join(ch for ch in name.upper() if ch.isalnum())[:4]  # "Hermannsweg…" → "HERM"
   fallback base = "TRIP" wenn leer
   code = f"GZ#{base}"; bei Kollision pro Nutzer: f"GZ#{base}{n}" (n=2,3,…)
   Eindeutigkeit über load_all_trips(user_id) geprüft.

4) Lazy-Persistenz
   Beim Versand (trip_report_scheduler / Betreff-Erzeugung): hat der Trip kein
   shortcode → generieren + via save_trip Read-Modify-Write persistieren
   (Merge: nur shortcode ergänzen, übrige Felder unberührt — Schema-Regel).

5) Python-Modell + Loader (Datenverlust-Schutz)
   Trip.shortcode: str = "" ; load_trip_from_dict liest data.get("shortcode","");
   save_trip serialisiert shortcode nur wenn nicht leer (omitempty-Parität zu Go).
   Ebenso activity/region NICHT mehr verlieren (Nebenbefund) — sofern trivial mit-erhalten.

6) Betreff trägt Shortcode (ASCII, immun gegen Space→Underscore)
   subject.py _build_skeleton: head = f"[{shortcode}] {trip_name} …" bzw.
   Präfix `[GZ#HERM]` voran. Exakte Position so, dass Inbound ihn parsen kann.

7) Inbound-Routing primär über Shortcode
   _extract_trip_name liefert weiterhin den Klammer-Inhalt; neuer Resolver:
   wenn Inhalt mit "GZ#" beginnt → Lookup über shortcode (case-insensitiv),
   sonst toleranter Namensvergleich. Reihenfolge: Shortcode zuerst, Name als Fallback.
```

## Expected Behavior

- **Input:** Antwort-Mail auf eine Briefing-Mail (Betreff RFC-2047-kodiert oder
  mit Unterstrichen statt Leerzeichen oder mit `[GZ#XXXX]`-Präfix), Body = Kommando
  (`jetzt`, `heute`, `stop`, …).
- **Output:** Korrekte Trip-Zuordnung → Kommando ausgeführt → Bestätigungs-Mail.
  Bei echtem Fehlschlag weiterhin „Trip nicht gefunden".
- **Side effects:** Erstmaliger Versand persistiert den generierten `shortcode` am
  Trip (idempotent, einmalig pro Trip).

## Acceptance Criteria

- **AC-1:** Given eine Antwort-Mail, deren Betreff RFC-2047-Q-kodiert ist (weil der
  Original-Briefing-Betreff einen Em-Dash `—` enthielt), When der Inbound-Reader den
  Betreff ausliest, Then dekodiert er ihn zuerst per `decode_header`/`make_header`,
  sodass die `[...]`-Klammern und der Trip-Bezeichner sichtbar werden und die Mail
  nicht mehr still ignoriert wird (Szenario A behoben).
  - Test: Echte MIME-Message mit Q-kodiertem Betreff erzeugen, durch den Reader
    schicken, beweisen dass ein Trip-Bezeichner extrahiert wird (vorher: None).

- **AC-2:** Given ein Trip namens `Hermannsweg mit Astrid 2026` (Leerzeichen) und ein
  aus dem Betreff extrahierter Bezeichner `Hermannsweg_mit_Astrid_2026` (Unterstriche),
  When `inbound_email_reader._find_trip_id` UND `trip_command_processor._find_trip`
  den Trip nachschlagen, Then findet die normalisierte Zuordnung
  (case-insensitive + Leerzeichen↔Unterstrich + Mehrfach-Whitespace) den Trip in
  beiden Stellen, und das Kommando wird ausgeführt statt „Trip nicht gefunden".
  - Test: Trip mit Leerzeichen-Namen anlegen, Lookup mit Unterstrich-Variante in
    beiden Funktionen → liefert denselben Trip; End-to-End: Kommando-Result success.

- **AC-3:** Given ein Trip ohne Shortcode für einen bestimmten Nutzer, When der
  Shortcode erzeugt wird, Then entsteht ein Code der Form `GZ#XXXX` (Präfix `GZ#` +
  bis zu 4 aus dem Namen abgeleitete Großbuchstaben, z.B. `GZ#HERM`), der pro Nutzer
  eindeutig ist (zweiter Trip mit gleichem Präfix erhält numerisches Suffix `GZ#HERM2`),
  und er bleibt über load→save erhalten (`shortcode` geht beim Speichern nicht verloren).
  - Test: Zwei Trips mit kollidierendem Namensanfang für einen Nutzer → zwei
    verschiedene, stabile Codes; Trip speichern und neu laden → Shortcode identisch.

- **AC-4:** Given ein Trip mit Shortcode `GZ#HERM`, When eine Briefing-Mail versendet
  und auf sie geantwortet wird, Then trägt der Betreff den Code (`[GZ#HERM] …`) und
  der Inbound-Reader ordnet die Antwort **primär über den Shortcode** dem richtigen
  Trip zu — auch wenn der Name durch Q-Encoding verändert wäre; der tolerante
  Namensvergleich bleibt Fallback für Mails ohne Code.
  - Test: Trip mit Shortcode, Betreff via `build_email_subject` erzeugen (enthält
    `GZ#HERM`), Reply simulieren, Reader findet den Trip über den Code.

- **AC-5:** Given der reale Versand-Betreff mit Em-Dash für einen Trip mit
  mehrwortigem Namen, When er MIME-serialisiert, als Reply empfangen und vom
  Inbound-Reader verarbeitet wird, Then beweist ein mock-freier Test den **kompletten**
  Pfad (Betreff bauen → `as_bytes()` serialisieren → empfangen → dekodieren → Trip
  finden → Kommando `jetzt` ausführen) — rot vor Fix, grün nach Fix.
  - Test: Kein Mock/patch; echte `email`-Serialisierung + echter Reader + echter
    Processor gegen einen realen Trip auf der Platte.

## Known Limitations

- Briefing-Mails, die **vor** dem Deploy versendet wurden, tragen keinen Shortcode;
  für sie greift ausschließlich der tolerante Namensvergleich (AC-2) — das ist
  ausreichend für den gemeldeten Bug.
- Bei extrem langen Betreffs kann die 78-Zeichen-Truncation-Kaskade den `[…]`-Präfix
  (inkl. Shortcode) verwerfen; dann ist keine Antwort-Zuordnung möglich (wie heute).
  Akzeptiert, da Randfall.
- Der Shortcode wird aus dem Namen abgeleitet, aber **einmalig** erzeugt und
  persistiert — eine spätere Umbenennung des Trips ändert den Code nicht (Stabilität
  vor Lesbarkeit beim Routing).

## Changelog

- 2026-06-12: Implementation complete (Bug #775). RFC-2047 decoding added, tolerant whitespace↔underscore lookup in both inbound_email_reader and trip_command_processor, new shortcode.py helper, Trip.shortcode field persisted, email subject updated with [GZ#XXXX] prefix.
