# Adversary-Dialog #2422 S1

Kontext: Adversary-Prüfung für Workflow `fix-2422-konfig-auslieferung-testluecken`, Issue #2422 Scheibe S1. Geprüfte Dateien (uncommittet, `git diff --stat`): `docs/reference/gates_und_ratschen.md` (+1 Zeile), `tests/helpers/einstellung_auslieferung_orakel.py` (+130/-4). Kein Produktcode im Diff. Spec: `docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md`.

Test-Artefakte: `docs/artifacts/fix-2422-konfig-auslieferung-testluecken/adversary-mutation-testlauf.txt` (finaler Lauf, 17 passed). Alle Mutationen erfolgten per String-Ersetzung mit vorheriger Sicherungskopie im Session-Scratchpad; nach jeder Runde `cmp`-Beleg + `git diff --stat`, dass nur die zwei GREEN-Dateien verändert bleiben.

### Runde 1

**Testlauf (Ausgangsstand):** `tests/tdd/test_einstellung_gleich_auslieferung.py` 16 passed; `tests/test_regel_budget_pruefdatum_einstellung_auslieferung.py` 1 passed.

**AC-1 (Golden-Trips laden unverändert)**
Bestätigung: `test_ac1_golden_trips_laden_unveraendert` vergleicht direkt Attribute des über `load_trip` geladenen `Trip`-Objekts gegen das rohe JSON.
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:89-121
Status: CONFIRMED

**AC-2 (Bug-Nachweis wind_chill × Telegram-Kurzstil)**
Bestätigung: Entfernt lokal genau den B1-Kurzform-Eintrag, prüft `rot == {genau diese Zelle}` per Mengengleichheit.
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:129-154
Status: CONFIRMED

**AC-3 (Orakel-Unabhängigkeit) — Finding F001**
Die Spec verbietet ausdrücklich AST-/`inspect.getsource`-Prüfungen (Implementation Details + Changelog). Der Test nutzt `inspect.getsource(orakel_mod)` mit Substring-Check `"from app.models import" not in quelle`; umgehbar mit `from app import models as models_mod`.
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:365-372
Severity: MEDIUM
Remediation: Zeilen 365-372 entfernen, AC-3 ausschließlich über die M1-Verhaltensdifferenz führen.

**AC-4 (Kürzel-Register nur zum Parsen)**
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:160-188
Status: CONFIRMED

**AC-5 (strukturelle Ausnahmen verengen die Erwartung nicht)**
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:194-232
Status: CONFIRMED — mit Einschränkung: Filter `e.metrik != "*"` fängt Wildcard-Ausweitung nur zufällig (Mutation C).

**AC-8 (Eintrag ohne Begründung blockt vor der Matrix)**
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:49-58, tests/tdd/test_einstellung_gleich_auslieferung.py:306-334
Status: CONFIRMED

**AC-9 (Mutations-Pflichtfänge M1-M4)**
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:347-472
Status: CONFIRMED (Runde 2 bestätigt zusätzlich echte Produktcode-Mutationen)

**AC-10 (Register-Startbefüllung)**
9 Einträge (3× B1, 3× B2, 1× B3, 1× B5, 1× strukturell/Issue #360) — passt zur Deckungstabelle.
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:66-189, tests/tdd/test_einstellung_gleich_auslieferung.py:478-509
Status: CONFIRMED

**AC-11 (Matrix-Abdeckung)**
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:515-560
Status: CONFIRMED

**AC-13 (Naht nur am Transport)**
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:603-627
Status: CONFIRMED mit Vorbehalt (F004)

**Register-Begründungen faktengeprüft:**
- `gust`/Telegram-7er-Limit: `CHANNEL_LIMITS["telegram"]["max_table_cols"] = 8`, Commit `5f9b57f9` = feat(#360), Issue #360 CLOSED; in Golden B ist `gust` rechnerisch das 8. Primary und wird demoted. Korrekt.
  Code reference: src/output/renderers/channel_layout.py:46-148
- B3/Issue #2429: Titel, Status und Ursache (`trip_report.py:142`) stimmen überein.
  Code reference: src/output/renderers/trip_report.py:130-142

### Runde 2

**Mutations-Gegenprobe — Register/Orakel**

Mutation A: zusätzlicher erfundener Eintrag `AusnahmeEintrag(metrik="wind", kanal="email_html", dimension="erscheint", befund="B1", grund="MUTATION-A ...")` im echten `AUSNAHMEN`. Ergebnis: alle 16 Tests grün, auch AC-6 und AC-7.
Ursache: `abweichungen_fuer_golden` baut `alle_abweichungen` registerunabhängig; AC-6 vergleicht damit tautologisch; AC-7 prüft nur eine lokale Probe-Zelle, nie den echten Bestand.
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:574-622, tests/tdd/test_einstellung_gleich_auslieferung.py:238-300

Mutation B: echten B3-Eintrag entfernt → `test_hauptmatrix_…` und `test_ac10_…` rot (Unterdeckung wird gefangen); AC-6 bleibt grün.

Mutation C: `gust`-Eintrag auf `metrik="*"` verbreitert → nur `test_ac5_…` rot (Zufallstreffer der Filterlogik).

**Finding F002 (HIGH): AC-6/AC-7 prüfen nicht das reale Register.**
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:574-622; tests/tdd/test_einstellung_gleich_auslieferung.py:238-300
Spec requirement: AC-6 „nicht mehr … und nicht weniger"; AC-7 veraltete Einträge werden sichtbar.
Conflict: Ein zusätzlicher, falscher oder zu breiter Eintrag im ECHTEN `AUSNAHMEN` bleibt unentdeckt.
Remediation: Test `veraltete_eintraege(AUSNAHMEN, genutzt_a | genutzt_b) == set()` gegen die echten, aus beiden Goldens gesammelten Mengen.

**Mutations-Gegenprobe — Produktcode**

| Mutation | Ort | Welcher Test wird rot |
|---|---|---|
| M1-real: `_sorted_by_layout`-Sortkey invertiert | src/app/models.py:822 | hauptmatrix, ac2, ac9_m1, ac10 |
| M2-real: Clip-Aufruf am `per_channel`-Aufrufort entfernt | src/app/models.py:983-988 | hauptmatrix, ac2, ac9_m2, ac10 |
| M3-real: `build_friendly_keys(dc)` → `set()` | src/output/renderers/trip_report.py:142 | hauptmatrix, ac9_m3, ac10 |
| Route: E-Mail liest `"sms"`-Layout | src/output/renderers/trip_report.py:136 | hauptmatrix, ac2, ac9_m3, ac10 |

**Finding F003 (MEDIUM): AC-12 deckt nur email_plain/golden_b ab**, Hauptmatrix überspringt Platzhalter (`ist_modus is None`).
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:566-597
Remediation: auf beide Goldens und alle sechs Kanäle ausweiten.

**Finding F004 (LOW): AC-13 prüft nur Substring „45"**, nicht die Zuordnung zur gust-Zelle.
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:615-627

**Finding F005 (LOW, latent): `bucket`-Default Modell `"primary"` vs. Orakel `"secondary"`.**
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:326

## Mutationstabelle (Zusammenfassung)

| # | Mutation | Fang |
|---|---|---|
| A | Bogus-Register-Eintrag ins echte `AUSNAHMEN` | KEIN Test → F002 |
| B | B3-Eintrag entfernt | hauptmatrix, ac10 |
| C | gust → `metrik="*"` | ac5 (Zufall) |
| M1-real | Sortkey invertiert | hauptmatrix, ac2, ac9_m1, ac10 |
| M2-real | Clip entfernt | hauptmatrix, ac2, ac9_m2, ac10 |
| M3-real | friendly_keys leer | hauptmatrix, ac9_m3, ac10 |
| Route | E-Mail ← SMS-Layout | hauptmatrix, ac2, ac9_m3, ac10 |

Verdict Runde 1–2: BROKEN — F002 (HIGH) und F001 (MEDIUM, Spec-Verstoß) blockieren; F003/F004/F005 ergänzend.

### Runde 3

**Testlauf (Fix-Loop 1):** 18 passed. Artefakt: `docs/artifacts/fix-2422-konfig-auslieferung-testluecken/adversary-test-output.txt`. `git diff --stat`: nur `docs/reference/gates_und_ratschen.md`, `tests/helpers/einstellung_auslieferung_orakel.py`, `tests/tdd/test_einstellung_gleich_auslieferung.py`.

**F001 — VERIFIED GEFIXT.** `inspect.getsource`-Check entfernt; AC-3 über M1-Verhaltensbeleg.
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:371-397
Status: CONFIRMED

**F002 — VERIFIED GEFIXT.** Neuer Test `test_ac6_ac7_echtes_register_hat_keine_unbenutzten_eintraege` prüft das ECHTE `AUSNAHMEN` über beide Goldens.
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:303-321
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:630-638
Status: CONFIRMED (Mutation A wird rot)

**F003 — VERIFIED GEFIXT.** AC-12 über beide Goldens × erreichbare Kanäle; Ausnahme nur `(thunder, email_html)`.
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:592-628
Status: CONFIRMED

**F004 — VERIFIED GEFIXT.** `roh_wert_der_metrik` prüft den Wert an der gust-Position.
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:576-609
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:631-664
Status: CONFIRMED (Mutation NEU 2 wird von AC-13 gefangen)

**F005 — VERIFIED GEFIXT.** Orakel-Default `bucket="primary"` wie `MetricConfig`.
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:326
Code reference: src/app/models.py:685
Status: CONFIRMED

### Runde 4

| # | Mutation | Ort | Welcher Test wird rot |
|---|---|---|---|
| A | Bogus-Eintrag ins echte `AUSNAHMEN` | tests/helpers/einstellung_auslieferung_orakel.py:66 | ac6_ac7_echtes_register (+ ac5 Nebeneffekt) |
| M1-real | Sortkey invertiert | src/app/models.py:822 | hauptmatrix, ac2, ac9_m1, ac10 |
| M2-real | Clip entfernt | src/app/models.py:988 | hauptmatrix, ac9_m2, ac10 (Korrektur R2: ac2 nicht) |
| M3-real | friendly_keys leer | src/output/renderers/trip_report.py:142 | hauptmatrix, ac9_m3, ac10 |
| Route | E-Mail ← SMS-Layout | src/output/renderers/trip_report.py:136 | hauptmatrix, ac2, ac6_ac7, ac9_m3, ac10 |
| NEU 1 | Zeit-Spalte nicht entfernt (synchron) | tests/helpers/einstellung_auslieferung_orakel.py:427 | keiner — harmlos, keine Fehlzuordnung |
| NEU 2 | Label/Wert-Versatz in `roh_wert_der_metrik` | tests/helpers/einstellung_auslieferung_orakel.py:606 | ac13 |
| C | gust-Eintrag → `metrik="*"` | tests/helpers/einstellung_auslieferung_orakel.py:177 | nur ac5 (Zufall über Vakuum-Schutz) |

**Finding F006 (MEDIUM):** Verbreiterung eines metrikscharfen Register-Eintrags auf `metrik="*"` wird von AC-6/AC-7/AC-10 nicht erkannt; `metrik="*"` ist laut Spec nur für B2 (kanalweit) vorgesehen.
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:630-638
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:194-232
Remediation: Test „jeder `*`-Eintrag hat befund B2" (Allow-Liste kanalweiter Befunde).

Verdict Runde 3–4: AMBIGUOUS — F001–F005 behoben, F006 offen → Fix-Loop 2.

### Runde 5

**Testlauf (Fix-Loop 2):** 19 passed. Artefakt: `docs/artifacts/fix-2422-konfig-auslieferung-testluecken/adversary-test-output.txt`.

**F006 — VERIFIED GEFIXT.** `KANALWEITE_BEFUNDE = frozenset({"B2"})` + Prüfung in `register_validieren` blockt `metrik="*"`-Einträge mit befund≠B2 vor der Matrix; Spy belegt Aufruf im echten Hauptmatrix-Pfad.
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:54
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:665
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:361-410
Status: CONFIRMED (Mutation C: 9 von 19 Tests rot)

**Finding F007 (MEDIUM):** `register_validieren` prüft bei Wildcard-Einträgen nur das befund-Label, nicht den (Kanal, Dimension)-Scope; Spec begrenzt B2 auf sms/telegram_kurzform/premium_sms × roh_einfach. Umgehung `gust`→`metrik="*"`, `befund="B2"` bei telegram_rich/erscheint: nur ac5 rot (Zufall über Vakuum-Schutz).
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:67
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:645-653
Remediation: Allow-Liste je Befund `{befund: {(kanal, dimension), ...}}`.

**Regressionschecks:** Mutation A → genau ac6_ac7 rot. M1-real order-invert → hauptmatrix, ac2, ac9_m1, ac10. M1-real bucket-invert → keiner in dieser Suite, aber `tests/unit/test_mail_column_order.py` (#1575) rot — kein unbewachtes Loch.
Code reference: src/app/models.py:822

| # | Mutation | Welcher Test wird rot |
|---|---|---|
| C | gust→`*`, befund unverändert | 9 Tests inkl. hauptmatrix, ac8_f006 |
| F007-Umgehung | gust→`*`, befund="B2" | nur ac5 (Zufall) |
| A | Bogus-Eintrag | ac6_ac7 |
| M1 bucket-invert | `-_BUCKET_RANK` | test_mail_column_order.py (fremde Suite) |
| M1 order-invert | `-mc.order` | hauptmatrix, ac2, ac9_m1, ac10 |

Verdict Runde 5: AMBIGUOUS — F006 behoben, F007 offen → Fix-Loop 3 (letzter).

### Runde 6

**Testlauf (Fix-Loop 3, final):** 20 passed. Artefakt: `docs/artifacts/fix-2422-konfig-auslieferung-testluecken/adversary-test-output.txt`.

**F007 — VERIFIED GEFIXT, geprüft an der Wirkstelle.** `register_validieren` prüft bei `metrik="*"` Befund-Label UND (Kanal, Dimension)-Scope gegen `KANALWEITE_BEFUNDE["B2"]`; Aufruf im Hauptmatrix-Pfad `abweichungen_fuer_golden`.
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:57-92
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:684
Code reference: docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md:39
Status: CONFIRMED (F007-real im echten Register: 10 von 20 rot inkl. hauptmatrix)

**Finding F008 (LOW, Hinweis):** Erweiterung der Allow-Liste um eine spec-fremde Zelle allein bleibt unbemerkt; folgenlos ohne zugehörigen Register-Eintrag, in Kombination fängt `test_ac6_ac7_echtes_register_hat_keine_unbenutzten_eintraege`. Kein AC-Verstoß → Sammel-Issue #1199.
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:57-63
Code reference: tests/tdd/test_einstellung_gleich_auslieferung.py:303-321

**Regression:** Mutation A → genau ac6_ac7 rot. M1-real order-invert → hauptmatrix, ac2, ac9_m1, ac10.
Code reference: src/app/models.py:822

Bestätigung: F006 weiterhin wirksam, keine Regression.
Code reference: tests/helpers/einstellung_auslieferung_orakel.py:76-83
Status: CONFIRMED

| # | Mutation | Fang |
|---|---|---|
| F007-real | gust → `*`, befund B2, im echten Register | 10 Tests inkl. hauptmatrix, ac8_f007 |
| Scope+telegram_rich | Allow-Liste erweitert | ac8_f007 |
| Scope+email_html allein | Allow-Liste erweitert | keiner → F008 LOW |
| Scope+email_html + Eintrag | zusätzlich passender `*`-Eintrag | ac6_ac7 |
| A | Bogus-Eintrag | ac6_ac7 |
| M1-real | order-invert | hauptmatrix, ac2, ac9_m1, ac10 |

VERDICT: VERIFIED — F001–F007 an der Wirkstelle geprüft und gefangen; 20/20 grün; F008 LOW ohne AC-Verstoß, kein Blocker.

## Geprüfte Dateien

- sha256:cb6134634aa06408d76ec8e09bc2b867d7f07f1d92eb561b4441a49ab9126602  docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md
- sha256:aa5e63c893823a134e0c5f90440055fbce74ee2bb39b87a8bdd7c09d8d2b3e05  src/app/models.py
- sha256:ba621af35d0872d41426529135ae5c6e004b3a0f25270be13879e4c9a73e2c1e  src/output/renderers/channel_layout.py
- sha256:2f98ae6008b2cf9028780d2ef521c458581539c5018ca7b4f397ae7bf99288cd  src/output/renderers/trip_report.py
- sha256:2737e30d96f2d5c9642ebbf44ccdb460d6585ac6f8727d2c50f402be306159f1  tests/helpers/einstellung_auslieferung_orakel.py
- sha256:e032b6aae576625b96fdebfdb9f2c9a2cd9602f0aeac2d9e0dbbf7175710ff75  tests/tdd/test_einstellung_gleich_auslieferung.py
