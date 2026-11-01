// Issue #2660 (i18n F11, Epic #2644) — AC-4 und AC-5: die geteilten Bausteine
// sprechen die Nutzersprache. Echter SSR-Render (svelte/server) unter
// `locale.set('en')` bzw. `'de'`; geprueft werden gerenderte Texte und
// `aria-label`/`title` gegen `trFor(...)`-Werte (en) bzw. gegen die Golden-
// Literale des Quelltexts vor der Umstellung (de, wortgleich). Keine
// Dateiinhalts-Pruefung.
//
// Der bits-ui-Dialog gibt unter svelte/server keinen Inhalt aus; fuer
// ConfirmDialog/SendConfirmDialog ersetzt `dialogRahmenHook.mjs` NUR den
// Dialog-Rahmen durch durchreichende Elemente, die Bausteine selbst sind echt.
// Spec: docs/specs/modules/i18n_f11_bausteine_ts_2660.md
//
//   cd frontend && npm test -- src/lib/components/__tests__/bausteine_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');
const COMPONENTS = path.resolve(HERE, '..');
const base = pathToFileURL(FRONTEND + '/').href;
const hook = (p: string) => register(pathToFileURL(p).href, base);
hook(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs'));
hook(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'));
hook(path.join(COMPONENTS, 'trip-new/__tests__/ssrRunesHook.mjs'));
hook(path.join(HERE, 'dialogRahmenHook.mjs'));

const { render } = await import('svelte/server');
const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const { sendTargetLabel } = await import(pathToFileURL(path.join(COMPONENTS, 'shared/versand-tab/sendTargetLabel.ts')).href);
const lade = async (rel: string) => (await import(pathToFileURL(path.join(COMPONENTS, rel)).href)).default;

afterEach(() => locale.set('de'));

const ohneKommentare = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
const html = (komp: unknown, props: Record<string, unknown>) =>
	ohneKommentare(render(komp as never, { props: props as never }).body);
const ent = (s: string) =>
	s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
const text = (h: string) => ent(h.replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();
const attribute = (h: string, name: string) => [...h.matchAll(new RegExp(`\\s${name}="([^"]*)"`, 'g'))].map((m) => ent(m[1]));
const DEUTSCH = /[äöüÄÖÜß]|\b(Zurück|Abbrechen|Weitere|Aktionen|Senden|Briefing senden|Berichtsart|Versand|Kanäle|Profil|Eigenes|Vorlage|Schliessen|Pausentag|heute|letzte|Schwellen|Keine)\b/;

const TRIP = { id: 'trip-1', name: 'GR20 Nord', region: 'Korsika', stages: [{ id: 's1', name: 'E1', date: '2026-10-17', waypoints: [] }] };
const PRESET = { id: 'cmp-1', name: 'GR20 Nord', location_ids: ['a', 'b'], schedule: 'daily', profil: 'wintersport' };
const JETZT = new Date('2026-10-17T12:00:00Z');
const leer = () => {};

/** Alle gemessenen Bausteine; jeder liefert sein HTML in der aktuellen Sprache. */
async function bausteine(): Promise<Record<string, string>> {
	const [BackLink, ConfirmDialog, SendConfirmDialog, ListActionsMenu, SubscriptionKebab, OutboxCard, PresetRail, SubscriptionCard] =
		await Promise.all([
			lade('atoms/BackLink.svelte'),
			lade('molecules/ConfirmDialog.svelte'),
			lade('molecules/SendConfirmDialog.svelte'),
			lade('organisms/ListActionsMenu.svelte'),
			lade('molecules/SubscriptionKebab.svelte'),
			lade('organisms/OutboxCard.svelte'),
			lade('organisms/PresetRail.svelte'),
			lade('organisms/SubscriptionCard.svelte')
		]);
	const dialog = { open: true, profile: null, subscription: null, onConfirm: leer, onCancel: leer };
	return {
		backLinkA: html(BackLink, { href: '/trips', label: 'Trips' }),
		backLinkButton: html(BackLink, { href: '/trips', label: 'Trips', onclick: leer }),
		confirm: html(ConfirmDialog, {
			open: true, title: 'T', description: 'D', confirmLabel: 'OK', onConfirm: leer, onCancel: leer, onOpenChange: leer
		}),
		sendTrip: html(SendConfirmDialog, { ...dialog, kind: 'trip' }),
		sendVergleich: html(SendConfirmDialog, { ...dialog, kind: 'vergleich' }),
		listMenu: html(ListActionsMenu, { actions: [], onSelect: leer }),
		kebab: html(SubscriptionKebab, { actions: [] }),
		outbox: html(OutboxCard, { contextName: 'GR20', reports: [] }),
		presetRail: html(PresetRail, { presets: [{ id: 'p', name: 'Eigen', builtin: false, metrics: [] }], totalActive: 3 }),
		cardTrip: html(SubscriptionCard, { kind: 'trip', sub: TRIP, now: JETZT, dense: true, onAction: leer, channels: [] }),
		cardVergleich: html(SubscriptionCard, { kind: 'vergleich', sub: PRESET, now: JETZT, dense: true, onAction: leer, channels: [] })
	};
}

describe('AC-4: Englisch — kein deutsches Wort in Beschriftung und aria-label', () => {
	test('Texte und Attribute kommen aus dem englischen Katalog', async () => {
		locale.set('en');
		const b = await bausteine();
		const weitere = trFor('en', 'aktionen.weitere');
		assert.deepEqual(attribute(b.backLinkA, 'aria-label'), [trFor('en', 'aktionen.zurueck_zu', { ziel: 'Trips' })]);
		assert.deepEqual(attribute(b.backLinkButton, 'aria-label'), [trFor('en', 'aktionen.zurueck_zu', { ziel: 'Trips' })]);
		assert.ok(text(b.confirm).includes(trFor('en', 'aktionen.abbrechen')), text(b.confirm));
		assert.ok(text(b.sendTrip).includes(trFor('en', 'aktionen.senden')), text(b.sendTrip));
		assert.ok(text(b.sendTrip).includes(trFor('en', 'bausteine.senden_dialog.titel')), text(b.sendTrip));
		assert.ok(attribute(b.sendTrip, 'aria-label').includes(trFor('en', 'bausteine.senden_dialog.berichtsart')));
		assert.ok(text(b.sendTrip).includes(trFor('en', 'bausteine.senden_dialog.morgen')), text(b.sendTrip));
		assert.ok(attribute(b.listMenu, 'aria-label').includes(weitere));
		assert.ok(attribute(b.kebab, 'aria-label').includes(weitere), b.kebab);
		assert.ok(attribute(b.cardTrip, 'aria-label').includes(weitere));
		assert.ok(text(b.outbox).includes(trFor('en', 'bausteine.versand.heute')), text(b.outbox));
		assert.ok(text(b.outbox).includes(trFor('en', 'bausteine.versand.alle_kanaele_ok')));
		assert.ok(text(b.presetRail).includes(trFor('en', 'bausteine.profil.wetter_profil')), text(b.presetRail));
		assert.ok(text(b.presetRail).includes(trFor('en', 'bausteine.profil.eigenes')));
		assert.ok(text(b.cardTrip).includes(trFor('en', 'bausteine.abo.keine_kanaele')), text(b.cardTrip));
		// Das Versandziel im Dialog liefert sendTargetLabel (Versand-Reiter, Paket F6), nicht F11.
		const versandziel = sendTargetLabel(null, null).text;
		for (const [name, h] of Object.entries(b)) {
			// Eigennamen (GR20, Korsika, Trips) und Nutzerdaten sind keine Katalogtexte.
			// Kachel-Text des Ortsvergleichs (Zeitplan, Profil, Orte-Zahl) liefert compare/subscriptionHelpers
			// (Pakete F3/F10); hier zaehlen dort nur die Attribute des Bausteins.
			const sichtbar = name === 'cardVergleich' ? '' : text(h).replace(versandziel, '');
			const gemessen = [sichtbar, ...attribute(h, 'aria-label'), ...attribute(h, 'title')].join(' | ');
			assert.doesNotMatch(gemessen, DEUTSCH, `${name}: ${gemessen}`);
		}
	});

	test('Trip- und Ortsvergleich-Verwendung zeigen denselben Text', async () => {
		locale.set('en');
		const b = await bausteine();
		assert.equal(text(b.sendTrip).split(' ').slice(0, 3).join(' '), text(b.sendVergleich).split(' ').slice(0, 3).join(' '));
		assert.ok(text(b.sendVergleich).includes(trFor('en', 'bausteine.senden_dialog.titel')));
		assert.deepEqual(attribute(b.cardTrip, 'aria-label'), attribute(b.cardVergleich, 'aria-label'));
		assert.deepEqual(attribute(b.cardTrip, 'title'), attribute(b.cardVergleich, 'title'));
	});
});

describe('AC-5: Deutsch — wortgleich zur Ausgabe vor der Umstellung', () => {
	test('Golden-Literale', async () => {
		locale.set('de');
		const b = await bausteine();
		assert.deepEqual(attribute(b.backLinkA, 'aria-label'), ['Zurück: Trips']);
		assert.deepEqual(attribute(b.backLinkButton, 'aria-label'), ['Zurück: Trips']);
		assert.ok(text(b.confirm).includes('Abbrechen'), text(b.confirm));
		assert.ok(text(b.sendTrip).startsWith('Briefing senden?'), text(b.sendTrip));
		assert.ok(attribute(b.sendTrip, 'aria-label').includes('Berichtsart'));
		assert.match(text(b.sendTrip), /Abbrechen.*Senden/);
		assert.match(text(b.sendTrip), /Morgen.*Abend/);
		assert.deepEqual(attribute(b.listMenu, 'aria-label'), ['Weitere Aktionen']);
		assert.deepEqual(attribute(b.listMenu, 'title'), ['Weitere Aktionen']);
		assert.ok(attribute(b.kebab, 'aria-label').includes('Weitere Aktionen'));
		assert.ok(attribute(b.kebab, 'title').includes('Weitere Aktionen'));
		assert.ok(attribute(b.cardTrip, 'aria-label').includes('Weitere Aktionen'));
		assert.ok(text(b.outbox).includes('Versand · heute'));
		assert.ok(text(b.outbox).includes('Was geht raus · GR20'));
		assert.ok(text(b.outbox).includes('Alle Kanäle ok'));
		assert.ok(text(b.presetRail).includes('Wetter-Profil'));
		assert.ok(text(b.presetRail).includes('Vorlage wählen oder eigenes Profil anlegen.'));
		assert.ok(text(b.presetRail).includes('EIGEN'));
		assert.ok(text(b.presetRail).includes('Eigenes Profil'));
		assert.ok(text(b.presetRail).includes('Aktuelle Auswahl (3 Metriken) als Profil sichern.'));
		assert.ok(text(b.presetRail).includes('+ Als Profil speichern'));
		assert.ok(text(b.cardTrip).includes('noch keine Kanäle'));
		assert.ok(text(b.cardTrip).includes('1 Etappen · 2026-10-17'), text(b.cardTrip));
	});

	test('eigenes cancelLabel gewinnt weiterhin', async () => {
		locale.set('en');
		const ConfirmDialog = await lade('molecules/ConfirmDialog.svelte');
		const h = html(ConfirmDialog, {
			open: true, title: 'T', description: 'D', confirmLabel: 'OK', cancelLabel: 'Eigen', onConfirm: leer, onCancel: leer, onOpenChange: leer
		});
		assert.ok(text(h).includes('Eigen'));
		assert.ok(!text(h).includes(trFor('en', 'aktionen.abbrechen')));
	});
});
