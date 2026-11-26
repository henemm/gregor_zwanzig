"""Selbstnachweis des Katalog-Waechters "Einstellung = Mail" (Rework #3020 R1b).

SPEC: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-1 bis AC-4, AC-16)

Befund (docs/context/rework-3020-pruefungen-und-waisen.md, Abschnitt R1b): eine Vitest-Datei mit
einem reinen Platzhalter-Titel (``test(`${key}`, ...)``) wird in ``_template_muster`` zu ``.+`` und
trifft jeden Titel. Damit gelten Katalogverweise ohne Dateiangabe immer als gefunden, auch wenn ihr
Test laengst geloescht ist (26 falsch-gruene ``D-*-frontend``-Faelle nach #3357).

Die Pruefungen laufen gegen die echten Waechter-Funktionen aus
``tests/tdd/test_einstellung_gleich_mail_fallliste.py``; die synthetischen Faelle liegen in
``tmp_path`` (kein Mock), die Katalogpruefungen (AC-3, AC-4) lesen den echten Katalog.
"""
from __future__ import annotations

from pathlib import Path

from tests.tdd import test_einstellung_gleich_mail_fallliste as w

#: Reine Platzhalter-Vorlage wie in ``standardwerte_hilfe_textkatalog.test.ts:88``.
_NUR_PLATZHALTER = "for (const key of keys) {\n  test(`${key}`, () => {});\n}\n"
_ZWEI_PLATZHALTER = "for (const [a, b] of paare) {\n  test(`${a}${b}`, () => {});\n}\n"
_MIT_FESTEM_ANTEIL = "for (const id of ids) {\n  test(`anzeige_${id}_gleich`, () => {});\n}\n"

#: Die 26 Verweise, die vor #3020 im Katalog standen (Titel der in #3357 geloeschten Dateien
#: ``editor_standard_gleich_mail.test.ts`` und ``nur_ein_bericht_kennzeichnung.test.ts``).
ALTE_VERWEISE_OHNE_TEST: dict[str, str] = {
    "D-trip_tabellen-nie_eingestellt-frontend": "frontend_seite_trip_tabellen_standard",
    "D-trip_tabellen-altbestand_ohne_metrics-frontend": "frontend_seite_trip_tabellen_altbestand",
    "D-trip_tabellen-gespeichert_folge-frontend": "frontend_seite_trip_tabellen_gespeichert",
    "D-trip_tabellen-gespeichert_folge_array_ungleich_order-frontend": "frontend_seite_trip_tabellen_gespeichert",
    "D-trip_tabellen-gespeichert_ausserhalb_grundauswahl-frontend": "frontend_seite_trip_tabellen_gespeichert",
    "D-trip_ausblick-nie_eingestellt-frontend": "frontend_seite_trip_ausblick_standard",
    "D-trip_ausblick-gespeichert_folge-frontend": "frontend_seite_trip_ausblick_gespeichert",
    "D-trip_ausblick-gespeichert_ausserhalb_grundauswahl-frontend": "frontend_seite_trip_ausblick_gespeichert",
    "D-orte_vergleichstabelle-nie_eingestellt-frontend": "frontend_seite_orte_vergleichstabelle_standard",
    "D-orte_vergleichstabelle-gespeichert_folge-frontend": "frontend_seite_orte_vergleichstabelle_gespeichert",
    "D-orte_vergleichstabelle-gespeichert_kanal_liste-frontend": "frontend_seite_orte_vergleichstabelle_gespeichert",
    "D-trip_vorlage-reihenfolge-frontend": "frontend_seite_trip_vorlage_reihenfolge",
    "D-trip_ausblick-bewusst_leer_alle_aus-frontend": "frontend_seite_trip_ausblick_bewusst_leer_alle_aus",
    "D-trip_tabellen-gespeichert_totalschnitt-frontend": "frontend_seite_trip_tabellen_gespeichert",
    "D-trip_tabellen-totalschnitt_aus_wirkt-frontend": "frontend_seite_trip_kanal_totalschnitt_aus_wirkt",
    "D-trip_ausblick-gespeichert_totalschnitt-frontend": "frontend_seite_trip_ausblick_gespeichert",
    "D-orte_vergleichstabelle-gespeichert_kanal_totalschnitt-frontend": "frontend_seite_orte_vergleichstabelle_gespeichert",
    "D-orte_vergleichstabelle-totalschnitt_aus_wirkt-frontend": "frontend_seite_orte_kanal_totalschnitt_aus_wirkt",
    "D-orte_vergleichstabelle-grundauswahl_bewusst_leer-frontend": "frontend_seite_orte_vergleichstabelle_grundauswahl_bewusst_leer",
    "D-trip_tabellen-hinweis_grundauswahl_leer-frontend": "frontend_seite_hinweis_grundauswahl_leer_trip",
    "D-orte_vergleichstabelle-hinweis_grundauswahl_leer-frontend": "frontend_seite_hinweis_grundauswahl_leer_orte",
    "D-trip_tabellen-nur_ein_bericht_semantik-frontend": "n3_semantik_wie_mail",
    "D-trip_tabellen-nur_ein_bericht_kennzeichnung-frontend": "n3_editor_kennzeichnet_je_zeile",
    "D-trip_tabellen-nur_ein_bericht_editorstand-frontend": "n3_kennzeichnung_folgt_dem_editorstand",
    "D-trip_tabellen-bericht_flags_bewahrt-frontend": "n3_speichern_bewahrt_bericht_flags",
    "D-trip_ausblick-grundauswahl_ohne_ausblick-frontend": "frontend_seite_trip_ausblick_grundauswahl_ohne_ausblick",
}
#: #3364: die drei Nur-ein-Bericht-Faelle sind gruen und zeigen auf die G44-Tests der Karte
#: (vorher ``ausnahme`` mit #3065, Kennzeichnung entfiel); der Flag-Erhalt bleibt ``ausnahme``/#3065
#: mit Go-Beleg.
_KARTENTEST = "frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts::"
NUR_EIN_BERICHT_GRUEN = {
    "D-trip_tabellen-nur_ein_bericht_semantik-frontend": _KARTENTEST + "n3_semantik_wie_mail",
    "D-trip_tabellen-nur_ein_bericht_kennzeichnung-frontend": _KARTENTEST + "n3_editor_kennzeichnet_je_zeile",
    "D-trip_tabellen-nur_ein_bericht_editorstand-frontend": _KARTENTEST + "n3_kennzeichnung_folgt_dem_editorstand",
}
BERICHT_FLAGS_BEWAHRT = "D-trip_tabellen-bericht_flags_bewahrt-frontend"
TELEGRAM_NUR_TAGESWERT_TEST = (
    "frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts::"
    "Trip: „nur Tageswert“, „passt nicht mehr“, Zeile mit max_length und Hinweissatz für Trip"
)


def _vitest_datei(wurzel: Path, name: str, inhalt: str) -> Path:
    datei = wurzel / "frontend" / "src" / "lib" / "z" / "__tests__" / name
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(inhalt, encoding="utf-8")
    return datei


def _editor_fall(fid: str, test: str) -> dict:
    return w._syn_fall(fid, "trip_vorlage", "editor", "standard", seite="frontend", test=test)


# ---------------------------------------------------------------------------
# AC-1: erfundener Titel ohne Dateiangabe wird rot, trotz reiner Platzhalter-Vorlage
# ---------------------------------------------------------------------------


def test_ac1_erfundener_titel_ohne_datei_wird_trotz_platzhalter_vorlage_rot(tmp_path):
    daten = w._syn_daten()
    daten["fallliste_editor.json"]["faelle"].append(
        _editor_fall("ed-erfunden", "frontend_seite_gibt_es_nicht_mehr"))
    verzeichnis = w._schreibe(tmp_path, daten)
    _vitest_datei(tmp_path, "hilfe_textkatalog.test.ts", _NUR_PLATZHALTER)

    fehler = w.pruefe_testverweise(w.lade_falllisten(verzeichnis), tmp_path)

    assert len(fehler) == 1, fehler
    assert "'ed-erfunden'" in fehler[0], fehler


# ---------------------------------------------------------------------------
# AC-2: Vorlage mit festem Anteil trifft, reine Platzhalter-Vorlage nie
# ---------------------------------------------------------------------------


def test_ac2_vorlage_mit_festem_anteil_trifft_reine_platzhalter_vorlage_nie(tmp_path):
    gemischt = _vitest_datei(tmp_path, "gemischt.test.ts", _MIT_FESTEM_ANTEIL + _NUR_PLATZHALTER)
    nur_platzhalter = _vitest_datei(tmp_path, "nur_platzhalter.test.ts", _NUR_PLATZHALTER + _ZWEI_PLATZHALTER)

    assert w._vitest_titel_gefunden("anzeige_a_nie_gleich", [gemischt]) is True
    assert w._vitest_titel_gefunden("anzeige_a_nie_gleich", [nur_platzhalter]) is False
    assert w._vitest_titel_gefunden("frei erfundener titel", [gemischt]) is False
    assert w._vitest_titel_gefunden("frei erfundener titel", [nur_platzhalter]) is False
    assert w._vitest_titel_gefunden("anzeige__gleich", [gemischt]) is False


# ---------------------------------------------------------------------------
# AC-16: genau der Fall mit fehlendem Ziel wird rot, die gueltigen bleiben gruen
# ---------------------------------------------------------------------------


def test_ac16_nur_faelle_mit_fehlendem_ziel_werden_rot(tmp_path):
    daten = w._syn_daten()
    editor = daten["fallliste_editor.json"]["faelle"]
    editor.append(_editor_fall("ed-titel-fehlt", "titel_den_es_nirgends_gibt"))
    editor.append(_editor_fall("ed-datei-fehlt", "gibt_es_nicht.test.ts::editor behaelt reihenfolge"))
    editor.append(_editor_fall("ed-gueltig-vorlage",
                               "frontend/src/lib/z/__tests__/gemischt.test.ts::anzeige_b_gleich"))
    verzeichnis = w._schreibe(tmp_path, daten)
    _vitest_datei(tmp_path, "gemischt.test.ts", _MIT_FESTEM_ANTEIL + _NUR_PLATZHALTER)

    fehler = w.pruefe_testverweise(w.lade_falllisten(verzeichnis), tmp_path)

    rote_ids = sorted(fid for fid in ("ed-titel-fehlt", "ed-datei-fehlt", "ed-gueltig-vorlage", "ed-1", "ed-2")
                      if any(f"'{fid}'" in f for f in fehler))
    assert rote_ids == ["ed-datei-fehlt", "ed-titel-fehlt"], fehler
    assert len(fehler) == 2, fehler


# ---------------------------------------------------------------------------
# AC-3: die 26 bisher falsch-gruenen Faelle
# ---------------------------------------------------------------------------


def _dateien_mit_reiner_platzhalter_vorlage() -> list[Path]:
    """Vitest-Dateien im echten Baum mit mindestens einer Titelvorlage ohne festen Text (``${key}``)."""
    return [d for d in sorted(w.REPO_ROOT.glob(w.VITEST_GLOB))
            if any(not w._hat_festen_text(v) for v in w._VITEST_TEMPLATE_GANZ.findall(d.read_text(encoding="utf-8")))]


def test_ac3_alte_verweise_der_26_faelle_erkennt_der_waechter_als_fehlend():
    """Beweis, dass der Falsch-Gruen-Mechanismus abgestellt ist: die 26 nackten Alt-Titel werden
    in keiner Datei mit reiner Platzhalter-Vorlage gefunden.

    Abgleich #3020 R1 (Aenderung an diesem Test von #3382): bis R1 sollten die Titel im ganzen
    Baum fehlen. Seit R1 sind sie dort woertlich belegt -- ``editor_standard_gleich_ausgabe_3020.test.ts``
    (``frontend_seite_*``) und ``was_steht_wo_karte.test.ts`` (``n3_*`` als todo #3364) --, ein
    Treffer im ganzen Baum ist also kein Falsch-Gruen mehr. Geprueft wird weiter genau der
    Mechanismus: eine Vorlage wie ``${key}`` darf keinen dieser Titel belegen."""
    dateien = _dateien_mit_reiner_platzhalter_vorlage()
    assert dateien, "keine Datei mit reiner Platzhalter-Vorlage im Baum -- der Test liefe leer"
    falsch_gefunden = [fid for fid, titel in ALTE_VERWEISE_OHNE_TEST.items()
                       if w._vitest_titel_gefunden(titel, dateien)]
    assert falsch_gefunden == [], f"Platzhalter-Vorlage belegt diese Faelle falsch: {falsch_gefunden}"


def test_ac3_katalog_verweist_jeden_der_26_faelle_ehrlich():
    """Im echten Katalog verweist jeder der 26 Faelle auf einen existierenden Test MIT
    Dateiangabe oder traegt ``ausnahme`` mit Verweismuster -- kein Gruen ohne echten Test."""
    faelle = {f["id"]: f for _, f in w._alle_faelle(w.lade_falllisten(w.FALLLISTEN_DIR))}
    vitest_dateien = sorted(w.REPO_ROOT.glob(w.VITEST_GLOB))
    fehler = []
    for fid in ALTE_VERWEISE_OHNE_TEST:
        fall = faelle.get(fid)
        if fall is None:
            fehler.append(f"{fid}: fehlt im Katalog")
            continue
        test = str(fall.get("test") or "")
        if fall.get("status") == "ausnahme":
            if not w.VERWEIS_MUSTER.search(str(fall.get("verweis") or "")):
                fehler.append(f"{fid}: ausnahme ohne Verweismuster")
        elif ".test.ts::" not in test:
            fehler.append(f"{fid}: Status {fall.get('status')!r} ohne Dateiangabe im Verweis {test!r}")
        elif not w._pruefe_vitest_verweis(test, vitest_dateien):
            fehler.append(f"{fid}: Verweis {test!r} nicht gefunden")
    assert fehler == [], "\n".join(fehler)


def test_3364_nur_ein_bericht_faelle_gruen_auf_kartentest():
    """#3364 (loest die Ratsche ``ausnahme``/#3065 ab): die drei Nur-ein-Bericht-Faelle stehen auf
    ``gruen``, verweisen auf #3364 und zeigen genau auf ihren G44-Kartentest, der im Baum existiert.
    Der Flag-Erhalt bleibt ``ausnahme`` mit #3065 (Go-Beleg)."""
    faelle = {f["id"]: f for _, f in w._alle_faelle(w.lade_falllisten(w.FALLLISTEN_DIR))}
    vitest_dateien = sorted(w.REPO_ROOT.glob(w.VITEST_GLOB))
    fehler = []
    for fid, soll_test in NUR_EIN_BERICHT_GRUEN.items():
        fall = faelle.get(fid)
        if fall is None:
            fehler.append(f"{fid}: fehlt im Katalog")
            continue
        if fall.get("status") != "gruen":
            fehler.append(f"{fid}: Status {fall.get('status')!r} statt 'gruen'")
        if fall.get("test") != soll_test:
            fehler.append(f"{fid}: Verweis {fall.get('test')!r} statt {soll_test!r}")
        if "#3364" not in str(fall.get("verweis") or ""):
            fehler.append(f"{fid}: Verweis nennt #3364 nicht")
        if not w._pruefe_vitest_verweis(soll_test, vitest_dateien):
            fehler.append(f"{fid}: Kartentest {soll_test!r} nicht gefunden")
    bewahrt = faelle.get(BERICHT_FLAGS_BEWAHRT, {})
    if bewahrt.get("status") != "ausnahme" or "#3065" not in str(bewahrt.get("verweis") or ""):
        fehler.append(f"{BERICHT_FLAGS_BEWAHRT}: ohne ausnahme/#3065")
    assert fehler == [], "\n".join(fehler)


# ---------------------------------------------------------------------------
# AC-4: Telegram "nur Tageswert" (ADR-0124 Nr. 3) ist im Katalog belegt
# ---------------------------------------------------------------------------


def test_ac4_katalogfall_telegram_nur_tageswert_verweist_gruen_auf_kartentest():
    faelle = [f for _, f in w._alle_faelle(w.lade_falllisten(w.FALLLISTEN_DIR))
              if str(f.get("test") or "") == TELEGRAM_NUR_TAGESWERT_TEST]
    assert faelle, "kein Katalogfall verweist auf den Kartentest „nur Tageswert“ (Telegram-Schnittlinie)"
    assert all(f.get("status") == "gruen" for f in faelle), [(f["id"], f.get("status")) for f in faelle]
    vitest_dateien = sorted(w.REPO_ROOT.glob(w.VITEST_GLOB))
    assert w._pruefe_vitest_verweis(TELEGRAM_NUR_TAGESWERT_TEST, vitest_dateien)


# ---------------------------------------------------------------------------
# #3390: Ortsvergleich-Telegram "alle Zeilen" ist gruen auf dem Kartentest belegt
# ---------------------------------------------------------------------------

ORTE_TELEGRAM_ALLE_ZEILEN = {
    f"E-R8-F3N-VERSAND-ORTE-{lang.upper()}": (
        "frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts::"
        f"Orte, {lang}: neun Metriken stehen alle in der Telegram-Spalte, ohne Marke und ohne Grenz-Text"
    )
    for lang in ("de", "en")
}


def test_3390_orte_telegram_faelle_verweisen_gruen_auf_kartentest():
    """AC-1/AC-2 (#3390): ORTE-DE/-EN stehen auf ``gruen`` und verweisen auf genau den
    Kartentest ihrer Sprache, der im Baum existiert."""
    faelle = {f["id"]: f for _, f in w._alle_faelle(w.lade_falllisten(w.FALLLISTEN_DIR))}
    vitest_dateien = sorted(w.REPO_ROOT.glob(w.VITEST_GLOB))
    fehler = []
    for fid, soll_test in ORTE_TELEGRAM_ALLE_ZEILEN.items():
        fall = faelle.get(fid)
        if fall is None:
            fehler.append(f"{fid}: fehlt im Katalog")
            continue
        if fall.get("status") != "gruen":
            fehler.append(f"{fid}: Status {fall.get('status')!r} statt 'gruen'")
        if fall.get("test") != soll_test:
            fehler.append(f"{fid}: Verweis {fall.get('test')!r} statt {soll_test!r}")
        if not w._pruefe_vitest_verweis(soll_test, vitest_dateien):
            fehler.append(f"{fid}: Kartentest {soll_test!r} nicht gefunden")
    assert fehler == [], "\n".join(fehler)
