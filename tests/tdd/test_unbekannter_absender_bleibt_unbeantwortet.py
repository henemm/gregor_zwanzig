"""TDD RED-Nachbarschaft — unbekannter E-Mail-Absender bleibt unbeantwortet
(Issue #2168, AC-2/AC-3).

SPEC: docs/specs/modules/fix_2168_antwort_an_den_fragenden.md (AC-2, AC-3)
Kontext: docs/context/fix-2168-antwort-an-den-fragenden.md

Kein Produktivcode-Defekt hier: ``InboundEmailReader._authorize``
(``inbound_email_reader.py:188-202``) laeuft in ``_process_single`` VOR dem
Trip-Lookup (``:107-109``) und laesst nur Absender durch, die ``mail_to``
oder ``inbound_address`` des aufgeloesten Profils sind. Ein Fremder wird auf
``\\Seen`` gesetzt und verworfen — es geht KEINE Antwort raus, an niemanden.
Das ist das gewuenschte Verhalten; es war bisher nur nicht durch einen Test
bewacht, der die tatsaechliche AUSBLEIBENDE Zustellung misst (das isolierte
``_authorize(...) is False`` existiert bereits in
``test_bug_inbound_email_loop.py:71-77`` und misst nicht den Versand).

AC-2 (Schweigen) und AC-3 (Positivkontrolle) teilen sich denselben
Testaufbau: echter ``InboundEmailReader._process_single``-Durchlauf mit einem
Fake-IMAP, das nur ``fetch``/``store`` bereitstellt (genau die beiden
Methoden, die ``_process_single`` benutzt), und einem echten Versand-
Aufzeichner an der ``EmailOutput``-Konstruktor-Naht (Muster
``_EmailAufzeichner``, ``test_kanaltreue_adhoc_antwort.py:147-156``). Kein
``Mock()``/``patch()``, kein Netz, kein echtes Postfach.
"""
from __future__ import annotations

import email.message
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.config import Settings  # noqa: E402
from app.loader import load_all_trips, save_trip  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.inbound_email_reader import InboundEmailReader  # noqa: E402

#: Exakter Standort aus ``providers/fixture.py::_FIXTURE_LOCATIONS`` — nur
#: als Timezone-Anker fuer ``trip_local_today`` gebraucht, kein Wetterabruf
#: findet in ``_show_status`` statt.
INNSBRUCK = (47.2692, 11.4041)

BASIS_MAIL_TO = "bekannt@example.invalid"
BASIS_MAIL_FROM = "system@example.invalid"


def _basis_settings() -> Settings:
    return Settings(
        mail_to=BASIS_MAIL_TO,
        mail_from=BASIS_MAIL_FROM,
        smtp_host="smtp.invalid",
        smtp_user="unbrauchbar",
        smtp_pass="unbrauchbar",
    )


def _email_aufzeichner_installieren(monkeypatch) -> list[dict]:
    """Ersetzt ``notification_service.EmailOutput`` — echte Klasse an der
    Konstruktor-Naht, kein ``Mock()``. Muster: ``_EmailAufzeichner``
    (``test_kanaltreue_adhoc_antwort.py:147-156``)."""
    from services import notification_service as ns

    aufzeichnungen: list[dict] = []

    class _EmailAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, html=True, plain_text_body=None, to=None,
                 mail_type=None, mail_format=None, compare_hourly_enabled=None):
            ziel = to if to else self._s.mail_to
            aufzeichnungen.append({"empfaenger": ziel, "subject": subject})

    monkeypatch.setattr(ns, "EmailOutput", _EmailAufzeichner)
    return aufzeichnungen


class _FakeImap:
    """Stellt genau die zwei Methoden bereit, die ``_process_single``
    benutzt (``inbound_email_reader.py:101-102,108,116,133,162``)."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw
        self.store_aufrufe: list[tuple] = []

    def fetch(self, uid, spec):
        return ("OK", [(None, self._raw)])

    def store(self, uid, flags, val):
        self.store_aufrufe.append((uid, flags, val))


def _raw_mail(*, from_addr: str, subject: str, body: str) -> bytes:
    msg = email.message.EmailMessage()
    msg["From"] = from_addr
    msg["To"] = BASIS_MAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)
    return msg.as_bytes()


def _trip_anlegen(user_id: str, *, name: str) -> Trip:
    """Ein einfacher Trip mit drei Etappen (gestern/heute/morgen) am
    Fixture-Standort — genug fuer ``### status``, keine Weiterverarbeitung
    braucht Wetterdaten."""
    trip_id = f"unbeantwortet-{uuid.uuid4().hex[:8]}"
    heute = datetime.now(timezone.utc).date()
    stages = [
        Stage(
            id=f"T{i}", name=f"Etappe {i}", date=heute + timedelta(days=i - 1),
            waypoints=[
                Waypoint(id=f"G{i}a", name="Start",
                         lat=INNSBRUCK[0], lon=INNSBRUCK[1], elevation_m=600),
                Waypoint(id=f"G{i}b", name="Ziel",
                         lat=INNSBRUCK[0] + 0.02, lon=INNSBRUCK[1] + 0.02,
                         elevation_m=900),
            ],
        )
        for i in range(3)
    ]
    trip = Trip(id=trip_id, name=name, stages=stages, official_alerts_enabled=False)
    save_trip(trip, user_id)
    return next(t for t in load_all_trips(user_id) if t.id == trip_id)


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


def test_ac2_unbekannter_absender_erhaelt_ueberhaupt_keine_antwort(monkeypatch):
    """AC-2 (Regressionswaechter, heute GRUEN — kein Produktivcode-Defekt).

    GIVEN eine E-Mail von einem Absender, zu dem kein Nutzerprofil existiert
          (und der nicht der Basis-``mail_to`` entspricht).
    WHEN  ``_process_single`` diese Nachricht VOLLSTAENDIG durchlaeuft.
    THEN  wird UEBERHAUPT KEINE Antwort versendet — weder an den Absender
          noch an das Basis-/Betreiberprofil. Der Versand-Aufzeichner sieht
          keinen einzigen Aufruf.

    Isoliertes ``_authorize(...) is False`` genuegt hierfuer NICHT (existiert
    bereits, misst aber nicht das Ausbleiben des Versands, siehe
    ``test_bug_inbound_email_loop.py:71-77``).
    """
    aufzeichnungen = _email_aufzeichner_installieren(monkeypatch)
    settings = _basis_settings()
    reader = InboundEmailReader()

    raw = _raw_mail(
        from_addr="fremder@example.invalid",
        subject="[Irgendein Trip] Status",
        body="status",
    )
    imap = _FakeImap(raw)

    verarbeitet = reader._process_single(imap, b"1", settings)

    assert verarbeitet == 0, (
        f"Vorbedingung: ein unbekannter Absender darf keinen Befehl "
        f"verarbeitet bekommen, erhalten {verarbeitet!r}"
    )
    assert aufzeichnungen == [], (
        f"AC-2: bei einem unbekannten Absender darf UEBERHAUPT KEINE Antwort "
        f"versendet werden — weder an ihn noch an den Betreiber. Aufgezeichnet "
        f"wurden {aufzeichnungen!r}"
    )
    assert imap.store_aufrufe, (
        "Testaufbau: die Mail muss trotzdem als gelesen markiert werden "
        "(kein endloses Wiederverarbeiten)"
    )


# ═══════════════════════════ AC-3 ════════════════════════════════════════════


def test_ac3_bekannter_absender_mit_existierendem_trip_erhaelt_sehr_wohl_eine_antwort(
    monkeypatch,
):
    """AC-3 (Positivkontrolle zu AC-2, MUSS GRUEN SEIN).

    GIVEN DERSELBE Testanordnung wie AC-2, aber mit einem bekannten Absender
          (== Basis-``mail_to``) und einem existierenden Trip im Betreff.
    WHEN  ``_process_single`` diese Nachricht verarbeitet.
    THEN  wird SEHR WOHL eine Antwort versendet.

    Ohne diese Kontrolle waere das leere Ergebnis in AC-2 genauso gut durch
    einen kaputten Testaufbau erklaerbar wie durch korrektes Blocken.
    """
    aufzeichnungen = _email_aufzeichner_installieren(monkeypatch)
    settings = _basis_settings()
    reader = InboundEmailReader()

    # Der bekannte Absender ist HIER "default" (kein Profil-Match noetig) --
    # `_authorize` laesst ihn durch, weil er == settings.mail_to ist.
    trip = _trip_anlegen("default", name="AC3 Bekannter Absender Trip")

    raw = _raw_mail(
        from_addr=BASIS_MAIL_TO,
        subject=f"[{trip.name}] Status",
        body="status",
    )
    imap = _FakeImap(raw)

    verarbeitet = reader._process_single(imap, b"1", settings)

    assert verarbeitet == 1, (
        f"Vorbedingung: ein bekannter Absender mit existierendem Trip muss "
        f"verarbeitet werden, erhalten {verarbeitet!r}"
    )
    assert aufzeichnungen, (
        "AC-3: ein bekannter Absender mit existierendem Trip muss SEHR WOHL "
        "eine Antwort erhalten — der Aufzeichner sah keinen einzigen Aufruf."
    )
    assert aufzeichnungen[0]["empfaenger"] == BASIS_MAIL_TO, (
        f"AC-3: die Antwort muss an die bekannte Adresse gehen, erhalten "
        f"{aufzeichnungen!r}"
    )
