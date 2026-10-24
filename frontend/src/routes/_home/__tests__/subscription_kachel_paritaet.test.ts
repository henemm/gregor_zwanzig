// TDD RED — Issue #2346 S2 (Epic #2345 P6): EINE Startseiten-Kachel fuer Trip und Ortsvergleich.
// Spec: docs/specs/modules/feat_2346_cockpit_paritaet.md — AC-1 (Teil S2), AC-9, AC-10, AC-16, AC-17, AC-18.
//
// Vertrag (hier festgelegt, /50 baut danach):
//   organisms/SubscriptionCard.svelte   neue Props: channels?: string[] (Kanal-Namen, kind-neutral),
//                                        nextSend?: string|null, lastSent?: string|null, href?: string.
//     -> Felder tragen data-field="status" | "channels" | "next-send" | "last-sent" (beide kinds, auch compact);
//        jeder Kanal ist ein Chip mit data-channel="<Name>"; fehlender Wert zeigt "—";
//        mit href ist der Name ein echter <a href=…>.
//   routes/_home/SubscriptionKachel.svelte   Props: kind, sub, nextSend?, lastSent? — wrappt SubscriptionCard compact;
//        Trip-Kanaele aus reportChannels(report_config) (Flags, nie empfaenger), Vergleich aus presetChannels;
//        href = /trips/{id} bzw. /compare/{id}.
//   routes/_home/kachelActions.ts       kachelActions() (kind-neutral, Umbenennung von compareKachelActions)
//   routes/_home/kachelVersand.ts       kachelVersand(kind, sub, nextBriefing) => { nextSend, lastSent }
//        nextSend = formatNextBriefing(nb, kind==='trip'?'route':'vergleich') (at===null => Grund, nb fehlt => "—");
//        lastSent = Vergleich: relativeLastSent(letzter_versand) ('' => null), Trip: null (bis S4).
//
// Pfadregel #1409: relativ zu DIESER Datei.
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/_home/__tests__/subscription_kachel_paritaet.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { existsSync } from 'node:fs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
const HOME = path.resolve(HERE, '..');
const ORGANISMS = path.join(FRONTEND, 'src/lib/components/organisms');

register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
// $app/navigation (goto) gibt es unter reinem Node nicht — Stub nur fuer diese Datei.
register(
	'data:text/javascript,' +
		encodeURIComponent(
			`export async function resolve(s, c, n) { if (s === '$app/navigation') return { url: 'data:text/javascript,export const goto=()=>{};', shortCircuit: true }; return n(s, c); }`
		),
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');

async function laden(abs: string): Promise<any> {
	assert.ok(existsSync(abs), `${path.relative(FRONTEND, abs)} fehlt (RED)`);
	return (await import(pathToFileURL(abs).href)).default;
}
async function modul(abs: string): Promise<any> {
	assert.ok(existsSync(abs), `${path.relative(FRONTEND, abs)} fehlt (RED)`);
	return import(pathToFileURL(abs).href);
}
const html = (comp: any, props: Record<string, unknown>) => render(comp, { props }).body.replace(/<!--.*?-->/g, '');
const kanaele = (h: string) => [...h.matchAll(/data-channel="([^"]+)"/g)].map((m) => m[1]);
const feldNamen = (h: string) => [...h.matchAll(/data-field="([^"]+)"/g)].map((m) => m[1]);

const JETZT = new Date('2026-10-17T12:00:00Z');
const TRIP: any = {
	id: 'trip-1',
	name: 'GR20 Nord',
	stages: [{ id: 's1', name: 'E1', date: '2026-10-17', waypoints: [] }],
	report_config: { enabled: true, send_email: true, send_telegram: false, send_sms: false, send_premium_sms: false },
	empfaenger: ['mail@example.org', 'telegram:12345']
};
const PRESET: any = {
	id: 'cmp-1',
	name: 'Ortsvergleich Nord',
	location_ids: ['a', 'b'],
	schedule: 'daily',
	send_telegram: true,
	letzter_versand: '2026-10-16T07:00:00Z'
};

describe('AC-1/AC-16: beide kinds — dieselben Felder, dieselbe Reihenfolge, aus EINEM Baustein', () => {
	test('Trip und Vergleich zeigen Status, Kanaele, naechster und letzter Versand in gleicher Reihenfolge', async () => {
		const Kachel = await laden(path.join(HOME, 'SubscriptionKachel.svelte'));
		const t = html(Kachel, { kind: 'trip', sub: TRIP, nextSend: 'Do 07:00 (CEST)', lastSent: 'gestern' });
		const c = html(Kachel, { kind: 'vergleich', sub: PRESET, nextSend: 'Fr 07:00 (CEST)', lastSent: 'gestern' });
		const soll = ['status', 'channels', 'next-send', 'last-sent'];
		assert.deepEqual(feldNamen(t), soll, 'Trip: Felder/Reihenfolge');
		assert.deepEqual(feldNamen(c), soll, 'Vergleich: Felder/Reihenfolge');
	});

	test('compact-Vergleichs-Kachel zeigt Kanaele sowie naechsten und letzten Versand (AC-16)', async () => {
		const Card = await laden(path.join(ORGANISMS, 'SubscriptionCard.svelte'));
		const h = html(Card, {
			kind: 'vergleich', sub: PRESET, now: JETZT, compact: true,
			channels: ['Email', 'Telegram'], nextSend: 'Fr 07:00 (CEST)', lastSent: 'gestern'
		});
		assert.deepEqual(kanaele(h), ['Email', 'Telegram']);
		assert.match(h, /Fr 07:00 \(CEST\)/);
		assert.match(h, /gestern/);
		assert.match(h, /data-testid="subscription-card-cmp-1"/);
	});

	test('fehlende Werte zeigen den ehrlichen Leerzustand "—", nie leere Felder', async () => {
		const Kachel = await laden(path.join(HOME, 'SubscriptionKachel.svelte'));
		for (const [kind, sub] of [['trip', TRIP], ['vergleich', PRESET]] as const) {
			const h = html(Kachel, { kind, sub, nextSend: null, lastSent: null });
			const feld = (f: string) => new RegExp(`data-field="${f}"[^>]*>([^]*?)</(?:span|div)>`).exec(h)?.[1] ?? '';
			assert.match(feld('last-sent'), /—/, `${kind}: letzter Versand`);
			assert.match(feld('next-send'), /—/, `${kind}: naechster Versand`);
		}
	});
});

describe('AC-9: Trip-Kanaele kommen aus den report_config-Flags, nie aus empfaenger', () => {
	test('nur send_email an, empfaenger enthaelt Telegram => ausschliesslich Email', async () => {
		const Kachel = await laden(path.join(HOME, 'SubscriptionKachel.svelte'));
		assert.deepEqual(kanaele(html(Kachel, { kind: 'trip', sub: TRIP })).map((k) => k.toLowerCase()), ['email']);
	});

	test('Gegenprobe: alle vier Flags => vier Kanaele', async () => {
		const Kachel = await laden(path.join(HOME, 'SubscriptionKachel.svelte'));
		const trip = { ...TRIP, empfaenger: [], report_config: { enabled: true, send_email: true, send_telegram: true, send_sms: true, send_premium_sms: true } };
		assert.deepEqual(kanaele(html(Kachel, { kind: 'trip', sub: trip })).map((k) => k.toLowerCase()), ['email', 'telegram', 'sms', 'premium-sms']);
	});
});

describe('AC-17: Kennung und Link beider kinds', () => {
	test('Trip: subscription-card-{id}, data-kind, Name als echter Link auf den Hub; kein altes trip-card', async () => {
		const Kachel = await laden(path.join(HOME, 'SubscriptionKachel.svelte'));
		const h = html(Kachel, { kind: 'trip', sub: TRIP });
		assert.match(h, /data-testid="subscription-card-trip-1"/);
		assert.match(h, /data-kind="trip"/);
		assert.match(h, /<a[^>]*href="\/trips\/trip-1"[^>]*>[^<]*GR20 Nord/);
		assert.doesNotMatch(h, /data-testid="trip-card"/);
	});

	test('Vergleich: Name verlinkt auf /compare/{id}', async () => {
		const Kachel = await laden(path.join(HOME, 'SubscriptionKachel.svelte'));
		const h = html(Kachel, { kind: 'vergleich', sub: PRESET });
		assert.match(h, /data-kind="vergleich"/);
		assert.match(h, /<a[^>]*href="\/compare\/cmp-1"[^>]*>[^<]*Ortsvergleich Nord/);
	});
});

describe('AC-18: naechster/letzter Versand aus der Backend-Antwort, ohne eigene Rechnung', () => {
	const NB = { at: '2026-10-22T07:00:00+02:00', local_date: '2026-10-22', local_time: '07:00', tz: 'Europe/Paris', tz_abbr: 'CEST', slot: 'morning' };

	test('Trip mit Termin: Wert aus local_date/local_time/tz_abbr; letzter Versand null bis S4', async () => {
		const { kachelVersand } = await modul(path.join(HOME, 'kachelVersand.ts'));
		assert.deepEqual(kachelVersand('trip', TRIP, NB), { nextSend: 'Do 07:00 (CEST)', lastSent: null });
	});

	test('at === null: der Grund statt eines Zeitpunkts (Trip und Vergleich)', async () => {
		const { kachelVersand } = await modul(path.join(HOME, 'kachelVersand.ts'));
		assert.equal(kachelVersand('trip', TRIP, { at: null, reason: 'paused' }).nextSend, 'pausiert');
		assert.equal(kachelVersand('vergleich', PRESET, { at: null, reason: 'ended' }).nextSend, 'Ortsvergleich beendet');
	});

	test('Antwort fehlt: "—" statt erfundener Zeit', async () => {
		const { kachelVersand } = await modul(path.join(HOME, 'kachelVersand.ts'));
		assert.equal(kachelVersand('trip', TRIP, null).nextSend, '—');
	});

	test('Vergleich: letzter Versand aus letzter_versand; ohne Wert null', async () => {
		const { kachelVersand } = await modul(path.join(HOME, 'kachelVersand.ts'));
		const mit = kachelVersand('vergleich', { ...PRESET, letzter_versand: new Date().toISOString() }, NB);
		assert.equal(mit.lastSent, 'heute');
		assert.equal(kachelVersand('vergleich', { ...PRESET, letzter_versand: undefined }, NB).lastSent, null);
	});

	test('Kachel rendert den gemappten Wert (Verdrahtung Mapping -> Anzeige)', async () => {
		const Kachel = await laden(path.join(HOME, 'SubscriptionKachel.svelte'));
		const { kachelVersand } = await modul(path.join(HOME, 'kachelVersand.ts'));
		const h = html(Kachel, { kind: 'trip', sub: TRIP, ...kachelVersand('trip', TRIP, { at: null, reason: 'paused' }) });
		assert.match(h, /pausiert/);
	});
});

describe('AC-10: tote Bausteine und Doppelungen sind weg', () => {
	const weg: Array<[string, string]> = [
		['routes/_home/TripKachel.svelte', path.join(HOME, 'TripKachel.svelte')],
		['routes/_home/CompareKachel.svelte', path.join(HOME, 'CompareKachel.svelte')],
		['organisms/HomeHeroTrip.svelte', path.join(ORGANISMS, 'HomeHeroTrip.svelte')],
		['organisms/HomeHeroCompare.svelte', path.join(ORGANISMS, 'HomeHeroCompare.svelte')],
		['molecules/CompareIdealRow.svelte', path.join(FRONTEND, 'src/lib/components/molecules/CompareIdealRow.svelte')]
	];
	for (const [name, abs] of weg) {
		test(`${name} existiert nicht mehr`, () => assert.ok(!existsSync(abs), `${name} existiert noch (RED)`));
	}

	test('Barrel organisms/index.ts exportiert HomeHeroTrip/HomeHeroCompare nicht mehr', async () => {
		const barrel = await import(pathToFileURL(path.join(ORGANISMS, 'index.ts')).href).catch((e) => ({ __fehler: e }));
		assert.ok(!('__fehler' in barrel), 'Barrel laedt nicht (veralteter Import auf geloeschte Datei?)');
		assert.ok(!('HomeHeroTrip' in barrel) && !('HomeHeroCompare' in barrel), 'Barrel exportiert noch HomeHero*');
	});
});
