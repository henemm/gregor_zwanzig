// ESM-Hook (#2660): ConfirmDialog.svelte bindet statt des bits-ui-Dialogs den
// durchreichenden Test-Rahmen `dialogRahmen.ts` ein. Nur die Import-Zeile wird
// ersetzt; der Rest der Komponente bleibt echt. Findet der Hook die Zeile nicht
// genau einmal, bricht er ab (kein vakuum-gruener Test).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compile } from 'svelte/compiler';

const MUSTER = "import * as Dialog from '$lib/components/ui/dialog/index.js';";
const RAHMEN = new URL('./dialogRahmen.ts', import.meta.url).href;

export async function load(url, context, nextLoad) {
	if (url.startsWith('file:') && url.endsWith('/lib/components/molecules/ConfirmDialog.svelte')) {
		const file = fileURLToPath(url);
		const quelle = readFileSync(file, 'utf-8');
		if (quelle.split(MUSTER).length !== 2) {
			throw new Error(`dialogRahmenHook: Muster "${MUSTER}" nicht genau einmal in ${file}`);
		}
		const { js } = compile(quelle.replace(MUSTER, `import * as Dialog from '${RAHMEN}';`), {
			generate: 'server',
			filename: file
		});
		return { format: 'module', shortCircuit: true, source: js.code };
	}
	return nextLoad(url, context);
}
