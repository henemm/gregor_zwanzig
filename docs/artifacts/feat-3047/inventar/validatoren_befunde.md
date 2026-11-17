# Bereich validatoren — Befunde (Runde 7, #3047)

Stand: Worktree auf `6ddf4a1` (main nach #3084). Alle Läufe ohne Netz, Mails über den echten Weg
(Trip: Loader → `NotificationService.send_trip_report` mit Ausblick aus `build_outlook_row`, Naht nur am
Transport; Orte: `send_one_compare_preset` mit Wetter-Naht `build_result`), dann `build_mime_message`,
beide Validatoren als Prozess mit `--eml --konfig` (Hook-Kopie, Log in tmp).

Skripte (alle unter `/tmp/claude-0/-home-user-gregor-zwanzig/8fd24bbd-2477-52fc-adc3-e2681826a5f8/scratchpad/inventar/validatoren/`):
`vh.py` (Kettenhelfer), `test_sweep.py` (38 Konfigurationen: T01–T23 Trip, O01–O15 Orte, je positiv + Verfälschungen),
`test_extra.py` (E01–E15 gezielte Fälle), `mutationen.py` (V01–V20 Mutationen der Validatoren),
`ergebnisse.jsonl` / `mutationen.jsonl` (Rohdaten), `mails/` (alle erzeugten und verfälschten Mails).

Aufruf (aus dem Worktree):
```
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers uv run pytest -p tests.conftest --rootdir=. -c pyproject.toml \
  <scratchpad>/inventar/validatoren/test_sweep.py -q -p no:warnings          # bzw. test_extra.py, -k <cfg>
uv run python <scratchpad>/inventar/validatoren/mutationen.py [V01 ...]
```
(Vorbedingung: Symlink `/opt/pw-browsers/chromium_headless_shell-1200 -> -1243`.)

## Ergebnis Sweep

38 Konfigurationen (Folgen ≠ Katalog, Roh/Einfach gemischt, nie eingestellt, bewusst leer, Totalschnitt,
Altbestand Fall A, Grundauswahl = Register-Vorgabe, Bucket secondary, per-Report-Liste, DE/EN, Morgen/Abend
mit und ohne Ausblick, Kompakt, Zusatzblöcke an/aus, Ausblick an/aus/[]/nie, Stundenverlauf an/aus/nie,
Nacht aus, Etappen- und Ortsnamen mit `& ' < >`/Umlauten/Überlänge, zwei Orte umgekehrt, Tagesfenster).
274 Validator-Läufe.

- Positiv: 37/38 Exit 0. Einzige Ablehnung T22 ist **richtig** (Produktfehler B-P2, Validator meldet ihn).
  Keine Fehlablehnung über den echten Weg; eine Fehlablehnung bei Tagesfenster (B-V5, abgeleitete Mail).
- Gefangen (Exit ≠ 0, Meldung mit Spaltenname): Spalte vertauscht HTML/Klartext (38/38 Trip, 13/13 Orte-Stunden), Spalte/Zeile zu viel
  (31/31), Vergleichszeile fehlt/zu viel (25/25), Ort fehlt (27/27), Ortsfolge mit Sonderzeichen (E14),
  Ausblick-Klartext fehlt (15/15), Ausblick/Stunden/Nacht trotz aus (6/6), Roh/Einfach in Trip-Stunden,
  Trip-Ausblick, Kompakt-Ausblick, Orte-Ausblick (E01, E02, E04, E13), Windrichtung fehlt (E03),
  Metrik trotz Morgen-Flag aus (E09).
- Blindstellen (Exit 0 trotz Verfälschung): siehe B-V1 bis B-V4.

## Befunde

### B-V1 — Ausblick: Zahl der Tageszeilen und Ausblick je Ort ungeprüft (bekannt #3083 H3, gegen den Auftrag echte Lücke)
- **Schwere:** mittel (Validator gilt als Soll-Prüfung „jede Einstellung“; ein fehlender Tag oder ein fehlender
  Orts-Ausblick ist für den Wanderer eine fehlende Antwort).
- **Soll:** Spec `feat_3047_einstellung_gleich_mail_pruefkatalog.md` §6 („Ausblick … im HTML-Teil und im
  Klartext-Teil“), AC-19; Konzept `einstellungen_neu.md` §5 Punkt 8 Ausblick „Kompakte Tageswerte der
  nächsten drei {Etappen|Tage}“.
- **Ist:** Eine fehlende Tageszeile besteht in **allen 27** Konfigurationen mit Ausblick (Trip HTML+Klartext 15/15,
  Trip-Kompakt 3/3, Orte 12/12). Orte-HTML: fehlt die ganze Ausblick-Tabelle eines Orts, besteht die Mail
  (12/12). Der Orte-Klartext prüft den Block je Ort (`_soll_ortsabschnitte`), die Zeilenzahl nicht.
- **Repro:** `test_sweep.py` Arten `ausblick_zeile_fehlt`, `kompakt_ausblick_zeile_fehlt`,
  `ausblick_eines_orts_fehlt_html` (Belegmails `mails/MUT_O01_de_folge_*`).
- **Dateien:** `.claude/hooks/briefing_mail_validator.py:760-771` (`_soll_tabellen` vergleicht nur Köpfe),
  `:788-804` (`_soll_kompakt`), `.claude/hooks/email_spec_validator.py:1290-1304` (`_soll_teil`), `:1307-1340`.
- **Fix:** Zeilenzahl je Ausblick-Tabelle/-Block gleich in HTML, Klartext und je Ort; Soll 3 (Horizont), außer die
  Mail trägt den Horizont-/„nicht abrufbar“-Hinweis (`outlook_state`, `vergleich.ausblick`-Hinweistext); Orte-HTML:
  Zahl Ausblick-Abschnitte = Zahl Orts-Abschnitte (Hinweisblock zählt).
- **Einordnung:** innerhalb Spec/Konzept.

### B-V2 — Zusatzblöcke Etappen-Kennzahlen und Vortag-Vergleich nie geprüft (bekannt #3083 H2, gegen den Auftrag echte Lücke)
- **Schwere:** mittel.
- **Soll:** Spec §6: `_soll_aus_konfiguration` leitet „… Ein/Aus, Ortsreihenfolge, **Zusatzblöcke**“ ab;
  Konzept §3.2 W17/W18, §5 Punkt 8 „Zusatzblöcke“.
- **Ist:** `trip_soll` berechnet `zusatz` (`_soll_aus_konfiguration.py:379`), kein Validator liest es.
  T10 (Vollformat) und T21 (Kompakt): Mail mit Kennzahlen „12.3 km | ↑800m …“ und „Vergleich zum Vortag“
  gegen Konfiguration mit beiden Schaltern aus → Exit 0.
- **Repro:** `test_sweep.py -k "T10 or T21"`, Art `zusatzblock_trotz_aus`.
- **Dateien:** `.claude/hooks/_soll_aus_konfiguration.py:379`, `.claude/hooks/briefing_mail_validator.py:984-1012`.
- **Fix:** in `pruefe_soll` (Voll und Kompakt) bei Schalter aus: Kennzahlen-Zeile (HTML-Kacheln km/↑/↓,
  Klartext „km | ↑“, Kompakt „km | +“) und Vortag-Zeile (`mail.vortag`-Text) dürfen nicht erscheinen;
  „an“ nur weich (datenabhängig).
- **Einordnung:** innerhalb Spec.

### B-V3 — Orte-Vergleichstabelle: Roh/Einfach je Zeile ungeprüft (neu)
- **Schwere:** mittel.
- **Soll:** Spec §2 Punkt 3 / §6 „Darstellung je Liste“; Konzept §3.2 W11 (Roh/Einfach in jeder Liste,
  ausdrücklich Vergleichstabelle).
- **Ist:** `uebersicht_einfach` lockert nur die FORMAT-Prüfung (`validate_format(einfach=…)`), die Form wird
  nicht gefordert. E10 (Böen Einfach, HTML zeigt „48 km/h“ statt Ampelpunkt), E11 (Niederschlag Einfach,
  Klartext „8.4 mm“ statt „mäßig“) und E12 (Wind Roh, Klartext „stark“ statt „26 km/h“) → alle Exit 0.
- **Repro:** `test_extra.py -k "E10 or E11 or E12"` (Mails `mails/E1[0-2]_*.eml`).
- **Dateien:** `.claude/hooks/email_spec_validator.py:1045` (`validate_format`), `:1307-1340` (`pruefe_soll`
  ohne Darstellungsprüfung der Übersicht), `.claude/hooks/_soll_aus_konfiguration.py:446-466`.
- **Fix:** `darstellung_meldungen("Vergleichstabelle", …)` über die Übersichtszeilen (HTML roh mit Ampelpunkt,
  Klartext `Label: Wert`), Formen aus `_orte_einfach` (Einfach → WORT/AMPEL, sonst ZAHL; Temperatur/Gewitter
  wie Trip-Ausnahmen).
- **Einordnung:** innerhalb Spec.

### B-V4 — Orte-Klartext-Stundenverlauf: nur erste Stundenzeile je Ort gelesen (bekannt #3083 H3)
- **Schwere:** niedrig–mittel.
- **Soll:** Spec §6 „Spalten des Stundenverlaufs … im Klartext-Teil“.
- **Ist:** Fehlt eine Spalte ab der zweiten Stundenzeile (09:00 …), besteht die Mail in 13/13 Konfigurationen.
- **Repro:** `test_sweep.py`, Art `stunden_klartext_spalte_fehlt_ab_zeile2`.
- **Dateien:** `.claude/hooks/email_spec_validator.py:1189-1191` (`not _STUNDE_RE.match(zeilen[i - 1])`).
- **Fix:** jede Stundenzeile gegen das Soll vergleichen (erste Abweichung je Ort melden).
- **Einordnung:** innerhalb Spec.

### B-V5 — Tagesfenster: Orte-Validator lehnt korrektes Fenster ab, Trip-Validator prüft es nicht (neu)
- **Schwere:** mittel (Fehlablehnung blockiert das E2E-Gate für jeden Nutzer mit Fenster ohne 09–11 Uhr).
- **Soll:** Konzept §5 Punkt 9 (W12 Tagesfenster, ADR-0035), Feld `day_window_start_hour/end_hour` (Trip und
  Orte, `models.py:447`, `:1393`); Spec §6 Soll aus der Konfiguration.
- **Ist:** `validate_hourly_table(body, time_start=9, time_end=16)` wird ohne Fenster aufgerufen
  (`email_spec_validator.py:1082`, Aufruf in `validate_message`), auch mit `--konfig`. Eine Mail mit Fenster
  12–16 Uhr (aus O01 durch Entfernen der Stunden 08–11 gebildet; die Wetter-Naht liefert ein festes Fenster)
  scheitert mit „fehlende Stunden: 09, 10, 11“ für jeden Ort. Trip: `briefing_mail_validator.py` kennt
  `day_window` gar nicht (Stunden nie gegen das Fenster geprüft).
- **Repro:** `test_extra.py -k tagesfenster` (Mail `mails/E15_tagesfenster_12_16.eml`).
- **Fix:** mit `--konfig` das Fenster aus `day_window_*` (Vorgabe 4/19 über die dokumentierte Regel, nicht
  `resolve_*` des Produkts) ableiten; Orte: erwartete Stunden = Fenster ∩ Vergleichszeitraum; Trip: Stunden der
  Etappentabelle im Fenster.
- **Einordnung:** innerhalb Konzept; die Spec #3047 nennt das Tagesfenster nicht (Erweiterung des Solls).

### B-V6 — Kanal-Parität der Prüfwerkzeuge: kein Soll-Validator für Telegram, SMS, Premium-SMS (neu)
- **Schwere:** mittel.
- **Soll:** ADR-0095 (jeder Kanal jede Frage, gleicher Inhalt), CLAUDE.md „alle vier Kanäle gleichrangig“;
  Konzept §5 Punkt 8 (eigene Listen je Kanal mit Reihenfolge und Roh/Einfach).
- **Ist:** `docs/reference/mail_validators.md` führt nur Mail-Validatoren; `.claude/commands/e2e-verify.md:239-241`:
  „Nicht abgedeckt: SMS, Premium-SMS und Telegram“; `.claude/hooks/e2e_telegram_live.py` prüft nur, ob die
  Test-Chat-Kennung gesetzt ist. Für `channel_layouts.telegram/sms/premium_sms` (Auswahl, Folge, Roh/Einfach,
  Schnittlinie 7 bzw. 160 Zeichen) gibt es kein `--konfig`-Gegenstück; die Staging-Schicht prüft diese Kanäle
  nie gegen die Einstellung.
- **Fix:** `_soll_aus_konfiguration` um Kanal-Listen erweitern und einen Prüfer für Telegram-Text und
  SMS-/Premium-Token-Zeile (Datei-Modus wie `--eml`, Quelle Transport-Mitschrift bzw. Staging-Vorschau) bauen.
- **Einordnung:** außerhalb Spec #3047 (nur E-Mail), innerhalb ADR-0095/Konzept → eigenes Issue.

### B-V7 — Ortsfolge der HTML-Abschnitte hängt am deutschen Wort „ORT“ (latent, Code-Lesung)
- **Schwere:** niedrig.
- **Ist:** `_ORT_KOPF_RE = r'>ORT</span>…'` (`email_spec_validator.py:1120`); das Soll wird auf gefundene
  Abschnitte gefiltert (`[n for n in soll["orte"] if n in sektionen]`, `:1333-1334`). Wird „ORT“ in der EN-Mail
  übersetzt (#3074), findet der Ausdruck nichts und die Prüfung wird still leer. Heute fangen die übrigen
  Ortsfolge-Prüfungen (Tabellenkopf, Klartext) dieselbe Vertauschung (E14).
- **Fix:** Etikett aus dem Katalog (`t(..., lang)`), leere Abschnittsliste bei erwarteten Orten als Fehler.
- **Einordnung:** innerhalb Spec; mit #3074 zusammen erledigen.

### B-V8 — Testlücke: Sortierung der E-Mail-Kanal-Liste nach `bucket`/`order` ungetestet (neu)
- **Schwere:** niedrig (Validator-Verhalten heute korrekt).
- **Soll:** CLAUDE.md Adversary-Pflicht (jede Verfälschung muss ein Test fangen); `_soll_aus_konfiguration.py`
  Docstring „sortiert nach bucket dann order (#1575)“.
- **Ist:** Mutation V03 (`_trip_email_liste` gibt die Kanal-Liste unsortiert zurück) überlebt
  `tests/tdd/test_einstellung_gleich_mail_validatoren.py` vollständig, weil dort jede `channel_layouts.email`
  in Array-Folge = `order` steht. Eigener Fall T23 (Array Wind, Regen, Temp; `order` Regen, Temp, Wind) fängt sie:
  die Mail folgt `order`, das mutierte Soll der Array-Folge → Exit 1.
- **Repro:** `python3 <scratchpad>/inventar/validatoren/eigene_gegenprobe.py V03_trip_liste_unsortiert "T23 or T15"`.
- **Fix:** T23 als Fall in die Validator-Testdatei übernehmen (ebenso für H1: T03/E09, siehe unten).
- **Einordnung:** innerhalb Spec (AC-14/M11-Geist).

### Produktbefunde, über den echten Weg gefunden (nicht Validator, zur Weitergabe an Bereich Trip-Mail/Kompakt)

#### B-P1 — Kompakt-Mail zeigt Etappen-Kennzahlen trotz `show_stage_stats = false`
- **Schwere:** mittel. **Soll:** Konzept §3.2 W17, §5 Punkt 8 Zusatzblöcke (gilt für die ganze E-Mail).
- **Ist:** T21: „12.3 km | +800m | -400m“ im Kompaktformat bei Schalter aus. Vollformat korrekt (T10).
- **Dateien:** `src/output/renderers/email/__init__.py:113-134` (reicht `stage_stats`, aber kein `show_stage_stats`
  an `render_compact`), `src/output/renderers/email/compact.py:179-188`.
- **Fix:** `stage_stats if show_stage_stats else None` an `render_compact` übergeben (oder Parameter ergänzen).
- **Repro:** `test_sweep.py -k T21` → `mails/T21_kompakt_zusatz_aus.plain` Zeile 5.

#### B-P2 — Kompakt-Mail zeigt 3-Tages-Ausblick trotz `show_outlook = false`
- **Schwere:** mittel. **Soll:** `MailInhaltCard.svelte` Schalter „Ausblick“, `report_config.show_outlook`;
  HTML/Klartext gaten ihn (`html.py:1187`, `plain.py:353`).
- **Ist:** T22: Kompakt-Mail trägt „Naechste Etappen“; der Validator meldet richtig „SOLL: Ausblick (Kompakt)
  erscheint, obwohl er laut Konfiguration aus ist“. Der Scheduler gated nur nach `multi_day_trend_reports`
  (`trip_report_scheduler.py:1852`), der echte Versand ist also betroffen.
- **Dateien:** `src/output/renderers/email/__init__.py:113-134` (`show_outlook` fehlt im Kompaktzweig),
  `src/output/renderers/email/compact.py`.
- **Fix:** `show_outlook` an `render_compact` durchreichen und den Ausblick-Block daran gaten.
- **Repro:** `test_sweep.py -k T22`.

## Bekannte Punkte neu eingestuft (#3083)
- **H1** (Morgen-Bericht/Flags je Metrik ungetestet): Validator-Verhalten korrekt (E08 Exit 0, E09 Exit 1 mit
  „Spalte zu viel: 'Gust'“), Testlücke in `test_einstellung_gleich_mail_validatoren.py` bestätigt (Mutationen V01,
  V02 überleben dort, siehe unten) → bleibt ausgelagert #3083.
- **H2** → B-V2 (echte Lücke gegen den Auftrag).
- **H3** → B-V1 (Zeilenzahl, Ausblick je Ort) und B-V4 (Klartext-Stunden nur Zeile 1).

## Mutationen der Validatoren (gegen `tests/tdd/test_einstellung_gleich_mail_validatoren.py`)

| ID | Datei | Ersetzung (alt → neu, gekürzt) | Repo-Validatortests | gefangen von | eigene Inventur-Tests |
|---|---|---|---|---|---|
| V01_flags_je_bericht_ignoriert | `_soll_aus_konfiguration.py` | `eigen = eintrag.get(f"{report}_enabled")` → `eigen = None` | **nein (überlebt)** | – | ja: T03_morgen_flag_je_metrik:positiv |
| V02_soll_report_immer_abend | `briefing_mail_validator.py` | `return soll["je_report"][_REPORT_ART[report.group(1).lower()] if repor` → `return soll["je_report"]["evening"]` | **nein (überlebt)** | – | ja: T03_morgen_flag_je_metrik:positiv |
| V03_trip_liste_unsortiert | `_soll_aus_konfiguration.py` | `return _sortiert(geschnitten)` → `return geschnitten` | **nein (überlebt)** | – | ja: T23_kanal_array_ungleich_order:positiv |
| V04_ausblick_leerer_schnitt_kein_rueckfall | `_soll_aus_konfiguration.py` | `return [m for m in kennungen if m in grundauswahl] or list(grundauswah` → `return [m for m in kennungen if m in grundauswahl]` | ja | test_trip_ausblick_totalschnitt_volle_grundauswahl[full] | – |
| V05_wind_nie_verschmolzen | `_soll_aus_konfiguration.py` | `return any(e["metric_id"] == "wind" for e in liste) and any(` → `return False and any(e["metric_id"] == "wind" for e in liste) and any(` | ja | test_trip_windrichtung_verschmolzen_roh_positiv_und_ohne_richtung_scheitert | – |
| V06_nachtblock_aus_ungeprueft | `briefing_mail_validator.py` | `if nacht and not s["nacht"]:` → `if False:` | ja | test_trip_nachttabelle_trotz_show_night_block_aus_scheitert | – |
| V07_orte_layout_enabled_ignoriert | `_soll_aus_konfiguration.py` | `if e.get("enabled") is not False:⏎            paare +=` → `if True:⏎            paare +=` | ja | test_orte_channel_layouts_vor_channel_active_metrics | – |
| V08_orte_ortsabschnitte_aus | `email_spec_validator.py` | `if not (soll["stunden_an"] or soll["ausblick_an"]):⏎        return []` → `return []` | ja | test_orte_einzelner_ortsblock_fehlt_im_klartext_scheitert[stunden] | ja: O01_de_folge:stunden_klartext_spalte_fehlt_ab_zeile2, O01_de_folge:ausblick_eines_orts_fehlt_html, O10_zwei_orte_umgekehrt:stunden_klartext_spalte_fehlt_ab_zeile2, O10_zwei_orte_umgekehrt:ausblick_eines_orts_fehlt_html |
| V09_orte_ausblick_darstellung_aus | `email_spec_validator.py` | `if not soll.get("ausblick_an") or not formen:⏎        return []` → `return []` | ja | test_orte_ausblick_roh_einfach[de] | ja: O11_ausblick_einfach:E13_ausblick_roh_statt_einfach |
| V10_abweichung_ohne_reihenfolge | `_soll_aus_konfiguration.py` | `if ist == soll:⏎        return None` → `if sorted(ist) == sorted(soll):⏎        return None` | ja | test_trip_spalten_vertauscht_scheitert_mit_name | – |
| V11_ueberblick_ungeprueft | `briefing_mail_validator.py` | `titel = _ml().erwartet("mail.pille.ueberschrift", lang)⏎    fehler = [` → `return []⏎    titel = _ml().erwartet("mail.pille.ueberschrift", lang)⏎` | Lauf abgebrochen | – | – |
| V12_kompakt_darstellung_aus | `briefing_mail_validator.py` | `return fehler + [m.replace("(Klartext)", "(Kompakt)") for m in _darste` → `return fehler⏎    return fehler + [m.replace("(Klartext)", "(Kompakt)"` | Lauf abgebrochen | – | – |
| V13_verwaist_aus | `briefing_mail_validator.py` | `fehler += _verwaist_html(html, lang) + _verwaist_klartext(plain, lang)` → `` | ja | test_trip_verwaiste_ueberschrift_scheitert | – |
| V16_orte_stunden_nie_vorgabe | `_soll_aus_konfiguration.py` | `ids = [] if grund == [] else (basis if eigen else list(HOURLY_DEFAULT_` → `ids = [] if grund == [] else list(HOURLY_DEFAULT_METRIC_IDS)` | ja | test_orte_stunden_nie_eingestellt_folgt_grundauswahl | – |
| V19_trip_multi_day_trend_ignoriert | `_soll_aus_konfiguration.py` | `and report in (trend_reports or []),` → `,` | Lauf abgebrochen | – | – |


Zusammenfassung: 12 Mutationen vollständig gelaufen, 9 gefangen, **3 überleben** die Repo-Validatortests
(V01, V02 = bekannt #3083 H1; V03 = neu, B-V8). Alle drei fängt die eigene Inventur (T03 bzw. T23, Skript
`eigene_gegenprobe.py`, Arbeitskopie `kopie4`). V11, V12, V19 wurden durch Abbruch beendet (Signal, kein Fang),
V14, V15, V17, V18, V20 nicht mehr gelaufen (Rechner stark ausgelastet durch parallele Sitzungen); die betroffenen
Matrixzellen sind deshalb `ungeprueft` statt `gruen`. Läufe V04 ff. in Arbeitskopien des Worktrees (`kopie1-3`,
nur `src`, `tests`, `api`, `data`, `.claude/hooks`), V01–V03 im Worktree selbst.

Nach jeder Mutation Datei aus `sicherung*/` zurückkopiert; im Worktree `git diff --stat` leer geprüft (Skript-assert und am Ende von Hand).
