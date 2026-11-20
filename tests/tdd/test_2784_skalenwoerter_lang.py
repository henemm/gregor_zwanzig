"""Stufenwoerter im Telegram-Briefing und in den Alarm-Stundenzeilen folgen der
Nutzersprache (Issue #2784, Epic #2644, ADR-0104).

SPEC: docs/specs/modules/i18n_skalenwoerter_lang_2784.md

Echte Renderer (``render_telegram_bubbles`` ueber die Golden-Fixture,
``render_email``/``render_telegram`` des Alarms), netzfrei, kein Mock.
Protokoll-Kuerzel (TH, VS, FZ) bleiben (Zeitspalten-Kopf folgt der Sprache, #3014), Deutsch bleibt byte-gleich,
die Ausblick-Gewitterzelle bleibt nach #2665 bewusst deutsch.
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

import pytest

from app.ampel import resolve_ampel
from app.models import ThunderLevel
from output.renderers.alert.model import AlertEvent, AlertHourRow, AlertMessage
from output.renderers.alert.render import render_email, render_sms, render_telegram
from output.renderers.narrow import _overview_line, _tg_day_footer
from tests.helpers.telegram_briefing_fixture import (
    TZ, _rows, _segment, _trend, build_texts,
)

_DE_STUFE = re.compile(r"\b(kein|leicht|mittel|hoch|mäßig|stark|sehr stark|schwach)\b")


# ---------------------------------------------------------------------------
# Telegram-Briefing (Stil rich)
# ---------------------------------------------------------------------------

def _bubble(texts: list[str], kopf: str) -> str:
    treffer = [b for b in texts if b.startswith(kopf)]
    assert len(treffer) == 1, f"Bubble {kopf!r} nicht eindeutig: {texts!r}"
    return treffer[0]


def _tabellen(texts: list[str]) -> list[str]:
    tabs = [b for b in texts if "<pre>" in b]
    assert len(tabs) == 2, "Vorbedingung: Segment- und Ziel-Tabelle"
    return tabs


def test_ac1_briefing_en_kurzuebersicht_und_fusszeile_mit_englischem_stufenwort():
    """AC-1: Kurzuebersicht (``TH ...``) und Fusszeile (``Air mass ...``) tragen
    das englische Gewitter-Stufenwort, Kuerzel TH/VS/FZ bleiben."""
    summary = _bubble(build_texts(lang="en"), "Summary")
    zeilen = summary.splitlines()
    assert "TH light" in zeilen, f"Kurzuebersicht ohne englisches Stufenwort:\n{summary}"
    assert "VS 15" in zeilen and "FZ 2800" in zeilen, "Kuerzel VS/FZ muessen bleiben"
    assert "Air mass light" in summary, f"Fusszeile ohne englisches Stufenwort:\n{summary}"
    assert not _DE_STUFE.search(summary), f"deutsches Stufenwort im en-Briefing:\n{summary}"


def test_ac1_briefing_en_segmenttabellen_ohne_deutsches_stufenwort():
    """AC-1: Segment-Tabellen zeigen ``none``/``light`` statt ``kein``/``leicht``,
    Kopfzeile mit Protokoll-Kuerzeln unveraendert."""
    for tab in _tabellen(build_texts(lang="en")):
        kopf = next(z for z in tab.splitlines() if z.startswith("Hr "))
        assert kopf.split() == ["Hr", "T", "W", "G", "R", "TH", "VS", "FZ"]
        assert not _DE_STUFE.search(tab), f"deutsches Stufenwort in en-Tabelle:\n{tab}"
    ziel = _tabellen(build_texts(lang="en"))[1]
    zeile_13 = next(z for z in ziel.splitlines() if z.startswith("13 "))
    zeile_16 = next(z for z in ziel.splitlines() if z.startswith("16 "))
    assert zeile_13.split()[5] == "light", zeile_13
    assert zeile_16.split()[5] == "none", zeile_16


def test_ac4_briefing_de_behaelt_deutsche_stufenwoerter():
    """AC-4: Deutsch (mit und ohne ``lang``) unveraendert deutsch."""
    for kw in ({}, {"lang": "de"}):
        texts = build_texts(**kw)
        summary = _bubble(texts, "Kurzübersicht")
        assert "TH leicht" in summary.splitlines()
        assert "Luftmasse leicht" in summary
        ziel = _tabellen(texts)[1]
        assert next(z for z in ziel.splitlines() if z.startswith("13 ")).split()[5] == "leicht"
        assert next(z for z in ziel.splitlines() if z.startswith("16 ")).split()[5] == "kein"


def _segment_ohne_gewitter():
    """Fixture-Segment, dessen ganzer Tag Gewitterstufe NONE traegt."""
    seg = _segment(1, (0.0, 8.4), (7, 12), [])
    daten = [replace(p, thunder_level=ThunderLevel.NONE) for p in seg.timeseries.data]
    return replace(seg, timeseries=replace(seg.timeseries, data=daten))


@pytest.mark.parametrize("lang, wort", [("en", "none"), ("de", "kein")])
def test_ac1_ac4_fusszeile_ohne_gewitter_folgt_der_sprache(lang, wort):
    """AC-1/AC-4: Entwarnungszweig der Fusszeile (Stufe NONE) in ``lang``;
    eine Datenluecke zeigt sprachunabhaengig ``?`` (#1331)."""
    seg = _segment_ohne_gewitter()
    assert _tg_day_footer([seg], ["thunder"], tz=TZ, lang=lang) == f"⚡ {wort}"
    assert _tg_day_footer([seg], ["thunder"], tz=TZ, has_gap=True, lang=lang) == "⚡ ?"


@pytest.mark.parametrize("lang, wort", [("en", "none"), ("de", "kein")])
def test_ac1_ac4_kurzuebersicht_ohne_gewitter_folgt_der_sprache(lang, wort):
    """AC-1/AC-4: Kurzuebersicht mit Tagesfenster-Stufe 0 in ``lang``;
    Datenluecke ``?``."""
    ampel = resolve_ampel(None)
    rows = [_rows(range(7, 13))]
    assert _overview_line(
        "thunder", rows, set(), day_thunder_sev=0, ampel=ampel, lang=lang,
    ) == f"TH {wort}"
    assert _overview_line(
        "thunder", rows, set(), day_thunder_sev=0, has_gap=True, ampel=ampel, lang=lang,
    ) == "TH ?"


@pytest.mark.parametrize("lang, wort", [("en", "medium"), ("de", "mittel")])
def test_ac1_ac4_kurzuebersicht_rueckfall_ohne_tagesfenster_folgt_der_sprache(lang, wort):
    """AC-1/AC-4: Rueckfallpfad ohne ``day_thunder_sev`` (schlimmste Zeile
    der Gehzeit-Reihen) zeigt das Stufenwort in ``lang``."""
    rows = _rows(range(7, 13))
    rows[2]["thunder"] = "MED"
    assert _overview_line(
        "thunder", [rows], set(), ampel=resolve_ampel(None), lang=lang,
    ) == f"TH {wort}"


def test_ac5_ausblick_gewitterzelle_bleibt_deutsch():
    """AC-5: Gewitterteil der Telegram-Ausblick-Zeile bleibt nach #2665 bewusst
    sprachunabhaengig deutsch (Regressions-Waechter, keine stille Umkehr)."""
    trend = _trend(date(2026, 10, 30))
    trend[0]["thunder"] = "MED"
    de = _bubble(build_texts(lang="de", multi_day_trend=trend), "3-Tages-Ausblick").splitlines()[1]
    en = _bubble(build_texts(lang="en", multi_day_trend=trend), "3-day outlook").splitlines()[1]
    assert de.endswith("⚡mittel") and en.endswith("⚡mittel"), (de, en)


# ---------------------------------------------------------------------------
# Alarm-Stundenzeilen (Mail Klartext + HTML, Telegram)
# ---------------------------------------------------------------------------

def _event(metric_id: str, hours: tuple, **extra) -> AlertEvent:
    basis = dict(
        metric_id=metric_id, threshold=1.0, cmp="über", occurred_at=hours[0].time,
        km_from=8.0, km_to=14.0, segment_id="3", stage_number=3,
        value_from=hours[0].value_from, value_to=hours[0].value_to,
        hours=hours, hours_range=(hours[0].time, hours[-1].time), hours_capped=False,
    )
    basis.update(extra)
    return AlertEvent(**basis)


def _msg(mode: str) -> AlertMessage:
    boeen = _event("gust", (AlertHourRow("14:00", 40.0, 66.0),
                            AlertHourRow("15:00", 45.0, 72.0)), threshold=20.0)
    regen = _event("precipitation", (AlertHourRow("16:00", 0.5, 6.0),), threshold=2.0)
    gewitter = _event("thunder", (AlertHourRow("17:00", 1.0, 3.0),))
    fm = {"gust": mode, "precip": mode, "thunder": "raw"}
    return AlertMessage(
        trip_short="GR20", stand_at="06:00", events=(boeen, regen, gewitter),
        ampel=resolve_ampel(None), format_modes={"email": fm, "telegram": fm},
    )


def _stundenzeilen(text: str) -> list[str]:
    return [z for z in text.splitlines() if re.match(r"^\d\d:\d\d \| ", z)]


def _html_zellen(html: str) -> list[str]:
    return re.findall(r"<tr><td[^>]*>\d\d:\d\d</td><td[^>]*>(.*?)</td></tr>", html)


_EN_EINFACH = [
    "14:00 | very strong → very strong",
    "15:00 | very strong → very strong",
    "16:00 | light → moderate",
    "17:00 | light → high",
]
_DE_EINFACH = [
    "14:00 | sehr stark → sehr stark",
    "15:00 | sehr stark → sehr stark",
    "16:00 | leicht → mäßig",
    "17:00 | leicht → hoch",
]


def test_ac2_ac3_alarm_en_einfach_klartext_und_telegram_englisch():
    """AC-2/AC-3: Modus Einfach, Sprache en -- Wind-/Regen-Adjektive und
    Gewitter-Stufenwort englisch in Mail-Klartext und Telegram."""
    msg = _msg("simplified")
    _html, plain = render_email(msg, lang="en")
    assert _stundenzeilen(plain) == _EN_EINFACH
    assert _stundenzeilen(render_telegram(msg, lang="en")) == _EN_EINFACH


def test_ac3_alarm_en_html_gewitterzeile_englisch():
    """AC-3 (HTML): Gewitter-Stundenzeile ROH zeigt das englische Stufenwort;
    Einfach-Zellen bleiben CSS-Punkte ohne deutsches Wort."""
    html, _plain = render_email(_msg("simplified"), lang="en")
    zellen = _html_zellen(html)
    assert zellen[-1] == "light → high", zellen
    for z in zellen:
        assert not _DE_STUFE.search(re.sub(r"<[^>]+>", "", z)), z


def test_ac3_alarm_en_roh_gewitterzeile_englisch():
    """AC-3 (Modus Roh): Zahlen bleiben, Gewitter-Stufenwort englisch."""
    msg = _msg("raw")
    _html, plain = render_email(msg, lang="en")
    erwartet = ["14:00 | 40 → 66", "15:00 | 45 → 72", "16:00 | 0.5 → 6.0",
                "17:00 | light → high"]
    assert _stundenzeilen(plain) == erwartet
    assert _stundenzeilen(render_telegram(msg, lang="en")) == erwartet


def test_ac4_alarm_de_unveraendert():
    """AC-4: Deutsch (mit und ohne ``lang``) unveraendert."""
    msg = _msg("simplified")
    for kw in ({}, {"lang": "de"}):
        html, plain = render_email(msg, **kw)
        assert _stundenzeilen(plain) == _DE_EINFACH
        assert _stundenzeilen(render_telegram(msg, **kw)) == _DE_EINFACH
        assert _html_zellen(html)[-1] == "leicht → hoch"


def test_ac5_alarm_kurzform_sms_text_unberuehrt():
    """AC-5: Kurzform (= SMS-Text) traegt nur Protokoll-Token, keine Stufenwoerter."""
    sms = render_sms(_msg("simplified"))
    assert not _DE_STUFE.search(sms) and "light" not in sms, sms
