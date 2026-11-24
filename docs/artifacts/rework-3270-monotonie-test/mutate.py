"""Mutationsnachweis #3270: String-Ersetzung mit externer Sicherungskopie,
Wiederherstellung per Pruefsumme belegt (nie git checkout/stash/reset).

Aufruf aus dem Repo-Wurzelverzeichnis: python3 <dieses Skript> <ausgabe.txt>
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

SEG = "src/services/trip_segments.py"
TEST = "tests/tdd/test_gehzeit_etappenregel.py"
ALT = "        if span <= 0:  # nicht strikt monoton\n            return None"
MUT = {
    "G1b-monotonie (AC-3: Pruefung abgeschaltet)": ALT.replace("span <= 0", "False"),
    "G1b-schwach (AC-4: span < 0 statt span <= 0)": ALT.replace("span <= 0", "span < 0"),
}


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run():
    r = subprocess.run(
        ["uv", "run", "pytest", "-v", "--tb=short", "-o", "addopts=",
         "-p", "no:cacheprovider", TEST],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return r.returncode, r.stdout + r.stderr


def main():
    backup = os.path.join(tempfile.mkdtemp(prefix="mut3270-"), "trip_segments.py")
    shutil.copy2(SEG, backup)
    orig = sha(SEG)
    out = [f"# Mutationsnachweis #3270\nPruefsumme Original: {orig}\n"]
    rc, text = run()
    out.append(f"## Unveraenderter Code: exit={rc}\n{text}")
    for name, neu in MUT.items():
        try:
            with open(SEG) as f:
                src = f.read()
            assert src.count(ALT) == 1, "Muster nicht eindeutig"
            with open(SEG, "w") as f:
                f.write(src.replace(ALT, neu))
            rc, text = run()
        finally:
            shutil.copyfile(backup, SEG)
        out.append(f"## Mutation {name}: exit={rc}\n{text}")
        out.append(f"Pruefsumme nach Wiederherstellung: {sha(SEG)} "
                   f"({'identisch' if sha(SEG) == orig else 'ABWEICHUNG'})\n")
    rc, text = run()
    out.append(f"## Nach Wiederherstellung: exit={rc}\n{text}")
    with open(sys.argv[1], "w") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    main()
