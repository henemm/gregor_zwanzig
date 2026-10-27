"""`/api/sms-symbols` fuehrt jede Vergleichsgroesse (#2232, Implementation
Details Punkt 3).

SPEC: docs/specs/modules/fix_2232_kuerzel_ein_modell_trip_vergleich.md

Ab dieser Scheibe speisen BEIDE Editor-Flaechen -- Trip und die drei
Vergleichs-Editoren -- ihre Kurzform-Marke aus diesem einen Endpoint, der
Vergleich adressiert ihn ueber `kuerzel_metric_id ?? metric_id`. Faellt dort
eine Groesse heraus, zeigt die Zeile im Editor gar keine Marke mehr -- still,
ohne Fehler. Genau das bewacht dieser Test.

Gemessen 2026-09-09: alle 25 ausgelieferten Vergleichsgroessen kommen an, ein
Endpoint-Fallback auf `MetricDefinition.sms_code` ist deshalb NICHT noetig
(die Spec sah ihn nur fuer den Fall einer Luecke vor).

Der Endpoint wird als Funktion aufgerufen (kein Netz, kein TestClient noetig) --
derselbe Wirkort, den `api/routers/config.py` registriert.
"""
from __future__ import annotations

from api.routers.config import get_sms_symbols
from output.renderers.compare_metric_catalog import (
    get_compare_metric_catalog, kuerzel_metric_id_for,
)


def _symbole_je_kennung() -> dict[str, list[str]]:
    return {m["metric_id"]: m["sms_symbols"] for m in get_sms_symbols()["metrics"]}


def test_jede_ausgelieferte_vergleichsgroesse_hat_eine_marke():
    """Jede Groesse, die der Vergleichs-Katalog ausliefert, findet unter ihrer
    Kuerzel-Kennung mindestens ein Symbol im Endpoint."""
    symbole = _symbole_je_kennung()
    katalog = get_compare_metric_catalog()
    assert len(katalog) >= 20, (
        f"Nur {len(katalog)} Vergleichsgroessen ausgeliefert -- der Test "
        "pruefte praktisch nichts."
    )

    ohne_marke = [
        (e["key"], kuerzel_metric_id_for(e))
        for e in katalog
        if not symbole.get(kuerzel_metric_id_for(e))
    ]
    assert not ohne_marke, (
        f"{len(ohne_marke)} Vergleichsgroessen finden in /api/sms-symbols kein "
        f"Kuerzel: {ohne_marke!r}. Ihre Zeile im Vergleichs-Editor traegt dann "
        "gar keine Kurzform-Marke. Abhilfe laut Spec: Fallback auf "
        "`MetricDefinition.sms_code` IM ENDPOINT (nicht im Client)."
    )


def test_die_temperatur_familie_traegt_genau_die_trip_kuerzel():
    """Die vier umgebauten Groessen liefern die Marken, die auch die Trip-SMS
    sendet -- der Endpoint ist ab #2232 die gemeinsame Quelle beider Flaechen.

    Bewusst gegen den Endpoint UND gegen das Register gefuehrt: getippt wird
    hier nur, WELCHE Groesse gemeint ist, nicht welches Kuerzel sie traegt."""
    from app.metric_catalog import get_metric

    symbole = _symbole_je_kennung()
    nach_key = {e["key"]: e for e in get_compare_metric_catalog()}
    for key, kennung in (
        ("temp_max_c", "temperature_day_high"),
        ("temp_min_c", "temperature_day_low"),
        ("wind_chill_max_c", "wind_chill_day_high"),
        ("wind_chill_min_c", "wind_chill_day_low"),
    ):
        assert kuerzel_metric_id_for(nach_key[key]) == kennung, (
            f"{key!r} loest seine Kuerzel-Kennung nicht auf {kennung!r} auf."
        )
        assert symbole.get(kennung) == list(get_metric(kennung).sms_multi_symbols), (
            f"Die Endpoint-Marke fuer {kennung!r} ({symbole.get(kennung)!r}) "
            "weicht vom Register ab "
            f"({list(get_metric(kennung).sms_multi_symbols)!r})."
        )


def test_die_kuerzel_kennung_reist_in_der_katalog_antwort_mit():
    """Der Client darf keine zweite Kuerzel-Quelle fuehren: die Antwort des
    Vergleichs-Katalogs nennt die Kennung selbst, unter der die Marke
    nachzuschlagen ist."""
    fehlend = [
        e["key"] for e in get_compare_metric_catalog() if not e.get("kuerzel_metric_id")
    ]
    assert not fehlend, (
        f"Katalogzeilen ohne `kuerzel_metric_id` in der Antwort: {fehlend!r} -- "
        "das Frontend muesste dann selbst entscheiden, welche Kennung gilt."
    )
