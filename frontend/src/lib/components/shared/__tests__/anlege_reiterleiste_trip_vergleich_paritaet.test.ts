// TDD RED — Issue #2277 Scheibe S3: die Anlege-Seiten /trips/new und
// /compare/new fuehren ab „Wetter-Metriken" dieselbe Reiterleiste:
// Wetter-Metriken · Wertebereiche · Alarme · Versand — gleiche Beschriftung,
// gleiche Reihenfolge, gleicher Lock-Hinweis.
//
// Spec: docs/specs/modules/feat_2277_s3_reiter_angleichung_rueckbau.md (AC-1, AC-2, AC-3, AC-4, AC-9)
//
// Messaufbau:
//   - Trip-Seite: ECHTES SSR-Rendering von TripNewEditor.svelte (tripNewSsr.ts).
//     Im Leerzustand sind die Reiter ab Etappen gesperrt; ihr Lock-Hinweis steht
//     dann im title="Gesperrt — <Hinweis>" — das ist genau der Text, den der
//     Nutzer beim Ueberfahren bzw. im Lock-Toast sieht.
//   - Compare-Seite: fuer CompareNewEditor.svelte existiert kein SSR-Harness
//     (kein Stub fuer den compare-wizard-state-Context, vgl.
//     compare_new_footer_nav_clearance.test.ts). Gelesen wird deshalb die
//     Reiter-Definition `TAB_DEFS` als STRUKTURIERTE Eintraege (id/label/lockHint)
//     — dieselbe Liste, aus der CompareNewEditor Tab-Leiste UND Lock-Toast
//     rendert (title=`Gesperrt — ${t.lockHint}`, showLockToast(...lockHint)).
//     Positivkontrolle: genau 6 Eintraege, sonst ist der Messaufbau kaputt.
//
// Pendant-Sperre: liegt bewusst in shared/__tests__ (prueft BEIDE Editoren).
//
// RED HEUTE: der Trip heisst hinten „Briefing-Zeitplan · Alerts" (andere
// Reihenfolge, andere Hinweise), der Fusszeilen-Hinweis fordert den „Zeitplan".
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/anlege_reiterleiste_trip_vergleich_paritaet.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
	renderTripNew,
	desktopTabs,
	mobilTabLabels,
	visibleText,
	FRONTEND
} from '../../trip-new/__tests__/tripNewSsr.ts';

const COMPARE_EDITOR = join(FRONTEND, 'src/lib/components/compare-new/CompareNewEditor.svelte');

interface ReiterDef {
	label: string;
	lockHint: string | null;
}

/** Die Reiter-Definition `TAB_DEFS` aus CompareNewEditor.svelte als Eintraege. */
function compareReiter(): ReiterDef[] {
	const src = readFileSync(COMPARE_EDITOR, 'utf-8');
	const block = /const TAB_DEFS\b[^=]*=\s*\[([\s\S]*?)\];/.exec(src);
	assert.ok(block, 'Messaufbau kaputt: `const TAB_DEFS = [...]` in CompareNewEditor.svelte nicht gefunden.');
	const eintraege: ReiterDef[] = [];
	const re = /\{\s*id:\s*'([^']+)',\s*label:\s*'([^']+)',\s*lockHint:\s*(null|'[^']*')\s*\}/g;
	let m: RegExpExecArray | null;
	while ((m = re.exec(block![1]))) {
		eintraege.push({ label: m[2], lockHint: m[3] === 'null' ? null : m[3].slice(1, -1) });
	}
	assert.equal(
		eintraege.length,
		6,
		`Messaufbau kaputt: erwartet 6 Compare-Reiter (Vergleich, Orte, Wetter-Metriken, Wertebereiche, Alarme, Versand), gelesen ${eintraege.length}.`
	);
	return eintraege;
}

/** Die Trip-Reiter im Leerzustand (alle ausser Route gesperrt) als Eintraege. */
function tripReiter(): ReiterDef[] {
	const html = renderTripNew({ activeTab: 'route', isMobileViewport: false });
	const tabs = desktopTabs(html);
	assert.ok(tabs.length >= 6, `Messaufbau kaputt: nur ${tabs.length} Desktop-Reiter gelesen.`);
	return tabs.map((t) => ({
		label: t.label,
		lockHint: t.title?.startsWith('Gesperrt — ') ? t.title.slice('Gesperrt — '.length) : null
	}));
}

/** Alles ab (einschliesslich) „Wetter-Metriken". */
function abWetterMetriken(reiter: ReiterDef[]): ReiterDef[] {
	const i = reiter.findIndex((r) => r.label === 'Wetter-Metriken');
	assert.notEqual(i, -1, `Messaufbau kaputt: kein Reiter „Wetter-Metriken" in ${reiter.map((r) => r.label).join(' · ')}`);
	return reiter.slice(i);
}

const GEMEINSAME_FOLGE = ['Wetter-Metriken', 'Wertebereiche', 'Alarme', 'Versand'];

describe('AC-1: /trips/new — vollständige Reiterleiste', () => {
	const ZIEL = ['Route', 'Etappen & GPX', 'Wegpunkte prüfen', ...GEMEINSAME_FOLGE];

	test('Desktop: Route · Etappen & GPX · Wegpunkte prüfen · Wetter-Metriken · Wertebereiche · Alarme · Versand', () => {
		assert.deepEqual(
			tripReiter().map((r) => r.label),
			ZIEL,
			'AC-1 FAIL: die Trip-Reiterleiste weicht von der Zielfolge ab.'
		);
	});

	test('Mobil (390 px-Zweig): dieselbe Folge', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: true });
		assert.deepEqual(mobilTabLabels(html).slice(0, ZIEL.length), ZIEL, 'AC-1/AC-10 FAIL: Mobil-Reiterfolge stimmt nicht.');
	});

	test('„Briefing-Zeitplan" und „Alerts" kommen als Reiter nicht mehr vor (Desktop + Mobil)', () => {
		const desktop = tripReiter().map((r) => r.label);
		const mobil = mobilTabLabels(renderTripNew({ activeTab: 'route', isMobileViewport: true }));
		for (const alt of ['Briefing-Zeitplan', 'Zeitplan', 'Alerts']) {
			assert.ok(!desktop.includes(alt), `AC-1 FAIL: Desktop-Reiter „${alt}" existiert noch.`);
			assert.ok(!mobil.includes(alt), `AC-1 FAIL: Mobil-Reiter „${alt}" existiert noch.`);
		}
	});
});

describe('AC-2: Lock-Hinweise der Trip-Reiter Alarme und Versand', () => {
	test('Alarme: „erst Wertebereiche öffnen"; Versand: „erst Alarme öffnen"', () => {
		const reiter = tripReiter();
		const alarme = reiter.find((r) => r.label === 'Alarme');
		const versand = reiter.find((r) => r.label === 'Versand');
		assert.ok(alarme, 'AC-2 FAIL: kein Trip-Reiter „Alarme".');
		assert.ok(versand, 'AC-2 FAIL: kein Trip-Reiter „Versand".');
		assert.equal(alarme!.lockHint, 'erst Wertebereiche öffnen', 'AC-2 FAIL: falscher Lock-Hinweis am Reiter Alarme.');
		assert.equal(versand!.lockHint, 'erst Alarme öffnen', 'AC-2 FAIL: falscher Lock-Hinweis am Reiter Versand.');
	});
});

describe('AC-3/AC-9: Parität Trip ↔ Ortsvergleich ab Wetter-Metriken', () => {
	test('Compare-Referenz unverändert: Wetter-Metriken · Wertebereiche · Alarme · Versand (AC-9)', () => {
		assert.deepEqual(
			abWetterMetriken(compareReiter()).map((r) => r.label),
			GEMEINSAME_FOLGE,
			'AC-9 FAIL: die Compare-Reiterleiste ab Wetter-Metriken hat sich verändert — sie ist die Referenz der Parität.'
		);
	});

	test('Beschriftung und Reihenfolge identisch', () => {
		assert.deepEqual(
			abWetterMetriken(tripReiter()).map((r) => r.label),
			abWetterMetriken(compareReiter()).map((r) => r.label),
			'AC-3 FAIL: Trip und Ortsvergleich unterscheiden sich ab Wetter-Metriken in Beschriftung oder Reihenfolge.'
		);
	});

	test('Lock-Hinweise identisch — AUSSER Wetter-Metriken (kind-eigen, begründet)', () => {
		// Ausnahme (Spec-Entscheidung 1, AC-3): die Eingangsbedingung von
		// „Wetter-Metriken" ist fachlich verschieden — beim Trip muessen erst alle
		// GPX hochgeladen sein, beim Ortsvergleich erst mind. 2 Orte gewaehlt.
		// Ein gemeinsamer Hinweistext waere fuer eine der beiden Seiten falsch.
		const trip = abWetterMetriken(tripReiter());
		const vergleich = abWetterMetriken(compareReiter());
		assert.equal(trip[0].lockHint, 'erst alle GPX hochladen', 'Ausnahme Wetter-Metriken: Trip-Hinweis geändert.');
		assert.equal(vergleich[0].lockHint, 'erst mind. 2 Orte auswählen', 'Ausnahme Wetter-Metriken: Compare-Hinweis geändert.');
		assert.deepEqual(
			trip.slice(1).map((r) => [r.label, r.lockHint]),
			vergleich.slice(1).map((r) => [r.label, r.lockHint]),
			'AC-3 FAIL: Lock-Hinweise von Wertebereiche/Alarme/Versand weichen zwischen Trip und Ortsvergleich ab.'
		);
	});
});

describe('AC-4: Fußzeilen-Hinweis und Fortschritt auf /trips/new', () => {
	test('Desktop-Fußzeile fordert im Leerzustand den Versand, nicht den Zeitplan', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: false });
		const text = visibleText(html);
		assert.ok(
			text.includes('Versand einrichten zum Speichern'),
			'AC-4 FAIL: der Fußzeilen-Hinweis „Versand einrichten zum Speichern" fehlt.'
		);
		assert.ok(
			!text.includes('Zeitplan einrichten zum Speichern'),
			'AC-4 FAIL: der Fußzeilen-Hinweis fordert noch den Zeitplan.'
		);
	});

	test('Mobil-Fortschritt bleibt „0/4" (vier Meilensteine)', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: true });
		assert.match(visibleText(html), /\b0\/4\b/, 'AC-4 FAIL: die mobile Fortschrittsanzeige steht nicht auf „/4".');
	});
});
