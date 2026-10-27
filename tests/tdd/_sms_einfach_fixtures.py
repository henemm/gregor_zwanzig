"""Gemeinsame Bausteine fuer #2422 S6 (Roh/Einfach in SMS-artigen Kanaelen, ``TF``).

Kein Test-Modul (fuehrender Unterstrich). Baut aus den Golden-Trip-JSONs
(``tests/fixtures/einstellung_auslieferung/``) in-Test veraenderte Varianten --
die Golden-Dateien selbst bleiben unangetastet -- und sendet sie ueber den
ECHTEN Loader/Kaskade/Formatter; einzige Naht ist der Transport-Aufzeichner.

SPEC: docs/specs/modules/fix_2422_s6_register_leeren.md
"""
from __future__ import annotations

import re

from tests.tdd._einstellung_auslieferung_fixtures import golden_dict, render_trip_dict

#: Spec AC-8 WORTGLEICH (nicht aus der Produktkonstante gelesen, damit die
#: Mutation "Id aus der Konstante streichen" den Testfall nicht mitloescht).
#: #2422 S6b (PO-Entscheid 2026-10-01): ``cape`` gestrichen -- nur waehlbare Groessen.
SPEC_SMS_FORMAT_IDS = ("cloud_total", "cloud_low", "cloud_mid", "cloud_high")
SPEC_OHNE_SMS_FORM = (
    "thunder", "wind_direction", "sunshine", "wind", "gust",
    "rain_probability", "precipitation",
)
#: ``cape`` ist im Katalog ``selectable=False`` (#1585) und erreicht deshalb
#: KEINEN Kanaltext ueber Layout/Kaskade -- seit S6b auch keine Roh/Einfach-Groesse.
WOLKEN = ("cloud_total", "cloud_low", "cloud_mid", "cloud_high")
WOLKEN_SYMBOL = {"cloud_total": "CT", "cloud_low": "CL", "cloud_mid": "CM", "cloud_high": "CH"}
#: Stufenwoerter der Wolken-Einfachform, niedrig -> hoch (Spec AC-5).
STUFEN = ("CLR", "FEW", "SCT", "BKN", "OVC")

#: Eintrag im Kanal-Layout je Modus: ``default`` = weder ``format_mode`` noch
#: ``use_friendly_format`` (Katalog-Default, AC-10); ``raw_explizit`` = ausdruecklich
#: ``format_mode: "raw"``. Rangfolge: format_mode > use_friendly_format=False > Katalog.
_MODUS_FELDER = {
    "raw": {"use_friendly_format": False},
    "einfach": {"use_friendly_format": True},
    "default": {},
    "raw_explizit": {"format_mode": "raw"},
}

#: Alle Metriken, die die SMS-Varianten aktiv fuehren (Reihenfolge = Layout-Order).
ALLE_SMS_METRIKEN = (
    "wind", "precipitation", "rain_probability", "gust", "thunder",
    "cloud_total", "cloud_low", "cloud_mid", "cloud_high", "sunshine",
    "wind_direction",
)


def _setze(liste: list, metric_id: str, *, order: int, modus: str) -> None:
    eintrag = next((m for m in liste if m["metric_id"] == metric_id), None)
    if eintrag is None:
        eintrag = {"metric_id": metric_id}
        liste.append(eintrag)
    eintrag.update({"enabled": True, "bucket": "primary", "order": order})
    eintrag.pop("use_friendly_format", None)
    eintrag.pop("format_mode", None)
    eintrag.update(_MODUS_FELDER[modus])


def variante(golden: str, modi: dict | None = None, *, standard: str = "raw") -> dict:
    """Golden-Dict mit ``ALLE_SMS_METRIKEN`` aktiv im SMS-Layout; ``modi`` setzt
    den Modus je Metrik, alle anderen bekommen ``standard`` (``raw``). Die
    Metrik steht bei Bedarf auch im globalen Maximum (Kaskade: Kanal <= global)."""
    d = golden_dict(golden)
    dc = d["display_config"]
    sms = dc["channel_layouts"]["sms"]
    for i, mid in enumerate(ALLE_SMS_METRIKEN, start=1):
        modus = (modi or {}).get(mid, standard)
        _setze(sms, mid, order=i, modus=modus)
        glob = next((m for m in dc["metrics"] if m["metric_id"] == mid), None)
        if glob is None:
            dc["metrics"].append({"metric_id": mid, "enabled": True, "order": 50 + i})
        else:
            glob["enabled"] = True
    return d


def sms_texte(monkeypatch, modi: dict | None = None, *, standard: str = "raw") -> dict:
    """Die drei SMS-artigen Texte {sms, premium_sms, telegram_kurzform} einer
    Variante: ``sms``/``premium_sms`` aus golden_b, ``telegram_kurzform`` aus
    golden_a (``telegram_style: kurzform``) -- je ein echter Versandlauf."""
    mit_b, _ = render_trip_dict(
        monkeypatch, variante("golden_b", modi, standard=standard), name="golden_b-s6",
    )
    mit_a, _ = render_trip_dict(
        monkeypatch, variante("golden_a", modi, standard=standard), name="golden_a-s6",
    )
    kurz = [s for s in mit_a.sendungen("telegram") if s["parse_mode"] is None]
    assert kurz, f"Vorbedingung: golden_a muss die Telegram-Kurzform senden: {mit_a!r}"
    return {
        "sms": mit_b.sendungen("sms")[0]["body"],
        "premium_sms": mit_b.sendungen("premium_sms")[0]["body"],
        "telegram_kurzform": kurz[0]["body"],
    }


def token(text: str, symbol: str) -> str | None:
    """Das Token von ``symbol`` (z.B. ``CT``) im SMS-Text -- exakt, ``W`` trifft
    nie ``WD:``. ``None``, wenn das Token fehlt."""
    rumpf = text.split(": ", 1)[1] if ": " in text else text
    for tok in rumpf.split(" "):
        if re.match(rf"^{re.escape(symbol)}(?=[:\d\-?])", tok):
            return tok
    return None


def stufe_aus_email_band(pct: float) -> str:
    """Erwartete SMS-Stufe fuer einen Wolkenwert, ABGELEITET aus der
    E-Mail-Klassifikation ``metric_format.cloud_emoji`` (nicht hart kopiert):
    die geordnete Folge der Emoji-Baender wird positionsgleich auf ``STUFEN``
    abgebildet."""
    from output.metric_format import cloud_emoji

    baender: list[str] = []
    for v in range(1, 101):
        e = cloud_emoji(float(v))
        if not baender or baender[-1] != e:
            baender.append(e)
    assert len(baender) == len(STUFEN), (
        f"Die E-Mail-Klassifikation hat {len(baender)} Baender, die SMS-Skala "
        f"{len(STUFEN)} Stufen: {baender}"
    )
    return STUFEN[baender.index(cloud_emoji(float(pct)))]


#: Band-Vokabular der E-Mail-Ampel in aufsteigender Schwere und die SMS-Stufe je
#: Band (Gewitter ``TH:``, AC-7: gruen -> ``-``, gelb -> ``L``, orange -> ``M``, rot -> ``H``).
AMPEL_REIHENFOLGE = ("green", "yellow", "orange", "red")
AMPEL_ZU_STUFE = dict(zip(AMPEL_REIHENFOLGE, ("-", "L", "M", "H")))


def zeile(forecast_kwargs: dict, specs, *, max_length: int = 160) -> str:
    """Echter Token-Builder + Renderer mit echten ``DailyForecast``-Werten. Ein
    (noch) fehlendes Produkt-Feld scheitert als Fehlschlag mit klarer Meldung."""
    import pytest

    from output.tokens.builder import build_token_line
    from output.tokens.dto import DailyForecast, NormalizedForecast
    from output.tokens.render import render_line

    try:
        tag = DailyForecast(**forecast_kwargs)
    except TypeError as exc:
        pytest.fail(f"DailyForecast kennt das Feld noch nicht: {exc}")
    line = build_token_line(
        NormalizedForecast(days=(tag,)), specs, report_type="evening", stage_name="E1",
    )
    return render_line(line, max_length)


def tokens_von(text: str) -> list[str]:
    return text.split(": ", 1)[1].split(" ")


def spec(symbol: str, modus: str, metric_id: str, **kw):
    """``MetricSpec`` wie der Versandpfad ihn tragen muss: ``format_mode`` je
    Metrik (``raw``/``symbol``) UND das Emoji-``friendly_label`` des Katalogs --
    der bisherige Einfach-Zweig des Builders gaebe dieses Emoji aus (nicht GSM-7)."""
    from app.metric_catalog import get_metric
    from output.tokens.dto import MetricSpec

    return MetricSpec(
        symbol=symbol, enabled=True, format_mode=modus,
        use_friendly_format=(modus == "symbol"),
        friendly_label=get_metric(metric_id).friendly_label or "", **kw,
    )
