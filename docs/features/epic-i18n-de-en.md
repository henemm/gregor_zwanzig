# Epic 2644: Zweisprachigkeit Deutsch/Englisch

**Status:** Geplant (2026-10-30) — Specs geschrieben, warten auf Block-Freigabe; Umsetzung autonom in einer Sitzung (Kern Sonnet, Migration Haiku)
**Epic Scope:** Web-UI, E-Mail, Telegram (Normalstil), Inbound-Befehle und -Antworten, Go-API-Meldungen, Konto-/Transaktions-Mails sprechen Deutsch **und** Englisch. Die Sprache ist eine Konto-Einstellung (`language`), vorbelegt aus dem Browser. Protokoll-Token, Kurzformen und Eigennamen werden nie übersetzt. **Präzisierung PO 2026-10-31 (ADR-0104): Die Kurzform von SMS, Premium-SMS und Telegram bleibt in JEDER Sprache unverändert; SMS-/Premium-SMS-Freitext (P8, #2670) entfällt.**
**Grundsatz:** `docs/adr/0104-zweisprachigkeit-de-en.md` · **Konventionen (verbindlich, schließt alle Entwurfsfragen):** `docs/features/epic-i18n-de-en-konventionen.md` · **Glossar:** `docs/reference/i18n_glossar.md` · **Issues:** Epic #2644 mit 32 Sub-Issues (#2645–#2681) · **Specs:** `docs/specs/modules/i18n_*.md` (Block-Freigabe, Abschnitt unten)
**PO-Auftrag:** 2026-10-30 („Erstelle einen Plan, wie du Gregor Zwanzig multilingual erstellst … Umsetzung später durch Agenten mit Haiku, wenn ausreichend"); Rückfragen per `AskUserQuestion` beantwortet (Sprachwahl, Umfang, Technik, Ablage).

---

## Leitbild

Ein Nutzer wählt einmal seine Sprache; danach spricht **jede** Fläche und **jeder** Kanal diese
Sprache mit demselben Inhalt (Kanal-Parität ADR-0095). Was Maschinen lesen oder was in 160 Zeichen
passen muss (`sms_code`, `compact_label`, Kürzel, `col_label`), bleibt unverändert (ADR-0042
Klasse 1 und Kurzform). Deutsch bleibt byte-gleich zur heutigen Ausgabe.

## Architektur der Lösung

```
user.json: language ─┬─> Go     internal/i18n      T(lang,key)   Handler, Konto-Mails, Fehler {code,message}
                     ├─> Python src/i18n           t(key,lang)   Renderer aller Kanäle, Inbound, API-detail
                     └─> Svelte $lib/i18n           t(key)        locale-Store aus +layout (user > Cookie > Accept-Language > de)
Metrik-Register: label_de / label_en · alert_label / alert_label_en   (col_label, sms_code, compact_label eingefroren)
Mail: Header X-GZ-Lang ──> Validatoren bilden Erwartungen aus dem Python-Katalog
```

- **Ein Auflösungsweg je Schicht:** `resolve_user_lang(user_id)` (Python), `i18n.FromContext(ctx)` (Go), `locals.lang` (SvelteKit). Kein zweiter Weg, kein globaler Zustand (zwei Nutzer im selben Scheduler-Lauf).
- **Kataloge:** flache, bereichs-präfixierte Schlüssel in JSON je Sprache **und Bereich**, damit Migrationspakete parallel ohne Dateikonflikt arbeiten. Platzhalter `{name}`, Plural `.one`/`.other`, Fallback Deutsch mit einmaligem Log. Paritätstest je Katalog.
- **Ratschen:** je Schicht ein Test gegen hartkodierte Nutzertexte mit schrumpfender Allowlist (S4, P11, G5).
- **Kurzform ist Platzform:** Telegram-Kurzstil und Premium-SMS bleiben für beide Kontosprachen vollständig englisch wie heute (#2417 AC-4); Nutzersprache wirkt nur in Langform-Kanälen (Spec P10). Präzisierung PO 2026-10-31: auch die SMS-Kurzform ist nie sprachabhängig, P8 entfällt (ADR-0104, Abschnitt „Präzisierung 2026-10-31“).

## Ist-Stand (gemessen 2026-10-30)

| Schicht | Befund |
|---|---|
| Frontend | 256 Svelte-Dateien; Katalog #2520 (`frontend/src/lib/i18n`, 112 Schlüssel, nur `de`, 9 Importeure); `app.html` fest `lang="de"`; deutsche Textzeilen: `components/shared/` ≈ 4.800, `compare/` ≈ 1.280, `routes/` ≈ 1.150, `trip-detail/` ≈ 700, `utils`+`stores` ≈ 700, Rest < 300 je Bereich |
| Python | 535 deutsche Literale in `src/output` + `src/services`; `trip_report_scheduler.py` 171 · `trip_command_processor.py` 146 · `channels/email.py` 122 · `metric_catalog.py` 80 · `alert/official_alerts.py` 79 · `notification_service.py` 78 · `email/html.py` 71; 40× `%d.%m.`; `UserPreferences.language` ungenutzt |
| Go | Grobmessung 471 Literale mit Umlaut (inkl. Kommentare); Spec-Messung: nur **57 Nutzertexte**, ~416 Fehlerstellen antworten mit englischen Codes (`error`-Feld) — G2/G3 übersetzen überwiegend Codes → Katalog statt deutscher Altexte; `model.User` ohne Sprachfeld |
| Inbound | #2417: `wort_en`, `kuerzel_bedeutung_en` vorhanden; `self._en` = Kurzform-Kanal |
| Validatoren | 4 Mail-Validatoren mit 31 deutschen Literal-Erwartungen |
| Entscheidungen | #94 gestrichen 2026-08-04 („lebt in ADR-0042 weiter"); #2520: eigener Katalog, kein Paraglide (2026-10-07) |

## Phasen, Pakete, Abhängigkeiten

| Phase | Paket | Issue | Modell | Abhängig von |
|---|---|---|---|---|
| 0 Fundament | S0 ADR-0104 freigeben, Glossar, api_contract | #2645 | Sonnet | — |
| 0 | S1 Sprachfeld `language` am Nutzer (Go+Python) | #2646 | Sonnet | S0 |
| 0 | S2 Frontend-Sprachkern | #2647 | Sonnet | S1 |
| 0 | S3 Sprachumschalter + Konto | #2648 | Haiku | S1, S2 |
| 0 | S4 Ratsche Frontend | #2649 | Sonnet | S2 |
| 1 Web-UI | F1 Auth-Routen | #2650 | Haiku | S2, S4 |
| 1 | F2 Hilfe, Onboarding, Begriffserklärungen | #2651 | Haiku | S2, S4 |
| 1 | F3 Home/Cockpit, Listen | #2652 | Haiku | S2, S4 |
| 1 | F4 Konto, Admin, Sidebar | #2653 | Haiku | S3, S4 |
| 1 | F5 Wertebereiche-Tab | #2654 | Haiku | S4, P1 |
| 1 | F6 Versand-Tab | #2655 | Haiku | S4 |
| 1 | F7 Alarme-Tab | #2656 | Haiku | F5 |
| 1 | F8 Layout-Tab, Korridor | #2657 | Haiku | S4 |
| 1 | F9 Trip-Flächen | #2658 | Haiku | F5–F8 |
| 1 | F10 Ortsvergleich-Flächen | #2659 | Haiku | F9 |
| 1 | F11 Bausteine, TS-Texte, Fehlercodes | #2660 | Haiku | S4 |
| 1 | F12 Frontend-Abschluss (E2E, Screenshots) | #2661 | Sonnet | F1–F11 |
| 2 Python | P1 i18n-Kern, Metrik-Register, `/api/metrics` | #2662 | Sonnet | S1 |
| 2 | PV Mail-Validatoren sprachfähig | #2663 | Sonnet | P1 |
| 2 | P2 Trip-Briefing-Mail HTML | #2664 | Haiku | PV |
| 2 | P3 Trip-Briefing compact/plain + Hinweise | #2665 | Haiku | P2 |
| 2 | P4 Vergleichs-Mail | #2666 | Haiku | PV |
| 2 | P5 Abweichungs-/Radar-Alarme | #2667 | Haiku | PV |
| 2 | P6 Amtliche Warnungen | #2668 | Haiku | PV |
| 2 | P7 Telegram | #2669 | Haiku | P1 |
| 2 | ~~P8 SMS/Premium-SMS-Freitext~~ **entfällt** (PO 2026-10-31, Kurzform unverändert) | #2670 | — | — |
| 2 | P9a Versand-Schicht (keine Sprachumschaltung der Kurzform) | #2671 | Haiku | PV |
| 2 | P9b Scheduler/Alarm-Orchestrierung (keine Sprachumschaltung der Kurzform) | #2672 | Haiku | P2–P7 |
| 2 | P10 Inbound (keine Sprachumschaltung der Kurzform) | #2673 | Sonnet | P1 |
| 2 | P11 API-Meldungen + Ratsche Python | #2674 | Haiku | P1 / P2–P10 |
| 3 Go | G1 i18n-Kern, Kontext, `code`+`message` | #2675 | Sonnet | S1 |
| 3 | G2 Handler Auth/Konto | #2676 | Haiku | G1 |
| 3 | G3 Handler Fachlogik, store/middleware | #2677 | Haiku | G1 |
| 3 | G4 Konto-Mails, notify, scheduler | #2678 | Haiku | G1 |
| 3 | G5 Ratsche Go | #2679 | Haiku | G1 |
| 4 Abschluss | A1 Doku, CLAUDE.md-Zeile | #2680 | Haiku | F12, P11, G5 |
| 4 | A2 E2E zweisprachig, Marker Pflicht | #2681 | Sonnet | A1 |

**Kritischer Pfad:** S0 → S1 → {S2 → S4 → F…; P1 → PV → P2… → P9b; G1 → G…} → A1 → A2.
**Parallelität:** drei Worktrees (Frontend, Python, Go) nach Phase 0; Querbezug nur F5/F7 ← P1.
**Modellwahl:** Sonnet für Kern, Validatoren, Inbound, E2E (10 Pakete); Haiku für 22 Migrationspakete. Adversary (`implementation-validator`) bleibt Sonnet. Haiku scheitert zweimal → Sonnet (Workflow-Regel).

## Spezifikationen und Block-Freigabe (PO-Entscheid 2026-10-30)

Alle 32 Specs liegen vor der Umsetzung in `docs/specs/modules/` (Format `_template.md`, ACs auf Deutsch,
`created: 2026-10-30`). Der PO gibt sie **einmal im Block** frei: Kommentar `freigabe i18n-specs` im Epic #2644
oder Häkchen `- [x] Approved` in den Dateien. Die erste Umsetzungs-Sitzung setzt daraufhin in allen Specs
`- [x] Approved (PO-Freigabe <Datum>)` und `status: approved` in einem Commit. Danach läuft die Umsetzung ohne
PO-Frage; einzige Unterbrechung ist ein gescheitertes Hard Gate (Konventionen Abschnitt 7).

| Paket | Spec | Paket | Spec |
|---|---|---|---|
| S0 #2645 | `i18n_s0_adr_glossar_2645.md` | P2 #2664 | `i18n_p2_briefing_mail_html_2664.md` |
| S1 #2646 | `i18n_s1_sprachfeld_nutzer_2646.md` | P3 #2665 | `i18n_p3_briefing_compact_plain_2665.md` |
| S2 #2647 | `i18n_s2_frontend_sprachkern_2647.md` | P4 #2666 | `i18n_p4_vergleichs_mail_2666.md` |
| S3 #2648 | `i18n_s3_sprachumschalter_konto_2648.md` | P5 #2667 | `i18n_p5_abweichungs_radar_alarme_2667.md` |
| S4 #2649 | `i18n_s4_ratsche_frontend_2649.md` | P6 #2668 | `i18n_p6_amtliche_warnungen_2668.md` |
| F1 #2650 | `i18n_f1_auth_routen_2650.md` | P7 #2669 | `i18n_p7_telegram_2669.md` |
| F2 #2651 | `i18n_f2_hilfe_infobox_2651.md` | ~~P8 #2670~~ | `i18n_p8_sms_freitext_2670.md` (superseded) |
| F3 #2652 | `i18n_f3_home_listen_2652.md` | P9a #2671 | `i18n_p9a_versand_schicht_2671.md` |
| F4 #2653 | `i18n_f4_konto_admin_nav_2653.md` | P9b #2672 | `i18n_p9b_scheduler_orchestrierung_2672.md` |
| F5 #2654 | `i18n_f5_wertebereiche_tab_2654.md` | P10 #2673 | `i18n_p10_inbound_2673.md` |
| F6 #2655 | `i18n_f6_versand_tab_2655.md` | P11 #2674 | `i18n_p11_api_meldungen_ratsche_2674.md` |
| F7 #2656 | `i18n_f7_alarme_tab_2656.md` | G1 #2675 | `i18n_g1_go_kern_2675.md` |
| F8 #2657 | `i18n_f8_layout_korridor_2657.md` | G2 #2676 | `i18n_g2_go_handler_auth_2676.md` |
| F9 #2658 | `i18n_f9_trip_flaechen_2658.md` | G3 #2677 | `i18n_g3_go_handler_fach_2677.md` |
| F10 #2659 | `i18n_f10_vergleich_flaechen_2659.md` | G4 #2678 | `i18n_g4_go_mails_2678.md` |
| F11 #2660 | `i18n_f11_bausteine_ts_2660.md` | G5 #2679 | `i18n_g5_ratsche_go_2679.md` |
| F12 #2661 | `i18n_f12_frontend_abschluss_2661.md` | A1 #2680 | `i18n_a1_doku_2680.md` |
| P1 #2662 | `i18n_p1_python_kern_metrik_2662.md` | A2 #2681 | `i18n_a2_e2e_zweisprachig_2681.md` |
| PV #2663 | `i18n_pv_mail_validatoren_2663.md` | | |

## Autonomer Ablauf (PO-Entscheid 2026-10-30: eine Sitzung, Pakete nacheinander)

Vollständig in den Konventionen, Abschnitte 7–9. Kurzfassung:

1. Nächstes Paket = erstes offenes in der **Reihenfolge** unten, dessen Abhängigkeiten geschlossen sind.
2. Je Paket: `/01-feature <issue>` → `/10-context` → `/20-analyse` → `/30-write-spec` (vorhandene Spec nur validieren) → `/40-tdd` → `/50-implement` (Developer-Agent im Modell des Spec-Kopfs) → `/60-validate` (Adversary Sonnet) → PR/Merge → `/70-deploy` → `/clear`.
3. Haiku scheitert zweimal → Sonnet. Hard Gate scheitert → Rollback, Kommentar in Paket-Issue und Epic, Halt.
4. Englische Texte prüft der Adversary gegen das Glossar; kein PO-Review (PO-Entscheid).
5. Zweiter Staging-Nutzer `en` entsteht autonom per Subadressierung und Register-API; Telegram-Prüfung per Sprach-Umschalten des Testnutzers (Konventionen Abschnitt 6).

**Reihenfolge:** S0 → S1 → S2 → S4 → S3 → P1 → PV → G1 → F1 → F11 → F2 → F3 → F4 → F6 → F8 → F5 → F7 → F9 → F10 → P2 → P3 → P4 → P5 → P6 → P7 → P9a → P9b → P10 → P11 → G2 → G3 → G4 → G5 → F12 → A1 → A2.

## Was jedes Haiku-Paket im Briefing braucht

1. Issue-Nummer, `OPENSPEC_ACTIVE_WORKFLOW`, freigegebene Spec mit ACs.
2. Zielbereich (Dateiliste) und Katalog-Namensraum; Allowlist-Eintrag, der zu entfernen ist.
3. Eine **Beispiel-Umstellung** aus dem Kern-Paket (vorher/nachher, Platzhalter, Plural).
4. Glossar-Pfad und das Verbot „Tour".
5. Golden-Regel: deutsche Ausgabe byte-gleich; Token-Wächter grün; Validator in beiden Sprachen.

## Risiken und Gegenmittel

| Risiko | Gegenmittel |
|---|---|
| Englische Texte länger → Layout-Brüche, SMS > 160 Zeichen | F12 Screenshot-Paare + Fresh-Eyes; SMS-Kurzform unverändert (Token-Wächter, kein Längenrisiko) |
| Validatoren brechen bei erster englischer Mail (Lehre #1381/#1404/#1420) | PV **vor** allen Mail-Renderer-Paketen; Marker `X-GZ-Lang` |
| Parallel-Pakete kollidieren im Katalog | Katalog je Bereich (eigene Datei je Paket) |
| Haiku übersetzt frei oder uneinheitlich | Glossar bindend; Adversary prüft Glossar-Konformität; Paritätstest |
| Zweiter Auflösungsweg / globaler Sprachzustand → falsche Sprache bei zweitem Nutzer | Eine Funktion je Schicht; Cross-User-Test in S1, P9a, P9b, G1 |
| Token unbemerkt verändert | Eingefrorene Fixture `metric_tokens_frozen.json` (P1) |
| CLAUDE.md-Budget | A1: eine Zeile, Budget-Test |

## Nicht Teil dieses Epics

Weitere Sprachen (neues ADR), Übersetzung amtlicher Warntexte (nur Quell-Block-Wahl), Übersetzung der Dokumentation (`docs/` bleibt deutsch), Übersetzung von Orts-/Regionsnamen, Admin-Mails an den Betreiber (bleiben deutsch).
