---
entity_id: feat_2417_kurzform_englisch
type: module
created: 2026-09-27
updated: 2026-09-27
status: draft
version: "1.0"
tags: [befehle, kurzform, premium-sms, telegram, metrik-katalog, englisch]
---

# Kurzform ist englisch — also auch ihre Befehle (#2417)

## Approval

- [ ] Approved

## Purpose

Der PO hat am 27.09.2026 zu Issue #2417 entschieden: Die Kurzform (Premium-SMS/Garmin, Telegram-Kurzform) ist englisch — also müssen dort auch die **Befehle** englisch sein. Auslöser war der Prod-Test vom 27.09. (AC-27 der Vorgänger-Spec): Auf `hilfe` kam „Commands: HEUTE today, MORGEN tomorrow, … Codes: D,Night,L,DayMax,TF,…" zurück — eine reine Wortübersetzung statt einer Aussage über die Wirkung, Kürzel ohne Bedeutung, und deutsche Befehlswörter mitten in einer englischen SMS. Der Befund war „Kurzhilfe inhaltlich wertlos" (Issue-Kommentar 27.09.).

**Die Festlegung „Kurzform ⇒ englische Befehle" ist bisher nur im Issue-Kommentar und in der Analyse-Kontextdatei (`docs/context/feature-2417-kurzform-englisch.md`) dokumentiert und wird mit dieser Spec-Freigabe erstmals verbindlich bestätigt.**

Diese Spec ersetzt außerdem drei Zusicherungen der Vorgänger-Spec `docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md`, die inhaltlich falsch waren, weil sie eine reine Wortübersetzung statt einer Wirkungsaussage verlangten: **AC-10, AC-11 und AC-23 gelten als abgelöst.**

## Source

- **File:** `src/services/trip_command_processor.py` (`_COMMAND_SPECS`, `_BARE_KEYWORD_MAP`, `_KURZHILFE_ENGLISCH`, `premium_sms_kurzhilfe`)
- **File:** `src/app/metric_catalog.py` (`MetricDefinition.sms_code`, `SMS_SYMBOL_BY_METRIC`, `SMS_MULTI_SYMBOLS_BY_METRIC`)
- **File:** `src/output/tokens/hazard_symbols.py` (`HAZARD_SMS_SYMBOLS`)
- **File:** `src/services/inbound_sms_reader.py`, `src/services/inbound_telegram_reader.py`, `src/output/channels/telegram.py` (`BOT_COMMANDS`)
- **Identifier:** siehe Affected Files unten.

> Schicht-Hinweis: alle betroffenen Dateien liegen im Python-Core (`src/services/`, `src/app/`, `src/output/`) — keine Go-/Frontend-Änderung nötig.

## Estimated Scope

- **LoC:** produktiv +250 bis +400 / -60; Tests +250 bis +350 (zählen nicht gegen das Limit). `loc_limit_override 500` ist vorab zu setzen — die Refactoring-Zeile (Tupel → NamedTuple) betrifft mehrere Leser gleichzeitig.
- **Files:** ~14 bis 17 (produktiv + Tests)
- **Effort:** medium bis high — zentraler Befehlssatz aller vier Kanäle, Kürzel-Bereinigung wirkt bis in den SMS-Renderer

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_COMMAND_SPECS` (`trip_command_processor.py:222`) | Upstream | einzige Quelle des Steuerbefehlssatzes (Issue #2134) — wird zur benannten Struktur |
| `get_all_metrics()` / `MetricDefinition` (`metric_catalog.py`) | Upstream | Quelle der Wetter-Kürzel für Eingabe und für CODES |
| `SMS_SYMBOL_BY_METRIC` / `SMS_MULTI_SYMBOLS_BY_METRIC` (`metric_catalog.py:792,840`) | Upstream | die tatsächlich GESENDETEN Kürzel — CODES leitet hieraus ab, nicht aus `sms_code` allein |
| `HAZARD_SMS_SYMBOLS` (`hazard_symbols.py:15`) | Upstream | Warn-Kürzel für den CODES-Abschnitt „Alerts" |
| `telegram_style` (Trip `report_config`, Vergleich `display_config`) | Upstream | steuert, ob eine Telegram-Antwort deutsch oder englisch ausfällt |
| `BOT_COMMANDS` (`telegram.py:122`) | Downstream | Telegram-Menü, muss Literal bleiben (`prod_selftest.py::_load_bot_commands` liest per `ast.literal_eval`) |
| `docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md` (AC-10/AC-11/AC-23) | Downstream | wird durch diese Spec ausdrücklich abgelöst |
| `src/output/renderers/sms_trip.py` | Downstream | liest weiterhin `SMS_SYMBOL_BY_METRIC` — ändert sich ein `sms_code`, wirkt das auf die tatsächlich versendete SMS (Renderer-Commit-Gate, Mail-Validator beachten) |

## Kernproblem: Kürzel-Widersprüche im Katalog (gemessen 27.09.2026)

Der Metrik-Katalog trägt je Größe mehrere Kürzel-Felder (`sms_code`, `col_label`, `sms_multi_symbols`). Die **Eingabe** (Kürzel-Abfrage per Nachricht, bisherige Kurzhilfe) nutzt `sms_code or col_label`. Die **Ausgabe** (tatsächlich gesendete SMS) nutzt die Register `SMS_SYMBOL_BY_METRIC`/`SMS_MULTI_SYMBOLS_BY_METRIC`. Bei 24 von 29 Größen stimmen beide überein. Die übrigen fünf zeigt die Tabelle: drei echte Widersprüche (`temperature`, `temperature_day_high`, `temperature_night`), dazu `fresh_snow` (nur ein Suffix, per Normalisierung lösbar) und `wind_chill` (nur Stundenverlauf, kein Widerspruch):

| Größe | Eingabe-Kürzel (heute) | Kürzel in der SMS gelesen | Widerspruch |
|---|---|---|---|
| `temperature` (Stundenverlauf) | `D` (`metric_catalog.py:134`) | — (nur Stundenverlauf, kein Tageswert) | `D` doppelt belegt: als Ausgabe-Kürzel ist `D` der Tageshöchstwert |
| `temperature_day_high` (Tageshöchstwert) | `DayMax` (kein `sms_code`, `metric_catalog.py:218-221`) | `D` (`sms_multi_symbols`) | gelesenes Kürzel `D` ist heute nicht sendbar |
| `temperature_night` (Nachtwert) | `Night` (kein `sms_code`, `metric_catalog.py:164-173`) | `N` (`sms_multi_symbols`) | gelesenes Kürzel `N` ist heute nicht sendbar |
| `fresh_snow` | `NS` (`sms_code`) | `NS24+` (`SMS_SYMBOL_GRAMMAR`, `metric_catalog.py:786`) | Suffix — per Normalisierung lösbar, kein echter Widerspruch |
| `wind_chill` (gefühlt, Stundenverlauf) | `TF` (`sms_code`) | — (nur Stundenverlauf) | kein Widerspruch, `TF` ist eindeutig |

Dazu die **Gefahren-Kürzel** der Warn-SMS (`hazard_symbols.py:15-26`): `FL` (hazard `flood`) kollidiert mit der Metrik `felt_day_low` (`sms_code="FL"`), `CL` (hazard `access_ban`) mit der Metrik `cloud_low` (`sms_code="CL"`), `W` (hazard `wind_gust`) mit der Metrik `wind` (`sms_code="W"`), `TH` (hazard `thunderstorm`) mit der Metrik `thunder` (`SMS_SYMBOL_GRAMMAR["thunder"]="TH:"`). Dazu kommen der Warn-Kürzel `HR` (Starkregen), der mit dem Météo-France-Baustein `HR:` kollidiert, und der Baustein `TH:` dieser Gruppe (`builder.py:29-30`), der mit dem Wetter-Kürzel `TH:` kollidiert. Alle diese Doppelungen werden mit AC-27 aufgelöst, weil der PO „keine Dopplung von Kürzeln" verlangt.

**Ziel:** Ein Kürzel = eine Bedeutung, überall, und was man in der SMS liest, kann man auch zurücksenden.

## Gemessenes Längenbudget (GSM-7, `sms_segments()`)

- HELP im verbindlichen Wortlaut unten: 402 Zeichen = **3 Segmente**
- CODES im verbindlichen Wortlaut unten (Wetter + weitere Bausteine + Format + Alerts): 758 Zeichen = **5 Segmente** (Grenze 765). Eine vollständige Erklärung aller lesbaren Zeichen passt nicht in 4 Segmente; Vollständigkeit geht vor, weil wer nur Premium-SMS empfängt, keine andere Quelle für die Bedeutung hat.

### Verbindlicher Wortlaut (Trip, Kurzform-Kanal)

Dieser Wortlaut ist Teil der Freigabe. Die Tests vergleichen die gesendete Antwort **zeichengenau** mit diesem Text (AC-8, AC-9). Gemessen am 27.09.2026 mit `sms_segments()`.

HELP:
```
Commands (German works too):
TODAY - today's stage weather
TOMORROW - tomorrow's stage weather
NOW - rain/storm next 2h
STORMS - storm risk today
ROUTE km - rain areas ahead
RESTDAY n - shift stages n days
STATUS - today + next stages
PAUSE 2D - no briefings 2 days/12H
SKIP - skip next briefing
STOP - end briefings
RESUME - restart briefings
CODES - code meanings
Send a code (e.g. R) for its values.
```

CODES:
```
Weather: T temp, D day max, N night, L day min, TF feels like, FD/FL/FN = D/L/N feels like, R rain mm, PR rain %, TH thunder, TH+ next stage, W wind km/h, G gusts, WD wind dir, HU humidity, DP dew point, CP storm energy, PT precip type, SL snow line m, NS24+ new snow 24h, CT/CL/CM/CH clouds total/low/mid/high, VS visibility, SU sun h, UV index, HP pressure, FZ 0C level m.
More: SD snow depth, AV avalanche level, C forecast confidence, Z:/M: fire zones/massifs.
Format: E4 stage 4, 23@5 over limit from 5h, (24@7) peak, D13/27 min/max, +HL hail, - none, ? no data.
Alerts after !: TS storm, FO flood, RA heavy rain, WG wind, SN snow, IC ice, HT heat, CD cold, FR fire, AB closure. L/M/H low/mid/high. VR:VT: Meteo-France rain/storm risk. X? no alert data.
```

**Wo die Bedeutungen stehen (PO-Vorgabe 27.09.2026: Der Metrik-Katalog ist der einzige Ort, an dem Wettermetriken definiert sein dürfen):**

| Kürzel-Art | Einzige Definitionsstelle der Bedeutung (en + de) |
|---|---|
| Jedes Kürzel einer Wettermetrik (alle Einträge in `_METRICS`, inklusive `snow_depth`=`SD`, `confidence`=`C` und beider Gewitter-Kürzel `TH`/`TH+`) | **`src/app/metric_catalog.py`**, im jeweiligen `MetricDefinition`-Eintrag, als neues Feld je Kürzel |
| Warn-Kürzel (`TH`, `FL`, `HR`, … hinter `!`) | `src/output/tokens/hazard_symbols.py`, direkt bei `HAZARD_SMS_SYMBOLS`, wo das Kürzel selbst definiert ist. Das sind amtliche Warnarten, keine Wettermetriken. |
| Übrige Bausteine ohne Katalog-Eintrag (`AV`, `Z:`, `M:`, `VR:`, `VT:`, `X?`) und Formatzeichen (`E<N>`, `@`, `(…)`, `/`, `+HL`, `-`, `?`) | `src/output/tokens/builder.py`, direkt bei der Konstante, die das Zeichen erzeugt |

CODES/KUERZEL enthält **keinen einzigen** eigenen Bedeutungstext. Die Antwort wird zur Laufzeit aus diesen drei Stellen zusammengesetzt. Die Blöcke oben (englisch) und in AC-10 (deutsch) sind das **erwartete Ergebnis** dieser Ableitung zum Freigabezeitpunkt, keine zweite Definition. Ändert jemand eine Bedeutung im Katalog, ändert sich die CODES-Antwort, und der Wortlaut-Test wird rot. Das ist gewollt, weil der PO dann den neuen Wortlaut sieht.

CODES erklärt damit **jedes** Zeichen, das in einer Kurzform-SMS erscheinen kann: die Wetter-Register, die übrigen Bausteine aus `src/output/tokens/builder.py` (`SD`, `AV`, `C`, `Z:`, `M:`, `VR:`, `VT:`, `X?`), die Formatzeichen und die Warn-Kürzel hinter `!`. Nicht erklärt wird nur `DBG` (erscheint ausschließlich im Test-/Debug-Modus, nie beim Nutzer).

Beim **Ortsvergleich** enthält HELP nur die Zeilen der dort erlaubten Befehle (laut `kinds`), in derselben Formulierung. Die Formatzeile entspricht der Kurzform-Grammatik in `docs/reference/sms_format.md` (`R0.2@6(1.4@16)` = über der Schwelle ab 6 Uhr, Spitze 1,4 um 16 Uhr; `D13/27` = Bereich Tiefst/Höchst; `+HL` = Hagel am Gewitter-Kürzel; `?` = Datenlücke).

**Verbindlich: HELP höchstens 3 Segmente, CODES höchstens 5 Segmente** (153 GSM-7-Zeichen je Segment, gemessen mit dem bestehenden Test-Helfer `sms_segments()` aus `tests/tdd/_befehl_e2e_fixtures.py`).

## Expected Behavior

- **Input:** ein Befehlswort (deutsch ODER englisch) oder ein Wetter-Kürzel, über E-Mail, Telegram oder Premium-SMS.
- **Output:** dieselbe Wirkung, unabhängig von der Eingabesprache. Die Antwortsprache richtet sich nach dem Kanal/Ziel (siehe unten), nicht nach der Eingabesprache des Nutzers.
- **Side effects:** keine neuen — mutierende Befehle (PAUSE/SKIP/STOP/RESUME/RESTDAY) schreiben weiterhin ausschließlich die Datei des tatsächlich getroffenen Ziels (Read-Modify-Write, unverändert).

## Acceptance Criteria

### A. Einzelquelle und Sprach-Erkennung

- **AC-1:** Given `_COMMAND_SPECS` ist heute ein reines Tupel `(wort, arg, beschreibung, kinds)` / When der Befehlssatz erweitert wird / Then trägt jeder Eintrag zusätzlich ein englisches Wort (`wort_en`) und eine englische Wirkungsbeschreibung (`wirkung_en`), alle bisherigen und neuen Leser greifen über Feldnamen zu, und `_KURZHILFE_ENGLISCH` existiert nicht mehr als separate Wortübersetzungs-Liste.
  - Test: `test_kommandoliste_einzelquelle.py` (bestehend, angepasst auf Feldnamen-Zugriff) plus neuer Test, der prüft, dass `_KURZHILFE_ENGLISCH` als Modul-Attribut nicht mehr existiert.

- **AC-2:** Given ein Nutzer sendet ein englisches Befehlswort (z. B. `TODAY`, `TOMORROW`, `NOW`, `STORMS`, `ROUTE`, `RESTDAY`, `STATUS`, `PAUSE`, `SKIP`, `STOP`, `RESUME`, `HELP`, `CODES`) / When die Nachricht über E-Mail, Telegram oder Premium-SMS ankommt / Then wird der Befehl erkannt und wirkt identisch zum bisherigen deutschen Wort — auf allen drei Kanälen, nicht nur auf Kurzform-Kanälen.
  - Test: `test_kurzform_befehle_englisch.py`, parametrisiert über alle englischen Wörter × drei Kanäle, Zusicherung auf den tatsächlich versendeten Antwortinhalt (gleiches Inhaltsmerkmal wie beim deutschen Wort).

- **AC-3:** Given `CODES` (deutsches Pendant `KUERZEL`, auch `KÜRZEL` mit Umlaut wird akzeptiert) ist ein neuer Befehl / When er über einen beliebigen Kanal ohne vorangestellten Trip-/Vergleichsnamen gesendet wird / Then wird er wie `HILFE` sofort beantwortet, ohne dass vorher ein Trip oder Ortsvergleich geladen wird (ziellos, wie `hilfe`/`columns` in `ZIELLOS_SCHLUESSEL`).
  - Test: `test_kurzform_befehle_englisch.py::test_codes_ist_ziellos`, prüft für alle drei Kanäle, dass die Antwort ohne Rückfrage kommt, auch wenn Trip **und** mehrere aktive Ortsvergleiche existieren.

### B. Antwortsprache je Kanal

- **AC-4:** Given eine Antwort geht über Premium-SMS hinaus / When sie versendet wird / Then ist ihr Text durchgehend englisch — unabhängig davon, ob der Nutzer deutsch oder englisch angefragt hat.
  - Test: `test_kurzform_befehle_englisch.py::test_premium_sms_antwort_ist_immer_englisch`, prüft je erreichbaren Antworttyp (siehe Abschnitt D) auf Abwesenheit deutscher Signalwörter und Anwesenheit des erwarteten englischen Inhalts.

- **AC-5:** Given das aufgelöste Ziel (Trip oder Ortsvergleich) hat `telegram_style == "kurzform"` (Trip: `report_config.telegram_style`, Vergleich: `display_config.telegram_style`) / When eine Antwort per Telegram an dieses Ziel geht / Then ist sie englisch; hat das Ziel keinen oder einen anderen `telegram_style`, bleibt die Antwort deutsch.
  - **Ziellose Befehle** (`HELP`/`HILFE`, `CODES`/`KUERZEL`) haben kein aufgelöstes Ziel. Für sie gilt auf Telegram deshalb: Die Sprache folgt dem **gesendeten Wort**. `HELP`/`CODES` antworten englisch, `HILFE`/`KUERZEL` deutsch, unabhängig davon, wie viele Trips oder Ortsvergleiche mit welchem Stil existieren. Auf Premium-SMS bleibt es immer englisch (AC-4), auf E-Mail immer deutsch (AC-6).
  - Test: `test_kurzform_befehle_englisch.py::test_telegram_sprache_folgt_telegram_style`, je einmal mit `telegram_style="kurzform"` und ohne, gleicher Befehl, unterschiedliche erwartete Sprache; dazu `test_ziellos_sprache_folgt_wort`: ein Nutzer mit einem Trip im Stil `kurzform` und einem Ortsvergleich ohne diesen Stil sendet `help`, `hilfe`, `codes` und `kuerzel` per Telegram und erhält englisch, deutsch, englisch und deutsch.

- **AC-6:** Given eine Antwort geht per E-Mail (inklusive Fußzeile) / When sie versendet wird / Then bleibt sie unverändert deutsch — unabhängig von der Eingabesprache und unabhängig von `telegram_style`.
  - Test: `test_kurzform_befehle_englisch.py::test_email_bleibt_immer_deutsch`.

- **AC-7:** Given `_KURZFORM_KANAELE` umfasst heute `("premium_sms", "sms")` / When die Sprachsteuerung für Telegram-Kurzform eingebaut wird / Then bleibt `_KURZFORM_KANAELE` unverändert — Telegram wird NICHT ergänzt, weil das den Drilldown-Pfad (`_ist_kurzform_kanal`, `trip_command_processor.py:656,1423,1476`) mit einem unbeabsichtigten Seiteneffekt verändern würde. Die Telegram-Sprachsteuerung läuft über eine eigene, vom Drilldown-Format getrennte Prüfung.
  - Test: bestehende Drilldown-Tests bleiben grün ohne Anpassung; neuer Test bestätigt `_KURZFORM_KANAELE == ("premium_sms", "sms")`.

### C. HELP-Kurzform

- **AC-8:** Given die Antwort auf `HELP`/`HILFE` ist nach AC-4/AC-5 englisch (Premium-SMS immer, Telegram bei gesendetem englischem Wort `HELP`) / When die Antwort aufgebaut wird / Then nennt sie ausschließlich die englischen Befehlswörter, je Befehl seine **Wirkung** (was zurückkommt) statt einer Wortübersetzung, einen Verweis auf `CODES` für die Wetter-Kürzel und einen Hinweis, dass deutsche Wörter ebenfalls funktionieren — und die Nachricht braucht höchstens 3 GSM-7-Segmente à 153 Zeichen, gemessen mit `sms_segments()`.
  - Der Text entspricht **zeichengenau** dem „Verbindlichen Wortlaut" oben (Trip) bzw. dessen Teilmenge (Ortsvergleich). Ein Stichwort-Test genügt nicht, weil genau so die wertlose alte Kurzhilfe durchgerutscht ist.
  - Test: `test_kurzform_befehle_englisch.py::test_help_kurzform_ist_der_freigegebene_wortlaut` vergleicht die über Premium-SMS tatsächlich versendete Antwort mit dem Wortlaut aus dieser Spec. Zusätzlich prüft er, dass jede Befehlszeile aus `_COMMAND_SPECS` (`wort_en` + `wirkung_en`) abgeleitet ist, damit ein neuer Befehl nicht ohne Wirkungstext erscheint. Außerdem prüft er Segmentzahl ≤ 3 und GSM-7-Sauberkeit (kein `–`/`→`/`°`, keine Emojis).

### D. CODES

- **AC-9:** Given die Antwort auf `CODES`/`KUERZEL` ist nach AC-4/AC-5 englisch (Premium-SMS immer, Telegram bei gesendetem englischem Wort `CODES`) / When die Antwort aufgebaut wird / Then enthält sie jedes Kürzel aus `SMS_SYMBOL_BY_METRIC` und `SMS_MULTI_SYMBOLS_BY_METRIC` (die tatsächlich gesendeten Ausgabe-Kürzel) mit einer kurzen englischen Bedeutung, dazu die übrigen Bausteine aus `builder.py` außer `DBG` (`SD`, `AV`, `C`, `Z:`, `M:`, `VR:`, `VT:`, `X?`), die Formatzeichen der Kurzform-Grammatik (Etappen-Präfix `E<N>`, Stunden-Marker `@`, Spitze `(…)`, Bereich `D13/27`, Hagel-Suffix `+HL`, Null-Form `-`, Lücken-Marker `?`) und einen eigenen Abschnitt „Alerts" mit den zehn Warn-Kürzeln aus `HAZARD_SMS_SYMBOLS` samt Stufen `L/M/H` — und braucht höchstens 5 Segmente.
  - Der Text entspricht **zeichengenau** dem „Verbindlichen Wortlaut" oben (`test_codes_ist_der_freigegebene_wortlaut`).
  - Test: `test_kuerzel_eindeutig.py::test_codes_vollstaendig_gegen_ausgabe_register` — leitet die Soll-Menge aus `SMS_SYMBOL_BY_METRIC`/`SMS_MULTI_SYMBOLS_BY_METRIC`/`HAZARD_SMS_SYMBOLS` ab (nicht aus einer zusätzlichen, handgepflegten Bedeutungs-Liste) und schlägt fehl, sobald ein Register-Kürzel in der CODES-Antwort fehlt oder ein Kürzel ohne Bedeutungstext auftaucht. Die Soll-Menge umfasst zusätzlich jedes Token-Symbol, das `builder.py` erzeugen kann (außer `DBG`). Segmentzahl ≤ 5 mit `sms_segments()`.

- **AC-10:** Given die Antwort auf `CODES`/`KUERZEL` ist nach AC-5/AC-6 deutsch (E-Mail immer, Telegram bei gesendetem deutschem Wort `KUERZEL`/`KÜRZEL`) / When die Antwort aufgebaut wird / Then entspricht sie **zeichengenau** dem deutschen Wortlaut unten, mit derselben Kürzelmenge wie AC-9. Jeder Kanal beantwortet damit dieselbe Frage.
  - Deutscher Wortlaut (verbindlich, ohne Segmentgrenze, weil E-Mail und Telegram nicht nach SMS-Segmenten zählen):
    ```
    Kürzel
    Wetter: T Temperatur, D Tageshöchstwert, N Nacht, L Tagestiefstwert, TF gefühlt, FD/FL/FN = D/L/N gefühlt, R Regen mm, PR Regenwahrscheinlichkeit %, TH Gewitter, TH+ Gewitter Folge-Etappe, W Wind km/h, G Böen, WD Windrichtung, HU Luftfeuchte, DP Taupunkt, CP Gewitterenergie, PT Niederschlagsart, SL Schneefallgrenze m, NS24+ Neuschnee 24h, CT/CL/CM/CH Bewölkung gesamt/tief/mittel/hoch, VS Sicht, SU Sonnenstunden, UV UV-Index, HP Luftdruck, FZ Nullgradgrenze m.
    Weitere: SD Schneehöhe, AV Lawinenstufe, C Vorhersage-Verlässlichkeit, Z:/M: Brandzonen/Massive.
    Format: E4 Etappe 4, 23@5 über der Schwelle ab 5 Uhr, (24@7) Spitze, D13/27 Tiefst/Höchst, +HL Hagel, - nichts, ? keine Daten.
    Warnungen nach !: TS Gewitter, FO Hochwasser, RA Starkregen, WG Wind, SN Schnee, IC Glätte, HT Hitze, CD Kälte, FR Waldbrand, AB Sperrung. L/M/H niedrig/mittel/hoch. VR:VT: Météo-France-Risiko Regen/Gewitter. X? keine Warndaten.
    ```
  - Test: `test_kuerzel_eindeutig.py::test_codes_deutsch_auf_langform_kanaelen`.

- **AC-23:** Given die Bedeutung eines Wetter-Kürzels (z. B. `R` = „rain mm" / „Regen mm") / When sie irgendwo gebraucht wird (CODES englisch, KUERZEL deutsch) / Then steht sie genau einmal im Code, nämlich im `MetricDefinition`-Eintrag der Metrik in `src/app/metric_catalog.py`. Warn-Kürzel stehen genau einmal in `hazard_symbols.py`, Bausteine ohne Katalog-Eintrag und Formatzeichen genau einmal in `builder.py`. Der CODES-Aufbau in `trip_command_processor.py` enthält keinen Bedeutungstext.
  - Test: `test_kuerzel_eindeutig.py::test_bedeutung_kommt_nur_aus_dem_katalog`. Die Bedeutung einer Katalog-Metrik wird im Test zur Laufzeit geändert, und die CODES-Antwort muss den geänderten Text zeigen. Zusätzlich muss jede `_METRICS`-Metrik mit Ausgabe-Kürzel eine nicht leere en- und de-Bedeutung tragen, sonst wird der Test rot. So wird eine neue Metrik ohne Bedeutung sofort sichtbar.

- **AC-24:** Given `docs/reference/metric_output_matrix.md` ist die zentrale Übersicht aller Ausgabeorte je Metrik / When CODES/KUERZEL als neuer Ausgabeort entsteht und `temperature` das Kürzel `T` erhält / Then führt das Dokument CODES/KUERZEL in Abschnitt 2 mit Datei:Zeile und Wächter, nennt das neue Bedeutungsfeld im Absatz „Grundlage" und führt `temperature` nicht mehr als Telegram-Ausnahme.
  - Test: `# doc-compliance-test` in `test_kuerzel_eindeutig.py` (erlaubte Ausnahme für Dokumentprüfungen).

### E. Kürzel-Eindeutigkeit (Designentscheidung, keine Verschiebung)

- **AC-11:** Given die CODES-Antwort gliedert sich in die Abschnitte „Weather", „More", „Format" und „Alerts after !" / When die Kürzel aller Abschnitte zusammen geprüft werden / Then kommt jedes Kürzel über **alle** Abschnitte hinweg genau einmal vor und hat genau eine Bedeutung. Es gibt keine Ausnahme je Abschnitt, weil die bisherigen Doppelbelegungen mit AC-27 aufgelöst werden. Stufen-Buchstaben (`L/M/H` hinter `:`) und Zahlen sind Werte und keine Kürzel.
  - Test: `test_kuerzel_eindeutig.py::test_ein_kuerzel_eine_bedeutung_ueberall` — baut aus allen Registern eine gemeinsame Kürzel→Bedeutung-Abbildung und schlägt fehl, sobald ein Kürzel zweimal vorkommt.

### F. Temperatur-Bereinigung (Verhaltensänderung)

- **AC-12:** Given `temperature` (Stundenverlauf) trägt heute `sms_code="D"`, obwohl `D` in der gesendeten SMS der Tageshöchstwert (`temperature_day_high`) ist / When der Katalog bereinigt wird / Then bekommt `temperature` im Katalog das Kürzel `T`, und `D` fragt danach eindeutig den Tageshöchstwert ab. `T` ist dabei nicht neu erfunden: Telegram zeigt die Temperatur schon heute als `T`, allerdings nur über die benannte Ausnahmeliste aus #1719 S4 (`docs/reference/metric_output_matrix.md` Abschnitt „Grundlage", Wächter `tests/unit/test_telegram_kuerzel_folgt_register.py`). Mit `sms_code="T"` entfällt der Ausnahme-Eintrag für `temperature`, weil Register und Telegram dann ohnehin übereinstimmen. Kein anderer Katalog-Eintrag trägt `T` als `sms_code`, `col_label` oder `sms_multi_symbols`.
  - Test: `test_kuerzel_eindeutig.py::test_temperature_kuerzel_ist_t`, plus Mutations-Gegenprobe (siehe Abschnitt „Mutationen").

- **AC-13:** Given `D` (Tageshöchstwert) und `N` (Nachtwert) sind heute nur lesbare Ausgabe-Kürzel, aber keine sendbaren Eingabe-Kürzel / When ein Nutzer `D` bzw. `N` als Kürzel-Abfrage sendet / Then liefert die Antwort den Tages-Einzelwert der heutigen Etappe für Tageshöchst- bzw. Nachtwert (denselben Wert und dieselbe Einheit, die das Trip-Briefing für diesen Tag zeigt) — **nicht** einen Stundenverlauf, weil diese Größen im Katalog keinen Stundenverlauf führen.
  - Test: `test_kuerzel_eindeutig.py::test_d_und_n_liefern_tageswert_kein_stundenverlauf`.

- **AC-14:** Given ein Nutzer hat bisher `D` gesendet und dafür den Temperatur-**Stundenverlauf** bekommen (weil `temperature.sms_code == "D"`) / When er nach dieser Änderung `D` bzw. `T` sendet / Then liefert `D` den **Tageshöchstwert** (AC-13) und `T` den bisherigen Temperatur-Stundenverlauf — eine beabsichtigte, hier ausdrücklich vermerkte **Verhaltensänderung** (Bereinigung der Doppelbelegung, siehe „Kernproblem"), keine versteckte Nebenwirkung.
  - Test: `test_kuerzel_eindeutig.py::test_t_liefert_den_bisherigen_temperatur_stundenverlauf` (Antwort auf `T` entspricht inhaltlich der bisherigen Antwort auf `D`).

- **AC-15:** Given `fresh_snow` wird in der SMS als `NS24+` ausgewiesen, ist aber unter `sms_code="NS"` eingebbar / When ein Nutzer das gelesene Kürzel `NS24+` unverändert zurücksendet / Then wird es normalisiert (Suffix `24+` entfernt) und als dieselbe Abfrage wie `NS` erkannt.
  - Test: `test_kuerzel_eindeutig.py::test_ns24plus_wird_zu_ns_normalisiert`.

- **AC-22:** Given ein Trip und ein Ortsvergleich mit der Metrik „Temperatur" (`temperature`) sowie ein Temperatur-Alarm / When nach der Umstellung automatisch Briefing, Ortsvergleich-SMS und Alarm-SMS erzeugt werden / Then bleibt die Kurzform-Zeile des **Trip-Briefings** zeichengleich (dort bedeutet `D` schon heute den Tageshöchstwert). An den beiden Stellen, die das Kürzel von `temperature` direkt aus dem Katalog lesen, steht künftig `T` statt `D`: in der **Temperatur-Alarm-SMS** (`alert/render.py:177`) und in der **Ortsvergleich-Kurzform** (`comparison.py`, Leser von `get_sms_code`). Das ist die sichtbare Folge von AC-12 in automatisch versendeten Nachrichten und hier ausdrücklich so gewollt: Ein Kürzel hat überall dieselbe Bedeutung.
  - Test: `test_kuerzel_eindeutig.py::test_automatische_ausgaben_nach_t_umstellung` vergleicht die Trip-Briefing-Zeile vorher/nachher (gleich) und prüft Alarm- und Ortsvergleich-SMS auf `T` statt `D` für die Temperatur.

**Hinweis Renderer-Commit-Gate:** Die Änderung von `MetricDefinition.sms_code` für `temperature` (AC-12) wirkt über `SMS_SYMBOL_BY_METRIC` in den SMS-Renderer (`src/output/renderers/sms_trip.py`) — der Renderer-Commit-Gate und `briefing_mail_validator.py` sind vor „E2E bestanden" erneut frisch zu fahren.

### G. Kollisionsfreiheit

- **AC-16:** Given die Menge aller Befehlswörter (deutsch **und** englisch, inklusive Aliase wie `NOW`/`HELP`) und die Menge aller Eingabe-Kürzel (alle Ausgabe-Kürzel nach Normalisierung, plus das neue `T`) / When beide Mengen gebildet werden / Then sind sie disjunkt — kein Befehlswort ist gleichzeitig ein gültiges Eingabe-Kürzel.
  - Test: `test_kuerzel_eindeutig.py::test_befehle_und_kuerzel_sind_disjunkt`.

- **AC-17:** Given der Premium-SMS-Verknüpfungscode hat die Gestalt `^XX[A-HJKMNP-Z]{3}[2-9]{3}$` / When die Menge aller Befehlswörter gegen dieses Muster geprüft wird / Then matcht kein Befehlswort dieses Muster.
  - Test: `test_kuerzel_eindeutig.py::test_kein_befehlswort_kollidiert_mit_verknuepfungscode`.

- **AC-18:** Given ein Nutzer mit gültigem Verknüpfungscode / When er `<Code> tomorrow` bzw. `<Code> restday 2` über den echten Premium-SMS-Journal-Eingang (`inbound_sms_reader.py`, `split_link_code` + `_verarbeite_befehl`) sendet / Then wird Code und Befehl korrekt getrennt, und der englische Befehl wirkt identisch zum deutschen Pendant (`morgen`/`ruhetag 2`).
  - Test: `test_kurzform_befehle_englisch.py::test_englischer_befehl_nach_verknuepfungscode_e2e`, zwei verschiedene Nutzer (Mandantentrennung).

### H. Sprachumfang: jede kurzform-erreichbare Antwort ist englisch

Auf einem Kurzform-Kanal (Premium-SMS immer, Telegram bei `telegram_style="kurzform"` des aufgelösten Ziels) ist **jede** Antwort englisch, nicht nur HELP/CODES. Für zielgebundene Befehle gilt der Stil des Ziels (AC-5). Für ziellose Befehle gilt das gesendete Wort (AC-5). Dasselbe gilt, wenn sich **kein eindeutiges Ziel** ergibt, etwa bei mehreren passenden Trips oder Ortsvergleichen mit Rückfrage: Die Sprache folgt dann dem gesendeten Wort (`PAUSE`/`RESUME` → englisch, `WEITER` → deutsch). Bei Wörtern, die in beiden Sprachen gleich lauten (`PAUSE`, `STATUS`, `SKIP`, `STOP`), antwortet Telegram in diesem Fall englisch. Ein vorangestellter Name, der ein Ziel eindeutig bestimmt, macht den Befehl zielgebunden. Dann gilt der Stil dieses Ziels, auch für `HILFE`/`HELP`. Für einen **unbekannten Befehl** auf Telegram gibt es weder Ziel noch erkanntes Wort, deshalb antwortet Telegram dort deutsch mit dem Zusatz „English: send HELP". Premium-SMS antwortet auch dann englisch. Erreichbare Textarten (Beleg-Fundstellen):

| Textart | Fundstelle (heutiger deutscher Text) |
|---|---|
| Unbekannter Befehl | `unknown_command_body()`, `trip_command_processor.py:268-277` |
| Ortsvergleich lehnt Trip-only-Befehl ab | `_compare_unavailable()`, `trip_command_processor.py:1136-1144` |
| Mehrdeutigkeit (PAUSE/RESUME bei mehreren Zielen) | `resolve_command_target()`-Rückgabetext, genutzt in `inbound_sms_reader.py:393-396` |
| PAUSE-Bestätigung (Trip) | `_apply_pause()`, `trip_command_processor.py:2388-2397` |
| PAUSE-Bestätigung (Ortsvergleich, unbefristet) | `_apply_compare_pause()`, `trip_command_processor.py:1161-1169` |
| SKIP-Bestätigung | `_apply_skip()`, `trip_command_processor.py:2399ff.` |
| STOP-Bestätigung (Trip) | `_cancel_trip()`, `trip_command_processor.py:2683-2695` |
| RESUME(WEITER)-Bestätigung (Trip) | `_resume_trip()`, `trip_command_processor.py:2697-2709` |
| RESTDAY(RUHETAG)-Bestätigung | `_apply_ruhetag()`, `trip_command_processor.py:2116-2169` |
| STATUS-Kopf | `_show_status()`, `f"Status: {trip.name}"`, `trip_command_processor.py:2258-2268` |

- **AC-19:** Given jede der oben gelisteten Textarten wird auf einem Kurzform-Kanal ausgelöst / When die Antwort tatsächlich versendet wird / Then ist ihr Text vollständig englisch (Kopf, Fließtext und ggf. Bestätigungssatz). Kein deutsches Wort wirbt mehr für einen deutschen Befehl in einer englischen Nachricht. **Einzige Ausnahme:** Auf einen unbekannten Befehl antwortet Telegram deutsch mit dem Zusatz „English: send HELP", weil es weder ein Ziel noch ein erkanntes Wort gibt, an dem sich die Sprache ablesen ließe (siehe Einleitung Abschnitt H). Für diese Zeile prüft der Test auf Telegram den deutschen Text samt Zusatz, auf Premium-SMS den englischen Text.
  - Test: `test_kurzform_befehle_englisch.py::test_alle_erreichbaren_textarten_sind_englisch`, parametrisiert über die Tabelle oben, je Kanal Premium-SMS und Telegram-Kurzform.

### I. Telegram-Menü

- **AC-20:** Given `BOT_COMMANDS` (`telegram.py:122-140`) ist ein statisches Listen-Literal, das `prod_selftest.py::_load_bot_commands` per `ast.literal_eval` liest / When der Befehlssatz um englische Wörter erweitert wird / Then bleibt `BOT_COMMANDS` ein Literal (keine Ableitung zur Laufzeit) und enthält zusätzlich zu den bestehenden deutschen Einträgen die neuen englischen Slash-Befehle (`/today`, `/tomorrow`, `/now`, `/storms`, `/route`, `/restday`, `/status`, `/pause`, `/skip`, `/stop`, `/resume`, `/help`, `/codes`, `/kuerzel`), alle im erlaubten Namensraum `[a-z0-9_]{1,32}` und die Gesamtliste bleibt unter dem Limit von 100 Einträgen.
  - Test: bestehender Vollständigkeits-Test `test_befehlsangebot_vollstaendig.py`, erweitert um einen Drift-Test, der `BOT_COMMANDS` gegen die vollständige Wortmenge aus `_COMMAND_SPECS` (`wort` ∪ `wort_en`) abgleicht.

### K. Dauerhafter Doppelungs-Wächter (PO-Vorgabe 27.09.2026)

PO wörtlich: „Ich möchte einen permanenten Test, der sicherstellt, dass es nicht zu einer Dopplung von Metriken, Kurzformen, Kürzeln etc. kommt."

Gemessener Ist-Stand vom 27.09.2026 über alle 32 `_METRICS`-Einträge: `id`, `label_de`, `col_key`, `col_label`, `compact_label`, `sms_code` und `sms_multi_symbols` sind heute schon eindeutig. Doppelt vergeben sind:
- `alert_label` „Schnee" für `snow_depth` **und** `fresh_snow`. Das ist ein echter Fehler: Eine Alarm-Nachricht sagt „Schnee", ohne dass man erkennt, ob die Schneehöhe oder der Neuschnee gemeint ist. Die Behebung ist Teil dieser Spec (AC-26).
- `alert_label` „Temp" für `temperature` und `temperature_cold`. Das ist zulässig: `temperature_cold` ist keine eigene Größe, sondern der nicht wählbare Kälte-Alarm auf dieselbe Temperatur.
- `D` ist heute zweimal belegt (`temperature` und `temperature_day_high`). Das behebt AC-12. Der Frontend-Test `metricKuerzelLegende.test.ts:399-410` schreibt diese Doppelung sogar als Soll fest („`D` genau zweimal"). Er wird auf „`D` einmal, `T` einmal" umgestellt.
- Nicht als Kennung geprüft werden `friendly_label` (Deko-Symbol, von allen vier Bewölkungsgrößen bewusst geteilt) und `dp_field` (Datenquelle; mehrere Auswertungen lesen denselben Messwert). Beides steht mit Begründung im Test.

- **AC-25:** Given der Metrik-Katalog, die Warn-Kürzel, die übrigen SMS-Bausteine, der Befehlssatz und das Telegram-Menü / When der Kern-Testlauf läuft (jeder Commit, CI-Job `test`) / Then scheitert ein **dauerhafter** Wächter, sobald eine dieser Doppelungen entsteht:
  1. Zwei `_METRICS`-Einträge (auch nicht wählbare) teilen sich `id`, `label_de`, `col_key`, `col_label`, `compact_label`, `alert_label` oder eine der neuen Bedeutungen (en/de).
  2. Ein Kürzel gehört zu mehr als einer Metrik. Geprüft wird über `sms_code`, `sms_multi_symbols` und die Grammatik-Formen (`TH:`, `NS24+`, …) nach Normalisierung.
  3. Ein Warn-Kürzel ist innerhalb von `HAZARD_SMS_SYMBOLS` doppelt, oder ein SMS-Baustein aus `builder.py` kollidiert mit einem Katalog-Kürzel. Überschneidungen zwischen den Gruppen sind **nicht** erlaubt (AC-11, AC-27).
  4. Ein Wort löst zwei verschiedene Befehle aus oder gleicht einem Kürzel (AC-16). Dass ein Befehl in beiden Sprachen gleich geschrieben wird (`PAUSE`, `STATUS`, `SKIP`, `STOP`), ist keine Doppelung: Es ist ein Wort für einen Befehl.
  5. Ein Telegram-Menüeintrag (Slash-Name) kommt zweimal vor. Gleich geschriebene Befehle stehen deshalb nur einmal im Menü.

  Erlaubte Doppelungen stehen in **einer** Ausnahmeliste im Test, jeweils mit Begründungssatz. Heute ist das nur `temperature`/`temperature_cold` für `alert_label`. Eine Ausnahme, die nicht mehr vorkommt, macht den Test ebenfalls rot, damit die Liste nicht veraltet. Der Wächter berechnet alle Soll-Mengen aus den Registern und tippt keine davon ab. Er meldet seine Trefferzahl (> 0), damit er nicht still grün ist, wenn er nichts findet.
  - Test: `tests/unit/test_keine_doppelten_kennungen.py` (dauerhaft, Kern-Schicht, ohne Netz). Pro Punkt 1–5 prüft eine Gegenprobe den Wächter mit einer verfälschten Katalogkopie und erwartet Rot. Er ergänzt die bestehenden Wächter und ersetzt keinen: `test_metrik_listen_register_ratchet.py` fängt Metrik-Listen außerhalb des Katalogs, `test_sms_token_symbol_register_ratchet.py` fängt SMS-Symbole, die vom Katalog abweichen. Zusammen decken die drei „doppelt im Katalog", „zweite Liste außerhalb" und „abweichendes Symbol" ab.

- **AC-26:** Given `snow_depth` und `fresh_snow` tragen beide `alert_label="Schnee"` / When ein Alarm zu einer der beiden Größen versendet wird / Then heißt es für `snow_depth` „Schneehöhe" und für `fresh_snow` „Neuschnee". Die beiden Alarme sind damit unterscheidbar, und AC-25 Punkt 1 ist grün, ohne dass dafür eine Ausnahme nötig ist.
  - Test: `test_keine_doppelten_kennungen.py` (Punkt 1) sowie ein Alarm-Rendertest je Größe, der den Namen in der versendeten Alarm-Nachricht prüft.

- **AC-27:** Given die Warn-Kürzel `TH`, `FL`, `HR`, `W`, `CL` und die Météo-France-Bausteine `HR:`/`TH:` gleichen heute Wetter-Kürzeln oder einander / When eine Warn-SMS oder eine Kurzform-SMS mit Météo-France-Risiko entsteht / Then tragen sie neue, überall eindeutige Kürzel: Gewitter `TS`, Hochwasser `FO`, Starkregen `RA`, Sturmböen `WG`, Sperrung `AB`, Météo-France-Regenrisiko `VR:`, Météo-France-Gewitterrisiko `VT:`. `SN`, `IC`, `HT`, `CD` und `FR` bleiben unverändert. Die neuen Kürzel wurden am 27.09.2026 gegen alle Katalog-, Baustein- und Befehlskürzel geprüft, es gibt keine Kollision. Die Umbenennung ist eine sichtbare Änderung in Warn-SMS und Kurzform-SMS und wird hier ausdrücklich so beschlossen.
  - Test: `test_keine_doppelten_kennungen.py` (Punkt 3, jetzt ohne Ausnahme) sowie je ein Rendertest für Warn-SMS und Météo-France-Block, der die neuen Kürzel in der versendeten Nachricht prüft. Betroffen sind `hazard_symbols.py`, `builder.py` (`VIGI_TH`/`VIGI_HR`), `docs/reference/sms_format.md` und die bestehenden Tests, die die alten Kürzel erwarten (gemessen: 15 Dateien in `src/`, `tests/`, `frontend/src/` nennen `HAZARD_SMS_SYMBOLS` oder `VIGI_HR`).

### J. Ablösung der Vorgänger-Spec

- **AC-21:** Given `docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md` enthält AC-10 (Vollständigkeit von Menü/Lang-/Kurzhilfe), AC-11 (GSM-7 + ≤3 Segmente der alten Kurzhilfe) und AC-23 (Premium-SMS bekommt die alte Kurzhilfe statt Langhilfe) / When diese Spec umgesetzt wird / Then werden alle drei dort als „abgelöst durch feat_2417_kurzform_englisch" vermerkt (Status-Änderung in der Datei selbst, keine neue AC-Nummer dort), weil ihr bisheriger Inhalt (Wortübersetzung ohne Wirkungsaussage) durch AC-8/AC-9 dieser Spec ersetzt wird.
  - Test: kein neuer Testcode — Dokumentationsänderung, geprüft durch Review/Doku-Vollständigkeit.

## Risiken

- **Reservierte SMS-Wörter:** `STOP` und `HELP` können von SMS-Gateways/Relays (seven.io, Garmin) als Opt-out/Hilfe-Schlüsselwort abgefangen werden, bevor die Nachricht überhaupt bei Gregor Zwanzig ankommt. `stop`/`help` existieren als deutsche Wörter bereits heute unverändert; der Prod-Test vom 27.09. sendete nur `<Code> hilfe`, nicht `<Code> stop`. **Ob ein nacktes `STOP`/`HELP` per Premium-SMS überhaupt ankommt, ist unbelegt** — keine AC dieser Spec verspricht das. Für die Hilfe gibt es den Ausweichweg `HILFE`, auf den die erste Zeile der HELP-Antwort („German works too") hinweist. Für `STOP` gibt es keinen gleichwertigen Ausweichweg, weil das deutsche Wort heute schon `stop` lautet. Dieses Risiko besteht also bereits unverändert und wird durch diese Spec weder größer noch kleiner. Der HELP-Wortlaut enthält darüber bewusst keinen eigenen Warnsatz, weil nicht belegt ist, dass das Problem überhaupt auftritt.
- **Kollisionsrisiko bei künftigen Katalog-Erweiterungen:** Eine neue Metrik mit `sms_code`, der zufällig einem künftigen Befehlswort gleicht, würde AC-16 rot werden lassen — das ist beabsichtigt (Frühwarnung), kein Fehlalarm.
- **BOT_COMMANDS wächst** von 17 auf ca. 26–30 Einträge (Limit 100, unkritisch, aber `prod_selftest.py`-Menüzahl-Erwartung ist mitzuziehen).

## Out of Scope

- Normale (Nicht-Premium-)SMS: kein Eingangsweg vorhanden (im Code geprüft) — keine AC dafür.
- Etappennummer `E4` vs. „02" (Issue #2441) — eigenes Ticket, nicht Teil dieser Spec.
- Wiedereinführung des Kanals Signal — app-weit entfernt seit #610, nicht Gegenstand dieser Spec.

## Test-/Verifikationsplan

### Kern (deterministisch, ohne Netz, `--disable-socket`)

| Datei | Inhalt |
|---|---|
| `tests/tdd/_befehl_e2e_fixtures.py` (bestehend, erweitert) | `sms_segments()` bleibt Quelle der Segmentzahl-Messung; PO-Lage-Fixture wiederverwendet |
| `tests/tdd/test_kurzform_befehle_englisch.py` (CREATE) | AC-2–AC-8, AC-18, AC-19: Wirkung je Befehl, Sprache je Kanal, Segmentgrenzen, Kollisions-E2E über den echten Eingang |
| `tests/tdd/test_kuerzel_eindeutig.py` (CREATE) | AC-9–AC-17: CODES-Vollständigkeit gegen Ausgabe-Register, Eindeutigkeit über alle Abschnitte, Disjunktheit, Temperatur-Bereinigung, NS-Normalisierung |
| `tests/tdd/test_befehlsangebot_vollstaendig.py` (bestehend, angepasst) | AC-20: BOT_COMMANDS-Drift gegen `_COMMAND_SPECS`; Umstellung auf Feldnamen-Zugriff statt Tupel-Entpacken |
| `tests/tdd/test_kommandoliste_einzelquelle.py`, `test_befehle_{email,telegram,premium_sms}_e2e.py` (bestehend, angepasst) | Umstellung von Tupel-Entpacken (4 Felder) auf Feldnamen-Zugriff (NamedTuple), da `_COMMAND_SPECS` jetzt mehr Felder trägt |

Jeder datenbewegende Pfad (mutierende Befehle über den Eingang) wird mit **zwei verschiedenen Nutzern** getestet (Mandantentrennung, unverändertes Projekt-Prinzip).

### Live (Staging/Prod, Marker `live`)

- **Telegram-Kurzform auf Staging** ist der Live-Nachweis, der den Deploy gated: englische HELP-/CODES-/TOMORROW-Antwort gegen einen Staging-Nutzer mit `telegram_style="kurzform"`.
- **Premium-SMS läuft NICHT live über die zweite seven.io-Nummer** in diesem Workflow — API-Send kommt dort als `InfoSMS` an, nicht als Premium-SMS-Antwort (#2322/#2417-Kommentare). Stattdessen: Premium-SMS wird im Kern durch den echten `inbound_sms_reader`-Pfad geprüft (siehe oben). Ein manueller Dialog mit dem Handy des PO (HELP, CODES, TOMORROW) dient als Nachkontrolle **nach** dem Prod-Deploy und blockiert den autonomen Deploy **nicht**.

### Mutations-Gegenprobe (PFLICHT, je ein Test muss rot werden)

| Mutation | Erwarteter roter Test |
|---|---|
| Wirkungstext (`wirkung_en`) eines Befehls wird geleert oder umformuliert | `test_help_kurzform_ist_der_freigegebene_wortlaut` |
| Eine Zeile des CODES-Wortlauts wird verändert | `test_codes_ist_der_freigegebene_wortlaut` |
| Telegram-`help` antwortet deutsch statt englisch (ziellos) | `test_ziellos_sprache_folgt_wort` |
| Ein CODES-Kürzel verliert seine Bedeutung (leerer String) | `test_codes_vollstaendig_gegen_ausgabe_register` |
| Telegram-Sprache wird vertauscht (kurzform→deutsch, Standard→englisch) | `test_telegram_sprache_folgt_telegram_style` |
| CODES-Aufbau erhält einen fest eingetippten Bedeutungstext statt ihn aus dem Katalog zu lesen | `test_bedeutung_kommt_nur_aus_dem_katalog` |
| `temperature` bekommt wieder `sms_code="D"` | `test_temperature_kuerzel_ist_t` und `test_automatische_ausgaben_nach_t_umstellung` |
| `wort_en` wird aus der Bare-Keyword-Erkennung entfernt | `test_kurzform_befehle_englisch.py` (Parametrisierung über alle englischen Wörter schlägt für das betroffene Wort fehl) |

## Known Limitations

- CODES braucht 5 SMS-Segmente, also etwa das Fünffache einer einzelnen Premium-SMS-Antwort. CODES wird nur auf ausdrückliche Anfrage gesendet, nie automatisch.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Dies ist eine Verhaltenskorrektur eines bestehenden, freigegebenen Befehlssatzes (Sprachwahl der Kurzform, Bereinigung einer Kürzel-Doppelbelegung im Katalog) und keine neue Grundsatzentscheidung über Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma oder Test-/Deploy-Strategie im Sinne der ADR-Kriterien aus `CLAUDE.md`. Die Ablösung der Vorgänger-AC läuft über den dokumentierten Spec-Supersede-Mechanismus (Status-Vermerk in `feat_2417_befehle_e2e_echter_eingang.md`).

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_command_processor.py` | MODIFY | `_COMMAND_SPECS` → NamedTuple mit `wort`, `wort_en`, `arg`, `beschreibung_de`, `wirkung_en`, `kinds`; `_KURZHILFE_ENGLISCH` entfällt; neue Kanalsprache-Logik; neuer Befehl `CODES`/`KUERZEL`; englische Fassungen aller in Abschnitt H gelisteten Textarten |
| `src/app/metric_catalog.py` | MODIFY | `temperature.sms_code` → `"T"`; neues Feld mit englischer und deutscher Bedeutung je Kürzel in jedem `MetricDefinition`-Eintrag (einzige Quelle für Wettermetrik-Bedeutungen); `temperature` aus der Telegram-Ausnahmeliste streichen; `NS24+`-Normalisierung |
| `src/output/tokens/hazard_symbols.py` | MODIFY | englische und deutsche Bedeutung je Warn-Kürzel direkt bei `HAZARD_SMS_SYMBOLS` |
| `src/output/tokens/builder.py` | MODIFY | Bedeutung (en/de) der Bausteine ohne Katalog-Eintrag und der Formatzeichen direkt bei ihren Konstanten |
| `tests/unit/test_telegram_kuerzel_folgt_register.py` | MODIFY | Ausnahme `temperature` entfällt |
| `tests/unit/test_keine_doppelten_kennungen.py` | CREATE | dauerhafter Doppelungs-Wächter (AC-25) |
| `frontend/src/lib/components/shared/__tests__/metricKuerzelLegende.test.ts` | MODIFY | Soll „`D` genau zweimal" wird „`D` einmal, `T` einmal" (Folge von AC-12) |
| `src/app/metric_catalog.py` (`snow_depth`, `fresh_snow`) | MODIFY | `alert_label` „Schneehöhe" / „Neuschnee" (AC-26) |
| `docs/reference/metric_output_matrix.md` | MODIFY | CODES/KUERZEL (Kurzform + deutsch) als neuer Ausgabeort in Abschnitt 2 mit Wächter; Absatz „Grundlage" um das neue Bedeutungsfeld ergänzen, Ausnahme `temperature` (`T`) streichen |
| `docs/reference/sms_format.md` | MODIFY | Verweis, dass die Bedeutung jedes Kürzels im Katalog steht und über CODES abrufbar ist |
| `src/services/inbound_sms_reader.py` | MODIFY | `CODES` ziellos wie `hilfe`; englische Wörter nach Verknüpfungscode erkannt |
| `src/services/inbound_telegram_reader.py` | MODIFY | Telegram-Kurzform-Sprachumschaltung nach `telegram_style`; englische Wörter erkannt |
| `src/output/channels/telegram.py` | MODIFY | `BOT_COMMANDS`-Literal um englische Slash-Befehle erweitert |
| `src/services/trip_selection.py` | MODIFY | `ZIELLOS_SCHLUESSEL` um `codes`/`kuerzel` ergänzt |
| `tests/tdd/test_kurzform_befehle_englisch.py` | CREATE | AC-2–AC-8, AC-18, AC-19 |
| `tests/tdd/test_kuerzel_eindeutig.py` | CREATE | AC-9–AC-17 |
| `tests/tdd/test_befehlsangebot_vollstaendig.py` | MODIFY | AC-20 Drift-Test, Feldnamen-Umstellung |
| `tests/tdd/test_kommandoliste_einzelquelle.py`, `test_befehle_{email,telegram,premium_sms}_e2e.py`, `_befehl_e2e_fixtures.py` | MODIFY | Tupel-Entpacken → Feldnamen-Zugriff |
| `docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md` | MODIFY | AC-10/AC-11/AC-23 als abgelöst vermerken |

## Changelog

- 2026-09-27: Initial spec created (Issue #2417, PO-Entscheid 27.09.2026: Kurzform ist englisch, also auch ihre Befehle).
