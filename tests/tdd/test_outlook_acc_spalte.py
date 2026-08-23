"""TDD RED — #2098 Befund B/C: ACC-Spalte im konfigurierbaren Ausblick-Zweig.

SPEC: docs/specs/modules/fix_2098_ausblick_acc_und_sonnenstunden.md (AC-5..AC-12)
KONTEXT: docs/context/fix-2098-ausblick-acc-und-sonnenstunden.md

Fehlerbild aus Nutzersicht: die ACC-Spalte (Prognose-Genauigkeit) ist aus der
3-Tages-Vorschau der Trip-Briefing-Mail verschwunden. ``show_acc`` wird nur im
ALTFORM-Zweig beider Renderer gelesen (outlook.py:165-178, :231, :316-332);
der konfigurierbare Zweig (``metrics`` gesetzt, :129-163 und :289-314) kennt
ACC nicht. Seit #1848 A3 loest ``resolve_trip_outlook_metrics()`` fuer den
Trip praktisch immer eine Metrikliste auf -- der Trip laeuft damit praktisch
immer ueber den Zweig ohne ACC.

🔴 AC-14 (Testluecke): alle bestehenden ACC-Waechter
(``test_shared_outlook_renderer.py:132-199``,
``test_trip_outlook_parity.py:94-122``) rufen OHNE ``metrics=`` auf und
pruefen damit den fuer den Trip toten Altform-Zweig. JEDER Test in dieser
Datei ruft ausdruecklich MIT ``metrics=`` -- dem produktiven Zweig. Der
Altform-Zweig kommt hier nur einmal vor, als unabhaengige Referenz fuer das
Aussehen des bekannten Farbpunkts (AC-5).

Kern-Schicht, deterministisch: keine Mocks/``patch()``/``MagicMock``, kein
Netz, kein Dateiinhalt-Check. Echte ``SegmentWeatherSummary``-/
``ForecastDataPoint``-Objekte, echte Renderer-Aufrufe.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen -- sonst
# pruefte ein Worktree-Lauf die unveraenderte Hauptrepo-Kopie.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

TZ = ZoneInfo("Europe/Berlin")

# Ausblick-Auswahl im Neuformat (#1848 A2: reine Kennungen).
_AUSWAHL = ["precipitation", "gust"]

# Die vier Stufen des bekannten Farbpunkts (_acc_dot, outlook.py:103-121):
# >=80 / >=60 / >=40 / <40. Die Klartext-Worte sind PO-festgelegt (AC-11).
_STUFEN_WORT = {85: "hoch", 65: "mittel", 45: "niedrig", 35: "sehr niedrig"}
_ACC_LABEL = "ACC"
_KEIN_WERT = "–"


# ---------------------------------------------------------------------------
# Echte Domaenen-Objekte
# ---------------------------------------------------------------------------

def _punkte():
    from app.models import ForecastDataPoint, ThunderLevel

    return [
        ForecastDataPoint(
            ts=datetime(2026, 7, 12, stunde, 0, tzinfo=timezone.utc),
            t2m_c=15.0, wind10m_kmh=12.0, wind_direction_deg=270, gust_kmh=44.0,
            precip_1h_mm=0.5, pop_pct=55, cloud_total_pct=60,
            thunder_level=ThunderLevel.NONE, visibility_m=15000.0,
            humidity_pct=55,
        )
        for stunde in range(8, 14)
    ]


def _summary(confidence):
    """Etappen-Aggregat mit gesetzter Prognose-Genauigkeit.

    ``confidence_pct_min`` ist die Quelle, aus der ``build_outlook_row()``
    den Schluessel ``confidence_pct`` des Row-Dicts baut (outlook.py:586-587,
    :599) -- VOR dem ``metrics``-Zweig, der Wert liegt also in beiden Zweigen
    gleichermassen vor.
    """
    from app.models import SegmentWeatherSummary, ThunderLevel

    return SegmentWeatherSummary(
        temp_min_c=9.0, temp_max_c=21.0, temp_avg_c=15.0,
        wind_max_kmh=25.0, gust_max_kmh=44.0, precip_sum_mm=2.5,
        cloud_avg_pct=60, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE, pop_max_pct=55,
        visibility_min_m=9000, confidence_pct_min=confidence,
    )


def _zeilen(confidences, *, metrics=None):
    """Ausblick-Zeilen ueber den echten Zeilenbau ``build_outlook_row()``."""
    from output.renderers.email.outlook import build_outlook_row

    auswahl = _AUSWAHL if metrics is None else metrics
    tage = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
    return [
        build_outlook_row(_summary(conf), _punkte(), tage[i % len(tage)], TZ,
                          metrics=auswahl)
        for i, conf in enumerate(confidences)
    ]


# ---------------------------------------------------------------------------
# Auswertung der gerenderten Ausgabe
# ---------------------------------------------------------------------------

def _kopf(html: str) -> list[str]:
    return [th.get_text(strip=True)
            for th in BeautifulSoup(html, "html.parser").find_all("th")]


def _datenzellen(html: str) -> list[list]:
    """Datenzeilen als Liste der ``<td>``-Elemente (Roh-HTML bleibt erhalten --
    der ACC-Farbpunkt hat KEINEN Text, ein Text-Extrakt saehe ihn nicht)."""
    koerper = BeautifulSoup(html, "html.parser").find("tbody")
    return [tr.find_all("td") for tr in koerper.find_all("tr")] if koerper else []


def _acc_zelle(html: str, zeile: int = 0):
    """Die ``<td>`` an der Position, die die Kopfzeile mit ACC beschriftet.

    Bewusst ueber den Kopf-Index statt ueber "die letzte Zelle": genau das
    Auseinanderlaufen von Beschriftung und Wert ist die Fehlerklasse (AC-10).
    """
    kopf = _kopf(html)
    assert _ACC_LABEL in kopf, (
        f"Die Kopfzeile des konfigurierbaren Ausblick-Zweigs traegt keine "
        f"ACC-Spalte: {kopf!r} (#2098 Befund B)."
    )
    zellen = _datenzellen(html)[zeile]
    assert len(zellen) == len(kopf), (
        f"Kopf ({len(kopf)} Spalten) und Datenzeile ({len(zellen)} Zellen) "
        f"laufen auseinander: {kopf!r}"
    )
    return zellen[kopf.index(_ACC_LABEL)]


def _punkt_farbe(td) -> str | None:
    treffer = re.search(r"background:(#[0-9a-fA-F]{6})", str(td))
    return treffer.group(1).lower() if treffer else None


def _klartext_zeilen(block: str) -> list[str]:
    """Die Wertzeilen des Klartext-Ausblicks (ohne Leer- und Ueberschriftzeile)."""
    return [z for z in block.splitlines()[2:] if z.strip()]


def _acc_wort(zeile: str) -> str | None:
    """Das Wort hinter dem ACC-Label einer Klartext-Zeile.

    Die Spalten sind mit zwei Leerzeichen getrennt (outlook.py:301-303), das
    Wort selbst darf also ein Leerzeichen enthalten ("sehr niedrig").
    """
    treffer = re.search(rf"\b{_ACC_LABEL} (\S.*?)(?:\s{{2,}}|$)", zeile)
    return treffer.group(1) if treffer else None


# ---------------------------------------------------------------------------
# AC-5 — HTML: ACC-Spalte im konfigurierbaren Zweig, bekannter Farbpunkt
# ---------------------------------------------------------------------------

def test_ac5_html_zeigt_acc_spalte_im_konfigurierbaren_zweig():
    """AC-5: Given ein Trip mit konfigurierten Ausblick-Metriken (``metrics``
    gesetzt -- der Zweig, ueber den der Trip seit #1848 A3 laeuft) / When das
    Briefing als HTML-Mail gerendert wird / Then erscheint eine ACC-Spalte mit
    dem bekannten 4-stufigen Farbpunkt HINTER den gewaehlten Metrik-Spalten.

    Das Aussehen wird gegen eine UNABHAENGIGE Quelle geprueft: derselbe
    Zeilensatz durch den Altform-Zweig (``metrics=None``), dessen ACC-Zelle
    seit jeher der Farbpunkt ist. Damit haengt der Test nicht an einem im
    Test abgeschriebenen Hex-Wert.
    """
    from output.renderers.email.outlook import render_outlook_table

    zeilen = _zeilen([85])
    html = render_outlook_table(zeilen, show_acc=True, metrics=_AUSWAHL)

    kopf = _kopf(html)
    assert kopf[-1] == _ACC_LABEL, (
        f"ACC steht nicht hinter den gewaehlten Metrik-Spalten: {kopf!r} "
        "(#2098 Befund B: show_acc wird im konfigurierbaren Zweig nicht "
        "gelesen)."
    )

    altform = render_outlook_table(zeilen, show_acc=True)
    erwarteter_punkt = _datenzellen(altform)[0][-1].decode_contents()
    assert _acc_zelle(html).decode_contents() == erwarteter_punkt, (
        "Die ACC-Zelle des konfigurierbaren Zweigs zeigt nicht denselben "
        f"Farbpunkt wie der Altform-Zweig: {_acc_zelle(html).decode_contents()!r} "
        f"vs. {erwarteter_punkt!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 — Klartext: ACC-Spalte mit Wort statt Punkt
# ---------------------------------------------------------------------------

def test_ac6_klartext_zeigt_acc_wort_hinter_den_gewaehlten_spalten():
    """AC-6: Given denselben konfigurierbaren Renderer-Zweig / When der
    Ausblick als Klartext-Mail gerendert wird / Then erscheint eine
    ACC-Spalte mit einem 4-stufigen deutschen Wort HINTER den gewaehlten
    Metrik-Spalten.

    Projektregel "HTML = Normalfassung, keine Dopplung": der Farbpunkt ist im
    HTML der EINZIGE Informationstraeger -- im Klartext braucht dieselbe
    Aussage ein Wort.
    """
    from output.renderers.email.outlook import render_outlook_plain

    block = render_outlook_plain(_zeilen([85]), show_acc=True, metrics=_AUSWAHL)
    zeile = _klartext_zeilen(block)[0]

    assert _ACC_LABEL in zeile, (
        f"Die Klartext-Ausblick-Zeile fuehrt keine ACC-Spalte: {zeile!r} "
        "(#2098 Befund C)."
    )
    assert _acc_wort(zeile) == _STUFEN_WORT[85], (
        f"ACC-Wort {_acc_wort(zeile)!r} statt {_STUFEN_WORT[85]!r} in {zeile!r}."
    )
    assert zeile.rstrip().endswith(f"{_ACC_LABEL} {_STUFEN_WORT[85]}"), (
        f"ACC steht nicht hinter den gewaehlten Metrik-Spalten: {zeile!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — zwei Stufen unterscheiden sich sichtbar (Gegenprobe mit echtem Wert)
# ---------------------------------------------------------------------------

def test_ac7_hohe_und_niedrigste_stufe_unterscheiden_sich_sichtbar():
    """AC-7: Given einen Genauigkeits-Wert von 85 % (hohe Stufe) und einen
    zweiten von 35 % (niedrigste Stufe) / When beide Etappen im selben
    Ausblick gerendert werden / Then unterscheiden sich die HTML-Farbpunkte
    sichtbar -- und ebenso die Klartext-Worte.

    Gegenprobe mit einem plausibel FALSCHEN Wert (35 statt 85), nicht mit
    ``None``: eine Zelle, die immer denselben Punkt zeigte, waere gegen einen
    Totalausfall geschuetzt, gegen einen falschen Wert aber blind.
    """
    from output.renderers.email.outlook import (
        render_outlook_plain, render_outlook_table,
    )

    zeilen = _zeilen([85, 35])
    html = render_outlook_table(zeilen, show_acc=True, metrics=_AUSWAHL)

    hoch, niedrig = _punkt_farbe(_acc_zelle(html, 0)), _punkt_farbe(_acc_zelle(html, 1))
    assert hoch is not None and niedrig is not None, (
        f"Mindestens eine ACC-Zelle traegt gar keinen Farbpunkt: "
        f"85% -> {hoch!r}, 35% -> {niedrig!r}"
    )
    assert hoch != niedrig, (
        f"85 % und 35 % erzeugen denselben Farbpunkt ({hoch!r}) -- die Spalte "
        "zeigt die Stufe nicht an."
    )

    worte = [_acc_wort(z) for z in
             _klartext_zeilen(render_outlook_plain(zeilen, show_acc=True,
                                                   metrics=_AUSWAHL))]
    assert worte == [_STUFEN_WORT[85], _STUFEN_WORT[35]], (
        f"Klartext-Worte {worte!r} statt "
        f"{[_STUFEN_WORT[85], _STUFEN_WORT[35]]!r}."
    )


# ---------------------------------------------------------------------------
# AC-8 — Ortsvergleich bleibt ohne ACC (mit Positivkontrolle)
# ---------------------------------------------------------------------------

def test_ac8_ortsvergleich_bleibt_ohne_acc_spalte():
    """AC-8: Given einen Ortsvergleich-Ausblick (``show_acc=False``, s.
    compare_html.py:1257 und comparison.py:367) / When er im konfigurierbaren
    Zweig als HTML- UND als Klartext-Mail gerendert wird / Then erscheint
    weder eine ACC-Spalte in der Kopfzeile noch eine ACC-Zelle in den
    Datenzeilen.

    Positivkontrolle: derselbe Zeilensatz mit ``show_acc=True`` MUSS die
    Spalte zeigen. Ohne diesen Teil waere der Test auch dann gruen, wenn der
    Renderer ueberhaupt nichts ausgaebe -- ein Ausbleiben-Test ohne Nachweis,
    dass es sonst geschaehe, bewacht nichts.
    """
    from output.renderers.email.outlook import (
        render_outlook_plain, render_outlook_table,
    )

    zeilen = _zeilen([85])

    mit_acc = render_outlook_table(zeilen, show_acc=True, metrics=_AUSWAHL)
    assert _ACC_LABEL in _kopf(mit_acc), (
        f"Positivkontrolle gescheitert: schon mit show_acc=True fehlt die "
        f"ACC-Spalte ({_kopf(mit_acc)!r}) -- der Ausbleiben-Nachweis fuer den "
        "Ortsvergleich waere wertlos (#2098 Befund B)."
    )
    mit_acc_klartext = render_outlook_plain(zeilen, show_acc=True,
                                            metrics=_AUSWAHL, show_name=False)
    assert _ACC_LABEL in _klartext_zeilen(mit_acc_klartext)[0], (
        "Positivkontrolle gescheitert: schon mit show_acc=True fehlt die "
        "ACC-Spalte im Klartext (#2098 Befund C)."
    )

    ohne_acc = render_outlook_table(zeilen, show_acc=False, metrics=_AUSWAHL)
    kopf_ohne = _kopf(ohne_acc)
    assert _ACC_LABEL not in kopf_ohne, (
        f"Der Ortsvergleich zeigt eine ACC-Spalte: {kopf_ohne!r} (ADR-0005/"
        "#710: Confidence ist keine per-Ort-Groesse)."
    )
    assert len(_datenzellen(ohne_acc)[0]) == len(kopf_ohne), (
        f"Kopf {kopf_ohne!r} und Datenzeile laufen im Compare-Fall "
        f"auseinander ({len(_datenzellen(ohne_acc)[0])} Zellen)."
    )
    assert len(_datenzellen(ohne_acc)[0]) == len(_datenzellen(mit_acc)[0]) - 1, (
        "show_acc=False soll genau EINE Zelle weniger tragen als "
        f"show_acc=True: {len(_datenzellen(ohne_acc)[0])} vs. "
        f"{len(_datenzellen(mit_acc)[0])}"
    )

    ohne_acc_klartext = render_outlook_plain(zeilen, show_acc=False,
                                             metrics=_AUSWAHL, show_name=False)
    assert _ACC_LABEL not in ohne_acc_klartext, (
        f"Der Klartext-Ortsvergleich zeigt ACC: {ohne_acc_klartext!r}"
    )


# ---------------------------------------------------------------------------
# AC-9 — ACC-Spalte OHNE dass confidence waehlbar wird (#710/ADR-0005)
# ---------------------------------------------------------------------------

def test_ac9_acc_spalte_ohne_dass_confidence_waehlbar_wird():
    """AC-9: Given die Backend-Aufloesung der waehlbaren Ausblick-Metriken
    (``available_aggregations``/``derived_aggregations``) / When nach der
    Behebung geprueft wird / Then taucht ``confidence``/ACC weiterhin NICHT
    in der Liste der waehlbaren Ausblick-Metriken auf -- die Spalte entsteht
    ausschliesslich als fest angehaengte Zusatzspalte AUSSERHALB der Auswahl.

    Beide Haelften stehen bewusst in EINEM Test: "ACC ist da" und "ACC ist
    nicht waehlbar" muessen GLEICHZEITIG gelten. Getrennt geprueft koennte
    eine Behebung, die ACC in den Katalog haengt, die eine Haelfte gruen
    machen, waehrend die andere in einer anderen Datei rot liegt.
    """
    from app.metric_catalog import get_metric
    from output.renderers.compare_outlook_metric_ids import (
        derived_aggregations, outlook_columns,
    )
    from output.renderers.email.outlook import render_outlook_table

    html = render_outlook_table(_zeilen([85]), show_acc=True, metrics=_AUSWAHL)
    assert _ACC_LABEL in _kopf(html), (
        f"Die ACC-Spalte fehlt: {_kopf(html)!r} (#2098 Befund B)."
    )

    assert get_metric("confidence").selectable is False, (
        "confidence ist waehlbar geworden -- ADR-0005/#710 verlangt "
        "selectable=False."
    )
    assert derived_aggregations("confidence") == [], (
        "confidence liefert Ausblick-Auswertungen und wuerde damit als "
        f"waehlbare Spalte erscheinen: {derived_aggregations('confidence')!r}"
    )
    assert outlook_columns(["confidence"]) == [], (
        "confidence erzeugt eine Spalte ueber outlook_columns() -- die "
        "ACC-Spalte muss AUSSERHALB des Metrik-Systems angehaengt werden "
        f"(#710): {outlook_columns(['confidence'])!r}"
    )
    aus_der_auswahl = [c["label"] for c in outlook_columns(_AUSWAHL)]
    assert _ACC_LABEL not in aus_der_auswahl, (
        f"outlook_columns() liefert eine ACC-Spalte ({aus_der_auswahl!r}) -- "
        "sie gehoert nicht in die Auswahl-Aufloesung, sondern wird vom "
        "Renderer fest angehaengt (#710)."
    )


# ---------------------------------------------------------------------------
# AC-10 — Kopf und Wert stehen an derselben Position
# ---------------------------------------------------------------------------

def test_ac10_acc_steht_in_kopf_und_datenzeile_an_derselben_position():
    """AC-10: Given eine Kopfzeile und eine Datenzeile desselben Ausblicks /
    When beide gerendert werden / Then steht die ACC-Spalte an derselben
    Position relativ zu den uebrigen Spalten -- kein Auseinanderlaufen von
    Beschriftung und Wert.

    Geprueft ueber ZWEI verschieden lange Auswahlen: die Position wird damit
    abgeleitet und nicht als Zahl im Test festgeschrieben. Zusaetzlich wird
    eine Nachbarspalte auf ihren WERT geprueft -- ein reiner Laengenvergleich
    saehe einen Versatz um eine Spalte nicht.
    """
    from output.renderers.compare_outlook_metric_ids import outlook_columns
    from output.renderers.email.outlook import render_outlook_table

    for auswahl in (["precipitation"], ["precipitation", "gust", "thunder",
                                        "sunshine"]):
        html = render_outlook_table(_zeilen([85], metrics=auswahl),
                                    show_acc=True, metrics=auswahl)
        kopf = _kopf(html)
        labels = [c["label"] for c in outlook_columns(auswahl)]

        assert kopf == ["Tag", *labels, _ACC_LABEL], (
            f"Kopfzeile {kopf!r} statt {['Tag', *labels, _ACC_LABEL]!r} "
            f"(Auswahl {auswahl!r})."
        )
        zellen = _datenzellen(html)[0]
        assert len(zellen) == len(kopf), (
            f"{len(zellen)} Zellen zu {len(kopf)} Spalten (Auswahl "
            f"{auswahl!r}): Kopf und Werte laufen auseinander."
        )
        assert _punkt_farbe(zellen[kopf.index(_ACC_LABEL)]) is not None, (
            f"An der ACC-Position (Index {kopf.index(_ACC_LABEL)}) steht kein "
            f"Farbpunkt (Auswahl {auswahl!r})."
        )
        assert zellen[kopf.index("Niederschlag")].get_text(strip=True) == "2.5 mm", (
            "Die Niederschlags-Zelle steht nicht unter ihrer Beschriftung: "
            f"{zellen[kopf.index('Niederschlag')].get_text(strip=True)!r} "
            f"(Auswahl {auswahl!r}) -- Spaltenversatz."
        )


# ---------------------------------------------------------------------------
# AC-11 — die vier Klartext-Worte
# ---------------------------------------------------------------------------

def test_ac11_vier_stufen_tragen_vier_eindeutige_klartext_worte():
    """AC-11: Given die vier HTML-Farbstufen (>=80 / >=60 / >=40 / <40) /
    When das Klartext-Wort je Stufe gerendert wird / Then ist jede Stufe
    durch ein eindeutiges, unterscheidbares Wort ohne Handlungsempfehlung
    vertreten (reine Zustandsbeschreibung, ADR-0007).
    """
    from output.renderers.email.outlook import render_outlook_plain

    werte = list(_STUFEN_WORT)
    block = render_outlook_plain(_zeilen(werte), show_acc=True, metrics=_AUSWAHL)
    worte = [_acc_wort(z) for z in _klartext_zeilen(block)]

    assert worte == [_STUFEN_WORT[w] for w in werte], (
        f"Klartext-Worte {worte!r} statt {[_STUFEN_WORT[w] for w in werte]!r} "
        f"fuer die Stufen {werte!r}."
    )
    assert len(set(worte)) == len(werte), (
        f"Die vier Stufen sind nicht unterscheidbar: {worte!r}"
    )


def test_ac11_klartext_wort_folgt_denselben_stufen_wie_der_farbpunkt():
    """AC-11 (Kopplung): Given eine Wertereihe quer ueber alle vier Stufen
    inklusive ihrer Grenzen (80/60/40) / When HTML und Klartext gerendert
    werden / Then wechselt das Klartext-Wort an GENAU denselben Stellen wie
    der Farbpunkt.

    Ohne diese Kopplung koennte das Wort eine eigene, abweichende
    Stufengrenze bekommen -- HTML und Klartext derselben Mail zeigten dann
    verschiedene Aussagen zur selben Zahl.
    """
    from output.renderers.email.outlook import (
        render_outlook_plain, render_outlook_table,
    )

    werte = [95, 85, 80, 79, 65, 60, 59, 45, 40, 39, 20, 0]
    zeilen = _zeilen(werte)
    html = render_outlook_table(zeilen, show_acc=True, metrics=_AUSWAHL)

    farben = [_punkt_farbe(_acc_zelle(html, i)) for i in range(len(werte))]
    worte = [_acc_wort(z) for z in
             _klartext_zeilen(render_outlook_plain(zeilen, show_acc=True,
                                                   metrics=_AUSWAHL))]

    assert None not in farben and None not in worte, (
        f"Unvollstaendige Ausgabe -- Farben: {farben!r}, Worte: {worte!r}"
    )
    nach_farbe = {farbe: sorted({w for f, w in zip(farben, worte) if f == farbe})
                  for farbe in set(farben)}
    assert all(len(w) == 1 for w in nach_farbe.values()), (
        "Zu einer Farbstufe gehoeren mehrere Klartext-Worte -- Wort und Punkt "
        f"folgen verschiedenen Grenzen: {nach_farbe!r} (Werte {werte!r})."
    )
    assert len(set(worte)) == len(set(farben)), (
        f"Anzahl Klartext-Worte {sorted(set(worte))!r} passt nicht zur Anzahl "
        f"Farbstufen {sorted(set(farben))!r} (Werte {werte!r})."
    )


# ---------------------------------------------------------------------------
# AC-12 — fehlender Wert bleibt "–"
# ---------------------------------------------------------------------------

def test_ac12_fehlende_genauigkeit_zeigt_strich_statt_absturz():
    """AC-12: Given einen fehlenden ``confidence_pct``-Wert (``None``) / When
    die Zeile gerendert wird / Then erscheint fuer ACC weiterhin "–" wie im
    HTML-Fall -- kein Absturz, kein leeres Feld.

    Gegenprobe im selben Test: eine zweite Zeile MIT Wert muss ihr Wort/ihren
    Punkt zeigen. Sonst waere ein Renderer, der ueberall "–" schreibt, gruen.
    """
    from output.renderers.email.outlook import (
        render_outlook_plain, render_outlook_table,
    )

    zeilen = _zeilen([None, 85])
    assert "confidence_pct" not in zeilen[0], (
        "Vorbedingung: die erste Zeile darf keinen Genauigkeitswert tragen."
    )

    html = render_outlook_table(zeilen, show_acc=True, metrics=_AUSWAHL)
    assert _acc_zelle(html, 0).get_text(strip=True) == _KEIN_WERT, (
        f"HTML-ACC ohne Wert: {_acc_zelle(html, 0).get_text(strip=True)!r} "
        f"statt {_KEIN_WERT!r}."
    )
    assert _punkt_farbe(_acc_zelle(html, 1)) is not None, (
        "Gegenprobe: die Zeile MIT Wert zeigt keinen Farbpunkt."
    )

    klartext = _klartext_zeilen(render_outlook_plain(zeilen, show_acc=True,
                                                     metrics=_AUSWAHL))
    assert _acc_wort(klartext[0]) == _KEIN_WERT, (
        f"Klartext-ACC ohne Wert: {_acc_wort(klartext[0])!r} statt "
        f"{_KEIN_WERT!r} in {klartext[0]!r}."
    )
    assert _acc_wort(klartext[1]) == _STUFEN_WORT[85], (
        f"Gegenprobe: {_acc_wort(klartext[1])!r} statt {_STUFEN_WORT[85]!r}."
    )
