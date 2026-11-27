// # doc-compliance-test
// TDD RED — Issue #3443 (S5d aus #2797, Epic #2791): Seitenbindung „Aktivieren“ (Kopf-Knopf, Kebab, Wechsel-Erkennung).
// Spec: docs/specs/modules/feat_3443_entwurf_aktivieren.md — ZUSATZ zu AC-3, AC-6, AC-12 (kein Verhaltensnachweis).
//
// Dieser Test liest die Verdrahtung am AST (aktionsmodellAst.ts, echter Svelte-5-Parser) und ist als
// `# doc-compliance-test` gekennzeichnet: er ERSETZT KEINEN Verhaltensnachweis. Das Verhalten belegen
// entwurf_aktivieren.test.ts (Modell), aktivierungs_wechsel_laufzeit.test.ts (Runen-Modul, echte Client-Laufzeit),
// trip_hub_aktionen_verhalten.test.ts / compare_hub_aktionen_verhalten.test.ts (echter Instanz-Code der Seiten)
// und frontend/e2e/hub-entwurf-aktivieren.staging.spec.ts (Staging).
//
// VERTRAG für den Developer (Namen festgelegt):
//   HubKopf.svelte    Prop `onAktivieren?: () => void` (ersetzt `aktivierenHref`); im hub-kopf-status ein
//                     <Btn variant="accent" size="sm" data-testid="hub-kopf-aktivieren" onclick={…onAktivieren…}>
//                     OHNE href, nur unter der Bedingung `onAktivieren` (kein Zweig nach `context`).
//   TripHeader.svelte Prop `onAktivieren?: () => void`; reicht sie NUR im Entwurf an HubKopf weiter
//                     (Ausdruck mit `tripStatus === "draft"`).
//   trips/[id]/+page.svelte   function handleAktivieren(); <TripHeader onAktivieren={handleAktivieren} …>;
//                     handleHubAction: if (id === 'activate') handleAktivieren();
//                     erstelleAktivierungsWechsel(() => ({ context: 'route', id: trip.id, lifecycle }), holen, meldenFn)
//   compare/[id]/+page.svelte function handleAktivieren(); <HubKopf onAktivieren={status === 'draft' ? handleAktivieren : undefined} …>
//                     (Bedingung auf den Entwurf, Variable `status` oder `lifecycle`);
//                     handleAction: if (id === 'activate') handleAktivieren();
//                     erstelleAktivierungsWechsel(() => ({ context: 'vergleich', id: currentPreset.id, lifecycle }), holen, meldenFn)
//   handleAktivieren nutzt fehltFuerAktivierung/hinweisFuer/zielFuer (shared/entwurfAktivieren) und goto; kein
//   Schreibweg (setPaused, setArchived, deleteSubscription, sendSubscription, sendStateUpdate, togglePause,
//   toggleActiveFromParent, api.put/patch/post/delete, fetch).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/aktivieren_seiten_bindung.test.ts

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
	zweig,
	importe,
	mitAttribut,
	bedingungen,
	aufrufe,
	erreichbar,
	ids,
	kurz,
	type Knoten
} from './aktionsmodellAst.ts';

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const TRIP_HUB = ladeSvelte(path.join(SRC, 'routes/trips/[id]/+page.svelte'));
const CMP_HUB = ladeSvelte(path.join(SRC, 'routes/compare/[id]/+page.svelte'));
const TRIP_HEADER = ladeSvelte(path.join(SRC, 'lib/components/trip-detail/TripHeader.svelte'));
const HUB_KOPF = ladeSvelte(path.join(SRC, 'lib/components/shared/hub-kopf/HubKopf.svelte'));

const SEITEN = [
	{ name: 'Trip-Hub', ast: TRIP_HUB, dispatch: 'handleHubAction', context: 'route', id: 'trip.id' },
	{ name: 'Orte-Hub', ast: CMP_HUB, dispatch: 'handleAction', context: 'vergleich', id: 'currentPreset.id' }
] as const;

/** Funktionsknoten oder ein lesbarer RED-Fehler statt eines Wurfs aus dem Helfer. */
function fn(ast: Knoten, name: string, wo: string): Knoten {
	try {
		return funktion(ast, name);
	} catch {
		assert.fail(`${wo}: Funktion ${name} fehlt`);
	}
}

const SCHREIBWEGE = [
	'setPaused',
	'setArchived',
	'deleteSubscription',
	'sendSubscription',
	'sendTestAlarm',
	'sendStateUpdate',
	'togglePause',
	'toggleActiveFromParent',
	'archivePreset',
	'unarchivePreset',
	'deletePreset',
	'loescheTrip',
	'fetch'
];

describe('HubKopf: „Aktivieren“ ist ein Knopf (onAktivieren), kein Link, ohne Zweig nach context (AC-1/AC-12)', () => {
	test('Btn hub-kopf-aktivieren: variant accent, size sm, kein href, Klick ruft onAktivieren', () => {
		const btn = mitAttribut(HUB_KOPF, 'data-testid', 'hub-kopf-aktivieren');
		assert.equal(btn.length, 1, `hub-kopf-aktivieren ${btn.length}× im HubKopf`);
		assert.equal(btn[0].name, 'Btn');
		assert.equal(attrKurz(btn[0], 'href'), undefined, `„Aktivieren“ hat noch ein href: ${attrKurz(btn[0], 'href')}`);
		assert.equal(attrKurz(btn[0], 'variant'), '"accent"');
		assert.equal(attrKurz(btn[0], 'size'), '"sm"');
		const klick = attrKurz(btn[0], 'onclick') ?? '';
		assert.match(klick, /\bonAktivieren\b/, `Klick ruft nicht onAktivieren: ${klick}`);
	});
	test('der Knopf steht nur unter `onAktivieren`, nicht unter `context`', () => {
		const btn = mitAttribut(HUB_KOPF, 'data-testid', 'hub-kopf-aktivieren')[0];
		assert.ok(btn, 'hub-kopf-aktivieren fehlt');
		const bed = bedingungen(HUB_KOPF.fragment, btn) ?? [];
		assert.ok(bed.some((b) => /\bonAktivieren\b/.test(b)), `Bedingungen: ${JSON.stringify(bed)}`);
		assert.ok(!bed.some((b) => /\bcontext\b/.test(b)), `Zweig nach context: ${JSON.stringify(bed)}`);
	});
	test('aktivierenHref ist überall entfallen (HubKopf, TripHeader, beide Seiten)', () => {
		for (const [name, ast] of [['HubKopf', HUB_KOPF], ['TripHeader', TRIP_HEADER], ['Trip-Hub', TRIP_HUB], ['Orte-Hub', CMP_HUB]] as const) {
			const alleIds = new Set([...ids(ast.instance), ...ids(ast.fragment)]);
			const attrs = collect(ast.fragment, (n) => n.type === 'Attribute' && n.name === 'aktivierenHref');
			assert.ok(!alleIds.has('aktivierenHref') && attrs.length === 0, `${name} nennt noch aktivierenHref`);
			assert.ok(!alleIds.has('AKTIVIEREN_ZIEL'), `${name} hält noch die Ziel-Konstante des Links`);
		}
	});
});

describe('TripHeader reicht onAktivieren nur im Entwurf an den HubKopf (AC-1)', () => {
	test('HubKopf-Einbettung: onAktivieren nur bei tripStatus === "draft"', () => {
		const kopf = komponenten(TRIP_HEADER, 'HubKopf');
		assert.equal(kopf.length, 1);
		const a = attrKurz(kopf[0], 'onAktivieren') ?? '';
		assert.match(a, /\bonAktivieren\b/, `TripHeader reicht onAktivieren nicht weiter: ${a}`);
		assert.match(a, /tripStatus === "draft"|"draft" === tripStatus/, `TripHeader gibt den Knopf nicht nur im Entwurf: ${a}`);
	});
});

for (const s of SEITEN) {
	describe(`${s.name}: Kopf-Knopf und Kebab rufen dieselbe Seitenfunktion (AC-6)`, () => {
		test(`Kebab-Zweig „activate“ in ${s.dispatch} ruft handleAktivieren()`, () => {
			const z = zweig(fn(s.ast, s.dispatch, s.name), 'id', 'activate');
			assert.equal(z.length, 1, `${s.name}: Zweig „activate“ ${z.length}×`);
			assert.match(z[0], /^(\{ )?(void )?handleAktivieren\(\)( \})?$/, `${s.name}: activate → ${z[0]}`);
		});
		test('Kopf-Einbettung bindet onAktivieren an handleAktivieren', () => {
			const kopf = collect(s.ast.fragment, (n) => n.type === 'Component' && (n.attributes ?? []).some((a: Knoten) => a.name === 'onTest'));
			assert.equal(kopf.length, 1, `${s.name}: Kopf-Einbettung nicht genau einmal`);
			const a = attrKurz(kopf[0], 'onAktivieren') ?? '';
			assert.match(a, /\bhandleAktivieren\b/, `${s.name}: onAktivieren = ${a || '(fehlt)'}`);
			if (s.name === 'Orte-Hub')
				assert.match(a, /(status|lifecycle) === "draft"/, `Orte-Hub gibt den Knopf nicht nur im Entwurf: ${a}`);
		});
		test('handleAktivieren nutzt das geteilte Modell und navigiert mit goto — ohne Schreibweg (AC-3/AC-4)', () => {
			const imp = importe(s.ast).find((i) => /shared\/entwurfAktivieren(\.(js|ts))?$/.test(i.quelle));
			assert.ok(imp, `${s.name}: importiert shared/entwurfAktivieren nicht`);
			for (const n of ['fehltFuerAktivierung', 'hinweisFuer', 'zielFuer']) assert.ok(imp!.namen.includes(n), `${s.name}: ${n} nicht importiert`);
			const r = erreichbar(s.ast, fn(s.ast, 'handleAktivieren', s.name));
			for (const n of ['fehltFuerAktivierung', 'hinweisFuer', 'zielFuer', 'goto'])
				assert.ok(r.bezeichner.has(n), `${s.name}: handleAktivieren erreicht ${n} nicht`);
			for (const w of SCHREIBWEGE) assert.ok(!r.bezeichner.has(w), `${s.name}: Klickpfad erreicht Schreibweg ${w}`);
			const apiSchreib = r.knoten.flatMap((k) =>
				collect(k, (n) => n.type === 'MemberExpression' && n.object?.name === 'api' && ['put', 'patch', 'post', 'delete', 'del'].includes(n.property?.name))
			);
			assert.deepEqual(apiSchreib.map(kurz), [], `${s.name}: Klickpfad schreibt über api`);
		});
		test('goto mit noScroll und keepFocus (Seite bleibt stehen, kein Neuladen)', () => {
			const r = erreichbar(s.ast, fn(s.ast, 'handleAktivieren', s.name));
			const args = r.knoten.flatMap((k) => aufrufe(k, 'goto')).map((c) => (c.arguments ?? []).map(kurz));
			assert.ok(args.length >= 1, `${s.name}: kein goto im Klickpfad`);
			for (const a of args) assert.match(a[1] ?? '', /noScroll: true.*keepFocus: true|keepFocus: true.*noScroll: true/, `${s.name}: goto(${a.join(', ')})`);
		});
	});

	describe(`${s.name}: Wechsel-Erkennung „Aktiviert“ ist gebunden (AC-7/AC-12)`, () => {
		test('importiert erstelleAktivierungsWechsel aus shared/aktivierungsWechsel.svelte und ruft es genau einmal', () => {
			const imp = importe(s.ast).find((i) => /shared\/aktivierungsWechsel\.svelte(\.(js|ts))?$/.test(i.quelle));
			assert.ok(imp && imp.namen.includes('erstelleAktivierungsWechsel'), `${s.name}: Import fehlt`);
			const calls = aufrufe(s.ast.instance, 'erstelleAktivierungsWechsel');
			assert.equal(calls.length, 1, `${s.name}: erstelleAktivierungsWechsel ${calls.length}×`);
			assert.deepEqual(bedingungen(s.ast.instance, calls[0]), [], `${s.name}: Aufruf steht unter einer Bedingung`);
			assert.equal(calls[0].arguments.length, 3, `${s.name}: erwartet (quelle, holen, beiMeldung)`);
		});
		test(`Quelle liest context „${s.context}“, id ${s.id} und den Lebenszyklus der Seite`, () => {
			const calls = aufrufe(s.ast.instance, 'erstelleAktivierungsWechsel');
			assert.equal(calls.length, 1);
			const q = kurz(calls[0].arguments[0]);
			assert.ok(q.includes(`context: "${s.context}"`), `${s.name}: Quelle ${q}`);
			assert.ok(q.includes(`id: ${s.id}`), `${s.name}: Quelle ${q}`);
			assert.ok(q.includes('lifecycle: lifecycle'), `${s.name}: Quelle ${q}`);
		});
		// Fix-Loop 1 (F002): die Seite schließt Abruf und Meldung wirklich an (kein No-op, keine Null-Antwort).
		test('holen ruft api.get mit dem übergebenen Pfad', () => {
			const holen = aufrufe(s.ast.instance, 'erstelleAktivierungsWechsel')[0]?.arguments?.[1];
			assert.equal(holen?.type, 'ArrowFunctionExpression', `${s.name}: holen ist keine Pfeilfunktion`);
			assert.equal(holen.params.length, 1, `${s.name}: holen nimmt den Pfad nicht entgegen`);
			const p = kurz(holen.params[0]);
			assert.match(kurz(holen.body), new RegExp(`^(\\{ return )?api\\.get\\(${p}\\)( \\})?$`), `${s.name}: holen = ${kurz(holen)}`);
		});
		test(`beiMeldung leitet den Text an den Meldungsweg der Seite (${s.name === 'Trip-Hub' ? 'meldung = text' : 'meldung(text, true)'})`, () => {
			const bei = aufrufe(s.ast.instance, 'erstelleAktivierungsWechsel')[0]?.arguments?.[2];
			assert.equal(bei?.type, 'ArrowFunctionExpression', `${s.name}: beiMeldung ist keine Pfeilfunktion`);
			assert.equal(bei.params.length, 1, `${s.name}: beiMeldung nimmt den Text nicht entgegen`);
			const t = kurz(bei.params[0]);
			if (s.name === 'Trip-Hub') {
				const z = collect(bei.body, (n) => n.type === 'AssignmentExpression' && n.left?.name === 'meldung');
				assert.deepEqual(z.map((n) => kurz(n.right)), [t], `${s.name}: beiMeldung = ${kurz(bei)}`);
				assert.deepEqual(bedingungen(bei.body, z[0]), [], `${s.name}: Meldung steht unter einer Bedingung`);
			} else {
				const c = aufrufe(bei.body, 'meldung');
				assert.deepEqual(c.map((n) => (n.arguments ?? []).map(kurz)), [[t, 'true']], `${s.name}: beiMeldung = ${kurz(bei)}`);
				assert.deepEqual(bedingungen(bei.body, c[0]), [], `${s.name}: Meldung steht unter einer Bedingung`);
			}
		});
	});
}

// Fix-Loop 1 (F001/F003): Orte-Reiter speichern am Seitenstand vorbei. Der Effekt prüft nach jedem
// erfolgreichen Speichern über aktivierungsUebernahme (Verhalten: entwurf_aktivieren.test.ts), ob der
// frische Stand den Entwurf aktiviert, und übernimmt nur dann.
describe('Orte-Hub: Effekt nach dem Speichern bindet aktivierungsUebernahme (AC-7)', () => {
	const effekte = () => aufrufe(CMP_HUB.instance, '$effect').filter((e) => ids(e).has('aktivierungsUebernahme'));
	test('genau ein unbedingter $effect, ausgelöst von hubSaveCtl.savedAt, fragt aktivierungsUebernahme(lifecycle)', () => {
		const imp = importe(CMP_HUB).find((i) => /shared\/entwurfAktivieren(\.(js|ts))?$/.test(i.quelle));
		assert.ok(imp?.namen.includes('aktivierungsUebernahme'), 'Orte-Hub importiert aktivierungsUebernahme nicht');
		const e = effekte();
		assert.equal(e.length, 1, `Effekt mit aktivierungsUebernahme ${e.length}×`);
		assert.deepEqual(bedingungen(CMP_HUB.instance, e[0]), [], 'Effekt steht unter einer Bedingung');
		const frage = aufrufe(e[0], 'aktivierungsUebernahme');
		assert.deepEqual(frage.map((c) => (c.arguments ?? []).map(kurz)), [['lifecycle']]);
		assert.deepEqual(bedingungen(e[0], frage[0]), ['hubSaveCtl.savedAt'], 'Prüfung hängt nicht am Speicher-Stempel');
	});
	test('übernimmt nur mit der Prüfung: uebernehmeFrischenVergleich(pruefe) unter `pruefe`', () => {
		const e = effekte()[0];
		assert.ok(e, 'Effekt fehlt');
		const decl = collect(e, (n) => n.type === 'VariableDeclarator' && n.init?.callee?.name === 'aktivierungsUebernahme');
		assert.equal(decl.length, 1, 'Ergebnis von aktivierungsUebernahme wird nicht gebunden');
		const v = decl[0].id.name as string;
		const hol = aufrufe(e, 'uebernehmeFrischenVergleich');
		assert.deepEqual(hol.map((c) => (c.arguments ?? []).map(kurz)), [[v]], 'uebernehmeFrischenVergleich ohne Prüfung');
		assert.ok((bedingungen(e, hol[0]) ?? []).includes(v), `Abruf nicht nur im Entwurf: ${JSON.stringify(bedingungen(e, hol[0]))}`);
	});
	test('uebernehmeFrischenVergleich verwirft den frischen Stand, wenn die Prüfung ihn ablehnt — vor der Übernahme', () => {
		const f = fn(CMP_HUB, 'uebernehmeFrischenVergleich', 'Orte-Hub');
		assert.equal(f.params.length, 1, 'uebernehmeFrischenVergleich nimmt keine Prüfung entgegen');
		const p0 = f.params[0];
		const p = String((p0.type === 'AssignmentPattern' ? p0.left : p0).name);
		const wache = collect(f, (n) => n.type === 'IfStatement' && kurz(n) === `if (${p} && !${p}(frisch.daten)) return false`);
		assert.equal(wache.length, 1, `Prüfung ${p} wird nicht auf frisch.daten angewandt`);
		const uebernahme = collect(f, (n) => n.type === 'AssignmentExpression' && n.left?.name === 'currentPreset');
		assert.equal(uebernahme.length, 1);
		assert.ok(wache[0].start < uebernahme[0].start, 'Prüfung kommt erst nach der Übernahme');
	});
});
