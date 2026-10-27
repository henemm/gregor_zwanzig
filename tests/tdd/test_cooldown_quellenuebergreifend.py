"""TDD RED — Issue #2018 Teil C: Der Cooldown-Satz sagt, dass er NUR
quelleneigen gilt.

Der gemeldete Fehler: Nutzer lesen "Du erhältst diese Warnung höchstens
einmal in 2 Stunden" als Zusicherung über ALLE Quellen. Tatsächlich hält der
Cooldown nur die jeweils EIGENE Quelle zurück — eine amtliche Warnung und ein
Radar-Nowcast desselben Ereignisses laufen durch getrennte Sperrzeiten. Der
Satz wird deshalb additiv präzisiert; der bestehende Wortlaut bleibt
unangetastet, damit die vier bestehenden Substring-Wächter grün bleiben.

SPEC: docs/specs/modules/alert_nachtragsmeldung.md — Teil C, AC-C1.

RED-Grund (heute): `render.py` rendert in beiden Zweigen
(`_render_email_onset` Einzel, `_render_email_onset_multi` Bündel) nur den
Satz ohne den Quellen-Zusatz.

Keine Mocks (CLAUDE.md): geprüft wird der ECHTE gerenderte E-Mail-Plain-Text
aus `render_email()` über echte `AlertMessage`/`OnsetEvent`-Fixtures, nicht
ein Aufruf-Nachweis.
"""
from __future__ import annotations

# Der bestehende, bewusst unangetastete Kern des Satzes — vier
# Bestandswächter prüfen genau diesen Substring.
BESTEHENDER_SUBSTRING = "höchstens einmal in"

# Die fachlich bindende Präzisierung (Wortlaut laut Spec Teil C).
QUELLEN_ZUSATZ = (
    "Bei Meldungen aus anderen Quellen (amtliche Warnung/Radar) greift "
    "dieser Cooldown nicht."
)


def _onset_event(location_label=None, onset_minutes: int = 12, onset_time: str = "14:35"):
    from output.renderers.alert.model import OnsetEvent

    return OnsetEvent(
        onset_minutes=onset_minutes, onset_time=onset_time, km_from=5.0, km_to=18.0,
        is_convective=False, intensity_label="leichter Regen",
        source_label="Radar (DWD)", location_label=location_label,
    )


def _message(events, cooldown_display="2 Stunden"):
    from output.renderers.alert.model import AlertMessage

    return AlertMessage(
        trip_short="GR20-Test", stand_at="14:23", events=tuple(events),
        source="Radar (DWD)", cooldown_display=cooldown_display,
    )


def _plain(msg) -> str:
    from output.renderers.alert.render import render_email

    _html, plain = render_email(msg)
    return plain


def test_einzel_onset_mail_sagt_dass_der_cooldown_nicht_quellenuebergreifend_gilt():
    """
    GIVEN: Eine Onset-Meldung für EINEN Ort mit gesetztem `cooldown_display`
    WHEN:  `render_email()` den Einzel-Zweig (`_render_email_onset`) rendert
    THEN:  Der Plain-Text enthält den bestehenden Cooldown-Satz UND den
           Zusatz, dass Meldungen aus anderen Quellen davon nicht erfasst sind

    AC-C1 (Issue #2018). RED heute: der Zusatz fehlt.
    """
    plain = _plain(_message([_onset_event()]))

    assert BESTEHENDER_SUBSTRING in plain, (
        f"Der bestehende Cooldown-Wortlaut darf nicht verschwinden: {plain!r}"
    )
    assert QUELLEN_ZUSATZ in plain, (
        f"Der Cooldown-Satz muss klarstellen, dass er NICHT quellenübergreifend "
        f"gilt — Zusatz fehlt im Einzel-Zweig: {plain!r}"
    )


def test_buendel_onset_mail_sagt_dass_der_cooldown_nicht_quellenuebergreifend_gilt():
    """
    GIVEN: Eine gebündelte Onset-Meldung über ZWEI Orte mit gesetztem
           `cooldown_display`
    WHEN:  `render_email()` den Bündel-Zweig (`_render_email_onset_multi`)
           rendert
    THEN:  Der Plain-Text enthält denselben präzisierten Cooldown-Satz wie der
           Einzel-Zweig — die Aussage darf nicht an einem der beiden Zweige
           hängenbleiben

    AC-C1 (Issue #2018). RED heute: der Zusatz fehlt.
    """
    plain = _plain(_message([
        _onset_event(location_label="Zermatt", onset_minutes=8, onset_time="14:31"),
        _onset_event(location_label="Chamonix", onset_minutes=15, onset_time="14:38"),
    ]))

    assert BESTEHENDER_SUBSTRING in plain, (
        f"Der bestehende Cooldown-Wortlaut darf nicht verschwinden: {plain!r}"
    )
    assert QUELLEN_ZUSATZ in plain, (
        f"Der Cooldown-Satz muss klarstellen, dass er NICHT quellenübergreifend "
        f"gilt — Zusatz fehlt im Bündel-Zweig: {plain!r}"
    )


def test_ohne_cooldown_bleibt_die_mail_ganz_ohne_cooldown_zeile():
    """
    GIVEN: Eine Onset-Meldung OHNE `cooldown_display`
    WHEN:  `render_email()` sie rendert
    THEN:  Weder der bestehende Satz noch der neue Zusatz erscheinen — die
           Präzisierung darf keine Cooldown-Zeile erzeugen, wo heute keine ist

    AC-C1 (Issue #2018), Bestandsinvariante. Heute grün; fällt, sobald der
    Zusatz bedingungslos angehängt wird.
    """
    plain = _plain(_message([_onset_event()], cooldown_display=None))

    assert BESTEHENDER_SUBSTRING not in plain, (
        f"Ohne Cooldown darf keine Cooldown-Zeile entstehen: {plain!r}"
    )
    assert "Cooldown" not in plain and QUELLEN_ZUSATZ not in plain, (
        f"Ohne Cooldown darf auch der Quellen-Zusatz nicht erscheinen: {plain!r}"
    )
