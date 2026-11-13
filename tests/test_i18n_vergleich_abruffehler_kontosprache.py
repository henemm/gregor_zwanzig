"""Ortsvergleich: Ersatz-Fehlertext eines gescheiterten Wetterabrufs folgt der
Kontosprache (Issue #2751).

Der Text landet als ``LocationResult.error`` in der Vergleichsausgabe
(``vergleich.ort.fehler``: "Fehler: {fehler}" / "Error: {fehler}"). Echte
``user.json`` unter der isolierten Datenwurzel (conftest #1133), kein Mock.
"""
from __future__ import annotations

from services.comparison_engine import _abruf_fehlertext
from tests.helpers.inbound_sprache_fixture import nutzer_anlegen


def test_fehlertext_englisch_fuer_en_konto_deutsch_fuer_de_konto():
    nutzer_anlegen("abruf-en", "en")
    nutzer_anlegen("abruf-de", "de")
    nutzer_anlegen("abruf-ohne", None)
    assert _abruf_fehlertext(None, "abruf-en") == "Weather fetch failed"
    assert _abruf_fehlertext("", "abruf-de") == "Wetterabruf fehlgeschlagen"
    assert _abruf_fehlertext(None, "abruf-ohne") == "Wetterabruf fehlgeschlagen"


def test_meldung_der_quelle_wird_durch_katalogtext_ersetzt():
    """#2961: die Meldung der Quelle (kann Interna tragen) geht nur ins Log."""
    nutzer_anlegen("abruf-en2", "en")
    assert _abruf_fehlertext("budget_throttled", "abruf-en2") == "Weather fetch failed"
