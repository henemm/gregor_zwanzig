---
entity_id: feat_1680_s5b_gewitter_herkunft_vorschau
type: feature
created: 2026-08-14
updated: 2026-08-14
status: approved
version: "1.1"
tags: [thunder, trip, sms, outlook, adr-0007, adr-0025, issue-1680, issue-1419, issue-1196]
---

<!-- Issue #1680, Scheibe 5b (Gewitter-Vorschau) — LETZTE Scheibe. Vorgaenger:
     S1 Ortsvergleich, S2 Trip-Kurzzusammenfassung, S3 vier weitere Orte,
     S4 Trip-Stundentabelle, S5a Mehrtages-Ausblick (alle live). Bezug:
     Epic #1419 Rang 4, Entscheidung E1. Grundlage: PFLICHTLEKTUERE
     docs/context/feat-1680-s5b-vorschau-herkunft.md (frisch gegen 1e5e0be9
     gemessen — die Zeilenangaben in feat-1680-s5-ausblick-vorschau-herkunft.md
     sind gedriftet). -->

# Gewitter: Herkunft der Stufe in der Gewitter-Vorschau sichtbar machen (#1680 Scheibe 5b)

## Approval

- [x] Approved — vom PO freigegeben am 2026-08-14 (Fassung v1.1, 14 ACs)

## Purpose

Die **Gewitter-Vorschau** (der Block „Gewitter-Vorschau" für die Folgetage
`+1`/`+2` in der Trip-Vollmail) ist der letzte Ausgabeort, der die fusionierte
Gewitterstufe zeigt, ohne die tragende Zutat zu nennen — alle anderen
Ausgabeorte (Ortsvergleich, Trip-Kurzzusammenfassung, vier weitere Orte,
Trip-Stundentabelle, Mehrtages-Ausblick in HTML/Klartext/Telegram/Compare)
tun das bereits seit S1–S5a. Er zeigt heute z. B.
`14.08.2026: ⚡Gewitter möglich ab 14:00` und lässt offen, worauf die
Einstufung beruht.

Nach dieser Scheibe kann Issue #1680 geschlossen werden (s. Abschnitt „Was
nach dieser Scheibe für #1680 offen bleibt").

Die Herkunft nennt weiterhin nur die Zutat, keine Bewertung und keine
Handlungsempfehlung (ADR-0007).

## Source

> **Schicht-Hinweis:** überwiegend Python-Core-Domänenschicht
> (`src/services/`, `src/app/`), mit einer notwendigen Verschiebung zweier
> Hilfsfunktionen aus der Darstellungsschicht (`src/output/`) in die
> Domänenschicht — Begründung s. „Am Code gemessen", Punkt 3. Kein Frontend,
> keine Go-Beteiligung, kein neuer Endpoint, keine neuen Persistenz-Felder.

- **File:** `src/services/trip_report_scheduler.py`
  - `_thunder_entry_from_trend_row()` (Z. 2251–2372) — **Primärpfad**: baut
    den Vorschau-Eintrag aus einer bereits vorliegenden `multi_day_trend`-Zeile
    (`row["hourly_thunder_signals"]`, das S5a-Trägerfeld, liegt hier bereits
    vor, wird aber nicht gelesen).
  - `_build_thunder_forecast()` (Z. 2442–2588) — **Rückfallpfad**: baut den
    Eintrag aus frisch geholten `ForecastDataPoint`s. Ruft bereits
    `summarize_points(thunder_dps)` (Z. 2587), liest davon aber nur
    `.hail_flag`.
- **File:** `src/app/thunder_scale.py` — Domänenschicht-Modul, das seit
  #1196 bereits `thunder_ordinal()`/`thunder_label_value()` aus
  `output/metric_format.py` beherbergt, genau weil der Zeitplaner sie braucht,
  aber keine Darstellungsschicht importieren darf. `union_of_max_carriers()`
  und `thunder_signal_label()`/`THUNDER_SIGNAL_LABEL_DE` ziehen aus demselben
  Grund hierher um (Punkt 3).
- **File:** `src/output/metric_format.py` — verliert die beiden Definitionen,
  behält sie aber als Re-Export (Muster Z. 29–39, dort bereits für
  `thunder_ordinal`/`thunder_label_value` vorhanden).
- **Nicht betroffen (bewusst):** `src/output/renderers/email/plain.py`
  (Z. 311–332) und `src/output/renderers/email/html.py` (Z. 1311–1329) — beide
  übernehmen `fc['text']` bereits heute wörtlich (nur der Hagel-Zusatz wird
  vom Renderer selbst angehängt). Da die Herkunft Teil von `text` wird, bleibt
  hier kein Renderer-Code zu ändern (Entscheidung E1, s. u.).

## Wortlaut (bereits entschieden, s. Briefing — hier zur Nachvollziehbarkeit
dokumentiert)

Die Herkunft steht **unmittelbar hinter der Tagesaussage** (dem Satz mit
„ab HH:MM"), mit demselben Trenner `" · "` wie an allen sechs bisherigen
Fundstellen seit S1. Bei mehreren tragenden Zutaten werden sie mit `", "`
verbunden. Sie steht **vor** dem Nacht-Halbsatz und vor dem (vom Renderer
angehängten) Hagel-Zusatz.

| Fall | Zeile |
|---|---|
| eine Zutat | `14.08.2026: ⚡Gewitter möglich ab 14:00 · CAPE` |
| zwei Zutaten | `14.08.2026: ⚡Gewitter möglich ab 14:00 · CAPE, Blitzdichte` |
| mit Nacht-Halbsatz | `14.08.2026: ⚡Gewitter möglich ab 14:00 · CAPE, nachts leicht Gewitter ab 02:00` |
| mit Hagel | `14.08.2026: ⚡Gewitter möglich ab 14:00 · CAPE · Hagel: ja` |
| kein Gewitter | `14.08.2026: Kein Gewitter erwartet` — **nie** eine Herkunft |

## Acceptance Criteria

- **AC-1:** Given einen Morgen-Bericht in Standard-Konfiguration (kein
  Mehrtages-Trend vorhanden) mit einer Folge-Etappe, deren Gewitterstufe der
  `+1`-Vorschau im Tagesfenster von genau einer Zutat getragen wird / When die
  Trip-Vollmail (Klartext **und** HTML) erzeugt wird / Then steht in der
  Zeile der Gewitter-Vorschau hinter der Tagesaussage `" · "` und die
  deutsche Bezeichnung der Zutat, wortgleich in beiden Formaten (z. B.
  `Gewitter möglich ab 14:00 · CAPE`).

- **AC-2:** Given einen Abend-Bericht mit ausdrücklich ausgeschaltetem
  Mehrtages-Ausblick (`show_outlook=false`), obwohl ein Mehrtages-Trend
  vorliegt, mit derselben tragenden Zutat wie in AC-1 / When die
  Trip-Vollmail erzeugt wird / Then zeigt die Gewitter-Vorschau denselben
  Herkunfts-Zusatz — obwohl hier der andere interne Bauweg läuft (Zeile aus
  dem vorliegenden Trend statt eines Neuabrufs).

- **AC-3:** Given eine Folge-Etappe, deren Höchststufe im Tagesfenster von
  **zwei** Zutaten gleichzeitig getragen wird / When die Gewitter-Vorschau
  gerendert wird / Then werden **beide** Zutaten genannt, mit `", "`
  verbunden — kein Gewinner gekürt (Auslegung (ii): alle tragenden Signale,
  unverändert seit S1).

- **AC-4:** Given eine Etappe mit Gewitter im Tagesfenster **und**
  zusätzlichem Gewitter im Nachtfenster / When die Gewitter-Vorschau
  gerendert wird / Then steht die Herkunft unmittelbar hinter der
  Tagesaussage und **vor** dem Nacht-Halbsatz; der Nacht-Halbsatz selbst
  bleibt wortgleich zu heute.

- **AC-5:** Given eine Etappe mit Gewitter **und** gesetztem
  Hagel-Kennzeichen / When die Gewitter-Vorschau gerendert wird / Then steht
  die Herkunft **vor** dem Hagel-Zusatz, und der Hagel-Zusatz bleibt
  wortgleich erhalten (`... ab 14:00 · CAPE · Hagel: ja`).

- **AC-6:** Given eine Etappe **ohne** Gewitter im Tagesfenster (Stufe „Kein
  Gewitter erwartet") / When die Gewitter-Vorschau gerendert wird / Then
  enthält die Zeile **weder** eine Zutat-Bezeichnung **noch** einen
  zusätzlichen `·`-Trenner — sie bleibt zeichengleich zu heute. Gegenprobe an
  dergleichen Fixture: Läge dieselbe Etappe bei einer Stufe oberhalb NONE,
  erschiene die Herkunft sehr wohl — der Test darf nicht vakuum-grün sein.

- **AC-7:** Given einen Trip mit einem vom Standard (4–19 Uhr) **abweichenden**
  Tagesfenster und einem Gewitter, das **nur** innerhalb dieses abweichenden
  Fensters liegt (Primärpfad: Abend-Bericht mit ausgeschaltetem Ausblick) /
  When die Gewitter-Vorschau gerendert wird / Then stammen angezeigte Stufe
  **und** angezeigte Herkunft aus demselben (abweichenden) Fenster — nie
  einer Zutat, die zur gezeigten Stufe nicht gehört.

- **AC-8:** Given eine Etappe, für die im Tagesfenster **keine** Stundenprobe
  liegt und die Stufe deshalb über das Kalendertags-Maximum bestimmt wird
  (Fail-soft-Zweig, ausschließlich im Primärpfad erreichbar) / When die
  Gewitter-Vorschau gerendert wird / Then erscheint die Stufe **ohne**
  Herkunft — es gibt für diesen Zweig keine zum Fenster passende
  Trägerquelle. Gegenprobe an derselben Fixture: Läge stattdessen ein Sample
  im Fenster, erschiene die Herkunft sehr wohl.

- **AC-9:** Given einen Trip-Briefing-Versand über SMS bzw. Premium-SMS mit
  einer Etappe, deren Gewitter-Vorschau in der zeitgleich erzeugten Mail eine
  Zutat trägt / When der SMS-Text erzeugt wird / Then enthält er **keine**
  der vier Zutat-Bezeichnungen. Nachweis per Sonde (Beschriftungsfunktion
  zur Laufzeit eindeutig markieren, nicht per Wortsuche), mit Gegenprobe,
  dass dieselbe Sonde in der zeitgleich erzeugten Mail anschlägt — sonst
  beweist ihre Abwesenheit in der SMS nichts.

- **AC-10:** Given einen Trip-Briefing-Versand über Telegram bzw. im
  E-Mail-Kompaktformat mit derselben Etappe / When Telegram-Bubbles bzw.
  Kompakt-Mail erzeugt werden / Then bleibt ihre Ausgabe zeichengleich zu
  heute — kein „Gewitter-Vorschau"-Block, keine Herkunft, weil beide
  Renderer das Vorschau-Datum strukturell nicht empfangen.

- **AC-11:** Given eine Vorschau-Etappe **ohne** Trägerinformation (weder
  `hourly_thunder_signals` im Primärpfad noch eine Trägerliste im
  Rückfallpfad — Alt-Aufrufer bzw. aufgezeichnete Fixtures vor Scheibe 1) /
  When die Gewitter-Vorschau gerendert wird / Then bleibt ihre Ausgabe
  **byte-identisch** zu heute — kein leerer `·`-Trenner, keine leere
  Herkunft.

- **AC-12:** Given einen Trip auf Staging mit Gewitter an einem der Folgetage /
  When ein Mensch (bzw. ein echter Browser) `/trips/<id>?tab=preview` öffnet
  und die Ansicht **„Morgen"** wählt / Then steht die tragende Zutat sichtbar
  im Gewitter-Vorschau-Block der angezeigten Mail — im echten Browser
  abgelesen, nicht aus einer Zwischendatei. Dies ist der Bildschirm-Nachweis
  für den Rückfallpfad aus AC-1.

- **AC-13:** Given denselben Trip mit im Reiter „Wetter-Metriken"
  **abgeschaltetem** Mehrtages-Ausblick / When dieselbe Vorschau-Fläche in der
  Ansicht **„Abend"** geöffnet wird / Then erscheint der Gewitter-Vorschau-Block
  ebenfalls mit Herkunft (Bildschirm-Nachweis für den Primärpfad aus AC-2).
  Gegenprobe im selben Durchgang: Mit **eingeschaltetem** Ausblick verschwindet
  der Block vollständig, und die Herkunft steht stattdessen in der
  Ausblick-Tabelle (unverändertes Verhalten aus S5a) — so ist belegt, dass die
  Fläche überhaupt reagiert und der Nachweis nicht ins Leere läuft.

- **AC-14:** Given einen ausgelösten Trip-Briefing-Versand auf Staging an das
  Test-Postfach / When die Mail per IMAP abgeholt wird / Then trägt die
  **zugestellte** Mail die Herkunft im Gewitter-Vorschau-Block, in der
  Klartext- **und** in der HTML-Fassung — geprüft an der empfangenen Nachricht,
  nicht an der Renderer-Ausgabe.

## Am Code gemessen

**1. Welcher Pfad überhaupt in der Mail ankommt (bestätigt gegen den
Kontext-Befund).** Die Vorschau erscheint nur bei `not outlook_active`, mit
`outlook_active = show_outlook and bool(multi_day_trend)` (`plain.py:309`,
`html.py:1309`). Gemessen: Morgen-Standard (`multi_day_trend_reports=
["evening"]`, `loader.py:919`) hat keinen Trend ⇒ **Rückfallpfad**, das ist
der Regelfall der Morgen-Mail. Abend-Standard hat einen Trend und
`show_outlook=True` ⇒ Vorschau unsichtbar. Nur Abend **mit** `show_outlook=
False` erreicht den **Primärpfad**. Beide Pfade brauchen deshalb einen
eigenen Nachweis (AC-1/AC-2); keiner deckt den anderen ab.

**2. Rückfallpfad-Fensterkohärenz ist strukturell bereits gegeben.** In
`_build_thunder_forecast()` wird `level` inline über
`max((dp.thunder_level for dp in thunder_dps), key=thunder_ordinal)`
berechnet; `summarize_points(thunder_dps)` (`:2587`, bisher nur für `hail`
gelesen) berechnet `thunder_level_max`/`thunder_level_max_signals`
(`weather_metrics.py:437-440`) über **dieselbe** Liste `thunder_dps`
(dieselbe Objektreferenz, kein Re-Filter). Da `_compute_thunder_level()`
lediglich `dp.thunder_level is not None` filtert — eine Bedingung, die jedes
Element von `thunder_dps` durch den vorgelagerten Filter in `day_dps`
(`and dp.thunder_level`) bereits erfüllt — liefern beide Berechnungen
garantiert dieselbe Stufe. Es ist **keine** neue Fensterfilterung nötig, nur
das **Hochheben** des bestehenden `summarize_points(thunder_dps)`-Aufrufs in
eine Variable, aus der sowohl `hail_flag` als auch
`thunder_level_max_signals` gelesen werden (bisher nur `hail_flag`, ein
Aufruf statt weiterhin nur einem impliziten am Dict-Ende).

**3. 🔴 Architektur-Wächter-Konflikt — im Briefing nicht erwähnt, aber ein
Hard Gate.** Entscheidung E1 verlangt, die Herkunft **im Zeitplaner**
(`trip_report_scheduler.py`) aufzubauen. Ein zeilengenauer Architektur-Wächter
(`tests/unit/test_notification_service.py:183-230`,
`test_scheduler_has_no_output_imports`) erlaubt in dieser Datei **exakt
eine** Zeile Import aus der Darstellungsschicht
(`from output.renderers.email.outlook import build_outlook_row`) und
verbietet jede weitere Zeile mit `"from output"`/`"import output"` — auch
`from output.metric_format import ...` fiele darunter (der Wächter prüft
zeilenweise auf den String, nicht auf das konkrete Modul). `union_of_max_
carriers()` (S2, `metric_format.py:559`) und `thunder_signal_label()`/
`THUNDER_SIGNAL_LABEL_DE` (S1, `metric_format.py:374-390`) liegen aktuell
beide in `src/output/metric_format.py` — ein direkter Import in den
Zeitplaner würde `test_scheduler_has_no_output_imports` rot machen.

Das ist exakt das Problem, das #1196 bereits einmal gelöst hat:
`thunder_ordinal()`/`thunder_label_value()` wurden aus demselben Grund von
`output/metric_format.py` nach `app/thunder_scale.py` verschoben, mit
unverändertem Re-Export in `metric_format.py` (Z. 29–39, Kommentar dort:
„der Zeitplaner braucht sie, darf aber keine Darstellungsschicht
importieren"). Diese Scheibe wendet dasselbe Muster ein zweites Mal an:

- `union_of_max_carriers()` braucht dafür nur `ThunderLevel` (`app.models`,
  bereits importiert) und `thunder_ordinal` (bereits in `thunder_scale.py`)
  statt des lokalen `max_thunder()`-Helfers — `top = max_thunder(stufen)`
  wird zu `top = max(stufen, key=thunder_ordinal)`. Keine weitere
  Abhängigkeit auf Darstellungsschicht.
- `thunder_signal_label()`/`THUNDER_SIGNAL_LABEL_DE` sind ein reines Dict
  plus Lookup, ohne jede weitere Abhängigkeit.
- Geprüft, dass der Umzug **keine** bestehenden Importe bricht: alle
  fünf externen Consumer (`helpers.py:751,1026`, `weather_metrics.py:642`,
  `trip_command_processor.py:866,893,941,1003`, `compare_html.py:235`,
  `trip_report.py:650`) importieren via `from output.metric_format import
  ...` — das bleibt durch den Re-Export gültig, unverändert wie beim
  #1196-Umzug.
- Geprüft, dass die S5a-„Sonde" (`test_thunder_origin_outlook.py:680-710`,
  mutiert `metric_format.THUNDER_SIGNAL_LABEL_DE` in-place via
  `.clear()`/`.update()`) wirksam bleibt: Ein Re-Export bindet **dieselbe**
  Dict-Instanz, in-place-Mutation wirkt objektidentisch unabhängig vom
  Modulnamen, über den zugegriffen wird.

**4. NONE-Schutz — kein zusätzlicher Level-Check an der Einfügestelle
nötig, aber die Mutations-Gegenprobe muss dort ansetzen.** `union_of_max_
carriers()` liefert bei einem Höchstwert `NONE` bereits `None` (S2, Finding
F001) — exakt das Muster, das `helpers.py:1033-1036` (S5a) bereits ohne
zusätzlichen Level-Check am Aufrufort verwendet
(`thunder_day_origin = (", ".join(...) if _day_carriers else None)`). Diese
Scheibe folgt demselben Muster. Aus S5a Punkt A gelernt: Eine Mutation, die
nur die innere Absicherung angreift, kann eine bereits doppelt abgesicherte
Garantie unberührt lassen. Die Pflicht-Mutation für AC-6 setzt deshalb
**direkt an der Einfügestelle** an (Suffix unbedingt anhängen, unabhängig
vom Ergebnis der Trägerermittlung) — das ist der tatsächliche Wirkort dieser
Scheibe.

## Betroffene Dateien

| Datei | Art | Beschreibung |
|---|---|---|
| `src/app/thunder_scale.py` | MODIFY | `union_of_max_carriers()` und `thunder_signal_label()`/`THUNDER_SIGNAL_LABEL_DE` aus `output/metric_format.py` hierher verschieben (Domänenschicht) — Voraussetzung, damit der Zeitplaner sie lesen darf, ohne den Architektur-Wächter zu verletzen (Punkt 3). |
| `src/output/metric_format.py` | MODIFY | Beide Symbole per Re-Export unverändert erhalten, analog zum bestehenden Re-Export von `thunder_ordinal`/`thunder_label_value` (Z. 29–39). Alle externen Importe (`helpers.py`, `weather_metrics.py`, `trip_command_processor.py`, `compare_html.py`, `trip_report.py`) bleiben gültig. |
| `src/services/trip_report_scheduler.py` | MODIFY | Beide Bauwege (`_thunder_entry_from_trend_row()`, `_build_thunder_forecast()`) hängen die Herkunft an `text` — unmittelbar nach dem Aufbau der Tagesaussage, vor der Berechnung/dem Anhängen des Nacht-Halbsatzes. Primärpfad: neue, fenstergefilterte `union_of_max_carriers()`-Auswertung über `row["hourly_thunder_signals"]` mit denselben `win_start`/`win_end`, die bereits `windowed` filtern. Rückfallpfad: `summarize_points(thunder_dps)`-Aufruf in eine Variable heben, `.thunder_level_max_signals` zusätzlich zu `.hail_flag` lesen. |
| `tests/tdd/test_thunder_origin_preview.py` | CREATE | Neue TDD-Testsuite für AC-1 bis AC-11, echte Renderkette bis zum fertigen Text (kein Mock-Theater). |
| `frontend/e2e/trip-preview-thunder-origin.staging.spec.ts` | CREATE | Playwright-Spec für AC-12/AC-13: öffnet `/trips/<id>?tab=preview`, schaltet Morgen/Abend um und liest den Text **im `email-iframe`** ab. **Gehört NICHT in die CI-Positivliste** — s. „Warum dieser Test nicht in die Ampel gehört". |

### Warum dieser Test nicht in die Ampel gehört (nachgetragen 2026-08-15)

Die erste Fassung dieser Spec sah vor, den Spec nach einer Vermessung (3× grün) in
`.github/ci_e2e_specs.txt` aufzunehmen. **Die Vermessung ist gelaufen — 3 von 3 grün
(1,7 min / 17,6 s / 17,5 s) — und das Ergebnis lautet trotzdem: nicht aufnehmen.**

Grund ist nicht Wackeligkeit, sondern Bauart: Die `e2e`-Lane fährt einen **isolierten
Offline-Stack** (`frontend/e2e/ci-stack.sh start`). Dieser Spec läuft dagegen **gegen
Staging** — er setzt `baseURL` auf `https://staging.gregor20.henemm.com`, braucht die
nginx-Schranke (`GZ_VALIDATOR_*`), die App-Anmeldung (`GZ_AUTH_*` aus der Staging-`.env`)
und eine `storageState`-Datei. Nichts davon existiert in der CI. Aufgenommen würde er dort
scheitern und die Ampel für alle rot färben.

**Deshalb die Umbenennung auf `*.staging.spec.ts`.** Das ist die etablierte Konvention des
Repos (25+ Dateien) und zugleich ein Wächter: Der Vermessungslauf schließt dieses Muster
ausdrücklich aus (`--exclude='*.staging.spec.ts'`, `ci.yml:277`).

🔴 **Ohne die Umbenennung wäre der Spec beim nächsten Vermessungslauf automatisch
aufgenommen worden.** Der zweite Filter (`grep -qE '/home/hem/gregor_zwanzig|__dirname'`,
`ci.yml:280`) greift bei ihm **nicht**: Er löst sein Verzeichnis über
`path.dirname(fileURLToPath(import.meta.url))` auf, enthält also weder `__dirname` noch
einen absoluten Pfad. Er wäre durch beide Filter gerutscht — eine gestellte Falle, gefunden
nur, weil vor dem Eintragen geprüft wurde, ob er in der Ampel überhaupt laufen *kann*.

**Nicht angefasst (bewusst):** `src/output/renderers/email/plain.py`,
`src/output/renderers/email/html.py` (E1), `src/output/renderers/sms_trip.py`,
`src/output/renderers/narrow.py`, `src/output/renderers/email/compact.py`
(alle strukturell unbetroffen, s. AC-9/AC-10), `src/services/preview_service.py`
(ruft dieselbe Scheduler-Methode und reicht das Dict unverändert durch — braucht
deshalb **keinen eigenen Code**, sehr wohl aber einen eigenen **Nachweis**: die
Bildschirm-Vorschau ist ein echter Wirkort, s. AC-12/AC-13).

## Expected Behavior

- **Input:** eine Folge-Etappe mit Gewitterstufe im Tagesfenster, entweder
  über eine vorliegende `multi_day_trend`-Zeile (Primärpfad) oder über frisch
  geholte `ForecastDataPoint`s (Rückfallpfad).
- **Output:** `thunder_forecast["+1"/"+2"]["text"]` trägt zusätzlich zur
  Tagesaussage die tragende(n) Zutat(en) — sichtbar in Klartext- und
  HTML-Trip-Vollmail, unverändert in SMS/Premium-SMS/Telegram/Kompakt-Mail.
- **Side effects:** keine. Reine Textzusammensetzung aus bereits vorhandenen
  Daten, keine zusätzlichen Netzabrufe (die Trägerdaten liegen in beiden
  Pfaden bereits vor, s. S5a Punkt 5 zur Anreicherung ohne Schalter).

## Testplan

| AC | Test (in `tests/tdd/test_thunder_origin_preview.py`) | Pfad/Fixture |
|---|---|---|
| AC-1 | `test_ac1_rueckfallpfad_eine_zutat_klartext_und_html` | Rückfallpfad — Morgen-Standard, kein Trend |
| AC-2 | `test_ac2_primaerpfad_eine_zutat_klartext_und_html` | Primärpfad — Abend, `show_outlook=False`, Trend vorhanden |
| AC-3 | `test_ac3_zwei_zutaten_werden_beide_genannt` | wahlweise Pfad, zwei echte Signale am Maximum |
| AC-4 | `test_ac4_herkunft_steht_vor_dem_nacht_halbsatz` | Tag- und Nachtgewitter in derselben Fixture |
| AC-5 | `test_ac5_herkunft_steht_vor_dem_hagel_zusatz` | Etappe mit `hail_flag=True` |
| AC-6 | `test_ac6_kein_gewitter_zeigt_nie_herkunft` | NONE-Fixture + Gegenprobe (gleiche Fixture, Stufe > NONE) |
| AC-7 | `test_ac7_primaerpfad_abweichendes_fenster` | Primärpfad, Tagesfenster z. B. 6–14 statt 4–19 |
| AC-8 | `test_ac8_primaerpfad_failsoft_ohne_traegerquelle` | Primärpfad, keine Stundenprobe im Fenster + Gegenprobe |
| AC-9 | `test_ac9_sms_und_premium_sms_ohne_herkunft_sonde` | Sonde auf `THUNDER_SIGNAL_LABEL_DE` (nach dem Umzug: `thunder_scale.THUNDER_SIGNAL_LABEL_DE`, objektidentisch mit dem Re-Export), Gegenprobe an derselben Mail |
| AC-10 | `test_ac10_telegram_und_kompaktmail_unveraendert` | Telegram-Bubbles + Kompakt-Mail derselben Etappe, Gegenprobe an der Vollmail |
| AC-11 | `test_ac11_ohne_traegerinfo_bleibt_byte_identisch` | beide Pfade je einmal mit/ohne S5a-Trägerfeld bzw. Rückfall-Trägerliste |
| AC-12 | `frontend/e2e/trip-preview-thunder-origin.staging.spec.ts` → `vorschau_morgen_zeigt_herkunft` | echter Browser gegen Staging, `?tab=preview`, Ansicht „Morgen" |
| AC-13 | dieselbe Datei → `vorschau_abend_ohne_ausblick_zeigt_herkunft` + Gegenprobe `mit_ausblick_verschwindet_der_block` | echter Browser gegen Staging, Ausblick-Schalter im Reiter „Wetter-Metriken" |
| AC-14 | `briefing_mail_validator.py` gegen die per IMAP abgeholte Staging-Mail (kein Unit-Test) | echt zugestellte Mail, Klartext + HTML |

**Aufrufweg des Browser-Tests (in der RED-Phase festgelegt):**
`cd frontend/e2e && npx playwright test trip-preview-thunder-origin.staging.spec.ts --reporter=line`.
Der Spec setzt `baseURL`, nginx-Schranke und `storageState` selbst per `test.use`; ein Aufruf
aus `frontend/` würde `playwright.config.ts` mitziehen (lokaler `webServer` + `global.setup`)
und ist deshalb **nicht** geeignet. Er sät seinen eigenen Trip `e2e-1680-s5b-origin` unter
`default` — der namensstabile Rolling-Trip gehört einem Nutzer ohne Anmeldeweg (s. Kontext,
Risiko 7).

**Bewusste Abweichung bei AC-13:** Der Vorzustand (`show_outlook=false`) wird per
`PUT /api/trips/<id>` hergestellt, nicht im Reiter „Wetter-Metriken" durchgeklickt. Der
**Wirkort** des Kriteriums ist die Vorschau-Fläche, und die wird im echten Browser gemessen;
den Schalter selbst bewachen die Editor-Tests. Ein Durchklicken des Schalters würde die
Zusicherung nicht schärfen, aber den Test an eine zweite, fremde Fläche binden.

**Fixture-Hinweis (Rückfallpfad-Regressionsschutz):** Die Fixture für AC-1
sollte zusätzlich zu den Punkten im Tagesfenster Punkte **außerhalb** des
Fensters mit einer **anderen** Zutat tragen. Würde die Implementierung die
Trägerliste versehentlich aus `day_dps` (ungefiltert) statt aus `thunder_dps`
(gefenstert) lesen, zeigte die Herkunft dann eine falsche Zutat — ohne
gemischte Fixture bliebe dieser Fehler unentdeckt, weil Punkt 2 diese
Kohärenz zwar strukturell nahelegt, aber nur der Test sie beweist
(Prüfort = Wirkort).

### Pflicht-Mutationsproben

Jede Mutation nur per String-Ersetzung mit externer Sicherungskopie — **nie**
`git checkout`/`stash`/`reset`.

- **(a)** Herkunfts-Suffix komplett aus dem Textaufbau entfernen (beide
  Bauwege) → **AC-1 und AC-2 müssen rot werden**.
- **(b)** Primärpfad: Fensterfilterung für die Trägerauswertung entfernen
  (ganzer Kalendertag statt Fenster) → **AC-7 muss rot werden**.
- **(c)** NONE-Zweig: Herkunfts-Suffix an der Einfügestelle unbedingt
  anhängen, unabhängig vom Ergebnis der Trägerermittlung → **AC-6 muss rot
  werden**.
- **(d)** Primärpfad: Fail-soft-Zweig bekommt eine Herkunft aus dem
  Kalendertags-Maximum ohne Fensterbezug statt „keine Herkunft" →
  **AC-8 muss rot werden**.
- **(e)** Reihenfolge vertauschen: Herkunft **nach** dem Nacht-Halbsatz statt
  davor einfügen → **AC-4 muss rot werden**.
- **(f)** Guard entfernen, der die Herkunft nur bei tatsächlich vorhandener
  Trägerliste anhängt (leerer/falscher Zusatz auch bei Alt-Fixtures ohne
  Trägerfeld) → **AC-11 muss rot werden**.

Kommt eine Mutation durch, ist das ein Finding, kein Nebenbefund.

## Risiken

1. **🔴 Renderer-Gate #811 greift nicht — der Nachweis muss deshalb aus der
   Spec kommen, nicht aus dem Wächter.** Diese Scheibe ändert
   `plain.py`/`html.py` **nicht**, also löst `renderer_mail_gate.py` nicht aus
   und erzwingt weder Mail-Validator noch Golden-Mail-Lauf. Die geänderte
   Text-Quelle (`trip_report_scheduler.py`) beeinflusst trotzdem **beide**
   Mail-Ausgaben. Genau diese Lücke schließen AC-14 (echt zugestellte Mail)
   und AC-12/AC-13 (echter Browser) ausdrücklich als Pflicht — sie sind hier
   kein Zusatz, sondern der Ersatz für ein Gate, das strukturell schweigt.

1b. **🔴 Bestandslücke, die dieser Scheibe vorausgeht: die Vorschau-Fläche ist
   heute unbewacht.** Gemessen: Kein einziges Playwright-Spec öffnet
   `/trips/<id>?tab=preview` und prüft den Inhalt des `email-iframe`. Der
   einzige Vorschau-E2E-Test (`frontend/e2e/email-preview-header.spec.ts`,
   in der CI-Positivliste) hängt an der Dev-Route `/email-preview-dev` mit
   **Mock-Daten**, die laut eigenem Kommentar (`+page.svelte:2-3, 29-31`) mit
   #189 hätte entfernt werden sollen und nur den Kopfbereich rendert — nie den
   Gewitter-Block. Der neue Spec aus dieser Scheibe schließt diese Lücke für
   den hier geänderten Text; die restliche Fläche bleibt unbewacht und gehört
   als Testlücke nach #1196.
2. **🔴 Architektur-Wächter `test_scheduler_has_no_output_imports` MUSS grün
   bleiben** — s. „Am Code gemessen" Punkt 3. Ein direkter Import aus
   `output.metric_format` in `trip_report_scheduler.py` (statt des Umzugs
   nach `app.thunder_scale`) macht diesen Bestandstest sofort rot und
   verletzt die Trip/Compare- bzw. Scheduler/Renderer-Trennung, die dieser
   Wächter seit Epic #1301 B4 erzwingt.
3. **Bruchrisiko Bestandstests, asymmetrisch (zu messen, nicht anzunehmen).**
   21 Tests vergleichen `entry["text"]` zeichengleich
   (`tests/unit/test_thunder_forecast_day_window.py` 6×,
   `tests/unit/test_thunder_night_addendum.py` 13×,
   `tests/tdd/test_thunder_forecast_low_level.py` 4×), dazu 2 Paritätstests
   (`tests/unit/test_thunder_night_addendum_parity.py:382,415` — v1.0 nannte
   hier fälschlich `tests/tdd/`, in der RED-Phase am Dateisystem korrigiert).
   **In der RED-Phase nachgemessen: keiner dieser Tests bricht** — keine ihrer
   Fixtures führt Trägerdaten (`thunder_level_signals`, Rohwerte oder Fusion);
   der Paritätstest fährt zwar den echten Provider-Pfad, sein Gewitter liegt
   aber ausschließlich in der Nachtquelle, die Tagesstufe ist `NONE`. Für den
   **Primärpfad** ist das Risiko strukturell gering: `hourly_thunder_signals`
   wird im ganzen Repo nur an zwei Stellen berührt (Erzeuger in
   `outlook.py`, Verbraucher in `helpers.py`), keine bekannte Testfixture
   setzt es für diese Tests. Für den **Rückfallpfad** ist es real: Fixtures
   mit echten `ForecastDataPoint`s können bereits heute Trägerlisten tragen
   (`dp.thunder_level_signals`), ohne dass ein Test das bisher prüft. Bricht
   ein Bestandstest, wird er **mitgezogen** (Erwartung angepasst), nicht
   umgedreht — sonst driftet dieselbe Erwartung in zwei Dateien
   auseinander (S3-Lehre).
4. **Renderer-unabhängige Konsumenten des Dict bleiben unverändert, aber
   ungeprüft von dieser Spec.** `preview_service.py` (Vorschau-Endpunkt)
   nutzt denselben Codepfad 1:1 und braucht deshalb keinen eigenen Test —
   sollte er künftig eigenständig auf `fc['text']` zugreifen und dabei einen
   anderen Renderer als Klartext/HTML ansprechen, gilt dieselbe Prüfpflicht
   wie für SMS/Telegram (AC-9/AC-10-Prinzip).
5. **`sms_text or email_plain`-Rückfall bleibt praktisch tot**, ist aber
   weiterhin nur eine Zusicherung per AC (AC-9), keine bauliche
   Unmöglichkeit (unverändert seit S2).

## Was sich NICHT ändern darf

- `src/output/renderers/email/plain.py` und `html.py` bleiben unangetastet
  (E1) — jede Änderung dort wäre ein Hinweis, dass die Entscheidung verlassen
  wurde.
- `tests/tdd/test_scheduler_has_no_output_imports` (in
  `tests/unit/test_notification_service.py`) bleibt grün, **ohne** angefasst
  zu werden — s. Risiken Punkt 2.
- SMS und Premium-SMS bleiben ohne Herkunft (AC-9).
- Telegram und Kompakt-Mail bleiben zeichengleich (AC-10).
- Der Nacht-Halbsatz bleibt wortgleich (AC-4, unverändert seit S5a).

## Nicht in dieser Scheibe

- **`aggregate_stage()`s Dispatch-Zweig** (`union_of_max_carriers` dort
  weiterhin unangeschlossen) — s. Known Limitations, gebucht in #1199
  (unverändert seit S5a).
- **Eine eigene Herkunft für den Nachtteil** — bewusste Grenze, deckungsgleich
  mit S5a AC-6.
- **Reihenfolgen-Vereinheitlichung bei mehreren gleichzeitig gipfelnden
  Zutaten** — unverändert seit S1, Sammel-Eintrag #1199.
- **Go-DTO und Frontend** — kein Verbraucher, unverändert seit S3.
- **Telegram und Kompakt-Mail** — strukturell kein Konsument des Vorschau-
  Dict, s. AC-10.

## Known Limitations

1. **`aggregate_stage()` bleibt unangeschlossen** (geerbt von S5a,
   `weather_metrics.py:1265-1266`). Betrifft diese Scheibe nicht direkt, da
   weder Primär- noch Rückfallpfad über diesen Zweig laufen.
2. **Der Nachtteil trägt nie eine Herkunft** (bewusst, wie im gesamten
   Ausblick/Vorschau-Strang seit S5a).
3. **Zwei Zutaten können je nach Stundenlage in unterschiedlicher Reihenfolge
   erscheinen** (Erstauftritts-Reihenfolge von `union_of_max_carriers()`,
   unverändert seit S1). Kein Gewinner, nur die Uhrzeit entscheidet die
   Nennreihenfolge.
4. **`sdi_2` (Superzellen) bleibt außen vor** — die Fusion hat vier Zutaten,
   nicht fünf (unverändert seit S1).
5. **EU_REST-LPI bleibt ein ausgewiesener Interim-Wert** (#1678, ADR-0048),
   unverändert seit S1.
6. **Zwei Zutaten plus Nacht-Halbsatz ergeben zwei Kommas hintereinander**
   in derselben Zeile (`· CAPE, Blitzdichte, nachts leicht Gewitter ab
   02:00`) — unschön, aber eindeutig lesbar, weil der Nacht-Halbsatz stets
   mit dem festen Wort „nachts" beginnt. Der Alternativweg —
   `format_night_addendum()` auf `·` umstellen — ist abgelehnt: dieser
   Wortlaut-Baustein ist geteilt (Trend- **und** Fetch-Weg) und würde weit
   über diese Scheibe hinaus wirken.

## Was nach dieser Scheibe für #1680 offen bleibt

**Nichts** — Issue #1680 kann geschlossen werden. Nach S5b trägt jeder
Ausgabeort, der die fusionierte Gewitterstufe als Fließtext zeigt, auch ihre
Herkunft: die acht Orte aus S1–S4 (Ortsvergleich, Trip-Kurzzusammenfassung,
vier weitere Orte, Trip-Stundentabelle), der Mehrtages-Ausblick in HTML,
Klartext, Telegram und beiden Compare-Renderpfaden (S5a) sowie nun die
Gewitter-Vorschau in Klartext und HTML (S5b). Die verbleibenden Kanäle — SMS,
Premium-SMS, Telegram-Kurzform-Token, Kompakt-Mail — zeigen die Stufe
grundsätzlich nur als Kürzel oder Zahl ohne Fließtext (`TH+:M@14` u. ä.) und
liegen damit strukturell außerhalb des Auftrags „Herkunft im Satz nennen"
(AC-9/AC-10 sichern das ausdrücklich ab, statt es nur zu behaupten). Offen
bleibt einzig `aggregate_stage()`s unangeschlossener Dispatch-Zweig
(Known Limitations 1) — er ist kein Ausgabeort, sondern totes Konfigurations-
Feld ohne erreichbaren Verbraucher, bleibt in #1199 gebucht und braucht vor
einem Fix zuerst einen echten Aufrufer.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe führt kein neues Architekturprinzip ein,
  sondern wendet ein bereits etabliertes Muster (#1196: Domänenschicht-
  Funktionen, die der Zeitplaner braucht, wandern aus `output/` nach
  `app/`, mit Re-Export) ein zweites Mal an. ADR-0007 (nur Zutat nennen,
  keine Bewertung) und ADR-0025 (Tagesfenster-Regeln) gelten unverändert
  fort.

## Changelog

- 2026-08-14: Initial spec created (Scheibe 5b, letzte Scheibe von #1680).
- 2026-08-14 (v1.1): AC-12/AC-13 (Nachweis im echten Browser auf der
  Vorschau-Fläche `/trips/<id>?tab=preview`, beide Bauwege) und AC-14
  (Nachweis an der per IMAP abgeholten Staging-Mail) ergänzt — auf Vorgabe des
  PO. Anlass: v1.0 hatte die Bildschirm-Vorschau als „profitiert automatisch
  mit, ohne eigenen Test" abgetan; gemessen ist sie ein echter Wirkort, in dem
  der geänderte Text in der Morgen-Ansicht standardmäßig sichtbar ist. Neuer
  Playwright-Spec als CREATE aufgenommen, Risiko 1 umformuliert (das
  Renderer-Gate schweigt hier strukturell), Bestandslücke 1b ergänzt.
