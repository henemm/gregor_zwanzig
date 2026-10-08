// doc-compliance-test
// Wächter #2288 / ADR-0024 (AC-2): im Frontend gibt es EINE Drag-Technik.
// Natives HTML5-`draggable=` kommt ausschliesslich unter `shared/dnd/` vor
// (dort nur als Kommentar/Doku). Keine Ausnahmeliste.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// dnd -> shared -> components -> lib -> src
const SRC = path.resolve(HERE, '../../../..');
const DND_DIR = HERE;

function walk(dir: string, out: string[] = []): string[] {
	for (const name of readdirSync(dir)) {
		if (name === 'node_modules' || name === '.svelte-kit') continue;
		const p = path.join(dir, name);
		if (statSync(p).isDirectory()) walk(p, out);
		else if (/\.(svelte|ts|js)$/.test(name)) out.push(p);
	}
	return out;
}

describe('#2288 AC-2: kein natives draggable ausserhalb shared/dnd', () => {
	test('`draggable=` kommt in keiner Quelldatei ausserhalb shared/dnd/ vor', () => {
		const treffer = walk(SRC)
			.filter((f) => !f.startsWith(DND_DIR + path.sep))
			.filter((f) => !/\.test\.ts$/.test(f))
			.filter((f) => /draggable\s*=/.test(readFileSync(f, 'utf8')))
			.map((f) => path.relative(SRC, f));
		assert.deepEqual(
			treffer,
			[],
			`natives draggable= gefunden (ADR-0024: nur SortableList/svelte-dnd-action): ${treffer.join(', ')}`
		);
	});

	test('EtappenStrip.svelte nutzt den geteilten Baustein statt nativem Drag', () => {
		const f = path.join(SRC, 'lib/components/trip-detail/waypoints/EtappenStrip.svelte');
		const code = readFileSync(f, 'utf8');
		assert.ok(!/draggable\s*=/.test(code), 'EtappenStrip enthält noch draggable=');
		assert.ok(!/ondragstart|ondragover|ondragend/.test(code), 'EtappenStrip enthält noch ondrag*');
		assert.ok(/SortableList/.test(code), 'EtappenStrip importiert SortableList nicht');
	});

	test('verwaiste GroupSection.svelte ist gelöscht und nirgends mehr referenziert', () => {
		const f = path.join(SRC, 'lib/components/compare/GroupSection.svelte');
		assert.ok(!existsSync(f), 'compare/GroupSection.svelte existiert noch (PO-Entscheid E-1: löschen)');
		const self = fileURLToPath(import.meta.url);
		const refs = walk(SRC)
			.filter((p) => p !== self)
			.filter((p) => /GroupSection/.test(readFileSync(p, 'utf8')))
			.map((p) => path.relative(SRC, p));
		assert.deepEqual(refs, [], `Verweise auf GroupSection: ${refs.join(', ')}`);
	});
});
