// TDD RED — Onboarding S3 (Issue #2521), Teil B: Hilfeseite /hilfe und Hilfelinks.
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md — AC-15, AC-16
// (Render), AC-18, AC-19, AC-21 (Render/Katalogtreue).
//
// Gemessen wird ECHT: die Seite routes/hilfe/+page.svelte, StartklarCheckliste,
// Sidebar, KontoSheet und BottomNav serverseitig gerendert (svelte/server,
// Pruefstand onboardingSsr.ts). Erwartete Texte kommen aus de.json — so beweist
// der Render zugleich, dass die Seite ueber t(key) aus dem Katalog liest.
//
// Vertraege (Test-Kennungen), die dieser Test festlegt:
//   Abschnitte  data-testid="hilfe-briefing" | "hilfe-alarme" | "hilfe-kanaele" | "hilfe-befehle"
//   Checkliste  Link href="/hilfe", Text = onboarding.checkliste.hilfe
//   Sidebar     data-testid="nav-hilfe", href="/hilfe", Text = nav.hilfe
//   KontoSheet  data-testid="konto-sheet-hilfe", href="/hilfe", Text = nav.hilfe
//   BottomNav   unveraendert (bewusst gruen, Gegenprobe AC-19)
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/__tests__/hilfe_seite_inhalt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import {
	ROUTES,
	FRONTEND,
	CHECKLISTE_DATEI,
	KATALOG,
	render,
	ladeKomponente,
	teilbaum,
	links,
	sichtbar,
	text,
	profilNeu,
	ohneKommentare
} from './onboardingSsr.ts';

const HILFE_DATEI = path.join(ROUTES, 'hilfe', '+page.svelte');
const ABSCHNITTE = ['hilfe-briefing', 'hilfe-alarme', 'hilfe-kanaele', 'hilfe-befehle'];

async function hilfeHtml(): Promise<string> {
	const Seite = await ladeKomponente(HILFE_DATEI);
	assert.ok(Seite, 'frontend/src/routes/hilfe/+page.svelte existiert nicht');
	return ohneKommentare(render(Seite, { props: { data: {} } }).body);
}

function abschnitt(html: string, id: string): string {
	const t = teilbaum(html, id);
	assert.ok(t, `Abschnitt data-testid="${id}" fehlt`);
	return t!;
}

describe('AC-15: /hilfe zeigt Briefing-Zeiten, Alarme, Kanaele und zuletzt die Antwort-Befehle', () => {
	test('vier Abschnitte in genau dieser Reihenfolge, Antwort-Befehle zuletzt', async () => {
		const html = await hilfeHtml();
		const pos = ABSCHNITTE.map((id) => html.indexOf(`data-testid="${id}"`));
		for (const [i, id] of ABSCHNITTE.entries()) assert.ok(pos[i] >= 0, `Abschnitt ${id} fehlt`);
		assert.deepEqual([...pos].sort((a, b) => a - b), pos, `Reihenfolge falsch: ${JSON.stringify(pos)}`);
	});
	test('Titel der Seite und der Abschnitte stammen aus dem Katalog', async () => {
		const html = await hilfeHtml();
		assert.ok(sichtbar(html).includes(text('hilfe.titel')));
		for (const [id, key] of [
			['hilfe-briefing', 'hilfe.briefing.titel'],
			['hilfe-alarme', 'hilfe.alarme.titel'],
			['hilfe-kanaele', 'hilfe.kanaele.titel'],
			['hilfe-befehle', 'hilfe.befehle.titel']
		]) {
			assert.ok(sichtbar(abschnitt(html, id)).includes(text(key)), `${id}: Titel ${key} fehlt`);
		}
	});
	test('Briefing-Zeiten: morgens und abends', async () => {
		const b = sichtbar(abschnitt(await hilfeHtml(), 'hilfe-briefing'));
		assert.ok(b.includes(text('hilfe.briefing.morgens')));
		assert.ok(b.includes(text('hilfe.briefing.abends')));
	});
	test('Alarme: Erklaertext aus dem Katalog', async () => {
		assert.ok(sichtbar(abschnitt(await hilfeHtml(), 'hilfe-alarme')).includes(text('hilfe.alarme.text')));
	});
	test('Antwort-Befehle: jeder Katalog-Befehl erscheint mit Beschreibung', async () => {
		const b = sichtbar(abschnitt(await hilfeHtml(), 'hilfe-befehle'));
		const befehle = Object.keys(KATALOG).filter((k) => /^hilfe\.befehle\.[^.]+\.befehl$/.test(k));
		assert.ok(befehle.length > 0, 'keine Befehlseintraege im Katalog');
		for (const k of befehle) {
			assert.ok(b.includes(KATALOG[k]), `Befehl ${KATALOG[k]} fehlt`);
			assert.ok(b.includes(KATALOG[k.replace(/\.befehl$/, '.text')]), `Beschreibung zu ${KATALOG[k]} fehlt`);
		}
	});
});

describe('AC-16: Kanaele gleichrangig nebeneinander', () => {
	test('E-Mail, Telegram, SMS und Premium-SMS stehen im Abschnitt Kanaele', async () => {
		const k = sichtbar(abschnitt(await hilfeHtml(), 'hilfe-kanaele'));
		for (const key of ['hilfe.kanaele.email', 'hilfe.kanaele.telegram', 'hilfe.kanaele.sms', 'hilfe.kanaele.premium_sms']) {
			assert.ok(k.includes(text(key)), `${key} fehlt im Abschnitt Kanaele`);
		}
	});
	test('kein Text auf der Seite nennt einen Hauptkanal oder Signal', async () => {
		const s = sichtbar(await hilfeHtml());
		assert.doesNotMatch(s, /Hauptkanal/i);
		assert.doesNotMatch(s, /\bSignal\b/);
	});
});

describe('AC-21 (Render): Lesbarkeit', () => {
	test('die Seite nutzt nie --g-ink-4 (nur Placeholder/Disabled erlaubt)', async () => {
		assert.ok(!(await hilfeHtml()).includes('--g-ink-4'));
	});
	test('kein „Tour" im gerenderten Text', async () => {
		assert.doesNotMatch(sichtbar(await hilfeHtml()), /\bTour/i);
	});
});

describe('AC-18: Hilfelink in der Startklar-Checkliste', () => {
	test('Link auf /hilfe mit Katalog-Text onboarding.checkliste.hilfe', async () => {
		const Checkliste = await ladeKomponente(CHECKLISTE_DATEI);
		assert.ok(Checkliste, 'StartklarCheckliste.svelte fehlt (Messaufbau)');
		const html = ohneKommentare(render(Checkliste, { props: { profil: profilNeu(), tripCount: 0, compareCount: 0 } }).body);
		const treffer = links(html).filter((l) => l.href === '/hilfe');
		assert.equal(treffer.length, 1, `erwartet genau einen Link auf /hilfe, gefunden ${treffer.length}`);
		assert.equal(treffer[0].text, text('onboarding.checkliste.hilfe'));
	});
});

// ─── AC-19: Seitenleiste, Konto-Menue, BottomNav ─────────────────────────────
const Sidebar = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/ui/sidebar/Sidebar.svelte')).href)).default;
const KontoSheet = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/ui/sidebar/KontoSheet.svelte')).href)).default;
const BottomNav = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/ui/sidebar/BottomNav.svelte')).href)).default;

function tagMitTestid(html: string, testid: string): string | null {
	const m = new RegExp(`<a\\b[^>]*data-testid="${testid}"[^>]*>[\\s\\S]*?</a>`).exec(html);
	return m ? m[0] : null;
}

describe('AC-19: Link „Hilfe" in Seitenleiste (Desktop) und Konto-Menue (Handy)', () => {
	test('Sidebar: nav-hilfe -> /hilfe, Text nav.hilfe', () => {
		const html = ohneKommentare(render(Sidebar, {
			props: { userId: 'u', displayName: 'U', currentPath: '/trips', darkMode: false, ontoggleDark: () => {} }
		}).body);
		const a = tagMitTestid(html, 'nav-hilfe');
		assert.ok(a, 'Sidebar: kein Eintrag data-testid="nav-hilfe"');
		assert.match(a!, /href="\/hilfe"/);
		assert.ok(sichtbar(a!).includes(text('nav.hilfe')));
	});
	test('KontoSheet (offen): konto-sheet-hilfe -> /hilfe, Text nav.hilfe', () => {
		const html = ohneKommentare(render(KontoSheet, {
			props: { open: true, onClose: () => {}, initials: 'U', displayName: 'U', userId: 'u', darkMode: false, ontoggleDark: () => {} }
		}).body);
		assert.ok(html.includes('konto-sheet-einstellungen'), 'Messaufbau kaputt: Konto-Sheet nicht offen gerendert');
		const a = tagMitTestid(html, 'konto-sheet-hilfe');
		assert.ok(a, 'KontoSheet: kein Eintrag data-testid="konto-sheet-hilfe"');
		assert.match(a!, /href="\/hilfe"/);
		assert.ok(sichtbar(a!).includes(text('nav.hilfe')));
	});
	test('Gegenprobe (bewusst gruen): BottomNav bleibt unveraendert — vier Ziele, kein /hilfe', () => {
		(globalThis as Record<string, unknown>).__gzLayoutTestPath = '/trips';
		const html = ohneKommentare(render(BottomNav, { props: { initials: 'U', kontoOpen: false, onKonto: () => {} } }).body);
		const ziele = links(html).map((l) => l.href);
		assert.deepEqual(ziele, ['/', '/trips', '/compare', '/archiv']);
	});
});
