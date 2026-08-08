"""TDD RED (#1558): Frontend-Aenderungen erzwingen einen echten Browserlauf.

Spec: docs/specs/modules/feat_1558_frontend_browser_gate.md — hier AC-1..AC-5, AC-8.
AC-6/AC-7 liegen in der Live-Schicht (test_frontend_browser_gate_staging.py).

GEPRUEFTE SCHNITTSTELLE (existiert noch nicht — genau deshalb ist die Suite rot):

  .claude/hooks/e2e_frontend_browser_gate.py
    CORE_PAGES: tuple[str, ...] — "/", "/trips", "/trips/new", "/compare",
      "/compare/new", "/locations".
    gate(scope, env) -> int — 0 = durchlassen, != 0 = blockieren. Springt NUR an
      bei scope in ("frontend-only", "full-stack"). Basis-URL aus
      env["GZ_VALIDATION_URL"] (Default wie design_fidelity_diff.py:374). gate()
      bewertet AUSSCHLIESSLICH das uebergebene env und laedt selbst keine
      Zugangsdaten aus Dateien nach — sonst waere "Zugangsdaten fehlen" nicht
      pruefbar; das Nachladen macht der Aufrufer.
    check_pages(base, paths, env) -> tuple[int, list[str]] — startet Chromium,
      meldet sich nur an wenn env GZ_AUTH_USER/GZ_AUTH_PASS traegt, laedt jede
      Seite, sammelt console(type=error) + pageerror. Meldungen nennen Seite UND
      Fehlertext.

  .claude/hooks/staging_gate.py
    FRONTEND_GATE_PATH: Path — Modul-Attribut (nicht inline im Funktionsrumpf),
      damit AC-8 mit einer ECHT kaputten Datei statt einem gemockten Importfehler
      geprueft werden kann.
    _frontend_browser_gate(scope) -> int — Aufruf in write_verdict() NACH der
      Scope-Berechnung (Z. 296); Import-/Syntaxfehler → Warnung + 0.

Deterministisch, ohne fremdes Netz: Wegwerf-Repo per git init, lokaler
http.server auf 127.0.0.1, echtes Chromium. Lauf:
  uv run pytest tests/tdd/test_frontend_browser_gate.py \
      --disable-socket --allow-hosts=127.0.0.1
"""

import importlib.util
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
GATE_PATH = HOOKS_DIR / "e2e_frontend_browser_gate.py"
DEAD_BASE = "http://127.0.0.1:9"  # Discard-Port: garantiert kein Staging


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sg = _load("staging_gate_fbg", HOOKS_DIR / "staging_gate.py")


def _gate_mod():
    assert GATE_PATH.exists(), f"Gate-Modul fehlt: {GATE_PATH}"
    return _load("e2e_frontend_browser_gate_under_test", GATE_PATH)


@pytest.fixture
def hostile(monkeypatch):
    """Umgebung, in der ein Browserlauf zwangslaeufig scheitern WUERDE: totes
    Staging, keine Zugangsdaten. Das unbeteiligte Telegram-Gate wird an seinem
    ehrlichen Seam neutralisiert (Muster test_staging_gate_verdict_merge)."""
    monkeypatch.setattr(sg, "_telegram_live_gate", lambda: 0)
    monkeypatch.setenv("GZ_VALIDATION_URL", DEAD_BASE)
    for k in ("GZ_AUTH_USER", "GZ_AUTH_PASS", "GZ_VALIDATOR_USER", "GZ_VALIDATOR_PASS"):
        monkeypatch.delenv(k, raising=False)


def _verdict(tmp_path, scope, e2e_path=None):
    """write_verdict mit leerer Findings-Datei (nicht angelegt → findings=[])."""
    return sg.write_verdict("VERIFIED: behauptet, aber unbelegt",
                            tmp_path / "findings.json",
                            e2e_path=e2e_path, scope_override=scope)


@pytest.mark.parametrize("scope", ["frontend-only", "full-stack"])
def test_frontend_scope_without_passed_browser_run_writes_no_attestation(
    tmp_path, hostile, scope
):
    """AC-1 (frontend-only) + AC-4 (full-stack zaehlt genauso): der Browserlauf
    kann nicht bestanden werden → Exit 1, KEINE Attestation."""
    e2e_path = tmp_path / "attestation.json"
    rc = _verdict(tmp_path, scope, e2e_path)
    assert rc == 1, f"Scope {scope}: Verdict ohne belegten Browserlauf muss Exit 1 liefern"
    assert not e2e_path.exists(), (
        f"Scope {scope}: Attestation geschrieben, obwohl der Browserlauf nicht "
        "bestanden werden konnte"
    )


@pytest.mark.parametrize("scope", ["backend", "docs-only"])
def test_non_frontend_scope_still_gets_attestation_in_browser_hostile_env(
    tmp_path, hostile, scope
):
    """AC-3: In einer Umgebung, in der ein Browserlauf zwangslaeufig scheitern
    wuerde, entsteht die Attestation trotzdem — damit ist belegt, dass KEIN
    Browserlauf stattfand, ohne einen Aufruf-Zaehler zu befragen."""
    e2e_path = tmp_path / "attestation.json"
    rc = _verdict(tmp_path, scope, e2e_path)
    assert rc == 0, f"Scope {scope} darf vom Frontend-Gate nicht blockiert werden"
    assert json.loads(e2e_path.read_text())["scope"] == scope


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                       text=True, check=True)
    return r.stdout.strip()


def _commit(repo: Path, rel: str, msg: str) -> str:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"# {msg}\n")
    _git(repo, "add", rel)
    _git(repo, "-c", "user.email=t@example.invalid", "-c", "user.name=T",
         "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def test_frontend_change_two_commits_back_still_triggers_gate(
    tmp_path, hostile, monkeypatch
):
    """AC-5 (Waechter gegen den HEAD~1-Erbfehler aus staging_gate.py:237):
    Commit-Folge A(backend) → B(frontend) → C(docs). Der juengste Commit zeigt
    nur Doku; ein eigener HEAD~1-Diff wuerde das Gate schlafen lassen. Gemessen
    wird die WIRKUNG: keine Attestation."""
    repo = tmp_path / "wegwerf-repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    base = _commit(repo, "src/backend.py", "A backend")
    _commit(repo, "frontend/src/lib/Foo.svelte", "B frontend")
    _commit(repo, "docs/notiz.md", "C nur doku")

    monkeypatch.setattr(sg, "REPO_DIR", repo)
    sg._e2e_paths.write_last_gate_scope(repo, base)

    # Vorbedingung 1: der letzte Commit allein sieht nur Dokumentation.
    assert sg._e2e_paths._detect_scope_from_git_diff("HEAD~1", "HEAD", repo) == "docs-only"
    # Vorbedingung 2: der bereits ermittelte Scope sieht die Frontend-Aenderung.
    assert sg._detect_committed_scope() == "frontend-only"

    rc = sg.write_verdict("VERIFIED: behauptet", tmp_path / "findings.json")

    assert rc == 1, "Gate muss trotz Doku-Commit an der Spitze anspringen"
    assert not sg._commit_e2e_path().exists(), (
        "Attestation entstand — das Gate hat die zwei Commits zurueckliegende "
        "Frontend-Aenderung nicht gesehen (HEAD~1-Erbfehler)"
    )


_CLEAN = "<!doctype html><html><head><title>ok</title></head><body><h1>Seite</h1></body></html>"
_BOOM = ("<!doctype html><html><head><title>boom</title></head><body><h1>Seite</h1>"
         "<script>null.gibtEsNichtHier();</script></body></html>")


@pytest.fixture
def local_site():
    """Echter lokaler HTTP-Server: '/boom' wirft beim Laden eine Ausnahme, alle
    anderen Pfade (inkl. der Kernseiten) sind sauber."""
    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = (_BOOM if self.path == "/boom" else _CLEAN).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # stumm
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    srv.server_close()


def test_console_error_while_loading_is_seen_and_named(local_site):
    """AC-2: eine Seite wirft beim Laden — das Gate sieht den Fehler, meldet
    Nicht-Bestehen und nennt Seite und Fehlertext."""
    pytest.importorskip("playwright.sync_api")
    rc, messages = _gate_mod().check_pages(local_site, ["/boom"], {})
    joined = " ".join(messages)
    assert rc != 0, f"Konsolenfehler blieb folgenlos (Meldungen: {messages})"
    assert "/boom" in joined, f"Meldung nennt die Seite nicht: {joined!r}"
    assert "gibtEsNichtHier" in joined, f"Meldung nennt den Fehlertext nicht: {joined!r}"


def test_unloadable_gate_module_lets_verdict_through_with_warning(
    tmp_path, hostile, monkeypatch, capsys
):
    """AC-8 erste Haelfte: ein defektes Gate darf nie die Ursache sein, dass
    niemand mehr ausliefern kann — echte kaputte Datei, kein gemockter Fehler."""
    broken = tmp_path / "e2e_frontend_browser_gate.py"
    broken.write_text("def gate(scope, env):\n    return 0\n  das ist kein python(\n")
    monkeypatch.setattr(sg, "FRONTEND_GATE_PATH", broken)

    e2e_path = tmp_path / "attestation.json"
    rc = _verdict(tmp_path, "frontend-only", e2e_path)

    assert rc == 0 and e2e_path.exists(), "Kaputtes Gate darf nicht blockieren"
    err = capsys.readouterr().err.lower()
    assert "warn" in err and "browser" in err, f"Warnung fehlt/unklar: {err!r}"


def test_missing_means_of_proof_blocks(local_site, hostile):
    """AC-8 zweite Haelfte: Zugangsdaten fehlen bzw. Staging ist tot → blockieren.
    Fall 1 laeuft gegen ein erreichbares, FEHLERFREIES Ziel — dort kann nur die
    Zugangsdaten-Pruefung selbst blocken."""
    g = _gate_mod()
    no_creds = {"GZ_VALIDATION_URL": local_site}
    dead = {"GZ_VALIDATION_URL": DEAD_BASE, "GZ_AUTH_USER": "u", "GZ_AUTH_PASS": "p",
            "GZ_VALIDATOR_USER": "u", "GZ_VALIDATOR_PASS": "p"}
    assert g.gate("frontend-only", no_creds) != 0, "fehlende Zugangsdaten muessen blocken"
    assert g.gate("frontend-only", dead) != 0, "unerreichbares Staging muss blocken"


# ---------------------------------------------------------------------------
# Adversary-Fund F001: die Fail-Grenze aus AC-8 sitzt an der Modulgrenze und
# war nur DORT geprueft, wo der Code steht (check_pages/gate direkt), nicht
# dort, wo sie WIRKT (die Verdrahtung in staging_gate). Zieht man den Aufruf
# `mod.gate(...)` mit in das try/except von _frontend_browser_gate(), blieben
# 19 von 19 Tests gruen — aus dem Waechter wuerde lautlos ein Freifahrtschein.
# ---------------------------------------------------------------------------

def test_unexpected_error_inside_gate_blocks_instead_of_passing(
    tmp_path, hostile, monkeypatch
):
    """AC-8, Grenzfall an der WIRKSTELLE: ein Gate-Modul, das sich sauber laden
    laesst, dessen gate() aber unerwartet abbricht, ist kein KAPUTTES GATE
    sondern ein NICHT ERBRACHTER NACHWEIS — es muss blockieren.

    Echte Datei statt gemocktem Fehler. Geprueft wird die Wirkung: es darf
    keine Attestation entstehen. Ob der Abbruch durchschlaegt oder als Exit 1
    zurueckkommt, ist dabei gleichwertig — beides blockiert. Was NICHT passieren
    darf, ist ein Durchlassen mit Warnung.
    """
    fake = tmp_path / "e2e_frontend_browser_gate.py"
    fake.write_text(
        "CORE_PAGES = ('/',)\n"
        "def load_validator_env():\n"
        "    pass\n"
        "def gate(scope, env):\n"
        "    raise RuntimeError('Browser-Start fehlgeschlagen 1558')\n"
    )
    monkeypatch.setattr(sg, "FRONTEND_GATE_PATH", fake)
    e2e_path = tmp_path / "attestation.json"

    try:
        rc = _verdict(tmp_path, "frontend-only", e2e_path)
    except RuntimeError:
        rc = 1  # Durchschlagen blockiert ebenfalls — kein Verdict entsteht.

    assert rc != 0, (
        "Ein unerwarteter Abbruch IM Browserlauf wurde als 'Gate kaputt' "
        "durchgelassen. Die Fail-Grenze verlaeuft aber zwischen 'Gate nicht "
        "ladbar' (durchlassen) und 'Nachweis nicht erbringbar' (blocken) — "
        "nicht entlang 'Exception ja/nein'."
    )
    assert not e2e_path.exists(), (
        "Attestation entstand, obwohl der Browserlauf unerwartet abbrach"
    )


# ---------------------------------------------------------------------------
# Adversary-Fund F002: AC-6 ("eine fehlerfreie Anmeldemaske ist KEINE
# bestandene Kernseite") war ausschliesslich in der Live-Schicht geprueft — und
# die ist per pyproject.toml:65 (-m 'not ... and not staging') aus jedem
# Standardlauf abgewaehlt. Entfernt man den unauthenticated_reason()-Aufruf,
# blieben 8 von 8 Kern-Tests gruen. Deshalb hier zusaetzlich in der Kern-
# Schicht, ohne Staging: derselbe lokale Server, echtes Chromium.
# ---------------------------------------------------------------------------

_LOGIN = ("<!doctype html><html><head><title>Anmeldung</title></head><body>"
          "<form><input name='username'>"
          "<input type='password' name='password'></form></body></html>")


@pytest.fixture
def unauth_site():
    """Lokaler Server, der antwortet wie eine NICHT angemeldete Anwendung — und
    dabei bewusst FEHLERFREI bleibt (kein Konsolenfehler, HTTP 200/302).
    '/umleitung' leitet auf '/login' um (Merkmal 1), '/passwortfeld' liefert
    direkt ein sichtbares Passwortfeld (Merkmal 2). Beide Merkmale sind
    unabhaengig, damit ein einzelner Umbau die Pruefung nicht still aushebelt."""
    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/umleitung":
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            body = (_LOGIN if self.path in ("/login", "/passwortfeld")
                    else _CLEAN).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # stumm
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    srv.server_close()


def test_missing_playwright_blocks_instead_of_skipping(monkeypatch, local_site):
    """AC-8, dritter Fall: fehlt Playwright, ist der Nachweis NICHT erbringbar →
    blocken. Kein Skip, kein stilles 0. Der ImportError ist echt (None in
    sys.modules laesst den Import scheitern) und durchlaeuft den echten Zweig."""
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    g = _gate_mod()
    rc, messages = g.check_pages(local_site, ["/"], {})
    assert rc != 0, f"fehlendes Playwright blieb folgenlos: {messages}"
    assert "playwright" in " ".join(messages).lower(), f"Grund unklar: {messages}"
    creds = {"GZ_VALIDATION_URL": local_site, "GZ_AUTH_USER": "u", "GZ_AUTH_PASS": "p",
             "GZ_VALIDATOR_USER": "u", "GZ_VALIDATOR_PASS": "p"}
    assert g.gate("frontend-only", creds) != 0, "Gate muss blocken statt zu ueberspringen"


def test_ambiguous_verdict_is_gated_like_verified(tmp_path, hostile):
    """Spec-Festlegung "Auch bei AMBIGUOUS? Ja": ein AMBIGUOUS-Verdict wird
    abgelegt und kann spaeter als Vorgaenger dienen — die Luecke waere sonst
    trivial zu nutzen. Also greift das Gate hier genauso."""
    e2e_path = tmp_path / "attestation.json"
    rc = sg.write_verdict("AMBIGUOUS: unklar und unbelegt", tmp_path / "findings.json",
                          e2e_path=e2e_path, scope_override="frontend-only")
    assert rc == 1, "AMBIGUOUS muss bei Frontend-Scope gegated werden wie VERIFIED"
    assert not e2e_path.exists(), "Attestation entstand trotz nicht bestandenem Browserlauf"


@pytest.mark.parametrize("path", ["/umleitung", "/passwortfeld"])
def test_unauthenticated_page_without_console_error_is_not_a_passed_page(
    unauth_site, path
):
    """AC-6 in der Kern-Schicht: fehlerfrei ist NICHT dasselbe wie bestanden.

    Die Seite laedt mit HTTP 200 und wirft keinerlei Konsolenfehler — sie ist
    nur nicht die angemeldete Zielseite. Genau die Falle aus #1307, bei der ein
    Gate mit einem Foto der Anmeldemaske bestand."""
    pytest.importorskip("playwright.sync_api")
    rc, messages = _gate_mod().check_pages(unauth_site, [path], {})
    joined = " ".join(messages).lower()

    assert rc != 0, (
        f"{path}: eine fehlerfreie Anmeldemaske wurde als bestandene Kernseite "
        f"gewertet (Meldungen: {messages})"
    )
    assert "konsolenfehler" not in joined, (
        f"{path}: die Sperre kam von einem Konsolenfehler statt von der "
        f"Anmelde-Pruefung — dann belegt der Test AC-6 nicht: {messages}"
    )
    assert any(w in joined for w in ("anmeld", "login", "passwort")), (
        f"{path}: Meldung nennt den Anmeldegrund nicht: {messages}"
    )


# ---------------------------------------------------------------------------
# Feldbefund 2026-08-08: das ausgelieferte Gate blockierte JEDE
# Frontend-Auslieferung. Ursache: es nahm die Anwendungs-Anmeldedaten aus der
# .env des Arbeitsordners. Staging hat eigene — gleicher Benutzername, anderes
# Passwort (gemessen an POST /api/auth/login: lokal 401 "invalid credentials",
# Staging-.env 200 mit gz_session-Cookie). Fuer die gesamte Kern-Suite war das
# unsichtbar, weil dort nie echte Zugangsdaten im Spiel sind.
# ---------------------------------------------------------------------------

def test_app_credentials_for_staging_come_from_the_staging_env(tmp_path, monkeypatch):
    """Zeigt der Lauf auf Staging, muessen die ANWENDUNGS-Daten aus der
    Staging-.env stammen — die nginx-Schranke weiterhin aus validator.env.

    Echte Dateien, echte Funktion. Isoliert wird nur der Prozess-Umgebungsblock,
    damit der Lauf keine Variablen in andere Tests traegt."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "validator.env").write_text(
        "GZ_VALIDATION_URL=https://staging.gregor20.henemm.com\n"
        "GZ_VALIDATOR_USER=nginx-benutzer\nGZ_VALIDATOR_PASS=nginx-geheim\n")
    (tmp_path / ".env").write_text(
        "GZ_AUTH_USER=gast\nGZ_AUTH_PASS=passwort-arbeitsordner\n")
    staging_env = tmp_path / "staging.env"
    staging_env.write_text("GZ_AUTH_USER=gast\nGZ_AUTH_PASS=passwort-staging\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "environ", {})  # Wegwerf-Umgebung, kein Leck
    g = _gate_mod()
    monkeypatch.setattr(g, "STAGING_ENV_PATH", staging_env)
    g.load_validator_env()

    assert os.environ.get("GZ_AUTH_PASS") == "passwort-staging", (
        "Das Gate meldet sich bei Staging mit dem Passwort des Arbeitsordners an "
        f"(bekam {os.environ.get('GZ_AUTH_PASS')!r}). Gemessen 2026-08-08 "
        "antwortet die Anwendung darauf mit 401 — das Gate blockiert dann JEDE "
        "Frontend-Auslieferung."
    )
    assert os.environ.get("GZ_VALIDATOR_USER") == "nginx-benutzer", (
        "die vorgeschaltete nginx-Schranke muss weiter aus .claude/validator.env kommen"
    )

    # Die Wahl muss ueberschreibbar bleiben: gesetzte Variablen behalten Vorrang.
    monkeypatch.setattr(os, "environ", {"GZ_AUTH_PASS": "vom-aufrufer"})
    g.load_validator_env()
    assert os.environ.get("GZ_AUTH_PASS") == "vom-aufrufer", (
        "eine bereits gesetzte Umgebungsvariable wurde ueberschrieben"
    )


_LOGINFORM = ("<!doctype html><html><body><form method='post' action='/login'>"
              "<input name='username'><input type='password' name='password'>"
              "<button type='submit'>Anmelden</button></form></body></html>")


@pytest.fixture
def rejecting_site():
    """Lokale Anwendung, die die Anmeldung ABLEHNT — nachgebaut nach dem am
    2026-08-08 an Staging gemessenen Verhalten: das Formular auf '/login'
    schickt per POST an '/login' und bekommt 401 (SvelteKit-Form-Action, NICHT
    '/api/auth/login' — ein fest verdrahteter Endpunkt fand hier still nichts)."""
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body):
            b = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_POST(self):  # noqa: N802
            self._send(401, _LOGINFORM)

        def do_GET(self):  # noqa: N802
            self._send(200, _LOGINFORM if self.path == "/login" else _CLEAN)

        def log_message(self, *a):  # stumm
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    srv.server_close()


def test_rejected_login_is_named_as_rejection_not_as_redirect(rejecting_site):
    """AC-6 unterscheidbar: "Anmeldung abgelehnt" ist etwas anderes als "steht
    noch auf der Anmeldemaske". Ohne diesen Unterschied gilt ein generell
    kaputter Anmeldeweg als Beleg dafuer, dass ein falsches Passwort erkannt
    wurde — genau dieser Fehlschluss ist am 2026-08-08 passiert.

    Die Zielseite '/trips' ist hier bewusst sauber und ohne Passwortfeld: die
    Sperre kann also NUR aus der Ablehnungs-Erkennung kommen."""
    pytest.importorskip("playwright.sync_api")
    env = {"GZ_AUTH_USER": "gast", "GZ_AUTH_PASS": "falsch"}
    rc, messages = _gate_mod().check_pages(rejecting_site, ["/trips"], env)
    joined = " ".join(messages).lower()

    assert rc != 0, f"abgelehnte Anmeldung blieb folgenlos: {messages}"
    assert "abgelehnt" in joined, f"Meldung nennt die Ablehnung nicht: {messages}"
    assert "401" in joined, f"Meldung nennt den HTTP-Status nicht: {messages}"
    assert "anmeldemaske" not in joined, (
        f"die Sperre kam aus der Rueckleitungs-Pruefung statt aus der Ablehnung — "
        f"dann sind die beiden Faelle weiterhin nicht unterscheidbar: {messages}"
    )
