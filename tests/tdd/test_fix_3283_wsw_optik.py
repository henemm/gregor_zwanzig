"""Karte "Was steht wo": Optik-Befunde der Bildpruefung, Python-Teil (#3283).

SPEC: docs/specs/modules/fix_3283_was_steht_wo_optik.md -- B2 (SMS-Fenster,
Zusatzspalten), B3 (E-Mail-Kuerzel), B4 (Telegram-Zaehlregel); AC-2 bis AC-6.

Kern-Schicht: echte Dateien, echter Router, echte Renderer, fester Beispiel-
Datensatz (``services.placements_beispiel``), kein Netz, kein Mock. Jeder
Fall laeuft fuer zwei verschiedene Nutzer (Mandantentrennung).

Das Soll fuer B4 bildet der Test aus der ECHTEN Telegram-Nachricht
(``TripReportFormatter.format_email`` -> ``telegram_bubbles``, Kopfzeile der
Stundentabelle) und nicht aus der Antwort des Endpoints.
"""
from __future__ import annotations

import json
import re

import pytest

from tests.tdd import test_placements_tabelle_endpoint as _endpoint
from tests.tdd.test_placements_tabelle_endpoint import (
    NUTZER_A, NUTZER_B, _ok, _orte, _sprache, _trip, _zeile,
)

# Fixture des Endpoint-Tests wiederverwenden (pytest findet sie über den Modulnamen).
client = _endpoint.client

NUTZER = (NUTZER_A, NUTZER_B)

#: Abgeleitete SMS-Fenster-Kinder ohne eigenes Beispiel in der SMS-Spalte (B2).
FENSTER_KINDER = ("temperature_day_low", "temperature_day_high",
                  "wind_chill_night", "wind_chill_day_low", "wind_chill_day_high")


def _hat_buchstabe_oder_ziffer(text: str) -> bool:
    return any(c.isalnum() for c in text)


# ---------------------------------------------------------------------------
# AC-4 / B3: E-Mail-Beispiel mit Spaltenkuerzel (nur Trip), reine Symbole ohne
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("user", NUTZER)
def test_ac4_trip_email_beispiel_mit_kuerzel_orte_unveraendert(client, user, lang):
    from app.metric_catalog import get_metric

    _sprache(user, lang)
    # Orte-Kontext: Zelle bleibt ohne Kuerzel-Praefix (Uebersicht je Zeile).
    _orte(user, "o-3283-b3", anzahl=1, placements={"version": 1, "rows": []})
    orte = _ok(client, "o-3283-b3", "vergleich", user)
    for mid in ("temperature", "wind", "gust"):
        beispiel = _zeile(orte, mid)["cells"]["email"]["example"]
        assert beispiel, (mid, "Vorbedingung: Orte-E-Mail hat ein Beispiel")
        assert not beispiel.startswith(get_metric(mid).col_label + " "), (mid, beispiel)

    _trip(user, "t-3283-b3", grund=["temperature", "gust", "cloud_total", "wind"],
          placements={"version": 1, "rows": []})
    trip = _ok(client, "t-3283-b3", "route", user)
    temp = _zeile(trip, "temperature")["cells"]["email"]["example"]
    gust = _zeile(trip, "gust")["cells"]["email"]["example"]
    # Kuerzel = col_label, sprachunabhaengig (DE und EN gleich).
    assert get_metric("temperature").col_label == "Temp"
    assert re.fullmatch(r"Temp -?\d+(\.\d)?", temp or ""), temp
    assert re.fullmatch(r"Gust \d+(\.\d)?", gust or ""), gust
    # Reines Symbol (Bewoelkung Einfach): kein Buchstabe, keine Ziffer -> ohne Praefix.
    wolke = _zeile(trip, "cloud_total")["cells"]["email"]["example"]
    assert wolke and not _hat_buchstabe_oder_ziffer(wolke), (
        "Vorbedingung: Bewoelkung zeigt ein reines Symbol", wolke)
    assert not wolke.startswith(get_metric("cloud_total").col_label), wolke


# ---------------------------------------------------------------------------
# AC-2 / AC-3 / B2: SMS-Fenster-Kinder ohne Beispiel, Datenwahrheit bleibt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("user", NUTZER)
def test_ac3_sms_fenster_kinder_ohne_beispiel_nacht_mit(client, user):
    _trip(user, "t-3283-b2", grund=["temperature", "wind_chill", "wind", "gust"],
          placements={"version": 1, "rows": []})
    antwort = _ok(client, "t-3283-b2", "route", user)
    sms = antwort["sms_example"]["text"]
    token = sms.split(" ")[1:]  # #3174: Kopf ``E<n>`` ohne ``:``

    # Vorbedingung: die SMS selbst traegt die Fenster-Token weiter (sms_werte
    # bleibt, nur das Beispiel der Karte entfaellt).
    assert any(re.fullmatch(r"D-?\d+/-?\d+", t) for t in token), sms
    assert any(re.fullmatch(r"FN-?\d+", t) for t in token), sms

    for mid in FENSTER_KINDER:
        zelle = _zeile(antwort, mid)["cells"]["sms"]
        assert zelle["state"] == "on", (mid, zelle)
        assert zelle["example"] is None, (mid, zelle)
        assert zelle["mark"] is None, (mid, "darf nicht als 'passt nicht mehr' gelten")

    nacht = _zeile(antwort, "temperature_night")["cells"]["sms"]
    assert re.fullmatch(r"N-?\d+", nacht["example"] or ""), nacht
    assert nacht["example"] in token and nacht["mark"] is None

    # AC-2 Datenwahrheit: Ausblick liefert sein Beispiel weiter.
    assert _zeile(antwort, "gust")["cells"]["outlook"]["example"], "Ausblick ohne example"
    # Eltern-Zeilen behalten ihr SMS-Beispiel.
    assert _zeile(antwort, "wind")["cells"]["sms"]["example"] in token


@pytest.mark.parametrize("user", NUTZER)
def test_ac2_orte_stundenverlauf_und_ausblick_liefern_example(client, user):
    """Datenwahrheit (AC-2): das Frontend blendet den Beispielwert in den
    Zusatzspalten aus, der Endpoint liefert ihn weiter. Zusammen mit der
    SMS-Fenster-Regel geprueft, damit derselbe Lauf beide Seiten zeigt."""
    _orte(user, "o-3283-b2", anzahl=3, placements={"version": 1, "rows": []})
    orte = _ok(client, "o-3283-b2", "vergleich", user)
    wind = _zeile(orte, "wind")["cells"]
    assert wind["hourly"]["state"] == "on" and wind["hourly"]["example"], wind["hourly"]
    assert wind["outlook"]["example"], wind["outlook"]

    _trip(user, "t-3283-b2o", grund=["temperature", "wind"], placements={"version": 1, "rows": []})
    trip = _ok(client, "t-3283-b2o", "route", user)
    assert _zeile(trip, "wind")["cells"]["outlook"]["example"]
    assert _zeile(trip, "temperature_day_high")["cells"]["sms"]["example"] is None


# ---------------------------------------------------------------------------
# AC-5 / AC-6 / B4: Telegram-Zaehlregel "ab der achten Metrik"
# ---------------------------------------------------------------------------

#: Gewitter und Gefuehlte Temperatur vorn (Position 0/1), im alten Feld
#: ``bucket`` als ``secondary`` gefuehrt (Altbestand vor dem neuen Editor).
B4_FOLGE = ["thunder", "wind_chill", "wind", "gust", "precipitation",
            "rain_probability", "cloud_total", "humidity", "uv_index"]
ALT_SECONDARY = ("thunder", "wind_chill")


def _b4_trip(user: str, kennung: str, folge: list[str]) -> None:
    pfad = _trip(user, kennung, grund=folge,
                 placements={"version": 1, "rows": [{"metric_id": m} for m in folge]})
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    for mc in daten["display_config"]["metrics"]:
        if mc["metric_id"] in ALT_SECONDARY:
            mc["bucket"] = "secondary"
    pfad.write_text(json.dumps(daten), encoding="utf-8")


def _telegram_spalten(user: str, kennung: str) -> list[str]:
    """Metrik-Kennungen der Stundentabelle der ECHTEN Telegram-Nachricht
    (Kopfzeile der ersten ``<pre>``-Tabelle, Kuerzel -> Katalog-ID)."""
    from app.loader import get_data_root, load_trip
    from app.metric_catalog import get_metric
    from output.renderers.trip_report import TripReportFormatter
    from services import placements_beispiel as pb

    trip = load_trip(kennung, data_dir=get_data_root(), user_id=user)
    bericht = TripReportFormatter().format_email(
        pb.trip_segmente(), trip.name, "evening", display_config=trip.display_config,
        report_config=trip.report_config, trip=trip, tz=pb.ZONE,
        stage_name=trip.stages[0].name, lang="de",
    )
    blase = next(b for b in bericht.telegram_bubbles if "<pre>" in b)
    kopf = blase.split("<pre>", 1)[1].strip().split("\n", 1)[0].split()
    assert kopf[0] == "Zt", kopf
    kuerzel = {get_metric(m).compact_label: m for m in B4_FOLGE}
    return [kuerzel[k] for k in kopf[1:]]


@pytest.mark.parametrize("anzahl", [8, 9])
@pytest.mark.parametrize("user", NUTZER)
def test_ac5_ac6_telegram_nachricht_und_karte_folgen_der_zaehlregel(client, user, anzahl):
    folge = B4_FOLGE[:anzahl]
    kennung = f"t-3283-b4-{anzahl}"
    _b4_trip(user, kennung, folge)

    spalten = _telegram_spalten(user, kennung)
    # AC-5: Gewitter und Gefuehlte (Altwert secondary, Position < 8) haben eine Spalte.
    assert "thunder" in spalten and "wind_chill" in spalten, spalten
    # AC-6: genau die ersten sieben Metriken, in Tabellenfolge.
    assert spalten == folge[:7], spalten

    antwort = _ok(client, kennung, "route", user)
    tg = [z for z in antwort["rows"]
          if z["cells"]["telegram"]["state"] == "on" and z["parent"] is None]
    assert [z["metric_id"] for z in tg] == folge, [z["metric_id"] for z in tg]
    markiert = {z["metric_id"] for z in tg if z["cells"]["telegram"]["mark"] == "nur_tageswert"}
    # Karte und Nachricht stimmen ueberein: nur_tageswert = ohne Spalte = ab Position 8.
    assert markiert == set(folge[7:]), markiert
    assert markiert == set(folge) - set(spalten)
