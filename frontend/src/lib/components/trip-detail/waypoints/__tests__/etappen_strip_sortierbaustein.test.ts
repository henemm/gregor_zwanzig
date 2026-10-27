// TDD RED — #2288 (Epic #2345 P2): Etappen-Strip über den geteilten Sortier-Baustein.
// Spec: docs/specs/modules/etappen_strip_sortable_list.md — AC-3 (Struktur), AC-6 (direction).
//
// Gemessen wird am ECHTEN serverseitigen Render (svelte/server) von EtappenStrip
// und SortableList — kein Mock, kein Quelltext-Grep. Die Verhaltens-ACs (Ziehen,
// Tastatur, Touch, Autoscroll) liegen in frontend/e2e/etappen-strip-sortieren.spec.ts.
//
// Ausfuehrung: cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//   --experimental-test-module-mocks --test src/lib/components/trip-detail/waypoints/__tests__/etappen_strip_sortierbaustein.test.ts
import { register } from 'node:module';
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> waypoints -> trip-detail -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');
register(
	pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const load = async (rel: string) =>
	(await import(pathToFileURL(path.join(FRONTEND, rel)).href)).default;
const EtappenStrip = await load('src/lib/components/trip-detail/waypoints/EtappenStrip.svelte');
const SortableList = await load('src/lib/components/shared/dnd/SortableList.svelte');

const stage = (id: string, name: string) => ({
	id,
	name,
	date: '2026-08-01',
	waypoints: [
		{ id: `${id}-w1`, name: 'Start', lat: 42.0, lon: 9.0, elevation_m: 100 },
		{ id: `${id}-w2`, name: 'Ziel', lat: 42.1, lon: 9.1, elevation_m: 900 }
	]
});
const STAGES = [stage('s1', 'Tag 1'), stage('s2', 'Tag 2'), stage('s3', 'Tag 3')];

function renderStrip(): string {
	return render(EtappenStrip, {
		props: {
			stages: STAGES,
			activeStageId: 's1',
			onStagesReorder: () => {},
			onStageActivate: () => {},
			onPauseInsert: () => {},
			onAddStage: () => {}
		}
	}).body;
}

/** Index hinter dem schliessenden Tag zum Tag, das an `start` öffnet (Nesting zählend). */
function endOfElement(html: string, start: number): number {
	const tag = /^<([a-zA-Z0-9-]+)/.exec(html.slice(start, start + 40))![1];
	const re = new RegExp(`<${tag}\\b[^>]*>|</${tag}>`, 'g');
	re.lastIndex = start;
	let depth = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		if (m[0].startsWith('</')) depth--;
		else if (!m[0].endsWith('/>')) depth++;
		if (depth === 0) return m.index + m[0].length;
	}
	throw new Error('Tag nicht geschlossen');
}

function zoneRange(html: string): [number, number] {
	const m = /<div[^>]*class="[^"]*\bsortable-zone\b[^"]*"/.exec(html);
	assert.ok(m, 'Strip rendert keine .sortable-zone (kein geteilter SortableList)');
	return [m.index, endOfElement(html, m.index)];
}

describe('#2288 AC-3: Strip-Aufbau um die Sortier-Zone', () => {
	test('Strip rendert genau eine Sortier-Zone und kein natives draggable', () => {
		const html = renderStrip();
		assert.equal(html.split('sortable-zone').length - 1, 1, 'genau eine .sortable-zone erwartet');
		assert.ok(!/draggable=/.test(html), 'natives draggable= im Strip');
	});

	test('je Etappe ein Griff (DragHandle) im Item', () => {
		const html = renderStrip();
		assert.equal(html.split('data-testid="drag-handle"').length - 1, STAGES.length);
	});

	test('Pause-Lücken: nach 0 und 1, NICHT nach der letzten Etappe', () => {
		const html = renderStrip();
		assert.ok(html.includes('data-testid="etappen-strip-pause-after-0"'));
		assert.ok(html.includes('data-testid="etappen-strip-pause-after-1"'));
		assert.ok(!html.includes('data-testid="etappen-strip-pause-after-2"'), 'Lücke nach letzter Etappe');
	});

	test('Pause-Lücken liegen INNERHALB der Zone, im Item-Wrapper (sonst entfernt dndzone sie)', () => {
		const html = renderStrip();
		const [zs, ze] = zoneRange(html);
		for (const i of [0, 1]) {
			const pos = html.indexOf(`data-testid="etappen-strip-pause-after-${i}"`);
			assert.ok(pos > zs && pos < ze, `Lücke ${i} liegt ausserhalb der Zone`);
			const itemClass = html.lastIndexOf('sortable-item', pos);
			assert.ok(itemClass > zs, `Lücke ${i} hat keinen sortable-item-Vorfahren`);
			const itemOpen = html.lastIndexOf('<div', itemClass);
			assert.ok(pos < endOfElement(html, itemOpen), `Lücke ${i} steht neben statt im Item`);
		}
	});

	test('„+ Etappe" liegt AUSSERHALB der Zone, hinter ihr, im Strip', () => {
		const html = renderStrip();
		const [, ze] = zoneRange(html);
		const btn = html.indexOf('+ Etappe');
		assert.ok(btn > ze, '„+ Etappe" muss nach der Zone stehen (Geschwister, nicht Kind)');
		const strip = html.indexOf('data-testid="etappen-strip"');
		const stripEnd = endOfElement(html, html.lastIndexOf('<', strip));
		assert.ok(btn < stripEnd, '„+ Etappe" ausserhalb des Strips');
	});

	test('Eyebrow „DRAG ZUM SORTIEREN" und Zone-Beschriftung vorhanden', () => {
		const html = renderStrip();
		assert.ok(html.includes('DRAG ZUM SORTIEREN'));
		assert.ok(/aria-label="Etappen sortieren"/.test(html), 'Zone ohne ariaLabel „Etappen sortieren"');
	});
});

describe('#2288 AC-6: SortableList direction', () => {
	const row = createRawSnippet((id: () => string) => ({
		render: () => `<span data-testid="probe-${id()}">${id()}</span>`
	}));
	const zoneTag = (extra: Record<string, unknown>): string => {
		const body = render(SortableList, {
			props: { items: ['a', 'b'], onDndReorder: () => {}, row, ariaLabel: 'Probe', ...extra }
		}).body;
		const m = /<div[^>]*sortable-zone[^>]*>/.exec(body);
		assert.ok(m, 'keine Zone gerendert');
		return m[0];
	};

	test('ohne Prop identisch mit explizit „vertical" (Bestandskonsumenten unverändert)', () => {
		assert.equal(zoneTag({}), zoneTag({ direction: 'vertical' }));
	});

	test('mit direction="horizontal" unterscheidet sich die Zone sichtbar vom Default', () => {
		assert.notEqual(zoneTag({ direction: 'horizontal' }), zoneTag({}), 'direction wirkt nicht');
	});

	test('Default ist nicht waagerecht', () => {
		assert.ok(!/flex-direction:\s*row|horizontal/.test(zoneTag({})));
	});
});
