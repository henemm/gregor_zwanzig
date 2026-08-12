"""TDD RED — Issue #1752 (Scheibe B zu #1745): Regen-/Radar-Alarme folgen dem
Alarm-Kanal-Satz statt den Briefing-Flags.

SPEC: docs/specs/modules/fix_1752_radar_folgt_alarm_kanaelen.md (AC-1 bis AC-7)

Heute loest ``check_radar_alerts()`` seine Kanaele ueber
``_radar_effective_channels()`` (``trip_alert.py:826``) auf — eine zweite,
leicht abweichende Ableitung, die AUSSCHLIESSLICH ``trip.report_config``
liest und ``trip.alert_channels``/``trip.alert_rules`` nie. Nach dieser
Scheibe nutzen alle drei Aufrufstellen (``:987``, ``:1061``, ``:1109``)
dieselbe Funktion wie Gewitter-, Aenderungs- und amtliche Alarme:
``_effective_alert_channels()``.

PRUEFORT = WIRKORT (CLAUDE.md): geprueft wird NICHT der Rueckgabewert einer
internen Funktion, sondern die persistierte Nebenwirkung — die
Kanal-Aufschluesselung ``channels_not_sent`` im echten ``alert_log.json``.
Deren Rangfolge (``alert_log.py:113-137``) trennt genau die beiden Fragen,
um die es hier geht:

* ``channel_disabled``  — der Kanal wurde gar nicht erst AUFGELOEST,
* ``delivery_failed``   — der Kanal WAR aufgeloest, kam aber nicht an,
* ``below_channel_threshold`` — aufgeloest, aber unter der Dringlichkeits-
  Schwelle.

Damit laesst sich „wurde der Kanal korrekt aufgeloest?" von „wurde er
zugestellt?" trennen, ohne echten Versand und ohne Transport-Attrappen.

TESTPOLITIK (CLAUDE.md „Test-Politik: Zwei Schichten", Kern-Schicht):
mock-frei — echte Trips, echter ``TripAlertService``, echtes
``alert_log.json``/``throttle_state.json``. Die einzige ``monkeypatch``-Naht
ist ``app.loader.load_all_trips`` (Trip-Einspeisung, s.u.), kein Test-Double
eines Prueflings.

WARUM KEIN DISK-RUNDLAUF: ``tests.helpers.nowcast_gate_fixtures.save_trip()``
serialisiert ``alert_channels``/``alert_rules``/``alert_channel_thresholds``
NICHT (nachgemessen, ``nowcast_gate_fixtures.py:405-434`` schreibt nur id,
name, Sperrzeit-/Ruhezeit-Felder, stages und report_config). Ein Rundlauf
ueber Platte verloere also ausgerechnet die drei Felder, um die es in dieser
Scheibe geht — der Trip wird deshalb direkt eingespeist.

WARUM ``settings_no_channel_reachable()``: bis #1701 stand in
``check_radar_alerts()`` ein globaler Bereitschafts-Guard, der einen Trip mit
ausschliesslich einem neuen Kanal verworfen haette, BEVOR ueberhaupt ein
Kanal-Set aufgeloest wurde — und alle Bestandstests hatten zufaellig einen
erreichbaren Zweitkanal daneben, der den Guard passierbar machte (Vorbild
``tests/unit/test_alert_channel_premium_sms.py:298-376``, „Schritt 0"). Kein
Kanal ist hier je „mit-erreichbar"; ob ein Protokoll-Eintrag entsteht, haengt
ausschliesslich an der Kanal-AUFLOESUNG.

AUSNAHME AC-5: dort ist ``settings_email_only()`` noetig — mit unerreichbaren
Kanaelen waere der Test schon heute gruen und wuerde die Nicht-Umsetzung
feiern statt sie zu messen (Begruendung im Testdocstring).

Pfadregel #1409: alle Zugriffe laufen ueber ``get_data_dir()`` (pytest-
isolierte Datenwurzel, #1133) bzw. die Helfer daneben — kein fester
Hauptrepo-Pfad.
"""
from __future__ import annotations

import uuid

from app.models import (
    AlertMetric,
    AlertRule,
    AlertRuleKind,
    AlertSeverity,
    TripReportConfig,
)
from services.alert_log import (
    REASON_BELOW_THRESHOLD,
    REASON_CHANNEL_DISABLED,
    REASON_DELIVERY_FAILED,
    REASON_NOWCAST,
    REASON_QUIET_HOURS,
)

from tests.helpers.alert_log_fixtures import reason_for_channel
from tests.helpers.nowcast_gate_fixtures import (
    SCOPE_TRIP_RADAR,
    CountingFrameSource,
    clean_uid,
    entries_for,
    fresh_uid,
    make_trip,
    quiet_window_elsewhere,
    quiet_window_now,
    read_log,
    read_throttle_state,
    reset_radar_cache,
    settings_email_only,
    settings_no_channel_reachable,
    suppression_reasons,
    trip_alert_service,
    write_user_tier,
)


# ───────────────────────────── Bausteine ────────────────────────────────────


def _trip_id(name: str) -> str:
    return f"trip-1752-{name}-{uuid.uuid4().hex[:6]}"


def _radar_trip(
    trip_id: str,
    *,
    send_email: bool = False,
    send_telegram: bool = False,
    send_sms: bool = False,
    alert_channels: dict | None = None,
    thresholds: dict | None = None,
    rules: list | None = None,
    quiet: bool = False,
):
    """Trip mit heute ganztaegig aktiver Etappe (Segment-Auswahl und
    Horizont-Guard greifen daher nicht) plus den drei Alarme-Reiter-Feldern.

    ``make_trip()`` braucht dafuer KEINE Erweiterung: ``alert_channels``,
    ``alert_channel_thresholds`` und ``alert_rules`` sind normale, nach der
    Konstruktion beschreibbare ``Trip``-Felder (``app/trip.py:192,214,219``);
    dasselbe Muster nutzt ``test_alert_channel_premium_sms.py::_base_trip``.
    """
    quiet_from, quiet_to = quiet_window_now() if quiet else quiet_window_elsewhere()
    trip = make_trip(trip_id, quiet_from=quiet_from, quiet_to=quiet_to)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=send_email, send_telegram=send_telegram,
        send_sms=send_sms, send_premium_sms=False,
    )
    if alert_channels is not None:
        trip.alert_channels = alert_channels
    if thresholds is not None:
        trip.alert_channel_thresholds = thresholds
    if rules is not None:
        trip.alert_rules = list(rules)
    return trip


def _sms_only_rule() -> AlertRule:
    """Aktive Alarm-Regel mit eigenem Kanal-Override (#638-Semantik)."""
    return AlertRule(
        id="rule-1752-sms", kind=AlertRuleKind.DELTA, metric=AlertMetric.WIND_GUST,
        threshold=20.0, severity=AlertSeverity.WARNING, enabled=True,
        unit="km/h", channels=["sms"],
    )


def _run_radar(monkeypatch, uid, trips, settings, mail_sink=None) -> int:
    """Echter ``check_radar_alerts()``-Lauf mit ausloesendem Nowcast.

    ``CountingFrameSource(onset_minutes=8)`` liefert leichten, NICHT
    konvektiven Regen (0.6 mm/h) in 8 Minuten — Dringlichkeit ``LOW``
    (``alert_urgency.urgency_from_radar``), Onset innerhalb der 20-Minuten-
    Grenze von ``radar_alert_due()``.
    """
    import app.loader as loader

    monkeypatch.setattr(loader, "load_all_trips", lambda **kw: list(trips))
    reset_radar_cache()
    return trip_alert_service(
        uid, settings, CountingFrameSource(onset_minutes=8),
        mail_sink if mail_sink is not None else (lambda subject, body: None),
    ).check_radar_alerts()


def _single_entry(uid: str, trip_id: str) -> dict:
    """Der EINE Protokoll-Eintrag dieses Trips, egal in welcher Liste.

    Welche Liste (``entries`` vs. ``not_delivered``) entscheidet
    ``append_entry()`` selbst anhand der Erreichbarkeit (D4, #1459) — das ist
    hier nicht die gepruefte Zusicherung, geprueft wird die
    Kanal-Aufschluesselung.
    """
    treffer = (
        entries_for(uid, trip_id, bucket="entries")
        + entries_for(uid, trip_id, bucket="not_delivered")
    )
    assert len(treffer) == 1, (
        f"Erwartet GENAU EINEN Protokoll-Eintrag fuer {trip_id!r}, gefunden "
        f"{len(treffer)}. Vollstaendiges Protokoll: {read_log(uid)!r}"
    )
    return treffer[0]


def _aufgeloeste_kanaele(entry: dict) -> set[str]:
    """Kanaele, die die AUFLOESUNG als aktiv bestimmt hat.

    Alles ausser ``channel_disabled``: ein Kanal, der zugestellt wurde, unter
    der Schwelle blieb oder technisch scheiterte, war Teil des effektiven
    Kanal-Satzes. Nur ``channel_disabled`` heisst „gar nicht aufgeloest".
    """
    aktiv = set(entry.get("channels_sent") or [])
    for item in entry.get("channels_not_sent") or []:
        if isinstance(item, dict) and item.get("reason") != REASON_CHANNEL_DISABLED:
            aktiv.add(item.get("channel"))
    return aktiv


def _kanaele_des_unterdrueckungs_eintrags(entry: dict) -> set[str]:
    """``append_suppressed_entry()`` listet GENAU die effektiven Kanaele
    (``alert_log.py:322-325``) — jeder mit dem Gate-Grund."""
    return {
        item.get("channel")
        for item in entry.get("channels_not_sent") or []
        if isinstance(item, dict)
    }


# ═══════════════════════════════ AC-1 ═══════════════════════════════════════


def test_radar_alert_channels_override_report_config_when_alert_channels_set(monkeypatch):
    """AC-1: Given im Alarme-Reiter ist Telegram bewusst AUS und SMS AN,
    waehrend im Trip-Briefing Telegram AN ist / When ein Regen-Alarm
    ausgeloest wird / Then richtet sich der Regen-Alarm nach der
    Alarme-Reiter-Einstellung: SMS zaehlt als aufgeloester Kanal
    (``delivery_failed`` — war konfiguriert, kam technisch nicht an),
    Telegram als abgeschalteter (``channel_disabled``).

    ROT-Grund (gemessen, ``trip_alert.py:826-856`` + ``:1061``):
    ``_radar_effective_channels()`` liest ausschliesslich ``report_config``
    UND filtert dabei selbst auf technische Erreichbarkeit. Mit
    ``settings_no_channel_reachable()`` ist das Ergebnis LEER, der Lauf bricht
    an ``:1061`` wortlos mit ``continue`` ab — es entsteht ueberhaupt kein
    Protokoll-Eintrag. ``trip.alert_channels`` wird nie gelesen.

    Mutation (Spec AC-1): Radar liest weiterhin (auch nur teilweise)
    ``report_config`` statt ausschliesslich der aus ``alert_channels``
    abgeleiteten Menge — Telegram erschiene dann mit ``delivery_failed``
    (= „war konfiguriert") statt ``channel_disabled`` (= „war ausgeschaltet").
    """
    uid = fresh_uid("ac1")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")  # sms_allowed() -> True (Falle 2)
        trip_id = _trip_id("ac1")
        trip = _radar_trip(
            trip_id,
            send_email=False, send_telegram=True,          # Briefing: Telegram AN
            alert_channels={"email": False, "telegram": False, "sms": True},
        )

        _run_radar(monkeypatch, uid, [trip], settings_no_channel_reachable())

        entry = _single_entry(uid, trip_id)
        assert reason_for_channel(entry, "sms") == REASON_DELIVERY_FAILED, (
            "AC-1: SMS ist im Alarme-Reiter AN und muss deshalb als "
            "aufgeloester (wenn auch unzustellbarer) Kanal protokolliert "
            f"werden, erhalten: {reason_for_channel(entry, 'sms')!r} "
            f"(Eintrag: {entry!r})"
        )
        assert reason_for_channel(entry, "telegram") == REASON_CHANNEL_DISABLED, (
            "AC-1: Telegram ist im Alarme-Reiter AUS — der Briefing-Haken darf "
            "ihn nicht zurueckholen, erhalten: "
            f"{reason_for_channel(entry, 'telegram')!r} (Eintrag: {entry!r})"
        )
    finally:
        clean_uid(uid)


# ═══════════════════════════════ AC-2 ═══════════════════════════════════════


def test_radar_alert_channels_fall_back_to_briefing_when_alert_channels_unset(monkeypatch):
    """AC-2: Given ein Bestandstrip hat NIE eine eigene Kanal-Auswahl
    gespeichert (``alert_channels is None``) und im Trip-Briefing ist Telegram
    aktiv / When ein Regen-Alarm ausgeloest wird / Then uebernimmt der
    Regen-Alarm die Briefing-Kanaele als Ersatzwert — Telegram bleibt ein
    aufgeloester Kanal, fuer diesen Trip aendert sich nichts.

    ROT-Grund (gemessen, ``trip_alert.py:840`` + ``:1061``): die alte
    Ableitung verlangt ZUSAETZLICH ``self._settings.can_send_telegram()``.
    Mit ``settings_no_channel_reachable()`` faellt Telegram dort heraus, das
    Kanal-Set ist leer und der Lauf bricht an ``:1061`` ohne Protokoll-Eintrag
    ab. Die Zielfunktion ``_effective_alert_channels()`` trennt Auflösung und
    Erreichbarkeit sauber und liefert ``{'telegram'}``.

    Gegenprobe zu AC-1 (Fallback statt Override).

    Mutation (Spec AC-2): der Fallback bei ``alert_channels is None`` bricht
    (z.B. weil der neue Code faelschlich ein leeres Dict statt der echten
    Fallback-Kette annimmt) — Telegram erschiene trotz aktivem Briefing-Flag
    als ``channel_disabled``.
    """
    uid = fresh_uid("ac2")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")
        trip_id = _trip_id("ac2")
        trip = _radar_trip(trip_id, send_email=False, send_telegram=True)
        assert trip.alert_channels is None, (
            "Voraussetzung: dieser Bestandstrip hat KEINE eigene Kanal-Auswahl"
        )

        _run_radar(monkeypatch, uid, [trip], settings_no_channel_reachable())

        entry = _single_entry(uid, trip_id)
        assert reason_for_channel(entry, "telegram") == REASON_DELIVERY_FAILED, (
            "AC-2: ohne eigene Alarme-Reiter-Auswahl muss der Briefing-Kanal "
            "Telegram als aufgeloest gelten, erhalten: "
            f"{reason_for_channel(entry, 'telegram')!r} (Eintrag: {entry!r})"
        )
        assert reason_for_channel(entry, "email") == REASON_CHANNEL_DISABLED, (
            "AC-2: E-Mail ist im Briefing AUS und darf nicht mit-vererbt "
            f"werden, erhalten: {reason_for_channel(entry, 'email')!r}"
        )
    finally:
        clean_uid(uid)


# ═══════════════════════════════ AC-3 ═══════════════════════════════════════


def test_radar_alert_below_threshold_channel_uses_shared_channel_set(monkeypatch):
    """AC-3: Given im Alarme-Reiter ist SMS aktiviert und traegt die
    Dringlichkeits-Schwelle „hoch" / When ein Regen-Alarm mit NIEDRIGER
    Dringlichkeit (leichter, nicht-konvektiver Regen) ausgeloest wird / Then
    erscheint SMS im Protokoll als „unter der eingestellten Schwelle"
    (``below_channel_threshold``) — nicht als „ausgeschaltet" und nicht als
    „technisch fehlgeschlagen". Die Schwelle wirkt weiterhin, jetzt aber auf
    dem geteilten Kanal-Satz.

    ROT-Grund (gemessen): ``split_by_threshold()`` (``trip_alert.py:1123``)
    bekommt heute das Ergebnis von ``_radar_effective_channels()``, das
    ``alert_channels`` nicht kennt und mit unerreichbaren Kanaelen leer ist —
    der Lauf endet an ``:1061``, es gibt keinen Eintrag und damit auch keine
    Schwellen-Aussage.

    Mutation (Spec AC-3): die Schwelle wird weiterhin auf dem alten,
    Briefing-basierten Kanal-Set angewendet — SMS taucht dann gar nicht als
    „aktiv, aber unter Schwelle" auf, sondern als ``channel_disabled``.
    """
    uid = fresh_uid("ac3")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")
        trip_id = _trip_id("ac3")
        trip = _radar_trip(
            trip_id,
            send_email=True, send_telegram=True,   # Briefing bewusst abweichend
            alert_channels={"email": False, "telegram": False, "sms": True},
            thresholds={"sms": "HIGH"},
        )

        _run_radar(monkeypatch, uid, [trip], settings_no_channel_reachable())

        entry = _single_entry(uid, trip_id)
        assert reason_for_channel(entry, "sms") == REASON_BELOW_THRESHOLD, (
            "AC-3: SMS ist eingeschaltet, die Meldung liegt aber unter der "
            "eingestellten Schwelle 'hoch' — genau das muss im Protokoll "
            f"stehen, erhalten: {reason_for_channel(entry, 'sms')!r} "
            f"(Eintrag: {entry!r})"
        )
    finally:
        clean_uid(uid)


# ═══════════════════════════════ AC-4 ═══════════════════════════════════════


def test_radar_alert_suppressed_entry_matches_dispatch_channel_set(monkeypatch):
    """AC-4: Given ein Regen-Alarm wird durch die Ruhezeit blockiert, BEVOR
    ueberhaupt ein Wetterabruf stattfindet, und ein Kanal ist ausschliesslich
    ueber den Alarme-Reiter aktiviert / When diese Unterdrueckung
    protokolliert wird / Then zeigt der Unterdrueckungs-Eintrag denselben
    Kanal, den ein tatsaechlicher Versand angesteuert haette.

    Aufbau: ZWEI Trips in EINEM Lauf, identisch konfiguriert bis auf das
    Ruhezeit-Fenster — Trip A (Ruhezeit jetzt) laeuft in die Unterdrueckungs-
    Protokollierung (``:987``), Trip B (Ruhezeit spaeter) in den Versandpfad
    (``:1061``/``:1109``). Verglichen werden die beiden Kanal-Listen
    gegeneinander; ein Test, der nur eine Seite prueft, laesst genau die
    Abweichung zu, um die es geht.

    ROT-Grund (gemessen): beide Stellen rufen ``_radar_effective_channels()``,
    das ``alert_channels`` nicht liest. Mit unerreichbaren Kanaelen ist das
    Ergebnis leer — ``append_suppressed_entry()`` kehrt bei leerem Kanal-Set
    ohne Eintrag zurueck (``alert_log.py:306-308``), der Versandpfad bricht an
    ``:1061`` ab. Es entsteht KEIN einziger Eintrag.

    Mutation (Spec AC-4): nur die Versand-Stelle (``:1061``/``:1109``) wird
    auf die geteilte Variable umgestellt, die Unterdrueckungs-Protokollierung
    (``:987``) bleibt bei der alten Aufloesung — dann entsteht entweder gar
    kein Unterdrueckungs-Eintrag oder einer mit anderen Kanaelen als der
    Versand.
    """
    uid = fresh_uid("ac4")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")
        trip_quiet_id, trip_loud_id = _trip_id("ac4-quiet"), _trip_id("ac4-loud")
        # Kanal AUSSCHLIESSLICH ueber den Alarme-Reiter (Briefing: nur E-Mail).
        kanaele = {"email": False, "telegram": False, "sms": True}
        trips = [
            _radar_trip(trip_quiet_id, send_email=True, alert_channels=dict(kanaele), quiet=True),
            _radar_trip(trip_loud_id, send_email=True, alert_channels=dict(kanaele)),
        ]

        _run_radar(monkeypatch, uid, trips, settings_no_channel_reachable())

        unterdrueckt = entries_for(uid, trip_quiet_id, bucket="not_delivered")
        assert len(unterdrueckt) == 1, (
            "AC-4: die Ruhezeit-Unterdrueckung muss GENAU EINEN Eintrag "
            f"hinterlassen, gefunden {len(unterdrueckt)}. Protokoll: "
            f"{read_log(uid)!r}"
        )
        assert REASON_QUIET_HOURS in suppression_reasons(unterdrueckt[0]), (
            f"AC-4: Grund 'Ruhezeit' fehlt im Eintrag: {unterdrueckt[0]!r}"
        )
        assert unterdrueckt[0].get("reason") == REASON_NOWCAST, (
            "AC-4: der Ausloeser bleibt der Nowcast, erhalten: "
            f"{unterdrueckt[0].get('reason')!r}"
        )

        versand = _single_entry(uid, trip_loud_id)
        assert _kanaele_des_unterdrueckungs_eintrags(unterdrueckt[0]) == {"sms"}, (
            "AC-4: der Unterdrueckungs-Eintrag muss genau den Alarme-Reiter-"
            "Kanal nennen, erhalten: "
            f"{_kanaele_des_unterdrueckungs_eintrags(unterdrueckt[0])!r}"
        )
        assert (
            _kanaele_des_unterdrueckungs_eintrags(unterdrueckt[0])
            == _aufgeloeste_kanaele(versand)
        ), (
            "AC-4: Unterdrueckungs-Protokoll und Versand duerfen NICHT auf "
            "unterschiedlichen Kanal-Listen beruhen — unterdrueckt: "
            f"{_kanaele_des_unterdrueckungs_eintrags(unterdrueckt[0])!r}, "
            f"Versand: {_aufgeloeste_kanaele(versand)!r}"
        )
    finally:
        clean_uid(uid)


# ═══════════════════════════════ AC-5 ═══════════════════════════════════════


def test_radar_alert_stays_silent_when_all_trip_channels_off(monkeypatch):
    """AC-5: Given im Alarme-Reiter sind ALLE vier Kanaele ausgeschaltet, das
    Trip-Briefing ist davon unberuehrt (E-Mail dort weiterhin AN) / When ein
    Regen-Alarm ausgeloest wuerde / Then bleibt der Trip vollstaendig still —
    kein Protokoll-Eintrag, keine Sperrzeit, keine Mail.

    WARUM HIER ``settings_email_only()`` STATT ``settings_no_channel_
    reachable()``: nachgemessen — mit unerreichbaren Kanaelen liefert schon
    die ALTE Ableitung ein leeres Set, der Trip bliebe auch heute still und
    der Test waere gruen, ohne irgendetwas zu bewachen (er feierte die
    Nicht-Umsetzung). Erst ein technisch ERREICHBARER Briefing-Kanal macht
    den Unterschied sichtbar: heute gewinnt das Briefing-Flag und der Alarm
    geht raus.

    ROT-Grund (gemessen): ``_radar_effective_channels()`` liefert mit
    ``report_config.send_email=True`` und erreichbarem SMTP ``{'email'}`` —
    der Alarm wird zugestellt, ``append_entry()`` schreibt einen Eintrag und
    ``record_nowcast_sent()`` bucht die Sperrzeit. Der Alarme-Reiter, in dem
    der Nutzer ALLES abgeschaltet hat, wird komplett ignoriert.

    Mutation (Spec AC-5): beim Entfernen des zweiten (toten) Leer-Checks
    (``:1111-1113``) wird der verbliebene erste (``:1061``) versehentlich auf
    eine andere, nicht-geteilte Variable umgehaengt — dann entstuende trotz
    vollstaendig ausgeschalteter Kanaele wieder ein Eintrag und/oder eine
    Sperrzeit.
    """
    uid = fresh_uid("ac5")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")
        trip_id = _trip_id("ac5")
        trip = _radar_trip(
            trip_id,
            send_email=True,  # Briefing unberuehrt AN
            alert_channels={
                "email": False, "telegram": False, "sms": False, "premium_sms": False,
            },
        )
        mails: list = []

        _run_radar(
            monkeypatch, uid, [trip], settings_email_only(),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )

        log = read_log(uid)
        assert entries_for(uid, trip_id, bucket="entries") == [], (
            f"AC-5: ein stumm geschalteter Trip darf keinen Eintrag in "
            f"'entries' erzeugen: {log!r}"
        )
        assert entries_for(uid, trip_id, bucket="not_delivered") == [], (
            f"AC-5: auch kein Eintrag in 'not_delivered': {log!r}"
        )
        assert mails == [], (
            f"AC-5: bei vollstaendig abgeschalteten Alarm-Kanaelen darf keine "
            f"Mail hinausgehen, erhalten: {mails!r}"
        )
        sperrzeit = read_throttle_state(uid).get(SCOPE_TRIP_RADAR, {})
        assert trip_id not in sperrzeit, (
            f"AC-5: es darf keine Sperrzeit fuer {trip_id!r} gebucht werden "
            f"(sonst schluckt sie den naechsten, gewollten Alarm): {sperrzeit!r}"
        )
    finally:
        clean_uid(uid)


# ═══════════════════════════════ AC-6 ═══════════════════════════════════════


def test_radar_alert_logs_configured_but_unreachable_channel(monkeypatch):
    """AC-6: Given im Alarme-Reiter ist ein Kanal aktiviert, der gerade
    technisch nicht erreichbar ist (kein Telegram-Bot hinterlegt) / When ein
    Regen-Alarm ausgeloest wird / Then hinterlaesst der Versuch einen
    nachvollziehbaren Protokoll-Eintrag („Kanal war aktiv, aber technisch
    nicht erreichbar" = ``delivery_failed``) statt spurlos zu verschwinden.
    Gewollte Verbesserung der Nachvollziehbarkeit (Spec D5), kein neuer
    Fehler.

    Wie AC-1 ohne jeden erreichbaren Kanal (``settings_no_channel_
    reachable()``) — hier aber als Nachweis, dass die NEUE Aufloesung nicht
    mehr selbst nach Erreichbarkeit filtert. Kein zufaellig erreichbarer
    Zweitkanal, der einen vorgelagerten Guard passierbar macht (Lehre aus
    „Schritt 0", #1701).

    ROT-Grund (gemessen, ``trip_alert.py:840``): die alte Ableitung macht die
    Erreichbarkeit (``can_send_telegram()``) zum TEIL der Aufloesung. Der
    Kanal gilt dort schon als „aus", das Set ist leer, ``:1061`` bricht
    wortlos ab — es entsteht kein Eintrag.

    Mutation (Spec AC-6): die Aufloesung prueft weiterhin selbst die
    technische Erreichbarkeit, statt das dem Versand zu ueberlassen — der
    erste Leer-Check braeche wieder wortlos ab, kein Eintrag entstuende.
    """
    uid = fresh_uid("ac6")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")
        trip_id = _trip_id("ac6")
        trip = _radar_trip(
            trip_id, send_email=False, send_telegram=False,
            alert_channels={"telegram": True},
        )
        settings = settings_no_channel_reachable()
        assert not settings.can_send_telegram(), (
            "Testvoraussetzung: Telegram ist technisch NICHT erreichbar"
        )

        _run_radar(monkeypatch, uid, [trip], settings)

        entry = _single_entry(uid, trip_id)
        assert reason_for_channel(entry, "telegram") == REASON_DELIVERY_FAILED, (
            "AC-6: der aktivierte, aber unerreichbare Kanal muss als "
            "'technisch gescheitert' protokolliert werden (nicht als "
            "'ausgeschaltet' und nicht gar nicht), erhalten: "
            f"{reason_for_channel(entry, 'telegram')!r} (Eintrag: {entry!r})"
        )
    finally:
        clean_uid(uid)


# ═══════════════════════════════ AC-7 ═══════════════════════════════════════


def test_radar_alert_channels_follow_active_alert_rule_override(monkeypatch):
    """AC-7: Given ein Trip hat eine aktive Alarm-Regel mit eigenem Kanal
    (nur SMS), waehrend der Alarme-Reiter selbst E-Mail eingeschaltet hat /
    When ein Regen-Alarm ausgeloest wird / Then beruecksichtigt der
    Regen-Alarm den Kanal der Regel — Regen-Alarme sind keine Ausnahme von
    den Alarm-Regeln mehr (Spec D4, echte Bedeutungserweiterung).

    Erwartete Aufschluesselung nach ``_effective_alert_channels()``
    (``trip_alert.py:1534-1542``): existiert mindestens eine aktive Regel mit
    nicht-leerer Kanalliste, gewinnt deren Union — der Standard-Kanal E-Mail
    traegt ``channel_disabled``, der Regel-Kanal SMS ``delivery_failed``.

    ROT-Grund (gemessen): ``_radar_effective_channels()`` liest
    ``trip.alert_rules`` ueberhaupt nicht; mit unerreichbaren Kanaelen ist
    das Set leer und der Lauf endet an ``:1061`` ohne Eintrag.

    Mutation (Spec AC-7): die neue Aufloesungsstelle ruft eine eigene,
    abgespeckte Fassung ohne den Regel-Union-Teil auf, statt
    ``_effective_alert_channels()`` unveraendert zu verwenden — der
    Regel-Kanal bliebe unberuecksichtigt, stattdessen gaelte weiterhin nur
    ``alert_channels`` (E-Mail).
    """
    uid = fresh_uid("ac7")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")
        trip_id = _trip_id("ac7")
        trip = _radar_trip(
            trip_id, send_email=True,
            alert_channels={"email": True, "telegram": False, "sms": False},
            rules=[_sms_only_rule()],
        )

        _run_radar(monkeypatch, uid, [trip], settings_no_channel_reachable())

        entry = _single_entry(uid, trip_id)
        assert reason_for_channel(entry, "sms") == REASON_DELIVERY_FAILED, (
            "AC-7: der Kanal-Override der aktiven Alarm-Regel muss auch fuer "
            "Regen-Alarme gelten, erhalten: "
            f"{reason_for_channel(entry, 'sms')!r} (Eintrag: {entry!r})"
        )
        assert reason_for_channel(entry, "email") == REASON_CHANNEL_DISABLED, (
            "AC-7: bei einer Regel mit eigenem Kanal gewinnt deren Union — "
            "der Standard-Kanal E-Mail zaehlt dann nicht mit, erhalten: "
            f"{reason_for_channel(entry, 'email')!r} (Eintrag: {entry!r})"
        )
    finally:
        clean_uid(uid)
