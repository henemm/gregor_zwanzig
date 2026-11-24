"""Laufzeit je Scanner: gesamt, davon ast.parse. Plus: Baeume halten vs. verwerfen."""
import ast, gc, importlib.util, sys, time
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(REPO), str(REPO / "src")]
T = REPO / "tests"
_parse = ast.parse
acc = [0.0, 0]


def parse(*a, **k):
    t = time.perf_counter()
    try:
        return _parse(*a, **k)
    finally:
        acc[0] += time.perf_counter() - t
        acc[1] += 1


ast.parse = parse


def lade(rel):
    spec = importlib.util.spec_from_file_location(Path(rel).stem + "_m", REPO / rel)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def mess(name, f):
    acc[:] = [0.0, 0]
    gc.collect()
    t = time.perf_counter()
    r = f()
    g = time.perf_counter() - t
    print(f"{name:32s} gesamt {g:6.1f}s  parse {acc[0]:6.1f}s ({acc[1]})  Rest {g-acc[0]:6.1f}s  Funde {len(r)}", flush=True)


w = lade("tests/tdd/test_fixture_wallclock_ratchet.py")
mess("wallclock direkt", lambda: w.scan_wallclock_arrival_fixtures(T))
mess("wallclock indirekt", lambda: w.scan_indirekte_wanduhr_fixtures(T))
g = lade("tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py")
mess("gestellte_uhr", lambda: g.scan_ungestellte_uhr(T))
h = lade("tests/tdd/test_thunder_scale_local_copy_guard.py")
sp = h._thunder_spec()
mess("thunder tests/ A+D", lambda: h.scan_tree([T], sp, rules=("A", "D")))
mess("thunder src+api A+B+C", lambda: h.scan_tree([h.SRC_ROOT, h.API_ROOT], sp))
r = lade("tests/tdd/test_repo_path_hardcoding_ratchet.py")
mess("repo_path", lambda: r.scan_for_hardcoded_repo_paths(T, REPO))
c = [0.0]
orig = r._module_constants
def mc(tree):
    t = time.perf_counter()
    try:
        return orig(tree)
    finally:
        c[0] += time.perf_counter() - t
r._module_constants = mc
r.scan_for_hardcoded_repo_paths(T, REPO)
print("   davon _module_constants", round(c[0], 1))
u = lade("tests/test_test_suite_passes_user_id_explicitly.py")
mess("user_id", lambda: u._sammle_verstoesse())
p = lade("tests/test_trips_pfad_rueckbau.py")
mess("trips_pfad", lambda: [c for f in sorted(T.rglob("*.py")) for c in p._real_calls_to(ast.parse(f.read_text("utf-8")), "get_trips_dir")])
mess("Baeume HALTEN, gc an", lambda: [ast.parse(f.read_text("utf-8")) for f in sorted(T.rglob("*.py"))])
gc.disable()
mess("Baeume HALTEN, gc aus", lambda: [ast.parse(f.read_text("utf-8")) for f in sorted(T.rglob("*.py"))])
