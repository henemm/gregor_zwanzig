// Issue #3192 (Workflow fix-3192-wetter-dialog-abgleich): Plural-Wahl im EN-Zuordner des
// Elementlisten-Erzeugers (scripts/elementliste_aus_mockup.ts).
// Der DE-Katalog führt „{count} Metriken“ unter `.one` UND `.other`; das EN-Soll muss sich nach der Zahl im
// Mockup-Text richten („12 Metriken“ ⇒ Mehrzahl), nicht nach dem alphabetisch ersten Schlüssel.
// Ohne Browser, ohne Mocks, gegen den echten i18n-Katalog.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_plural_3192.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as gen from '../../../../scripts/elementliste_aus_mockup.ts';

const REPO = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..', '..');
const katalog = gen.ladeKatalog(join(REPO, 'frontend/src/lib/i18n/messages'));

test('#3192: „12 Metriken“ bekommt die Mehrzahl-Form, nie die Einzahl', () => {
	const r = gen.ermittleEn('12 Metriken', katalog);
	assert.equal(r.luecke, false);
	assert.equal(r.text_en, '{count} metrics');
	assert.ok(!r.i18n_key?.endsWith('.one'), `Einzahl-Schlüssel gewählt: ${r.i18n_key}`);
});

test('#3192: Vorlagen-Unterzeile „N Metriken · Stichworte“ = Mehrzahl + Katalog-Stichworte', () => {
	const r = gen.ermittleEn('12 Metriken · Wind, Regen, gefühlte Temperatur', katalog);
	assert.equal(r.text_en, '{count} metrics · Wind, rain, feels-like temperature');
	assert.equal(r.muster, '{count} Metriken · Wind, Regen, gefühlte Temperatur');
});

test('#3192: pluralPasst wählt `.one` nur für 1, `.other` nur für andere Zahlen', () => {
	assert.equal(gen.pluralPasst('a.b.one', ['count'], ['1']), true);
	assert.equal(gen.pluralPasst('a.b.one', ['count'], ['12']), false);
	assert.equal(gen.pluralPasst('a.b.other', ['count'], ['12']), true);
	assert.equal(gen.pluralPasst('a.b.other', ['count'], ['1']), false);
	// Kein Plural-Schlüssel oder kein Zahlwert: keine Einschränkung.
	assert.equal(gen.pluralPasst('a.b.metrikzahl', ['count'], ['1']), true);
	assert.equal(gen.pluralPasst('a.b.one', ['count'], ['viele']), true);
	assert.equal(gen.pluralPasst('a.b.one', ['name'], ['12']), true);
});
