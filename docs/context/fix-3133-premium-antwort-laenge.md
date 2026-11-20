# Context: fix-3133-premium-antwort-laenge

## Request Summary
Befehlsantworten an die Premium-SMS (Garmin inReach, Grenze 153 Zeichen) gehen ungekürzt raus (HELP Trip 456, HELP Vergleich 158, CODES 761, unbekannter Befehl 185). **PO-Entscheidung 2026-11-20 (Issue-Kommentar #3133): seitenweise** — jede Antwort genau eine Nachricht ≤ 153, am Ende Verweis wie „mehr: HILFE 2"; der Nutzer fragt die nächste Seite selbst ab. Verworfen: automatische Aufteilung 1/n (Kontingent 15/Tag), Kurzfassung + Rest per Mail (Kanal-Parität ADR-0095).

## Related Files
| File | Relevance |
|------|-----------|
| src/services/inbound_sms_reader.py:197-476 | Eingang Premium-SMS → `_verarbeite_befehl` → Prozessor → `send_command_reply_premium_sms` (:470); ziellos-Zweig :428 (ZIELLOS_SCHLUESSEL = hilfe, columns, kuerzel), Mehrdeutig-Hinweis :444-451 |
| src/services/notification_service.py:2260-2285 | `send_command_reply_premium_sms`: eine Kontingent-Reservierung, ein `send()` mit ungekürztem Body |
| src/services/trip_command_processor.py | `hilfe_kurzform` :444, `codes_text` :498, `unknown_command_body` :400, `_KURZFORM_KANAELE` :875, `_KURZFORM_MAX_ZEICHEN`=160 :878, `process` :1202 (`self._en`), `_parse_command` :1426 (liefert value, „HILFE 2" → ("hilfe","2"), value wird bei hilfe/kuerzel :1358-1361, :1524-1527 verworfen), `_show_help_for_kind` :1537, `_show_codes` :1551, Drilldown-Kürzung `_format_drilldown_kurzform` :2228-2278 |
| src/services/trip_selection.py:72 | ZIELLOS_SCHLUESSEL |
| src/output/channels/premium_sms.py, seven_io_base.py:193-222 | Transport: ein POST, kein Kürzen/Teilen |
| src/output/renderers/channel_layout.py:57 | CHANNEL_LIMITS["premium_sms"].max_chars = 153 |
| src/utils/ascii_fold.py:51 | fold_ascii kann verlängern → erst falten, dann messen |

## Weitere potenziell > 153 (datenabhängig)
STATUS `_show_status` :2859 (Zeile je Etappe), RUHETAG :2746, STARTDATUM :2820, PAUSE-Bestätigung (langer Trip-Name), JETZT `_show_now` :3024, STRECKE (nutzt Telegram-Format für premium_sms :3259), GLANCE/GEWITTER `_handle_query` :1779-1807, Mehrdeutig-Hinweis (Namensliste), Vergleich `_compare_versand` :1575 („ohne Daten: <liste>").

## Existing Patterns
- Argumente zu Befehlen existieren (PAUSE 2D, RUHETAG n, STRECKE km, STARTDATUM, REPORT morning) → Seitenzahl als `value` passt ins Muster.
- Drilldown-Kurzform kürzt schon (hintere Gruppen weg, „+Nh not shown"), aber auf 160 statt 153.
- Briefing-Premium-Text wird mit Grenze 153 neu formatiert (#3100).

## Dependencies / Dependents
- `hilfe_kurzform` läuft auch für Telegram mit `msg.englisch=True`; `codes_text` für alle Kanäle (Telegram/E-Mail en); `unknown_command_body` auch im Telegram-Reader. **Seitenlogik darf nur an `channel == "premium_sms"` hängen**, nie an `self._en` oder in den Textbausteinen selbst. `sms` steht in `_KURZFORM_KANAELE`, hat aber keinen produktiven Eingang.
- Kontingent ADR-0116 Nr. 6: `premium_sms_reply` 15/Tag; jede Seite = eine Antwort = ein Platz.

## Existing Specs (werden berührt / teilweise abgelöst)
- docs/specs/modules/feat_2417_kurzform_englisch.md: AC-8 (HELP ≤ 3 Segmente, verbindlicher Wortlaut), AC-9 (CODES ≤ 5 Segmente), Known Limitation :352 → für premium_sms abgelöst durch #3133.
- feat_2417_befehle_e2e_echter_eingang.md, feat_2420_befehle_anzeigen.md, feat_2184_s4_premium_sms_kommandoverarbeiter.md, feat_3100_premium_sms_fallliste.md.
- docs/reference/premium_sms_format.md §1/§4/Sprache (Budget 160 vs 153 angleichen), sms_format.md §5a („genau eine Nachricht", Drilldown 160).
- ADR-0049, ADR-0116, ADR-0095.

## Tests (Muster + betroffene)
- Muster: `tests/tdd/test_3100_premium_sms_fallliste.py` (`_eingang`, `_trip_premium_ueber_eingang`), Aufzeichner `tests/helpers/transport_mitschrift.py::aufzeichner_installieren` (`mit.sendungen("premium_sms")`), Eingang `tests/tdd/test_premium_sms_kommandopfad.py`; HTTP-Recorder `tests/tdd/_befehl_e2e_fixtures.py::sende_premium_sms`.
- Werden rot und müssen angepasst werden: `test_kurzform_befehle_englisch.py` (HELP/CODES-Wortlaut — Telegram-Wortlaut muss gleich bleiben, nur Premium ändert sich), Segment-Tests in `test_befehle_premium_sms_e2e.py` (:331, :353, :399), `test_befehlsangebot_vollstaendig.py:79`.

## Risks & Considerations
- Seitenschnitt an Zeilengrenzen (Befehle/Codes nicht mitten im Eintrag zerschneiden); Verweis-Text selbst zählt ins Budget.
- Seitenzahl außerhalb des Bereichs (HILFE 9) → definierte Antwort.
- Generische Lösung (jede Premium-Antwort > 153 wird geseitet) vs. nur HELP/CODES: datenabhängige Antworten (STATUS etc.) wären mit „mehr: STATUS 2" nur stabil, wenn die Neuberechnung deterministisch ist. Alternative: universelles „MORE/MEHR" über gespeicherte letzte Antwort je Nutzer (Zustand). → Analyse-Entscheidung.
- Neues Befehlswort (MORE/MEHR) wäre ein Eintrag in `_COMMAND_SPECS` und taucht in HELP aller Kanäle auf.
- Drilldown-Grenze 160 → 153 angleichen.

## Analysis

### Type
Bug (Premium-SMS-Befehlsantworten > 153 Zeichen gehen ungekürzt raus); Lösungsrichtung durch PO festgelegt: seitenweise.

### Entscheidung Ansatz (Tech Lead, nach Plan/Sonnet-Bewertung)
**Ansatz A + zentrales Sicherheitsnetz.**
- **Seiten** nur für die statischen, nebenwirkungsfreien Texte: HILFE/HELP (route UND vergleich) und KÜRZEL/CODES. Seitenzahl als `value` aus `_parse_command` („HILFE 2" → ("hilfe","2")), bisher in `process()` :1358-1361 und Vergleichs-Dispatch :1524-1527 verworfen → durchreichen (F5: auch im Vergleichs-Dispatch).
- **Harte Kürzung mit Kennzeichen** zentral in `send_command_reply_premium_sms` (notification_service.py ~2278) vor `send()`, für ALLE übrigen Premium-Antworten (STATUS, RUHETAG, STARTDATUM, PAUSE-Bestätigung, JETZT, STRECKE, GLANCE/GEWITTER, Mehrdeutig-Hinweis, Vergleich-Versand „ohne Daten", Fehler/Kontingent). Immer erst `fold_ascii`, dann messen (F3: Premium-Weg faltet bisher nirgends; ein Nicht-GSM-Zeichen → UCS-2).
- **Unbekannter Befehl (F1):** keine Seiten (HILFE 2 setzt den Fehlertext nicht fort) — Premium bekommt eine Fassung ≤ 153 mit Verweis auf HILFE/HELP. Tech-Lead-Entscheidung im Rahmen der PO-Vorgabe „jede Antwort genau eine Nachricht ≤ 153", in der Spec als AC sichtbar.
- **Verworfen:** B (generischer Seiten-Wrapper: PAUSE/RUHETAG schreiben Daten erneut, „2" kollidiert mit PAUSE 2D/STRECKE km/STARTDATUM/REPORT, STATUS/JETZT wetter-/zeitabhängig und buchen `manueller_abruf` ADR-0117); C (MEHR/MORE mit gespeicherter letzter Antwort: neuer Zustand je Nutzer, TTL, Isolation, neuer HELP-Eintrag in allen Kanälen) → ggf. Folge-Ticket, falls datenabhängige Antworten im Betrieb häufig gekürzt werden.

### Seitenmechanik
- Neues reines Modul `src/services/premium_sms_pages.py`: `paginate(zeilen, page, *, verweis_fn, limit=153) -> str`. Jede Zeile falten → messen, Verweis zählt ins Budget, greedy ganze Einträge (nie mitten im Befehl/Code schneiden), Einzelzeile > 153 hart kürzen, Seitenzahl aus Gesamtlauf, letzte Seite ohne Verweis.
- Aufruf nur bei `msg.channel == "premium_sms"` in `_show_help`/`_show_help_for_kind`/`_show_codes`; NIE an `self._en` (trifft Telegram) und nie in `hilfe_kurzform`/`codes_text` → Telegram-/E-Mail-Wortlaut unverändert.
- Ungültige Seite: „abc"/≤0 → Seite 1; > N → kurze Antwort „HELP: pages 1-N" (de: „HILFE: Seiten 1-N").
- Verweis-Text über i18n-Katalog `i18n/messages/{de,en}/inbound.json` (Muster `inbound.kuerzel.*`), z. B. `inbound.seite.mehr` = „mehr: {befehl} {n}" / „more: {befehl} {n}"; {befehl} = Befehlswort in Nutzersprache (HILFE/HELP, KUERZEL/CODES).
- Achtung: neues Argument „[Seite]" in `_COMMAND_SPECS.arg_en` würde HELP-Text aller Kanäle ändern → nur aufnehmen, wenn bewusst; sonst steht der Verweis selbst als Erklärung. Entscheidung in Spec: NICHT in `_COMMAND_SPECS` aufnehmen (Telegram-Wortlaut bleibt).
- Ziellos-Zweig (`ZIELLOS_SCHLUESSEL`) darf durch value nicht anders auflösen (Doppel-Parse reader → `_ParseNurProcessor` → process).
- Drilldown-Grenze `_KURZFORM_MAX_ZEICHEN`=160 (F6) kanalabhängig über `CHANNEL_LIMITS` (premium_sms 153, sms 160).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/premium_sms_pages.py | CREATE | reine Seiten-/Kürz-Funktion (~70 LoC) |
| src/services/trip_command_processor.py | MODIFY | Seiten-Weiche hilfe/kuerzel (route+vergleich), Premium-Fassung unbekannter Befehl, Drilldown-Grenze kanalabhängig (~40) |
| src/services/notification_service.py | MODIFY | `send_command_reply_premium_sms`: falten + harte Kürzung vor `send()` (~15) |
| src/i18n/messages/{de,en}/inbound.json | MODIFY | Verweis- und Bereichs-Texte (~6 Schlüssel) |
| tests/tdd/test_3133_premium_antwort_laenge.py | CREATE | am echten Eingang (Muster test_3100_premium_sms_fallliste.py, `mit.sendungen("premium_sms")`), alle Seiten ≤153 und vollständig, Telegram unverändert, zwei Nutzer |
| tests/tdd/test_kurzform_befehle_englisch.py, test_befehle_premium_sms_e2e.py (:331/:353/:399), test_befehlsangebot_vollstaendig.py:79 | MODIFY | Premium-Erwartungen auf Seiten umstellen |
| docs/reference/premium_sms_format.md, sms_format.md §5a, docs/specs/modules/feat_2417_kurzform_englisch.md (AC-8/AC-9, Known Limitation :352) | MODIFY | 153-Budget, Seiten, Ablösung für premium_sms |

### Scope Assessment
- Files: ~10 (3 Produktiv + 1 neu, i18n, Tests, Docs)
- Estimated LoC: ~+120 Produktiv, ~+190 Tests, Docs
- Risk Level: MEDIUM — zentraler Versandweg der Premium-Antworten; Telegram-Wortlaut muss nachweislich gleich bleiben.

### Dependencies
Kontingent ADR-0116 (15 Antworten/Tag, jede Seite = ein Platz, Kürzung erzeugt keinen Mehrverbrauch; Gate läuft vor der Kürzung, unkritisch da rein). Kanal-Parität ADR-0095 (alle Hilfe-/Codes-Inhalte über Seiten erreichbar). ADR-0104 i18n.

### Open Questions
- keine offenen Produktfragen; Kürzung datenabhängiger Antworten (Inhaltsverlust bei sehr langem STATUS) wird in der Spec als AC + Known Limitation sichtbar gemacht, Folge-Ticket MEHR/MORE nur bei Bedarf.
