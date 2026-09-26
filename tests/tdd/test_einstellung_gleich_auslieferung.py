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

import pytest

from app.models import UnifiedWeatherDisplayConfig
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
    parse_email_html,
    parse_email_plain,
    register_validieren,
    rote_zellen_beide_goldens,
    rote_zellen_fuer_golden,
    veraltete_eintraege,
)
from tests.tdd._einstellung_auslieferung_fixtures import golden_dict, render_golden

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
        trip = load_trip(data)
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

    Zugleich der Beleg fuer AC-3 (Orakel-Unabhaengigkeit): die Orakel-Funktion
    importiert nichts aus ``app.models`` (Code-Review-Beleg unten) -- bliebe
    sie heimlich an ``_sorted_by_layout`` gekoppelt, waere M1 unsichtbar,
    weil beide Seiten gleich falsch wuerden.
    """
    import app.models as models_mod
    import inspect

    from tests.helpers import einstellung_auslieferung_orakel as orakel_mod
    quelle = inspect.getsource(orakel_mod)
    assert "from app.models import" not in quelle and "import app.models" not in quelle, (
        "AC-3: die Orakel-Funktion darf nichts aus app.models importieren."
    )

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


def test_ac12_keine_rote_zelle_durch_fehlende_rohdaten(monkeypatch):
    """AC-12 (synthetische Voll-Wetter-Fixture).

    Given die neue synthetische Voll-Wetter-Fixture belegt ALLE Felder, die
    den bestehenden ``openmeteo``-Fixtures fehlen (humidity, dewpoint,
    pressure, wind_chill_c, cloud_mid/high, precip_type, snow_new_24h).
    When beide Goldens damit gerendert werden.
    Then enthaelt die E-Mail-Klartext-Tabelle keinen Platzhalter fuer eine
    Metrik, die dort laut Orakel aktiv sein soll -- AUSSER der bekannten
    Telegram-Geisterspalte (B5, eigener roter Befund, keine Datenluecke) und
    den erlaubten SMS-Nullformen (z.B. ``TH+:-``).

    Bewusst NUR Klartext (nicht HTML): ``thunder`` traegt in der HTML-Tabelle
    eine farbige Ampel-Punkt-Darstellung statt Text (``trip_report.py``
    ``_AMPEL_CAPABLE_METRIC_IDS``-Nachbarschaft) -- das ist eine
    Darstellungsentscheidung, keine fehlende Rohdaten-Zelle; die zugrunde
    liegenden Rohdaten sind vorhanden (dieselbe Groesse steht textuell im
    Klartext-Teil derselben Mail).
    """
    gb = golden_dict("golden_b")
    mit_b, _ = render_golden(monkeypatch, "golden_b")

    email_sendung = mit_b.sendungen("email")[0]
    ids_plain, modi_plain = parse_email_plain(email_sendung["plain_text_body"])

    erwartet_email = {mid for mid, _ in erwartete_kaskade(gb, "email_html", "evening")}
    for mid in erwartet_email:
        if mid in ids_plain:
            assert modi_plain.get(mid) is not None, (
                f"AC-12: {mid!r} zeigt in der E-Mail-Klartext-Tabelle einen "
                f"Platzhalter statt eines Wertes."
            )


# ═══════════════════════════ AC-13 ═══════════════════════════════════════════


def test_ac13_naht_liegt_nur_am_transport(monkeypatch):
    """AC-13 (Naht nur am Transport).

    Given ``EmailOutput``/``SMSOutput``/``PremiumSmsOutput``/``TelegramOutput``
    werden per ``monkeypatch.setattr`` durch den Aufzeichner ersetzt.
    When beide Goldens versendet werden.
    Then laufen Loader, Kaskade und Formatter unveraendert echt -- der
    Aufzeichner erfasst den vollstaendigen, durch echte Formatierung
    erzeugten Text je Kanal (golden-spezifische Wetterwerte aus der
    Voll-Wetter-Fixture, nicht nur Metrik-Labels -- ein vom Test selbst
    vorgegebener Text kaeme ohne echten Formatter-Lauf nicht zustande).
    """
    mit_b, _ = render_golden(monkeypatch, "golden_b")
    email = mit_b.sendungen("email")[0]
    assert "45" in email["plain_text_body"], (
        "AC-13: der konkrete Boen-Wert (45 km/h) aus der Voll-Wetter-Fixture "
        "muss im echt formatierten Klartext stehen."
    )
    assert "45" in email["body"], (
        "AC-13: derselbe Wert muss auch im echt formatierten HTML stehen."
    )
    sms = mit_b.sendungen("sms")[0]["body"]
    assert "45" in sms, "AC-13: die SMS traegt denselben Boen-Wert."
    telegram_texte = " ".join(s["body"] for s in mit_b.sendungen("telegram"))
    assert "45" in telegram_texte, "AC-13: Telegram traegt denselben Boen-Wert."
