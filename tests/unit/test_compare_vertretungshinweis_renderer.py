"""Issue #1563 — Vertretungshinweis je Ort im Ortsvergleich (TDD RED, Renderer).

SPEC: docs/specs/modules/feat_1563_compare_vertretungshinweis.md (AC-1..AC-8,
AC-10, AC-11)

Kern-Schicht, netzfrei, ohne Mock-Theater: echte ``LocationResult`` /
``ComparisonResult`` / ``ForecastMeta`` und echte Renderer-Aufrufe.

Vertrag fuer die Implementierung (Spec R1, R2, R5, R6):
- ``LocationResult.forecast_meta: Optional[ForecastMeta] = None`` (neu).
- ``fallback_notice.build_compare_fallback_lines(location_results, *, lang)``
  -> list[str], je Zeile ``"<Ort>: <Text aus build_fallback_lines>"``.
- ``render_compare_html`` / ``render_comparison_text`` / ``render_compare_telegram``
  / ``render_compare_email`` nehmen das Schluesselwort
  ``show_fallback_notice: bool = False``. Nur die Briefing-Compare-Mail setzt
  ``True``; Alarm-/Vorschau-Aufrufer lassen den Default (AC-8).

Beobachtungspunkt: das Rendererergebnis (dort WIRKT die Zusicherung); der
erwartete Klartext kommt aus der echten ``build_fallback_lines``.
"""
from __future__ import annotations
from tests.helpers.ampel_allgemein import PRESET_ALLGEMEIN

import html as _html
from datetime import date, datetime, timedelta, timezone

from app.models import ForecastDataPoint, ForecastMeta, Provider
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.fallback_notice import build_fallback_lines

ROHKENNUNGEN = ("Fallback", "icon_eu", "eu_direct")
GEWITTER_FELD = "lightning_density_per_km2_3h"


def _meta(**kw) -> ForecastMeta:
    return ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                        grid_res_km=2.2, **kw)


def _wetter_meta() -> ForecastMeta:
    # Grundvorhersage-Vertretung (Wetterzeile)
    return _meta(fallback_model="icon_eu", fallback_metrics=["temperature_2m"],
                 fallback_reason="metric_gap")


def _gewitter_meta() -> ForecastMeta:
    # nur Gewitter-Vertretung
    return _meta(fallback_model="icon_eu", fallback_metrics=[GEWITTER_FELD],
                 fallback_reason="thunder_source_unavailable")


def _kollision_meta() -> ForecastMeta:
    # Gewitter UND Grundvorhersage
    return _meta(fallback_model="icon_eu",
                 fallback_metrics=["temperature_2m", GEWITTER_FELD],
                 fallback_reason="metric_gap")


def _loc(name: str, idx: int) -> SavedLocation:
    return SavedLocation(id=f"loc-{idx}", name=name, lat=47.0 + idx, lon=11.0,
                         elevation_m=1000 + idx, timezone="Europe/Vienna")


def _lr(name: str, idx: int, meta=None, error=None) -> LocationResult:
    base = datetime(2026, 11, 5, 9, tzinfo=timezone.utc)
    hourly = [ForecastDataPoint(ts=base + timedelta(hours=h), t2m_c=4.0 + h,
                                wind10m_kmh=10.0, gust_kmh=20.0,
                                cloud_total_pct=40, precip_1h_mm=0.0)
              for h in range(8)]
    kw = dict(location=_loc(name, idx), score=0, temp_min=4.0, temp_max=11.0,
              wind_max=10.0, gust_max=20.0, cloud_avg=40, hourly_data=hourly)
    if error:
        kw.update(error=error, hourly_data=[])
    lr = LocationResult(**kw)
    if meta is not None:
        lr.forecast_meta = meta  # Feld heute nicht deklariert (Spec R1)
    return lr


def _result(*lrs: LocationResult) -> ComparisonResult:
    return ComparisonResult(locations=list(lrs), time_window=(9, 16),
                            target_date=date(2026, 11, 5),
                            created_at=datetime(2026, 11, 4, 6, 0))


def _zeilen(meta, lang="de") -> list:
    z = build_fallback_lines(meta, lang=lang)
    assert z, "Testannahme: diese Meta traegt eine Vertretung"
    return z


def _html_mail(result, **kw) -> str:
    from output.renderers.email.compare_html import render_compare_html
    kw.setdefault("preset", PRESET_ALLGEMEIN)
    return _html.unescape(render_compare_html(result, **kw))


def _text_mail(result, **kw) -> str:
    from output.renderers.comparison import render_comparison_text
    return render_comparison_text(result, preset=kw.pop("preset", None), **kw)


def _telegram(result, **kw) -> str:
    from output.renderers.comparison import render_compare_telegram
    return render_compare_telegram(result, **kw)


def _alle_ausgaben(result, **kw) -> dict:
    return {"html": _html_mail(result, **kw), "text": _text_mail(result, **kw),
            "telegram": _telegram(result, **kw)}


def _zwei_orte_zweiter_betroffen(meta=None):
    return _result(_lr("Innsbruck", 1), _lr("Seefeld", 2, meta or _wetter_meta()))


# ---------------------------------------------------------------- Hilfsfunktion

def test_build_compare_fallback_lines_nur_betroffener_ort_mit_namen():
    from output.renderers.fallback_notice import build_compare_fallback_lines

    res = _zwei_orte_zweiter_betroffen()
    zeilen = build_compare_fallback_lines(res.locations, lang="de")
    erwartet = [f"Seefeld: {z}" for z in _zeilen(_wetter_meta())]
    assert zeilen == erwartet
    assert not any("Innsbruck" in z for z in zeilen)


def test_build_compare_fallback_lines_beide_betroffen_in_tabellenreihenfolge():
    from output.renderers.fallback_notice import build_compare_fallback_lines

    res = _result(_lr("Innsbruck", 1, _gewitter_meta()),
                  _lr("Seefeld", 2, _wetter_meta()))
    zeilen = build_compare_fallback_lines(res.locations, lang="de")
    assert zeilen[0].startswith("Innsbruck: ")
    assert zeilen[-1].startswith("Seefeld: ")


def test_build_compare_fallback_lines_kollision_zwei_zeilen_ein_ort():
    from output.renderers.fallback_notice import build_compare_fallback_lines

    res = _zwei_orte_zweiter_betroffen(_kollision_meta())
    zeilen = build_compare_fallback_lines(res.locations, lang="de")
    assert len(zeilen) == 2 and all(z.startswith("Seefeld: ") for z in zeilen)


def test_build_compare_fallback_lines_fehlerort_und_none_liefern_nichts():
    from output.renderers.fallback_notice import build_compare_fallback_lines

    fehler = _lr("Seefeld", 2, _wetter_meta(), error="Abruf fehlgeschlagen")
    assert build_compare_fallback_lines(
        [_lr("Innsbruck", 1), fehler], lang="de") == []
    assert build_compare_fallback_lines([_lr("A", 1), _lr("B", 2)], lang="de") == []


def test_build_compare_fallback_lines_englisch_aus_dem_katalog():
    from output.renderers.fallback_notice import build_compare_fallback_lines

    res = _zwei_orte_zweiter_betroffen()
    zeilen = build_compare_fallback_lines(res.locations, lang="en")
    assert zeilen == [f"Seefeld: {z}" for z in _zeilen(_wetter_meta(), "en")]
    assert "backup" in zeilen[0].lower()


# ----------------------------------------------------------- AC-1 / AC-2 / AC-3

def test_ac1_html_hinweiszeile_mit_ortsnamen_nur_betroffener_ort():
    html = _html_mail(_zwei_orte_zweiter_betroffen(), show_fallback_notice=True)
    zeile = f"Seefeld: {_zeilen(_wetter_meta())[0]}"
    assert html.count(zeile) == 1
    assert "Innsbruck: " not in html


def test_ac2_klartext_hinweiszeile_ohne_rohkennungen():
    text = _text_mail(_zwei_orte_zweiter_betroffen(), show_fallback_notice=True)
    assert f"Seefeld: {_zeilen(_wetter_meta())[0]}" in text
    for roh in ROHKENNUNGEN:
        assert roh not in text


def test_ac3_telegram_hinweiszeile_ohne_rohkennungen():
    tg = _telegram(_zwei_orte_zweiter_betroffen(), show_fallback_notice=True)
    assert f"Seefeld: {_zeilen(_wetter_meta())[0]}" in tg
    for roh in ROHKENNUNGEN:
        assert roh not in tg


def test_hinweis_steht_unter_der_tabelle_nicht_im_kopf():
    text = _text_mail(_zwei_orte_zweiter_betroffen(), show_fallback_notice=True)
    zeile = f"Seefeld: {_zeilen(_wetter_meta())[0]}"
    assert text.index(zeile) > text.index("Innsbruck")


# --------------------------------------------------------------------- AC-4

def test_ac4_normalfall_byte_identisch_und_kein_leerer_rahmen():
    ohne = _result(_lr("Innsbruck", 1), _lr("Seefeld", 2))
    basis = _alle_ausgaben(ohne)  # Default: ohne Flag
    assert basis == _alle_ausgaben(ohne)  # Determinismus der Messung
    # Flag an, aber keine Vertretung -> unveraendert, nichts Zusaetzliches
    assert _alle_ausgaben(ohne, show_fallback_notice=True) == basis
    # Vertretung vorhanden, Flag aus (Default) -> unveraendert gegenueber Normalfall
    mit = _zwei_orte_zweiter_betroffen()
    assert _alle_ausgaben(mit) == basis


# --------------------------------------------------------------------- AC-5

def test_ac5_fehlerort_erzeugt_keinen_hinweisblock():
    fehler = _lr("Seefeld", 2, _wetter_meta(), error="Abruf fehlgeschlagen")
    res = _result(_lr("Innsbruck", 1), fehler)
    ref = _result(_lr("Innsbruck", 1), _lr("Seefeld", 2, error="Abruf fehlgeschlagen"))
    assert _alle_ausgaben(res, show_fallback_notice=True) == _alle_ausgaben(ref)


# --------------------------------------------------------------------- AC-6

def test_ac6_kollision_zwei_zeilen_gleicher_ort_gewitterzeile_ohne_quelle():
    res = _zwei_orte_zweiter_betroffen(_kollision_meta())
    zeilen = _zeilen(_kollision_meta())
    assert len(zeilen) == 2
    for name, ausgabe in _alle_ausgaben(res, show_fallback_notice=True).items():
        for z in zeilen:
            assert f"Seefeld: {z}" in ausgabe, name
    from i18n import t
    # Gewitterzeile nennt keinen Quellennamen (Kollisionsfall)
    assert zeilen[0] == t("mail.fallback.gewitter_ohne_quelle", "de")
    assert "DWD Europa" not in zeilen[0]


# --------------------------------------------------------------------- AC-7

def test_ac7_englisch_katalogtext_ortsname_unuebersetzt():
    res = _zwei_orte_zweiter_betroffen()
    en = _zeilen(_wetter_meta(), "en")[0]
    de = _zeilen(_wetter_meta(), "de")[0]
    assert en != de
    for name, ausgabe in _alle_ausgaben(
            res, show_fallback_notice=True, lang="en").items():
        assert f"Seefeld: {en}" in ausgabe, name
        assert de not in ausgabe, name


def test_ac7_katalog_hat_muster_compare_zeile_in_beiden_sprachen():
    from i18n import t
    for lang in ("de", "en"):
        muster = t("mail.fallback.compare_zeile", lang, ort="X", text="Y")
        assert "X" in muster and "Y" in muster and "compare_zeile" not in muster


# --------------------------------------------------------------------- AC-8

def test_ac8_default_aufruf_alarm_vorschau_zeigt_keinen_hinweis():
    res = _zwei_orte_zweiter_betroffen()
    zeile = f"Seefeld: {_zeilen(_wetter_meta())[0]}"
    default = _alle_ausgaben(res)
    briefing = _alle_ausgaben(res, show_fallback_notice=True)
    for name in default:
        assert zeile not in default[name], name
        assert zeile in briefing[name], name


def test_ac8_render_compare_email_reicht_flag_an_html_und_text_durch():
    from output.renderers.comparison import render_compare_email

    res = _zwei_orte_zweiter_betroffen()
    zeile = f"Seefeld: {_zeilen(_wetter_meta())[0]}"
    h0, t0 = render_compare_email(res, preset=PRESET_ALLGEMEIN)
    h1, t1 = render_compare_email(res, show_fallback_notice=True, preset=PRESET_ALLGEMEIN)
    assert zeile not in _html.unescape(h0) and zeile not in t0
    assert zeile in _html.unescape(h1) and zeile in t1


# -------------------------------------------------------------------- AC-10

def test_ac10_zwei_nutzer_hinweis_des_einen_nie_in_der_mail_des_anderen():
    # Nutzer 1: Seefeld betroffen; Nutzer 2: Innsbruck betroffen (anderer Text)
    mail1 = _alle_ausgaben(_result(_lr("Innsbruck", 1),
                                   _lr("Seefeld", 2, _wetter_meta())),
                           show_fallback_notice=True)
    mail2 = _alle_ausgaben(_result(_lr("Innsbruck", 1, _gewitter_meta()),
                                   _lr("Seefeld", 2)),
                           show_fallback_notice=True)
    z1 = f"Seefeld: {_zeilen(_wetter_meta())[0]}"
    z2 = f"Innsbruck: {_zeilen(_gewitter_meta())[0]}"
    for name in mail1:
        assert z1 in mail1[name] and z2 not in mail1[name], name
        assert z2 in mail2[name] and z1 not in mail2[name], name


# -------------------------------------------------------------------- AC-11

def test_ac11_sms_ohne_hinweis_und_innerhalb_160_zeichen():
    from output.renderers.comparison import render_compare_sms

    mit = _zwei_orte_zweiter_betroffen(_kollision_meta())
    sms = render_compare_sms(mit)
    ref = render_compare_sms(_result(_lr("Innsbruck", 1), _lr("Seefeld", 2)))
    assert sms == ref
    assert len(sms) <= 160
    for z in _zeilen(_kollision_meta()):
        assert z not in sms
