"""Die Schreibsperre haelt immer die Datei, die JETZT unter dem Sperrpfad liegt (#2961, F7).

Go raeumt Sperrdateien verwaister Kennungen nach der Freigabe auf (ADR-0083,
Nachtrag 2026-11-13). Wird die Sperrdatei zwischen ``open`` und ``flock``
entfernt oder ersetzt, haelt ein naiver Schreiber einen flock auf einer
geloeschten Inode -- ein zweiter Schreiber legt eine neue Datei an und sperrt
sie gleichzeitig. Das Rennen wird ueber die Testnaht
``file_lock._testnaht_nach_open`` deterministisch zwischen open und flock
ausgeloest; geprueft wird mit einem echten zweiten flock auf den Pfad.
"""
from __future__ import annotations

import fcntl
import os

import pytest

from services import file_lock


def _fremder_versuch_blockiert(lock_pfad) -> bool:
    """Ein zweiter Schreiber oeffnet den Pfad und versucht zu sperren."""
    fd = os.open(lock_pfad, os.O_CREAT | os.O_RDWR, 0o660)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


@pytest.mark.parametrize("art", ["entfernt", "ersetzt"])
def test_sperre_gilt_fuer_die_datei_unter_dem_pfad(tmp_path, monkeypatch, art):
    ziel = tmp_path / "trip.json"
    lock_pfad = file_lock.lock_path_for(ziel)
    aufrufe: list[int] = []

    def _rennen(pfad):
        aufrufe.append(1)
        if len(aufrufe) == 1:  # nur beim ersten Versuch: Go raeumt auf / legt neu an
            os.remove(pfad)
            if art == "ersetzt":
                neu = tmp_path / "neu.lock"
                neu.write_bytes(b"")
                os.replace(neu, pfad)

    monkeypatch.setattr(file_lock, "_testnaht_nach_open", _rennen)
    with file_lock.exclusive_lock(ziel, timeout_s=1.0):
        assert _fremder_versuch_blockiert(lock_pfad), (
            "Ein zweiter Schreiber bekaeme die Sperre parallel -- gehalten wird eine "
            "verwaiste Datei statt der unter dem Pfad."
        )
    assert len(aufrufe) == 2, "nach dem Rennen genau ein neuer Versuch"
    assert not _fremder_versuch_blockiert(lock_pfad), "nach Freigabe wieder frei"


def test_dauerndes_rennen_endet_mit_lock_timeout(tmp_path, monkeypatch):
    ziel = tmp_path / "trip.json"
    monkeypatch.setattr(file_lock, "_testnaht_nach_open", os.remove)
    with pytest.raises(file_lock.LockTimeout):
        with file_lock.exclusive_lock(ziel, timeout_s=0.2):
            pass
