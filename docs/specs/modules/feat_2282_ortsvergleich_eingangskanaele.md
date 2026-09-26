---
entity_id: feat_2282_ortsvergleich_eingangskanaele
type: module
created: 2026-09-16
updated: 2026-09-26
status: draft
version: "1.1"
tags: [ortsvergleich, inbound, trip-command-processor, trip-selection, epic-2133, epic-1374, issue-2282]
---

# Ortsvergleich über Eingangskanäle ansprechbar — Scheibe S1 (Auswahl, Rückfrage, Pause/Weiter)

## Approval

- [ ] Approved

## Purpose

Heute ist die gesamte Eingangskette (Telegram, Premium-SMS, E-Mail) ausschliesslich
trip-gebunden: Telegram und Premium-SMS lösen ohne Trip-Namen im Text über
`pick_active_trip` immer einen Trip auf, ein Ortsvergleich kann darüber nicht adressiert
werden; der E-Mail-Betreff `[Name]` findet ebenfalls nur Trips. Diese Scheibe macht den
Ortsvergleich für die zwei Befehle, die schon heute kind-neutral abbildbar sind
(`pause`/`weiter`), über alle drei Eingangskanäle ansprechbar und legt die geteilte
Auswahl-/Rückfrage-Logik, auf der die folgenden Scheiben (`report`/`heute`/`morgen`,
E-Mail-Antwort auf Vergleichs-Mails, Shortcodes) aufbauen. Scheibe **S1** von Ticket
#2282 (Dach-Epics #1374/#2345), Vorbedingung Epic #2133 S1–S3 ist erfüllt (geschlossen
2026-09-15).

## Nicht-Ziele / Folge-Scheiben (bewusst NICHT Teil dieser Spec)

| Nicht-Ziel | Grund / Folge-Scheibe |
|---|---|
| `report`/`heute`/`morgen` am Ortsvergleich tatsächlich versenden | Braucht `restrict_to_channel` in `send_compare_report` (`notification_service.py:1154-1242`) und einen `premium_sms`-Zweig dort — beides Gegenstand von **S2**, Vorbedingung **#2275**. Diese Spec liefert für die drei Befehle nur eine Übergangsantwort (AC-11). |
| E-Mail-Antwort auf eine Vergleichs-Mail per Betreff `Wetter-Vergleich: {name}` | Der Vergleichs-Betreff trägt heute keine `[Name]`-Klammern wie der Trip-Betreff — das ist **S3**, baut auf dieser Spec auf. |
| Shortcode-Vergabe (`GZ#…`) für Vergleiche inkl. Go-Feld, Kollisionsprüfung, Anzeige | Shortcodes werden produktiv nie vergeben (`generate_shortcode` hat nur Test-Aufrufer); Adressierung läuft in dieser Scheibe stattdessen über die aktive Auswahl und, bei Mehrdeutigkeit, über den Namen. Optionale **S4**, PO-Wunsch. |
| Jede schema-relevante Datei (`models.py`, `trip.py`, `loader.py`, `internal/model/*.go`, `internal/store/*.go`) | S1 ändert an keiner dieser Dateien etwas — keine Migration, kein Pre-Snapshot-Hook nötig. |

## Abweichungen vom Ticket-Entwurf

- **Ticket-AC „`report` antwortet kanaltreu auf demselben Kanal wie die Anfrage":**
  widerspricht der bereits getroffenen Entscheidung `feat_2126_kanaltreue_adhoc_antwort.md:156-157`
  (`report` bleibt für den Trip bewusst **mehrkanalig**, nur `heute`/`morgen` sind
  kanaltreu). Ein kanaltreues `report` nur für Vergleiche wäre eine neue, unbegründete
  Abweichung vom bestehenden Verhalten. Diese Scheibe verschiebt `report` ohnehin nach
  **S2** und übernimmt dort dieselbe Regel wie beim Trip — kein ADR-Bruch, keine
  Sonderregel für Vergleiche.
- **Ticket-AC „Pause trägt `paused_at`, identischer Wortlaut wie beim Trip":** Der
  Vergleich pausiert strukturell anders als der Trip (`schedule="manual"` +
  `previous_schedule` + `paused_at`, unbefristet, vs. Trip `report_config.paused_until`,
  befristet). Ein wortidentischer Text („pausiert bis … / Zum Fortsetzen: STOP") wäre für
  den Vergleich sachlich falsch (keine Dauer, kein `STOP`-Befehl am Vergleich). Diese
  Scheibe übernimmt Struktur und Tonalität des Trip-Texts, aber mit sachlich passendem
  Inhalt (AC-8/AC-9).
- **Ticket-Vorschlag „Adressierung über Shortcode `GZ#`":** Shortcodes sind produktiv tot
  (siehe Nicht-Ziele oben). Diese Scheibe adressiert stattdessen über die aktive Auswahl
  und, bei Mehrdeutigkeit, über den vorangestellten Namen — beides bereits für Trips
  etabliertes Muster (`_find_trip`), hier auf beide `kind`s erweitert.

## Source

- **File:** `src/services/trip_selection.py` — neue kind-neutrale Auswahl- und
  Text-Funktion, ergänzt `pick_active_trip(trips, now_utc)` (`:27`, unverändert).
- **File:** `src/services/trip_command_processor.py` — `_find_trip` (`:852`, beide kinds),
  `_COMMAND_SPECS` (`:127`, kind-Menge je Eintrag), `process()` (`:677`, Dispatch-Weiche
  vor dem bestehenden Trip-Dispatch), neue `_apply_compare_pause`/`_resume_compare`
  (Vorbild `_apply_pause` `:1993`, `_resume_trip` `:2348`).
- **File:** `src/services/inbound_telegram_reader.py` — `:211-227` (heutiger
  Abbruch-Text „Kein aktiver Trip gefunden", wird durch den Aufruf der neuen
  Auswahlfunktion ersetzt) und `:378` (`_find_active_trip`).
- **File:** `src/services/inbound_sms_reader.py` — `:322` dito (Premium-SMS-Zweig aus
  #2184, eigener, wortgleich abweichender Abbruch-Text — auch dieser wird durch den
  Aufruf derselben Auswahlfunktion ersetzt, siehe Implementation Details Abschnitt 2).
- **File:** `src/services/inbound_email_reader.py` — `_find_trip_id` (`:304`) sucht künftig
  beide kinds; Duplikat zu `_find_trip` wird dabei nicht aufgelöst (siehe Known
  Limitations), nur die Suchmenge erweitert. E-Mail nutzt **nicht** die neue
  aktive Auswahl (dort ist der Name im Betreff immer Pflicht, siehe Abschnitt 2).
- **File:** `src/services/scheduler_dispatch_service.py` — `save_compare_preset_pause`
  (`:279`, unverändert, Vorbild für die neue Resume-Gegenfunktion).

## Estimated Scope

- **LoC:** ~+350/−60 (Analyse-Schätzung, Ticket #2282)
- **Files:** ~6 Produktivdateien (MODIFY) + 3 Testdateien (CREATE, siehe „Vorgeschlagene
  Testdateien")
- **Effort:** high
- **Risk:** HIGH — Eingriff in die gesamte Eingangskette aller drei Kanäle,
  Trip-Regression und Mandantentrennung sind beide gleichzeitig gefährdet.
- **LoC-Limit:** 250 wird gerissen → `workflow.py set-field loc_limit_override 500`

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `pick_active_trip(trips, now_utc)` (`trip_selection.py:27`) | function | Bleibt unverändert die Trip-Hälfte der Auswahl; die neue Funktion ruft sie auf statt ihre Logik zu duplizieren |
| `ComparePreset.archived_at` / `.end_date` (`models.py:1308`/`:1331`, als `dict`-Feld im Loader-Rohformat) | field | Werden für die `aktiv`-Bestimmung **direkt** gelesen — bewusst NICHT über `is_silenced()` (siehe Abschnitt „Implementation Details" Punkt 1, Begründung) |
| `save_compare_preset_pause(user_id, preset_id, data_root, now_iso)` (`scheduler_dispatch_service.py:279`) | function | Read-Modify-Write-Vorbild mit kind-Guard — die neue Resume-Gegenfunktion folgt exakt demselben Muster |
| `load_all_trips(user_id)` / `load_compare_presets(user_id)` | function | Bleiben **in den Readern** — die Auswahlfunktion nimmt beide Listen als Parameter (Präzedenzfall aus #2184: vier Testdateien patchen `load_all_trips` auf dem Reader-Modulpfad, ein Umzug des Ladens würde sie blind machen) |
| `_find_trip(trip_name, user_id)` (`trip_command_processor.py:852`) | method | Wird um die Vergleichs-Suche erweitert — dieselbe tolerante Normalisierung (`_norm`), keine zweite Suchfunktion |
| `_COMMAND_SPECS` (`trip_command_processor.py:127`) | constant | Einzige Quelle für Hilfe-/Fehlertexte (#2134) — bekommt die kind-Zugehörigkeit je Befehl, damit `hilfe` am Vergleich und die Ablehnungstexte aus **derselben** Tabelle stammen |
| `CommandResult` → `send_command_reply_*` (`notification_service.py`) | contract | Unverändert für den Erfolgs-/Ablehnungsfall am eindeutig aufgelösten Ziel (#2168, Antwort an den Fragenden). Der Rückfrage-/Kein-Kandidat-Fall läuft dagegen **vor** `InboundMessage`/`process()`, wie heute schon der „Kein aktiver Trip gefunden"-Abbruch (`inbound_telegram_reader.py:213-227`) — siehe Abschnitt 2 |

## Implementation Details

### 1. Kind-neutrale Auswahl UND Text — EINE Funktion in `trip_selection.py`

Der heutige Abbruch „Kein aktiver Trip gefunden" passiert **vor** dem Bau von
`InboundMessage`, im jeweiligen Reader selbst, mit einem je Reader eigenen Text
(`inbound_telegram_reader.py:213-227`, `inbound_sms_reader.py:322`) — es gibt also
heute schon keinen einzigen Ort für diesen Fall. Damit die Mehrdeutigkeits-Fälle dieser
Scheibe nicht auf dieselbe Weise dreifach (Telegram, Premium-SMS, künftig weitere Kanäle)
neu formuliert werden, liegen **Auswahl UND die drei möglichen Ergebnistexte** in einer
einzigen neuen Funktion, die beide Reader aufrufen — Text-Erzeugung ist damit genauso
einquellig wie `_COMMAND_SPECS` für die Befehlstexte:

```
def resolve_active_target(
    trips: list[Trip], presets: list[dict], now_utc: datetime, *, channel: str,
) -> ZielErgebnis
```

`ZielErgebnis` hat drei Varianten:
- **eindeutig:** `(kind, objekt)` — Reader baut `InboundMessage` daraus wie heute
  (bei `kind == "route"`: `trip_name=objekt.name`, unverändertes Verhalten; bei
  `kind == "vergleich"`: neues Feld/Attribut, siehe Abschnitt 3).
- **mehrdeutig:** fertig formulierter Text (kanalabhängig gekürzt, AC-15) — der Reader
  sendet ihn **anstelle** des heutigen „Kein aktiver Trip gefunden" direkt über seinen
  bestehenden Antwortweg und beendet die Verarbeitung, **ohne** `process()` aufzurufen.
- **keiner:** fester Text „Kein aktiver Trip oder Ortsvergleich gefunden" (ersetzt den
  bisherigen, je Reader eigenen Text) — gleiches Vorgehen wie bei „mehrdeutig".

**Kandidatenbildung:**
- Trip-Kandidat: `pick_active_trip(trips, now_utc)` — liefert 0 oder 1 Trip
  (Etappen-Overlap am Ortstag der Trip, sonst frühester zukünftiger Trip; unverändert).
- Vergleichs-Kandidaten: alle `presets`, für die gilt: `archived_at` ist leer **und**
  (`end_date` ist leer **oder** `end_date` ≥ heutiger Tag). Referenzzeitpunkt für
  „heutiger Tag" ist hier bewusst der **UTC-Kalendertag von `now_utc`**, NICHT die
  ortsspezifische Zone eines Vergleichs-Ortes
  (`compare_slot_scheduler.first_resolvable_tz`, `:107-113`, #1726). Begründung: diese
  Prüfung entscheidet nur, ob ein Vergleich für Kanal-Routing noch als „laufend" zählt —
  anders als bei `presets_due_for_hour`, das einen tatsächlichen Sendezeitpunkt
  bestimmt, hat ein Tagesrand-Fehler um Mitternacht UTC hier keine Versand-Konsequenz,
  nur höchstens für wenige Stunden eine falsche Ein-/Ausblendung als Auswahlkandidat.
  Ergäbe sich daraus ein sichtbares Fehlverhalten, ist das ein Nebenbefund für eine
  Folge-Scheibe, kein Blocker dieser Spec.
- **Pausiert zählt NICHT als inaktiv** — nur `archived_at`/`end_date` werden geprüft,
  bewusst **nicht** über `is_silenced()` (`compare_alert_guard.py:39`), weil dessen
  dritte Bedingung (`schedule == "manual"`) hier gerade das Gegenteil der gewünschten
  Aussage träfe: ein per `pause` stillgelegter Vergleich soll für die Auswahl weiterhin
  als aktiv gelten, sonst wäre `weiter` nie erreichbar. `is_silenced` selektiv nur mit
  einer seiner drei Bedingungen aufzurufen widerspräche zudem der eigenen AC-28-Regel der
  Funktion („diese Prüfung darf nur einmal existieren") — deshalb werden `archived_at`/
  `end_date` hier direkt gelesen, als eigene, andere Frage („noch adressierbar?" statt
  „darf gerade senden?").

**Entscheidungstabelle:**

| Trip-Kandidat | Vergleichs-Kandidaten | Ergebnis |
|---|---|---|
| 1 | 0 | eindeutig: Trip (unverändert zu heute) |
| 0 | genau 1 | eindeutig: dieser Vergleich |
| 1 | ≥ 1 | mehrdeutig — Rückfrage |
| 0 | ≥ 2 | mehrdeutig — Rückfrage |
| 0 | 0 | keiner |

**Rückfrage-Text:** zählt Namen aller Kandidaten auf und erklärt die Adressierung, z. B.
`"Mehrdeutig: Korsika (Trip), Zermatt vs. Saas-Fee (Vergleich). Bitte mit Namen
antworten, z. B. 'Korsika pause'."` Für `channel == "premium_sms"` kürzt dieselbe
Funktion die Namen bei Bedarf, bis der Text inklusive aller Kandidaten in 160
GSM-7-Zeichen passt (AC-15) — die Anzahl der aufgezählten Kandidaten wird dabei nie
reduziert, nur die Namenslänge.

Lädt selbst nichts — `trips`/`presets` kommen vom aufrufenden Reader (unverändert
`load_all_trips`/`load_compare_presets`), damit die vier bestehenden Testdateien, die
`load_all_trips` auf dem Reader-Modulpfad patchen, nicht blind gegen echte Daten laufen
(Präzedenzfall #2184). `resolve_active_target`/`ZielErgebnis` sind Namensvorschläge,
keine bindende Signatur (siehe Known Limitations).

### 2. Reader-Integration

Telegram (`:211-227`) und Premium-SMS (`:322`) ersetzen ihren heutigen, je eigenen
Abbruch durch: `ergebnis = resolve_active_target(trips, presets, now_utc,
channel=<"telegram"|"premium_sms">)`. Bei `mehrdeutig`/`keiner` senden sie den
mitgelieferten Text über ihren bestehenden Antwortweg (`send_telegram_message` bzw.
`PremiumSmsOutput.send`) und brechen ab — **kein** Aufruf von `process()`, keine
`InboundMessage`. Bei `eindeutig` bauen sie `InboundMessage` wie heute und rufen
`process()` auf. E-Mail bleibt aussen vor: dort ist der Name im Betreff (`[Name]`)
bereits Pflicht (`inbound_email_reader.py:66/:141-145/:200`), es gibt keinen
„aktive Auswahl ohne Namen"-Fall — nur `_find_trip_id` wird auf beide kinds erweitert
(Abschnitt 4).

### 3. `InboundMessage` für einen Vergleich

`InboundMessage.trip_name` bleibt als Feldname bestehen (kein Schema-Bruch), trägt für
einen aufgelösten Vergleich dessen `name` (identisches Muster zum Trip-Fall). Damit
`process()` weiss, dass es sich um einen Vergleich handelt (und nicht versehentlich in
den Trip-Dispatch läuft), bekommt `InboundMessage` ein zusätzliches, additives Feld
`resolved_kind: str | None = None` (Default `None` = Trip-Verhalten unverändert, wie
bisher ausschliesslich über `_find_trip` aufgelöst). Reader, die bereits über
`resolve_active_target` eindeutig auf einen Vergleich aufgelöst haben, setzen
`resolved_kind="vergleich"` und `resolved_preset_id=<id>` (zweites additives Feld, damit
`process()` nicht erneut über den Namen suchen muss, wenn er nicht eindeutig ist — siehe
Namensgleichheits-Fall AC-7). Ist `resolved_kind` gesetzt, überspringt `process()` den
Aufruf von `_find_trip` und geht direkt in die Vergleichs-Dispatch-Weiche (Abschnitt 5).
Bleibt `resolved_kind` `None` (E-Mail, oder Telegram/Premium-SMS mit explizit
vorangestelltem Namen im Text), sucht `_find_trip` wie in Abschnitt 4 beschrieben über
beide kinds.

### 4. Namensadressierung (`_find_trip` erweitert auf beide kinds)

Beginnt die Nachricht mit einem Namen (Telegram/Premium-SMS: Nutzer tippt einen Namen
statt sich auf die aktive Auswahl zu verlassen; E-Mail: `[Name]` im Betreff, stets
Pflicht), wird dieser Name gegen beide kinds geprüft (tolerante Normalisierung `_norm`,
wie heute für Trips). Trifft der Name eindeutig auf genau ein Objekt (Trip oder
Vergleich), wird dieses direkt angesprochen — auch wenn `resolve_active_target` sonst
Mehrdeutigkeit gemeldet hätte (der explizite Name hat Vorrang vor der aktiven Auswahl).
Trifft derselbe Name auf **einen Trip und einen Vergleich gleichzeitig**
(Namensgleichheit), wird das wie Mehrdeutigkeit behandelt (derselbe Rückfrage-Text wie
in Abschnitt 1) — es wird NICHT still der Trip bevorzugt. `inbound_email_reader.
_find_trip_id` (`:304`) bekommt dieselbe Erweiterung: der `[Name]`-Betreff findet
künftig auch Vergleiche.

### 5. Dispatch-Weiche in `process()`

Ist das aufgelöste Ziel ein Vergleich (`resolved_kind == "vergleich"` ODER
`_find_trip` liefert einen Vergleichstreffer über den Namen), verzweigt `process()` **vor**
dem bestehenden, unveränderten Trip-Dispatch (`:791-833`, bleibt byte-gleich) auf einen
eigenen, kleinen Dispatch-Block:

| Befehl | Verhalten am Vergleich |
|---|---|
| `pause` | Neue `_apply_compare_pause` — ruft `save_compare_preset_pause` auf (unverändert), ignoriert eine mitgegebene Dauer, Antworttext sagt „pausiert, bis du 'weiter' sendest" |
| `weiter` | Neue `_resume_compare` (RMW-Gegenstück, siehe Abschnitt 6) |
| `hilfe` | Zeigt nur die Zeilen aus `_COMMAND_SPECS`, deren kind-Menge `"vergleich"` enthält |
| `report`, `heute`, `morgen` | Feste Übergangsantwort „für Ortsvergleiche per Nachricht noch nicht verfügbar — bitte Web-App", keine Änderung, kein Versand |
| alle übrigen (`strecke`, `skip`, `ruhetag`, `startdatum`, `abbruch`, `now`/`jetzt`, `status`, `gewitter`/`heute_gewitter`, `glance`, Drilldowns, Metrikwörter) | „'<befehl>' gibt es beim Ortsvergleich nicht", keine Änderung |

### 6. `weiter` am Vergleich (`_resume_compare`, neue Funktion in
`scheduler_dispatch_service.py`)

Exaktes RMW-Gegenstück zu `save_compare_preset_pause` (`:279-337`): liest die
Preset-Datei, prüft denselben kind-Guard (`kind` ∈ `{None, "", "vergleich"}`, sonst
`return` ohne Schreiben — F002-Schutz), setzt `schedule = entry.get("previous_schedule")
or "daily"` und löscht `paused_at` **im selben Schreibvorgang** — nicht in zwei Schritten,
sonst könnte ein Crash zwischen beiden Writes einen inkonsistenten Zwischenzustand
hinterlassen. Leeres `previous_schedule` ⇒ `"daily"` (AC-9), identisch zu
`computePauseToggle` in `frontend/src/lib/components/compare/subscriptionHelpers.ts`
(`preset.previous_schedule || 'daily'`) — das Fortsetzen per Nachricht verhält sich
damit genau wie das Fortsetzen in der Web-App. Read-Modify-Write, kein Replace
(Datenverlust-Regel).

### 7. `_COMMAND_SPECS` bekommt eine kind-Menge

Jeder Eintrag trägt zusätzlich, für welche(n) kind(s) er gilt
(`frozenset({"route"})` / `frozenset({"vergleich"})` / beide). `pause`/`weiter`/`hilfe`
gelten für beide; alle anderen bestehenden Einträge bleiben `{"route"}`. Diese Menge ist
die **einzige** Quelle sowohl für die `hilfe`-Ausgabe am Vergleich als auch für die
generische Ablehnungsantwort „gibt es beim Ortsvergleich nicht" — keine zweite,
handgepflegte Liste (Konsistenz mit der bestehenden #2134-Regel).

## Vorgeschlagene Testdateien

- `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py` — AC-1 bis AC-7 (Auswahl,
  Rückfrage, Namensadressierung, Namensgleichheit)
- `tests/tdd/test_vergleich_pause_weiter.py` — AC-8, AC-9, AC-10
- `tests/tdd/test_vergleich_befehlsablehnung.py` — AC-11, AC-12
- Mandantentrennung (AC-14) und Trip-Regression (AC-13) können in eine der obigen
  Dateien integriert oder, falls das Zwei-Nutzer-Fixture-Setup umfangreich wird, in eine
  vierte Datei `tests/tdd/test_vergleich_inbound_mandantentrennung.py` ausgelagert
  werden — Entscheidung fällt in der RED-Phase anhand der tatsächlichen Fixture-Grösse.

## Expected Behavior

- **Input:** Eine Nachricht über Telegram, Premium-SMS oder E-Mail, mit oder ohne
  vorangestellten Namen, von einem Nutzer mit beliebiger Kombination aus aktiven Trips
  und aktiven Ortsvergleichen.
- **Output:** Bei eindeutiger Auswahl wird der Befehl an das ermittelte Objekt
  ausgeführt (Trip-Pfad unverändert, Vergleich beschränkt auf `pause`/`weiter`/`hilfe`
  plus definierte Ablehnungs-/Übergangstexte für alle anderen Befehle). Bei Mehrdeutigkeit
  oder fehlendem Kandidaten wird `process()` gar nicht erst aufgerufen, stattdessen
  sendet der Reader direkt den von `resolve_active_target` gelieferten Text.
- **Side effects:** `pause`/`weiter` am Vergleich schreiben ausschliesslich die
  `briefings/<preset_id>.json`-Datei des anfragenden Nutzers (RMW). Kein Trip wird durch
  diese Scheibe je geschrieben, wenn die Auflösung auf einen Vergleich zeigt, und
  umgekehrt.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat genau einen aktiven Trip und keinen aktiven
  Ortsvergleich (Ausgangslage unverändert zu heute) / When er per Telegram oder
  Premium-SMS ohne Namen `pause` sendet / Then wird der Trip pausiert wie vor dieser
  Änderung — keine Rückfrage, kein neuer Text.
  - Test: bestehende Trip-Pause-Testfälle laufen unverändert durch die neue Auswahl.

- **AC-2:** Given ein Nutzer hat **keinen** aktiven Trip und genau **einen** aktiven
  (ggf. bereits pausierten) Ortsvergleich / When er per Telegram oder Premium-SMS ohne
  Namen `weiter` sendet / Then wird genau dieser Ortsvergleich fortgesetzt — keine
  Rückfrage, obwohl kein Name im Text steht, und obwohl der Vergleich pausiert war
  (Pause zählt nicht als inaktiv).
  - Test: Nutzer-Fixture mit einem archivierten Trip (also 0 Trip-Kandidaten) und einem
    pausierten, nicht archivierten Vergleich; Befehl ohne Namen ausführen, Schreibresultat
    der Preset-Datei prüfen.

- **AC-3:** Given ein Nutzer hat mehrere Trips, aber keinen aktiven Ortsvergleich /
  When er wie heute ohne Namen einen Trip-Befehl sendet / Then bleibt das Ergebnis
  identisch zum Stand vor dieser Änderung (`pick_active_trip` entscheidet allein,
  keine neue Rückfrage durch das Hinzukommen von Ortsvergleichen als Konzept).
  - Test: Fixture mit zwei Trips (einer aktuell, einer zukünftig), kein Vergleich vorhanden,
    Befehl ohne Namen — Ergebnis identisch zum bestehenden Testfall vor dieser Spec.

- **AC-4:** Given ein Nutzer hat einen aktiven Trip **und** mindestens einen aktiven
  Ortsvergleich (oder keinen Trip und mindestens zwei aktive Ortsvergleiche) / When er
  per Telegram oder Premium-SMS ohne Namen einen Befehl sendet / Then erhält er
  **direkt vom Reader** (ohne dass `process()`/`TripCommandProcessor` aufgerufen wird)
  eine Rückfrage, die alle Kandidatennamen aufzählt und erklärt, wie er mit Namen
  adressiert (`<Name> <Befehl>`) — **kein** Befehl wird ausgeführt.
  - Test: je eine Fixture für beide Mehrdeutigkeits-Fälle (Trip+Vergleich;
    Vergleich+Vergleich ohne Trip); Rückfrage-Text UND ausbleibende Wirkung
    (keine Schreiboperation an Trip oder Preset, `TripCommandProcessor.process` wird
    nicht aufgerufen) prüfen.
  - **Status:** Abgelöst durch `feat_2417_befehle_e2e_echter_eingang.md`
    (Befehls-×-Lagen-Matrix): Nur `pause`/`weiter` fragen bei Trip+Ortsvergleich noch
    nach — jeder andere Befehl (inkl. `hilfe`) erreicht sein Ziel ohne Rückfrage.

- **AC-5:** Given ein Nutzer hat weder einen aktiven Trip noch einen aktiven
  Ortsvergleich / When er per Telegram oder Premium-SMS einen Befehl ohne Namen sendet /
  Then lautet die Antwort „Kein aktiver Trip oder Ortsvergleich gefunden" (statt des
  bisherigen, je Kanal unterschiedlichen „Kein aktiver Trip gefunden") — für **beide**
  Kanäle identisch, weil beide denselben `resolve_active_target`-Text senden.
  - Test: Fixture ohne aktive Kandidaten, für Telegram UND Premium-SMS je den
    Antworttext exakt prüfen.

- **AC-6:** Given eine Mehrdeutigkeits-Lage wie in AC-4, aber die Nachricht beginnt mit
  dem (tolerant normalisierten) Namen eines der Kandidaten / When der Befehl gesendet
  wird / Then wird genau dieses benannte Objekt angesprochen — Trip oder Vergleich,
  je nachdem was der Name trifft — ohne Rückfrage, und `process()` wird diesmal
  aufgerufen. Dasselbe gilt für eine E-Mail mit `[Name]` im Betreff, wenn `Name` einen
  Ortsvergleich bezeichnet.
  - Test: dieselbe Mehrdeutigkeits-Fixture wie AC-4, einmal mit vorangestelltem
    Trip-Namen, einmal mit vorangestelltem Vergleichsnamen, dazu ein E-Mail-Betreff-Test
    mit `[Vergleichsname]`.

- **AC-7:** Given ein Trip und ein Ortsvergleich desselben Nutzers tragen **denselben**
  Namen / When eine Nachricht mit diesem Namen vorangestellt gesendet wird / Then
  erhält der Nutzer die Rückfrage aus AC-4 statt einer stillen Auflösung auf den Trip.
  - Test: Fixture mit Namensgleichheit Trip↔Vergleich, Rückfrage-Text und ausbleibende
    Wirkung prüfen.

- **AC-8:** Given ein aktiver, nicht pausierter Ortsvergleich wird eindeutig
  angesprochen / When `pause` gesendet wird — mit oder ohne mitgegebene Dauerangabe /
  Then wird der Vergleich unbefristet pausiert (`schedule="manual"`,
  `previous_schedule` gesetzt, `paused_at` gesetzt), eine mitgegebene Dauer wird nicht
  ausgewertet, und die Antwort sagt sinngemäss „pausiert, bis du 'weiter' sendest" —
  kein Verweis auf `STOP` oder eine Dauer.
  - Test: einmal `pause` ohne Wert, einmal `pause 2d` senden — beide Male identisches
    Schreibresultat (unbefristete Pause) und identischer Antworttext.

- **AC-9:** Given ein per `pause` (AC-8) pausierter Ortsvergleich / When `weiter`
  gesendet wird / Then wird `previous_schedule` nach `schedule` übernommen — ist
  `previous_schedule` leer, gilt `"daily"`, identisch zum Fortsetzen in der Web-App
  (`frontend/src/lib/components/compare/subscriptionHelpers.ts:349`) — und `paused_at`
  im selben Schreibvorgang gelöscht — der Vergleich gilt
  danach laut `is_silenced()` als nicht mehr pausiert.
  - Test: Pause- und Resume-Befehl nacheinander senden, `schedule`/`paused_at` der
    Preset-Datei vor und nach `weiter` vergleichen (ein einziger Dateizugriff pro
    Schritt genügt, kein Zwischenzustand mit nur einem der beiden Felder korrigiert),
    zusätzlich `is_silenced(entry) == False` nach `weiter` prüfen.

- **AC-10:** Given ein Ortsvergleich ist **nicht** pausiert / When `weiter` gesendet
  wird / Then antwortet der Prozessor „ist nicht pausiert" und ändert die Preset-Datei
  **nicht**.
  - Test: nicht pausierte Vergleichs-Fixture, `weiter` senden, Datei-Zeitstempel/-inhalt
    vor und nach dem Befehl identisch.

- **AC-11:** Given ein Ortsvergleich ist eindeutig angesprochen / When einer der
  Befehle `strecke`, `skip`, `ruhetag`, `startdatum`, `abbruch`, `status`, `now`/`jetzt`,
  `gewitter`, `glance`, ein Drilldown-Token oder ein Metrikwort gesendet wird / Then
  antwortet der Prozessor „'<befehl>' gibt es beim Ortsvergleich nicht" und ändert am
  Vergleich **nichts**; wird stattdessen `report`, `heute` oder `morgen` gesendet, lautet
  die Antwort „für Ortsvergleiche per Nachricht noch nicht verfügbar — bitte Web-App",
  ebenfalls ohne Änderung und **ohne** dass ein Briefing versendet wird.
  - Test: für mindestens je einen Vertreter aus beiden Gruppen (z. B. `skip` und
    `heute`) den erwarteten Text UND das Ausbleiben jeder Schreib-/Versandoperation
    prüfen.

- **AC-12:** Given `hilfe` wird an einem eindeutig angesprochenen Ortsvergleich
  gesendet / When die Antwort erzeugt wird / Then enthält sie ausschliesslich die am
  Vergleich verfügbaren Befehle (`pause`, `weiter`, `hilfe`) — keine Trip-only-Befehle
  aus `_COMMAND_SPECS`.
  - Test: `hilfe`-Antwort am Vergleich mit der `hilfe`-Antwort an einem Trip
    vergleichen — die Vergleichs-Antwort ist eine echte Teilmenge, nicht dieselbe Liste.

- **AC-13:** Trip-Regression. Given ein Nutzer hat **keinen** aktiven Ortsvergleich /
  When er einen beliebigen bestehenden Trip-Befehl sendet (inklusive `report`, `heute`,
  `morgen`, Drilldowns, `pause 2d`) / Then ist sowohl der Antworttext als auch die
  tatsächliche Wirkung identisch zum Stand vor dieser Änderung — als eigene, positive
  Kontrolle dieser Spec (nicht nur „bestehende Tests bleiben grün"): `pause 2d` an
  einem Trip liefert weiterhin `report_config.paused_until` gesetzt und den Text
  „Zum Fortsetzen: STOP (dauerhaft) oder warte bis die Pause abläuft" — die für
  Vergleiche geänderte Pause-Antwort (AC-8) darf den Trip-Text nicht verändert haben.
  - Test: die bestehende Trip-Command-Testsuite (`test_trip_command_processor.py`,
    `test_issue_731_unified_commands.py`, `test_issue_882_pause_skip.py`,
    `test_issue_612_report_on_demand.py`) läuft unverändert grün gegen den neuen Code,
    ergänzt um die eigene `pause 2d`-Assertion aus dieser Spec.

- **AC-14:** Mandantentrennung. Given zwei Nutzer A und B haben je einen Ortsvergleich
  mit **demselben** Namen / When Nutzer A per Telegram oder Premium-SMS `pause` an
  seinen Vergleich sendet / Then wird ausschliesslich die Preset-Datei unter
  `data/users/<A>/briefings/` verändert, die Datei von B unter `data/users/<B>/briefings/`
  bleibt unverändert, und die Antwort geht ausschliesslich an A.
  - Test: zwei echte Nutzerverzeichnisse in einem temporären Datenwurzel-Fixture,
    identischer Vergleichsname, Befehl von A ausführen, beide Dateien danach vergleichen.

- **AC-15:** Given eine Rückfrage nach AC-4 wird für den Premium-SMS-Kanal erzeugt /
  When die Anzahl und Länge der Kandidatennamen den Text sonst über das GSM-7-Limit
  treiben würde / Then bleibt die versendete Rückfrage bei **höchstens 160 GSM-7-Zeichen**
  — alle Kandidaten bleiben in der Aufzählung enthalten, notfalls mit gekürzten Namen,
  nicht mit einer unvollständigen Liste. Die Kürzung geschieht in `resolve_active_target`
  selbst (`channel="premium_sms"`), nicht als nachträglicher Zuschnitt im Reader.
  - Test: Fixture mit mehreren Kandidaten mit bewusst langen Namen, Aufruf mit
    `channel="premium_sms"`, Zeichenlänge des zurückgegebenen Textes messen (kein
    Dateiinhalt-Check); Partner-Aufruf mit `channel="telegram"` zeigt, dass dort keine
    Kürzung stattfindet (Telegram hat kein 160-Zeichen-Limit).

## Mutations-Gegenprobe

1. **`archived_at`/`end_date`-Prüfung durch `is_silenced(preset)` ersetzen (alle drei
   Bedingungen statt nur der zwei relevanten).** Ein Test, der nur den unpausierten
   Erfolgspfad prüft (AC-1/AC-3), bleibt grün — fängt nur AC-2/AC-9, wo ein pausierter,
   nicht archivierter Vergleich trotzdem als Kandidat gelten bzw. nach `weiter` wieder
   aktiv sein muss.
2. **Mehrdeutigkeits-Fall `Trip + 1 Vergleich` fälschlich als eindeutig behandeln**
   (z. B. Trip immer bevorzugen, wenn genau ein Vergleich daneben aktiv ist). Ein Test mit
   `0 Trip + 1 Vergleich` (AC-2) bleibt grün, weil dieser Fall unverändert eindeutig ist.
   Fängt nur AC-4 mit **genau** `1 Trip + 1 Vergleich`.
3. **Resume schreibt `schedule` und löscht `paused_at` in zwei getrennten
   Dateizugriffen statt einem RMW.** Ein Test, der nur den Endzustand nach `weiter`
   prüft, bleibt grün. Fängt nur ein Test, der den Schreibvorgang selbst zählt (genau
   ein `open(..., "w")` zwischen Lesen und Antwort) oder eine Exception zwischen beiden
   Schreibvorgängen simuliert und danach einen konsistenten Zustand fordert.
4. **`_COMMAND_SPECS`-kind-Filter nur in der `hilfe`-Ausgabe anwenden, nicht in der
   Ablehnungsantwort.** Ein Test, der nur `hilfe` prüft (AC-12), bleibt grün. Fängt nur
   AC-11, wenn er einen Trip-only-Befehl am Vergleich sendet und den exakten
   Ablehnungstext (nicht nur „irgendeine Fehlermeldung") verlangt.
5. **Namensadressierung (AC-6) bevorzugt bei Namensgleichheit weiterhin den Trip statt
   der Rückfrage.** Ein Test ohne Namensgleichheits-Fixture bleibt grün. Fängt nur AC-7
   mit einem Trip und einem Vergleich desselben Namens im selben Nutzerkonto.
6. **Rückfrage-/Kein-Kandidat-Fall ruft `process()` trotzdem auf** (statt vor
   `InboundMessage` abzubrechen wie heute der „Kein aktiver Trip"-Fall). Ein Test, der
   nur den Antworttext prüft, bleibt grün. Fängt nur AC-4, wenn er zusätzlich prüft,
   dass `TripCommandProcessor.process`/jede Schreiboperation **nicht** aufgerufen wurde.

## Known Limitations

- **`_find_trip` (Prozessor) und `_find_trip_id` (E-Mail-Reader) bleiben zwei
  Implementierungen derselben Suche.** Diese Spec erweitert beide auf beide kinds,
  löst das vorbestehende Duplikat aber nicht auf (Umbau ausserhalb des Scopes dieser
  Scheibe; im Kontext bereits als Befund vermerkt).
- **`jetzt`/`gewitter`/`status`/`glance` am Ortsvergleich bekommen in dieser Scheibe
  bewusst die generische Ablehnung „gibt es beim Ortsvergleich nicht"**, nicht die
  „noch nicht verfügbar"-Übergangsantwort von `report`/`heute`/`morgen`. Diese drei
  Befehle lösen beim Trip keinen mehrkanaligen Versand aus, sondern liefern eine
  synchrone Text-Antwort auf Basis vorhandener Wetterformatierer — eine
  Vergleichs-Fassung dieser Formatierer existiert noch nicht und ist nicht Teil dieser
  Spec. Eine spätere Scheibe kann sie ergänzen und müsste dafür `_COMMAND_SPECS`
  entsprechend erweitern.
- **Der `aktiv`-Vergleichstag verwendet den UTC-Kalendertag, nicht die Ortszone des
  einzelnen Vergleichs.** Bewusste Vereinfachung gegenüber `presets_due_for_hour`
  (siehe Implementation Details Punkt 1) — betrifft nur die Kanal-Routing-Entscheidung
  „noch adressierbar?", keinen Sendezeitpunkt. Zeigt sich das als sichtbarer Fehler,
  ist das ein Nebenbefund für eine Folge-Scheibe.
- **`resolve_active_target`/`ZielErgebnis`/`resolved_kind`/`resolved_preset_id` sind
  Namensvorschläge, keine bindende Signatur.** Die Implementierung darf andere Namen
  wählen, solange der beschriebene Vertrag erhalten bleibt: (a) Auswahl und alle drei
  Ergebnistexte kommen aus **einer** Funktion, (b) sie lädt selbst nichts, (c) die
  Entscheidungstabelle aus Abschnitt 1 sowie die Kanal-abhängige 160-Zeichen-Kürzung
  (AC-15) sind erfüllt.
- **Heißen ein Trip und ein Ortsvergleich gleich, ist per Nachricht keiner der beiden
  eindeutig ansprechbar** (AC-7 fragt immer zurück). Abhilfe bis S4 (Shortcode):
  einen der beiden in der Web-App umbenennen — die Rückfrage nennt beide Arten, damit
  der Nutzer die Ursache erkennt.
- **Go-Web-Editor ist von dieser Scheibe nicht betroffen.** Es wird kein neues Feld
  am `ComparePreset`-Modell eingeführt; die Pause-Felder existieren bereits und werden
  nur gelesen/geschrieben, nie in ihrer Struktur verändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe eröffnet keine neue Entscheidungsfläche — sie überträgt
  das bereits dokumentierte Muster „geteilter Kommandoverarbeiter, `kind`-Guard bei
  jedem Schreibzugriff" (ADR-0023, gemeinsames Modell/kind) auf zwei zusätzliche
  Befehle und drei Eingangskanäle, die bereits alle vier für Trips existieren
  (ADR-0049, Premium-SMS als vierter Kanal, bleibt unberührt). Die Pause-Semantik des
  Vergleichs (`schedule="manual"`) existiert bereits produktiv (Issue #1250) und wird
  hier nicht verändert, nur über einen zweiten Schreibpfad (Resume) ergänzt. Kein neues
  ADR nötig.

## Changelog

- 2026-09-16: Initial spec created (Scheibe S1 von Ticket #2282, nach Analyse-Phase mit
  Kontext-Dokument `docs/context/feat-2282-compare-inbound.md`).
- 2026-09-16 (Review-Nachtrag, vor Freigabe): Transportvertrag zwischen Reader und
  Prozessor präzisiert (`resolve_active_target` liefert Auswahl UND alle drei
  Ergebnistexte aus einer Funktion, additive `InboundMessage`-Felder `resolved_kind`/
  `resolved_preset_id`); `aktiv`-Prädikat auf direktes Lesen von `archived_at`/
  `end_date` statt `is_silenced()` umgestellt und die UTC-Tag-Vereinfachung explizit
  begründet statt implizit gelassen; `previous_schedule`-Leerfall in Abschnitt 6
  aufgelöst (kein Default nötig); AC-5 um Kanalangabe ergänzt, AC-9 um
  `is_silenced()`-Prüfung, AC-13 um eine eigene positive Assertion; Mutation 6
  (Rückfrage darf `process()` nicht aufrufen) ergänzt; vorgeschlagene Testdateinamen
  ergänzt.
- 2026-09-16 (TDD-RED, Konsistenz): Abschnitt 6 an die freigegebene AC-9 angeglichen —
  leeres `previous_schedule` ⇒ `"daily"` (vorher widersprüchlich „kein Sonderfall").
  Die Namen `resolve_active_target`, Ergebnis mit `.kind`/`.target`/`.text`,
  `InboundMessage.resolved_kind`/`resolved_preset_id` sind mit den RED-Tests bindend.
  Zusätzliche positive Regressionskontrolle: `tests/tdd/test_trip_eingang_regressionskontrolle.py`.
