"""Prototyp: gefilterte Scans, Funde muessen gleich sein."""
import ast, dataclasses, importlib.util, re, sys, time, unicodedata
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(REPO), str(REPO / "src")]
T = REPO / "tests"


def lade(rel):
    spec = importlib.util.spec_from_file_location(Path(rel).stem + "_m", REPO / rel)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def norm(s):
    return s if s.isascii() else unicodedata.normalize("NFKC", s)


class Root:
    def __init__(self, pred):
        self.pred = pred

    def rglob(self, muster):
        return [f for f in T.rglob(muster) if self.pred(norm(f.read_text("utf-8")))]


def mess(name, f):
    t = time.perf_counter()
    r = f()
    print(f"{name:34s} {time.perf_counter()-t:6.1f}s  Funde {len(r)}", flush=True)
    return r


w = lade("tests/tdd/test_fixture_wallclock_ratchet.py")
mess("wallclock direkt (strftime)", lambda: w.scan_wallclock_arrival_fixtures(Root(lambda s: "strftime" in s)))
al = w._ALARMPFADE_INDIREKT
# Modulpfad kann ueber Punkte/Whitespace getrennt sein, der gesuchte Name ist aber EIN Bezeichner-Stueck
mess("wallclock indirekt (Alarmpfad&Stage)", lambda: w.scan_indirekte_wanduhr_fixtures(Root(lambda s: "Stage" in s and any(a in s for a in al))))
g = lade("tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py")
mess("gestellte_uhr", lambda: g.scan_ungestellte_uhr(Root(lambda s: "make_trip" in s and "save_trip" in s)))

h = lade("tests/tdd/test_thunder_scale_local_copy_guard.py")
rx = re.compile(r"#[^\n]*(?:1:1|wortw(?:oe|ö)rt|identische|eingefroren|unver(?:ae|ä)ndert)", re.I)
orig = h.scan_source
n = [0]


def scan_source(source, filename, spec, *, rules=("A", "B", "C"), canonical_order=None):
    if rules == ("D",) and not rx.search(source):
        return []
    n[0] += 1
    return orig(source, filename, spec, rules=rules, canonical_order=canonical_order)


h.scan_source = scan_source
mess("thunder tests/ nur D, Kommentarfilter", lambda: h.scan_tree([T], h._thunder_spec(), rules=("D",)))
print("   geparst:", n[0])
n[0] = 0
h.scan_source = orig

r = lade("tests/tdd/test_repo_path_hardcoding_ratchet.py")
t = time.perf_counter()
baeume = 0
co = [0.0]
src = __import__("inspect").getsource(r._module_constants)
neu = src.replace("    consts: dict = {}\n", "    consts: dict = {}\n    knoten = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))]\n", 1).replace("for node in ast.walk(tree):", "for node in knoten:", 1)
assert neu != src
exec(neu, r.__dict__)
mess("repo_path (Zuweisungen 1x sammeln)", lambda: r.scan_for_hardcoded_repo_paths(T, REPO))

u = lade("tests/test_test_suite_passes_user_id_explicitly.py")
a, b = u._baue_ziel_register()
ur = re.compile("|".join(sorted(set(a) | set(b))))
mess("user_id (Register)", lambda: (setattr(u, "_TESTS_DIR", Root(lambda s: ur.search(s))), u._sammle_verstoesse())[1])
p = lade("tests/test_trips_pfad_rueckbau.py")
mess("trips_pfad", lambda: [c for f in Root(lambda s: "get_trips_dir" in s).rglob("*.py") for c in p._real_calls_to(ast.parse(f.read_text("utf-8")), "get_trips_dir")])
