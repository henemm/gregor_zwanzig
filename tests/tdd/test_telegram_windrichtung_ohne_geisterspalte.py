"""TDD RED -- #2422 S6, B5: Telegram rich zeigt bei "Windrichtung mit Wind
zusammengefuehrt" KEINE eigene Spalte ``WD``.

SPEC: docs/specs/modules/fix_2422_s6_register_leeren.md (AC-13)

Heute: der Merge laeuft (die Windzelle traegt Wert und Richtung, "20 W"), aber
``channel_layout.render_for_channel`` filtert die Layout-Spalte ``wind_direction``
nicht -- es entsteht eine Geisterspalte ``WD`` mit nur Platzhaltern, die wegen des
7er-Limits eine ECHTE Metrik (hier ``humidity``) aus der Tabelle verdraengt.

Geprueft wird am ROHEN Tabellenkopf (``Zt ...``-Zeile) des gesendeten Telegram-
Textes -- NICHT ueber den Orakel-Parser, der reine Platzhalter-Spalten ohnehin
still verwirft und damit die Geisterspalte nie sieht.

Ortsvergleich-Telegram bleibt unberuehrt: die Ortsvergleich-Waechter der Scheibe S5
(``test_compare_einstellung_auslieferung_kette.py``) laufen unveraendert mit.

RED-Gruende (heute): ``WD`` steht im Kopf; ``humidity`` fehlt im Kopf;
``demoted_count`` zaehlt ``wind_direction`` mit.
GUARDS (heute gruen): Windrichtung im Roh-Modus bleibt eine eigene Spalte; ohne
aktiven Wind gibt es nichts zu verschmelzen -- die Spalte bleibt.
"""
from __future__ import annotations

import re

import pytest

from app.loader import load_trip
from app.metric_catalog import get_metric
from output.renderers.channel_layout import render_for_channel, telegram_metric_notice
from tests.helpers.einstellung_auslieferung_orakel import _kanal_texte
from tests.tdd._einstellung_auslieferung_fixtures import golden_dict, render_golden

pytestmark = pytest.mark.filterwarnings("ignore")

_WD = get_metric("wind_direction").compact_label
_HU = get_metric("humidity").compact_label
_G = get_metric("gust").compact_label


def _tabelle(mitschrift) -> tuple[list[str], str]:
    """(Kopf-Tokens ohne 'Zt', erste Datenzeile) der Telegram-rich-Stunden-Tabelle
    -- roh, ohne jede Platzhalter-Filterung."""
    bodies, _ = _kanal_texte(mitschrift, "telegram_rich")
    for body in bodies:
        zeilen = body.splitlines()
        for i, zeile in enumerate(zeilen):
            if zeile.startswith("Zt "):
                return zeile.split()[1:], zeilen[i + 1]
    raise AssertionError(f"keine Telegram-Tabelle ('Zt ...') gefunden: {bodies!r}")


def test_ac13_kein_wd_im_tabellenkopf_windzelle_traegt_die_richtung(monkeypatch):
    """AC-13: Given ``wind_direction`` im Skalenmodus zusammen mit ``wind`` im
    Telegram-Layout (golden_b), When Telegram rich gerendert wird, Then gibt es
    KEINE eigene Spalte ``WD`` im Tabellenkopf, und die Windzelle zeigt Wert UND
    Richtung ("20 W").

    Mutation (Merge-Filter in ``render_for_channel`` entfernt) -> ``WD`` steht
    wieder im Kopf -> rot."""
    mit, _ = render_golden(monkeypatch, "golden_b")
    kopf, erste_zeile = _tabelle(mit)
    assert _WD not in kopf, (
        f"AC-13: Geisterspalte {_WD!r} im Telegram-Tabellenkopf {kopf} -- die "
        f"Richtung ist bereits in die Windzelle verschmolzen."
    )
    assert re.search(r"(?<!\d)20 W(?!\S)", erste_zeile), (
        f"AC-13: die Windzelle muss Wert und Richtung tragen ('20 W'): {erste_zeile!r}"
    )


def test_ac13_verdraengte_metrik_rueckt_in_die_tabelle_nach(monkeypatch):
    """AC-13: die bisher wegen des 7er-Limits verdraengte Metrik (``humidity``, in
    golden_b nach ``wind_direction`` eingereiht) steht jetzt im Tabellenkopf;
    ``gust`` bleibt die eine verdraengte (Register-Eintrag, Kurzuebersicht)."""
    mit, _ = render_golden(monkeypatch, "golden_b")
    kopf, _ = _tabelle(mit)
    assert _HU in kopf, (
        f"AC-13: {_HU!r} (humidity) muss nachruecken, Tabellenkopf: {kopf}"
    )
    assert _G not in kopf, f"AC-13: gust wird vom 7er-Limit weiter verdraengt: {kopf}"
    bodies, _ = _kanal_texte(mit, "telegram_rich")
    hinweis = telegram_metric_notice(1, context="route")
    # Der Hinweis ist 60 Zeichen lang und wird in der Kurzuebersicht bei 56
    # Zeichen umbrochen (narrow._wrap) -- Umbruch-unabhaengig vergleichen.
    flach = [" ".join(b.split()) for b in bodies]
    assert any(hinweis in b for b in flach), (
        f"AC-13: der Hinweis auf EINE verdraengte Groesse ({hinweis!r}) fehlt -- "
        f"wind_direction darf nicht mitgezaehlt werden."
    )
    assert not any(telegram_metric_notice(2, context="route") in b for b in flach)


def test_ac13_render_for_channel_table_columns_und_demoted_count():
    """AC-13: ``render_for_channel("telegram", ...)`` fuer golden_b -- die Spalten
    enthalten ``wind_direction`` NICHT, ``humidity`` ist die 7. und letzte
    Metrik-Spalte, ``demoted_count`` zaehlt nur ``gust`` (1). Der Filter sitzt VOR
    der Begrenzung, damit Spalten UND Zaehler stimmen."""
    trip = load_trip(golden_dict("golden_b"), user_id="default")
    layout = render_for_channel("telegram", trip.display_config, "evening")
    assert "wind_direction" not in layout.table_columns, (
        f"AC-13: Geisterspalte in table_columns: {layout.table_columns}"
    )
    assert layout.table_columns == [
        "precipitation", "wind", "rain_probability", "thunder",
        "cloud_total", "cloud_low", "humidity",
    ], f"AC-13: table_columns={layout.table_columns}"
    assert layout.demoted_count == 1, (
        f"AC-13: demoted_count zaehlt wind_direction mit: {layout.demoted_count}"
    )


def _variante_wd(mutation) -> dict:
    d = golden_dict("golden_b")
    mutation(d["display_config"]["channel_layouts"]["telegram"])
    return d


def test_ac13_guard_windrichtung_im_roh_modus_bleibt_eigene_spalte():
    """AC-13 (GUARD, heute gruen): ist ``wind_direction`` im Telegram-Layout
    ausdruecklich ``format_mode: "raw"`` (Gradzahl), wird NICHT verschmolzen
    (``should_merge_wind_dir`` verlangt den Skalenmodus) -- die Spalte bleibt. Ein
    zu breiter Filter, der jede ``wind_direction``-Spalte loescht, faellt hier
    auf."""
    def roh(layout):
        for m in layout:
            if m["metric_id"] == "wind_direction":
                m.pop("use_friendly_format", None)
                m["format_mode"] = "raw"

    trip = load_trip(_variante_wd(roh), user_id="default")
    layout = render_for_channel("telegram", trip.display_config, "evening")
    assert "wind_direction" in layout.table_columns, (
        f"GUARD: Windrichtung im Roh-Modus muss eine eigene Spalte bleiben: "
        f"{layout.table_columns}"
    )


def test_ac13_guard_ohne_aktiven_wind_bleibt_die_spalte():
    """AC-13 (GUARD, heute gruen): ohne aktiven ``wind`` im Telegram-Layout gibt es
    nichts zu verschmelzen -- die ``wind_direction``-Spalte bleibt."""
    def ohne_wind(layout):
        for m in layout:
            if m["metric_id"] == "wind":
                m["enabled"] = False
                m["bucket"] = "secondary"

    trip = load_trip(_variante_wd(ohne_wind), user_id="default")
    layout = render_for_channel("telegram", trip.display_config, "evening")
    assert "wind_direction" in layout.table_columns, (
        f"GUARD: ohne Wind keine Verschmelzung: {layout.table_columns}"
    )


def test_ac13_kurzuebersicht_hat_keine_eigene_wd_zeile_richtung_steckt_in_der_windzeile(monkeypatch):
    """AC-13 (Kurzuebersicht, #2422 S6): dieselbe Geisterspalte in anderer Form --
    bei zusammengefuehrter Windrichtung steht in der Telegram-Kurzuebersicht KEINE
    eigene Zeile ``WD -``; die Richtung steckt in der Windzeile (``W 20 W``).

    Mutation (Filter in ``narrow.py`` entfernt) -> ``WD –`` steht wieder da -> rot."""
    mit, _ = render_golden(monkeypatch, "golden_b")
    bodies, _ = _kanal_texte(mit, "telegram_rich")
    uebersicht = next(b for b in bodies if b.startswith("Kurzübersicht"))
    zeilen = uebersicht.splitlines()
    assert not any(z.split()[:1] == [_WD] for z in zeilen if z.strip()), (
        f"AC-13: eigene {_WD!r}-Zeile in der Kurzuebersicht: {zeilen}"
    )
    assert any(re.match(r"W 20 W\b", z) for z in zeilen), (
        f"AC-13: die Windzeile muss die Richtung tragen: {zeilen}"
    )
