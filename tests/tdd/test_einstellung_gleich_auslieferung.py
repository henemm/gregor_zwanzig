"""TDD RED — Invarianten-Test "Einstellung = Auslieferung" (Issue #2422 S1).

SPEC: docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md (AC-1..AC-14)
Kontext: docs/context/fix-2422-konfig-auslieferung-testluecken.md

Kernidee: fuer die waehlbaren Metriken x sechs Ausgabe-Formen wird geprueft,
ob das, was im gespeicherten Golden-Trip-JSON steht, tatsaechlich am
Transport ankommt -- Einstieg ueber das Persistenzformat des Editors, echter
Loader/Kaskade/Formatter, Naht ausschliesslich an den Transport-Klassen
(``tests/helpers/transport_mitschrift.py``). Jede bestehende Abweichung wird
ueber das Ausnahme-Register (``tests/helpers/einstellung_auslieferung_orakel.py
::AUSNAHMEN``) sichtbar gemacht statt stillschweigend grün durchgewunken.

RED-Charakter: ``AUSNAHMEN`` ist waehrend TDD RED (/40) LEER -- /50 befuellt
sie mit den durch die zwei Goldens tatsaechlich ausgeloesten Befunden B1/B2/
B3/B5 + der strukturellen Telegram-7er-Ausnahme (gust). Erwartet ROT: der
Hauptmatrix-Test, AC-2, AC-4 (Toleranzteil), AC-6, AC-10 (alle haengen an
einem BEFUELLTEN Register). AC-1/AC-7/AC-8/AC-9/AC-11/AC-12/AC-13 sind reine
Test-Maschinerie und laufen bereits jetzt gruen.

Kein ``Mock()``/``patch()``/``MagicMock`` -- Loader, Kaskade und Formatter
laufen echt; die einzige Naht ist der geteilte Transport-Aufzeichner.
"""
from __future__ import annotations

import json

import pytest

from tests.helpers.einstellung_auslieferung_orakel import (
    AUSNAHMEN,
    AusnahmeEintrag,
    RegisterValidierungsFehler,
    abweichungen_fuer_golden,
    alle_waehlbaren_metrik_ids,
    erreichbare_kanaele,
    erwartete_kaskade,
    hat_roh_einfach_dimension,
    KANAELE,
    parse_kanal,
    register_validieren,
    roh_wert_der_metrik,
    rote_zellen_beide_goldens,
    rote_zellen_fuer_golden,
    veraltete_eintraege,
)
from tests.helpers.erwartungsdateien_erzeugen import (
    _REITER_ZU_ORAKEL_KANAL,
    REPORT_TYPE as ANZEIGE_REPORT_TYPE,
)
from tests.tdd._einstellung_auslieferung_fixtures import (
    GOLDEN_DIR,
    golden_dict,
    render_golden,
)

pytestmark = pytest.mark.filterwarnings("ignore")


def _render_beide(monkeypatch_a, monkeypatch_b):
    ga = golden_dict("golden_a")
    mit_a, _trip_a = render_golden(monkeypatch_a, "golden_a")
    gb = golden_dict("golden_b")
    mit_b, _trip_b = render_golden(monkeypatch_b, "golden_b")
    return ga, mit_a, gb, mit_b


# ═══════════════════════════ Hauptmatrix-Test ═══════════════════════════════


def test_hauptmatrix_einstellung_gleich_auslieferung(monkeypatch):
    """Kernfrage des PO: kommt an, was eingestellt wurde?

    Given beide Golden-Trip-JSONs (identisches Roster/Layout, nur die
    Versand-Schalter unterscheiden sich) ueber den echten Loader eingelesen
    und ueber den echten Formatter + NotificationService versendet (Naht nur
    am Transport).
    When die Matrix ueber alle sechs Ausgabe-Formen laeuft.
    Then bleibt sie an JEDER Zelle gruen, die nicht durch einen begruendeten
    Register-Eintrag gedeckt ist -- rote Zellen OHNE Deckung sind die
    belegte Testluecken-Liste aus #2422.

    RED heute: ``AUSNAHMEN`` ist leer, die vier Produktabweichungen B1/B2/B3/
    B5 + die strukturelle Telegram-7er-Ausnahme sind ungedeckt.
    """
    ga, mit_a, gb, mit_b = _render_beide(monkeypatch, monkeypatch)
    rot, _genutzt = rote_zellen_beide_goldens(ga, mit_a, gb, mit_b, AUSNAHMEN)
    assert rot == set(), (
        f"Ungedeckte Abweichung(en) Einstellung != Auslieferung: {sorted(rot)} "
        f"-- jede Zelle braucht entweder einen Fix oder einen begruendeten "
        f"Register-Eintrag in AUSNAHMEN."
    )


# ═══════════════════════════ AC-1 ═══════════════════════════════════════════


def test_ac1_golden_trips_laden_unveraendert(monkeypatch):
    """AC-1: beide Golden-JSONs werden ueber ``load_trip`` 1:1 eingelesen --
    Kanal-Layouts und Kaskade entstehen exakt wie im JSON, ohne synthetische
    Nachbearbeitung im Testcode. Direkter Attributvergleich, keine
    Produktfunktion als Vergleichsmassstab."""
    from app.loader import load_trip

    for name in ("golden_a", "golden_b"):
        data = golden_dict(name)
        trip = load_trip(data, user_id="default")
        dc = trip.display_config
        assert dc.per_channel_layouts is not None
        for kanal in ("email", "telegram", "sms"):
            geladen = dc.per_channel_layouts[kanal]
            roh = data["display_config"]["channel_layouts"][kanal]
            assert len(geladen) == len(roh), (
                f"{name}/{kanal}: {len(geladen)} geladene vs. {len(roh)} "
                f"JSON-Eintraege"
            )
            for mc, roh_mc in zip(geladen, roh):
                assert mc.metric_id == roh_mc["metric_id"]
                assert mc.enabled == roh_mc.get("enabled", True)
                assert mc.bucket == roh_mc.get("bucket", "primary")
                assert mc.order == roh_mc.get("order", 0)
                assert mc.use_friendly_format == roh_mc.get("use_friendly_format", True)
        globale = dc.metrics
        roh_global = data["display_config"]["metrics"]
        assert len(globale) == len(roh_global)
        for mc, roh_mc in zip(globale, roh_global):
            assert mc.metric_id == roh_mc["metric_id"]
            assert mc.enabled == roh_mc.get("enabled", True)
            assert mc.order == roh_mc.get("order", 0)


# ═══════════════════════════ AC-2 ═══════════════════════════════════════════


_B1_ZELLE_KURZFORM = ("wind_chill", "telegram_kurzform", "erscheint")


def test_ac2_fehlender_register_eintrag_wind_chill_telegram_kurzform_wird_rot(monkeypatch):
    """AC-2 (Bug-Nachweis aus Nutzersicht).

    Given der Register-Eintrag fuer ``wind_chill x telegram_kurzform x
    erscheint`` wird aus einer LOKALEN Kopie von ``AUSNAHMEN`` entfernt.
    When der Invarianten-Test auf Golden A laeuft.
    Then wird GENAU diese eine Zelle rot -- nicht ihre Reihenfolge- oder
    Roh/Einfach-Zelle (die entfallen laut Orakel-Regel bei einer im Text
    fehlenden Metrik).

    RED heute: ``AUSNAHMEN`` ist leer, es gibt nichts zu entfernen -- die
    Golden-A-Matrix wird an ALLEN drei tatsaechlichen Abweichungen rot statt
    an genau dieser einen (die anderen zwei fehlen als Deckung).
    """
    ga = golden_dict("golden_a")
    mit_a, _ = render_golden(monkeypatch, "golden_a")
    register = [
        e for e in AUSNAHMEN
        if (e.metrik, e.kanal, e.dimension) != _B1_ZELLE_KURZFORM
    ]
    rot, _genutzt = rote_zellen_fuer_golden(ga, mit_a, register)
    assert rot == {_B1_ZELLE_KURZFORM}, (
        f"AC-2: erwartet GENAU {{{_B1_ZELLE_KURZFORM}}}, erhalten {sorted(rot)} "
        f"-- AUSNAHMEN muss ausser dieser Zelle alle anderen Golden-A-"
        f"Abweichungen bereits abdecken, damit die Isolation sichtbar wird."
    )


# ═══════════════════════════ AC-4 ═══════════════════════════════════════════


def test_ac4_fehlendes_kuerzel_aendert_die_erwartung_nicht(monkeypatch):
    """AC-4 (Kuerzel-Register nur zum Parsen).

    Given ``wind_chill`` ist im SMS-Kanal-Layout aktiv, traegt aber seit
    #1887 E6 KEIN Kuerzel in ``SMS_SYMBOL_BY_METRIC``/
    ``SMS_MULTI_SYMBOLS_BY_METRIC``.
    When die Orakel-Erwartung fuer Golden B / Kanal 'sms' gebildet wird.
    Then bleibt ``wind_chill`` in der Erwartung "aktiv" -- unabhaengig vom
    Kuerzel-Register. Die tatsaechliche Abwesenheit im gesendeten Text wird
    NUR ueber einen begruendeten Register-Eintrag (B1) toleriert, niemals
    dadurch, dass der Parser kein Kuerzel findet.
    """
    gb = golden_dict("golden_b")
    erwartet = erwartete_kaskade(gb, "sms", "evening")
    erwartet_ids = [mid for mid, _ in erwartet]
    assert "wind_chill" in erwartet_ids, (
        "AC-4 Teil 1 (muss gruen sein): die Orakel-Erwartung fuer 'sms' muss "
        "wind_chill weiterhin als aktiv fuehren, unabhaengig vom fehlenden "
        "SMS-Kuerzel."
    )

    # Toleranzteil (haengt am befuellten Register -- RED solange AUSNAHMEN leer ist).
    mit_b, _ = render_golden(monkeypatch, "golden_b")
    rot, _genutzt = rote_zellen_fuer_golden(gb, mit_b, AUSNAHMEN)
    assert ("wind_chill", "sms", "erscheint") not in rot, (
        "AC-4 Teil 2: die B1-Abweichung muss ueber einen begruendeten "
        "Register-Eintrag toleriert sein, nicht als ungedeckte rote Zelle "
        "auftauchen."
    )


# ═══════════════════════════ AC-5 ═══════════════════════════════════════════


def test_ac5_strukturelle_ausnahme_verengt_die_erwartung_nicht():
    """AC-5 (strukturelle Ausnahmen nur als Register-Eintrag, nie in der
    Orakel-Regel selbst).

    Given jede im Register gefuehrte STRUKTURELLE Ausnahme (``befund``
    referenziert eine strukturelle Grenze, z.B. das Telegram-7er-
    Tabellenlimit -- erkennbar an ``befristet=True`` UND einer Metrik, die in
    der zugehoerigen Kaskade eigentlich aktiv ist).
    When die Orakel-Erwartung fuer die betroffene Zelle gebildet wird.
    Then fuehrt sie die Metrik WEITERHIN als "erscheint" -- die Orakel-
    Funktion kennt 160er-Budget/``DROP_ORDER``/Telegram-7er-Limit/
    ``VISIBILITY_GATE_IDS`` NICHT und veraendert die Erwartung ihretwegen
    nicht.

    Vakuum-Schutz (PFLICHT laut Auftrag): mit leerem Register gibt es KEINE
    strukturelle Ausnahme zu pruefen -- das darf NICHT stillschweigend
    gruen durchlaufen, sondern muss explizit scheitern.
    """
    strukturelle = [
        e for e in AUSNAHMEN
        if e.befund not in ("B1", "B2", "B3", "B5") and e.metrik != "*"
    ]
    assert strukturelle, (
        "Vakuum-Schutz: kein einziger struktureller Ausnahme-Eintrag im "
        "Register -- ohne mindestens eine ausgeloeste strukturelle Ausnahme "
        "(z.B. Telegram-7er-Limit) ist dieser Test nicht prüfbar und darf "
        "nicht vakuum-gruen laufen."
    )
    for eintrag in strukturelle:
        for name in ("golden_a", "golden_b"):
            golden = golden_dict(name)
            if eintrag.kanal not in erreichbare_kanaele(golden["report_config"]):
                continue
            erwartet_ids = [mid for mid, _ in erwartete_kaskade(golden, eintrag.kanal, "evening")]
            assert eintrag.metrik in erwartet_ids, (
                f"AC-5: die Orakel-Erwartung darf {eintrag.metrik!r} in "
                f"{eintrag.kanal!r} nicht wegen der strukturellen Ausnahme "
                f"{eintrag.befund!r} unterdruecken."
            )


# ═══════════════════════════ AC-6 ═══════════════════════════════════════════


def test_ac6_leeres_register_ist_rot_an_genau_den_registrierten_zellen(monkeypatch):
    """AC-6 (Rueckdreh-Gegenprobe).

    Given das Ausnahme-Register wird lokal auf ``[]`` gesetzt.
    When der Invarianten-Test ueber beide Goldens laeuft.
    Then wird er an GENAU den Zellen rot, die ``AUSNAHMEN`` normalerweise
    abdeckt -- nicht mehr, nicht weniger; die Menge ist NICHT leer.

    RED heute: ``AUSNAHMEN`` ist bereits leer -- der Vakuum-Schutz
    ("Menge ist nicht leer") schlaegt daher zwangslaeufig fehl.
    """
    assert AUSNAHMEN, (
        "Vakuum-Schutz: AUSNAHMEN ist leer -- die Rueckdreh-Gegenprobe kann "
        "erst pruefen, sobald das Register befuellt ist (RED-Erwartung: "
        "dieser Test ist waehrend /40 absichtlich rot)."
    )
    ga, mit_a, gb, mit_b = _render_beide(monkeypatch, monkeypatch)
    rot_leer, _ = rote_zellen_beide_goldens(ga, mit_a, gb, mit_b, [])

    # "Was AUSNAHMEN normalerweise deckt": ALLE Abweichungen (unabhaengig von
    # der Register-Filterung) desselben Laufs -- das ist die Zellmenge, die
    # bei leerem Register sichtbar werden MUSS.
    normal_gedeckt: set = set()
    for golden, mit in ((ga, mit_a), (gb, mit_b)):
        _rot, alle, _genutzt = abweichungen_fuer_golden(golden, mit, AUSNAHMEN)
        normal_gedeckt |= alle

    assert rot_leer == normal_gedeckt, (
        f"AC-6: bei leerem Register muss GENAU die Zellmenge rot werden, die "
        f"AUSNAHMEN normalerweise deckt. rot_leer={sorted(rot_leer)} "
        f"normal_gedeckt={sorted(normal_gedeckt)}"
    )
    assert rot_leer != set(), "AC-6: die Menge darf nicht leer sein (Vakuum)."


# ═══════════════════════════ AC-7 ═══════════════════════════════════════════


def test_ac7_veralteter_eintrag_wird_rot(monkeypatch):
    """AC-7 (veralteter Eintrag).

    Given ein Register-Eintrag fuer eine Zelle, die im tatsaechlich
    gesendeten Text mit der Orakel-Erwartung UEBEREINSTIMMT (Zustand
    "bereits gefixt") -- hier: eine nachweislich korrekt erscheinende
    E-Mail-Metrik (``wind`` in Golden A, email_html, Dimension 'erscheint').
    When der Test laeuft.
    Then wird dieser Eintrag als "veraltet" gemeldet -- NICHT genutzt, um
    irgendeine tatsaechlich rote Zelle zu decken.
    """
    ga = golden_dict("golden_a")
    mit_a, _ = render_golden(monkeypatch, "golden_a")
    veralteter_eintrag = AusnahmeEintrag(
        metrik="wind", kanal="email_html", dimension="erscheint",
        befund="AC7-PROBE", grund="Testkoerper: nachweislich gruene Zelle",
        befristet=True,
    )
    register = list(AUSNAHMEN) + [veralteter_eintrag]
    _rot, genutzt = rote_zellen_fuer_golden(ga, mit_a, register)
    veraltete = veraltete_eintraege(register, genutzt)
    assert veralteter_eintrag in veraltete, (
        f"AC-7: der Eintrag fuer eine bereits korrekte Zelle muss als "
        f"veraltet erkannt werden, gemeldet wurden {veraltete}"
    )


def test_ac6_ac7_echtes_register_hat_keine_unbenutzten_eintraege(monkeypatch):
    """AC-6/AC-7 (Finding F002 der Adversary-Pruefung): Gegenprobe gegen das
    ECHTE ``AUSNAHMEN``-Register, nicht nur gegen eine lokale Kopie mit einem
    testkoerper-eigenen Eintrag.

    Given das ECHTE ``AUSNAHMEN``-Register laeuft ueber BEIDE Goldens.
    When die tatsaechlich genutzten Eintraege gesammelt werden.
    Then ist KEIN Eintrag unbenutzt -- ein zusaetzlicher, erfundener oder
    laengst veralteter Eintrag im echten Register faellt sonst nie auf (die
    Hauptmatrix wird nur an ungedeckten Abweichungen rot, nicht an
    ueberschuessiger Deckung). Mutations-Gegenprobe (PFLICHT): ein Bogus-
    Eintrag ins echte Register (z.B. eine gruene Zelle, die keine der beiden
    Goldens ueberhaupt abweichen laesst) muss GENAU diesen Test rot faerben.
    """
    ga, mit_a, gb, mit_b = _render_beide(monkeypatch, monkeypatch)
    _rot, genutzt = rote_zellen_beide_goldens(ga, mit_a, gb, mit_b, AUSNAHMEN)
    veraltete = veraltete_eintraege(AUSNAHMEN, genutzt)
    assert veraltete == set(), (
        f"AC-6/AC-7: das ECHTE Register enthaelt unbenutzte Eintraege (weder "
        f"durch Golden A noch Golden B ausgeloest): {veraltete} -- entweder "
        f"bereits gefixt (veraltet) oder nie eine tatsaechliche Abweichung."
    )


# ═══════════════════════════ AC-8 ═══════════════════════════════════════════


def test_ac8_eintrag_ohne_begruendung_blockt_vor_der_matrix(monkeypatch):
    """AC-8 (Eintrag ohne Begruendung).

    Given ein Register-Eintrag mit leerem ``grund``.
    When das Register vor der Matrixpruefung validiert wird.
    Then schlaegt die Validierung mit einer spezifischen Fehlermeldung fehl
    -- BEVOR irgendeine Zelle geprueft wurde (Reihenfolge-Nachweis ueber
    einen Zaehler, der erst nach erfolgreicher Validierung inkrementiert
    wuerde).
    """
    zaehler = {"matrix_zellen_geprueft": 0}
    kaputt = AusnahmeEintrag(
        metrik="wind", kanal="sms", dimension="erscheint",
        befund="AC8-PROBE", grund="   ", befristet=True,
    )
    with pytest.raises(RegisterValidierungsFehler):
        register_validieren([kaputt])
        zaehler["matrix_zellen_geprueft"] += 1  # darf nie erreicht werden
    assert zaehler["matrix_zellen_geprueft"] == 0, (
        "AC-8: die Matrix-Pruefung darf nach einem Validierungsfehler nicht "
        "mehr anlaufen."
    )

    kaputt_ohne_befund = AusnahmeEintrag(
        metrik="wind", kanal="sms", dimension="erscheint",
        befund="", grund="ein Grund", befristet=True,
    )
    with pytest.raises(RegisterValidierungsFehler):
        register_validieren([kaputt_ohne_befund])


def test_ac8_f006_wildcard_metrik_ohne_kanalweiten_befund_blockt_vor_der_matrix(monkeypatch):
    """AC-8 / Finding F006 (Adversary-Runde 4).

    Given ein Register-Eintrag mit ``metrik="*"``, dessen ``befund`` NICHT
    der kanalweite Befund B2 ist (laut Spec, Abschnitt "Ausnahme-Register",
    ist ``metrik="*"`` ausschliesslich fuer B2 vorgesehen).
    When das Register vor der Matrixpruefung validiert wird.
    Then schlaegt die Validierung mit einer spezifischen Fehlermeldung fehl --
    BEVOR irgendeine Zelle geprueft wurde. Ein metrikscharfer Eintrag (z.B.
    der ``gust``-Eintrag fuer das Telegram-7er-Tabellenlimit) darf sich also
    nicht unbemerkt auf ``metrik="*"`` verbreitern.
    """
    verbreiterter_gust_eintrag = AusnahmeEintrag(
        metrik="*", kanal="telegram_rich", dimension="erscheint",
        befund="Issue #360 (Telegram-7er-Tabellenlimit)",
        grund="Mutation C: metrikscharfer gust-Eintrag auf '*' verbreitert.",
        befristet=False,
    )
    with pytest.raises(RegisterValidierungsFehler, match="kanalweiten Befunde"):
        register_validieren([verbreiterter_gust_eintrag])

    # Das ECHTE Register darf keinen solchen Eintrag enthalten -- die
    # Validierung des Produktions-Registers muss gruen bleiben.
    register_validieren(AUSNAHMEN)

    # Vollstaendiger Nachweis: der Hauptmatrix-Pfad ruft ``register_validieren``
    # tatsaechlich mit dem ECHTEN Register auf (nicht nur isoliert getestet).
    import tests.helpers.einstellung_auslieferung_orakel as orakel_mod

    aufrufe: list = []
    orig_validieren = orakel_mod.register_validieren

    def _aufzeichnender_validieren(register):
        aufrufe.append(list(register))
        return orig_validieren(register)

    monkeypatch.setattr(
        orakel_mod, "register_validieren", _aufzeichnender_validieren, raising=True,
    )
    ga = golden_dict("golden_a")
    mit_a, _ = render_golden(monkeypatch, "golden_a")
    rote_zellen_fuer_golden(ga, mit_a, AUSNAHMEN)
    assert any(aufruf == list(AUSNAHMEN) for aufruf in aufrufe), (
        "F006-Nachweis: der Hauptmatrix-Pfad (abweichungen_fuer_golden) muss "
        "register_validieren(AUSNAHMEN) tatsaechlich mit dem ECHTEN Register "
        f"aufrufen, aufgezeichnete Aufrufe: {aufrufe!r}"
    )


def test_ac8_f007_wildcard_b2_ausserhalb_des_erlaubten_scopes_blockt(monkeypatch):
    """AC-8 / Finding F007 (Adversary-Runde 5).

    Given ein Register-Eintrag mit ``metrik="*"`` und dem kanalweiten Befund
    ``B2`` (besteht damit den F006-Check), dessen (Kanal, Dimension) aber
    NICHT im laut Spec fuer B2 erlaubten Scope liegt (nur sms/
    telegram_kurzform/premium_sms x roh_einfach -- Umgehung aus Runde 5:
    ``gust`` auf telegram_rich/erscheint mit befund="B2" verbreitert).
    When das Register vor der Matrixpruefung validiert wird.
    Then schlaegt die Validierung mit einer scope-spezifischen Fehlermeldung
    fehl -- das reine befund-Label "B2" reicht nicht, der (Kanal, Dimension)-
    Ort muss mitgeprueft werden. Das ECHTE Register bleibt gueltig.
    """
    verbreiterter_gust_b2 = AusnahmeEintrag(
        metrik="*", kanal="telegram_rich", dimension="erscheint",
        befund="B2",
        grund="F007: gust-Umgehung -- B2-Label ohne passenden Scope.",
        befristet=False,
    )
    with pytest.raises(RegisterValidierungsFehler, match="Scope"):
        register_validieren([verbreiterter_gust_b2])

    # Das ECHTE Register enthaelt ausschliesslich B2-Eintraege innerhalb des
    # erlaubten Scopes (sms/telegram_kurzform/premium_sms x roh_einfach) --
    # die Validierung des Produktions-Registers muss gruen bleiben.
    register_validieren(AUSNAHMEN)


# ═══════════════════════════ AC-9 ═══════════════════════════════════════════


def _rot_fuer_golden_b(monkeypatch) -> set:
    gb = golden_dict("golden_b")
    mit_b, _ = render_golden(monkeypatch, "golden_b")
    rot, _ = rote_zellen_fuer_golden(gb, mit_b, [])
    return rot


def test_ac9_m1_sortkey_invertiert_wird_in_email_reihenfolge_rot(monkeypatch):
    """AC-9 M1: Sortkey in ``app.models._sorted_by_layout`` invertiert.

    Telegram re-sortiert seine Tabellen-Spalten in
    ``channel_layout.render_for_channel`` ein zweites Mal nach ``m.order``
    (unabhaengig vom Sortier-ERGEBNIS von ``_sorted_by_layout`` -- nur die
    Werte zaehlen) -- die Mutation bleibt dort deshalb strukturell unsichtbar
    (Code: channel_layout.py, `primary = sorted([...], key=lambda m: m.order)`).
    E-Mail liest ``dc.metrics`` dagegen DIREKT in der von
    ``get_metrics_for_channel`` gelieferten Reihenfolge (kein zweiter Sort)
    -- die betroffene Zelle liegt daher bei E-Mail, nicht bei Telegram-rich
    (Abweichung von der urspruenglichen Erwartung, siehe Abschlussbericht).

    Zugleich der VERHALTENS-Beleg fuer AC-3 (Orakel-Unabhaengigkeit, kein
    AST-/``inspect.getsource``-Test -- der widerspraeche der Spec): bliebe die
    Orakel-Funktion heimlich an ``_sorted_by_layout`` gekoppelt, waere M1
    unsichtbar, weil beide Seiten (Erwartung UND tatsaechlicher Text) gleich
    falsch wuerden. Genau das prueft dieser Test unten -- er wird rot, also
    ist die Orakel-Erwartung unabhaengig von ``_sorted_by_layout``.
    """
    import app.models as models_mod

    rot_basis = _rot_fuer_golden_b(monkeypatch)

    orig = models_mod._sorted_by_layout

    def invertiert(metrics):
        return list(reversed(orig(metrics)))

    monkeypatch.setattr(models_mod, "_sorted_by_layout", invertiert, raising=True)
    rot_mutiert = _rot_fuer_golden_b(monkeypatch)

    diff = rot_mutiert - rot_basis
    reihenfolge_treffer = {z for z in diff if z[2] == "reihenfolge" and z[1] in ("email_html", "email_plain")}
    assert reihenfolge_treffer, (
        f"AC-9 M1: erwartet mindestens eine neue Reihenfolge-Zelle bei "
        f"E-Mail, Differenz war {sorted(diff)}"
    )


def test_ac9_m2_clip_laesst_dewpoint_durch_wird_bei_sms_rot(monkeypatch):
    """AC-9 M2: ``_clip_to_global_maximum``-Aequivalent laesst eine Metrik
    durch, die laut P2 geclippt werden muesste (``dewpoint``: aktiv im
    SMS-Kanal-Layout, aber NICHT im globalen Maximum)."""
    from app.models import UnifiedWeatherDisplayConfig as DC

    rot_basis = _rot_fuer_golden_b(monkeypatch)

    def kein_schnitt(self, metrics, report_type):
        return metrics

    monkeypatch.setattr(DC, "_clip_to_global_maximum", kein_schnitt, raising=True)
    rot_mutiert = _rot_fuer_golden_b(monkeypatch)

    diff = rot_mutiert - rot_basis
    erwartet_zelle = ("dewpoint", "sms", "erscheint")
    assert erwartet_zelle in diff, (
        f"AC-9 M2: erwartet {erwartet_zelle} in der Differenz, erhalten "
        f"{sorted(diff)}"
    )


def test_ac9_m3_friendly_keys_liest_falsche_dc_wird_bei_telegram_rich_rot(monkeypatch):
    """AC-9 M3: ``build_friendly_keys`` liefert eine falsche (hier: leere)
    Menge statt der aus der uebergebenen ``dc`` abgeleiteten.

    Abweichung von der urspruenglichen Spec-Annahme, mit Code-Beleg (siehe
    Abschlussbericht): E-Mail ist strukturell IMMUN gegen diese Mutation --
    ``render_email()`` berechnet sich ``format_modes`` JEDE Sekunde selbst
    aus der eigenen ``display_config`` (``email/__init__.py:137``,
    ``build_format_modes(display_config)``), und ``fmt_val()``
    (``email/helpers.py:783-792``) LAESST ``format_modes`` IMMER vor
    ``friendly_keys`` gewinnen, wenn es gesetzt ist. Nur Telegram
    (``narrow.py``s ``_cell()``) ruft ``fmt_val()`` OHNE ``format_modes`` auf
    und haengt deshalb ausschliesslich am geteilten ``self._friendly_keys``
    (B3-Mechanismus). Die durch M3 gefangene Zelle liegt daher zwingend bei
    Telegram rich, nie bei E-Mail -- ``cloud_low`` ist in Golden B in E-Mail
    UND Telegram gleich (friendly) konfiguriert, am Baseline also GRUEN
    (beide Seiten liefern "friendly", auch wenn Telegram sie technisch nur
    dank des E-Mail-Werts erreicht), und wird erst durch die Mutation (keine
    Roh/Einfach-Information mehr) rot.
    """
    import output.renderers.trip_report as tr_mod

    rot_basis = _rot_fuer_golden_b(monkeypatch)
    assert ("cloud_low", "telegram_rich", "roh_einfach") not in rot_basis, (
        "Testaufbau: cloud_low muss am Baseline in Telegram rich GRUEN sein, "
        "sonst faengt die Mutation nichts Neues."
    )

    monkeypatch.setattr(tr_mod, "build_friendly_keys", lambda dc: set(), raising=True)
    rot_mutiert = _rot_fuer_golden_b(monkeypatch)

    diff = rot_mutiert - rot_basis
    erwartet_zelle = ("cloud_low", "telegram_rich", "roh_einfach")
    assert erwartet_zelle in diff, (
        f"AC-9 M3: erwartet {erwartet_zelle} in der Differenz, erhalten "
        f"{sorted(diff)}"
    )


def test_ac9_m4_formatter_liest_globale_liste_wird_bei_uv_index_rot(monkeypatch):
    """AC-9 M4: der Formatter liest ``dc.metrics`` (die globale Liste)
    statt des Kanal-Layouts -- sichtbar an P3 (``uv_index``: global aktiv,
    in KEINEM Kanal-Layout aktiv)."""
    from app.models import UnifiedWeatherDisplayConfig as DC

    rot_basis = _rot_fuer_golden_b(monkeypatch)

    def immer_global(self, channel, report_type):
        return self.get_metrics_for_report_type(report_type)

    monkeypatch.setattr(DC, "get_metrics_for_channel", immer_global, raising=True)
    rot_mutiert = _rot_fuer_golden_b(monkeypatch)

    diff = rot_mutiert - rot_basis
    uv_treffer = {z for z in diff if z[0] == "uv_index" and z[2] == "erscheint"}
    assert uv_treffer, (
        f"AC-9 M4: erwartet mindestens eine neue uv_index-Erscheint-Zelle, "
        f"Differenz war {sorted(diff)}"
    )


# ═══════════════════════════ AC-10 ═══════════════════════════════════════════


def test_ac10_register_deckt_exakt_die_ausgeloesten_befunde_ab(monkeypatch):
    """AC-10 (Register-Startbefuellung).

    Given die durch die zwei Golden-Varianten tatsaechlich ausgeloesten
    Befunde B1, B2, B3, B5 sowie die ausgeloeste strukturelle Ausnahme.
    When Scheibe S1 abgeschlossen wird.
    Then hat jede daraus resultierende rote Zelle genau einen Register-
    Eintrag mit Befund-Referenz und Grund -- und fuer B4/B6/B7/B8/B9
    existiert bewusst KEIN Eintrag.

    RED heute: ``AUSNAHMEN`` ist leer -- weder die B1/B2/B3/B5-Eintraege
    noch die strukturelle Ausnahme existieren.
    """
    for befund in ("B1", "B2", "B3", "B5"):
        assert any(e.befund == befund for e in AUSNAHMEN), (
            f"AC-10: erwartet mindestens einen Register-Eintrag fuer "
            f"{befund!r}, AUSNAHMEN={AUSNAHMEN!r}"
        )
    for verbotener_befund in ("B4", "B6", "B7", "B8", "B9"):
        assert not any(e.befund == verbotener_befund for e in AUSNAHMEN), (
            f"AC-10: kein Register-Eintrag fuer {verbotener_befund!r} erlaubt"
        )
    for e in AUSNAHMEN:
        assert e.befund and e.befund.strip()
        assert e.grund and e.grund.strip()

    ga, mit_a, gb, mit_b = _render_beide(monkeypatch, monkeypatch)
    rot, _ = rote_zellen_beide_goldens(ga, mit_a, gb, mit_b, AUSNAHMEN)
    assert rot == set(), (
        f"AC-10: mit dem vollstaendig befuellten Register muss der Lauf "
        f"ueber beide Goldens gruen sein, rot war {sorted(rot)}"
    )


# ═══════════════════════════ AC-11 ═══════════════════════════════════════════


def test_ac11_matrix_ist_vollstaendig(monkeypatch):
    """AC-11 (Matrix-Abdeckung).

    Given alle waehlbaren Metriken (``selectable=true``, ``confidence_pct``
    per Issue #710 ausgeschlossen) und die sechs Kanaele.
    When der Invarianten-Test ueber BEIDE Goldens laeuft.
    Then hat jede Kombination aus Metrik x Kanal x Dimension, die in
    mindestens einem der beiden Goldens ERREICHBAR ist, ein Ergebnis (gruen,
    rot oder Register-gedeckt) -- keine erreichbare Kombination wird
    stillschweigend ausgelassen.
    """
    alle_ids = alle_waehlbaren_metrik_ids()
    assert len(alle_ids) >= 15, (
        f"Vakuum-Schutz: nur {len(alle_ids)} waehlbare Metriken -- der "
        f"Katalog-Filter liefert zu wenig fuer eine aussagekraeftige "
        f"Vollstaendigkeitspruefung."
    )
    assert "confidence" not in alle_ids and "confidence_pct" not in alle_ids, (
        "AC-11: confidence_pct ist per Issue #710 nicht waehlbar und darf "
        "nicht in der Matrix auftauchen."
    )

    ga, mit_a, gb, mit_b = _render_beide(monkeypatch, monkeypatch)
    ergebnis_vorhanden: set = set()
    for golden, name in ((ga, "golden_a"), (gb, "golden_b")):
        for kanal in erreichbare_kanaele(golden["report_config"]):
            erwartet_ids = {mid for mid, _ in erwartete_kaskade(golden, kanal, "evening")}
            for mid in alle_ids:
                # "erscheint" ist fuer JEDE erreichbare Kombination auswertbar
                # (aktiv oder nicht -- immer ein Ergebnis).
                ergebnis_vorhanden.add((mid, kanal, "erscheint"))
                if mid in erwartet_ids and hat_roh_einfach_dimension(mid):
                    ergebnis_vorhanden.add((mid, kanal, "reihenfolge"))
                    ergebnis_vorhanden.add((mid, kanal, "roh_einfach"))
                elif mid in erwartet_ids:
                    ergebnis_vorhanden.add((mid, kanal, "reihenfolge"))

    fehlende = []
    for mid in alle_ids:
        for kanal in KANAELE:
            if (mid, kanal, "erscheint") not in ergebnis_vorhanden:
                fehlende.append((mid, kanal, "erscheint"))
    assert not fehlende, (
        f"AC-11: {len(fehlende)} Kombinationen ohne jedes Ergebnis, z.B. "
        f"{fehlende[:5]}"
    )


# ═══════════════════════════ AC-12 ═══════════════════════════════════════════


#: Dokumentierte, begruendete Ausnahmen (Finding F003): keine fehlende
#: Rohdaten-Zelle, sondern eine bewusste Darstellungsentscheidung. ``thunder``
#: zeigt in der E-Mail-HTML-Tabelle eine farbige Ampel-Punkt-Zelle statt Text
#: (``trip_report.py`` ``_AMPEL_CAPABLE_METRIC_IDS``-Nachbarschaft) -- die
#: zugrunde liegenden Rohdaten sind vorhanden (dieselbe Groesse steht
#: textuell im Klartext-Teil derselben Mail, per ``parse_email_plain``
#: separat geprueft).
_AC12_ERLAUBTE_PLATZHALTER: set[tuple[str, str]] = {("thunder", "email_html")}


def test_ac12_keine_rote_zelle_durch_fehlende_rohdaten(monkeypatch):
    """AC-12 (synthetische Voll-Wetter-Fixture) -- Finding F003: ueber BEIDE
    Goldens und ALLE sechs von ihnen jeweils erreichbaren Kanaele, nicht nur
    golden_b/email_plain.

    Given die neue synthetische Voll-Wetter-Fixture belegt ALLE Felder, die
    den bestehenden ``openmeteo``-Fixtures fehlen (humidity, dewpoint,
    pressure, wind_chill_c, cloud_mid/high, precip_type, snow_new_24h).
    When beide Goldens damit ueber alle sechs Ausgabe-Formen gerendert
    werden.
    Then hat keine im jeweiligen Kanaltext TATSAECHLICH erscheinende Metrik
    einen Platzhalter statt eines Wertes -- AUSSER der dokumentierten,
    begruendeten Ausnahme oben. Eine erwartete, aber im Text FEHLENDE Metrik
    ist eine "erscheint"-Abweichung (Register-Sache), nicht Gegenstand von
    AC-12.
    """
    ga, mit_a, gb, mit_b = _render_beide(monkeypatch, monkeypatch)

    for golden, mitschrift, golden_name in ((ga, mit_a, "golden_a"), (gb, mit_b, "golden_b")):
        for kanal in erreichbare_kanaele(golden["report_config"]):
            erwartet_ids = {mid for mid, _ in erwartete_kaskade(golden, kanal, "evening")}
            ist_ids, ist_modi = parse_kanal(mitschrift, kanal)
            for mid in erwartet_ids:
                if mid not in ist_ids:
                    continue  # "erscheint"-Abweichung, nicht Gegenstand von AC-12
                if (mid, kanal) in _AC12_ERLAUBTE_PLATZHALTER:
                    continue
                assert ist_modi.get(mid) is not None, (
                    f"AC-12: {mid!r} zeigt in Kanal {kanal!r} ({golden_name}) "
                    f"einen Platzhalter statt eines Wertes."
                )


# ═══════════════════════════ AC-13 ═══════════════════════════════════════════


def test_ac13_naht_liegt_nur_am_transport(monkeypatch):
    """AC-13 (Naht nur am Transport) -- Finding F004: Zuordnung an der
    GUST-STELLE pruefen (``roh_wert_der_metrik``), nicht nur ein Substring
    ``"45"`` irgendwo im Text (der koennte zufaellig von anderswo stammen).

    Given ``EmailOutput``/``SMSOutput``/``PremiumSmsOutput``/``TelegramOutput``
    werden per ``monkeypatch.setattr`` durch den Aufzeichner ersetzt.
    When beide Goldens versendet werden.
    Then laufen Loader, Kaskade und Formatter unveraendert echt -- der
    Aufzeichner erfasst den vollstaendigen, durch echte Formatierung
    erzeugten Text je Kanal, und der konkrete Boen-Wert (45 km/h) aus der
    Voll-Wetter-Fixture steht GENAU an der ``gust``-Stelle (Spalte/Token),
    nicht nur irgendwo im Text.
    """
    mit_b, _ = render_golden(monkeypatch, "golden_b")

    assert roh_wert_der_metrik(mit_b, "email_plain", "gust") == "45", (
        "AC-13: der Boen-Wert muss an der gust-Spalte im echt formatierten "
        "Klartext stehen."
    )
    assert roh_wert_der_metrik(mit_b, "email_html", "gust") == "45", (
        "AC-13: derselbe Wert muss an der gust-Spalte im echt formatierten "
        "HTML stehen."
    )
    sms_wert = roh_wert_der_metrik(mit_b, "sms", "gust")
    # SMS-Token-Grammatik haengt einen Zeitstempel-Suffix an (z.B. "45@4") --
    # derselbe Trenn-Trick wie in ``parse_sms_artig`` bei der Modus-Erkennung.
    assert sms_wert is not None and sms_wert.split("@")[0].split("/")[0] == "45", (
        f"AC-13: die SMS muss den Boen-Wert am gust-Kuerzel tragen, erhalten "
        f"{sms_wert!r}."
    )
    # Telegram rich: gust wird wegen des Telegram-7er-Tabellenlimits (Issue
    # #360, Register-Eintrag) aus der Stunden-Tabelle verdraengt und
    # erscheint statt dessen in der begleitenden Kurzuebersicht-Bubble
    # ("G 45") -- ``roh_wert_der_metrik`` sucht beide Fundstellen.
    assert roh_wert_der_metrik(mit_b, "telegram_rich", "gust") == "45", (
        "AC-13: Telegram muss den Boen-Wert an der gust-Stelle tragen "
        "(Stunden-Tabelle oder Kurzuebersicht-Zeile)."
    )


# ═══════════════ Golden C / Issue #2422 S2a (B9-Fix) ═════════════════════════
#
# SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (AC-1).
# Golden C loest -- anders als Golden A/B -- fuer SMS/Telegram-Kurzform/
# Premium-SMS die Kaskadenquelle 'global' aus (kein eigenes
# ``channel_layouts.sms``). Vor dem B9-Fix (Aktivierungs-Gate in
# ``trip_report.py:337-346``) bleibt die SMS-/Kurzform-/Premium-Reihenfolge
# bei 'global' auf der festen POSITIONAL-Standardreihenfolge stehen, obwohl
# der Editor die globale Reihenfolge zeigt -- das ist GENAU B9.


def test_golden_c_kaskadenquelle_global_wird_ausgeloest():
    """AC-1: Golden C laedt ueber ``load_trip`` und loest fuer SMS die
    Kaskadenquelle 'global' aus (kein eigenes ``channel_layouts.sms``),
    waehrend E-Mail (eigenes ``channel_layouts.email``) bei 'per_channel'
    bleibt. Dies ist eine reine Vorbedingungs-Pruefung der Golden-C-Fixture
    (Kaskadenquelle-KLASSIFIZIERUNG aendert sich durch den B9-Fix NICHT --
    nur die *Wirkung* der Kaskadenquelle 'global' auf die SMS-Position tut
    es, siehe ``test_hauptmatrix_golden_c_b9_reihenfolge``). Bereits heute
    GRUEN -- das Golden-Setup, nicht der Bug, wird hier bewiesen."""
    from app.loader import load_trip

    trip = load_trip(golden_dict("golden_c"), user_id="default")
    dc = trip.display_config

    for report_type in ("morning", "evening"):
        assert dc.cascade_source_for_channel("sms", report_type) == "global", (
            f"Golden C muss fuer SMS/{report_type} die Kaskadenquelle "
            f"'global' ausloesen (kein eigenes channel_layouts.sms)."
        )
        assert dc.cascade_source_for_channel("telegram", report_type) == "global", (
            f"Golden C muss fuer Telegram/{report_type} ebenfalls 'global' "
            f"ausloesen (kein eigenes channel_layouts.telegram)."
        )
        assert dc.cascade_source_for_channel("email", report_type) == "per_channel", (
            f"Golden C muss fuer E-Mail/{report_type} bei 'per_channel' "
            f"bleiben (eigenes channel_layouts.email vorhanden)."
        )


#: Empirisch ermittelte (Scratchpad-Lauf 2026-09-27 gegen den UNVERAENDERTEN
#: Code) rote Zellmenge, die Golden C ueber die S1-Matrixfunktion UND das
#: unveraenderte S1-Register (B1/B2/B3/B5) erzeugt -- ausschliesslich
#: 'reihenfolge'-Zellen fuer sms/premium_sms/telegram_kurzform, die weder
#: durch B1 (wind_chill, kein SMS-Kuerzel) noch durch B2 (Roh/Einfach
#: kanalweit) bereits gedeckt sind. KEINE Zelle ausserhalb dieser Menge --
#: das waere Kategorie (c) (neuer, hier nicht benannter Befund, AC-18: PO
#: vorlegen statt registrieren). Evening/morning unterscheiden sich, weil G4
#: (``cloud_low.evening_enabled=false``, ``humidity.morning_enabled=false``)
#: die jeweils betroffene Metrik aus BEIDEN Seiten (erwartet+ist) desselben
#: Report-Typs entfernt -- und der Ausschluss verschiebt zusaetzlich die
#: relative Position der VERBLEIBENDEN Metriken im Index-Vergleich
#: (``abweichungen_fuer_golden`` vergleicht relative Ranglisten, nicht
#: absolute Positionen) -- bestaetigt gegen den simulierten B9-Fix (rot ==
#: leer fuer BEIDE Report-Typen, Scratchpad-Lauf 2026-09-27).
_B9_ERWARTETE_ZELLEN_EVENING: set = {
    (mid, kanal, "reihenfolge")
    for kanal in ("sms", "premium_sms", "telegram_kurzform")
    for mid in (
        "gust", "precipitation", "rain_probability", "cloud_total",
        "humidity", "sunshine", "uv_index",
    )
}
_B9_ERWARTETE_ZELLEN_MORNING: set = {
    (mid, kanal, "reihenfolge")
    for kanal in ("sms", "premium_sms", "telegram_kurzform")
    for mid in ("gust", "precipitation", "rain_probability", "sunshine", "uv_index")
}
_B9_ERWARTETE_ZELLEN_JE_REPORT_TYPE = {
    "evening": _B9_ERWARTETE_ZELLEN_EVENING,
    "morning": _B9_ERWARTETE_ZELLEN_MORNING,
}


@pytest.mark.parametrize("report_type", ["evening", "morning"])
def test_hauptmatrix_golden_c_b9_reihenfolge_wird_rot(monkeypatch, report_type):
    """B9-Nachweis (Kern dieser Scheibe, AC-1/AC-18), fuer morning UND
    evening (G4: ``morning_enabled``/``evening_enabled`` wirken nur je
    eigenem Report-Typ).

    Given Golden C (Kaskadenquelle 'global' fuer sms/telegram_kurzform/
    premium_sms, siehe ``test_golden_c_kaskadenquelle_global_wird_
    ausgeloest``) und das UNVERAENDERTE S1-Register (B1/B2/B3/B5, keine
    neuen Eintraege -- AC-18).
    When Golden C ueber dieselbe Matrixfunktion wie A/B laeuft
    (``rote_zellen_fuer_golden``), fuer ``report_type`` in {evening, morning}.
    Then ist die rote Zellmenge LEER -- die Editor-Reihenfolge fuer
    sms/premium_sms/telegram_kurzform kommt genauso an wie bei Golden A/B
    mit eigenem Kanal-Layout, unabhaengig vom Report-Typ.

    RED heute: das Aktivierungs-Gate in ``trip_report.py:337-346`` setzt bei
    Kaskadenquelle 'global' keine ``position`` -> SMS-/Kurzform-/
    Premium-Ausgabe faellt auf die feste POSITIONAL-Standardreihenfolge
    zurueck, waehrend die Orakel-Erwartung der GLOBALEN Editor-Reihenfolge
    folgt -- das erzeugt exakt die je Report-Typ dokumentierte Zellmenge.
    Nach dem B9-Fix wird die rote Menge fuer BEIDE Report-Typen leer, ohne
    dass das Register einen einzigen neuen Eintrag braucht (bestaetigt
    gegen einen simulierten Fix, Scratchpad-Lauf 2026-09-27).
    """
    gc = golden_dict("golden_c")
    mit_c, _ = render_golden(monkeypatch, "golden_c", report_type=report_type)
    rot, _genutzt = rote_zellen_fuer_golden(gc, mit_c, AUSNAHMEN, report_type=report_type)

    # B1 (wind_chill ohne SMS-Kuerzel) und B2 (Roh/Einfach kanalweit) bleiben
    # ueber das UNVERAENDERTE Register gedeckt -- Golden C darf daran nichts
    # Neues ausloesen (Kategorie (b) der Abschlussbericht-Einsortierung).
    # Dieser Teil ist bereits heute gruen (Bestandsschutz-Beleg).
    for kanal in ("sms", "premium_sms", "telegram_kurzform"):
        assert ("wind_chill", kanal, "erscheint") not in rot, (
            f"Golden C darf B1 (wind_chill ohne SMS-Kuerzel) in {kanal!r} "
            f"nicht neu ausloesen -- das S1-Register deckt diese Zelle "
            f"bereits golden-unabhaengig ab."
        )

    # Charakterisierung des heutigen (kaputten) Standes -- verschwindet mit
    # dem B9-Fix; bleibt sie ungleich, ist Golden C selbst nicht mehr
    # register-sauber (Kategorie (c), AC-18-Verstoss).
    erwartete_zellen = _B9_ERWARTETE_ZELLEN_JE_REPORT_TYPE[report_type]
    assert rot in (set(), erwartete_zellen), (
        f"Golden C/{report_type} loest eine ANDERE als die bekannte "
        f"B9-Zellmenge aus -- das waere ein neuer, hier nicht benannter "
        f"Befund (Kategorie (c), AC-18: PO vorlegen statt registrieren). "
        f"Erhalten: {sorted(rot)}"
    )

    # Die eigentliche B9-Zusicherung dieser Scheibe: nach dem Fix ist die
    # Menge LEER -- RED heute, GRUEN nach dem B9-Fix (Aktivierungs-Gate
    # entfernt).
    assert rot == set(), (
        f"B9 (Kaskadenquelle 'global', report_type={report_type!r}): "
        f"unbehobene 'reihenfolge'-Zellen fuer sms/premium_sms/"
        f"telegram_kurzform: {sorted(rot)} -- der B9-Fix "
        f"(trip_report.py:337-346, Aktivierungs-Gate entfernen) behebt "
        f"genau diese Zellmenge, ohne einen neuen Register-Eintrag zu "
        f"brauchen."
    )


# ═══════════════ AC-18 (keine neuen Register-Eintraege) ══════════════════════


def test_ac18_keine_neuen_register_eintraege():
    """AC-18: B9 und K8 werden in dieser Scheibe PRODUKTIV gefixt, nicht
    registriert -- das S1-Register bleibt nach Abschluss von S2a
    UNVERAENDERT (nur die S1-Befunde B1/B2/B3/B5 + die strukturelle
    Telegram-7er-Ausnahme, Issue #360).

    Given die Umsetzung dieser Scheibe (B9-Fix, K8-Fix, Aenderungspfad).
    When das AUSNAHMEN-Register nach Abschluss von S2a gelesen wird.
    Then enthaelt es KEINEN Eintrag mit ``befund`` in {"B9", "K8", "K9"}
    oder einem in dieser Spec nicht benannten neuen Kuerzel -- jeder erlaubte
    Eintrag traegt einen der bereits aus S1 bekannten Befunde.
    """
    verbotene_befunde = {"B4", "B6", "B7", "B8", "B9", "K8", "K9"}
    erlaubte_befunde = {"B1", "B2", "B3", "B5", "Issue #360 (Telegram-7er-Tabellenlimit)"}

    # #2422 S3 (AC-28): auch nach S3 bleibt das Register beim S1-Bestand --
    # gleiche ZAHL und keine Kennung dieser Spec (``S3-...``). Eine in /40//50
    # entdeckte Abweichung wird produktiv gefixt oder dem PO vorgelegt, nie
    # befristet eingetragen. Charakterisierung: heute gruen.
    S1_BESTAND_ANZAHL = 9
    assert len(AUSNAHMEN) == S1_BESTAND_ANZAHL, (
        f"AC-28: das Register hat {len(AUSNAHMEN)} Eintraege, der S1-Bestand "
        f"ist {S1_BESTAND_ANZAHL} -- S3 legt KEINE neuen Eintraege an."
    )
    for eintrag in AUSNAHMEN:
        assert not str(eintrag.befund).upper().startswith("S3"), (
            f"AC-28: Register-Eintrag mit S3-Kennung {eintrag.befund!r} -- "
            f"S3 fixt produktiv statt zu registrieren."
        )
    for eintrag in AUSNAHMEN:
        assert eintrag.befund not in verbotene_befunde, (
            f"AC-18: Register-Eintrag mit verbotenem Befund {eintrag.befund!r} "
            f"gefunden -- B9/K8/K9 werden in S2a PRODUKTIV gefixt, nicht "
            f"registriert (PO-Entscheid 2026-09-27)."
        )
        assert eintrag.befund in erlaubte_befunde, (
            f"AC-18: Register-Eintrag mit unbekanntem, hier nicht benanntem "
            f"Befund {eintrag.befund!r} -- neue Befunde innerhalb dieser "
            f"Kette werden produktiv gefixt statt registriert; ausserhalb "
            f"der Kette dem PO vorlegen, statt sie befristet zu tolerieren."
        )


# ═══════════════ AC-5 (Speichern ohne Aenderung = Auslieferung, B9-Nachweis) ═


def _fehlt_hinweis(pfad) -> str:
    return (
        f"{pfad} fehlt -- wird in /50 aus der TS-Helferkette erzeugt "
        f"(Golden laden, ohne Aenderung speichern, Ergebnis einfrieren). "
        f"Bis dahin ROT NUR WEGEN FEHLENDER /50-DATEI, kein B9/K8-Befund."
    )


@pytest.mark.parametrize("report_type", ["evening", "morning"])
@pytest.mark.parametrize("golden_name", ["golden_a", "golden_b", "golden_c"])
def test_ac5_speichern_ohne_aenderung_veraendert_die_auslieferung_nicht(
    golden_name: str, report_type: str,
) -> None:
    """AC-5: ``erwartete_kaskade(nach_speichern_<golden>) ==
    erwartete_kaskade(golden)`` -- ohne Ausnahme, fuer A/B/C UND fuer
    morning UND evening (NICHT den report-typ-neutralen 'anzeige'-Sentinel:
    der wuerde morning_enabled/evening_enabled -- also gerade den K8-Verlust
    bei Golden C -- unsichtbar machen, weil beide Seiten dann gleich robust
    auf 'enabled' zurueckfielen).

    Fuer Golden C ist das zugleich der Python-Nachweis von B9 bei
    Kaskadenquelle 'global' OHNE SMS-Bearbeitung: die ausgelieferte
    SMS-Reihenfolge muss der Editor-Reihenfolge folgen.
    """
    golden = golden_dict(golden_name)
    pfad = GOLDEN_DIR / f"nach_speichern_{golden_name}.json"
    if not pfad.exists():
        pytest.fail(_fehlt_hinweis(pfad))
    nach_speichern = json.loads(pfad.read_text())

    for kanal in erreichbare_kanaele(golden["report_config"]):
        erwartet = erwartete_kaskade(golden, kanal, report_type)
        ist = erwartete_kaskade(nach_speichern, kanal, report_type)
        assert ist == erwartet, (
            f"AC-5: {golden_name}/{kanal}/{report_type} -- Speichern ohne "
            f"Aenderung veraendert die Auslieferung: vorher={erwartet}, "
            f"nachher={ist}"
        )


def test_ac5_golden_c_sms_reihenfolge_gegen_erwartungsdatei(monkeypatch) -> None:
    """AC-5 (Golden C, explizit gegen ``erwartung_golden_c.json``): die
    TATSAECHLICH ausgelieferte SMS-Reihenfolge (evening, echter Renderer-
    Pfad -- kein Orakel-Selbstvergleich, sonst waere die Zusicherung
    tautologisch) folgt der eingefrorenen Editor-Erwartung -- eingeschraenkt
    auf die bei 'evening' tatsaechlich ausgelieferten Metriken (G4/K8 filtert
    ``cloud_low`` bei evening zusaetzlich heraus; das ist nicht Gegenstand
    dieses B9-spezifischen Tests, siehe report-typ-parametrisierter AC-5
    oben). Das ist der direkte, dateibasierte B9-Nachweis, den die Spec fuer
    Golden C explizit verlangt.

    RED heute: das Aktivierungs-Gate faellt bei Kaskadenquelle 'global' auf
    die feste POSITIONAL-Reihenfolge zurueck, die Editor-Erwartungsdatei
    zeigt aber die globale Reihenfolge."""
    erwartung_pfad = GOLDEN_DIR / "erwartung_golden_c.json"
    if not erwartung_pfad.exists():
        pytest.fail(
            f"AC-5: {erwartung_pfad} fehlt -- "
            f"'uv run python3 -m tests.helpers.erwartungsdateien_erzeugen' laufen lassen."
        )
    erwartung = json.loads(erwartung_pfad.read_text())
    erwartung_sms_ids = [m["metric_id"] for m in erwartung["channels"]["sms"]]

    mitschrift, _ = render_golden(monkeypatch, "golden_c")
    ist_ids, _ = parse_kanal(mitschrift, "sms")

    # Nur IDs vergleichen, die BEIDE Seiten fuehren -- die durch G4/K8
    # bedingte Abwesenheit von cloud_low bei evening ist ein separater
    # Befund (K8), nicht Gegenstand dieses B9-Tests.
    gemeinsam_erwartet = [mid for mid in erwartung_sms_ids if mid in ist_ids]
    gemeinsam_ist = [mid for mid in ist_ids if mid in erwartung_sms_ids]
    assert gemeinsam_ist == gemeinsam_erwartet, (
        f"AC-5/B9: Golden C -- die tatsaechlich ausgelieferte SMS-Reihenfolge "
        f"weicht von der Editor-Erwartungsdatei ab.\nausgeliefert="
        f"{gemeinsam_ist}\nerwartung={gemeinsam_erwartet}"
    )


# ═══════════ AC-15/AC-16 (Aenderungspfad: "ich stelle X ein, Y kommt an") ════


def _lade_aenderungsfaelle() -> dict:
    return json.loads((GOLDEN_DIR / "aenderungsfaelle.json").read_text())


_AENDERUNGSFAELLE = _lade_aenderungsfaelle()


@pytest.mark.parametrize("fall", sorted(_AENDERUNGSFAELLE))
def test_ac15_aenderung_kommt_wie_eingestellt_an(fall: str) -> None:
    """AC-15: die Projektion aus ``nach_aenderung_<fall>.json`` (gespeicherter
    Stand) stimmt mit der Projektion aus ``nach_aenderung_<fall>_anzeige.json``
    (Editor-Anzeige nach derselben Aenderung) ueberein -- ohne Ausnahme, auch
    fuer Fall 4 (SMS-Erstbearbeitung). Report-typ-neutraler 'anzeige'-Sentinel
    (dieselbe Wahrheit wie ``erwartung_golden_*.json`` -- der Editor selbst
    ist nicht report-typ-gesplittet)."""
    nach_pfad = GOLDEN_DIR / f"nach_aenderung_{fall}.json"
    anzeige_pfad = GOLDEN_DIR / f"nach_aenderung_{fall}_anzeige.json"
    if not nach_pfad.exists() or not anzeige_pfad.exists():
        pytest.fail(
            f"AC-15: {nach_pfad.name}/{anzeige_pfad.name} fehlen -- werden "
            f"in /50 aus der TS-Aenderungs-Simulation erzeugt "
            f"(aenderungsfaelle.json::{fall}). ROT NUR WEGEN FEHLENDER "
            f"/50-DATEI, kein B9/K8-Befund."
        )
    nach = json.loads(nach_pfad.read_text())
    anzeige = json.loads(anzeige_pfad.read_text())

    # AC-15 gilt "je Kanal" -- alle drei Reiter, nicht nur der bearbeitete
    # (fuer die unbearbeiteten Reiter ist das zugleich die B9-/No-Op-
    # Zusicherung aus AC-5, hier fuer den Aenderungsfall mitgeprueft).
    for pruef_reiter, orakel_kanal in _REITER_ZU_ORAKEL_KANAL.items():
        erwartet = anzeige["channels"][pruef_reiter]
        ist = [
            {"metric_id": mid, "friendly": friendly}
            for mid, friendly in erwartete_kaskade(nach, orakel_kanal, ANZEIGE_REPORT_TYPE)
        ]
        assert ist == erwartet, (
            f"AC-15: {fall}/{pruef_reiter} -- gespeicherter Stand liefert eine "
            f"andere Auswahl/Reihenfolge/Roh-Einfach als die Editor-Anzeige "
            f"nach der Aenderung.\nist={ist}\nerwartet={erwartet}"
        )


@pytest.mark.parametrize("fall", sorted(_AENDERUNGSFAELLE))
def test_ac16_aenderung_hat_tatsaechlich_gewirkt(fall: str) -> None:
    """AC-16 (Plausibilitaet): die Projektion aus ``nach_aenderung_<fall>.json``
    unterscheidet sich von der Original-Golden-Projektion GENAU um die
    eingestellte Aenderung (aenderungsfaelle.json) und sonst nirgends --
    schliesst einen zufaellig gruenen No-Op-Fehlschluss aus."""
    definition = _AENDERUNGSFAELLE[fall]
    golden_name = definition["golden"]
    reiter = definition["channel"]
    orakel_kanal = _REITER_ZU_ORAKEL_KANAL[reiter]
    nach_pfad = GOLDEN_DIR / f"nach_aenderung_{fall}.json"
    if not nach_pfad.exists():
        pytest.fail(
            f"AC-16: {nach_pfad.name} fehlt -- wird in /50 aus der "
            f"TS-Aenderungs-Simulation erzeugt (aenderungsfaelle.json::"
            f"{fall}). ROT NUR WEGEN FEHLENDER /50-DATEI, kein B9/K8-Befund."
        )
    golden = golden_dict(golden_name)
    nach = json.loads(nach_pfad.read_text())

    vorher = [mid for mid, _ in erwartete_kaskade(golden, orakel_kanal, ANZEIGE_REPORT_TYPE)]
    nachher = [mid for mid, _ in erwartete_kaskade(nach, orakel_kanal, ANZEIGE_REPORT_TYPE)]

    kind = definition["kind"]
    if kind == "deselect":
        mid = definition["metric_id"]
        assert mid in vorher and mid not in nachher, (
            f"AC-16 {fall}: {mid!r} muss nach der Abwahl im Kanal {reiter!r} "
            f"fehlen -- vorher={vorher}, nachher={nachher}"
        )
        assert nachher == [m for m in vorher if m != mid], (
            f"AC-16 {fall}: alle anderen Metriken muessen in gleicher "
            f"Reihenfolge bleiben -- vorher={vorher}, nachher={nachher}"
        )
    elif kind == "swap":
        a, b = definition["metric_a"], definition["metric_b"]
        assert a in vorher and b in vorher and vorher.index(a) < vorher.index(b), (
            f"Testaufbau {fall}: {a!r} muss vor {b!r} im Original-Golden "
            f"stehen -- vorher={vorher}"
        )
        erwartete_nachher = list(vorher)
        ia, ib = erwartete_nachher.index(a), erwartete_nachher.index(b)
        erwartete_nachher[ia], erwartete_nachher[ib] = erwartete_nachher[ib], erwartete_nachher[ia]
        assert nachher == erwartete_nachher, (
            f"AC-16 {fall}: {a!r}/{b!r} muessen GENAU ihre Position "
            f"tauschen -- erwartet={erwartete_nachher}, nachher={nachher}"
        )
    elif kind == "format_toggle":
        mid = definition["metric_id"]
        vorher_friendly = dict(erwartete_kaskade(golden, orakel_kanal, ANZEIGE_REPORT_TYPE))[mid]
        nachher_friendly = dict(erwartete_kaskade(nach, orakel_kanal, ANZEIGE_REPORT_TYPE))[mid]
        assert vorher_friendly == definition["from_friendly"], (
            f"Testaufbau {fall}: {mid!r} muss im Original-Golden "
            f"friendly={definition['from_friendly']} sein"
        )
        assert nachher_friendly == definition["to_friendly"], (
            f"AC-16 {fall}: {mid!r} muss nach der Aenderung "
            f"friendly={definition['to_friendly']} sein, war {nachher_friendly!r}"
        )
        assert nachher == vorher, (
            f"AC-16 {fall}: Auswahl/Reihenfolge duerfen sich bei einem "
            f"reinen Roh/Einfach-Wechsel nicht aendern -- vorher={vorher}, "
            f"nachher={nachher}"
        )
    elif kind == "deselect_and_swap":
        mid = definition["deselect_metric_id"]
        a, b = definition["metric_a"], definition["metric_b"]
        assert mid in vorher and mid not in nachher, (
            f"AC-16 {fall}: {mid!r} muss nach der Abwahl in {reiter!r} "
            f"fehlen -- vorher={vorher}, nachher={nachher}"
        )
        rest_vorher = [m for m in vorher if m != mid]
        assert a in rest_vorher and b in rest_vorher and rest_vorher.index(a) < rest_vorher.index(b), (
            f"Testaufbau {fall}: {a!r} muss vor {b!r} stehen (nach Abzug "
            f"von {mid!r}) -- rest_vorher={rest_vorher}"
        )
        ia, ib = rest_vorher.index(a), rest_vorher.index(b)
        rest_vorher[ia], rest_vorher[ib] = rest_vorher[ib], rest_vorher[ia]
        assert nachher == rest_vorher, (
            f"AC-16 {fall}: nach Abwahl von {mid!r} muessen {a!r}/{b!r} "
            f"GENAU ihre Position tauschen -- erwartet={rest_vorher}, "
            f"nachher={nachher}"
        )
    else:
        pytest.fail(f"Unbekannte Fall-Art {kind!r} in aenderungsfaelle.json::{fall}")

    # Alle anderen Kanaele bleiben gegenueber dem Original-Golden UNVERAENDERT
    # -- fuer JEDEN der vier Faelle (nicht nur Fall 4/deselect_and_swap), so
    # wie AC-16 es fuer die volle Kette vorschreibt: nur der bearbeitete
    # Reiter (``definition["channel"]``) darf abweichen.
    for anderer_reiter, anderer_kanal in _REITER_ZU_ORAKEL_KANAL.items():
        if anderer_reiter == reiter:
            continue
        v = [mid for mid, _ in erwartete_kaskade(golden, anderer_kanal, ANZEIGE_REPORT_TYPE)]
        n = [mid for mid, _ in erwartete_kaskade(nach, anderer_kanal, ANZEIGE_REPORT_TYPE)]
        assert v == n, (
            f"AC-16 {fall}: Kanal {anderer_reiter!r} muss gegenueber dem "
            f"Original-Golden unveraendert bleiben (nur {reiter!r} wurde "
            f"bearbeitet) -- vorher={v}, nachher={n}"
        )
