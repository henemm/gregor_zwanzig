// TDD RED — Feature #2287 (Epic #2345, Etappe P2 „eine Reiterleiste"):
// BEIDE Hubs (`TripTabs.svelte`, `CompareTabs.svelte`) benutzen WIRKLICH die
// gemeinsame Aufloesung — nicht nur die Hilfsfunktion `resolveTab` (die prueft
// `subscription_tabs_resolve.test.ts`).
//
// Spec: docs/specs/modules/feat_2287_tab_kennungen.md — AC-3, AC-4, AC-6, AC-7, AC-8, AC-12, AC-14
//
// Messweise (wie `compare_retry_reiterwechsel_eingabe_bleibt.test.ts`): das ECHTE
// Instanz-Skript der Hub-Komponente wird gegen gesaete Props ausgewertet
// (`umgebungFuer`), die echten `$effect`-Rumpfe laufen (`effekteVon`), und es wird
// beobachtet, was der Hub TUT: welcher Reiter aktiv wird und was er in die
// Adresszeile schreibt (Trip: `goto`, Vergleich: `history.replaceState` — beide
// Schreibwege werden aufgezeichnet, der Hub darf sich fuer einen entscheiden).
// Das Aufzeichnen ersetzt nur das Browser-API; die Entscheidung trifft der echte Hub.
//
// Harness-Grenzen (bewusst benannt, damit ein richtiges GREEN nicht rot bleibt):
//   - Es laufen NUR `$effect`-Rumpfe. Steht die Adresszeilen-Bereinigung der Alt-Kennung in
//     `onMount`, laeuft sie hier nie → die URL-Tests bleiben rot; sie gehoert in einen `$effect`
//     (oder in die Funktion, die der Effekt ruft) — oder dieser Test wird in /50 angepasst.
//   - Importe der Hubs werden mit `jsAlsTs` (`.js`- und endungslose Spezifizierer → `.ts`) gebunden.
//   - Scheiternde Effekte werden NICHT verschluckt, sondern in den Assert-Meldungen ausgegeben.
//
// Grenze (SSR-only-Kernsuite, kein DOM): dass der Panel-Rahmen den testid
// `…-panel-wertebereiche` wirklich rendert und die Zurueck-Taste keinen Verlauf
// hat, ist nur im Browser messbar → Playwright in `/e2e-verify` (AC-3 History-Laenge,
// AC-12 Panel-testid, AC-14 Handy-Viewport).
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/hub_reiter_gemeinsame_aufloesung.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, effekteVon, type Knoten } from './svelteInstanzPruefstand.ts';
import { createController } from './versandVergleichPruefstand.ts';
import { vollerVergleich } from './goMergeServerPruefstand.ts';
import { subscriptionTabs, resolveTab } from '../subscriptionTabs.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const TRIP_HUB = join(HIER, '..', '..', 'trip-detail', 'TripTabs.svelte');
const VERGLEICH_HUB = join(HIER, '..', '..', 'compare', 'CompareTabs.svelte');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

type Kind = 'trip' | 'vergleich';

/** Adresszeilen-Schreibungen des Hubs (relativ `?tab=x` oder absolut). */
let schreibungen: Array<{ url: string; replace: boolean }> = [];
const globaleAlt = {
	window: (globalThis as Knoten).window,
	history: (globalThis as Knoten).history
};

afterEach(() => {
	(globalThis as Knoten).window = globaleAlt.window;
	(globalThis as Knoten).history = globaleAlt.history;
});

function adresszeileVorbereiten(pfad: string, tab: string | null): void {
	schreibungen = [];
	const href = `http://localhost${pfad}${tab === null ? '' : `?tab=${encodeURIComponent(tab)}`}`;
	(globalThis as Knoten).window = {
		location: { href, search: tab === null ? '' : `?tab=${tab}`, pathname: pfad },
		matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
	};
	(globalThis as Knoten).history = {
		state: null,
		replaceState: (_s: unknown, _t: string, url: string | URL) => {
			schreibungen.push({ url: String(url), replace: true });
		},
		pushState: (_s: unknown, _t: string, url: string | URL) => {
			schreibungen.push({ url: String(url), replace: false });
		}
	};
}

const gotoAufzeichnung = (url: string, opt?: { replaceState?: boolean }) => {
	schreibungen.push({ url: String(url), replace: opt?.replaceState === true });
	return Promise.resolve();
};

/** Oeffnet den ECHTEN Hub mit `?tab=<roh>` und laesst seine Effekte laufen. */
async function hubOeffnen(
	kind: Kind,
	roh: string | null,
	extra: Knoten = {}
): Promise<{ u: Knoten; fehler: string[] }> {
	const pfad = kind === 'trip' ? '/trips/t-1' : '/compare/c-1';
	adresszeileVorbereiten(pfad, roh);
	const initialTab = roh ?? undefined;
	const saat: Knoten =
		kind === 'trip'
			? {
					initialTab,
					goto: gotoAufzeichnung,
					page: { url: new URL(`http://localhost${pfad}${roh === null ? '' : `?tab=${roh}`}`) },
					badges: {},
					...extra
				}
			: {
					initialTab,
					preset: vollerVergleich('c-1'),
					locations: [],
					// im Skript nach der Item-Liste deklariert (Zaehler-Badge) — Saat statt TDZ
					orteCount: 3,
					goto: gotoAufzeichnung,
					page: { url: new URL(`http://localhost${pfad}${roh === null ? '' : `?tab=${roh}`}`) },
					...extra
				};
	const { u, ast, quelle } = await umgebungFuer(kind === 'trip' ? TRIP_HUB : VERGLEICH_HUB, saat, { jsAlsTs: true });
	const fehler: string[] = [];
	for (const e of effekteVon(ast, quelle, u)) {
		try {
			e();
		} catch (err) {
			// nicht verschlucken: ein Effekt, der an einer fehlenden Bindung scheitert, wuerde sonst
			// als „falscher activeTab" erscheinen und die eigentliche Ursache verdecken.
			fehler.push(String(err));
		}
	}
	return { u, fehler };
}

const tabAusUrl = (url: string): string | null => new URL(url, 'http://localhost/x').searchParams.get('tab');

for (const kind of ['trip', 'vergleich'] as Kind[]) {
	const hub = kind === 'trip' ? 'TripTabs' : 'CompareTabs';

	describe(`AC-12 / AC-1 / AC-2 / AC-3: ${hub} benutzt die gemeinsame Aufloesung samt URL-Umschreibung`, () => {
		const altFaelle: Array<[string, string]> = [
			['alerts', 'wertebereiche'],
			['idealwerte', 'wertebereiche'],
			['weather', 'wetter-metriken'],
			['layout', 'wetter-metriken'],
			['briefings', 'versand'],
			['preview', 'vorschau'],
			['overview', 'uebersicht'],
			['stages', kind === 'trip' ? 'etappen' : 'orte'],
			// AC-5: kind-fremde Punkte-Kennung
			[kind === 'trip' ? 'orte' : 'etappen', kind === 'trip' ? 'etappen' : 'orte']
		];

		for (const [alt, neu] of altFaelle) {
			test(`?tab=${alt} → aktiver Reiter '${neu}' und Adresszeile EINMAL per replace auf ?tab=${neu}`, async () => {
				const { u, fehler } = await hubOeffnen(kind, alt);
				assert.equal(
					u.activeTab,
					neu,
					`${hub} oeffnet nicht den Reiter '${neu}' (aktiv: ${String(u.activeTab)}); Effekt-Fehler: ${JSON.stringify(fehler)}`
				);
				assert.equal(
					schreibungen.length,
					1,
					`erwartet genau EINE Adresszeilen-Schreibung, gemessen: ${JSON.stringify(schreibungen)}`
				);
				assert.equal(schreibungen[0].replace, true, 'ein zusaetzlicher Verlaufseintrag waere ein Befund (AC-3)');
				assert.equal(tabAusUrl(schreibungen[0].url), neu);
			});
		}

		test('der Hub bindet die GEMEINSAME Aufloesung und Tabelle (keine eigene Kopie)', async () => {
			const { u } = await hubOeffnen(kind, null);
			const werte = Object.values(u);
			assert.ok(werte.includes(resolveTab), `${hub} bindet shared/subscriptionTabs.resolveTab nicht (eigene Aufloesung?)`);
			assert.ok(werte.includes(subscriptionTabs), `${hub} bindet shared/subscriptionTabs.subscriptionTabs nicht (eigene Tabelle?)`);
		});

		for (const neu of subscriptionTabs(kind).map((t) => t.id)) {
			test(`AC-4: ?tab=${neu} → Reiter '${neu}' ohne jede Adresszeilen-Umschreibung`, async () => {
				const { u } = await hubOeffnen(kind, neu);
				assert.equal(u.activeTab, neu);
				assert.deepEqual(schreibungen, [], 'neue Kennung darf die URL nicht umschreiben');
			});
		}

		test("AC-6: ?tab=foo → Uebersicht und der Parameter 'tab' wird aus der Adresszeile entfernt", async () => {
			const { u } = await hubOeffnen(kind, 'foo');
			assert.equal(u.activeTab, 'uebersicht');
			assert.equal(schreibungen.length, 1, `gemessen: ${JSON.stringify(schreibungen)}`);
			assert.equal(schreibungen[0].replace, true);
			assert.equal(tabAusUrl(schreibungen[0].url), null, 'tab-Parameter muss entfernt sein');
		});

		test('kein ?tab= → Uebersicht, URL bleibt unberuehrt', async () => {
			const { u } = await hubOeffnen(kind, null);
			assert.equal(u.activeTab, 'uebersicht');
			assert.deepEqual(schreibungen, []);
		});
	});

	describe(`AC-14: ${hub} reicht die Reiterleisten-Items (MTabBar, Handy wie Desktop) aus subscriptionTabs('${kind}')`, () => {
		test('Items: gleiche Kennungen, Reihenfolge und Beschriftung wie die gemeinsame Tabelle', async () => {
			const { u } = await hubOeffnen(kind, null);
			const praefix = kind === 'trip' ? 'trip-detail-tab-' : 'compare-detail-tab-';
			// Die Item-Liste fuer MTabBar wird ueber ihre testid-Form gefunden (nicht ueber den
			// Variablennamen), damit eine Umbenennung im Hub den Test nicht blind macht.
			const items = Object.values(u).find(
				(v) =>
					Array.isArray(v) &&
					v.length > 0 &&
					v.every((i) => i && typeof i.testid === 'string' && i.testid.startsWith(praefix))
			) as Array<{ value: string; label: string; testid: string }> | undefined;
			assert.ok(Array.isArray(items), 'Item-Liste der Reiterleiste nicht auswertbar');
			assert.deepEqual(
				items.map((i) => [i.value, i.label]),
				subscriptionTabs(kind).map((t) => [t.id, t.label])
			);
			assert.deepEqual(
				items.map((i) => i.testid),
				subscriptionTabs(kind).map((t) => praefix + t.id),
				'testid wird aus der neuen Kennung abgeleitet (E5)'
			);
		});
	});
}

// ── AC-7 / AC-8: Flush-Guard mit den NEUEN Kennungen ────────────────────────────

/** Echter SaveStatus-Controller mit einer ausstehenden Speicherung; zaehlt Speicherlaeufe. */
function ausstehend(): { ctl: ReturnType<typeof createController>; laeufe: () => number } {
	const ctl = createController('hub-guard');
	let n = 0;
	ctl.schedule(async () => {
		n += 1;
	}, 60_000);
	return { ctl, laeufe: () => n };
}

describe('AC-7: Trip-Hub — Reiterwechsel aus einem selbst speichernden Reiter flusht (neue Kennungen)', () => {
	for (const reiter of ['wertebereiche', 'wetter-metriken', 'versand', 'alarme', 'etappen']) {
		test(`Wechsel aus '${reiter}' mit hasPending → Speicherung laeuft VOR dem Wechsel`, async () => {
			const { ctl, laeufe } = ausstehend();
			const { u } = await hubOeffnen('trip', reiter, { saveController: ctl });
			assert.equal(u.activeTab, reiter, 'Vorbedingung: Hub steht im Reiter ' + reiter);
			schreibungen = [];
			await (u.handleValueChange as (v: string) => Promise<void>)('uebersicht');
			assert.equal(laeufe(), 1, `Flush-Guard greift fuer '${reiter}' nicht (Literal veraltet?)`);
			assert.equal(u.activeTab, 'uebersicht');
			ctl.cancel?.();
		});
	}

	test("Wechsel aus der Uebersicht flusht NICHT (Gegenprobe: Guard ist nicht auf alles offen)", async () => {
		const { ctl, laeufe } = ausstehend();
		const { u } = await hubOeffnen('trip', 'uebersicht', { saveController: ctl });
		await (u.handleValueChange as (v: string) => Promise<void>)('versand');
		assert.equal(laeufe(), 0);
		ctl.cancel?.();
	});

	test('der Wechsel schreibt die NEUE Kennung in die Adresszeile (nie eine alte)', async () => {
		const { u } = await hubOeffnen('trip', 'uebersicht');
		schreibungen = [];
		await (u.handleValueChange as (v: string) => Promise<void>)('wertebereiche');
		assert.equal(schreibungen.length, 1);
		assert.equal(tabAusUrl(schreibungen[0].url), 'wertebereiche');
	});
});

describe('AC-8: Vergleich-Hub — Flush-Guard mit wertebereiche (nicht mehr idealwerte)', () => {
	for (const reiter of ['wertebereiche', 'wetter-metriken', 'versand', 'alarme']) {
		test(`Wechsel aus '${reiter}' mit ausstehender Speicherung → Flush`, async () => {
			const { ctl, laeufe } = ausstehend();
			const { u } = await hubOeffnen('vergleich', reiter, { saveController: ctl });
			assert.equal(u.activeTab, reiter);
			await (u.handleValueChange as (v: string) => Promise<void>)('uebersicht');
			assert.equal(laeufe(), 1, `Flush-Guard greift fuer '${reiter}' nicht`);
			ctl.cancel?.();
		});
	}

	test('der Wechsel schreibt die NEUE Kennung in die Adresszeile', async () => {
		const { u } = await hubOeffnen('vergleich', 'uebersicht');
		schreibungen = [];
		await (u.handleValueChange as (v: string) => Promise<void>)('wertebereiche');
		assert.equal(schreibungen.length, 1);
		assert.equal(tabAusUrl(schreibungen[0].url), 'wertebereiche');
	});
});

// ── Panel-Weichen: kein Alt-Literal mehr im Rahmen ──────────────────────────────

// doc-compliance-test: das Panel-Rendering ist ohne DOM nicht ausfuehrbar; hier wird
// nur belegt, dass die Panel-Weichen die neue Kennung verwenden (die echte
// Messung des gerenderten testid `…-panel-wertebereiche` ist Playwright, AC-12/AC-15).
describe('Panel-Weichen nutzen die neuen Kennungen (doc-compliance-test)', () => {
	test("TripTabs: Panel-Weiche kennt 'wertebereiche'/'versand'/'etappen'/'wetter-metriken'/'uebersicht'/'vorschau' — kein 'alerts'/'briefings'/'stages'/'weather'/'overview'/'preview'", () => {
		const q = readFileSync(TRIP_HUB, 'utf-8');
		for (const neu of ['wertebereiche', 'versand', 'etappen', 'wetter-metriken', 'uebersicht', 'vorschau']) {
			assert.ok(q.includes(`tab.value === '${neu}'`), `Panel-Weiche fuer '${neu}' fehlt`);
		}
		for (const alt of ['alerts', 'briefings', 'stages', 'weather', 'overview', 'preview']) {
			assert.ok(!q.includes(`tab.value === '${alt}'`), `Alt-Kennung '${alt}' in der Panel-Weiche`);
			assert.ok(!q.includes(`activeTab === '${alt}'`), `Alt-Kennung '${alt}' im Flush-Guard`);
		}
	});

	test("CompareTabs: kein 'idealwerte' mehr in activeTab-Vergleichen, handleValueChange und Panel-testids", () => {
		const q = readFileSync(VERGLEICH_HUB, 'utf-8');
		assert.ok(!/idealwerte/.test(q.replace(/\/\/[^\n]*|\/\*[\s\S]*?\*\//g, '').replace(/idealwerteHydrat(ed|ing)/g, "")),
			"Alt-Kennung 'idealwerte' kommt im Hub noch in Code/testid vor (Kommentare und `idealwerteHydrated/-Hydrating` ausgenommen)");
		assert.ok(q.includes("activeTab === 'wertebereiche'"), "Panel-Weiche fuer 'wertebereiche' fehlt");
	});
});
