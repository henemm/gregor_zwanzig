// TDD RED — Feature #2287 (Epic #2345, Etappe P2), AC-8: der Flush-Guard des
// Ortsvergleich-Hubs fuehrt `wertebereiche` (NICHT mehr `idealwerte`), `alarme`,
// `wetter-metriken`, `versand`. Ein Wechsel aus dem Reiter Wertebereiche mit
// ausstehender Speicherung loest den Flush aus.
//
// Spec: docs/specs/modules/feat_2287_tab_kennungen.md — AC-8
// Mutation (Adversary): `wertebereiche` zurueck auf `idealwerte` → GENAU diese Tests werden rot.
//
// Der Hub-Pfad (CompareTabs.handleValueChange → Guard) ist in
// `hub_reiter_gemeinsame_aufloesung.test.ts` gemessen.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/vergleich_flush_guard_neue_kennungen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	SELBST_SPEICHERNDE_VERGLEICH_REITER,
	sichereSelbstSpeichererVorReiterwechsel
} from '../wetter-tab/wertebereicheVergleichSpeicherung.ts';
import { createController } from './versandVergleichPruefstand.ts';

function ausstehend(): { ctl: ReturnType<typeof createController>; laeufe: () => number } {
	const ctl = createController('vergleich-guard');
	let n = 0;
	ctl.schedule(async () => {
		n += 1;
	}, 60_000);
	return { ctl, laeufe: () => n };
}

// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-2): Wertebereiche und Wetter-Metriken liegen
// im Reiter `wetter`, Alarme und Versand in `zustellung` — die Liste fuehrt genau diese beiden.
describe('AC-8: SELBST_SPEICHERNDE_VERGLEICH_REITER mit den neuen Kennungen', () => {
	test('enthaelt genau wetter, zustellung (#2794)', () => {
		assert.deepEqual([...SELBST_SPEICHERNDE_VERGLEICH_REITER].sort(), ['wetter', 'zustellung']);
	});

	test("keine Alt-Kennung mehr in der Liste (idealwerte, wertebereiche, alarme, wetter-metriken)", () => {
		for (const alt of ['idealwerte', 'wertebereiche', 'alarme', 'wetter-metriken']) {
			assert.equal(SELBST_SPEICHERNDE_VERGLEICH_REITER.includes(alt), false, alt);
		}
	});
});

describe('AC-8: Flush-Verhalten des generischen Guards', () => {
	for (const reiter of ['wetter', 'zustellung']) {
		test(`Wechsel aus ${reiter} mit hasPending → Speicherung laeuft VOR dem Wechsel`, async () => {
			const { ctl, laeufe } = ausstehend();
			assert.equal(ctl.hasPending, true);
			await sichereSelbstSpeichererVorReiterwechsel(reiter, 'uebersicht', ctl);
			assert.equal(laeufe(), 1);
		});
	}

	test('Wechsel aus den Alt-Kennungen idealwerte/wertebereiche flusht NICHT (Alt-Kennung ist kein Reiter mehr)', async () => {
		for (const alt of ['idealwerte', 'wertebereiche']) {
			const { ctl, laeufe } = ausstehend();
			await sichereSelbstSpeichererVorReiterwechsel(alt, 'uebersicht', ctl);
			assert.equal(laeufe(), 0, alt);
			ctl.cancel?.();
		}
	});

	test('Wechsel aus der Uebersicht flusht nicht', async () => {
		const { ctl, laeufe } = ausstehend();
		await sichereSelbstSpeichererVorReiterwechsel('uebersicht', 'wetter', ctl);
		assert.equal(laeufe(), 0);
		ctl.cancel?.();
	});
});
