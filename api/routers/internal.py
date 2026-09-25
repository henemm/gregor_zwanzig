"""Interne Endpunkte für Tooling/Validator und für den Go-Prozess (Issue #115).

Spec: docs/specs/modules/validator_internal_loaded_endpoint.md
Spec: docs/specs/modules/forecast_go_pfad_kontingent.md (#2391)

Macht den Python-Loader-Output für den External Validator (Issue #110)
direkt beobachtbar. Nicht versionsstabil, nicht für Frontend/Endbenutzer.

Seit #2391 nicht mehr ausschliesslich read-only: die
Kontingent-Reservierung (``POST /api/_internal/forecast-budget/reserve``)
bucht im Erfolgsfall in den Tageszaehler (ADR-0076). Alle Routen dieses
Moduls liegen hinter ``X-GZ-Core-Auth`` (ADR-0062, Middleware in
``api/main.py``).
"""
import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import Settings
from output.channels.base import OutputConfigError, OutputError
from output.channels.sms import SMSOutput

# Issue #1308: Frueher gab es hier ein echtes Modul-Duplikat -- der
# /loaded-Endpoint importierte ``src.app.loader`` (eigenes Modul-Objekt,
# eigenes ungepatchtes ``_DATA_ROOT``), waehrend der Stage-Weather-Endpoint
# ueber den bare ``app.loader``-Pfad isoliert lief. Beide Namen sind jetzt
# bare-Importe desselben Modulobjekts -- kein Dual-Modul-Duplikat mehr, nur
# noch ein Namens-Alias fuer Lesbarkeit. Der /loaded-Endpoint liest bewusst
# den echten ``data/``-Bestand (Issue #115); die Isolation fuer diesen Test
# wird jetzt explizit ueber ``pytest.mark.real_data_root`` gesteuert
# (tests/tdd/test_internal_loaded_endpoint.py), nicht mehr zufaellig ueber
# den Import-Stil.
from app.loader import load_all_trips as _legacy_load_all_trips, _trip_to_dict
from app.loader import load_all_trips
from providers.base import get_provider
# Bare-Import wie oben (#1308): der Monkeypatch auf die Klassenkonstante
# DAILY_BUDGET trifft nur dann dieselbe Klasse, die dieser Endpunkt benutzt.
from services.forecast_budget import ForecastBudgetGate
from services.stage_weather import compute_stage_weather
from services import sms_daily_limit

router = APIRouter()


@router.get("/api/_internal/trip/{trip_id}/loaded")
def loaded_trip(trip_id: str, user_id: str = Query(...)):
    """Liefert den hydrierten Trip als JSON, inklusive der vom Loader
    auto-injizierten ``display_config``. Kanonische Serialisierung via
    ``_trip_to_dict`` — Datetimes als ISO-Strings, Enums als ``.value``.
    """
    trip = next((t for t in _legacy_load_all_trips(user_id) if t.id == trip_id), None)
    if trip is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trip {trip_id} nicht gefunden fuer User {user_id}",
        )
    return _trip_to_dict(trip)


def get_stage_weather_provider():
    """Default-Provider fuer den Stage-Weather-Endpoint (Issue #1212, Slice R1).

    ``get_provider("openmeteo")`` entspricht dem im Briefing-Pfad genutzten
    Standard-Provider (trip_report_scheduler.py) und respektiert
    GZ_TEST_FIXTURE_DIR (Offline-Test-Modus, FixtureProvider) -- Aufloesung
    erst zur Request-Zeit, nicht beim Modul-Import.
    """
    return get_provider("openmeteo")


@router.get("/api/_internal/trips/{trip_id}/stages-weather")
def stages_weather(
    trip_id: str,
    user_id: str = Query(...),
    provider=Depends(get_stage_weather_provider),
):
    """Etappen-Wetter + Risiko fuer einen Trip (Issue #1212, Slice R1).

    Spiegelt den Go-Handler `StagesWeatherHandler` 1:1 im Response-Vertrag,
    nutzt aber die Python-RiskEngine als Single Source of Truth (ADR-0015).
    Read-only, keine Seiteneffekte.
    """
    try:
        trips = load_all_trips(user_id)
    except Exception:
        return JSONResponse(status_code=500, content={"error": "store_error"})

    trip = next((t for t in trips if t.id == trip_id), None)
    if trip is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})

    try:
        results = compute_stage_weather(trip, provider, user_id=user_id)
    except Exception:
        # F001 (Adversary, Issue #1212): Last-Resort-Guard -- falls trotz der
        # Pro-Stage-Guards in compute_stage_weather doch etwas Unerwartetes
        # ausserhalb der Stage-Schleife bricht, darf der Request nicht mit
        # einem ungefangenen 500 crashen (AC-5).
        return JSONResponse(status_code=500, content={"error": "store_error"})
    return {"results": results}


# --- Kontingent-Reservierung fuer den Go-Forecast-Pfad (Issue #2391) --------

# Ein Forecast-Abruf ueber den Go-Pfad kostet mindestens zwei Upstream-Calls
# (doRequest fuer die Vorhersage + fetchUVData, beide laufen unbedingt). Die
# Zahl ist bewusst eine Konstante HIER und keine Groesse auf der Leitung: ein
# Query-Parameter "units" liesse Handler und Gate auseinanderdriften, weil der
# Core dann jede vom Aufrufer geschickte Zahl annaehme, statt selbst zu wissen,
# was ein Forecast-Abruf kostet (Spec, "Implementation Details").
EINHEITEN_JE_FORECAST_ABRUF = 2


def _sekunden_bis_utc_mitternacht(jetzt: datetime | None = None) -> int:
    """Wartezeit bis zum Zaehler-Reset an der UTC-Tagesgrenze.

    Der Tageszaehler wird an der UTC-Mitternacht zurueckgesetzt
    (``ForecastBudgetGate._load_for_today``) — jeder kuerzere Wert waere eine
    Luege gegenueber dem Aufrufer, jeder laengere unnoetig. Aufgerundet und auf
    mindestens 1 geklemmt, damit ein Aufruf knapp vor der Grenze nie 0 nennt.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    naechste = (jetzt + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int(math.ceil((naechste - jetzt).total_seconds())))


@router.post("/api/_internal/forecast-budget/reserve")
def reserve_forecast_budget(user_id: str = Query(...), priority: str = Query(...)):
    """Prueft und bucht das Tageskontingent eines Forecast-Abrufs in EINEM
    Aufruf — der Weg, ueber den der Go-Handler ``/api/forecast`` an dasselbe
    Gate andockt, ohne es in Go nachzubauen (ADR-0076, Issue #2391).

    ``user_id`` ist Pflicht-Parameter OHNE Default (ADR-0003/ADR-0075 Punkt 4):
    ein Ersatzwert wie ``"default"`` buchte auf ein fremdes Konto. ``priority``
    ist bewusst ein freier String und kein ``Literal`` — das Gate kennt die
    zulaessigen Werte, und eine Typeinschraenkung hier verdoppelte diese
    Kenntnis.

    Erlaubter und abgelehnter Weg sind zwei DISJUNKTE Zweige: eine Ablehnung
    bucht nichts.
    """
    gate = ForecastBudgetGate(user_id)
    if not gate.allow(priority):
        return {
            "allowed": False,
            "retry_after_s": _sekunden_bis_utc_mitternacht(),
        }

    # Auf dem Go-Pfad gibt es keinen Antwort-Cache — jeder durchgelassene
    # Abruf ist faktisch ein Miss. Ohne diese Buchung luege die Cache-Hit-Quote
    # in /api/scheduler/status nach oben.
    gate.record_cache_miss()
    for _ in range(EINHEITEN_JE_FORECAST_ABRUF):
        # Wiederholter Aufruf statt eines Zaehler-Parameters: record_call()
        # traegt zusaetzlich die user_id in die mengengepruefte Menge
        # "active_users" ein, der zweite Aufruf erhoeht also ausschliesslich
        # "calls". Absicht, kein Kopierfehler (Spec Z. 73-85).
        gate.record_call()
    return {"allowed": True}


class SmsVerificationCodeRequest(BaseModel):
    """Nutzlast des Go-Prozesses fuer den SMS-Bestaetigungscode (#2406, §8)."""

    user_id: str
    to: str
    code: str


@router.post("/api/_internal/sms/verification-code")
def send_sms_verification_code(req: SmsVerificationCodeRequest):
    """Verschickt EINE Bestaetigungs-SMS — Issue #2406, Spec §8.

    Go erzeugt und prueft den Code, Python bleibt der einzige seven.io-Transport
    (ADR-0062/ADR-0076); ein zweiter Client in Go waere die Abweichung.

    Die Zielnummer kommt aus dem AUFRUF, nicht aus dem Profil: bei einer
    ausstehenden Nummer (``pending_sms_to``) steht sie noch gar nicht als
    ``sms_to`` in ``user.json``, und die Fail-closed-Sperre in
    ``with_user_profile`` wuerde sie ohnehin verwerfen. Das
    ``model_copy``-Override setzt sie deshalb NACH dem Profil-Aufbau — die
    ``is_test_user``/``env == "staging"``-Sandbox-Weiche greift davor und bleibt
    damit vollstaendig erhalten.
    """
    settings = Settings().with_user_profile(req.user_id).model_copy(
        update={"sms_to": req.to}
    )
    if not settings.can_send_sms():
        return JSONResponse(status_code=422, content={"error": "sms_not_configured"})
    try:
        SMSOutput(settings).send("", f"Dein Gregor20-Bestaetigungscode: {req.code}")
    except (OutputConfigError, OutputError):
        # Der Code bleibt in Go gueltig — der Nutzer kann "erneut senden".
        return JSONResponse(status_code=502, content={"error": "sms_send_failed"})
    return {"status": "sent"}


@router.get("/api/_internal/sms/daily-usage")
def sms_daily_usage(user_id: str = Query(...)):
    """Tageskontingent-Anzeige fuer /account (S4b, Issue #2412). `user_id` ohne
    Default -- ein Ersatzwert wie "default" zeigte ein fremdes Konto."""
    return sms_daily_limit.get_daily_usage(user_id, datetime.now(timezone.utc))
