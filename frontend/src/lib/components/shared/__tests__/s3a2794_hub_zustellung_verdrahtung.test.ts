// Issue #2794 S3a, Teil-PR 2 (Fix-Loop 1, Adversary F001 + F004): die Einbettung des
// Uebergangsreiters Zustellung in den HUBS — geprueft dort, wo die Zusicherung WIRKT.
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-7 (Inventar im Orts-Briefing:
// Alarme und Aktivieren), AC-5 / §1 (Anker `#versand` springt in den Versand-Abschnitt).
//
// Warum hier und nicht in ZustellungTab: der Baustein rendert den Alarm-Teil des
// Vergleichs nur, WENN der Hub ihm das Snippet `alarmeBereich` uebergibt, und die
// Aktivierungs-Karte nur, wenn der Hub `activation` mitgibt. Fehlt das Attribut an der
// Hub-Einbettung, verschwinden im Orts-Briefing ALLE Alarme bzw. das Aktivieren — der
// Baustein-Waechter bleibt dabei gruen (Mutationen M21/M22). Ebenso springt `?tab=versand`
// bzw. `#versand` nur in den Versand-Abschnitt, wenn der Hub den Sprung-Zaehler
// `versandSprung` an ZustellungTab durchreicht (Mutation M23).
//
// Messweise: AST der ECHTEN Hub-Komponente (svelte/compiler.parse) fuer die Snippet-Kette;
// fuer den Sprung wird der Attribut-Ausdruck an der ZustellungTab-Einbettung gegen das
// ECHTE Instanz-Skript des Hubs (svelteInstanzPruefstand.umgebungFuer) mit `?tab=versand`
// bzw. `?tab=zustellung` ausgewertet — gemessen wird der Wert, der am Baustein ankommt.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_hub_zustellung_verdrahtung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { svelteAst, einbettungenMitWeichen, reiterVon, attribut, propNamen, type Knoten } from './s3a2794Ast.ts';
import { umgebungFuer, findeKomponenten, attributAusdruck, werte } from './svelteInstanzPruefstand.ts';
import { vollerVergleich } from './goMergeServerPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const KOMP = join(HIER, '..', '..');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const DATEI = {
	tripHub: join(KOMP, 'trip-detail', 'TripTabs.svelte'),
	vergleichHub: join(KOMP, 'compare', 'CompareTabs.svelte'),
	zustellung: join(KOMP, 'shared', 'zustellung-tab', 'ZustellungTab.svelte'),
	panel: join(KOMP, 'shared', 'WetterMetrikenVersandPanel.svelte'),
	// #2795 S3b Teilschritt 1b: neue Bausteine des Reiters.
	uebergang: join(KOMP, 'organisms', 'zustellung-tab', 'UebergangBlock.svelte'),
	briefingZeiten: join(KOMP, 'organisms', 'zustellung-tab', 'BriefingZeiten.svelte')
};

/** Die eine ZustellungTab-Einbettung eines Hubs (unter dem Reiter zustellung). */
function zustellungEinbettung(datei: string): { knoten: Knoten; quelle: string; ast: Knoten } {
	const { ast, quelle } = svelteAst(datei);
	const z = einbettungenMitWeichen(ast, quelle, ['ZustellungTab']);
	assert.equal(z.length, 1, `Messaufbau: erwartet genau eine ZustellungTab-Einbettung, gefunden ${z.length}`);
	assert.deepEqual(reiterVon(z[0]), ['zustellung'], 'Messaufbau: ZustellungTab haengt nicht am Reiter zustellung');
	return { knoten: z[0].knoten, quelle, ast };
}

/** Alle `{#snippet name()}`-Bloecke im Markup. */
function snippetBlock(ast: Knoten, name: string): Knoten | null {
	let gefunden: Knoten | null = null;
	(function lauf(n: unknown): void {
		if (gefunden || n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (k.type === 'SnippetBlock' && k.expression?.name === name) {
			gefunden = k;
			return;
		}
		for (const [f, v] of Object.entries(k)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
	})(ast.fragment);
	return gefunden;
}

/** Snippet, das an der Einbettung unter dem Attribut `name` haengt (nur ein nackter Bezeichner zaehlt). */
function snippetAmAttribut(knoten: Knoten, quelle: string, ast: Knoten, name: string): Knoten {
	const a = attribut(knoten, quelle, name);
	assert.ok(a, `F001: die ZustellungTab-Einbettung im Vergleichs-Hub traegt kein Attribut \`${name}\``);
	assert.ok(a!.ausdruck && /^[A-Za-z_$][\w$]*$/.test(a!.ausdruck), `F001: \`${name}\` ist kein Snippet-Bezeichner (${JSON.stringify(a)})`);
	const s = snippetBlock(ast, a!.ausdruck!);
	assert.ok(s, `F001: \`${name}={${a!.ausdruck}}\` — kein {#snippet ${a!.ausdruck}()} im Hub`);
	return s!;
}

/** data-testid-Literale aller Elemente/Komponenten eines Teilbaums. */
function testids(wurzel: Knoten, quelle: string): string[] {
	const out: string[] = [];
	(function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if ((k.type === 'RegularElement' || k.type === 'Component') && Array.isArray(k.attributes)) {
			const t = attribut(k, quelle, 'data-testid');
			if (t?.literal) out.push(t.literal);
		}
		for (const [f, v] of Object.entries(k)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
	})(wurzel.body);
	return out;
}

// ── F001: Vergleichs-Hub reicht Alarme und Aktivieren an den Reiter Zustellung ──

describe('AC-7 (F001): Vergleichs-Hub übergibt ZustellungTab den Alarm-Baustein und die Aktivierungs-Karte', () => {
	// #2795 S3b Teilschritt 1b: die Alarm-Zustellung (Kanaele, Dringlichkeit, Stille Stunden,
	// Mindestabstand) ist jetzt Teil des Reiters selbst (KanalTabelle/StilleStunden, ein Speicherer,
	// s3b2795_zustellung_struktur). Der Hub reicht deshalb KEIN Alarm-Snippet mehr — prueft hier,
	// dass der alte Weg nicht still parallel weiterlaeuft (sonst zwei Speicherwege fuer alert_*).
	test('s3b2795_vergleich_zustellung_ohne_alarmeBereich_alarme_im_reiter_selbst', () => {
		const { knoten, quelle } = zustellungEinbettung(DATEI.vergleichHub);
		assert.equal(attribut(knoten, quelle, 'alarmeBereich'), null, '#2795: der Vergleichs-Hub reicht noch ein alarmeBereich-Snippet an ZustellungTab');
		const { ast: zAst, quelle: zQ } = svelteAst(DATEI.zustellung);
		for (const name of ['KanalTabelle', 'StilleStunden']) {
			assert.equal(einbettungenMitWeichen(zAst, zQ, [name]).length, 1, `#2795: ZustellungTab bettet ${name} nicht genau einmal ein`);
		}
	});

	test('s3a2794_f001_vergleich_zustellung_bekommt_activation_karte', () => {
		const { knoten, quelle, ast } = zustellungEinbettung(DATEI.vergleichHub);
		const s = snippetAmAttribut(knoten, quelle, ast, 'activation');
		const ids = testids(s, quelle);
		assert.ok(ids.includes('compare-hub-activation-card'), `F001: activation-Snippet ohne Aktivierungs-Karte (testids: ${ids.join(', ')})`);
		assert.ok(ids.includes('compare-hub-activation-cta'), `F001: activation-Snippet ohne Aktivieren-Knopf (testids: ${ids.join(', ')})`);
		const knopf = findeKomponenten({ fragment: s.body }, 'Btn').find((b) => attribut(b, quelle, 'data-testid')?.literal === 'compare-hub-activation-cta');
		assert.equal(attributAusdruck(knopf!, quelle, 'onclick'), 'handleToggleActive', 'F001: der Aktivieren-Knopf ruft nicht handleToggleActive');
	});

	// #2795 S3b Teilschritt 1b: die Aktivierungs-Karte steht im Uebergangsblock (der alte
	// Versand-Abschnitt des Panels entfaellt im Reiter). Gemessen wird die Kette Hub -> ZustellungTab
	// -> UebergangBlock -> {@render activation()}.
	test('s3b2795_zustellungtab_reicht_activation_an_den_uebergangsblock_der_sie_rendert', () => {
		const { ast, quelle } = svelteAst(DATEI.zustellung);
		const ueb = einbettungenMitWeichen(ast, quelle, ['UebergangBlock']);
		assert.equal(ueb.length, 1, 'Messaufbau: ZustellungTab bettet den Uebergangsblock nicht genau einmal ein');
		assert.ok(attribut(ueb[0].knoten, quelle, 'activation'), 'F001: ZustellungTab reicht activation nicht an den Uebergangsblock');
		const { ast: uAst, quelle: uQ } = svelteAst(DATEI.uebergang);
		let rendert = false;
		(function lauf(n: unknown): void {
			if (rendert || n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) return n.forEach(lauf);
			const k = n as Knoten;
			if (k.type === 'RenderTag' && /^activation\s*\(/.test(uQ.slice(k.expression.start, k.expression.end).replace(/\?\./g, ''))) {
				rendert = true;
				return;
			}
			for (const [f, v] of Object.entries(k)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
		})(uAst.fragment);
		assert.ok(rendert, 'F001: der Uebergangsblock rendert das Snippet activation nicht');
	});
});

// ── F004: der Sprung-Zaehler versandSprung kommt am Reiter Zustellung an ──────

async function hubUmgebung(kind: 'trip' | 'vergleich', roh: string): Promise<Knoten> {
	const pfad = kind === 'trip' ? '/trips/t-1' : '/compare/c-1';
	const basis: Knoten = {
		initialTab: roh,
		goto: () => Promise.resolve(),
		page: { url: new URL(`http://localhost${pfad}?tab=${roh}`) }
	};
	const saat: Knoten =
		kind === 'trip' ? { ...basis, badges: {} } : { ...basis, preset: vollerVergleich('c-1'), locations: [], orteCount: 3 };
	const { u } = await umgebungFuer(kind === 'trip' ? DATEI.tripHub : DATEI.vergleichHub, saat, { jsAlsTs: true });
	return u;
}

for (const [kind, datei] of [
	['trip', DATEI.tripHub],
	['vergleich', DATEI.vergleichHub]
] as const) {
	describe(`AC-5 (F004) Hub ${kind}: ?tab=versand springt im Reiter Zustellung in den Versand-Abschnitt`, () => {
		for (const [roh, soll] of [
			['versand', 1],
			['briefings', 1],
			['zustellung', 0],
			['alarme', 0]
		] as const) {
			test(`s3a2794_f004_${kind}_versandSprung_kommt_an_zustellungtab_an_${roh}`, async () => {
				const { knoten, quelle } = zustellungEinbettung(datei);
				const ausdruck = attributAusdruck(knoten, quelle, 'versandSprung');
				assert.ok(ausdruck, `F004: die ZustellungTab-Einbettung im ${kind}-Hub traegt kein versandSprung — #versand springt nicht in den Abschnitt`);
				const u = await hubUmgebung(kind, roh);
				assert.equal(werte(ausdruck!, u), soll, `F004: ?tab=${roh} — am Reiter Zustellung kommt versandSprung=${String(werte(ausdruck!, u))} an (erwartet ${soll})`);
			});
		}
	});
}

// #2795 S3b Teilschritt 1b: `#versand` ist jetzt die Karte der Briefing-Zeiten (das Panel steht
// im Uebergangsblock OHNE Versand-Abschnitt). Der Zaehler muss deshalb dort ankommen.
describe('AC-5 (F004): ZustellungTab reicht versandSprung an die Briefing-Zeiten, die #versand tragen', () => {
	test('s3b2795_zustellungtab_reicht_versandSprung_an_briefingzeiten', () => {
		const { ast, quelle } = svelteAst(DATEI.zustellung);
		const bz = einbettungenMitWeichen(ast, quelle, ['BriefingZeiten']);
		assert.equal(bz.length, 1, 'Messaufbau: ZustellungTab bettet BriefingZeiten nicht genau einmal ein');
		assert.equal(attributAusdruck(bz[0].knoten, quelle, 'versandSprung'), 'versandSprung', 'F004: ZustellungTab reicht versandSprung nicht an BriefingZeiten');
		const { ast: bAst } = svelteAst(DATEI.briefingZeiten);
		assert.ok(propNamen(bAst).includes('versandSprung'), 'F004: BriefingZeiten nimmt kein versandSprung');
	});
});
