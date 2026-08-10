"""TDD RED — Issue #1661 Teil B: der Δ-Anker des Ortsvergleichs traegt keinen
Tagesbezug, obwohl der Abend-Versand ueber MORGEN informiert.

SPEC: docs/specs/modules/fix_1661_anker_vom_falschen_tag.md — AC-7..AC-10.
(AC-1..AC-6/AC-11/AC-13..AC-15: test_alert_anchor_day_guard.py; AC-12/AC-16
sind Go.)

Der Defekt in einem Satz: ``send_one_compare_preset()`` kennt seit #1232 den
Tag, ueber den es informiert (Morgen-Slot → heute, Abend-Slot → heute+1), gibt
ihn aber nur an den Mail-Betreff weiter. Die Closure ``_anchor_and_reset()``
(``scheduler_dispatch_service.py:407-420``) reicht ihn NICHT an
``_write_compare_alert_snapshots()`` durch — der Δ-Anker eines Abend-Presets
beschreibt deshalb den SCHREIBTAG statt des gebriefeten Tages, waehrend der
15-Minuten-Frisch-Abruf am jeweils laufenden Tag bleibt.

Kern-Schicht, deterministisch (kein Netz, kein Versand), mock-frei: echter
Versandpfad ``send_one_compare_preset()``, echter ``CompareAlertService``,
echte ``CompareLocationWeatherSource``, Provider als echter Fake aus der
Registry. Die Spionage-Quelle ist eine echte Unterklasse des Prueflings, die
nach dem Mitschreiben an den echten Abrufweg delegiert.

Der Aufbau (``Szenario``, ``Wetterlage``, Uhr-Naht, Provider-Fake) wird bewusst
aus ``tests/tdd/test_compare_alert_day_window.py`` WIEDERVERWENDET statt
nachgebaut — derselbe Pruefling, dieselbe Fehlerfamilie; eine zweite Kopie
liefe auseinander.
"""
from __future__ import annotations

import inspect
import json
from datetime import timedelta

import pytest

from services.compare_location_weather_source import CompareLocationWeatherSource

from tests.helpers.alert_log_fixtures import settings_email_only
from tests.tdd.test_compare_alert_day_window import (
    ALPEN_LAT,
    ALPEN_LON,
    Szenario,
    flach,
)

# Petropawlowsk-Kamtschatski (Asia/Kamchatka, UTC+12) — ein Ort WEIT oestlich
# von UTC. Nur fuer den F002-Test: bei 18:00 UTC ist dort bereits 06:00 des
# FOLGETAGS, der ortslokale Kalendertag laeuft dem UTC-Tag also um einen
# vollen Tag voraus. In Mitteleuropa (ALPEN_*) faellt dieser Unterschied
# ausserhalb eines schmalen Nachtfensters gar nicht auf — genau deshalb war
# die UTC/Ortszeit-Vermischung dort unsichtbar.
KAMTSCHATKA_LAT, KAMTSCHATKA_LON = 53.0200, 158.6500


# ─────────────────────── Spionage-Quelle (kein Mock) ────────────────────────

class SpionierendeQuelle(CompareLocationWeatherSource):
    """Echte Unterklasse des Prueflings, die die Abruf-Argumente mitschreibt
    und danach an den echten Abrufweg delegiert.

    Die Delegation bindet sich per ``inspect.signature`` an die tatsaechliche
    Signatur der Basisklasse — derselbe Test trifft dadurch VOR und NACH dem
    Fix denselben Produktionscode, statt an einem ``TypeError`` zu scheitern.
    """

    def __init__(self) -> None:
        self.aufrufe: list[dict] = []

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              target_date=None, tage_ab_ortstag=None):
        self.aufrufe.append({
            "point_id": point_id,
            "start_hour": start_hour,
            "end_hour": end_hour,
            "target_date": target_date,
            "tage_ab_ortstag": tage_ab_ortstag,
        })
        parameter = inspect.signature(super().fetch).parameters
        zusatz = {}
        if "target_date" in parameter:
            zusatz["target_date"] = target_date
        if "tage_ab_ortstag" in parameter and tage_ab_ortstag is not None:
            zusatz["tage_ab_ortstag"] = tage_ab_ortstag
        return super().fetch(point_id, lat, lon, start_hour, end_hour, **zusatz)


# ──────────────────────────── Schritte am Szenario ──────────────────────────

def versand_mit_zieltag(sz: Szenario, lage, target_date, versatz,
                        ueberschreibung=None, heute=None):
    """Report-Versand ueber den ECHTEN Produktionspfad
    ``send_one_compare_preset()`` mit dem Tagesbezug des Slot-Schedulers
    (``compare_slot_scheduler.presets_due_for_hour``: Morgen-Slot → heute /
    Versatz 0, Abend-Slot → heute+1 / Versatz +1) — genau auf diesem Weg
    entsteht in Produktion der Δ-Anker. Transport ueber die ``*_sink``-Naehte,
    es geht nichts raus; ``official_alerts_enabled=False`` haelt den Pfad
    offline.

    ``versatz`` (#1661, Adversary-Finding F003): der Tagesbezug wird in BEIDEN
    Formen uebergeben, weil beide aus derselben Zeitabfrage des Slot-Schedulers
    stammen — absoluter Zieltag fuer Betreff/Engine, Versatz fuer den Anker.
    Nur eines von beiden zu uebergeben ist ein Programmierfehler und scheitert
    laut (s. ``test_f003_nur_eine_der_beiden_tagesangaben_scheitert_laut``).

    ``heute`` stellt den SYSTEMTAG des Dispatch-Loops
    (``dispatch_orchestrator.py`` → ``date.today()``, auf dem Server UTC).
    Ohne Angabe ist das ``sz.basis_tag`` — genau das Verhaeltnis, das in
    Produktion fuer Orte ohne nennenswerten UTC-Versatz gilt. Der Wert wird
    gestellt statt gelesen, damit der Test nicht nachts von selbst rot wird (in
    Mitteleuropa laeuft der Ortstag dem UTC-Tag ab 22 Uhr UTC voraus). Seit
    F003 darf er auf den Anker KEINE Wirkung mehr haben — der Systemtag geht
    dort nicht mehr ein.
    """
    import services.scheduler_dispatch_service as dispatch_mod
    from services.scheduler_dispatch_service import send_one_compare_preset

    systemtag = sz.basis_tag if heute is None else heute

    class _GestellterTag(dispatch_mod.date):
        @classmethod
        def today(cls):
            return systemtag

    sz._monkeypatch.setattr(dispatch_mod, "date", _GestellterTag)

    sz._stelle_wetter(lage)
    preset = {
        **sz.preset,
        "official_alerts_enabled": False,
        **(ueberschreibung or {}),
    }
    send_one_compare_preset(
        preset,
        settings_email_only(),
        sz.user_id,
        "data",
        target_date=target_date,
        tage_ab_ortstag=versatz,
        mail_sink=lambda *a, **k: None,
        sms_sink=lambda *a, **k: None,
        telegram_sink=lambda *a, **k: None,
    )


def gespeicherter_anker(sz: Szenario):
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    eintraege = CompareWeatherSnapshotService(user_id=sz.user_id).load(
        sz.preset_id, sz.location_id,
    )
    assert eintraege, (
        "Fixtur-Schutz: der Report-Versand hat gar keinen Δ-Anker geschrieben "
        "— der Anker-Schreibpfad wurde nicht durchlaufen, der Test bewacht "
        "nichts."
    )
    return eintraege[0]


def lauf_mit_spion(sz: Szenario, lage, stunde: int):
    """Ein vollstaendiger 15-Minuten-Alarm-Check zur Ortszeit ``stunde``, bei
    dem die Frisch-Abruf-Argumente mitgeschrieben werden."""
    from services.compare_alert import CompareAlertService

    spion = SpionierendeQuelle()
    sz._stelle_wetter(lage)
    sz._stelle_uhr(stunde)
    mails: list[tuple[str, str]] = []
    CompareAlertService(
        settings=settings_email_only(),
        user_id=sz.user_id,
        weather_source=spion,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    ).check_all_compare_presets()
    return spion, mails


def preset_fenster(sz: Szenario) -> tuple[int, int]:
    from services.report_config_resolver import resolve_compare_time_window

    return resolve_compare_time_window(sz.preset)


# ═════════════════════════════════ AC-7 ══════════════════════════════════════

def test_ac7_abendanker_traegt_den_gebriefeten_tag(monkeypatch, tmp_path):
    """AC-7 (Teil B — Abendanker traegt den gebriefeten Tag).

    GIVEN ein Ortsvergleich-Preset mit aktiviertem Abend-Slot (der
    Slot-Scheduler uebergibt dafuer ``target_date = heute+1``)
    WHEN der Abend-Report ueber den echten Versandpfad rausgeht und dabei den
    Δ-Anker schreibt
    THEN traegt der gespeicherte Δ-Anker ``target_date = heute+1`` — den Tag,
    ueber den das Briefing tatsaechlich informiert, NICHT den Schreibtag.

    HEUTE ROT: ``_write_compare_alert_snapshots`` bekommt ``target_date`` gar
    nicht durchgereicht, und ``PointWeatherData`` hat das Feld noch nicht —
    der Anker traegt keinerlei Tagesbezug.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    morgen = sz.basis_tag + timedelta(days=1)

    versand_mit_zieltag(sz, flach(sz), morgen, versatz=1)

    anker = gespeicherter_anker(sz)
    assert getattr(anker, "target_date", None) == morgen, (
        "AC-7: Der Abend-Anker muss den gebriefeten Tag tragen "
        f"({morgen.isoformat()}). Gefunden: "
        f"{getattr(anker, 'target_date', '<Feld existiert nicht>')!r}. "
        "Ohne Tagesbezug beschreibt der Anker den Schreibtag, waehrend das "
        "Briefing ueber morgen informiert hat."
    )


# ═════════════════════════════════ AC-8 ══════════════════════════════════════

def test_ac8_frisch_abruf_holt_denselben_tag_wie_der_anker(monkeypatch, tmp_path):
    """AC-8 (Teil B — Anker und Frisch-Abruf beschreiben denselben Tag).

    GIVEN einen Δ-Anker mit gesetztem ``target_date`` = morgen
    (Abend-Slot-Preset)
    WHEN der 15-Minuten-Alarm-Check noch am selben Kalendertag (heute) den
    Frisch-Abruf fuer diesen Ort holt
    THEN bezieht sich der Frisch-Abruf auf DENSELBEN Kalendertag wie der Anker
    — unabhaengig davon, welcher Tag beim Check gerade „heute" ist.

    HEUTE ROT: dem Frisch-Abruf wird kein ``target_date`` uebergeben, er
    bleibt am laufenden lokalen Tag. Anker (morgen) und Frisch-Abruf (heute)
    beschreiben zwei verschiedene Tage — Δ ohne jede Vorhersage-Aenderung.

    Dies ist die neu gefasste Zusicherung, die ``fix_1584c`` AC-5 ergaenzt
    (E3): nicht „beide bleiben am laufenden Tag", sondern „beide beschreiben
    DENSELBEN Tag — naemlich den, ueber den zuletzt gebrieft wurde".
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    morgen = sz.basis_tag + timedelta(days=1)

    versand_mit_zieltag(sz, flach(sz), morgen, versatz=1)
    spion, _mails = lauf_mit_spion(sz, flach(sz), 15)

    assert spion.aufrufe, (
        "Fixtur-Schutz: der Alarm-Check hat gar keinen Frisch-Abruf gemacht "
        "— der Test bewacht sonst nichts."
    )
    gesehen = [a["target_date"] for a in spion.aufrufe]
    assert gesehen == [morgen] * len(gesehen), (
        f"AC-8: Der Frisch-Abruf muss denselben Tag holen wie der Anker "
        f"({morgen.isoformat()}). Tatsaechlich uebergeben: {gesehen}. "
        "Anker und Frisch-Abruf beschreiben damit verschiedene Kalendertage, "
        "und der Δ-Vergleich misst den Tagesunterschied statt der "
        "Vorhersage-Aenderung."
    )


# ═════════════════════════════════ AC-9 ══════════════════════════════════════

def test_ac9_morgen_slot_anker_traegt_heute(monkeypatch, tmp_path):
    """AC-9, erste Haelfte (Teil B — Morgen-Slot traegt den laufenden Tag).

    GIVEN ein Ortsvergleich-Preset OHNE aktivierten Abend-Slot (der
    Produktiv-Regelfall: 4 von 5 Presets; der Slot-Scheduler uebergibt dafuer
    ``target_date = heute``)
    WHEN der Morgen-Report den Δ-Anker schreibt
    THEN traegt der Anker ``target_date = heute``.

    ⚠️ ABWEICHUNG VOM RED-BRIEFING, GEMELDET: das Briefing fuehrt AC-9 als
    „heute schon korrekt, Test bleibt gruen". Die freigegebene Spec verlangt
    hier aber ausdruecklich „Assert: gespeicherter Anker traegt
    ``target_date = heute``" — und dieses Feld gibt es heute gar nicht. Der
    Test ist damit HEUTE ROT, aus demselben Grund wie AC-7. Der
    Regressionsanteil von AC-9 („der nachfolgende Alarm-Check verhaelt sich
    exakt wie vor dieser Scheibe") steht als eigener, gruener Test darunter.
    Die Spec ist bindend, deshalb wurde nicht umgedeutet.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)

    versand_mit_zieltag(sz, flach(sz), sz.basis_tag, versatz=0)

    anker = gespeicherter_anker(sz)
    assert getattr(anker, "target_date", None) == sz.basis_tag, (
        "AC-9: Der Morgen-Anker muss den laufenden Tag tragen "
        f"({sz.basis_tag.isoformat()}). Gefunden: "
        f"{getattr(anker, 'target_date', '<Feld existiert nicht>')!r}."
    )


def test_ac9_regression_morgen_slot_frisch_abruf_bleibt_am_laufenden_tag(
    monkeypatch, tmp_path
):
    """AC-9, zweite Haelfte (REGRESSIONSSCHUTZ — heute korrektes Verhalten).

    GIVEN denselben Morgen-Slot-Aufbau (``target_date = heute``)
    WHEN der nachfolgende Alarm-Check laeuft
    THEN verhaelt er sich exakt wie vor dieser Scheibe: das Abruf-Fenster ist
    das aufgeloeste Preset-Fenster, und der Frisch-Abruf wird NICHT auf einen
    anderen Kalendertag verschoben.

    Dieser Test ist HEUTE GRUEN und soll es bleiben. Er bewacht genau die
    Nebenwirkung, die Teil B haben koennte: dass der neue Tagesbezug auch
    Morgen-Slot-Presets (4 von 5 in Produktion) auf einen anderen Tag zieht.
    Zugelassen ist deshalb ausschliesslich „kein Tagesbezug" (Bestand) oder
    „der laufende lokale Tag" (nach dem Fix) — ``heute+1`` waere rot.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)

    versand_mit_zieltag(sz, flach(sz), sz.basis_tag, versatz=0)
    spion, _mails = lauf_mit_spion(sz, flach(sz), 15)

    assert spion.aufrufe, "Fixtur-Schutz: kein Frisch-Abruf gelaufen."
    gesehen = [a["target_date"] for a in spion.aufrufe]
    assert all(t in (None, sz.basis_tag) for t in gesehen), (
        "AC-9: Ein Morgen-Slot-Preset darf den Frisch-Abruf NICHT auf einen "
        f"anderen Kalendertag ziehen. Erwartet: kein Tagesbezug oder "
        f"{sz.basis_tag.isoformat()}. Tatsaechlich: {gesehen}."
    )
    fenster = [(a["start_hour"], a["end_hour"]) for a in spion.aufrufe]
    assert fenster == [preset_fenster(sz)] * len(fenster), (
        "AC-9: Das Abruf-Fenster muss unveraendert das aufgeloeste "
        f"Preset-Fenster {preset_fenster(sz)} sein. Tatsaechlich: {fenster}."
    )


# ════════════════════════════════ AC-10 ══════════════════════════════════════

def test_ac10_regression_altbestand_ohne_target_date_bleibt_unveraendert(
    monkeypatch, tmp_path
):
    """AC-10 (REGRESSIONSSCHUTZ — Altbestand ohne ``target_date``).

    GIVEN einen Compare-Δ-Anker aus der Zeit VOR dieser Scheibe: eine Datei
    ohne ``target_date``-Schluessel (im gemessenen Produktivbestand sind das
    alle acht Anker des aktiven Presets)
    WHEN der Alarm-Check ihn laedt
    THEN wird ``target_date`` als ``None`` gelesen, es kracht nicht, und der
    Frisch-Abruf verhaelt sich exakt wie heute (laufender lokaler Tag,
    unveraendertes Preset-Fenster) — keine Migration noetig.

    Dieser Test ist HEUTE GRUEN und soll es bleiben.

    Die Fixture entsteht ueber den echten Schreibweg und wird danach gezielt
    um den Schluessel erleichtert. So ist garantiert, dass der Schluessel
    FEHLT (und nicht nur zufaellig ``null`` ist) und der Rest der Datei
    trotzdem echt bleibt.
    """
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    versand_mit_zieltag(sz, flach(sz), sz.basis_tag, versatz=0)

    dienst = CompareWeatherSnapshotService(user_id=sz.user_id)
    pfad = dienst._path(sz.preset_id, sz.location_id)
    daten = json.loads(pfad.read_text())
    daten.pop("target_date", None)
    pfad.write_text(json.dumps(daten, indent=2))
    assert "target_date" not in json.loads(pfad.read_text()), "Fixtur-Schutz"

    eintraege = dienst.load(sz.preset_id, sz.location_id)
    assert eintraege, (
        "AC-10: Ein Altbestands-Anker ohne target_date muss weiterhin lesbar "
        "sein — kein Fehler, keine Migration."
    )
    assert getattr(eintraege[0], "target_date", None) is None, (
        "AC-10: Fehlt der Schluessel, muss target_date als None gelesen "
        f"werden. Gefunden: {getattr(eintraege[0], 'target_date', None)!r}."
    )

    spion, _mails = lauf_mit_spion(sz, flach(sz), 15)
    assert spion.aufrufe, "Fixtur-Schutz: kein Frisch-Abruf gelaufen."
    gesehen = [a["target_date"] for a in spion.aufrufe]
    assert gesehen == [None] * len(gesehen), (
        "AC-10: Ohne Anker-Tagesbezug muss der Frisch-Abruf ohne Tagesbezug "
        f"laufen (Bestandsverhalten). Tatsaechlich uebergeben: {gesehen}."
    )
    fenster = [(a["start_hour"], a["end_hour"]) for a in spion.aufrufe]
    assert fenster == [preset_fenster(sz)] * len(fenster), (
        "AC-10: Das Abruf-Fenster muss unveraendert das aufgeloeste "
        f"Preset-Fenster {preset_fenster(sz)} sein. Tatsaechlich: {fenster}."
    )


# ══════════ Adversary-Finding F001 (Tages-Parameter ohne Default) ════════════

def test_f001_tages_parameter_des_ankerschreibers_hat_keinen_default():
    """Bewacht Adversary-Finding F001 (MEDIUM).

    GIVEN den Δ-Anker-Schreiber ``_write_compare_alert_snapshots``
    WHEN man seine Signatur betrachtet bzw. ihn ohne den Tages-Parameter
    aufruft
    THEN hat der Parameter KEINEN Default und der Aufruf scheitert sofort mit
    ``TypeError``.

    Warum das nicht ueber das Verhalten pruefbar ist: es gibt genau EINEN
    Produktiv-Aufrufer, und der uebergibt das Argument. Fuehrt man einen
    Default ein (``= None`` mit stillem Rueckfall auf „heute"), bleibt jeder
    Verhaltenstest gruen — der Adversary hat genau das vorgefuehrt und KEIN
    Test wurde rot. Der Schutz ist strukturell gemeint: er bewacht KUENFTIGE
    Aenderungen, die das Argument vergessen. Ohne ihn faellt der Anker still
    auf den Schreibtag zurueck, statt laut zu scheitern — dieselbe
    Fehlerklasse wie der stille Parameter-Rueckfall, den diese Scheibe behebt.

    Vorbild ist der bereits pflichtige ``preset``-Parameter aus #1169
    (``test_compare_alert_day_window.py::test_f001_versandpfad_reicht_das_
    preset_fenster_an_den_anker_durch``), dessen Pflichtigkeit dieselbe
    Begruendung traegt.
    """
    from services.scheduler_dispatch_service import _write_compare_alert_snapshots

    parameter = inspect.signature(_write_compare_alert_snapshots).parameters
    assert "tage_ab_ortstag" in parameter, (
        "F001: `_write_compare_alert_snapshots` muss den Tages-Parameter "
        f"`tage_ab_ortstag` fuehren. Gefunden: {list(parameter)}."
    )
    assert parameter["tage_ab_ortstag"].default is inspect.Parameter.empty, (
        "F001: `tage_ab_ortstag` darf KEINEN Default haben — mit Default "
        "faellt ein vergessenes Argument still auf den Schreibtag zurueck, "
        "statt sofort zu scheitern. Gefunden: "
        f"{parameter['tage_ab_ortstag'].default!r}."
    )

    with pytest.raises(TypeError):
        # Bewusst mit leerer Ortsliste: haette der Parameter einen Default,
        # liefe der Aufruf hier folgenlos durch — genau das soll er nicht.
        _write_compare_alert_snapshots("preset-x", [], "user-x", {})


# ══════ Adversary-Finding F004 (Durchreichungsweg: Defaults verboten) ════════

def test_f004_tages_parameter_des_versandschritts_hat_keinen_default():
    """Bewacht Adversary-Finding F004 (MEDIUM) — dieselbe Zusicherung wie F001,
    eine Stufe frueher im Durchreichungsweg.

    GIVEN den Versandschritt ``_dispatch_due_preset``, der den Tagesversatz vom
    Faelligkeits-Tripel an ``send_one_compare_preset`` weitergibt
    WHEN man seine Signatur betrachtet bzw. ihn ohne den Tages-Parameter
    aufruft
    THEN ist der Parameter keyword-only, hat KEINEN Default, und der Aufruf
    scheitert sofort mit ``TypeError``.

    Warum strukturell und nicht ueber das Verhalten: es gibt genau EINEN
    Produktiv-Aufrufer (``CompareDispatchStrategy.dispatch_one``), und der
    uebergibt das Argument. Der Adversary hat hier einen stillen Default ``= 0``
    eingefuehrt — KEINE der geprueften Testdateien wurde rot, obwohl der Δ-Anker
    damit wieder den Schreibtag statt des gebriefeten Tages truege. Der
    Entweder-beide-oder-keines-Waechter in ``send_one_compare_preset`` faengt
    das NICHT: er prueft nur, ob beide Angaben ``None`` sind — ein Versatz 0
    neben einem Zieltag ``heute+1`` ist fuer ihn widerspruchsfrei.

    Keyword-only gehoert zur Zusicherung: als positionaler Parameter koennte
    ein kuenftiger Aufrufer ihn an die falsche Stelle schieben, ohne dass der
    Fehler laut wird.
    """
    from datetime import date as _date

    from services.scheduler_dispatch_service import _dispatch_due_preset

    parameter = inspect.signature(_dispatch_due_preset).parameters
    assert "tage_ab_ortstag" in parameter, (
        "F004: `_dispatch_due_preset` muss den Tages-Parameter "
        f"`tage_ab_ortstag` fuehren. Gefunden: {list(parameter)}."
    )
    assert parameter["tage_ab_ortstag"].default is inspect.Parameter.empty, (
        "F004: `tage_ab_ortstag` darf KEINEN Default haben — mit Default "
        "faellt ein vergessenes Argument still auf den Schreibtag zurueck, "
        "statt sofort zu scheitern. Gefunden: "
        f"{parameter['tage_ab_ortstag'].default!r}."
    )
    assert parameter["tage_ab_ortstag"].kind is inspect.Parameter.KEYWORD_ONLY, (
        "F004: `tage_ab_ortstag` muss keyword-only bleiben, damit er an der "
        "Aufrufstelle benannt ist. Gefunden: "
        f"{parameter['tage_ab_ortstag'].kind!s}."
    )

    with pytest.raises(TypeError):
        # Bewusst inert: leeres Preset, `settings=None` -> der Empfaenger-Check
        # in `send_one_compare_preset` wirft sofort ValueError, die
        # `_dispatch_due_preset` faengt. Haette der Parameter einen Default,
        # liefe der Aufruf also folgenlos durch (Rueckgabe False) statt zu
        # scheitern — genau das soll er nicht.
        _dispatch_due_preset({}, _date(2026, 1, 1), None, "user-x", "data", [])


def test_f004_faelligkeits_tripel_traegt_keine_default_tagesangaben():
    """Bewacht dieselbe Fehlerklasse an der QUELLE des Tagesbezugs.

    GIVEN ``DuePreset`` — das Tripel, in dem der Slot-Scheduler den Tagesbezug
    EINMAL bildet und in beiden Formen weiterreicht
    WHEN man es ohne den Tagesversatz erzeugt
    THEN scheitert das sofort mit ``TypeError``; keines der beiden Tagesfelder
    hat einen Default.

    Ein NamedTuple-Feld-Default (``tage_ab_ortstag: int = 0``) ist dieselbe
    stille Falle eine Stufe hoeher: heute baut nur ``_due()`` das Tripel und
    uebergibt vollstaendig positional, es wuerde also kein einziger Test rot.
    Ein kuenftiger zweiter Bauplatz — etwa ein Sonderslot — bekaeme damit
    schweigend „Versatz 0" und schriebe den Abendanker wieder auf den
    laufenden Tag. Fuer den Bauplatz ``_due()`` selbst gilt dasselbe: beide
    Mutationen wurden vorgefuehrt, keine machte einen der bestehenden Tests
    rot.
    """
    from datetime import date as _date

    from services.compare_slot_scheduler import DuePreset, _due

    versatz = inspect.signature(_due).parameters["tage_ab_ortstag"]
    assert versatz.default is inspect.Parameter.empty, (
        "F004: `_due` baut das Tripel aus dem Versatz — mit Default erzeugt "
        "ein Aufrufer, der ihn vergisst, still einen Morgen-Slot-Eintrag. "
        f"Gefunden: {versatz.default!r}."
    )

    defaults = getattr(DuePreset, "_field_defaults", {})
    for feld in ("target_date", "tage_ab_ortstag"):
        assert feld in DuePreset._fields, (
            f"F004: `DuePreset` muss das Feld `{feld}` fuehren. Gefunden: "
            f"{DuePreset._fields}."
        )
        assert feld not in defaults, (
            f"F004: `DuePreset.{feld}` darf KEINEN Default haben — sonst "
            "erzeugt ein unvollstaendiger Bauplatz still einen falschen "
            f"Tagesbezug. Gefunden: {defaults.get(feld)!r}."
        )

    with pytest.raises(TypeError):
        DuePreset({}, _date(2026, 1, 1))


# ═════════════ Adversary-Finding F002 (UTC-Tag vs. Ortstag) ══════════════════

def test_f002_abendanker_folgt_dem_ortstag_nicht_dem_utc_tag(monkeypatch, tmp_path):
    """Bewacht Adversary-Finding F002 (MEDIUM).

    GIVEN einen Ortsvergleich WEIT oestlich von UTC (Kamtschatka, UTC+12) und
    einen Abend-Slot, der um 18:00 UTC feuert — dort ist es zu diesem Zeitpunkt
    bereits 06:00 des FOLGETAGS, der Ortstag laeuft dem UTC-Tag also um einen
    vollen Tag voraus
    WHEN der Abend-Report ueber den echten Versandpfad rausgeht und dabei den
    Δ-Anker schreibt
    THEN beschreibt der Anker den ORTSLOKALEN Folgetag (``Ortstag + 1``) — den
    Tag, ueber den das Abend-Briefing informiert.

    Warum dieser Test existiert: der Dispatch-Loop bildet seinen Zieltag aus
    ``date.today()`` (``dispatch_orchestrator.py:120``, Systemzeit = UTC auf
    diesem Server). Reicht man diesen ABSOLUTEN Tag bis in ``fetch()`` durch,
    verdraengt er dort den ortslokal gebildeten Tag — und trifft fuer jeden Ort
    ab UTC+6 den LAUFENDEN statt den naechsten Ortstag. Das ist derselbe
    Fehler, den diese Scheibe behebt, nur an einer anderen Stelle wieder
    eingebaut. In Mitteleuropa faellt er nicht auf, weil UTC-Tag und Ortstag
    dort fast immer uebereinstimmen — das ist Glueck, keine Absicherung.

    Der Tag wird deshalb RELATIV weitergereicht (Morgen-Slot 0, Abend-Slot +1)
    und erst in ``fetch()`` gegen den Ortstag aufgeloest.
    """
    sz = Szenario(monkeypatch, tmp_path, KAMTSCHATKA_LAT, KAMTSCHATKA_LON)
    # 06:00 Ortszeit am Ortstag == 18:00 UTC des VORTAGS (UTC+12).
    sz._stelle_uhr(6)
    utc_tag = sz.basis_tag - timedelta(days=1)
    # Genau das, was `presets_due_for_hour(presets, 18, date.today())` fuer den
    # Abend-Slot liefert: UTC-heute + 1 Tag.
    slot_zieltag = utc_tag + timedelta(days=1)

    versand_mit_zieltag(sz, flach(sz), slot_zieltag, versatz=1, heute=utc_tag)

    anker = gespeicherter_anker(sz)
    erwartet = sz.basis_tag + timedelta(days=1)
    assert getattr(anker, "target_date", None) == erwartet, (
        "F002: Der Abendanker eines Ortes bei UTC+12 muss den ortslokalen "
        f"FOLGETAG tragen ({erwartet.isoformat()}). Gefunden: "
        f"{getattr(anker, 'target_date', '<Feld existiert nicht>')!r}. "
        f"Der UTC-basierte Slot-Zieltag ist {slot_zieltag.isoformat()} und "
        f"damit der LAUFENDE Ortstag ({sz.basis_tag.isoformat()}) — wird er "
        "unveraendert durchgereicht, beschreibt der Anker den heutigen statt "
        "den gebriefeten Tag."
    )


def test_f002_absoluter_tag_und_versatz_zugleich_scheitern_laut(monkeypatch, tmp_path):
    """Bewacht die zweite Haelfte von F002: die beiden Wege duerfen sich nie
    still ueberstimmen.

    GIVEN einen Aufruf der Wetterquelle, der BEIDE Tages-Angaben setzt — den
    absoluten Tag (Leseseite, Δ-Check) und den Versatz gegen den Ortstag
    (Schreibseite, Anker)
    WHEN ``fetch()`` laeuft
    THEN scheitert er sofort mit ``ValueError``, statt einen der beiden Wege
    stillschweigend gewinnen zu lassen.

    Genau diese stille Vorfahrt war der Fehler: der absolute (UTC-)Tag hat den
    ortslokal gebildeten verdraengt, ohne dass irgendwo etwas aufgefallen
    waere. Zwei Wahrheiten ueber denselben Kalendertag sind ein
    Programmierfehler und muessen laut sein.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    sz._stelle_wetter(flach(sz))
    quelle = CompareLocationWeatherSource()

    with pytest.raises(ValueError) as fehler:
        quelle.fetch(
            sz.location_id, sz.lat, sz.lon, 4, 19,
            target_date=sz.basis_tag, tage_ab_ortstag=1,
        )
    assert "tage_ab_ortstag" in str(fehler.value), (
        "Die Meldung muss beide Wege benennen, sonst sucht der naechste "
        f"Leser an der falschen Stelle. Gefunden: {fehler.value}"
    )


# ════ Adversary-Finding F003 (Tagessprung zwischen Sammeln und Schreiben) ════

def _settings_ohne_versandweg():
    """Sendefaehig konfigurierter Empfaenger, aber KEIN funktionsfaehiger
    Kanal: der echte ``EmailOutput``-Guard wirft seinen echten
    ``OutputConfigError``, ohne je eine Verbindung aufzubauen. Muster aus
    ``test_compare_briefing_anchor_survives_dispatch_failure.py``.

    Alle Transport-Felder ausdruecklich leer (#1477 — sonst zieht
    ``Settings()`` still die Prod-``.env`` und es ginge echt etwas raus).
    Der Δ-Anker wird seit #1629 in BEIDEN Zweigen geschrieben (Erfolg wie
    Versandfehler), der Nachweis haengt also nicht am Versand-Ausgang.
    """
    from app.config import Settings

    settings = Settings(
        smtp_host="", smtp_user="", smtp_pass="",
        mail_to="tdd-1661@example.invalid",
        telegram_bot_token="", telegram_chat_id="",
        telegram_test_bot_token="", telegram_test_chat_id="",
        sms_gateway_url="", seven_api_key="", sms_to="",
    )
    assert settings.can_send_email() is False, "Vorbedingung: kein echter Versand"
    assert settings.can_send_telegram() is False, "Sicherung (#1477)"
    assert settings.can_send_sms() is False, "Sicherung (#1477)"
    return settings


def _abend_preset_auf_platte(sz: Szenario) -> dict:
    """Schreibt das Szenario-Preset mit AKTIVEM ABEND-SLOT (18:00) dorthin, wo
    der Dispatch-Loop es liest, und gibt dasselbe Dict zurueck."""
    from app.loader import get_data_root

    from tests.helpers.compare_briefings import write_compare_briefings

    preset = {
        **sz.preset,
        "morning_enabled": False,
        "morning_time": "06:00:00",
        "evening_enabled": True,
        "evening_time": "18:00:00",
        "official_alerts_enabled": False,
    }
    write_compare_briefings(get_data_root() / "users" / sz.user_id, [preset])
    return preset


def _stelle_systemtag(monkeypatch, modul, tag) -> None:
    """Stellt den Systemtag (``date.today()``), den ``modul`` sieht."""
    import datetime as datetime_mod

    class _GestellterTag(datetime_mod.date):
        @classmethod
        def today(cls):
            return tag

    monkeypatch.setattr(modul, "date", _GestellterTag)


@pytest.mark.parametrize(
    "systemtag_versatz",
    [
        pytest.param(1, id="mitternacht-dazwischen"),
        pytest.param(-40, id="systemtag-weit-zurueck"),
        pytest.param(400, id="systemtag-weit-voraus"),
    ],
)
def test_f003_tagessprung_zwischen_sammeln_und_schreiben_verschiebt_den_anker_nicht(
    monkeypatch, tmp_path, systemtag_versatz,
):
    """Bewacht Adversary-Finding F003 (HIGH).

    GIVEN ein Ortsvergleich-Preset mit aktivem Abend-Slot (18:00), dessen
    Faelligkeit zum Zeitpunkt T1 gesammelt wurde, als der Systemtag noch Tag D
    war (``presets_due_for_hour(..., today=D)`` → Zieltag D+1)
    WHEN das Preset erst zum spaeteren Zeitpunkt T2 tatsaechlich geschrieben
    wird — nach eigenem Wetterabruf, Rendering und der 2-Sekunden-Warteschlange
    je vorangehendem Preset — und dazwischen Mitternacht gefallen ist, der
    Systemtag also auf D+1 steht, waehrend die ORTSZEIT am Ort noch auf Tag D
    laeuft
    THEN traegt der geschriebene Δ-Anker trotzdem den gebriefeten Tag D+1.

    HEUTE ROT: der Versatz wird als ``(target_date - date.today()).days``
    gebildet, also aus ZWEI ``date.today()``-Auswertungen zu ZWEI
    verschiedenen Realzeitpunkten. Nach dem Tagessprung ergibt die Differenz
    0 statt +1, und der Anker beschreibt still den laufenden statt den
    gebriefeten Tag — exakt die Fehlerklasse, die diese Scheibe behebt.

    Der Lauf geht ueber den ECHTEN Orchestrator-Adapter
    (``CompareDispatchStrategy.dispatch_one``) mit einem Faelligkeits-Eintrag
    aus dem ECHTEN Slot-Scheduler — die gesamte Durchreich-Kette
    (``presets_due_for_hour`` → ``dispatch_one`` → ``_dispatch_due_preset`` →
    ``send_one_compare_preset`` → ``_write_compare_alert_snapshots`` →
    ``fetch()``) laeuft dabei scharf. Reisst sie an irgendeiner Stelle,
    entsteht gar kein Anker und der Fixtur-Schutz in
    ``gespeicherter_anker()`` schlaegt an.

    Die drei Faelle sind der NACHWEIS der Unabhaengigkeit, nicht drei
    Varianten desselben Falls: der Systemtag des Schreibpfads wird um +1, -40
    und +400 Tage verstellt. Der Anker muss in ALLEN dreien denselben Tag
    tragen — er haengt damit nachweislich an keiner zweiten
    ``date.today()``-Auswertung mehr, sondern nur noch am durchgereichten
    Slot-Versatz und am Ortstag.
    """
    import services.scheduler_dispatch_service as dispatch_mod
    from app.loader import get_data_root
    from services.compare_slot_scheduler import presets_due_for_hour
    from services.dispatch_orchestrator import CompareDispatchStrategy

    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    tag_d = sz.basis_tag
    morgen = tag_d + timedelta(days=1)
    preset = _abend_preset_auf_platte(sz)

    sz._stelle_wetter(flach(sz))
    # Die ORTSZEIT bleibt auf Tag D stehen (12:00) — der Ort hat die
    # Mitternacht noch vor sich.
    sz._stelle_uhr(12)

    # T1 — Sammelzeitpunkt: der Systemtag ist Tag D, der Abend-Slot briefed
    # ueber D+1. Exakt das, was `CompareDispatchStrategy.collect_due()` mit
    # `date.today() == D` liefert.
    faellig = presets_due_for_hour([preset], hour=18, today=tag_d)
    assert len(faellig) == 1, (
        "Fixtur-Schutz: der Abend-Slot muss zur Stunde 18 faellig sein, sonst "
        f"bewacht der Test nichts. Gefunden: {faellig!r}"
    )

    # T2 — Schreibzeitpunkt: zwischen T1 und hier ist Mitternacht gefallen,
    # der Systemtag des Schreibpfads steht woanders als beim Sammeln.
    _stelle_systemtag(
        monkeypatch, dispatch_mod, tag_d + timedelta(days=systemtag_versatz),
    )

    CompareDispatchStrategy(
        _settings_ohne_versandweg(), sz.user_id, str(get_data_root()),
    ).dispatch_one(faellig[0])

    anker = gespeicherter_anker(sz)
    assert getattr(anker, "target_date", None) == morgen, (
        "F003: Der Abend-Anker muss den gebriefeten Tag tragen "
        f"({morgen.isoformat()}), auch wenn zwischen Faelligkeits-Sammlung "
        "und Anker-Schreiben Mitternacht faellt. Gefunden: "
        f"{getattr(anker, 'target_date', '<Feld existiert nicht>')!r} — der "
        "Versatz wurde aus einer ZWEITEN Zeitabfrage rekonstruiert statt von "
        "der Stelle uebernommen, die ihn kennt (Morgen-Slot 0, Abend-Slot +1)."
    )


@pytest.mark.parametrize(
    "zusatz",
    [
        pytest.param({"target_date": True}, id="nur-zieltag"),
        pytest.param({"tage_ab_ortstag": True}, id="nur-versatz"),
    ],
)
def test_f003_nur_eine_der_beiden_tagesangaben_scheitert_laut(
    monkeypatch, tmp_path, zusatz,
):
    """Bewacht die zweite Haelfte von F003: kein Rest-Zeitfenster.

    GIVEN einen Aufruf des Versandpfads, der NUR EINE der beiden zusammen-
    gehoerigen Tagesangaben setzt — entweder den absoluten Zieltag oder den
    Versatz gegen den Ortstag
    WHEN ``send_one_compare_preset`` laeuft
    THEN scheitert er sofort mit ``ValueError``, statt die fehlende Angabe aus
    einer zweiten ``date.today()``-Auswertung nachzurechnen.

    Genau diese Nachrechnung war F003. Wuerde sie irgendwo wieder eingefuehrt
    (als Bequemlichkeit fuer einen Aufrufer, der nur den Zieltag hat), waere
    der stille Tagesversatz zurueck. Der Fehler muss laut sein, damit ein
    kuenftiger Aufrufer den Versatz von der Stelle holt, die ihn kennt.
    """
    from services.scheduler_dispatch_service import send_one_compare_preset

    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    sz._stelle_wetter(flach(sz))
    argumente: dict = {}
    if zusatz.get("target_date"):
        argumente["target_date"] = sz.basis_tag + timedelta(days=1)
    if zusatz.get("tage_ab_ortstag"):
        argumente["tage_ab_ortstag"] = 1

    with pytest.raises(ValueError) as fehler:
        send_one_compare_preset(
            {**sz.preset, "official_alerts_enabled": False},
            settings_email_only(),
            sz.user_id,
            "data",
            mail_sink=lambda *a, **k: None,
            sms_sink=lambda *a, **k: None,
            telegram_sink=lambda *a, **k: None,
            **argumente,
        )
    text = str(fehler.value)
    assert "target_date" in text and "tage_ab_ortstag" in text, (
        "Die Meldung muss BEIDE Angaben benennen, sonst weiss der naechste "
        f"Aufrufer nicht, was er mitzugeben hat. Gefunden: {text}"
    )
