"""Nachweis-Schicht: ist der Messlatte-Ersatz am Epic #1458 nachlesbar? (Epic #1458)

Die Zusicherungen dieser Arbeit liegen NICHT im Code, sondern auf GitHub: ein
Befund-Kommentar am Epic, der geschlossene Epic-Zustand und zwei Folge-Issues.
Geprueft wird deshalb aus Nutzersicht -- "kann ich am Epic nachlesen, warum die
alte Messlatte ersetzt wurde, und sind die Folgebefunde gebucht?" -- gegen die
echte GitHub-API via ``gh``. Kein Mock: ein gemockter ``gh``-Aufruf wuerde nur
die eigene Annahme zurueckspiegeln und nichts ueber den Zustand auf GitHub
aussagen.

Weil dafuer Netz noetig ist, traegt das Modul den Marker ``live`` -- der
deterministische Kern-Testlauf sammelt diese Tests nicht ein.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

# Repo-Wurzel relativ zur eigenen Testdatei aufloesen -- nie ueber einen festen
# Hauptrepo-Pfad, sonst prueft ein Worktree-Lauf das falsche Repository.
REPO_ROOT = Path(__file__).resolve().parents[1]

EPIC_NUMBER = 1458
GH_TIMEOUT_S = 60

# Wortgrenzen sind hier tragend: ohne sie prueft das Muster nicht "genau diese
# Zeile". ``\b`` allein genuegt NICHT -- der Unterstrich in "alert_log" ist ein
# Wortzeichen, "nicht_alert_log.py:226-229" haette also keine Grenze davor.
# Darum ``(?<!\w)`` vorn, und ``(?!\d)`` hinten, damit ":1430"/":2290" nicht
# als Treffer durchgehen.
FUNDSTELLE_LOG = r"(?<!\w)alert_log\.py\s*:\s*226\s*[-–]\s*229(?!\d)"
FUNDSTELLE_GATE = r"(?<!\w)alert_gate\.py\s*:\s*143(?!\d)"


def _gh_json(args: list[str]) -> object:
    """Ruft ``gh`` im Repo der Testdatei auf und gibt die JSON-Antwort zurueck.

    Scheitert der Aufruf (fehlendes ``gh``, fehlende Authentifizierung,
    API-Fehler), bricht der Test mit der Original-Fehlermeldung ab -- das ist
    dann ausdruecklich KEIN inhaltlicher Befund, sondern ein Werkzeugproblem,
    und muss als solches erkennbar sein. Kein Skip: ein stiller Skip wuerde
    die Zusicherung unbemerkt abschalten.
    """
    try:
        proc = subprocess.run(
            ["gh", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_S,
        )
    except FileNotFoundError:  # pragma: no cover - Werkzeugproblem
        pytest.fail("WERKZEUG: 'gh' ist nicht installiert -- kein inhaltlicher Befund.")
    if proc.returncode != 0:  # pragma: no cover - Werkzeugproblem
        pytest.fail(
            "WERKZEUG: 'gh "
            + " ".join(args)
            + f"' scheiterte (exit {proc.returncode}) -- kein inhaltlicher Befund.\n"
            + proc.stderr.strip()
        )
    return json.loads(proc.stdout)


def _normalize(text: str) -> str:
    """Whitespace vereinheitlichen, damit Zeilenumbrueche und Einrueckungen im
    Kommentartext die Suche nicht scheitern lassen. Zeichen werden NICHT
    entfernt -- fehlt eine Zahl, bleibt der Test rot."""
    return re.sub(r"\s+", " ", text)


@pytest.fixture(scope="module")
def epic_comments() -> list[str]:
    """Alle Kommentar-Texte von Issue #1458, normalisiert."""
    data = _gh_json(["issue", "view", str(EPIC_NUMBER), "--json", "comments"])
    return [c.get("body", "") for c in data["comments"]]


@pytest.fixture(scope="module")
def epic_comments_normalized(epic_comments: list[str]) -> list[str]:
    return [_normalize(body) for body in epic_comments]


def _issues_with_labels(*labels: str, state: str = "open") -> list[dict]:
    args = ["issue", "list", "--state", state, "--limit", "100"]
    for label in labels:
        args += ["--label", label]
    args += ["--json", "number,title,body,labels"]
    return _gh_json(args)


def _open_issues_with_labels(*labels: str) -> list[dict]:
    return _issues_with_labels(*labels, state="open")


def _issue_texts(number: int) -> list[str]:
    """Body und alle Kommentar-Texte eines Issues, normalisiert.

    Der PO-Entscheid kann an beiden Stellen stehen -- beim Anlegen im Body, bei
    einer spaeteren Revision als Kommentar. Beide Orte zaehlen, aber jeder
    Textblock wird EINZELN geprueft: sonst wuerde ein "PO-Entscheid" aus dem
    Body zusammen mit einer "Begruendung" aus einem beliebigen anderen
    Kommentar als Treffer durchgehen.
    """
    data = _gh_json(["issue", "view", str(number), "--json", "body,comments"])
    return [_normalize(data.get("body") or "")] + [
        _normalize(c.get("body", "")) for c in data.get("comments", [])
    ]


def _titles(issues: list[dict]) -> str:
    if not issues:
        return "(keine)"
    return ", ".join(f"#{i['number']} {i['title']!r}" for i in issues)


# --- AC-2: Begruendung mit Fundstelle -----------------------------------------
def test_ac2_kommentar_begruendet_unerfuellbare_messlatte(epic_comments_normalized):
    """GIVEN die alte Messlatte des Epics ist strukturell nicht erfuellbar
    WHEN ein Leser die Kommentare von Issue #1458 durchgeht
    THEN findet er einen Kommentar, der die Fundstelle alert_log.py:226-229
         nennt und begruendet, dass der Wert der gemeldeten Groesse dort nicht
         gefuehrt wird."""
    mit_fundstelle = [
        body for body in epic_comments_normalized if re.search(FUNDSTELLE_LOG, body)
    ]
    assert mit_fundstelle, (
        f"Kein Kommentar an #{EPIC_NUMBER} nennt die Fundstelle "
        "'alert_log.py:226-229' -- die Begruendung, warum die alte Messlatte "
        f"nicht erfuellbar ist, ist am Epic nicht nachlesbar "
        f"({len(epic_comments_normalized)} Kommentare geprueft)."
    )
    mit_begruendung = [
        body
        for body in mit_fundstelle
        if re.search(r"Wert[^.]{0,160}nicht|nicht[^.]{0,160}Wert", body)
    ]
    assert mit_begruendung, (
        f"Der Kommentar an #{EPIC_NUMBER} nennt zwar 'alert_log.py:226-229', "
        "begruendet aber nicht, dass der WERT der gemeldeten Groesse dort nicht "
        "gefuehrt wird -- ohne diese Begruendung bleibt offen, warum "
        "Wiederholung nicht von neuer Information unterscheidbar ist."
    )


# --- AC-3: Basislinie mit Zeitraum und Nutzer ---------------------------------
def test_ac3_kommentar_nennt_basislinie_mit_zeitraum_und_nutzer(
    epic_comments_normalized,
):
    """GIVEN die Ersatzkennzahl K1 hat die Basislinie 66,7 %
    WHEN ein Leser die Kommentare von Issue #1458 durchgeht
    THEN findet er einen Kommentar, der 66,7 % zusammen mit dem Messzeitraum
         2026-08-04 bis 2026-08-17 und dem Nutzer henning nennt."""
    # ``(?<!\d)`` statt ``\b``: zwischen "1" und "6" in "166,7 %" gibt es keine
    # Wortgrenze, die falsche Nachbarzahl wuerde sonst mitzaehlen.
    kandidaten = [
        body for body in epic_comments_normalized if re.search(r"(?<!\d)66,7\s*%", body)
    ]
    assert kandidaten, (
        f"Kein Kommentar an #{EPIC_NUMBER} nennt die Basislinie '66,7 %' -- "
        "ohne Basislinie ist Kennzahl K1 nicht nachpruefbar."
    )
    fehlend_pro_kandidat = []
    for body in kandidaten:
        fehlt = [
            teil
            for teil, muster in (
                ("2026-08-04", r"2026-08-04"),
                ("2026-08-17", r"2026-08-17"),
                ("henning", r"henning"),
            )
            if not re.search(muster, body)
        ]
        if not fehlt:
            return
        fehlend_pro_kandidat.append(fehlt)
    pytest.fail(
        f"Der Kommentar an #{EPIC_NUMBER} nennt '66,7 %', aber ohne "
        f"vollstaendige Einordnung -- fehlend: {fehlend_pro_kandidat}. "
        "Eine Basislinie ohne Zeitraum und Nutzer ist nicht reproduzierbar."
    )


# --- AC-3: beide Ersatzkennzahlen ---------------------------------------------
def test_ac3_kommentar_nennt_beide_ersatzkennzahlen(epic_comments_normalized):
    """GIVEN die alte Messlatte wird durch zwei Kennzahlen K1 und K2 ersetzt
    WHEN ein Leser die Kommentare von Issue #1458 durchgeht
    THEN findet er einen Kommentar, der beide Kennzahlen K1 und K2 benennt."""
    for body in epic_comments_normalized:
        if re.search(r"\bK1\b", body) and re.search(r"\bK2\b", body):
            return
    nur_k1 = sum(
        1
        for body in epic_comments_normalized
        if re.search(r"\bK1\b", body) and not re.search(r"\bK2\b", body)
    )
    nur_k2 = sum(
        1
        for body in epic_comments_normalized
        if re.search(r"\bK2\b", body) and not re.search(r"\bK1\b", body)
    )
    pytest.fail(
        f"Kein Kommentar an #{EPIC_NUMBER} nennt beide Ersatzkennzahlen K1 UND "
        f"K2 (nur K1: {nur_k1}, nur K2: {nur_k2}). Die Messlatte gilt erst als "
        "ersetzt, wenn beide Seiten -- weniger Wiederholung UND nicht weniger "
        "echte Warnung -- am Epic stehen."
    )


# --- AC-4: 85 % ist ein Artefakt ----------------------------------------------
def test_ac4_kommentar_markiert_85_prozent_als_artefakt(epic_comments):
    """GIVEN die naive Kontrollprobe auf Juni/Juli liefert 85 %
    WHEN ein Leser den Kommentar an Issue #1458 liest
    THEN steht die Zahl 85 % im selben Absatz mit dem Wort 'Artefakt' und dem
         Hinweis, dass sie nicht zum Vergleich taugt."""
    absaetze = [
        _normalize(absatz)
        for body in epic_comments
        for absatz in re.split(r"\n\s*\n", body)
    ]
    mit_85 = [a for a in absaetze if re.search(r"\b85\s*%", a)]
    assert mit_85, (
        f"Kein Kommentar an #{EPIC_NUMBER} erwaehnt die Kontrollprobe '85 %' -- "
        "die Artefakt-Falle ist damit nicht dokumentiert und ein spaeterer "
        "Leser koennte die Zahl fuer einen Vergleichswert halten."
    )
    ohne_artefakt = [a for a in mit_85 if not re.search(r"Artefakt", a, re.I)]
    assert not ohne_artefakt, (
        f"Ein Absatz im Kommentar an #{EPIC_NUMBER} nennt '85 %' ohne das Wort "
        f"'Artefakt' im selben Absatz: {ohne_artefakt[0][:200]!r}"
    )
    if not any(re.search(r"Vergleich", a, re.I) for a in mit_85):
        pytest.fail(
            f"Der Absatz mit '85 %' an #{EPIC_NUMBER} sagt nicht, dass die Zahl "
            "nicht als Vergleichswert taugt -- 'Artefakt' allein sagt einem "
            "Leser noch nicht, dass er damit nicht rechnen darf."
        )


# --- AC-5: Epic geschlossen ---------------------------------------------------
def test_ac5_epic_1458_ist_geschlossen():
    """GIVEN der Befund-Kommentar ist an Issue #1458 gepostet
    WHEN der Nachweis abgeschlossen ist
    THEN ist Issue #1458 geschlossen."""
    data = _gh_json(["issue", "view", str(EPIC_NUMBER), "--json", "state"])
    assert data["state"] == "CLOSED", (
        f"Issue #{EPIC_NUMBER} ist '{data['state']}', nicht 'CLOSED' -- das Epic "
        "gilt erst als erledigt, wenn die ersetzte Messlatte dokumentiert und "
        "das Epic geschlossen ist."
    )


# --- AC-6: Folge-Issue "Protokoll fuehrt den Wert" ------------------------------
def test_ac6_folge_issue_protokoll_wert_ist_gebucht():
    """GIVEN Befund B3 aus #1459 ist nur zur Haelfte geschlossen (Groesse ja,
         Wert nein)
    WHEN der Nachweis abgeschlossen ist
    THEN existiert ein offenes Issue mit den Labels 'enhancement' und
         'area:alerts', dessen Beschreibung alert_log.py:226-229 als Fundstelle
         nennt."""
    issues = _open_issues_with_labels("enhancement", "area:alerts")
    treffer = [i for i in issues if re.search(FUNDSTELLE_LOG, _normalize(i["body"] or ""))]
    assert treffer, (
        "Kein offenes Issue mit den Labels 'enhancement' + 'area:alerts' nennt "
        "'alert_log.py:226-229' im Body -- der Nebenbefund B3 (Protokoll fuehrt "
        "die Groesse, nicht den Wert) ist nicht gebucht, obwohl Kennzahl K1 ohne "
        f"ihn dauerhaft nur teilweise messbar bleibt. Geprueft: {_titles(issues)}"
    )


# --- AC-7: Folge-Issue "Ruhezeit-Sperre" ---------------------------------------
def test_ac7_folge_issue_ruhezeit_sperre_ist_gebucht():
    """GIVEN Befund F3: 52 Vorfaelle durch die Ruhezeit-Sperre unterdrueckt,
         48 davon nachts zwischen 02 und 06 Uhr
    WHEN der Nachweis abgeschlossen ist
    THEN existiert -- unabhaengig von offen/geschlossen -- ein Issue mit den
         Labels 'priority:high' und 'area:alerts', dessen Beschreibung
         alert_gate.py:143, die Zahlen 52 und 48 sowie die Phrase 'nicht
         verifiziert' enthaelt, und an dem der PO-Entscheid begruendet
         nachlesbar ist.

    Bewusst NICHT auf ``--state open`` eingeschraenkt: ob das Issue offen
    bleibt oder geschlossen wird, entscheidet der PO (#1955 wurde am
    2026-08-18 nach Revision von F3 geschlossen) -- das ist kein Zustand, den
    diese Lieferung zusichern kann. Zugesichert ist, dass der Befund
    vollstaendig gebucht und der Umgang damit begruendet ist.
    """
    issues = _issues_with_labels("priority:high", "area:alerts", state="all")
    kandidaten = [
        i for i in issues if re.search(FUNDSTELLE_GATE, _normalize(i["body"] or ""))
    ]
    assert kandidaten, (
        "Kein Issue mit den Labels 'priority:high' + 'area:alerts' nennt "
        "'alert_gate.py:143' im Body -- der Ruhezeit-Befund F3 (akute Gefahr "
        "kommt nachts nicht durch) ist nicht gebucht. "
        f"Geprueft: {_titles(issues)}"
    )
    fehlend_pro_kandidat = []
    for issue in kandidaten:
        body = _normalize(issue["body"] or "")
        fehlt = [
            teil
            for teil, muster in (
                ("52", r"\b52\b"),
                ("48", r"\b48\b"),
                ("nicht verifiziert", r"nicht verifiziert"),
            )
            if not re.search(muster, body, re.I)
        ]
        # Der PO-Entscheid muss begruendet sein -- ein blosser Vermerk
        # "PO-Entscheid: eigenes Issue" sagt einem spaeteren Leser nicht,
        # WARUM so entschieden wurde. Marker und Begruendung muessen im
        # SELBEN Textblock stehen.
        if not any(
            re.search(r"PO-Entscheid", text, re.I)
            and re.search(r"Begr(ü|ue)ndung|\bweil\b|\bdenn\b", text, re.I)
            for text in _issue_texts(issue["number"])
        ):
            fehlt.append("begruendeter PO-Entscheid (Body oder Kommentar)")
        if not fehlt:
            return
        fehlend_pro_kandidat.append((issue["number"], fehlt))
    pytest.fail(
        "Das Folge-Issue zur Ruhezeit-Sperre nennt 'alert_gate.py:143', aber "
        f"nicht alles Noetige -- fehlend je Kandidat: {fehlend_pro_kandidat}. "
        "Ohne die Zahlen 52/48 fehlt das Ausmass, ohne 'nicht verifiziert' liest "
        "sich ein belegter Verdacht wie eine bewiesene Fehlfunktion, und ohne "
        "begruendeten PO-Entscheid ist nicht nachlesbar, warum mit dem Befund so "
        "umgegangen wurde."
    )
