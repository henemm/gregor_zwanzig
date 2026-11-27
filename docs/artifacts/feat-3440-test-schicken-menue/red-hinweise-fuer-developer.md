# RED #3440 – Vertrag und Hinweise für die GREEN-Phase

## Testdateien
- tests/tdd/test_briefings_send_endpoint.py (Abschnitt test_3440_*)
- internal/handler/briefing_send_test.go (TestBriefingSend3440_*)
- frontend/src/lib/components/molecules/__tests__/test_schicken_modell.test.ts
- frontend/src/lib/utils/__tests__/send_channel_3440.test.ts
- frontend/src/lib/components/shared/hub-kopf/__tests__/test_schicken_menue_bindung.test.ts
- frontend/e2e/hub-send-menue.staging.spec.ts (+ frontend/playwright.3440-test-menue.staging.config.ts), nur --list geprüft

RED: Python 34 neu rot / 64 Bestand grün; Go 3 Tests (22 Subtests) rot / 11 grün; node --test 48 rot.

## API testSchickenModell.ts (Vertrag im Testkopf)
- testMenueModell(profil, context: 'route'|'vergleich', berichtsart='morning') -> {segment|null, zeilen[email,telegram,sms,premium_sms], alle:{text}, erweiterungen:[]}
- TestZeile {kanal,name,bedienbar,ziel,grund,sperrText (tr('zustellung.gesperrt',{grund})),kontoLink:null|{verb,text,href:'/account'}}
- einzelRueckmeldung({context,berichtsart,kanal,ziel,jetzt}); alleRueckmeldung({context,berichtsart,sentChannels,profil})
- briefingSendUrl(kind,id,reportType?,channel?); sendSubscription(kind,id,{reportType?,channel?},fetchFn); SendRunResult.sentChannels?
- HubKopf: subscription-hub-send aria-haspopup="menu", aria-expanded, kein onSend; Seiten reichen onTest (Trip über TripHeader); testids test-schicken-ok / test-schicken-fehler

## Hinweise
- Kontingent: Cache-Treffer wird erstattet; Test leert Wetter-Cache per reset_shared_weather_cache_for_tests zwischen Klicks.
- 409 heißt in Python already_in_progress (already_running = Frontend-Klassifikation).
- Tarif ohne SMS muss channels_unreachable liefern (Trip-Naht liefert heute evtl. no_channels).
- Go-Fehlercode invalid_channel braucht Katalogtext fach.fehler.invalid_channel*.
- Bestandstests test_ac10_*, test_ac13_alt_route_* brechen durch sent_channels -> in GREEN umstellen, ebenso die Bestandsliste aus dem Test Plan der Spec (umstellen, nicht löschen).
