// TDD: Issue #1232 Scheibe 1 — Adversary-Fund F002 (BROKEN → Fix).
//
// Beweist: buildAlertDeliveryPayload() liefert IMMER alle 5 Alert-
// Zustellungsfelder in EINEM Objekt — die Grundlage dafür, dass VersandTab
// nur EINEN gemeinsamen saveController.schedule()-Aufruf für die gesamte
// Alert-Zustellung braucht (statt 3 unabhängiger, die sich den einzigen
// Debounce-Slot gegenseitig überschreiben würden).
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/alertDeliveryPayload.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildAlertDeliveryPayload } from './alertDeliveryPayload.ts';

test('#1232 F002: buildAlertDeliveryPayload enthält alle 5 Felder in einer Payload', () => {
	const payload = buildAlertDeliveryPayload({
		officialAlertsEnabled: true,
		officialAlertTriggersEnabled: false,
		cooldownMinutes: 60,
		quietFrom: '22:00',
		quietTo: '06:00'
	});
	assert.deepEqual(payload, {
		official_alerts_enabled: true,
		official_alert_triggers_enabled: false,
		alert_cooldown_minutes: 60,
		alert_quiet_from: '22:00',
		alert_quiet_to: '06:00'
	});
});

test('#1232 F002: fehlende Cooldown/Quiet-Werte werden zu null (kein undefined im PUT-Body)', () => {
	const payload = buildAlertDeliveryPayload({
		officialAlertsEnabled: false,
		officialAlertTriggersEnabled: true,
		cooldownMinutes: undefined,
		quietFrom: undefined,
		quietTo: undefined
	});
	assert.equal(payload.alert_cooldown_minutes, null);
	assert.equal(payload.alert_quiet_from, null);
	assert.equal(payload.alert_quiet_to, null);
	assert.equal(payload.official_alerts_enabled, false);
	assert.equal(payload.official_alert_triggers_enabled, true);
});

test('#1232 F002: zwei rasch aufeinanderfolgende Änderungen ergeben EINE Payload mit BEIDEN neuen Werten (kein Verwerfen)', () => {
	// Simuliert: Nutzer togglet "Amtliche Warnungen" (a) und danach, noch
	// innerhalb des Debounce-Fensters, "Cooldown" (b). Da VersandTab bei jeder
	// Änderung buildAlertDeliveryPayload() mit dem GESAMTEN aktuellen Zustand
	// aufruft, enthält die zuletzt geplante Payload zwangsläufig beide
	// Änderungen — es gibt keinen Zwischenschritt, der nur EIN Feld sendet.
	const afterFirstChange = buildAlertDeliveryPayload({
		officialAlertsEnabled: false,
		officialAlertTriggersEnabled: true,
		cooldownMinutes: undefined,
		quietFrom: undefined,
		quietTo: undefined
	});
	const afterSecondChange = buildAlertDeliveryPayload({
		officialAlertsEnabled: false,
		officialAlertTriggersEnabled: true,
		cooldownMinutes: 90,
		quietFrom: undefined,
		quietTo: undefined
	});
	// Die zweite (finale) Payload enthält weiterhin die erste Änderung UND die neue.
	assert.equal(afterSecondChange.official_alerts_enabled, false);
	assert.equal(afterSecondChange.alert_cooldown_minutes, 90);
	assert.notDeepEqual(afterFirstChange, afterSecondChange);
});
