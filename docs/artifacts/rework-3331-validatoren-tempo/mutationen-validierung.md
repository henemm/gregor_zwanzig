# Nachweise aus der Validierung (#3331)

Anlass: die Protokollzeilen S12 und S15 sind abgeschnitten. Verfahren: eine String-Ersetzung, externe Sicherungskopie, sha256 vorher/nachher.

## N-S12 (AC-6, Rueckfall auf subprocess.run) -> ROT

```
ALT:
            raise

    def _starte
NEU:
            return subprocess.run(befehl, capture_output=True, text=True, env=env, cwd=cwd, timeout=timeout)

    def _starte
```

```
E   Failed: DID NOT RAISE ServerFehler
E   Failed: DID NOT RAISE ServerFehler
E   Failed: DID NOT RAISE ServerFehler
E   Failed: DID NOT RAISE ServerFehler
E   Failed: DID NOT RAISE ServerFehler
E   tests.helpers.validator_server.ServerFehler: Server tot: Traceback (most recent call last):
    FileNotFoundError: [Errno 2] No such file or directory: '/private/var/folders/9n/w5wl_q1x7j17v9y0b5nw6vj80000gn/T/pytest-of-hem/pytest-1889/test_ac6_gescheiterte_einricht0/fehlt'
    AssertionError: Kind konnte nicht eingerichtet werden
E   FileNotFoundError: [Errno 2] No such file or directory: PosixPath('/private/var/folders/9n/w5wl_q1x7j17v9y0b5nw6vj80000gn/T/pytest-of-hem/pytest-1889/test_ac6_gescheiterte_einricht0/fehlt')
/opt/homebrew/Cellar/python@3.12/3.12.15/Frameworks/Python.framework/Versions/3.12/lib/python3.12/subprocess.py:1955: FileNotFoundError: [Errno 2] No such file or directory: PosixPath('/private/var/folders/9n/w5wl_q1x7j17v9y0b5nw6vj80000gn/T/pytest-of-hem/pytest-1889/test_ac6_gescheiterte_einricht0/fehlt')
FAILED tests/test_validator_server.py::test_ac6_toter_server_scheitert_laut_und_startet_neu
FAILED tests/test_validator_server.py::test_ac6_ungeeigneter_server_scheitert_laut[ohne-fork]
FAILED tests/test_validator_server.py::test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]
FAILED tests/test_validator_server.py::test_ac6_ungeeigneter_server_scheitert_laut[meldung-nach-eof]
FAILED tests/test_validator_server.py::test_ac6_ungeeigneter_server_scheitert_laut[stirbt-vor-startzeile]
FAILED tests/test_validator_server.py::test_ac6_gescheiterte_einrichtung_des_kindes_ist_kein_ergebnis
6 failed, 24 deselected in 9.24s
exit=1
sha256 vorher/nachher 564312edf3fec02b / 564312edf3fec02b
```

## N-S15 (AC-7, direkter Aufruf im Server statt os.fork) -> ROT

```
ALT:
    hier, dort = socket.socketpair()
NEU:
    import io
    o, e = io.StringIO(), io.StringIO()
    os.environ.clear()
    os.environ.update(anfrage["env"])
    sys.argv = [anfrage["skript"], *anfrage["args"]]
    antworte(pid=os.getpid())
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        code = _fuehre_aus(anfrage["skript"])
    antworte(returncode=code, stdout=o.getvalue(), stderr=e.getvalue())
    return
    hier, dort = socket.socketpair()
```

```
E   AssertionError: assert ['False', 'Tr...True', 'True'] == ['False', 'Fa...lse', 'False']
/Users/hem/Developer/gregor_zwanzig/.claude/worktrees/rework-3279-testsuite-tempo/tests/test_validator_server.py:273: AssertionError: assert ['False', 'Tr...True', 'True'] == ['False', 'Fa...lse', 'False']
FAILED tests/test_validator_server.py::test_ac7_zweiter_lauf_sieht_keinen_zustand_des_ersten
1 failed, 29 deselected in 4.06s
exit=1
sha256 vorher/nachher 564312edf3fec02b / 564312edf3fec02b
```
