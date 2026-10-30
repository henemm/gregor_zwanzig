---
entity_id: i18n_pv_mail_validatoren_2663
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2663, python, model-sonnet]
---

# i18n PV: Mail-Validatoren sprachfähig — Marker `X-GZ-Lang`, Erwartungen aus dem Katalog statt Literalen

**Issue:** #2663 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 4 (Mail-Marker), 6 (Validatoren und E2E)

## Approval

- [ ] Approved

## Purpose

Die vier Mail-Validatoren sind das Hard Gate für jeden Mail-Pfad. Sobald ein Renderer Englisch spricht, würden sie eine korrekte englische Mail ablehnen und den Deploy blockieren (Lehre aus #1381, #1404, #1420: Beschriftung geändert, Validator vergessen). Dieses Paket läuft deshalb **vor** allen Renderer-Paketen: jede Mail trägt den Kopf `X-GZ-Lang: de|en`, und die Validatoren bilden ihre Erwartungen (Überschriften, Legendenzeilen, Hinweise, Warn-Wörter) aus dem Python-Katalog in der Sprache dieses Kopfes. Deutsche Mails werden exakt so geprüft wie heute.

## Source

- **File:** `src/output/channels/email.py`, `.claude/hooks/_mail_lang.py` (neu), `.claude/hooks/email_spec_validator.py`, `.claude/hooks/briefing_mail_validator.py`, `.claude/hooks/official_alert_mail_validator.py`, `.claude/hooks/radar_alert_mail_validator.py`, `docs/reference/mail_validators.md`
- **Identifier:** `build_mime_message`, `EmailOutput.send`, `mail_lang`, `validate_message`, `run_validation`, `_OVERVIEW_METRIC_CHECKS`, `_OVERVIEW_WARN_LABEL`, `_VERDICT_RE`, `_INTENSITY_LABELS`

> **Schicht-Hinweis:** Python-Core (`src/output/channels/email.py`) und Hook-Werkzeuge (`.claude/hooks/`). Die Validatoren sind eigenständige Skripte; sie finden `src` relativ zur eigenen Datei (Pfadregel #1409), nie über einen festen Hauptrepo-Pfad. Kein Go- und kein Frontend-Code.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Beide Mail-Arten laufen über dieselben Hilfsfunktionen (`_mail_lang.py`, Katalog `mail.*` für Trip, `vergleich.*` für Ortsvergleich, `warnung.*`/`alarm.*` für Alarme). Es entsteht kein zweiter Validator je Sprache und kein Pendant.
> - **Mandantentrennung:** Der Kopf trägt nur die Sprache des Empfängerkontos; die Validatoren lesen keine Nutzerdaten. Wo ein Aufrufer die Sprache noch nicht kennt, steht `de`, nie ein Nutzer-Fallback `default`.
> - **Kanäle:** Betrifft die E-Mail-Validatoren aller Mail-Arten (Trip-Briefing `full`/`compact`, Ortsvergleich, amtliche Warnung, Radar-/Regen-Alarm). Telegram, SMS und Premium-SMS haben keinen Mail-Kopf; ihre Sprache prüft A2 (#2681) am Staging-Lauf. Kanal-Parität: gleicher Inhalt, nur kanalgerechte Form.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/output/channels/email.py` | MODIFY | `build_mime_message(..., lang=None)` und `EmailOutput.send(..., lang=None)`: Kopf `X-GZ-Lang` (Z. 306–377, 657–667, 855–867), beide Zweige (HTML und Klartext) |
| `.claude/hooks/_mail_lang.py` | CREATE | gemeinsame Hilfe: `mail_lang(msg)`, `erwartet(key, lang, **p)`, `marker(key, lang)`, `HEADER_PFLICHT` |
| `.claude/hooks/email_spec_validator.py` | MODIFY | Ortsvergleich: Warn-Zeile (Z. 503), Zeit-Spalte (Z. 575), Überblickszeilen (Z. 650–693, 719–723), `--eml`, Aufteilung von `run_validation` |
| `.claude/hooks/briefing_mail_validator.py` | MODIFY | Trip-Briefing: `"Tag"` (Z. 205), `"Nacht am Ziel"` (Z. 291, 547), `"kein Regen"` (Z. 412), `validate_message` (Z. 613), `--eml` |
| `.claude/hooks/official_alert_mail_validator.py` | MODIFY | amtliche Warnung: `_VERDICT_RE` (Z. 52), `_EAWS_WORDS` (Z. 69), Warn-Wörter (Z. 60, 78–81), `Gültig:` (Z. 86, 90), `Quelle:` (Z. 102), Entwarnung (Z. 160), `--eml` |
| `.claude/hooks/radar_alert_mail_validator.py` | MODIFY | Radar-Alarm: `_INTENSITY_LABELS` (Z. 39–47), `_SEGMENT_RE` (Z. 65–68), Cooldown-Hinweis (Z. 140), `--eml` |
| `src/i18n/messages/de/{mail,vergleich,warnung,alarm}.json`, `src/i18n/messages/en/{mail,vergleich,warnung,alarm}.json` | MODIFY | nur die in der Tabelle unten genannten Schlüssel |
| `docs/reference/mail_validators.md` | MODIFY | Marker-Header-Tabelle (Z. 93–94, 121, 174, 178): `X-GZ-Lang`, Übergangsregel, `--eml` |
| `tests/helpers/mail_lang_fixture.py` | CREATE | `als_englisch(eml_bytes, schluessel)`: ersetzt die Katalogtexte de→en für Testzwecke |
| `tests/fixtures/mail/{compare,briefing_full,briefing_compact,official_alert,radar_alert}_de.eml` | CREATE | deutsche Gerüst-Fixtures aus dem echten Renderer-Pfad, mit Kopf `X-GZ-Lang: de` |
| `tests/unit/test_mail_lang_marker_header.py` | CREATE | Test zu AC-6 und AC-8 |
| `tests/unit/test_compare_mail_validator_sprache.py` | CREATE | Tests zu AC-1 bis AC-3 |
| `tests/unit/test_briefing_mail_validator_sprache.py` | CREATE | Test zu AC-4 |
| `tests/unit/test_alarm_mail_validatoren_sprache.py` | CREATE | Test zu AC-5 |

## Estimated Scope

- **LoC:** ca. 260 Code ohne Katalogdaten, Fixtures und Tests (`_mail_lang.py` ~55, `email.py` ~15, vier Validatoren je ~40–60). Das Workflow-Limit von 250 LoC wird berührt: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** ca. 22 (davon 5 Fixtures, 4 Tests, 8 Katalogdateien)
- **Effort:** high (Hard-Gate-Pfad)

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2662 P1 | Paket | `src/i18n` (`t`, `Lang`), Registerfelder `label_en`, `aggregation_label(agg, lang)` |
| `app.metric_catalog` (`get_metric`, `col_label`) | module | Spaltenköpfe der Stundentabelle bleiben Kurzform (`col_label`, unverändert) |
| `.claude/hooks/_validator_log.py`, `_e2e_paths.py` | module | YAML-Log und Pfade; das Log bekommt das Feld `warnings` |
| `output.channels.email.build_mime_message` | function | setzt die Kopfzeilen `X-GZ-Mail-Type`, `X-GZ-Format`, neu `X-GZ-Lang` |
| `docs/reference/mail_validators.md`, `docs/reference/gates_und_ratschen.md` | doc | Validator- und Gate-Referenz |
| Blockiert | Pakete | P2 (#2664), P3 (#2665), P4 (#2666), P5 (#2667), P6 (#2668) |
| ADR-0104 | adr | Marker `X-GZ-Lang`, Pflicht erst nach A2 |

## Implementation Details

**1. Kopfzeile.** `build_mime_message(..., lang: str | None = None)`: der Wert ist `"en"` nur bei `lang == "en"`, sonst `"de"`; der Kopf `X-GZ-Lang` wird in **beiden** Zweigen (HTML mit `MIMEMultipart("alternative")` und Klartext) neben `X-GZ-Mail-Type` gesetzt und gilt für **alle** Mail-Arten (`trip-briefing`, `compare`, `deviation-alert`, `official-alert`, `radar-alert`, Service-Mails). Der Wert ist ausdrücklich die **Sprache des Inhalts**, nicht eine Absicht: solange ein Renderer noch Deutsch ausgibt (bis P2 ff.), steht `de`. `EmailOutput.send(..., lang=None)` reicht den Wert durch (Z. 855–867). Die Aufrufer, die ihren Nutzer kennen (`notification_service`, `radar_alert_service`), übergeben `lang=resolve_user_lang(user_id)` in den jeweiligen Renderer-Paketen; PV selbst stellt keinen Aufrufer um.

**2. Hilfsmodul `.claude/hooks/_mail_lang.py`:**

```python
HEADER_PFLICHT = False          # A2 (#2681) stellt auf True; dann: Header fehlt -> Fehler (Exit 1)
def mail_lang(msg) -> tuple[str, list[str]]:
    """(lang, warnungen). Fehlt der Kopf: ("de", ["X-GZ-Lang fehlt ..."]) -- bei
    HEADER_PFLICHT stattdessen ValueError. Wert ausser de/en: ValueError."""
def erwartet(key: str, lang: str, **params) -> str:   # = i18n.t(key, lang, **params)
def marker(key: str, lang: str, trenner: str = " (") -> str:
    """Text eines Schlüssels bis vor den ersten Trenner, z. B. 'Nacht am Ziel'."""
```

Es fügt `src` relativ zur eigenen Datei in `sys.path` ein und importiert `from i18n import t`. Jeder Validator ruft `mail_lang(msg)` genau einmal; bei `ValueError` meldet er einen Fehler (Exit 1) mit dem Text „X-GZ-Lang unbekannt oder fehlt“. Warnungen gehen auf `stderr` (`WARNUNG: …`) und in das YAML-Log unter `warnings:` (`_write_validation_log(success, errors, warnings=None)`).

**3. Erwartungen aus dem Katalog (de = heutiges Literal wortgleich, en = Glossar).** PV legt **nur** diese Schlüssel an; die Renderer der Pakete P2–P6 müssen exakt dieselben Texte über dieselben Schlüssel ausgeben:

| Schlüssel | de | en | Verwender (Validator) |
|---|---|---|---|
| `vergleich.zeile.amtliche_warnungen` | Amtliche Warnungen | Official warnings | `_OVERVIEW_WARN_LABEL` (Z. 503) |
| `vergleich.stunden.zeit` | Zeit | Time | `_HOUR_COLUMNS_V2[0]` (Z. 575) |
| `mail.ausblick.spalte_tag` | Tag | Day | briefing Z. 205 |
| `mail.nacht.am_ziel` | Nacht am Ziel ({hoehe}m) | Night at destination ({hoehe}m) | briefing Z. 291, 547 (über `marker`) |
| `mail.pille.kein_regen` | kein Regen | no rain | briefing Z. 412 |
| `warnung.verdict.one` / `.other` | {count} amtliche Warnung / {count} amtliche Warnungen | {count} official warning / {count} official warnings | `_VERDICT_RE` (Z. 52) |
| `warnung.gueltig` | Gültig | Valid | Z. 86 (Validator hängt `:` an) |
| `warnung.quelle` | Quelle | Source | Z. 102, 315 |
| `warnung.abgerufen_bei` | abgerufen bei | retrieved from | Z. 315 |
| `warnung.stufe.gelb` / `.orange` / `.rot` | GELB / ORANGE / ROT | YELLOW / ORANGE / RED | Z. 60 |
| `warnung.lawine.stufe` | Lawinenstufe {n} ({wort}) | Avalanche level {n} ({wort}) | Z. 68 |
| `warnung.eaws.1` … `.5` | gering, mäßig, erheblich, groß, sehr groß | low, moderate, considerable, high, very high | `_EAWS_WORDS` (Z. 69) |
| `warnung.entwarnung.wort` | Entwarnung | All clear | Z. 184 |
| `warnung.entwarnung.uebergang` | Stufe {alt} → {neu} | Level {alt} → {neu} | Z. 160 |
| `warnung.entwarnung.beendet` | beendet | ended | Z. 160 |
| `warnung.gefahr.<hazard>` | Hitze, Gewitter, Kälte, Sturm, Starkregen, Schneefall, Glatteis, Zugang gesperrt, Waldbrand-Gefahr, Hochwasser/Erdrutsch | Heat, Thunderstorm, Cold, Storm, Heavy rain, Snowfall, Black ice, Access closed, Wildfire risk, Flood/landslide | `_OTHER_HAZARD_RE` (Z. 78) |
| `alarm.radar.intensitaet.leicht` / `.maessig` / `.stark` / `.hagel` / `.gewitter` / `.regen` | Leichter Regen, Mäßiger Regen, Starker Regen, Starker Hagel, Gewitter, Regen | Light rain, Moderate rain, Heavy rain, Heavy hail, Thunderstorm, Rain | `_INTENSITY_LABELS` (Z. 39–47) |
| `alarm.radar.cooldown_praefix` | höchstens einmal in | at most once in | Z. 140 |
| `alarm.segment.etappe` | Etappe {n} | Stage {n} | `_SEGMENT_RE` (Z. 65) |
| `alarm.segment.ziel` | Ziel | Destination | `_SEGMENT_RE` |

Die `<hazard>`-Kennungen sind die Schlüssel von `_HAZARD_LABELS` in `alert/official_alerts.py` (Z. 65–89) ohne `avalanche_bulletin` (`extreme_heat`, `thunderstorm`, `extreme_cold`, `wind_gust`, `rain`, `snow`, `black_ice`, `access_ban`, `wildfire_risk`, `flood`, dazu `avalanche` = Lawine / Avalanche). Kürzel (`Temp`, `Sun`, `Rain`, `Thdr` …) sind Spaltenköpfe aus `col_label` und bleiben in beiden Sprachen gleich; der Validator liest sie weiter aus dem Register, nicht aus dem Katalog.

**4. Überblickszeilen des Ortsvergleichs.** `_OVERVIEW_METRIC_CHECKS` (Z. 650–693) wird zu einer Funktion `overview_metric_checks(lang)`: Schlüssel = `get_metric(id).label(lang)` plus bei zwei Auswertungen ` ` + `aggregation_label(agg, lang)` (zum Beispiel `Temperatur Maximum` / `Temperature Maximum`), Wert = unveränderte Regex-Bereichs-Paare. Die Modulkonstanten `_OVERVIEW_METRIC_CHECKS`, `_OVERVIEW_WARN_LABEL`, `_OVERVIEW_NO_CHECK_LABELS` und `_HOUR_COLUMNS_V2` bleiben mit **deutschem** Wert bestehen (`= overview_metric_checks("de")` usw.), weil fünf Bestandstests sie importieren; sie müssen bytegleich zu heute sein (die Mengengleichung in `tests/unit/test_compare_mail_overview_plausibility_coverage.py` bleibt grün). `validate_structure`, `validate_plausibility` und `validate_hourly_table` bekommen `lang` als Schlüsselwort (Standard `"de"`).

**5. Beispiel-Umstellung (Briefing-Validator, Z. 547).**

```python
# vorher
night_marker = html.find("Nacht am Ziel")
# nachher
night_marker = html.find(marker("mail.nacht.am_ziel", lang))
```

Für `lang = "en"` ist der Marker `Night at destination`. Dieselbe Ersetzung an Z. 291 (`"Nacht am Ziel" in html[…]`). Die Stelle `_th_tokens(block)[0] != "Tag"` (Z. 205) wird zu `!= erwartet("mail.ausblick.spalte_tag", lang)`.

**6. Aufteilung und Datei-Modus.** `email_spec_validator.run_validation()` (Z. 1030–1064) holt die Mail wie bisher per IMAP und ruft danach neu `validate_message(msg, min_locations=3)`, das alle `validate_*`-Prüfungen enthält (Signatur und Verhalten von `run_validation` bleiben). Jeder der vier Validatoren bekommt `--eml PFAD`: die Mail wird aus der Datei gelesen statt per IMAP, Exit-Codes unverändert (0 bestanden, 1 Verletzung, 2 technischer Fehler). So sind die Fixtures ohne Netz prüfbar.

**7. Fixtures und Testhilfe.** `tests/fixtures/mail/*_de.eml` entstehen einmalig aus dem echten Renderer- und `build_mime_message`-Pfad (Vorbild: `tests/tdd/test_official_alert_mail_validator.py::_build_real_official_alert_message`, deterministische Daten, feste Zeit `2026-10-29T06:00+02:00`, Nutzer `golden-de`). Englische Dateien gibt es in PV **noch nicht**: `tests/helpers/mail_lang_fixture.py::als_englisch(eml_bytes, schluessel)` ersetzt in einer deutschen Fixture die Katalogtexte der Tabelle (de → en) und setzt den Kopf auf `en`. Die Pakete P2–P6 legen echte `*_en.eml` aus ihren Renderern daneben und stellen die betroffenen Tests auf diese um.

**8. Übergang.** Fehlt `X-GZ-Lang`: Sprache `de`, Warnung, Exit unverändert (0 bei sonst bestandener Mail). `HEADER_PFLICHT = True` schaltet A2 (#2681) mit einer einzigen Zeile.

## Expected Behavior

- **Input:** Eine zugestellte oder gespeicherte Mail (`--eml`) mit Kopf `X-GZ-Mail-Type`, `X-GZ-Format` (nur Trip) und `X-GZ-Lang`.
- **Output:** Exit 0 bei bestandener Prüfung in der Sprache des Kopfes, Exit 1 bei Verletzung oder bei Widerspruch zwischen Kopf und Inhalt, Exit 2 bei technischem Fehler. Eine Mail ohne Kopf wird als `de` geprüft und erzeugt eine Warnung.
- **Side effects:** Das YAML-Validator-Log bekommt `warnings`; die Mailkopfzeile `X-GZ-Lang` erscheint in jeder gesendeten Mail. Kein Versand, kein Eingriff in Nutzerdaten.

## Acceptance Criteria

- **AC-1:** Given eine Ortsvergleichs-Mail mit drei Orten, Kopf `X-GZ-Lang: en` und englischen Überschriften (Zeile „Official warnings“, Spalte „Time“, Überblickszeilen wie „Temperature Maximum“) / When `email_spec_validator.py --eml` läuft / Then ist der Exit-Code 0.
  - Test: `tests/unit/test_compare_mail_validator_sprache.py` — echte Fixture `compare_de.eml`, per `als_englisch` in die englische Fassung gebracht, Validator als Prozess gestartet.

- **AC-2:** Given dieselbe Ortsvergleichs-Mail mit englischem Inhalt, aber Kopf `X-GZ-Lang: de` (und umgekehrt deutscher Inhalt mit Kopf `en`) / When der Validator läuft / Then ist der Exit-Code 1 und die Meldung nennt den Widerspruch zwischen Sprache und Inhalt.
  - Test: `tests/unit/test_compare_mail_validator_sprache.py` — beide Richtungen, Prüfung von Exit-Code und Meldungstext.

- **AC-3:** Given eine deutsche Ortsvergleichs-Mail ohne Kopf `X-GZ-Lang` / When der Validator läuft / Then ist der Exit-Code 0, auf `stderr` und im YAML-Log steht eine Warnung über den fehlenden Kopf, und ein unbekannter Wert wie `fr` ergibt Exit 1.
  - Test: `tests/unit/test_compare_mail_validator_sprache.py` — Mail ohne Kopf und Mail mit Kopf `fr`; Log wird im temporären Log-Ordner gelesen.

- **AC-4:** Given eine Trip-Briefing-Mail im Format `full` und eine im Format `compact`, jeweils mit englischem Inhalt und Kopf `en` / When `briefing_mail_validator.py --eml` läuft / Then ist der Exit-Code 0 (Marker „Night at destination“ und „Day“ werden aus dem Katalog erwartet), und mit deutschem Kopf bei englischem Inhalt ist er 1.
  - Test: `tests/unit/test_briefing_mail_validator_sprache.py` — Fixtures `briefing_full_de.eml` und `briefing_compact_de.eml`, englische Fassung per `als_englisch`.

- **AC-5:** Given eine amtliche Warnmail und eine Radar-Alarm-Mail mit englischem Inhalt („2 official warnings“, „Valid:“, „Source:“, „retrieved from“ bzw. „Heavy rain“, „Stage 3“, „at most once in“) und Kopf `en` / When `official_alert_mail_validator.py --eml` bzw. `radar_alert_mail_validator.py --eml` läuft / Then ist der Exit-Code 0, und bei Kopf `de` mit demselben englischen Inhalt ist er 1.
  - Test: `tests/unit/test_alarm_mail_validatoren_sprache.py` — Fixtures `official_alert_de.eml` und `radar_alert_de.eml`, englische Fassung per `als_englisch`.

- **AC-6:** Given zwei Mails, nacheinander in demselben Prozess gebaut, die erste mit `lang="en"` für Nutzer A, die zweite ohne Angabe für Nutzer B / When die Kopfzeilen gelesen werden / Then trägt die erste `X-GZ-Lang: en`, die zweite `X-GZ-Lang: de`, ein Wert wie `fr` wird zu `de`, und das gilt für `trip-briefing`, `compare`, `deviation-alert`, `official-alert` und `radar-alert` im HTML- wie im Klartext-Zweig.
  - Test: `tests/unit/test_mail_lang_marker_header.py` — echter Aufruf von `build_mime_message` je Mail-Art, kein SMTP.

- **AC-7:** Given die deutschen Bestands-Fixtures und -Tests der vier Validatoren / When sie nach der Umstellung laufen / Then bleiben sie unverändert grün; die deutschen Modulkonstanten (`_OVERVIEW_METRIC_CHECKS`, `_OVERVIEW_WARN_LABEL`, `_HOUR_COLUMNS_V2`) sind wortgleich zu heute, und die Mengengleichung der Überblickszeilen gegen den Renderer hält.
  - Test: `tests/unit/test_compare_mail_overview_plausibility_coverage.py`, `tests/unit/test_compare_validator_single_name_form.py`, `tests/tdd/test_official_alert_mail_validator.py`, `tests/tdd/test_issue_733_briefing_mail_validator.py`, `tests/tdd/test_issue_830_radar_alert_validator.py` laufen unverändert grün (Golden `de`).

- **AC-8:** Given ein Validator-Lauf mit `HEADER_PFLICHT = True` (Schalter für A2) / When die Mail keinen Kopf trägt / Then ist der Exit-Code 1; mit dem Standard `False` bleibt es bei der Warnung.
  - Test: `tests/unit/test_mail_lang_marker_header.py` — `mail_lang()` mit gesetztem und ungesetztem Schalter (Schalter wird im Test über das Modulattribut gesetzt und zurückgesetzt).

## Known Limitations

- Annahme: Die Aufrufer in `notification_service.py` und `radar_alert_service.py` werden erst in den Renderer-Paketen (P2–P6, P9a/P9b) auf `lang=resolve_user_lang(user_id)` umgestellt; bis dahin trägt jede Mail wahrheitsgemäß `X-GZ-Lang: de`.
- Annahme: Die englischen Gerüst-Fixtures entstehen in PV nur im Speicher (`als_englisch`); echte englische Renderer-Mails kommen mit P2–P6 und ersetzen diese Prüfung.
- Annahme: Die Warnstufen-Wörter bleiben auf die drei Farbwörter GELB/ORANGE/ROT (in der Sprache der Mail) beschränkt; das vierte Wort GRÜN prüft der Validator wie heute nicht.
- Die Schlüsselwerte der Tabelle sind jetzt verbindlich: ändert ein Renderer-Paket einen dieser Texte, ändert es den Katalogeintrag und damit zugleich die Validator-Erwartung (das ist die gewollte Kopplung).
- `deviation-alert`-Mails haben weiterhin keinen eigenen Validator; der Briefing-Validator weist sie als „falscher Validator“ ab (#1282).
- Die Spaltenköpfe der Stundentabelle bleiben die Kurzformen aus `col_label` (ADR-0042 Klasse 1) und werden nicht übersetzt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Der Marker `X-GZ-Lang` macht die Sprache einer Mail maschinenlesbar und koppelt Validator und Renderer über denselben Katalogschlüssel; Pflicht wird er erst nach A2, damit der Übergang keinen Deploy blockiert.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
