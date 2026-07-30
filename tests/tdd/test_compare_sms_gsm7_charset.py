"""Compare-SMS bleibt im GSM-7-Zeichensatz (#1362 S5b, Adversary-Fund Runde 4).

Fund im Staging-Nachweis (PO, 2026-07-30): das Grad-Zeichen `°` gehoert nicht
zum GSM-7-Alphabet (GSM 03.38). Sobald ein einziges GSM-7-fremdes Zeichen in
der SMS steht, kodiert der Betreiber die GANZE Nachricht in UCS-2 -- dort
passen nur 67 Zeichen je Teil statt 153 (SMS-Verkettung, 3GPP TS 23.040). Eine
neun-Groessen-Auswahl mit `33°C` sprang dadurch beobachtet von 1 auf 2
SMS-Teile -- eine STILLE Kostenverdopplung, weil kein bisheriger Pruefdurchgang
Zeichen GEGEN DEN ZEICHENSATZ statt nur gegen die 140-Byte-Grenze gezaehlt hat.

Zweiter, beim Bau dieses Waechters gefundener Fall (nicht Teil der PO-Meldung,
aber derselbe Fehlerklasse): `ThunderLevel.NONE` (ein echter, gesetzter Wert --
kein fehlender Wert, der schon vorher herausgefiltert wuerde) formatiert ueber
`_THUNDER_LEVEL_LABEL` auf den Halbgeviertstrich "--" (U+2014, EM DASH) --
ebenfalls kein GSM-7-Zeichen. Reproduziert ueber `thunder_max` bei einem Ort
OHNE Gewitterrisiko (der Normalfall).

Scope (PO-Vorgabe): NUR der SMS-Pfad. Telegram und Mail behalten `°`/alle
Zeichen unveraendert (eigene Formatierung, eigene Budget-Realitaet -- Telegram
4096 Zeichen, Mail HTML). Das zentrale `unit`-Feld im Katalog (`metric_catalog.
py`) wird NICHT geaendert (Mail/Telegram lesen es weiterhin korrekt) -- die
Umwandlung sitzt ausschliesslich dort, wo die SMS-Zelle gebaut wird
(`comparison.py:_sms_metric_cell`).

QA-Runde (F001, HIGH): der urspruengliche Waechter waehlte ALLE 26 Groessen
auf einmal -- das Budget lief dabei IMMER ueber, `_sms_location_part`
schneidet dann von HINTEN Zellen weg. 12 von 26 Groessen (u.a. ausgerechnet
`wind_chill_min/max`, `dewpoint_avg`, `wind_direction_avg` -- alle drei
haengen `°`/`°C` an) fielen dadurch NIE in den geprueften Text. Beleg per
Mutation (`_PRECIP_TYPE_LABEL["RAIN"] = "Regen…"`): der alte Test blieb
gruen. `test_every_compare_metric_renders_unclipped_and_gsm7_clean` ersetzt
ihn -- jede Groesse EINZELN (kein Ueberlauf moeglich) plus eine
Vollstaendigkeitsliste, die am Ende gegen die volle 26er-Menge geprueft wird.

QA-Runde (Nachbarbefund): die GSM-7-Extension-Tabelle (Zirkumflex, geschweifte
und eckige Klammern, Tilde, Pipe, Backslash, Form-Feed, Euro-Zeichen) ist
kodierbar, kostet aber ZWEI Septets -- die 153er-Budget-Herleitung nimmt
EINS an. `_GSM7_CHARSET` schliesst die Extension-Tabelle deshalb bewusst
AUS (s. `_GSM7_EXTENDED_TWO_SEPTET_CHARS`), obwohl sie technisch
GSM-7-kodierbar waere.

Ortsnamen-Ausnahme (PO verlangt sichtbare Begruendung, falls noetig): Orts-
namen sind Freitext-Nutzerdaten (`SavedLocation.name`) -- der Renderer darf
sie nicht verfaelschen oder transliterieren, das waere Datenverlust an
Nutzereingaben. Dieser Waechter prueft deshalb bewusst nur die vom RENDERER
SELBST erzeugten Textbausteine (Kopf, Kuerzel, Werte, Trennzeichen, Ueberlauf-
/Warnhinweise) mit ASCII-reinen Test-Ortsnamen -- ein Nutzer, der einen
GSM-7-fremden Ortsnamen speichert (z.B. Emoji), erzwingt UCS-2 fuer SEINE
Vergleichs-SMS; das ist eine bekannte, hier bewusst NICHT behobene Folge von
Freitext-Ortsnamen, keine Renderer-Regression.

KEINE Mocks: echte `LocationResult`/`SavedLocation`/`OfficialAlert`-Objekte,
echter Renderer-Aufruf.
"""
from __future__ import annotations

from datetime import date, datetime

from app.models import ForecastDataPoint, PrecipType, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_compare_sms
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from services.official_alerts.models import OfficialAlert
from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS

TARGET_DATE = date(2026, 7, 30)
CREATED_AT = datetime(2026, 7, 30, 8, 0)

ALL_26_RENDERER_IDS = list(dict.fromkeys(FRONTEND_TO_RENDERER_METRIC_ID.values()))

# ---------------------------------------------------------------------------
# GSM 03.38 Default Alphabet + Extension Table (3GPP TS 23.038) -- der volle
# 7-Bit-Zeichensatz, den eine SMS ohne UCS-2-Umschaltung nutzen darf. Quelle:
# GSM 03.38 / 3GPP TS 23.038 Abschnitt 6.2.1 (Default Alphabet) + 6.2.1.1
# (Extension Table). Zeichen der Extension-Tabelle kosten beim Versand ZWEI
# Septets (ESC-Sequenz) -- fuer die Zeichensatz-PRUEFUNG selbst zaehlt nur,
# ob das Zeichen ueberhaupt GSM-7-kodierbar ist, nicht der Septet-Preis.
# ---------------------------------------------------------------------------
_GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅå"
    "Δ_ΦΓΛΩΠΨΣΘΞÆæßÉ"
    " !\"#¤%&'()*+,-./"
    "0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

# 128 Codepunkte (0x00-0x7F) minus ESC (0x1B, kein eigenes Zeichen, leitet
# nur zur Extension-Tabelle um) = 127 druckbare/Steuer-Zeichen.
assert len(_GSM7_BASIC) == len(set(_GSM7_BASIC)) == 127, (
    f"GSM7-Basisalphabet-Tabelle falsch abgetippt oder mit Duplikaten: "
    f"erwartet 127 verschiedene Zeichen, gezaehlt {len(_GSM7_BASIC)} "
    f"({len(set(_GSM7_BASIC))} verschieden)."
)

# Adversary-Fund Runde 6 (Nachbarbefund, PO-Auftrag 2026-07-30): die
# Extension-Tabelle (Form-Feed, ^ { } \ [ ~ ] | €) ist zwar GSM-7-KODIERBAR,
# kostet beim Versand aber ZWEI Septets je Zeichen (ESC-Fluchtsequenz) --
# die 153er-Budget-Herleitung (channel_layout.py) geht von GENAU EINEM
# Septet je Zeichen aus. Ein einziges Extension-Zeichen wuerde also STILL
# die 153-Zeichen-Zusage verletzen (real weniger Platz als angenommen), ohne
# dass eine reine "ist GSM-7-kodierbar?"-Pruefung das saehe. Einfacher und
# sicherer als die Budget-Rechnung um eine Doppelzaehlung zu erweitern: der
# Waechter LEHNT diese Zeichen ab, obwohl sie technisch GSM-7-kodierbar sind
# -- nicht weil sie unzulaessig waeren, sondern weil sie die
# Ein-Septet-Annahme des Budgets verfaelschen. Aktuell emittiert kein
# Compare-SMS-Renderer-Baustein eines davon; diese Konstante dokumentiert
# nur, WAS ausgeschlossen ist (nicht Teil von `_GSM7_CHARSET`).
_GSM7_EXTENDED_TWO_SEPTET_CHARS = "\x0c^{}\\[~]|€"

_GSM7_CHARSET = frozenset(_GSM7_BASIC)  # OHNE Extension-Tabelle, s.o.


def _first_non_gsm7_char(text: str) -> str | None:
    """Erstes Zeichen in `text`, das NICHT im GSM-7-Zeichensatz steht, oder
    `None`, wenn der gesamte Text GSM-7-kodierbar ist."""
    for ch in text:
        if ch not in _GSM7_CHARSET:
            return ch
    return None


def assert_gsm7_clean(text: str, context: str) -> None:
    bad = _first_non_gsm7_char(text)
    assert bad is None, (
        f"GSM-7-Verstoss in {context}: Zeichen {bad!r} (U+{ord(bad):04X}) ist "
        f"nicht im GSM-7-Zeichensatz (GSM 03.38) -- die SMS wechselt dadurch "
        f"in UCS-2 (67 statt 153 Zeichen je Teil bei Verkettung, 3GPP TS "
        f"23.040) -- STILLE Kostenverdopplung. Text: {text!r}"
    )


def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.26, lon=11.39, elevation_m=600)


def _dp(hour: int, *, precip_type: "PrecipType | None" = None) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour),
        t2m_c=15.0, wind10m_kmh=10.0, wind_direction_deg=180, gust_kmh=15.0,
        precip_1h_mm=0.0, cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
        visibility_m=10000, humidity_pct=70, dewpoint_c=8.0,
        pressure_msl_hpa=1013.0, cape_jkg=1500.0, freezing_level_m=1200,
        snowfall_limit_m=1300, wind_chill_c=12.0, cloud_low_pct=10,
        cloud_mid_pct=20, cloud_high_pct=30, precip_type=precip_type,
    )


def _loc_result(
    name: str, *, thunder: ThunderLevel = ThunderLevel.NONE,
    precip_type: "PrecipType | None" = None,
    alerts: list[OfficialAlert] | None = None,
) -> LocationResult:
    """Ort mit Werten fuer ALLE 26 Compare-Groessen -- ASCII-reiner Ortsname
    (s. Moduldocstring "Ortsnamen-Ausnahme"). `wind_direction_avg`/
    `wind_chill_min`/`wind_chill_max`/`cloud_low_avg`/`cloud_mid_avg`/
    `cloud_high_avg` sind "Klasse A" (eigenes `LocationResult`-Feld, nicht aus
    `hourly_data` abgeleitet, s. `compare_metric_ids.py`-Kopfkommentar) --
    ohne sie waeren `wind_direction_avg`/`wind_chill_min`/`wind_chill_max`
    nie pruefbar (F001-Vollstaendigkeitsanspruch)."""
    return LocationResult(
        location=_loc("a", name),
        temp_max=33.0, temp_min=17.0, wind_max=34.0, gust_max=40.0,
        snow_depth_cm=0.0, snow_new_cm=0.0, precip_sum_mm=0.3, pop_max_pct=40,
        thunder_level_max=thunder, visibility_min_m=8000, uv_index_max=7.0,
        cloud_avg=46, sunny_hours=5,
        wind_direction_avg=180, wind_chill_min=8.0, wind_chill_max=18.0,
        cloud_low_avg=10, cloud_mid_avg=20, cloud_high_avg=30,
        hourly_data=[_dp(h, precip_type=precip_type) for h in range(24)],
        official_alerts=alerts or [],
    )


def _result(locations: list[LocationResult]) -> ComparisonResult:
    return ComparisonResult(
        locations=locations, time_window=(0, 23), target_date=TARGET_DATE,
        created_at=CREATED_AT,
    )


# ---------------------------------------------------------------------------
# Haupt-Waechter -- RED-Grund heute: `format_value("temperature", ...,
# style="plain")` haengt "°C" an (`temp_max`/`temp_min`/`wind_chill_*`/
# `dewpoint_avg`), `wind_direction_avg`s eigenes Lambda haengt blosses "°" an
# -- beides GSM-7-fremd. Zusaetzlich formatiert `ThunderLevel.NONE` (echter
# Wert, kein fehlender) auf den GSM-7-fremden Halbgeviertstrich "--".
#
# Adversary-Fund F001 (QA-Runde, #1362 S5b): eine Auswahl ALLER 26 Groessen
# ueberlaeuft das Budget IMMER (s. AC-3) -- `_sms_location_part` schneidet
# dann von HINTEN Zellen weg. Bei 26 gewaehlten Groessen bleiben nur die
# vordersten ~14-20 tatsaechlich im Text stehen; der Rest (u.a. ausgerechnet
# `wind_chill_min/max`, `dewpoint_avg`, `wind_direction_avg` -- alle drei
# haengen `°`/`°C` an) wird NIE gerendert und damit NIE geprueft. Beleg per
# Mutation: `_PRECIP_TYPE_LABEL["RAIN"] = "Regen…"` liess den alten Test
# gruen, weil `precip_type` in der 26er-Auswahl in den Ueberlauf fiel, waehrend
# `render_compare_sms(..., enabled_metrics=["precip_type"])` das Fremdzeichen
# unsaniert zeigte. Deshalb PRUEFT DIESER TEST JEDE DER 26 GROESSEN EINZELN
# (Budget bei einer Groesse garantiert nicht ueberlaufen) UND fuehrt eine
# Vollstaendigkeitsliste (`checked`), die am Ende gegen die volle 26er-Menge
# geprueft wird -- fehlt eine Groesse in der Schleife (z.B. weil sie
# versehentlich uebersprungen wird), schlaegt der Test fehl, statt einfach
# weniger zu pruefen.
# ---------------------------------------------------------------------------

def test_every_compare_metric_renders_unclipped_and_gsm7_clean():
    """Jede der 26 Compare-Groessen wird EINZELN ausgewaehlt (garantiert kein
    Metrik-Ueberlauf bei nur einer Groesse) und muss dabei (a) tatsaechlich als
    VOLLSTAENDIGE Zelle im Text erscheinen -- sonst waere die Pruefung selbst
    luckenhaft -- und (b) GSM-7-rein sein. `thunder_max`/`precip_type`
    zusaetzlich ueber alle Gewitterstufen/Niederschlagsarten, weil deren
    Formatierung vom jeweiligen Enum-Wert abhaengt (s. `ThunderLevel.NONE`-
    Fund oben)."""
    from output.renderers.comparison import _sms_metric_cell

    checked: set[str] = set()

    def _check_one(loc: LocationResult, metric_id: str, context: str) -> None:
        cell = _sms_metric_cell(loc, metric_id)
        assert cell is not None, (
            f"Testaufbau/Produktion defekt: {metric_id!r} liefert an diesem "
            "Ort keine Zelle (kein Wert oder kein Kuerzel) -- der "
            "Vollstaendigkeits-Anspruch dieses Waechters (JEDE Groesse "
            "mindestens einmal ungekuerzt pruefen) waere sonst verletzt."
        )
        sms = render_compare_sms(_result([loc]), enabled_metrics=[metric_id])
        assert cell in sms, (
            f"Zelle {cell!r} fuer {metric_id!r} fehlt im Einzelauswahl-"
            f"Render {sms!r} ({context}) -- unerwarteter Verlust bei einer "
            "einzeln ausgewaehlten Groesse. Vollstaendigkeits-Anspruch verletzt."
        )
        assert_gsm7_clean(sms, f"SMS ({metric_id}, {context})")
        checked.add(metric_id)

    loc_default = _loc_result("Innsbruck")
    for metric_id in ALL_26_RENDERER_IDS:
        if metric_id in ("thunder_max", "precip_type"):
            continue  # unten mit allen Enum-Zustaenden geprueft
        _check_one(loc_default, metric_id, "Standardzustand")

    # thunder_max/precip_type unabhaengig durchprobiert (eigene Enum-
    # Dimensionen, kein Kreuzprodukt noetig): jede Gewitterstufe bzw.
    # Niederschlagsart hat ihren eigenen `_fmt_*`-Zweig, der einzeln
    # sanitiert werden muss.
    for thunder in (ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH):
        loc = _loc_result("Innsbruck", thunder=thunder)
        _check_one(loc, "thunder_max", f"thunder={thunder.value}")

    for precip_type in (
        PrecipType.RAIN, PrecipType.SNOW, PrecipType.MIXED,
        PrecipType.FREEZING_RAIN,
    ):
        loc = _loc_result("Innsbruck", precip_type=precip_type)
        _check_one(loc, "precip_type", f"precip_type={precip_type.value}")

    missing = set(ALL_26_RENDERER_IDS) - checked
    assert not missing, (
        f"Vollstaendigkeits-Anspruch verletzt: {sorted(missing)} wurden NIE "
        "ungekuerzt geprueft -- dieser Waechter deckt dann nicht mehr alle "
        "26 Groessen ab (genau der F001-Fund)."
    )


def test_gsm7_extension_table_chars_are_rejected_despite_being_gsm7_encodable():
    """Adversary-Fund Runde 6 (Nachbarbefund): Extension-Tabellen-Zeichen
    sind GSM-7-kodierbar, kosten aber zwei Septets -- die 153er-Budget-
    Herleitung nimmt EIN Septet je Zeichen an. Der Waechter muss sie deshalb
    als GSM-7-fremd BEHANDELN (s. Kommentar an `_GSM7_EXTENDED_TWO_SEPTET_
    CHARS`), sonst koennte ein technisch "GSM-7-kodierbares" Zeichen die
    Budget-Zusage unbemerkt verfaelschen."""
    for ch in _GSM7_EXTENDED_TWO_SEPTET_CHARS:
        assert ch not in _GSM7_CHARSET, (
            f"Extension-Zeichen {ch!r} (U+{ord(ch):04X}) ist faelschlich im "
            "akzeptierten GSM-7-Zeichensatz -- es kostet zwei Septets."
        )
        assert _first_non_gsm7_char(ch) == ch, (
            f"assert_gsm7_clean muss Extension-Zeichen {ch!r} als Verstoss "
            "erkennen, tut es aber nicht."
        )


def test_sms_with_official_alert_marker_stays_gsm7_clean_for_every_hazard():
    """Der `!`-Warnmarker (alle neun Katalog-Gefahren, Stufe rot) darf kein
    GSM-7-fremdes Zeichen einschleusen."""
    for hazard in HAZARD_SMS_SYMBOLS:
        alert = OfficialAlert(
            source="meteoalarm", hazard=hazard, level=4, label=hazard,
            valid_from=datetime(2026, 7, 30, 10, 0),
            valid_to=datetime(2026, 7, 30, 14, 0), region_label="Region",
        )
        loc = _loc_result("Innsbruck", alerts=[alert])
        sms = render_compare_sms(_result([loc]))
        assert_gsm7_clean(sms, f"SMS (amtliche Warnung {hazard!r})")


def test_sms_location_and_metric_overflow_stay_gsm7_clean():
    """Der Orts-Ueberlauf (' +k Orte') und der Metrik-Ueberlauf ('+N') selbst
    duerfen kein GSM-7-fremdes Zeichen enthalten -- inklusive der langen
    26-Groessen-Auswahl, die beide Ueberlaeufe gleichzeitig ausloest (s.
    test_compare_sms_kuerzel.py::test_metric_overflow_and_location_overflow_...)."""
    loc_a = _loc_result("Andermatt Talstation")
    loc_b = _loc_result("Zermatt")
    sms = render_compare_sms(
        _result([loc_a, loc_b]), enabled_metrics=ALL_26_RENDERER_IDS,
    )
    assert_gsm7_clean(sms, "SMS (Orts- + Metrik-Ueberlauf gleichzeitig)")


def test_sms_degenerate_long_name_truncation_stays_gsm7_clean():
    """Die Wortgrenzen-Kuerzung im Degenerationsfall (extrem langer Ortsname,
    ASCII) haengt "..." (drei ASCII-Punkte) an -- kein Unicode-Auslassungs-
    zeichen."""
    long_name = "Sankt" + "Wolfgangimsalzkammergut" * 20
    loc = _loc_result(long_name)
    sms = render_compare_sms(_result([loc]), enabled_metrics=ALL_26_RENDERER_IDS)
    assert_gsm7_clean(sms, "SMS (Degenerationsfall, extrem langer Ortsname)")


def test_head_and_error_location_text_are_gsm7_clean():
    """Kopf ("Vergleich DD.MM.:") und Fehler-Ort ("<Name> n/a") sind reiner
    ASCII-Text -- Regressionsschutz, falls sich das je aendert."""
    loc_ok = _loc_result("Andermatt")
    loc_err = LocationResult(location=_loc("b", "Zermatt"), error="API-Fehler")
    sms = render_compare_sms(_result([loc_ok, loc_err]))
    assert_gsm7_clean(sms, "SMS (Kopf + Fehler-Ort)")


def test_aggregation_sign_characters_are_gsm7_clean():
    """Das Auswertungszeichen `+`/`-` (Hoechst-/Tiefstwert derselben Groesse,
    z.B. `temp_max`/`temp_min`) ist bereits GSM-7-basisch (0x2B/0x2D) --
    Regressionsschutz, dass diese Kombination nicht doch ein anderes Zeichen
    einschleust."""
    loc = _loc_result("Innsbruck")
    sms = render_compare_sms(
        _result([loc]), enabled_metrics=["temp_max", "temp_min"],
    )
    assert "D+ " in sms and "D- " in sms, f"Testaufbau defekt: {sms!r}"
    assert_gsm7_clean(sms, "SMS (Auswertungszeichen +/-)")


# ---------------------------------------------------------------------------
# Zeichenbudget -- PO-Entscheidung 2026-07-30 (Runde 5): 140 war die BYTE-
# Grenze einer SMS-PDU (3GPP TS 23.038/23.040), keine Zeichengrenze. Dieser
# Test leitet den verkettungssicheren GSM-7-Wert aus den ROHGROESSEN her
# (140 Byte Payload, 6 Byte Verkettungs-Header, 7 Bit je GSM-7-Zeichen) und
# prueft `CHANNEL_LIMITS["sms"]["max_chars"]` GEGEN DIESE HERLEITUNG -- ein
# Test, der nur `== 153` gegen die Konstante selbst prueft, waere wertlos
# (PO-Auftrag woertlich).
# ---------------------------------------------------------------------------

def test_sms_char_budget_matches_gsm7_concatenated_derivation():
    """Der SMS-Zeichenbudget-Wert muss dem verkettungssicheren GSM-7-Wert
    entsprechen -- gilt NUR, weil der Compare-SMS-Text per Waechter (s. oben)
    GSM-7-rein ist (Ortsnamen-Ausnahme s. Moduldocstring)."""
    from output.renderers.channel_layout import CHANNEL_LIMITS

    sms_pdu_payload_bytes = 140       # 3GPP TS 23.038/23.040
    concat_udh_header_bytes = 6       # User-Data-Header je Teil bei Verkettung
    gsm7_bits_per_char = 7
    bits_per_byte = 8

    usable_bytes_per_part = sms_pdu_payload_bytes - concat_udh_header_bytes
    derived_chars_per_part = (usable_bytes_per_part * bits_per_byte) // gsm7_bits_per_char

    actual = CHANNEL_LIMITS["sms"]["max_chars"]
    assert actual == derived_chars_per_part, (
        f"SMS-Zeichenbudget ({actual}) weicht von der GSM-7-Verkettungs-"
        f"Herleitung ab: floor(({sms_pdu_payload_bytes} - "
        f"{concat_udh_header_bytes}) * {bits_per_byte} / {gsm7_bits_per_char}) "
        f"= {derived_chars_per_part}."
    )


def test_sms_budget_lets_more_metrics_through_than_the_old_140():
    """Nachweis, dass die Anhebung auf 153 tatsaechlich mehr Inhalt traegt:
    dieselbe Beispielzeile (14 grosszuegig gewaehlte Groessen -- reicht fuer
    einen Metrik-Ueberlauf bei BEIDEN Budgets, s. `test_compare_sms_kuerzel.
    py::test_sms_cuts_whole_metrics_not_mid_token_...`) zeigt bei Budget 140
    (dem ALTEN Wert) weniger Zellen als bei 153 (dem NEUEN) -- sonst waere die
    Anhebung folgenlos."""
    from output.renderers.comparison import _sms_location_part, _sms_metric_cell

    name = "Andermatt Talstation"
    loc = LocationResult(
        location=_loc("a", name),
        temp_max=16.4, wind_max=15.0, gust_max=20.0, snow_depth_cm=20.0,
        snow_new_cm=4.0, precip_sum_mm=5.0, pop_max_pct=30,
        thunder_level_max=ThunderLevel.MED, visibility_min_m=8000,
        uv_index_max=5.0,
        # `_dp()` traegt Feuchte/CAPE/Nullgradgrenze/Schneefallgrenze bereits
        # standardmaessig (s. Definition oben) -- keine weitere Fixture noetig.
        hourly_data=[_dp(h) for h in range(24)],
    )
    enabled = [
        "temp_max", "wind_max", "gust_max", "precip_sum", "pop_max",
        "thunder_max", "visibility_min", "uv_max", "snow_depth_cm",
        "snow_new_cm", "humidity_avg", "cape_max", "freezing_level",
        "snowfall_limit",
    ]
    head_len = len("Vergleich 30.07.:") + 1  # Kopf + ein Trennzeichen
    part_140 = _sms_location_part(loc, enabled, budget=140 - head_len)
    part_153 = _sms_location_part(loc, enabled, budget=153 - head_len)

    def _shown_metric_count(part: str) -> int:
        """Zahl der ausgewaehlten Groessen, deren VOLLSTAENDIGE Kuerzel-Wert-
        Zelle im Ortsteil steht (nicht ueber den `+N`-Ueberlaufhinweis
        verdraengt) -- dieselbe Zellberechnung wie die Produktion selbst."""
        cells = (_sms_metric_cell(loc, mid) for mid in enabled)
        return sum(1 for cell in cells if cell is not None and cell in part)

    count_140 = _shown_metric_count(part_140)
    count_153 = _shown_metric_count(part_153)

    assert count_153 > count_140, (
        f"Die Anhebung von 140 auf 153 ist FOLGENLOS oder sogar schlechter "
        f"fuer diese Beispielzeile: {count_140} Groessen bei Budget 140 "
        f"({part_140!r}) vs. {count_153} bei 153 ({part_153!r})."
    )
