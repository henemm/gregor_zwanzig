// TDD RED — Issue #2278 (Epic #2345 P3), AC-1, AC-6, AC-8, AC-12.
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md
//
// EINE Erwartungstabelle (kind-unabhaengig!) fuer `subscriptionActions(kind, status, surface)`:
// beide Arten x vier Lebenszyklus-Status x drei Flaechen. Die Tabelle steht hier EINMAL;
// beide Arten werden gegen dieselbe Zeile geprueft (AC-6).
//
// Vokabular: `kind` ist der bestehende `SubscriptionKind` aus shared/subscriptionTabs.ts
// ('trip' | 'vergleich'), kein zweites Vokabular. `status` = Lebenszyklus-Schicht
// 'draft' | 'active' | 'paused' | 'archived' (Ausgabe von `subscriptionLifecycle`).
//
// Beschriftungen = die PO-freigegebenen AC-Texte (AC-1/AC-2/AC-12): Pausieren/Fortsetzen,
// Senden, Alarme, Wetter-Metriken, Bearbeiten, Loeschen, Setup fortsetzen,
// Archivieren/Reaktivieren.
// #1743 (Spec feat_1743_reiter_aufraeumen AC-27): die Aktion „Vorschau" entfaellt ersatzlos;
// die uebrigen Aktionen bleiben in Reihenfolge und Wirkung unveraendert.
//
// ANNAHMEN, die die Spec nicht ausdruecklich festlegt (im Handback gelistet):
//   - Status 'archived' auf Liste/Mobil: Reaktivieren · Loeschen (Liste blendet Archiviertes
//     aus, die Zelle ist nur der Vollstaendigkeit der Tabelle wegen festgelegt)
//   - Hub-Kebab 'draft': nur Loeschen; Hub-Kebab 'archived': Reaktivieren · Loeschen
//
// RED heute: das Modul `shared/subscriptionActions.ts` existiert nicht.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/subscriptionActions.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MODUL = pathToFileURL(path.join(HERE, '..', 'subscriptionActions.ts')).href;
const mod: any = await import(MODUL).catch(() => null);

function braucheModul(): any {
	assert.ok(mod, 'Modul shared/subscriptionActions.ts fehlt (RED) — AC-6 Aktionsquelle.');
	return mod;
}

type Kind = 'trip' | 'vergleich';
type Status = 'draft' | 'active' | 'paused' | 'archived';
type Surface = 'list' | 'hub' | 'mobile';
const KINDS: Kind[] = ['trip', 'vergleich'];

const LABEL: Record<string, string> = {
	pause: 'Pausieren',
	resume: 'Fortsetzen',
	send: 'Senden',
	alarms: 'Alarme',
	weather: 'Wetter-Metriken',
	edit: 'Bearbeiten',
	archive: 'Archivieren',
	unarchive: 'Reaktivieren',
	delete: 'Löschen',
	'continue-setup': 'Setup fortsetzen'
};

const LISTE_AKTIV = ['pause', 'send', 'alarms', 'weather', 'edit', 'delete'];
const LISTE_PAUSIERT = ['resume', 'send', 'alarms', 'weather', 'edit', 'delete'];

/** DIE Erwartungstabelle: status -> Flaeche -> IDs in Reihenfolge. */
const ERWARTET: Record<Status, Record<Surface, string[]>> = {
	draft: {
		list: ['continue-setup', 'delete'],
		mobile: ['continue-setup', 'delete'],
		hub: ['delete']
	},
	active: { list: LISTE_AKTIV, mobile: LISTE_AKTIV, hub: ['pause', 'archive', 'delete'] },
	paused: { list: LISTE_PAUSIERT, mobile: LISTE_PAUSIERT, hub: ['resume', 'archive', 'delete'] },
	archived: {
		list: ['unarchive', 'delete'],
		mobile: ['unarchive', 'delete'],
		hub: ['unarchive', 'delete']
	}
};

describe('AC-6: subscriptionActions = EINE Tabelle fuer beide Arten', () => {
	for (const status of Object.keys(ERWARTET) as Status[]) {
		for (const surface of Object.keys(ERWARTET[status]) as Surface[]) {
			for (const kind of KINDS) {
				test(`${kind} x ${status} x ${surface}: IDs, Beschriftung, Reihenfolge`, () => {
					const { subscriptionActions } = braucheModul();
					const ist = subscriptionActions(kind, status, surface);
					const ids = ist.map((a: any) => a.id);
					assert.deepEqual(ids, ERWARTET[status][surface], `IDs/Reihenfolge weichen ab (${kind}/${status}/${surface})`);
					assert.deepEqual(
						ist.map((a: any) => a.label),
						ERWARTET[status][surface].map((id) => LABEL[id]),
						`Beschriftungen weichen ab (${kind}/${status}/${surface})`
					);
				});
			}
		}
	}

	test('beide Arten liefern bei gleichem Status identische Ergebnisse (alle Zellen)', () => {
		const { subscriptionActions } = braucheModul();
		for (const status of Object.keys(ERWARTET) as Status[]) {
			for (const surface of ['list', 'hub', 'mobile'] as Surface[]) {
				assert.deepEqual(
					subscriptionActions('trip', status, surface),
					subscriptionActions('vergleich', status, surface),
					`Trip und Ortsvergleich unterscheiden sich bei ${status}/${surface}`
				);
			}
		}
	});

	test('"Loeschen" ist an jeder Stelle als gefaehrlich markiert, sonst keine Aktion', () => {
		const { subscriptionActions } = braucheModul();
		for (const status of Object.keys(ERWARTET) as Status[]) {
			for (const surface of ['list', 'hub', 'mobile'] as Surface[]) {
				for (const a of subscriptionActions('trip', status, surface)) {
					assert.equal(!!a.danger, a.id === 'delete', `danger-Flag falsch bei ${a.id} (${status}/${surface})`);
				}
			}
		}
	});
});

describe('AC-8: Alarme / Wetter-Metriken statt "Alert-Konfiguration"', () => {
	test('keine Fläche, kein Status, keine Art kennt die ID "alert-config"', () => {
		const { subscriptionActions } = braucheModul();
		for (const kind of KINDS)
			for (const status of Object.keys(ERWARTET) as Status[])
				for (const surface of ['list', 'hub', 'mobile'] as Surface[])
					for (const a of subscriptionActions(kind, status, surface)) {
						assert.notEqual(a.id, 'alert-config');
						assert.doesNotMatch(a.label, /Alert-Konfiguration/);
					}
	});

	test('aktiv in der Liste: "alarms" und "weather" fuer beide Arten vorhanden', () => {
		const { subscriptionActions } = braucheModul();
		for (const kind of KINDS) {
			const ids = subscriptionActions(kind, 'active', 'list').map((a: any) => a.id);
			assert.ok(ids.includes('alarms') && ids.includes('weather'), `${kind}: ${ids.join(',')}`);
		}
	});
});

describe('AC-1: Trip-Liste hat "Pausieren" an erster Stelle (wie Ortsvergleich)', () => {
	test('aktiver Trip, Liste: erste Aktion = Pausieren', () => {
		const { subscriptionActions } = braucheModul();
		const erste = subscriptionActions('trip', 'active', 'list')[0];
		assert.deepEqual([erste.id, erste.label], ['pause', 'Pausieren']);
	});
	test('pausierter Trip, Liste: erste Aktion = Fortsetzen', () => {
		const { subscriptionActions } = braucheModul();
		const erste = subscriptionActions('trip', 'paused', 'list')[0];
		assert.deepEqual([erste.id, erste.label], ['resume', 'Fortsetzen']);
	});
});

describe('AC-12: Hub-Kebab = Lebenszyklus (Senden ist Primaerknopf, nicht im Kebab)', () => {
	test('Hub enthaelt weder send noch preview/edit/alarms/weather', () => {
		const { subscriptionActions } = braucheModul();
		for (const kind of KINDS)
			for (const status of ['active', 'paused'] as Status[]) {
				const ids = subscriptionActions(kind, status, 'hub').map((a: any) => a.id);
				for (const verboten of ['send', 'preview', 'edit', 'alarms', 'weather'])
					assert.ok(!ids.includes(verboten), `${kind}/${status}: Hub-Kebab enthaelt ${verboten}`);
			}
	});
	test('Liste und Mobil bieten kein "Archivieren" (Liste blendet Archiviertes aus)', () => {
		const { subscriptionActions } = braucheModul();
		for (const surface of ['list', 'mobile'] as Surface[])
			for (const status of ['draft', 'active', 'paused'] as Status[])
				assert.ok(!subscriptionActions('trip', status, surface).some((a: any) => a.id === 'archive'));
	});
});

describe('Lebenszyklus-Schicht subscriptionLifecycle(kind, obj, now?)', () => {
	const JETZT = new Date('2026-10-17T12:00:00Z');
	const etappe = (date: string) => ({ id: 's', name: 's', date, waypoints: [] });
	const trip = (extra: Record<string, unknown> = {}) => ({
		id: 't1',
		name: 'T',
		stages: [etappe('2026-10-17')],
		...extra
	});
	const preset = (extra: Record<string, unknown> = {}) => ({
		id: 'c1',
		name: 'V',
		location_ids: ['a'],
		schedule: 'daily',
		...extra
	});

	test('Trip: ohne Etappen-Datum = draft; geplant/aktiv/fertig = active', () => {
		const { subscriptionLifecycle } = braucheModul();
		assert.equal(subscriptionLifecycle('trip', trip({ stages: [] }), JETZT), 'draft');
		for (const datum of ['2026-12-01', '2026-10-17', '2026-01-01'])
			assert.equal(subscriptionLifecycle('trip', trip({ stages: [etappe(datum)] }), JETZT), 'active', datum);
	});
	test('Trip: paused_at = paused, archived_at gewinnt = archived', () => {
		const { subscriptionLifecycle } = braucheModul();
		assert.equal(subscriptionLifecycle('trip', trip({ paused_at: '2026-10-01T00:00:00Z' }), JETZT), 'paused');
		assert.equal(
			subscriptionLifecycle('trip', trip({ paused_at: 'x', archived_at: '2026-10-02T00:00:00Z' }), JETZT),
			'archived'
		);
	});
	test('Ortsvergleich: Entwurf / aktiv / pausiert (manual und paused_at) / archiviert', () => {
		const { subscriptionLifecycle } = braucheModul();
		assert.equal(subscriptionLifecycle('vergleich', preset({ location_ids: [] })), 'draft');
		assert.equal(subscriptionLifecycle('vergleich', preset()), 'active');
		assert.equal(subscriptionLifecycle('vergleich', preset({ schedule: 'manual' })), 'paused');
		assert.equal(subscriptionLifecycle('vergleich', preset({ paused_at: '2026-10-01T00:00:00Z' })), 'paused');
		assert.equal(subscriptionLifecycle('vergleich', preset({ archived_at: '2026-10-02T00:00:00Z' })), 'archived');
	});
});
