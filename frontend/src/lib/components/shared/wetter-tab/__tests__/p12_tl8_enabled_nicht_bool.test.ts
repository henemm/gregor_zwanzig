// Issue #3047 Runde 7, Paket p12 — Testluecke TL8 (Editor-Inventar M1: `enabled === true` -> `!== false`).
// Nach E3 normalisiert der Editor fehlendes `enabled` wie Python auf „an“ (Mutation M1a gefangen von
// ac26/e3). Verbleibende Luecke: ein gespeichertes `enabled` ohne Wahrheitswert (`null`, Altbestand)
// — Python nimmt die Groesse NICHT in die Mail, der Reiter Wetter darf sie dann nicht als gewaehlt
// zeigen. Kette wie ac26_einstellung_gleich_ausgabe.test.ts: echter Lader `standAusAbo` gegen die
// echten Python-Resolver (ausgabeOrakel.ts). Zwei Nutzer, Folgen ungleich Katalogfolge.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/p12_tl8_enabled_nicht_bool.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { live } from './wetterTabDaten.ts';
import { pythonAusgabe } from './ausgabeOrakel.ts';
import { eigenschaftenAusKatalog, vorlagenAusTemplates } from '../ampelModell.ts';
import * as Z from '../wetterZustand.ts';

const LIVE = live();
const VORLAGEN = vorlagenAusTemplates(LIVE.templates);
const EIG = eigenschaftenAusKatalog(LIVE.metrics);
const menge = (a: string[]) => [...new Set(a)].sort();

const TRIPS: Record<string, { display_config: Record<string, unknown> }> = {
	a_enabled_null: {
		display_config: {
			metrics: [
				{ metric_id: 'precipitation', enabled: true, bucket: 'primary', order: 0 },
				{ metric_id: 'wind', enabled: null, bucket: 'primary', order: 1 },
				{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 2 }
			]
		}
	},
	b_enabled_null_vorn: {
		display_config: {
			metrics: [
				{ metric_id: 'thunder', enabled: null, bucket: 'primary', order: 0 },
				{ metric_id: 'uv_index', enabled: true, bucket: 'primary', order: 1 }
			]
		}
	}
};

const AUS = pythonAusgabe({ trip: TRIPS });

for (const id of Object.keys(TRIPS)) {
	test(`tl8_enabled_null_nicht_gewaehlt_wie_mail_${id}`, () => {
		const s = Z.standAusAbo('route', { id, name: id, stages: [], ...structuredClone(TRIPS[id]) }, VORLAGEN, {}, { eig: EIG });
		assert.ok(AUS.trip[id].mail.length > 0, 'Messaufbau: Mail leer');
		assert.deepEqual(menge(s.auswahl), menge(AUS.trip[id].mail));
	});
}
