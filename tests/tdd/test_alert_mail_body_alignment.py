"""Angeglichener Mail-Koerper der Trip-Alarme (#1744 Scheibe A2, AC-8..AC-12).

SPEC: docs/specs/modules/fix_1744_alarm_format_angleichen.md
      („Scheibe A2 — Mail-Koerper", freigegeben 2026-08-12)

Kein Mock, kein Netz: es rendern die echten Renderer bzw. laeuft der echte
`NotificationService`-Trip-Pfad mit aufzeichnender `mail_sink`. HTML wird mit
BeautifulSoup strukturell geparst, nicht per Substring-Suche im Rohtext.

RED-Phase 2026-08-12 — was hier heute scheitert und warum:

* **AC-8 Bausteinfolge** — die amtliche Warn-Mail fuehrt zwischen Datenzeilen
  und Stand-Zeile einen Baustein, den die Zielreihenfolge nicht kennt: die
  Quelle-Box (`_standalone_src_html`, `official_alerts.py:1285-1315`). Sie wird
  laut Spec zur Datenzeile „Quelle".
* **AC-8 Bauform** — der Nowcast baut je Datenzeile eine
  `<table role="presentation">`, Label links / Wert rechtsbuendig
  (`_datarow_html`, `render.py:403-417`; die Tabellenform ist Outlook-Absicht,
  kein Zufall). Die amtliche Warnung baut stattdessen ein CSS-Grid mit einem
  einzigen Facts-Block, in dem Label und Wert als `<span class="k">…</span> …
  <br>` inline stehen. Derselbe Auslese-Helfer findet dort heute NULL Zeilen.

**Bewahrungs-ACs (AC-9, AC-10, AC-11, AC-12) sind heute gruen** und muessen den
Umbau ueberleben. Sie sind bewusst am Wirkort formuliert — an der gerenderten
Mail bzw. am gerenderten Betreff —, nicht an Zwischenprodukten.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from bs4 import BeautifulSoup

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.official_alerts import (
    OfficialAlertNotice, build_official_alert_notices, render_official_alert_subject,
    render_warn_block,
)
from output.renderers.alert.render import render_email
from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
VON = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
BIS = datetime(2026, 7, 11, 21, 0, tzinfo=UTC)
QUELLE = "GeoSphere Austria"
REGION = "Hermagor-Pressegger See"

# --- Bausteine der gemeinsamen Zielreihenfolge (Spec, „Gemeinsamer
# Mail-Aufbau (A2)"). Typ-eigene Bausteine (Skala nur amtlich, Sperrzeit nur
# Nowcast) sitzen an FESTEN Positionen und duerfen fehlen. --------------------
KENNZEICHEN, UEBERSCHRIFT, SKALA = "kennzeichen", "ueberschrift", "warnstufen-skala"
DATENZEILEN, SPERRZEIT = "datenzeilen", "sperrzeit-hinweis"
STAND, HERKUNFT, UNBEKANNT = "stand-zeile", "herkunfts-fusszeile", "UNBEKANNT"

SOLL_REIHENFOLGE = (
    KENNZEICHEN, UEBERSCHRIFT, SKALA, DATENZEILEN, SPERRZEIT, STAND, HERKUNFT,
)

_KENNZEICHEN_RE = re.compile(r"Radar-Nowcast|\d+\s+amtliche Warnung")
_WOCHENTAG_DATUM_RE = re.compile(r"\b(Mo|Di|Mi|Do|Fr|Sa|So)\s+\d{2}\.\d{2}\.")
_SEGMENT_NENNUNG_RE = re.compile(r"Segment\s+[\d,–\s]+")


def _alert(level=2, hazard="thunderstorm", label="Gewitter") -> OfficialAlert:
    return OfficialAlert(
        source="geosphere_warn", hazard=hazard, level=level, label=label,
        valid_from=VON, valid_to=BIS, region_label=REGION,
    )


def _amtliche_mail(notices=None, **overrides) -> str:
    """Die eigenstaendige amtliche Warn-Mail ueber den geteilten Baustein —
    derselbe Weg, den `send_official_alert` geht (`render_warn_block(
    variant="standalone", ...)`)."""
    if notices is None:
        notices = [OfficialAlertNotice(
            alert=_alert(), scope_label="Segment 3", sms_scope="nur S3",
            affected_chips=["Segment 3"], free_chips=[],
        )]
    kwargs = dict(
        variant="standalone", source_label=QUELLE, stand_at="09:30", tz=UTC,
        context_label="KHW 403",
    )
    kwargs.update(overrides)
    return render_warn_block(notices, **kwargs)


def _nowcast_mail() -> tuple[str, str]:
    """Die Nowcast-Mail (html, plain) — Vorbild-Aufbau laut Spec."""
    msg = AlertMessage(
        trip_short="KHW 403", stand_at="09:30", source="radar",
        cooldown_display="60 Min",
        events=(OnsetEvent(
            onset_minutes=25, onset_time="10:05", km_from=8.0, km_to=8.0,
            is_convective=True, intensity_label="stark",
            source_label="Radar (DWD)", segment_id="Ziel",
        ),),
    )
    return render_email(msg)


def _bausteine(html: str) -> list[tuple[str, str]]:
    """Leitet aus einer gerenderten Mail die Abfolge ihrer Bausteine ab.

    Betrachtet werden die direkten Kinder von `<body>` — je Kind genau EIN
    Baustein. Die Zuordnung geschieht ueber Merkmale, die in BEIDEN heutigen
    Bauformen und in der Zielbauform tragen, damit dieser Test die
    *Reihenfolge* misst und nicht die Bauform (die prueft AC-8s zweiter Test):

    | Baustein   | erkannt an                                              |
    |------------|---------------------------------------------------------|
    | Stand      | Text beginnt mit „Stand: heute"                         |
    | Sperrzeit  | Text enthaelt „hoechstens einmal in"                     |
    | Skala      | Klasse `stufe-line` (uniforme Stufe)                     |
    | Ueberschrift | Tag `h1` ODER Klasse `body-h1`                        |
    | Kennzeichen | Text ist die Alarmart-Kennung („Radar-Nowcast" bzw.     |
    |            | „N amtliche Warnung(en)")                                |
    | Datenzeilen | traegt mindestens eine Datenzeile — `table[role=        |
    |            | presentation]` (Nowcast-Bauform) ODER `.facts` (heutige  |
    |            | amtliche Bauform); BEIDE zaehlen bewusst                 |
    | Herkunft   | Text traegt die Mailart-Zeile der geteilten Fusszeile    |

    Alles andere wird `UNBEKANNT` — ein Baustein, den die Zielreihenfolge nicht
    kennt, faellt damit auf, statt still durchzurutschen.

    Rueckgabe: `(Baustein, Textausschnitt)` je Kind, in DOM-Reihenfolge.
    """
    soup = BeautifulSoup(html, "html.parser")
    ergebnis: list[tuple[str, str]] = []
    for el in soup.body.find_all(recursive=False):
        text = el.get_text(" ", strip=True)
        klassen = set(el.get("class") or [])
        if text.startswith("Stand: heute"):
            art = STAND
        elif "höchstens einmal in" in text:
            art = SPERRZEIT
        elif "stufe-line" in klassen or el.select_one(".stufe-line"):
            art = SKALA
        elif el.name == "h1" or "body-h1" in klassen:
            art = UEBERSCHRIFT
        elif _KENNZEICHEN_RE.fullmatch(text) or _KENNZEICHEN_RE.match(text):
            art = KENNZEICHEN
        elif el.select_one('table[role="presentation"]') or el.select_one(".facts"):
            art = DATENZEILEN
        elif re.search(r"(Amtliche Warnung|Regen-/Gewitter-Alarm|Abweichungs-Alarm)", text):
            art = HERKUNFT
        else:
            art = UNBEKANNT
        ergebnis.append((art, text[:80]))
    return ergebnis


def _ist_teilfolge(folge: list[str], soll: tuple[str, ...]) -> bool:
    """Ob `folge` eine Teilfolge von `soll` ist (Reihenfolge eingehalten,
    Auslassungen erlaubt) — genau die Zusicherung „typ-eigene Bausteine duerfen
    an ihrer festen Position fehlen, ohne die uebrigen zu verschieben"."""
    rest = list(soll)
    for baustein in folge:
        if baustein not in rest:
            return False
        rest = rest[rest.index(baustein) + 1:]
    return True


def _datenzeilen(html: str) -> list[tuple[str, str]]:
    """Liest die Datenzeilen in der Bauform des Nowcasts aus: eine
    `<table role="presentation">` mit genau zwei Zellen — Label links,
    Wert rechtsbuendig (`_datarow_html`, `render.py:403-417`).

    DERSELBE Helfer laeuft ueber beide Mails. Findet er in der amtlichen
    Warnung nichts, haben die beiden Mails nicht dieselbe Bauform — das ist
    die Aussage von AC-8s zweitem Halbsatz, nicht ein Helfer-Fehler.
    """
    soup = BeautifulSoup(html, "html.parser")
    zeilen: list[tuple[str, str]] = []
    for tabelle in soup.select('table[role="presentation"]'):
        for tr in tabelle.select("tr"):
            zellen = tr.find_all("td", recursive=False)
            if len(zellen) != 2:
                continue
            links, rechts = zellen
            if (links.get("align"), rechts.get("align")) != ("left", "right"):
                continue
            zeilen.append((links.get_text(" ", strip=True), rechts.get_text(" ", strip=True)))
    return zeilen


def _text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


# ---------------------------------------------------------------------------
# AC-8 — dieselbe Bausteinfolge, dieselbe Bauform der Datenzeilen
# ---------------------------------------------------------------------------
def test_ac8_beide_mailtypen_haben_dieselbe_bausteinfolge():
    """AC-8: Given je eine Nowcast-Mail und eine amtliche Warn-Mail / When
    beide gerendert werden / Then folgen ihre Bausteine derselben Reihenfolge.

    Geprueft wird nicht Byte gegen Byte, sondern die aus beiden Mails
    abgeleitete Baustein-ABFOLGE (`_bausteine`): jede der beiden muss eine
    Teilfolge der gemeinsamen Soll-Reihenfolge sein. Typ-eigene Bausteine
    (Warnstufen-Skala nur amtlich, Sperrzeit-Hinweis nur Nowcast) duerfen an
    ihrer festen Position fehlen; ein Baustein AUSSERHALB der Soll-Reihenfolge
    darf es nicht geben.

    RED heute: die amtliche Warnung fuehrt zwischen Datenzeilen und Stand-Zeile
    die Quelle-Box (`.src`) — ein Baustein, den die Zielreihenfolge nicht kennt.
    """
    nowcast_html, _ = _nowcast_mail()
    amtlich_html = _amtliche_mail()

    nowcast = _bausteine(nowcast_html)
    amtlich = _bausteine(amtlich_html)

    assert UNBEKANNT not in [a for a, _ in nowcast], (
        f"Nowcast-Mail traegt einen Baustein ausserhalb der Soll-Reihenfolge: {nowcast!r}"
    )
    assert UNBEKANNT not in [a for a, _ in amtlich], (
        "Amtliche Warn-Mail traegt einen Baustein ausserhalb der Soll-Reihenfolge "
        f"{SOLL_REIHENFOLGE!r}:\n" + "\n".join(f"  {a:20} {t!r}" for a, t in amtlich)
    )
    assert _ist_teilfolge([a for a, _ in nowcast], SOLL_REIHENFOLGE), (
        f"Nowcast-Bausteinfolge weicht ab: {[a for a, _ in nowcast]!r}"
    )
    assert _ist_teilfolge([a for a, _ in amtlich], SOLL_REIHENFOLGE), (
        f"Amtliche Bausteinfolge weicht ab: {[a for a, _ in amtlich]!r}"
    )
    # Anker gegen einen falsch-gruenen Vergleich zweier leerer Folgen.
    gemeinsam = {KENNZEICHEN, UEBERSCHRIFT, DATENZEILEN, STAND, HERKUNFT}
    assert gemeinsam <= set(a for a, _ in nowcast), f"Nowcast unvollstaendig: {nowcast!r}"
    assert gemeinsam <= set(a for a, _ in amtlich), f"Amtlich unvollstaendig: {amtlich!r}"


def test_ac8_fakten_der_warnung_stehen_in_datenzeilen_der_nowcast_bauform():
    """AC-8 (zweiter Halbsatz): Given die amtliche Warn-Mail / When sie
    gerendert wird / Then stehen ihre Fakten in Datenzeilen DERSELBEN Bauform
    wie beim Nowcast — `<table role="presentation">`, Label links, Wert
    rechtsbuendig.

    Derselbe Auslese-Helfer laeuft ueber beide Mails. Geprueft wird, dass die
    vier Fakten (Gefahrenart, Gueltigkeitsfenster, Ortsbezug, Quelle) als WERT
    einer solchen Zeile auftauchen — die LABEL-Texte gibt die Spec nicht vor
    und dieser Test schreibt sie deshalb auch nicht fest.

    RED heute: die amtliche Warnung rendert ein CSS-Grid mit `<br>`-getrennten
    Inline-Facts; `_datenzeilen()` findet dort null Zeilen.
    """
    nowcast_html, _ = _nowcast_mail()
    amtlich_html = _amtliche_mail()

    nowcast_zeilen = _datenzeilen(nowcast_html)
    assert nowcast_zeilen, (
        "Vorbild verloren: die Nowcast-Mail traegt keine Datenzeile in der "
        "Tabellen-Bauform mehr — dann misst dieser Test nichts mehr."
    )

    amtlich_zeilen = _datenzeilen(amtlich_html)
    assert amtlich_zeilen, (
        "Amtliche Warn-Mail traegt keine einzige Datenzeile in der Nowcast-Bauform "
        f"(<table role=presentation>, Label links / Wert rechts). Nowcast zum "
        f"Vergleich: {nowcast_zeilen!r}"
    )

    werte = " | ".join(w for _, w in amtlich_zeilen)
    assert "Gewitter" in werte, f"Gefahrenart steht in keiner Datenzeile: {amtlich_zeilen!r}"
    assert _WOCHENTAG_DATUM_RE.search(werte), (
        f"Gueltigkeitsfenster steht in keiner Datenzeile: {amtlich_zeilen!r}"
    )
    assert "Segment 3" in werte, f"Ortsbezug steht in keiner Datenzeile: {amtlich_zeilen!r}"
    assert QUELLE in werte, f"Quelle steht in keiner Datenzeile: {amtlich_zeilen!r}"


# ---------------------------------------------------------------------------
# AC-9 — Bewahrungs-AC, heute gruen: die Warnstufe bleibt eine SKALA
# ---------------------------------------------------------------------------
def test_ac9_warnstufe_bleibt_eine_skala_und_wird_kein_einzelwort():
    """AC-9 (Bewahrungs-AC, heute gruen): Given eine amtliche Warnung der Stufe
    GELB / When die Mail gerendert wird / Then ist die Warnstufe weiterhin als
    Skala erkennbar — alle drei Stufenbezeichnungen plus die Einordnung
    „niedrigste von drei" — und nicht auf ein einzelnes Wort reduziert.

    Muss den Umbau ueberleben: die Skala traegt eine Einordnung, die eine blosse
    Wortangabe verliert (Spec, „Gemeinsamer Mail-Aufbau (A2)").
    """
    text = _text(_amtliche_mail())
    for wort in ("GELB", "ORANGE", "ROT"):
        assert wort in text, f"Stufenbezeichnung {wort!r} fehlt — Skala verloren: {text!r}"
    assert "niedrigste von drei" in text, (
        f"Einordnung 'niedrigste von drei' fehlt -- Skala auf ein Wort reduziert: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-10 — Bewahrungs-AC, heute gruen: keine Information geht verloren
# ---------------------------------------------------------------------------
def test_ac10_umbau_verliert_keine_der_vier_pflichtangaben():
    """AC-10 (Bewahrungs-AC, heute gruen): Given eine amtliche Warnung / When
    die Mail gerendert wird / Then enthaelt sie unveraendert Gefahrenart,
    Gueltigkeitsfenster, Ortsbezug und Quelle.

    Jede Angabe wird EINZELN nachgewiesen (die Spec verlangt genau das), und
    zwar am sichtbaren Text der gerenderten Mail — unabhaengig davon, in
    welchem Baustein sie nach dem Umbau sitzt. Die beiden Literale „Quelle:"
    und „abgerufen bei" sind zusaetzlich vom Warn-Mail-Waechter (P-4)
    vorgeschrieben und stehen deshalb mit im Nachweis.
    """
    text = _text(_amtliche_mail())
    assert "Gewitter" in text, f"Gefahrenart fehlt: {text!r}"
    assert _WOCHENTAG_DATUM_RE.search(text), f"Gueltigkeitsfenster ohne Datum: {text!r}"
    assert "15:00" in text and "21:00" in text, f"Gueltigkeits-Zeiten fehlen: {text!r}"
    assert "Segment 3" in text, f"Ortsbezug fehlt: {text!r}"
    assert QUELLE in text, f"Quelle fehlt: {text!r}"
    assert "Quelle:" in text, f"Pflicht-Literal 'Quelle:' fehlt (Waechter P-4): {text!r}"
    assert "abgerufen bei" in text, (
        f"Pflicht-Literal 'abgerufen bei' fehlt (Waechter P-4): {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-11 — Bewahrungs-AC, heute gruen: ADR-0033 bleibt gewahrt
# ---------------------------------------------------------------------------
def test_ac11_63_segmente_eine_warnung_nennt_nur_das_betroffene_segment():
    """AC-11 (Bewahrungs-AC, heute gruen): Given ein Trip mit 63 Segmenten und
    einer Warnung fuer 1 Segment / When die Mail gerendert wird / Then
    erscheinen weiterhin KEINE nicht betroffenen Segmente (ADR-0033).

    Gemessen am Wirkort: an der Mail, die der echte Trip-Pfad
    (`NotificationService.send_official_alert`) erzeugt — nicht an den
    Zwischen-DTOs. Der bestehende ADR-0033-Test
    (`test_official_alert_warn_section.py::test_ac11_trip_path_shows_only_
    affected_segment_chips`) prueft dieselbe Zusicherung an einer kleinen
    Route; dieser hier nimmt die in der Spec genannte grosse Route, in der ein
    Rueckfall auf ein Vollrouten-Gitter sofort sichtbar waere.
    """
    from app.config import Settings
    from app.trip import Stage, Trip, Waypoint
    from services.notification_service import NotificationService

    waypoints = [
        Waypoint(id=f"w{i}", name=f"P{i}", lat=46.6 + i * 0.001, lon=13.0 + i * 0.001,
                 elevation_m=1500.0)
        for i in range(64)  # 64 Wegpunkte -> 63 Segmente
    ]
    trip = Trip(
        id="tdd-1744-a2-adr33", name="KHW 403",
        stages=[Stage(id="s1", name="Tag 1", date=date(2026, 7, 11), waypoints=waypoints)],
    )
    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid", smtp_pass="x",
        mail_to="to@test.invalid",
    )
    zugestellt: list[str] = []
    NotificationService(settings, "tdd-1744-a2-adr33").send_official_alert(
        trip=trip, notices=[(_alert(), ["7"])], effective_channels={"email"},
        mail_sink=lambda subject, body: zugestellt.append(body),
        sms_sink=lambda text: None,
    )
    assert len(zugestellt) == 1, "Trip-Pfad hat keine Mail erzeugt"

    text = _text(zugestellt[0])
    genannt = {m.strip() for m in _SEGMENT_NENNUNG_RE.findall(text)}
    assert genannt == {"Segment 7"}, (
        f"ADR-0033 verletzt: die Mail nennt ausser dem betroffenen Segment weitere "
        f"Segmente {sorted(genannt)!r}. Text: {text!r}"
    )
    assert "übrige Strecke frei" not in text, f"ADR-0033: Vollrouten-Hinweis zurueck: {text!r}"
    assert "🏁 Ziel" not in text, f"ADR-0033: nicht betroffenes Ziel-Segment genannt: {text!r}"


# ---------------------------------------------------------------------------
# AC-12 — Bewahrungs-AC, heute gruen: ehrliche Sammelangabe im Betreff
# ---------------------------------------------------------------------------
def test_ac12_betreff_nennt_bei_gemischtem_umfang_mehrere_segmente():
    """AC-12 (Bewahrungs-AC, heute gruen): Given mehrere amtliche Warnungen mit
    VERSCHIEDENEM Umfang / When der Betreff gerendert wird / Then steht dort die
    ehrliche Sammelangabe „mehrere Segmente" und nicht ein einzelnes Segment
    (AC-3 der Warnmail-Spec #1248).

    Der Bestandstest `test_official_alert_subject_compact.py` deckt denselben
    Fall ab; dieser haelt die Zusicherung im Aenderungssatz von A2 fest, weil
    A2 den Mail-Koerper umbaut und dabei die Notice-Bildung mit anfasst.
    """
    from app.trip import Stage, Trip, Waypoint

    waypoints = [
        Waypoint(id=f"w{i}", name=f"P{i}", lat=46.6 + i * 0.01, lon=13.0 + i * 0.01,
                 elevation_m=1500.0)
        for i in range(6)
    ]
    trip = Trip(
        id="tdd-1744-a2-ac12", name="KHW 403",
        stages=[Stage(id="s1", name="Tag 1", date=date(2026, 7, 11), waypoints=waypoints)],
    )
    notices = build_official_alert_notices(trip, [
        (_alert(level=2, hazard="thunderstorm", label="Gewitter"), ["2"]),
        (_alert(level=3, hazard="extreme_heat", label="Hitze"), ["4"]),
    ])
    assert len(notices) == 2, f"Aufbau kaputt: {len(notices)} Warnungen statt 2"

    betreff = render_official_alert_subject(notices, prefix=trip.name, tz=UTC)
    assert "mehrere Segmente" in betreff, (
        f"Betreff nennt keine ehrliche Sammelangabe bei gemischtem Umfang: {betreff!r}"
    )
    assert "Segment 2" not in betreff and "Segment 4" not in betreff, (
        f"Betreff verallgemeinert den Umfang EINER Warnung auf alle: {betreff!r}"
    )
