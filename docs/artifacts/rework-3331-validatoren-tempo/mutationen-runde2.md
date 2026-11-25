# Mutationen Runde 2 (Adversary)

Gleiches Verfahren wie Runde 1: eine String-Ersetzung, Original im Speicher und als Kopie im Scratchpad, sha256 vorher/nachher je Lauf, ganze Datei tests/test_validator_server.py mit -n 4 --dist loadgroup. Ausgangs-sha (unmutiert, Stand Runde 2):

```
60d8a171ebbae048 mail_lang_fixture.py
8c61adf971e01e1f test_einstellung_gleich_mail_soll_placements.py
d8db1d2d810fabab test_einstellung_gleich_mail_validatoren.py
a89409f8a3a01129 test_validator_server.py
564312edf3fec02b validator_server.py
```

### S08 (AC-4) -> ROT
- Mutation: os.killpg(pid, signal.SIGKILL) => os.kill(pid, signal.SIGKILL)
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 4 failed, 26 passed, 13 warnings in 35.63s (37s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind], test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-ergebnis], test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-startzeile]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S09 (AC-5) -> ROT
- Mutation: self.verwerfen()
            if isinstance(fehler, TimeoutError): => if isinstance(fehler, TimeoutError):
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 4 failed, 26 passed, 13 warnings in 33.42s (35s)
- Rote Tests: test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-ergebnis], test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-startzeile], test_ac6_toter_server_scheitert_laut_und_startet_neu
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S10 (AC-5) -> ROT
- Mutation: if antwort.get("kennung") != self._kennung: => if False:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 2 failed, 28 passed, 13 warnings in 30.97s (32s)
- Rote Tests: test_ac5_fremde_kennung_scheitert_laut[ergebnis], test_ac5_fremde_kennung_scheitert_laut[startzeile]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S11 (AC-5) -> ROT
- Mutation: _beende_gruppe(self._kind) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 4 failed, 26 passed, 13 warnings in 44.02s (45s)
- Rote Tests: test_ac10_browser_weg_nach_frist, test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-ergebnis], test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-startzeile]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S12 (AC-6) -> ROT
- Mutation: raise subprocess.TimeoutExpired(befehl, timeout) from fehler
            raise => raise subprocess.TimeoutExpired(befehl, timeout) from fehler
            if isin
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 8 failed, 22 passed, 13 warnings in 28.81s (30s)
- Rote Tests: test_ac5_fremde_kennung_scheitert_laut[ergebnis], test_ac5_fremde_kennung_scheitert_laut[startzeile], test_ac6_gescheiterte_einrichtung_des_kindes_ist_kein_ergebnis, test_ac6_toter_server_scheitert_laut_und_startet_neu, test_ac6_ungeeigneter_server_scheitert_laut[meldung-nach-eof], test_ac6_ungeeigneter_server_scheitert_laut[ohne-fork], test_ac6_ungeeigneter_server_scheitert_laut[stirbt-vor-startzeile], test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S14 (AC-6) -> ROT
- Mutation: if threading.active_count() != 1:
        raise SystemExit(f"validator_server: m => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 27.88s (29s)
- Rote Tests: test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S15 (AC-7) -> ROT
- Mutation: def _bediene(anfrage: dict, ein_fd: int, aus, basis: list[str]) -> None:
    def => def _bediene(anfrage: dict, ein_fd: int, aus, basis: list[str]) -> None:
    def
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 16 failed, 14 passed, 13 warnings in 41.25s (42s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind], test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs, test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-ergebnis], test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-startzeile], test_ac6_gescheiterte_einrichtung_des_kindes_ist_kein_ergebnis, test_ac6_toter_server_scheitert_laut_und_startet_neu, test_ac6_ungeeigneter_server_scheitert_laut[stirbt-vor-startzeile], test_ac7_zweiter_lauf_sieht_keinen_zustand_des_ersten, test_ac8_exit_regeln_wie_im_echten_prozess[ausnahme], test_ac8_exit_regeln_wie_im_echten_prozess[none], test_ac8_exit_regeln_wie_im_echten_prozess[signal] (+4 weitere)
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S16 (AC-8) -> ROT
- Mutation: code = ende.code => code = 1 if ende.code is None else ende.code
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 37.77s (39s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[none]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S18 (AC-8) -> ROT
- Mutation: sys.excepthook(type(fehler), fehler.with_traceback(tb), tb) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 28.86s (30s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[ausnahme]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S19 (AC-9) -> ROT
- Mutation: im_server: bool = False => im_server: bool = True
- Datei: tests/helpers/mail_lang_fixture.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 31.99s (33s)
- Rote Tests: test_ac9_ohne_opt_in_echter_prozess
- sha256 vorher/nachher: 60d8a171ebba / 60d8a171ebba -> IDENTISCH

### S20a (AC-10) -> ROT
- Mutation: for zeile in ein:  # bis EOF, auch bei hart beendetem Klienten
        _bediene( => while True:
        zeile = ein.readline()
        if not zeile:
            tim
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 43.93s (45s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S21 (AC-4) -> ROT
- Mutation: os.setsid() => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 5 failed, 25 passed, 13 warnings in 42.19s (43s)
- Rote Tests: test_ac10_browser_weg_nach_frist, test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind], test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-ergebnis], test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-startzeile]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S22 (Haertung) -> ROT
- Mutation: os.dup2(os.open(os.devnull, os.O_RDONLY), 0) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 32.85s (34s)
- Rote Tests: test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S26 (Haertung) -> ROT
- Mutation: tempfile.tempdir = None => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 37.22s (39s)
- Rote Tests: test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S31 (Haertung) -> ROT
- Mutation: sys.path[:] = [os.path.dirname(anfrage["skript"]), *basis] => sys.path[:] = [os.path.dirname(anfrage["skript"]), *sys.path]
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 4 failed, 26 passed, 13 warnings in 35.77s (37s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[ausnahme], test_ac8_exit_regeln_wie_im_echten_prozess[none], test_ac8_exit_regeln_wie_im_echten_prozess[text], test_ac8_exit_regeln_wie_im_echten_prozess[zahl]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S32 (Haertung) -> ROT
- Mutation: basis = sys.path[1:] => basis = sys.path[:]
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 4 failed, 26 passed, 13 warnings in 32.48s (34s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[ausnahme], test_ac8_exit_regeln_wie_im_echten_prozess[none], test_ac8_exit_regeln_wie_im_echten_prozess[text], test_ac8_exit_regeln_wie_im_echten_prozess[zahl]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S33 (AC-8) -> ROT
- Mutation: os.waitstatus_to_exitcode(fertig[1]) => os.WEXITSTATUS(fertig[1])
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 32.11s (33s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[signal]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S35 (AC-5) -> ROT
- Mutation: self._kennung = self._kind = None
            return => return
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 31.54s (33s)
- Rote Tests: test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### S43 (Haertung) -> ROT
- Mutation: except BaseException:
        sys.excepthook(*sys.exc_info())
    finally: => except BaseException:
        pass
    finally:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 33.27s (35s)
- Rote Tests: test_ac6_gescheiterte_einrichtung_des_kindes_ist_kein_ergebnis
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S24a (AC-5/6 Start) -> ROT
- Mutation: if sync.recv(1): => if True:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 27.23s (29s)
- Rote Tests: test_ac6_ungeeigneter_server_scheitert_laut[stirbt-vor-startzeile]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S24b (AC-5/6 Start) -> ROT
- Mutation: assert hier.recv(1), "Kind konnte nicht eingerichtet werden" => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 22.51s (23s)
- Rote Tests: test_ac6_gescheiterte_einrichtung_des_kindes_ist_kein_ergebnis
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S25alle (AC-5/6 Start) -> ROT
- Mutation: for fd in fremde_fds:  # sonst bliebe beim Klienten/Server das EOF aus
          => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 44.08s (45s)
- Rote Tests: test_ac6_ungeeigneter_server_scheitert_laut[stirbt-vor-startzeile]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S25ein_fd (AC-5/6 Start) -> GRUEN
- Mutation: [ein_fd, aus.fileno(), hier.fileno()] => [aus.fileno(), hier.fileno()]
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 30.87s (32s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S25aus (AC-5/6 Start) -> GRUEN
- Mutation: [ein_fd, aus.fileno(), hier.fileno()] => [ein_fd, hier.fileno()]
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 29.58s (31s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S25hier (AC-5/6 Start) -> ROT
- Mutation: [ein_fd, aus.fileno(), hier.fileno()] => [ein_fd, aus.fileno()]
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 30.23s (32s)
- Rote Tests: test_ac6_ungeeigneter_server_scheitert_laut[stirbt-vor-startzeile]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S36 (AC-5) -> ROT
- Mutation: if self._kennung and self._kind is None:
                    with contextlib.sup => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 31.06s (32s)
- Rote Tests: test_ac5_abbruch_im_warten_vertauscht_keine_antwort[vor-startzeile]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-F001 (F001) -> ROT
- Mutation: with contextlib.suppress(subprocess.TimeoutExpired):
                    self._p => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 29.89s (31s)
- Rote Tests: test_ac6_ungeeigneter_server_scheitert_laut[meldung-nach-eof]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-F001b (F001) -> GRUEN
- Mutation: if time.monotonic() >= ende:
                    raise TimeoutError
             => with contextlib
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 29.73s (31s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S20c (AC-10) -> ROT
- Mutation: for zeile in ein:  # bis EOF, auch bei hart beendetem Klienten
        _bediene( => while True:
        zeile = ein.readline()
        if not zeile:
            tim
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 41.04s (42s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S23 (Haertung) -> GRUEN
- Mutation: os.dup2(2, 1)  # nichts ausser dem Protokoll geht an den Klienten => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 32.75s (34s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S27b (Frist) -> GRUEN
- Mutation: START_FRIST = 60.0 => START_FRIST = 3600.0
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 30.13s (31s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S30 (Haertung) -> GRUEN
- Mutation: daten[:select.PIPE_BUF] => daten
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 34.18s (35s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S44 (Haertung) -> GRUEN
- Mutation: code = 1
    try:
        for fd => code = 0
    try:
        for fd
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 30.65s (32s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S49 (AC-5) -> GRUEN
- Mutation: os.urandom(8).hex() => "k"
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 27.49s (29s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S13 (AC-6) -> GRUEN
- Mutation: assert hasattr(os, "fork"), "validator_server: os.fork fehlt auf dieser Plattfor => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 32.60s (34s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S20b (AC-10) -> GRUEN
- Mutation: atexit.register(self.verwerfen) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 34.86s (36s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S34 (AC-8) -> GRUEN
- Mutation: return (code or 0) & 0xFF => return (code or 0)
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 30 passed, 13 warnings in 32.84s (34s)
- Rote Tests: -
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S47 (AC-8) -> ROT
- Mutation: run_name="__main__")
    except SystemExit => run_name="validator")
    except SystemExit
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 4 failed, 26 passed, 13 warnings in 31.48s (33s)
- Rote Tests: test_ac1_prozess_und_server_gleich[briefing_mail_validator-False], test_ac1_prozess_und_server_gleich[briefing_mail_validator-True], test_ac1_prozess_und_server_gleich[email_spec_validator-False], test_ac1_prozess_und_server_gleich[email_spec_validator-True]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S28 (AC-10) -> ROT
- Mutation: anfrage["timeout"] + 1) => anfrage["timeout"] + 1000)
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 40.78s (42s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S29 (AC-6) -> ROT
- Mutation: with contextlib.suppress(BrokenPipeError):  # Server tot: _lies meldet es => if True:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 29 passed, 13 warnings in 32.55s (34s)
- Rote Tests: test_ac6_toter_server_scheitert_laut_und_startet_neu
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

### R-S37 (AC-6) -> ROT
- Mutation: raise ServerFehler(f"Server tot: {self._stderr.read()}") => raise TimeoutError
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 6 failed, 24 passed, 13 warnings in 28.18s (29s)
- Rote Tests: test_ac6_gescheiterte_einrichtung_des_kindes_ist_kein_ergebnis, test_ac6_toter_server_scheitert_laut_und_startet_neu, test_ac6_ungeeigneter_server_scheitert_laut[meldung-nach-eof], test_ac6_ungeeigneter_server_scheitert_laut[ohne-fork], test_ac6_ungeeigneter_server_scheitert_laut[stirbt-vor-startzeile], test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]
- sha256 vorher/nachher: 564312edf3fe / 564312edf3fe -> IDENTISCH

## Flackermessung Adversary (F001, Runde 2)
Last: 14 Busy-Prozesse, Mac 10 Kerne. Testzahl je Lauf aus der pytest-Schlusszeile ausgewertet (alle Laeufe gleich):
- Serie A: 30 Laeufe, je 17 passed, `-n 4 --dist loadgroup`, -k "ac3 or ac4 or ac5 or ac6 or ac8": 0 rot.
- Serie B: 50 Laeufe, je 8 passed, seriell, -k "ac6 or ac5_fremde" (u. a. zusatz-thread, ohne-fork, meldung-nach-eof, stirbt-vor-startzeile, toter Server, fremde Kennung): 0 rot.
Zum Vergleich Runde 1 (alter Stand, gleiche Last): 3 von 28 Laeufen rot. Hinweis: der Implementierer-Nachweis `flacker-nachweis.txt` zeigt je Lauf "1 gruen"; ob dort nur ein Test lief, ist ungeklaert und stuetzt F001 nicht; massgeblich sind Serie A und B.
