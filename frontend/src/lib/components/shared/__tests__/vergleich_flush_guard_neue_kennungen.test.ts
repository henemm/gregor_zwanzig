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
} from '../corridor-editor/wertebereicheVergleichSpeicherung.ts';
import { createController } from './versandVergleichPruefstand.ts';

function ausstehend(): { ctl: ReturnType<typeof createController>; laeufe: () => number } {
	const ctl = createController('vergleich-guard');
	let n = 0;
	ctl.schedule(async () => {
		n += 1;
	}, 60_000);
	return { ctl, laeufe: () => n };
}

describe('AC-8: SELBST_SPEICHERNDE_VERGLEICH_REITER mit den neuen Kennungen', () => {
	test('enthaelt genau wertebereiche, alarme, wetter-metriken, versand', () => {
		assert.deepEqual([...SELBST_SPEICHERNDE_VERGLEICH_REITER].sort(), [
			'alarme',
			'versand',
			'wertebereiche',
			'wetter-metriken'
		]);
	});

	test("kein 'idealwerte' mehr in der Liste", () => {
		assert.equal(SELBST_SPEICHERNDE_VERGLEICH_REITER.includes('idealwerte'), false);
	});
});

describe('AC-8: Flush-Verhalten des generischen Guards', () => {
	test('Wechsel aus wertebereiche mit hasPending → Speicherung laeuft VOR dem Wechsel', async () => {
		const { ctl, laeufe } = ausstehend();
		assert.equal(ctl.hasPending, true);
		await sichereSelbstSpeichererVorReiterwechsel('wertebereiche', 'uebersicht', ctl);
		assert.equal(laeufe(), 1);
	});

	test('Wechsel aus der Alt-Kennung idealwerte flusht NICHT (Alt-Kennung ist kein Reiter mehr)', async () => {
		const { ctl, laeufe } = ausstehend();
		await sichereSelbstSpeichererVorReiterwechsel('idealwerte', 'uebersicht', ctl);
		assert.equal(laeufe(), 0);
		ctl.cancel?.();
	});

	test('Wechsel aus der Uebersicht flusht nicht', async () => {
		const { ctl, laeufe } = ausstehend();
		await sichereSelbstSpeichererVorReiterwechsel('uebersicht', 'wertebereiche', ctl);
		assert.equal(laeufe(), 0);
		ctl.cancel?.();
	});
});
