"""TDD RED — Issue #2051 Scheibe S2b: die raeumliche Ausdehnung erreicht die
uebrigen LANGFORM-Stellen (Betreff, Telegram rich) und bleibt im
Mehr-Orte-Zweig ein dokumentierter No-op.

SPEC: docs/specs/modules/feat_2051_s2b_ausdehnung_kanaele.md — AC-1, AC-2,
AC-3, AC-14.

RED-Ursache: `_onset_extent_suffix()` (S2a, `render.py:614`) haengt heute an
GENAU EINER Aufrufstelle (E-Mail-Trip-Langform, `render.py:742`). Betreff
(`render.py:486`) und Telegram rich (`render.py:813`) verketten den Baustein
nicht — die Ausdehnungsangabe fehlt dort vollstaendig.

Mock-frei: echte `OnsetEvent`/`RainZone`/`AlertMessage`-Objekte durch die
echten Renderer (Muster `test_regen_ausdehnung_textstellen.py` aus S2a),
feste Zeitangaben, keine Wanduhr.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)
from services.rain_extent import RainZone

_MINIMAL_FIELDS = dict(
    onset_minutes=25, onset_time="15:00", km_from=0.0, km_to=6.0,
    is_convective=False, intensity_label="Mäßiger Regen",
    source_label="Radar (DWD)", event_end_time="16:30",
)


def _onset_event(**overrides) -> OnsetEvent:
    fields = dict(_MINIMAL_FIELDS)
    fields.update(overrides)
    return OnsetEvent(**fields)


def _onset_msg(*events: OnsetEvent) -> AlertMessage:
    return AlertMessage(
        trip_short="KHW 403", stand_at="14:35", events=tuple(events),
        source="Radar (DWD)",
    )


def _langform_soll(*zonen: RainZone) -> str:
    """Der Sollstring der LANGFORM, ABGELEITET aus den Zonenwerten der
    Fixture (`Nass km 8-12`) — nie als Literal getippt.

    Ein im Produktivcode hart verdrahtetes Ergebnis faellt dadurch auf: die
    beiden Faelle unten unterscheiden sich ausschliesslich in ihren
    Zonenwerten, und genau die muessen im Text ankommen."""
    spannen = ", ".join(
        f"km {int(round(z.km_from))}-{int(round(z.km_to))}" for z in zonen
    )
    return f"Nass {spannen}"


_ZONE_A = RainZone(km_from=8.0, km_to=12.0, onset_minutes=20, event_end_minutes=40)
_ZONE_B = RainZone(km_from=3.0, km_to=5.0, onset_minutes=20, event_end_minutes=40)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der geprueften Renderer wird RELATIV ZU DIESER
    Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die Datei des
    Hauptrepos und lieferte falsches Gruen."""
    from output.renderers.alert import render as render_module

    modul_pfad = Path(inspect.getfile(render_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# --------------------------------------------------------------------------
# AC-1 — der E-Mail-Betreff traegt die Ausdehnung aus den Zonendaten DES
#        JEWEILIGEN Events, nicht einen konstanten Text.
# --------------------------------------------------------------------------

def test_ac1_betreff_traegt_die_zone_des_jeweiligen_events():
    """AC-1 GIVEN zwei `OnsetEvent` mit `km_measured=True`, die sich
    AUSSCHLIESSLICH in ihrer Zone unterscheiden (Fall A: km 8-12, Fall B:
    km 3-5)
    WHEN `render_subject` beide rendert
    THEN traegt Fall A `Nass km 8-12` und NICHT `Nass km 3-5`, Fall B
    umgekehrt.

    Die Sollstrings werden aus den Zonenwerten der Fixture ABGELEITET
    (`_langform_soll`) — ein hart verdrahtetes Ergebnis im Produktivcode
    faellt dadurch auf. Die Kreuz-Negativpruefung schliesst aus, dass der
    Betreff einen konstanten Text traegt, der zufaellig zu einem der beiden
    Faelle passt.

    RED heute: der Betreff (`render.py:486`) verkettet
    `_onset_extent_suffix` nicht."""
    soll_a = _langform_soll(_ZONE_A)
    soll_b = _langform_soll(_ZONE_B)
    assert soll_a != soll_b, (
        f"Testvoraussetzung: die beiden Sollstrings muessen sich "
        f"unterscheiden, waren beide {soll_a!r}"
    )

    betreff_a = render_subject(
        _onset_msg(_onset_event(km_measured=True, rain_zones=(_ZONE_A,)))
    )
    betreff_b = render_subject(
        _onset_msg(_onset_event(km_measured=True, rain_zones=(_ZONE_B,)))
    )

    assert soll_a in betreff_a, (
        f"AC-1: Fall A muss {soll_a!r} tragen:\n{betreff_a}"
    )
    assert soll_b not in betreff_a, (
        f"AC-1: Fall A darf {soll_b!r} (Zone des anderen Falls) NICHT "
        f"tragen:\n{betreff_a}"
    )
    assert soll_b in betreff_b, (
        f"AC-1: Fall B muss {soll_b!r} tragen:\n{betreff_b}"
    )
    assert soll_a not in betreff_b, (
        f"AC-1: Fall B darf {soll_a!r} (Zone des anderen Falls) NICHT "
        f"tragen:\n{betreff_b}"
    )


# --------------------------------------------------------------------------
# AC-2 — Telegram rich: dieselbe Zusicherung in der ZWEITEN Zeile.
# --------------------------------------------------------------------------

def test_ac2_telegram_rich_zweite_zeile_traegt_die_zone_des_events():
    """AC-2 GIVEN denselben Zwei-Faelle-Aufbau wie AC-1
    WHEN `render_telegram` beide rendert
    THEN traegt die ZWEITE Zeile in Fall A `Nass km 8-12` und nicht
    `Nass km 3-5`, in Fall B umgekehrt.

    Sollstrings wie in AC-1 aus den Zonenwerten abgeleitet. Geprueft wird
    ausdruecklich die zweite Zeile (die Detailzeile mit Zeit, Intensitaet und
    Quelle) — die Kopfzeile traegt keine Suffixe.

    RED heute: `_render_telegram_onset` (`render.py:810-814`) verkettet
    `_onset_extent_suffix` nicht."""
    soll_a = _langform_soll(_ZONE_A)
    soll_b = _langform_soll(_ZONE_B)

    text_a = render_telegram(
        _onset_msg(_onset_event(km_measured=True, rain_zones=(_ZONE_A,)))
    )
    text_b = render_telegram(
        _onset_msg(_onset_event(km_measured=True, rain_zones=(_ZONE_B,)))
    )
    zeilen_a = text_a.split("\n")
    zeilen_b = text_b.split("\n")

    assert len(zeilen_a) >= 2 and len(zeilen_b) >= 2, (
        f"Testvoraussetzung: Telegram rich hat mindestens zwei Zeilen — "
        f"A={zeilen_a!r}, B={zeilen_b!r}"
    )

    assert soll_a in zeilen_a[1], (
        f"AC-2: Fall A muss {soll_a!r} in der zweiten Zeile tragen:\n{zeilen_a[1]}"
    )
    assert soll_b not in zeilen_a[1], (
        f"AC-2: Fall A darf {soll_b!r} NICHT tragen:\n{zeilen_a[1]}"
    )
    assert soll_b in zeilen_b[1], (
        f"AC-2: Fall B muss {soll_b!r} in der zweiten Zeile tragen:\n{zeilen_b[1]}"
    )
    assert soll_a not in zeilen_b[1], (
        f"AC-2: Fall B darf {soll_a!r} NICHT tragen:\n{zeilen_b[1]}"
    )


# --------------------------------------------------------------------------
# AC-3 — Mehr-Orte-Zweig: die zusaetzliche Anhaengung ist ein dokumentierter
#        No-op. Der Ortsvergleich-Buendelpfad setzt `rain_zones` nie
#        (S2a AC-15), also bleibt der Text byte-identisch.
# --------------------------------------------------------------------------

def _buendel_msg(**overrides) -> AlertMessage:
    """Zwei Events aus dem Ortsvergleich-Muster (`_render_email_onset_multi`).

    `rain_zones` bleibt per Default LEER — die einzige Konstellation, die
    dieser Pfad in Produktion je erhaelt (S2a AC-15)."""
    gemeinsam = dict(
        km_from=0.0, km_to=6.0, source_label="Radar (DWD)",
    )
    gemeinsam.update(overrides)
    erster = OnsetEvent(
        onset_minutes=25, onset_time="18:00", is_convective=False,
        intensity_label="Mäßiger Regen", location_label="Sillian",
        event_end_time="19:30", **gemeinsam,
    )
    zweiter_felder = dict(gemeinsam)
    zweiter_felder["source_label"] = "AROME-FR"
    zweiter = OnsetEvent(
        onset_minutes=40, onset_time="18:15", is_convective=True,
        intensity_label="Starker Regen", location_label="Zermatt",
        **zweiter_felder,
    )
    return AlertMessage(
        trip_short="KHW 403", stand_at="17:30", events=(erster, zweiter),
        source="Radar (DWD)",
    )


# Aufgenommener Ist-Text des Mehr-Orte-Zweigs VOR dieser Spec (Stand
# `c8334159`, aufgenommen 2026-08-23 durch Rendern derselben Fixture).
# Wanduhrfrei: `stand_at` und alle Zeiten stammen aus der Fixture.
_AC3_GOLD_PLAIN = (
    "Regen-Alarm: 2 Orte\n"
    "\n"
    "Radar-Nowcast\n"
    "\n"
    "Sillian · Regen in 25 Min: ab 18:00 · letzter Regen gegen 19:30 · "
    "Mäßiger Regen\n"
    "Zermatt · Gewitter/Hagel in 40 Min: ab 18:15 · Starker Regen\n"
    "\n"
    "Stand: heute 17:30 · Quelle: Radar (DWD), AROME-FR\n"
    "\n"
    "Regen-/Gewitter-Alarm · Radar (DWD)"
)


def test_ac3_mehr_orte_zweig_bleibt_byte_identisch():
    """AC-3 GIVEN ein Buendel-`AlertMessage` mit zwei Events aus dem
    Ortsvergleich-Pfad (`rain_zones` jeweils leer — die einzige
    Konstellation, die dieser Pfad in Produktion je erhaelt)
    WHEN der Mehr-Orte-Zweig gerendert wird
    THEN bleibt der Text byte-identisch zum Stand VOR dieser Spec, obwohl
    `_onset_extent_suffix` dort kuenftig ebenfalls aufgerufen wird.

    Regressionstest: laeuft heute (RED-Zustand) GRUEN und muss nach der
    Implementierung gruen BLEIBEN — die Anhaengung ist ein dokumentierter
    No-op, kein neues Verhalten fuer den Ortsvergleich.

    Positivkontrolle in `test_ac3_positivkontrolle_...` unten: derselbe Zweig
    zeigt die Angabe sehr wohl, sobald Zonen gesetzt sind. Ohne sie waere
    diese Byte-Gleichheit trivial erfuellbar (ein Baustein, der nirgends
    wirkt, ist immer identisch)."""
    _html, plain = render_email(_buendel_msg())

    assert plain == _AC3_GOLD_PLAIN, (
        "AC-3: der Mehr-Orte-Zweig hat sich gegenueber dem Stand vor dieser "
        f"Spec veraendert.\nErhalten:\n{plain!r}\nErwartet:\n{_AC3_GOLD_PLAIN!r}"
    )
    assert "Nass km" not in plain, (
        f"AC-3: ohne Zonen darf keine Ausdehnungs-Angabe erscheinen:\n{plain}"
    )


def test_ac3_positivkontrolle_mehr_orte_zweig_zeigt_gesetzte_zonen():
    """AC-3 (Positivkontrolle) GIVEN denselben Buendel-Aufbau, aber MIT
    gesetzten Zonen und `km_measured=True` an beiden Events
    WHEN derselbe Mehr-Orte-Zweig rendert
    THEN traegt der Text die Ausdehnungsangabe.

    Zweck: nachweisen, dass die Byte-Gleichheit oben aus den LEEREN Zonen
    folgt und nicht daraus, dass der Baustein an dieser Stelle ueberhaupt
    nicht verkettet ist. Genau dieser Unterschied macht AC-3 zu einer
    Zusicherung statt zu einer Selbstverstaendlichkeit.

    RED heute: `_render_email_onset_multi` (`render.py:658-660`) verkettet
    `_onset_extent_suffix` nicht."""
    soll = _langform_soll(_ZONE_A)
    msg = _buendel_msg(km_measured=True, rain_zones=(_ZONE_A,))

    _html, plain = render_email(msg)

    assert soll in plain, (
        f"AC-3 (Positivkontrolle): mit gesetzten Zonen muss {soll!r} im "
        f"Mehr-Orte-Zweig erscheinen — sonst prueft die Byte-Gleichheit "
        f"oben nichts:\n{plain}"
    )


# --------------------------------------------------------------------------
# AC-14 — keine Handlungsempfehlung, keine Ankunftszeit-Rechnung in den vier
#         neu betroffenen Texten.
# --------------------------------------------------------------------------

# Identische Musterliste wie S2a-AC-16
# (`test_regen_ausdehnung_textstellen.py:294-308`).
_VERBOTENE_MUSTER = [
    "verlass dich nicht",
    "solltest du",
    "bis dahin solltest",
    "rechne damit, dass du",
    "sei vorsichtig",
    "achte darauf, dass du",
    "plane damit",
    "du erreichst",
    "wirst du dort",
    "wirst du diese zone",
    "bist du dort",
    "kommst du dort an",
    "wenn du ankommst",
]


def _pruefe(kandidaten: dict[str, str]) -> dict[str, list[str]]:
    gefunden: dict[str, list[str]] = {}
    for name, text in kandidaten.items():
        text_klein = text.lower()
        treffer = [m for m in _VERBOTENE_MUSTER if m in text_klein]
        if treffer:
            gefunden[name] = treffer
    return gefunden


def test_ac14_keine_bevormundung_in_den_vier_neu_betroffenen_texten():
    """AC-14 GIVEN die vier neu betroffenen Texte (Betreff, Telegram rich,
    Mehr-Orte-Zweig, Kurzform) MIT gesetzter Ausdehnungsangabe
    WHEN sie auf Handlungsempfehlungen und Ankunftszeit-Rechnungen ueber den
    Nutzer geprueft werden
    THEN enthaelt KEINER eine solche Formulierung — ausschliesslich
    km-Spannen und Zeiten.

    Zwei Kontrollen, ohne die die Negativpruefung trivial waere:
      * DETEKTOR-Positivkontrolle (Lehre aus #2054): ein synthetischer,
        absichtlich verbotener Satz muss von derselben Pruefschleife
        gefunden werden;
      * INHALTS-Vorbedingung: in jedem der vier Texte muss die
        Ausdehnungsangabe ueberhaupt stehen — sonst prueft der Test einen
        Text ohne den Gegenstand des ACs.

    RED heute: die Vorbedingung faellt fuer Betreff, Telegram rich,
    Mehr-Orte-Zweig und Kurzform aus (die Angabe fehlt dort)."""
    langform_soll = _langform_soll(_ZONE_A)
    kurzform_soll = f"km{int(round(_ZONE_A.km_from))}-{int(round(_ZONE_A.km_to))}"

    einzel = _onset_msg(_onset_event(km_measured=True, rain_zones=(_ZONE_A,)))
    buendel = _buendel_msg(km_measured=True, rain_zones=(_ZONE_A,))
    _html, multi_plain = render_email(buendel)

    texte = {
        "betreff": render_subject(einzel),
        "telegram_rich": render_telegram(einzel),
        "mehr_orte": multi_plain,
        "kurzform": render_sms(einzel),
    }

    synthetisch = _pruefe({
        "synthetisch": f"{langform_soll}. Du erreichst diese Zone in 45 Minuten.",
    })
    assert synthetisch, (
        "Vorbedingung: der Detektor muss einen ABSICHTLICH eingebauten "
        "Verstoss erkennen — sonst waere die Negativpruefung unten trivial "
        "wahr."
    )

    for name, text in texte.items():
        erwartet = kurzform_soll if name == "kurzform" else langform_soll
        assert erwartet in text, (
            f"Vorbedingung ({name}): die Ausdehnungsangabe {erwartet!r} muss "
            f"ueberhaupt im Text stehen, sonst prueft AC-14 hier nichts:\n{text}"
        )

    treffer = _pruefe(texte)
    assert not treffer, (
        f"AC-14: verbotene Formulierung gefunden: {treffer}\nTexte: {texte}"
    )
