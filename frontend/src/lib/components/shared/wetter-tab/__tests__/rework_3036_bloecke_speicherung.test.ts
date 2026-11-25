// TDD RED — Issue #3036: die zwei neuen Block-Schalter Kurz-Zusammenfassung (show_compact_summary) und
// Großwetterlage (show_stability) der Karte „Was steht wo“ (nur Trip).
// Spec docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md, AC-1 (Startwert, fehlend = an) und AC-2
// (Frontend-Teil: Teilfeld-PUT auf report_config, nur das geänderte Feld, kein anderer Schlüssel).
// Den Merge auf der Server-Seite und den zweiten Nutzer prüft frontend/e2e/rework-3036-bloecke-schalter.spec.ts.
//
// Reine Logik shared/wetter-tab/wasStehtWoSpeicherung.ts mit einem Schreib-Client im Speicher (kein Netz).
// RED heute: felderAusAntwort kennt die zwei Felder nicht, felderNutzlast schreibt sie nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/rework_3036_bloecke_speicherung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { erstelleFelderSpeicherung, felderAusAntwort, felderNutzlast } from '../wasStehtWoSpeicherung.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const NEU = ['show_compact_summary', 'show_stability'] as const;
const BLOCKS = { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich' };

describe('#3036 AC-1: Startwert der zwei Schalter aus blocks', () => {
	for (const feld of NEU) {
		test(`${feld}: gespeichert false → aus`, () => {
			const f = felderAusAntwort({ blocks: { ...BLOCKS, [feld]: false } } as J) as J;
			assert.equal(f[feld], false, `${feld} fehlt in den Feldern der Karte`);
		});
		test(`${feld}: fehlendes Feld → an`, () => {
			const f = felderAusAntwort({ blocks: { ...BLOCKS } } as J) as J;
			assert.equal(f[feld], true, `${feld} ohne gespeicherten Wert muss an sein`);
		});
	}
});

describe('#3036 AC-2: Umschalten speichert nur das geänderte Feld in report_config', () => {
	for (const feld of NEU) {
		test(`${feld} aus: Nutzlast { report_config: { ${feld}: false } }, sonst nichts`, () => {
			const alt = felderAusAntwort({ blocks: BLOCKS } as J) as J;
			assert.deepEqual(felderNutzlast('route', { ...alt, [feld]: false }, alt), { report_config: { [feld]: false } });
		});
		test(`${feld} wieder an: Nutzlast { report_config: { ${feld}: true } }`, () => {
			const alt = felderAusAntwort({ blocks: { ...BLOCKS, [feld]: false } } as J) as J;
			assert.deepEqual(felderNutzlast('route', { ...alt, [feld]: true }, alt), { report_config: { [feld]: true } });
		});
		test(`${feld}: Orts-Vergleich schreibt das Feld nie`, () => {
			const alt = felderAusAntwort({ blocks: BLOCKS } as J) as J;
			assert.deepEqual(felderNutzlast('vergleich', { ...alt, [feld]: false }, alt), {});
		});
	}

	test('Schalter umgelegt: genau ein PUT auf /api/trips/{id} mit nur diesem Feld', async () => {
		const aufrufe: { pfad: string; rumpf: unknown }[] = [];
		const client = {
			get: async () => ({}) as never,
			put: async <T>(pfad: string, rumpf: unknown) => {
				aufrufe.push({ pfad, rumpf: JSON.parse(JSON.stringify(rumpf)) });
				return { id: 'gr' } as T;
			}
		};
		const start = felderAusAntwort({ blocks: BLOCKS } as J) as J;
		const f = erstelleFelderSpeicherung({ client: client as J, kind: 'route', id: 'gr', start });
		f.melden({ ...start, show_stability: false });
		await new Promise((r) => setTimeout(r, 0));
		assert.equal(aufrufe.length, 1, 'Umschalten von show_stability löst keinen PUT aus');
		assert.equal(aufrufe[0].pfad, '/api/trips/gr');
		assert.deepEqual(aufrufe[0].rumpf, { report_config: { show_stability: false } });
	});
});
