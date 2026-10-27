// Issue #699 — Doppelter Pfad im Trip-Header; Eyebrow-Format.
// Spec: docs/specs/modules/issue_699_doppelter_pfad_header.md
//
// Issue #2284 S2 (docs/specs/modules/feat_2284_s2_trip_kopf.md, AC-2, AC-17,
// Entscheidung 4): Die Eyebrow zeigt NUR noch den Datumsbereich. Die Region steht
// in einer eigenen, per Stift änderbaren Zeile UNTER dem Namen. Damit ist die alte
// #699-Aussage „Eyebrow = REGION · DATUM" durch eine freigegebene AC umgekehrt;
// alle übrigen #699-Aussagen gelten weiter (Inventar:
// docs/artifacts/feat-2284-s2-trip-kopf/ac17-zusicherungs-inventar.md, Abschnitt B).
//
// Soll nach S2:
//   Trips / KHW 403                    ← obere Breadcrumb (+page.svelte, nicht hier)
//   10.–12. OKTOBER 2026                ← Eyebrow: nur Datumsbereich
//   KHW · Karnischer Höhenweg 403  ✎    ← H1 (trip-detail-h1)
//   Karnische Alpen ✎                   ← Region-Zeile
//
// Früher Quelltext-Grep; jetzt VERHALTEN: die echte Komponente wird serverseitig
// gerendert (svelte/server, Hooks frontend/test-svelte-ssr-hooks.mjs) und das
// erzeugte Markup geprüft. Anker sind testids und die DOM-Reihenfolge — keine
// komponenten-internen CSS-Klassen, damit der Umbau auf den Baustein die Prüfung
// nicht still aushebelt.
//
// RED vor S2: Eyebrow enthält die Region, und unter dem Namen steht keine Region-Zeile.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//
// Ausführung:
//   cd frontend && npm test -- src/lib/components/trip-detail/TripHeader.issue699.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// trip-detail -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const PRUEFLING = path.join(HERE, 'TripHeader.svelte');

const JETZT = new Date(2026, 9, 2, 10, 0); // 02.10.2026, lokal
const DATUM = '10.–12. Oktober 2026';

function trip(extra: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		id: 't-699',
		name: 'Karnischer Höhenweg 403',
		shortcode: 'KHW',
		region: 'Karnische Alpen',
		activity: 'trekking',
		stages: [
			{ id: 'T1', name: 'E1', date: '2026-10-10', waypoints: [{ id: 'G1', name: 'A', lat: 46.6, lon: 12.9, elevation_m: 1200 }, { id: 'G2', name: 'B', lat: 46.62, lon: 12.95, elevation_m: 1700 }] },
			{ id: 'T2', name: 'E2', date: '2026-10-12', waypoints: [] }
		],
		...extra
	};
}

async function html(t: Record<string, unknown>): Promise<string> {
	const Komponente = (await import(pathToFileURL(PRUEFLING).href)).default;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	return render(Komponente as any, { props: { trip: t, now: JETZT } }).body;
}

const text = (b: string): string =>
	b
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/<[^>]+>/g, ' ')
		.replace(/ /g, ' ')
		.replace(/\s+/g, ' ')
		.trim();

/** Alles, was im Kopf VOR der Überschrift steht (= Eyebrow). */
const vorH1 = (b: string): string => text(b.split(/<h1[\s>]/)[0]);

/** Text eines Elements mit testid (erstes Vorkommen, gleichnamiges Tag bis zum Ende). */
function elementText(b: string, id: string): string {
	const m = new RegExp(`<([a-z0-9]+)[^>]*data-testid="${id}"[^>]*>`).exec(b);
	assert.ok(m, `Element ${id} fehlt`);
	const rest = b.slice(m.index + m[0].length);
	const ende = rest.indexOf(`</${m[1]}>`);
	return text(rest.slice(0, ende));
}

describe('#699 AC-1: keine zweite Breadcrumb im Trip-Kopf', () => {
	test('gerenderter Kopf enthält kein „MEINE TRIPS"', async () => {
		assert.ok(!text(await html(trip())).toUpperCase().includes('MEINE TRIPS'));
	});

	test('gerenderter Kopf hat kein trip-detail-breadcrumb und kein <nav>', async () => {
		const b = await html(trip());
		assert.ok(!b.includes('data-testid="trip-detail-breadcrumb"'), 'innere Breadcrumb ist zurück');
		assert.ok(!/<nav[\s>]/.test(b), 'der Trip-Kopf rendert eine Navigation');
	});
});

describe('#699 AC-3-follow-up: Meta-Zeile zeigt nur Strecke und Höhenmeter, kein Datum', () => {
	test('trip-detail-meta zeigt km und Hm, aber keinen Datumsbereich', async () => {
		const meta = elementText(await html(trip()), 'trip-detail-meta');
		assert.match(meta, /\bkm\b/, `km fehlt: ${meta}`);
		assert.match(meta, /↑\s*\S+\s*m\b/, `Hm fehlt: ${meta}`);
		assert.ok(!meta.includes('Oktober') && !/\d{1,2}\.\d{1,2}\./.test(meta), `Datum in der Meta-Zeile: ${meta}`);
	});
});

describe('#699 / #2284 S2 AC-2: Eyebrow nur Datumsbereich, Region in eigener Zeile', () => {
	test('Eyebrow (Text vor der Überschrift) zeigt den Datumsbereich', async () => {
		const eyebrow = vorH1(await html(trip()));
		assert.ok(eyebrow.includes(DATUM), `Datumsbereich fehlt in der Eyebrow: „${eyebrow}"`);
	});

	test('Eyebrow beginnt nicht mit „Trip ·"', async () => {
		assert.ok(!/^Trip\s*·/.test(vorH1(await html(trip()))));
	});

	test('Eyebrow zeigt NUR den Datumsbereich — keine Region, kein Trenner', async () => {
		const eyebrow = vorH1(await html(trip()));
		assert.ok(!eyebrow.includes('Karnische Alpen'), `Region steht noch in der Eyebrow: „${eyebrow}"`);
		assert.equal(eyebrow, DATUM, `Eyebrow ist nicht genau der Datumsbereich: „${eyebrow}"`);
	});

	test('Region steht in eigener Zeile unter dem Namen (nach </h1>, vor der Statuszeile)', async () => {
		const b = await html(trip());
		const nachH1 = b.split('</h1>')[1] ?? '';
		const bisStatus = nachH1.split('data-testid="trip-detail-status-supplement"')[0].replace(/<[^>]*$/, '');
		assert.ok(text(bisStatus).includes('Karnische Alpen'), `Region fehlt zwischen Name und Statuszeile: „${text(bisStatus)}"`);
		assert.ok(bisStatus.includes('data-testid="trip-region-edit-toggle"'), 'Region-Stift fehlt in der Region-Zeile');
		assert.equal(text(b).split('Karnische Alpen').length - 1, 1, 'Region steht nicht genau einmal im Kopf');
	});

	test('Trip ohne Region: Eyebrow bleibt der Datumsbereich, kein verwaistes „·"', async () => {
		const eyebrow = vorH1(await html(trip({ region: undefined })));
		assert.equal(eyebrow, DATUM);
	});

	test('Trip ohne Etappendaten: kein verwaistes „·" vor der Überschrift', async () => {
		const ohneDaten = trip({ stages: [{ id: 'T1', name: 'E1', waypoints: [] }] });
		const eyebrow = vorH1(await html(ohneDaten));
		assert.ok(!eyebrow.includes('·'), `verwaister Trenner in der Eyebrow: „${eyebrow}"`);
		assert.ok(!eyebrow.includes('Karnische Alpen'), `Region in der Eyebrow: „${eyebrow}"`);
	});
});
