"""Fixtures fuer den Pruefkatalog Trip von Issue #3047 („Einstellung = Mail").

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(§1 Aufbau, §2 Listen, Paket A).

Kein Test-Modul (fuehrender Unterstrich). Baut auf den Bausteinen von
``tests/tdd/_einstellung_auslieferung_fixtures.py`` auf (``render_trip_dict``,
``segment``, ``night_weather``, ``frisches_profil``, ``TRANSPORT_ENV``) und
VERAENDERT sie nicht. ``render_trip_dict`` kennt keinen 3-Tages-Ausblick
(``multi_day_trend`` bleibt dort leer); ``render_trip_mit_ausblick`` ergaenzt
genau das: drei Tageszeilen aus der Produktfunktion
``trip_report_scheduler.trend_zeile(...)`` -- dem Zeilenbau, den der
Zeitplaner (``_build_trend``) je Etappe ruft, nur ohne Wetter-Netz.

Kein ``Mock()``/``patch()``/``MagicMock``. Einzige Naht ist der Transport
(``tests/helpers/transport_mitschrift.py``). Loader, Kaskade, Renderer und
Versandweg laufen echt. Die ``user_id`` ist immer die des frischen Profils,
nie ``"default"`` (Mandantentrennung, AC-12).
"""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from typing import Optional

from app.loader import get_data_dir, load_trip
from services.notification_service import NotificationService, TripReportRequest
from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd._einstellung_auslieferung_fixtures import (  # noqa: F401  (Re-Export)
    DAY, STAGE_NAME, TRANSPORT_ENV, TZ, frisches_profil, night_weather,
    render_trip_dict, segment,
)

#: Feste Wochentagsnamen der drei Ausblick-Tage (nur Beschriftung).
AUSBLICK_TAGE = ("Mo", "Di", "Mi")

#: Standard-Metriken des Basis-Trips in KATALOGFOLGE (so legt der Editor das
#: Array ab; die eingestellte Position steht allein in ``order``).
BASIS_KATALOG = (
    "temperature", "wind", "gust", "wind_direction", "precipitation",
    "cloud_total", "uv_index",
)

_FEHLT = object()


def metrik_eintraege(
    folge: list[str], *, einfach: Optional[set[str]] = None,
    aus: Optional[set[str]] = None, katalog: tuple[str, ...] = BASIS_KATALOG,
) -> list[dict]:
    """Eintraege im Persistenzformat: Array in KATALOGFOLGE, ``order`` =
    Position in ``folge``. Metriken aus ``katalog``, die nicht in ``folge``
    stehen, werden mit ``enabled=False`` abgelegt (so speichert der Editor eine
    Abwahl). ``einfach``: Metriken mit ``use_friendly_format=True``, alle
    anderen Roh. ``aus``: zusaetzlich ausdruecklich abgewaehlt."""
    einfach = einfach or set()
    aus = aus or set()
    from app.metric_catalog import _METRICS

    rang = {m.id: i for i, m in enumerate(_METRICS)}
    reihen = sorted(set(katalog) | set(folge), key=lambda m: rang[m])
    eintraege = []
    hinten = len(folge)
    for mid in reihen:
        an = mid in folge and mid not in aus
        eintraege.append({
            "metric_id": mid, "enabled": an, "bucket": "primary",
            "order": folge.index(mid) if mid in folge else hinten,
            "use_friendly_format": mid in einfach,
        })
        if mid not in folge:
            hinten += 1
    return eintraege


def trip_json(
    folge: list[str], *, einfach: Optional[set[str]] = None,
    email_layout: Optional[list[dict]] = None,
    outlook_metrics=_FEHLT, outlook_metric_formats=_FEHLT,
    report_config: Optional[dict] = None, display: Optional[dict] = None,
    trip_id: str = "pruefkatalog-3047",
) -> dict:
    """Rohes Trip-JSON (Persistenzformat wie ``golden_a.json``).

    ``folge``: eingestellte Grundauswahl-Folge (globale ``metrics``).
    ``email_layout``: optional ``channel_layouts.email`` (rohe Eintraege).
    ``outlook_metrics``/``outlook_metric_formats``: fehlen, wenn nicht
    angegeben (Altbestand/nie eingestellt)."""
    heute = date.today()
    stages = []
    for i in range(3):
        stages.append({
            "id": f"T{i}", "name": f"Etappe {i}",
            "date": (heute + timedelta(days=i - 1)).isoformat(),
            "waypoints": [
                {"id": f"G{i}a", "name": "Start", "lat": 47.2692, "lon": 11.4041,
                 "elevation_m": 600},
                {"id": f"G{i}b", "name": "Ziel", "lat": 47.2892, "lon": 11.4241,
                 "elevation_m": 900},
            ],
        })
    dc: dict = {"trip_id": trip_id, "metrics": metrik_eintraege(folge, einfach=einfach)}
    if email_layout is not None:
        dc["channel_layouts"] = {"email": email_layout}
    if outlook_metrics is not _FEHLT:
        dc["outlook_metrics"] = outlook_metrics
    if outlook_metric_formats is not _FEHLT:
        dc["outlook_metric_formats"] = outlook_metric_formats
    dc.update(display or {})
    rc = {
        "trip_id": trip_id, "enabled": True,
        "morning_time": "07:00:00", "evening_time": "18:00:00",
        "send_email": True, "send_sms": False, "send_telegram": False,
        "send_premium_sms": False, "email_format": "full",
    }
    rc.update(report_config or {})
    return {
        "id": trip_id, "name": "Pruefkatalog 3047", "stages": stages,
        # #3047 E4: Briefing ODER Alarm an -> beides an; aus = beide Schalter aus.
        "official_alerts_enabled": False, "official_warnings": {"enabled": False},
        "display_config": dc, "report_config": rc,
    }


def sprache_setzen(uid: str, language: str) -> None:
    """Read-Modify-Write auf ``user.json`` des frischen Profils (#102)."""
    pfad = get_data_dir(uid) / "user.json"
    daten = json.loads(pfad.read_text())
    daten["language"] = language
    pfad.write_text(json.dumps(daten))


def ausblick_zeilen(trip, report_type: str, *, lang: str = "de") -> list[dict]:
    """Drei Ausblick-Tageszeilen aus dem Zeilenbau des Zeitplaners selbst
    (``trip_report_scheduler.trend_zeile``, den ``_build_trend`` je Etappe
    ruft -- #3047 F007: kein Nachbau der Argumente). Wetterpunkte aus
    ``segment()``, das Tagesaggregat aus der kanonischen Aggregation
    ``summarize_points`` (die handgebaute ``segment().aggregated`` traegt
    nicht alle Felder; ``_build_trend`` aggregiert die echten Segmente)."""
    from services.trip_report_scheduler import trend_zeile
    from services.weather_metrics import summarize_points

    zeilen = []
    for i, tag in enumerate(AUSBLICK_TAGE):
        seg = segment(DAY + 1 + i)
        agg = summarize_points(list(seg.timeseries.data))
        row = trend_zeile(trip, agg, [seg], tag, TZ, report_type=report_type, lang=lang)
        row["date"] = date(2026, 7, DAY + 1 + i)
        row["name"] = f"Etappe {i + 1}"
        zeilen.append(row)
    return zeilen


def render_trip_mit_ausblick(
    monkeypatch, data: dict, *, report_type: str = "evening",
    uid: Optional[str] = None, language: Optional[str] = None,
    mit_ausblick: bool = True, day_comparison=None,
    mitschrift: Optional[Kanalmitschrift] = None,
    official_alerts: Optional[list] = None,
) -> tuple[Kanalmitschrift, object, str]:
    """Wie ``render_trip_dict``, zusaetzlich mit drei Ausblick-Tageszeilen
    (``multi_day_trend``) und mit der ECHTEN ``user_id`` des Profils im Loader
    (nie ``"default"``). Gibt (Mitschrift, geladener Trip, user_id) zurueck.

    ``day_comparison``: optionaler Vortag-Vergleich (echtes
    ``DayComparison``-Datenobjekt) fuer die Vortag-Zeile (AC-9).
    ``mitschrift``: eine bereits installierte Mitschrift weiterverwenden
    (AC-12: zwei Nutzer, EIN Aufzeichner -- Kreuzpruefung der Empfaenger).
    ``official_alerts``: echte ``OfficialAlert``-Objekte am Etappen-Segment,
    wie der Abruf sie dort ablegt (WV6: amtliche Warnungen zuerst)."""
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    if mitschrift is None:
        mitschrift = aufzeichner_installieren(monkeypatch)
    uid = uid or frisches_profil()
    if language:
        sprache_setzen(uid, language)
    trip = load_trip(copy.deepcopy(data), user_id=uid)
    assert trip is not None, "Trip-JSON liess sich nicht laden"
    rc = trip.report_config
    trend = ausblick_zeilen(trip, report_type, lang=language or "de") if mit_ausblick else None
    seg = segment()
    if official_alerts:
        seg.official_alerts = list(official_alerts)
    request = TripReportRequest(
        trip=trip, report_type=report_type, segment_weather=[seg],
        trip_tz=TZ, night_weather=night_weather(), stage_name=STAGE_NAME,
        stage_stats={"distance_km": 12.0, "ascent_m": 900.0, "descent_m": 100.0,
                     "max_elevation_m": 1400},
        multi_day_trend=trend, day_comparison=day_comparison,
        report_config=rc, display_config=trip.display_config,
        send_email=rc.send_email, send_sms=rc.send_sms,
        send_telegram=rc.send_telegram, send_premium_sms=rc.send_premium_sms,
    )
    ergebnis = NotificationService(user_id=uid).send_trip_report(request)
    assert ergebnis.sent, f"Vorbedingung: Trip muss versendet werden: {ergebnis}"
    return mitschrift, trip, uid


def mail_sendung(mitschrift: Kanalmitschrift) -> dict:
    """Die EINE aufgezeichnete E-Mail-Sendung (Vorbedingung)."""
    sendungen = mitschrift.sendungen("email")
    assert len(sendungen) == 1, f"Vorbedingung: genau eine Mail erwartet: {mitschrift!r}"
    return sendungen[0]


def mail_teile(mitschrift: Kanalmitschrift) -> tuple[Optional[str], str]:
    """(HTML-Teil oder None bei Kompakt, Klartext-Teil) derselben Mail."""
    s = mail_sendung(mitschrift)
    if s["mail_format"] == "compact":
        return None, s["body"]
    return s["body"], s["plain_text_body"]


def eml_aus_mitschrift(mitschrift: Kanalmitschrift, *, lang: str = "de") -> bytes:
    """Die aufgezeichnete Sendung als echte MIME-Nachricht (.eml-Bytes) --
    gebaut von derselben reinen Produktfunktion ``build_mime_message`` wie
    ``EmailOutput.send`` (HTML + Klartext als multipart/alternative, Kompakt
    als einzelner Klartext-Teil, Marker-Header ``X-GZ-*``)."""
    from output.channels.email import build_mime_message

    s = mail_sendung(mitschrift)
    kompakt = s["mail_format"] == "compact"
    msg = build_mime_message(
        subject=s["subject"], body=s["body"], from_addr="gregor@example.invalid",
        to_header=s["empfaenger"], reply_to=None, html=not kompakt,
        plain_text_body=None if kompakt else s["plain_text_body"],
        mail_type=s["mail_type"], mail_format=s["mail_format"], lang=lang,
    )
    return msg.as_bytes()


def baue_trip_eml(
    trip_json: dict, *, report_type: str = "evening", mit_ausblick: bool = True,
    language: str = "de", monkeypatch=None,
) -> bytes:
    """Komplette Trip-Mail (HTML + Klartext bzw. Kompakt) als .eml-Bytes ueber
    den echten Versandweg -- fuer Paket C (Validatoren per ``--eml``).

    Ohne ``monkeypatch`` wird ein eigener ``pytest.MonkeyPatch`` benutzt und
    danach zurueckgesetzt (die Datenwurzel-Isolation der ``conftest.py`` muss
    trotzdem aktiv sein, also nur innerhalb eines pytest-Laufs aufrufen)."""
    import pytest

    if monkeypatch is None:
        with pytest.MonkeyPatch.context() as mp:
            return baue_trip_eml(trip_json, report_type=report_type,
                                 mit_ausblick=mit_ausblick, language=language,
                                 monkeypatch=mp)
    mitschrift, _trip, _uid = render_trip_mit_ausblick(
        monkeypatch, trip_json, report_type=report_type, language=language,
        mit_ausblick=mit_ausblick,
    )
    return eml_aus_mitschrift(mitschrift, lang=language)
