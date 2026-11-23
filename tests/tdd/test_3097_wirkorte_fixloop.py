"""#3097 Fix-Schleife 1: Zusicherungen dort pruefen, wo sie wirken (Adversary F005).

SPEC: docs/specs/modules/feat_3097_orte_stundenverlauf_darstellung.md (AC-1, AC-4)

- F005: nur echte Booleans gelten als Einstellung. ``"true"``/``1`` aus einer
  verbogenen Konfiguration schalten den Stundenverlauf NICHT auf Einfach --
  geprueft am Resolver-Ergebnis und an der zugestellten Mail.

F004 (Validator-Render-Weg) ist hier bewusst NICHT abgedeckt: der Stub-Ort von
``render_compare_email_preview`` hat keine Stundendaten, die Stundentabelle
entsteht dort gar nicht -- die Durchreichung ist am HTML unbeobachtbar.

Kein ``Mock()``/``patch()``: echte Resolver, echte Mail-Kette.
"""
from __future__ import annotations

from tests.tdd.test_3097_stundenverlauf_darstellung import (
    PUNKT, _preset, _zahl, html_stunden, klartext_stunden,
)
from tests.helpers.einstellung_gleich_mail_orte import sende_orte_mail


# ---------------------------------------------------------------------------
# F005: nicht-boolesche Werte gelten nicht als Einfach
# ---------------------------------------------------------------------------

def test_f005_resolver_ignoriert_nicht_boolesche_werte():
    from services.channel_list_resolver import resolve_channel_lists
    from tests.helpers.tabelle_aus_wunsch import orte_wunsch_als_tabelle

    # #3237: der Stundenverlauf-Wunsch wirkt nur ueber die Tabelle.
    dc = orte_wunsch_als_tabelle(_preset(
        ["wind", "gust", "precipitation", "temperature"],
        {"wind": "true", "gust": 1, "precipitation": True, "temperature": None}))["display_config"]
    formate = {z.metric_id: z.format for z in resolve_channel_lists(dc, "compare").hourly}
    # #3237: "nicht Einfach" steht in der Tabelle ausdruecklich als ``raw``
    # (Orte-Stundenverlauf Roh; frueher ``None`` = Flaechen-Standard Roh).
    assert formate == {"wind": "raw", "gust": "raw", "precipitation": "simplified",
                       "temperature": None}, formate


def test_f005_mail_bleibt_roh_bei_nicht_booleschen_werten():
    ohne = sende_orte_mail(_preset(["wind", "gust", "temperature"]))
    verbogen = sende_orte_mail(_preset(["wind", "gust", "temperature"], {"wind": "true", "gust": 1}))
    assert (verbogen.html, verbogen.plain) == (ohne.html, ohne.plain), (
        "\"true\"/1 im Feld hourly_metric_formats veraendert die Mail -- nur echte "
        "Booleans duerfen als Einstellung gelten")
    for tab in html_stunden(verbogen.html):
        assert all(_zahl(t) and PUNKT not in f for t, f in tab["wind"]), tab["wind"]
    for tab in klartext_stunden(verbogen.plain):
        assert all(_zahl(z) for z in tab["gust"]), tab["gust"]
