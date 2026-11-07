// TDD RED — Issue #1839 AC-6: Ladehinweis "Vorschau wird berechnet…" der
// Alarm-Vorschau (geteilt Trip/Vergleich, EINE Komponente AlertPreviewCard).
// Spec: docs/specs/modules/fix_1839_trip_vorschau_kalt.md
//
// Grenze (ehrlich): Der Lade-Zustand entsteht erst nach dem Klick auf
// „Vorschau laden" im Browser (Abruf laeuft) und ist serverseitig nicht
// renderbar. Dieser Test bewacht deshalb, was im Node-Kontext echt pruefbar
// ist: der Katalogtext existiert in BEIDEN Sprachen (nicht leer, nicht gleich
// dem Schluessel) und ist vom Knopftext "Lade…" verschieden. Das Erscheinen
// des Statuselements im Lade-Zustand und sein Verschwinden nach Abschluss
// prueft die Live-Spec gegen Staging (/e2e-verify).
//
// RED HEUTE: der Schluessel `alarme.vorschau.berechnet` fehlt in de + en.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/alerts-tab/__tests__/alertPreviewBerechnetHinweis.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Pfadregel #1409: relativ zu DIESER Datei.
const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> alerts-tab -> components -> lib
const MESSAGES = path.resolve(HERE, '../../../i18n/messages');
const KEY = 'alarme.vorschau.berechnet';

function katalog(sprache: 'de' | 'en'): Record<string, string> {
	return JSON.parse(readFileSync(path.join(MESSAGES, sprache, 'alarme.json'), 'utf-8'));
}

for (const sprache of ['de', 'en'] as const) {
	test(`AC-6: Katalogtext ${KEY} existiert (${sprache}) und unterscheidet sich vom Knopftext`, () => {
		const k = katalog(sprache);
		const text = k[KEY];
		assert.equal(typeof text, 'string', `${KEY} fehlt in ${sprache}/alarme.json`);
		assert.ok(text.trim().length > 0, `${KEY} ist leer (${sprache})`);
		assert.notEqual(text, KEY, 'Schluessel darf nicht als Text stehen');
		assert.notEqual(text, k['alarme.vorschau.lade'], 'Hinweis muss mehr sagen als der Knopftext "Lade…"');
	});
}

test('AC-6: DE nennt "berechnet", EN nennt "preview" (gleichwertige Aussage)', () => {
	assert.match(katalog('de')[KEY] ?? '', /berechnet/i);
	assert.match(katalog('en')[KEY] ?? '', /preview/i);
});
