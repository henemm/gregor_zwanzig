// TDD RED — Issue #3059: E-Mail-Format Ausführlich/Kompakt für Orte (Spec docs/specs/modules/feat_3059_orte_kompakt_mail.md).
//
//   AC-3: Orte speichern `display_config.email_format` per Teilfeld (Read-Modify-Write); `telegram_style`
//         liegt im selben `display_config`-Objekt und wird nicht überschrieben.
//   AC-13: Texte des Format-Schalters ohne Trip-spezifische Wörter, DE und EN (Datenprüfung am Katalog).
//
// Reine Logik: shared/wetter-tab/wasStehtWoSpeicherung.ts (kein Netz, kein Mock).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/orte_email_format_3059.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { felderNutzlast, felderAusAntwort, type Felder } from '../wasStehtWoSpeicherung.ts';

const basis: Felder = {
	show_stage_stats: true,
	show_yesterday_comparison: true,
	show_night_block: true,
	email_format: 'full',
	telegram_style: 'rich',
	hourly_enabled: true
};

describe('#3059 Orte: email_format in display_config (AC-3)', () => {
	test('full -> compact: nur display_config.email_format, sonst nichts', () => {
		assert.deepEqual(felderNutzlast('vergleich', { ...basis, email_format: 'compact' }, basis), {
			display_config: { email_format: 'compact' }
		});
	});
	test('compact -> full wird ebenfalls geschrieben', () => {
		const alt: Felder = { ...basis, email_format: 'compact' };
		assert.deepEqual(felderNutzlast('vergleich', basis, alt), { display_config: { email_format: 'full' } });
	});
	test('email_format und telegram_style zugleich: beide im SELBEN display_config, keiner überschreibt den anderen', () => {
		const rumpf = felderNutzlast('vergleich', { ...basis, email_format: 'compact', telegram_style: 'kurzform' }, basis);
		assert.deepEqual(rumpf, { display_config: { email_format: 'compact', telegram_style: 'kurzform' } });
	});
	test('email_format zusammen mit hourly_enabled: hourly_enabled oben, email_format in display_config', () => {
		assert.deepEqual(felderNutzlast('vergleich', { ...basis, email_format: 'compact', hourly_enabled: false }, basis), {
			hourly_enabled: false,
			display_config: { email_format: 'compact' }
		});
	});
	test('unverändertes email_format: kein email_format-Schlüssel (Teilfeld, kein Replace)', () => {
		const kompakt: Felder = { ...basis, email_format: 'compact' };
		assert.deepEqual(felderNutzlast('vergleich', { ...kompakt, telegram_style: 'kurzform' }, kompakt), { display_config: { telegram_style: 'kurzform' } });
		assert.deepEqual(felderNutzlast('vergleich', kompakt, kompakt), {});
	});
	test('Orte schreiben email_format nie nach report_config (Trip-Ort des Felds)', () => {
		const rumpf = felderNutzlast('vergleich', { ...basis, email_format: 'compact' }, basis) as Record<string, unknown>;
		assert.equal('report_config' in rumpf, false);
		assert.equal((rumpf.display_config as Record<string, unknown> | undefined)?.email_format, 'compact');
	});
});

describe('#3059 Regression Trip: email_format bleibt in report_config', () => {
	test('Trip full -> compact unverändert report_config.email_format', () => {
		assert.deepEqual(felderNutzlast('route', { ...basis, email_format: 'compact' }, basis), { report_config: { email_format: 'compact' } });
	});
});

describe('#3059 Orte: Startwert aus blocks', () => {
	test('blocks.email_format "compact" der Orte-Antwort ergibt compact; fehlend ergibt full', () => {
		assert.equal(felderAusAntwort({ blocks: { hourly: true, telegram_style: 'rich', email_format: 'compact' } } as never).email_format, 'compact');
		assert.equal(felderAusAntwort({ blocks: { hourly: true, telegram_style: 'rich' } } as never).email_format, 'full');
	});
});

describe('#3059 Katalog: Format-Texte neutral für Trip und Orte, DE und EN (AC-13)', () => {
	// Datenprüfung am Übersetzungskatalog (keine Quelltext-Prüfung): die Texte erscheinen künftig auch bei Orten.
	const HERE = path.dirname(fileURLToPath(import.meta.url));
	const katalog = (sprache: string) => JSON.parse(readFileSync(path.resolve(HERE, '../../../../i18n/messages', sprache, 'wetter.json'), 'utf8'));
	const wert = (o: Record<string, unknown>, schluessel: string): unknown =>
		schluessel.split('.').reduce<unknown>((acc, k) => (acc && typeof acc === 'object' ? (acc as Record<string, unknown>)[k] : undefined), o);
	const SCHLUESSEL = ['wsw.kanal.email_format', 'wsw.kanal.email_format_hinweis', 'wsw.kanal.ausfuehrlich', 'wsw.kanal.kompakt'];
	const VERBOTEN = /\b(Trips?|Etappen?|Routen?|stages?|trips?|routes?)\b/i;
	for (const sprache of ['de', 'en']) {
		test(`${sprache}: alle Format-Texte vorhanden und ohne Trip-Wörter`, () => {
			const k = katalog(sprache) as Record<string, unknown>;
			for (const s of SCHLUESSEL) {
				// Katalog ist flach („wetter.wsw.kanal.…“); verschachtelt als Rückfall.
				const v = k[`wetter.${s}`] ?? wert(k, `wetter.${s}`);
				assert.equal(typeof v, 'string', `${sprache}: wetter.${s} fehlt`);
				assert.ok((v as string).trim().length > 0, `${sprache}: wetter.${s} leer`);
				assert.doesNotMatch(v as string, VERBOTEN, `${sprache}: wetter.${s} enthält Trip-Wort`);
			}
		});
	}
});
