// Issue #2155 S2, AC-8 — Fix-Loop F001 (Adversary): Der Farbpunkt der
// Konto-Karte "Deine Reports" wird an der Stelle geprueft, an der er WIRKT —
// in der serverseitig gerenderten ECHTEN Kontoseite (+page.svelte via
// svelte/server `render()`), nicht nur in der reinen Funktion `lastRunDot`.
// Damit ist die Template-Verdrahtung (`{@const dot = lastRunDot(...)}` +
// `class:bg-*`) bewacht: faellt das Template auf die alte Inline-Logik
// (`job.last_run?.status === 'ok'` / `=== 'error'` / `!job.last_run?.time`)
// zurueck, bekommt ein `partial`/`budget`-Lauf keinen neutralen Punkt mehr
// und dieser Test wird rot (Mutation M6).
//
// Muster: sms_verify_kontoseite.test.ts (lokaler $app-Stub + geteilte SSR-Kette).
// Pfadregel #1409: Prueflinge relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/account/__tests__/scheduler-last-run-dot-render.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> account -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(HERE, 'app-navigation-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const AccountPage = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/routes/account/+page.svelte')).href)
).default;

// #2400: Punktfarben stehen auf Tokens (Dunkles Design), nicht mehr auf Tailwind-Palettenfarben.
const GRUEN = 'bg-[var(--g-success)]';
const ROT = 'bg-[var(--g-danger)]';
const NEUTRAL = 'bg-[var(--g-ink-3)]';
const GRAU = 'bg-[var(--g-ink-faint)]';
const FARBEN = [GRUEN, ROT, NEUTRAL, GRAU] as const;
type Farbe = (typeof FARBEN)[number];

function renderKonto(lastRun: unknown): string {
	return render(AccountPage, {
		props: {
			data: {
				profile: {
					id: 'konto-2155',
					display_name: 'Konto 2155',
					email: 'konto2155@beispiel.de',
					mail_to: 'konto2155@beispiel.de',
					email_verified: true,
					tier: 'standard',
					created_at: '2026-09-01T10:00:00Z',
					passkeys: []
				},
				scheduler: {
					jobs: [
						{
							id: 'trip_reports_hourly',
							name: 'Trip-Checks',
							next_run: '2026-09-28T11:00:00Z',
							last_run: lastRun
						}
					]
				},
				health: null,
				templates: [],
				trips: [],
				comparePresets: [],
				locations: [],
				metricPresets: []
			}
		}
	}).body;
}

// Farbklassen des (einzigen) Status-Punkts der Karte "Deine Reports":
// der letzte <span class="... size-2 rounded-full ..."> vor dem Job-Label.
function punktFarben(html: string): Farbe[] {
	const karte = html.indexOf('Deine Reports');
	assert.ok(karte !== -1, 'Karte "Deine Reports" nicht gerendert');
	const rest = html.slice(karte);
	const zeile = rest.indexOf('Trip-Checks');
	assert.ok(zeile !== -1, 'Job-Zeile "Trip-Checks" nicht gerendert');
	const spans = [...rest.slice(0, zeile).matchAll(/<span\b[^>]*>/g)].map((m) => m[0]);
	const punkt = spans.reverse().find((s) => / size-2 /.test(` ${(s.match(/class="([^"]*)"/) ?? [])[1] ?? ''} `));
	assert.ok(punkt, `Status-Punkt (size-2) nicht gefunden in: ${spans.join(' | ')}`);
	const klassen = ((punkt.match(/class="([^"]*)"/) ?? [])[1] ?? '').split(/\s+/);
	return FARBEN.filter((f) => klassen.includes(f));
}

const T = '2026-09-27T10:00:00Z';

describe('#2155 S2 AC-8 — Farbpunkt in der gerenderten Konto-Karte', () => {
	test('last_run null -> grauer Punkt (--g-ink-faint), sonst keine Farbe', () => {
		assert.deepEqual(punktFarben(renderKonto(null)), [GRAU]);
	});

	test('status ok -> gruener Punkt (--g-success)', () => {
		assert.deepEqual(punktFarben(renderKonto({ time: T, status: 'ok', error: '' })), [
			GRUEN
		]);
	});

	test('status error -> roter Punkt (--g-danger)', () => {
		assert.deepEqual(punktFarben(renderKonto({ time: T, status: 'error', error: 'x' })), [
			ROT
		]);
	});

	for (const status of ['partial', 'budget']) {
		test(`status ${status} -> neutraler Punkt (--g-ink-3), weder gruen noch rot noch grau`, () => {
			assert.deepEqual(punktFarben(renderKonto({ time: T, status, error: '' })), [NEUTRAL]);
		});
	}
});
