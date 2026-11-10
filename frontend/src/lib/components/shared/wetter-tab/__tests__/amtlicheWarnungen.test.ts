// TDD RED — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.1. AC-20 (Kern).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — Implementation Details §1 `amtlicheWarnungen.ts`
//
// Lese-Regel (ODER): ist `official_warnings` vorhanden (Objekt mit `enabled`), gilt
//   official_warnings.enabled || official_alerts_enabled;
// sonst `official_alert_triggers_enabled` (Default an, d. h. nur `false` schaltet aus).
// Schreib-Regel: setzt `official_alerts_enabled` und `official_warnings.enabled` auf denselben Wert;
// weitere Felder von `official_warnings` (z. B. `sources`) bleiben erhalten.
// Gleiche Felder bei Trip und Orts-Briefing (beide top-level am Abo).
//
// Festgelegte API (amtlicheWarnungen.ts):
//   type WarnFelder = { official_alerts_enabled?: boolean|null;
//                       official_warnings?: { enabled?: boolean; sources?: string[] } | null;
//                       official_alert_triggers_enabled?: boolean|null }
//   amtlicheWarnungenAn(abo: WarnFelder | null | undefined): boolean
//   amtlicheWarnungenFelder(an: boolean, abo: WarnFelder | null | undefined):
//       { official_alerts_enabled: boolean; official_warnings: { enabled: boolean; sources?: string[] } }
//
// RED heute: amtlicheWarnungen.ts existiert nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/amtlicheWarnungen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { amtlicheWarnungen } from './wetterTabDaten.ts';

const BOOL3 = [true, false, undefined] as const;

describe('AC-20: Lese-Regel Amtliche Warnungen (ODER, Fallback Default an)', () => {
	// Alle Kombinationen mit vorhandenem official_warnings.enabled
	for (const ow of [true, false]) {
		for (const alt of BOOL3) {
			for (const trig of BOOL3) {
				const soll = ow || alt === true;
				test(`ac20_lesen_ow_${ow}_alerts_${alt}_triggers_${trig}_ist_${soll}`, async () => {
					const w = await amtlicheWarnungen();
					const abo: Record<string, unknown> = { official_warnings: { enabled: ow, sources: ['meteoalarm'] } };
					if (alt !== undefined) abo.official_alerts_enabled = alt;
					if (trig !== undefined) abo.official_alert_triggers_enabled = trig;
					assert.equal(w.amtlicheWarnungenAn(abo), soll, `AC-20: ${JSON.stringify(abo)}`);
				});
			}
		}
	}

	test('ac20_altfelder_auseinander_bericht_an_alarm_aus_ist_an', async () => {
		const w = await amtlicheWarnungen();
		assert.equal(w.amtlicheWarnungenAn({ official_alerts_enabled: true, official_warnings: { enabled: false } }), true);
	});

	// Ohne official_warnings (fehlt oder null): official_alert_triggers_enabled, Default an
	for (const ow of [undefined, null]) {
		for (const alt of BOOL3) {
			for (const trig of BOOL3) {
				const soll = trig !== false;
				test(`ac20_fallback_ow_${ow}_alerts_${alt}_triggers_${trig}_ist_${soll}`, async () => {
					const w = await amtlicheWarnungen();
					const abo: Record<string, unknown> = {};
					if (ow !== undefined) abo.official_warnings = ow;
					if (alt !== undefined) abo.official_alerts_enabled = alt;
					if (trig !== undefined) abo.official_alert_triggers_enabled = trig;
					assert.equal(w.amtlicheWarnungenAn(abo), soll, `AC-20 Fallback: ${JSON.stringify(abo)}`);
				});
			}
		}
	}

	test('ac20_leeres_oder_fehlendes_abo_ist_an', async () => {
		const w = await amtlicheWarnungen();
		assert.equal(w.amtlicheWarnungenAn({}), true);
		assert.equal(w.amtlicheWarnungenAn(null), true);
		assert.equal(w.amtlicheWarnungenAn(undefined), true);
	});
});

describe('AC-20: Schreib-Regel setzt beide Felder gleich', () => {
	for (const an of [true, false]) {
		test(`ac20_schreiben_${an}_setzt_beide_felder`, async () => {
			const w = await amtlicheWarnungen();
			for (const abo of [
				{},
				{ official_alerts_enabled: !an, official_warnings: { enabled: !an } },
				{ official_alerts_enabled: an, official_warnings: { enabled: !an } },
				{ official_alerts_enabled: !an }
			]) {
				const f = w.amtlicheWarnungenFelder(an, abo);
				assert.equal(f.official_alerts_enabled, an, `official_alerts_enabled bei ${JSON.stringify(abo)}`);
				assert.equal(f.official_warnings?.enabled, an, `official_warnings.enabled bei ${JSON.stringify(abo)}`);
				assert.equal(w.amtlicheWarnungenAn({ ...abo, ...f }), an, 'nach dem Schreiben liest die Regel nicht den geschriebenen Wert');
			}
		});
	}

	test('ac20_schreiben_erhaelt_sources', async () => {
		const w = await amtlicheWarnungen();
		const abo = { official_warnings: { enabled: true, sources: ['dwd', 'meteoalarm'] } };
		const f = w.amtlicheWarnungenFelder(false, abo);
		assert.deepEqual(f.official_warnings, { enabled: false, sources: ['dwd', 'meteoalarm'] });
		assert.equal(abo.official_warnings.enabled, true, 'amtlicheWarnungenFelder mutiert die Eingabe');
	});
});
