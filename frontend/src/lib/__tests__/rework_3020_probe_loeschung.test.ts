// TDD RED — Issue #3020 S1, AC-11: Tests zu lebendem Verhalten hängen nicht mehr an toten
// Bausteinen. Je Nutzer läuft die ECHTE Testdatei in einem eigenen Prozess, für den die
// 54 Dateien des Umfangs nicht existieren. Fällt mit S4 weg (dann sind sie gelöscht).
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { SCHEIBEN, LEBENDE_HELFER_NUTZER } from './rework_3020_umfang.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(HERE, '../..');
const FRONTEND = join(SRC, '..');
const KOMP = join(SRC, 'lib/components');
const TOT = Object.values(SCHEIBEN)
	.flat()
	.map((p) => join(KOMP, p));

function probe(args: string[]): Promise<{ code: number | null; aus: string }> {
	const env: NodeJS.ProcessEnv = { ...process.env, GZ_3020_TOT: JSON.stringify(TOT) };
	delete env.NODE_TEST_CONTEXT; // sonst meldet der innere Lauf an den äußeren statt per Exit-Code
	return new Promise((fertig) => {
		const p = spawn(
			process.execPath,
			[
				'--import',
				pathToFileURL(join(HERE, 'rework_3020_probe_hooks.mjs')).href,
				'--import',
				'./test-lib-loader.mjs',
				'--experimental-strip-types',
				'--experimental-test-module-mocks',
				...args
			],
			{ cwd: FRONTEND, env }
		);
		let aus = '';
		p.stdout.on('data', (d) => (aus += d));
		p.stderr.on('data', (d) => (aus += d));
		p.on('close', (code) => fertig({ code, aus }));
	});
}

const skript = (code: string) => probe(['--input-type=module', '-e', code]);

describe('Selbsttest: die Probe verbirgt genau die toten Dateien', () => {
	const tot = join(KOMP, 'shared/versand-tab/vtBriefingChannelsText.ts');
	const lebend = join(KOMP, 'shared/layout-tab/ltChannels.ts');
	const url = (p: string) => JSON.stringify(pathToFileURL(p).href);

	test('tote_datei_unsichtbar__import', async () => {
		const r = await skript(`await import(${url(tot)})`);
		assert.notEqual(r.code, 0);
		assert.match(r.aus, /PROBE-LOESCHUNG #3020/);
	});
	test('tote_datei_unsichtbar__readFileSync', async () => {
		const r = await skript(`(await import('node:fs')).readFileSync(new URL(${url(tot)}))`);
		assert.notEqual(r.code, 0);
		assert.match(r.aus, /PROBE-LOESCHUNG #3020/);
	});
	test('lebende_datei_sichtbar__import_und_readFileSync', async () => {
		const r = await skript(`await import(${url(lebend)}); (await import('node:fs')).readFileSync(new URL(${url(lebend)}))`);
		assert.equal(r.code, 0, r.aus.slice(-600));
	});
});

describe('AC-11: lebende Helfer-Nutzer sind in der Probe-Löschung grün', { concurrency: 4 }, () => {
	for (const rel of LEBENDE_HELFER_NUTZER) {
		test(`gruen_ohne_tote_bausteine__${rel.split('/').pop()}`, async () => {
			const datei = join(SRC, rel);
			assert.ok(existsSync(datei), `${rel} fehlt (umbenannt? Liste nachziehen, nicht kürzen)`);
			// Ohne `--test`: kein Glob, die Klammern in `[id]` stören nicht; node:test setzt den Exit-Code.
			const r = await probe([datei]);
			const ursache = r.aus.match(/PROBE-LOESCHUNG #3020: \S+/)?.[0] ?? r.aus.slice(-800);
			assert.equal(r.code, 0, `AC-11: ${rel} hängt noch an einem toten Baustein.\n${ursache}`);
			assert.match(r.aus, /(#|ℹ) pass [1-9]/, `${rel}: kein Test gelaufen`);
		});
	}
});
