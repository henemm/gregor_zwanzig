# Mutationen Runde 1 (Adversary, Workflow rework-3331-validatoren-tempo)

Verfahren: je Mutation eine String-Ersetzung. Original vorher im Speicher und als Kopie im Sitzungs-Scratchpad gesichert; kein Versionskontroll-Rueckgriff. Nach jedem Lauf Original zurueckgeschrieben, sha256 vorher/nachher verglichen. Testlauf: -n 4 --dist loadgroup, nur benannte Dateien.

Ausgangs-sha256 (unmutierter Stand, Scratchpad-Kopien):

```
afb73d8da6fc5f43 _mail_lang.py
02259436cd9f0388 _soll_aus_konfiguration.py
d677c56c6d857c19 briefing_mail_validator.py
059ae906c6ade242 email_spec_validator.py
60d8a171ebbae048 mail_lang_fixture.py
8c61adf971e01e1f test_einstellung_gleich_mail_soll_placements.py
d8db1d2d810fabab test_einstellung_gleich_mail_validatoren.py
93442b36e332d3ae test_validator_server.py
28e0e04ff5e722ad validator_server.py
```

### S01 (AC-1) -> ROT
- Mutation: stderr=err.read()) => stderr="")
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 6 failed, 19 passed, 13 warnings in 28.11s (29s)
- Rote Tests: test_ac1_prozess_und_server_gleich[briefing_mail_validator-False], test_ac1_prozess_und_server_gleich[briefing_mail_validator-True], test_ac1_prozess_und_server_gleich[email_spec_validator-False], test_ac1_prozess_und_server_gleich[email_spec_validator-True], test_ac8_exit_regeln_wie_im_echten_prozess[ausnahme], test_ac8_exit_regeln_wie_im_echten_prozess[text]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S02 (AC-1/8) -> ROT
- Mutation: antworte(returncode=code, stdout => antworte(returncode=int(bool(code)), stdout
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 2 failed, 23 passed, 13 warnings in 33.03s (34s)
- Rote Tests: test_ac5_abbruch_im_warten_vertauscht_keine_antwort, test_ac8_exit_regeln_wie_im_echten_prozess[zahl]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S03 (AC-1) -> ROT
- Mutation: stdout=out.read(), => stdout="",
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 16 failed, 9 passed, 13 warnings in 29.67s (31s)
- Rote Tests: test_ac1_prozess_und_server_gleich[briefing_mail_validator-False], test_ac1_prozess_und_server_gleich[briefing_mail_validator-True], test_ac1_prozess_und_server_gleich[email_spec_validator-False], test_ac1_prozess_und_server_gleich[email_spec_validator-True], test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs, test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort, test_ac6_toter_server_scheitert_laut_und_startet_neu, test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread], test_ac7_zweiter_lauf_sieht_keinen_zustand_des_ersten, test_ac8_exit_regeln_wie_im_echten_prozess[ausnahme], test_ac8_exit_regeln_wie_im_echten_prozess[none] (+4 weitere)
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S04 (AC-3) -> ROT
- Mutation: os.environ.clear() => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 24 passed, 13 warnings in 29.16s (31s)
- Rote Tests: test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S05 (AC-3) -> ROT
- Mutation: os.chdir(anfrage["cwd"]) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 24 passed, 13 warnings in 29.94s (31s)
- Rote Tests: test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S06 (AC-3) -> ROT
- Mutation: time.tzset() => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac3'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 4.43s (6s)
- Rote Tests: test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S07 (AC-3) -> ROT
- Mutation: sys.argv = [anfrage["skript"], *anfrage["args"]] => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac3'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 4.27s (5s)
- Rote Tests: test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S07b (AC-3) -> ROT
- Mutation: os.environ.update(anfrage["env"]) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac3'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 2.70s (4s)
- Rote Tests: test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S08 (AC-4) -> ROT
- Mutation: os.killpg(pid, signal.SIGKILL) => os.kill(pid, signal.SIGKILL)
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac4'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 14.26s (15s)
- Rote Tests: test_ac4_frist_beendet_kind_und_enkel
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S09 (AC-5) -> ROT
- Mutation: self.verwerfen()
            if isinstance(fehler, TimeoutError): => if isinstance(fehler, TimeoutError):
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac5'`
- Ergebnis: ROT, exit=1, 1 failed, 2 passed, 10 warnings in 12.35s (14s)
- Rote Tests: test_ac5_abbruch_im_warten_vertauscht_keine_antwort
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S10 (AC-5) -> ROT
- Mutation: if antwort.get("kennung") != self._kennung: => if False:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac5'`
- Ergebnis: ROT, exit=1, 2 failed, 1 passed, 10 warnings in 5.65s (7s)
- Rote Tests: test_ac5_fremde_kennung_scheitert_laut[ergebnis], test_ac5_fremde_kennung_scheitert_laut[startzeile]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S11 (AC-5) -> ROT
- Mutation: _beende_gruppe(self._kind) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac5 or ac4'`
- Ergebnis: ROT, exit=1, 2 failed, 2 passed, 10 warnings in 14.44s (16s)
- Rote Tests: test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S11b (AC-4/5) -> GRUEN
- Mutation: _beende_gruppe(pid)
        raise => pass
        raise
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac5 or ac4'`
- Ergebnis: GRUEN, exit=0, 4 passed, 10 warnings in 7.44s (9s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S12 (AC-6) -> ROT
- Mutation: raise subprocess.TimeoutExpired(befehl, timeout) from fehler
            raise => raise subprocess.TimeoutExpired(befehl, timeout) from fehler
            if isin
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac6'`
- Ergebnis: ROT, exit=1, 3 failed, 10 warnings in 4.44s (6s)
- Rote Tests: test_ac6_toter_server_scheitert_laut_und_startet_neu, test_ac6_ungeeigneter_server_scheitert_laut[ohne-fork], test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S13 (AC-6) -> GRUEN
- Mutation: assert hasattr(os, "fork"), "validator_server: os.fork fehlt auf dieser Plattfor => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac6'`
- Ergebnis: GRUEN, exit=0, 3 passed, 10 warnings in 5.42s (6s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S14 (AC-6) -> ROT
- Mutation: if threading.active_count() != 1:
        raise SystemExit(f"validator_server: m => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac6'`
- Ergebnis: ROT, exit=1, 1 failed, 2 passed, 10 warnings in 4.88s (6s)
- Rote Tests: test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S15 (AC-7) -> ROT
- Mutation: def _bediene(anfrage: dict, ein_fd: int, aus, basis: list[str]) -> None:
    def => def _bediene(anfrage: dict, ein_fd: int, aus, basis: list[str]) -> None:
    def
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac7'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 3.83s (5s)
- Rote Tests: test_ac7_zweiter_lauf_sieht_keinen_zustand_des_ersten
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S16 (AC-8) -> ROT
- Mutation: code = ende.code => code = 1 if ende.code is None else ende.code
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac8'`
- Ergebnis: ROT, exit=1, 1 failed, 3 passed, 10 warnings in 4.82s (6s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[none]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S17 (AC-8) -> ROT
- Mutation: print(code, file=sys.stderr) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac8'`
- Ergebnis: ROT, exit=1, 1 failed, 3 passed, 10 warnings in 4.63s (6s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[text]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S18 (AC-8) -> ROT
- Mutation: sys.excepthook(type(fehler), fehler.with_traceback(tb), tb) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac8'`
- Ergebnis: ROT, exit=1, 1 failed, 3 passed, 10 warnings in 4.46s (6s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[ausnahme]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S19 (AC-9) -> ROT
- Mutation: im_server: bool = False => im_server: bool = True
- Datei: tests/helpers/mail_lang_fixture.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac9'`
- Ergebnis: ROT, exit=1, 1 failed, 1 passed, 10 warnings in 4.25s (5s)
- Rote Tests: test_ac9_ohne_opt_in_echter_prozess
- sha256 vorher/nachher: 60d8a171ebba / 60d8a171ebba -> IDENTISCH

### S20a (AC-10) -> ROT
- Mutation: for zeile in ein:  # bis EOF, auch bei hart beendetem Klienten
        _bediene( => while True:
        zeile = ein.readline()
        if not zeile:
            tim
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac10'`
- Ergebnis: ROT, exit=1, 1 failed, 3 passed, 10 warnings in 16.48s (18s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S20b (AC-10) -> GRUEN
- Mutation: atexit.register(self.verwerfen) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac10'`
- Ergebnis: GRUEN, exit=0, 4 passed, 10 warnings in 12.57s (14s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S21 (AC-4) -> ROT
- Mutation: os.setsid() => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac4 or ac5 or ac10'`
- Ergebnis: ROT, exit=1, 4 failed, 4 passed, 10 warnings in 20.29s (21s)
- Rote Tests: test_ac10_browser_weg_nach_frist, test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind], test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S22 (Haertung) -> GRUEN
- Mutation: os.dup2(os.open(os.devnull, os.O_RDONLY), 0) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 30.21s (31s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S23 (Haertung) -> GRUEN
- Mutation: os.dup2(2, 1)  # nichts ausser dem Protokoll geht an den Klienten => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 26.87s (28s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S24a (Haertung) -> GRUEN
- Mutation: if sync.recv(1): => if True:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 32.80s (34s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S24b (Haertung) -> GRUEN
- Mutation: assert hier.recv(1), "Kind konnte nicht eingerichtet werden" => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 31.91s (33s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S25 (Haertung) -> ROT
- Mutation: for fd in fremde_fds:  # sonst bliebe beim Klienten/Server das EOF aus
          => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 24 passed, 13 warnings in 27.08s (28s)
- Rote Tests: test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S26 (Haertung) -> GRUEN
- Mutation: tempfile.tempdir = None => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 28.77s (30s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S27 (Frist) -> ROT
- Mutation: START_FRIST = 60.0 => START_FRIST = 0.001
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 23 failed, 2 passed, 13 warnings in 11.24s (13s)
- Rote Tests: test_ac10_browser_weg_nach_frist, test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind], test_ac10_server_verschwindet_mit_dem_worker[kill], test_ac10_server_verschwindet_mit_dem_worker[normal], test_ac1_prozess_und_server_gleich[briefing_mail_validator-False], test_ac1_prozess_und_server_gleich[briefing_mail_validator-True], test_ac1_prozess_und_server_gleich[email_spec_validator-False], test_ac1_prozess_und_server_gleich[email_spec_validator-True], test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs, test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort, test_ac5_fremde_kennung_scheitert_laut[ergebnis] (+11 weitere)
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S27b (Frist) -> GRUEN
- Mutation: START_FRIST = 60.0 => START_FRIST = 3600.0
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 31.27s (33s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S28 (Frist/AC-10) -> ROT
- Mutation: anfrage["timeout"] + 1) => anfrage["timeout"] + 1000)
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 24 passed, 13 warnings in 31.48s (33s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S28b (Frist) -> ROT
- Mutation: if time.monotonic() > ende: => if False:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 24 passed, 13 warnings in 39.53s (41s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S29 (Haertung) -> ROT
- Mutation: with contextlib.suppress(BrokenPipeError):  # Server tot: _lies meldet es => if True:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 24 passed, 13 warnings in 25.01s (26s)
- Rote Tests: test_ac6_toter_server_scheitert_laut_und_startet_neu
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S30 (Haertung) -> GRUEN
- Mutation: daten[:select.PIPE_BUF] => daten
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 26.58s (28s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S31 (Haertung) -> GRUEN
- Mutation: sys.path[:] = [os.path.dirname(anfrage["skript"]), *basis] => sys.path[:] = [os.path.dirname(anfrage["skript"]), *sys.path]
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 26.07s (27s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S32 (Haertung) -> GRUEN
- Mutation: basis = sys.path[1:] => basis = sys.path[:]
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 26.65s (28s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S33 (AC-8) -> GRUEN
- Mutation: os.waitstatus_to_exitcode(fertig[1]) => os.WEXITSTATUS(fertig[1])
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac8'`
- Ergebnis: GRUEN, exit=0, 4 passed, 10 warnings in 4.43s (6s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S34 (AC-8) -> GRUEN
- Mutation: return (code or 0) & 0xFF => return (code or 0)
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac8'`
- Ergebnis: GRUEN, exit=0, 4 passed, 10 warnings in 4.48s (5s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S35 (AC-5) -> GRUEN
- Mutation: self._kennung = self._kind = None
            return => return
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 25.82s (27s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S36 (AC-5) -> GRUEN
- Mutation: if self._kennung and self._kind is None:
                    with contextlib.sup => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 26.18s (27s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S37 (AC-6) -> ROT
- Mutation: raise TimeoutError if time.monotonic() >= ende else ServerFehler(f"Server tot: { => raise TimeoutError
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac6'`
- Ergebnis: ROT, exit=1, 3 failed, 10 warnings in 4.01s (5s)
- Rote Tests: test_ac6_toter_server_scheitert_laut_und_startet_neu, test_ac6_ungeeigneter_server_scheitert_laut[ohne-fork], test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S38 (Haertung) -> ROT
- Mutation: stderr=self._stderr, bufsize=0) => stderr=self._stderr)
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 21 failed, 4 passed, 13 warnings in 193.87s (0:03:13) (195s)
- Rote Tests: test_ac10_browser_weg_nach_frist, test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind], test_ac10_server_verschwindet_mit_dem_worker[kill], test_ac10_server_verschwindet_mit_dem_worker[normal], test_ac1_prozess_und_server_gleich[briefing_mail_validator-False], test_ac1_prozess_und_server_gleich[briefing_mail_validator-True], test_ac1_prozess_und_server_gleich[email_spec_validator-False], test_ac1_prozess_und_server_gleich[email_spec_validator-True], test_ac3_kind_bekommt_genau_die_umgebung_des_aufrufs, test_ac4_frist_beendet_kind_und_enkel, test_ac5_abbruch_im_warten_vertauscht_keine_antwort, test_ac5_fremde_kennung_scheitert_laut[ergebnis] (+9 weitere)
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S39 (AC-1) -> ROT
- Mutation: ("returncode", "stdout", "stderr") => ("returncode", "stderr", "stdout")
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac1_'`
- Ergebnis: ROT, exit=1, 4 failed, 12 warnings in 10.38s (11s)
- Rote Tests: test_ac1_prozess_und_server_gleich[briefing_mail_validator-False], test_ac1_prozess_und_server_gleich[briefing_mail_validator-True], test_ac1_prozess_und_server_gleich[email_spec_validator-False], test_ac1_prozess_und_server_gleich[email_spec_validator-True]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S40 (AC-4) -> ROT
- Mutation: if isinstance(fehler, TimeoutError):
                raise subprocess => if False:
                raise subprocess
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac4'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 5.19s (6s)
- Rote Tests: test_ac4_frist_beendet_kind_und_enkel
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S42 (AC-6) -> ROT
- Mutation: stdout=subprocess.PIPE, stderr=self._stderr, bufsize=0) => stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac6'`
- Ergebnis: ROT, exit=1, 2 failed, 1 passed, 10 warnings in 5.10s (6s)
- Rote Tests: test_ac6_ungeeigneter_server_scheitert_laut[ohne-fork], test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S43 (Haertung) -> GRUEN
- Mutation: except BaseException:
        sys.excepthook(*sys.exc_info())
    finally: => except BaseException:
        pass
    finally:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 22.78s (24s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S44 (Haertung) -> GRUEN
- Mutation: code = 1
    try:
        for fd => code = 0
    try:
        for fd
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 22.75s (24s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S45 (AC-8) -> ROT
- Mutation: sys.stdout.flush()
    sys.stderr.flush() => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac8'`
- Ergebnis: ROT, exit=1, 4 failed, 10 warnings in 2.96s (4s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[ausnahme], test_ac8_exit_regeln_wie_im_echten_prozess[none], test_ac8_exit_regeln_wie_im_echten_prozess[text], test_ac8_exit_regeln_wie_im_echten_prozess[zahl]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S46 (AC-8) -> ROT
- Mutation: while tb and tb.tb_frame.f_code.co_filename != skript: => while False:
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac8'`
- Ergebnis: ROT, exit=1, 1 failed, 3 passed, 10 warnings in 4.63s (6s)
- Rote Tests: test_ac8_exit_regeln_wie_im_echten_prozess[ausnahme]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S47 (AC-8) -> GRUEN
- Mutation: run_name="__main__")
    except SystemExit => run_name="validator")
    except SystemExit
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac8'`
- Ergebnis: GRUEN, exit=0, 4 passed, 10 warnings in 3.05s (4s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S49 (AC-5) -> GRUEN
- Mutation: os.urandom(8).hex() => "k"
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 21.35s (22s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S11b-voll (AC-4/5) -> ROT
- Mutation: _beende_gruppe(pid)
        raise => pass
        raise
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 1 failed, 24 passed, 13 warnings in 30.23s (32s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill-mit-kind]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S13-voll (AC-6) -> GRUEN
- Mutation: assert hasattr(os, "fork"), "validator_server: os.fork fehlt auf dieser Plattfor => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 29.05s (30s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S20b-voll (AC-10) -> GRUEN
- Mutation: atexit.register(self.verwerfen) => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 27.07s (28s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S33-voll (AC-8) -> GRUEN
- Mutation: os.waitstatus_to_exitcode(fertig[1]) => os.WEXITSTATUS(fertig[1])
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 26.43s (28s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S34-voll (AC-8) -> GRUEN
- Mutation: return (code or 0) & 0xFF => return (code or 0)
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 30.99s (32s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S47-voll (AC-8) -> ROT
- Mutation: run_name="__main__")
    except SystemExit => run_name="validator")
    except SystemExit
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: ROT, exit=1, 4 failed, 21 passed, 13 warnings in 25.63s (27s)
- Rote Tests: test_ac1_prozess_und_server_gleich[briefing_mail_validator-False], test_ac1_prozess_und_server_gleich[briefing_mail_validator-True], test_ac1_prozess_und_server_gleich[email_spec_validator-False], test_ac1_prozess_und_server_gleich[email_spec_validator-True]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### Z1 (Opt-in) -> ROT
- Mutation: im_server=not prozess, => im_server=False,
- Datei: tests/tdd/test_einstellung_gleich_mail_validatoren.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac9 or ac2_ or ac3'`
- Ergebnis: ROT, exit=1, 1 failed, 4 passed, 11 warnings in 6.74s (7s)
- Rote Tests: test_ac9_zieldatei_schaltet_ein_und_kann_prozess
- sha256 vorher/nachher: d8db1d2d810f / d8db1d2d810f -> IDENTISCH

### Z2 (AC-2) -> ROT
- Mutation: ohne_installiertes_src=prozess) => ohne_installiertes_src=False)
- Datei: tests/tdd/test_einstellung_gleich_mail_validatoren.py
- Befehl: `uv run pytest tests/test_validator_server.py tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 2 failed, 3 passed, 12 warnings in 15.32s (17s)
- Rote Tests: test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: d8db1d2d810f / d8db1d2d810f -> IDENTISCH

### Z3 (AC-2) -> ROT
- Mutation: [*python, "-S"], sysconfig => python, sysconfig
- Datei: tests/helpers/mail_lang_fixture.py
- Befehl: `uv run pytest tests/test_validator_server.py tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 2 failed, 3 passed, 12 warnings in 15.26s (17s)
- Rote Tests: test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: 60d8a171ebba / 60d8a171ebba -> IDENTISCH

### [UNGUELTIG: Treiberfehler, nur 1 von 2 Ersetzungen in email_spec_validator.py angewandt, in Runde 1b wiederholt] H1 (AC-2 ORTE: nur email_spec_validator (2 Stellen)) -> GRUEN
- Mutation: sys.path.insert(0, str(_REPO_SRC)) => pass
- Datei: .claude/hooks/email_spec_validator.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: GRUEN, exit=0, 5 passed, 12 warnings in 9.13s (10s)
- Rote Tests: -
- sha256 vorher/nachher: 059ae906c6ad / 059ae906c6ad -> IDENTISCH

### H2 (AC-2: nur _soll_aus_konfiguration) -> ROT
- Mutation: sys.path.insert(0, str(_SRC)) => pass
- Datei: .claude/hooks/_soll_aus_konfiguration.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 3 failed, 2 passed, 12 warnings in 6.65s (8s)
- Rote Tests: test_trip_echter_prozess_mit_konfig, test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: 02259436cd9f / 02259436cd9f -> IDENTISCH

### H3 (AC-2: nur _mail_lang) -> ROT
- Mutation: sys.path.insert(0, str(_SRC)) => pass
- Datei: .claude/hooks/_mail_lang.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 2 failed, 3 passed, 12 warnings in 9.69s (11s)
- Rote Tests: test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: afb73d8da6fc / afb73d8da6fc -> IDENTISCH

### H4 (AC-2: nur _mail_trust) -> GRUEN
- Mutation: sys.path.insert(0, str(_SRC)) => pass
- Datei: .claude/hooks/_mail_trust.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: GRUEN, exit=0, 5 passed, 12 warnings in 9.16s (10s)
- Rote Tests: -
- sha256 vorher/nachher: 379aafa5c59f / 379aafa5c59f -> IDENTISCH

### [UNGUELTIG: Treiberfehler, nur 1 von 2 Ersetzungen in email_spec_validator.py angewandt, in Runde 1b wiederholt] H5 (AC-2 ORTE alle: email_spec(2)+_soll+_mail_lang+_mail_trust) -> ROT
- Mutation: sys.path.insert(0, str(_REPO_SRC)) => pass
- Datei: .claude/hooks/email_spec_validator.py, .claude/hooks/_soll_aus_konfiguration.py, .claude/hooks/_mail_lang.py, .claude/hooks/_mail_trust.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 3 failed, 2 passed, 12 warnings in 7.23s (8s)
- Rote Tests: test_trip_echter_prozess_mit_konfig, test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: 059ae906c6ad 02259436cd9f afb73d8da6fc 379aafa5c59f / 059ae906c6ad 02259436cd9f afb73d8da6fc 379aafa5c59f -> IDENTISCH

### H6 (AC-2 TRIP alle: briefing+_soll+_mail_lang+_mail_trust) -> ROT
- Mutation: sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src")) => pass
- Datei: .claude/hooks/briefing_mail_validator.py, .claude/hooks/_soll_aus_konfiguration.py, .claude/hooks/_mail_lang.py, .claude/hooks/_mail_trust.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 3 failed, 2 passed, 12 warnings in 7.29s (8s)
- Rote Tests: test_trip_echter_prozess_mit_konfig, test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: d677c56c6d85 02259436cd9f afb73d8da6fc 379aafa5c59f / d677c56c6d85 02259436cd9f afb73d8da6fc 379aafa5c59f -> IDENTISCH

### H7 (AC-2 TRIP: nur briefing_mail_validator) -> ROT
- Mutation: sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src")) => pass
- Datei: .claude/hooks/briefing_mail_validator.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 1 failed, 4 passed, 12 warnings in 9.47s (11s)
- Rote Tests: test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator]
- sha256 vorher/nachher: d677c56c6d85 / d677c56c6d85 -> IDENTISCH

### [UNGUELTIG: Treiberfehler, nur 1 von 2 Ersetzungen in email_spec_validator.py angewandt, in Runde 1b wiederholt] H8 (AC-2 ORTE alle ohne _mail_trust) -> ROT
- Mutation: sys.path.insert(0, str(_REPO_SRC)) => pass
- Datei: .claude/hooks/email_spec_validator.py, .claude/hooks/_soll_aus_konfiguration.py, .claude/hooks/_mail_lang.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 3 failed, 2 passed, 12 warnings in 7.44s (9s)
- Rote Tests: test_trip_echter_prozess_mit_konfig, test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: 059ae906c6ad 02259436cd9f afb73d8da6fc / 059ae906c6ad 02259436cd9f afb73d8da6fc -> IDENTISCH

### H9 (AC-2 TRIP alle ohne _mail_trust) -> ROT
- Mutation: sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src")) => pass
- Datei: .claude/hooks/briefing_mail_validator.py, .claude/hooks/_soll_aus_konfiguration.py, .claude/hooks/_mail_lang.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 3 failed, 2 passed, 12 warnings in 7.17s (8s)
- Rote Tests: test_trip_echter_prozess_mit_konfig, test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: d677c56c6d85 02259436cd9f afb73d8da6fc / d677c56c6d85 02259436cd9f afb73d8da6fc -> IDENTISCH

### V1-server (AC-11 TRIP Format-Pruefung) -> ROT
- Mutation: if msg["X-GZ-Format"] != s["email_format"]: => if False:
- Datei: .claude/hooks/briefing_mail_validator.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'format_widerspricht'`
- Ergebnis: ROT, exit=1, 2 failed, 10 warnings in 6.47s (8s)
- Rote Tests: test_trip_format_widerspricht_konfig_scheitert[compact-full], test_trip_format_widerspricht_konfig_scheitert[full-compact]
- sha256 vorher/nachher: d677c56c6d85 / d677c56c6d85 -> IDENTISCH

### V1-prozess (AC-11 TRIP Format-Pruefung) -> ROT
- Mutation: if msg["X-GZ-Format"] != s["email_format"]: => if False:
- Datei: .claude/hooks/briefing_mail_validator.py, tests/tdd/test_einstellung_gleich_mail_validatoren.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'format_widerspricht'`
- Ergebnis: ROT, exit=1, 2 failed, 10 warnings in 7.03s (8s)
- Rote Tests: test_trip_format_widerspricht_konfig_scheitert[compact-full], test_trip_format_widerspricht_konfig_scheitert[full-compact]
- sha256 vorher/nachher: d677c56c6d85 d8db1d2d810f / d677c56c6d85 d8db1d2d810f -> IDENTISCH

### V2-server (AC-11 ORTE Ortsfolge) -> ROT
- Mutation: return [f"SOLL: Ortsfolge ({teil}): {diff}".replace("Spalte", "Ort")] if diff el => return []
- Datei: .claude/hooks/email_spec_validator.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'ortsfolge_vertauscht'`
- Ergebnis: ROT, exit=1, 1 failed, 11 warnings in 6.96s (8s)
- Rote Tests: test_orte_ortsfolge_vertauscht_scheitert
- sha256 vorher/nachher: 059ae906c6ad / 059ae906c6ad -> IDENTISCH

### V2-prozess (AC-11 ORTE Ortsfolge) -> ROT
- Mutation: return [f"SOLL: Ortsfolge ({teil}): {diff}".replace("Spalte", "Ort")] if diff el => return []
- Datei: .claude/hooks/email_spec_validator.py, tests/tdd/test_einstellung_gleich_mail_validatoren.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'ortsfolge_vertauscht'`
- Ergebnis: ROT, exit=1, 1 failed, 11 warnings in 7.25s (8s)
- Rote Tests: test_orte_ortsfolge_vertauscht_scheitert
- sha256 vorher/nachher: 059ae906c6ad d8db1d2d810f / 059ae906c6ad d8db1d2d810f -> IDENTISCH

### V3-server (AC-11 TRIP Render-Pruefung (Chromium)) -> ROT
- Mutation: errors.extend(_check_rendered(html, stunden_erwartet, ausblick_tag)) => pass
- Datei: .claude/hooks/briefing_mail_validator.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'versteckt'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 6.20s (7s)
- Rote Tests: test_trip_ausblick_erwartet_aber_versteckt_scheitert
- sha256 vorher/nachher: d677c56c6d85 / d677c56c6d85 -> IDENTISCH

### V3-prozess (AC-11 TRIP Render-Pruefung (Chromium)) -> ROT
- Mutation: errors.extend(_check_rendered(html, stunden_erwartet, ausblick_tag)) => pass
- Datei: .claude/hooks/briefing_mail_validator.py, tests/tdd/test_einstellung_gleich_mail_validatoren.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'versteckt'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 6.55s (8s)
- Rote Tests: test_trip_ausblick_erwartet_aber_versteckt_scheitert
- sha256 vorher/nachher: d677c56c6d85 d8db1d2d810f / d677c56c6d85 d8db1d2d810f -> IDENTISCH

### V5-server (AC-11 TRIP/ORTE Spalte zu viel) -> ROT
- Mutation: zuviel = [x for x in ist if x not in soll] => zuviel = []
- Datei: .claude/hooks/_soll_aus_konfiguration.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'zu_viel'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 7.70s (9s)
- Rote Tests: test_trip_spalte_zu_viel_scheitert
- sha256 vorher/nachher: 02259436cd9f / 02259436cd9f -> IDENTISCH

### V5-prozess (AC-11 TRIP/ORTE Spalte zu viel) -> ROT
- Mutation: zuviel = [x for x in ist if x not in soll] => zuviel = []
- Datei: .claude/hooks/_soll_aus_konfiguration.py, tests/tdd/test_einstellung_gleich_mail_validatoren.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'zu_viel'`
- Ergebnis: ROT, exit=1, 1 failed, 10 warnings in 7.15s (8s)
- Rote Tests: test_trip_spalte_zu_viel_scheitert
- sha256 vorher/nachher: 02259436cd9f d8db1d2d810f / 02259436cd9f d8db1d2d810f -> IDENTISCH

### V6-server (AC-11 ORTE Ortsfolge nicht pruefbar) -> ROT
- Mutation: fehler.append(f"SOLL: Ortsfolge nicht prüfbar: {soll['orte_unpruefbar']}") => pass
- Datei: .claude/hooks/email_spec_validator.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'rohes_preset_ohne_ortsnamen'`
- Ergebnis: ROT, exit=1, 1 failed, 11 warnings in 7.53s (9s)
- Rote Tests: test_orte_rohes_preset_ohne_ortsnamen_scheitert_laut
- sha256 vorher/nachher: 059ae906c6ad / 059ae906c6ad -> IDENTISCH

### V6-prozess (AC-11 ORTE Ortsfolge nicht pruefbar) -> ROT
- Mutation: fehler.append(f"SOLL: Ortsfolge nicht prüfbar: {soll['orte_unpruefbar']}") => pass
- Datei: .claude/hooks/email_spec_validator.py, tests/tdd/test_einstellung_gleich_mail_validatoren.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'rohes_preset_ohne_ortsnamen'`
- Ergebnis: ROT, exit=1, 1 failed, 11 warnings in 7.81s (9s)
- Rote Tests: test_orte_rohes_preset_ohne_ortsnamen_scheitert_laut
- sha256 vorher/nachher: 059ae906c6ad d8db1d2d810f / 059ae906c6ad d8db1d2d810f -> IDENTISCH

### [UNGUELTIG: Treiberfehler, nur 1 von 2 Ersetzungen in email_spec_validator.py angewandt, in Runde 1b wiederholt] C1-orte-echter (AC-2 Diagnose) -> GRUEN
- Mutation: sys.path.insert(0, str(_REPO_SRC)) => pass
- Datei: .claude/hooks/email_spec_validator.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'orte_echter_prozess'`
- Ergebnis: GRUEN, exit=0, 1 passed, 11 warnings in 7.71s (9s)
- Rote Tests: -
- sha256 vorher/nachher: 059ae906c6ad / 059ae906c6ad -> IDENTISCH

### H1 (AC-2 ORTE: nur email_spec_validator (2 Stellen)) -> ROT
- Mutation: sys.path.insert(0, str(_REPO_SRC)) => pass
- Datei: .claude/hooks/email_spec_validator.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 2 failed, 3 passed, 12 warnings in 9.83s (11s)
- Rote Tests: test_orte_echter_prozess_mit_konfig, test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: 059ae906c6ad / 059ae906c6ad -> IDENTISCH

### H5 (AC-2 ORTE alle: email_spec(2)+_soll+_mail_lang+_mail_trust) -> ROT
- Mutation: sys.path.insert(0, str(_REPO_SRC)) => pass
- Datei: .claude/hooks/email_spec_validator.py, .claude/hooks/_soll_aus_konfiguration.py, .claude/hooks/_mail_lang.py, .claude/hooks/_mail_trust.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 4 failed, 1 passed, 12 warnings in 6.39s (8s)
- Rote Tests: test_orte_echter_prozess_mit_konfig, test_trip_echter_prozess_mit_konfig, test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: 059ae906c6ad 02259436cd9f afb73d8da6fc 379aafa5c59f / 059ae906c6ad 02259436cd9f afb73d8da6fc 379aafa5c59f -> IDENTISCH

### H8 (AC-2 ORTE alle ohne _mail_trust) -> ROT
- Mutation: sys.path.insert(0, str(_REPO_SRC)) => pass
- Datei: .claude/hooks/email_spec_validator.py, .claude/hooks/_soll_aus_konfiguration.py, .claude/hooks/_mail_lang.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py tests/test_validator_server.py -n 4 --dist loadgroup -k 'echter_prozess or ac2_'`
- Ergebnis: ROT, exit=1, 4 failed, 1 passed, 12 warnings in 6.33s (7s)
- Rote Tests: test_orte_echter_prozess_mit_konfig, test_trip_echter_prozess_mit_konfig, test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[briefing_mail_validator], test_ac2_prozesslauf_bemerkt_fehlenden_src_pfad[email_spec_validator]
- sha256 vorher/nachher: 059ae906c6ad 02259436cd9f afb73d8da6fc / 059ae906c6ad 02259436cd9f afb73d8da6fc -> IDENTISCH

### H5s (AC-2 nur Serverlauf (positive Faelle, ORTE alle src-Pfade entfernt)) -> GRUEN
- Mutation: sys.path.insert(0, str(_REPO_SRC)) => pass
- Datei: .claude/hooks/email_spec_validator.py, .claude/hooks/_soll_aus_konfiguration.py, .claude/hooks/_mail_lang.py, .claude/hooks/_mail_trust.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'positiv_mail_stimmt'`
- Ergebnis: GRUEN, exit=0, 2 passed, 11 warnings in 7.99s (9s)
- Rote Tests: -
- sha256 vorher/nachher: 059ae906c6ad 02259436cd9f afb73d8da6fc 379aafa5c59f / 059ae906c6ad 02259436cd9f afb73d8da6fc 379aafa5c59f -> IDENTISCH

### H6s (AC-2 nur Serverlauf (positive Faelle, TRIP alle src-Pfade entfernt)) -> GRUEN
- Mutation: sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src")) => pass
- Datei: .claude/hooks/briefing_mail_validator.py, .claude/hooks/_soll_aus_konfiguration.py, .claude/hooks/_mail_lang.py, .claude/hooks/_mail_trust.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_validatoren.py -n 4 --dist loadgroup -k 'positiv_mail_stimmt'`
- Ergebnis: GRUEN, exit=0, 2 passed, 11 warnings in 7.79s (9s)
- Rote Tests: -
- sha256 vorher/nachher: d677c56c6d85 02259436cd9f afb73d8da6fc 379aafa5c59f / d677c56c6d85 02259436cd9f afb73d8da6fc 379aafa5c59f -> IDENTISCH

### S20c (AC-10 EOF-Ende UND atexit zusammen) -> ROT
- Mutation: for zeile in ein:  # bis EOF, auch bei hart beendetem Klienten
        _bediene( => while True:
        zeile = ein.readline()
        if not zeile:
            tim
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup -k 'ac10'`
- Ergebnis: ROT, exit=1, 2 failed, 2 passed, 10 warnings in 16.82s (18s)
- Rote Tests: test_ac10_server_verschwindet_mit_dem_worker[kill], test_ac10_server_verschwindet_mit_dem_worker[normal]
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### Z4 (Z.489 prozess=True entfernt) -> GRUEN
- Mutation: *_ampel_rohwerte(), prozess=True) => *_ampel_rohwerte())
- Datei: tests/tdd/test_einstellung_gleich_mail_soll_placements.py
- Befehl: `uv run pytest tests/tdd/test_einstellung_gleich_mail_soll_placements.py -n 4 --dist loadgroup -k 'abnahme_3156'`
- Ergebnis: GRUEN, exit=0, 2 passed, 10 warnings in 7.63s (9s)
- Rote Tests: -
- sha256 vorher/nachher: 8c61adf971e0 / 8c61adf971e0 -> IDENTISCH

### S25 (Haertung) -> GRUEN
- Mutation: for fd in fremde_fds:  # sonst bliebe beim Klienten/Server das EOF aus
          => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 26.12s (27s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

### S25 (Haertung) -> GRUEN
- Mutation: for fd in fremde_fds:  # sonst bliebe beim Klienten/Server das EOF aus
          => pass
- Datei: tests/helpers/validator_server.py
- Befehl: `uv run pytest tests/test_validator_server.py -n 4 --dist loadgroup`
- Ergebnis: GRUEN, exit=0, 25 passed, 13 warnings in 25.61s (27s)
- Rote Tests: -
- sha256 vorher/nachher: 28e0e04ff5e7 / 28e0e04ff5e7 -> IDENTISCH

---
## Zusammenfassung Runde 1 (91 Eintraege, davon 4 UNGUELTIG gekennzeichnet; Hash nach jedem Rueckspielen identisch, kein Eintrag mit Abweichung)

Hinweise zur Lesart: Bei Eintraegen mit `-k` lief nur der betroffene Test-Ausschnitt; war das Ergebnis dort GRUEN, folgte (soweit relevant) ein Eintrag `-voll` mit der ganzen Datei. S25 (erster Eintrag ROT) ist nicht reproduzierbar (zwei Wiederholungen GRUEN): die Rotfaerbung stammt aus der Flanke von `test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]` (siehe Finding F001 im Dialog), nicht aus der Mutation.

### Ueberlebende Verfaelschungen (kein Test rot) und Einordnung
| ID | Verfaelschung | Einordnung |
|---|---|---|
| S13/-voll | `assert hasattr(os, "fork")` entfernt | gleichwertig: ohne fork stirbt der Server beim ersten `os.fork()` mit AttributeError, dessen Text "fork" enthaelt; der Test erwartet nur ServerFehler mit "fork" |
| S20b/-voll | `atexit` des Klienten entfernt | gleichwertig zu EOF-Ende: der Server endet ueber EOF auf stdin (S20a allein ROT, S20c beides ROT) |
| S34/-voll | `& 0xFF` entfernt | gleichwertig: `os._exit` kuerzt auf 8 Bit |
| S11b (nur -k) | killpg im Server-`_warte` entfernt | in der ganzen Datei ROT (`kill-mit-kind`), nicht gleichwertig, aber nur von diesem einen Test bewacht |
| S22 | stdin des Servers nicht auf /dev/null | UNBEWACHT: Kind erbt sonst die Anfrage-Pipe als stdin (Finding F004) |
| S23 | `dup2(2, 1)` weg | UNBEWACHT (Schutz gegen Fremdausgaben im Protokollkanal; heute druckt kein vorgeladenes Modul) |
| S24a/S24b | Handschlag (Kind wartet auf "1" des Servers / Server wartet auf Kind) | UNBEWACHT (Finding F004) |
| S26 | `tempfile.tempdir = None` weg | UNBEWACHT (TMPDIR des Aufrufs wirkt dann nicht im Kind) |
| S27b | START_FRIST 60 s -> 3600 s | UNBEWACHT (haengender Serverstart nicht getestet) |
| S30 | PIPE_BUF-Stuecke beim Senden | UNBEWACHT (Anfragen < 4 KiB nie ueber der Grenze, Tests senden kleine Umgebungen) |
| S31/S32 | Kind-`sys.path` aus Server-Pfad statt Grundpfad | UNBEWACHT (AC-3 prueft nur `sys.path[0]`) |
| S33/-voll | `waitstatus_to_exitcode` -> `WEXITSTATUS` | UNBEWACHT: Signaltod des Kindes (negativer returncode) hat keinen Test (Probe: heute gleich dem Prozess) |
| S35 | `_kennung/_kind` nach Erfolg nicht zuruecksetzen | UNBEWACHT (spaeteres `verwerfen` koennte `killpg` auf eine wiederverwendete pid schicken) |
| S36 | Startzeile beim Verwerfen nachlesen | UNBEWACHT (Abbruch vor Eingang der Startzeile) |
| S43/S44 | Setup-Fehler im Kind still / Exit-Code 0 | UNBEWACHT |
| S47 (-k ac8) / S47-voll | `run_name != "__main__"` | ROT in AC-1 (Validator tut dann nichts); AC-8-Tests allein fangen es nicht |
| S49 | konstante Kennung | UNBEWACHT mit echtem Server (nur Ersatz-Server prueft die Kennung) |
| H4 | `_mail_trust`-sys.path allein | gleichwertig (andere Eintraege ersetzen ihn) |
| H5s/H6s | alle src-Pfade weg, NUR Serverlauf | erwartet GRUEN: der Server verdeckt den Fehler (so spezifiziert, AC-2) |
| Z4 | `prozess=True` in soll_placements Z. 489 entfernt | UNBEWACHT, aber redundant: den Prozesslauf je Validator garantieren die `*_echter_prozess_mit_konfig`-Tests der Zieldatei |
