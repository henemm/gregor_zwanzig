"""Absicherung des vorgewaermten Fork-Servers der Mail-Validatoren (Issue #3331).

SPEC: docs/specs/modules/rework_3331_validatoren_tempo.md (AC-1 bis AC-10).
Der Server laeuft echt (kein Mock): Hilfs-Skripte melden, was im Kind ankommt;
Prozesse werden ueber ``ps`` gesucht. Kern-Schicht, ohne Netz.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import yaml

from tests.helpers import validator_server as vs
from tests.helpers.mail_lang_fixture import validator_lauf
from tests.tdd import test_einstellung_gleich_mail_validatoren as ziel

REPO = Path(__file__).resolve().parents[1]

#: Meldet pid/ppid -- im echten Prozess ist der Vater der Test, sonst der Server.
PROBE = "import json, os\nprint(json.dumps([os.getpid(), os.getppid()]))\n"
#: Startet einen schlafenden Enkel, meldet beide pids (atomar) und haengt.
HAENGT = """
import os, subprocess, sys, time
enkel = subprocess.Popen(["sleep", "60"])
with open(sys.argv[1] + ".tmp", "w") as f:
    f.write(f"{os.getpid()} {enkel.pid}")
os.rename(sys.argv[1] + ".tmp", sys.argv[1])
time.sleep(60)
"""
#: Vorspann: der Server stirbt, sobald sein Kind eingerichtet ist und auf das Startzeichen wartet.
STIRBT = """
import os, select, signal, socket
fork, socketpair, paar = os.fork, socket.socketpair, []
def sterbend():
    pid = fork()
    if pid == 0:
        signal.alarm(45)  # kein Rest, falls das Kind faelschlich ewig wartet
        return pid
    with open(f"{__file__}.{pid}.pid", "w") as f:
        f.write(str(pid))
    select.select([paar[0]], [], [], 10)
    os.kill(os.getpid(), signal.SIGKILL)
socket.socketpair = lambda: paar.extend(socketpair()) or paar
os.fork = sterbend
"""


@pytest.fixture
def klient():
    k = vs.Klient()
    yield k
    k.verwerfen()


def _skript(tmp_path: Path, text: str, name: str = "skript.py") -> Path:
    pfad = tmp_path / name
    pfad.write_text(text, encoding="utf-8")
    return pfad


def _lauf(k, tmp_path: Path, text: str, *args: str, timeout: float = 20, env=None):
    return k.lauf(_skript(tmp_path, text), list(args), env=dict(os.environ) if env is None else env,
                  cwd=str(tmp_path), timeout=timeout)


def _lebt(pid: int) -> bool:
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def _alle_weg(pids, frist: float = 8) -> list[int]:
    """Wartet bis ``frist``; Rueckgabe: noch lebende pids (leer = alles weg)."""
    ende = time.monotonic() + frist
    while (rest := [p for p in pids if _lebt(p)]) and time.monotonic() < ende:
        time.sleep(0.1)
    return rest


def _pids_aus(pfad: Path, frist: float = 10) -> list[int]:
    ende = time.monotonic() + frist
    while not pfad.exists() and time.monotonic() < ende:
        time.sleep(0.05)
    return [int(p) for p in pfad.read_text().split()]


def _fall(monkeypatch, tmp_path, validator, rot):
    if validator == ziel.TRIP:
        daten = ziel._trip_daten(ziel._TRIP_FOLGE)
        eml, konfig = ziel._trip_eml(monkeypatch, daten), ziel._konfig(tmp_path, "trip", daten)
        a, b = ">Gust</th>", ">Temp</th>"
    else:
        preset = ziel._orte_preset()
        eml, konfig = ziel._orte_eml(monkeypatch, preset), ziel._orte_konfig(tmp_path, preset)
        a, b = "Kufstein", "Innsbruck"
    if rot:
        eml = ziel._aendere(eml, html=lambda h: ziel._tausche(h, a, b))
    return eml, konfig


def _neue_logs(log_dir: Path, bekannt: set) -> list[dict]:
    logs = []
    for pfad in sorted(set(log_dir.glob("*.yaml")) - bekannt):
        daten = yaml.safe_load(pfad.read_text())
        assert daten.pop("validated_at"), pfad
        logs.append({**daten, "datei": re.sub(r"^[\d_]+", "", pfad.name)})
    return logs


@pytest.mark.timeout(60)
@pytest.mark.parametrize("rot", [False, True])
@pytest.mark.parametrize("validator", [ziel.TRIP, ziel.ORTE])
def test_ac1_prozess_und_server_gleich(monkeypatch, tmp_path, validator, rot):
    eml, konfig = _fall(monkeypatch, tmp_path, validator, rot)
    ergebnisse, bekannt = [], set()
    for im_server in (False, True):
        lauf, log_dir = validator_lauf(tmp_path, validator, eml, "--konfig", konfig, im_server=im_server)
        ergebnisse.append((lauf.returncode, lauf.stdout, lauf.stderr, _neue_logs(log_dir, bekannt)))
        bekannt = set(log_dir.glob("*.yaml"))
    prozess, server = ergebnisse
    assert prozess[0] == int(rot) and len(prozess[3]) == 1, prozess
    assert server == prozess


@pytest.mark.timeout(60)
@pytest.mark.parametrize("validator", [ziel.TRIP, ziel.ORTE])
def test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad(monkeypatch, tmp_path, validator):
    """Verfaelscht wird nur die Hook-KOPIE in ``tmp_path``. ``src`` liegt ueber
    die editierbare Installation sonst immer im Suchpfad -- der Prozesslauf
    muss ihn ausblenden, sonst bemerkt er den fehlenden Eintrag nie."""
    eml, konfig = _fall(monkeypatch, tmp_path, validator, rot=False)
    code, aus = ziel._lauf(tmp_path, validator, eml, "--konfig", konfig, prozess=True)
    assert code == 0, aus
    ersetzt = 0
    for name in (validator, "_soll_aus_konfiguration", "_mail_lang"):
        pfad = tmp_path / "repo" / ".claude" / "hooks" / f"{name}.py"
        neu, n = re.subn(r'sys\.path\.insert\(0, str\((_REPO_SRC|_SRC|[^\n]*"src")\)\)', "pass",
                         pfad.read_text(encoding="utf-8"))
        assert n, f"Testaufbau: kein src-Pfad in {name}"
        pfad.write_text(neu, encoding="utf-8")
        ersetzt += n
    code, aus = ziel._lauf(tmp_path, validator, eml, "--konfig", konfig, prozess=True)
    assert code != 0, f"fehlender src-Pfad unbemerkt ({ersetzt} Stellen entfernt): {aus}"


def test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs(monkeypatch, tmp_path, klient):
    monkeypatch.setenv("GZ_NUR_SERVER", "1")
    monkeypatch.setenv("TZ", "UTC")
    env = {"PATH": os.environ["PATH"], "NUR_LAUF": "ja", "TZ": "Pacific/Kiritimati", "TMPDIR": str(tmp_path)}
    text = ("import json, os, sys, tempfile, time\n"
            "print(json.dumps([dict(os.environ), time.timezone, os.getcwd(), sys.argv, sys.path[0],\n"
            "                  tempfile.gettempdir(), sys.stdin.read()]))\n")
    lauf = _lauf(klient, tmp_path, text, "a", "b c", env=env)
    assert lauf.returncode == 0, lauf.stderr
    umgebung, zone, cwd, argv, pfad0, tmp, stdin = json.loads(lauf.stdout)
    assert umgebung == env
    assert zone == -14 * 3600
    assert os.path.realpath(cwd) == os.path.realpath(tmp_path)
    assert argv == [str(tmp_path / "skript.py"), "a", "b c"]
    assert (pfad0, tmp, stdin) == (str(tmp_path), str(tmp_path), "")
    assert klient._kind is klient._kennung is None, "spaeteres Verwerfen traefe eine fremde Prozessgruppe"


def test_ac4_frist_beendet_kind_und_enkel(tmp_path, klient):
    with pytest.raises(subprocess.TimeoutExpired):
        _lauf(klient, tmp_path, HAENGT, str(tmp_path / "pids"), timeout=2)
    pids = _pids_aus(tmp_path / "pids", frist=0)
    assert len(pids) == 2 and _alle_weg(pids) == []
    assert _lauf(klient, tmp_path, "print('danach')").stdout == "danach\n"


class _Abbruch(BaseException):
    """Wie pytest-timeout: kein ``Exception``-Nachfahre, mitten im Warten."""


@pytest.mark.parametrize("wo", ["vor-startzeile", "vor-ergebnis"])
def test_ac5_abbruch_im_warten_vertauscht_keine_antwort(tmp_path, klient, wo):
    assert _lauf(klient, tmp_path, "print('vorher')").stdout == "vorher\n"
    alt = klient.pid
    pids: list[int] = []

    def ausloesen():
        pids.extend(_pids_aus(tmp_path / "pids"))
        os.kill(os.getpid(), signal.SIGUSR1)

    def wirf(*_):
        raise _Abbruch

    def liest_nicht(*_):
        del klient._lies  # verwerfen liest die Startzeile wieder echt
        time.sleep(20)

    if wo == "vor-startzeile":
        klient._lies = liest_nicht
    vorher = signal.signal(signal.SIGUSR1, wirf)
    faden = threading.Thread(target=ausloesen)
    faden.start()
    try:
        with pytest.raises(_Abbruch):
            _lauf(klient, tmp_path, HAENGT, str(tmp_path / "pids"))
    finally:
        faden.join()
        signal.signal(signal.SIGUSR1, vorher)
    assert len(pids) == 2 and _alle_weg([*pids, alt]) == []
    lauf = _lauf(klient, tmp_path, "print('danach'); raise SystemExit(7)")
    assert (lauf.returncode, lauf.stdout) == (7, "danach\n")
    assert klient.pid != alt


@pytest.mark.parametrize("fremd_ab", [0, 1], ids=["startzeile", "ergebnis"])
def test_ac5_fremde_kennung_scheitert_laut(tmp_path, klient, fremd_ab):
    """Ersatz-Server, der Zeilen eines anderen Laufs liefert (pid unbelegt)."""
    klient.server_skript = _skript(tmp_path, f"""
import json, sys
for zeile in sys.stdin:
    echt = json.loads(zeile)["kennung"]
    teile = [{{"pid": 2**30}}, {{"returncode": 0, "stdout": "alt", "stderr": ""}}]
    for i, teil in enumerate(teile):
        print(json.dumps({{**teil, "kennung": "fremd" if i >= {fremd_ab} else echt}}), flush=True)
""", "server.py")
    with pytest.raises(vs.ServerFehler, match="(?i)kennung"):
        _lauf(klient, tmp_path, PROBE)


def test_ac6_toter_server_scheitert_laut_und_startet_neu(tmp_path, klient):
    _lauf(klient, tmp_path, PROBE)
    alt = klient.pid
    os.kill(alt, signal.SIGKILL)
    assert _alle_weg([alt]) == []
    with pytest.raises(vs.ServerFehler):
        _lauf(klient, tmp_path, PROBE)
    _kind, vater = json.loads(_lauf(klient, tmp_path, PROBE).stdout)
    assert vater == klient.pid != alt


@pytest.mark.parametrize("vorspann,meldung,kinder", [
    ("import os; del os.fork", "fork", 0),
    ("import threading, time; threading.Thread(target=time.sleep, args=(60,), daemon=True).start()", "Thread", 0),
    ("import os, sys, time; os.close(1); time.sleep(0.5); sys.exit('spaet')", "Server tot: spaet", 0),
    (STIRBT, "Server tot", 1),
], ids=["ohne-fork", "zusatz-thread", "meldung-nach-eof", "stirbt-vor-startzeile"])
def test_ac6_ungeeigneter_server_scheitert_laut(tmp_path, klient, vorspann, meldung, kinder):
    klient.server_skript = _skript(tmp_path, f"{vorspann}\nimport runpy\n"
                     f"runpy.run_path({str(vs.SERVER_SKRIPT)!r}, run_name='__main__')\n", "server.py")
    with pytest.raises(vs.ServerFehler, match=f"(?i){meldung}"):
        _lauf(klient, tmp_path, "import sys; open(sys.argv[1], 'w')", str(tmp_path / "gelaufen"))
    pids = [int(p.read_text()) for p in tmp_path.glob("*.pid")]
    assert len(pids) == kinder and _alle_weg(pids) == []
    assert not (tmp_path / "gelaufen").exists()


def test_ac6_gescheiterte_einrichtung_des_kindes_ist_kein_ergebnis(tmp_path, klient):
    with pytest.raises(vs.ServerFehler, match="(?s)FileNotFoundError.*Kind konnte nicht eingerichtet"):
        klient.lauf(_skript(tmp_path, PROBE), [], env=dict(os.environ), cwd=tmp_path / "fehlt", timeout=20)


def test_ac7_zweiter_lauf_sieht_keinen_zustand_des_ersten(tmp_path, klient):
    setzen = ("import os, sys, i18n\nos.environ['GZ_MARKE'] = '1'\nsys.modules['gz_marke'] = sys\n"
              "i18n.catalog.get_catalog().texte['de']['gz.marke'] = 'x'\nsys.path.append('/gz-marke')\n")
    melden = ("import os, sys, i18n\nprint('GZ_MARKE' in os.environ, 'gz_marke' in sys.modules,\n"
              "      'gz.marke' in i18n.catalog.get_catalog().texte['de'], '/gz-marke' in sys.path)\n")
    erster = _lauf(klient, tmp_path, setzen + melden)
    assert erster.stdout.split() == ["True"] * 4, erster.stderr
    server = klient.pid
    assert _lauf(klient, tmp_path, melden).stdout.split() == ["False"] * 4
    assert klient.pid == server, "beide Laeufe muessen im selben Server stattfinden"


@pytest.mark.parametrize("ende", [
    "raise SystemExit(3)", "raise SystemExit(None)", "raise SystemExit('Meldung')",
    "def f():\n    raise ValueError('kaputt')\nf()", "import os; os.kill(os.getpid(), 15)",
], ids=["zahl", "none", "text", "ausnahme", "signal"])
def test_ac8_exit_regeln_wie_im_echten_prozess(tmp_path, klient, ende):
    text = f"import sys\nprint('Ausgabe', sys.path)\n{ende}\n"
    server = _lauf(klient, tmp_path, text)
    prozess = subprocess.run([sys.executable, str(tmp_path / "skript.py")], capture_output=True,
                             text=True, cwd=tmp_path)
    assert (server.returncode, server.stdout, server.stderr) == \
        (prozess.returncode, prozess.stdout, prozess.stderr)


def _mit_probe(tmp_path: Path) -> Path:
    hooks = tmp_path / "repo" / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    _skript(hooks, PROBE, "probe.py")
    return tmp_path


def test_ac9_ohne_opt_in_echter_prozess(tmp_path):
    lauf, _ = validator_lauf(_mit_probe(tmp_path), "probe", b"")
    assert json.loads(lauf.stdout)[1] == os.getpid()
    lauf, _ = validator_lauf(tmp_path, "probe", b"", im_server=True)
    assert json.loads(lauf.stdout)[1] == vs.GEMEINSAM.pid != os.getpid()


def test_ac9_zieldatei_schaltet_ein_und_kann_prozess(tmp_path):
    _mit_probe(tmp_path)
    assert json.loads(ziel._lauf(tmp_path, "probe", b"", prozess=True)[1])[1] == os.getpid()
    assert json.loads(ziel._lauf(tmp_path, "probe", b"")[1])[1] == vs.GEMEINSAM.pid


@pytest.mark.parametrize("art", ["normal", "kill", "kill-mit-kind"])
def test_ac10_server_verschwindet_mit_dem_worker(tmp_path, art):
    kurz, haengt = _skript(tmp_path, PROBE, "kurz.py"), _skript(tmp_path, HAENGT, "haengt.py")
    worker = _skript(tmp_path, f"""
import os, sys, time
sys.path.insert(0, {str(REPO)!r})
from tests.helpers.validator_server import GEMEINSAM as k
opt = dict(env=dict(os.environ), cwd={str(tmp_path)!r})
k.lauf({str(kurz)!r}, [], **opt)
print(k.pid, flush=True)
if {art!r} == "kill-mit-kind":
    k.lauf({str(haengt)!r}, [{str(tmp_path / "pids")!r}], timeout=3, **opt)
elif {art!r} == "kill":
    time.sleep(60)
""", "worker.py")
    p = subprocess.Popen([sys.executable, str(worker)], stdout=subprocess.PIPE, text=True, cwd=REPO)
    try:
        pids = [int(p.stdout.readline())]
        assert art == "normal" or _lebt(pids[0])
        if art == "kill-mit-kind":
            pids += _pids_aus(tmp_path / "pids")
    finally:
        if art != "normal":
            p.kill()
        p.wait(timeout=10)
        p.stdout.close()
    assert _alle_weg(pids, frist=12) == []


def test_ac10_browser_weg_nach_frist(tmp_path, klient):
    """Echter Chromium: Treiber und Browser sind Enkel des Kindes."""
    text = """
import os, subprocess, sys, time
from playwright.sync_api import sync_playwright
browser = sync_playwright().start().chromium.launch(headless=True)
zeilen = subprocess.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True).stdout.split("\\n")
paare = [tuple(map(int, z.split())) for z in zeilen if z.strip()]
baum = [os.getpid()]
for pid in baum:
    baum += [p for p, v in paare if v == pid]
with open(sys.argv[1], "w") as f:
    f.write(" ".join(map(str, baum)))
time.sleep(60)
"""
    with pytest.raises(subprocess.TimeoutExpired):
        _lauf(klient, tmp_path, text, str(tmp_path / "pids"), timeout=8)
    pids = _pids_aus(tmp_path / "pids", frist=0)
    assert len(pids) >= 3, f"Testaufbau: Kind, Treiber und Browser erwartet, gefunden {pids}"
    assert _alle_weg(pids) == []
