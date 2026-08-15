"""Ratsche: keine Liste unter ``src/``/``api/`` erfindet ein eigenes Vokabular.

SPEC: docs/specs/modules/fix_1856_e7_metrik_listen_waechter.md — AC-2..AC-6.

Umgekehrt gestellte Frage gegenueber der E3b-Ratsche
(``test_sms_token_symbol_register_ratchet.py``): nicht "kenne ich diese
Liste?", sondern "welche Liste legt etwas je Wettergroesse fest, OHNE
registriert zu sein?".

Der Erkennungs-Kern liegt in ``tests/helpers/metrik_listen_scan.py``
(Testschicht, kein Produktivcode) — nur so ist er gegen ERFUNDENE Eingaben
pruefbar. Genau darauf kommt es an: im heutigen Bestand ist alles
registriert, ein Waechter, der ausschliesslich den Bestand sieht, ist gruen,
ohne je etwas geprueft zu haben (in Etappe E3a sind zwei Waechter genau so
gescheitert).

Vertrag des Kerns (Phase GREEN baut ihn):

  KENNUNGEN                        frozenset der 32 ``_METRICS``-Ids — NICHT
                                   ``get_all_metrics()`` (29, filtert
                                   ``selectable=False`` weg)
  Fundstelle                       datei, zeile, seite ("schluessel"|"wert"|
                                   "element"), kennungen, name, freigestellt
  scanne_register_listen(wurzeln)  alle erkannten Sammlungen; ``wurzeln``
                                   sind Verzeichnisse ODER einzelne Dateien
  unregistrierte_register_listen(wurzeln)
                                   davon die weder registrierten noch per
                                   ``# gz-fremdvokabular: …`` freigestellten
  RegisteredList                   frozen dataclass: ist, ort,
                                   soll_vollstaendig, fehlend_erlaubt,
                                   begruendung
  REGISTERED_LISTS                 dict[str, RegisteredList]
  pruefe_registrierte_liste(schluessel, reg) -> list[str]
                                   Befund-Zeilen (leer = in Ordnung); prueft
                                   Gueltigkeit, Vollstaendigkeit UND die
                                   Begruendung der Ausnahmen (AC-4/AC-5)
  finde_kuerzel_kollisionen(...)   AC-1, geprueft in der E3b-Ratsche

Bauprinzipien, uebernommen aus der E3b-Ratsche: kein Regex ueber Quelltext
(echter AST) · keine handgepflegte Kennungs-Liste (das Soll kommt aus dem
Register) · Nichtstun ist kein Bestehen (Trefferzahl behaupten) · der
Pruefling stammt aus DIESEM Arbeitsbaum (#1409).

Regel-Budget (CLAUDE.md): Pruefdatum 2026-11-15.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import app.metric_catalog as katalog_mod
from app.metric_catalog import _METRICS, get_all_metrics
from output.renderers.channel_layout import METRIC_PRIORITY
from tests.helpers.metrik_listen_scan import (
    KENNUNGEN, REGISTERED_LISTS, RegisteredList, _literal, _registriere,
    pruefe_registrierte_liste, scanne_register_listen,
    unregistrierte_register_listen,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_WURZELN = (REPO_ROOT / "src", REPO_ROOT / "api")

# Falsch-Positiv-Pruefstein: das Vokabular der amtlichen Warnungen sieht
# strukturell aus wie eine Metrik-Liste, hat gegen das Register aber Quote
# 0/10. Ein Waechter, der SIE meldet, wird abgeschaltet.
HAZARD_DATEI = REPO_ROOT / "src" / "output" / "tokens" / "hazard_symbols.py"
# Gegenstueck: hier MUSS der Scan anschlagen, sonst misst die Gegenprobe nichts.
POSITIV_DATEI = REPO_ROOT / "src" / "output" / "renderers" / "channel_layout.py"

MP_SCHLUESSEL = "channel_layout.METRIC_PRIORITY"
HER_SCHLUESSEL = "compare_hourly_metric_ids.HOURLY_EXCLUSION_REASON"
HER_DATEI = REPO_ROOT / "src/output/renderers/compare_hourly_metric_ids.py"
# Die vier Schluessel, die #1728 S1 dort per Schleife nachtraegt statt literal.
HER_NACHGETRAGEN = frozenset({
    "temperature_day_low", "temperature_day_high",
    "wind_chill_day_low", "wind_chill_day_high",
})

# AC-5: Vorzustand zum Stand der Spec (2026-08-15). Die Ausnahmeliste darf nur
# SCHRUMPFEN — waechst sie, muss jemand diese Zeile bewusst aendern.
#
# 2 -> 6 am 2026-08-15, bewusst angehoben: #1728 Scheibe 1 (``c18f8eb7``) hat
# das Register von 28 auf 32 Groessen erweitert; die vier neuen
# Tagesrichtungen (``temperature_day_low/_high``, ``wind_chill_day_low/_high``)
# fehlen in ``METRIC_PRIORITY`` aus DEMSELBEN Grund wie die beiden
# Nachtfenster-Skalare. Die Regel „darf nur schrumpfen" bewacht Nachsicht
# gegenueber BESTEHENDEN Groessen — kommen Groessen hinzu, ist begruendetes
# Wachstum zulaessig.
#
# 🔴 Festgehalten wird die MENGE, nicht nur ihre Groesse. Die Spec beschreibt
# den Groessenvergleich; er allein laesst offen, dass jemand einen Eintrag
# gegen einen anderen TAUSCHT — bei 6 statt 2 Eintraegen ist das kein
# Randfall mehr. Der Groessenvergleich bleibt (AC-5), der Mengenvergleich
# kommt hinzu; beides zusammen ist "darf nur schrumpfen" im Wortsinn.
VORZUSTAND_FEHLEND_ERLAUBT: dict[str, frozenset[str]] = {
    MP_SCHLUESSEL: frozenset({
        "temperature_night", "wind_chill_night",
        "temperature_day_low", "temperature_day_high",
        "wind_chill_day_low", "wind_chill_day_high",
    }),
}

# ---------------------------------------------------------------------------
# Wegwerf-Module: der Waechter wird gegen ERFUNDENE Faelle geprueft, nicht nur
# gegen den (vollstaendig registrierten) Bestand.
# ---------------------------------------------------------------------------
WEGWERF_SCHLUESSELSEITE = '''"""Wegwerf-Modul der Wirksamkeitsprobe."""
WICHTIGKEIT = {
    "temperature": 95,
    "wind": 90,
    "gust": 88,
}
'''

WEGWERF_WERTESEITE = '''"""Wegwerf-Modul der Wirksamkeitsprobe."""
SPALTE_ZU_GROESSE = {
    "tmax": "temperature",
    "vmax": "wind",
}
'''

WEGWERF_TIPPFEHLER = '''"""Wegwerf-Modul der Wirksamkeitsprobe."""
WICHTIGKEIT = {"temperature": 95, "temperatuer": 90, "wind": 88}
'''

WEGWERF_FLUCHTVENTIL = '''"""Wegwerf-Modul der Wirksamkeitsprobe."""
# gz-fremdvokabular: Zufallstreffer, hier stehen Dateinamen, keine Groessen.
FREIGESTELLT = ("temperature", "wind")

NICHT_FREIGESTELLT = ("gust", "thunder")
'''


def _wegwerf_modul(tmp_path: Path, quelltext: str) -> Path:
    pfad = tmp_path / "wegwerf_liste.py"
    pfad.write_text(quelltext, encoding="utf-8")
    return pfad


def _zeile_von(quelltext: str, anfang: str) -> int:
    for nr, zeile in enumerate(quelltext.splitlines(), start=1):
        if zeile.startswith(anfang):
            return nr
    raise AssertionError(f"{anfang!r} steht nicht im Wegwerf-Modul")


# ---------------------------------------------------------------------------
# Selbstpruefung des Waechters (AC-3, Bauprinzipien 3 und 4)
# ---------------------------------------------------------------------------

def test_waechter_liest_das_register_dieses_arbeitsbaums():
    """#1409: laege die Soll-Quelle im Hauptrepo, meldete ein Worktree-Lauf
    falsches Gruen — geprueft wuerde dann eine fremde Kopie."""
    katalog = Path(katalog_mod.__file__).resolve()
    assert str(katalog).startswith(str(REPO_ROOT)), (
        f"Das Register kommt aus {katalog}, erwartet unterhalb {REPO_ROOT}."
    )


def test_scan_hat_pruefmaterial():
    """Nichtstun ist kein Bestehen: beide Seiten behaupten ihre Trefferzahl."""
    gefunden = scanne_register_listen(SCAN_WURZELN)

    assert len(gefunden) > 0, (
        "Der AST-Scan findet unter src/ + api/ keine einzige Register-Liste — "
        "er prueft praktisch nichts. Eigene Messung zum Stand dieser Etappe "
        "(2026-08-15 nach #1728 S3, dict/set/list/tuple, Mindestgroesse 2): "
        "46 Fundstellen in 12 Dateien unter src/ + api/ (vor S3: 42 — die vier "
        "Tagesrichtungs-Regelzeilen wurden erst sichtbar, als das "
        "Auswertungswort aus ``_DERIVED_METRIC_RULES`` fiel). Der strukturelle "
        "``in``-Ausschluss haelt weitere Fundstellen zurueck (s. "
        "Modul-Docstring des Scan-Kerns, Grenzen)."
    )
    assert len(REGISTERED_LISTS) > 0, (
        "REGISTERED_LISTS ist leer — dann ist jede Gueltigkeitspruefung aus "
        "AC-4/AC-6 leer und der Waechter gruen, ohne etwas zu bewachen."
    )
    assert any(reg.soll_vollstaendig for reg in REGISTERED_LISTS.values()), (
        "Keine einzige Registrierung prueft Vollstaendigkeit — die "
        "Rueckrichtung aus AC-4 (fehlende Groesse in einer Liste, die alle "
        "waehlbaren fuehren muss) ist dann unbewacht."
    )
    # Befund 5 der Analyse: `get_all_metrics()` filtert `selectable=False` weg.
    # Wer dagegen prueft, meldet drei GUELTIGE Kennungen als unbekannt.
    assert KENNUNGEN == {m.id for m in _METRICS}, (
        f"Soll-Menge weicht von _METRICS ab: "
        f"{sorted({m.id for m in _METRICS} ^ set(KENNUNGEN))!r}"
    )
    assert {"cape", "confidence", "temperature_cold"} <= KENNUNGEN, (
        "Gegen get_all_metrics() geprueft statt gegen _METRICS."
    )


# ---------------------------------------------------------------------------
# AC-2: die umgekehrt gestellte Frage
# ---------------------------------------------------------------------------

def test_keine_unregistrierte_register_liste_unter_src_und_api():
    """Die Ratsche selbst: jede Liste, die etwas je Wettergroesse festlegt,
    ist registriert (Stufe 2) oder ausdruecklich freigestellt."""
    offen = unregistrierte_register_listen(SCAN_WURZELN)

    assert not offen, (
        "Diese Sammlungen schluesseln nach Wettergroesse, sind aber weder in "
        "REGISTERED_LISTS eingetragen noch mit '# gz-fremdvokabular: …' "
        "freigestellt:\n"
        + "\n".join(f"  - {f}  {sorted(f.kennungen)!r}" for f in offen)
    )


@pytest.mark.parametrize(
    "quelltext, anfang, seite, erwartete_kennungen",
    [
        (WEGWERF_SCHLUESSELSEITE, "WICHTIGKEIT", "schluessel",
         {"temperature", "wind", "gust"}),
        (WEGWERF_WERTESEITE, "SPALTE_ZU_GROESSE", "wert",
         {"temperature", "wind"}),
    ],
    ids=["schluesselseite", "werteseite"],
)
def test_scan_meldet_eine_erfundene_unregistrierte_liste(
    tmp_path, quelltext, anfang, seite, erwartete_kennungen,
):
    """Der eigentliche Wirksamkeitsnachweis fuer AC-2. Im Bestand ist alles
    registriert — ohne diesen Fall belegt die gruene Ratsche oben nichts.

    Die Werteseite ist kein Nebenfall: eine Uebersetzungstabelle INS Register
    (fremder Schluessel, Kennung als Wert) muss genauso gefunden werden,
    sonst entkommt jede neue Tabelle durch blosses Umdrehen.
    """
    pfad = _wegwerf_modul(tmp_path, quelltext)

    gefunden = scanne_register_listen([pfad])
    assert len(gefunden) == 1, (
        f"Erwartet genau eine Fundstelle, bekommen: {gefunden!r}"
    )
    fund = gefunden[0]
    assert fund.seite == seite
    assert set(fund.kennungen) == erwartete_kennungen
    assert fund.zeile == _zeile_von(quelltext, anfang)
    assert fund.name == anfang

    offen = unregistrierte_register_listen([pfad])
    assert len(offen) == 1, (
        "Eine erfundene, nirgends registrierte Liste bleibt unbeanstandet — "
        f"der Waechter kann AC-2 nicht erfuellen. Gemeldet: {offen!r}"
    )
    meldung = str(offen[0])
    assert "wegwerf_liste.py" in meldung and str(fund.zeile) in meldung, (
        f"Die Meldung nennt nicht Datei:Zeile: {meldung!r}"
    )
    assert anfang in meldung, f"Die Meldung nennt den Namen nicht: {meldung!r}"


def test_fluchtventil_stellt_nur_die_kommentierte_fundstelle_frei(tmp_path):
    """``# gz-fremdvokabular:`` verhindert nichts — es macht die Entscheidung
    zitierbar. Zwei Sammlungen, eine kommentiert: gemeldet wird genau die
    andere (sonst waere der Test durch Nichtstun gruen).

    🔴 Der Kommentar gehoert an DIE Fundstelle, die er freistellt — an die
    Zeile bzw. unmittelbar darueber. Die Spec sagt "in den ersten 20 Zeilen um
    die Fundstelle"; als Fenster von +/-20 Zeilen gelesen, stellte EIN
    Kommentar alles frei, was zufaellig in der Naehe steht (in
    ``metric_catalog.py`` liegen sieben Register-Listen dicht beieinander).
    Diese Testfassung schliesst diese Lesart aus.
    """
    pfad = _wegwerf_modul(tmp_path, WEGWERF_FLUCHTVENTIL)

    gefunden = scanne_register_listen([pfad])
    assert len(gefunden) == 2, (
        f"Beide Sammlungen muessen gefunden werden: {gefunden!r}"
    )
    freigestellt = [f for f in gefunden if f.freigestellt]
    assert [f.name for f in freigestellt] == ["FREIGESTELLT"], (
        f"Falsche Fundstelle freigestellt: {gefunden!r}"
    )
    assert len(freigestellt[0].freigestellt.strip()) >= 15, (
        "Eine Freistellung ohne lesbare Begruendung ist keine Freistellung."
    )

    offen = unregistrierte_register_listen([pfad])
    assert [f.name for f in offen] == ["NICHT_FREIGESTELLT"], (
        f"Gemeldet werden muss genau die unkommentierte Sammlung: {offen!r}"
    )


def test_gleicher_modulname_erbt_keine_registrierung(tmp_path, monkeypatch):
    """Der Registrierungs-Schluessel ist ``modulname.sammlung`` — im Repo gibt
    es ``models.py`` zweimal unter ``src/`` (``app/``, registriert;
    ``services/official_alerts/``, nicht). Ohne den Ortsabgleich in
    ``_ort_passt`` erbte die zweite Datei die Registrierung der ersten, und
    eine neue Liste dort bliebe stumm."""
    for ordner in ("app", "fremd"):
        (tmp_path / ordner).mkdir()
        (tmp_path / ordner / "models.py").write_text(
            WEGWERF_SCHLUESSELSEITE, encoding="utf-8")
    monkeypatch.setitem(
        REGISTERED_LISTS, "models.WICHTIGKEIT",
        RegisteredList(ist=lambda: {"temperature"}, ort="app/models.py:2"))

    offen = unregistrierte_register_listen([tmp_path])

    assert [f.datei.parent.name for f in offen] == ["fremd"], (
        "Gemeldet werden muss genau die gleichnamige Sammlung im NICHT "
        f"registrierten Verzeichnis: {offen!r}")


def test_hazard_symbols_bleiben_unauffaellig():
    """Falsch-Positive sind schlimmer als eine Restluecke: ``HAZARD_SMS_SYMBOLS``
    (Quote 0/10) darf nicht anschlagen. Die Gegenprobe an ``channel_layout.py``
    zeigt im selben Test, dass der Scan ueberhaupt etwas sieht — sonst waere
    'findet nichts' der Beweis fuer 'es gibt nichts'."""
    assert HAZARD_DATEI.exists() and POSITIV_DATEI.exists()

    harmlos = scanne_register_listen([HAZARD_DATEI])
    assert harmlos == [], (
        "Das Vokabular der amtlichen Warnungen wurde als Register-Liste "
        f"gemeldet: {harmlos!r}"
    )

    positiv = scanne_register_listen([POSITIV_DATEI])
    assert positiv, (
        "Der Scan findet nicht einmal METRIC_PRIORITY (25 Kennungen) — die "
        "Gegenprobe oben ist damit wertlos."
    )


# ---------------------------------------------------------------------------
# AC-4/AC-5/AC-6: Gueltigkeit, Vollstaendigkeit, Ausnahmen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schluessel", sorted(REGISTERED_LISTS))
def test_registrierte_liste_ist_in_ordnung(schluessel):
    """AC-4: jede Kennung existiert im Register; traegt die Registrierung
    ``soll_vollstaendig``, fehlt auch keine waehlbare Groesse. AC-5: eine
    ``fehlend_erlaubt``-Ausnahme ohne Begruendungssatz mit Ticket-Bezug ist
    keine Ausnahme (Wirksamkeit s. ``test_ausnahme_ohne_begruendung...``)."""
    befunde = pruefe_registrierte_liste(schluessel, REGISTERED_LISTS[schluessel])
    assert befunde == [], "\n".join(befunde)


def test_verfaelschte_kennung_wird_namentlich_gemeldet():
    """AC-6, Existenzrichtung. Ohne diesen Fall belegt der gruene Lauf oben
    nicht, dass die Pruefung ueberhaupt zubeisst."""
    echt = set(METRIC_PRIORITY)
    verfaelscht = (echt - {"temperature"}) | {"temperatuer"}
    reg = RegisteredList(
        ist=lambda: verfaelscht, ort="src/output/renderers/channel_layout.py:60",
    )

    befunde = pruefe_registrierte_liste(MP_SCHLUESSEL, reg)

    assert befunde, (
        "Eine Kennung, die das Register nicht kennt, blieb unbeanstandet."
    )
    text = "\n".join(befunde)
    assert "temperatuer" in text, (
        f"Die Meldung nennt die falsche Kennung nicht: {text!r}"
    )
    assert "channel_layout.py:60" in text, (
        f"Die Meldung nennt die Fundstelle nicht: {text!r}"
    )


def test_tippfehler_in_einer_ast_gelesenen_liste_wird_gemeldet(tmp_path):
    """AC-4, Existenzrichtung fuer die 40 ueber ``_literal`` AST-gelesenen
    Registrierungen: der Test darueber baut eine ``RegisteredList`` von Hand
    und trifft mit ``METRIC_PRIORITY`` eine der beiden, die ``_literal`` NICHT
    durchlaufen. 🔴 Zugleich Nachweis der Stufen-Trennung — Quote 2/3,
    Stufe 1 findet die Liste deshalb nicht (erste Zusicherung). Filtert
    ``_literal`` seine Ausgabe auf ``KENNUNGEN`` (die von der Spec verworfene
    Kopplung an Stufe 1), faellt der Tippfehler weg und dieser Test wird rot.
    """
    pfad = _wegwerf_modul(tmp_path, WEGWERF_TIPPFEHLER)
    assert scanne_register_listen([pfad]) == [], (
        "Stufe 1 darf diese Liste (Quote 2/3) gerade NICHT finden — sonst "
        "misst der Test die Unabhaengigkeit der beiden Stufen nicht.")
    reg = _registriere(str(pfad), "WICHTIGKEIT", "schluessel")
    text = "\n".join(pruefe_registrierte_liste("wegwerf.WICHTIGKEIT", reg))

    assert "temperatuer" in text, (
        "Der Tippfehler in einer AST-gelesenen Registrierung blieb "
        f"unbeanstandet — Stufe 2 haengt an der Quote aus Stufe 1: {text!r}")
    assert "wegwerf_liste.py" in text, f"Ohne Fundstelle unbrauchbar: {text!r}"


def test_per_schleife_nachgetragene_schluessel_werden_mitgeprueft():
    """Gegenstueck zum Test darueber: ``HOURLY_EXCLUSION_REASON`` fuehrt drei
    Schluessel literal, die vier restlichen traegt #1728 S1 per Schleife nach
    (``compare_hourly_metric_ids.py:84-96``). Wer hier ``_literal`` liest,
    prueft 3 von 7 und schweigt ausgerechnet ueber die NEUEN Kennungen —
    Stufe 1 sieht die Schleife ohnehin nicht, ein Tippfehler dort entkaeme
    also beiden Stufen. Diese eine Registrierung liest deshalb das echte
    Objekt; faellt sie je auf ``_registriere`` zurueck, wird dieser Test rot.
    """
    literal = set(_literal(HER_DATEI, "HOURLY_EXCLUSION_REASON", "schluessel")[0])
    ist = set(REGISTERED_LISTS[HER_SCHLUESSEL].ist())

    assert literal < ist, (
        f"Die Registrierung sieht nur {sorted(ist)!r} — nicht mehr als das "
        f"Literal {sorted(literal)!r}. Dann liest sie wieder den Quelltext."
    )
    assert ist - literal == set(HER_NACHGETRAGEN), (
        f"Zur Laufzeit kommen {sorted(ist - literal)!r} hinzu, erwartet waren "
        f"{sorted(HER_NACHGETRAGEN)!r}. Aendert sich der Schleifen-Nachtrag, "
        "gehoert diese Zeile bewusst nachgezogen."
    )


def test_entfernte_ausnahme_macht_die_luecke_in_metric_priority_sichtbar():
    """AC-6, Vollstaendigkeitsrichtung — zugleich der Fang-Beleg dieser Etappe
    (Regel-Budget): ``METRIC_PRIORITY`` fehlen sechs waehlbare Groessen — die
    beiden Nachtfenster-Skalare (seit #1484/#1660 A) und die vier
    Tagesrichtungen (seit #1728 Scheibe 1). Die Datei importiert nichts aus
    ``metric_catalog`` — kein anderer Waechter haette das gefangen. Behoben
    wird es in E6, hier wird es mechanisch reproduzierbar.

    Die vier neuen sind der erste echte Fang des Waechters im Betrieb: sie
    entstanden NACH seiner Einfuehrung und wurden nicht von Hand entdeckt.
    """
    reg = REGISTERED_LISTS[MP_SCHLUESSEL]
    assert reg.soll_vollstaendig is not None, (
        f"{MP_SCHLUESSEL} traegt kein soll_vollstaendig — die "
        "Vollstaendigkeitsrichtung ist dort unbewacht."
    )
    assert pruefe_registrierte_liste(MP_SCHLUESSEL, reg) == [], (
        "Mit dokumentierter Ausnahme muss die Registrierung still sein "
        "(sonst ist der Waechter am Tag der Einfuehrung rot)."
    )

    ohne_ausnahme = replace(reg, fehlend_erlaubt=frozenset())
    text = "\n".join(pruefe_registrierte_liste(MP_SCHLUESSEL, ohne_ausnahme))

    luecke = {
        "temperature_night", "wind_chill_night",
        "temperature_day_low", "temperature_day_high",
        "wind_chill_day_low", "wind_chill_day_high",
    }
    for fehlend in sorted(luecke):
        assert fehlend in text, (
            f"{fehlend!r} fehlt in METRIC_PRIORITY, wird aber nicht gemeldet: "
            f"{text!r}"
        )
    assert {m.id for m in get_all_metrics()} >= luecke, (
        "Alle sechs Groessen sind waehlbar — sonst waere der Fang keiner."
    )


def test_ausnahme_ohne_begruendung_ist_keine_ausnahme():
    """AC-5: Muster ``COMPACT_LABEL_EXCEPTIONS``/``gz-eigenstaendig`` — ein
    Eintrag ohne lesbaren Satz mit Ticket-Bezug wird gemeldet."""
    reg = REGISTERED_LISTS[MP_SCHLUESSEL]

    for kaputt, warum in (
        (replace(reg, begruendung=""), "leere Begruendung"),
        (replace(reg, begruendung="s.o."), "zu kurze Begruendung"),
        (replace(reg, begruendung="Wird spaeter einmal nachgezogen werden."),
         "Begruendung ohne Ticket-Bezug"),
    ):
        befunde = pruefe_registrierte_liste(MP_SCHLUESSEL, kaputt)
        assert befunde, f"{warum} blieb unbeanstandet ({kaputt.begruendung!r})"
        assert MP_SCHLUESSEL in "\n".join(befunde)


def test_ausnahmeliste_darf_nur_schrumpfen():
    """AC-5: waechst sie, muss jemand ``VORZUSTAND_FEHLEND_ERLAUBT`` bewusst
    aendern — kein stiller Filter."""
    for schluessel in sorted(VORZUSTAND_FEHLEND_ERLAUBT):
        assert schluessel in REGISTERED_LISTS, (
            f"{schluessel!r} steht im Vorzustand, aber nicht in "
            "REGISTERED_LISTS — der Vorzustand bewacht ein Phantom."
        )

    for schluessel, reg in sorted(REGISTERED_LISTS.items()):
        if not reg.fehlend_erlaubt:
            continue
        assert schluessel in VORZUSTAND_FEHLEND_ERLAUBT, (
            f"{schluessel!r} hat eine neue Ausnahmeliste "
            f"({sorted(reg.fehlend_erlaubt)!r}), die nirgends festgehalten "
            "ist. Ausnahmen werden eingetragen, nicht eingeschmuggelt."
        )
        erlaubt = VORZUSTAND_FEHLEND_ERLAUBT[schluessel]
        assert len(reg.fehlend_erlaubt) <= len(erlaubt), (
            f"{schluessel!r}: Ausnahmeliste gewachsen von {len(erlaubt)} auf "
            f"{len(reg.fehlend_erlaubt)} ({sorted(reg.fehlend_erlaubt)!r})."
        )
        assert reg.fehlend_erlaubt <= erlaubt, (
            f"{schluessel!r}: {sorted(reg.fehlend_erlaubt - erlaubt)!r} steht "
            "neu in der Ausnahmeliste, ohne dass der Vorzustand es kennt. "
            "Gleich viele Eintraege heisst nicht dieselben — ein Tausch waere "
            "sonst eine stille neue Ausnahme."
        )
