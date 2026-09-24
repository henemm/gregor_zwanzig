"""TDD RED — Issue #2406 (S3 aus #2153, Epic #2138): Fail-closed-Sperre des
SMS-Versands auf die BESTAETIGTE Nummer.

Spec: docs/specs/modules/sms_nummer_verifikation.md — AC-1, AC-8 (Python-Teil),
AC-12; Wirkstelle `src/app/config.py::with_user_profile` (§9).

Gemessen wird an der WIRKSTELLE und auf dem VERSANDPFAD, nicht am Schreibweg:
`with_user_profile()` darf `sms_to` nur durchreichen, wenn
`sms_verified_number` (getrimmt) damit uebereinstimmt — und `SMSOutput.send()`
mit denselben Settings darf den Transport dann gar nicht erst erreichen.

Kein Netz, kein Mock-Theater: der Transport (`httpx.post`) wird durch einen
Sentinel ersetzt, der den Aufruf aufzeichnet und `AssertedNetworkTouch` wirft
(Muster tests/tdd/test_sms_test_isolation.py). Der Sentinel beweist positiv
(Kontrollfall: er FEUERT, die bestaetigte Nummer kommt durch) wie negativ
(Sperrfall: er bleibt stumm, die Sperre entschied VOR dem Transport).

Die Sandbox-Zwaenge der Basisklasse (#1336 Test-Modus-Key, #1476
Herkunftssperre) wuerden sonst VOR der Empfaengeraufloesung zuschlagen und ein
falsches Gruen erzeugen: deshalb ist `seven_sandbox_key == seven_api_key`
gesetzt — dann laufen beide Sperren durch und der Test landet tatsaechlich auf
der Verifikations-Frage.

RED heute: `with_user_profile` uebernimmt `sms_to` ungeprueft
(config.py:427-431) — die unbestaetigte Nummer erreicht `Settings.sms_to` und
der Sentinel feuert.

Ausfuehren:
  uv run pytest tests/test_sms_versand_nur_bestaetigte_nummer.py -v -rA --disable-socket
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.loader import get_data_dir
from output.channels.base import ChannelBlockedError
from output.channels.sms import SMSOutput

NUMMER_EIGEN = "+491511111111"
NUMMER_FREMD = "+491512222222"
SANDBOX = "sandbox-key-2406"


class AssertedNetworkTouch(Exception):
    """Beweist, dass der HTTP-Transport erreicht wurde."""


@pytest.fixture
def transport(monkeypatch):
    """Sentinel auf `httpx.post` — zeichnet auf und bricht ab, bevor Netz entsteht."""
    aufrufe: list[dict] = []

    def _sentinel(*args, **kwargs):
        aufrufe.append({"args": args, "kwargs": kwargs})
        raise AssertedNetworkTouch("httpx.post wurde erreicht")

    monkeypatch.setattr(httpx, "post", _sentinel)
    return aufrufe


def _profil_schreiben(user_id: str, **felder) -> Path:
    """Schreibt `data/users/<user_id>/user.json` unter der isolierten
    Testwurzel (conftest `_isolate_data_root`, #1133) — dieselbe Wurzel, die
    `with_user_profile` liest."""
    pfad = get_data_dir(user_id) / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    profil = {
        "id": user_id,
        "email": f"{user_id}@beispiel.de",
        "mail_to": f"{user_id}-empfang@beispiel.de",
        "display_name": f"Konto {user_id}",
        "tier": "standard",
    }
    profil.update(felder)
    pfad.write_text(json.dumps(profil, indent=2), encoding="utf-8")
    return pfad


def _settings() -> Settings:
    """Settings ohne .env (#2282: eine lokale .env wuerde die Aussage kippen).
    Sandbox-Key == API-Key: beide seven.io-Sperren laufen durch, der Test misst
    die Verifikations-Frage und nicht eine Konfigurationssperre."""
    return Settings(
        _env_file=None,
        env="production",
        sms_gateway_url="https://gateway.seven.io/api/sms",
        seven_api_key=SANDBOX,
        seven_sandbox_key=SANDBOX,
        sms_from=None,
        sms_to=None,
    )


# ── AC-1 (a): die Wirkstelle ────────────────────────────────────────────────


def test_ac1a_unbestaetigte_nummer_erreicht_settings_nicht():
    """user.json direkt editiert: sms_to zeigt auf eine andere Nummer als
    sms_verified_number → Settings.sms_to bleibt None (fail-closed)."""
    _profil_schreiben(
        "ac1a", sms_to=NUMMER_EIGEN, sms_verified_number=NUMMER_FREMD,
        sms_verified_at="2026-09-01T10:00:00Z",
    )
    s = _settings().with_user_profile("ac1a")
    assert s.sms_to is None, (
        "AC-1: stimmt sms_verified_number nicht mit sms_to ueberein, darf die Nummer "
        f"Settings.sms_to nie erreichen — bekommen {s.sms_to!r}"
    )
    assert not s.can_send_sms(), "AC-1: ohne Empfaenger darf can_send_sms() False sein"


def test_ac1a_nummer_ohne_bestaetigungsfeld_erreicht_settings_nicht():
    """Bestandskonto vor dem Backfill: sms_to gesetzt, sms_verified_number fehlt."""
    _profil_schreiben("ac1aa", sms_to=NUMMER_EIGEN)
    s = _settings().with_user_profile("ac1aa")
    assert s.sms_to is None, (
        "AC-1: ohne sms_verified_number ist die Nummer unbewiesen — Settings.sms_to muss None "
        f"bleiben, bekommen {s.sms_to!r}"
    )


def test_ac1a_bestaetigte_nummer_kommt_durch():
    """Kontrollfall — ohne ihn waere die Sperre auch dann 'gruen', wenn sie
    ALLE Nummern verwuerfe."""
    _profil_schreiben(
        "ac1ab", sms_to=NUMMER_EIGEN, sms_verified_number=NUMMER_EIGEN,
        sms_verified_at="2026-09-01T10:00:00Z",
    )
    s = _settings().with_user_profile("ac1ab")
    assert s.sms_to == NUMMER_EIGEN, (
        f"AC-1 Kontrollfall: die bestaetigte Nummer muss durchkommen, bekommen {s.sms_to!r}"
    )


# ── AC-1 (b): der Versandpfad ───────────────────────────────────────────────


def test_ac1b_versandpfad_blockt_unbestaetigte_nummer(transport):
    _profil_schreiben(
        "ac1b", sms_to=NUMMER_EIGEN, sms_verified_number=NUMMER_FREMD,
        sms_verified_at="2026-09-01T10:00:00Z",
    )
    kanal = SMSOutput(_settings().with_user_profile("ac1b"))
    with pytest.raises(ChannelBlockedError) as fehler:
        kanal.send("", "Testnachricht")
    assert getattr(fehler.value, "reason_code", "") == "sms_no_recipient", (
        "AC-1: der Versand muss am fehlenden Empfaenger blocken (sms_no_recipient), "
        f"bekommen {getattr(fehler.value, 'reason_code', None)!r}"
    )
    assert transport == [], (
        "AC-1: bei unbestaetigter Nummer darf der seven.io-Transport nie erreicht werden — "
        f"Aufrufe: {transport}"
    )


def test_ac1b_versandpfad_laesst_bestaetigte_nummer_durch(transport):
    """Kontrollfall auf demselben Pfad: der Sentinel FEUERT und traegt die Nummer."""
    _profil_schreiben(
        "ac1bb", sms_to=NUMMER_EIGEN, sms_verified_number=NUMMER_EIGEN,
        sms_verified_at="2026-09-01T10:00:00Z",
    )
    kanal = SMSOutput(_settings().with_user_profile("ac1bb"))
    with pytest.raises(AssertedNetworkTouch):
        kanal.send("", "Testnachricht")
    assert transport, "AC-1 Kontrollfall: die bestaetigte Nummer muss den Transport erreichen"
    assert transport[0]["kwargs"]["data"]["to"] == NUMMER_EIGEN


# ── AC-8 (Python-Teil): B traegt A's Nummer ein ─────────────────────────────


def test_ac8_fremde_nummer_bleibt_fuer_das_fremde_konto_gesperrt(transport):
    """A hat seine Nummer bestaetigt, B hat sie nur eingetragen: aus B's Konto
    geht dauerhaft keine SMS an diese Nummer, aus A's Konto sehr wohl."""
    _profil_schreiben(
        "ac8a", sms_to=NUMMER_EIGEN, sms_verified_number=NUMMER_EIGEN,
        sms_verified_at="2026-09-01T10:00:00Z",
    )
    _profil_schreiben("ac8b", sms_to=NUMMER_EIGEN)

    b = _settings().with_user_profile("ac8b")
    assert b.sms_to is None, (
        f"AC-8: B's Konto darf die fremde Nummer nicht adressieren, bekommen {b.sms_to!r}"
    )
    with pytest.raises(ChannelBlockedError):
        SMSOutput(b).send("", "Aus B's Konto")
    assert transport == [], f"AC-8: aus B's Konto darf nichts versandt werden, Aufrufe: {transport}"

    a = _settings().with_user_profile("ac8a")
    assert a.sms_to == NUMMER_EIGEN, "AC-8: A's eigene, bestaetigte Nummer bleibt wirksam"


# ── AC-12: Normalisierungs-Symmetrie nach dem Backfill ──────────────────────


def test_ac12_getrimmter_profilwert_bleibt_gegen_ungetrimmte_backfill_kopie_sendefaehig():
    """Backfill-Zustand: sms_verified_number ist die byteidentische Kopie eines
    Altbestands MIT Leerzeichen; der Nutzer speichert die Nummer spaeter ueber
    das (trimmende) Profil-Update erneut. Das Konto muss sendefaehig bleiben."""
    _profil_schreiben(
        "ac12", sms_to=NUMMER_EIGEN, sms_verified_number=f" {NUMMER_EIGEN} ",
        sms_verified_at="2026-09-01T10:00:00Z",
    )
    s = _settings().with_user_profile("ac12")
    assert s.sms_to == NUMMER_EIGEN, (
        "AC-12: der Vergleich muss beide Seiten getrimmt behandeln — sonst sperrt der Backfill "
        f"genau das Konto aus, das er schuetzen sollte. Bekommen {s.sms_to!r}"
    )


def test_ac12_ungetrimmter_altbestand_wird_getrimmt_durchgereicht():
    """Beide Seiten ungetrimmt (reiner Backfill-Zustand): sendefaehig, und der
    an den Transport gereichte Wert ist der getrimmte."""
    _profil_schreiben(
        "ac12b", sms_to=f" {NUMMER_EIGEN} ", sms_verified_number=f" {NUMMER_EIGEN} ",
        sms_verified_at="2026-09-01T10:00:00Z",
    )
    s = _settings().with_user_profile("ac12b")
    assert s.sms_to == NUMMER_EIGEN, (
        "AC-12: der Rohwert mit Leerzeichen muss getrimmt an Settings.sms_to gehen, "
        f"bekommen {s.sms_to!r}"
    )
