// Issue #923 Adversary Finding F002: der reale Fetch/Catch-Pfad von
// ChannelFidelitySMS.svelte/ChannelPreviewCard.svelte (api.post(...).then/
// .catch) war von keinem Test erreichbar, weil svelte/server's render()
// weder onMount noch $effect ausführt — alle Frontend-Tests injizieren die
// Serverantwort ausschließlich über previewOverride. Diese Datei testet die
// extrahierte, DOM-freie Logik `loadSmsFidelityPreview()`
// (smsFidelityPreview.ts) direkt in Node — kein svelte/server, kein Mount,
// kein Mock-Framework: `post` ist eine einfache Funktion, die der Test
// selbst als Erfolgs- oder Reject-Stub übergibt.
//
// Kernbehauptung (F002): bei einem Fehler (Netzwerkausfall, Reject) liefert
// die Funktion IMMER `preview: null` — nie eine lokal nachgerechnete Kopie
// der alten Client-Kürzungslogik. Test 2 unten ist die mutations-taugliche
// Probe dafür.
//
// Pfadregel #1409: Pfad relativ zu dieser Datei.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/__tests__/sms_fidelity_preview_fetch.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	loadSmsFidelityPreview,
	type SmsFidelityPreview
} from '../smsFidelityPreview.ts';

const SAMPLE_PREVIEW: SmsFidelityPreview = {
	line: 'Etappe: D18',
	char_count: 11,
	max_length: 160,
	carried_ids: ['temperature']
};

describe('loadSmsFidelityPreview — Erfolgsfall', () => {
	test('liefert die Serverantwort unverändert als preview, error === null', async () => {
		let calledPath = '';
		let calledBody: unknown = null;
		const post = async (path: string, body: unknown): Promise<SmsFidelityPreview> => {
			calledPath = path;
			calledBody = body;
			return SAMPLE_PREVIEW;
		};

		const result = await loadSmsFidelityPreview(['temperature'], post);

		assert.equal(calledPath, '/api/_validator/sms-fidelity-preview');
		assert.deepEqual(calledBody, { metric_ids: ['temperature'] });
		assert.deepEqual(result.preview, SAMPLE_PREVIEW);
		assert.equal(result.error, null);
	});
});

describe('loadSmsFidelityPreview — Fehlerfall (F002)', () => {
	test('bei Reject ist preview EXAKT null — keine lokale Fallback-Berechnung', async () => {
		const post = async (): Promise<SmsFidelityPreview> => {
			throw new Error('Netzwerkfehler');
		};

		const result = await loadSmsFidelityPreview(['temperature', 'wind'], post);

		assert.equal(
			result.preview,
			null,
			'F002: preview muss bei einem Fehler exakt null sein — jeder andere Wert ' +
				'(z.B. ein aus metricById nachgerechnetes Objekt) ist ein heimlicher ' +
				'Client-Fallback und muss diesen Test rot machen.'
		);
		assert.equal(result.error, 'Netzwerkfehler');
	});

	test('bei einem API-Fehlerobjekt ({error: string}) wird die Meldung übernommen', async () => {
		const post = async (): Promise<SmsFidelityPreview> => {
			// eslint-disable-next-line @typescript-eslint/no-throw-literal
			throw { error: 'validator busy' };
		};

		const result = await loadSmsFidelityPreview(['temperature'], post);

		assert.equal(result.preview, null);
		assert.equal(result.error, 'validator busy');
	});
});
