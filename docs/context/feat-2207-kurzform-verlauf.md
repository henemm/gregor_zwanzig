# Context: feat-2207-kurzform-verlauf

Issue: [#2207](https://github.com/henemm/gregor_zwanzig/issues/2207) — Scheibe **S5** von Epic
[#2133](https://github.com/henemm/gregor_zwanzig/issues/2133).
Vorbedingungen S1 (#2134) und S2 (#2185/#2186) sind live, ebenso S3 (#2126/#2168) und S4 (#2184).

## Request Summary

Der Ad-hoc-Verlauf soll auf dem Kurzform-Kanal (Premium-SMS, perspektivisch SMS) in der Kurzform
ausgeliefert werden — Kürzel aus dem Metrik-Katalog statt ausgeschriebener Wörter, Wechselpunkte
statt Tabelle — mit einer festgelegten Längengrenze und Kürzungsregel. Heute bekommt der
Kurzform-Kanal wortwörtlich denselben Text wie E-Mail.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py:1179-1230` | `_format_drilldown` — **die** zu erweiternde Stelle. Erzeugt seit S2 die Wechselpunkt-Gruppen (`HH:MM–HH:MM  <Text>`), Gruppenschlüssel ist der formatierte Anzeigetext + Hagelnotiz |
| `src/services/trip_command_processor.py:917-982` | `_handle_drilldown` — Legacy-Abruf (thunder/wind/precip), ruft `_format_drilldown` (`:970`), setzt `with_emoji = channel == "telegram"` (`:931`) |
| `src/services/trip_command_processor.py:998-1041` | `_handle_metric_drilldown` — Abruf JEDER Katalog-Größe (S1), ruft `_format_drilldown` (`:1028`). Benennt eine ungefüllte Größe bereits ehrlich (`:1018-1027`) |
| `src/services/trip_command_processor.py:1043-1178` | `_handle_hours_drilldown` — Vierspalten-Stundentabelle, nutzt `_format_drilldown` **nicht** (S2 hat sie bewusst unangetastet gelassen) |
| `src/services/trip_command_processor.py:56-63` | `InboundMessage`-Dataclass — Feld `channel: str` |
| `src/app/metric_catalog.py:28-96` | `MetricDefinition`; für S5 relevant: `sms_code` (`:75`, GSM-7-taugliches Kürzel), `unit`/`display_unit`, `label_de`, `decimals`, `selectable` (`:73`) |
| `src/app/metric_catalog.py:525-539`, `:570-593` | Beispiel-Einträge `cloud_low` (`sms_code="CL"`) und `visibility` (`sms_code="VS"`, `display_unit="km"`, `decimals=1`) |
| `src/services/notification_service.py:1809-1820` | `send_command_reply_premium_sms` — reicht `result.confirmation_body` unverändert durch |
| `src/services/notification_service.py:1795-1807`, `:1822-1839` | E-Mail- und Telegram-Zweig — identische Durchreichung, dürfen sich nicht ändern |
| `src/output/tokens/render.py:17-23`, `:73-121` | `DROP_ORDER` + `_truncate()` — die vorhandene Kürzungsstrategie des Briefings (Feld-Weglassung, kein Textabschnitt); `render_line()` wirft `ValueError`, wenn 160 Zeichen trotzdem gerissen werden |
| `src/utils/ascii_fold.py` | `fold_ascii()` — Umlaut-Digraphen + `anyascii`-Transliteration, nicht faltbare Zeichen werden sichtbar `?`, keine stille Löschung |
| `src/output/channels/seven_io_base.py:155-187` | `send()` transportiert den Body 1:1 ans Gateway — keine Längenprüfung |
| `src/output/channels/premium_sms.py:18-20` | Docstring: Premium-SMS hat **absichtlich keinen eigenen Renderer** für den Briefing-Text, damit SMS und Premium-SMS inhaltlich nicht auseinanderlaufen |
| `docs/reference/sms_format.md` (v2.29, `status: active`) | **SSOT der Kurzform** — Token-Schreibweisen, Stundenformat `@7` ohne führende Null, Einheiten weggelassen, Rundungsregeln (§ Werte), Truncation-Strategie (§6, `:485-499`) |

## Existing Patterns

- **Ein Vokabular, kein zweites.** Seit #2134 speisen sich acht vorher unabhängige Befehlslisten aus
  dem Metrik-Katalog. Das Kurzform-Kürzel steht dort bereits als `sms_code` — S5 darf keine neue
  Abkürzungstabelle anlegen.
- **Kurzform-Konventionen des Briefings** (`docs/reference/sms_format.md`): Token-Kürzel
  englisch/international, Werte ohne Einheit (Ausnahme `%`), Stunde als `@7` statt `@07`,
  Temperatur ganzzahlig, Niederschlag eine Nachkommastelle.
  Beispielzeile: `Ballone: D16 R- PR10%@14(20%@17) W- G- TH:- TH+:-` (49 Zeichen).
- **Kürzen heißt Weglassen, nicht Abschneiden.** `_truncate()` entfernt ganze Felder in fester
  Reihenfolge (`DROP_ORDER`), strippt danach die Spitzenwert-Klammern, und wirft am Ende lieber
  einen Fehler, als eine halbe Zeile auszuliefern.
- **Kanal-Verzweigung existiert bereits**, aber nur als Emoji-Schalter
  (`with_emoji = channel == "telegram"`) und als Herkunftszeilen-Schalter
  (`zeige_herkunft = channel not in ("sms", "premium_sms")`, `:1387,:1464,:1524`).
- **Ehrliche Lücke statt Schweigen** ist an einer Stelle schon gebaut
  (`_handle_metric_drilldown:1018-1027`) und im Epic als Anforderung für S5 wiederholt.

## Dependencies

- **Upstream:** `WeatherExtractor.drilldown()` (metrik-generisch, keine Erlaubt-Liste),
  `get_metric()` / Metrik-Katalog, `_metric_formatter()`, `_day_window()`, `local_fmt()`.
- **Downstream:** `CommandResult.confirmation_body` → `NotificationService.send_command_reply_*` →
  `PremiumSmsOutput` / `EmailOutput` / Telegram. Ebenso die Telegram-Buttons (`reply_markup`), die
  auf dem Kurzform-Kanal bedeutungslos sind.

## Existing Specs

| Spec | Status | Bezug |
|---|---|---|
| `docs/specs/modules/feat_2185_verlauf_wechselpunkte.md` | draft (v1.0) | S2 — die Wechselpunkt-Form, auf der S5 aufsetzt |
| `docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md` | implemented (v1.0) | S1 — Befehlssatz aus dem Katalog |
| `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md` | approved (v1.1) | S4 — Premium-SMS erreicht den Processor |
| `docs/specs/modules/feat_2126_kanaltreue_adhoc_antwort.md` | approved (v1.1) | S3 — Antwort läuft über den Eingangskanal |
| `docs/specs/modules/trip_command_processor.md` | approved (v2.1) | Rahmen-Spec des Processors |
| `docs/specs/modules/inbound_command_channels.md` | draft (v1.4) | Polling-Schicht der Eingangskanäle |
| `docs/reference/sms_format.md` | active (v2.29) | Kurzform-SSOT — **keine** `docs/specs/`-Datei, aber die maßgebliche Referenz |

## Risks & Considerations

1. **🔴 Der Kanalname `sms` hat heute keinen Inbound-Erzeuger.** Produktiv gesetzt werden nur
   `"email"` (`inbound_email_reader.py:143-148`), `"telegram"`
   (`inbound_telegram_reader.py:230-232`, `:328`) und `"premium_sms"`
   (`inbound_sms_reader.py:264`). `"sms"` kommt ausschließlich in Tests vor. Die Kurzform-Antwort
   greift also faktisch **nur bei Premium-SMS** — die Verzweigung muss `"sms"` trotzdem
   mit abdecken, sonst entsteht später eine stille Lücke.
2. **Regressionsgefahr für E-Mail und Telegram.** `_format_drilldown` wird von beiden Abrufwegen
   und zusätzlich von vier Altwächtern benutzt (`test_issue_654_telegram_thunder_drilldown.py`,
   `test_hail_telegram_stunden_drilldown.py`, `test_telegram_drilldown_local_time_boundary.py`,
   `test_drilldown_day_window_local_date.py`). Die Langform muss zeichengleich bleiben.
3. **Keine Längengrenze im gesamten Kommando-Antwortpfad.** Weder Processor noch
   `send_command_reply_premium_sms` noch `SevenIoChannelBase.send` prüfen die Länge; ADR-0049
   sagt zu Zeichenlängen und Segmentierung nichts. Die Grenze muss die Spec setzen — der einzige
   Präzedenzfall im Repo ist 160 Zeichen aus dem Briefing.
4. **Kürzungsregel ist eine Produktentscheidung.** Beim Briefing ist die Zeile ein Feldbündel, aus
   dem sich Felder weglassen lassen. Ein Verlauf ist eine Folge von Zeitbereichen — dort ist
   „weglassen" nicht neutral: Jede weggelassene Stunde ist eine verschwiegene Auskunft. Die Regel
   muss die Lücke also entweder benennen oder gröber verdichten, statt still zu kürzen
   (Anschluss an Risiko 5 und an `project_nur_daten_keine_handlungsempfehlung`).
5. **Geführt ≠ gefüllt.** Eine im Gebiet nicht befüllte Größe muss auch in der Kurzform benannt
   werden. Für den Ganz-oder-nichts-Fall ist das gebaut (`:1018`), für einzelne Lückenstunden
   trägt heute `fmt(None, …)` einen eigenen Anzeigetext und damit eine eigene Gruppe.
6. **GSM-7.** Der Verlauf enthält heute Zeichen außerhalb GSM-7 — Gedankenstrich `–` als
   Bereichstrenner (`:1225`), Mittelpunkt `·` als Notiz-Trenner (`:1228`), Gradzeichen und Umlaute
   aus `label_de`. Für den Kurzform-Zweig braucht es `fold_ascii()` bzw. die GSM-7-Faltung analog
   `comparison.py:618-640`.
7. **Telegram-Buttons im Kurzform-Zweig.** `reply_markup` wird unverändert mitgegeben; auf
   Premium-SMS ist es wirkungslos, aber auch nicht schädlich — kein Handlungsbedarf, nur nicht
   versehentlich für die Kanalunterscheidung heranziehen.
8. **Bindung an die Trip-Metrikauswahl bleibt aus.** Epic-Vorgabe: die Auswahl steuert, was
   ungefragt kommt, nicht, was man fragen darf.

## Analysis

### Type

**Feature** — letzte Scheibe des Epics #2133, kein Fehlverhalten, sondern eine fehlende Ausbaustufe.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_command_processor.py` | MODIFY | Gruppierungsschleife (`:1209-1220`) in einen geteilten Helfer auslagern; neue Kurzform-Formatierung daneben; Kanalverzweigung an den zwei Aufrufstellen (`:970`, `:1028`) |
| `docs/reference/sms_format.md` | MODIFY | Bereichsnotation `@h1-h2` und die Kürzungsregel des Kurzform-Verlaufs in die SSOT aufnehmen (Doku, keine LoC) |
| `docs/specs/modules/feat_2207_kurzform_verlauf.md` | CREATE | Spec mit ACs |
| `tests/tdd/test_adhoc_kurzform_verlauf.py` | CREATE | TDD-RED-Datei |

### Scope Assessment

- Produktivdateien: **1** (`trip_command_processor.py`)
- Geschätzte LoC: **+100 bis +130** Produktivcode — innerhalb des 250er-Limits
- Risk Level: **MEDIUM** — die berührte Funktion bedient vier Kanäle und fünf Regressionswächter

### Technical Approach

**Eigene Kurzform-Formatierung neben `_format_drilldown`, mit ausgelagerter gemeinsamer
Gruppierungslogik.** `_format_drilldown` selbst wird nicht angefasst; nur ihr Innenblock
(„aufeinanderfolgende Stunden mit gleichem Text zu einer Gruppe verschmelzen", `:1209-1220`)
wandert in einen Helfer, den beide Formatierer aufrufen. Damit bleibt der Kern — *wann ändert sich
der Wert* — tatsächlich geteilt (PO-Vorgabe „möglichst viel geteilter Code"), während die
Langform für E-Mail und Telegram zeichengleich bleibt, weil kein Zeichen ihres Ausgabepfads
verändert wird.

Die Kanalverzweigung sitzt an den beiden Aufrufstellen, im Muster des bereits vorhandenen
`with_emoji = channel == "telegram"` (`:931`, `:1056`).

Verworfen: ein Kurzform-Zweig **innerhalb** von `_format_drilldown` (mischt zwei strukturell
verschiedene Ausgabeformen in einem Funktionskörper und zwingt jeden Altwächter auf einen
Default) sowie ein eigenes Modul unter `src/output/renderers/` (dort lebt die Renderer-Schicht des
proaktiven Briefings mit eigener DTO-Welt; der Befehlspfad hätte nur Kopplungskosten davon).

### Entscheidungen (Tech Lead)

| # | Entscheidung | Begründung |
|---|---|---|
| **D1** | Grenze **160 Zeichen**, vorher GSM-7-normalisiert | Einzige im Repo etablierte Zahl (`sms_format.md:45`); darüber zerlegt das Gateway die Nachricht **still** in mehrere kostenpflichtige Segmente — dieselbe Mechanik, die `comparison.py:601-609` als „stille Kostenverdopplung" dokumentiert. Kein technischer Zwang im Code (`seven_io_base.py:167`), also eine bewusste Produktgrenze |
| **D2** | Kürzel = `sms_code`; ist es leer, der `col_label` | Beides Katalogfelder, keine zweite Liste. Betrifft genau zwei Größen: `temperature_night` (→ `Night`) und `temperature_day_high` (→ `DayMax`); ihre `sms_code` wurden in v2.28 bewusst geleert. 27 der 29 wählbaren Größen tragen ein Kürzel, alle kollisionsfrei, alle höchstens zwei Zeichen |
| **D3** | Kürzen heißt: **hintere** Wechselpunkt-Gruppen wegnehmen, nie mitten in einer Gruppe; danach ein Anhang, der die Zahl der nicht gezeigten Stunden **nennt** | Die nahe Zukunft ist die gestellte Frage („wann verzieht sich der Nebel"). Eine weggelassene Stunde ohne Hinweis wäre eine verschwiegene Auskunft; die Zahl im Anhang macht die Lücke sichtbar, ohne einen Rat zu geben (ADR-0007) |
| **D4** | **Keine** Segmentierung in mehrere Nachrichten | Jede Premium-SMS über das Satellitengerät kostet erneut. Eine Nachricht mit ehrlichem Rest-Hinweis ist billiger und ehrlicher als drei Nachrichten |
| **D5** | **Keine** Vergröberung der Werte in diesem Slice | Reizvoll, aber sie bräuchte eine Klassen-Eskalation je Metriktyp (Zahl vs. Himmelsrichtung vs. Gewitterstufe — nicht alles ist vergröberbar) und neue Klassengrenzen sind eine Produktentscheidung. Sprengt die 250 LoC → eigenes Folge-Ticket |
| **D6** | Datenlücke im Verlauf erscheint als `?`, fehlender/unterschwelliger Wert als `-` | Genau die Unterscheidung, die die Kurzform-SSOT bereits trifft (`sms_format.md:436-457`) — nichts Neues erfunden |
| **D7** | Verzweigung deckt `sms` **und** `premium_sms` ab | `sms` hat heute keinen Inbound-Erzeuger; ihn wegzulassen erzeugt eine Lücke, die erst bei Aktivierung des SMS-Wegs sichtbar würde. Kostet in diesem Zuschnitt nichts |
| **D8** | Neue Wörter in der Kurzform sind **englisch** | PO-Ansage 2026-08-22: „SMS ist English." Die Token-Kürzel sind es bereits (`R` = Rain, `TH` = Thunder) |
| **D9** | Die Bereichsnotation kommt in `sms_format.md` | Die Kurzform-SSOT wird erweitert, nicht umgangen — sonst entsteht genau die Zweitliste, die das Epic verbietet |

### Formatentwurf

Langform heute (E-Mail/Telegram, bleibt unverändert):

```
Sichtweite — Verlauf
14:00–16:00  0.3 km
17:00  5.0 km
18:00–21:00  42.5 km
```

Kurzform (neu, Premium-SMS):

```
VS 0.3@14-16 5.0@17 42.5@18-21
```
30 Zeichen. Kürzel `VS` einmal vorn (der Verlauf betrifft genau eine Größe), Werte ohne Einheit,
Stunden ohne führende Null — alles Konventionen aus `sms_format.md:477-478` und §5.

### Dependencies

- **Upstream:** `WeatherExtractor.drilldown()`, `get_metric()`, `_metric_formatter()`,
  `_day_window()`, `local_fmt()`, `fold_ascii()`
- **Downstream:** `CommandResult.confirmation_body` → `send_command_reply_premium_sms` →
  `PremiumSmsOutput`

### Risiken der Umsetzung

1. Versehentliche Änderung von `_format_drilldown` → bricht fünf Wächter
   (`test_adhoc_verlauf_wechselpunkte.py` AC-8 sowie vier Alttests zu Drilldown/Hagel/Zeitzone).
2. Ohne GSM-7-Faltung kippt das Gateway auf UCS-2 und die 160 Zeichen halbieren sich faktisch auf
   70 — die Grenze wäre dann falsch gemessen.
3. `fmt(None, …)` liefert heute den langen Text „keine Daten"; ohne kurzform-taugliche Entsprechung
   verschluckt ausgerechnet die Kurzform die Lücken, die die Langform ehrlich benennt.
4. `tests/helpers/verlauf_abdeckung.py` prüft die Lückenlosigkeit der Langform-Zeilen; für die
   Kurzform braucht es eine eigene Parsing-Variante, sonst bewacht kein Test die Vollständigkeit.

### Ausdrücklich NICHT in dieser Scheibe

- **Telegram-Kurzform.** `telegram_style="kurzform"` wirkt heute nur auf Berichte und Alarme
  (`notification_service.py:612,1104,1391,1682`), **nicht** auf Kommando-Antworten
  (`:1822-1839`). Telegram hat keine Längengrenze, die Langform ist dort strikt reicher. Wird als
  offener Punkt in der Spec benannt, aber nicht mitgebaut.
- **Vergröberung der Werte** (D5) — eigenes Folge-Ticket.
- Die Vierspalten-Stundentabelle `dd_hours_*`, die schon S2 bewusst unangetastet ließ.

## Was sich NICHT ändern darf

- E-Mail- und Telegram-Antworten bleiben zeichengleich (Wächter:
  `tests/tdd/test_adhoc_verlauf_wechselpunkte.py`, AC-8 Kanalparität).
- Kein neues Abrufvokabular, keine zweite Kürzel-Liste neben `sms_code`.
- Kanaltreue aus S3: Antwort geht über den Eingangsweg an den tatsächlichen Absender.
- Keine Handlungsempfehlungen — nur Daten (ADR-0007).
