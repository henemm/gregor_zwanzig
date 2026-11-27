"""TDD RED -- Issue #1987 Scheibe S2: Ortsvergleich-Alarm schreibt Kanal-Merker
nur fuer ZUGESTELLTE Kanaele, je Versandgruppe.

SPEC: ``docs/specs/modules/fix_1987_s2_compare_kanal_anker.md`` -- AC-1,
AC-2, AC-3, AC-8 (additive Kanaldateien nach Zustellung), AC-9.

Gepruefte Zusicherung in einem Satz: nach
``send_multi_location_deviation_alert`` wird fuer jeden Ort einer Gruppe und
jeden Kanal in ``notif_result.delivered_channels`` DIESER Gruppe ein Merker
``{preset}__{loc}__alarm_{channel}.json`` geschrieben -- sonst keiner; das
Melde-Gedaechtnis, Throttle und Protokoll bleiben davon unberuehrt, ein
Schreibfehler am Merker kippt den Versand nicht.

Kanalwahl: die Spec nennt fuer AC-1 "SMS scheitert" als Beispiel. Im Kern
(ohne Netz) laesst sich Telegram deterministisch scheitern -- am ECHTEN
Telegram-Transport im Testmodus ohne zustellbaren Empfaenger (dieselben
Settings wie das S1-Pendant), gebucht als ``delivery_failed``. Deshalb steht hier
Telegram fuer den scheiternden Kanal; die Regel ist kanalneutral.

Angenommene API (Spec, Affected Files):
``CompareWeatherSnapshotService.save_alarm_anchor(preset, loc, point, channel)``
und ``.load_alarm_anchor(preset, loc, channel) -> list[PointWeatherData]``.

Mandantentrennung: jeder Test laeuft mit eindeutigen user_ids; AC-1 prueft
zusaetzlich, dass ein Lauf von Nutzer A im Baum von Nutzer B nichts schreibt.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from tests.helpers.briefing_imminent_fixtures import write_user_tier
from tests.helpers.alert_log_fixtures import (
    read_log,
    settings_email_and_failing_telegram,
)
from tests.tdd._compare_channel_anchor_fixtures import (
    ANKER_MM,
    FRISCH_HOCH_MM,
    FesteQuelle,
    FRISCH_NIEDRIG_MM,
    ORT_A,
    ORT_B,
    alarm_dateien,
    alarmlauf,
    basis_mm,
    basis_spion,
    briefing_anker,
    kanal_merker,
    lege_vergleich_an,
    letzter_eintrag,
    merker,
    nutzer,
    punkt,
    snapshot_dir,
    telegram_gescheitert,
    verzeichnis_stand,
)

EMAIL_ALT_MM = 5.0
TELEGRAM_ALT_MM = 6.0
# Dringlichkeit eines Orts kommt aus der Ampel (Muster
# test_compare_alert_channel_threshold.py): 13 mm -> gelb (LOW),
# 30 mm -> rot (HIGH). Ohne Ampel waeren beide Orte HIGH -> nur EINE Gruppe.
_AMPEL_GERING_HOCH = {
    "template": "allgemein",
    "metrics": {"precipitation": {
        "upper": {"yellow": 10, "orange": 20, "red": 29}, "alarm_ab": "yellow",
    }},
}


def _settings():
    s = settings_email_and_failing_telegram()
    assert s.can_send_email() and s.can_send_telegram(), (
        "Fixtur-Schutz: E-Mail muss zustellen koennen und Telegram muss "
        "betreten werden (und dort scheitern)."
    )
    return s


# ═════════════════════════════════ AC-1 ══════════════════════════════════════


def test_ac1_nur_zugestellter_kanal_bekommt_merker_je_ort_der_gruppe():
    """AC-1 (+ Mandantentrennung).

    GIVEN ein Ortsvergleich mit zwei Orten und den Kanaelen E-Mail und
          Telegram, je Ort ein Briefing-Anker und je Kanal ein alter Merker;
          ein zweiter Nutzer B mit identischen Kennungen und eigenen Merkern.
    WHEN  Nutzer A einen Alarm bekommt, den nur E-Mail zustellt (Telegram
          scheitert am echten Transport).
    THEN  traegt fuer JEDEN Ort der E-Mail-Merker den frischen Stand, der
          Telegram-Merker bleibt auf seinem Altstand (Wert + Zeitstempel), und
          im Baum von Nutzer B aendert sich nichts.

    HEUTE ROT: ``save_alarm_anchor`` existiert nicht (AttributeError).
    Mutation Spec Nr. 1 (``effective_channels`` statt ``delivered_channels``)
    liesse den Telegram-Merker vorruecken -> rot.
    """
    uid_a, uid_b, pid = nutzer("ac1a"), nutzer("ac1b"), "cp-s2-ac1"
    for uid in (uid_a, uid_b):
        lege_vergleich_an(uid, pid, orte=(ORT_A, ORT_B), send_telegram=True)
        for loc in (ORT_A[0], ORT_B[0]):
            briefing_anker(uid, pid, loc, ANKER_MM, alter=timedelta(hours=4))
            kanal_merker(uid, pid, loc, "email", EMAIL_ALT_MM, alter=timedelta(hours=3))
            kanal_merker(uid, pid, loc, "telegram", TELEGRAM_ALT_MM, alter=timedelta(hours=3))
    tg_vorher = {loc: merker(uid_a, pid, loc, "telegram").fetched_at for loc in (ORT_A[0], ORT_B[0])}
    b_vorher = verzeichnis_stand(uid_b)

    mails: list = []
    sent, _ = alarmlauf(uid_a, _settings(),
                        {ORT_A[0]: FRISCH_HOCH_MM, ORT_B[0]: FRISCH_HOCH_MM}, mails)

    assert sent == 1 and mails, "Fixtur-Schutz: der Alarm muss per E-Mail zugestellt sein."
    eintrag = letzter_eintrag(uid_a)
    assert eintrag["channels_sent"] == ["email"] and telegram_gescheitert(eintrag), (
        "Fixtur-Schutz: Zustellbilanz muss 'E-Mail zugestellt, Telegram gescheitert' lauten."
    )
    for loc in (ORT_A[0], ORT_B[0]):
        em = merker(uid_a, pid, loc, "email")
        assert em is not None and em.aggregated.precip_sum_mm == pytest.approx(FRISCH_HOCH_MM), (
            f"AC-1: E-Mail-Merker von {loc} muss den zugestellten Frischstand tragen."
        )
        tg = merker(uid_a, pid, loc, "telegram")
        assert tg.aggregated.precip_sum_mm == pytest.approx(TELEGRAM_ALT_MM), (
            f"AC-1: Telegram-Merker von {loc} darf nicht vorruecken (nicht zugestellt)."
        )
        assert tg.fetched_at == tg_vorher[loc], f"AC-1: Telegram-Merker {loc} wurde neu geschrieben."
    assert verzeichnis_stand(uid_b) == b_vorher, (
        "Mandantentrennung: der Lauf von Nutzer A hat im Baum von Nutzer B geschrieben."
    )


# ═════════════════════════════════ AC-2 ══════════════════════════════════════


def test_ac2_merker_nur_fuer_orte_der_zugestellten_gruppe():
    """AC-2.

    GIVEN zwei Orte mit verschieden dringlicher Aenderung (A: HIGH, B: LOW)
          und Kanal-Schwelle E-Mail=HIGH -> zwei Versandgruppen:
          Gruppe {A} per E-Mail (zugestellt) und Gruppe {A, B} per Telegram
          (scheitert).
    WHEN  der Versand abgeschlossen ist.
    THEN  hat nur Ort A einen E-Mail-Merker; Ort B bekommt keinen Merker,
          und kein Ort einen Telegram-Merker.

    HEUTE ROT: ``load_alarm_anchor`` existiert nicht (AttributeError).
    Mutation "Schreiben ueber ``delivered_all`` fuer alle Gruppen-Orte"
    gaebe Ort B einen E-Mail-Merker -> rot. Das greift nur, wenn die
    zugestellte Gruppe {A} VOR der gescheiterten {A, B} laeuft; die
    Gruppenfolge ist seit F001 (Fix-Loop 1) nach Ortsliste sortiert und
    damit unabhaengig von PYTHONHASHSEED.
    """
    uid, pid = nutzer("ac2"), "cp-s2-ac2"
    # Fixtur-Schutz Reihenfolge: der Versand sortiert die Gruppen nach ihrer
    # sortierten Ortsliste -- {A} muss also vor {A, B} kommen, sonst liefe die
    # gescheiterte Gruppe zuerst und die delivered_all-Mutation bliebe stumm.
    assert (ORT_A[0],) < tuple(sorted((ORT_A[0], ORT_B[0]))), (
        "Fixtur-Schutz: Gruppe {A} (E-Mail) muss vor Gruppe {A, B} (Telegram) laufen."
    )
    lege_vergleich_an(uid, pid, orte=(ORT_A, ORT_B), send_telegram=True,
                      alert_channel_thresholds={"email": "HIGH"},
                      display_config={"ampel": _AMPEL_GERING_HOCH})
    for loc in (ORT_A[0], ORT_B[0]):
        briefing_anker(uid, pid, loc, ANKER_MM, alter=timedelta(hours=2))

    mails: list = []
    sent, _ = alarmlauf(uid, _settings(),
                        {ORT_A[0]: FRISCH_HOCH_MM, ORT_B[0]: FRISCH_NIEDRIG_MM}, mails)

    assert sent == 1 and mails, "Fixtur-Schutz: Gruppe {A} muss per E-Mail zugestellt sein."
    eintrag = letzter_eintrag(uid)
    assert eintrag["channels_sent"] == ["email"], "Fixtur-Schutz: nur E-Mail zugestellt."
    assert telegram_gescheitert(eintrag), "Fixtur-Schutz: Telegram muss betreten und gescheitert sein."

    em_a = merker(uid, pid, ORT_A[0], "email")
    assert em_a is not None and em_a.aggregated.precip_sum_mm == pytest.approx(FRISCH_HOCH_MM), (
        "AC-2: Ort A (zugestellte Gruppe) braucht einen E-Mail-Merker mit Frischstand."
    )
    assert merker(uid, pid, ORT_B[0], "email") is None, (
        "AC-2: Ort B war nicht in der zugestellten E-Mail-Gruppe -- kein E-Mail-Merker."
    )
    for loc in (ORT_A[0], ORT_B[0]):
        assert merker(uid, pid, loc, "telegram") is None, (
            f"AC-2: Telegram ist gescheitert -- kein Telegram-Merker fuer {loc}."
        )


# ═════════════════════════════════ AC-3 ══════════════════════════════════════


def test_ac3_ohne_jede_zustellung_entsteht_kein_merker():
    """AC-3.

    GIVEN ein Ortsvergleich, dessen einziger Alarmkanal Telegram ist, mit
          vorbelegten Merkern fuer E-Mail und Telegram.
    WHEN  ein Alarm laeuft, den kein Kanal zustellt (Transportfehler).
    THEN  entsteht keine neue ``__alarm_*``-Datei, und die vorhandenen
          Merker bleiben unveraendert.

    HEUTE ROT: ``save_alarm_anchor`` existiert nicht (AttributeError).
    """
    uid, pid = nutzer("ac3"), "cp-s2-ac3"
    lege_vergleich_an(uid, pid, send_email=False, send_telegram=True)
    briefing_anker(uid, pid, ORT_A[0], ANKER_MM, alter=timedelta(hours=4))
    kanal_merker(uid, pid, ORT_A[0], "email", EMAIL_ALT_MM, alter=timedelta(hours=3))
    kanal_merker(uid, pid, ORT_A[0], "telegram", TELEGRAM_ALT_MM, alter=timedelta(hours=3))
    vorher = verzeichnis_stand(uid)
    dateien_vorher = alarm_dateien(uid)

    mails: list = []
    sent, _ = alarmlauf(uid, _settings(), {ORT_A[0]: FRISCH_HOCH_MM}, mails)

    assert not mails, "Fixtur-Schutz: E-Mail ist hier nicht konfiguriert."
    eintrag = letzter_eintrag(uid)
    assert eintrag["channels_sent"] == [] and telegram_gescheitert(eintrag), (
        "Fixtur-Schutz: der Versand muss versucht und von keinem Kanal zugestellt sein."
    )
    assert sent == 0
    assert alarm_dateien(uid) == dateien_vorher, "AC-3: ohne Zustellung keine neue Merker-Datei."
    assert verzeichnis_stand(uid) == vorher, "AC-3: kein Merker darf neu geschrieben werden."


# ═════════════════════════════════ AC-8 ══════════════════════════════════════


def test_ac8_nach_zustellung_kommen_kanaldateien_additiv_zur_bestandsdatei():
    """AC-8 (Schreibhaelfte).

    GIVEN ein Bestands-Ortsvergleich nur mit der kanallosen Briefing-Datei.
    WHEN  ein Alarm per E-Mail zugestellt wird (Telegram scheitert).
    THEN  bleibt die Briefing-Datei byte-gleich (Zeitstempel + Groesse), und
          es kommt genau ein E-Mail-Merker additiv hinzu.

    HEUTE ROT: kein Merker wird geschrieben (``alarm_dateien`` leer).
    """
    uid, pid = nutzer("ac8w"), "cp-s2-ac8w"
    lege_vergleich_an(uid, pid, send_telegram=True)
    briefing_anker(uid, pid, ORT_A[0], ANKER_MM, alter=timedelta(hours=3))
    briefing_name = f"{pid}__{ORT_A[0]}.json"
    vorher = verzeichnis_stand(uid)[briefing_name]

    mails: list = []
    sent, _ = alarmlauf(uid, _settings(), {ORT_A[0]: FRISCH_HOCH_MM}, mails)

    assert sent == 1 and mails, "Fixtur-Schutz: E-Mail muss zugestellt sein."
    assert verzeichnis_stand(uid)[briefing_name] == vorher, (
        "AC-8: die Bestandsdatei darf durch den Alarm nicht angefasst werden."
    )
    assert alarm_dateien(uid) == {f"{pid}__{ORT_A[0]}__alarm_email.json"}, (
        f"AC-8: erwartet genau einen additiven E-Mail-Merker, vorgefunden {alarm_dateien(uid)!r}."
    )


# ═════════════════════════════════ AC-9 ══════════════════════════════════════


def _stand_nach_lauf(uid: str, pid: str) -> dict:
    from services.alert_state import AlertStateService
    from services.throttle_store import ThrottleStore

    state = AlertStateService(user_id=uid).load(f"{pid}:{ORT_A[0]}")
    eintrag = letzter_eintrag(uid)
    return {
        "state": {k: v["last_reported_value"] for k, v in state.items()},
        "throttled": ThrottleStore(uid).is_throttled(
            "compare_preset", pid, 120, datetime.now(timezone.utc),
        ),
        "protokoll": {k: eintrag.get(k) for k in (
            "channels_sent", "changes_count", "severity", "reason", "entity_id",
        )},
        "protokoll_anzahl": len(read_log(uid)["entries"]),
    }


def test_ac9_merker_aendert_gedaechtnis_throttle_protokoll_nicht_und_schreibfehler_kippt_versand_nicht():
    """AC-9.

    GIVEN zwei identische Ortsvergleiche bei zwei Nutzern; bei Nutzer B ist
          der Pfad des E-Mail-Merkers vorab als VERZEICHNIS belegt
          (Schreibfehler am Merker).
    WHEN  bei beiden derselbe Alarm per E-Mail zugestellt wird.
    THEN  sind Melde-Gedaechtnis, Throttle und Protokolleintrag bei beiden
          gleich (das Merker-Schreiben veraendert sie nicht), B gilt
          trotzdem als zugestellt, und nur A hat einen lesbaren E-Mail-Merker.

    HEUTE ROT: A hat keinen E-Mail-Merker (``load_alarm_anchor`` fehlt).
    """
    uid_a, uid_b, pid = nutzer("ac9a"), nutzer("ac9b"), "cp-s2-ac9"
    for uid in (uid_a, uid_b):
        lege_vergleich_an(uid, pid, send_telegram=True)
        briefing_anker(uid, pid, ORT_A[0], ANKER_MM, alter=timedelta(hours=3))
    blockiert = snapshot_dir(uid_b) / f"{pid}__{ORT_A[0]}__alarm_email.json"
    blockiert.mkdir(parents=True)

    staende = {}
    for uid in (uid_a, uid_b):
        mails: list = []
        sent, _ = alarmlauf(uid, _settings(), {ORT_A[0]: FRISCH_HOCH_MM}, mails)
        assert sent == 1 and mails, f"AC-9: Versand bei {uid} muss als zugestellt gelten."
        staende[uid] = _stand_nach_lauf(uid, pid)

    a, b = staende[uid_a], staende[uid_b]
    assert a["state"], "Fixtur-Schutz: das Melde-Gedaechtnis muss nach Zustellung gefuellt sein."
    assert a["protokoll"]["channels_sent"] == ["email"], "Fixtur-Schutz: nur E-Mail zugestellt."
    assert a == b, (
        "AC-9: Gedaechtnis/Throttle/Protokoll muessen mit und ohne erfolgreiches "
        f"Merker-Schreiben gleich sein: A={a!r} B={b!r}."
    )
    assert blockiert.is_dir(), "Fixtur-Schutz: der blockierte Pfad bleibt ein Verzeichnis."
    em_a = merker(uid_a, pid, ORT_A[0], "email")
    assert em_a is not None and em_a.aggregated.precip_sum_mm == pytest.approx(FRISCH_HOCH_MM), (
        "AC-9: bei Nutzer A muss der E-Mail-Merker geschrieben sein."
    )


# ═══════════════════ Merker-Datum aus der Basis (F002) ═══════════════════════


class _QuelleOhneDatum(FesteQuelle):
    """Echte Unterklasse der festen Quelle (kein Mock): liefert den
    Frischpunkt stets OHNE ``target_date`` -- wie eine Wetterquelle, die den
    uebergebenen Tagesbezug nicht zurueckspiegelt."""

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None, **kw):
        self.aufrufe.append({"point_id": point_id, **kw})
        return punkt(point_id, self._werte.get(point_id, 0.0), target_date=None)


def _lauf_mit(uid: str, quelle, mails: list) -> int:
    from services.compare_alert import CompareAlertService

    return CompareAlertService(
        settings=_settings(), user_id=uid, weather_source=quelle,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    ).check_all_compare_presets()


def test_merker_uebernimmt_datum_der_basis_wenn_frischpunkt_keins_traegt(monkeypatch):
    """Spec "Herkunft von target_date am geschriebenen Merker" (+ AC-6).

    GIVEN ein Ortsvergleich nur mit E-Mail, ein DATIERTER Briefing-Anker, und
          eine Wetterquelle, die den Frischpunkt ohne ``target_date`` liefert.
    WHEN  ein Alarm per E-Mail zugestellt wird und danach ein zweiter
          Alarmlauf (ohne neue Abweichung) die Basis bestimmt.
    THEN  traegt der geschriebene E-Mail-Merker das Datum des Briefing-Ankers,
          und der zweite Lauf vergleicht gegen DIESEN Merker (er ist neuer als
          der Briefing-Anker und besteht den Tagesbezug-Guard).

    Mutationen ``pass`` statt ``dataclasses.replace`` bzw. ``if False:``
    liessen den Merker undatiert -> Guard verwirft ihn -> Basis waere der
    Briefing-Anker (2 mm) -> rot.
    """
    uid, pid = nutzer("f002"), "cp-s2-f002"
    tag = date.today() + timedelta(days=1)
    lege_vergleich_an(uid, pid)
    # Tageslimit aus: der Folgelauf soll die Basis auswerten, nicht am
    # free-Limit (ein Abweichungsalarm je Tag) enden.
    write_user_tier(uid, "premium")
    briefing_anker(uid, pid, ORT_A[0], ANKER_MM, alter=timedelta(hours=4), target_date=tag)

    mails: list = []
    quelle = _QuelleOhneDatum({ORT_A[0]: FRISCH_HOCH_MM})
    sent = _lauf_mit(uid, quelle, mails)

    assert sent == 1 and mails, "Fixtur-Schutz: der Alarm muss per E-Mail zugestellt sein."
    assert quelle.aufrufe and quelle.aufrufe[0].get("target_date") == tag, (
        "Fixtur-Schutz: der Abruf muss den Tagesbezug des Briefing-Ankers erhalten haben."
    )
    em = merker(uid, pid, ORT_A[0], "email")
    assert em is not None and em.aggregated.precip_sum_mm == pytest.approx(FRISCH_HOCH_MM), (
        "Fixtur-Schutz: der E-Mail-Merker muss den zugestellten Frischstand tragen."
    )
    assert em.target_date == tag, (
        f"Merker muss das Datum der Basis ({tag}) uebernehmen, traegt {em.target_date!r}."
    )

    # Sperrzeit des ersten Versands ueber die echte Store-API beenden, damit
    # der Folgelauf die Basis tatsaechlich auswertet.
    from services.throttle_store import ThrottleStore

    ThrottleStore(uid).clear("compare_preset", pid)
    gesehen = basis_spion(monkeypatch)
    _lauf_mit(uid, _QuelleOhneDatum({ORT_A[0]: FRISCH_HOCH_MM}), [])
    assert basis_mm(gesehen) == pytest.approx(FRISCH_HOCH_MM), (
        "Folgelauf muss den datierten E-Mail-Merker als Basis nehmen, nicht den "
        "aelteren Briefing-Anker."
    )
