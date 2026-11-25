// Rework #3020 R1, AC-11 und AC-15: Schalter der Karte „Was steht wo“ beim Trip.
//   AC-11: ein noch nicht gespeicherter neuer Trip (Anlegen) hat keinen Nachtblock-Schalter
//          (Ersatz fuer trip_night_block_schalter_verdrahtung.test.ts, „Schalter nur Trip/bestehend“).
//   AC-15: der Haken „Großwetterlage“ folgt `show_stability`, nie `show_outlook`
//          (Ersatz fuer mail_inhalt_haken_grosswetterlage_3237.test.ts).
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-11, AC-15)
//
// Server-Render der ECHTEN Datei organisms/wetter-tab/WasStehtWoKarte.svelte; die Antwort des Endpoints setzt
// startzustandHook.mjs als Startwert (Muster rework_3036_bloecke_schalter.test.ts). Dazu die echten Module
// `wasStehtWoSpeicherung.ts` (Kartenmodell) und `mailInhaltKonstanten.ts`.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/rework_3020_karte_schalter.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const DATEI = path.resolve(HERE, '..', 'wetter-tab', 'WasStehtWoKarte.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(HERE, 'startzustandHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const { de } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/messages/de/index.ts')).href);
const { felderAusAntwort, felderNutzlast } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts')).href
);
const { mailInhaltBausteine } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/mailInhaltKonstanten.ts')).href);
after(() => locale.set('de'));

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const g = globalThis as J;

const START: [string, string][] = [
	['let antwort = $state<PlacementsAntwort | null>(null);', 'let antwort = $state<PlacementsAntwort | null>(globalThis.__wswAntwort);'],
	["let phase = $state<'laedt' | 'fehler' | 'bereit'>('laedt');", "let phase = $state<'laedt' | 'fehler' | 'bereit'>(globalThis.__wswPhase ?? 'bereit');"]
];
async function karte(a: J, props: Record<string, unknown>): Promise<string> {
	g.__wswAntwort = a;
	g.__wswPhase = undefined;
	const url = pathToFileURL(DATEI).href + `?start=${encodeURIComponent(JSON.stringify(START))}`;
	const K = (await import(url)).default;
	return render(K, { props: { id: 'abo-1', context: 'route', ...props } }).body.replace(/<!--[\s\S]*?-->/g, '');
}
const tags = (h: string, testid: string) => h.match(new RegExp(`<[a-z][^>]*data-testid="${testid}"[^>]*>`, 'g')) ?? [];
const attr = (auf: string, name: string) => auf.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1] ?? null;

const z = (state: string) => ({ state, format: null, reason: null, example: null, ampel: null, mark: null });
function trip(blocks: J = {}, stored = true): J {
	return {
		kind: 'route', lang: 'de', stored, placements: { version: 1, rows: [{ metric_id: 'wind' }] }, location_count: null,
		columns: [
			{ stelle: 'email', subtitle: 'stundentabelle', block_off: false, rests: null },
			{ stelle: 'telegram', subtitle: 'nachricht', block_off: false, rests: null },
			{ stelle: 'sms', subtitle: 'und_premium_sms', block_off: false, rests: null },
			{ stelle: 'outlook', subtitle: 'email_und_telegram', block_off: false, rests: null }
		],
		fixed_rows: [],
		rows: [{ metric_id: 'wind', name: 'Wind-T', position: 0, parent: null, cells: { email: z('on'), telegram: z('on'), sms: z('on'), outlook: z('off') } }],
		sms_example: null,
		outlook_reports: ['evening'],
		blocks: { show_stage_stats: true, show_yesterday_comparison: true, email_format: 'full', telegram_style: 'rich', outlook: { morning: false, evening: true }, ...blocks },
		legend: { metrics: [], fixed: [] },
		example_version: 1
	};
}

describe('Rework #3020 AC-11: kein Nachtblock-Schalter beim noch nicht gespeicherten neuen Trip', () => {
	test('Gegenprobe bestehender Trip: der Nachtblock-Schalter ist da', async () => {
		locale.set('de');
		const h = await karte(trip(), {});
		assert.equal(tags(h, 'was-steht-wo-show_night_block').length, 1, 'Messaufbau: bestehender Trip zeigt den Schalter');
	});
	test('Anlegen (createMode): die Karte zeigt keinen Nachtblock-Schalter', async () => {
		locale.set('de');
		const h = await karte(trip({}, false), { createMode: true, entwurf: () => ({}) });
		assert.ok(tags(h, 'was-steht-wo-show_stability').length === 1, 'Messaufbau: Karte im Anlegen bereit gerendert');
		assert.equal(tags(h, 'was-steht-wo-show_night_block').length, 0, 'im Anlegen darf es den Nachtblock-Schalter nicht geben');
	});
});

describe('Rework #3020 AC-15: Haken „Großwetterlage“ folgt show_stability, nie show_outlook', () => {
	const FAELLE = [
		{ blocks: { show_stability: true, show_outlook: false }, an: 'true' },
		{ blocks: { show_stability: false, show_outlook: true }, an: 'false' }
	];
	for (const f of FAELLE) {
		test(`Karte: show_stability=${f.blocks.show_stability}, show_outlook=${f.blocks.show_outlook} -> Haken ${f.an}`, async () => {
			locale.set('de');
			const h = await karte(trip(f.blocks), {});
			const t = tags(h, 'was-steht-wo-show_stability');
			assert.equal(t.length, 1, 'Haken Großwetterlage fehlt');
			assert.equal(attr(t[0], 'aria-label'), de['wetter.wsw.bloecke.grosswetterlage'], 'der Haken muss „Großwetterlage“ heißen');
			assert.equal(attr(t[0], 'aria-checked'), f.an, 'der Haken folgt nicht show_stability');
			assert.equal(String(felderAusAntwort({ blocks: f.blocks }).show_stability), f.an, 'Kartenmodell folgt nicht show_stability');
		});
	}
	test('Kartenmodell: Haken umschalten schreibt report_config.show_stability, nie show_outlook', () => {
		const start = felderAusAntwort({ blocks: { show_stability: true, show_outlook: false } });
		const rumpf = felderNutzlast('route', { ...start, show_stability: false }, start);
		assert.deepEqual(rumpf, { report_config: { show_stability: false } });
		assert.ok(!JSON.stringify(rumpf).includes('show_outlook'));
	});
	test('mailInhaltKonstanten: der Baustein „Großwetterlage“ ist show_stability; show_outlook ist kein Baustein', () => {
		locale.set('de');
		const b = mailInhaltBausteine();
		assert.equal(b.show_stability?.label, de['layout.mail_inhalt.grosswetterlage']);
		assert.equal('show_outlook' in b, false, 'show_outlook darf kein Mail-Inhalt-Baustein sein');
		const grossWetter = Object.entries(b).filter(([, v]) => (v as { label: string }).label === de['layout.mail_inhalt.grosswetterlage']);
		assert.deepEqual(grossWetter.map(([k]) => k), ['show_stability']);
	});
});
