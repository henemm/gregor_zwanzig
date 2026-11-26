// TDD RED — Issue #3020 Spec 2.0: Rückbau-Wächter für R1 (AC-3 Anzahl, AC-6) und R2 (AC-7).
// doc-compliance-test: Strukturwächter (Testtabelle, Existenz, Importe), KEIN Verhaltensnachweis.
//
// R2 erhöht STAND im selben PR von 1 auf 2. RED der zweiten Scheibe ohne Änderung nachweisen:
// GZ_3020_STAND=2 node … --test <diese Datei>. Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { RESTBESTAND, RESTBESTAND_ANZAHL, BARREL, BLEIBT } from './rework_3020_umfang.ts';
import { GELOESCHT, ENTFALLEN, KATALOG } from './rework_3020_rote_liste.ts';

const STAND = Number(process.env.GZ_3020_STAND ?? 1);

const HERE = dirname(fileURLToPath(import.meta.url));
const LIB = join(HERE, '..');
const SRC = join(LIB, '..');
const REPO = join(SRC, '..', '..');
const KOMP = join(LIB, 'components');
const TABELLE = join(REPO, 'docs/specs/modules/rework_3020_testtabelle.md');

/** Zeilen der Testtabelle in R1 (R2-F3). */
const ZEILEN_R1 = 60 + 145 + 15;
/**
 * Fälle, die bis zur Reparatur von #3355 ausstehen (AC-3); sinkt nur mit dem Bugfix. Von 4 auf 0: 71c27e117 (#3297) hat die
 * Vollkopie im Reiter Wetter behoben, die vier Fälle laufen ohne `todo` grün (Gegenprobe V1: Vollkopie wieder drin, alle vier rot).
 */
const AUSSTEHEND_3355 = 0;
/** `todo`-Fälle einer Testdatei, die auf #3355 verweist. */
const todos3355 = (q: string): string[] => (q.includes('#3355') ? [...q.matchAll(/\btodo:\s*[A-Z_'"`]/g)].map((m) => m[0]) : []);
/** Dürfen vor R2 schon fehlen: auf main gelöscht durch #3301 (02f684e86), #3298 (9bf9c2dbf) und #3366 (PR #3386,
 *  Layout-Reiter samt Hilfsdateien). Nur die Existenzprüfung entfällt, die Menge der 42 bleibt. */
const VORAB_GELOESCHT = [
	'compare/compareHourlyMetricDefs.ts',
	'compare/hourlyFriendlyMap.ts',
	...['LTCapNote.svelte', 'LTChannelPicker.svelte', 'LTCutLine.svelte', 'LayoutTab.svelte', 'channelLayoutsDirty.ts', 'ltIdealRange.ts'].map(
		(n) => `shared/layout-tab/${n}`
	)
];

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
const ALLE = RESTBESTAND.map((p) => ({ p, abs: join(KOMP, p) }));
const trifft = (ziel: string, abs: string) => ziel === abs || `${ziel}.ts` === abs;

// ── Testtabelle: | `ID` | beleg/neu/ausstehend/streichen | Begründung | Beleg | Mutation | ─────────────────────────
// ID = G01..G60, E001..E145 (rework_3020_rote_liste.ts) oder Katalog-ID. Beleg = `pfad ab Wurzel::Testname`.
type Zeile = { id: string; entscheid: string; grund: string; beleg: string; mutation: string };
const tabellentext = () => (existsSync(TABELLE) ? readFileSync(TABELLE, 'utf-8') : '');
const zeilen = (): Zeile[] =>
	tabellentext()
		.split('\n')
		.map((z) => z.match(/^\|\s*`(G\d{2}|E\d{3}|E-[A-Z0-9-]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$/))
		.filter((m): m is RegExpMatchArray => m !== null)
		.map(([, id, e, g, b, m]) => ({ id, entscheid: e.trim(), grund: g.trim(), beleg: b.trim(), mutation: m.trim() }));

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
/** Titelvorlage ohne festen Textanteil (`${key}`) passte ausgefüllt auf jeden Namen; sie zählt nur wörtlich zitiert. */
const ohneFestenText = (vorlage: string) => !/[\p{L}\p{N}]/u.test(vorlage.replace(/\$\{[^}]*\}/g, ''));
function titelImQuelltext(q: string, titel: string): boolean {
	return [...q.matchAll(/\b(?:test|it)(?:\.\w+)?\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`([^`]*)`)/g)].some(([, a, b, c]) =>
		c === undefined
			? (a ?? b).replace(/\\(.)/g, '$1') === titel
			: c === titel || (!ohneFestenText(c) && new RegExp(`^${c.split(/\$\{[^}]*\}/).map(escape).join('.+')}$`).test(titel))
	);
}
/** Steht ein Test mit diesem Namen in der Datei (wörtlich oder als ausgefüllte Template-Vorlage)? */
function hatTest(pfad: string, titel: string): boolean {
	const abs = join(REPO, pfad);
	if (!existsSync(abs) || !/(\.test\.ts|\.spec\.ts|\/test_[^/]+\.py|_test\.go)$/.test(pfad) || !titel) return false;
	const q = lies(abs);
	if (pfad.endsWith('.py')) return new RegExp(`def ${escape(titel)}\\s*\\(`).test(q);
	if (pfad.endsWith('.go')) return new RegExp(`func ${escape(titel)}\\s*\\(`).test(q);
	return titelImQuelltext(q, titel);
}
const belege = (z: Zeile) => [...z.beleg.matchAll(/`([^`]+?)::([^`]+)`/g)].map(([, pfad, titel]) => ({ pfad, titel }));

describe('Umfang (Vakuum-Schutz)', () => {
	test('restbestand_42_ohne_dopplung', () => {
		assert.equal(RESTBESTAND.length, RESTBESTAND_ANZAHL);
		assert.equal(new Set(RESTBESTAND).size, RESTBESTAND_ANZAHL);
	});
	test('rote_liste_60_145_15_ohne_dopplung', () => {
		assert.equal(new Set(GELOESCHT.map(([, f]) => f)).size, 60);
		assert.equal(new Set(ENTFALLEN.map(([, f, t]) => `${f}::${t}`)).size, 145);
		assert.equal(new Set(KATALOG).size, 15);
		assert.equal(new Set([...GELOESCHT.map(([i]) => i), ...ENTFALLEN.map(([i]) => i), ...KATALOG]).size, ZEILEN_R1);
	});
	test('bleibt_liste_existiert_und_ist_nicht_im_umfang', () => {
		const namen = new Set(quelltexte.map((f) => basename(f)));
		for (const n of BLEIBT) {
			assert.ok(namen.has(n), `${n} muss bleiben, fehlt aber`);
			assert.ok(!RESTBESTAND.some((p) => basename(p) === n), `${n} steht im Umfang`);
		}
	});
	test('testnamen_erkennung_unterscheidet_vorhanden_und_erfunden', () => {
		const diese = relative(REPO, fileURLToPath(import.meta.url));
		assert.ok(hatTest(diese, 'restbestand_42_ohne_dopplung'));
		assert.ok(!hatTest(diese, 'diesen_test_gibt_es_nicht'));
		assert.ok(!hatTest('frontend/src/lib', 'restbestand_42_ohne_dopplung'), 'Verzeichnis ist kein Beleg');
	});
	test('testnamen_erkennung_vorlage_ohne_festen_text_ist_kein_treffer', () => {
		const quelle = (vorlage: string) => `for (const key of X) test(\`${vorlage}\`, () => {});`;
		for (const leer of ['${key}', '${a}${b}', '${a} – ${b}: ${c}']) {
			assert.ok(!titelImQuelltext(quelle(leer), 'diesen_test_gibt_es_nicht'), leer);
			assert.ok(!titelImQuelltext(quelle(leer), 'a – b: c'), leer);
			assert.ok(titelImQuelltext(quelle(leer), leer), `${leer}: wörtlich zitierte Vorlage zählt`);
		}
		assert.ok(titelImQuelltext(quelle('kanal ${key} bleibt'), 'kanal sms bleibt'), 'Vorlage mit festem Text zählt');
		assert.ok(titelImQuelltext(quelle('kanal ${key} bleibt'), 'kanal ${key} bleibt'));
		assert.ok(!titelImQuelltext(quelle('kanal ${key} bleibt'), 'kanal sms entfällt'));
	});
});

describe('AC-6 (R1): je gelöschter Testdatei, entfallenem Fall und Katalogfall ein Entscheid', () => {
	const soll = [...GELOESCHT.map(([i]) => i), ...ENTFALLEN.map(([i]) => i), ...KATALOG];

	test('tabelle_fuehrt_genau_die_eingefrorene_liste', () => {
		const ids = zeilen().map((z) => z.id);
		assert.deepEqual(soll.filter((i) => !ids.includes(i)), [], 'AC-6: ohne Entscheid');
		assert.deepEqual(ids.filter((i) => !soll.includes(i)), [], 'AC-6: Zeile ohne Gegenstück');
		assert.equal(ids.length, ZEILEN_R1, 'AC-6: Zeilenzahl (Dopplung?)');
	});
	test('jede_zeile_hat_entscheid_und_begruendung', () => {
		const z = zeilen();
		assert.ok(z.length > 0, 'AC-6: Testtabelle hat keine R1-Zeile');
		const fehler = z.flatMap((r) => {
			if (!/^(beleg|neu|ausstehend|streichen)$/.test(r.entscheid)) return [`${r.id}: Entscheid „${r.entscheid}“`];
			if (r.grund.length < 20) return [`${r.id}: Begründung fehlt`];
			if (r.entscheid === 'streichen' && !/^Ohne lebende Aussage: .{20,}/.test(r.grund)) return [`${r.id}: „streichen“ ohne benannten Grund`];
			if (r.entscheid === 'ausstehend' && !/#\d{4}/.test(r.grund)) return [`${r.id}: „ausstehend“ ohne Issue`];
			if (r.entscheid === 'neu' && !/^[A-Z]+\d+[a-z]? rot/.test(r.mutation)) return [`${r.id}: „neu“ ohne Mutationsprobe`];
			return [];
		});
		assert.deepEqual(fehler, [], `AC-6:\n${fehler.join('\n')}`);
	});
	test('jeder_beleg_ist_testdatei_mit_testname', () => {
		const pflichtig = zeilen().filter((z) => z.entscheid !== 'streichen');
		assert.ok(pflichtig.length > 0, 'AC-6: keine Zeile mit Beleg');
		const fehler = pflichtig.flatMap((z) => {
			const b = belege(z);
			if (!b.length) return [`${z.id}: kein Beleg \`pfad::Testname\``];
			return b.filter(({ pfad, titel }) => !hatTest(pfad, titel)).map(({ pfad, titel }) => `${z.id} -> ${pfad}::${titel}`);
		});
		assert.deepEqual(fehler, [], `AC-6: Beleg nicht auffindbar:\n${fehler.join('\n')}`);
	});
	test('keine_vertagung_auf_abgeschaffte_scheiben', () => {
		assert.doesNotMatch(tabellentext(), /neu in S[1-4]|offen \(S[1-4]\)/, 'AC-6: Vermerk aus dem Schema S1 bis S4 ist nicht eingelöst');
	});
});

describe('AC-3 (R1): ausstehende Fälle zu #3355 sind sichtbar und gezählt', () => {
	// Bei Sollzahl 0 wäre eine blinde Zählung grün: die Erkennung und die Dateimenge werden deshalb eigens geprüft.
	test('zaehlung_findet_jeden_todo_mit_verweis', () => {
		const fall = (wert: string) => `test('x', { todo: ${wert} }, async () => {});`;
		assert.equal(todos3355(`// Bug #3355\n${fall('BEFUND')}\n${fall("'Bug offen'")}`).length, 2);
		assert.deepEqual(todos3355(fall('BEFUND')), [], 'ohne Verweis zählt der Fall nicht');
		const verweise = quelltexte.filter((f) => /\.test\.ts$/.test(f) && readFileSync(f, 'utf-8').includes('#3355')).map((f) => basename(f));
		for (const n of ['trip_python_skip_next_ohne_412.test.ts', 'trip_reiter_nutzlast_nur_eigene_felder.test.ts'])
			assert.ok(verweise.includes(n), `${n}: Regressionsverweis #3355 fehlt`);
	});
	test('anzahl_im_code_und_in_der_tabelle', () => {
		const treffer = quelltexte
			.filter((f) => /\.test\.ts$/.test(f))
			.flatMap((f) => todos3355(readFileSync(f, 'utf-8')).map(() => relative(REPO, f)));
		assert.equal(treffer.length, AUSSTEHEND_3355, `AC-3: ausstehende Fälle mit Verweis auf #3355: ${JSON.stringify(treffer)}`);
		assert.match(tabellentext(), new RegExp(`Ausstehend zu #3355: ${AUSSTEHEND_3355}\\b`), 'AC-3: Anzahl fehlt in der Testtabelle');
	});
});

describe(`AC-7 (R2): Restbestand, STAND ${STAND}`, () => {
	for (const { p, abs } of ALLE) {
		test(`restbestand__${p}`, () => {
			if (STAND < 2 && VORAB_GELOESCHT.includes(p)) return;
			if (STAND < 2) assert.ok(existsSync(abs), `${p} ist gelöscht: STAND im selben PR auf 2 erhöhen`);
			else assert.ok(!existsSync(abs), `AC-7: ${p} existiert noch`);
		});
	}
	test('vorab_geloescht_nur_wirklich_geloeschte_scope_dateien', () => {
		for (const p of VORAB_GELOESCHT) {
			assert.ok(RESTBESTAND.includes(p), `${p} steht nicht im Umfang`);
			assert.ok(!existsSync(join(KOMP, p)), `${p} existiert noch: Ausnahme aus VORAB_GELOESCHT streichen`);
		}
	});
	test('kein_quelltext_importiert_eine_geloeschte_datei', () => {
		if (STAND < 2) return;
		const treffer = quelltexte.flatMap((f) =>
			importziele(f)
				.filter((z) => ALLE.some((w) => trifft(z, w.abs)))
				.map((z) => `${relative(REPO, f)} -> ${relative(SRC, z)}`)
		);
		assert.deepEqual(treffer, [], `AC-7: ${treffer.length} Import(e) auf gelöschte Dateien:\n${treffer.join('\n')}`);
	});
	test('barrel_zeilen', () => {
		for (const [barrel, name] of BARREL) {
			const steht = new RegExp(`\\b${name}\\b`).test(lies(join(KOMP, barrel)));
			assert.equal(steht, STAND < 2, `AC-7: ${barrel} / ${name}`);
		}
	});
	test('importerkennung_findet_lebende_kante', () => {
		const ziel = join(KOMP, 'shared/layout-tab/ltChannels.ts');
		assert.ok(quelltexte.some((f) => importziele(f).some((z) => trifft(z, ziel))));
	});
});
