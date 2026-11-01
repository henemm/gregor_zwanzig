// TDD RED — Issue #2281 (Epic #2345 P4), AC-2 / Test 13.
// Spec: docs/specs/modules/feat_2281_vergleich_versand_historie.md
//
// Zusicherung: In BEIDEN Hubs (Trip `trip-detail/HubOverview.svelte`, Ortsvergleich
// `compare/CompareTabs.svelte`, Reiter Übersicht, dort mobil UND Desktop) zeigt DERSELBE geteilte
// Baustein `shared/BriefingHistory.svelte` die bisherigen Zustellungen als Liste (Slot Morgen/Abend,
// Kanäle, Zeitpunkt, „von Hand") bzw. einen Leerzustand. Der verwaiste Dialog
// `briefing-history/BriefingHistoryDialog.svelte` existiert nicht mehr.
//
// Prüfweg: Unter `svelte/server` laufen weder `$effect` noch `onMount` — ein Fetch passiert beim
// SSR nie. Deshalb zwei Ebenen:
//   (a) Hub-Verdrahtung am AST (echter Svelte-Compiler, `aktionsmodellAst.ts`): welcher Baustein,
//       aus welcher Quelle, mit welchem `kind`/`id`, unter welcher Bedingung.
//   (b) Baustein echt gerendert (`svelte/server`) mit übergebenen Einträgen bzw. leerer Liste,
//       plus URL-Bau als reine Funktion.
//
// Vertrag (hier festgelegt, /50 baut danach — NICHT wörtlich in der Spec, siehe Handback):
//   shared/BriefingHistory.svelte   Props: id: string, kind: 'route'|'vergleich',
//                                   entries?: Array<{sent_at, kind, channels, on_demand?}>
//                                   (gesetzt => direkt rendern, KEIN Fetch; undefined => Fetch auf
//                                   briefingHistoryUrl(id, kind))
//     -> Wurzel data-testid="briefing-history" mit data-kind="{kind}"
//     -> je Eintrag data-testid="briefing-history-entry", data-channels="{channels.join(',')}",
//        Slot-Text „Morgen" (morning) / „Abend" (evening), <time datetime="{sent_at}">,
//        „von Hand" nur bei on_demand === true
//     -> leere Liste: data-testid="briefing-history-empty"
//   shared/briefingHistory.ts       export briefingHistoryUrl(id, kind)
//                                   => `/api/briefings/${id}/briefing-history?kind=${kind}`
//
// RED heute: Baustein, Helfer und beide Einbindungen fehlen; der Dialog existiert noch.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/briefing_history_hubs.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { existsSync } from 'node:fs';
import { ladeSvelte, komponenten, importe, attrKurz, bedingungen } from './__tests__/aktionsmodellAst.ts';
import { umgebungFuer, werte } from './__tests__/svelteInstanzPruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// shared -> components -> lib -> src -> frontend
const COMPONENTS = path.resolve(HERE, '..');
const FRONTEND = path.resolve(HERE, '../../../..');

register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');

const BAUSTEIN = path.join(COMPONENTS, 'shared/BriefingHistory.svelte');
const HELFER = path.join(COMPONENTS, 'shared/briefingHistory.ts');
const TRIP_HUB = path.join(COMPONENTS, 'trip-detail/HubOverview.svelte');
const CMP_HUB = path.join(COMPONENTS, 'compare/CompareTabs.svelte');
const TRIP_TABS = path.join(COMPONENTS, 'trip-detail/TripTabs.svelte');
const UEBERSICHT = path.join(COMPONENTS, 'shared/hub-uebersicht/HubUebersicht.svelte');
const DIALOG = path.join(COMPONENTS, 'briefing-history/BriefingHistoryDialog.svelte');

async function bausteinLaden(): Promise<any> {
	assert.ok(existsSync(BAUSTEIN), 'shared/BriefingHistory.svelte fehlt (RED) — AC-2 geteilter Baustein.');
	return (await import(pathToFileURL(BAUSTEIN).href)).default;
}
const html = (comp: any, props: Record<string, unknown>) =>
	render(comp, { props }).body.replace(/<!--.*?-->/g, '');

/** Einbettungen von <BriefingHistory> plus Nachweis, dass sie aus shared/ importiert wird. */
function einbettungen(datei: string) {
	const ast = ladeSvelte(datei);
	const imp = importe(ast).find((i) => i.namen.includes('BriefingHistory'));
	return { ast, imp, embeds: komponenten(ast, 'BriefingHistory') };
}

// Issue #2682: die Historie steht im geteilten Übersichts-Baustein shared/hub-uebersicht/HubUebersicht.svelte
// (kind={context}, id = Trip- bzw. Vergleichs-Kennung); beide Hubs binden ihn im Reiter Übersicht ein.
describe('AC-2 (a): beide Hubs binden den GETEILTEN Baustein ein', () => {
	test('Übersichts-Baustein: BriefingHistory aus shared/, kind={context}, mobil UND Desktop', () => {
		const { ast, imp, embeds } = einbettungen(UEBERSICHT);
		assert.ok(imp, 'HubUebersicht importiert BriefingHistory nicht.');
		assert.match(imp.quelle, /(^|\/)shared\/BriefingHistory\.svelte$/, `Importquelle ist nicht der geteilte Baustein: ${imp.quelle}`);
		assert.equal(embeds.length, 1, 'HubUebersicht bettet <BriefingHistory> nicht genau einmal ein.');
		const mobil: boolean[] = [];
		const desktop: boolean[] = [];
		for (const e of embeds) {
			assert.equal(attrKurz(e, 'kind'), 'context', 'Baustein muss kind={context} übergeben.');
			const b = bedingungen(ast.fragment, e);
			assert.ok(b, 'Einbettung ist nicht erreichbar.');
			const mob = b.filter((x) => x.includes('isMobileViewport'));
			if (mob.length === 0) {
				mobil.push(true);
				desktop.push(true);
			} else if (mob.every((x) => x === 'isMobileViewport')) mobil.push(true);
			else if (mob.every((x) => x === '!(isMobileViewport)')) desktop.push(true);
		}
		assert.ok(mobil.length > 0, 'Kein Pfad zeigt die Historie MOBIL (isMobileViewport).');
		assert.ok(desktop.length > 0, 'Kein Pfad zeigt die Historie auf dem DESKTOP (!isMobileViewport).');
	});

	test('Übersichts-Baustein: id der Historie = trip.id (route) bzw. preset.id (vergleich)', async () => {
		const leer = { trip: undefined, preset: undefined, status: undefined, orte: undefined, saveController: undefined, onJump: undefined, children: undefined };
		const r = await umgebungFuer(UEBERSICHT, { ...leer, context: 'route', trip: { id: 't-7', stages: [] } }, { jsAlsTs: true });
		const v = await umgebungFuer(UEBERSICHT, { ...leer, context: 'vergleich', preset: { id: 'cmp-3', location_ids: [] } }, { jsAlsTs: true });
		const e = komponenten(r.ast, 'BriefingHistory')[0];
		const idAusdruck = attrKurz(e, 'id') ?? '';
		assert.equal(werte(idAusdruck, r.u), 't-7', 'Trip-Übersicht übergibt nicht id={trip.id}');
		assert.equal(werte(idAusdruck, v.u), 'cmp-3', 'Vergleichs-Übersicht übergibt nicht id={preset.id}');
	});

	test('Trip-Hub: TripTabs bindet die Übersicht mit context="route" im Reiter Übersicht ein; HubOverview lädt keine eigene Historie', () => {
		const ast = ladeSvelte(TRIP_TABS);
		const e = komponenten(ast, 'HubUebersicht');
		assert.equal(e.length, 1, 'TripTabs bindet HubUebersicht nicht genau einmal ein.');
		assert.equal(attrKurz(e[0], 'context'), '"route"');
		assert.equal(attrKurz(e[0], 'trip'), 'trip');
		const b = bedingungen(ast.fragment, e[0]) ?? [];
		assert.ok(b.some((x) => x.includes('"uebersicht"')), `Einbindung steht nicht im Reiter Übersicht: ${JSON.stringify(b)}`);
		assert.equal(komponenten(ladeSvelte(TRIP_HUB), 'BriefingHistory').length, 0, 'HubOverview bettet die Historie zusätzlich ein (zwei Abrufe, AC-12).');
	});

	test('Ortsvergleich-Hub: CompareTabs bindet die Übersicht mit context="vergleich" im Reiter Übersicht ein', () => {
		const ast = ladeSvelte(CMP_HUB);
		const e = komponenten(ast, 'HubUebersicht');
		assert.equal(e.length, 1, 'CompareTabs bindet HubUebersicht nicht genau einmal ein.');
		assert.equal(attrKurz(e[0], 'context'), '"vergleich"');
		assert.equal(attrKurz(e[0], 'preset'), 'preset');
		const b = bedingungen(ast.fragment, e[0]);
		assert.ok(b && b.includes('activeTab === "uebersicht"'), `Einbindung steht nicht im Reiter Übersicht: ${JSON.stringify(b)}`);
		assert.equal(komponenten(ast, 'BriefingHistory').length, 0, 'CompareTabs bettet die Historie zusätzlich ein (zwei Abrufe, AC-12).');
	});

	test('der verwaiste Dialog briefing-history/BriefingHistoryDialog.svelte existiert nicht mehr', () => {
		assert.equal(existsSync(DIALOG), false, 'BriefingHistoryDialog.svelte existiert noch (RED) — muss gelöscht werden.');
	});
});

describe('AC-2 (b): der Baustein rendert Liste bzw. Leerzustand', () => {
	const EINTRAEGE = [
		{ sent_at: '2026-10-20T05:00:00Z', kind: 'morning', channels: ['email', 'telegram'], on_demand: false },
		{ sent_at: '2026-10-20T16:00:00Z', kind: 'evening', channels: ['sms'], on_demand: true }
	];

	for (const kind of ['route', 'vergleich'] as const) {
		test(`kind=${kind}: zwei Einträge — Slot, Kanäle, Zeitpunkt, „von Hand" genau einmal`, async () => {
			const Comp = await bausteinLaden();
			const out = html(Comp, { id: 'x-1', kind, entries: EINTRAEGE });
			assert.match(out, new RegExp(`data-testid="briefing-history"[^>]*data-kind="${kind}"|data-kind="${kind}"[^>]*data-testid="briefing-history"`), 'Wurzel mit data-kind fehlt.');
			const eintraege = out.split('data-testid="briefing-history-entry"').length - 1;
			assert.equal(eintraege, 2, 'Es müssen genau zwei Einträge gerendert werden.');
			assert.ok(out.includes('Morgen'), 'Slot „Morgen" fehlt.');
			assert.ok(out.includes('Abend'), 'Slot „Abend" fehlt.');
			assert.ok(out.includes('data-channels="email,telegram"'), 'Kanäle des ersten Eintrags fehlen.');
			assert.ok(out.includes('data-channels="sms"'), 'Kanäle des zweiten Eintrags fehlen.');
			assert.ok(out.includes('datetime="2026-10-20T05:00:00Z"'), 'Zeitpunkt (time datetime) des ersten Eintrags fehlt.');
			assert.ok(out.includes('datetime="2026-10-20T16:00:00Z"'), 'Zeitpunkt (time datetime) des zweiten Eintrags fehlt.');
			assert.equal(out.split('von Hand').length - 1, 1, '„von Hand" muss genau einmal (nur bei on_demand) erscheinen.');
			assert.ok(!out.includes('data-testid="briefing-history-empty"'), 'Leerzustand darf bei Einträgen nicht erscheinen.');
		});

		test(`kind=${kind}: keine Einträge — Leerzustand, keine Zeile`, async () => {
			const Comp = await bausteinLaden();
			const out = html(Comp, { id: 'x-1', kind, entries: [] });
			assert.ok(out.includes('data-testid="briefing-history-empty"'), 'Leerzustand fehlt.');
			assert.ok(!out.includes('data-testid="briefing-history-entry"'), 'Leerzustand darf keine Zeile zeigen.');
		});
	}

	test('briefingHistoryUrl baut den kind-neutralen Endpunkt', async () => {
		assert.ok(existsSync(HELFER), 'shared/briefingHistory.ts fehlt (RED).');
		const { briefingHistoryUrl } = await import(pathToFileURL(HELFER).href);
		assert.equal(briefingHistoryUrl('trip-7', 'route'), '/api/briefings/trip-7/briefing-history?kind=route');
		assert.equal(briefingHistoryUrl('cmp-3', 'vergleich'), '/api/briefings/cmp-3/briefing-history?kind=vergleich');
	});
});
