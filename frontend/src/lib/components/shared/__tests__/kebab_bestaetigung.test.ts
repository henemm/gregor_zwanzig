// TDD RED — Issue #3442 (S5c aus #2797, Epic #2791): Rückfragen im Kebab-Menü des Hubs (Archivieren, Löschen).
// Spec: docs/specs/modules/feat_3442_kebab_rueckfragen.md — AC-3, AC-10, AC-11, AC-12, AC-14 (Kern-Schicht).
//
// VERTRAG für den Developer — frontend/src/lib/components/shared/kebabBestaetigung.ts (reine Funktionen,
// node:testbar, ohne DOM; Texte nur über den Katalog in der aktuellen Sprache, neue Schlüssel `aktionen.kebab.*`):
//
//   export function braucheRueckfrage(id: string): boolean;          // nur 'archive' und 'delete'
//   export interface KebabRueckfrage {
//     id: 'archive' | 'delete';
//     titel: string;                       // „Archivieren?“ / „Löschen?“
//     text: string;                        // Mockup-Wortlaut, Name als Platzhalter
//     bestaetigen: string;                 // tr('aktionen.archive') / tr('listen.archiv.endgueltig_loeschen')
//     abbrechen: string;                   // tr('aktionen.abbrechen')
//     gefahr: boolean;                     // true nur beim Löschen (Gefahrknopf)
//     abschnitt: 'kebab-bestaetigung-archivieren' | 'kebab-bestaetigung-loeschen';  // data-abschnitt am Panel
//   }
//   export function rueckfrage(id: string, name: string): KebabRueckfrage | null;   // null ohne Rückfrage
//   export function erfolgsText(id: string): string;                  // pause/resume/archive/unarchive
//   export function fehlerText(id: string, e: unknown): string;       // Netz / 5xx / 4xx mit Server-Detail
//
// Menülabels im Hub (subscriptionActions, Fläche 'hub'): „Archivieren …“ und „Löschen …“ (Leerzeichen + U+2026),
// alles andere ohne Ellipse; Listen und Mobil-Liste bleiben unverändert (AC-16).
//
// Fehlerobjekte sind ECHT: SubscriptionExecError entsteht über den echten Adapter (setArchived/deleteSubscription)
// aus einer echten Response; der Netzfehler ist der TypeError, den fetch im Browser wirft.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/kebab_bestaetigung.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { locale, trFor } from '../../../i18n/index.ts';
import { de } from '../../../i18n/messages/de/index.ts';
import { en } from '../../../i18n/messages/en/index.ts';
import { deleteSubscription, setArchived, SubscriptionExecError } from '../subscriptionExec.ts';
import { subscriptionActions } from '../subscriptionActions.ts';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;

afterEach(() => locale.set('de'));

async function modul(): Promise<Json> {
	try {
		return await import('../kebabBestaetigung.ts');
	} catch (e) {
		assert.fail(`TDD RED: shared/kebabBestaetigung.ts fehlt oder lädt nicht (${(e as Error).message})`);
	}
}

const NAME = 'GR221 Mallorca';
// Sonderzeichen: Anführungszeichen, spitze Klammern, Ersetzungsmuster ($&, {name}) dürfen nichts verbiegen.
const SONDER = 'Süd „Nord“ <b>&</b> $& {name}';

/** Echter SubscriptionExecError über den echten Adapter, aus einer echten Response mit `status`. */
async function serverFehler(id: 'archive' | 'delete', status: number, detail?: string): Promise<unknown> {
	const body = detail === undefined ? '' : JSON.stringify({ detail });
	const fetchFn = (async () => new Response(body, { status, headers: { 'Content-Type': 'application/json' } })) as typeof fetch;
	try {
		if (id === 'archive') await setArchived('trip', 't-3442', true, fetchFn);
		else await deleteSubscription('vergleich', 'c-3442', fetchFn);
	} catch (e) {
		assert.ok(e instanceof SubscriptionExecError, 'Vorbedingung: der Adapter wirft SubscriptionExecError');
		return e;
	}
	assert.fail('Vorbedingung: der Adapter hätte werfen müssen');
}

/** Netzfehler, wie fetch ihn wirft (kein SubscriptionExecError). */
async function netzFehler(id: 'archive' | 'delete'): Promise<unknown> {
	const fetchFn = (async () => {
		throw new TypeError('Failed to fetch');
	}) as typeof fetch;
	try {
		if (id === 'archive') await setArchived('vergleich', 'c-3442', true, fetchFn);
		else await deleteSubscription('trip', 't-3442', fetchFn);
	} catch (e) {
		assert.ok(!(e instanceof SubscriptionExecError), 'Vorbedingung: Netzfehler ist kein SubscriptionExecError');
		return e;
	}
	assert.fail('Vorbedingung: der Adapter hätte werfen müssen');
}

describe('AC-3/AC-10: nur Archivieren und Löschen fragen nach', () => {
	test('braucheRueckfrage: archive/delete wahr; pause/resume/unarchive/send falsch', async () => {
		const m = await modul();
		assert.equal(m.braucheRueckfrage('archive'), true);
		assert.equal(m.braucheRueckfrage('delete'), true);
		// #3443 AC-2: „Aktivieren“ fragt nicht nach (schreibt nichts, nennt nur, was fehlt).
		for (const id of ['pause', 'resume', 'unarchive', 'send', 'continue-setup', 'activate', ''])
			assert.equal(m.braucheRueckfrage(id), false, `${id || '(leer)'} darf keine Rückfrage haben`);
	});

	test('rueckfrage ohne Rückfrage-Aktion ist null (Reaktivieren, Pausieren)', async () => {
		const m = await modul();
		for (const id of ['unarchive', 'pause', 'resume', 'activate']) assert.equal(m.rueckfrage(id, NAME), null, id);
	});
});

describe('AC-1/AC-3: Rückfrage-Texte (Mockup-Wortlaut, Name als Platzhalter)', () => {
	test('Löschen: Titel, Text, „Endgültig löschen“ als Gefahrknopf, „Abbrechen“, Abschnitt-Haken', async () => {
		const m = await modul();
		assert.deepEqual(m.rueckfrage('delete', NAME), {
			id: 'delete',
			titel: 'Löschen?',
			text: '„GR221 Mallorca“ wird endgültig gelöscht. Briefings und Alarme hören sofort auf. Das lässt sich nicht rückgängig machen.',
			bestaetigen: 'Endgültig löschen',
			abbrechen: 'Abbrechen',
			gefahr: true,
			abschnitt: 'kebab-bestaetigung-loeschen'
		});
	});

	test('Archivieren: Titel, Text, „Archivieren“ (kein Gefahrknopf), „Abbrechen“, Abschnitt-Haken', async () => {
		const m = await modul();
		assert.deepEqual(m.rueckfrage('archive', NAME), {
			id: 'archive',
			titel: 'Archivieren?',
			text: '„GR221 Mallorca“ verschwindet aus der Liste. Es kommen keine Briefings und Alarme mehr. Du kannst es im Archiv reaktivieren.',
			bestaetigen: 'Archivieren',
			abbrechen: 'Abbrechen',
			gefahr: false,
			abschnitt: 'kebab-bestaetigung-archivieren'
		});
	});

	test('Name mit Sonderzeichen und Ersetzungsmustern steht wörtlich im Text', async () => {
		const m = await modul();
		assert.equal(
			m.rueckfrage('delete', SONDER).text,
			`„${SONDER}“ wird endgültig gelöscht. Briefings und Alarme hören sofort auf. Das lässt sich nicht rückgängig machen.`
		);
		assert.equal(
			m.rueckfrage('archive', SONDER).text,
			`„${SONDER}“ verschwindet aus der Liste. Es kommen keine Briefings und Alarme mehr. Du kannst es im Archiv reaktivieren.`
		);
	});

	test('der Name gehört zum Aufruf: zwei Namen ergeben zwei verschiedene Texte', async () => {
		const m = await modul();
		assert.notEqual(m.rueckfrage('delete', 'A').text, m.rueckfrage('delete', 'B').text);
		assert.ok(m.rueckfrage('delete', 'Dolomiten Süd').text.includes('„Dolomiten Süd“'));
	});
});

describe('AC-4/AC-10/AC-11: Erfolgsmeldungen je Aktion (Wortlaut #2797)', () => {
	test('Pausieren, Fortsetzen, Archivieren, Reaktivieren', async () => {
		const m = await modul();
		assert.equal(m.erfolgsText('pause'), 'Pausiert. Bis ‚Fortsetzen‘ kommen keine Briefings und Alarme.');
		assert.equal(m.erfolgsText('resume'), 'Fortgesetzt. Das nächste Briefing kommt wie geplant.');
		assert.equal(m.erfolgsText('archive'), 'Archiviert. Im Archiv kannst du es reaktivieren.');
		assert.equal(m.erfolgsText('unarchive'), 'Reaktiviert.');
	});
});

describe('AC-12: Fehlertexte nach Fehlerklasse, mit echten Fehlerobjekten', () => {
	const WORT = { archive: 'Archivieren', delete: 'Löschen' } as const;
	for (const id of ['archive', 'delete'] as const) {
		test(`${id}: Netzfehler ⇒ „${WORT[id]} hat nicht geklappt: keine Verbindung zum Server. …“`, async () => {
			const m = await modul();
			assert.equal(
				m.fehlerText(id, await netzFehler(id)),
				`${WORT[id]} hat nicht geklappt: keine Verbindung zum Server. Versuch es gleich noch einmal.`
			);
		});
		test(`${id}: Server-5xx ⇒ „${WORT[id]} hat nicht geklappt: Fehler auf dem Server. …“ (Detail wird NICHT gezeigt)`, async () => {
			const m = await modul();
			for (const status of [500, 502, 503]) {
				assert.equal(
					m.fehlerText(id, await serverFehler(id, status, 'interner Stacktrace xyz')),
					`${WORT[id]} hat nicht geklappt: Fehler auf dem Server. Versuch es später noch einmal.`,
					`Status ${status}`
				);
			}
		});
		test(`${id}: 4xx mit Server-Detail ⇒ das Detail`, async () => {
			const m = await modul();
			assert.equal(m.fehlerText(id, await serverFehler(id, 409, 'Der Trip wird gerade bearbeitet.')), 'Der Trip wird gerade bearbeitet.');
			assert.equal(m.fehlerText(id, await serverFehler(id, 422, 'Name fehlt.')), 'Name fehlt.');
		});
	}
	test('Netz- und Serverfehler unterscheiden sich (keine Sammelmeldung)', async () => {
		const m = await modul();
		assert.notEqual(m.fehlerText('delete', await netzFehler('delete')), m.fehlerText('delete', await serverFehler('delete', 500)));
	});
});

describe('Menülabels im Hub: Ellipse nur bei Aktionen mit Rückfrage; Listen unverändert (AC-16)', () => {
	const labels = (status: Json, surface: Json) => subscriptionActions('trip', status, surface).map((a) => a.label);
	test('Hub DE: aktiv, pausiert, archiviert, Entwurf', () => {
		assert.deepEqual(labels('active', 'hub'), ['Pausieren', 'Archivieren …', 'Löschen …']);
		assert.deepEqual(labels('paused', 'hub'), ['Fortsetzen', 'Archivieren …', 'Löschen …']);
		assert.deepEqual(labels('archived', 'hub'), ['Reaktivieren', 'Löschen …']);
		// Entwurf: „Löschen …“ steht unverändert am Ende; die neue Reihenfolge mit „Aktivieren“ prüft
		// der Test „#3443 Hub DE Entwurf: …“ unten.
		assert.equal(labels('draft', 'hub').at(-1), 'Löschen …');
	});
	test('#3443 Hub DE Entwurf: „Aktivieren“ (ohne Ellipse, keine Rückfrage) zuerst, dann „Löschen …“', () => {
		assert.deepEqual(labels('draft', 'hub'), ['Aktivieren', 'Löschen …']);
	});
	test('Hub EN: „Archive …“ / „Delete …“', () => {
		locale.set('en');
		assert.deepEqual(labels('active', 'hub'), ['Pause', 'Archive …', 'Delete …']);
	});
	test('Trip und Orts-Vergleich bekommen dieselben Hub-Labels (ein Code)', () => {
		for (const status of ['active', 'paused', 'archived', 'draft'] as const)
			assert.deepEqual(
				subscriptionActions('vergleich', status, 'hub').map((a) => a.label),
				labels(status, 'hub'),
				status
			);
	});
	test('Liste und Mobil-Liste: „Löschen“ ohne Ellipse (unverändert)', () => {
		for (const surface of ['list', 'mobile'] as const) {
			const l = labels('active', surface);
			assert.ok(l.includes('Löschen'), `${surface}: ${JSON.stringify(l)}`);
			assert.ok(!l.some((x: string) => x.includes('…')), `${surface}: ${JSON.stringify(l)}`);
		}
	});
});

describe('AC-14: Englisch über den Katalog (kein hartkodierter Text)', () => {
	test('Rückfrage EN: Knöpfe aus dem Katalog, Titel/Text englisch mit Namen', async () => {
		const m = await modul();
		const deDel = m.rueckfrage('delete', NAME);
		const deArc = m.rueckfrage('archive', NAME);
		locale.set('en');
		const del = m.rueckfrage('delete', NAME);
		const arc = m.rueckfrage('archive', NAME);
		assert.equal(del.bestaetigen, 'Delete permanently');
		assert.equal(arc.bestaetigen, 'Archive');
		assert.equal(del.abbrechen, 'Cancel');
		assert.equal(arc.abbrechen, 'Cancel');
		for (const [r, d] of [[del, deDel], [arc, deArc]]) {
			assert.notEqual(r.titel, d.titel);
			assert.notEqual(r.text, d.text);
			assert.ok(r.text.includes(NAME), `EN-Text ohne Namen: ${r.text}`);
			assert.doesNotMatch(`${r.titel} ${r.text}`, /[äöüßÄÖÜ]|Löschen|Archivieren|Briefings und Alarme/);
			assert.equal(r.abschnitt, d.abschnitt, 'Abschnitt-Haken ist sprachunabhängig');
			assert.equal(r.gefahr, d.gefahr);
		}
	});

	test('Erfolgs- und Fehlertexte EN weichen vom Deutschen ab und sind nicht deutsch', async () => {
		const m = await modul();
		const fehler = { netz: await netzFehler('delete'), server: await serverFehler('archive', 500) };
		const deutsch = [
			...['pause', 'resume', 'archive', 'unarchive'].map((id) => m.erfolgsText(id)),
			m.fehlerText('delete', fehler.netz),
			m.fehlerText('archive', fehler.server)
		];
		locale.set('en');
		const englisch = [
			...['pause', 'resume', 'archive', 'unarchive'].map((id) => m.erfolgsText(id)),
			m.fehlerText('delete', fehler.netz),
			m.fehlerText('archive', fehler.server)
		];
		englisch.forEach((txt: string, i: number) => {
			assert.ok(txt.length > 0, `leer: ${i}`);
			assert.notEqual(txt, deutsch[i], `nicht übersetzt: ${txt}`);
			assert.doesNotMatch(txt, /[äöüßÄÖÜ]|hat nicht geklappt|Versuch es|Pausiert|Fortgesetzt|Archiviert|Reaktiviert/, txt);
		});
	});

	test('Katalog: neue Schlüssel aktionen.kebab.* in DE und EN gleich, Platzhalter gleich, nicht leer', () => {
		const kebab = (k: Record<string, string>) => Object.keys(k).filter((x) => x.startsWith('aktionen.kebab.')).sort();
		const d = kebab(de as Record<string, string>);
		const e = kebab(en as Record<string, string>);
		// mindestens: 2 Titel, 2 Texte, 4 Erfolgsmeldungen, 2 Fehlerklassen
		assert.ok(d.length >= 10, `zu wenige aktionen.kebab.*-Schlüssel in de: ${JSON.stringify(d)}`);
		assert.deepEqual(e, d, 'Schlüsselmengen aktionen.kebab.* in de/en verschieden');
		const ph = (s: string) => [...s.matchAll(/\{([a-z0-9_]+)\}/g)].map((x) => x[1]).sort();
		for (const k of d) {
			const dv = (de as Record<string, string>)[k];
			const ev = (en as Record<string, string>)[k];
			assert.ok(dv.trim() && ev.trim(), `${k}: leer`);
			assert.deepEqual(ph(ev), ph(dv), `${k}: Platzhalter de/en verschieden`);
		}
	});

	test('Katalog DE enthält die Mockup-Texte (Titel, Meldungen) unter aktionen.kebab.*', () => {
		const werte = Object.entries(de as Record<string, string>)
			.filter(([k]) => k.startsWith('aktionen.kebab.'))
			.map(([, v]) => v);
		for (const soll of [
			'Löschen?',
			'Archivieren?',
			'Pausiert. Bis ‚Fortsetzen‘ kommen keine Briefings und Alarme.',
			'Fortgesetzt. Das nächste Briefing kommt wie geplant.',
			'Archiviert. Im Archiv kannst du es reaktivieren.',
			'Reaktiviert.'
		])
			assert.ok(werte.includes(soll), `„${soll}“ fehlt unter aktionen.kebab.*`);
		// Bestehende Knopftexte werden wiederverwendet, nicht dupliziert geändert.
		assert.equal(trFor('de', 'listen.archiv.endgueltig_loeschen'), 'Endgültig löschen');
		assert.equal(trFor('de', 'aktionen.archive'), 'Archivieren');
		assert.equal(trFor('de', 'aktionen.abbrechen'), 'Abbrechen');
	});
});
