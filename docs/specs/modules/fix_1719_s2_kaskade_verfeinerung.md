---
entity_id: fix_1719_s2_kaskade_verfeinerung
type: bugfix
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [metrics, cascade, adr-0050, issue-1719, telegram]
---

<!-- Issue #1719, Scheibe 2 -- Backend-Verfeinerungsfilter. Baut auf Scheibe 1
     (ADR-0050 + Pruefstand, docs/specs/modules/fix_1719_s1_kaskade_pruefstand.md)
     auf: der dort gebaute AC-7-Test (xfail(strict=True)) wird mit dieser
     Scheibe gruen, seine Markierung entfaellt. Grundlage:
     docs/context/fix-1719-s2-kaskade-verfeinerung.md (gemessen 2026-08-11,
     Basis-Commit 32b781ed = Merge PR #1735). S3 (Frontend), S4 (Legende) sind
     eigene, spaetere Scheiben. -->

# Metrik-Kaskade: die Kanal-Ebene schneidet die Grundauswahl, statt sie zu ersetzen (#1719 Scheibe 2)

## Approval

- [ ] Approved

## Purpose

ADR-0050 (Scheibe 1) legt fest: die globale Metrik-Auswahl ist das Maximum,
eine Kanal-Ebene darf nur abwählen, nie hinzufügen. Der heutige Code hält das
nicht ein — `UnifiedWeatherDisplayConfig.get_metrics_for_channel()`
(`src/app/models.py:825-863`) **ersetzt** die Grundauswahl vollständig, sobald
eine Kanal-Ebene existiert, statt sie zu begrenzen. Der in Scheibe 1 gebaute
Prüfstand `tests/tdd/test_channel_metric_matrix.py::test_kaskade_ac7_sms_channel_must_not_add_globally_disabled_metric`
belegt das reproduzierbar rot (`xfail(strict=True)`). Diese Scheibe baut den
Lesepfad auf die Verfeinerungs-Semantik um: ein Maximum-Schnitt in
`get_metrics_for_channel()` (D1/D2/D3/D4) sowie die Behebung eines zweiten,
bereits heute scharfen Fehlers (K2 aus dem Kontext-Dokument) — Telegram folgt
ohne eigene Kanal-Ebene der **kollabierten E-Mail-Auswahl** statt der
Grundauswahl, weil `trip_report.py` eine bereits auf E-Mail reduzierte
`dc`-Instanz an den Telegram-Renderer durchreicht. Kein Frontend, keine
Datenmigration (D6, begründet).

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/app/`,
> `src/output/renderers/`) + Testcode. Kein Frontend, keine Go-Beteiligung —
> `channel_layouts` wird dort nur als opaker JSON-Schlüssel durchgereicht
> (Kontext-Dokument Abschnitt 3, „Go").

- **File:** `src/app/models.py` — `UnifiedWeatherDisplayConfig.get_metrics_for_channel()`
  (Z. 825-863), `_cascade_source_for_channel()` (Z. 712-734, **unverändert**),
  `_filter_metrics_by_report_type()` (Z. 670-703, **unverändert** — wird
  aufgerufen, nicht erweitert, s. D1)
- **File:** `src/output/renderers/trip_report.py` — `TripReportFormatter.format_email()`,
  Kollabierungsschritt (Z. 122-138), `_dc_uncollapsed` (Z. 132),
  `seg_tables`-Bau (Z. 146), `render_telegram_bubbles`-Aufruf (Z. 256-276,
  insb. `dc=dc` Z. 260 und `seg_tables=seg_tables` Z. 259)
- **File:** `src/app/loader.py` — `_parse_display_config()`, Docstring des
  `channel_layouts`-Parse-Zweigs (Z. 836-841)
- **Identifier:** `app.models.UnifiedWeatherDisplayConfig.get_metrics_for_channel()`,
  `output.renderers.trip_report.TripReportFormatter.format_email()`,
  `output.renderers.narrow.render_telegram_bubbles()`,
  `output.renderers.channel_layout.render_for_channel()`

## Estimated Scope

- **LoC:** ~+170/-25 (Limit 250) — 3 Produktivcode-Dateien + Docstring-Korrekturen,
  4 Python-Testdateien (1 neuer Abschnitt + 4 Fixture-Reparaturen) und 1 neuer
  Playwright-Klickpfad inkl. Staging-Setup (~60 Zeilen nach Bestandsmuster).
- **Files:** 8 (3 Produktivcode, 5 Tests davon 1 Browser-Klickpfad) — siehe
  Affected Files.
- **Deploy-Folge:** Durch den Klickpfad gegen Staging ist der Scope **nicht**
  `docs-only`; die Auslieferung durchläuft die volle Staging-Verifikation.
- **Effort:** medium-high. Der Schnitt selbst ist klein; das Risiko liegt in
  der Wechselwirkung mit der E-Mail-Kollabierung (Kontext-Dokument, Risiko 1)
  — Produktivpfad aller vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/fix-1719-s2-kaskade-verfeinerung.md` | GRUNDLAGE (gemessen) | Alle Zahlen/Belegstellen dieser Spec sind daraus übernommen, nicht neu recherchiert |
| `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` | ZUSAGE | Regeln 1-5, gegen die diese Scheibe umsetzt (Regel 4 bleibt S3) |
| `docs/specs/modules/fix_1719_s1_kaskade_pruefstand.md` | VORGÄNGER | Prüfstand, Basis-Fixture, Test-Helfer (`_load_cascade_dc`, `_cascade_sms_variant`, `_kaskade_mail_headers`, `_kaskade_telegram_cells`, `_kaskade_sms_text`, `_kaskade_report`) |
| `tests/tdd/test_channel_metric_matrix.py` | WIRD ERWEITERT | `xfail(strict=True)` bei AC-7 entfällt; neuer, eigener Abschnitt mit den ACs dieser Scheibe |
| `tests/fixtures/metric_cascade/khw_display_config_widerspruch.json` | WIRD WIEDERVERWENDET | Basis-Fixture; neue Ein-/Mehrfeld-Varianten (u. a. `channel_layouts.email`/`.telegram`, `per_report_layouts`) nach dem in Scheibe 1 etablierten Muster |
| `docs/reference/metric_output_matrix.md` | REFERENZ | Ausgabeorte je Metrik (#1514) |
| `tests/tdd/test_issue_429_channel_layouts.py`, `test_issue_434_per_report_layouts.py`, `tests/integration/test_issue_448_validator_metrics_for_channel.py` | WIRD REPARIERT | Fünf bekannt rot werdende Bestandstests, s. eigener Abschnitt unten |
| `frontend/e2e/metrik-grundauswahl-schneidet-kanal.staging.spec.ts` (+ Staging-Setup/Config nach Bestandsmuster) | NEU | **Pflicht-Klickpfad zu AC-10** (PO-Leitplanke #1719): die Editor-Sequenz wird geklickt, nicht konstruiert. Einzige Frontend-Datei dieser Scheibe — sie ändert das Frontend nicht, sie bedient es |

## Implementation Details

**D1 — Ort des Schnitts:** in `get_metrics_for_channel()`
(`models.py:825-863`), **nicht** im geteilten `_filter_metrics_by_report_type()`
(Z. 670-703). Letzteres wird mit drei verschiedenen Listen aufgerufen,
darunter `self.metrics` selbst — ein Maximum-Parameter wäre an einer von drei
Aufrufstellen unbenutzt und vermischte zwei Zuständigkeiten (Report-Typ-Filter
vs. Kaskaden-Schnitt). Der Schnitt betrifft **ausschließlich** die Zweige
`source == "per_report"` und `source == "per_channel"` — der `source ==
"global"`-Zweig (Z. 862-863, `_sorted_by_layout(self.get_metrics_for_report_type(report_type))`)
bleibt unverändert, weil er selbst bereits das Maximum ist. Diese Abgrenzung
ist zugleich die Absicherung gegen einen Fix, der versehentlich zu breit
schneidet und dadurch Kanäle ohne eigene Ebene (E-Mail/Telegram bei einer
reinen SMS-Kanal-Fixture) verändert (s. AC-2).

**D2 — Schnittmenge:** gegen die **IDs** aus
`self.get_metrics_for_report_type(report_type)` (Z. 814-823, ruft
`_filter_metrics_by_report_type(self.metrics, report_type)` auf), nicht gegen
rohe `enabled`-Flags. Nur so wirkt ADR-0050 Regel 3 auch für
`morning_enabled`/`evening_enabled` (s. AC-9), und die abgeleiteten
Nachtgrößen (`temperature_night`/`wind_chill_night`, `loader.py:803-834`, dort
nur an `self.metrics` angehängt) sowie das `selectable`-Gate (#1585,
`_is_selectable()`, Z. 646-667) bleiben korrekt berücksichtigt, weil sie
bereits Teil der Menge sind, gegen die geschnitten wird.

**D3 — beide Kanal-Ebenen gegen dieselbe globale Menge, NICHT verkettet:**
`per_report_layouts[report_type][channel]` wird gegen die globale Menge
geschnitten, nicht zusätzlich gegen `per_channel_layouts[channel]`. ADR-0050
Regel 1 nennt ausdrücklich die Grundauswahl als Maximum, keine
Zwischenebene — eine Verkettung würde einen Report-Typ-Override fälschlich auf
das einschränken, was der allgemeine Kanal-Layer zufällig enthält (s. AC-8).

**D4 — leere Grundauswahl:** `if not self.metrics:` → nicht schneiden, Kanal-
Ebene bleibt vollständig erhalten. Die Prüfung sitzt direkt in
`get_metrics_for_channel()` (Prüfort = Wirkort), **nicht** als Wiederverwendung
von `_trip_metrics_altbestand` (`trip_report.py:128`, das lebt in einer
anderen Datei und misst denselben Sachverhalt zu einem anderen Zeitpunkt für
einen anderen Zweck). Begründung: `loader.py:758` macht aus einem fehlenden
`metrics`-Feld `[]`; ein Maximum-Filter, der `[]` als „nichts erlaubt" liest,
würde Altbestands-Trips und den inerten Compare-Sonderfall (Kontext-Dokument
Abschnitt 1) auf null Metriken schneiden — Totalausfall statt Bugfix (s. AC-7).

**D5 — Telegram (behebt K2 zusätzlich zum Kern-Fix):** `format_email()`
übergibt an `render_telegram_bubbles()` (Aufruf Z. 256-276) `dc=_dc_uncollapsed`
statt der kollabierten `dc` (heute Z. 260: `dc=dc`) — damit liest
`render_for_channel("telegram", …)` (`narrow.py:661`) im `global`-Fallback-Zweig
wieder `self.metrics` der **echten** Grundauswahl statt der E-Mail-Auswahl.
Zusätzlich braucht Telegram eine **eigene** Zeilenmenge: die heute geteilte
`seg_tables` (`trip_report.py:146`, gebaut aus der kollabierten `dc` via
`_extract_hourly_rows()`/`_dp_to_row()`, Z. 627-649) bleibt für E-Mail
unverändert (s. AC-6), Telegram bekommt eine zweite, aus `_dc_uncollapsed`
gebaute Zeilenmenge. Ohne diese zweite Hälfte erschienen Telegram-Spalten ohne
Werte („–"), weil `_dp_to_row()` (Z. 636-649) nur Metriken einträgt, die in
der übergebenen `dc` `enabled` sind — die Spalte wäre über `dc=_dc_uncollapsed`
zwar sichtbar, aber leer (s. AC-3 vs. AC-5, unten getrennt geprüft).

**D6 — keine Datenmigration.** Begründung (Kontext-Dokument, K1): kein
Bestandsfall (0 verbotene Widersprüche, gemessen) UND der ausgelieferte Editor
erzeugt den Widerspruchszustand laufend neu (`WeatherMetricsTab.svelte:638`
kopiert die Grundauswahl beim ersten Anfassen eines Kanal-Tabs, `onToggleMetric`
ändert danach nur noch die globale Ebene) — eine Einmal-Migration löste das
Problem nicht dauerhaft, der Lesepfad-Schnitt schon. Entspricht dem in
ADR-0050 bereits benannten Preis „stiller Rückfall auf AUS für
Alt-Konfigurationen" (s. AC-10 für die Editor-Sequenz als Datenlage-Test).

**D7 — Premium-SMS/Compare unberührt:** Premium-SMS bekommt keine eigene
Kaskaden-Ebene (`premium_sms.py:19-21` sendet `report.sms_text` unverändert,
`trip_report.py:295` liest die SMS-Kaskade unter dem Schlüssel `"sms"`) — es
erbt die SMS-Kaskade transitiv (s. AC-11). Der Ortsvergleich ruft
`_parse_display_config()` gar nicht auf (`comparison.py:647-670` baut eine
Wegwerf-Config ohne Kanal-Ebenen) und ist damit von dieser Scheibe strukturell
nicht berührt.

**Verworfen (Kontext-Dokument): `seg_tables` global verbreitern.** Der
Vorschlag, die Stundenzeilen für ALLE Kanäle aus dem vollen Maximum zu bauen
(statt einer Telegram-eigenen Zeilenmenge, D5), ist am Code widerlegt:
`email/html.py:673,903` leiten die Mail-Spalten über `visible_cols(rows)` aus
den Zeilen-Schlüsseln ab, gefiltert nur über `allowed_col_keys`, und
`_allowed_col_keys_for_horizon()` liefert bei `horizon=None` ausdrücklich
`None` — das ist der Fall für **alle Etappen ab Tag 4**. Breitere Zeilen
schöben dort ungefiltert neue Spalten in die Trip-Mail. Telegram bekommt
deshalb eine **eigene** Zeilenmenge; der E-Mail-Pfad (Z. 146) bleibt
unangetastet (s. AC-6).

## Expected Behavior

- **Input:** die Basis-Fixture aus Scheibe 1 (`khw_display_config_widerspruch.json`,
  über den echten Loader geparst) sowie kontrollierte Ein-/Mehrfeld-Varianten
  davon (u. a. mit ergänzten `channel_layouts.email`/`.telegram`- und
  `per_report_layouts`-Einträgen), unveränderte `F.segment()`/`F.night_weather()`-
  Wetterdaten (Vorbild Scheibe 1, AC-10).
- **Output:** `get_metrics_for_channel()` liefert für `per_report`/`per_channel`-
  Quellen nur noch Metriken, deren ID auch in
  `get_metrics_for_report_type(report_type)` steht; der `global`-Zweig ist
  unverändert. Der bestehende `test_kaskade_ac7_…`-Test läuft ohne
  `xfail`-Markierung grün. Telegram folgt ohne eigene Ebene der Grundauswahl
  und zeigt für eigene Telegram-Auswahl echte Werte statt „–".
- **Side effects:** keine neue Persistenz, kein neues Pflicht-Gate. E-Mail-
  Ausgabe für Trips ohne Kanal-Widerspruch bleibt byte-identisch (s. AC-6).

## Acceptance Criteria

- **AC-1 (Kern — Kanal darf nicht hinzufügen):** Given eine Kanal-Ebene führt
  eine Metrik `enabled: true`, die in der globalen Grundauswahl `enabled:
  false` ist / When die drei Kanal-Renderpfade (E-Mail-Kopfzeile,
  Telegram-rich-Zellen, SMS-Text) über den echten Renderpfad laufen / Then
  erscheint die Metrik in KEINEM der drei Kanäle — ADR-0050 Regel 1/2 gilt.
  - Test: der bestehende `tests/tdd/test_channel_metric_matrix.py::test_kaskade_ac7_sms_channel_must_not_add_globally_disabled_metric`
    (Z. 827-848) läuft gegen den umgebauten Produktivcode grün; die
    `@pytest.mark.xfail(strict=True, …)`-Markierung (Z. 823-826) MUSS entfernt
    werden — sonst schlägt der Test als `XPASS` fehl (S1, Known Limitation 2).

- **AC-2 (Abwahl wirkt nur im eigenen Kanal — Gegenprobe zum S1-Spec-Fehler,
  ADR-0050 Regel 5):** Given eine SMS-Kanal-Ebene wählt eine global aktive
  Metrik ab (`enabled: false` oder weggelassen), E-Mail und Telegram haben
  KEINE eigene Kanal-Ebene für diesen Report-Typ / When der Schnitt aus D1
  läuft / Then bleibt die Metrik in E-Mail und Telegram unverändert sichtbar —
  der Schnitt (D1) greift ausschließlich in den `per_report`/`per_channel`-
  Zweigen von `get_metrics_for_channel()`, NIE im `global`-Zweig
  (Z. 862-863). Eine SMS-Abwahl darf E-Mail/Telegram strukturell nicht
  verändern können.
  - Test: Regressions-Bestätigung der bereits in Scheibe 1 korrigierten
    AC-4/AC-6-Fälle (`test_kaskade_ac4_…`, `test_kaskade_ac6_…`) NACH dem
    Umbau — beide bleiben unverändert grün, plus eine Assertion, dass
    `cascade_source_for_channel("email"/"telegram", …)` weiterhin `"global"`
    liefert (Beleg, dass der `global`-Zweig unangetastet blieb).

- **AC-3 (Telegram MIT eigener Telegram-Ebene = Telegram ∩ Grundauswahl):**
  Given eine Fixture-Variante mit `channel_layouts.telegram`, die eine global
  aktive Metrik abwählt / When `render_for_channel("telegram", dc,
  report_type)` läuft / Then fehlt die Metrik in `table_columns` +
  `detail_metrics`, alle übrigen global aktiven Metriken bleiben vorhanden.
  - Test: strukturelle Spalten-Prüfung wie der bestehende
    `_kaskade_telegram_cells()`-Helfer (`test_channel_metric_matrix.py:708-710`,
    ruft `render_for_channel` direkt mit der geladenen Fixture-`dc` auf) —
    diese Prüfung ist von der E-Mail-Kollabierung (D5) UNABHÄNGIG, weil sie
    nicht über `format_email()` läuft.

- **AC-4 (Telegram OHNE eigene Telegram-Ebene folgt Grundauswahl, NICHT
  E-Mail-Auswahl — behebt K2):** Given eine Fixture-Variante mit
  `channel_layouts.email` (Metrik X dort abgewählt, global aktiv) UND KEINER
  eigenen `channel_layouts.telegram` / When der ECHTE Renderpfad
  `TripReportFormatter().format_email(...)` läuft (NICHT `render_for_channel()`
  direkt mit der frisch geladenen `dc`, s. Hinweis unten) / Then erscheint
  Metrik X weiterhin in den Telegram-Bubbles, weil Telegram ohne eigene Ebene
  auf die Grundauswahl fällt — nicht auf die kollabierte E-Mail-Auswahl.
  - **Wichtiger Konstruktionshinweis:** `_kaskade_telegram_cells()` (S1-Helfer)
    lädt die `dc` frisch und ruft `render_for_channel` direkt auf — dieser Weg
    geht NIE durch `format_email()`s Kollabierungsschritt (Z. 122-138) und
    kann K2 deshalb strukturell nicht sehen. AC-4 MUSS stattdessen über
    `report.telegram_bubbles` (Ergebnis von `_kaskade_report(dc).telegram_bubbles`
    o. ä., der echte End-zu-End-Pfad) prüfen — sonst wäre der Test grün, ohne
    K2 zu bewachen (exakt die Fehlerklasse aus CLAUDE.md „Prüfort = Wirkort").
  - Test: `report.telegram_bubbles`-Text auf das Vorhandensein von Metrik X
    (Label/Zelle) prüfen, gegen eine Fixture-Variante mit
    `channel_layouts.email` ⊊ Grundauswahl und ohne `channel_layouts.telegram`.

- **AC-5 (Telegram zeigt echten WERT, nicht „–"):** Given eine
  Fixture-Variante, in der eine Metrik in `channel_layouts.telegram` AN und in
  `channel_layouts.email` AUS ist (beide Ebenen ⊊ Grundauswahl, aber
  unterschiedlich) / When der ECHTE Renderpfad (`format_email()` →
  `render_telegram_bubbles`) läuft / Then trägt die Telegram-Tabellenzelle den
  ECHTEN Zahlenwert der Metrik (aus `F.segment()`), nicht ein leeres Feld oder
  „–" — das ist der Nachweis für die D5-„zweite Hälfte" (eigene
  Telegram-Zeilenmenge), unabhängig vom Spalten-Nachweis aus AC-3.
  - Test: `report.telegram_bubbles`-Text parsen (Vorbild
    `_narrow_table`-Zeilenformat), Zellwert der Zielmetrik gegen den erwarteten
    numerischen Wert aus `F.segment()` prüfen — NICHT nur Spalten-Präsenz.

- **AC-6 (E-Mail bleibt unverändert, insbesondere Etappen ab Tag 4):** Given
  ein Trip ohne Kanal-Widerspruch (E-Mail-Kanal-Ebene fehlt oder ist mit der
  Grundauswahl identisch) mit mindestens einer Etappe, für die
  `_allowed_col_keys_for_horizon()` `None` liefert (`html.py:924-947`,
  `horizon=None` ab Tag 4, `helpers.py:318-322`) / When `format_email()` vor
  und nach dem Umbau mit identischem Input läuft / Then sind `email_html` und
  `email_plain` byte-identisch — insbesondere bleibt die
  Stundentabellen-Kopfzeile unverändert, weil `seg_tables` (`trip_report.py:146`)
  weiterhin ausschließlich aus der kollabierten `dc` gebaut wird und die
  Telegram-eigene Zeilenmenge (D5) eine separate Variable ist, die den
  E-Mail-Pfad nicht berührt.
  - **Test (verbindliche Form — „vorher/nachher" ist KEIN automatisierbarer
    Wächter):** Ein Test, der nur zwei Läufe *derselben* Codeversion
    vergleicht, kann nie rot werden. Die Zusicherung ist stattdessen als
    Eigenschaft EINES Laufs zu prüfen: Given eine Fixture-Variante, in der
    die **Telegram**-Ebene eine echte Obermenge der **E-Mail**-Ebene ist
    (mindestens eine Metrik nur in Telegram) / When `format_email()` läuft /
    Then enthält die Kopfzeile der E-Mail-Stundentabelle für eine Etappe mit
    `horizon=None` **genau** die Spalten der E-Mail-Auswahl — die
    Telegram-exklusive Metrik darf dort NICHT auftauchen.
    Das ist der Wächter gegen den in der Analyse verworfenen Ansatz
    („`seg_tables` global verbreitern"): würde jemand die Zeilenmenge
    gemeinsam statt getrennt aufbauen, liefe genau dieser Test rot, weil
    `visible_cols(rows)` (`email/helpers.py:296-299`) die Spalten bei
    `allowed_col_keys=None` aus den Zeilen-Schlüsseln ableitet.
    Zusätzlich zulässig, aber nicht ausreichend: ein in der RED-Phase gegen
    den unveränderten Stand aufgenommenes Soll-Artefakt (Golden File) der
    E-Mail-Ausgabe derselben Fixture.

- **AC-7 (Leere/fehlende Grundauswahl schneidet nicht):** Given `dc.metrics ==
  []` (leere globale Liste) UND eine SMS-Kanal-Ebene mit mehreren aktiven
  Einträgen / When `get_metrics_for_channel("sms", …)` läuft / Then bleibt die
  vollständige SMS-Kanal-Ebene unverändert erhalten — D4 greift, kein
  Totalausfall.
  - Test: Fixture-Variante mit geleerter `metrics`-Liste (Roh-JSON-Patch,
    Vorbild `_cascade_sms_variant`), Assertion `len(get_metrics_for_channel("sms",
    …)) == len(per_channel_layouts["sms"])`.

- **AC-8 (`per_report_layouts` wird gegen die globale Menge geschnitten, NICHT
  gegen `per_channel_layouts`):** Given `per_report_layouts["evening"]["sms"]`
  enthält eine Metrik, die global aktiv, aber im allgemeinen
  `per_channel_layouts["sms"]` nicht enthalten oder dort deaktiviert ist /
  When `get_metrics_for_channel("sms", "evening")` läuft / Then bleibt die
  Metrik im Ergebnis erhalten — der Schnitt (D3) prüft ausschließlich gegen
  die globale Menge, eine Verkettung mit der Kanal-Ebene würde sie fälschlich
  ausschließen.
  - Test: Fixture-Variante, die zusätzlich `per_report_layouts.evening.sms`
    ergänzt (in der Basis-Fixture nicht vorhanden, 0 Bestandsträger laut
    Kontext-Dokument), Ziel-Metrik global aktiv + per_channel abweichend.

- **AC-9 (Report-Typ-Flags wirken im Schnitt):** Given ein globaler Eintrag
  mit `evening_enabled=False` für eine Metrik, deren SMS-Kanal-Eintrag
  `enabled: true` (ohne eigenen `evening_enabled`-Override) führt / When der
  SMS-Renderpfad für `report_type="evening"` läuft / Then fehlt die Metrik im
  SMS-Text für den Abend-Report, weil D2 gegen
  `get_metrics_for_report_type("evening")` schneidet, wo die Metrik wegen
  `evening_enabled=False` nicht enthalten ist — ein Schnitt gegen rohe
  `enabled`-Flags hätte sie fälschlich durchgelassen.
  - Test: Fixture-Variante mit `evening_enabled: false` am globalen Eintrag
    einer kollisionssicheren Ziel-Metrik, SMS-Kanal-Eintrag unverändert aktiv;
    Assertion gegen `report.sms_text` für `report_type="evening"`.

- **AC-10 (Editor-Sequenz aus K1 als Datenlage-AC):** Given eine SMS-Kanal-
  Ebene ist zunächst ein vollständiger Snapshot der Grundauswahl (identische
  Einträge/Zustände) — danach wird AUSSCHLIESSLICH der globale Eintrag einer
  Metrik auf `enabled: false` gesetzt, der SMS-Kanal-Eintrag bleibt
  unverändert `enabled: true` (exakt die Reproduktionsfolge aus dem
  Kontext-Dokument: SMS-Tab öffnen → zurück zur Grundauswahl → dort abwählen →
  speichern) / When alle drei Kanal-Renderpfade laufen / Then verschwindet die
  Metrik auch aus dem SMS-Kanal.
  - Test A (Kern-Suite): zweistufig konstruierte Fixture-Variante (erst
    Kanal-Ebene = Kopie der Grundauswahl, dann NUR der globale Eintrag
    geändert) — ergänzt AC-1 um den Nachweis, dass auch der über den Editor
    real erreichbare Entstehungsweg abgesichert ist.
  - **Test B (PFLICHT — echter Browser-Klickpfad, PO-Leitplanke aus #1719):**
    Test A konstruiert die Datenlage von Hand und belegt damit **nicht**,
    dass der Editor sie tatsächlich so erzeugt — eine Aussage über den
    Editor ohne den Editor. Deshalb zusätzlich ein Playwright-Klickpfad
    unter `frontend/e2e/` gegen Staging, der die Sequenz **klickt**:
    Trip-Editor öffnen → Reiter „Wetterwerte" → **SMS-Kanal anwählen**
    (erzeugt die Kanal-Kopie, `WeatherMetricsTab.svelte:638`) → zurück zur
    **Grundauswahl** → dort die Ziel-Metrik abwählen → speichern → danach
    die **zugestellte Ausgabe** prüfen (Test-Briefing bzw.
    Kurzform-Vorschau des echten Versandwegs): die Metrik darf im SMS-Text
    nicht mehr vorkommen.
    Bewusst **kein** Deploy-Gate-Ersatz: das Frontend-Browser-Gate (#1558)
    lädt sechs Seiten und sammelt Konsolenfehler — es klickt keinen AC durch
    und genügt hier nicht.
    Namensregel: nach Verhalten benennen (z. B.
    `frontend/e2e/metrik-grundauswahl-schneidet-kanal.staging.spec.ts`),
    nicht nach Issue-Nummer. Vorbilder für Aufbau und Staging-Setup:
    `frontend/e2e/weather-metrics-tab-autosave.spec.ts`,
    `frontend/e2e/issue-776-metrics-toggle.spec.ts`,
    `frontend/e2e/layout-tab-route.spec.ts`.
    **Wichtig für die Erwartung:** Der Klickpfad beweist die Zusicherung von
    S2 (die zugestellte Ausgabe folgt der Grundauswahl), NICHT das
    Editor-Verhalten aus ADR-0050 Regel 4 („Aus ist ein Zustand") — das ist
    S3. Er läuft daher bewusst gegen den **unveränderten** Editor: dass der
    Editor eine widersprüchliche Datenlage schreibt, ist hier
    Versuchsaufbau, nicht Fehler.

- **AC-11 (SMS/Premium-SMS erben ohne eigene Änderung am Versandpfad):**
  Given `output/channels/premium_sms.py` sendet `report.sms_text` unverändert
  (Z. 19-21) UND `trip_report.py:295` liest die SMS-Kaskade unter dem
  Schlüssel `"sms"` / When AC-1 bis AC-2 sowie AC-9/AC-10 gegen `report.sms_text`
  laufen / Then gilt jedes Ergebnis strukturell auch für Premium-SMS — kein
  separater Render-Aufruf oder eigene Kaskaden-Ebene `channel_layouts.premium_sms`
  nötig oder vorhanden (D7).
  - **Test (verbindliche Form — Struktur-Behauptung genügt NICHT):** Die
    Abwesenheit eines `"premium_sms"`-Schlüssels zu assertieren, belegt das
    Verhalten nicht; „erbt sich schon" ist bei diesem Kanal bereits einmal
    falsch gewesen. Der Nachweis läuft über den **echten Versandweg**: der
    Text, den `PremiumSmsOutput.send()` hinausgibt, wird an einem lokalen
    HTTP-Empfänger abgenommen (bestehendes Muster `premium_sms_stub`,
    `tests/tdd/test_channel_origin_guard_parity.py:211-229` — echter Server,
    kein Mock) und muss (a) zeichengleich `report.sms_text` sein und (b) das
    Kürzel der durch den Schnitt entfernten Metrik NICHT enthalten.
    Damit ist Premium-SMS als vierter, gleichrangiger Kanal an derselben
    Zusicherung gemessen wie die anderen drei — nicht bloß als Erbe
    behauptet.

- **AC-12 (Abgeleitete Nachtgrößen fallen nicht unbeabsichtigt aus einer
  Kanal-Ebene):** Given die globale Liste enthält einen `"temperature"`-
  Eintrag, sodass `loader.py:810-819` `"temperature_night"` ableitet und an
  `self.metrics` anhängt, UND eine SMS-Kanal-Ebene führt ebenfalls einen
  expliziten `"temperature_night"`-Eintrag mit `enabled: true` (wie ein
  Editor-Snapshot ihn nach K1 anlegen könnte) / When
  `get_metrics_for_channel("sms", …)` läuft / Then bleibt `"temperature_night"`
  im SMS-Ergebnis erhalten — der Schnitt (D2, ID-basiert gegen
  `get_metrics_for_report_type()`) erkennt die abgeleitete Größe korrekt, ohne
  Sonderbehandlung, weil ihre ID bereits Teil des abgeleiteten globalen
  Maximums ist.
  - Test: Fixture-Variante mit globalem `"temperature"` + explizitem
    `"temperature_night"`-Eintrag im SMS-Kanal-Layout; Assertion auf die von
    `get_metrics_for_channel("sms", …)` zurückgegebene ID-Liste (nicht auf den
    SMS-Text — Nachtgrößen haben eine eigene, hier nicht betroffene
    Token-Ableitung, s. `reference_trip_temperature_is_specially_computed`).
    Diese Liste speist direkt `_sms_metrics_ordered`/`sms_metric_ids`
    (`trip_report.py:295-296`) — das ist der korrekte Wirkort für diese
    Zusicherung.

## Known Limitations

1. **Bestehende Kaskaden-Umgehung bleibt bestehen:** die Telegram-
   Kurzübersicht (`narrow.py:735/741/776`) liest `dc.get_enabled_metric_ids()`
   statt der Kanal-Kaskade und bleibt damit an die (nach D5 weiterhin
   kollabierte) E-Mail-Auswahl gekoppelt. Durch S2 wird das nicht schlimmer
   (bereits in S1 als „Adversary Angriff 5" benannt) — Behebung ist nicht Teil
   dieser Scheibe.
2. **`dataclasses.replace(dc, metrics=…)` bleibt bestehen** — die Wurzel, dass
   `dc` nach der E-Mail-Kollabierung über ihre eigene Grundauswahl „lügt",
   wird nicht aufgelöst. D5 umschifft die Auswirkung für Telegram gezielt
   (analog dem `_dc_uncollapsed`-Muster für SMS aus #1575), löst die Ursache
   aber nicht auf. Folgearbeit, nicht S2.
3. **Keine Datenmigration für Bestandstrips** mit bereits „erweiternden"
   Kanal-Layouts — bewusster Verzicht (D6). Betroffene Konfigurationen fallen
   nach dieser Scheibe still auf AUS zurück (ADR-0050, „Negativ/Preis").
4. **Docstring-Korrekturen sind Teil dieser Scheibe** (`models.py:826-841`,
   `loader.py:836-841` beschreiben heute eine Ersetzungs-Semantik) — reiner
   Text, kein Verhaltens-Nachweis nötig.

## Nicht in dieser Scheibe

- **Frontend** (Editor-Zustandsanzeige „Aus ist ein Zustand" statt Löschung,
  `CHANNEL_COL_BUDGET.sms`-Korrektur, ADR-0050 Regel 4) — Scheibe S3.
- **Legende/Erklärtext zur Kaskade im UI** — Scheibe S4.
- **Telegram-Kurzübersicht** (`narrow.py:735/741/776`) — bleibt an die
  E-Mail-Kollabierung gekoppelt, ausdrücklich unverändert durch diese Scheibe
  (s. Known Limitations 1).
- **Auflösung der `dataclasses.replace`-Kollabierung als Ganzes** (drei
  E-Mail-Renderer von `dc.metrics` entkoppeln) — Folgearbeit, nicht S2.
- **Datenmigration für Bestandstrips** — D6, begründet verzichtet.

## Offene Fragen

Keine blockierenden. Die in Scheibe 1 als offen benannte Migrationsfrage ist
mit D6 beantwortet (Verzicht, begründet). Die übrigen dort offen gelassenen
Punkte (Telegram-Kurzübersicht, `dataclasses.replace`-Auflösung) sind bewusste
Abgrenzungen dieser Scheibe (s. „Nicht in dieser Scheibe"), keine offenen
Fragen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0050 (`docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md`),
  bereits in Scheibe 1 verabschiedet und indiziert.
- **Rationale:** Diese Scheibe setzt Regeln 1-3 und 5 der bestehenden
  Entscheidung im Produktivcode um (Regel 4 ist Frontend/S3). Kein neues ADR
  nötig, kein Änderungsbedarf am ADR-Index.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie WIRKT —
oder nur dort, wo der Code steht?** Konkreter Fallstrick in dieser Scheibe:
der S1-Helfer `_kaskade_telegram_cells()` ruft `render_for_channel()` direkt
mit einer frisch geladenen `dc` auf und geht NIE durch `format_email()`s
Kollabierungsschritt — er kann K2 (AC-4) strukturell nicht sehen. AC-4/AC-5
MÜSSEN über den echten End-zu-End-Pfad (`report.telegram_bubbles`) laufen.

**Pflicht-Mutationsproben:**

- **(a) Schnitt aus D1 weglassen** (Zeilen um `models.py:846-860` auf die
  alte Ersetzung zurückdrehen) ⇒ AC-1 UND AC-5 (Telegram-Wert) MÜSSEN BEIDE
  rot werden, nicht nur eines — AC-1 prüft SMS/E-Mail/Telegram-Spalten für den
  Kern-Fall, AC-5 prüft zusätzlich den Telegram-Wert für einen anderen
  Fixture-Fall; ein Fix, der nur einen der beiden Pfade repariert, muss
  sichtbar bleiben.
- **(b) Schnitt gegen rohe `enabled`-Flags statt gegen
  `get_metrics_for_report_type()`** ⇒ AC-9 (Report-Typ-Flags) MUSS rot werden
  — die Metrik bliebe fälschlich im Abend-SMS-Text, obwohl `evening_enabled`
  sie ausschließt.
- **(c) `if not self.metrics`-Schutz (D4) entfernen** ⇒ AC-7 (Leerauswahl)
  MUSS rot werden — die SMS-Kanal-Ebene würde auf `[]` kollabieren.
- **(d) `dc=_dc_uncollapsed` an `render_telegram_bubbles` zurückdrehen** (Z.
  260 wieder `dc=dc`) ⇒ AC-4 MUSS rot werden (K2-Regression: Telegram folgt
  wieder der kollabierten E-Mail-Auswahl statt der Grundauswahl). AC-3 bleibt
  davon UNBERÜHRT, weil `per_channel_layouts`/`per_report_layouts` von
  `dataclasses.replace` nicht verändert werden (Kontext-Dokument Abschnitt 2)
  — AC-3 prüft ausschließlich den Fall MIT eigener Telegram-Ebene.
- **(e) die eigene Telegram-Zeilenmenge (D5, zweite Hälfte) zurückdrehen**
  (Telegram bekommt wieder die aus der kollabierten `dc` gebaute `seg_tables`,
  während `dc=_dc_uncollapsed` für die Spaltenermittlung korrekt bleibt) ⇒
  AC-5 (Wert) MUSS rot werden — die Spalte erscheint, aber leer/„–". AC-3
  (Spalten-Präsenz, geprüft unabhängig von `seg_tables` über
  `render_for_channel`/`_kaskade_telegram_cells`) bleibt dabei GRÜN. Das
  belegt, dass AC-3 und AC-5 unterschiedliche Dinge bewachen — ein Fix, der
  nur die Spalten-Hälfte von D5 umsetzt, muss trotzdem als unvollständig
  auffallen.
- **Verwechslungsprobe (Vorbild S1):** in AC-9/AC-10 versehentlich dieselbe
  Ziel-Metrik-ID wie AC-1/AC-7 verwenden — muss an der jeweiligen
  Vorbedingungs-Assertion (global aktiv vs. global inaktiv) erkennbar
  scheitern, bevor die eigentliche Prüfung überhaupt läuft.

## Bekannt rot werdende Bestandstests (mechanisch zu reparieren)

Fünf Bestandstests haben Kanal-Metriken, die in der jeweiligen globalen
Fixture-Liste **nicht** vorkommen — genau das von ADR-0050 verbotene Muster,
das D1 jetzt schneidet:

- `tests/tdd/test_issue_429_channel_layouts.py::test_ac3_per_channel_layout_wins_over_global`
  (Z. 189-203) — Kanal-Layout führt `temperature`, `wind_chill`, `wind`,
  `gust`, `precipitation`, `cloud_total`.
- `tests/tdd/test_issue_429_channel_layouts.py::test_ac5_channel_limits_still_applied_with_per_channel_layouts`
  (Z. 224-238) — Telegram-Layout mit 10 `metric_{i}`-Einträgen.
- `tests/tdd/test_issue_434_per_report_layouts.py::test_ac3_per_report_wins_over_per_channel`
  (Z. 170-183) — `per_report`-Override führt `temperature`, `precipitation`,
  `wind`, `gust`, `wind_chill`.
- `tests/integration/test_issue_448_validator_metrics_for_channel.py::test_ac2_per_channel_layout_returns_per_channel`
  (Z. 232-247) — Kanal-Layout führt `precipitation`.
- `tests/integration/test_issue_448_validator_metrics_for_channel.py::test_ac3_per_report_beats_per_channel`
  (Z. 249-264) — `per_report`-Override führt `sunshine_hours`, Kanal-Layout
  `wind_speed`.

**Reparatur = globale Liste der jeweiligen Test-Fixture-Hilfsfunktion
(`_per_channel_trip_data()`, `_per_report_trip_data()`, `trip_per_channel`,
`trip_per_report_and_channel`) um genau diese fehlenden Metrik-IDs ergänzen.**
Die Reparatur darf die Testaussage NICHT abschwächen: jeder Test prüft nach
der Ergänzung weiterhin dieselbe Kaskaden-Priorität (per_report > per_channel
> global) wie vorher — nur die Vorbedingung „Kanal-Metrik ist auch global
aktiv" kommt hinzu, weil sie unter ADR-0050 immer gelten muss. Assertions auf
die Ergebnis-Liste/-Reihenfolge bleiben unverändert; wo ein Test bislang eine
NICHT global vorhandene Metrik als Erwartung nutzte, muss diese Erwartung
durch dieselbe Metrik ersetzt werden, nachdem sie auch der globalen Liste
hinzugefügt wurde — nicht durch eine andere, um die geprüfte Kaskadenlogik
nicht zu verwässern.

## Changelog

- 2026-08-11: Initial spec created (Issue #1719, Scheibe 2). Grundlage:
  `docs/context/fix-1719-s2-kaskade-verfeinerung.md` (gemessen, Basis-Commit
  `32b781ed` = Merge PR #1735, Scheibe 1).
