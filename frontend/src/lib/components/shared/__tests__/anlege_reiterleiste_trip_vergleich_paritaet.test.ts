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
// Issue #1743 (feat_1743_reiter_aufraeumen, AC-17/AC-19): der Reiter „Versand" entfaellt auf beiden
// Anlege-Seiten; gemeinsame Folge ab Wetter-Metriken ist Wetter-Metriken · Wertebereiche · Alarme.
// Die Compare-Reiter werden jetzt per ECHTEM SSR-Rendering gelesen (Wizard-Kontext wie im
// AC-12-Block unten) statt per Quelltext-Regex auf `TAB_DEFS` — die Liste ist kuenftig abgeleitet.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/anlege_reiterleiste_trip_vergleich_paritaet.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
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

const { render } = await import('svelte/server');
const VergleichEditor = (await import(pathToFileURL(COMPARE_EDITOR).href)).default;

/** Die Desktop-Reiter von /compare/new im Leerzustand (alle ausser „Vergleich" gesperrt),
 *  gelesen aus dem ECHTEN SSR-Markup (`compare-editor-tab-<id>`, Lock-Hinweis im title). */
function compareReiter(): ReiterDef[] {
	const wiz = { name: '', region: '', profile: 'wandern', pickedIds: [] as string[] };
	const html = render(VergleichEditor, {
		props: { stateOverride: { activeTab: 'vergleich', isMobileViewport: false } },
		context: new Map([['compare-wizard-state', wiz]])
	}).body;
	const eintraege: ReiterDef[] = [];
	const re = /<button([^>]*\bdata-testid="compare-editor-tab-[a-z-]+"[^>]*)>([\s\S]*?)<\/button>/g;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		const title = /\btitle="([^"]*)"/.exec(m[1])?.[1] ?? null;
		const label = visibleText(m[2]).replace(/&amp;/g, '&').replace(/[⊘✓]/g, '').trim();
		eintraege.push({ label, lockHint: title?.startsWith('Gesperrt — ') ? title.slice('Gesperrt — '.length) : null });
	}
	assert.ok(
		eintraege.length >= 5,
		`Messaufbau kaputt: erwartet mind. 5 Compare-Reiter (Vergleich, Orte, Wetter-Metriken, Wertebereiche, Alarme), gelesen ${eintraege.length}.`
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

const GEMEINSAME_FOLGE = ['Wetter-Metriken', 'Wertebereiche', 'Alarme'];

describe('AC-1: /trips/new — vollständige Reiterleiste', () => {
	const ZIEL = ['Route', 'Etappen & GPX', 'Wegpunkte prüfen', ...GEMEINSAME_FOLGE];

	test('Desktop: Route · Etappen & GPX · Wegpunkte prüfen · Wetter-Metriken · Wertebereiche · Alarme (kein Versand)', () => {
		assert.deepEqual(
			tripReiter().map((r) => r.label),
			ZIEL,
			'AC-1 FAIL: die Trip-Reiterleiste weicht von der Zielfolge ab.'
		);
	});

	test('Mobil (390 px-Zweig): dieselbe Folge', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: true });
		assert.deepEqual(mobilTabLabels(html).slice(0, ZIEL.length + 1), ZIEL, 'AC-1/AC-10 FAIL: Mobil-Reiterfolge stimmt nicht (#1743: kein Reiter nach Alarme).');
	});

	test('„Briefing-Zeitplan" und „Alerts" kommen als Reiter nicht mehr vor (Desktop + Mobil)', () => {
		const desktop = tripReiter().map((r) => r.label);
		const mobil = mobilTabLabels(renderTripNew({ activeTab: 'route', isMobileViewport: true }));
		for (const alt of ['Briefing-Zeitplan', 'Zeitplan', 'Alerts', 'Versand']) {
			assert.ok(!desktop.includes(alt), `AC-1 FAIL: Desktop-Reiter „${alt}" existiert noch.`);
			assert.ok(!mobil.includes(alt), `AC-1 FAIL: Mobil-Reiter „${alt}" existiert noch.`);
		}
	});
});

describe('AC-2: Lock-Hinweis des Trip-Reiters Alarme; Versand ist kein Reiter mehr (#1743)', () => {
	test('Alarme: „erst Wertebereiche öffnen"; kein Reiter „Versand"', () => {
		const reiter = tripReiter();
		const alarme = reiter.find((r) => r.label === 'Alarme');
		assert.ok(alarme, 'AC-2 FAIL: kein Trip-Reiter „Alarme".');
		assert.equal(alarme!.lockHint, 'erst Wertebereiche öffnen', 'AC-2 FAIL: falscher Lock-Hinweis am Reiter Alarme.');
		assert.ok(!reiter.some((r) => r.label === 'Versand'), '#1743 AC-19 FAIL: Trip-Reiter „Versand" existiert noch.');
	});
});

describe('AC-3/AC-9: Parität Trip ↔ Ortsvergleich ab Wetter-Metriken', () => {
	test('Compare-Referenz: Wetter-Metriken · Wertebereiche · Alarme (AC-9, #1743 ohne Versand)', () => {
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
			'AC-3 FAIL: Lock-Hinweise von Wertebereiche/Alarme weichen zwischen Trip und Ortsvergleich ab.'
		);
	});
});

describe('AC-4: Fußzeilen-Hinweis und Fortschritt auf /trips/new', () => {
	test('Desktop-Fußzeile fordert im Leerzustand weder den Zeitplan noch einen Versand-Schritt (#1743)', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: false });
		const text = visibleText(html);
		assert.ok(
			!text.includes('Zeitplan einrichten zum Speichern'),
			'AC-4 FAIL: der Fußzeilen-Hinweis fordert noch den Zeitplan.'
		);
		assert.ok(
			!text.includes('Versand einrichten zum Speichern'),
			'#1743 AC-19 FAIL: der Fußzeilen-Hinweis fordert noch den Versand-Schritt — Speichern haengt an Alarme.'
		);
	});

	test('Mobil-Fortschritt startet bei „0/N"', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: true });
		assert.match(visibleText(html), /\b0\/\d\b/, 'AC-4 FAIL: keine mobile Fortschrittsanzeige „0/N".');
	});
});

// ── Onboarding S3 (Issue #2521, AC-12): neuer Knopf „Mit Standardwerten speichern" ──
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md. Additiv — die
// obigen Zusicherungen bleiben unveraendert. Beide Leisten fuehren (solange der
// Bestandsknopf gesperrt ist) denselben Knopf mit derselben Beschriftung. Der
// Ortsvergleich wird mit Wizard-Kontext gerendert wie in
// compare-new/__tests__/compare_new_lock_engine_wirkstelle.test.ts.
describe('AC-12 (#2521 S3): Standardwerte-Knopf in beiden Anlege-Leisten', () => {
	test('Trip-Footer und Ortsvergleich-Kopfzeile tragen den Knopf mit identischer Beschriftung', async () => {
		const Vergleich = VergleichEditor;
		const wiz = { name: 'X', region: '', profile: 'wandern', pickedIds: ['loc0', 'loc1'] };
		const vergleich = render(Vergleich, {
			props: { stateOverride: { activeTab: 'vergleich', isMobileViewport: false } },
			context: new Map([['compare-wizard-state', wiz]])
		}).body;
		const trip = renderTripNew({ activeTab: 'route', isMobileViewport: false });
		const beschriftung = (html: string, testid: string): string | null => {
			const m = new RegExp(`<button\\b[^>]*data-testid="${testid}"[^>]*>([\\s\\S]*?)</button>`).exec(html);
			return m ? visibleText(m[1]) : null;
		};
		const t = beschriftung(trip, 'trip-new-standardwerte-btn');
		const v = beschriftung(vergleich, 'compare-editor-standardwerte');
		assert.ok(t, 'AC-12 FAIL: Trip-Footer ohne Standardwerte-Knopf (trip-new-standardwerte-btn).');
		assert.ok(v, 'AC-12 FAIL: Ortsvergleich-Kopfzeile ohne Standardwerte-Knopf (compare-editor-standardwerte).');
		assert.equal(t, v, 'AC-12 FAIL: Beschriftung des Standardwerte-Knopfs weicht zwischen Trip und Ortsvergleich ab.');
	});
});
