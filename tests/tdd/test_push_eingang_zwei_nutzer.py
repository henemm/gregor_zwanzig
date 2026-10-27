"""Kern-Schicht: Mandantentrennung ueber den Push-Eingang (Issue #2439 Scheibe a).

Spec: docs/specs/modules/feat_2439_befehle_push_eingang.md

AC-10: Given zwei verschiedene Nutzer mit je eigener Absendernummer und je
eigenem Trip, When beide kurz nacheinander Befehle senden und der Poll ueber den
Pfad laeuft, den der Kick ausloest (``POST /api/scheduler/inbound-sms``), Then
wirkt jeder Befehl nur auf den Trip seines Absenders, jede Antwort geht nur an
den eigenen Absender, und ein unbekannter Absender wird nie dem Nutzer
"default" zugeordnet.

Der Webhook verarbeitet nichts selbst (Variante A, "Weckruf"): die Zuordnung
Absender -> Nutzer geschieht im bestehenden Poll (Lern-Endpunkt). Der Test faehrt
deshalb den ECHTEN Endpunkt, den Go per Kick aufruft, gegen ein Journal mit drei
Nachrichten (Nutzer A, Nutzer B, Unbekannt) und nutzt das vorhandene
Transport-Fundament ``tests/tdd/_befehl_e2e_fixtures.py`` (aufgezeichneter
Netzrand, Aufzeichner statt Rueckspiegeln).

Heute ROT, weil ``/inbound-sms`` kein ``processed`` meldet (Go braucht es fuer den
Nachversuch, AC-7); die Mandantentrennung selbst ist Bestand und bleibt
mitbewacht.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import scheduler
from tests.tdd._befehl_e2e_fixtures import (
    basis_settings,  # noqa: F401  (stellt die hermetische Konfiguration bereit)
    install_transport_fakes,
    lege_po_lage_nutzer_an,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

UNBEKANNTER_ABSENDER = "+4915100000000"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(scheduler.router)
    return TestClient(app, raise_server_exceptions=True)


def test_ac10_zwei_nutzer_ueber_den_inbound_sms_endpunkt(monkeypatch, user_ids, client):
    recorder = install_transport_fakes(monkeypatch)
    a = lege_po_lage_nutzer_an(user_ids, trip_name="Trip Alpha", anzahl_vergleiche=0)
    b = lege_po_lage_nutzer_an(user_ids, trip_name="Trip Beta", anzahl_vergleiche=0)
    assert a.premium_sms_reply_to != b.premium_sms_reply_to

    # Nur A und B sind dem Lern-Endpunkt bekannt; der Unbekannte bekommt 409.
    recorder.registriere_premium_sms_absender(a.premium_sms_reply_to, a.user_id)
    recorder.registriere_premium_sms_absender(b.premium_sms_reply_to, b.user_id)
    recorder.journal_eintrag_anhaengen(a.premium_sms_reply_to, "status")
    recorder.journal_eintrag_anhaengen(UNBEKANNTER_ABSENDER, "status")
    recorder.journal_eintrag_anhaengen(b.premium_sms_reply_to, "status")

    antwort = client.post("/api/scheduler/inbound-sms")

    assert antwort.status_code == 200, antwort.text
    body = antwort.json()
    assert body.get("status") != "busy", body
    # AC-7-Vertrag: genau die zwei bekannten Absender wurden VERARBEITET; der
    # unbekannte zaehlt nicht. (Heute fehlt das Feld ganz.)
    assert body.get("processed") == 2, f"processed muss 2 sein (A und B, nicht der Unbekannte): {body}"

    recorder.pruefe_keine_unbekannten_aufrufe()
    gesendet = recorder.premium_sms_out
    assert len(gesendet) == 2, f"genau eine Antwort je bekanntem Absender erwartet: {gesendet!r}"
    an_a = [m for m in gesendet if m["to"] == a.premium_sms_reply_to]
    an_b = [m for m in gesendet if m["to"] == b.premium_sms_reply_to]
    assert len(an_a) == 1 and len(an_b) == 1, f"je Absender genau eine Antwort: {gesendet!r}"

    # Jeder Befehl wirkt nur auf den Trip des eigenen Absenders.
    assert "Trip Alpha" in an_a[0]["text"] and "Trip Beta" not in an_a[0]["text"], an_a[0]["text"]
    assert "Trip Beta" in an_b[0]["text"] and "Trip Alpha" not in an_b[0]["text"], an_b[0]["text"]

    # Der unbekannte Absender bekommt nichts und landet nie bei "default".
    assert all(m["to"] != UNBEKANNTER_ABSENDER for m in gesendet), gesendet
    lern = getattr(recorder, "premium_sms_learn_aufrufe", [])
    assert any(p.get("from") == UNBEKANNTER_ABSENDER for p in lern), (
        "der unbekannte Absender muss durch den Lern-Endpunkt gelaufen sein (409)"
    )
    for text in (m["text"] for m in gesendet):
        assert "default" not in text.lower().split(), text


def test_ac10_nur_unbekannter_absender_wirkungslos(monkeypatch, user_ids, client):
    """Gegenprobe: ohne bekannten Absender keine Antwort, processed == 0."""
    recorder = install_transport_fakes(monkeypatch)
    lege_po_lage_nutzer_an(user_ids, trip_name="Trip Gamma", anzahl_vergleiche=0)
    recorder.journal_eintrag_anhaengen(UNBEKANNTER_ABSENDER, "status")

    antwort = client.post("/api/scheduler/inbound-sms")

    assert antwort.status_code == 200, antwort.text
    body = antwort.json()
    assert body.get("processed") == 0, f"unbekannter Absender darf nicht zaehlen: {body}"
    assert recorder.premium_sms_out == [], recorder.premium_sms_out
