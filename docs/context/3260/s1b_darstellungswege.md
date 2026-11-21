# #3260 Schritt 1 (Scheibe B): Implementierungskarte

Stand: HEAD `3c2899a2c`. Nur gelesen, keine Repo-Änderung. Die Ratsche `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py` gibt es noch nicht (sie kommt mit Spec s1a). Alle Zeilenangaben gelten für diesen Stand.
Soll-Tabelle: Spec `feat_3122_was_steht_wo.md`, Teil A Nr. 4 (Zeilen 109-116). Ampelpunkt erkennt man am Markup `border-radius:50%` (Konstante `PUNKT` in den Tests).

---------------------------------------------------------------------------
## 1. Einstieg je Stelle × Fläche × Ausgabeart, Aufruf im Test, Ort der Formwahl

### Testgerüste, die es schon gibt (wiederverwenden)
- **Trip über den echten Versandweg, mit placements**: `tests/tdd/test_einstellung_gleich_mail_trip_tabelle.py`
  - `zeile(mid, aus=(), email=..., telegram=..., outlook=...)`, `tabelle(zeilen, outlook_reports=["evening"])`, `trip(placements, folge=[...], report_config={...})`
  - `senden(monkeypatch, data, "evening")` liefert eine Kanalmitschrift. Danach `mail_teile(mit)` (HTML, Text), `telegram_tabelle(mit)`, `_tg_kurz(mit, kuerzel)`, `telegram_ausblick(mit)`.
  - Kompakt-Mail: `trip(..., report_config={"email_format": "compact"})`, dann `mail_teile(...)[1]` (Muster `_ausblick_trip`, Zeile 444).
  - Fixtures: `tests/tdd/_einstellung_gleich_mail_trip_fixtures.py` (`trip_json`, `render_trip_mit_ausblick`, `BASIS_KATALOG`, `AUSBLICK_TAGE`).
  - Parser: `tests/helpers/einstellung_gleich_mail_trip.py` (`html_tabellen`, `klartext_tabellen`, `html_ausblick`, `klartext_ausblick(text, AUSBLICK_TAGE)`, `zellform(text, fragment)` liefert zahl/einfach/ampel). Achtung: Die Soll-Hilfen dort (`AMPEL_GROESSEN`, `soll_stundenformen`, Zeilen 55 und 322-345) haben die alte #814-Ausnahme fest eingebaut („Klartext = Zahl“). Für den neuen Test nicht verwenden, das Soll von Hand schreiben (ADR-0127 Nr. 5).
  - Vorlage für die Muster: `tests/tdd/test_3156_renderer_nachzug_roh_einfach.py` (`_trip_regen`, `_orte_regen`).
- **Orte über den echten Versandweg, mit placements**: `tests/tdd/test_einstellung_gleich_mail_orte_tabelle.py`
  - `preset(zeilen=[{"metric_id": m, "places": AN, "formats": {"email": "simplified", "telegram": ..., "hourly": ..., "outlook": ...}}], grund=[(id, agg), ...])`
  - Fixture `mit`. `senden(mit, p, slot="evening")` gibt ein dict mit den Schlüsseln html, plain, telegram, sms und premium_sms zurück.
  - Parser: `tests/helpers/einstellung_gleich_mail_orte.py` (`html_vergleichszellen` mit rohem Fragment, `html_stundenverlauf`, `html_ausblick` mit rohem Fragment, `klartext_vergleichswerte`, `klartext_stundenverlauf`, `klartext_ausblick`), dazu `tg_bloecke`. Rohe Stunden-Fragmente liefert `test_3097_stundenverlauf_darstellung.html_stunden`.
  - Gegenwind-Fall (Windrichtungs-Ampel) braucht die Vorlage `radtour`. Nur diese Vorlage hat Grenzen für `wind_direction` (`ampel_templates.py:121`). Setzbar per `display_config.ampel={"template":"radtour"}`, siehe `app/ampel.py::_aufloesen`.
- **Schnellere Direktaufrufe ohne Versandweg** (für Einzelzellen):
  - Modus-Matrix (Renderer-Gate): `tests/tdd/test_issue_811_mode_matrix.py::_render(email_format, raw, alert, enabled, dp)` ruft `render_email`. Sie arbeitet mit der Altform (`use_friendly_format`, ohne `format_mode`), deshalb zeigt der Text dort die Zahl.
  - Trip-Ausblick: `tests/helpers/trip_outlook_selection.py::outlook_rows(...)` und `render_trip_mail(dc, rows)`, außerdem `tests/helpers/trip_outlook_channels.py::trip(...)`, `versendete_teile(...)`, `compact_outlook_block`, `telegram_outlook_bubble`.
  - Orte-Ausblick direkt: `test_outlook_darstellungsform._compare_mail(formats)`, also `render_compare_email(..., preset=PRESET_ALLGEMEIN)` (`tests/helpers/ampel_allgemein.py`).
  - Kurz-Zusammenfassung: `test_gewitter_zelle_zusammenfassung_sprache._satz(lang, hourly, friendly=)`, also `CompactSummaryFormatter().format_weather_summary(...)`.

### Trip
| Stelle / Ausgabeart | Einstieg | Ort der Roh/Einfach- und Ampel-Entscheidung heute |
|---|---|---|
| email · HTML (Stundentabelle) | `email/__init__.py:35 render_email` → `email/html.py render_html` | `email/helpers.py:790 fmt_val`: Wind/Böen 877-899, Niederschlag 902-908, Regenwahrscheinlichkeit 937-945, Gewitter 842-873, Wolken 912-917, Sonne 918-931, Windrichtung 958-966. Modus aus `build_format_modes` (helpers:1410), Ampelpunkt aus `build_html_indicator_keys` (helpers:1433). Zelltönung `html.py:655-693`. Zeilen: `trip_report.py:166 channel_metric_configs(_email_rows)` → `helpers.py:1352 mit_zeilen_format` |
| email · Text | `email/plain.py render_plain` | dasselbe `fmt_val` mit `html=False` (Wort nur bei `mode=="simplified"`; die Altform `use_friendly_format` ergibt "raw" und damit die Zahl, bekannte Lücke bis zur Migration B6) |
| email · Kompakt | `email/compact.py render_compact` | keine Metrikzellen (nur Kacheln). Nur der Ausblick ist betroffen, siehe unten |
| telegram | `narrow.py:770 render_telegram_bubbles` (Aufruf `trip_report.py:355`) | `narrow.py:88 _cell` → `fmt_val(html=False)`, Modi `build_format_modes(_dc_telegram)` (trip_report:367) aus `helpers.py:1315 telegram_metric_configs`. Kurzübersicht `narrow.py:519 _overview_line` (@h nur bei `hat_ampel`, :623) |
| outlook · alle | Zeilenbau `email/outlook.py:528 build_outlook_row` → `:631 _outlook_row` (Zellen :823-851) | `compare_outlook_metric_ids.py:528 format_outlook_value` (Einfach ergibt Wort, :568) und `outlook.py:440 _metric_column_bg`. Formate aus `helpers.py:1399 outlook_auswahl(view.outlook)` |
| outlook · HTML | `outlook.py:91 render_outlook_table` (Aufruf `html.py:1246`), konfigurierbarer Zweig 155-189 | gibt `stage["cells"]` escaped aus (:182-186) |
| outlook · Text | `outlook.py:326 render_outlook_plain` (`cells` bei :365) | gemeinsame `cells` |
| outlook · Kompakt | `compact.py:258-284` | gemeinsame `cells`, dann `_ascii` (:284, und der ganze Text nochmals bei :336) |
| outlook · Telegram | `narrow.py:695 _outlook_lines` (`cells` bei :716) | gemeinsame `cells` |
| Kurz-Zusammenfassung (HTML-Kopf, Text) | `trip_report.py:219/917 _generate_compact_summary` → `compact_summary.py:125 format_weather_summary` | `use_friendly_format` der **E-Mail**-Zeilen (dc ist die eingeklappte E-Mail-Auswahl): Wolken :233, Wind :245-252, Gewitter :256 |

### Orte (Orts-Vergleich)
| Stelle / Ausgabeart | Einstieg | Ort der Entscheidung heute |
|---|---|---|
| email · HTML (Vergleichstabelle) | `comparison.py:535 render_compare_email` → `compare_html.py:1814 render_compare_html` → `:952 _render_overview_table` → `:811 _render_overview_row` | `compare_html.py:780 _friendly_overview_html` (Ampel-IDs ergeben den Punkt über `fmt_val`, :793; Gewitter ergibt den Punkt, :798; sonst `_friendly_outlook_text`). Formate `opts.metric_formats("email")` (`compare_briefing_aufbau.py:118`, `report_config_resolver.py:284`) |
| email · Text | `comparison.py:187 render_comparison_text` | `comparison.py:691 _fmt_overview_cell` → `:664 _friendly_overview_text` |
| hourly · HTML | `compare_html.py:1233 _render_hour_table` → `:1175 _render_hour_row` | `compare_html.py:1143 _hour_einfach_text` (**:1160 nur wind/gust ergeben einen Punkt**). Formate `report_config_resolver.py:402 _compare_hourly` (:415), Filter `compare_outlook_metric_ids.py:496 resolve_hourly_metric_formats` |
| hourly · Text | `comparison.py:440` → `_hour_einfach_text(html=False)` | `compare_outlook_metric_ids.py:512 _friendly_hour_text` (Stunden-Skala) |
| telegram | `comparison.py:822 render_compare_telegram` → `:928 _telegram_location_block` → `:770 _plain_metric_cell` | `_fmt_overview_cell` und `:742 _ampel_stunde` (Marke :792) |
| outlook · HTML | `compare_html.py:1437 _render_location_outlook` → `:1352 _build_location_outlook_rows` → `_outlook_row(context="vergleich")` → `render_outlook_table` | wie Trip (`format_outlook_value`). Formate `report_config_resolver.py:420 _compare_outlook` |
| outlook · Text | `comparison.py:399/478` → `render_outlook_plain` | gemeinsame `cells` |
| outlook · Telegram | `comparison.py:1029 _telegram_outlook_lines` → `narrow._outlook_lines` | gemeinsame `cells` |

---------------------------------------------------------------------------
## 2. Wie die Formen heute entstehen

- **Ampelpunkt (HTML)**: Das Markup baut `email/helpers.py:683 _ampel_dot_css(level, hail=False)`, ein `<span>` mit 10px, `border-radius:50%`, `background:fill` und `box-shadow:0 0 0 3px ring` (bei Hagel zusätzlich ein Ring `0 0 0 6px`). Die Farben stehen in `_AMPEL_DOT_COLORS` (helpers:668).
  - Die Stufe kommt aus `output/metric_format.py:141 severity_for(metric_id, value, ampel=)`. Das geht über `app.ampel.schwellen_aus_ampel` (ampel.py:274) zu `severity_from_thresholds` (metric_format:154). Ergebnis ist green/yellow/orange/red aus der Abo-Ampel (`resolve_ampel`).
  - Dazu gehören die Hüllen `_ampel_dot_severity` (helpers:727), `ampel_level` (:748) und `mit_windrichtung` (:765, Wind und Gegenwind, höhere Stufe gewinnt).
  - Gewitter: `helpers.py:1577 _thunder_band` → `app/ampel.py:329 thunder_color`.
  - Die Zelltönung ist getrennt davon: Trip `html.py:655`, Orte `compare_html._sev_cell_style`/`tone_css`, Ausblick `outlook.py:440`.
  - Fähigkeit: `metric_catalog.AMPEL_METRIC_IDS` (:1220) umfasst wind, gust, precipitation und rain_probability.
- **Wortstufe** (`services/weather_metrics.py`):
  - `format_wind_strength` :124 (10/25/40)
  - `format_precip_intensity` :145 (Stunden-Skala)
  - `format_precip_daily_sum` :163 (Tagessumme)
  - `format_rain_probability_scale` :184
  - `format_sunshine_scale` :206
  - Gewitterwort: `app.thunder_scale.thunder_label(val, lang=)`. Die Zelle mit Zutaten und Hagel baut `email/thunder_branch.py:206 thunder_cell_html/_plain/_compact/_telegram`.
  - Die Zuordnung Metrik zu Skala (if-Kette) steht in `compare_outlook_metric_ids.py:455 _friendly_outlook_text` (Tageswert) und `:512 _friendly_hour_text` (Stundenwert).
  - Zweite, abweichende Windskala (15/35/60) in `compact_summary.py:544-551`.
- **Symbol**:
  - Wolken: `metric_format.py:265 cloud_emoji`
  - Sonne pro Stunde: `weather_metrics.py:58 get_weather_emoji`
  - ASCII-Wolkenstufe CLR/FEW/SCT/BKN/OVC: `output/tokens/metrics.py:23 cloud_stufe` (SMS)
- **Kompass**: `utils/geo.py:94 degrees_to_compass` (die Hülle `weather_metrics.py:273` delegiert dorthin). Roh-Grad: `fmt_val` :961 (`f"{int(val)}°"`), Orte `compare_html._fmt_deg` :188.
- **Zahl**: `metric_format.py:88 format_value(metric_id, value, style)`. Daneben gibt es viele örtliche Formatierer (`compare_html._fmt_*` :188-211, `comparison._PLAIN_ROWS` :86-137, `format_outlook_value` :576-579).

---------------------------------------------------------------------------
## 3. Auflösung von placements und Formaten (so stellt ein Test „Einfach“ an einer Stelle ein)

- Gespeichert: `display_config.placements.rows[].formats.{email,telegram,hourly,outlook}` ∈ raw|simplified (`hourly` nur bei Orten).
- `services/placements.py`: `read_placements` :118, `resolve_rows` :216, `_cell` :170. Format nur dort, wo `zwei_formen_stellen` die Stelle nennt, sonst `standard_form`. Dazu `metrics_at` :239, `heutige_form` :308 (Wissen über die Altform), `placements_from_legacy` :398.
- `services/channel_list_resolver.py:114 resolve_channel_lists(dc, surface, report_type, **abo)` liefert ein `MailViewModel` (email, telegram, sms, premium_sms, outlook, hourly; jeweils `ChannelRow(metric_id, enabled, format, source)`). Weitere Teile: `placements_view` :255, `_kanal_rows` :298, `_compare_view` :495 (Altpfad, liest `hourly_metric_formats`/`outlook_metric_formats` bei :519-529), `_trip_format` :383.
- Trip: `report_config_resolver.py:204 resolve_trip_view` → `trip_report.format_email` (:150-166) → `channel_metric_configs`/`telegram_metric_configs`/`outlook_auswahl` (helpers :1372/:1315/:1399) → `build_format_modes`/`build_html_indicator_keys`.
- Orte: `report_config_resolver.py:307 resolve_compare_render_options` → `opts.metric_formats(kanal)` :284, `_compare_hourly` :402, `_compare_outlook` :420. Durchgereicht in `compare_briefing_aufbau.py:96-175`.
- Am einfachsten im Test: Trip mit `zeile(mid, email="simplified", telegram="simplified", outlook="simplified")`, Orte mit `{"metric_id": mid, "places": AN, "formats": {...}}`. Wirkung hat das nur, wenn die Metrik auch in der Grundauswahl steht (`folge=` bzw. `grund=`).

---------------------------------------------------------------------------
## 4. Abweichungen der Renderer von der Tabelle heute

1. **Orte-Stundenverlauf HTML, Niederschlag und Regenwahrscheinlichkeit Einfach: Wort statt Ampelpunkt (#3255).** Ursache: `compare_html.py:1160` `if html and metric_id in ("wind", "gust")`. Niederschlag fällt auf `_friendly_hour_text` (Stunden-Skala), Regenwahrscheinlichkeit auf die Skala 25/50/75. Der Text bleibt beim Wort (richtig).
2. **3-Tages-Ausblick HTML (Trip und Orte), Wind, Böen, Niederschlag und Regenwahrscheinlichkeit Einfach: Wort statt Ampelpunkt.** Ursache:
   - `compare_outlook_metric_ids.py:568-571` liefert für `friendly` das Wort in den gemeinsamen `stage["cells"]`. Der Kommentar dazu (:562-567) schließt den HTML-Punkt ausdrücklich aus.
   - `outlook.py:182-186` setzt `_html.escape(text)` in die Zelle. Das ist für Text, Kompakt und Telegram richtig, für HTML falsch.
   - Text, Kompakt und Telegram müssen das Wort behalten. Gelöst wird das mit einer eigenen HTML-Zelle oder mit Rohwerten im Zeilen-dict (siehe Nr. 5).
3. **Kurz-Zusammenfassung, Gewitter:**
   - `compact_summary.py:644-647` zeigt bei friendly `"⚡ möglich"` (`mail.zusammenfassung.gewitter_symbol`), sonst `"Gewitter möglich"` (`gewitter_moeglich`). Es gibt kein Stufenwort (leicht/mittel/hoch), und die Wahl hängt am E-Mail-Umschalter, weitergereicht bei :256 (`enabled["thunder"].use_friendly_format`).
   - LOW hat schon einen eigenen Satz (:640-643, „Instabile Luftmasse (leicht)“).
   - Soll: das Stufenwort aus `thunder_label` (bzw. `max_lvl`), unabhängig vom Umschalter. Katalogtexte stehen in `i18n/messages/{de,en}/mail.json:172-173`.
4. **Kurz-Zusammenfassung, Windrichtung hängt am Wind-Umschalter**: `compact_summary.py:555` `if wind_dir_enabled and ... and friendly:`. `friendly` kommt aus wind/gust (:247-249). Soll: nur `wind_dir_enabled`.
5. **Orte-Telegram: `@h`-Marke an der Windrichtung.**
   - `comparison.py:792` hängt bei jeder friendly-Zelle `_ampel_stunde` an.
   - `_ampel_stunde` (:742-767) fragt `ampel_seite(ampel, "wind_direction", <Grad>)`. `schwellen_aus_ampel` lässt `wind_direction` als `AMPEL_ABGELEITET` durch (ampel.py:255/283).
   - Mit Vorlage `radtour` (Grenzen 10/20/30 km/h Gegenwind) ergibt 225° die Seite „oben“, also „SW@hh“ zur Stunde mit dem höchsten Gradwert. Gemessen: `ampel_seite(radtour, 'wind_direction', 225) == 'oben'`, alle anderen Vorlagen geben None.
   - Soll: Marke nur für Wind, Böen, Niederschlag und Regenwahrscheinlichkeit (Spec Nr. 4, letzter Satz), am besten über eine Katalog-Fähigkeit statt einer neuen ID-Liste.
6. **Kompakt-Mail, Ausblick Bewölkung Einfach ergibt `:partly_sunny:`.** `cells` trägt `cloud_emoji`, und `compact.py:284` (`_ascii` → `fold_ascii`/anyascii) macht daraus `:sunny:`, `:white_sun_small_cloud:`, `:partly_sunny:`, `:white_sun_cloud:`, `:cloud:` (gemessen). Dasselbe würde der Gesamt-`_ascii` (:336) mit jedem Emoji tun. Kandidat für die ASCII-Form ist `tokens/metrics.cloud_stufe` (CLR/FEW/SCT/BKN/OVC, dieselbe Bandgrenze). Das muss im Katalog als Form für die Ausgabeart „ascii“ entschieden werden (technisch; Alternative Zahl %).
7. **Bekannt, nicht in Schritt 1:** Trip-Nur-Text in der Altform (`use_friendly_format` ohne `format_mode`) zeigt bei Wind, Böen, Niederschlag und Regenwahrscheinlichkeit weiter die Zahl (`helpers.py:879/903/940` prüfen `mode=="simplified"`, `loader._resolve_format_mode` gibt "raw"). Die Golden-Datei `test_3156 ac7_trip_altbestand_ampel_*` hält das fest, die Lösung ist die Migration B6. Im neuen Test nur den placements-Pfad prüfen.
8. **Unschärfe der Tabelle bei Sonnenstunden** („Symbol bzw. Wortstufe“): Heute zeigt die Trip-Stundentabelle (HTML, Text, Telegram) das Symbol (`get_weather_emoji`, Stundenwert). Orte-Übersicht, Orte-Telegram und Ausblick zeigen die Wortstufe (`format_sunshine_scale`, Tageswert). Im Test so festschreiben: Stundenwert ergibt Symbol, Tageswert ergibt Wortstufe.

Ohne Abweichung (dient als Gegenprobe im Test):
- Trip-HTML (Stundentabelle) Punkt bei den vier Ampel-Metriken und bei Gewitter, Text Wort (placements-Pfad).
- Trip-Telegram Wort.
- Orte-Übersicht HTML Punkt (vier Metriken und Gewitter), Text und Telegram Wort.
- Orte-Stundenverlauf Wind und Böen Punkt.
- Wolken Symbol, Windrichtung Kompass bzw. Grad, im Stundenverlauf immer Kompass (nur Verschmelzung).
- Ausblick Text, Kompakt und Telegram Wort.
- Gewitter im Ausblick bzw. im Telegram immer Wort.

---------------------------------------------------------------------------
## 5. Vorschlag: Katalog-Formtabelle und eine Verarbeitungsfunktion

### Katalog (`src/app/metric_catalog.py`)
```python
# Formen: "zahl" | "wort" | "symbol" | "ampelpunkt" | "kompass"
# Ausgabearten: "html" | "text" | "ascii" (Kompakt-Mail; fehlt = wie "text")
@dataclass(frozen=True)
class FormPaar:
    raw: str
    simplified: str

_AMPEL4 = {s: {"html": FormPaar("zahl", "ampelpunkt"), "text": FormPaar("zahl", "wort")}
           for s in ("email", "telegram", "hourly", "outlook")}
_WOLKE = {s: {"html": FormPaar("zahl", "symbol"), "text": FormPaar("zahl", "symbol"),
              "ascii": FormPaar("zahl", "wort")}  # wort = Stufe CLR..OVC, nie ein Emoji
          for s in ("email", "telegram", "hourly", "outlook")}
STELLEN_FORMEN: dict[str, dict[str, dict[str, FormPaar]]] = {
    "wind": _AMPEL4, "gust": _AMPEL4, "precipitation": _AMPEL4, "rain_probability": _AMPEL4,
    "cloud_total": _WOLKE, "cloud_low": _WOLKE, "cloud_mid": _WOLKE, "cloud_high": _WOLKE,
    "sunshine": {"email": {...("zahl","symbol")}, "telegram": {...}, "outlook": {"html"/"text": ("zahl","wort")}},
    "wind_direction": {"email"/"telegram"/"outlook": ("zahl","kompass"), "hourly": ("kompass","kompass")},
    "thunder": {"email": {"html": ("wort","ampelpunkt"), "text": ("wort","wort")},
                "telegram": {"text": ("wort","wort")}, "outlook": {...("wort","wort")}},
}
# Wortskala je Wertart (Stunde/Tag), heute als if-Kette in den Renderern:
WORTSKALA = {"wind": {"stunde": "wind_strength", "tag": "wind_strength"},
             "precipitation": {"stunde": "precip_intensity", "tag": "precip_daily_sum"},
             "rain_probability": {...: "rain_probability"}, "sunshine": {"tag": "sunshine"}}
STUNDEN_MARKE = frozenset({"wind", "gust", "precipitation", "rain_probability"})  # @h im Orte-Telegram

def form(metric_id, stelle, ausgabeart, fmt) -> str: ...   # fehlt: "zahl"; "ascii" faellt auf "text"
```
- `STELLEN_ZWEI_FORMEN` daraus **ableiten** (Stelle mit raw != simplified in irgendeiner Ausgabeart). Dann bleiben `zwei_formen_stellen`, `AMPEL_METRIC_IDS` und `OUTLOOK_FRIENDLY_CAPABLE` und damit `test_katalog_stellen_formen.py` unverändert grün (`hourly` bei `wind_direction` hat zwei gleiche Formen und zählt deshalb nicht).

### Verarbeitung (`src/output/metric_format.py`)
```python
@dataclass(frozen=True)
class Zelle:
    text: str              # Klartext/Telegram/ASCII-taugliche Fassung
    html: str              # fertiger Zellinhalt (escaped Text oder Punkt-<span>)
    form: str              # zahl|wort|symbol|ampelpunkt|kompass
    stufe: Optional[str]   # green|yellow|orange|red (Abo-Ampel), auch bei Zahl (Toenung)

def darstellung(metric_id: str, wert, *, stelle: str, ausgabeart: str, fmt: Optional[str],
                ampel: dict, wertart: str = "stunde", lang: str = "de",
                hagel: Optional[bool] = None, gegenwind_kmh: Optional[float] = None) -> Zelle
def stunden_marke_erlaubt(metric_id) -> bool        # Katalog STUNDEN_MARKE
```
Was die Funktion für Schritt 1 als Erstes umhüllt (Minimum, kein Umbau von Schritt 6):
- Stufe: `severity_for` / `mit_windrichtung`-Logik / `_thunder_band` → `thunder_color`.
- Punkt-Markup: `_ampel_dot_css` und `_AMPEL_DOT_COLORS` zogen von helpers hierher um, helpers re-exportiert sie (Muster wie beim thunder_scale-Re-Export).
- Wort: die fünf `weather_metrics.format_*` über `WORTSKALA`, dazu `thunder_label`.
- Symbol: `cloud_emoji`, `get_weather_emoji`. ASCII-Wolke: `tokens.metrics.cloud_stufe`.
- Kompass: `utils.geo.degrees_to_compass`. Zahl: `format_value` bzw. die Spaltenangaben unit/decimals.

Erste Aufrufer in Schritt 1 (je eine Abweichung aus Nr. 4):
- `compare_html._hour_einfach_text` (:1143). Die ID-Liste bei :1160 entfällt, der Ratschen-Zähler sinkt.
- `_outlook_row`: speichert je Spalte Rohwert, metric_id, Wertart „tag“ und fmt (z. B. `row["zellen_roh"]`). `render_outlook_table` ruft `darstellung(..., ausgabeart="html").html`, `render_outlook_plain` und `narrow._outlook_lines` nutzen `"text"`, `compact.py` nutzt `"ascii"`. Minimale Variante: `row["cells_html"]` und `row["cells_ascii"]` neben `cells`, im Zeilenbau einmal über `darstellung` gebaut.
- `compact_summary._format_thunder`: Stufenwort und kein `friendly`. `_format_wind`: Kompass ohne `friendly`.
- `comparison._plain_metric_cell` (:792): Marke nur bei `stunden_marke_erlaubt`.

`fmt_val` (helpers:790) bleibt in Schritt 1 unangetastet. Später leitet es seine vier Ampel-Zweige auf `darstellung` um.

---------------------------------------------------------------------------
## 6. Tests, die das alte Verhalten festhalten (umschreiben)

- `tests/tdd/test_3097_stundenverlauf_darstellung.py`
  - :162-176 `test_einfachformen_je_groesse[rain_probability-wort]` verlangt in der HTML-Stundentabelle Regenwahrscheinlichkeit als Wort (`t in REGEN_WORTE`). Neu: `PUNKT in f`, der Text bleibt Wort (Klartext-Teil :175-176 bleibt).
  - :183-206 `test_ac6_niederschlag_stundenskala` verlangt im HTML die Stunden-Skala als Text (`ist == soll`, :197-199). Neu: im HTML Punkt (Stufe nach Abo-Ampel), die Stunden-Skala nur im Klartext (:200-202 bleibt).
  - Auch betroffen: :259-270 `test_ac11_validator_akzeptiert_einfach_zellen`. Der Mail-Validator `validate_hourly_table` muss Punkte in Niederschlag und Regenwahrscheinlichkeit annehmen, das prüfen.
- `tests/tdd/test_outlook_darstellungsform.py`
  - :109-170 `test_ac5_wind_boeen_zeigt_dieselbe_wortstufe_in_allen_vier_ausgaben` prüft HTML-Zelle Böen gleich Wortstufe (:159) und alle vier gleich (:163). Neu: HTML zeigt den Punkt, Text, Kompakt und Telegram dasselbe Wort.
  - :399-438 `test_ac6_einfach_zeigt_nur_wort_kein_ampelpunkt_im_text` prüft `format_outlook_value(44, friendly)` gleich Wort, escaped gleich Rohtext, kein Punkt-Marker. Neu: Die Textfassung bleibt Wort, zusätzlich wird geprüft, dass die HTML-Fassung den Punkt trägt.
  - :593-626 `test_ac5_ortsvergleich_zeigt_wortstufe_in_html_und_klartext` prüft die HTML-Ausblickzelle Orte gleich `format_wind_strength(25)` (:603). Neu: Punkt im HTML, Wort im Klartext.
  - Ebenso :802-832 und :834-866 `test_f002_vorschaudienst_/versandpfad_zeigt_die_umschaltung...`, die eine HTML-Böen-Zelle in `_wind_wortstufen()` verlangen (:827, :861).
- `tests/unit/test_gewitter_zelle_zusammenfassung_sprache.py`
  - :193-197 und :200-205 halten den Satz mit „Thunderstorm possible 9:00–12:00“ bzw. „Gewitter möglich 9:00–12:00“ fest.
  - :241-249 `test_zusammenfassung_maessig_sturm_freundlich` erwartet „⚡ possible/⚡ möglich 9:00–10:00“ bei friendly.
  - :252-267 Orte-Wrapper erwartet „⚡ möglich“/„⚡ possible“, dazu die Negativliste mit „möglich“.
  - Der Ausblick-Zellenteil (:61-142) ist nicht betroffen.
- `tests/unit/test_trip_summary_text.py:118`: Der aufgezeichnete Satz enthält „…, ⚡ möglich 13:00–15:00“ (Zellengleichheit, :123-131).
- Weitere Stellen mit dem Zusammenfassungs-Satz:
  - `tests/tdd/test_thunder_origin_trip.py:162-164, 247` („⚡ möglich 14:00–17:00 · CAPE“)
  - `tests/unit/test_briefing_compact_plain_sprache.py:217`
  - Golden-Datei `tests/fixtures/einstellung_gleich_mail/trip_altbestand_golden.txt:7` (und die .html)
- Nicht betroffen: `test_thunder_headline_sentence`, `test_thunder_forecast_low_level`, `test_thunder_origin_preview` betreffen die Gewitter-Vorschau (anderer Satz).
- Orte-Telegram `@h`: Kein Test hält die Windrichtungs-Marke fest. Neuer roter Test mit Vorlage `radtour`.
- Kompakt-Wolke: Kein Test hält `:partly_sunny:` fest. Neuer roter Test über `trip(... zeile("cloud_total", outlook="simplified") ..., report_config={"email_format":"compact"})`.
