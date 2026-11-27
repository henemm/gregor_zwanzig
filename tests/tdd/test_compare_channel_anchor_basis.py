"""TDD RED -- Issue #1987 Scheibe S2: Basis-Aufloesung des Ortsvergleich-Alarms
je Kanal ("Variante B'").

SPEC: ``docs/specs/modules/fix_1987_s2_compare_kanal_anker.md`` -- AC-4, AC-5,
AC-6, AC-7, AC-8, AC-12.

Regel: je Kanal c der rohen ``config.channels`` gilt
basis_c = neuester gueltiger Stand aus {Briefing-Anker, Merker c}; gueltig =
Alter <= 26 h UND (Merker nur, wenn sein ``target_date`` dem des
Briefing-Ankers gleicht; beide leer = gleich); nie Merker fremder Kanaele.
Der gemeinsame Lauf vergleicht gegen die AELTESTE basis_c.

Beobachtet wird ausschliesslich Verhalten, nicht Namen neuer Hilfsfunktionen:
der an ``DeviationAlertEngine.evaluate`` uebergebene ``cached``-Wert
(aufzeichnender Wrapper, die echte Methode laeuft weiter -- kein Mock) und das
an den Frisch-Abruf uebergebene ``target_date``. Die Staende sind ueber
eindeutige Niederschlagswerte unterscheidbar (1.0 / 2.0 / 3.0 mm), ihr Alter
ueber praepariertes ``fetched_at``. Der Frischwert entspricht keinem Stand so
weit, dass ein Versand die Beobachtung stoeren koennte (kein Ausloesen noetig).

Kanaele: E-Mail (geerbt) und -- wo zwei Kanaele gebraucht werden -- Telegram
ueber ``send_telegram`` (kein Tarif-Gate, anders als SMS/Premium-SMS).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.helpers.alert_log_fixtures import read_log, settings_email_and_failing_telegram
from tests.tdd._compare_channel_anchor_fixtures import (
    ALLE_KANAELE,
    ORT_A,
    alarmlauf,
    basis_mm,
    basis_spion,
    briefing_anker,
    kanal_merker,
    lege_vergleich_an,
    merker,
    nutzer,
    verzeichnis_stand,
)

BRIEFING_MM = 1.0
MERKER_1_MM = 2.0
MERKER_2_MM = 3.0
RUHIG_MM = 1.5  # Frischwert: Δ < Schwelle gegen jeden Stand -> kein Versand

LOC = ORT_A[0]


def _lauf(uid: str):
    return alarmlauf(uid, settings_email_and_failing_telegram(), {LOC: RUHIG_MM})


# ═════════════════════════════════ AC-4 ══════════════════════════════════════


@pytest.mark.parametrize(
    "briefing_alter_h, merker_alter_h, erwartet",
    [
        (5, 2, MERKER_1_MM),   # spaeterer Alarm-Merker loest aelteres Briefing ab
        (1, 4, BRIEFING_MM),   # spaeteres Briefing loest aelteren Merker ab
    ],
    ids=["merker_neuer", "briefing_neuer"],
)
def test_ac4_basis_eines_kanals_ist_der_neuere_der_beiden_staende(
    monkeypatch, briefing_alter_h, merker_alter_h, erwartet,
):
    """AC-4.

    GIVEN ein Ortsvergleich nur mit E-Mail, Briefing-Anker (1.0 mm) und
          E-Mail-Merker (2.0 mm) mit unterschiedlichem Alter.
    WHEN  der Alarmlauf die Basis bestimmt.
    THEN  bekommt ``evaluate`` den jeweils NEUEREN der beiden Staende.

    HEUTE ROT: ``save_alarm_anchor`` fehlt; fachlich liest der Bestand nur
    den Briefing-Anker (Fall "merker_neuer" waere 1.0 statt 2.0).
    """
    uid, pid = nutzer("ac4"), "cp-s2-ac4"
    lege_vergleich_an(uid, pid)
    briefing_anker(uid, pid, LOC, BRIEFING_MM, alter=timedelta(hours=briefing_alter_h))
    kanal_merker(uid, pid, LOC, "email", MERKER_1_MM, alter=timedelta(hours=merker_alter_h))
    gesehen = basis_spion(monkeypatch)

    _lauf(uid)

    assert basis_mm(gesehen) == pytest.approx(erwartet), (
        f"AC-4: Basis muss der neuere Stand ({erwartet} mm) sein, "
        f"gesehen {basis_mm(gesehen)} mm."
    )


# ═════════════════════════════════ AC-5 ══════════════════════════════════════


def test_ac5_gemeinsamer_lauf_vergleicht_gegen_die_aelteste_kanal_basis(monkeypatch):
    """AC-5.

    GIVEN E-Mail und Telegram; Briefing-Anker 8 h alt (1.0 mm), E-Mail-Merker
          2 h alt (2.0 mm, "09:00"), Telegram-Merker 5 h alt (3.0 mm, "06:00").
    WHEN  der gemeinsame Auswertungslauf die Basis des Ortes bestimmt.
    THEN  wird gegen die AELTERE Kanal-Basis verglichen (Telegram, 3.0 mm),
          damit auch die Aenderung zwischen 06:00 und 09:00 gemeldet wird.

    HEUTE ROT: ``save_alarm_anchor`` fehlt. Mutation Spec Nr. 2 ("juengste
    statt aelteste") lieferte 2.0 mm -> rot.
    """
    uid, pid = nutzer("ac5"), "cp-s2-ac5"
    lege_vergleich_an(uid, pid, send_telegram=True)
    briefing_anker(uid, pid, LOC, BRIEFING_MM, alter=timedelta(hours=8))
    kanal_merker(uid, pid, LOC, "email", MERKER_1_MM, alter=timedelta(hours=2))
    kanal_merker(uid, pid, LOC, "telegram", MERKER_2_MM, alter=timedelta(hours=5))
    gesehen = basis_spion(monkeypatch)

    _lauf(uid)

    assert basis_mm(gesehen) == pytest.approx(MERKER_2_MM), (
        "AC-5: der gemeinsame Lauf muss gegen die aelteste Kanal-Basis "
        f"(Telegram, {MERKER_2_MM} mm) vergleichen, gesehen {basis_mm(gesehen)} mm."
    )


# ═════════════════════════════════ AC-6 ══════════════════════════════════════


@pytest.mark.parametrize(
    "merker_tag_versatz, erwartet",
    [(-1, BRIEFING_MM), (0, MERKER_1_MM)],
    ids=["merker_gestern_ignoriert", "merker_gleicher_tag_gilt"],
)
def test_ac6_merker_mit_anderem_target_date_wird_ignoriert(
    monkeypatch, merker_tag_versatz, erwartet,
):
    """AC-6.

    GIVEN ein Briefing-Anker fuer HEUTE (6 h alt, 1.0 mm) und ein juengerer
          E-Mail-Merker (1 h alt, 2.0 mm) mit Tagesbezug gestern bzw. heute.
    WHEN  die Basis aufgeloest wird.
    THEN  gilt bei abweichendem Tag der Briefing-Anker, bei gleichem Tag der
          Merker; der Frisch-Abruf bekommt den Tag des Briefing-Ankers.

    HEUTE ROT: ``save_alarm_anchor`` fehlt. Mutation Spec Nr. 4 (Guard
    entfernt) liesse den gestrigen Merker gelten -> rot.
    """
    heute = date.today()
    uid, pid = nutzer("ac6"), "cp-s2-ac6"
    lege_vergleich_an(uid, pid)
    briefing_anker(uid, pid, LOC, BRIEFING_MM, alter=timedelta(hours=6), target_date=heute)
    kanal_merker(uid, pid, LOC, "email", MERKER_1_MM, alter=timedelta(hours=1),
                 target_date=heute + timedelta(days=merker_tag_versatz))
    gesehen = basis_spion(monkeypatch)

    _, quelle = _lauf(uid)

    assert basis_mm(gesehen) == pytest.approx(erwartet), (
        f"AC-6: erwartete Basis {erwartet} mm, gesehen {basis_mm(gesehen)} mm."
    )
    assert [a.get("target_date") for a in quelle.aufrufe] == [heute], (
        "AC-6: der Frisch-Abruf muss den Tagesbezug des Briefing-Ankers bekommen."
    )


# ═════════════════════════════════ AC-7 ══════════════════════════════════════


def test_ac7_nur_alte_staende_ort_uebersprungen_mit_diagnose(monkeypatch):
    """AC-7 (keine gueltige Basis).

    GIVEN Briefing-Anker 30 h alt und E-Mail-Merker 28 h alt.
    WHEN  der Alarmlauf laeuft.
    THEN  wird der Ort uebersprungen (kein ``evaluate``-Aufruf, kein Abruf)
          und die Diagnose ``too_old`` protokolliert -- kein Vergleich gegen
          einen erfundenen Stand.

    HEUTE ROT: ``save_alarm_anchor`` fehlt (der Rest ist Bestandsverhalten).
    """
    uid, pid = nutzer("ac7a"), "cp-s2-ac7a"
    lege_vergleich_an(uid, pid)
    briefing_anker(uid, pid, LOC, BRIEFING_MM, alter=timedelta(hours=30))
    kanal_merker(uid, pid, LOC, "email", MERKER_1_MM, alter=timedelta(hours=28))
    gesehen = basis_spion(monkeypatch)

    _, quelle = _lauf(uid)

    assert gesehen == [] and quelle.aufrufe == [], (
        "AC-7: ohne gueltigen Stand darf weder abgerufen noch ausgewertet werden."
    )
    gaps = [e.get("reference_gap") for e in read_log(uid)["not_delivered"]]
    assert "too_old" in gaps, f"AC-7: Diagnose 'too_old' fehlt, vorgefunden {gaps!r}."


def test_ac7_alter_briefing_anker_frischer_merker_gilt(monkeypatch):
    """AC-7 (Merker rettet die Basis).

    GIVEN Briefing-Anker 30 h alt (1.0 mm) und E-Mail-Merker 2 h alt (2.0 mm).
    WHEN  der Alarmlauf laeuft.
    THEN  wird gegen den Merker ausgewertet (nicht uebersprungen).

    HEUTE ROT: ``save_alarm_anchor`` fehlt; fachlich ueberspringt der Bestand
    den Ort wegen des zu alten Briefing-Ankers.
    """
    uid, pid = nutzer("ac7b"), "cp-s2-ac7b"
    lege_vergleich_an(uid, pid)
    briefing_anker(uid, pid, LOC, BRIEFING_MM, alter=timedelta(hours=30))
    kanal_merker(uid, pid, LOC, "email", MERKER_1_MM, alter=timedelta(hours=2))
    gesehen = basis_spion(monkeypatch)

    _lauf(uid)

    assert basis_mm(gesehen) == pytest.approx(MERKER_1_MM), (
        "AC-7: der frische Merker muss den zu alten Briefing-Anker ersetzen."
    )


# ═════════════════════════════════ AC-8 ══════════════════════════════════════


def test_ac8_bestandsdaten_briefing_anker_ist_basis_aller_kanaele(monkeypatch):
    """AC-8 (Lesehaelfte).

    GIVEN ein Bestands-Ortsvergleich mit E-Mail und Telegram, nur der
          kanallosen Briefing-Datei, keiner Kanaldatei.
    WHEN  der erste Alarmlauf nach dem Deploy laeuft (ohne Versand).
    THEN  ist der Briefing-Anker die Basis, die Datei bleibt unveraendert, und
          fuer keinen der vier Kanaele existiert ein Merker.

    HEUTE ROT: ``load_alarm_anchor`` fehlt (die Basis selbst stimmt heute).
    """
    uid, pid = nutzer("ac8r"), "cp-s2-ac8r"
    lege_vergleich_an(uid, pid, send_telegram=True)
    briefing_anker(uid, pid, LOC, BRIEFING_MM, alter=timedelta(hours=3))
    vorher = verzeichnis_stand(uid)
    gesehen = basis_spion(monkeypatch)

    _lauf(uid)

    assert basis_mm(gesehen) == pytest.approx(BRIEFING_MM), "AC-8: Briefing-Anker muss Basis sein."
    assert verzeichnis_stand(uid) == vorher, "AC-8: Bestandsdatei darf sich nicht aendern."
    for channel in ALLE_KANAELE:
        assert merker(uid, pid, LOC, channel) is None, (
            f"AC-8: ohne Zustellung darf fuer {channel} kein Merker entstehen."
        )


# ═════════════════════════════════ AC-12 ═════════════════════════════════════


def test_ac12_kanal_ohne_merker_nutzt_nie_den_merker_eines_anderen_kanals(monkeypatch):
    """AC-12.

    GIVEN E-Mail und Telegram; Briefing-Anker 6 h alt (1.0 mm) und nur fuer
          E-Mail ein frischerer Merker (1 h alt, 2.0 mm).
    WHEN  die Basis fuer Telegram (ohne eigenen Merker) aufgeloest wird.
    THEN  gilt fuer Telegram allein der Briefing-Anker; da der gemeinsame
          Lauf die aelteste Kanal-Basis nimmt, sieht ``evaluate`` 1.0 mm.

    HEUTE ROT: ``save_alarm_anchor`` fehlt. Mutation Spec Nr. 3 ("Rueckfall
    auf anderen Kanal") machte die Telegram-Basis zum E-Mail-Merker -> 2.0 mm.
    """
    uid, pid = nutzer("ac12"), "cp-s2-ac12"
    lege_vergleich_an(uid, pid, send_telegram=True)
    briefing_anker(uid, pid, LOC, BRIEFING_MM, alter=timedelta(hours=6))
    kanal_merker(uid, pid, LOC, "email", MERKER_1_MM, alter=timedelta(hours=1))
    gesehen = basis_spion(monkeypatch)

    _lauf(uid)

    assert basis_mm(gesehen) == pytest.approx(BRIEFING_MM), (
        "AC-12: Telegram ohne eigenen Merker muss den Briefing-Anker nutzen; "
        f"gesehen {basis_mm(gesehen)} mm (Kontamination durch den E-Mail-Merker?)."
    )
    assert merker(uid, pid, LOC, "telegram") is None, "Fixtur-Schutz: Telegram hat keinen Merker."
