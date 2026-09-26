"""Gemeinsames Fundament der Ende-zu-Ende-Befehlstests durch den echten
Kanal-Eingang (#2417).

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md
CONTEXT: docs/context/feature-2417-interaktions-testabdeckung.md

Fuehrender Unterstrich: Test-Helfer, kein pytest-Testfall (Vorbild
``tests/tdd/_hiking_window_fixtures.py``, ``tests/tdd/_gsm7_charset.py``).

===========================================================================
Belegte Einspeisepunkte (recherchiert vor dem Bau dieses Moduls)
===========================================================================

**Transport-Bibliothek — httpx, Modulfunktionen, kein Client:**

- ``src/output/channels/telegram.py:359,377`` (``TelegramOutput._post``):
  ``httpx.post(url, json=payload, timeout=...)`` — Modulfunktion, kein
  ``httpx.Client``. Ein ``httpx.MockTransport`` liesse sich hier NICHT
  einhaengen; der Netzrand ist ``httpx.post`` selbst.
- ``src/output/channels/seven_io_base.py:171`` (``SevenIoChannelBase.send``,
  Basis von ``PremiumSmsOutput``): ebenfalls ``httpx.post(...)``, aber mit
  ``data=payload`` (Formular, seven.io erwartet ``application/x-www-form-
  urlencoded``) statt ``json=``. Unterscheidbar von Telegram allein am
  Keyword-Argument.
- ``src/services/inbound_sms_reader.py:245`` (``_verarbeite_befehl``-Vorlauf
  in ``_poll_journal``): ``httpx.post(LEARN_ENDPOINT, json=payload,
  timeout=5)`` gegen den internen Go-Lern-Endpunkt
  (``/api/internal/premium-sms-learn``).
- ``src/services/inbound_sms_reader.py:388`` (``_fetch_journal``):
  ``httpx.get(JOURNAL_URL, headers=..., params={"limit": 100}, timeout=10)``.

  Alle vier Aufrufe nutzen denselben, geteilten ``httpx``-Modulnamensraum
  (jedes Modul macht ``import httpx`` und ruft ``httpx.post``/``httpx.get``
  auf das Modulobjekt). EIN globaler ``monkeypatch.setattr(httpx, "post",
  sink)`` bzw. ``"get"`` faengt deshalb ALLE vier Stellen — Vorbild
  ``tests/tdd/test_telegram_test_mode_guard.py:56-76`` (Sink-Klasse statt
  Mock). ``tests/tdd/test_premium_sms_kommandopfad.py:203-211`` ersetzt
  stattdessen das ``httpx``-Symbol NUR im Reader-Modul — dieses Fundament
  geht bewusst den globalen Weg, weil die Spec explizit den Netzrand ALLER
  drei Kanaele mit EINEM Sink verlangt (weniger Faelle, in denen ein Test
  vergisst, eine der vier Stellen zu patchen).

**SMTP — smtplib.SMTP als Context-Manager:**

- ``src/output/channels/email.py:503-518`` (``EmailOutput._dial_and_send``):
  ``with smtplib.SMTP(host, port, timeout=...) as server: server.starttls();
  server.login(...); server.sendmail(from_addr, recipients, msg.as_string())``.
  Sink-Vorbild: ``tests/tdd/test_mail_fallback_guard.py:93-151``
  (``_FakeSMTPConnection``/``_RecordingSMTP``) — ``sendmail()`` bekommt den
  bereits fertig serialisierten RFC822-Text (``msg.as_string()``), das
  Aufzeichnen dieses Strings reicht fuer jede MIME-/Header-Zusicherung.

**Herkunftssperre (#1476) — ALLE DREI Sendekanaele leiten in diesem Worktree
sonst um oder werfen:**

- ``src/output/channels/telegram.py::_guard_code_origin`` (~L152-172): bei
  ``running_origin(Path(__file__)) == "test"`` wird JEDE ``chat_id`` auf
  ``settings.telegram_test_chat_id`` umgeschrieben — unabhaengig vom
  Aufrufer. Da dieses Modul in einem Git-Worktree unter
  ``/home/hem/gregor_zwanzig/.claude/worktrees/...`` liegt, ist
  ``running_origin`` hier IMMER ``"test"`` (``app/origin_guard.py``:
  Checkout-Wurzel != ``PROD_ROOT``/``STAGING_ROOT`` -> Default ``"test"``).
  Ungepinnt wuerden AC-12/AC-32 (verschiedene Chat-IDs je Nutzer) strukturell
  IMMER auf dieselbe Test-Chat-ID einlaufen.
- ``src/output/channels/premium_sms.py::_origin`` (eigenes Modulsymbol,
  ueberschreibt ``SevenIoChannelBase._origin``): bei Herkunft ``"test"``
  wird NUR der API-Key auf den Sandbox-Key umgeschaltet
  (``seven_io_base.py:127-149``) — der Empfaenger (gelernte Rueckadresse)
  bleibt unangetastet. Ein Pin ist hier fachlich NICHT noetig, wird aber aus
  Konsistenzgruenden mitgepinnt (ein Sandbox-Key muss ohnehin gesetzt sein).
- ``src/output/channels/email.py:679`` (``EmailOutput.send``): bei
  Herkunft ``"test"`` UND Empfaenger != ``gregor-test@henemm.com`` wird JEDER
  Empfaenger auf genau diese eine Adresse umgeschrieben — zerstoert jede
  Mandantentrennung (AC-12 fuer E-Mail).
- ``src/services/inbound_sms_reader.py::_origin`` (lokale Tiefe-2-Variante,
  L118-129) + ``poll_and_process`` (L146-182): bei Herkunft != ``"production"``
  wird der komplette Journal-Poll uebersprungen, AUSSER
  ``GZ_PREMIUM_SMS_POLL_DRYRUN=1`` ist gesetzt — dann laeuft ein Trockenlauf,
  der ``_verarbeite_befehl`` NIE aufruft (Spec-Zweig ``dry_run: if ...:
  learned+=0`` statt ``self._verarbeite_befehl(...)``). Fuer eine ECHTE
  Befehlsausfuehrung durch den Journal-Eingang (Spec-Forderung) muss die
  Herkunft auf ``"production"`` gepinnt werden — Vorbild
  ``tests/tdd/test_premium_sms_kommandopfad.py:381-399``
  (``monkeypatch.setattr(reader_mod, "classify_origin", lambda root:
  herkunft)``), hier global uebernommen.

Alle vier Pins geschehen in :func:`pin_production_origins`.

**E-Mail-Empfaenger-Guard (unabhaengig von der Herkunftssperre):**

- ``src/output/channels/email.py:761-800``: auf dem NICHT-Resend-Pfad (jeder
  ``smtp_host`` ohne Substring ``"resend"``) sind NUR Empfaenger aus
  ``LOCAL_MAIL_DOMAINS = {"henemm.com"}`` erlaubt (``_is_local_mail_domain``,
  L229), reservierte Test-Domains (``example.com`` u.a., L195) sind IMMER
  blockiert. Fixture-Nutzer brauchen deshalb ``mail_to`` auf
  ``@henemm.com`` (z.B. ``nutzer-a@henemm.com``), niemals
  ``@example.com``/``.invalid``.

**Mail-SPF/DKIM-Autorisierung (``_authorize``, inbound_email_reader.py:225-254):**

- Braucht ``Authentication-Results: <mail_server_hostname>; spf=pass;
  dkim=pass`` (oder ``dmarc=pass`` als Alignment-Ersatz) UND
  ``settings.email_verified_at`` gesetzt. Fixtures:
  ``tests/fixtures/authentication_results_fixtures.py::AR_PASS,
  TEST_AUTHSERV_ID`` (Vorbild:
  ``tests/test_inbound_reader_no_default_settings_lookup.py:79-97``).

**Offline-Wetter — Fixture-Provider, EXAKTER Koordinatentreffer:**

- ``tests/conftest.py:65-79`` (autouse ``_use_fixture_provider``, alle
  Nicht-``live``-Tests): erzwingt ``GZ_TEST_FIXTURE_DIR`` -> ``FixtureProvider``
  fuer JEDEN Forecast-Abruf, auch den vollen On-Demand-Versand
  (``heute``/``morgen`` loesen ``TripCommandProcessor._trigger_on_demand`` ->
  ``TripReportSchedulerService.send_on_demand_report`` aus,
  ``trip_command_processor.py:1163-1170,1237-1281`` — das ist der VOLLE
  Briefing-Versandpfad, keine einfache Text-Antwort).
- ``src/providers/fixture.py:42-53``: EINZIGE Fixture-Location ist
  Innsbruck (47.2692, 11.4041); der Nearest-Match trifft sie unabhaengig von
  der tatsaechlichen Distanz. Alle Fixture-Wegpunkte in diesem Modul nutzen
  deshalb exakt diese Koordinaten (Vorbild:
  ``tests/tdd/test_premium_sms_kommandopfad.py`` ``INNSBRUCK = (47.2692,
  11.4041)``, ``official_alerts_enabled=False`` — sonst haengt der Alarmpfad
  ohne Fixture-Naht am Netz).
- Fuer Ad-hoc-Abfragen (Metrik-Kuerzel, ``glance``, ``timeline_*``,
  ``strecke``), die NICHT ueber den vollen Versandpfad laufen, sondern ueber
  ``WeatherExtractor``/Snapshot-Cache: zusaetzliche Vorbelegung via
  ``WeatherSnapshotService(user_id).save(trip_id, segments, date)``
  (Vorbild ``tests/helpers/adhoc_metrik_fixtures.py:179-198``) macht
  ``timeline.available`` sofort ``True`` und verhindert einen zweiten,
  echten Fetch-Versuch.

**Premium-SMS-Journal-Eingang — ``_poll_journal``/``_verarbeite_befehl``,
nicht der direkte Funktionsaufruf:**

- ``src/services/inbound_sms_reader.py:146-182`` (``poll_and_process``) ist
  der oeffentliche Einstieg; er ruft intern ``_poll_journal`` (L184-302), die
  bei HTTP 200 des Lern-Endpunkts UND ``dry_run=False`` ``_verarbeite_befehl``
  aufruft (L272-273). Dieses Fundament faehrt deshalb ``poll_and_process()``
  (mit gepinnter ``"production"``-Herkunft), NICHT ``_verarbeite_befehl``
  direkt — sonst wuerden Absender-Zuordnung (Lern-Endpunkt) und
  Verknuepfungs-Code-Zerlegung (``split_link_code``) am Draht vorbeigehen,
  genau der Fehler, den die Spec ausdruecklich ausschliesst ("nicht ueber
  einen direkten Funktionsaufruf, der die Lern-/Zuordnungsschritte
  ueberspringt").
- Vorbild fuer Journal-/Lern-Doubles: ``tests/tdd/test_premium_sms_kommandopfad.py``
  Klassen ``_Journal``/``_LernEndpunkt`` (L131-200) — hier als Recorder-
  Methoden auf dem GLOBALEN httpx-Sink nachgebaut (s.o.).

**Telegram-Webhook-Eingang / Callback / Mandanten-Trennung:**

- ``src/services/inbound_telegram_reader.py::_process_update`` (L168-293)
  ist der reale Eingang fuer Text/Slash; ``_process_callback_query``
  (L373-439) fuer Knopf-Klicks. Dieses Fundament ruft BEIDE Methoden direkt
  auf einer echten ``InboundTelegramReader()``-Instanz auf (kein
  ``TestClient`` gegen ``/api/internal/telegram-webhook`` — der Secret-
  Header-Pfad selbst ist nicht Gegenstand dieser Spec und fuegte nur eine
  weitere HTTP-Schicht ohne zusaetzlichen Erkenntniswert hinzu; die Reader-
  Methode IST der Vertrag, den Go nach dem Secret-Check unveraendert
  aufruft).
- Mandantenaufloesung ueber ``lookup_user_by_telegram_chat_id`` (echt, nicht
  gepatcht) — jeder Fixture-Nutzer bekommt eine EIGENE ``telegram_chat_id``
  in ``user.json``, echte Datei unter der isolierten Datenwurzel
  (``tests/conftest.py`` autouse ``_isolate_data_root``/``_SESSION_DATA_ROOT``).

**Fixture-Datenhelfer — kopiert, NICHT verschoben:**

- ``tests/tdd/test_eingangsauswahl_trip_und_vergleich.py:57-113``
  (``user_ids``, ``_trip``, ``_preset``, ``_preset_file``, ``_read``) sind
  unten als ``_trip``/``_preset``/``_preset_file``/``_read`` uebernommen und
  an die Innsbruck-Fixture-Koordinaten sowie ``official_alerts_enabled=False``
  angepasst (die Originaldatei bleibt UNVERAENDERT lauffaehig, dieses Modul
  kopiert nur). ``_via_telegram``/``_via_premium_sms`` (L127-176 derselben
  Datei) wurden BEWUSST NICHT uebernommen: sie patchen
  ``TelegramOutput.send``/``PremiumSmsOutput.send`` als Klassenmethode weg —
  exakt die "gepruefte, wo der Code steht, nicht wo er wirkt"-Luecke, die
  Issue #2417 ausloeste. Die neuen Eingangstreiber unten
  (``sende_telegram_text`` etc.) senden stattdessen bis zum echten
  ``httpx.post``/``smtplib.SMTP``-Netzrand.

**Nutzerkennung — bewusst OHNE "test"/"tdd":**

- ``src/app/config.py:56-71`` (``is_test_user_id``): seit #2152/ADR-0072 gilt
  NICHT mehr die alte "test"/"tdd"-Substring-Heuristik, sondern
  ausschliesslich der Fixture-Nutzer ``tg-live-e2e`` (case-insensitiv) oder
  ein explizites ``is_test_user: true`` im Profil. ``with_user_profile()``
  (``config.py:394-453``) setzt bei ``force_test=True`` u.a.
  ``telegram_chat_id`` NICHT aus dem Profil (L440-441) — ein
  faelschlich als Test-Nutzer erkanntes Konto wuerde also OHNE Fehlermeldung
  die falsche (globale Test-)Chat-ID bekommen und AC-12/AC-32 unbemerkt
  entwerten. Fixture-Nutzerkennungen hier tragen deshalb das Praefix
  ``gz2417-`` (kein "test"/"tdd"), und kein Profil setzt ``is_test_user``.

===========================================================================
Nachgemessene Telegram-Antworten (PO-Feedback 2026-09-25, Korrektur)
===========================================================================

``klicke_telegram_knopf`` rief anfangs ``_process_callback_query`` DIREKT
auf einer frischen ``InboundTelegramReader()``-Instanz auf -- die Methode
selbst ruft aber nie ``_ensure_notification_service()``, das passiert nur
in ``_process_update`` VOR der Callback-Weiche (L173). Ein direkter Aufruf
kollabierte deshalb mit ``AttributeError: 'NoneType' object has no
attribute 'edit_telegram_message_text'``. Fix: ``klicke_telegram_knopf``
baut jetzt ein volles ``update``-Dict mit ``"callback_query"``-Schluessel
und geht ueber ``_process_update`` -- der reale Weg, den auch das Produkt
nimmt (``_process_callback_query`` wird nie isoliert aufgerufen).

Beim Nachmessen jedes ``_QUERY_KEYS``-Eintrags und jedes
``_CALLBACK_QUERY_MAP``-Schluessels gegen den tatsaechlich gesendeten Text
(Lage L2, Fixture-Trip "Solo-Trip"):

- ``glance``/``act_overview``: ``"[[Solo-Trip] Glance]\n\n🗓 Glance — heute
  & morgen\n\nheute (25.09): 🌡 2–2°C  💨 15 km/h  🌧 0.6mm  ⛈ Gewitter:
  kein\nmorgen (26.09): ..."``. Der Trip-Name steht zwar im (doppelt
  eingeklammerten) Betreff -- das gilt aber fuer JEDE Antwort jedes Befehls
  gleichermassen und schliesst nichts Falsches aus. Merkmal deshalb die
  Katalog-Einheiten ``get_metric("temperature").unit`` (``"°C"``) UND
  ``get_metric("wind").unit`` (``"km/h"``), die nur bei echt gerendertem
  Zahlenmaterial auftauchen.
- ``heute_gewitter``/``gewitter``: ``"⛈ Gewitter heute (25.09): kein"`` --
  Merkmal ``get_metric("thunder").label_de`` (``"Gewitter"``).
- ``timeline_heute``/``tl_today``, ``timeline_morgen``/``tl_tomorrow``:
  ``"📋 Timeline · Heute (25.09)\n\n🕐 19:00 · 900 m\n   🌡 2–2 °C  💨 15
  km/h  🌧 0.6 mm  ⛈ kein"`` -- dieselben zwei Katalog-Einheiten wie
  ``glance``.
- ``now``/``jetzt``: ``"[[Solo-Trip] Nowcast]\n\nKein Niederschlag...\n
  Quelle: ARPAE ICON-2I (2 km, Italien)."`` -- der Trip-Name TRAEGT hier
  tatsaechlich die einzige stabile Unterscheidung (die Nowcast-Quelle
  wechselt je nach Wetterlage), Merkmal bleibt ``ziel``.
- ``act_help``: identisch zur getippten ``hilfe`` (alle 12 Befehlswoerter).
- ``act_pause``/``act_skip``: identisch zu ``pause``/``skip`` als getipptes
  Wort (der Ziel-/Trip-Name traegt auch hier tatsaechlich, weil BEIDE
  Antworten -- Erfolg UND "Dauer fehlt" -- ihn im Betreff fuehren).
- ``act_columns``: KEIN Wort-Pendant, KEIN ``reply_markup`` (nachgemessen:
  ``markup=False``) -- reiner Hinweistext auf den Web-Editor. Merkmal ist
  das reale Zitat ``"Spalten-Konfiguration"`` aus
  ``trip_command_processor.py::_show_columns_info``. Die Spec nennt als
  Ziel "Metrik-Auswahlknöpfe im reply_markup" -- das ist der Stand NACH
  einer noch nicht gebauten Aenderung; wer das umsetzt, muss diesen Eintrag
  aktualisieren.

===========================================================================
Rebase auf origin/main (2026-09-25): SMS-Tageslimit braucht ``tier``
===========================================================================

Issue #2412 S4a (Commit 47cbc102) fuehrte ein SMS-Tageslimit ein
(``src/services/sms_daily_limit.py``): ein Nutzer OHNE ``tier`` in
``user.json`` gilt als ``"free"`` mit SMS-/Premium-SMS-Cap 0 und wird
blockiert (Log: "Premium-SMS confirmation blocked: SMS-Tageslimit
erreicht") -- unabhaengig von Journal/Lernendpunkt/Zielaufloesung, die
sonst alle sauber liefen. ``_schreibe_user_json`` (der EINE Schreibweg
fuer JEDEN Fixture-Nutzer -- PO-Lage, L1-L6, Zweitnutzer) setzt seitdem
``"tier": "premium"`` (entspricht der realen PO-Lage). Der externe Helfer
``tests/helpers/nutzer_tier.py::nutzer_mit_tier`` schreibt nur ``id``+
``tier`` und wuerde die uebrigen Felder (``mail_to``,
``telegram_chat_id``, ``premium_sms_reply_to``, ...) verlieren -- deshalb
direkt im bestehenden Read-Modify-Write ergaenzt, kein zweiter
Schreibweg.

===========================================================================
Fehlerbehandlung, die einen Testlauf FAELSCHLICH gruen aussehen laesst
===========================================================================

``NotificationService.send_command_reply_*``/``send_telegram_message``
fangen JEDE ``Exception`` und loggen sie nur (notification_service.py:
1815-1878) — ein ausgeloester Guard, ein Tippfehler im Sink oder ein
``AssertionError`` IM Sink erzeugt score `0 Sends`, nicht einen Fehlschlag.
Deshalb zeichnet der Recorder unbekannte/fehlerhafte Aufrufe in
``Recorder.unbekannt`` auf, statt sie zu werfen — jeder Aufrufer-Test MUSS
zusaetzlich ``recorder.unbekannt == []`` pruefen (bzw. den Helfer
``recorder.pruefe_keine_unbekannten_aufrufe()`` aufrufen).
"""
from __future__ import annotations

import json
import shutil
import smtplib
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import httpx
import pytest

from app.config import Settings
from app.loader import get_briefings_dir, get_data_dir, save_trip
from app.metric_catalog import get_all_metrics, get_metric
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    PrecipType,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from output.channels.telegram import TelegramOutput
from services.inbound_sms_reader import SERVICE_NUMBER
from services.trip_command_processor import (
    _BARE_KEYWORD_MAP,
    _BEIDE_KINDS,
    _COMMAND_SPECS,
    _QUERY_KEYS,
    _ROUTE_ONLY,
)
from services.inbound_telegram_reader import _CALLBACK_QUERY_MAP
from services.trip_selection import KEIN_KANDIDAT_TEXT
from tests.fixtures.authentication_results_fixtures import AR_PASS, TEST_AUTHSERV_ID

# ---------------------------------------------------------------------------
# Fixture-Koordinaten (Fixture-Provider, exakter Treffer -- s. Moduldoku)
# ---------------------------------------------------------------------------

INNSBRUCK_LAT, INNSBRUCK_LON = 47.2692, 11.4041

#: Nicht-Resend-Host (lokale Zustellung, Vorbild test_mail_fallback_guard.py).
SMTP_HOST = "mail.henemm.com"
LEARN_ENDPOINT_SUFFIX = "/api/internal/premium-sms-learn"
JOURNAL_URL = "https://gateway.seven.io/api/journal/inbound"
PREMIUM_SMS_SANDBOX_KEY = "sandbox-fake-2417"

#: Noch nicht existierender Produktsymbole -- lazy per getattr holen (Spec-
#: Auflage: NIE top-level importieren, sonst bricht der Collect ganzer
#: Testdateien, solange die Fixes aus #2417 nicht implementiert sind).
_SENTINEL = object()


def kein_aktives_ziel_text():
    """Der (noch zu implementierende) Hinweistext fuer L4/L5 bei
    ``_ROUTE_ONLY``/Metrik-Kuerzel-Befehlen (Spec-Abschnitt "Erlaeuterungen").
    ``None``, solange das Produkt das Symbol nicht anbietet -- ein Test, der
    das braucht, MUSS das selbst pruefen und rot werden, statt hier zu
    raten."""
    from services import trip_selection as ts

    return getattr(ts, "KEIN_AKTIVES_ZIEL_TEXT", _SENTINEL)


def premium_sms_kurzhilfe_funktion():
    """Die (noch zu implementierende) GSM-7-Kurzhilfe-Funktion fuer den
    Premium-SMS-Kanal. ``None``, solange sie nicht existiert."""
    from services import trip_command_processor as tcp

    fn = getattr(tcp, "premium_sms_kurzhilfe", _SENTINEL)
    return None if fn is _SENTINEL else fn


# ---------------------------------------------------------------------------
# Herkunftssperren pinnen (s. Moduldoku) + Prozessweiten Zustand zuruecksetzen
# ---------------------------------------------------------------------------

def pin_production_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pint die Herkunftssperre auf ``"production"`` in allen drei
    Sendekanaelen PLUS die lokale Herkunftspruefung des Premium-SMS-Readers.

    Ohne diesen Pin misst dieses Fundament (das im Worktree, nicht im
    Hauptcheckout laeuft) strukturell die falsche Sache: jeder Telegram-/
    E-Mail-Empfaenger wuerde auf eine einzelne Test-Adresse umgeschrieben,
    und der Premium-SMS-Journal-Poll wuerde ganz uebersprungen (s. Moduldoku).
    """
    import output.channels.email as email_mod
    import output.channels.premium_sms as premium_sms_mod
    import output.channels.telegram as telegram_mod
    import services.inbound_sms_reader as sms_reader_mod

    monkeypatch.setattr(telegram_mod, "running_origin", lambda module_file: "production")
    monkeypatch.setattr(premium_sms_mod, "running_origin", lambda module_file: "production")
    monkeypatch.setattr(email_mod, "running_origin", lambda module_file: "production")
    monkeypatch.setattr(sms_reader_mod, "classify_origin", lambda root: "production")


def reset_telegram_process_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """``TelegramOutput`` haelt Drossel-Zeitstempel und gesendete IDs auf
    KLASSENEBENE (prozessweit, telegram.py:143-151) -- ohne Reset sammeln
    sich ueber viele parametrisierte Faelle hinweg Eintraege an, bis die
    Drossel (``_reserve_send_slot``) echte Wartezeiten (bis 30s) ausloest."""
    monkeypatch.setattr(TelegramOutput, "_rate_limit_stamps", {})
    monkeypatch.setattr(TelegramOutput, "recent_message_ids", [])


# ---------------------------------------------------------------------------
# Recorder -- der EINE Netzrand-Sink fuer Telegram/seven.io/Lern-Endpunkt/
# Journal (httpx) und fuer die Antwortmail (smtplib.SMTP)
# ---------------------------------------------------------------------------

@dataclass
class Recorder:
    """Zeichnet JEDEN tatsaechlich versendeten Aufruf auf. Zusicherung
    ausschliesslich hierauf, nie auf Rueckgabewerte eigener Funktionen."""

    telegram: list[dict] = field(default_factory=list)
    premium_sms_out: list[dict] = field(default_factory=list)
    emails: list[dict] = field(default_factory=list)
    unbekannt: list[dict] = field(default_factory=list)
    _next_message_id: int = 9000
    _journal: list[dict] = field(default_factory=list)
    _naechste_journal_id: int = 1

    # -- Telegram/seven.io/Lern-Endpunkt: gemeinsamer httpx.post-Sink -------

    def httpx_post(self, url, *, json=None, data=None, headers=None, timeout=None, **kw):
        url_s = str(url)
        if "api.telegram.org" in url_s:
            return self._telegram_post(url_s, json or {})
        if url_s.endswith(LEARN_ENDPOINT_SUFFIX):
            return self._learn_post(json or {})
        if data is not None and "text" in data and "to" in data:
            # seven.io-Gateway (SMS/Premium-SMS) -- Formular, kein JSON.
            self.premium_sms_out.append(
                {"to": data["to"], "text": data["text"], "from": data.get("from")}
            )
            return httpx.Response(200, text="100")
        self.unbekannt.append({"url": url_s, "json": json, "data": data, "richtung": "post"})
        return httpx.Response(599, text="unbekannte URL im Testlauf (Recorder.httpx_post)")

    def httpx_get(self, url, *, headers=None, params=None, timeout=None, **kw):
        url_s = str(url)
        if url_s == JOURNAL_URL:
            return httpx.Response(200, json=list(self._journal))
        self.unbekannt.append({"url": url_s, "richtung": "get"})
        return httpx.Response(599, text="unbekannte URL im Testlauf (Recorder.httpx_get)")

    def _telegram_post(self, url: str, payload: dict) -> httpx.Response:
        methode = url.rsplit("/", 1)[-1]
        self._next_message_id += 1
        mid = self._next_message_id
        eintrag = {"methode": methode, "payload": payload, "message_id": mid}
        self.telegram.append(eintrag)
        if methode == "sendMessage":
            return httpx.Response(200, json={"ok": True, "result": {"message_id": mid}})
        if methode in ("editMessageText", "deleteMessage", "answerCallbackQuery", "setMyCommands"):
            return httpx.Response(200, json={"ok": True, "result": True})
        self.unbekannt.append({"url": url, "json": payload, "richtung": "telegram-unbekannt"})
        return httpx.Response(404, json={"ok": False})

    def _learn_post(self, payload: dict) -> httpx.Response:
        self.premium_sms_learn_aufrufe = getattr(self, "premium_sms_learn_aufrufe", [])
        self.premium_sms_learn_aufrufe.append(payload)
        sender = payload.get("from", "")
        user_id = self._nummer_zu_user.get(sender)  # type: ignore[attr-defined]
        if not user_id:
            return httpx.Response(409, json={"error": "no_unique_premium_candidate"})
        return httpx.Response(200, json={"status": "ok", "user_id": user_id})

    # -- Premium-SMS-Journal: vom Treiber befuellt --------------------------

    def registriere_premium_sms_absender(self, nummer: str, user_id: str) -> None:
        if not hasattr(self, "_nummer_zu_user"):
            self._nummer_zu_user: dict[str, str] = {}
        self._nummer_zu_user[nummer] = user_id

    def journal_eintrag_anhaengen(self, sender: str, text: str) -> int:
        msg_id = self._naechste_journal_id
        self._naechste_journal_id += 1
        self._journal.append({
            "id": str(msg_id), "from": sender, "to": SERVICE_NUMBER, "text": text,
            "timestamp": "2026-09-25 08:00:00", "reply_to_message_id": None, "price": 0.0,
        })
        return msg_id

    # -- SMTP-Sink ------------------------------------------------------

    def smtp_sink(self):
        recorder = self

        class _FakeSocket:
            def settimeout(self, timeout: float) -> None:
                pass

        class _FakeSMTPConnection:
            def __init__(self, host: str) -> None:
                self._host = host
                self.sock = _FakeSocket()

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> bool:
                return False

            def starttls(self) -> None:
                return None

            def login(self, user, password) -> None:
                return None

            def sendmail(self, from_addr, to_addrs, msg) -> None:
                recorder.emails.append({
                    "host": self._host, "from": from_addr,
                    "to": tuple(to_addrs), "raw": msg,
                })

        class _RecordingSMTP:
            def __call__(self, host, port, *a, **kw):
                return _FakeSMTPConnection(host)

        return _RecordingSMTP()

    # -- Auswertungshelfer ------------------------------------------------

    def pruefe_keine_unbekannten_aufrufe(self) -> None:
        assert self.unbekannt == [], (
            f"Recorder hat {len(self.unbekannt)} nicht erkannte/nicht "
            f"routbare Netzaufrufe gesehen -- ein Guard oder ein Fehler im "
            f"Sink kann Sends stumm verschlucken (s. Moduldoku): {self.unbekannt}"
        )

    def telegram_inhalte(self, chat_id: str | int | None = None) -> list[dict]:
        """Telegram-Sends, die tatsaechlich SICHTBAREN Inhalt tragen -- ohne
        das Loeschen der Lade-Nachricht und ohne ``answerCallbackQuery``
        (Spinner-Ende traegt keinen Inhalt). Fuer AC-32 ("genau ein Versand")."""
        raus = [
            e for e in self.telegram
            if e["methode"] in ("sendMessage", "editMessageText")
        ]
        if chat_id is not None:
            raus = [e for e in raus if str(e["payload"].get("chat_id")) == str(chat_id)]
        return raus


def install_transport_fakes(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    """Ein Aufruf, der alles Noetige installiert: Herkunftspins, Prozess-
    Zustands-Reset, globaler httpx- und smtplib-Sink. Gibt den Recorder
    zurueck, an dem jeder Test seine Zusicherungen misst."""
    pin_production_origins(monkeypatch)
    reset_telegram_process_state(monkeypatch)
    recorder = Recorder()
    monkeypatch.setattr(httpx, "post", recorder.httpx_post)
    monkeypatch.setattr(httpx, "get", recorder.httpx_get)
    monkeypatch.setattr(smtplib, "SMTP", recorder.smtp_sink())
    return recorder


# ---------------------------------------------------------------------------
# Settings-Aufbau -- jedes Transport-Feld ausdruecklich (#1477)
# ---------------------------------------------------------------------------

def basis_settings(**overrides) -> Settings:
    """Basis-``Settings`` mit unbrauchbaren, aber VOLLSTAENDIGEN
    Zugangsdaten -- kein Feld faellt still auf die echte Prod-``.env``
    zurueck (#1477)."""
    defaults = dict(
        _env_file=None,
        env="development",
        smtp_host=SMTP_HOST,
        smtp_port=587,
        smtp_user="unbrauchbar",
        smtp_pass="unbrauchbar",
        mail_from="gregor_zwanzig@henemm.com",
        mail_to="globaler-rueckfall@henemm.com",
        mail_server_hostname=TEST_AUTHSERV_ID,
        imap_host=SMTP_HOST,
        imap_user="unbrauchbar",
        imap_pass="unbrauchbar",
        telegram_bot_token="0000000:unbrauchbar",
        telegram_chat_id="globaler-rueckfall-chat",
        telegram_test_bot_token="",
        telegram_test_chat_id="",
        sms_gateway_url="https://gateway.seven.io/api/sms",
        seven_api_key="unbrauchbar",
        seven_sandbox_key=PREMIUM_SMS_SANDBOX_KEY,
        sms_to="+490000000000",
    )
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Fixture-Datenhelfer -- kopiert & angepasst aus
# tests/tdd/test_eingangsauswahl_trip_und_vergleich.py:57-113 (s. Moduldoku)
# ---------------------------------------------------------------------------

@pytest.fixture
def user_ids():
    """Frische Mandantenkennungen OHNE "test"/"tdd" (s. Moduldoku) je Test,
    Aufraeumen danach."""
    created: list[str] = []

    def _new() -> str:
        uid = f"gz2417-{uuid.uuid4().hex[:8]}"
        created.append(uid)
        return uid

    yield _new
    for uid in created:
        shutil.rmtree(get_briefings_dir(uid).parent, ignore_errors=True)


#: Ein Wert je Stundenfeld, das mindestens eine waehlbare Katalog-Groesse
#: fuehrt (Team-Lead-Vorgabe 2026-09-25, Fundament-Korrektur 4 -- Vorbild
#: ``test_abruf_jede_metrik_e2e.py::STANDARD_STUNDENWERT``, HIER separat
#: gepflegt, weil eine Testdatei nicht vom Fundament importieren darf und
#: umgekehrt Doppelimport zwischen zwei gleichrangigen Modulen vermieden
#: wird). ``uv_index`` bleibt ABSICHTLICH aussen vor -- sie ist die bewusst
#: leer gelassene Groesse fuer AC-33 ("fehlende Groesse wird benannt");
#: wuerde sie hier mitgefuellt, koennte kein Ad-hoc-Abruf mehr den
#: "nicht verfuegbar"-Fall zeigen.
STANDARD_STUNDENWERT: dict = dict(
    t2m_c=12.0, wind10m_kmh=18.0, wind_direction_deg=225, gust_kmh=30.0,
    precip_1h_mm=0.4, pop_pct=40, thunder_level=ThunderLevel.MED,
    pressure_msl_hpa=1013.0, humidity_pct=55, dewpoint_c=6.0,
    snow_depth_cm=12.0, snow_new_24h_cm=2.0, snowfall_limit_m=1800,
    freezing_level_m=2200, wind_chill_c=9.0, visibility_m=8000,
    cloud_total_pct=60, cloud_low_pct=40, cloud_mid_pct=20, cloud_high_pct=10,
    dni_wm2=120.0, precip_type=PrecipType.RAIN,
)


def _segment_fuer_stage(stage: Stage) -> SegmentWeatherData:
    """EIN Segment fuer GENAU eine Etappe, mit Stundenpunkten aus
    ``STANDARD_STUNDENWERT``, deren ``arrival_time`` (= ``end_time``, s.
    ``app/day_window.py::display_end_time``) SICHER auf ``stage.date``
    faellt (06:00-17:00 UTC -- bei Innsbruck (UTC+1/+2) niemals ueber
    Mitternacht hinaus in den naechsten Kalendertag rutschend).

    WICHTIG (Team-Lead-Fund 2026-09-25, Regression bei ``heute_gewitter``):
    ein EINZELNES Mega-Segment ueber mehrere Tage (Vorbild
    ``tests/helpers/adhoc_metrik_fixtures.py``, dort nur fuer
    ``drilldown()``-Ad-hoc-Abrufe genutzt) hat GENAU EINE ``arrival_time``
    und landet damit nur in EINEM Kalendertag. ``WeatherExtractor.timeline()``
    (genutzt von ``glance``/``heute_gewitter``/``timeline_heute``/
    ``timeline_morgen`` sowie den Buttons ``act_overview``/``tl_*``)
    aggregiert aber PRO SEGMENT-``arrival_time``/Kalendertag
    (``_aggregate_day()``, ``trip_command_processor.py``) -- ein
    Mega-Segment liefert deshalb fuer ALLE Tage ausser dem einen getroffenen
    ``"noch keine Wetterdaten"`` statt eines echten Werts. Ein Segment JE
    ETAPPE (wie der echte Fetch-Pfad ``_fetch_and_save_snapshot`` es via
    ``_convert_trip_to_segments(trip, today)``/``(trip, tomorrow)`` baut)
    behebt das, ohne den Ad-hoc-``drilldown()``-Pfad zu beeintraechtigen
    (der iteriert die Zeitreihe direkt, unabhaengig von Segmentgrenzen)."""
    tag_start = datetime(
        stage.date.year, stage.date.month, stage.date.day, 6, tzinfo=timezone.utc,
    )
    punkte = [
        ForecastDataPoint(ts=tag_start + timedelta(hours=i), **STANDARD_STUNDENWERT)
        for i in range(12)
    ]
    segment = TripSegment(
        segment_id=f"seg-2417-{stage.id}",
        start_point=GPXPoint(lat=INNSBRUCK_LAT, lon=INNSBRUCK_LON, elevation_m=600),
        end_point=GPXPoint(lat=INNSBRUCK_LAT + 0.02, lon=INNSBRUCK_LON + 0.02, elevation_m=900),
        start_time=tag_start, end_time=punkte[-1].ts,
        duration_hours=11.0, distance_km=10.0, ascent_m=300.0, descent_m=300.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=0.0),
            data=punkte,
        ),
        aggregated=SegmentWeatherSummary(
            temp_min_c=-10.0, temp_max_c=35.0, thunder_level_max=ThunderLevel.MED,
            wind_max_kmh=40.0, precip_sum_mm=5.0, pop_max_pct=60,
        ),
        fetched_at=tag_start, provider=Provider.OPENMETEO.value,
    )


def _speichere_snapshot_fuer_trip(trip: Trip, user_id: str) -> None:
    """Echter Stunden-Snapshot ueber ``WeatherSnapshotService`` -- EIN
    Segment JE ETAPPE (s. ``_segment_fuer_stage``-Docstring). Vorbild
    ``tests/helpers/adhoc_metrik_fixtures.py::lege_trip_an`` /
    ``test_abruf_jede_metrik_e2e.py::_speichere_snapshot``. Noetig, weil
    ``_handle_metric_drilldown()`` (bares Metrik-Wort) ueber
    ``WeatherExtractor(...).drilldown()`` einen VORAB gespeicherten Snapshot
    liest -- ohne ihn liefert JEDES Metrik-Kuerzel strukturell "no data",
    unabhaengig davon, ob die Zielaufloesung/Formatierung korrekt ist
    (Team-Lead-Fund 2026-09-25: das machte das Premium-SMS-``sms_code``-
    Merkmal vakuum-gruen)."""
    from services.weather_snapshot import WeatherSnapshotService

    segments = [_segment_fuer_stage(stage) for stage in trip.stages]
    WeatherSnapshotService(user_id).save(trip.id, segments, date.today())


def _trip(user_id: str, name: str, *, tag: date | None = None) -> Trip:
    """Drei Etappen (gestern/heute/morgen, Ortstag) an der Innsbruck-Fixture-
    Koordinate -- Vorbild ``_trip_anlegen``
    (test_premium_sms_kommandopfad.py:350-378). ``official_alerts_enabled=
    False``, sonst haengt der Alarmpfad ohne Fixture-Naht am Netz.

    Seedet seit der Fundament-Korrektur 4 (Team-Lead 2026-09-25) zusaetzlich
    einen echten Wetter-Snapshot (``_speichere_snapshot_fuer_trip``/
    ``STANDARD_STUNDENWERT``) fuer JEDEN so angelegten Trip -- Ad-hoc-
    Metrik-Abrufe (bares Katalogwort/-kuerzel per Telegram/Premium-SMS)
    liefern dadurch echte Werte statt strukturell "no data"/"nicht
    verfuegbar", unabhaengig von der jeweiligen Lage (L2/L3/L6)."""
    heute = tag or date.today()
    trip_id = f"gz2417-{uuid.uuid4().hex[:8]}"
    stages = [
        Stage(
            id=f"T{i}", name=label, date=heute + timedelta(days=i - 1),
            waypoints=[
                Waypoint(id=f"G{i}a", name="Start",
                         lat=INNSBRUCK_LAT, lon=INNSBRUCK_LON, elevation_m=600),
                Waypoint(id=f"G{i}b", name="Ziel",
                         lat=INNSBRUCK_LAT + 0.02, lon=INNSBRUCK_LON + 0.02, elevation_m=900),
            ],
        )
        for i, label in enumerate(("Etappe Gestern", "Etappe Heute", "Etappe Morgen"))
    ]
    trip = Trip(
        id=trip_id, name=name, stages=stages, official_alerts_enabled=False,
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=True, send_sms=True,
            send_premium_sms=True, send_telegram=True,
        ),
    )
    save_trip(trip, user_id)
    from app.loader import load_all_trips
    geladen = next(t for t in load_all_trips(user_id) if t.id == trip_id)
    _speichere_snapshot_fuer_trip(geladen, user_id)
    return geladen


def _preset(user_id: str, name: str, **felder) -> dict:
    pid = f"gz2417-cmp-{uuid.uuid4().hex[:8]}"
    entry = {
        "id": pid,
        "name": name,
        "kind": "vergleich",
        "user_id": user_id,
        "location_ids": ["loc-a", "loc-b"],
        "schedule": "daily",
        "previous_schedule": "",
        "created_at": "2026-09-01T08:00:00Z",
    }
    entry.update(felder)
    d = get_briefings_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pid}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry


def _preset_file(user_id: str, preset_id: str) -> Path:
    return get_briefings_dir(user_id) / f"{preset_id}.json"


def _read(user_id: str, preset_id: str) -> dict:
    return json.loads(_preset_file(user_id, preset_id).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Nutzer-Fixturen (PO-Lage + Lagen L1-L6 + Zweitnutzer Mandantentrennung)
# ---------------------------------------------------------------------------

@dataclass
class BefehlNutzer:
    user_id: str
    mail_to: str
    telegram_chat_id: str
    premium_sms_reply_to: str
    trip: Trip | None = None
    presets: list[dict] = field(default_factory=list)


def _schreibe_user_json(user_id: str, *, mail_to: str, telegram_chat_id: str,
                         premium_sms_reply_to: str) -> None:
    """Der EINE Schreibweg fuer ``user.json`` in diesem Fundament (PO-Lage,
    L1-L6, Zweitnutzer -- alle gehen hier durch).

    ``tier: "premium"`` (Issue #2412 S4a / Commit 47cbc102, nach dem Rebase
    auf ``origin/main`` dazugekommen): seit dem SMS-Tageslimit-Gate
    (``src/services/sms_daily_limit.py``) gilt ein Nutzer OHNE ``tier`` als
    ``"free"`` mit SMS-/Premium-SMS-Cap 0 -- jeder Premium-SMS-Versand waere
    sonst blockiert (``"Premium-SMS confirmation blocked: SMS-Tageslimit
    erreicht"``), unabhaengig von Journal/Lernendpunkt/Zielaufloesung. Der
    externe Helfer ``tests/helpers/nutzer_tier.py::nutzer_mit_tier`` passt
    hier NICHT direkt (er schreibt nur ``id``+``tier`` und wuerde
    ``mail_to``/``telegram_chat_id``/``premium_sms_reply_to`` verlieren) --
    das Feld wird deshalb direkt in diesem EINEN Read-Modify-Write-Schreibweg
    ergaenzt, entspricht der realen PO-Lage (Premium-SMS-Nutzer)."""
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": user_id,
        "tier": "premium",
        "mail_to": mail_to,
        "email_verified_at": "2026-01-01T00:00:00Z",
        "telegram_chat_id": telegram_chat_id,
        "premium_sms_reply_to": premium_sms_reply_to,
        "premium_sms_reply_at": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")


def lege_po_lage_nutzer_an(new_user_id: Callable[[], str], *, trip_name: str = "KHW 403",
                            anzahl_vergleiche: int = 2) -> BefehlNutzer:
    """L3: 1 aktiver Trip UND >=1 aktive Ortsvergleiche ohne ``end_date`` --
    die tatsaechliche Lage des PO (Spec "PO-Lage-Fixture")."""
    user_id = new_user_id()
    chat_id = f"chat-{user_id}"
    mail_to = f"{user_id}@henemm.com"
    reply_to = f"+49170{abs(hash(user_id)) % 10_000_000:07d}"
    _schreibe_user_json(
        user_id, mail_to=mail_to, telegram_chat_id=chat_id,
        premium_sms_reply_to=reply_to,
    )
    trip = _trip(user_id, trip_name)
    presets = [
        _preset(user_id, f"Vergleich {i + 1}") for i in range(anzahl_vergleiche)
    ]
    return BefehlNutzer(
        user_id=user_id, mail_to=mail_to, telegram_chat_id=chat_id,
        premium_sms_reply_to=reply_to, trip=trip, presets=presets,
    )


def lege_lage_an(new_user_id: Callable[[], str], lage: str) -> BefehlNutzer:
    """Baut eine der sechs Lagen der Befehls-x-Lagen-Matrix (Spec-Tabelle).

    L1: 0 Trips, 0 aktive Vergleiche
    L2: 1 Trip, 0 aktive Vergleiche
    L3: 1 Trip, >=1 aktive Vergleiche (== PO-Lage)
    L4: 0 Trips, genau 1 aktiver Vergleich
    L5: 0 Trips, >=2 aktive Vergleiche
    L6: >=2 Trips, 0 aktive Vergleiche (pick_active_trip waehlt vorab einen)
    """
    if lage == "L3":
        return lege_po_lage_nutzer_an(new_user_id)

    user_id = new_user_id()
    chat_id = f"chat-{user_id}"
    mail_to = f"{user_id}@henemm.com"
    reply_to = f"+49170{abs(hash(user_id)) % 10_000_000:07d}"
    _schreibe_user_json(
        user_id, mail_to=mail_to, telegram_chat_id=chat_id,
        premium_sms_reply_to=reply_to,
    )
    nutzer = BefehlNutzer(
        user_id=user_id, mail_to=mail_to, telegram_chat_id=chat_id,
        premium_sms_reply_to=reply_to,
    )
    if lage == "L1":
        return nutzer
    if lage == "L2":
        nutzer.trip = _trip(user_id, "Solo-Trip")
        return nutzer
    if lage == "L4":
        nutzer.presets = [_preset(user_id, "Solo-Vergleich")]
        return nutzer
    if lage == "L5":
        nutzer.presets = [_preset(user_id, "Vergleich A"), _preset(user_id, "Vergleich B")]
        return nutzer
    if lage == "L6":
        nutzer.trip = _trip(user_id, "Erster Trip", tag=date.today())
        _trip(user_id, "Zweiter Trip", tag=date.today() + timedelta(days=30))
        return nutzer
    raise ValueError(f"Unbekannte Lage {lage!r} -- erwartet L1..L6.")


# ---------------------------------------------------------------------------
# Eingangs-Treiber je Kanal
# ---------------------------------------------------------------------------

def sende_telegram_text(settings: Settings, nutzer: BefehlNutzer, text: str) -> None:
    """Ein getippter Telegram-Text durch den ECHTEN Webhook-Verarbeitungs-
    pfad (``_process_update``)."""
    from services.inbound_telegram_reader import InboundTelegramReader

    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": nutzer.telegram_chat_id},
            "text": text,
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
        },
    }
    InboundTelegramReader()._process_update(update, settings)


def klicke_telegram_knopf(settings: Settings, nutzer: BefehlNutzer, callback_data: str,
                           *, message_id: int = 555) -> None:
    """Ein Knopf-Klick durch den ECHTEN Callback-Verarbeitungspfad.

    Geht ueber ``_process_update`` (nicht direkt ueber
    ``_process_callback_query``): NUR ``_process_update`` ruft vorab
    ``_ensure_notification_service()`` -- ein direkter Aufruf von
    ``_process_callback_query`` auf einer frischen Reader-Instanz traf sonst
    auf ``self._notification_service is None`` und krachte mit
    ``AttributeError`` (gefunden beim Nachmessen der echten Knopf-Antworten
    fuer ``ERWARTETES_MERKMAL``, PO-Feedback 2026-09-25). Das ist zugleich
    der reale Weg: das Produkt ruft ``_process_callback_query`` nie isoliert
    auf, immer ueber ``_process_update``."""
    from services.inbound_telegram_reader import InboundTelegramReader

    update = {
        "update_id": 1,
        "callback_query": {
            "id": f"cbq-{uuid.uuid4().hex[:8]}",
            "data": callback_data,
            "message": {
                "chat": {"id": nutzer.telegram_chat_id},
                "message_id": message_id,
            },
        },
    }
    InboundTelegramReader()._process_update(update, settings)


class _FakeImap:
    """Double NUR an der IMAP-Transportgrenze (Vorbild
    ``tests/test_inbound_reader_no_default_settings_lookup.py:97-104``)."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw
        self.stored: list[tuple] = []

    def fetch(self, uid, spec):
        return "OK", [(b"1 (RFC822 {n})", self._raw)]

    def store(self, uid, flags, value):
        self.stored.append((uid, flags, value))


def _mime_plain(from_addr: str, subject: str, body: str) -> bytes:
    raw = "\r\n".join([
        f"From: {from_addr}",
        "To: cmd@example.com",
        f"Subject: {subject}",
        f"Authentication-Results: {AR_PASS}",
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=utf-8",
        "",
        body,
    ]).encode("utf-8")
    return raw


def _mime_apple_html_only(from_addr: str, subject: str, befehl: str) -> bytes:
    """``multipart/alternative`` NUR mit ``text/html`` -- die Apple-Mail-
    Antwortstruktur aus B2 (Spec-Abschnitt "E-Mail-Normalisierung")."""
    import quopri

    html = (
        f'<body dir="auto">{befehl}<br id="lineBreakAtBeginningOfSignature">'
        '<div dir="ltr"><div><br></div></div>'
        '<div dir="ltr"><br><blockquote type="cite">Am 25.09.2026 um 06:06 '
        "schrieb Absender:<br><br></blockquote></div></body>"
    )
    qp = quopri.encodestring(html.encode("utf-8")).decode("ascii")
    boundary = "Apple-Mail=_GZ2417"
    raw = (
        f"From: {from_addr}\r\n"
        "To: cmd@example.com\r\n"
        f"Subject: {subject}\r\n"
        f"Authentication-Results: {AR_PASS}\r\n"
        "MIME-Version: 1.0\r\n"
        f'Content-Type: multipart/alternative; boundary="{boundary}"\r\n'
        "\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/html;\r\n"
        "\tcharset=utf-8\r\n"
        "Content-Transfer-Encoding: quoted-printable\r\n"
        "\r\n"
        f"{qp}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    return raw


def _mime_alternative_beide(from_addr: str, subject: str, befehl: str) -> bytes:
    """``multipart/alternative`` mit BEIDEN Teilen -- Regressionsschutz:
    ``text/plain`` bleibt bevorzugt, wenn vorhanden."""
    boundary = "Alt-Mail=_GZ2417"
    html = f"<p>{befehl}</p>"
    raw = (
        f"From: {from_addr}\r\n"
        "To: cmd@example.com\r\n"
        f"Subject: {subject}\r\n"
        f"Authentication-Results: {AR_PASS}\r\n"
        "MIME-Version: 1.0\r\n"
        f'Content-Type: multipart/alternative; boundary="{boundary}"\r\n'
        "\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        f"{befehl}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        f"{html}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    return raw


MAIL_FORMEN: dict[str, Callable[[str, str, str], bytes]] = {
    "plain": _mime_plain,
    "alternative_beide": _mime_alternative_beide,
    "apple_html": _mime_apple_html_only,
}


def sende_email(settings: Settings, nutzer: BefehlNutzer, body: str, *,
                 form: str = "plain", trip_name: str | None = None) -> int:
    """Eine Befehlsmail durch den ECHTEN ``_process_single``-Pfad mit
    Fake-IMAP. Gibt den Rueckgabewert von ``_process_single`` zurueck (1 =
    verarbeitet). ``form`` in ``MAIL_FORMEN`` (``plain``/
    ``alternative_beide``/``apple_html``)."""
    from services.inbound_email_reader import InboundEmailReader

    ziel_name = trip_name or (nutzer.trip.name if nutzer.trip else "")
    subject = f"Re: [{ziel_name}] Etappe"
    bauer = MAIL_FORMEN[form]
    raw = bauer(nutzer.mail_to, subject, body)
    imap = _FakeImap(raw)
    reader = InboundEmailReader()
    return reader._process_single(imap, b"1", settings)


def sende_premium_sms(settings: Settings, recorder: Recorder, nutzer: BefehlNutzer,
                       text: str, *, mit_kartenlink: bool = False) -> int:
    """Eine Garmin-inReach-Nachricht durch den ECHTEN Journal-Eingang
    (``poll_and_process`` -> ``_poll_journal`` -> ``_verarbeite_befehl``,
    Herkunft auf ``"production"`` gepinnt -- s. Moduldoku). Gibt die Anzahl
    ECHT gelernter Rueckadressen zurueck (Vertrag von ``poll_and_process``)."""
    from services.inbound_sms_reader import InboundSmsReader

    recorder.registriere_premium_sms_absender(nutzer.premium_sms_reply_to, nutzer.user_id)
    volltext = text
    if mit_kartenlink:
        volltext = f"{text} inreachlink.com/g-0Ab1Cd2Ef... (47.2692, 11.4041)"
    recorder.journal_eintrag_anhaengen(nutzer.premium_sms_reply_to, volltext)
    reader = InboundSmsReader()
    return reader.poll_and_process(settings)


# ---------------------------------------------------------------------------
# sms_segments -- GSM-7/UCS-2-Segmentzaehlung (Spec-Abschnitt
# "Premium-SMS-Kurzhilfe" + "Segmentrechnung")
# ---------------------------------------------------------------------------

from tests.tdd._gsm7_charset import (  # noqa: E402
    GSM7_EXTENDED_TWO_SEPTET_CHARS,
    _first_non_gsm7_char,
)


def sms_segments(text: str) -> int:
    """Anzahl SMS-Segmente fuer ``text``. GSM-7 (160 Zeichen 1 Segment / 153
    je Segment bei Mehrteil, 2-Septet-Erweiterungszeichen zaehlen doppelt)
    bzw. UCS-2-Fallback (70/67 UTF-16-Codeeinheiten), falls ein Zeichen nicht
    GSM-7-faltbar ist (Regressionsschutz)."""
    if _first_non_gsm7_char(text) is None:
        laenge = sum(2 if ch in GSM7_EXTENDED_TWO_SEPTET_CHARS else 1 for ch in text)
        if laenge <= 160:
            return 1
        return -(-laenge // 153)
    laenge = len(text.encode("utf-16-le")) // 2
    if laenge <= 70:
        return 1
    return -(-laenge // 67)


# ---------------------------------------------------------------------------
# SOLL_MATRIX -- Befehlsklasse x Lage -> erwartetes Ergebnis (Spec-Tabelle,
# "loest #2282 AC-4 ab"). Statisches Domainwissen aus der freigegebenen Spec,
# NICHT aus dem Produktcode ableitbar (die Spec-Tabelle IST die Vorgabe).
# ---------------------------------------------------------------------------

ERGEBNIS_ANTWORT_TRIP = "antwort_trip"
ERGEBNIS_HILFE = "hilfe"
ERGEBNIS_KEIN_KANDIDAT = "kein_kandidat"
ERGEBNIS_KEIN_AKTIVES_ZIEL = "kein_aktives_ziel"
ERGEBNIS_RUECKFRAGE = "rueckfrage"
ERGEBNIS_ANTWORT_VERGLEICH = "antwort_vergleich"

KLASSE_ZIELLOS = "ziellos"
KLASSE_ROUTE_ONLY = "route_only"
KLASSE_METRIK_QUERY = "metrik_query"
KLASSE_BEIDE_KINDS = "beide_kinds"

SOLL_MATRIX: dict[str, dict[str, str]] = {
    KLASSE_ZIELLOS: {
        "L1": ERGEBNIS_HILFE, "L2": ERGEBNIS_HILFE, "L3": ERGEBNIS_HILFE,
        "L4": ERGEBNIS_HILFE, "L5": ERGEBNIS_HILFE, "L6": ERGEBNIS_HILFE,
    },
    KLASSE_ROUTE_ONLY: {
        "L1": ERGEBNIS_KEIN_KANDIDAT, "L2": ERGEBNIS_ANTWORT_TRIP,
        "L3": ERGEBNIS_ANTWORT_TRIP, "L4": ERGEBNIS_KEIN_AKTIVES_ZIEL,
        "L5": ERGEBNIS_KEIN_AKTIVES_ZIEL, "L6": ERGEBNIS_ANTWORT_TRIP,
    },
    KLASSE_METRIK_QUERY: {
        "L1": ERGEBNIS_KEIN_KANDIDAT, "L2": ERGEBNIS_ANTWORT_TRIP,
        "L3": ERGEBNIS_ANTWORT_TRIP, "L4": ERGEBNIS_KEIN_AKTIVES_ZIEL,
        "L5": ERGEBNIS_KEIN_AKTIVES_ZIEL, "L6": ERGEBNIS_ANTWORT_TRIP,
    },
    KLASSE_BEIDE_KINDS: {
        "L1": ERGEBNIS_KEIN_KANDIDAT, "L2": ERGEBNIS_ANTWORT_TRIP,
        "L3": ERGEBNIS_RUECKFRAGE, "L4": ERGEBNIS_ANTWORT_VERGLEICH,
        "L5": ERGEBNIS_RUECKFRAGE, "L6": ERGEBNIS_ANTWORT_TRIP,
    },
}

#: Woerter, die der Reader VOR jeder Zielauflösung beantwortet (Spec
#: Implementation Details Punkt 1/2). ``hilfe`` steht in ``_COMMAND_SPECS``
#: mit kind ``_BEIDE_KINDS`` (das steuert NUR die Vergleichs-/Trip-Hilfe-
#: Variante im Prozessor) -- die READER-seitige Klassifizierung ist eine
#: andere Achse und muss ``hilfe`` deshalb VORAB herausnehmen, sonst
#: landete es faelschlich in der `_BEIDE_KINDS`-Rueckfrage-Zeile.
ZIELLOSE_WOERTER = frozenset({"hilfe"})
ZIELLOSE_CALLBACKS = frozenset({"act_help", "act_columns"})


def _route_only_reader_woerter() -> frozenset[str]:
    """Reader-seitige Schluesselworte der ``_ROUTE_ONLY``-Zeile, UEBER
    ``_BARE_KEYWORD_MAP`` auf ihre internen Schluessel abgebildet (z.B.
    ``gewitter`` -> ``heute_gewitter``, ``jetzt``/``now`` -> ``now``)."""
    woerter = {w for w, _a, _b, k in _COMMAND_SPECS if k == _ROUTE_ONLY}
    return frozenset(_BARE_KEYWORD_MAP.get(w, w) for w in woerter) | {"now"}


def _beide_kinds_reader_woerter() -> frozenset[str]:
    woerter = {w for w, _a, _b, k in _COMMAND_SPECS if k == _BEIDE_KINDS}
    return frozenset(_BARE_KEYWORD_MAP.get(w, w) for w in woerter) - ZIELLOSE_WOERTER


def klassifiziere_wort(reader_schluessel: str) -> str:
    """Ordnet ein READER-Schluesselwort (nach ``_BARE_KEYWORD_MAP``-
    Aufloesung, also z.B. ``"now"``, ``"heute_gewitter"``, ``"pause"``) einer
    Befehlsklasse der Matrix zu."""
    if reader_schluessel in ZIELLOSE_WOERTER:
        return KLASSE_ZIELLOS
    if reader_schluessel in _route_only_reader_woerter():
        return KLASSE_ROUTE_ONLY
    if reader_schluessel in _beide_kinds_reader_woerter():
        return KLASSE_BEIDE_KINDS
    if reader_schluessel in _QUERY_KEYS:
        return KLASSE_METRIK_QUERY
    from app.metric_catalog import metric_command_words

    if reader_schluessel in metric_command_words():
        return KLASSE_METRIK_QUERY
    raise AssertionError(
        f"Kein Klassen-Eintrag fuer Reader-Schluessel {reader_schluessel!r} -- "
        "SOLL_MATRIX/klassifiziere_wort ergaenzen (Vollstaendigkeits-Pflicht)."
    )


def klassifiziere_callback(callback_data: str) -> str:
    """Wie ``klassifiziere_wort``, aber fuer ``_CALLBACK_QUERY_MAP``-Werte."""
    if callback_data in ZIELLOSE_CALLBACKS:
        return KLASSE_ZIELLOS
    if callback_data == "act_pause":
        return KLASSE_BEIDE_KINDS
    if callback_data in ("act_skip",):
        return KLASSE_ROUTE_ONLY
    if callback_data in ("act_overview", "tl_today", "tl_tomorrow", "glance", "heute", "morgen", "now"):
        return KLASSE_METRIK_QUERY
    raise AssertionError(
        f"Kein Klassen-Eintrag fuer Callback {callback_data!r} -- "
        "klassifiziere_callback ergaenzen."
    )


def alle_callback_faelle() -> list[str]:
    """AC-8/AC-9-Parametrisierung: alle ``_CALLBACK_QUERY_MAP``-Schluessel --
    abgeleitet, keine handgetippte Liste."""
    return sorted(_CALLBACK_QUERY_MAP)


def angebotene_route_only_und_metrik_faelle() -> list[str]:
    """AC-1-Parametrisierung: alle ``_ROUTE_ONLY``-Reader-Schluessel UNION
    alle Query-Keys UNION alle getippten Metrik-WORTE (nicht die Metrik-ID --
    genau das Wort, das der Reader tatsaechlich ueber die Leitung bekommt und
    per ``metric_command_words()`` aufloest). Abgeleitet, keine
    handgetippte Liste."""
    from app.metric_catalog import metric_command_words

    faelle = sorted(_route_only_reader_woerter())
    faelle += sorted(_QUERY_KEYS)
    faelle += sorted(metric_command_words())
    return faelle


def tippbare_route_only_und_metrik_woerter() -> list[tuple[str, str]]:
    """Wie ``angebotene_route_only_und_metrik_faelle()``, aber mit ECHTEN
    Nutzereingaben statt interner Reader-Schluessel (PO-Feedback
    2026-09-25): ``angebotene_route_only_und_metrik_faelle()`` liefert u.a.
    ``"abbruch"``/``"heute_gewitter"`` -- Woerter, die kein Nutzer tippt (der
    Reader bildet ``stop``/``gewitter`` erst ueber ``_BARE_KEYWORD_MAP``
    darauf ab). Text-getriebene Tests (Telegram-Freitext, Premium-SMS)
    brauchen das getippte Wort, nicht den internen Schluessel.

    Gibt ``(getipptes_wort, klasse)``-Paare zurueck -- die Klasse ist bereits
    mitgeliefert, weil ``klassifiziere_wort()`` NUR interne Reader-Schluessel
    versteht und ein getipptes Wort wie ``"gewitter"`` dort fehlschlagen
    wuerde (es klassifiziert erst NACH der ``_BARE_KEYWORD_MAP``-Aufloesung).

    Deckt dieselbe Menge ab wie ``angebotene_route_only_und_metrik_faelle()``
    (``_ROUTE_ONLY``-Woerter aus ``_COMMAND_SPECS`` UNION Query-Keys UNION
    Metrik-Worte aus ``metric_command_words()``) -- abgeleitet, keine
    handgetippte Liste. ``_QUERY_KEYS`` und die Metrik-Worte sind bereits
    direkt eingetippte Formen (unveraendert uebernommen); nur die
    ``_ROUTE_ONLY``-Zeile wird hier aus den ROHEN ``_COMMAND_SPECS``-Woertern
    gebildet statt aus deren interner Abbildung.
    """
    from app.metric_catalog import metric_command_words

    faelle: list[tuple[str, str]] = [
        (wort, KLASSE_ROUTE_ONLY) for wort, _arg, _beschreibung, kind in _COMMAND_SPECS
        if kind == _ROUTE_ONLY
    ]
    faelle += [(wort, KLASSE_METRIK_QUERY) for wort in sorted(_QUERY_KEYS)]
    faelle += [(wort, KLASSE_METRIK_QUERY) for wort in sorted(metric_command_words())]
    return faelle


# ---------------------------------------------------------------------------
# ERWARTETES_MERKMAL -- Inhaltsmerkmal je Befehl (Spec-Abschnitt
# "Inhaltsmerkmal je Befehl")
# ---------------------------------------------------------------------------

def _stufenname(trip: Trip | None, index: int) -> str:
    if trip is None or len(trip.stages) <= index:
        raise AssertionError("Fixture-Trip hat nicht die erwarteten 3 Etappen.")
    return trip.stages[index].name


#: Knopf-Faelle, die INHALTLICH dieselbe Antwort ausloesen wie ein
#: getipptes Wort (nachgemessen am echten Telegram-Eingang in Lage L2, PO-
#: Feedback 2026-09-25 -- ``klicke_telegram_knopf`` mit jedem
#: ``_CALLBACK_QUERY_MAP``-Schluessel gegen den tatsaechlich gesendeten Text
#: verglichen). ``act_columns`` hat KEIN Wort-Pendant -- eigene Regel unten.
_CALLBACK_ALIAS_FUER_MERKMAL = {
    "act_help": "hilfe",
    "act_overview": "glance",
    "act_pause": "pause",
    "act_skip": "skip",
    "tl_today": "timeline_heute",
    "tl_tomorrow": "timeline_morgen",
}


def _premium_sms_etappen_kuerzel(trip: Trip, index: int) -> str:
    """``"E{n}"`` wie es der echte Premium-SMS-Versandpfad erzeugt -- die
    1-basierte CHRONOLOGISCHE Position von ``trip.stages[index]`` (nach
    Datum sortiert), nicht die Listenposition. Beleg (Nachmessung
    2026-09-25): ``Trip.numbered_stage_label()`` (``app/trip.py:294-310``)
    baut ``"Etappe {position}: {rest}"`` aus genau dieser Position und wird
    als ``stage_name`` an ``SMSTripFormatter.format_sms()`` durchgereicht
    (``trip_report_scheduler.py:1469``); ``_sms_stage_prefix()``
    (``output/renderers/sms_trip.py:46-54``) liest daraus per Regex
    ``^Etappe\\s+(\\d+)`` die Nummer heraus und baut ``"E{n}"``."""
    ordered = sorted(trip.stages, key=lambda s: s.date)
    ziel_stage = trip.stages[index]
    position = ordered.index(ziel_stage) + 1
    return f"E{position}"


def _premium_sms_merkmal_fuer(fall: str, *, nutzer: BefehlNutzer):
    """Premium-SMS-eigene Merkmal-Ausnahmen (PO-Feedback 2026-09-25,
    Fundament-Korrektur 3).

    ``PremiumSmsOutput.send(subject, body)`` IGNORIERT ``subject``
    vollstaendig (``output/channels/seven_io_base.py::send`` -- "``subject``
    wird ignoriert -- eine SMS hat kein Betreff-Feld"). Jedes Standard-
    Merkmal, das nur im Telegram-/E-Mail-Betreff lebte
    (``f"[{trip.name}] ..."``), FEHLT deshalb im tatsaechlich gesendeten
    Premium-SMS-BODY komplett -- nachgemessen fuer alle 64 Faelle aus
    ``tippbare_route_only_und_metrik_woerter()`` (9 ``_ROUTE_ONLY``-Woerter
    minus die drei, die schon body-eigene Signale tragen -- ``gewitter``/
    ``status``/``skip``/``stop`` funktionieren unveraendert --, plus alle 55
    Metrik-Worte) UND fuer ``pause``/``weiter`` (``_BEIDE_KINDS``, ausserhalb
    von ``tippbare_route_only_und_metrik_woerter()``, aber von den
    E2E-Testdateien ebenfalls per Premium-SMS gepruefte Befehlsworte,
    Nachmessung 2026-09-25): ``pause`` OHNE Dauer nennt das Ziel NUR im
    Betreff ("[Solo-Trip] PAUSE: Dauer fehlt") und braucht deshalb eine
    Ausnahme; ``weiter``/``skip``/``stop``/``status`` nennen das Ziel bereits
    woertlich im Body und brauchen KEINE.

    Gibt ``None`` zurueck, wenn die Standard-Ableitung schon body-taugliches
    Merkmal liefert (kein Sonderfall noetig) -- der Aufrufer faellt dann auf
    die generische Logik unten zurueck.

    BEOBACHTUNGEN aus der Nachmessung (kein Fix-Auftrag dieses Fundaments,
    an Team-Lead gemeldet):

    - ``jetzt``/``now``: der Nowcast-Body traegt WEDER Trip- noch
      Etappenbezug (``_show_now`` schreibt den Namen nur in
      ``confirmation_subject``, nie in den Body) -- das Merkmal
      (Radar-Quellenkennung) kann NICHT zwischen einer richtig und einer
      FALSCH adressierten Antwort unterscheiden.
    - ``strecke``: der Fixture-Trip hat keine echte Kilometrierung/kein
      GPX-Hoehenprofil -- die Antwort ist deshalb IMMER der
      "nicht verfuegbar"-Fallback, auf jedem Kanal. Das eigentliche
      Inhaltsmerkmal ("Regen-Ereignisflaechen entlang der Reststrecke") ist
      mit dieser Fixture nicht pruefbar.
    - Metrik-Worte (BEHOBEN, Fundament-Korrektur 4, Team-Lead 2026-09-25):
      ``_handle_metric_drilldown()`` liest ueber
      ``WeatherExtractor(...).drilldown()`` einen vorab gespeicherten
      Snapshot -- ohne ihn lieferte JEDES Metrik-Kuerzel strukturell
      ``"<Kuerzel> no data"``, was das ``sms_code``-Merkmal vakuum-gruen
      machte (traf auch auf den "no data"-Body zu). ``_trip()`` seedet seit
      dieser Korrektur ueber ``_speichere_snapshot``/
      ``STANDARD_STUNDENWERT`` einen echten Snapshot mit Werten fuer JEDE
      selectable Katalog-Groesse ausser ``uv_index`` (bewusst leer fuer
      AC-33) -- das Merkmal bleibt ``sms_code``/``col_label``, ist aber
      jetzt kein vakuumer Treffer mehr: ein fehlerhaft aufgeloester oder
      nicht gelieferter Wert zeigt sich als ``"<Kuerzel> no data"``, was das
      Merkmal WEITERHIN erfuellen wuerde -- Testdateien, die "kein
      no data" pruefen wollen, brauchen dafuer eine EIGENE, zusaetzliche
      Zusicherung (``FEHLERTEXTE``/eigener String-Check), dieses Fundament
      garantiert nur, dass ein echter Snapshot vorliegt.
    """
    if fall == "heute":
        return _premium_sms_etappen_kuerzel(nutzer.trip, 1)
    if fall == "morgen":
        return _premium_sms_etappen_kuerzel(nutzer.trip, 2)
    if fall in ("now", "jetzt"):
        return "ARPAE ICON-2I"
    if fall == "ruhetag":
        # Body nennt die verschobene FOLGE-Etappe beim Namen (Nachmessung:
        # "Verschobene Etappen:\n  Etappe Morgen: ... -> ...").
        return _stufenname(nutzer.trip, 2)
    if fall == "strecke":
        return "Kilometrierung"
    if fall == "pause":
        # Nachmessung (Team-Lead-Anfrage 2026-09-25): "pause" OHNE Dauer
        # liefert Body "Bitte Dauer angeben, z.B. PAUSE 2d oder PAUSE 12h.
        # Format: N d (Tage) oder N h (Stunden)." -- der Trip-Name steht
        # NUR im (bei Premium-SMS verworfenen) Betreff
        # "[Solo-Trip] PAUSE: Dauer fehlt".
        return "Dauer angeben"
    # "weiter"/"skip"/"stop"/"status" brauchen KEINE Ausnahme (bestaetigt bei
    # derselben Nachmessung): ihre Bodies nennen das Ziel bereits woertlich
    # ("...fuer 'Solo-Trip'..." bzw. die Etappennamen) -- die generische
    # Logik unten (return None) greift unveraendert.

    from app.metric_catalog import metric_command_words

    metric_id = metric_command_words().get(fall)
    if metric_id is not None:
        metric = get_metric(metric_id)
        return metric.sms_code or metric.col_label

    return None


def merkmal_fuer(fall: str, *, nutzer: BefehlNutzer, ziel_name: str | None = None,
                  kanal: str | None = None):
    """Woran die RICHTIGE Antwort fuer ``fall`` erkennbar ist, gemessen an
    den tatsaechlichen Fixture-Daten von ``nutzer`` (nicht am Produktcode).

    ``fall`` ist entweder ein Reader-Schluesselwort (z.B. ``"heute"``,
    ``"now"``) oder ein ``_CALLBACK_QUERY_MAP``-Schluessel (z.B.
    ``"act_help"``, ``"tl_today"``) -- beide Namensraeume ueberschneiden sich
    nicht mit Ausnahme der bewusst identischen Faelle (``"glance"``,
    ``"heute"``, ``"morgen"``, ``"now"`` sind sowohl Callback- als auch
    Reader-Schluessel und liefern dieselbe Antwort, nachgemessen).

    ``kanal`` (optional, additiv -- PO-Feedback 2026-09-25, Fundament-
    Korrektur 3): ``kanal="premium_sms"`` schaltet die Premium-SMS-eigenen
    Ausnahmen aus :func:`_premium_sms_merkmal_fuer` VOR die generische Logik
    -- ``PremiumSmsOutput.send()`` ignoriert ``subject`` komplett, jedes
    Merkmal, das nur im Betreff lebte, muesste sonst im Body scheitern.
    Bestehende Aufrufe OHNE ``kanal`` (Telegram/E-Mail, wo der Betreff Teil
    des zusammengesetzten Texts ist) bleiben unveraendert.

    Gibt entweder einen einzelnen erwarteten Teilstring oder ein Tupel
    mehrerer Pflicht-Teilstrings zurueck (z.B. ``hilfe`` -> alle 12
    Befehlswoerter; ``glance``/``timeline_*`` -> Einheit-Paar, s.u.). Wirft
    ``AssertionError`` bei einem unbekannten Fall -- das ist gewollt: ein
    neuer Fall OHNE Eintrag darf nicht mit "kam irgendeine Antwort"
    durchrutschen.

    WICHTIG (PO-Feedback 2026-09-25): fuer ``glance``/``timeline_*``/
    ``heute_gewitter`` reicht der Trip-/Vergleichsname NICHT als Merkmal --
    die echte Antwort traegt zwar (ueberraschend) den Namen im doppelt
    eingeklammerten Betreff `"[[<Ziel>] Glance]"`, das ist aber ein
    zu schwaches Signal (jede Antwort jedes Befehls traegt den Namen dort,
    ein Merkmal muesste also nichts Falsches ausschliessen). Diese drei
    Faelle pruefen deshalb auf ECHTE, aus dem Katalog abgeleitete
    Wettergroessen-Einheiten (``°C``/``km/h``) bzw. die Katalog-Beschriftung
    der Gewitter-Groesse -- Belege im Docstring des Moduls, Abschnitt
    "Nachgemessene Telegram-Antworten".
    """
    fall = _CALLBACK_ALIAS_FUER_MERKMAL.get(fall, fall)
    ziel = ziel_name or (nutzer.trip.name if nutzer.trip else "")

    if kanal == "premium_sms":
        premium_merkmal = _premium_sms_merkmal_fuer(fall, nutzer=nutzer)
        if premium_merkmal is not None:
            return premium_merkmal

    if fall == "hilfe":
        return tuple(w.upper() for w, _a, _b, _k in _COMMAND_SPECS)
    if fall == "heute":
        return _stufenname(nutzer.trip, 1)
    if fall == "morgen":
        return _stufenname(nutzer.trip, 2)
    if fall in ("now", "jetzt"):
        return ziel
    if fall in ("heute_gewitter", "gewitter"):
        return get_metric("thunder").label_de
    if fall == "strecke":
        return ziel
    if fall == "ruhetag":
        return ziel
    if fall == "status":
        return _stufenname(nutzer.trip, 1)
    if fall in ("skip", "stop", "abbruch"):
        return ziel
    if fall in ("pause", "weiter"):
        return ziel
    if fall == "glance":
        return (get_metric("temperature").unit, get_metric("wind").unit)
    if fall in ("timeline_heute", "timeline_morgen"):
        return (get_metric("temperature").unit, get_metric("wind").unit)
    if fall == "act_columns":
        # Kein Wort-Pendant, kein reply_markup (nachgemessen: der Klick
        # liefert reinen Hinweistext auf den Web-Editor, KEIN Inline-
        # Keyboard) -- reales Zitat aus trip_command_processor.py
        # ``_show_columns_info``.
        return "Spalten-Konfiguration"
    if fall == KEIN_KANDIDAT_TEXT:
        return KEIN_KANDIDAT_TEXT

    from app.metric_catalog import metric_command_words

    metric_id = metric_command_words().get(fall)
    if metric_id is not None:
        return get_metric(metric_id).label_de

    raise AssertionError(
        f"Kein ERWARTETES_MERKMAL fuer Fall {fall!r} hinterlegt -- "
        "merkmal_fuer() in tests/tdd/_befehl_e2e_fixtures.py ergaenzen "
        "(Vollstaendigkeits-Pflicht der Spec)."
    )


# ---------------------------------------------------------------------------
# Fehlertext-Konstanten, gegen die "frei von Fehlertexten" geprueft wird
# ---------------------------------------------------------------------------

FEHLERTEXTE = (
    "Mehrdeutig",
    "Unbekannter Befehl",
    KEIN_KANDIDAT_TEXT,
)
