"""Ein Kuerzel je Groesse: Telegram spricht dieselbe Sprache wie die SMS.

Issue #1719 Scheibe S4 — Spec docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md
(AC-1, AC-2, AC-3). PO woertlich (2026-08-12): "Warum gibt es ein extra
Telegram Kuerzel? Das will ich nicht!"

Heute pflegt der Katalog ZWEI Kuerzel je Groesse von Hand: ``compact_label``
(Telegram) und ``sms_code`` (Register). Gemessen sind 11 von 25 Groessen
auseinandergelaufen — Luftdruck heisst in Telegram ``P``, in der SMS ``HP``;
die Regenwahrscheinlichkeit ``P%`` gegen ``PR``. Niemand haelt die beiden
Tabellen synchron, also driften sie.

**Das Soll-Kuerzel ist das, was die Trip-SMS TATSAECHLICH sendet** — also
``SMS_MULTI_SYMBOLS_BY_METRIC`` (Vorrang) bzw. ``SMS_SYMBOL_BY_METRIC``, beide
in ``output/renderers/sms_trip.py``. Nicht ``sms_code`` allein: bei
``temperature_night`` fuehrt das Register ``TN``, gesendet wird aber ``N``
(Spec, Abschnitt 1, Zeile "Nacht-Tiefsttemperatur ... kuenftig N"), und bei
``fresh_snow`` fuehrt das Register ``NS``, gesendet wird ``NS24+``. Genau diese
zwei Faelle sind der Kern des gemeldeten Defekts ("das Badge nennt ein Kuerzel,
das in keiner Trip-SMS auftaucht"), sie duerfen also nicht wegdefiniert werden.
Fuer die uebrigen 23 Groessen faellt beides zusammen.

Zwei benannte Ausnahmen bleiben (Spec Abschnitt 1): ``temperature`` (``T``) und
``wind_chill`` (``TF``). Das Register fuehrt dort TAGESAUSWERTUNGEN (``K``/``D``
bzw. ``FK``/``FD``/``WC``); die Telegram-Zelle zeigt einen STUNDENWERT — ein
Spaltenkopf "Tageshoechst" waere dort eine falsche Aussage.

KEINE Mocks, KEIN Dateiinhalt-Check: echte Model-Objekte, echter Renderaufruf
(``render_telegram_bubbles``), Nutzersicht auf den Bubble-Text. Die Erwartung
wird aus den SMS-Tabellen GERECHNET, nicht abgetippt (Spec AC-1: "gegen
SMS_SYMBOL_BY_METRIC gerechnet").

Ausfuehren:
  uv run pytest tests/unit/test_telegram_kuerzel_folgt_register.py
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import pytest

_TZ = ZoneInfo("Europe/Berlin")

# Mindestlaenge einer Ausnahme-Begruendung. Muster: die `gz-eigenstaendig`-/
# `gz-main-path`-Ausnahmen der Commit-Waechter (#1409/#1481 B) verlangen
# ebenfalls 15 sinnvolle Zeichen — eine Ausnahme ohne Satz ist keine.
_MIN_BEGRUENDUNG = 15

# Kandidaten-Namen fuer die benannte Ausnahmeliste im Katalog. Der erste
# gefundene gewinnt; `COMPACT_LABEL_EXCEPTIONS` ist der vorgeschlagene Name.
# Die Liste gehoert laut Spec ("Implementation Details") NEBEN die
# `MetricDefinition` in `app/metric_catalog.py` — eine Quelle, nicht zwei.
_AUSNAHMELISTE_NAMEN = (
    "COMPACT_LABEL_EXCEPTIONS",
    "COMPACT_LABEL_AUSNAHMEN",
    "TELEGRAM_KUERZEL_AUSNAHMEN",
    "_COMPACT_LABEL_EXCEPTIONS",
)


# ═══════════════════════════════════════════════════════════════════════════
# Soll-Kuerzel: gerechnet aus den Tabellen, aus denen die SMS wirklich rendert
# ═══════════════════════════════════════════════════════════════════════════

def _soll_kuerzel(metric_id: str) -> Optional[str]:
    """Das Kuerzel, das die Trip-SMS fuer ``metric_id`` tatsaechlich sendet.

    Dieselbe Aufloesung wie ``/api/sms-symbols::_symbols_for``
    (api/routers/config.py): MULTI hat Vorrang, ``rstrip(":")`` entfernt die
    Grammatik-Trennung ("TH:" -> "TH"). Bei Mehrfach-Token gilt das ERSTE als
    Kuerzel der Groesse — die weiteren benennen Auswertungen (Tiefst/Hoechst).
    """
    from output.renderers.sms_trip import (
        SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC,
    )
    if metric_id in SMS_MULTI_SYMBOLS_BY_METRIC:
        return SMS_MULTI_SYMBOLS_BY_METRIC[metric_id][0].rstrip(":")
    if metric_id in SMS_SYMBOL_BY_METRIC:
        return SMS_SYMBOL_BY_METRIC[metric_id].rstrip(":")
    return None


def _ausnahmeliste() -> Optional[dict[str, str]]:
    """Die benannte Ausnahmeliste aus dem Katalog, oder None wenn es keine gibt."""
    import app.metric_catalog as katalog
    for name in _AUSNAHMELISTE_NAMEN:
        wert = getattr(katalog, name, None)
        if isinstance(wert, dict):
            return wert
    return None


def pruefe_kuerzel(
    eintraege: list[tuple[str, str, Optional[str]]],
    ausnahmen: dict[str, str],
) -> list[str]:
    """Reine Pruefregel — liefert je Verstoss eine lesbare Zeile.

    ``eintraege``: (metric_id, compact_label, soll_kuerzel). Als eigene
    Funktion, damit derselbe Wachhund unten an einem KUENSTLICHEN Katalog-
    Eintrag vorgefuehrt werden kann: ein Waechter, der nur auf dem heutigen
    Bestand gruen ist, bewacht nichts (Mutations-Gegenprobe).
    """
    verstoesse: list[str] = []
    for metric_id, compact_label, soll in eintraege:
        if soll is None:
            continue  # Groesse ohne SMS-Kuerzel — nichts zu vereinheitlichen
        if metric_id in ausnahmen:
            begruendung = str(ausnahmen[metric_id]).strip()
            if len(begruendung) < _MIN_BEGRUENDUNG:
                verstoesse.append(
                    f"{metric_id}: steht in der Ausnahmeliste, aber ohne "
                    f"Begruendung (>= {_MIN_BEGRUENDUNG} Zeichen), war: "
                    f"{begruendung!r}"
                )
            continue
        if compact_label != soll:
            verstoesse.append(
                f"{metric_id}: Telegram sendet {compact_label!r}, die SMS "
                f"sendet {soll!r} — dieselbe Groesse, zwei Kuerzel. Entweder "
                f"gleichziehen oder mit Begruendung in die Ausnahmeliste."
            )
    return verstoesse


# ═══════════════════════════════════════════════════════════════════════════
# Fixture: ein echter Renderaufruf, keine Attrappe
# ═══════════════════════════════════════════════════════════════════════════

def _segment():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=46.5, lon=8.1, elevation_m=1800.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=46.6, lon=8.2, elevation_m=2400.0,
                           distance_from_start_km=6.0),
        start_time=datetime(2026, 7, 3, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 3, 10, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=6.0, ascent_m=600.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 7, 3, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0, interp="point_grid",
    )
    dps = [
        ForecastDataPoint(ts=datetime(2026, 7, 3, h, 0, tzinfo=timezone.utc))
        for h in (6, 7, 8, 9)
    ]
    agg = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=14.0, wind_max_kmh=8.0,
        precip_sum_mm=0.0, cloud_avg_pct=40,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=dps),
        aggregated=agg, fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _dc(metric_ids: list[str]):
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    return UnifiedWeatherDisplayConfig(
        trip_id="e2e-1719-s4",
        metrics=[
            MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
            for i, m in enumerate(metric_ids)
        ],
        updated_at=datetime.now(timezone.utc),
    )


# Werte je col_key des Katalogs — bewusst schmal, damit die 32-Zeichen-Grenze
# der Telegram-Tabelle (`narrow._TG_TABLE_WIDTH`) die Kopfzeile nicht umbricht.
_ZELLWERTE = {
    "humidity": 60, "cloud": 40, "visibility": 8000, "pressure": 1013,
    "freeze_lvl": 3200, "temp": 14, "felt": 12,
}


def _tabellenkopf(metric_ids: list[str]) -> list[str]:
    """Rendert das Briefing und liefert die Spaltenkoepfe der Stundentabelle."""
    from output.renderers.narrow import render_telegram_bubbles

    rows = [
        {"time": f"{h:02d}", **_ZELLWERTE} for h in (6, 7, 8, 9)
    ]
    bubbles = render_telegram_bubbles(
        segments=[_segment()], seg_tables=[rows], dc=_dc(metric_ids),
        report_type="evening", tz=_TZ, trip_name="Kuerzel S4",
    )
    tabellen = [b.text for b in bubbles if "<pre>" in b.text]
    assert tabellen, (
        "Kein <pre>-Tabellenblock im Briefing — der Testaufbau erreicht den "
        f"geprueften Renderpfad nicht. Bubbles: {[b.text[:40] for b in bubbles]}"
    )
    kopfzeile = tabellen[0].split("<pre>", 1)[1].lstrip("\n").splitlines()[0]
    kopf = kopfzeile.split()
    assert len(kopf) == 1 + len(metric_ids), (
        f"Kopfzeile {kopfzeile!r} hat {len(kopf)} statt {1 + len(metric_ids)} "
        "Spalten — vermutlich umgebrochen. Testaufbau anpassen (schmalere "
        "Zellwerte oder weniger Metriken), nicht die Erwartung lockern."
    )
    assert kopf[0] == "Zt", f"Erste Spalte ist die Zeit, war: {kopf!r}"
    return kopf[1:]


def _kurzuebersicht(metric_ids: list[str]) -> str:
    from output.renderers.narrow import render_telegram_bubbles

    rows = [{"time": f"{h:02d}", **_ZELLWERTE} for h in (6, 7, 8, 9)]
    bubbles = render_telegram_bubbles(
        segments=[_segment()], seg_tables=[rows], dc=_dc(metric_ids),
        report_type="evening", tz=_TZ, trip_name="Kuerzel S4",
    )
    return next(b.text for b in bubbles if "Kurzübersicht" in b.text)


# ═══════════════════════════════════════════════════════════════════════════
# AC-1 — die Stundentabelle traegt die SMS-Kuerzel
# ═══════════════════════════════════════════════════════════════════════════

_AC1_IDS = ["humidity", "cloud_total", "visibility", "pressure", "freezing_level"]


def test_telegram_spaltenkoepfe_tragen_die_kuerzel_der_sms():
    """AC-1: Given ein Briefing mit Luftfeuchtigkeit, Bewoelkung, Sichtweite,
    Luftdruck und Nullgradgrenze / When die Telegram-Stundentabelle gerendert
    wird / Then tragen die Spaltenkoepfe genau die Kuerzel, die die SMS fuer
    diese Groessen sendet (heute: H/C/V/P/0G gegen HU/CT/VS/HP/NL)."""
    erwartet = [_soll_kuerzel(m) for m in _AC1_IDS]
    assert all(erwartet), f"Testaufbau: Groesse ohne SMS-Kuerzel in {_AC1_IDS}"

    kopf = _tabellenkopf(_AC1_IDS)
    assert kopf == erwartet, (
        "AC-1 FAIL: die Telegram-Stundentabelle spricht eine andere Sprache "
        f"als die SMS.\n  Telegram: {kopf}\n  SMS:      {erwartet}\n"
        "Der Nutzer liest in der SMS ein Kuerzel, das er in der Telegram-"
        "Tabelle nicht wiederfindet."
    )


def test_telegram_kurzuebersicht_traegt_die_kuerzel_der_sms():
    """AC-1, zweiter Wirkort: dieselbe Zusicherung fuer die Kurzuebersicht-
    Bubble (`narrow._overview_line`) — sie liest denselben `compact_label`,
    steht aber in einer anderen Bubble. Ein Fix nur an der Tabelle waere an
    der Stelle richtig, an der der Code steht, und falsch dort, wo er wirkt."""
    text = _kurzuebersicht(_AC1_IDS)
    zeilen_anfaenge = [
        z.split(" ", 1)[0] for z in text.splitlines() if z.strip()
    ]
    fehlend = [
        (m, _soll_kuerzel(m)) for m in _AC1_IDS
        if _soll_kuerzel(m) not in zeilen_anfaenge
    ]
    assert not fehlend, (
        "AC-1 FAIL (Kurzuebersicht): diese Groessen stehen dort NICHT unter "
        f"dem Kuerzel, das die SMS sendet: {fehlend}.\nGerendert:\n{text}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-3 — Temperatur und Gefuehlte Temperatur behalten ihr Stundenkuerzel
# ═══════════════════════════════════════════════════════════════════════════

def test_temperatur_und_gefuehlte_behalten_das_stundenkuerzel():
    """AC-3: Given Temperatur und Gefuehlte Temperatur / When die
    Stundentabelle gerendert wird / Then stehen dort weiterhin `T` und `TF` —
    NICHT `K`/`D` bzw. `FK`/`FD`/`WC`. Die Zelle zeigt einen Stundenwert; ein
    Kopf, der "Tagestiefst" bedeutet, waere dort eine falsche Aussage.

    Regressionsschutz: heute gruen, muss die Vereinheitlichung ueberleben."""
    kopf = _tabellenkopf(["temperature", "wind_chill"])
    assert kopf == ["T", "TF"], (
        f"AC-3 FAIL: Spaltenkoepfe {kopf} statt ['T', 'TF']. Die Ausnahme fuer "
        "Temperatur/Gefuehlte Temperatur ist bei der Vereinheitlichung "
        "verlorengegangen — die Zelle wuerde eine Tagesauswertung behaupten, "
        "zeigt aber einen Stundenwert."
    )


def test_ausnahmeliste_nennt_beide_temperaturen_mit_begruendung():
    """AC-3 Gegenprobe / AC-2: die beiden Ausnahmen stehen NAMENTLICH und mit
    Begruendung in einer Liste im Katalog — nicht als stiller Sonderfall im
    Renderer. Ohne diese Liste ist "compact_label darf nicht wegdriften"
    (Spec Abschnitt 2) nicht pruefbar."""
    ausnahmen = _ausnahmeliste()
    assert ausnahmen is not None, (
        "AC-2/AC-3 FAIL: `app.metric_catalog` fuehrt keine benannte "
        f"Ausnahmeliste (gesucht: {', '.join(_AUSNAHMELISTE_NAMEN)}). Solange "
        "es sie nicht gibt, ist jede Abweichung zwischen Telegram- und "
        "SMS-Kuerzel ununterscheidbar von einem Fluechtigkeitsfehler — genau "
        "so ist der heutige Zustand entstanden."
    )
    for metric_id in ("temperature", "wind_chill"):
        assert metric_id in ausnahmen, (
            f"AC-3 FAIL: '{metric_id}' fehlt in der Ausnahmeliste "
            f"(enthalten: {sorted(ausnahmen)})."
        )
        assert len(str(ausnahmen[metric_id]).strip()) >= _MIN_BEGRUENDUNG, (
            f"AC-3 FAIL: Ausnahme '{metric_id}' ohne Begruendung: "
            f"{ausnahmen[metric_id]!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AC-2 — der Waechter ueber den ganzen Katalog
# ═══════════════════════════════════════════════════════════════════════════

def test_kein_telegram_kuerzel_weicht_unbegruendet_von_der_sms_ab():
    """AC-2: Given der vollstaendige Metrik-Katalog / When Telegram-Kuerzel und
    SMS-Kuerzel jeder Groesse verglichen werden / Then sind sie identisch,
    ausser fuer die Groessen der benannten Ausnahmeliste."""
    from app.metric_catalog import get_all_metrics

    ausnahmen = _ausnahmeliste()
    assert ausnahmen is not None, (
        "AC-2 FAIL: keine benannte Ausnahmeliste im Katalog (gesucht: "
        f"{', '.join(_AUSNAHMELISTE_NAMEN)}) — ohne sie kann `compact_label` "
        "beim naechsten Katalog-Eintrag genauso wegdriften wie bisher."
    )
    eintraege = [
        (m.id, m.compact_label, _soll_kuerzel(m.id)) for m in get_all_metrics()
    ]
    verstoesse = pruefe_kuerzel(eintraege, ausnahmen)
    assert not verstoesse, (
        "AC-2 FAIL — dieselbe Groesse traegt zwei Kuerzel:\n  "
        + "\n  ".join(verstoesse)
    )


@pytest.mark.parametrize(
    "ausnahmen,soll_rot,warum",
    [
        ({}, True, "neuer Eintrag ohne Ausnahme muss auffallen"),
        ({"nebelbank": "kurz"}, True, "Ausnahme ohne Begruendung zaehlt nicht"),
        (
            {"nebelbank": "Telegram zeigt hier den Stundenwert, das Register "
                          "die Tagesauswertung"},
            False,
            "begruendete Ausnahme ist erlaubt",
        ),
    ],
)
def test_waechter_faengt_einen_neuen_katalogeintrag(ausnahmen, soll_rot, warum):
    """WERKZEUG-SELBSTTEST, KEIN AC-2-NACHWEIS — bitte nicht verwechseln.

    Geprueft wird ``pruefe_kuerzel`` (oben in DIESER Datei definiert), nicht
    der Produktivcode: ein KUENSTLICHER Katalog-Eintrag mit abweichendem
    `compact_label` und ohne begruendete Ausnahme muss den Waechter rot machen.
    Deshalb ist dieser Test heute gruen und bleibt es — er belegt kein
    Produktivverhalten.

    Sein Zweck ist die Gegenprobe zum eigentlichen AC-2-Waechter
    (``test_kein_telegram_kuerzel_weicht_unbegruendet_von_der_sms_ab``, rot):
    ohne ihn waere jener nur eine Momentaufnahme des heutigen Bestands — gruen,
    sobald jemand einmal aufgeraeumt hat, und blind fuer den naechsten Eintrag.
    Ein Waechter, der nur auf dem heutigen Bestand gruen ist, bewacht nichts."""
    kuenstlich = [("nebelbank", "NB", "FG")]
    verstoesse = pruefe_kuerzel(kuenstlich, ausnahmen)
    assert bool(verstoesse) is soll_rot, (
        f"Waechter-Gegenprobe fehlgeschlagen ({warum}): "
        f"Verstoesse={verstoesse}, erwartet rot={soll_rot}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-2, Grammatikformen (Adversary Runde 2, F004)
#
# Der Waechter oben rechnet BEIDE Seiten aus denselben Tabellen und ist
# gegenueber den Grammatik-Ausnahmen damit selbstbezueglich: entfernt man sie,
# aendern sich Soll UND Ist gleichzeitig, und er bleibt gruen. Gefangen wurde
# das bisher nur von einer thematisch fremden Datei
# (tests/tdd/test_sms_snow_symbols.py). Die Grammatikformen sind aber Teil der
# Kuerzel-Wahrheit, die S4 zusichert — der Nutzer liest 'NS24+' in seiner SMS
# und muss genau das im Editor wiederfinden. Deshalb hier, mit ausdruecklichen
# Sollwerten und Begruendung.
# ═══════════════════════════════════════════════════════════════════════════

_GRAMMATIKFORMEN = [
    ("thunder", "TH:", "der Doppelpunkt trennt die Gewitter-Stufe vom Kuerzel"),
    ("fresh_snow", "NS24+", "'24+' benennt das 24-Stunden-Fenster des Neuschnees"),
]


@pytest.mark.parametrize("metric_id,erwartet,grund", _GRAMMATIKFORMEN)
def test_grammatikform_ueberschreibt_das_register_kuerzel(metric_id, erwartet, grund):
    """AC-2: Given eine Groesse, deren gesendetes Kuerzel eine Grammatikform
    traegt / When das Kuerzel-Register aufgeloest wird / Then gilt die
    Grammatikform, NICHT das nackte Register-Kuerzel — sonst nennt die
    Oberflaeche ein Kuerzel, das in keiner Nachricht so vorkommt."""
    from app.metric_catalog import get_sms_code
    from output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC

    ist = SMS_SYMBOL_BY_METRIC[metric_id]
    assert ist == erwartet, (
        f"F004 FAIL ({metric_id}): die Kurzform sendet {ist!r}, erwartet ist "
        f"{erwartet!r} — {grund}. Wurde die Grammatik-Ausnahme entfernt, faellt "
        f"das Kuerzel auf das nackte Register zurueck und stimmt mit nichts "
        f"mehr ueberein, was der Nutzer wirklich liest."
    )
    assert ist != get_sms_code(metric_id), (
        f"F004 FAIL ({metric_id}): Grammatikform und Register-Kuerzel sind "
        f"identisch ({ist!r}). Dann ist die Ausnahme wirkungslos geworden — "
        f"entweder ist sie verschwunden, oder das Register wurde ihr "
        f"angeglichen. Beides macht diesen Wachhund blind."
    )


def test_neuschnee_traegt_die_grammatikform_auch_in_telegram():
    """AC-1/AC-2: Given Neuschnee / When die Telegram-Stundentabelle gerendert
    wird / Then steht dort 'NS24+' — dasselbe, was die SMS sendet. Ohne die
    Grammatik-Ausnahme stuende dort 'NS', ein Kuerzel, das in keiner Nachricht
    vorkommt (Spec-Tabelle, Zeile 'Neuschnee NS -> NS24+')."""
    kopf = _tabellenkopf(["fresh_snow"])
    assert kopf == ["NS24+"], (
        f"F004 FAIL: Spaltenkopf {kopf} statt ['NS24+']. Die Telegram-Tabelle "
        "nennt eine Groesse anders, als die SMS sie sendet."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-9 — eine Groesse ohne Kuerzel bekommt keines angedichtet
#
# Der Editor speist die Kurzform-Marke aus /api/sms-symbols (Spec Abschnitt 3).
# Damit "erscheint keine leere oder erfundene Marke, sondern gar keine"
# ueberhaupt erreichbar ist, darf schon die Antwort keine leeren und keine
# erfundenen Eintraege enthalten. Aufruf der ECHTEN Endpoint-Funktion, kein
# Netz, kein Mock.
# ═══════════════════════════════════════════════════════════════════════════

def test_kuerzel_katalog_erfindet_keine_und_liefert_keine_leeren():
    """AC-9: Given eine Groesse ohne Registereintrag (`confidence`, seit #710
    nicht waehlbar und ohne `sms_code`) / When der Kuerzel-Katalog abgerufen
    wird / Then fehlt sie dort ganz — statt mit einer leeren Marke zu
    erscheinen. Und keine gelistete Groesse traegt ein leeres Kuerzel."""
    from api.routers.config import get_sms_symbols

    antwort = get_sms_symbols()
    eintraege = {e["metric_id"]: e["sms_symbols"] for e in antwort["metrics"]}

    leer = {
        mid: syms for mid, syms in eintraege.items()
        if not syms or any(not str(s).strip() for s in syms)
    }
    assert not leer, (
        f"AC-9 FAIL: /api/sms-symbols liefert leere Kuerzel: {leer}. Der Editor "
        "wuerde daraus eine Marke 'Kurzform' ohne Inhalt bauen."
    )
    assert "confidence" not in eintraege, (
        "AC-9 FAIL: 'confidence' hat keinen Registereintrag und darf im "
        "Kuerzel-Katalog nicht auftauchen — sonst erfindet die Oberflaeche "
        f"eine Marke fuer eine Groesse ohne Kuerzel. Enthalten: {sorted(eintraege)}"
    )
