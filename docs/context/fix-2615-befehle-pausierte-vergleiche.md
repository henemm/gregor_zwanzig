# Context: fix-2615-befehle-pausierte-vergleiche

## Request Summary
Wetterbefehle `heute`/`morgen`/`report` fragen „Mehrdeutig/Ambiguous“, obwohl genau EIN Ortsvergleich aktiv ist und alle anderen pausiert sind (Prod, PO 24./25.10.). Zusätzlich sind die auf 4 Zeichen gekürzten Premium-SMS-Rückfrage-Namen bei gleichem Anfang („Zill“/„Zill“) nicht unterscheidbar.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_selection.py:123` | `_vergleich_ist_aktiv` zählt Pausierte bewusst als aktiv (#2282, wegen `weiter`) |
| `src/services/trip_selection.py:72` | `_BEIDE_KINDS_ONLY_SCHLUESSEL` = pause, weiter, report, heute, morgen — alle durch denselben Filter |
| `src/services/trip_selection.py:205` | `resolve_active_target` (Entscheidungstabelle, Filter Z. 223) |
| `src/services/trip_selection.py:267` | `resolve_command_target` — Weiche je Befehlsschlüssel |
| `src/services/trip_selection.py:172-202` | `_rueckfrage_text` / `_rueckfrage_mit_laenge` — Kürzen auf min. 4 Zeichen (Premium-SMS) |
| `src/services/compare_alert_guard.py:48` | `is_silenced()` — vorhandene SSOT für „pausiert/archiviert/abgelaufen“ (paused_at, schedule=="manual", archived_at, end_date) |
| `src/services/inbound_telegram_reader.py:281,507` | Aufrufer: `resolve_command_target` (Text) UND `resolve_active_target` direkt für Knopf `act_pause` |
| `src/services/inbound_sms_reader.py:380` | Aufrufer Premium-SMS (`resolve_command_target`) |
| `src/services/trip_command_processor.py:1354` | Namensgleichheit Trip/Vergleich → `resolve_active_target` (Rückfrage) |

## Existing Patterns
- Eine geteilte Auflösung für Telegram + Premium-SMS (#2417 AC-18); E-Mail geht über denselben Processor.
- Ziel-Klassifizierung nach Befehlsschlüssel: ziellos / Trip-only / beide Kinds.
- Rückfrage-Text: Telegram volle Namen, Premium-SMS GSM-7-gefaltet und ≤160 Zeichen gekürzt.

## Dependencies / Dependents
- Upstream: `fold_ascii`, `pick_active_trip`, Preset-Dicts (`paused_at`, `schedule`, `archived_at`, `end_date`).
- Downstream: Telegram-Reader, SMS-Reader, Command-Processor (Rückfrage bei Namensgleichheit), Tests `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py` (u. a. AC-2 „1 Vergleich pausiert, 0 Trip → eindeutig“), `test_trip_auswahl_geteilt.py`, `test_befehle_*_e2e.py`.

## Existing Specs
- `docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md` (Entscheidungstabelle, „Pause zählt als aktiv“)
- `docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md`

## Risks & Considerations
- `pause`/`weiter` müssen pausierte Vergleiche weiter adressieren können (sonst nie „weiter“).
- Offene Randfälle für die Analyse: nur pausierte Vergleiche vorhanden + `heute` (→ Rückfall auf bisheriges Verhalten oder „kein aktives Ziel“?); Trip + 1 aktiver + n pausierte Vergleiche; Knopf `act_pause` bleibt beim alten Verhalten.
- „Pausiert“ SSOT ist `is_silenced()` — nicht neu erfinden (archived/end_date werden schon in `_vergleich_ist_aktiv` behandelt).
- Rückfrage-Namen: Eindeutigkeit nach Kürzen (und nach GSM-7-Faltung!) sicherstellen; Antwort-Parser muss den gekürzten/nummerierten Namen wieder auflösen können — noch zu prüfen.
- Multi-User: Test mit zwei Nutzern (Pause eines Nutzers darf den anderen nicht beeinflussen).

## Analysis

### Type
Bug (nutzersichtbar, Prod, 2 Teilbefunde im selben Auflösungs-Baustein)

### Befund 1 — Pausierte zählen bei heute/morgen/report mit (bestätigt durch Codelesen)
`resolve_command_target` schickt `pause/weiter/report/heute/morgen` durch `resolve_active_target`; dort filtert `_vergleich_ist_aktiv` nur archiviert/abgelaufen. 0 Trips + 6 nicht archivierte (5 pausierte) Vergleiche ⇒ Zeile 229ff „>=2 Vergleiche → mehrdeutig“. Ausnahme „Pause zählt als aktiv“ ist nur für `pause`/`weiter` nötig.

### Befund 2 — Rückfrage-Namen (VERSCHÄRFT gegenüber Ticket)
Nicht nur „nicht unterscheidbar“: Der Antwort-Parser `match_leading_name` (trip_command_processor.py:~110) und `_find_compare_preset` vergleichen **exakt** (normalisiert/GSM-7-gefaltet), KEIN Präfix. Eine gekürzte Antwort „Muen pause“ (Name „München …“) findet **nichts** ⇒ die gekürzte Premium-SMS-Rückfrage ist auch bei eindeutigen Namen nicht beantwortbar (kostenpflichtige Endlosschleife). Kürzen (`_rueckfrage_text`, Boden 4 Zeichen) ist nur dann harmlos, wenn der Name ≤ Kürzlänge ist.

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| src/services/trip_selection.py | MODIFY | `resolve_active_target(..., pausierte_ausblenden=False)`; `resolve_command_target` setzt es für `report/heute/morgen`; Rückfall auf bisheriges Verhalten, wenn KEIN aktiver Vergleich übrig (Pausierte per `is_silenced`-SSOT, nicht neu erfinden). Kürzen in `_rueckfrage_text`: Länge so wählen, dass gekürzte Namen paarweise eindeutig sind |
| src/services/trip_command_processor.py | MODIFY | `match_leading_name` + `_find_compare_preset`: Fallback „eindeutiges Präfix (≥4 Zeichen, nach exakt/gefaltet)“, damit gekürzte Antworten auflösen; Mehrfachtreffer ⇒ weiter mehrdeutig, nie erster |
| tests/tdd/test_eingangsauswahl_trip_und_vergleich.py (o. neue Datei nach Verhalten) | MODIFY/CREATE | s. u. |

Unverändert: Telegram-Knopf `act_pause` (ruft `resolve_active_target` direkt, Default = altes Verhalten), `pause`/`weiter`, Namensgleichheit Z. 1354 (Default).

### Technischer Ansatz (Empfehlung)
1. Pausierte-Filter nur für `heute/morgen/report` (additiver Parameter, Default alt ⇒ `pause/weiter/act_pause/Z.1354` unberührt).
2. Rückfall: gibt es nach Filter 0 aktive Vergleiche, aber pausierte, gilt das bisherige Verhalten (1 pausierter ⇒ eindeutig, AC-2 bleibt grün; mehrere ⇒ Rückfrage). Begründung: ein ausdrücklicher Befehl an einen einzigen pausierten Vergleich bleibt möglich.
3. Rückfrage-Namen: Kürzlänge nach Faltung so erhöhen, bis alle eindeutig (Boden 4); passt es nicht in 160 Zeichen ⇒ Kandidaten durchnummerieren NICHT (würde neuen Parser brauchen) — stattdessen Präfix-Fallback im Parser (Punkt 3) und bei Nicht-Eindeutigkeit trotz Maximallänge volle Länge priorisieren, Anzahl-Hinweis „+N weitere“ nur wenn nötig. Identische Namen (zwei Orte exakt „Zill…“ gleich) sind auch vollständig nicht adressierbar ⇒ in der Spec als Randfall festlegen (Rückfrage nennt dann Hinweis, im Frontend umbenennen).
4. Parser: Präfix-Fallback erst NACH exakt und gefaltet exakt, nur wenn Präfix-Treffer genau 1 Kandidat und `_rest_ist_gueltiger_befehl(rest)`.

### Scope
Dateien: 2 Prod + 1–2 Test; ~+70/−10 LoC; Risiko MITTEL (zentrale Auflösung für alle Kanäle; Präfix-Matching könnte Trip-Namen-Kollisionen erzeugen ⇒ nur als letzter Fallback, nur eindeutig).

### Dependencies
Telegram-Reader (281, 507), Premium-SMS-Reader (380), Processor (1354), `compare_alert_guard.is_silenced`. E-Mail geht über den Processor mit Betreff-Namen (kein Mehrdeutigkeits-Zweig über `resolve_command_target`) — in Spec/Test belegen.

### Tests (Nutzersicht, Kern-Schicht, zwei Nutzer)
- 0 Trips, 1 aktiv + 5 pausiert: `heute/morgen/report` ⇒ eindeutig der aktive (rot vor Fix).
- `pause`/`weiter` mit denselben Daten ⇒ unverändert mehrdeutig; Trip + pausierte ⇒ Trip.
- Nur pausierte (1 ⇒ eindeutig; mehrere ⇒ Rückfrage).
- Premium-SMS-Rückfrage: gekürzte Namen paarweise eindeutig; Antwort „Muen pause“ löst auf den richtigen Vergleich auf (Roundtrip Rückfrage→Antwort).
- Zweiter Nutzer: Pausen des einen beeinflussen den anderen nicht.
- Mutation: Filter für `pause` aktiv schalten ⇒ muss Test rot machen.

### Open Questions
- [x] Nur pausierte + `heute`: Rückfall auf bisheriges Verhalten (Tech-Entscheid, kein PO-Thema).
- [ ] Spec-AC auf Deutsch zur Freigabe: Formulierung „Wetterbefehle heute/morgen/report ignorieren pausierte Ortsvergleiche, solange mindestens ein aktiver existiert“.
