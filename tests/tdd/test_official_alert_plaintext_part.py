"""Eigener Klartext-Teil der amtlichen Warn-Mail (#1744 Scheibe A2, AC-13).

SPEC: docs/specs/modules/fix_1744_alarm_format_angleichen.md
      („Der Klartext der amtlichen Warn-Mail", PO-Entscheid 2026-08-12)

Gemessen wird die ZUGESTELLTE Mail: der echte Trip-Pfad
`NotificationService.send_official_alert` laeuft durch, `EmailOutput.send`
laeuft ECHT (inkl. aller Empfaenger-Waechter und des echten MIME-Baus in
`build_mime_message`) — ersetzt ist ausschliesslich der Steckdosenrand
`EmailOutput._dial_and_send`, der sonst eine SMTP-Verbindung aufmachen wuerde.
Kein Mock-Objekt, kein Netz, kein Versand. Geprueft wird der `text/plain`-Teil
der so entstandenen MIME-Nachricht.

RED-Grund, am 2026-08-12 nachgemessen: `send_official_alert` ruft
`EmailOutput.send(...)` OHNE `plain_text_body`
(`src/services/notification_service.py:859-861`). `build_mime_message`
(`src/output/channels/email.py:350-358`) strippt daraufhin die Tags aus dem
HTML — heraus kommt EINE einzige zusammengeklebte Zeile:

    1 amtliche WarnungGewitter gemeldet.WarnstufeGELBORANGEROTniedrigste von
    dreiGewitterGueltig: Sa 11.07. · 15:00-21:00Route: Segment 3 Quelle: ...

Sie traegt NULL Label-Wert-Zeilen. Genau daran scheitert dieser Test heute.

Mutations-Gegenprobe (Spec, AC-13): wird die Uebergabe des Klartexts an den
Mailer spaeter wieder entfernt, faellt der Text auf exakt diesen gestrippten
Zustand zurueck — der Test wird wieder rot. Er prueft damit den GEBAUTEN
Klartext, nicht den gestrippten.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from email.message import Message
from zoneinfo import ZoneInfo

import pytest

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_email
from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
VON = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
BIS = datetime(2026, 7, 11, 21, 0, tzinfo=UTC)
QUELLE = "GeoSphere Austria"

# Label-Wert-Zeile: „Label: Wert" auf EINER Zeile, so wie die Nowcast-Mail sie
# baut („Wo & wann: 🏁 Ziel · ab 10:05"). Das Label bleibt kurz und enthaelt
# keinen Doppelpunkt.
_LABEL_WERT_RE = re.compile(r"^([^:]{1,40}): (\S.*)$")
_WOCHENTAG_DATUM_RE = re.compile(r"\b(Mo|Di|Mi|Do|Fr|Sa|So)\s+\d{2}\.\d{2}\.")

DATENZEILE, STAND, HERKUNFT = "datenzeile", "stand-zeile", "herkunfts-fusszeile"
SPERRZEIT = "sperrzeit-hinweis"
#: Die drei Zeilenarten, deren Reihenfolge AC-13 festlegt.
AC13_ARTEN = (DATENZEILE, STAND, HERKUNFT)

#: Zeitzone der Fixture-Wegpunkte (46.6 N / 13.0 O liegt in Kaernten). Der
#: echte Versandpfad leitet sie ueber `tz_for_coords` aus dem ersten Wegpunkt
#: ab und rendert die Gueltigkeit LOKAL -- die UTC-Zeiten oben stehen deshalb
#: nicht woertlich in der Mail.
FIXTURE_TZ = "Europe/Vienna"


@pytest.fixture()
def zugestellte_nachrichten(monkeypatch) -> list[Message]:
    """Zeichnet die MIME-Nachrichten auf, die `EmailOutput.send()` gebaut hat.

    Ersetzt wird nur `_dial_and_send` — der EINE Ort, an dem eine SMTP-
    Verbindung entsteht (`email.py:461`). Alles davor (Empfaenger-Aufloesung,
    Herkunftssperre, Allowlist-/Lokal-Waechter, `build_mime_message`) laeuft
    unveraendert. `msg` ist das sechste Positionsargument; die Signatur wird
    absichtlich locker gefasst, damit ein spaeterer Parameter-Zuwachs am
    Transportrand diesen Test nicht bricht.
    """
    from output.channels.email import EmailOutput

    erfasst: list[Message] = []

    def _aufzeichnen(self, *args, **kwargs):
        erfasst.append(kwargs.get("msg") if "msg" in kwargs else args[5])

    monkeypatch.setattr(EmailOutput, "_dial_and_send", _aufzeichnen)
    return erfasst


def _klartext(msg: Message) -> str:
    teile = [
        part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
        for part in msg.walk()
        if part.get_content_type() == "text/plain"
    ]
    assert teile, "Die zugestellte Mail hat gar keinen text/plain-Teil"
    return "\n".join(teile)


def _zeilenarten(klartext: str) -> list[tuple[str, str]]:
    """Leitet aus einem Klartext die Abfolge seiner Zeilenarten ab.

    - `datenzeile`  — eine Zeile der Form „Label: Wert"
    - `stand-zeile` — beginnt mit „Stand: heute"
    - `herkunfts-fusszeile` — die geteilte Herkunftszeile, erkennbar an der
      Mailart-Bezeichnung (`_MAIL_TYPE_LABELS`, `email/helpers.py:477-484`)
    - `sperrzeit-hinweis` — der Cooldown-Satz; er hat zwar Label-Wert-Gestalt
      („Cooldown: Du erhaeltst …"), ist aber ein typ-eigener Baustein und
      KEINE Datenzeile. Ohne diese Unterscheidung faende die Nowcast-Mail
      hinter ihrer Stand-Zeile eine zweite Datenzeilen-Gruppe.

    Alles Uebrige (Ueberschrift, Kennzeichen, Leerzeilen) bleibt
    unklassifiziert und stoert die Reihenfolge-Pruefung nicht — AC-13 nennt
    ausdruecklich nur die drei erstgenannten Arten.
    """
    arten: list[tuple[str, str]] = []
    for rohzeile in klartext.splitlines():
        zeile = rohzeile.strip()
        if not zeile:
            continue
        if zeile.startswith("Stand: heute"):
            arten.append((STAND, zeile))
        elif "höchstens einmal in" in zeile:
            arten.append((SPERRZEIT, zeile))
        elif re.search(r"(Amtliche Warnung|Regen-/Gewitter-Alarm|Abweichungs-Alarm)", zeile):
            arten.append((HERKUNFT, zeile))
        elif _LABEL_WERT_RE.match(zeile):
            arten.append((DATENZEILE, zeile))
    return arten


def _datenpaare(klartext: str) -> list[tuple[str, str]]:
    paare = []
    for art, zeile in _zeilenarten(klartext):
        if art != DATENZEILE:
            continue
        treffer = _LABEL_WERT_RE.match(zeile)
        paare.append((treffer.group(1).strip(), treffer.group(2).strip()))
    return paare


def _reihenfolge(klartext: str) -> list[str]:
    """Abfolge der DREI von AC-13 genannten Zeilenarten, Wiederholungen
    zusammengefasst (mehrere Datenzeilen hintereinander sind EIN Block)."""
    folge: list[str] = []
    for art, _ in _zeilenarten(klartext):
        if art not in AC13_ARTEN:
            continue
        if not folge or folge[-1] != art:
            folge.append(art)
    return folge


def _nowcast_klartext() -> str:
    """Der Klartext der Nowcast-Mail — die Bezugsgroesse, an der AC-13 die
    Reihenfolge misst. Er entsteht im selben Aufruf wie das HTML aus denselben
    Label-Wert-Tupeln (`render.py:260-263`)."""
    msg = AlertMessage(
        trip_short="KHW 403", stand_at="09:30", source="radar",
        cooldown_display="60 Min",
        events=(OnsetEvent(
            onset_minutes=25, onset_time="10:05", km_from=8.0, km_to=8.0,
            is_convective=True, intensity_label="stark",
            source_label="Radar (DWD)", segment_id="Ziel",
        ),),
    )
    return render_email(msg)[1]


def _amtliche_mail_versenden(zugestellte_nachrichten) -> Message:
    from app.config import Settings
    from app.trip import Stage, Trip, Waypoint
    from services.notification_service import NotificationService

    waypoints = [
        Waypoint(id=f"w{i}", name=f"P{i}", lat=46.6 + i * 0.01, lon=13.0 + i * 0.01,
                 elevation_m=1500.0)
        for i in range(6)
    ]
    trip = Trip(
        id="tdd-1744-a2-plain", name="KHW 403",
        stages=[Stage(id="s1", name="Tag 1", date=date(2026, 7, 11), waypoints=waypoints)],
    )
    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=VON, valid_to=BIS, region_label="Hermagor-Pressegger See",
    )
    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid", smtp_pass="x",
        mail_to="to@test.invalid",
    )
    NotificationService(settings, "tdd-1744-a2-plain").send_official_alert(
        trip=trip, notices=[(alert, ["3"])], effective_channels={"email"},
        sms_sink=lambda text: None,
    )
    assert len(zugestellte_nachrichten) == 1, (
        f"Erwartet genau EINE zugestellte Mail, erfasst: {len(zugestellte_nachrichten)}"
    )
    msg = zugestellte_nachrichten[0]
    assert msg.get("X-GZ-Mail-Type") == "official-alert", (
        f"Falscher Mail-Typ erfasst: {msg.get('X-GZ-Mail-Type')!r}"
    )
    return msg


def test_ac13_warnmail_traegt_eigens_gebauten_klartext_mit_datenzeilen(
    zugestellte_nachrichten,
):
    """AC-13: Given eine amtliche Warn-Mail / When sie versendet wird / Then
    traegt sie einen eigens gebauten Klartext-Teil mit denselben Datenzeilen
    wie ihr HTML — nicht mehr den aus dem HTML gestrippten Text.

    Nachgewiesen werden die vier von der Spec genannten Angaben als
    Label-Wert-Zeilen. Fest verlangt sind nur die beiden Label, die ohnehin der
    Warn-Mail-Waechter vorschreibt (`Gueltig:` in P-3, `Quelle:` in P-4); die
    Label fuer Gefahrenart und Ortsbezug gibt die Spec nicht vor — sie werden
    deshalb ueber ihren WERT nachgewiesen, nicht ueber einen erfundenen
    Label-Text.
    """
    klartext = _klartext(_amtliche_mail_versenden(zugestellte_nachrichten))
    paare = _datenpaare(klartext)

    assert len(paare) >= 4, (
        "Der Klartext-Teil traegt keine gebauten Datenzeilen (erwartet mindestens "
        "vier: Gefahrenart, Gueltigkeitsfenster, Ortsbezug, Quelle). Gefunden: "
        f"{paare!r}\nGanzer Klartext:\n{klartext}"
    )

    label = {k for k, _ in paare}
    werte = [v for _, v in paare]

    assert "Gültig" in label, f"Keine Gueltigkeits-Datenzeile: {paare!r}"
    gueltig = next(v for k, v in paare if k == "Gültig")
    assert _WOCHENTAG_DATUM_RE.search(gueltig), (
        f"Gueltigkeitsfenster ohne Wochentag+Datum (Waechter P-3): {gueltig!r}"
    )
    von_lokal = VON.astimezone(ZoneInfo(FIXTURE_TZ)).strftime("%H:%M")
    bis_lokal = BIS.astimezone(ZoneInfo(FIXTURE_TZ)).strftime("%H:%M")
    assert von_lokal in gueltig and bis_lokal in gueltig, (
        f"Gueltigkeits-Zeiten ({von_lokal}-{bis_lokal} Ortszeit) fehlen in der "
        f"Datenzeile: {gueltig!r}"
    )

    assert "Quelle" in label, f"Keine Quellen-Datenzeile: {paare!r}"
    quelle = next(v for k, v in paare if k == "Quelle")
    assert QUELLE in quelle, f"Quellen-Datenzeile nennt die Quelle nicht: {quelle!r}"

    assert any(v.strip() == "Gewitter" for v in werte), (
        f"Gefahrenart steht in keiner Datenzeile: {paare!r}"
    )
    assert any("Segment 3" in v for v in werte), (
        f"Ortsbezug steht in keiner Datenzeile: {paare!r}"
    )


def test_ac13_klartext_reihenfolge_entspricht_der_nowcast_mail(zugestellte_nachrichten):
    """AC-13 (Reihenfolge): Given der Klartext-Teil der amtlichen Warn-Mail /
    When er mit dem Klartext der Nowcast-Mail verglichen wird / Then stehen
    Datenzeilen, Stand-Zeile und Herkunfts-Fusszeile in derselben Reihenfolge.

    Verglichen werden nur die DREI von AC-13 genannten Zeilenarten. Wo
    Ueberschrift und Kennzeichen im Klartext stehen, laesst die Spec offen —
    dieser Test schreibt es deshalb bewusst nicht fest.
    """
    nowcast = _reihenfolge(_nowcast_klartext())
    assert nowcast == [DATENZEILE, STAND, HERKUNFT], (
        "Bezugsgroesse verloren: der Nowcast-Klartext hat nicht mehr die Abfolge "
        f"Datenzeilen -> Stand -> Herkunft, sondern {nowcast!r}"
    )

    klartext = _klartext(_amtliche_mail_versenden(zugestellte_nachrichten))
    amtlich = _reihenfolge(klartext)
    assert amtlich == nowcast, (
        "Der Klartext der amtlichen Warn-Mail folgt nicht der Zeilenfolge der "
        f"Nowcast-Mail.\nNowcast:  {nowcast!r}\nAmtlich:  {amtlich!r}\n"
        f"Ganzer Klartext:\n{klartext}"
    )


def test_ac13_klartext_ist_nicht_der_gestrippte_html_koerper(zugestellte_nachrichten):
    """AC-13 (Gegenprobe zum Ist-Zustand): Given die zugestellte Warn-Mail /
    When ihr Klartext-Teil betrachtet wird / Then ist er nicht der aus dem HTML
    gestrippte Text.

    Erkennungsmerkmal des gestrippten Textes, am 2026-08-12 gemessen: er faellt
    zu EINER einzigen Zeile zusammen, weil `re.sub(r'<[^>]+>', '', ...)`
    zwischen benachbarten Inline-Elementen kein Trennzeichen einfuegt (dieselbe
    Ursache, die den Warn-Mail-Waechter zu seiner Wortgrenzen-Ausnahme fuer
    'GELBORANGEROT' zwingt, `official_alert_mail_validator.py:56-59`).

    Dieser Test ist die Mutations-Gegenprobe in Testform: wird die Uebergabe
    des Klartexts an den Mailer entfernt, wird er wieder rot.
    """
    klartext = _klartext(_amtliche_mail_versenden(zugestellte_nachrichten))
    zeilen = [z for z in klartext.splitlines() if z.strip()]

    assert len(zeilen) > 1, (
        "Der Klartext-Teil besteht aus einer einzigen zusammengeklebten Zeile — "
        f"das ist der aus dem HTML gestrippte Text, kein gebauter:\n{klartext!r}"
    )
    assert "GELBORANGEROT" not in klartext.replace(" ", ""), (
        "Die Warnstufen-Skala klebt im Klartext zusammen — Merkmal des "
        f"gestrippten HTML-Koerpers:\n{klartext!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 — derselbe Mailtyp aus dem Ortsvergleich (Adversary F001, 2026-08-13)
# ---------------------------------------------------------------------------
#
# Der Ortsvergleich verschickt DENSELBEN Mailtyp (`X-GZ-Mail-Type:
# official-alert`) ueber denselben Renderer -- nur ueber eine zweite
# Versandfunktion (`send_multi_location_official_alert` ->
# `_dispatch_compare_official_email`). Die 28 Bestandstests dieser Flaeche
# fahren ausnahmslos ueber `mail_sink`, und dieser Zweig uebergibt nur das
# HTML: die Zeile `plain_text_body=plain` im `EmailOutput.send`-Zweig war
# damit von KEINEM Test bewacht -- ihre Entfernung lief unbemerkt durch. Dieser
# Test schliesst die Luecke am selben Wirkort wie der Trip-Pfad: echter
# `EmailOutput.send`-Durchlauf, geprueft wird der zugestellte text/plain-Teil.


def _compare_mail_versenden(zugestellte_nachrichten) -> Message:
    from app.config import Settings
    from app.user import SavedLocation
    from services.notification_service import NotificationService

    orte = [
        SavedLocation(id="loc-a", name="Hermagor", lat=46.62, lon=13.68, elevation_m=600),
        SavedLocation(id="loc-b", name="Kötschach", lat=46.67, lon=13.00, elevation_m=710),
    ]
    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=VON, valid_to=BIS, region_label="Hermagor-Pressegger See",
    )
    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid", smtp_pass="x",
        mail_to="to@test.invalid",
    )
    NotificationService(settings, "tdd-1744-a2-compare").send_multi_location_official_alert(
        preset_name="Kärnten-Vergleich", locations=orte,
        tagged_alerts=[(alert, ["loc-a"])], effective_channels={"email"},
        sms_sink=lambda text: None, telegram_sink=lambda *a, **kw: None,
    )
    assert len(zugestellte_nachrichten) == 1, (
        f"Erwartet genau EINE zugestellte Mail, erfasst: {len(zugestellte_nachrichten)}"
    )
    msg = zugestellte_nachrichten[0]
    assert msg.get("X-GZ-Mail-Type") == "official-alert", (
        f"Falscher Mail-Typ erfasst: {msg.get('X-GZ-Mail-Type')!r}"
    )
    return msg


def test_ac13_compare_warnmail_traegt_denselben_gebauten_klartext(
    zugestellte_nachrichten,
):
    """AC-13 (Ortsvergleich): Given eine amtliche Warn-Mail aus dem
    Ortsvergleich / When sie versendet wird / Then traegt sie denselben eigens
    gebauten Klartext-Teil wie die Trip-Warn-Mail — Datenzeilen, Stand-Zeile
    und Herkunfts-Fusszeile in derselben Reihenfolge.

    Einziger fachlicher Unterschied zum Trip-Pfad: der Ortsbezug heisst „Orte"
    statt „Route" und nennt Ortsnamen statt Segment-Kennungen
    (`scope_kind="locations"`, AC-12 der Warnmail-Spec).
    """
    klartext = _klartext(_compare_mail_versenden(zugestellte_nachrichten))
    paare = _datenpaare(klartext)

    assert len(paare) >= 4, (
        "Der Klartext-Teil der Compare-Warn-Mail traegt keine gebauten "
        f"Datenzeilen. Gefunden: {paare!r}\nGanzer Klartext:\n{klartext}"
    )
    label = {k for k, _ in paare}
    assert "Gültig" in label, f"Keine Gueltigkeits-Datenzeile: {paare!r}"
    assert "Quelle" in label, f"Keine Quellen-Datenzeile: {paare!r}"
    assert "Orte" in label, (
        f"Ortsbezug fehlt oder heisst nicht 'Orte' (Compare-Pfad): {paare!r}"
    )

    gueltig = next(v for k, v in paare if k == "Gültig")
    assert _WOCHENTAG_DATUM_RE.search(gueltig), (
        f"Gueltigkeitsfenster ohne Wochentag+Datum (Waechter P-3): {gueltig!r}"
    )
    assert QUELLE in next(v for k, v in paare if k == "Quelle"), (
        f"Quellen-Datenzeile nennt die Quelle nicht: {paare!r}"
    )
    assert any("Hermagor" in v for v in (v for _, v in paare)), (
        f"Betroffener Ort steht in keiner Datenzeile: {paare!r}"
    )

    assert _reihenfolge(klartext) == [DATENZEILE, STAND, HERKUNFT], (
        "Der Klartext der Compare-Warn-Mail folgt nicht der Zeilenfolge "
        f"Datenzeilen -> Stand -> Herkunft: {_reihenfolge(klartext)!r}\n"
        f"Ganzer Klartext:\n{klartext}"
    )
    zeilen = [z for z in klartext.splitlines() if z.strip()]
    assert len(zeilen) > 1 and "GELBORANGEROT" not in klartext.replace(" ", ""), (
        "Der Klartext-Teil ist der aus dem HTML gestrippte Text, kein "
        f"gebauter:\n{klartext!r}"
    )


# ---------------------------------------------------------------------------
# Issue #2018 Teil C (Korrektur 5) — additiver Waechter, Adversary-Finding F001
# ---------------------------------------------------------------------------

#: Der bestehende, bewusst unangetastete Kern des Cooldown-Satzes.
COOLDOWN_KERN = "höchstens einmal in"
#: Die Praezisierung aus Issue #2018 Teil C — sie MUSS in DERSELBEN Zeile
#: stehen (Spec, Korrektur 5), sonst zerfaellt der Sperrzeit-Hinweis in zwei
#: Bloecke und die zeilenweise Klassifikation oben (`_zeilenarten`) sieht
#: hinter der Stand-Zeile eine zweite Zeilengruppe.
COOLDOWN_ZUSATZ = "greift dieser Cooldown nicht"


def _buendel_nowcast_klartext() -> str:
    """Derselbe Klartext, aber aus dem Buendel-Zweig
    (`_render_email_onset_multi`) — er baut den Cooldown-Satz ein ZWEITES Mal
    und muss dieselbe Auflage erfuellen."""
    ereignisse = tuple(
        OnsetEvent(
            onset_minutes=minuten, onset_time=zeit, km_from=8.0, km_to=8.0,
            is_convective=True, intensity_label="stark",
            source_label="Radar (DWD)", location_label=ort,
        )
        for ort, minuten, zeit in (("Zermatt", 25, "10:05"), ("Chamonix", 40, "10:20"))
    )
    return render_email(AlertMessage(
        trip_short="KHW 403", stand_at="09:30", source="radar",
        cooldown_display="60 Min", events=ereignisse,
    ))[1]


@pytest.mark.parametrize(
    "klartext_bauen, zweig",
    [(_nowcast_klartext, "Einzel-Onset"), (_buendel_nowcast_klartext, "Buendel-Onset")],
)
def test_2018_cooldown_zusatz_steht_in_derselben_klartext_zeile(klartext_bauen, zweig):
    """Issue #2018 Teil C, Korrektur 5 — Adversary-Finding F001.

    GIVEN den gerenderten Klartext einer Nowcast-Mail mit gesetztem Cooldown
    WHEN  die Zeile mit dem bestehenden Cooldown-Satz gesucht wird
    THEN  traegt GENAU DIESE Zeile auch den Quellen-Zusatz — der Zusatz
          steht nie in einer eigenen Zeile und nie ein zweites Mal.

    Warum dieser Waechter noetig ist: die Klassifikation in `_zeilenarten()`
    erkennt den Sperrzeit-Hinweis am Substring `höchstens einmal in`. Ein in
    eine eigene Zeile ausgelagerter Zusatz faellt durch alle vier Muster und
    bleibt unklassifiziert — die Reihenfolge-Pruefung dieser Datei bliebe
    gruen, obwohl die Auflage gebrochen ist (nachgemessen 2026-08-21). Der
    Waechter prueft die Auflage deshalb am gerenderten Nutzertext direkt.

    Gegenprobe (Pflicht): wird der Zusatz in `render.py` in einen eigenen
    Klartext-Block gezogen, wird dieser Test rot.
    """
    klartext = klartext_bauen()
    kern_zeilen = [z.strip() for z in klartext.splitlines() if COOLDOWN_KERN in z]
    zusatz_zeilen = [z.strip() for z in klartext.splitlines() if COOLDOWN_ZUSATZ in z]

    assert len(kern_zeilen) == 1, (
        f"{zweig}: erwartet GENAU EINE Cooldown-Zeile:\n{klartext}"
    )
    assert COOLDOWN_ZUSATZ in kern_zeilen[0], (
        f"{zweig}: der Quellen-Zusatz muss in DERSELBEN Zeile wie der "
        f"bestehende Cooldown-Satz stehen (Spec Korrektur 5) — "
        f"gefunden: {kern_zeilen[0]!r}\nGanzer Klartext:\n{klartext}"
    )
    assert zusatz_zeilen == kern_zeilen, (
        f"{zweig}: der Quellen-Zusatz steht ausserhalb der Cooldown-Zeile "
        f"oder doppelt: {zusatz_zeilen!r}\nGanzer Klartext:\n{klartext}"
    )
