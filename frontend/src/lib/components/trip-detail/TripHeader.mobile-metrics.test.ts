// Issue #416 — Mobile Kennzahlen-Kacheln im Trip-Detail-Header.
// Spec: docs/specs/modules/issue_416_mobile_trip_kennzahlen.md
//
// Drei mobile-only Stat-Kacheln (ETAPPE, BRIEFING, START IN / TAG) im Trip-Kopf,
// sichtbar nur bis 899 px Breite.
//
// Issue #2284 S2 (AC-17, Entscheidung 7): `TripHeader` bleibt Hülle um den Baustein
// `SubscriptionHeader`; die Kacheln `trip-header-mobile-metrics` bleiben in der Hülle.
// Früher Quelltext-Grep (testid-Strings, Import-Namen, Variablennamen); jetzt
// VERHALTEN: die echte Komponente wird serverseitig gerendert (svelte/server) und
// Beschriftung + Wert jeder Kachel für die Trip-Zustände geprüft. Jede alte
// Import-/Variablen-Aussage hat so ein Verhaltens-Gegenstück
// (Inventar: docs/artifacts/feat-2284-s2-trip-kopf/ac17-zusicherungs-inventar.md, D).
//
// Grenze: SSR wertet kein Layout aus. Die Sichtbarkeitsregel (ausgeblendet ab 900 px,
// sichtbar bis 899 px) wird deshalb am CSS-AUSGANG DES SVELTE-COMPILERS geprüft
// (`compile().css.code` — das CSS, das der Browser bekommt), nicht am Quelltext;
// kein E2E prüft die Kachel-Sichtbarkeit (Grep frontend/e2e: kein Treffer).
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//
// Ausführung:
//   cd frontend && npm test -- src/lib/components/trip-detail/TripHeader.mobile-metrics.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { compile } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const PRUEFLING = path.join(HERE, 'TripHeader.svelte');

const etappen = (...daten: string[]) =>
	daten.map((date, i) => ({ id: `T${i + 1}`, name: `E${i + 1}`, date, waypoints: [] }));

function trip(extra: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		id: 't-416',
		name: 'GR20 Nord',
		region: 'Korsika',
		activity: 'trekking',
		stages: etappen('2026-10-10', '2026-10-11', '2026-10-12'),
		report_config: { enabled: true, morning_enabled: true, evening_enabled: true, morning_time: '07:00:00', evening_time: '18:00:00' },
		...extra
	};
}

async function html(t: Record<string, unknown>, now: Date): Promise<string> {
	const Komponente = (await import(pathToFileURL(PRUEFLING).href)).default;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	return render(Komponente as any, { props: { trip: t, now } }).body;
}

const text = (b: string): string =>
	b
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/<[^>]+>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();

/** „LABEL WERT" einer Kachel (Inhalt des Elements mit der testid). */
function kachel(b: string, id: string): string {
	const start = b.indexOf(`data-testid="${id}"`);
	assert.ok(start >= 0, `Kachel ${id} fehlt`);
	// Kachel-Wrapper ist ein <div>; bis zur nächsten Kachel bzw. Ende des Containers.
	const rest = b.slice(b.indexOf('>', start) + 1);
	const naechste = rest.search(/data-testid="metric-|<\/header>/);
	return text(rest.slice(0, naechste < 0 ? undefined : naechste).replace(/<div[^>]*$/, ''));
}

const GEPLANT = new Date(2026, 9, 2, 10, 0); // 8 Tage vor dem Start
const AKTIV = new Date(2026, 9, 11, 10, 0); // Tag 2 von 3
const BEENDET = new Date(2026, 9, 20, 10, 0);

describe('#416 AC-5: Kachel-Container und drei Kacheln', () => {
	test('gerenderter Kopf trägt trip-header-mobile-metrics mit drei Kacheln genau einmal', async () => {
		const b = await html(trip(), GEPLANT);
		for (const id of ['trip-header-mobile-metrics', 'metric-etappe', 'metric-briefing', 'metric-start']) {
			assert.equal(b.split(`data-testid="${id}"`).length - 1, 1, `${id} nicht genau einmal`);
		}
		const container = b.split('data-testid="trip-header-mobile-metrics"')[1] ?? '';
		for (const id of ['metric-etappe', 'metric-briefing', 'metric-start']) {
			assert.ok(container.includes(`data-testid="${id}"`), `${id} liegt nicht im Kachel-Container`);
		}
	});
});

describe('#416 AC-1: ETAPPE', () => {
	test('geplant ⇒ „ETAPPE —/3"', async () => {
		assert.equal(kachel(await html(trip(), GEPLANT), 'metric-etappe'), 'ETAPPE —/3');
	});
	test('aktiv (Tag 2) ⇒ „ETAPPE 2/3"', async () => {
		assert.equal(kachel(await html(trip(), AKTIV), 'metric-etappe'), 'ETAPPE 2/3');
	});
	test('beendet ⇒ „ETAPPE 3/3"', async () => {
		assert.equal(kachel(await html(trip(), BEENDET), 'metric-etappe'), 'ETAPPE 3/3');
	});
	test('ohne Etappen ⇒ „ETAPPE —"', async () => {
		assert.equal(kachel(await html(trip({ stages: [] }), GEPLANT), 'metric-etappe'), 'ETAPPE —');
	});
});

describe('#416 AC-2: BRIEFING', () => {
	test('Morgen-Briefing aktiv ⇒ Morgenzeit „07:00"', async () => {
		assert.equal(kachel(await html(trip(), GEPLANT), 'metric-briefing'), 'BRIEFING 07:00');
	});
	test('nur Abend-Briefing ⇒ Abendzeit „18:00"', async () => {
		const t = trip({ report_config: { enabled: true, morning_enabled: false, evening_enabled: true, morning_time: '07:00:00', evening_time: '18:00:00' } });
		assert.equal(kachel(await html(t, GEPLANT), 'metric-briefing'), 'BRIEFING 18:00');
	});
	test('Briefing aus ⇒ „—"', async () => {
		const t = trip({ report_config: { enabled: false, morning_time: '07:00:00', evening_time: '18:00:00' } });
		assert.equal(kachel(await html(t, GEPLANT), 'metric-briefing'), 'BRIEFING —');
	});
});

describe('#416 AC-3: START IN / TAG / STATUS', () => {
	test('geplant ⇒ „START IN 8 Tg"', async () => {
		assert.equal(kachel(await html(trip(), GEPLANT), 'metric-start'), 'START IN 8 Tg');
	});
	test('aktiv ⇒ „TAG Tag 2"', async () => {
		assert.equal(kachel(await html(trip(), AKTIV), 'metric-start'), 'TAG Tag 2');
	});
	test('beendet ⇒ „STATUS —"', async () => {
		assert.equal(kachel(await html(trip(), BEENDET), 'metric-start'), 'STATUS —');
	});
});

describe('#416 AC-4: Sichtbarkeit nur bis 899 px (übersetztes CSS)', () => {
	// Compiler-Ausgang, nicht Quelltext: geprüft wird das CSS, das ausgeliefert wird.
	const css = compile(readFileSync(PRUEFLING, 'utf-8'), { generate: 'client', filename: PRUEFLING }).css?.code ?? '';
	const ohneLeer = css.replace(/\s+/g, '');

	test('Grundregel: .mobile-metrics ist ausgeblendet (display:none)', () => {
		const grund = ohneLeer.split('@media')[0];
		assert.match(grund, /\.mobile-metrics(\.svelte-[a-z0-9]+)?\{[^}]*display:none/, `keine Grundregel display:none: ${css}`);
	});

	test('Media-Regel (max-width:899px) blendet die Kacheln als Flex-Reihe ein', () => {
		assert.match(
			ohneLeer,
			/@media\(max-width:899px\)\{[^@]*\.mobile-metrics(\.svelte-[a-z0-9]+)?\{[^}]*display:flex/,
			`keine 899px-Regel mit display:flex: ${css}`
		);
	});
});
