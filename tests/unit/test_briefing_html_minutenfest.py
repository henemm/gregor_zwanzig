"""#2744 AC-4: Briefing-HTML-Vergleich haelt auch ueber einen Minutenwechsel.

Der Erzeugungszeitstempel (``HH:MM``) ist Produktverhalten und bleibt. Der
Test stellt deshalb die Uhr um BEIDE Renderlaeufe fest. RED heute: die Hilfe
``render_paar_bei_fester_uhr`` existiert nicht (ImportError).

Beleg der Anfaelligkeit (gemessen 2026-11-06): ``render_reich()`` bei
12:59:59 und ``render_reich("de")`` bei 13:00:01 liefern UNGLEICHES HTML.
"""
from __future__ import annotations

from freezegun import freeze_time

from tests.helpers.briefing_html_sprache_fixture import (
    render_paar_bei_fester_uhr,
    render_reich,
)


def test_ac4_paar_ist_gleich_obwohl_die_uhr_ueber_die_minute_laufen_wuerde():
    # Ein umgebender, tickender Rahmen simuliert den Minutenwechsel; die Hilfe
    # muss ihn durch ihren eigenen festen Block neutralisieren.
    with freeze_time("2026-11-05 12:59:59", auto_tick_seconds=30):
        ohne_lang, mit_de = render_paar_bei_fester_uhr()
    assert ohne_lang.email_html == mit_de.email_html


def test_ac4_ohne_festen_block_waere_der_minutenwechsel_sichtbar():
    """Gegenprobe: der Messaufbau ist scharf -- zwei Laeufe in verschiedenen
    Minuten liefern wirklich verschiedenes HTML."""
    with freeze_time("2026-11-05 12:59:59"):
        a = render_reich().email_html
    with freeze_time("2026-11-05 13:00:01"):
        b = render_reich("de").email_html
    assert a != b
