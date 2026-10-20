// TDD RED — Issue #2438 (S2b von #2422, Epic #2507): Editor-Hinweis
// „Kanal kann nur abwählen" (B6, ADR-0050 Regel 1–3).
//
// Spec: docs/specs/modules/feat_2438_kanal_abwahl_hinweis.md
//   AC-3  leere Aus-Gruppe zeigt den Hinweis trotzdem
//   AC-4  globale Grundauswahl-Ansicht (ohne `offColumns`) zeigt ihn NICHT
//   AC-6  exakter Wortlaut, nur Regelbeschreibung (keine Handlungsempfehlung)
//   AC-7  Aus-Zeile + Wiederherstellen bleiben unverändert (befüllte Gruppe)
//
// Gerendert wird der ECHTE Baustein serverseitig (svelte/server) — kein Mock.
// `ltKanalAbwahlHinweisText` und der Hinweis werden NUR dynamisch importiert,
// damit ein (in RED) fehlender Export jeden Test einzeln rot macht statt die
// Datei mit einem Ladefehler zu kippen.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/kanal_abwahl_hinweis.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
// registriert die Runen-/.svelte-Hooks (Nebenwirkung des Imports)
import '../../trip-new/__tests__/tripNewSsr.ts';

const here = dirname(fileURLToPath(import.meta.url));
const WORTLAUT =
	'Ein Kanal zeigt höchstens, was in der Grundauswahl gewählt ist. Was dort fehlt, erscheint in keinem Kanal.';

async function hinweisText(): Promise<string> {
	const mod: any = await import(
		pathToFileURL(join(here, '..', 'layout-tab', 'ltChannels.ts')).href
	);
	assert.equal(
		typeof mod.ltKanalAbwahlHinweisText,
		'function',
		'ltChannels.ts muss ltKanalAbwahlHinweisText() exportieren'
	);
	return mod.ltKanalAbwahlHinweisText();
}

async function rendere(
	offColumns?: string[],
	kanal: string = 'email',
	showAbwahlHinweis?: boolean
): Promise<string> {
	const { render } = await import('svelte/server');
	const comp: any = (
		await import(
			pathToFileURL(join(here, '..', 'weather-metrics-tab', 'WeatherV2Reihenfolge.svelte')).href
		)
	).default;
	const metricById: Record<string, any> = {
		temperature: { id: 'temperature', label: 'Temperatur', unit: '°C' },
		wind: { id: 'wind', label: 'Wind', unit: 'km/h' }
	};
	const props: Record<string, unknown> = {
		primaryColumns: ['temperature'],
		metricById,
		friendlyMap: {},
		activeChannel: kanal,
		highlight: null,
		onRemove: () => {},
		onDndReorder: () => {},
		onMode: () => {},
		kuerzelById: {}
	};
	if (offColumns !== undefined) {
		props.offColumns = offColumns;
		props.onRestore = () => {};
	}
	if (showAbwahlHinweis !== undefined) props.showAbwahlHinweis = showAbwahlHinweis;
	return render(comp, { props }).body;
}

describe('#2438 Kanal-Abwahl-Hinweis', () => {
	test('AC-6: exakter Wortlaut, keine Handlungsempfehlung', async () => {
		const t = await hinweisText();
		assert.equal(t, WORTLAUT);
		assert.doesNotMatch(t, /\b(solltest|sollte|bitte|wähle|aktiviere|schalte)\b/i);
	});

	test('AC-3: leere Aus-Gruppe zeigt den Hinweis trotzdem', async () => {
		const html = await rendere([], 'email', true);
		assert.match(html, /data-testid="wm2-aus-gruppe"/);
		assert.match(html, /data-testid="wm2-aus-hinweis"/);
		assert.ok(html.includes(WORTLAUT), 'Hinweistext fehlt im gerenderten Baustein');
	});

	test('AC-7: befüllte Aus-Gruppe: Hinweis NACH den Aus-Zeilen, Aus-Zeile bleibt', async () => {
		const html = await rendere(['wind'], 'email', true);
		const zeile = html.indexOf('data-testid="wm2-aus-row"');
		const hinweis = html.indexOf('data-testid="wm2-aus-hinweis"');
		assert.ok(zeile >= 0, 'wm2-aus-row muss unverändert erscheinen');
		assert.ok(hinweis > zeile, 'Hinweis muss unter der Aus-Liste stehen');
		assert.ok(html.includes(WORTLAUT));
	});

	for (const kanal of ['telegram', 'sms']) {
		test(`AC-1/AC-3: Hinweis erscheint auch im Kanal ${kanal} (leere Aus-Gruppe)`, async () => {
			const html = await rendere([], kanal, true);
			assert.match(html, /data-testid="wm2-aus-hinweis"/);
			assert.ok(html.includes(WORTLAUT));
		});
	}

	test('AC-4: globale Grundauswahl-Ansicht (ohne offColumns) hat keinen Hinweis', async () => {
		const html = await rendere(undefined);
		assert.doesNotMatch(html, /wm2-aus-hinweis/);
		assert.ok(!html.includes(WORTLAUT));
	});

	// Fix #2438 (fix_2438_hinweis_nur_kanal_block): Opt-in, Default aus.
	test('AC-3/AC-6: offColumns OHNE showAbwahlHinweis (Ausblick) zeigt keinen Hinweis, Aus-Gruppe bleibt', async () => {
		for (const off of [[], ['wind']]) {
			const html = await rendere(off);
			assert.match(html, /data-testid="wm2-aus-gruppe"/);
			assert.doesNotMatch(html, /wm2-aus-hinweis/);
			assert.ok(!html.includes(WORTLAUT));
		}
	});

	test('AC-5: ohne offColumns bleibt der Hinweis auch mit showAbwahlHinweis=true aus', async () => {
		const html = await rendere(undefined, 'email', true);
		assert.doesNotMatch(html, /wm2-aus-hinweis/);
	});
});
