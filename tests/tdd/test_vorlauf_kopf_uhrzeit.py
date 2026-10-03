"""TDD RED — Issue #2261 Teil A (A-1), AC-9: Kopf nennt bei fernem Beginn die
Uhrzeit statt der Restminuten.

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md — AC-9, Implementation
Details §6.

Mit der Schwelle auf dem Quell-Horizont (180 Min) entstehen Alarme mit
Beginn in 170 Minuten. "Regen in 170 Min" ist auf der Huette nicht lesbar;
ab `onset_minutes > LOCATION_SHARPNESS_LIMIT_MIN` (60) nennt der KOPF
(Betreff, E-Mail-H1, E-Mail-Buendelzeile, Telegram-Kopf -- alle ueber
`_onset_wann_kopf`) die Uhrzeit mit Tagesbezug in der Form des SMS-Bausteins
`_sms_onset_time` ("ab 14:10", ueber Mitternacht "ab Mi0:23"). Bis
einschliesslich 60 bleibt "in N Min", "laeuft bereits" bleibt.

Das Praefix "ab " ist das Beispiel der Spec selbst (AC-9: z. B. "ab 14:10").

Kein Mock: echte `OnsetEvent`/`AlertMessage`-Objekte durch die echten
Renderer (`render_subject`/`render_email`/`render_telegram`), feste
`onset_time`-Werte (Muster `test_alert_onset_day_rollover.py`). Den Weg
durch die echte Pruefstrecke inklusive Tagesbezug bewacht
`test_vorlauf_kanalparitaet.py` (AC-10).
"""
from __future__ import annotations

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_email, render_subject, render_telegram


def _event(**kw) -> OnsetEvent:
    felder = dict(
        onset_minutes=170, onset_time="14:10", km_from=3.0, km_to=3.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="INCA",
    )
    felder.update(kw)
    return OnsetEvent(**felder)


def _msg(*events: OnsetEvent) -> AlertMessage:
    return AlertMessage(
        trip_short="KHW Test", stand_at="11:20", events=tuple(events),
        source="radar",
    )


def _koepfe(e: OnsetEvent) -> dict[str, str]:
    """Alle Kopf-Wirkorte eines Einzel-Alarms: Betreff, E-Mail (HTML und
    Klartext, beide tragen die H1) und Telegram-Kopfzeile."""
    msg = _msg(e)
    html, plain = render_email(msg)
    telegram = render_telegram(msg)
    return {
        "Betreff": render_subject(msg),
        "E-Mail-HTML": html,
        "E-Mail-Klartext": plain,
        "Telegram-Kopf": telegram.split("\n", 1)[0],
    }


def _buendel_zeilen(*events: OnsetEvent) -> dict[str, str]:
    html, plain = render_email(_msg(*events))
    return {"Buendel-HTML": html, "Buendel-Klartext": plain}


# ═══════════════════════════════ AC-9 ═════════════════════════════════════


def test_kopf_nennt_uhrzeit_bei_onset_ueber_60():
    """AC-9: Given ein Alarm mit Onset 170 (Beginn 14:10, gleicher Tag)
    When Betreff, E-Mail-Kopf und Telegram-Kopf gerendert werden
    Then nennt jeder Kopf "Regen ab 14:10" und an KEINER Stelle "in 170 Min".
    Grenzfall 61 (knapp ueber `LOCATION_SHARPNESS_LIMIT_MIN`) schaltet
    ebenfalls auf die Uhrzeit; ebenso die E-Mail-Buendelzeile des
    Ortsvergleichs.

    RED heute: `_onset_wann_kopf` liefert immer "in N Min"."""
    for minuten, uhrzeit in ((170, "14:10"), (61, "12:21")):
        e = _event(onset_minutes=minuten, onset_time=uhrzeit)
        for wo, text in _koepfe(e).items():
            assert f"Regen ab {uhrzeit}" in text, (
                f"AC-9: {wo} muss bei Onset {minuten} (> 60) die Uhrzeit "
                f"'Regen ab {uhrzeit}' nennen (Form des SMS-Bausteins "
                f"_sms_onset_time). Fehlender Schritt: _onset_wann_kopf "
                f"schaltet oberhalb LOCATION_SHARPNESS_LIMIT_MIN nicht auf "
                f"die Uhrzeit um.\n{text}"
            )
            assert f"in {minuten} Min" not in text, (
                f"AC-9: {wo} nennt bei Onset {minuten} noch die Restminuten "
                f"'in {minuten} Min'.\n{text}"
            )

    a = _event(location_label="Ort A", onset_minutes=170, onset_time="14:10")
    b = _event(location_label="Ort B", onset_minutes=40, onset_time="12:20")
    for wo, text in _buendel_zeilen(a, b).items():
        assert "Ort A · Regen ab 14:10" in text, (
            f"AC-9: {wo}: die Buendelzeile des fernen Orts muss die Uhrzeit "
            f"tragen ('Ort A · Regen ab 14:10').\n{text}"
        )
        assert "in 170 Min" not in text, (
            f"AC-9: {wo} nennt noch 'in 170 Min'.\n{text}"
        )
        assert "Ort B · Regen in 40 Min" in text, (
            f"AC-9: {wo}: der nahe Ort (Onset 40) behaelt die Restminuten.\n{text}"
        )


def test_kopf_bleibt_restminuten_bis_60():
    """AC-9: Given Onset 40 bzw. genau 60 (Grenze einschliesslich)
    When die Koepfe gerendert werden
    Then bleibt "in 40 Min" bzw. "in 60 Min" -- keine Uhrzeit im Kopf.

    Regressionswaechter (heute gruen): faengt eine Umsetzung, die schon bei
    60 (">= statt >") oder pauschal auf die Uhrzeit umschaltet (Grenzwert;
    nicht in der Mutationsliste der Spec, per Gegenprobe rot)."""
    for minuten, uhrzeit in ((40, "12:00"), (60, "12:20")):
        e = _event(onset_minutes=minuten, onset_time=uhrzeit)
        for wo, text in _koepfe(e).items():
            if wo.startswith("E-Mail"):
                # Die E-Mail-Detailzeile nennt den ZEITPUNKT ("ab 12:00") --
                # das ist nicht der Kopf. Geprueft wird hier nur die H1.
                assert f"Regen in {minuten} Min" in text, (
                    f"AC-9: {wo}: bei Onset {minuten} (<= 60) muss der Kopf "
                    f"'Regen in {minuten} Min' bleiben.\n{text}"
                )
                continue
            assert f"Regen in {minuten} Min" in text, (
                f"AC-9: {wo}: bei Onset {minuten} (<= 60) muss der Kopf "
                f"'Regen in {minuten} Min' bleiben.\n{text}"
            )
            assert f"ab {uhrzeit}" not in text, (
                f"AC-9: {wo}: bei Onset {minuten} (<= 60) darf der Kopf keine "
                f"Uhrzeit tragen.\n{text}"
            )


def test_kopf_uhrzeit_mit_tagesbezug_ueber_mitternacht():
    """AC-9: Given ein Onset 170, der ueber Mitternacht rutscht
    (Beginn 00:23 am Folgetag, Mittwoch)
    When die Koepfe gerendert werden
    Then traegt der Kopf den Tagesbezug in der Form des SMS-Bausteins:
    "ab Mi0:23" (Wochentagskuerzel vorangestellt, Stunde ohne fuehrende
    Null) -- nie die nackte, mehrdeutige "00:23"/"0:23" ohne Kuerzel.

    Gegenprobe im selben Test: derselbe Onset am gleichen Tag (offset 0)
    traegt KEIN Kuerzel.

    RED heute: Kopf sagt "in 170 Min"."""
    e = _event(
        onset_minutes=170, onset_time="00:23", onset_day_offset=1,
        onset_weekday="Mi",
    )
    for wo, text in _koepfe(e).items():
        assert "Regen ab Mi0:23" in text, (
            f"AC-9: {wo}: der Kopf muss den Tagesbezug wie die SMS tragen "
            f"('Regen ab Mi0:23'). Fehlender Schritt: _onset_wann_kopf nutzt "
            f"_sms_onset_time (inkl. onset_weekday) nicht.\n{text}"
        )
        assert "in 170 Min" not in text, (
            f"AC-9: {wo} nennt noch 'in 170 Min'.\n{text}"
        )

    gleicher_tag = _event(
        onset_minutes=170, onset_time="14:10", onset_day_offset=0,
        onset_weekday="Mi",
    )
    for wo, text in _koepfe(gleicher_tag).items():
        assert "Regen ab 14:10" in text and "Mi14:10" not in text, (
            f"AC-9 Gegenprobe: {wo}: ohne Tageswechsel kein Kuerzel im Kopf.\n{text}"
        )


def test_laeuft_bereits_unveraendert():
    """AC-9: Given ein bereits laufendes Ereignis
    When die Koepfe gerendert werden
    Then bleibt "laeuft bereits" -- keine Uhrzeit, keine Restminuten.

    Regressionswaechter (heute gruen): faengt eine Umsetzung, die den neuen
    Uhrzeit-Zweig VOR die Laufend-Weiche setzt (Weichen-Reihenfolge; nicht
    in der Mutationsliste der Spec, per Gegenprobe rot)."""
    e = _event(onset_minutes=0, onset_time="11:20", already_running=True)
    for wo, text in _koepfe(e).items():
        assert "Regen läuft bereits" in text, (
            f"AC-9: {wo}: laufender Regen muss 'Regen läuft bereits' bleiben.\n{text}"
        )
        if wo in ("Betreff", "Telegram-Kopf"):
            assert "Min" not in text and "ab 11:20" not in text, (
                f"AC-9: {wo}: laufender Regen darf weder Restminuten noch "
                f"Uhrzeit im Kopf tragen.\n{text}"
            )
