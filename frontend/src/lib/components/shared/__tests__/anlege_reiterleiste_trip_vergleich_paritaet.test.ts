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
//     (kein Stub fuer den Wizard-Context, vgl.
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
	// Issue #2727 (AC-9): kein Context-Stub mehr — Leerzustand = stateOverride ohne Name/Orte.
	const html = render(VergleichEditor, {
		props: { stateOverride: { activeTab: 'vergleich', isMobileViewport: false, name: '', pickedIds: [] } }
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
		eintraege.length >= 4,
		`Messaufbau kaputt: erwartet mind. 4 Compare-Reiter (Vergleich, Orte, Wetter, Zustellung), gelesen ${eintraege.length}.`
	);
	return eintraege;
}

/** Die Trip-Reiter im Leerzustand (alle ausser Route gesperrt) als Eintraege. */
function tripReiter(): ReiterDef[] {
	const html = renderTripNew({ activeTab: 'route', isMobileViewport: false });
	const tabs = desktopTabs(html);
	assert.ok(tabs.length >= 5, `Messaufbau kaputt: nur ${tabs.length} Desktop-Reiter gelesen.`);
	return tabs.map((t) => ({
		label: t.label,
		lockHint: t.title?.startsWith('Gesperrt — ') ? t.title.slice('Gesperrt — '.length) : null
	}));
}

// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-6): die gemeinsame Folge ab „Wetter"
// lautet Wetter · Zustellung (Wertebereiche gehen in Wetter auf, Alarme in Zustellung).
/** Alles ab (einschliesslich) „Wetter". */
function abWetterMetriken(reiter: ReiterDef[]): ReiterDef[] {
	const i = reiter.findIndex((r) => r.label === 'Wetter');
	assert.notEqual(i, -1, `Messaufbau kaputt: kein Reiter „Wetter" in ${reiter.map((r) => r.label).join(' · ')}`);
	return reiter.slice(i);
}

const GEMEINSAME_FOLGE = ['Wetter', 'Zustellung'];

describe('AC-1: /trips/new — vollständige Reiterleiste', () => {
	const ZIEL = ['Route', 'Etappen & GPX', 'Wegpunkte prüfen', ...GEMEINSAME_FOLGE];

	test('Desktop: Route · Etappen & GPX · Wegpunkte prüfen · Wetter · Zustellung (kein Versand)', () => {
		assert.deepEqual(
			tripReiter().map((r) => r.label),
			ZIEL,
			'AC-1 FAIL: die Trip-Reiterleiste weicht von der Zielfolge ab.'
		);
	});

	test('Mobil (390 px-Zweig): dieselbe Folge', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: true });
		assert.deepEqual(mobilTabLabels(html).slice(0, ZIEL.length + 1), ZIEL, 'AC-1/AC-10 FAIL: Mobil-Reiterfolge stimmt nicht (kein Reiter nach Zustellung).');
	});

	test('„Briefing-Zeitplan", „Alerts" und die entfallenen Schritte kommen als Reiter nicht mehr vor (Desktop + Mobil)', () => {
		const desktop = tripReiter().map((r) => r.label);
		const mobil = mobilTabLabels(renderTripNew({ activeTab: 'route', isMobileViewport: true }));
		for (const alt of ['Briefing-Zeitplan', 'Zeitplan', 'Alerts', 'Versand', 'Wetter-Metriken', 'Wertebereiche', 'Alarme']) {
			assert.ok(!desktop.includes(alt), `AC-1 FAIL: Desktop-Reiter „${alt}" existiert noch.`);
			assert.ok(!mobil.includes(alt), `AC-1 FAIL: Mobil-Reiter „${alt}" existiert noch.`);
		}
	});
});

describe('AC-2: Lock-Hinweis des Trip-Reiters Zustellung; Versand ist kein Reiter mehr (#1743)', () => {
	test('Zustellung: „erst Wetter öffnen"; kein Reiter „Versand"', () => {
		const reiter = tripReiter();
		const zustellung = reiter.find((r) => r.label === 'Zustellung');
		assert.ok(zustellung, 'AC-2 FAIL: kein Trip-Reiter „Zustellung".');
		assert.equal(zustellung!.lockHint, 'erst Wetter öffnen', 'AC-2 FAIL: falscher Lock-Hinweis am Reiter Zustellung.');
		assert.ok(!reiter.some((r) => r.label === 'Versand'), '#1743 AC-19 FAIL: Trip-Reiter „Versand" existiert noch.');
	});
});

describe('AC-3/AC-9: Parität Trip ↔ Ortsvergleich ab Wetter-Metriken', () => {
	test('Compare-Referenz: Wetter · Zustellung (AC-9, #2794)', () => {
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
			'AC-3 FAIL: Lock-Hinweis von Zustellung weicht zwischen Trip und Ortsvergleich ab.'
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
	// #2837 S2 (Entscheidung 6, AC-10) UMGEDREHT: beide tragen den Knopf im Desktop-FUSS
	// (Trip tn-desktop-footer, Ortsvergleich cm-desktop-footer), der Vergleich nicht mehr in der Kopfzeile.
	test('Trip-Fuß und Ortsvergleich-Fuß tragen den Knopf mit identischer Beschriftung', async () => {
		const Vergleich = VergleichEditor;
		// Issue #2727 (AC-9): kein Context-Stub mehr — Name und Orte reisen ueber stateOverride.
		const vergleich = render(Vergleich, {
			props: { stateOverride: { activeTab: 'vergleich', isMobileViewport: false, name: 'X', pickedIds: ['loc0', 'loc1'] } }
		}).body;
		const trip = renderTripNew({ activeTab: 'route', isMobileViewport: false });
		const beschriftung = (html: string, testid: string): string | null => {
			const m = new RegExp(`<button\\b[^>]*data-testid="${testid}"[^>]*>([\\s\\S]*?)</button>`).exec(html);
			return m ? visibleText(m[1]) : null;
		};
		/** Ab dem Fuß-Wrapper (der Fuß ist das letzte Element des Desktop-Zweigs). */
		const abFuss = (html: string, fuss: string): string => {
			const i = html.indexOf(`data-testid="${fuss}"`);
			assert.notEqual(i, -1, `#2837 S2 FAIL: Desktop-Fuß ${fuss} fehlt.`);
			return html.slice(i);
		};
		const t = beschriftung(abFuss(trip, 'tn-desktop-footer'), 'trip-new-standardwerte-btn');
		const v = beschriftung(abFuss(vergleich, 'cm-desktop-footer'), 'compare-editor-standardwerte');
		assert.ok(t, 'AC-12 FAIL: Trip-Fuß ohne Standardwerte-Knopf (trip-new-standardwerte-btn).');
		assert.ok(v, '#2837 S2 AC-10 FAIL: Ortsvergleich-Fuß ohne Standardwerte-Knopf (compare-editor-standardwerte).');
		assert.equal(t, v, 'AC-12 FAIL: Beschriftung des Standardwerte-Knopfs weicht zwischen Trip und Ortsvergleich ab.');
	});
});
