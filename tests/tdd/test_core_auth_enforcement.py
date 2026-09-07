"""TDD RED fuer Issue #2142, Scheibe 2 — "Python erzwingt".

Spec: docs/specs/bugfix/core_shared_secret_auth.md (AC-5 bis AC-11).

Der Python-Core hat heute KEINERLEI Authentifizierung: wer ihn direkt anspricht
(lokaler Prozess auf demselben Server), umgeht ``appendUserID`` in
``internal/handler/proxy.go`` vollstaendig und liest mit frei gewaehlter
``?user_id=`` fremde Daten. Diese Datei misst die kuenftige
``@app.middleware("http")`` in ``api/main.py`` an der Wirkstelle: echte
``TestClient``-Anfragen gegen ``api.main:app``, keine Mocks.

Pruefling fuer den Nutzdaten-Nachweis ist
``GET /api/_internal/trip/{trip_id}/loaded?user_id=...`` — ein Endpoint, der
OHNE Auth heute tatsaechlich etwas tut: er liefert den vollstaendig hydrierten
Trip eines beliebigen, frei waehlbaren Nutzers als JSON aus. Genau daran ist
"kein Seiteneffekt, keine Daten in der Antwort" ueberhaupt messbar; ein
Endpoint, der ohne Auth ohnehin nur 422 antwortet, koennte das nicht belegen.

Warum Middleware und nicht ``lifespan``: der FastAPI-``lifespan`` laeuft unter
``TestClient(app)`` ohne ``with``-Block NICHT (gemessen, Kontext-Dokument).
Alle Tests hier bauen den Client bewusst ohne ``with`` — was hier gruen wird,
wird von der Middleware bewacht, nicht vom Startup-Hook.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

CORE_AUTH_HEADER = "X-GZ-Core-Auth"
CORE_SECRET_ENV = "GZ_CORE_SHARED_SECRET"
GUELTIGES_SECRET = "tdd-2142-core-secret-abcdefghijklmnop"

# Realer Bestand aus tests/fixtures/data_root (Session-Fixture in
# tests/conftest.py materialisiert ihn nach data/users/): ein Trip, der einem
# konkreten Nutzer gehoert. Ohne Auth gibt der Core ihn heute jedem heraus.
FREMDER_TRIP = "gr221-mallorca"
FREMDER_USER = "default"
GESCHUETZTER_PFAD = f"/api/_internal/trip/{FREMDER_TRIP}/loaded"


def client_ohne_core_auth() -> TestClient:
    """``TestClient`` mit nachweislich ENTFERNTEM ``X-GZ-Core-Auth``-Header.

    Ab der GREEN-Phase versorgt eine autouse-Fixture in ``tests/conftest.py``
    jede ``TestClient``-Instanz zentral mit dem gueltigen Header (sonst braechen
    die ~68 Bestands-Testdateien). Ein Test, der den Header einfach "nicht
    setzt", wuerde ihn dann trotzdem mitschicken und still gruen werden. Hier
    wird er darum aktiv aus den Client-Kopfzeilen entfernt und die Entfernung
    anschliessend geprueft.
    """
    client = TestClient(app)
    client.headers.pop(CORE_AUTH_HEADER, None)
    assert CORE_AUTH_HEADER not in client.headers, (
        f"{CORE_AUTH_HEADER} liess sich nicht aus dem TestClient entfernen — "
        "ohne diese Entfernung misst kein Negativtest dieser Datei etwas."
    )
    return client


@pytest.fixture
def secret_konfiguriert(monkeypatch) -> str:
    """Der Prozess kennt ein gueltiges gemeinsames Geheimnis."""
    monkeypatch.setenv(CORE_SECRET_ENV, GUELTIGES_SECRET)
    return GUELTIGES_SECRET


@pytest.fixture
def secret_nicht_konfiguriert(monkeypatch) -> None:
    """Der Prozess kennt GAR KEIN gemeinsames Geheimnis (AC-9, fail-closed).

    Zwei Quellen muessen dafuer schweigen: die Umgebungsvariable UND die
    ``.env``-Datei, die ``Settings`` ueber ``env_file`` mitliest. Wird nur die
    Variable geloescht, entscheidet der zufaellige Inhalt der lokalen ``.env``
    ueber das Testergebnis — auf dem Server steht das Geheimnis dort (Schritt 0
    der Rollout-Reihenfolge), in der CI nicht. Deshalb wird die ``.env``-Quelle
    fuer die Dauer des Tests abgeschaltet (monkeypatch stellt sie danach
    wieder her).
    """
    from app.config import Settings

    monkeypatch.delenv(CORE_SECRET_ENV, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)


def _antwort_enthaelt_keine_trip_daten(response) -> None:
    """Kein Byte des fremden Trips darf in der Antwort stehen (AC-5)."""
    text = response.text
    for verraeterisch in ("GR221", "display_config", '"stages"', "aggregation"):
        assert verraeterisch not in text, (
            f"Die abgewiesene Antwort gibt Nutzdaten preis ({verraeterisch!r} "
            f"im Koerper): {text[:400]!r}"
        )


@pytest.mark.real_data_root
def test_ohne_header_401_und_keine_nutzdaten(secret_konfiguriert):
    """AC-5 / Test 6: Secret konfiguriert, Anfrage OHNE Header → 401, kein Seiteneffekt.

    Given der Python-Core hat ein gueltiges Geheimnis konfiguriert
    When ``GET /api/_internal/trip/gr221-mallorca/loaded?user_id=default`` ohne
         ``X-GZ-Core-Auth`` eintrifft
    Then antwortet der Core mit 401 und gibt keine Trip-Daten heraus.

    Der Endpoint ist rein lesend — ein Versand kann hier gar nicht entstehen;
    der messbare Seiteneffekt ist die Datenherausgabe, und genau die wird
    geprueft.
    """
    client = client_ohne_core_auth()

    response = client.get(GESCHUETZTER_PFAD, params={"user_id": FREMDER_USER})

    assert response.status_code == 401, (
        f"Ohne {CORE_AUTH_HEADER} muss der Python-Core 401 antworten, bekam "
        f"{response.status_code}. Heute hat er keine Auth-Pruefung — genau das "
        "ist der Befund aus #2142."
    )
    _antwort_enthaelt_keine_trip_daten(response)


@pytest.mark.real_data_root
def test_falscher_header_wert_401(secret_konfiguriert):
    """AC-6 / Test 7: falscher Header-Wert → 401.

    Given der Python-Core hat ein gueltiges Geheimnis konfiguriert
    When eine Anfrage mit falschem ``X-GZ-Core-Auth``-Wert eintrifft
    Then antwortet der Core mit 401 und gibt keine Trip-Daten heraus.
    """
    client = client_ohne_core_auth()

    response = client.get(
        GESCHUETZTER_PFAD,
        params={"user_id": FREMDER_USER},
        headers={CORE_AUTH_HEADER: GUELTIGES_SECRET + "-falsch"},
    )

    assert response.status_code == 401, (
        f"Ein falscher {CORE_AUTH_HEADER}-Wert muss mit 401 abgewiesen werden, "
        f"bekam {response.status_code}."
    )
    _antwort_enthaelt_keine_trip_daten(response)


@pytest.mark.real_data_root
def test_korrekter_header_endpoint_unveraendert(secret_konfiguriert):
    """AC-7 / Test 8: korrekter Header → Endpoint verhaelt sich unveraendert.

    REGRESSIONSSCHUTZ — dieser Test ist im RED-Stand bereits GRUEN und soll es
    bleiben. Er ist der Gegenpol zu den Negativtests: er faellt um, sobald die
    Middleware authentifizierte Aufrufer mitblockt. Genau das waere der teure
    Fehler dieser Scheibe (fail-closed ueber 20 Aufrufstellen — eine zu strenge
    Pruefung legt den gesamten Core lahm).
    """
    client = TestClient(app)

    response = client.get(
        GESCHUETZTER_PFAD,
        params={"user_id": FREMDER_USER},
        headers={CORE_AUTH_HEADER: GUELTIGES_SECRET},
    )

    assert response.status_code == 200, (
        f"Mit korrektem {CORE_AUTH_HEADER} muss der Endpoint unveraendert "
        f"antworten, bekam {response.status_code}: {response.text[:300]!r}"
    )
    daten = response.json()
    assert daten["id"] == FREMDER_TRIP
    assert "display_config" in daten
    assert daten["stages"], "Trip-Hydration muss unveraendert Etappen liefern"


@pytest.mark.real_data_root
@pytest.mark.parametrize("leerer_wert", [False, True])
def test_secret_nicht_konfiguriert_503(monkeypatch, secret_nicht_konfiguriert, leerer_wert):
    """AC-9 / Test 9: Secret im Prozess nicht konfiguriert → 503 (fail-closed).

    Zwei Auspraegungen von "nicht konfiguriert" werden geprueft: Variable und
    ``.env``-Eintrag fehlen ganz, sowie Variable auf leeren Wert gesetzt (so
    kommt es an, wenn jemand die Zeile in der ``.env`` leer laesst). Beide
    duerfen NIE offen durchlassen — 503 statt unauthentifizierter Antwort, exakt
    das Muster aus ``telegram_webhook.go`` ("webhook not configured").
    """
    if leerer_wert:
        monkeypatch.setenv(CORE_SECRET_ENV, "")

    client = client_ohne_core_auth()

    response = client.get(GESCHUETZTER_PFAD, params={"user_id": FREMDER_USER})

    assert response.status_code == 503, (
        "Ohne konfiguriertes Geheimnis muss der Python-Core mit 503 abriegeln "
        f"statt die Anfrage durchzulassen, bekam {response.status_code}."
    )
    _antwort_enthaelt_keine_trip_daten(response)


def test_health_ohne_header_immer_200(monkeypatch):
    """AC-8 / Test 10: ``GET /health`` ohne Header → 200, in BEIDEN Zustaenden.

    Heute bereits GRUEN und muss es bleiben: Go ruft diesen Pfad selbst ohne
    Header ab (``proxy.go``) und ``ci-stack.sh`` pollt ihn als Boot-Pruefung,
    bevor ueberhaupt etwas konfiguriert sein kann. Der Test faellt um, sobald
    die Ausnahme zu weit (dann greifen die Negativtests nicht mehr) oder zu eng
    (dann sperrt sich der Core beim Start selbst aus) gefasst wird.
    """
    from app.config import Settings

    # Zustand 1: Geheimnis konfiguriert
    monkeypatch.setenv(CORE_SECRET_ENV, GUELTIGES_SECRET)
    response = client_ohne_core_auth().get("/health")
    assert response.status_code == 200, (
        f"/health muss bei konfiguriertem Geheimnis ohne Header 200 liefern, "
        f"bekam {response.status_code}."
    )
    assert response.json()["status"] == "ok"

    # Zustand 2: Geheimnis gar nicht konfiguriert
    monkeypatch.delenv(CORE_SECRET_ENV, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    response = client_ohne_core_auth().get("/health")
    assert response.status_code == 200, (
        "/health muss AUCH ohne konfiguriertes Geheimnis 200 liefern — sonst "
        "kommt der CI-Stack nie ueber seine Boot-Pruefung hinaus, bekam "
        f"{response.status_code}."
    )
    assert response.json()["status"] == "ok"


def test_health_praefix_pfad_bleibt_authpflichtig(secret_konfiguriert):
    """AC-8 Grenzfall: ein Pfad, der nur mit ``/health`` BEGINNT, bleibt auth-pflichtig.

    ``CORE_AUTH_EXEMPT_PATHS`` ist als exakte Menge definiert
    (``frozenset({"/health"})``), nicht als Praefix-Regel. ``/health/sub``
    existiert in KEINEM Router (kein 404-Risiko durch die Ausnahme selbst) —
    die Middleware laeuft ohnehin VOR dem Routing, entscheidet also bei
    fehlendem Header zuerst: 401. Wuerde der Vergleich zu
    ``path.startswith("/health")`` aufgeweicht, kaeme der Request unauth an
    den (nicht existenten) Router durch und liefe in ein Router-404 statt in
    das Middleware-401 dieses Tests — der Test faellt dann rot um.
    """
    client = client_ohne_core_auth()

    response = client.get("/health/sub")

    assert response.status_code == 401, (
        "Ein Pfad, der nur mit /health BEGINNT, muss weiterhin auth-pflichtig "
        f"sein (exakter Vergleich, keine Praefix-Ausnahme), bekam "
        f"{response.status_code}."
    )


def test_health_mit_query_bleibt_ausnahme(secret_konfiguriert):
    """AC-8 Gegenprobe: ``/health?...`` bleibt die Ausnahme.

    ``request.url.path`` enthaelt den Query-String NICHT — dieser Fall darf
    trotz der Grenzpruefung oben NICHT rot werden, sonst waere ein Boot-Poll
    mit angehaengtem Query kaputt.
    """
    client = client_ohne_core_auth()

    response = client.get("/health", params={"probe": "1"})

    assert response.status_code == 200, (
        "GET /health?probe=1 muss weiterhin die Ausnahme sein (path ohne "
        f"Query bleibt exakt '/health'), bekam {response.status_code}."
    )


class KommandoRekorder:
    """Echter Aufzeichner an der Stelle, an der Telegram-Kommandos ausgefuehrt
    werden (``InboundTelegramReader._process_update``).

    Kein ``Mock``: eine gewoehnliche Klasse, die den einen Aufruf mitschreibt,
    den der Webhook-Endpoint gegen den Reader taetigt. Gemessen wird damit die
    WIRKUNG ("wurde ein Kommando ausgefuehrt?"), nicht ein Statuscode — ein
    stiller 200 mit trotzdem ausgefuehrtem Kommando waere der gefaehrliche Fall.
    """

    def __init__(self) -> None:
        self.aufrufe: list[dict] = []

    def _process_update(self, update: dict, settings) -> bool:  # noqa: ANN001
        self.aufrufe.append(update)
        return True


@pytest.fixture
def telegram_rekorder(monkeypatch) -> KommandoRekorder:
    """Setzt den Modul-Reader des Webhooks auf den Aufzeichner und leert den
    prozessglobalen Dedup-Speicher (``_seen_ids`` ueberlebt sonst zwischen
    Tests und wuerde ein Update still als Duplikat verwerfen)."""
    from api.routers import webhook

    rekorder = KommandoRekorder()
    monkeypatch.setattr(webhook, "_reader", rekorder)
    webhook._seen_ids.clear()
    webhook._seen_order.clear()
    return rekorder


def _telegram_update(update_id: int) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "chat": {"id": 424242, "type": "private"},
            "text": "/wetter",
        },
    }


@pytest.mark.parametrize(
    "telegram_header",
    [None, "falsches-telegram-secret"],
    ids=["telegram-secret-fehlt", "telegram-secret-falsch"],
)
def test_webhook_ohne_telegram_secret_fuehrt_kein_kommando_aus(
    monkeypatch, secret_konfiguriert, telegram_rekorder, telegram_header
):
    """AC-10 / Test 11: gueltige Core-Auth, aber fehlendes/falsches Telegram-Secret
    → KEIN Telegram-Kommando wird ausgefuehrt (Defense in Depth).

    Given ``POST /api/internal/telegram-webhook`` mit gueltigem
          ``X-GZ-Core-Auth``, aber ohne bzw. mit falschem
          ``X-Telegram-Bot-Api-Secret-Token``
    When der Request verarbeitet wird
    Then erreicht das Update die Kommando-Verarbeitung nicht.

    Heute reicht ``webhook.py`` jeden Body ungeprueft an
    ``InboundTelegramReader._process_update`` weiter — der Docstring dort
    schreibt den Localhost-Trust sogar als Soll fest. Die Core-Auth-Pruefung
    allein genuegt nicht: wer das gemeinsame Geheimnis kennt (jeder Prozess mit
    Lesezugriff auf die ``.env``), koennte sonst Kommandos fuer ein fremdes
    Konto ausloesen.
    """
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "echtes-telegram-webhook-secret")

    headers = {CORE_AUTH_HEADER: secret_konfiguriert}
    if telegram_header is not None:
        headers["X-Telegram-Bot-Api-Secret-Token"] = telegram_header

    client = TestClient(app)
    client.post(
        "/api/internal/telegram-webhook",
        json=_telegram_update(920142001),
        headers=headers,
    )

    assert telegram_rekorder.aufrufe == [], (
        "Ohne gueltiges Telegram-Secret darf KEIN Kommando ausgefuehrt werden, "
        f"es wurden aber {len(telegram_rekorder.aufrufe)} Update(s) an die "
        "Kommando-Verarbeitung durchgereicht."
    )


def test_webhook_mit_telegram_secret_fuehrt_kommando_aus(
    monkeypatch, secret_konfiguriert, telegram_rekorder
):
    """AC-10 (Positivkontrolle): mit gueltigem Telegram-Secret wird das Kommando
    ausgefuehrt.

    Ohne diese Gegenprobe wuerde der Negativtest oben auch dann gruen, wenn die
    Kommando-Verarbeitung aus einem ganz anderen Grund nie erreicht wird (z. B.
    weil der Aufzeichner gar nicht am Draht haengt) — dann maesse er nichts.
    Heute bereits GRUEN: ``webhook.py`` fuehrt jedes Update aus.
    """
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "echtes-telegram-webhook-secret")

    client = TestClient(app)
    client.post(
        "/api/internal/telegram-webhook",
        json=_telegram_update(920142002),
        headers={
            CORE_AUTH_HEADER: secret_konfiguriert,
            "X-Telegram-Bot-Api-Secret-Token": "echtes-telegram-webhook-secret",
        },
    )

    assert len(telegram_rekorder.aufrufe) == 1, (
        "Mit gueltigem Telegram-Secret MUSS das Update die "
        "Kommando-Verarbeitung erreichen — sonst misst der Negativtest nichts."
    )


@pytest.mark.real_data_root
def test_waechter_bleibt_im_testlauf_scharf(secret_konfiguriert):
    """AC-11 / Test 12: die zentrale Test-Fixture darf den Waechter nicht abschalten.

    Given ``tests/conftest.py`` versorgt ab der GREEN-Phase jede
          ``TestClient``-Instanz automatisch mit dem gueltigen Header
    When ein Test diesen Header ausdruecklich wieder ENTFERNT
    Then antwortet der Python-Core mit 401.

    Zwei Zusicherungen in einem Test, weil erst beide zusammen etwas beweisen:
    (a) ein unveraenderter Client traegt den Header — die Fixture wirkt, die
    ~68 Bestandsdateien laufen weiter; (b) nach dem Entfernen kommt 401 — es
    gibt KEINE testlauf-spezifische Ausnahme (kein ``_in_pytest()``-Bypass),
    die die Pruefung insgesamt stilllegt. Ohne (a) koennte (b) auch dann gruen
    sein, wenn die Fixture gar nichts tut; ohne (b) waere die Fixture selbst
    der blinde Fleck.
    """
    versorgter_client = TestClient(app)
    assert versorgter_client.headers.get(CORE_AUTH_HEADER) == secret_konfiguriert, (
        "Die autouse-Fixture in tests/conftest.py versorgt TestClient-Instanzen "
        "nicht mit dem gueltigen Header — ohne sie brechen die Bestandstests "
        f"breit. Vorgefunden: {versorgter_client.headers.get(CORE_AUTH_HEADER)!r}"
    )

    entbloesster_client = client_ohne_core_auth()
    response = entbloesster_client.get(
        GESCHUETZTER_PFAD, params={"user_id": FREMDER_USER}
    )

    assert response.status_code == 401, (
        "Der Waechter ist im Testlauf nicht scharf: eine Anfrage mit "
        f"nachweislich entferntem {CORE_AUTH_HEADER} kam mit "
        f"{response.status_code} durch. Ein Testlauf-Bypass wuerde bedeuten, "
        "dass KEIN Test der Suite die Durchsetzung noch belegen kann."
    )
    _antwort_enthaelt_keine_trip_daten(response)
