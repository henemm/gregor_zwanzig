"""Issue #2283 AC-6: Abbild der Python-Vorschau-Routen fuer den Go-Waechter.

Spec: docs/specs/modules/shared_preview_tab.md (AC-6)

Der Go-Waechter ``internal/router/preview_proxy_targets_test.go`` prueft, dass
jede im Go-Router registrierte Vorschau-Proxy-Route ein Ziel im Python-Core
hat. Der Go-Testlauf (CI-Job ``go-test``) hat keine Python-Umgebung — er liest
deshalb ein versioniertes Abbild der Routentabelle:
``internal/router/testdata/python_preview_routes.json``.

Dieser Test haelt das Abbild ehrlich: Er vergleicht es mit der **fertig
gebauten Anwendung** (``api.main:app.routes``), nicht mit Quelltext. Weicht es
ab (neue/entfernte Vorschau-Route in Python), wird er rot — dann das Abbild
neu erzeugen::

    uv run python tests/test_vorschau_proxy_ziel_snapshot.py --write

Filter: nur Pfade, die ``preview`` enthalten. So machen fremde, unbeteiligte
Python-Routen paralleler Sitzungen das Abbild nicht staendig ungueltig; zielt
ein Go-Vorschau-Proxy auf einen Pfad ausserhalb des Filters, schlaegt der
Go-Waechter fehl (fail-closed) und der Filter ist zu erweitern.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[1] / "internal" / "router" / "testdata" / "python_preview_routes.json"


def _vorschau_routen() -> list[dict[str, str]]:
    from fastapi.routing import APIRoute

    from api.main import app

    eintraege = set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or "preview" not in route.path:
            continue
        for methode in route.methods:
            if methode == "HEAD":
                continue
            eintraege.add((methode, route.path))
    return [{"method": m, "path": p} for m, p in sorted(eintraege, key=lambda e: (e[1], e[0]))]


def test_abbild_entspricht_der_gebauten_python_app():
    """Das versionierte Abbild ist exakt die Vorschau-Routentabelle der echten App."""
    erwartet = _vorschau_routen()
    assert erwartet, "keine einzige Vorschau-Route in api.main:app gefunden — Filter oder App kaputt"
    assert SNAPSHOT.exists(), f"Abbild fehlt: {SNAPSHOT} — mit --write erzeugen"
    abbild = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert abbild == erwartet, (
        "Abbild der Python-Vorschau-Routen ist veraltet — neu erzeugen mit\n"
        "  uv run python tests/test_vorschau_proxy_ziel_snapshot.py --write\n"
        f"Abbild: {abbild}\nApp:    {erwartet}"
    )


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    if "--write" not in sys.argv:
        print(json.dumps(_vorschau_routen(), indent=2))
        sys.exit(0)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(_vorschau_routen(), indent=2) + "\n", encoding="utf-8")
    print(f"geschrieben: {SNAPSHOT}")
