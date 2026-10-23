// TDD RED — Issue #2278 (Epic #2345 P3), AC-14 (+ AC-2 Filter-Pillen, AC-6 Blatt-Aktionen mobil).
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — Implementation Details 7.
//
// Bei Trip UND Ortsvergleich sieht der Nutzer mobil DIESELBE Karte (`SubscriptionCard`), DASSELBE
// Aktionsblatt (`SubscriptionActionSheet`) und DIESELBEN Filter-Pillen (`StatusFilterPills`).
// Diese Bausteine rendern unter `svelte/server` (kein bits-ui-Portal in der dichten Karte, `Sheet` ist
// eine einfache Komponente) und werden deshalb ECHT gerendert und am HTML gemessen.
//
// Vertrag (hier festgelegt, /50 baut danach):
//   organisms/SubscriptionCard.svelte   Props: kind ('trip'|'vergleich'), sub, now?, dense?, compact?,
//                                        onclick?, onAction?(id), actions? (explizite Aktionsliste fuers Kebab
//                                        der NICHT-dichten Karte; Default = subscriptionActions(kind,status,'list');
//                                        die Startseiten-Kachel uebergibt compareKachelActions(), AC-15)
//     -> Wurzel data-testid="subscription-card-{id}", data-kind, data-status (Lebenszyklus:
//        draft|active|paused|archived — dieselbe Ableitung wie subscriptionLifecycle), Name im Text;
//        dense + onAction: Menue-Knopf data-testid="subscription-card-menu-{id}" (aria-label "Weitere Aktionen").
//   mobile/SubscriptionActionSheet.svelte  Props: open, onClose, kind, status, name?, onAction(id), surface? ('mobile')
//     -> je Aktion aus subscriptionActions(kind,status,surface) ein <button data-testid="subscription-action-{id}">Label</button>
//   molecules/StatusFilterPills.svelte  Props: active, counts {all,aktiv,geplant,pausiert,fertig}, onSelect(value)
//     -> fuenf <button data-testid="status-filter-pill-{value}" aria-pressed> "Label (n)" in der Reihenfolge
//        Alle · Aktiv · Geplant · Pausiert · Fertig
//
// RED heute: alle drei Komponenten existieren nicht.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/organisms/__tests__/subscription_card.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { existsSync } from 'node:fs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> organisms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const COMPONENTS = path.resolve(HERE, '../..');

register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const { subscriptionActions } = (await import(
	pathToFileURL(path.join(COMPONENTS, 'shared/subscriptionActions.ts')).href
).catch(() => ({}))) as any;

async function laden(rel: string): Promise<any> {
	const datei = path.join(COMPONENTS, rel);
	assert.ok(existsSync(datei), `${rel} fehlt (RED) — AC-14 geteilter Baustein.`);
	return (await import(pathToFileURL(datei).href)).default;
}
const html = (comp: any, props: Record<string, unknown>) => render(comp, { props }).body.replace(/<!--.*?-->/g, '');

const TRIP = {
	id: 'trip-1',
	name: 'GR20 Nord',
	region: 'Korsika',
	stages: [{ id: 's1', name: 'E1', date: '2026-10-17', waypoints: [] }]
};
const PRESET = { id: 'cmp-1', name: 'GR20 Nord', location_ids: ['a', 'b'], schedule: 'daily', profil: 'wintersport' };
const JETZT = new Date('2026-10-17T12:00:00Z');

describe('AC-14: SubscriptionCard — dieselbe Karte fuer beide Arten', () => {
	test('Trip und Ortsvergleich: Wurzel-Testid, data-kind, data-status, Name', async () => {
		const Card = await laden('organisms/SubscriptionCard.svelte');
		const t = html(Card, { kind: 'trip', sub: TRIP, now: JETZT, dense: true, onAction: () => {}, onclick: () => {} });
		const c = html(Card, { kind: 'vergleich', sub: PRESET, dense: true, onAction: () => {}, onclick: () => {} });
		assert.match(t, /data-testid="subscription-card-trip-1"/);
		assert.match(c, /data-testid="subscription-card-cmp-1"/);
		assert.match(t, /data-kind="trip"/);
		assert.match(c, /data-kind="vergleich"/);
		assert.match(t, /data-status="active"/);
		assert.match(c, /data-status="active"/);
		assert.match(t, /GR20 Nord/);
		assert.match(c, /GR20 Nord/);
	});

	test('pausiert/archiviert: data-status folgt dem Lebenszyklus beider Arten', async () => {
		const Card = await laden('organisms/SubscriptionCard.svelte');
		const p = html(Card, { kind: 'trip', sub: { ...TRIP, paused_at: '2026-10-01T00:00:00Z' }, now: JETZT, dense: true });
		const v = html(Card, { kind: 'vergleich', sub: { ...PRESET, schedule: 'manual' }, dense: true });
		assert.match(p, /data-status="paused"/);
		assert.match(v, /data-status="paused"/);
	});

	test('dichte Karte mit onAction: Menue-Knopf "Weitere Aktionen" bei BEIDEN Arten; ohne onAction keiner', async () => {
		const Card = await laden('organisms/SubscriptionCard.svelte');
		for (const [kind, sub, id] of [['trip', TRIP, 'trip-1'], ['vergleich', PRESET, 'cmp-1']] as const) {
			const mit = html(Card, { kind, sub, now: JETZT, dense: true, onAction: () => {} });
			assert.match(mit, new RegExp(`data-testid="subscription-card-menu-${id}"`), `${kind}: Menue-Knopf fehlt`);
			assert.match(mit, /aria-label="Weitere Aktionen"/);
			const ohne = html(Card, { kind, sub, now: JETZT, dense: true });
			assert.doesNotMatch(ohne, /subscription-card-menu-/, `${kind}: Menue-Knopf ohne onAction`);
		}
	});

	test('beide Arten teilen dieselbe Struktur: gleiche Menge an data-testid-Mustern', async () => {
		const Card = await laden('organisms/SubscriptionCard.svelte');
		const muster = (h: string) =>
			[...h.matchAll(/data-testid="([^"]+)"/g)].map((m) => m[1].replace(/(trip|cmp)-1$/, '{id}')).sort();
		const t = muster(html(Card, { kind: 'trip', sub: TRIP, now: JETZT, dense: true, onAction: () => {}, onclick: () => {} }));
		const c = muster(html(Card, { kind: 'vergleich', sub: PRESET, dense: true, onAction: () => {}, onclick: () => {} }));
		assert.deepEqual(t, c);
	});
});

describe('AC-14/AC-6: SubscriptionActionSheet — dasselbe Blatt, Aktionen aus der einen Quelle', () => {
	for (const status of ['active', 'paused', 'draft'] as const) {
		test(`Status ${status}: Knoepfe == subscriptionActions(kind, status, "mobile") fuer Trip und Ortsvergleich`, async () => {
			assert.ok(subscriptionActions, 'subscriptionActions fehlt (RED)');
			const Sheet = await laden('mobile/SubscriptionActionSheet.svelte');
			for (const kind of ['trip', 'vergleich'] as const) {
				const h = html(Sheet, { open: true, onClose: () => {}, onAction: () => {}, kind, status, name: 'GR20 Nord' });
				const ist = [...h.matchAll(/data-testid="subscription-action-([^"]+)"[^>]*>([^<]*)</g)].map((m) => [m[1], m[2].trim()]);
				const soll = subscriptionActions(kind, status, 'mobile').map((a: any) => [a.id, a.label]);
				assert.deepEqual(ist, soll, `${kind}/${status}`);
			}
		});
	}

	test('beide Arten rendern byte-gleich (nur kind unterscheidet die Eingabe)', async () => {
		const Sheet = await laden('mobile/SubscriptionActionSheet.svelte');
		const props = { open: true, onClose: () => {}, onAction: () => {}, status: 'active', name: 'X' };
		assert.equal(html(Sheet, { ...props, kind: 'trip' }), html(Sheet, { ...props, kind: 'vergleich' }));
	});

	test('"Senden" und "Alarme" sind im Blatt enthalten (AC-2/AC-14)', async () => {
		const Sheet = await laden('mobile/SubscriptionActionSheet.svelte');
		const h = html(Sheet, { open: true, onClose: () => {}, onAction: () => {}, kind: 'vergleich', status: 'active', name: 'X' });
		for (const id of ['send', 'alarms', 'weather', 'edit', 'pause', 'delete'])
			assert.match(h, new RegExp(`subscription-action-${id}"`), `Aktion ${id} fehlt im Blatt`);
		// #1743 AC-27: die Aktion „Vorschau" entfaellt mit dem Vorschau-Reiter.
		assert.doesNotMatch(h, /subscription-action-preview"/, 'Aktion preview steht noch im Blatt');
	});
});

describe('AC-2/AC-14: StatusFilterPills — fuenf Pillen, geteilt', () => {
	test('Reihenfolge Alle · Aktiv · Geplant · Pausiert · Fertig mit Zaehlern; aktive Pille aria-pressed', async () => {
		const Pills = await laden('molecules/StatusFilterPills.svelte');
		const h = html(Pills, { active: 'pausiert', counts: { all: 9, aktiv: 4, geplant: 2, pausiert: 1, fertig: 2 }, onSelect: () => {} });
		const pillen = [...h.matchAll(/<button[^>]*data-testid="status-filter-pill-([a-z]+)"([^>]*)>([\s\S]*?)<\/button>/g)];
		assert.deepEqual(
			pillen.map((m) => m[1]),
			['all', 'aktiv', 'geplant', 'pausiert', 'fertig']
		);
		assert.deepEqual(
			pillen.map((m) => m[3].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim()),
			['Alle (9)', 'Aktiv (4)', 'Geplant (2)', 'Pausiert (1)', 'Fertig (2)']
		);
		const gedrueckt = pillen.filter((m) => /aria-pressed="true"/.test(m[0])).map((m) => m[1]);
		assert.deepEqual(gedrueckt, ['pausiert']);
	});
});
