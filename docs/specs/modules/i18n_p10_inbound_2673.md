---
entity_id: i18n_p10_inbound_2673
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2673, python, model-sonnet]
---

# i18n P10: Inbound-Befehle und Antworten zweisprachig

**Issue:** #2673 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 1, 2, 4, 6

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer unterwegs einen Befehl an Gregor schickt (E-Mail-Antwort, Telegram, Premium-SMS), bekommt die Antwort in der Sprache seines Kontos: ein Nutzer mit `language=en` liest `Rest day added: +2 days.`, ein Nutzer mit `de` liest unverändert `Ruhetag eingetragen: +2 Tage.`. Befehlswörter beider Sprachen (`RUHETAG`/`RESTDAY`, `HILFE`/`HELP`, `ABBRUCH`/`CANCEL` …) werden auf jedem Eingangskanal verstanden, unabhängig von der Kontosprache. Die Kurzform-Logik der Premium-SMS und des Telegram-Kurzstils (`self._en`, #2417) ist Platzform und bleibt byte-gleich; die neue Nutzersprache (`self._lang`) wird davon sauber getrennt.

## Source

- **File:** `src/services/trip_command_processor.py`, `src/services/inbound_telegram_reader.py`, `src/services/inbound_sms_reader.py`, `src/services/inbound_email_reader.py`, `src/services/trip_selection.py`, `src/output/renderers/email/command_block.py`
- **Identifier:** `TripCommandProcessor.process` (Z. 1108, setzt `self._en` in Z. 1118), `TripCommandProcessor._t` (Z. 1105), `_COMMAND_SPECS` (Z. 287-323), `_BARE_KEYWORD_MAP` (Z. 232-252, ergänzt Z. 327-329), `_VALID_COMMANDS` (Z. 228), `command_rows` (Z. 332), `command_overview` (Z. 364), `unknown_command_body` (Z. 369), `hilfe_kurzform` (Z. 387), `codes_text` (Z. 441), `telegram_englisch` (Z. 479), `TripCommandProcessor._show_help` (Z. 2854), `_show_help_for_kind` (Z. 1438), `_show_codes` (Z. 1456), `_show_status` (Z. 2826), `_apply_ruhetag` (Z. 2610), `_cancel_trip` (Z. 3337), `_resume_trip` (Z. 3357), `_on_demand_failure_body` (Z. 925), `InboundTelegramReader._send_unknown_command` (Z. 322), `_dispatch_and_reply` (Z. 336), `_antworte_auf_knopf` (Z. 484), `_process_start_command` (Z. 612), `_verarbeite_befehl` im Premium-SMS-Reader (Z. 351), `_process_single_inner` im E-Mail-Reader (Z. 217), `resolve_active_target` / `resolve_trip_only_target` / `resolve_command_target` / `_rueckfrage_text` in `trip_selection.py` (Z. 175-319)

> **Schicht-Hinweis:** Reiner Python-Core (`src/services/`, `src/output/renderers/email/`). Kein Go-, kein Frontend-Code. Die Sprache liest Python über `resolve_user_lang(user_id)` aus `data/users/<id>/user.json` (Paket P1 #2662, Feld legt S1 #2646 an). Die statische Telegram-Befehlsliste `BOT_COMMANDS` in `src/output/channels/telegram.py` (Z. 132-165) wird von `prod_selftest.py` per `ast.literal_eval` gelesen und gehört zu P7 (#2669), nicht hierher.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Die Befehlsverarbeitung ist bereits geteilt (`_COMMAND_SPECS` mit `kinds`, `_dispatch_compare`, `command_rows(kind)`); kein neuer Baustein mit Pendant entsteht. Texte, die Trip und Ortsvergleich identisch verwenden (Hilfe-Kopf, `Trip nicht gefunden`, `Briefing jetzt senden`), liegen **einmal** in `inbound.*`, nie je Kind doppelt. Die Vergleichs-Varianten stehen als `…beschreibung_vergleich` neben der Trip-Beschreibung.
> - **Mandantentrennung:** `resolve_user_lang(msg.user_id)` mit der `user_id` der eingehenden Nachricht (E-Mail: aus dem aufgelösten Absender, Telegram: aus der Chat-Zuordnung, Premium-SMS: aus der Antwort des Lern-Endpunkts); **kein** Fallback auf `"default"`, keine Modul- oder Prozess-globale Sprache. Zwei Nutzer in einem Prozesslauf bekommen je ihre Sprache (AC-6).
> - **Kanäle:** Berührt sind die Eingangs-/Antwortkanäle E-Mail, Telegram und Premium-SMS sowie der Kanalname `sms` (steht in `_KURZFORM_KANAELE`, hat heute keinen produktiven Eingang). Alle vier Kanäle sind in der Tabelle „Kanal × Nutzersprache" benannt; gleicher Inhalt, kanalgerechte Form.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/services/trip_command_processor.py` | MODIFY | `self._lang` einführen, `_t(de, en)`-Paare und deutsche Literale auf `_m(key)` umstellen, `_COMMAND_SPECS`-Beschreibungen aus dem Katalog, `command_rows`/`unknown_command_body`/`codes_text`/Hilfe mit `lang`, Bare-Wörter `abbruch`/`cancel` |
| `src/services/inbound_telegram_reader.py` | MODIFY | Nutzersprache einmal je Nachricht auflösen und durchreichen; Registrierungs-, Verbunden-, Konflikt-, Lade- und Unbekannt-Texte aus dem Katalog; Log-Zeilen mit `# i18n-log` |
| `src/services/inbound_sms_reader.py` | MODIFY | Nutzersprache aus `user_id` auflösen und an `resolve_command_target` geben; `Hinweis`-Betreff aus dem Katalog; Log-Zeilen mit `# i18n-log` |
| `src/services/inbound_email_reader.py` | MODIFY | Antwort `Trip nicht gefunden` (Z. 256-264) aus dem Katalog in Nutzersprache; Log-Zeilen mit `# i18n-log` |
| `src/services/trip_selection.py` | MODIFY | Texte `KEIN_KANDIDAT_TEXT*`, `KEIN_AKTIVES_ZIEL_TEXT*`, Rückfrage `Mehrdeutig:` aus dem Katalog; neues keyword-only `lang` an den drei `resolve_*`-Funktionen |
| `src/output/renderers/email/command_block.py` | MODIFY | nur die beiden Aufrufe `command_rows(kind)` (Z. 18 und Z. 25) auf `command_rows(kind, lang=lang)`; Kopfzeile, Eyebrow und Hinweis gehören P3 (#2665) |
| `src/i18n/messages/de/inbound.json` | MODIFY | Bereichsdatei `inbound` (von P1 leer angelegt): deutsche Texte, wörtlich wie heute |
| `src/i18n/messages/en/inbound.json` | MODIFY | Bereichsdatei `inbound`: englische Texte laut Glossar |
| `tests/tdd/test_befehle_nutzersprache_antworten.py` | CREATE | Antwortsprache je Kanal und Kontosprache (AC-1, AC-2, AC-7) |
| `tests/tdd/test_befehle_kurzform_sprachunabhaengig.py` | CREATE | Premium-SMS/Telegram-Kurzform unverändert für `de` und `en` (AC-3, AC-4) |
| `tests/tdd/test_befehle_beide_sprachen_erkannt.py` | CREATE | alle Wörter der Befehlstabelle in beiden Kontosprachen und auf allen Eingangskanälen (AC-5) |
| `tests/tdd/test_befehle_zwei_nutzer_sprache.py` | CREATE | zwei Nutzer, derselbe Befehl, je eigene Sprache (AC-6) |
| `tests/test_i18n_inbound_katalog_paritaet.py` | CREATE | Schlüssel- und Platzhalterparität des Bereichs `inbound`, Ratsche für die fünf Dateien (AC-8, `# doc-compliance-test`) |
| `tests/golden/inbound/*.de.txt`, `tests/golden/inbound/*.en.txt` | CREATE | deutsche Golden-Dateien (vor der Umstellung geschrieben) und englische Review-Dateien |
| `tests/fixtures/i18n_python_allowlist.json` | MODIFY | Einträge der fünf Quelldateien entfernen (Anlage durch P11 Teil 1, #2674) |
| `tests/tdd/test_befehlsangebot_vollstaendig.py`, `tests/tdd/test_kommandoliste_einzelquelle.py`, `tests/tdd/test_kurzform_befehle_englisch.py`, `tests/test_hilfe_befehle_drift.py`, `tests/tdd/test_befehlsblock_trip_und_vergleich_mail.py` | MODIFY (nur falls rot) | bestehende Drift-Tests lesen `_COMMAND_SPECS`-Felder per Namen; bleiben grün, weil `beschreibung_de`/`wirkung_en` byte-gleiche Werte behalten |

## Estimated Scope

- **LoC:** ca. 450 Code ohne Tests und ohne Katalogdaten (Prozessor ca. 330, Reader ca. 60, `trip_selection.py` ca. 40, `command_block.py` 2). Der Katalog umfasst ca. 220 Schlüssel je Sprache. Das überschreitet das Workflow-Limit von 250 LoC: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** 8 Code-/Katalogdateien, 6 neue Testdateien, ca. 10 Golden-Dateien.
- **Effort:** high (3.555 Zeilen Prozessor, Grammatik, Kurzform-Logik #2417).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2662 P1 (`src/i18n`: `t`, `tn`, `resolve_user_lang`, `fmt_date`; `MetricDefinition.label(lang)`) | Paket | Katalog-Zugriff, Sprachauflösung, englische Wettergrößen-Namen für die Hilfe |
| #2646 S1 | Paket | Feld `language` in `user.json` |
| #2665 P3 | Paket | `command_block.py`: `lang`-Parameter an `render_commands_plain/html` und Mail-Texte; P10 ändert dort nur die beiden `command_rows`-Aufrufe |
| #2674 P11 Teil 1 | Paket | Ratsche und Allowlist; P10 kürzt sie |
| #2663 PV | Paket | Validator-Sprachlauf; Befehlsblock der Briefing-Mail wird dort geprüft |
| `app.metric_catalog` (`MetricDefinition.kuerzel_bedeutung_de/en`, `col_label`, `sms_code`) | Modul | Kürzel-Bedeutungen; Kürzel selbst bleiben eingefroren |
| `output.tokens.builder`, `output.tokens.hazard_symbols` (`*_BEDEUTUNG_DE/EN`) | Modul | `codes_text` liest beide Sprachen bereits heute |
| `tests/fixtures/metric_tokens_frozen.json`, `tests/test_metric_tokens_eingefroren.py` | Test | Token-Wächter (P1); muss grün bleiben |
| ADR-0104, ADR-0042, ADR-0095 | ADR | Sprache am Nutzer; Kurzform ist Platzform; Kanal-Parität |

## Implementation Details

### 1. Zwei getrennte Begriffe

- `self._en: bool` — **unverändert** das Kurzform-Kanal-Flag (`msg.englisch or msg.channel in _KURZFORM_KANAELE`, Z. 1118). Es entscheidet über Platzform (GSM-7, ≤ 160 Zeichen, englische Befehlswörter, Kürzel, `hilfe_kurzform`, `codes_text(True)`). Es wird nicht umbenannt und nicht aus der Nutzersprache abgeleitet.
- `self._lang: Lang` — **neu**, Klassenattribut-Default `"de"`, in `process()` direkt nach Z. 1118 genau einmal gesetzt: `self._lang = resolve_user_lang(msg.user_id)`.
- Antworttext-Regel in einer Methode, ersetzt `_t(de, en)`:

```python
def _m(self, key: str, **params: object) -> str:
    """Antworttext: Kurzform-Kanal = englischer Katalogtext (wie heute die en-Branche
    von _t), sonst die Nutzersprache. Schlüssel ohne Bereichspräfix."""
    lang = "en" if self._en else self._lang
    return t(f"inbound.{key}", lang, **params)
```

Folge: Der englische Katalogtext eines Schlüssels ist **wörtlich** der heutige `en`-Zweig des `_t`-Paars (GSM-7-sicher, byte-gleich zu heute auf Premium-SMS und Telegram-Kurzform). Der deutsche Katalogtext ist wörtlich der heutige `de`-Zweig. Für Texte, die heute nur deutsch existieren (Langform-Hilfe, `Trip nicht gefunden`, Stundenverlauf-Überschriften), schreibt P10 neue englische Texte nach Glossar. Plural über `tn(f"inbound.{key}", count, lang, …)`.

Strings, die **ausschließlich** in `if self._en:`-Zweigen stehen (Kurzform-Aufbau wie `storms {stufe}`, `Storm risk today (…)`, `hilfe_kurzform`-Zeilen, `wirkung_en`, `arg_en`) und weder Umlaut, ß noch Signalwort tragen, bleiben als englische Platzform-Literale im Code (ADR-0104 Nr. 5; die Ratsche meldet sie nicht). Die `if self._en:`-Zweige selbst bleiben strukturell unangetastet.

### 2. Befehle in beiden Sprachen (Tabelle Befehl × Sprache)

Alle Wörter beider Spalten werden auf **jedem** Eingangskanal erkannt (E-Mail, Telegram, Premium-SMS), unabhängig von der Kontosprache: `_BARE_KEYWORD_MAP` ist die Vereinigung (Z. 327-329 leitet `wort_en` aus `_COMMAND_SPECS` ab). Die Kontosprache bestimmt nur, welche Wörter die **Hilfe** zeigt und in welcher Sprache geantwortet wird.

| Interner Schlüssel | Deutsch (`wort`) | Englisch (`wort_en`) | Bemerkung |
|---|---|---|---|
| heute | HEUTE | TODAY | Trip und Ortsvergleich (`_BEIDE_KINDS`) |
| morgen | MORGEN | TOMORROW | Trip und Ortsvergleich |
| now | JETZT (auch NOW) | NOW | `now` steht heute schon in `_BARE_KEYWORD_MAP` |
| heute_gewitter | GEWITTER | STORMS | nur Trip |
| strecke | STRECKE `[km]` | ROUTE `[km]` | nur Trip |
| ruhetag | RUHETAG `[N]` | RESTDAY `[N]` | nur Trip |
| status | STATUS | STATUS | gleiches Wort in beiden Sprachen |
| pause | PAUSE `[2d / 12h]` | PAUSE `[2d / 12h]` | Trip; am Ortsvergleich ohne Dauer |
| skip | SKIP | SKIP | nur Trip |
| abbruch | STOP (auch ABBRUCH) | STOP (also CANCEL) | **neu als Alleinwort:** `abbruch` und `cancel` (bisher nur `### abbruch`); keine eigene Zeile in `_COMMAND_SPECS` (Alias, `test_befehlsangebot_vollstaendig.py` Z. 348 bleibt wahr) |
| weiter | WEITER | RESUME | Trip und Ortsvergleich |
| hilfe | HILFE | HELP | Trip und Ortsvergleich; ziellos |
| kuerzel | KUERZEL / KÜRZEL | CODES | Trip und Ortsvergleich; ziellos |
| startdatum | STARTDATUM `JJJJ-MM-TT` | STARTDATE `YYYY-MM-DD` | nur Trip; Argumentform in der englischen Hilfe `YYYY-MM-DD` |
| report | REPORT `[morning / evening]` | REPORT `[morning / evening]` | Trip und Ortsvergleich |

Protokoll-Token bleiben unverändert und stehen nie im Katalog: `wort`, `wort_en`, `kinds`, `arg`, `arg_en`, `callback_data` der Telegram-Knöpfe, `col_label`, `sms_code`, Kürzel.

### 3. Antwortform je Kanal und Kontosprache (Tabelle Kanal × Nutzersprache)

| Kanal / Lage | Konto `de` | Konto `en` |
|---|---|---|
| E-Mail-Antwort (`channel="email"`, Langform) | Antworttext deutsch wie heute; Hilfe mit deutschen Wörtern und Beschreibungen | Antworttext englisch; Hilfe mit englischen Wörtern (`wort_en`) und englischen Beschreibungen; Wettergrößen mit `metric.label("en")`; Kürzel unverändert |
| Telegram, Standardstil, Wort ohne Kurzform-Bezug (`STATUS`, `HILFE`, `KUERZEL`, `RUHETAG` …) | Langform deutsch wie heute | Langform englisch |
| Telegram, Standardstil, ziellos mit englischem Wort `HELP`/`CODES` (#2417 AC-5) | Kurzform englisch wie heute | Kurzform englisch (identisch) |
| Telegram, Ziel mit `telegram_style="kurzform"` | Kurzform englisch wie heute | Kurzform englisch (identisch) |
| Premium-SMS (`channel="premium_sms"`) | Kurzform englisch, GSM-7, wie heute (#2417 AC-4) | Kurzform englisch, identisch |
| SMS (`channel="sms"`, kein produktiver Eingang) | wie Premium-SMS | wie Premium-SMS |
| Telegram-Knopf-Beschriftungen (`_GLANCE_BUTTONS`, `_HEUTE_BUTTONS`, `_MORGEN_BUTTONS`) | deutsch wie heute (auch im Kurzstil) | englisch (`Hours`, `Thunder`, `Wind`, `Rain`, `Timeline today`) |
| Unbekannter Chat (kein Konto zugeordnet) | deutsch (kein Konto, keine Sprache) | — |

Die Kurzform-Antworten sind für beide Kontosprachen **identisch**, weil die Platzform sprachunabhängig ist (ADR-0104 Nr. 5, #2417 AC-4). Das Konto `en` ändert also nur die Langform-Pfade.

### 4. Signaturen

```python
# trip_command_processor.py  (alle neuen Parameter keyword-only, Default bewahrt Alt-Aufrufer)
def command_rows(kind: str = "route", *, lang: Lang = "de") -> list[tuple[str, str]]
def command_overview(en: bool = False) -> str                      # unverändert; Langform-en ruft command_overview(en=True)
def unknown_command_body(prefix: str, en: bool = False, *, lang: Lang = "de") -> str
def hilfe_langform(kind: str = "route", *, lang: Lang = "de") -> str   # NEU: Langform-Hilfe, de byte-gleich zu heute
def codes_text(en: bool, vergleich: bool = False) -> str            # unverändert; Langform-en ruft codes_text(True)
class TripCommandProcessor:
    _lang: Lang = "de"
    def _m(self, key: str, **params: object) -> str
    def _fmt_datum(self, d: date) -> str     # Kurzform und de: f"{d:%d.%m.%Y}"; Langform en: fmt_date(d, "en", "kurz")

# trip_selection.py
def resolve_active_target(..., englisch: bool = False, lang: Lang = "de", pausierte_ausblenden: bool = False)
def resolve_trip_only_target(..., channel: str = "", englisch: bool = False, lang: Lang = "de")
def resolve_command_target(..., channel: str, englisch: bool = False, lang: Lang = "de")
```

`_COMMAND_SPECS` behält alle Feldnamen. `beschreibung_de` und `beschreibung_de_vergleich` werden beim Modulimport mit `t("inbound.befehl.<wort>.beschreibung", "de")` bzw. `….beschreibung_vergleich` befüllt (byte-gleicher Wert, die bestehenden Drift-Tests lesen weiter `s.beschreibung_de`). Neue Felder mit Default `""`: `beschreibung_en`, `beschreibung_en_vergleich` (befüllt mit `t(…, "en")`). `wirkung_en`, `wirkung_en_vergleich`, `arg`, `arg_en` bleiben Literale (Platzform bzw. Protokoll). Die Argumentform `JJJJ-MM-TT` des Befehls `startdatum` hat den Katalogschlüssel `inbound.befehl.startdatum.arg`; `command_rows(kind, lang="en")` setzt dort `YYYY-MM-DD` ein, alle anderen Argumentformen sind sprachneutral.

`TripCommandProcessor._show_help` und `_show_help_for_kind` rufen für `not self._en` die neue Funktion `hilfe_langform(kind, lang=self._lang)`; für `lang="de"` entsteht exakt der heutige Text (Z. 2866-2889 bzw. 1446-1454). Die Wettergrößen-Zeile nutzt `metric.label(lang)` statt `metric.label_de` (Z. 2886); `col_label`/`sms_code` bleiben unverändert (Token-Wächter).

Weitere Stellen mit `lang`: `_on_demand_failure_body(outcome, label, target_date, en=False, objekt="Trip")` bekommt `lang` und liest die heutigen Zweige (Z. 938-965) aus `inbound.fehler.versand.*`; `_BRIEFING_HINWEIS` (Z. 555) wird zu `_briefing_hinweis(day_token, lang)`; die Knopf-Konstanten werden zu Funktionen `_glance_buttons(lang)`, `_heute_buttons(lang)`, `_morgen_buttons(lang)` mit unverändertem `callback_data`; `_metric_formatter` (Z. 678) bekommt `lang` für `· keine Daten` und die Niederschlagsart (`inbound.niederschlagsart.rain` … aus `PRECIP_TYPE_LABEL_DE`, de byte-gleich); `numbered_stage_label(stage, en=…)` bekommt `en=self._en or self._lang == "en"` (das Wort `Stage` gibt es dort schon). Himmelsrichtungs-Kürzel (`degrees_to_compass` ohne `language`, Default `en`) bleiben unverändert.

### 5. Katalog-Namensraum und Beispiel-Schlüssel

Bereich `inbound` (nur `src/i18n/messages/{de,en}/inbound.json` anfassen). Schlüsselgruppen: `inbound.antwort.*` (Bestätigungen und Fehler), `inbound.hilfe.*`, `inbound.befehl.<wort>.*`, `inbound.ziel.*` (Auswahl-Texte aus `trip_selection.py`), `inbound.fehler.versand.*`, `inbound.telegram.*` (Reader-Texte), `inbound.niederschlagsart.*`, `inbound.unbekannt.*`. Platzhalter snake_case, in `de` und `en` identisch (`{trip_name}`, `{count}`, `{liste}`, `{beispiel}`).

| Schlüssel | `de` (wörtlich wie heute) | `en` |
|---|---|---|
| `inbound.antwort.ruhetag_bereits.betreff` | `[{trip_name}] Ruhetag bereits eingetragen` | `[{trip_name}] Rest day already set` |
| `inbound.antwort.ruhetag_bereits.text` | `Ruhetag wurde heute bereits eingetragen.` | `A rest day was already added today.` |
| `inbound.antwort.keine_etappen.betreff` | `[{trip_name}] Keine Etappen` | `[{trip_name}] No stages` |
| `inbound.antwort.ruhetag_eingetragen.one` / `.other` | `Ruhetag eingetragen: +{count} Tag.` / `Ruhetag eingetragen: +{count} Tage.` | `Rest day added: +{count} day.` / `Rest day added: +{count} days.` |
| `inbound.antwort.trip_beendet.betreff` | `[{trip_name}] Trip beendet` | `[{trip_name}] Trip ended` |
| `inbound.antwort.trip_nicht_gefunden.text` | `Kein Trip mit Name '{trip_name}' gefunden.` | `No trip named '{trip_name}' found.` |
| `inbound.hilfe.kopf` | `Verfügbare Befehle:` | `Available commands:` |
| `inbound.hilfe.wetter_kopf` | `Wetter-Größen (Kürzel senden → Stundenverlauf):` | `Weather values (send a code → hourly values):` |
| `inbound.befehl.ruhetag.beschreibung` | `Etappen um N Tage verschieben (Standard: 1)` | `Shift stages by N days (default: 1)` |
| `inbound.befehl.stop.beschreibung` | `Briefings dauerhaft deaktivieren (auch ABBRUCH)` | `Turn briefings off for good (also CANCEL)` |
| `inbound.befehl.heute.beschreibung_vergleich` | `Vergleich für heute jetzt senden` | `Send the comparison for today now` |
| `inbound.ziel.kein_kandidat` | `Kein aktiver Trip oder Ortsvergleich gefunden.` | `No active trip or location comparison found.` |
| `inbound.antwort.keine_daten` | `· keine Daten` | `· no data` |

Hinweis: `Trip beendet` und der deutsche Abschiedssatz in Z. 3350-3353 bleiben wörtlich; deutsche Wortwahl wird in diesem Epic nicht verändert. Alle englischen Texte folgen Glossar und Konventionen Abschnitt 2 (Sentence case, einfache Sätze, kein Ausrufezeichen, Etappe = *stage*, Ortsvergleich = *location comparison*). Die im Kopf von `i18n_glossar.md` verbotenen Wörter gelten auch auf Englisch.

### 6. Beispiel-Umstellung (Datei:Zeile, vorher → nachher)

`src/services/trip_command_processor.py:2619-2626` (`_apply_ruhetag`, Idempotenz-Antwort):

```python
# vorher
confirmation_subject=self._t(
    f"[{trip.name}] Ruhetag bereits eingetragen", f"[{trip.name}] Rest day already set"),
confirmation_body=self._t("Ruhetag wurde heute bereits eingetragen.",
                          "A rest day was already added today."),

# nachher
confirmation_subject=self._m("antwort.ruhetag_bereits.betreff", trip_name=trip.name),
confirmation_body=self._m("antwort.ruhetag_bereits.text"),
```

Plural-Beispiel `:2683-2686` (`tage_wort` und die Zeile `Ruhetag eingetragen: +N Tage.`): beide Zeilen entfallen zugunsten von `lines = [self._m_n("antwort.ruhetag_eingetragen", shift_days), ""]` mit `_m_n` = `tn(f"inbound.{key}", count, lang)` (gleiche Sprachwahl wie `_m`).

### 7. Golden-Fixture, Reihenfolge und Wächter

1. **Zuerst** (vor jeder Codeänderung) die deutschen Ist-Ausgaben mit deterministischer Fixture (feste Zeit `2026-10-29T06:00+02:00`, Nutzer `golden-de`, ein Trip mit drei Etappen, ein Ortsvergleich mit drei Orten) nach `tests/golden/inbound/<fall>.de.txt` schreiben: `hilfe_trip`, `hilfe_vergleich`, `kuerzel`, `status`, `ruhetag_bestaetigung`, `ruhetag_bereits`, `trip_beendet`, `unbekannt_trip`, `trip_nicht_gefunden`, `rueckfrage_mehrdeutig`. Zusätzlich die heutige Kurzform-Ausgabe (`channel="premium_sms"`): `kurz_hilfe.en.txt`, `kurz_codes.en.txt`, `kurz_status.en.txt`, `kurz_unbekannt.en.txt`. Tests vergleichen byte-genau.
2. Dann umstellen: erst `trip_selection.py`, dann `command_rows`/`unknown_command_body`/`hilfe_langform`, dann die Methoden des Prozessors, zuletzt die drei Reader.
3. Englische Ausgaben derselben Fixture als `*.en.txt` einchecken (Review-Hilfe).
4. **Token-Wächter:** `tests/test_metric_tokens_eingefroren.py` bleibt grün; P10 berührt weder `metric_catalog.py` noch `col_label`/`compact_label`/`sms_code`.
5. **Renderer-Commit-Gate:** der Commit an `command_block.py` löst das Gate aus (`src/output/renderers/email/*.py`); vor dem Commit Modus-Matrix-Test und `briefing_mail_validator.py` bzw. `email_spec_validator.py` frisch grün.
6. **Allowlist:** in `tests/fixtures/i18n_python_allowlist.json` die Pfade `src/services/trip_command_processor.py`, `src/services/inbound_telegram_reader.py`, `src/services/inbound_sms_reader.py`, `src/services/inbound_email_reader.py` und `src/services/trip_selection.py` entfernen. Deutsche Log-Zeilen (Umlaut oder Signalwort, z. B. `inbound_sms_reader.py:204-211, 252, 290, 322, 368, 469, 490, 516`, `inbound_telegram_reader.py:447, 631, 636, 652`, `trip_command_processor.py:2679-2681`) tragen den Zeilenkommentar `# i18n-log` und werden nicht übersetzt (Logs bleiben deutsch).
7. **Mutations-Gegenproben (Adversary):** (a) `self._lang = "de"` fest verdrahten → AC-1 und AC-6 rot; (b) `_m` ohne `self._en`-Zweig → AC-3 rot; (c) `"cancel"` aus `_BARE_KEYWORD_MAP` entfernen → AC-5 rot; (d) ein deutsches Literal in `trip_selection.py` → AC-8 rot.

## Expected Behavior

- **Input:** eine eingehende Nachricht (`InboundMessage` mit `user_id`, `channel`, `body`, ggf. `englisch`) über E-Mail, Telegram oder Premium-SMS.
- **Output:** `CommandResult` mit Betreff und Text in der Sprache des Kontos (Langform) bzw. in der englischen Platzform (Kurzform-Kanal); Befehlswörter beider Sprachen lösen denselben Befehl aus.
- **Side effects:** keine neuen. Befehle ändern Daten wie bisher (Read-Modify-Write unter Sperre); die Sprache wird nur gelesen, nie geschrieben. Kein Fallback auf `"default"`.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit `language=en` und einem aktiven Trip / When er per Telegram (Standardstil) `STATUS` und danach `HILFE` sendet / Then ist die Statusantwort englisch (Zeilen `Stage 1: …`, Datum im englischen Format `Thu 30 Oct`), die Hilfe zeigt die englischen Wörter (`RESTDAY`, `TODAY`, `HELP`) mit englischen Beschreibungen und Wettergrößen-Namen (`Humidity`, `Wind gusts`), und alle Kürzel (`col_label`, `sms_code`) stehen unverändert da.
  - Test: tests/tdd/test_befehle_nutzersprache_antworten.py — der echte Webhook-Eintritt (`InboundTelegramReader._process_update`) liefert dem `en`-Nutzer englische Langform-Antworten; geprüft wird der tatsächlich versendete Text, die Kürzel-Spalte ist byte-gleich zum Token-Wächter.

- **AC-2:** Given ein Nutzer mit `language=de` (oder ohne Feld) / When er `STATUS`, `HILFE`, `KUERZEL`, `RUHETAG`, `STOP` und einen unbekannten Befehl per E-Mail und per Telegram (Standardstil) sendet / Then sind alle Antworten byte-gleich zur deutschen Golden-Ausgabe der Ist-Fassung.
  - Test: tests/tdd/test_befehle_nutzersprache_antworten.py — Golden-Vergleich gegen `tests/golden/inbound/*.de.txt` (vor der Umstellung aus dem unveränderten Code erzeugt), Fixture mit fester Zeit und Nutzer `golden-de`.

- **AC-3:** Given ein Nutzer mit `language=de` / When er per Premium-SMS `HELP`, `CODES`, `TOMORROW`, `STATUS` oder einen unbekannten Befehl sendet oder eine mehrdeutige Auswahl auslöst / Then ist die Antwort byte-gleich zur heutigen Kurzform (englische Befehlswörter, GSM-7, höchstens drei Segmente, Kürzel mit englischer Bedeutung) und enthält kein deutsches Signalwort.
  - Test: tests/tdd/test_befehle_kurzform_sprachunabhaengig.py — Vergleich mit `tests/golden/inbound/kurz_*.en.txt` über den echten Premium-SMS-Eingang (`_verarbeite_befehl`), GSM-7- und Segmentprüfung.

- **AC-4:** Given ein Nutzer mit `language=en` / When er dieselben Befehle per Premium-SMS und per Telegram mit Kurzform-Stil sendet / Then ist die Antwort identisch zu der des `de`-Nutzers (Platzform ist sprachunabhängig, #2417 AC-4), und die Kürzel-Bedeutungen kommen aus `kuerzel_bedeutung_en`.
  - Test: tests/tdd/test_befehle_kurzform_sprachunabhaengig.py — gleiche Eingaben für `de`- und `en`-Nutzer, die Antwortinhalte sind gleich; Positivkontrolle: dieselbe Eingabe per E-Mail unterscheidet sich zwischen den Nutzern.

- **AC-5:** Given je ein Nutzer mit `de` und mit `en` / When der `de`-Nutzer `RESTDAY 2`, `CANCEL` und `CODES` und der `en`-Nutzer `RUHETAG 2`, `ABBRUCH` und `KUERZEL` sendet, jeweils per E-Mail, Telegram und Premium-SMS / Then führt jedes Wort denselben Befehl aus wie sein Gegenstück der Befehlstabelle, und die Antwort kommt in der Kontosprache.
  - Test: tests/tdd/test_befehle_beide_sprachen_erkannt.py — parametrisiert über alle 15 Zeilen der Tabelle × beide Wörter × drei Eingangskanäle × beide Kontosprachen; geprüft wird die Wirkung (verschobene Etappen, deaktivierter Versand), nicht nur die Erkennung. Gegenprobe: ein Fremdwort wie `Hilfen` bleibt unbekannt.

- **AC-6:** Given zwei Nutzer, A mit `de` und B mit `en`, jeder mit eigenem Trip / When beide im selben Prozess nacheinander und verschachtelt denselben Befehl `RUHETAG` per E-Mail und per Telegram senden / Then antwortet jedem Nutzer seine Sprache, jede Änderung trifft nur den eigenen Trip, und ein dritter Nutzer ohne Konto-Feld bekommt Deutsch.
  - Test: tests/tdd/test_befehle_zwei_nutzer_sprache.py — zwei `user_id`s in einem Prozess über den echten Eingang; Gegenprobe mit dem Mutanten „globale Sprache" (Test muss rot werden); Trip des jeweils anderen Nutzers bleibt unverändert.

- **AC-7:** Given ein Nutzer mit `language=en` / When er einen unbekannten Befehl, einen Befehl an einen nicht existierenden Trip oder einen Befehl sendet, der einen internen Fehler auslöst, und wenn er die Briefing-Mail mit Befehlsblock erhält / Then sind Betreff und Text dieser Fehlerantworten englisch, `command_rows("route", lang="en")` und `command_rows("vergleich", lang="en")` liefern englische Wörter und Beschreibungen, und für `lang="de"` sind beide Listen byte-gleich zu heute.
  - Test: tests/tdd/test_befehle_nutzersprache_antworten.py — Fehlerpfade des echten Eingangs je Kanal; `command_rows`-Vergleich gegen Golden für `de`, Inhaltsprüfung für `en` (englische Wörter, kein deutsches Signalwort, `JJJJ-MM-TT` ersetzt durch `YYYY-MM-DD`).

- **AC-8:** Given der Katalogbereich `inbound` und die fünf migrierten Quelldateien / When der Paritäts- und der Ratschentest laufen / Then haben `inbound.json` in `de` und `en` identische Schlüssel- und Platzhaltermengen, die Quelldateien enthalten keinen hartkodierten Nutzertext außerhalb von `t(...)`, und ihre Allowlist-Einträge sind entfernt; ein neu eingefügtes deutsches Literal färbt den Test rot.
  - Test: tests/test_i18n_inbound_katalog_paritaet.py — `# doc-compliance-test` (Paritäts- und Ratschentest, kein Verhaltensnachweis); Verhaltensanteil: Mutation mit einem deutschen Literal in `trip_selection.py` muss rot werden.

## Known Limitations

- **Annahme 1 (Kurzform-Antworten, Konflikt Issue/ADR):** ADR-0104 Nr. 5 sagt, Antworttexte folgten der Nutzersprache; #2417 AC-4 und das Issue (AC-2 „byte-gleich zu heute") verlangen für Premium-SMS und Telegram-Kurzstil durchgehend englische, GSM-7-sichere Antworten für **beide** Kontosprachen. Konservativ gilt: Kurzform bleibt für `de` und `en` identisch englisch; nur Langform-Pfade folgen der Kontosprache. Die Issue-Skizze „deutsche Kürzel-Bedeutung" für einen `de`-Nutzer auf Premium-SMS wird deshalb nicht umgesetzt (heute antwortet `codes_text(True)` dort englisch).
- **Annahme 2 (Alleinwörter):** `ABBRUCH` und `CANCEL` werden als Alleinwörter neu erkannt (Glossar `i18n_glossar.md`, Abschnitt Inbound-Befehle; die Hilfe bewirbt „auch ABBRUCH" schon heute). Eigene Zeilen in `_COMMAND_SPECS` entstehen nicht.
- **Annahme 3 (Datumsformat):** Langform-Antworten für `en` schreiben Daten als `Thu 30 Oct` (`fmt_date(d, "en", "kurz")`, ADR-0104 Nr. 6); `de` und alle Kurzform-Pfade behalten `%d.%m.%Y`.
- **Annahme 4 (unbekannter Chat):** Telegram-Nachrichten eines Chats ohne zugeordnetes Konto (`user_id is None`, Registrierungshinweis, `/start`-Antworten) bleiben deutsch; es gibt keine Kontosprache. Die Telegram-Spracheinstellung des Absenders wird nicht ausgewertet.
- **Annahme 5 (Telegram-Menü):** `BOT_COMMANDS` (Befehlsmenü, statische deutsche Beschreibungen) gehört zu P7 (#2669); `prod_selftest.py` liest die Liste per `ast.literal_eval`, ein `t()`-Aufruf ist dort nicht möglich. P10 ändert diese Datei nicht.
- Gewitterstufen-Wörter und Niederschlagsarten in der Langform folgen `lang` nur über die in diesem Paket ergänzten Katalogschlüssel; die Domänentabellen `THUNDER_LABEL_DE` und `PRECIP_TYPE_LABEL_DE` bleiben unverändert.
- Die Antwortmail auf einen E-Mail-Befehl trägt keinen Validator-Marker; der Staging-Nachweis läuft über `.claude/tools/staging_befehl_pruefen.py` (nur `de`-Nutzer) und Kern-Tests mit echtem Eingang für `en`. Der zweisprachige Live-Lauf folgt in A2 (#2681).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042, ADR-0095)
- **Rationale:** Die Sprache gehört dem Nutzer (ADR-0104 Nr. 1), die Kurzform ist Platzform und keine Sprache (ADR-0104 Nr. 5, ADR-0042), und jeder Eingangskanal beantwortet jede Frage (ADR-0095); deshalb werden `self._lang` und `self._en` getrennt geführt.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
