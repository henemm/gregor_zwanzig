// TDD RED — Feature #2287 (Epic #2345, Etappe P2 „eine Reiterleiste"):
// `subscriptionTabs(kind)` und `resolveTab(kind, raw)` — EINE Tabelle, EINE
// Aufloesung fuer Trip- und Ortsvergleich-Hub.
//
// Spec: docs/specs/modules/feat_2287_tab_kennungen.md — E1/E2/E3, AC-1, AC-2, AC-4, AC-5, AC-6
//
// RED-Erwartung: `../subscriptionTabs.ts` existiert noch nicht → ERR_MODULE_NOT_FOUND.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/subscription_tabs_resolve.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { subscriptionTabs, resolveTab } from '../subscriptionTabs.ts';

type Kind = 'trip' | 'vergleich';
const KINDS: Kind[] = ['trip', 'vergleich'];

/** Punkte-Reiter: im Trip `etappen`, im Vergleich `orte` (Spec E2). */
const PUNKTE: Record<Kind, string> = { trip: 'etappen', vergleich: 'orte' };

function neueKennungen(kind: Kind): string[] {
	return ['uebersicht', PUNKTE[kind], 'wetter-metriken', 'wertebereiche', 'alarme', 'versand', 'vorschau'];
}

describe('subscriptionTabs(kind): Reihenfolge, Kennungen, Beschriftung (gleich wie vor #2287)', () => {
	test('Trip: sieben Reiter in der Reihenfolge der Reiterleiste', () => {
		assert.deepEqual(
			subscriptionTabs('trip').map((t) => t.id),
			neueKennungen('trip')
		);
	});

	test('Vergleich: sieben Reiter in der Reihenfolge der Reiterleiste', () => {
		assert.deepEqual(
			subscriptionTabs('vergleich').map((t) => t.id),
			neueKennungen('vergleich')
		);
	});

	test('Beschriftung unveraendert (Trip „Etappen & Wegpunkte", Vergleich „Orte")', () => {
		assert.deepEqual(
			subscriptionTabs('trip').map((t) => t.label),
			['Übersicht', 'Etappen & Wegpunkte', 'Wetter-Metriken', 'Wertebereiche', 'Alarme', 'Versand', 'Vorschau']
		);
		assert.deepEqual(
			subscriptionTabs('vergleich').map((t) => t.label),
			['Übersicht', 'Orte', 'Wetter-Metriken', 'Wertebereiche', 'Alarme', 'Versand', 'Vorschau']
		);
	});

	test('beide Hubs unterscheiden sich NUR im Punkte-Reiter (Teilungs-Invariante)', () => {
		const t = subscriptionTabs('trip').map((x) => x.id);
		const v = subscriptionTabs('vergleich').map((x) => x.id);
		const ohnePunkte = (ids: string[]) => ids.filter((i) => i !== 'etappen' && i !== 'orte');
		assert.deepEqual(ohnePunkte(t), ohnePunkte(v));
	});
});

describe('AC-4: neue Kennungen × beide kinds — unveraendert, kein Umschreiben', () => {
	for (const kind of KINDS) {
		for (const id of neueKennungen(kind)) {
			test(`resolveTab('${kind}', '${id}') → ${id}, legacy=false, known=true`, () => {
				assert.deepEqual(resolveTab(kind, id), { tab: id, legacy: false, known: true });
			});
		}
	}
});

/** Alt-Kennung → neuer Reiter je kind (kind-uebergreifende LEGACY-Tabelle, Spec E1 Punkt 2). */
const ALT: Array<[string, (k: Kind) => string]> = [
	['overview', () => 'uebersicht'],
	['stages', (k) => PUNKTE[k]],
	['weather', () => 'wetter-metriken'],
	['alerts', () => 'wertebereiche'],
	['briefings', () => 'versand'],
	['preview', () => 'vorschau'],
	['idealwerte', () => 'wertebereiche'],
	['layout', () => 'wetter-metriken']
];

describe('AC-1 / AC-2: Alt-Kennungen werden in BEIDEN Hubs auf den neuen Reiter umgeleitet', () => {
	for (const kind of KINDS) {
		for (const [alt, ziel] of ALT) {
			test(`resolveTab('${kind}', '${alt}') → ${ziel(kind)}, legacy=true (URL wird bereinigt)`, () => {
				const r = resolveTab(kind, alt);
				assert.equal(r.tab, ziel(kind));
				assert.equal(r.legacy, true, 'legacy-Flag steuert die einmalige URL-Bereinigung (E4)');
				assert.equal(r.known, true, 'eine Alt-Kennung ist bekannt — kein Rest-Fallback');
			});
		}
	}

	test('Beispiele der Spec: /trips/{id}?tab=alerts und /compare/{id}?tab=alerts → Wertebereiche', () => {
		assert.equal(resolveTab('trip', 'alerts').tab, 'wertebereiche');
		assert.equal(resolveTab('vergleich', 'alerts').tab, 'wertebereiche');
	});
});

describe('AC-5: kind-fremde Punkte-Kennung → eigener Punkte-Reiter', () => {
	test("Trip: 'orte' → 'etappen' (legacy)", () => {
		assert.deepEqual(resolveTab('trip', 'orte'), { tab: 'etappen', legacy: true, known: true });
	});
	test("Vergleich: 'etappen' → 'orte' (legacy)", () => {
		assert.deepEqual(resolveTab('vergleich', 'etappen'), { tab: 'orte', legacy: true, known: true });
	});
});

describe('AC-6: unbekannt / leer / fehlend → Uebersicht, tab-Parameter wird entfernt (bewusster Rest-Fallback)', () => {
	for (const kind of KINDS) {
		for (const roh of ['foo', 'Wertebereiche', 'punkte', '#weather', '   ', '']) {
			test(`resolveTab('${kind}', ${JSON.stringify(roh)}) → uebersicht, known=false, legacy=false`, () => {
				assert.deepEqual(resolveTab(kind, roh), { tab: 'uebersicht', legacy: false, known: false });
			});
		}
		test(`resolveTab('${kind}', null/undefined) → uebersicht, known=false`, () => {
			assert.equal(resolveTab(kind, null as unknown as string).tab, 'uebersicht');
			assert.equal(resolveTab(kind, null as unknown as string).known, false);
			assert.equal(resolveTab(kind, undefined as unknown as string).tab, 'uebersicht');
			assert.equal(resolveTab(kind, undefined as unknown as string).known, false);
		});
	}
});

describe('Konsistenz: jedes Aufloesungsergebnis ist ein Reiter der eigenen Tabelle', () => {
	for (const kind of KINDS) {
		test(`${kind}: alle neuen + alten + fremden Kennungen landen auf einer Kennung aus subscriptionTabs('${kind}')`, () => {
			const gueltig = subscriptionTabs(kind).map((t) => t.id);
			const alle = [...neueKennungen('trip'), ...neueKennungen('vergleich'), ...ALT.map(([a]) => a), 'foo', ''];
			for (const roh of alle) {
				assert.ok(gueltig.includes(resolveTab(kind, roh).tab), `${kind}/${roh} → ${resolveTab(kind, roh).tab}`);
			}
		});
	}
});
