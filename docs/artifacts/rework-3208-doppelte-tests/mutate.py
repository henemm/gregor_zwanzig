"""Mutationsnachweis #3208: String-Ersetzung mit externer Sicherungskopie,
Wiederherstellung aus der Sicherung (nie git checkout/stash/reset).

Aufruf: python3 mutate.py <phase:vorher|nachher> <ausgabe.txt> [mutation-id ...]
"""
import hashlib, os, re, shutil, subprocess, sys, tempfile

ROOT = "/home/hem/gregor_zwanzig/.claude/worktrees/inherited-meandering-tome"
# Sicherungskopien AUSSERHALB des Repos (mkdtemp: 0700, nicht weltlesbar)
BACKUP = os.environ.get("MUT_BACKUP") or tempfile.mkdtemp(prefix="mut3208-")

G1_VORHER = [
    "tests/tdd/test_gehzeit_etappenregel.py",
    "tests/tdd/test_gehzeit_folgt_wegstrecke.py",
    "tests/tdd/test_issue_802_fahrrad_segment_zeit.py",
    "tests/test_3196_trip_tempo_dav.py",
    "tests/test_3197_tempo_je_etappe.py",
]
G1_NACHHER = [f for f in G1_VORHER if "wegstrecke" not in f]
G3 = [
    "tests/tdd/test_3099_sms_resolver.py",
    "tests/tdd/test_3100_premium_sms_fallliste.py",
]

NAI = "src/core/naismith.py"
SEG = "src/services/trip_segments.py"
TR = "src/output/renderers/trip_report.py"
CAT = "src/app/metric_catalog.py"

MUT = {
    "G1a": ("gemessene Strecke ignoriert (immer Luftlinie)", "G1", [
        (NAI, "            if measured is not None:\n                dist = measured[i] - measured[i - 1]",
              "            if False:\n                dist = measured[i] - measured[i - 1]"),
    ]),
    "G1b-abschnitt": ("Rueckfall je Abschnitt statt je Etappe (Luecke/Fall entwertet nur das Paar)", "G1", [
        (NAI, "            if measured is not None:\n                dist = measured[i] - measured[i - 1]\n            else:",
              "            _a = getattr(prev, 'distance_from_start_km', None)\n"
              "            _b = getattr(wp, 'distance_from_start_km', None)\n"
              "            if _a is not None and _b is not None and _b > _a:\n"
              "                dist = _b - _a\n"
              "            elif measured is not None:\n                dist = measured[i] - measured[i - 1]\n            else:"),
    ]),
    "G1b-monotonie": ("Monotonie-Pruefung aus (fallende/gleiche Werte gelten als vermessen)", "G1", [
        (SEG, "        if span <= 0:  # nicht strikt monoton\n            return None",
              "        if False:  # nicht strikt monoton\n            return None"),
    ]),
    "G1b-ruckfall-aus": ("Rueckfallregel ganz aus (Monotonie und Plausibilitaet)", "G1", [
        (SEG, "        if span <= 0:  # nicht strikt monoton\n            return None",
              "        if False:  # nicht strikt monoton\n            return None"),
        (SEG, "        if span + _MEASURED_SLACK_KM < luftlinie:\n            return None",
              "        if False:\n            return None"),
    ]),
    "G1c-grundtempo": ("Grundtempo in speeds_for_tempo um 25 % erhoeht", "G1", [
        (NAI, "    return (v, r_auf * f, r_ab * f)", "    return (v * 1.25, r_auf * f, r_ab * f)"),
    ]),
    "G1c-gewicht": ("Gewicht des kleineren Anteils in dav_hours 1/3 statt 1/2", "G1", [
        (NAI, "    return max(t_h, t_v) + min(t_h, t_v) / 2", "    return max(t_h, t_v) + min(t_h, t_v) / 3"),
    ]),
    "G1d": ("Aufstiegsrate zu Fuss 350 statt 300 Hm/h", "G1", [
        (NAI, '    "fuss": (4.0, 300.0, 500.0),', '    "fuss": (4.0, 350.0, 500.0),'),
    ]),
    "G3a": ("Premium-SMS liest die Premium-Liste statt der SMS-Liste", "G3", [
        (TR, "        premium_sms_text = (\n            sms_text if len(sms_text) <= _premium_max",
             "        _p_ids, _p_pos, _p_fmt = sms_rows_to_maps(_channel_view.premium_sms)\n"
             "        _p_specs = [MetricSpec(symbol=sym, enabled=m in _p_ids, position=_p_pos.get(m))\n"
             "                    for m, sym in SMS_SYMBOL_BY_METRIC.items()\n"
             "                    if m not in SMS_NULLFORM_METRIC_IDS and m != 'thunder']\n"
             "        _p_specs += build_extended_metric_specs(_p_ids, _p_pos, _p_fmt)\n"
             "        premium_sms_text = SMSTripFormatter().format_sms(segments, tz=self._tz,\n"
             "            max_length=_premium_max, **{**_sms_kwargs, 'disabled_specs': _p_specs})\n"
             "        _ungenutzt = (\n            sms_text if len(sms_text) <= _premium_max"),
    ]),
    "G3b": ("SMS-Kuerzel Niederschlag 'Q' statt 'R'", "G3", [
        (CAT, "\n\n# Issue #1410: metric_id -> MEHRERE SMS-Kuerzel",
              "\nSMS_SYMBOL_BY_METRIC['precipitation'] = 'Q'\n\n# Issue #1410: metric_id -> MEHRERE SMS-Kuerzel"),
    ]),
}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run(files):
    r = subprocess.run(["uv", "run", "pytest", "-q", "-p", "no:warnings", "-o", "addopts=",
                        "-p", "no:cacheprovider", *files],
                       cwd=ROOT, capture_output=True, text=True)
    out = r.stdout + r.stderr
    failed = sorted(set(re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M)))
    summ = [l for l in out.splitlines() if re.search(r"\d+ (passed|failed|error)", l)]
    return r.returncode, failed, (summ[-1] if summ else out[-400:])


def main():
    phase, out_path, *ids = sys.argv[1:]
    ids = ids or list(MUT)
    os.makedirs(BACKUP, exist_ok=True)
    log = open(out_path, "w")
    w = lambda s: (log.write(s + "\n"), log.flush(), print(s, flush=True))
    w(f"# Mutationsnachweis #3208 -- Phase: {phase}")
    for mid in ids:
        desc, grp, edits = MUT[mid]
        files = G3 if grp == "G3" else (G1_VORHER if phase == "vorher" else G1_NACHHER)
        targets = sorted({e[0] for e in edits})
        orig = {}
        for t in targets:
            src = os.path.join(ROOT, t)
            bak = os.path.join(BACKUP, t.replace("/", "__"))
            shutil.copy2(src, bak)
            orig[t] = sha(src)
        try:
            for t, old, new in edits:
                p = os.path.join(ROOT, t)
                text = open(p).read()
                n = text.count(old)
                assert n == 1, f"{mid}: Muster in {t} {n}x gefunden"
                open(p, "w").write(text.replace(old, new))
            rc, failed, summ = run(files)
        finally:
            for t in targets:
                shutil.copy2(os.path.join(BACKUP, t.replace("/", "__")), os.path.join(ROOT, t))
                assert sha(os.path.join(ROOT, t)) == orig[t], f"Wiederherstellung {t} fehlgeschlagen"
        w(f"\n## {mid}: {desc}")
        w(f"Ziel: {', '.join(targets)} | Testdateien: {' '.join(files)}")
        w(f"Ergebnis mutiert: exit={rc} | {summ}")
        w("ROT (gefangen)" if failed else "GRUEN (NICHT gefangen)")
        for f in failed:
            w(f"  FAILED {f}")
        rc2, failed2, summ2 = run(files)
        w(f"Nach Wiederherstellung aus Sicherung: exit={rc2} | {summ2}")
        assert rc2 == 0, f"{mid}: nach Wiederherstellung nicht gruen: {failed2}"
    log.close()


if __name__ == "__main__":
    main()
