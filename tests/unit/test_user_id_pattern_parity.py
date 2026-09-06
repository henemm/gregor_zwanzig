# doc-compliance-test
"""user_id-Muster-Paritaet Python <-> Go (#1364).

Das Zulassungsmuster fuer Nutzer-Kennungen existiert zweimal: in der
kanonischen Go-Quelle (internal/store/pathsafe.go, erzwingt es beim
Anlegen UND beim Pfadbau — seit #2140; internal/handler/passkey.go haengt
nur noch daran) und im Python-Core (app.loader.VALID_USER_ID_RE, erzwingt
es beim Pfadbau). Driften beide, sperrt Python real registrierte Nutzer
aus oder laesst Kennungen durch, die Go nie vergeben haette.

Strukturregel auf Quelltext-als-Daten: das Go-Muster ist aus Python nur
als Text erreichbar (kein Go-Toolchain-Aufruf im Kernlauf) — gleiche
Werkzeug-Klasse wie test_egress_inventory_drift.py (#1337) und
test_mail_recipient_parity.py (#1412); daher ``# doc-compliance-test``.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.loader import VALID_USER_ID_RE

_REPO = Path(__file__).resolve().parents[2]
_PASSKEY_GO = _REPO / "internal" / "store" / "pathsafe.go"


def test_python_muster_ist_deckungsgleich_mit_go():
    """Given das kanonische Go-Muster in store/pathsafe.go / When das Python-
    Muster daneben gelegt wird / Then sind beide identisch (#1364:
    'beide Stellen gehoeren zusammen')."""
    go_src = _PASSKEY_GO.read_text(encoding="utf-8")
    m = re.search(
        r"ValidUserIDRe\s*=\s*regexp\.MustCompile\(`([^`]+)`\)", go_src
    )
    assert m, "ValidUserIDRe nicht in pathsafe.go gefunden — Muster verschoben?"
    assert VALID_USER_ID_RE.pattern == m.group(1)
