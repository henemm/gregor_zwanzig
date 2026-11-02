// Issue #2194 (E-Mail als Login-Kennung) — Nachbesserung Konto-Seite.
// Spec: docs/specs/modules/email_login_identifier.md (Affected Files: account)
//
// Die Konto-Seite zeigt die Konto-Kennung (`u-<8hex>`) weiterhin an — sie ist
// der Ausweg-Login bei doppelten Adressen —, beschriftet sie aber als
// „Konto-Kennung" / „Account ID" statt „Benutzername" / „Username".
//
// Echter SSR-Render der Konto-Seite (Pruefstand f4KontoAdminNavSsr.ts). Jeder
// en-Fall rendert zuerst de und schaltet dann ohne Neuladen auf en.
//
//   cd frontend && npm test -- src/routes/account/__tests__/konto_kennung_beschriftung.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { locale, kontoRendern, kontoDaten, profil } from '../../__tests__/f4KontoAdminNavSsr.ts';

const KENNUNG = 'u-1a2b3c4d';
const ERWARTET = { de: 'Konto-Kennung', en: 'Account ID' } as const;

afterEach(() => locale.set('de'));

/** Der Profil-Eintrag, der die Kennung zeigt: Beschriftung + Wert. */
function kennungsEintrag(html: string): { beschriftung: string; wert: string } {
	const eintraege = [
		...html.matchAll(/<div class="grid gap-1">\s*<span[^>]*>([\s\S]*?)<\/span>\s*<span[^>]*>([\s\S]*?)<\/span>\s*<\/div>/g)
	].map((m) => ({ beschriftung: m[1].trim(), wert: m[2].trim() }));
	const treffer = eintraege.filter((e) => e.wert === KENNUNG);
	assert.equal(treffer.length, 1, `Profil-Eintrag mit der Kennung ${KENNUNG} nicht (genau einmal) gefunden`);
	return treffer[0];
}

function rendern(lang: 'de' | 'en'): string {
	const daten = kontoDaten({ profile: profil({ id: KENNUNG }) });
	locale.set('de');
	const de = kontoRendern(daten);
	if (lang === 'de') return de;
	locale.set('en');
	return kontoRendern(daten);
}

describe('#2194 — Konto-Seite beschriftet die Kennung als Konto-Kennung', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`konto_${lang}_kennung_sichtbar_mit_beschriftung_${ERWARTET[lang]}`, () => {
			const eintrag = kennungsEintrag(rendern(lang));
			assert.equal(eintrag.wert, KENNUNG, `${lang}: Kennung muss sichtbar bleiben`);
			assert.equal(eintrag.beschriftung, ERWARTET[lang], `${lang}: Beschriftung`);
			assert.doesNotMatch(eintrag.beschriftung, /benutzername|username/i, `${lang}: Beschriftung nennt Benutzername`);
		});
	}
});
