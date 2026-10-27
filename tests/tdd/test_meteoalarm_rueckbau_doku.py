# doc-compliance-test
"""TDD RED -- Doku-Vermerke zum MeteoAlarm-EDR-Rueckbau (Issue #2266, Epic #2258).

SPEC: docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md (AC-7, AC-8)

Werkzeug-Klasse (CLAUDE.md-Ausnahme ``# doc-compliance-test``): gelesen werden
AUSSCHLIESSLICH Doku-/Fixture-Beschreibungen, nie Produkt-Quelltext unter ``src/``:

- ``tests/fixtures/meteoalarm_feed/README.md`` (AC-7)
- ``docs/adr/0074-auffrischraster-meteoalarm-feed-deutschland.md`` (AC-8)
- ``docs/specs/data_sources.md`` (AC-8)

Geprueft wird je Abschnitt (nicht dateiweit) und mit Verneinungs-Naehe, damit
ein beliebiges Stichwort irgendwo in der Datei nicht genuegt. Vor dem Vergleich
wird normalisiert (Kleinschreibung, Umlaute -> ae/oe/ue/ss, Leerraum
zusammengefasst) -- ``data_sources.md`` schreibt transliteriert, ADR-0074 mit
Umlauten. Der WERT der TTL (1800 s) wird zusaetzlich als Verhaltenstest in
``tests/tdd/test_warn_journal_felder.py`` geprueft.

RED heute: README nennt ``MeteoAlarmSource.fetch()`` als Herkunft und sagt nichts
zu eingefrorenen Snapshots; ADR-0074 hat keinen Lizenz-Abschnitt;
``data_sources.md`` fuehrt ``api.meteoalarm.org`` als "abgeloest, Code bleibt".
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FEED_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "meteoalarm_feed"
_README = _FEED_FIXTURES / "README.md"
_ADR_0074 = _REPO_ROOT / "docs" / "adr" / "0074-auffrischraster-meteoalarm-feed-deutschland.md"
_DATA_SOURCES = _REPO_ROOT / "docs" / "specs" / "data_sources.md"
# Vorhandensein/Nutzbarkeit der Feed-Fixtures (zweiter Teil von AC-7) prueft
# ``tests/tdd/test_meteoalarm_feed_aequivalenz_snapshots.py``.

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _norm(text: str) -> str:
    text = text.lower().translate(_UMLAUTE)
    text = re.sub(r"[‐-―]", "-", text)  # typografische Striche -> '-'
    return re.sub(r"\s+", " ", text)


def _abschnitte(markdown: str) -> list[tuple[int, str, str]]:
    """Zerlegt Markdown in (Ebene, Ueberschrift, Rumpf bis zur naechsten
    Ueberschrift gleicher oder hoeherer Ebene)."""
    zeilen = markdown.splitlines()
    koepfe = [(i, len(m.group(1)), m.group(2)) for i, z in enumerate(zeilen)
              if (m := re.match(r"^(#{1,6})\s+(.*)$", z))]
    ergebnis = []
    for n, (start, ebene, titel) in enumerate(koepfe):
        ende = len(zeilen)
        for folge_start, folge_ebene, _ in koepfe[n + 1:]:
            if folge_ebene <= ebene:
                ende = folge_start
                break
        ergebnis.append((ebene, titel, "\n".join(zeilen[start + 1:ende])))
    return ergebnis


def _abschnitt(markdown: str, titel_muster: str, quelle: str) -> str:
    treffer = [rumpf for _e, titel, rumpf in _abschnitte(markdown)
               if re.search(titel_muster, _norm(titel))]
    assert treffer, f"{quelle}: kein Abschnitt mit Ueberschrift ~ /{titel_muster}/ gefunden"
    return treffer[0]


def _verneint(text: str, begriff: str, fenster: int = 120) -> bool:
    """``begriff`` steht im selben Satz in Naehe einer Verneinung."""
    neg = r"\b(?:kein\w*|nicht|nie|ohne)\b"
    return bool(re.search(rf"{neg}[^.]{{0,{fenster}}}{begriff}|{begriff}[^.]{{0,{fenster}}}{neg}", text))


def _fehlende_lizenz_aussagen(abschnitt: str) -> list[str]:
    """AC-8-Kernaussagen zur Feed-TTL gegen die EUMETNET-Weitergabe-Auflage."""
    t = _norm(abschnitt)
    fehlend = []
    if "eumetnet" not in t:
        fehlend.append("Bezug auf die EUMETNET-Auflage")
    # Naehe statt Satzgrenze: "TTL 1800 s ... Die TTL bleibt unveraendert" ist zulaessig.
    if not re.search(r"1800 ?s.{0,200}(?:unveraendert|bleibt)|(?:unveraendert|bleibt).{0,200}1800 ?s", t):
        fehlend.append("TTL bleibt unveraendert bei 1800 s")
    if not re.search(r"mindest[\w-]*verzug|mindest[^.]{0,80}verzug", t):
        fehlend.append("Cache erfuellt einen Mindest-Verzug")
    if not _verneint(t, r"obergrenze"):
        fehlend.append("keine Obergrenze belegt")
    if not _verneint(t, r"primaerquelle"):
        fehlend.append("keine Primaerquelle im Repo")
    return fehlend


# ── AC-7: README der Feed-Fixtures ────────────────────────────────────────────

def test_ac7_readme_nennt_die_edr_klasse_nicht_mehr_als_herkunft():
    """AC-7: GIVEN die EDR-Klasse ist zurueckgebaut, WHEN die README gelesen
    wird, THEN verweist sie nicht mehr auf ``MeteoAlarmSource.fetch()`` als
    (nachvollziehbaren) Abrufweg der Snapshots."""
    text = _README.read_text(encoding="utf-8")
    assert "MeteoAlarmSource.fetch()" not in text, (
        "README nennt weiterhin MeteoAlarmSource.fetch() als Herkunft der Snapshots -- "
        "die Klasse existiert nach #2266 nicht mehr"
    )


def test_ac7_readme_edr_snapshots_eingefroren_und_ohne_aufzeichnungsskript():
    """AC-7: GIVEN das Aufzeichnungsskript lag nie im Repo, WHEN die Abschnitte
    zu ``edr_snapshot_it.json`` und ``edr_snapshot_at.json`` gelesen werden,
    THEN steht in JEDEM, dass der Snapshot eingefroren ist und kein
    Aufzeichnungsskript existiert."""
    text = _README.read_text(encoding="utf-8")
    probleme = []
    for land in ("it", "at"):
        rumpf = _norm(_abschnitt(text, rf"edr_snapshot_{land}\.json", "README"))
        if "eingefroren" not in rumpf:
            probleme.append(f"edr_snapshot_{land}: 'eingefroren' fehlt")
        if not _verneint(rumpf, r"(?:aufzeichnungs-?skript|skript)"):
            probleme.append(f"edr_snapshot_{land}: Aussage 'kein Aufzeichnungsskript' fehlt")
    assert not probleme, "\n".join(probleme)


# ── AC-8: Lizenz-Pruefergebnis zur Feed-TTL ───────────────────────────────────

def test_ac8_adr_0074_traegt_lizenz_pruefergebnis_zur_feed_ttl():
    """AC-8: GIVEN die Lizenzfrage zur 30-min-TTL, WHEN ADR-0074 gelesen wird,
    THEN steht in einem Lizenz-Abschnitt: TTL bleibt 1800 s, erfuellt einen
    Mindest-Verzug, keine Obergrenze belegt, keine Primaerquelle im Repo."""
    abschnitt = _abschnitt(_ADR_0074.read_text(encoding="utf-8"), r"lizenz", "ADR-0074")
    fehlend = _fehlende_lizenz_aussagen(abschnitt)
    assert not fehlend, f"ADR-0074 Lizenz-Abschnitt: es fehlen {fehlend}"


def test_ac8_data_sources_antrag_2_vermerkt_rueckbau_und_lizenz_pruefergebnis():
    """AC-8: GIVEN Antrag #2 (MeteoAlarm) in ``data_sources.md``, WHEN er gelesen
    wird, THEN ist ``api.meteoalarm.org`` als zurueckgebaut (#2266) vermerkt --
    ohne den veralteten Satz "Code bleibt ... erhalten" -- und das
    Lizenz-Pruefergebnis zur Feed-TTL steht im selben Antrag."""
    abschnitt = _abschnitt(_DATA_SOURCES.read_text(encoding="utf-8"),
                           r"^antrag #2\b", "data_sources.md")
    edr_zeilen = [_norm(z) for z in abschnitt.splitlines() if "api.meteoalarm.org" in z]
    assert edr_zeilen, "data_sources.md Antrag #2: api.meteoalarm.org wird gar nicht mehr erwaehnt"
    assert any("zurueckgebaut" in z and "2266" in z for z in edr_zeilen), (
        f"api.meteoalarm.org muss als zurueckgebaut (#2266) vermerkt sein, Zeilen: {edr_zeilen}"
    )
    assert not any("code bleibt" in z for z in edr_zeilen), (
        f"veralteter Vermerk 'Code bleibt ... erhalten' steht noch: {edr_zeilen}"
    )
    fehlend = _fehlende_lizenz_aussagen(abschnitt)
    assert not fehlend, f"data_sources.md Antrag #2: es fehlen {fehlend}"
