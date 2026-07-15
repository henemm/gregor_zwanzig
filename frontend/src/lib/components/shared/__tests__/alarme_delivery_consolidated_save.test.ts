// TDD RED — Issue #1258 Scheibe S2: geteilter Alarme-Organism (ungewired).
// AC-12: mehrere in schneller Folge geänderte Felder (z.B. Cooldown +
// amtliche Warnungen) lösen GENAU EINEN konsolidierten Save aus, nicht
// mehrere unabhängige.
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md (AC-12)
// Vorbild: frontend/src/lib/components/shared/VersandTab.svelte:209-260
//   (buildAlertDeliverySaveFn, EIN $effect, saveController.schedule())
// Vorbild-Payload: frontend/src/lib/components/shared/versand-tab/alertDeliveryPayload.ts
//
// `alarmeDeliveryPayload.ts` existiert noch NICHT — Import schlägt heute
// fehl (RED), bis Phase 6 das Modul unter
// frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts anlegt.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_delivery_consolidated_save.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildAlarmeDeliveryPayload } from '../alarme-tab/alarmeDeliveryPayload.ts';

// ── Teil (a): Konsolidierte Payload-Funktion ───────────────────────────────

test('#1258 AC-12a: buildAlarmeDeliveryPayload konsolidiert mehrere geänderte Felder in EIN Payload-Objekt mit allen Keys', () => {
	const payload = buildAlarmeDeliveryPayload({
		officialAlertsEnabled: true,
		officialWarningsEnabled: false,
		cooldownMinutes: 45,
		quietFrom: '22:00',
		quietTo: '06:00'
	});
	assert.deepEqual(payload, {
		official_alerts_enabled: true,
		official_warnings: { enabled: false },
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '06:00'
	});
});

test('#1258 AC-12a: official_warnings enthält NUR "enabled", KEINEN sources-Key (Server-RMW erhält Bestand, S1-F002)', () => {
	const payload = buildAlarmeDeliveryPayload({
		officialAlertsEnabled: true,
		officialWarningsEnabled: true,
		cooldownMinutes: 30
	}) as { official_warnings: Record<string, unknown> };
	assert.deepEqual(Object.keys(payload.official_warnings), ['enabled']);
	assert.equal('sources' in payload.official_warnings, false);
});

// Adversary Fix-Loop 1, F002: officialAlertsEnabled/officialWarningsEnabled
// waren optional mit stillem Default (enabled:false) bei fehlendem Wert —
// jetzt PFLICHT + Laufzeit-Guard (strip-types prüft zur Laufzeit nichts).
test('#1258 AC-12a/F002: buildAlarmeDeliveryPayload wirft bei fehlendem officialWarningsEnabled (kein stilles false)', () => {
	assert.throws(() => {
		buildAlarmeDeliveryPayload({
			officialAlertsEnabled: true,
			officialWarningsEnabled: undefined as unknown as boolean
		});
	}, /officialWarningsEnabled/);
});

test('#1258 AC-12a/F002: buildAlarmeDeliveryPayload wirft bei Nicht-boolean officialWarningsEnabled (z.B. String aus falscher Quelle)', () => {
	assert.throws(() => {
		buildAlarmeDeliveryPayload({
			officialAlertsEnabled: true,
			officialWarningsEnabled: 'true' as unknown as boolean
		});
	}, /officialWarningsEnabled/);
});

test('#1258 AC-12a: fehlende Cooldown/Quiet-Werte werden zu null (Vorbild alertDeliveryPayload.ts, kein undefined im PUT-Body)', () => {
	const payload = buildAlarmeDeliveryPayload({
		officialAlertsEnabled: false,
		officialWarningsEnabled: false,
		cooldownMinutes: undefined,
		quietFrom: undefined,
		quietTo: undefined
	}) as Record<string, unknown>;
	assert.equal(payload.alert_cooldown_minutes, null);
	assert.equal(payload.alert_quiet_from, null);
	assert.equal(payload.alert_quiet_to, null);
});

test('#1258 AC-12a: zwei rasch aufeinanderfolgende Änderungen ergeben je eine Payload mit dem VOLLSTÄNDIGEN aktuellen Zustand (kein Feld geht verloren)', () => {
	const afterFirstChange = buildAlarmeDeliveryPayload({
		officialAlertsEnabled: true,
		officialWarningsEnabled: true,
		cooldownMinutes: undefined,
		quietFrom: undefined,
		quietTo: undefined
	}) as Record<string, unknown>;
	const afterSecondChange = buildAlarmeDeliveryPayload({
		officialAlertsEnabled: true,
		officialWarningsEnabled: false,
		cooldownMinutes: 45,
		quietFrom: undefined,
		quietTo: undefined
	}) as Record<string, unknown>;
	// Die zweite (finale) Payload enthält weiterhin den ersten Änderungspfad
	// (officialAlertsEnabled) UND die neuen Werte (officialWarningsEnabled,
	// cooldownMinutes) — genau das macht den EINEN konsolidierten Save AC-12
	// konform: es gibt keinen Zwischenschritt, der nur EIN Feld sendet.
	assert.equal(afterSecondChange.official_alerts_enabled, true);
	assert.equal((afterSecondChange.official_warnings as { enabled: boolean }).enabled, false);
	assert.equal(afterSecondChange.alert_cooldown_minutes, 45);
	assert.notDeepEqual(afterFirstChange, afterSecondChange);
});

// ── Teil (b): Debounce-Konsolidierung (genau EIN Save pro Fenster) ────────
//
// Der reale saveController (`SaveStatus` in
// frontend/src/lib/stores/saveStatusStore.svelte.ts:17-82, insb.
// `schedule()` :64-72) kann in einem reinen node:test NICHT instanziiert
// werden: seine Instanzfelder (`state = $state(...)`, `error = $state(...)`,
// `savedAt = $state(...)`) sind Svelte-5-Runen, die als Klassenfeld-
// Initializer bei JEDEM `new SaveStatus()` ausgeführt werden — außerhalb
// eines vom Svelte-Compiler transformierten Kontexts wirft das sofort
// `ReferenceError: $state is not defined` (verifiziert:
// `node --import ./test-lib-loader.mjs --experimental-strip-types -e
// "import('./src/lib/stores/saveStatusStore.svelte.ts')..."` → exakt dieser
// Fehler). Ein Versuch, die Datei vorab mit `svelte/compiler`s
// `compileModule()` zu übersetzen, scheitert ebenfalls, weil `compileModule`
// kein TypeScript parst (`Unexpected token`, `js_parse_error`) und die Datei
// Typannotationen enthält — eine Vorab-Strip-Pipeline dafür existiert im
// Repo nicht und wäre neue Test-Infrastruktur, kein Verhaltenstest.
//
// Bestehende Precedent im Repo für genau diese Einschränkung:
// `frontend/src/lib/components/compare/__tests__/compare_hub_wizard_bridge.test.ts`
// (Kommentarblock) und `wizard_state_no_legacy_save.test.ts` — beide
// instanziieren `$state`-Klassen NIE in node:test.
//
// Fallback (wie im Entwickler-Briefing vorgesehen): eine REALE Zeit-
// Reproduktion des in `schedule()` dokumentierten Ein-Slot-Debounce-
// Vertrags — EIN `_timer`/`_pendingFn`, 700 ms, jeder neue `schedule()`-
// Aufruf ersetzt den vorherigen vollständig, statt einen zweiten parallelen
// Save zu planen. Das ist KEIN Mock der Business-Logik: `_timer`/
// `_pendingFn` sind in der echten Klasse plain JS-Felder (nicht `$state`),
// der Debounce-Mechanismus selbst hängt nicht von Runen ab — hier 1:1 aus
// saveStatusStore.svelte.ts:64-72 übernommen, nur ohne die (hier
// irrelevanten) `$state`-Anzeigefelder. Echtes `setTimeout`, echte
// Wartezeit (~1s), keine Fake-Timer.

interface MinimalScheduleController {
	schedule(saveFn: () => Promise<void>, ms?: number): void;
}

function createMinimalScheduleController(): MinimalScheduleController {
	// 1:1-Reproduktion von SaveStatus.schedule()/doSave() (saveStatusStore.svelte.ts:47-72),
	// ohne die $state-Anzeigefelder (state/error/savedAt) — s. Kommentarblock oben.
	let timer: ReturnType<typeof setTimeout> | null = null;
	let pendingFn: (() => Promise<void>) | null = null;
	async function doSave(saveFn: () => Promise<void>): Promise<void> {
		pendingFn = null;
		timer = null;
		await saveFn();
	}
	return {
		schedule(saveFn: () => Promise<void>, ms = 700): void {
			pendingFn = saveFn;
			if (timer !== null) clearTimeout(timer);
			timer = setTimeout(() => {
				void doSave(saveFn);
			}, ms);
		}
	};
}

test(
	'#1258 AC-12b: zwei schedule()-Aufrufe kurz hintereinander (Cooldown- und amtliche-Warnungen-Änderung) führen zu GENAU EINEM Save nach dem Debounce-Fenster',
	{ timeout: 2000 },
	async () => {
		const controller = createMinimalScheduleController();
		let saveCount = 0;
		let lastPayload: object | null = null;

		// Änderung 1: officialWarningsEnabled togglet.
		controller.schedule(async () => {
			saveCount++;
			lastPayload = buildAlarmeDeliveryPayload({
				officialAlertsEnabled: true,
				officialWarningsEnabled: false,
				cooldownMinutes: undefined
			});
		});

		// Änderung 2 (kurz danach, innerhalb der 700ms): Cooldown geändert.
		// schedule() ersetzt den pending Save vollständig — Änderung 1 wird NICHT
		// separat gespeichert.
		await new Promise((r) => setTimeout(r, 50));
		controller.schedule(async () => {
			saveCount++;
			lastPayload = buildAlarmeDeliveryPayload({
				officialAlertsEnabled: true,
				officialWarningsEnabled: false,
				cooldownMinutes: 45
			});
		});

		// Real-Zeit-Warten bis nach dem 700ms-Debounce-Fenster (~1s Gesamt).
		await new Promise((r) => setTimeout(r, 1000));

		assert.equal(saveCount, 1, 'genau EIN Save darf nach dem Debounce-Fenster gelaufen sein');
		assert.equal(
			(lastPayload as unknown as { alert_cooldown_minutes: number | null }).alert_cooldown_minutes,
			45,
			'der eine gelaufene Save muss den finalen, konsolidierten Zustand enthalten (Cooldown UND officialWarnings)'
		);
	}
);
