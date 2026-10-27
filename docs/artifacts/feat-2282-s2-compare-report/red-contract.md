# RED-Vertrag feat-2282-s2-compare-report (#2282 S2)

RED-Lauf: `test-red-output.txt` — 104 failed, 527 passed, 0 errors (alle Fehlschläge AssertionError, keine Collection-Fehler).

## Absichtlich grüne Tests (Regressionswächter)
- `test_ac10_telegram_mit_tripnamen_bedient_nicht_den_vergleich` (Gegenprobe)
- `test_ac11_nur_trip_bleibt_unveraendert_beim_trip` (×6), `test_ac11_query_befehle_bleiben_trip_only` (glance, gewitter)
- `test_kanaltreue_adhoc_antwort.py` (17, unverändert), `test_befehle_telegram_e2e.py`, `test_befehle_premium_sms_e2e.py`, `test_trip_eingang_regressionskontrolle.py`, `test_vergleich_pause_weiter.py`

## Was /50 erfüllen muss (von den Tests festgelegt)
1. `services.user_tier.resolve_restricted_channel_flags(restrict, user_id)` → `(email, sms, premium_sms, telegram)`, identisch zum bisherigen Trip-Tupel. AC-7 prüft gegen die feste Tabelle `ERWARTET_FLAGS` (aus dem heutigen Trip-`_resolve_channel_flags` abgelesen).
2. `services.compare_slot_scheduler.preset_ortstag(preset: dict, all_locations: dict[id→SavedLocation], now_utc: datetime) -> date`.
3. `send_compare_preset(user_id, preset_id, …, restrict_to_channel=<kanal>)` als Keyword-Argument (plus `tage_ab_ortstag`).
4. Zieltag aus `msg.received_at`, nicht aus der Systemuhr (sonst AC-3 rot).
5. Anfragekanal per Tarif gesperrt (Premium-SMS ohne Premium-Tarif) → `channels_unreachable`, nicht `no_channels`.
6. SMS-Tageslimit ausgeschöpft → Absage mit Label „Ortsvergleich".
7. `invalid_preset` erzeugt der Prozessor aus `ValueError`/`KeyError` von `send_compare_preset` (kein `SendOutcomeError` dafür).
8. Jeder Code trägt „Ortsvergleich" in Betreff oder Text, auch die `report`-Tabelle; `\bTrip\b` darf nicht vorkommen (auch nicht „Trip-Editor"); die fünf Code-Texte sind paarweise verschieden.
9. Teilausfall: Orte mit `lr.error` (keine Wetterdaten) werden beim Namen genannt → Fehler je Ort aus dem Dispatch nach oben durchreichen; gelöschte Orte als ID.
10. Ladehinweis am Vergleich auch für `report` (obwohl nicht in `_QUERY_KEYS`); Trip-`report` bleibt ohne Ladehinweis.
11. heute/morgen setzen bei Erfolg `suppress_email_reply=True` (unterdrückt auch die zweite Premium-SMS).
12. Antwort-Betreffs am Vergleich tragen den Vergleichsnamen (e2e L4/report sucht ihn im Telegram-Text).
13. Sowohl `kinds` in `_COMMAND_SPECS` (Hilfe) als auch `_BEIDE_KINDS_ONLY_SCHLUESSEL` bekommen report/heute/morgen. Telegram-Knöpfe (Callback-Pfad über `resolve_trip_only_target`) bleiben trip-only.

## Offene Punkte für Staging
- AC-4 im Kern nur auf Prozessor-Ebene (`suppress_email_reply` + genau eine Compare-Mail an der Transport-Naht); „keine zweite Mail im Postfach" über den echten E-Mail-Eingang ist Staging-Punkt.
- Kein eigener SMS-Eingang (Reader nimmt nur Premium-SMS an) → AC-5 läuft über den Prozessor mit `channel="sms"`.
- AC-13 und AC-16 sind reine Staging-Schicht, kein Kern-Ersatztest.
