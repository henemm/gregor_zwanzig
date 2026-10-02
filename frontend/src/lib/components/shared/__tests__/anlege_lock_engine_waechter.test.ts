// TDD RED — #2277 S4, AC-8/AC-9: Die Compare-Kopie der Lock-Engine ist weg, beide Anlege-Seiten
// nutzen den geteilten Kern. Auflösung relativ zur eigenen Testdatei (kein Hauptrepo-Pfad).
// doc-compliance-test (Quellbaum-Wächter: Zusicherung ist „diese Datei/dieser Import existiert nicht")

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const COMPONENTS = path.resolve(HERE, '../..'); // shared/__tests__ -> shared -> components
const FRONTEND = path.resolve(COMPONENTS, '../../..'); // components -> lib -> src -> frontend

function walk(dir: string, out: string[] = []): string[] {
	if (!fs.existsSync(dir)) return out;
	for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
		if (e.name === 'node_modules' || e.name === '.svelte-kit') continue;
		const f = path.join(dir, e.name);
		if (e.isDirectory()) walk(f, out);
		else if (/\.(ts|svelte|mjs|js)$/.test(e.name)) out.push(f);
	}
	return out;
}

test('AC-8: compare-new/compareNewLogic.ts existiert nicht mehr', () => {
	assert.ok(!fs.existsSync(path.join(COMPONENTS, 'compare-new/compareNewLogic.ts')));
});

test('AC-8: der Kern shared/anlegeLockEngine.ts existiert', () => {
	assert.ok(fs.existsSync(path.join(COMPONENTS, 'shared/anlegeLockEngine.ts')));
});

test('AC-8: kein Quell-/Testcode in src/ und e2e/ importiert compareNewLogic', () => {
	const self = fileURLToPath(import.meta.url);
	const files = [...walk(path.join(FRONTEND, 'src')), ...walk(path.join(FRONTEND, 'e2e'))].filter((f) => f !== self);
	const importRe = /(?:from|import)\s*\(?\s*['"][^'"]*compareNewLogic[^'"]*['"]/;
	const offenders = files.filter((f) => importRe.test(fs.readFileSync(f, 'utf8')));
	assert.deepEqual(offenders.map((f) => path.relative(FRONTEND, f)), []);
});

test('AC-8: CompareNewEditor und tripNewLogic importieren den Kern', () => {
	const importsKern = (rel: string) =>
		/from\s+['"][^'"]*anlegeLockEngine(\.ts)?['"]/.test(fs.readFileSync(path.join(COMPONENTS, rel), 'utf8'));
	assert.ok(importsKern('compare-new/CompareNewEditor.svelte'), 'CompareNewEditor importiert den Kern nicht');
	assert.ok(importsKern('trip-new/tripNewLogic.ts'), 'tripNewLogic importiert den Kern nicht');
});

test('AC-9: keine neue Logikdatei in compare-new/ (Pendant-Sperre)', () => {
	const files = fs.readdirSync(path.join(COMPONENTS, 'compare-new')).filter((n) => n.endsWith('.ts'));
	assert.deepEqual(files.sort(), ['compareNewVorlage.ts']);
});
