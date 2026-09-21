"""TDD RED fuer Issue #2391 (Scheibe S3 von #2150, Epic #2138 Multi-User).

SPEC: docs/specs/modules/forecast_go_pfad_kontingent.md (AC-1, AC-3, AC-4, AC-8, AC-9)
Ausfuehrung:
    uv run pytest tests/tdd/test_internal_forecast_budget_reserve.py -v -rA

Prueft den NEUEN Core-Endpunkt

    POST /api/_internal/forecast-budget/reserve?user_id=<id>&priority=polling
      -> 200 {"allowed": true}
      -> 200 {"allowed": false, "retry_after_s": <Sekunden bis UTC-Mitternacht>}

gegen einen echten ``TestClient(api.main.app)`` und die echte, vom Produkt
geschriebene Zaehlerdatei. KEIN Mock, kein Patch auf ``ForecastBudgetGate``.

RED-Erwartung: die Route existiert noch nicht -> FastAPI antwortet **404**
auf jede Anfrage dieser Datei.

Warum die Core-Auth hier ausdruecklich hergestellt wird
-------------------------------------------------------
``api/main.py:enforce_core_auth`` ist fail-closed und antwortet **503**, wenn
im Prozess gar kein gemeinsames Geheimnis gesetzt ist (ADR-0062, #2142). Ein
TestClient-Aufruf ohne Vorbereitung liefe also heute wie nach der
Implementierung in 503 -- ein RED, das nichts beweist und in GREEN rot bleibt.
``_reserve()`` unten weist einen 503 darum mit eigener Meldung ab, damit ein
Konfigurationsfehler nie als Fachbefund gelesen wird.

Warum der Zaehlerstand IMMER durch den Endpunkt selbst entsteht
---------------------------------------------------------------
``calls`` und ``active_users`` werden in dieser Datei NIE per Fixture
vorgeschrieben. Eine Fixture, die diese Felder selbst anlegt, macht die
Zusicherung vakuum-gruen -- genau so ist es im RED von #2387 schiefgegangen.
Das Arrangement besteht darum aus wiederholten ``reserve``-Aufrufen, und der
erreichte Stand wird vor der eigentlichen Handlung aus der real geschriebenen
Datei zurueckgelesen (``_pruefe_arrangement``).

Warum ``DAILY_BUDGET`` fuer AC-3/AC-4/AC-8 verkleinert wird
------------------------------------------------------------
Mit dem Produktivwert 9000 braeuchte das Arrangement ueber 3600
``reserve``-Aufrufe (je fuenf fcntl-Lock-Zyklen) -- Minuten Laufzeit in der
Kern-Schicht. Die naheliegende Alternative, ``active_users`` mit vielen
Kennungen vorzuschreiben, um den fairen Anteil zu druecken, faellt aus: genau
dieses Feld ist der Pruefling des Schreibwegs. Der Monkeypatch auf die
Klassenkonstante laesst dagegen JEDES geschriebene Feld vom Produkt kommen.
ADR-0075 Punkt 6 bleibt unberuehrt -- ``TestForecastBudgetConstantsMatchPython``
(``internal/scheduler/forecast_budget_health_test.go:256``) liest den
Python-QUELLTEXT, nicht den Laufzeitwert. AC-1 und AC-9 laufen bewusst gegen
die ECHTE Konstante, damit die gebuchte Menge unter Produktivbedingungen
belegt ist.

AC-2, AC-5, AC-6 und AC-7 liegen Go-seitig
(``internal/handler/forecast_test.go``).
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.loader import get_data_dir, get_data_root
from services.forecast_budget import PROVIDER, ForecastBudgetGate

PFAD = "/api/_internal/forecast-budget/reserve"

CORE_AUTH_HEADER = "X-GZ-Core-Auth"
CORE_SECRET_ENV = "GZ_CORE_SHARED_SECRET"
TEST_SECRET = "tdd-2391-core-shared-secret-abcdefghij"

NUTZER_A = "nutzer_a"
NUTZER_B = "nutzer_b"

# Eine erlaubte Reservierung bucht laut Spec 2 Einheiten (record_call zweimal:
# doRequest + fetchUVData laufen im Regelfall unbedingt) und genau einen
# Cache-Miss (auf dem Go-Pfad gibt es keinen Antwort-Cache).
EINHEITEN_JE_RESERVIERUNG = 2

# Verkleinerter Deckel fuer die Arrangement-Tests (s. Modul-Docstring).
KLEINER_DECKEL = 20
SEKUNDEN_JE_TAG = 86400


# --- Zugriff auf die real geschriebenen Zaehlerdateien ---------------------

def _globale_datei():
    return get_data_root() / "diagnostics" / "forecast_budget.json"


def _nutzer_datei(user_id: str):
    return get_data_dir(user_id) / "diagnostics" / "forecast_budget.json"


def _lies(pfad) -> dict:
    if not pfad.exists():
        return {}
    return json.loads(pfad.read_text())


def _globale_calls() -> int:
    return _lies(_globale_datei()).get("calls", {}).get(PROVIDER, 0)


def _nutzer_calls(user_id: str) -> int:
    return _lies(_nutzer_datei(user_id)).get("calls", {}).get(PROVIDER, 0)


def _cache_misses() -> int:
    return _lies(_globale_datei()).get("cache_misses", 0)


def _aktive_nutzer() -> set:
    return set(_lies(_globale_datei()).get("active_users", []))


def _zaehlerstand(*nutzer) -> dict:
    """Vollstaendiger Stand aller vom Endpunkt beschriebenen Felder."""
    stand = {
        "global_calls": _globale_calls(),
        "cache_misses": _cache_misses(),
        "active_users": _aktive_nutzer(),
    }
    for user_id in nutzer:
        stand[f"calls[{user_id}]"] = _nutzer_calls(user_id)
    return stand


# --- Client + Aufruf -------------------------------------------------------

@pytest.fixture
def core_client(monkeypatch) -> TestClient:
    """TestClient mit nachweislich gueltiger Core-Auth.

    ``monkeypatch.setenv`` laeuft VOR dem Bau des Clients: die
    conftest-Patchung von ``TestClient.__init__`` friert den Header-Wert zum
    Konstruktionszeitpunkt ein, und ``api/main.py:_core_shared_secret()``
    bevorzugt dieselbe Quelle (``os.environ``) -- Client-Header und
    Server-Erwartung koennen so nicht auseinanderdriften. Eine lokale ``.env``
    kommt damit gar nicht erst zum Zug.
    """
    monkeypatch.setenv(CORE_SECRET_ENV, TEST_SECRET)
    client = TestClient(app)
    assert client.headers.get(CORE_AUTH_HEADER) == TEST_SECRET, (
        "Der TestClient traegt nicht das erwartete gemeinsame Geheimnis — ohne "
        "das misst diese Datei nur die Core-Authentifizierung, nicht den "
        f"Endpunkt. Vorgefunden: {client.headers.get(CORE_AUTH_HEADER)!r}"
    )
    return client


@pytest.fixture
def kleiner_deckel(monkeypatch) -> int:
    """Verkleinert das Tagesbudget, damit das Arrangement ueber den echten
    Endpunkt in wenigen Aufrufen erreichbar bleibt (s. Modul-Docstring)."""
    monkeypatch.setattr(ForecastBudgetGate, "DAILY_BUDGET", KLEINER_DECKEL)
    return KLEINER_DECKEL


def _reserve(client: TestClient, user_id: str, priority: str = "polling"):
    antwort = client.post(PFAD, params={"user_id": user_id, "priority": priority})
    assert antwort.status_code != 503, (
        "Der Core antwortet fail-closed mit 503 — im Prozess ist kein "
        "gemeinsames Geheimnis gesetzt. Das ist ein Aufbaufehler des Tests, "
        "kein Fachbefund (ADR-0062, api/main.py:enforce_core_auth)."
    )
    return antwort


def _erlaube(client: TestClient, user_id: str, priority: str = "polling") -> None:
    """Ein Arrangement-Aufruf, der durchgelassen werden MUSS.

    Schlaegt er fehl oder wird er abgelehnt, ist der spaeter gepruefte
    Zaehlerstand nicht der gemeinte — das muss laut auffallen, nicht still in
    ein plausibel aussehendes, aber falsches Urteil laufen.
    """
    antwort = _reserve(client, user_id, priority)
    assert antwort.status_code == 200, (
        f"Arrangement-Reservierung fuer {user_id!r} lieferte "
        f"{antwort.status_code}: {antwort.text[:300]!r}"
    )
    assert antwort.json()["allowed"] is True, (
        f"Arrangement-Reservierung fuer {user_id!r} wurde abgelehnt — der "
        f"aufgebaute Zaehlerstand waere nicht der gemeinte: {antwort.json()}"
    )


def _baue_stufe_1_lage(client: TestClient) -> None:
    """Bringt den globalen Zaehler ins Stufe-1-Band und Nutzer A ueber seinen
    fairen Anteil — ausschliesslich ueber den Endpunkt selbst.

    Mit ``DAILY_BUDGET = 20``: acht Reservierungen von A (global 16, A 16),
    dann eine von B (global 18 = 90 %, B 2, ``active_users = {A, B}``). Fairer
    Anteil bei N=2 ist 10 — A liegt mit 16 darueber, B mit 2 darunter, und der
    globale Anteil liegt mitten im Band (0,80 <= 0,90 < 0,95), nicht auf der
    Schwelle.
    """
    for _ in range(8):
        _erlaube(client, NUTZER_A)
    _erlaube(client, NUTZER_B)


def _pruefe_arrangement() -> None:
    """Positivkontrolle auf den SCHREIBWEG (ADR-0075, Konsequenzen).

    Liest ``calls`` (global und je Nutzer) sowie ``active_users`` aus den real
    vom Produkt geschriebenen Dateien zurueck. Faellt der Schreibweg auf
    ``active_users`` aus, bliebe N = 0, der faire Anteil das ganze Tagesbudget
    und Stufe 1 feuerte nie — die Drossel-Tests waeren dann gruen, ohne etwas
    zu bewachen.
    """
    assert _globale_calls() == 18, (
        f"Globaler Zaehler nach dem Arrangement: {_globale_calls()}, erwartet "
        "18 (9 erlaubte Reservierungen x 2 Einheiten)"
    )
    assert _nutzer_calls(NUTZER_A) == 16, (
        f"Nutzer-Topf A: {_nutzer_calls(NUTZER_A)}, erwartet 16"
    )
    assert _nutzer_calls(NUTZER_B) == 2, (
        f"Nutzer-Topf B: {_nutzer_calls(NUTZER_B)}, erwartet 2"
    )
    assert _aktive_nutzer() == {NUTZER_A, NUTZER_B}, (
        f"active_users: {_aktive_nutzer()}, erwartet zwei Kennungen — aus "
        "dieser Menge leitet das Gate N fuer den fairen Anteil ab"
    )


# ---------------------------------------------------------------------------
# AC-1: eine erlaubte Reservierung erhoeht den Tageszaehler der echten
#       user_id um 2 Einheiten
# ---------------------------------------------------------------------------

def test_erlaubte_reservierung_bucht_zwei_einheiten_auf_die_echte_user_id(core_client):
    """AC-1 (Realisierung auf der Python-Seite, s. Abweichungen im Bericht).

    Given ein angemeldeter Nutzer loest eine Reservierung aus und das
          Kontingent ist frei
    When der Endpunkt mit ``allowed: true`` antwortet
    Then ist der Tageszaehler GENAU DIESER ``user_id`` um 2 Einheiten hoeher —
         und der eines anderen Nutzers unveraendert (ADR-0003).

    Laeuft gegen die ECHTE ``DAILY_BUDGET``-Konstante: die gebuchte Menge muss
    unter Produktivbedingungen stimmen, nicht nur unter einem Testdeckel.
    """
    vorher_a = _nutzer_calls(NUTZER_A)
    vorher_b = _nutzer_calls(NUTZER_B)
    vorher_global = _globale_calls()

    antwort = _reserve(core_client, NUTZER_A)

    assert antwort.status_code == 200, (
        f"Erwartet 200, bekam {antwort.status_code}: {antwort.text[:300]!r}"
    )
    assert antwort.json() == {"allowed": True}, (
        f"Bei freiem Kontingent erwartet {{'allowed': True}}, bekam {antwort.json()}"
    )
    assert _nutzer_calls(NUTZER_A) - vorher_a == EINHEITEN_JE_RESERVIERUNG, (
        "AC-1: der Nutzer-Topf der aufrufenden user_id muss sich um genau 2 "
        f"Einheiten erhoehen, bekam {_nutzer_calls(NUTZER_A) - vorher_a}"
    )
    assert _globale_calls() - vorher_global == EINHEITEN_JE_RESERVIERUNG, (
        "AC-1: derselbe Aufruf muss auch den globalen Topf um 2 Einheiten "
        f"erhoehen, bekam {_globale_calls() - vorher_global}"
    )
    assert _nutzer_calls(NUTZER_B) == vorher_b, (
        "AC-1 (Gegenlesung, ADR-0003): die Buchung darf NICHT im Topf eines "
        "anderen Nutzers landen — sonst beweist die Positivkontrolle nur, "
        "dass ueberhaupt irgendwo gezaehlt wird"
    )
    assert NUTZER_A in _aktive_nutzer(), (
        "AC-1: record_call() muss die user_id in active_users eintragen — "
        "faellt dieser Schreibweg aus, bleibt N=0 und Stufe 1 feuert nie"
    )


# ---------------------------------------------------------------------------
# AC-9: genau ein record_cache_miss() je erlaubter Reservierung
# ---------------------------------------------------------------------------

def test_erlaubte_reservierung_bucht_genau_einen_cache_miss(core_client):
    """AC-9.

    Given ein durchgelassener Aufruf erreicht den Python-Core
    When die Reservierung mit ``allowed: true`` beantwortet wird
    Then ist ``cache_misses`` um GENAU 1 hoeher als vorher.

    Nicht ``>= 1``: zweimal gebucht wuerde die Cache-Hit-Quote in
    ``/api/scheduler/status`` nach unten luegen, gar nicht gebucht nach oben.
    """
    vorher = _cache_misses()

    antwort = _reserve(core_client, NUTZER_A)

    assert antwort.status_code == 200, (
        f"Erwartet 200, bekam {antwort.status_code}: {antwort.text[:300]!r}"
    )
    assert antwort.json()["allowed"] is True
    assert _cache_misses() - vorher == 1, (
        "AC-9: genau ein Cache-Miss je erlaubter Reservierung, bekam "
        f"{_cache_misses() - vorher}"
    )


# ---------------------------------------------------------------------------
# AC-3: der Vielverbraucher wird gedrosselt, der Unbeteiligte nicht
# ---------------------------------------------------------------------------

def test_vielverbraucher_abgelehnt_unbeteiligter_erlaubt(core_client, kleiner_deckel):
    """AC-3.

    Given A liegt ueber seinem fairen Anteil (DAILY_BUDGET/N), B klar darunter,
          und der globale Zaehler hat die polling-Schwelle erreicht
    When beide ``reserve`` mit ``priority=polling`` aufrufen
    Then antwortet der Endpunkt A mit ``allowed: false`` und B mit
         ``allowed: true``.
    """
    _baue_stufe_1_lage(core_client)
    _pruefe_arrangement()

    antwort_a = _reserve(core_client, NUTZER_A)
    assert antwort_a.status_code == 200, (
        f"Erwartet 200 mit Urteil, bekam {antwort_a.status_code}: "
        f"{antwort_a.text[:300]!r}"
    )
    assert antwort_a.json()["allowed"] is False, (
        "AC-3: Nutzer A liegt mit 16 Einheiten ueber seinem fairen Anteil "
        f"(20/2 = 10) — er muss gedrosselt werden, bekam {antwort_a.json()}"
    )
    retry = antwort_a.json()["retry_after_s"]
    assert isinstance(retry, int) and 0 < retry <= SEKUNDEN_JE_TAG, (
        "AC-3: die Ablehnung muss die Wartezeit bis zum naechsten "
        f"UTC-Mitternacht nennen (0 < s <= {SEKUNDEN_JE_TAG}), bekam {retry!r}"
    )

    antwort_b = _reserve(core_client, NUTZER_B)
    assert antwort_b.status_code == 200
    assert antwort_b.json()["allowed"] is True, (
        "AC-3 (Kern des Tickets): B liegt mit 2 Einheiten klar unter seinem "
        "fairen Anteil — der Vielverbrauch von A darf ihn nicht mitdrosseln, "
        f"bekam {antwort_b.json()}"
    )


# ---------------------------------------------------------------------------
# AC-8: eine abgelehnte Reservierung bucht NICHTS
# ---------------------------------------------------------------------------

def test_abgelehnte_reservierung_bucht_nichts(core_client, kleiner_deckel):
    """AC-8.

    Given der Endpunkt lehnt eine Reservierung ab (``allowed: false``)
    When der Zaehlerstand vor und nach dieser Anfrage verglichen wird
    Then ist er identisch — die Ablehnung hat nichts gebucht.

    Die Ablehnung wird VOR dem Vergleich zugesichert. Ohne diese Zusicherung
    waere der Test im RED-Stand (404, es passiert nichts) vakuum-gruen und
    bewiese nach GREEN nichts ueber die disjunkten Zweige des Endpunkts.
    """
    _baue_stufe_1_lage(core_client)
    _pruefe_arrangement()

    vorher = _zaehlerstand(NUTZER_A, NUTZER_B)

    antwort = _reserve(core_client, NUTZER_A)

    assert antwort.status_code == 200, (
        f"Erwartet 200 mit Urteil, bekam {antwort.status_code}: "
        f"{antwort.text[:300]!r}"
    )
    assert antwort.json()["allowed"] is False, (
        "Voraussetzung dieses Tests: die Reservierung MUSS abgelehnt werden, "
        f"bekam {antwort.json()}"
    )

    assert _zaehlerstand(NUTZER_A, NUTZER_B) == vorher, (
        "AC-8: eine abgelehnte Reservierung darf weder calls noch "
        "active_users noch cache_misses veraendern — 'allow, dann record egal "
        f"was' ist von aussen unsichtbar. Vorher {vorher}, nachher "
        f"{_zaehlerstand(NUTZER_A, NUTZER_B)}"
    )


# ---------------------------------------------------------------------------
# AC-4: priority und user_id kommen am Gate an und WIRKEN dort
# ---------------------------------------------------------------------------

def test_priority_aus_der_query_erreicht_das_gate(core_client, kleiner_deckel):
    """AC-4 (Python-Haelfte: Wirkung der angekommenen Werte).

    Given der globale Zaehler liegt bei 90 % — ueber der polling-Schwelle
          (80 %), aber unter der alert_check-Schwelle (95 %) — und A liegt
          ueber seinem fairen Anteil
    When dieselbe user_id einmal mit ``priority=polling`` und einmal mit
        ``priority=alert_check`` reserviert
    Then wird nur die ``polling``-Anfrage abgelehnt.

    Das ist die Zusicherung, die ``allow()`` selbst NICHT leistet: eine
    unbekannte Prioritaet laesst es fail-open immer durch
    (``forecast_budget.py:133-134``). Ein Test, der nur ein Urteil befolgt,
    bliebe bei einem Tippfehler in ``priority`` gruen. Dass die beiden
    Antworten AUSEINANDERGEHEN, kann nur daran liegen, dass der Wert aus der
    Query bis ins Gate durchgereicht wird — eine im Endpunkt festverdrahtete
    Prioritaet ergaebe zwei gleiche Antworten.
    """
    _baue_stufe_1_lage(core_client)
    _pruefe_arrangement()

    mit_polling = _reserve(core_client, NUTZER_A, priority="polling")
    assert mit_polling.status_code == 200, (
        f"Erwartet 200, bekam {mit_polling.status_code}: {mit_polling.text[:300]!r}"
    )
    assert mit_polling.json()["allowed"] is False, (
        "AC-4: bei 90 % Auslastung und ueberschrittenem fairen Anteil muss "
        f"priority=polling abgelehnt werden, bekam {mit_polling.json()}"
    )

    mit_alert = _reserve(core_client, NUTZER_A, priority="alert_check")
    assert mit_alert.status_code == 200, (
        f"Erwartet 200, bekam {mit_alert.status_code}: {mit_alert.text[:300]!r}"
    )
    assert mit_alert.json()["allowed"] is True, (
        "AC-4: dieselbe Lage mit priority=alert_check liegt unter deren "
        "Schwelle (95 %) und muss durchgelassen werden. Beide Antworten "
        "gleich => der Endpunkt reicht die Prioritaet nicht durch, sondern "
        f"verdrahtet sie fest. Bekam {mit_alert.json()}"
    )


def test_user_id_aus_der_query_bestimmt_den_getroffenen_topf(core_client, kleiner_deckel):
    """AC-4 (zweite Haelfte: die user_id wirkt an der richtigen Stelle).

    Given A ist ueber seinem fairen Anteil, B darunter — derselbe globale Stand
    When nacheinander mit ``user_id=A`` und ``user_id=B`` reserviert wird
    Then geht das Urteil auseinander UND die Buchung des erlaubten Aufrufs
         landet ausschliesslich im Topf von B.

    Ohne die Topf-Gegenlesung waere der Test auch dann gruen, wenn der
    Endpunkt zwar richtig urteilt, aber auf ein fremdes Konto bucht.
    """
    _baue_stufe_1_lage(core_client)
    _pruefe_arrangement()

    a_vorher = _nutzer_calls(NUTZER_A)
    b_vorher = _nutzer_calls(NUTZER_B)

    urteil_a = _reserve(core_client, NUTZER_A)
    urteil_b = _reserve(core_client, NUTZER_B)

    assert urteil_a.status_code == 200 and urteil_b.status_code == 200, (
        f"Erwartet 200/200, bekam {urteil_a.status_code}/{urteil_b.status_code}"
    )
    assert urteil_a.json()["allowed"] is False and urteil_b.json()["allowed"] is True, (
        "AC-4: dieselbe Anfrage mit unterschiedlicher user_id muss "
        f"unterschiedlich beschieden werden, bekam A={urteil_a.json()} "
        f"B={urteil_b.json()}"
    )
    assert _nutzer_calls(NUTZER_A) == a_vorher, (
        "AC-4/AC-8: der abgelehnte Aufruf von A darf seinen Topf nicht erhoehen"
    )
    assert _nutzer_calls(NUTZER_B) - b_vorher == EINHEITEN_JE_RESERVIERUNG, (
        "AC-4: die 2 Einheiten des erlaubten Aufrufs muessen im Topf von B "
        f"landen, bekam {_nutzer_calls(NUTZER_B) - b_vorher}"
    )


# ---------------------------------------------------------------------------
# Schnittstelle: user_id ist Pflichtparameter ohne Default (ADR-0003/ADR-0075)
# ---------------------------------------------------------------------------

def test_reserve_ohne_user_id_wird_abgewiesen(core_client):
    """Spec „Implementation Details": auf der Leitung reisen user_id UND
    priority; ``user_id`` ist Pflichtparameter ohne Default (Muster
    ``api/routers/internal.py:29``, ADR-0075 Punkt 4).

    Ein Default — insbesondere ``"default"`` — waere ein Cross-User-Datenleck:
    die Buchung landete auf einem fremden Konto.
    """
    antwort = core_client.post(PFAD, params={"priority": "polling"})

    assert antwort.status_code != 503, (
        "Aufbaufehler: kein gemeinsames Geheimnis im Prozess gesetzt"
    )
    assert antwort.status_code == 422, (
        "Ohne user_id muss der Endpunkt die Anfrage abweisen (422, "
        f"Pflicht-Query-Parameter), bekam {antwort.status_code}: "
        f"{antwort.text[:300]!r}"
    )
    assert _aktive_nutzer() == set(), (
        "Eine Anfrage ohne user_id darf niemanden in active_users eintragen — "
        f"vorgefunden: {_aktive_nutzer()}"
    )
