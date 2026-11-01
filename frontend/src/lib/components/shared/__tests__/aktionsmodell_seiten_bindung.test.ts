// Fix-Loop 1 — Issue #2278, F001/F002/F003/F006/F007/F008/F011/F013 (AC-1, AC-3, AC-4, AC-5, AC-10, AC-11, AC-12, AC-16).
// Die Zusicherungen wirken an der SEITENVERDRAHTUNG (Liste/Hub beider Arten), nicht im Helfer: welche
// Aktion in welchen Zweig faellt, welches Argument in den Request geht, wer das Konto-Profil bekommt,
// dass „Senden" nur den Dialog oeffnet. Kein DOM in der Kernsuite (bits-ui rendert unter svelte/server
// nichts) — verglichen wird die Bindung als exakter, formatunabhaengiger Ausdruck (aktionsmodellAst.kurz).
// Vertauschtes Argument, falscher Zweig, fehlendes Profil, direktes Senden: jedes wird hier rot.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/aktionsmodell_seiten_bindung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ladeSvelte,
	komponenten,
	collect,
	attrKurz,
	funktion,
	initialisierer,
	zweig,
	zuweisungen,
	aufrufArgumente,
	mitAttribut,
	bedingungen,
	aufrufe,
	lokaleBindungen,
	kurz
} from './aktionsmodellAst.ts';

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const { trFor } = await import('../../../i18n/index.ts');
const TRIPS = ladeSvelte(path.join(SRC, 'routes/trips/+page.svelte'));
const TRIP_HUB = ladeSvelte(path.join(SRC, 'routes/trips/[id]/+page.svelte'));
const CMP = ladeSvelte(path.join(SRC, 'routes/compare/+page.svelte'));
const CMP_HUB = ladeSvelte(path.join(SRC, 'routes/compare/[id]/+page.svelte'));

const dlg = (ast: any) => komponenten(ast, 'SendConfirmDialog')[0];
const sheet = (ast: any) => komponenten(ast, 'SubscriptionActionSheet')[0];

describe('F006: Dispatch der Listen — Aktion -> Zweig -> Wirkung', () => {
	const tabelle = (art: 'trips' | 'compare') => {
		const t = art === 'trips' ? '`/trips/${t.id}' : '"/compare/" + p.id';
		const ende = (tab: string) => (art === 'trips' ? `goto(${t}?tab=${tab}\`)` : `goto(${t} + "?tab=${tab}")`);
		const basis = art === 'trips' ? `goto(${t}\`)` : `goto(${t})`;
		const v = art === 'trips' ? 't' : 'p';
		const toggle = art === 'trips' ? 'togglePause' : 'togglePause';
		return {
			pause: `void ${toggle}(${v}, true)`,
			resume: `void ${toggle}(${v}, false)`,
			send: `sendTarget = ${v}`,
			// #1743 AC-27: die Aktion „Vorschau" entfaellt (kein Zweig 'preview' mehr)
			alarms: ende('alarme'),
			weather: ende('wetter-metriken'),
			edit: basis,
			'continue-setup': basis,
			delete: `deleteTarget = ${v}`
		};
	};
	for (const [name, ast, fn, art] of [
		['Trip-Liste', TRIPS, 'onTripAction', 'trips'],
		['Compare-Liste', CMP, 'onCompareAction', 'compare']
	] as const) {
		test(`${name}: jede Aktion faellt in ihren Zweig mit der richtigen Wirkung`, () => {
			for (const [id, erwartet] of Object.entries(tabelle(art)))
				assert.deepEqual(zweig(funktion(ast, fn), 'key', id), [erwartet], `${name}: ${id}`);
		});
		test(`#1743 AC-27: ${name} hat keinen Zweig 'preview' mehr`, () => {
			assert.deepEqual(zweig(funktion(ast, fn), 'key', 'preview'), [], `${name}: Vorschau-Zweig existiert noch`);
		});
	}
	test('Trip-Hub: pausieren/fortsetzen schreiben den richtigen Zielzustand; Archivieren fragt, Loeschen fragt', () => {
		const f = funktion(TRIP_HUB, 'handleHubAction');
		assert.deepEqual(zweig(f, 'id', 'pause'), ['void sendStateUpdate(true, undefined)']);
		assert.deepEqual(zweig(f, 'id', 'resume'), ['void sendStateUpdate(false, undefined)']);
		assert.deepEqual(zweig(f, 'id', 'archive'), ['handleArchiveClick()']);
		assert.deepEqual(zweig(f, 'id', 'unarchive'), ['handleArchiveClick()']);
		assert.deepEqual(zweig(f, 'id', 'delete'), ['handleDeleteClick()']);
		assert.equal(kurz(funktion(TRIP_HUB, 'handleArchiveClick').body), '{ archiveDialogOpen = true }');
	});
	test('Compare-Hub: archive/unarchive/delete in ihren eigenen Zweigen', () => {
		const f = funktion(CMP_HUB, 'handleAction');
		assert.deepEqual(zweig(f, 'id', 'pause'), ['{ void togglePause() }']);
		assert.deepEqual(zweig(f, 'id', 'resume'), ['{ void togglePause() }']);
		assert.deepEqual(zweig(f, 'id', 'archive'), ['{ void archivePreset() }']);
		assert.deepEqual(zweig(f, 'id', 'unarchive'), ['{ void unarchivePreset() }']);
		assert.deepEqual(zweig(f, 'id', 'delete'), ['{ deleteDialogOpen = true }']);
		assert.deepEqual(aufrufArgumente(funktion(CMP_HUB, 'archivePreset'), 'setArchived'), [['"vergleich"', 'currentPreset.id', 'true']]);
		assert.deepEqual(aufrufArgumente(funktion(CMP_HUB, 'unarchivePreset'), 'setArchived'), [['"vergleich"', 'currentPreset.id', 'false']]);
	});
	test('die Adapter-Aufrufe geben den Zielzustand `paused` unveraendert weiter', () => {
		assert.deepEqual(aufrufArgumente(funktion(TRIPS, 'togglePause'), 'setPaused'), [['"trip"', 'trip.id', 'paused']]);
		assert.deepEqual(aufrufArgumente(funktion(CMP, 'togglePause'), 'setPaused'), [['"vergleich"', 'preset.id', 'paused']]);
	});
	test('mobiles Blatt und Zeilenmenue teilen einen Dispatch (kein toter Sheet-Handler)', () => {
		assert.equal(kurz(sheet(TRIPS).attributes.find((a: any) => a.name === 'onAction').value.expression), '(id) => { if (actionTrip) onTripAction(id, actionTrip) }');
		assert.equal(kurz(sheet(CMP).attributes.find((a: any) => a.name === 'onAction').value.expression), '(id) => { if (actionPreset) onCompareAction(id, actionPreset) }');
	});
});

describe('F001: „Senden" oeffnet nur den Dialog; gesendet wird erst nach Bestaetigung', () => {
	test('Trip-Hub: Primaerknopf setzt nur sendDialogOpen, Dialog-Bestaetigung ist handleSendConfirm', () => {
		const btn = mitAttribut(TRIP_HUB, 'data-testid', 'subscription-hub-send')[0];
		assert.equal(attrKurz(btn, 'onclick'), '() => { sendDialogOpen = true }');
		assert.equal(attrKurz(btn, 'disabled'), 'sendLoading || lifecycle === "archived" || lifecycle === "draft"');
		assert.equal(attrKurz(dlg(TRIP_HUB), 'onConfirm'), 'handleSendConfirm');
		assert.equal(attrKurz(dlg(TRIP_HUB), 'open'), 'sendDialogOpen');
	});
	test('Compare-Hub: Primaerknopf setzt nur sendDialogOpen, Bestaetigung schliesst und sendet', () => {
		const btn = mitAttribut(CMP_HUB, 'data-testid', 'subscription-hub-send')[0];
		assert.equal(attrKurz(btn, 'onclick'), '() => sendDialogOpen = true');
		assert.equal(attrKurz(btn, 'disabled'), 'isSending || lifecycle === "archived"');
		assert.equal(attrKurz(dlg(CMP_HUB), 'onConfirm'), '() => { sendDialogOpen = false; void handleTestSend() }');
		assert.deepEqual(aufrufArgumente(funktion(CMP_HUB, 'handleTestSend'), 'sendSubscription'), [['"vergleich"', 'currentPreset.id']]);
	});
	test('F022: der Zeilen-Primaerknopf „Briefing senden" ist an die Liste gebunden (Trip UND Compare)', () => {
		const tabelle = (ast: any) => komponenten(ast, 'ListTable')[0];
		assert.equal(attrKurz(tabelle(TRIPS), 'rowPrimary'), 'tripRowPrimary');
		assert.equal(attrKurz(tabelle(CMP), 'rowPrimary'), 'compareRowPrimary');
		assert.deepEqual(bedingungen(CMP.fragment, tabelle(CMP)), [], 'Compare-Tabelle steht unter einer Bedingung');
	});
	test('Listen: Dialog-Bestaetigung ist confirmSend, offen = Ziel gesetzt', () => {
		for (const ast of [TRIPS, CMP]) {
			assert.equal(attrKurz(dlg(ast), 'onConfirm'), 'confirmSend');
			assert.equal(attrKurz(dlg(ast), 'open'), 'sendTarget !== null');
		}
	});
});

describe('F002 (AC-10): jede Seite gibt dem Dialog das Profil des angemeldeten Nutzers', () => {
	for (const [name, ast, kind] of [
		['Trip-Liste', TRIPS, '"trip"'],
		['Trip-Hub', TRIP_HUB, '"trip"'],
		['Compare-Liste', CMP, '"vergleich"'],
		['Compare-Hub', CMP_HUB, '"vergleich"']
	] as const) {
		test(`${name}: profile = data.profile, kind = ${kind}`, () => {
			assert.equal(attrKurz(dlg(ast), 'profile'), 'data.profile');
			assert.equal(attrKurz(dlg(ast), 'kind'), kind);
		});
	}
});

describe('F003 (AC-4): die gewaehlte Berichtsart erreicht den Request', () => {
	test('Trip-Liste und Trip-Hub: erster Parameter der Bestaetigung geht als reportType in sendSubscription', () => {
		const liste = funktion(TRIPS, 'confirmSend');
		const hub = funktion(TRIP_HUB, 'handleSendConfirm');
		assert.deepEqual(liste.params.map(kurz), ['berichtsart']);
		assert.deepEqual(hub.params.map(kurz), ['berichtsart']);
		assert.deepEqual(aufrufArgumente(liste, 'sendSubscription'), [['"trip"', 'target.id', '{ reportType: berichtsart }']]);
		assert.deepEqual(aufrufArgumente(hub, 'sendSubscription'), [['"trip"', 'trip.id', '{ reportType: berichtsart }']]);
	});
	test('Compare-Liste sendet ohne Berichtsart', () => {
		assert.deepEqual(aufrufArgumente(funktion(CMP, 'confirmSend'), 'sendSubscription'), [['"vergleich"', 'target.id']]);
	});
});

describe('F007 (AC-11/AC-2): Archiv-Ausblendung, Filter und Pillenzaehler', () => {
	test('Refetch der Trip-Liste blendet Archiviertes aus', () => {
		assert.deepEqual(zuweisungen(funktion(TRIPS, 'refetchTrips'), 'trips'), [
			'await api.get("/api/trips").filter((t) => t.archived_at == null)'
		]);
	});
	test('Mobilfilter wirkt und die Karten iterieren die GEFILTERTE Liste', () => {
		assert.equal(kurz(initialisierer(TRIPS, 'mobileFiltered')), '$derived(filteredTrips.filter((t) => mobileFilter === "all" || tripStatus(t, now) === mobileFilter))');
		assert.equal(kurz(initialisierer(CMP, 'mobilePresets')), '$derived(presets.filter((p) => mobileFilter === "all" || compareFilterStatus(p) === mobileFilter))');
		const each = (ast: any) => collect(ast.fragment, (n) => n.type === 'EachBlock').map((n) => kurz(n.expression));
		assert.ok(each(TRIPS).includes('mobileFiltered'));
		assert.deepEqual(each(CMP), ['mobilePresets']);
	});
	test('jeder Pillenzaehler vergleicht gegen SEINEN Status', () => {
		const zaehler = (ast: any, f: string, status: string) => `${f}.filter((${f === 'presets' ? 'p' : 't'}) => ${status}).length`;
		const trips = kurz(initialisierer(TRIPS, 'pillCounts'));
		const cmp = kurz(initialisierer(CMP, 'pillCounts'));
		for (const s of ['aktiv', 'geplant', 'pausiert', 'fertig'])
			assert.ok(trips.includes(`${s}: ${zaehler(TRIPS, 'filteredTrips', `tripStatus(t, now) === "${s}"`)}`), `Trip ${s}`);
		for (const s of ['aktiv', 'pausiert', 'fertig'])
			assert.ok(cmp.includes(`${s}: ${zaehler(CMP, 'presets', `compareFilterStatus(p) === "${s}"`)}`), `Compare ${s}`);
	});
});

describe('F008 (AC-5/AC-12): Trip-Hub Loeschdialog, Navigation, Menue-Flaeche', () => {
	const bestaetigungen = () => komponenten(TRIP_HUB, 'ConfirmDialog');
	test('Loeschdialog nennt trip.name; Bestaetigen loescht und navigiert auf /trips', () => {
		const del = bestaetigungen().find((c) => attrKurz(c, 'confirmTestid') === '"trip-detail-delete-confirm-yes"')!;
		assert.match(attrKurz(del, 'description')!, /\$\{trip\.name\}/);
		assert.equal(attrKurz(del, 'onConfirm'), 'handleDeleteConfirm');
		assert.deepEqual(aufrufArgumente(funktion(TRIP_HUB, 'handleDeleteConfirm'), 'goto'), [['"/trips"']]);
		assert.deepEqual(aufrufArgumente(funktion(TRIP_HUB, 'handleDeleteConfirm'), 'deleteSubscription'), [['"trip"', 'trip.id']]);
	});
	test('Archivieren/Reaktivieren laeuft ueber die Rueckfrage und schreibt erst bei Bestaetigung', () => {
		const arch = bestaetigungen().find((c) => attrKurz(c, 'confirmTestid') === '"trip-detail-archive-confirm-yes"')!;
		assert.equal(attrKurz(arch, 'onConfirm'), 'handleArchiveConfirm');
		assert.deepEqual(aufrufArgumente(funktion(TRIP_HUB, 'handleArchiveConfirm'), 'sendStateUpdate'), [['undefined', 'nextArchived']]);
	});
	test('beide Huebs: Kebab und Blatt zeigen die Hub-Aktionen (Flaeche "hub")', () => {
		assert.equal(attrKurz(komponenten(TRIP_HUB, 'SubscriptionKebab')[0], 'actions'), 'subscriptionActions("trip", lifecycle, "hub")');
		assert.equal(attrKurz(komponenten(CMP_HUB, 'SubscriptionKebab')[0], 'actions'), 'subscriptionActions("vergleich", lifecycle, "hub")');
		assert.equal(attrKurz(komponenten(TRIP_HUB, 'SubscriptionKebab')[0], 'onSelect'), 'handleHubAction');
		assert.equal(attrKurz(komponenten(CMP_HUB, 'SubscriptionKebab')[0], 'onSelect'), 'handleAction');
		for (const ast of [TRIP_HUB, CMP_HUB]) {
			assert.equal(attrKurz(sheet(ast), 'surface'), '"hub"');
			assert.equal(attrKurz(sheet(ast), 'status'), 'lifecycle');
		}
		assert.equal(attrKurz(sheet(TRIP_HUB), 'onAction'), 'handleHubAction');
		assert.equal(attrKurz(sheet(CMP_HUB), 'onAction'), 'handleAction');
	});
});

describe('F011 (AC-17): Fehler und Erfolg des Versands/Pausierens werden angezeigt', () => {
	const zeigt = (ast: any, test: string, wert: string) =>
		collect(ast.fragment, (n) => n.type === 'IfBlock' && kurz(n.test) === test).some(
			(n) => collect(n.consequent, (x) => x.type === 'ExpressionTag' && kurz(x.expression) === wert).length > 0
		);
	test('Trip-Liste: Versandfehler und Pausierfehler landen in `error`, das gerendert wird', () => {
		assert.deepEqual(zuweisungen(funktion(TRIPS, 'confirmSend'), 'error'), ['null', 'o.message']);
		// #2652 (i18n F3): Erfolgstext aus dem Katalog; deutsch unveraendert.
		assert.deepEqual(zuweisungen(funktion(TRIPS, 'confirmSend'), 'sendInfo'), ['null', 'tr("listen.meldung.versendet")']);
		assert.equal(trFor('de', 'listen.meldung.versendet'), 'Briefing wurde versendet.');
		assert.ok(zuweisungen(funktion(TRIPS, 'togglePause'), 'error').length === 2, 'Pausierfehler wird nicht gesetzt');
		assert.ok(zeigt(TRIPS, 'error', 'error') && zeigt(TRIPS, 'sendInfo', 'sendInfo'));
	});
	test('Compare-Liste: Versandfehler landet in `error`, das gerendert wird', () => {
		assert.deepEqual(zuweisungen(funktion(CMP, 'confirmSend'), 'error'), ['null', 'o.message']);
		assert.ok(zeigt(CMP, 'error', 'error') && zeigt(CMP, 'sendInfo', 'sendInfo'));
	});
	test('Loeschen: DELETE ueber den Adapter, danach verschwindet der Eintrag aus der Liste', () => {
		const t = funktion(TRIPS, 'handleDelete');
		assert.deepEqual(aufrufArgumente(t, 'deleteSubscription'), [['"trip"', 'target.id']]);
		assert.deepEqual(zuweisungen(t, 'trips'), ['trips.filter((t) => t.id !== target.id)']);
		const c = funktion(CMP, 'confirmDelete');
		assert.deepEqual(aufrufArgumente(c, 'deleteSubscription'), [['"vergleich"', 'target.id']]);
		assert.deepEqual(zuweisungen(c, 'presets'), ['presets.filter((p) => p.id !== target.id)']);
	});
	test('Trip-Hub: ok-Zweig setzt sendStatus "ok" (gerendert als test-briefing-success), Fehler als "error"', () => {
		assert.deepEqual(zuweisungen(funktion(TRIP_HUB, 'handleSendConfirm'), 'sendStatus'), ['"idle"', '"ok"', '"error"', '"idle"']);
		assert.deepEqual(zuweisungen(funktion(TRIP_HUB, 'handleSendConfirm'), 'sendMessage'), ['null', 'o.message']);
		const ok = collect(TRIP_HUB.fragment, (n) => n.type === 'IfBlock' && kurz(n.test) === 'sendStatus === "ok"');
		assert.equal(mitAttribut({ fragment: ok[0].consequent }, 'data-testid', 'test-briefing-success').length, 1);
	});
});

describe('F019/F015/F018: die Bindung steht UNTER DER ERWARTETEN Bedingung (kein toter Zweig)', () => {
	const unter = (ast: any, knoten: any) => bedingungen(ast.fragment, knoten);
	test('Dialog und Aktionsblatt aller vier Seiten stehen unbedingt', () => {
		for (const [name, ast] of [['Trip-Liste', TRIPS], ['Trip-Hub', TRIP_HUB], ['Compare-Liste', CMP], ['Compare-Hub', CMP_HUB]] as const) {
			assert.deepEqual(unter(ast, dlg(ast)), [], `${name}: SendConfirmDialog steht unter einer Bedingung`);
			assert.deepEqual(unter(ast, sheet(ast)), [], `${name}: SubscriptionActionSheet steht unter einer Bedingung`);
		}
	});
	test('Hub-Kebab: Trip = „nicht mobil" (else von {#if mobil}), Compare = {#if !mobil} — exakt, ohne Zusatzbedingung', () => {
		assert.deepEqual(unter(TRIP_HUB, komponenten(TRIP_HUB, 'SubscriptionKebab')[0]), ['!(mobil)']);
		assert.deepEqual(unter(CMP_HUB, komponenten(CMP_HUB, 'SubscriptionKebab')[0]), ['!mobil']);
	});
	test('Hub-Primaerknopf „Senden": Trip unbedingt, Compare nur ausserhalb des Entwurfs', () => {
		assert.deepEqual(unter(TRIP_HUB, mitAttribut(TRIP_HUB, 'data-testid', 'subscription-hub-send')[0]), []);
		assert.deepEqual(unter(CMP_HUB, mitAttribut(CMP_HUB, 'data-testid', 'subscription-hub-send')[0]), ['!(status === "draft")']);
	});
	test('Schreib-/Sendeaufrufe der Handler stehen unbedingt (kein if (false), kein toter Zweig)', () => {
		for (const [ast, fn, ziel] of [
			[TRIPS, 'togglePause', 'setPaused'],
			[TRIPS, 'confirmSend', 'sendSubscription'],
			[TRIPS, 'handleDelete', 'deleteSubscription'],
			[CMP, 'togglePause', 'setPaused'],
			[CMP, 'confirmSend', 'sendSubscription'],
			[CMP, 'confirmDelete', 'deleteSubscription'],
			[TRIP_HUB, 'handleSendConfirm', 'sendSubscription'],
			[TRIP_HUB, 'handleDeleteConfirm', 'deleteSubscription'],
			[CMP_HUB, 'handleTestSend', 'sendSubscription'],
			[CMP_HUB, 'deletePreset', 'deleteSubscription'],
			[CMP_HUB, 'archivePreset', 'setArchived'],
			[CMP_HUB, 'unarchivePreset', 'setArchived'],
			[CMP_HUB, 'handleDeleteConfirm', 'deletePreset'],
			[TRIPS, 'togglePause', 'refetchTrips'],
			[CMP, 'togglePause', 'fetch']
		] as const) {
			const f = funktion(ast, fn);
			const calls = aufrufe(f, ziel);
			assert.equal(calls.length, 1, `${fn}: ${ziel} nicht (erreichbar) gefunden`);
			assert.deepEqual(bedingungen(f, calls[0]), [], `${fn}: ${ziel} steht unter einer Bedingung`);
		}
	});
});

describe('F013 (AC-17): toter Code im Trip-Hub', () => {
	test('handlePauseClick existiert nicht mehr', () => {
		assert.ok(!lokaleBindungen(TRIP_HUB).has('handlePauseClick'));
	});
});

describe('Fix-Loop 2 (AC-3/AC-12): Senden-Primaerknopf ist auf JEDER Breite erreichbar', () => {
	// Vorfahren-Elemente mit nacktem Klassen-Token `hidden` (= ohne Breakpoint-Praefix) blenden den
	// Knopf unterhalb des Desktop-Breakpoints aus („hidden desktop:flex").
	const versteckendeVorfahren = (ast: any, knoten: any): string[] =>
		collect(ast.fragment, (n) => n.type === 'RegularElement' || n.type === 'Component')
			.filter((el) => collect(el, (k) => k === knoten).length > 0)
			.flatMap((el) => {
				const klasse = (el.attributes ?? []).find((a: any) => a.type === 'Attribute' && a.name === 'class');
				const text = klasse ? collect(klasse, (k) => k.type === 'Text').map((k) => k.data).join(' ') : '';
				return text.split(/\s+/).includes('hidden') ? [`${el.name}.${text}`] : [];
			});
	for (const [name, ast] of [['Trip-Hub', TRIP_HUB], ['Compare-Hub', CMP_HUB]] as const) {
		test(`${name}: kein Vorfahre des Senden-Knopfs ist unterhalb des Desktop-Breakpoints versteckt`, () => {
			const btn = mitAttribut(ast, 'data-testid', 'subscription-hub-send')[0];
			assert.ok(btn, `${name}: Senden-Knopf fehlt`);
			assert.deepEqual(versteckendeVorfahren(ast, btn), []);
		});
	}
	test('Compare-Hub: das Aktionsblatt bleibt mobil ueber den Kebab erreichbar (nicht doppelt gebaut)', () => {
		assert.equal(mitAttribut(CMP_HUB, 'data-testid', 'subscription-kebab').length, 2);
		assert.equal(komponenten(CMP_HUB, 'SubscriptionActionSheet').length, 1);
	});
});
