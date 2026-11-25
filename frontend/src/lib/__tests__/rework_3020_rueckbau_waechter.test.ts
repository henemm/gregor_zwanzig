// TDD RED — Issue #3020 (AC-3, AC-4): Rückbau-Wächter, wächst je Scheibe.
// doc-compliance-test: Strukturwächter (Existenz, Importe, Testtabelle), KEIN Verhaltensnachweis.
//
// STAND = zuletzt gelöschte Scheibe; jede Scheibe erhöht ihn im selben PR. RED der nächsten
// Scheibe ohne Änderung nachweisen: GZ_3020_STAND=<n> node ... --test <diese Datei>.
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { SCHEIBEN, ANZAHL, BLEIBT, type Scheibe } from './rework_3020_umfang.ts';
import { ROTE_LISTE, ROTE_LISTE_ANZAHL } from './rework_3020_rote_liste.ts';

const STAND = Number(process.env.GZ_3020_STAND ?? 1);

const HERE = dirname(fileURLToPath(import.meta.url));
const LIB = join(HERE, '..');
const SRC = join(LIB, '..');
const REPO = join(SRC, '..', '..');
const KOMP = join(LIB, 'components');
const TABELLE = join(REPO, 'docs/specs/modules/rework_3020_testtabelle.md');

const quelltexte = [SRC, join(SRC, '..', 'e2e')].flatMap((d) =>
	(readdirSync(d, { recursive: true }) as string[])
		.filter((f) => /\.(ts|js|mjs|svelte)$/.test(f) && !/node_modules|rework_3020_/.test(f))
		.map((f) => join(d, f))
);

/** Quelltext ohne Kommentare (Block-, HTML- und reine Zeilenkommentare). */
const lies = (f: string) =>
	readFileSync(f, 'utf-8')
		.replace(/\/\*[\s\S]*?\*\/|<!--[\s\S]*?-->/g, '')
		.replace(/^\s*\/\/.*$/gm, '');

/** Absolute Ziele aller import-, export-from- und import()-Angaben (relativ und `$lib`). */
function importziele(datei: string): string[] {
	return [...lies(datei).matchAll(/(?:\bfrom|\bimport)\s*\(?\s*['"](\.{1,2}\/[^'"]+|\$lib\/[^'"]+)['"]/g)].map((m) =>
		(m[1].startsWith('$lib/') ? join(LIB, m[1].slice(5)) : resolve(dirname(datei), m[1])).replace(/\.js$/, '.ts')
	);
}

const ALLE = ([2, 3, 4] as Scheibe[]).flatMap((s) => SCHEIBEN[s].map((p) => ({ s, p, abs: join(KOMP, p) })));
const trifft = (ziel: string, abs: string) => ziel === abs || `${ziel}.ts` === abs;

describe('Umfang (Vakuum-Schutz)', () => {
	test('laenge_je_scheibe_wie_spec_und_keine_dopplung', () => {
		for (const s of [2, 3, 4] as Scheibe[]) assert.equal(SCHEIBEN[s].length, ANZAHL[s], `Scheibe ${s}`);
		assert.equal(new Set(ALLE.map((a) => a.p)).size, 54);
	});
	test('bleibt_liste_existiert_und_ist_nicht_im_umfang', () => {
		const namen = new Set(quelltexte.map((f) => basename(f)));
		for (const n of BLEIBT) {
			assert.ok(namen.has(n), `${n} muss bleiben, fehlt aber`);
			assert.ok(!ALLE.some((a) => basename(a.p) === n), `${n} steht im Umfang`);
		}
	});
});

describe('AC-11: Testgerüst LayoutTabPruefstand gelöscht (S1)', () => {
	test('datei_existiert_nicht_mehr', () => {
		assert.ok(!existsSync(join(KOMP, 'shared/layout-tab/__tests__/LayoutTabPruefstand.svelte')));
	});
});

describe(`AC-3: Scheiben bis S${STAND} sind gelöscht`, () => {
	for (const { s, p, abs } of ALLE) {
		test(`S${s}__${p}`, () => {
			if (s > STAND) assert.ok(existsSync(abs), `${p} ist gelöscht, gehört aber zu Scheibe ${s}: STAND im selben PR erhöhen`);
			else assert.ok(!existsSync(abs), `AC-3: ${p} existiert noch`);
		});
	}
	test('kein_quelltext_importiert_eine_geloeschte_datei', () => {
		const weg = ALLE.filter((a) => a.s <= STAND);
		const treffer = quelltexte.flatMap((f) =>
			importziele(f)
				.filter((z) => weg.some((w) => trifft(z, w.abs)))
				.map((z) => `${relative(REPO, f)} -> ${relative(SRC, z)}`)
		);
		assert.deepEqual(treffer, [], `AC-3: ${treffer.length} Import(e) auf gelöschte Dateien:\n${treffer.join('\n')}`);
	});
	test('importerkennung_findet_lebende_kante', () => {
		// Selbsttest des Scanners an einer Kante, die den Rückbau überlebt.
		const ziel = join(KOMP, 'shared/layout-tab/ltChannels.ts');
		assert.ok(quelltexte.some((f) => importziele(f).some((z) => trifft(z, ziel))));
	});
});

describe('AC-4: Testtabelle deckt jede Testdatei mit totem Baustein ab', () => {
	// Zeilenformat: | `lib/…/x.test.ts` | S3 | umstellen | Begründung | Ersatzbeleg | Mutation |
	const zeilen = () =>
		(existsSync(TABELLE) ? readFileSync(TABELLE, 'utf-8') : '')
			.split('\n')
			.map((z) => z.match(/^\|\s*`([^`]+\.test\.ts)`\s*\|\s*(S[1-4])\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|/))
			.filter((m): m is RegExpMatchArray => m !== null);

	test('tabelle_existiert_und_jede_zeile_hat_entscheid_und_begruendung', () => {
		const z = zeilen();
		assert.ok(z.length >= 100, `AC-4: Testtabelle fehlt oder ist unvollständig (${z.length} Zeilen)`);
		assert.equal(new Set(z.map((m) => m[1])).size, z.length, 'AC-4: Testdatei doppelt');
		for (const [, datei, , entscheid, grund, beleg] of z) {
			assert.match(entscheid, /^(löschen|umstellen|Ersatzbeleg)$/, `${datei}: Entscheid`);
			assert.ok(grund.length >= 20, `${datei}: Begründung fehlt`);
			if (entscheid === 'löschen') assert.match(grund, /^Ohne lebende Aussage: .{20,}/, `${datei}: „löschen“ ohne benannten Grund`);
			else assert.match(beleg, /`[^`]+`/, `${datei}: Ersatzbeleg-Pfad fehlt`);
		}
	});
	test('tabelle_fuehrt_genau_die_rote_liste_der_probe_loeschung', () => {
		assert.equal(new Set(ROTE_LISTE).size, ROTE_LISTE_ANZAHL);
		const inTabelle = zeilen().map((m) => m[1]);
		assert.deepEqual(ROTE_LISTE.filter((f) => !inTabelle.includes(f)), [], 'AC-4: rote Testdatei ohne Zeile');
		assert.deepEqual(inTabelle.filter((f) => !ROTE_LISTE.includes(f)), [], 'AC-4: Zeile ohne rote Testdatei');
	});
	test('jeder_ersatzbeleg_existiert_oder_ist_neu_in_einer_spaeteren_scheibe', () => {
		const fehler = zeilen().flatMap(([, datei, , , , beleg]) =>
			[...beleg.matchAll(/(?:neu in S([2-4]): )?`([^`]+)`/g)]
				.filter(([, neuIn, pfad]) => (neuIn ? Number(neuIn) <= STAND : !existsSync(join(/^(tests|frontend)\//.test(pfad) ? REPO : SRC, pfad))))
				.map(([text]) => `${datei} -> ${text}`)
		);
		assert.deepEqual(fehler, [], `AC-4: Ersatzbeleg fehlt (oder „neu in Sx“ ist nach Sx nicht eingelöst):\n${fehler.join('\n')}`);
	});
	test('jede_testdatei_mit_totem_import_steht_in_der_tabelle', () => {
		const bekannt = new Set(zeilen().map((m) => m[1]));
		const fehlend = quelltexte
			.filter((f) => /\.test\.ts$/.test(f))
			.filter((f) => importziele(f).some((z) => ALLE.some((a) => trifft(z, a.abs))))
			.map((f) => relative(SRC, f))
			.filter((r) => !bekannt.has(r));
		assert.deepEqual(fehlend, [], `AC-4: ${fehlend.length} Testdatei(en) ohne Entscheid:\n${fehlend.join('\n')}`);
	});
});
