// Issue #2653 (i18n F4, Epic #2644) — AC-5: Navigation (Sidebar, untere Leiste,
// Konto-Blatt) und Speicher-Anzeige in der Nutzersprache.
//   * Navigation: das ECHTE +layout.svelte rendert Sidebar, BottomNav und das
//     (per Hook geoeffnete) Konto-Blatt und setzt `locale` selbst aus data.lang —
//     geprueft wird also dort, wo die Sprache wirkt. Erst de, dann ohne Neuladen en.
//   * Speicher-Anzeige: SaveIndicator mit einer ECHTEN SaveStatus-Instanz
//     (saveStatusStore.svelte.ts) je Zustand; die Uhrzeit bleibt in `.save-time`.
// Englische Anker sind feste Literale (exakter Elementinhalt, nicht Teilstring).
// Spec: docs/specs/modules/i18n_f4_konto_admin_nav_2653.md
//
//   cd frontend && npm test -- src/lib/components/ui/__tests__/navigation_und_speicheranzeige_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { get } from 'svelte/store';
import { locale, navRendern, layoutDaten } from '../../../../routes/__tests__/f4KontoAdminNavSsr.ts';
import { FRONTEND, render, ohneKommentare, teilbaum } from '../../../../routes/__tests__/onboardingSsr.ts';
import { deutscheReste, sichtbarerText, attributText } from '../../../../routes/__tests__/f3Sprachpruefung.ts';

const SaveIndicator = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/ui/SaveIndicator.svelte')).href)).default;
const { createSaveStatus } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/stores/saveStatusStore.svelte.ts')).href);

afterEach(() => locale.set('de'));

/** Sichtbarer Text der direkten Kind-Elemente eines Teilbaums, in Reihenfolge. */
const texte = (html: string, re: RegExp) => [...html.matchAll(re)].map((m) => m[1].replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim());

describe('AC-5: Navigation ueber das echte Layout (data.lang)', () => {
	const en = () => {
		navRendern(layoutDaten('de'));
		return navRendern(layoutDaten('en'));
	};

	test('Layout setzt die Sprache aus data.lang', () => {
		en();
		assert.equal(get(locale), 'en');
		navRendern(layoutDaten('de'));
		assert.equal(get(locale), 'de');
	});

	test('Sidebar: Hauptmenue englisch, exakte Labels', () => {
		const sb = teilbaum(en(), 'desktop-sidebar')!;
		assert.deepEqual(texte(sb, /<span style="flex: 1;">([^<]*)<\/span>/g), ['Home', 'My trips', 'Location comparison', 'Archive', 'Help', 'Admin']);
	});

	test('untere Leiste: Labels exakt, Konto-Kreis aria-label „Account"', () => {
		const h = en();
		const leiste = teilbaum(h, 'bottom-nav')!;
		assert.deepEqual(texte(leiste, /<span class="bottom-nav__label[^"]*">([^<]*)<\/span>/g), ['Overview', 'Trips', 'Comparison', 'Archive']);
		assert.match(teilbaum(h, 'konto-kreis')!, /aria-label="Account"/);
	});

	test('Konto-Blatt: Menuepunkte, Schalter, Schliessen, Abmelden englisch', () => {
		const blatt = teilbaum(en(), 'konto-sheet')!;
		assert.match(blatt, /^<div data-testid="konto-sheet" role="dialog" aria-label="Account"/);
		assert.deepEqual(texte(blatt, /<span class="konto__label[^"]*">([^<]*)<\/span>/g), [
			'Channels & recipients',
			'Settings',
			'System status',
			'Help',
			'Dark theme',
			'Admin',
			'Data export'
		].map((s) => s.replace('&', '&amp;')));
		assert.match(blatt, /aria-label="Close"/);
		assert.match(teilbaum(blatt, 'konto-sheet-dark')!, /aria-label="Dark theme"/);
		assert.equal(sichtbarerText(teilbaum(blatt, 'konto-sheet-logout')!), 'Sign out');
		assert.ok(sichtbarerText(blatt).includes('V0.20 · Weather briefing'));
	});

	test('Sidebar-Benutzermenue (geoeffnet): Konto, System-Status, Hell/Dunkel, Abmelden', () => {
		const g = globalThis as Record<string, unknown>;
		g.__gzSidebarMenueOffen = true;
		try {
			const menue = (dunkel: boolean) => {
				const sb = teilbaum(navRendern(layoutDaten('de')), 'desktop-sidebar')!;
				assert.ok(sichtbarerText(sb).includes('Konto System-Status Dark Mode Abmelden'), 'Messaufbau: Menue zu');
				locale.set('en');
				return sichtbarerText(teilbaum(navRendern(layoutDaten('en', { darkMode: dunkel })), 'desktop-sidebar')!);
			};
			const t = menue(false);
			assert.ok(t.includes('Golden Account System status Dark mode Sign out'), t);
			assert.ok(!/Konto|Abmelden|Mode\b/.test(t), t);
		} finally {
			g.__gzSidebarMenueOffen = false;
		}
	});

	test('kein deutscher nav.*-Text im englischen Layout (Text und Attribute)', () => {
		const h = en();
		assert.deepEqual(deutscheReste(sichtbarerText(h), ['nav.']), []);
		assert.deepEqual(deutscheReste(attributText(h), ['nav.']), []);
	});

	test('Deutsch bleibt: Startseite, Übersicht, Kanäle & Empfänger, aria-label „Konto"', () => {
		en();
		const h = navRendern(layoutDaten('de'));
		assert.deepEqual(texte(teilbaum(h, 'desktop-sidebar')!, /<span style="flex: 1;">([^<]*)<\/span>/g), ['Startseite', 'Meine Trips', 'Orts-Vergleich', 'Archiv', 'Hilfe', 'Admin']);
		assert.deepEqual(texte(teilbaum(h, 'bottom-nav')!, /<span class="bottom-nav__label[^"]*">([^<]*)<\/span>/g), ['Übersicht', 'Trips', 'Vergleich', 'Archiv']);
		assert.match(teilbaum(h, 'konto-kreis')!, /aria-label="Konto"/);
	});
});

type Zustand = { state: string; savedAt?: Date | null; error?: string | null };
function anzeige(z: Zustand): string {
	const c = createSaveStatus();
	c.state = z.state;
	c.savedAt = z.savedAt ?? null;
	c.error = z.error ?? null;
	return ohneKommentare(render(SaveIndicator, { props: { controller: c } }).body);
}
/** de rendern, dann ohne Neuladen auf en. */
function enNachDe(z: Zustand): string {
	locale.set('de');
	anzeige(z);
	locale.set('en');
	return anzeige(z);
}
/** Inhalt des Text-<span> ohne Klasse (der Zustandstext). */
const zustandsText = (html: string) => /<span>([^<]*)<\/span>/.exec(html)?.[1];

describe('AC-5: Speicher-Anzeige je Zustand', () => {
	const UM = new Date(2026, 9, 29, 14, 30);

	test('gespeichert: „Saved", Uhrzeit weiter im eigenen .save-time', () => {
		const h = enNachDe({ state: 'idle', savedAt: UM });
		assert.equal(zustandsText(h), 'Saved');
		assert.match(h, /<span>Saved<\/span> <span class="save-time[^"]*">14:30<\/span>/);
		locale.set('de');
		assert.match(anzeige({ state: 'idle', savedAt: UM }), /<span>Gespeichert<\/span> <span class="save-time[^"]*">14:30<\/span>/);
	});

	test('ungespeichert / speichernd: „Not saved", „Saving …"', () => {
		assert.equal(zustandsText(enNachDe({ state: 'dirty' })), 'Not saved');
		assert.equal(zustandsText(enNachDe({ state: 'saving' })), 'Saving …');
		locale.set('de');
		assert.equal(zustandsText(anzeige({ state: 'saving' })), 'Speichere …');
	});

	test('Konflikt: Ersatztext und Knopf „Save again"; Server-Text bleibt unveraendert', () => {
		const h = enNachDe({ state: 'conflict' });
		assert.equal(zustandsText(h), 'Conflict while saving');
		assert.equal(/<button[^>]*>([^<]*)<\/button>/.exec(h)?.[1].trim(), 'Save again');
		assert.equal(zustandsText(enNachDe({ state: 'conflict', error: 'Etag passt nicht' })), 'Etag passt nicht');
	});

	test('Fehler: „Error while saving" und mit Meldung „Error while saving: …"', () => {
		assert.equal(zustandsText(enNachDe({ state: 'error' })), 'Error while saving');
		assert.equal(zustandsText(enNachDe({ state: 'error', error: 'HTTP 500' })), 'Error while saving: HTTP 500');
		locale.set('de');
		assert.equal(zustandsText(anzeige({ state: 'error', error: 'HTTP 500' })), 'Fehler beim Speichern: HTTP 500');
	});
});
