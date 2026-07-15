// TDD RED — Issue #1258 Scheibe S3: F003-Nachzug (S2-Adversary, #1199).
// `alarmeDeliveryPayload.ts`s Laufzeit-Guard prüft heute NUR
// `officialWarningsEnabled` auf einen echten boolean — `officialAlertsEnabled`
// kann unbemerkt undefined/Nicht-boolean sein und würde als solches in die
// PUT-Payload durchgereicht. S3 spiegelt den Guard symmetrisch.
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (Implementation Details Abschnitt 9 "S3-Detail-Festlegungen",
//   Punkt "F003-Nachzug")
// Vorbild (Guard-Muster für officialWarningsEnabled, bereits grün):
//   frontend/src/lib/components/shared/__tests__/alarme_delivery_consolidated_save.test.ts
//
// RED-Ursache: `buildAlarmeDeliveryPayload` (alarmeDeliveryPayload.ts:31-36)
// wirft aktuell ausschließlich bei nicht-boolean `officialWarningsEnabled` —
// für `officialAlertsEnabled` existiert kein Guard, die Funktion baut die
// Payload klaglos und wirft NICHT, weshalb `assert.throws` unten fehlschlägt.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_delivery_guard_symmetry.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildAlarmeDeliveryPayload } from '../alarme-tab/alarmeDeliveryPayload.ts';

test('#1258 S3 F003-Nachzug: buildAlarmeDeliveryPayload wirft bei Nicht-boolean officialAlertsEnabled (Guard-Symmetrie zu officialWarningsEnabled)', () => {
	assert.throws(() => {
		buildAlarmeDeliveryPayload({
			officialAlertsEnabled: 'true' as unknown as boolean,
			officialWarningsEnabled: true,
			channels: { email: true, telegram: false, sms: false }
		});
	}, /officialAlertsEnabled/);
});

test('#1258 S3 F003-Nachzug: buildAlarmeDeliveryPayload wirft bei fehlendem (undefined) officialAlertsEnabled (kein stiller Default)', () => {
	assert.throws(() => {
		buildAlarmeDeliveryPayload({
			officialAlertsEnabled: undefined as unknown as boolean,
			officialWarningsEnabled: true,
			channels: { email: true, telegram: false, sms: false }
		});
	}, /officialAlertsEnabled/);
});
