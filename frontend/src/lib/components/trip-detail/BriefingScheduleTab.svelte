<script lang="ts">
	import { api } from '$lib/api.js';
	import { Btn } from '$lib/components/atoms';
	import VersandTab from '$lib/components/shared/VersandTab.svelte';
	import type { Trip, ReportConfig } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	// Issue #1269 (c): ohne Nutzergeste kein Schreibzugriff — derselbe Gate wie
	// im Inhalt-Tab (weatherSaveGate.ts), kein Sonderweg.
	import { weatherSaveGate } from './weatherSaveGate.ts';
	// Issue #1269 Fix-Loop 1 (Adversary F001): Anzeige aus dem Inhalts-Diff
	// treiben (nicht nur aus dem Gate) — identisch zu WeatherMetricsTab.svelte
	// und CompareEditor.svelte (dirty-$derived), sonst AC-7-Asymmetrie.
	import { reportConfigChangedByUser } from '$lib/components/shared/reportConfigDirty';

	interface Props {
		trip: Trip;
		onTripUpdate?: (updated: Trip) => void;
		/** Issue #758: SaveStatus controller — wenn gesetzt, entfällt der Briefing-Zeitplan-Button. */
		saveController?: SaveStatus;
		/** Issue #1232: Tab-Wechsel (Versand-Tab → "Etappen öffnen →"). */
		onJump?: (tab: string) => void;
	}
	let { trip, onTripUpdate, saveController, onJump }: Props = $props();

	let reportConfig = $state<ReportConfig>(
		trip.report_config ? JSON.parse(JSON.stringify(trip.report_config)) : {}
	);

	// Legacy save state (only used when saveController is not present)
	let saving = $state(false);
	let statusMsg = $state('');

	// Issue #1269 (c): kein Katalog-Ladevorgang in diesem Tab — report_config
	// liegt synchron aus dem Trip vor (kein SSR-Wartezustand wie im Inhalt-Tab).
	const catalogLoaded = true;
	let userTouched = $state(false);

	// Issue #758: build save function for the current reportConfig state.
	// F002: keepalive:true stellt sicher, dass der Fetch auch bei harter Browser-Navigation
	// (page.goto) den Server erreicht — der Browser bricht einen normalen Fetch beim
	// Seitenabbau ab, keepalive-Requests werden zu Ende gesendet.
	function buildSaveFn() {
		const configSnapshot = { ...reportConfig };
		return async function doSaveReportConfig() {
			await api.put<Trip>(`/api/trips/${trip.id}`, { report_config: configSnapshot }, { keepalive: true });
			onTripUpdate?.({ ...trip, report_config: configSnapshot });
		};
	}

	function makeSaveHandler() {
		return async function doSave() {
			saving = true;
			statusMsg = '';
			try {
				const configSnapshot = { ...reportConfig };
				await api.put<Trip>(`/api/trips/${trip.id}`, { report_config: configSnapshot });
				statusMsg = 'Gespeichert.';
				onTripUpdate?.({ ...trip, report_config: configSnapshot });
			} catch (e: unknown) {
				const err = e as { error?: string; detail?: string };
				statusMsg = err.detail ?? err.error ?? 'Fehler beim Speichern';
			} finally {
				saving = false;
			}
		};
	}

	// Issue #758: whenever reportConfig changes (via $effect), auto-save.
	// AC-5: save fires synchronously (no debounce) so the fetch reaches the server
	// even when the user navigates away immediately (hard navigation via page.goto).
	// The server persists the data regardless of whether the client awaits the response.
	// Issue #1269 (a)+(c): VersandTab normalisiert reportConfig beim Mounten
	// (toHHMMSS, Default-Materialisierung) und schreibt es zurueck. Fix-Loop 1
	// (Adversary F001): Anzeige aus dem INHALTS-DIFF treiben, Schreiben aus
	// der GESTE — dieselbe Regel wie WeatherMetricsTab.svelte scheduleAutoSave()
	// (Zeile ~490-497):
	//   changed=false (reine Mount-Kanonisierung)     -> nichts (fixt (a))
	//   changed=true  UND Gate "save" (echte Geste)   -> doSave() (fixt (c))
	//   changed=true  ABER Gate "skip" (keine Geste)  -> setDirty() — ehrliche
	//     "Nicht gespeichert"-Anzeige statt stillem Verlust (AC-6/AC-7), falls
	//     die Gesten-Erfassung eine Aenderung mal nicht einfaengt (F003/F004-Klasse).
	let _lastReportConfig: ReportConfig = reportConfig;
	$effect(() => {
		const cur = reportConfig;
		if (cur !== _lastReportConfig) {
			const changed = reportConfigChangedByUser(_lastReportConfig, cur);
			_lastReportConfig = cur;
			if (changed && saveController) {
				if (weatherSaveGate({ catalogLoaded, userTouched }) === 'save') {
					// Fire-and-forget: doSave starts the fetch immediately.
					// beforeNavigate + flush handles SvelteKit client-side navigations (AC-5 belt).
					void saveController.doSave(buildSaveFn());
				} else {
					saveController.setDirty();
				}
			}
		}
	});

	// Issue #1269 (c) — Vorbild WeatherMetricsTab.svelte (#1234 Fix-Loop 2):
	// Capture-Phase-Listener auf dem umschliessenden Container. VersandTab
	// selbst darf laut Teilungs-Invariante nicht kanalspezifisch fuer diesen
	// Zweck geaendert werden — die Geste-Erfassung sitzt hier im Parent.
	const REPORT_CONFIG_INTERACTIVE_SELECTOR =
		'input, button, select, textarea, label, [role="checkbox"], [role="radio"], [role="switch"]';
	function onReportConfigTouchGesture(e: Event) {
		if ((e.target as HTMLElement | null)?.closest?.(REPORT_CONFIG_INTERACTIVE_SELECTOR)) {
			userTouched = true;
		}
	}
	function onReportConfigValueChange() {
		userTouched = true;
	}
</script>

<div class="briefing-schedule-tab">
	<!-- Issue #1232 Scheibe 1: VersandTab (context="route") ersetzt EditReportConfigSection
	     für Kanäle/Zeitplan/Laufzeit/Alert-Zustellung. Mail-Inhalt bleibt unangetastet im
	     Inhalt-Tab (WeatherMetricsTab, Issue #736 AC-10-Korrektur).
	     Issue #1269 (c): Capture-Phase-Listener (s. Script oben) — VersandTab
	     normalisiert reportConfig beim Mounten, das darf nicht als Nutzergeste
	     zaehlen; eine echte Interaktion MUSS aber weiterhin gaten. -->
	<div
		class="report-config-touch-scope"
		onpointerdowncapture={onReportConfigTouchGesture}
		onkeydowncapture={onReportConfigTouchGesture}
		onchangecapture={onReportConfigValueChange}
		oninputcapture={onReportConfigValueChange}
	>
		<VersandTab
			context="route"
			{trip}
			{onTripUpdate}
			{saveController}
			bind:reportConfig
			{onJump}
		/>
	</div>

	<!-- Issue #758: Expliziter Speichern-Button nur ohne saveController (Backward-Compat). -->
	{#if !saveController}
		<div style="margin-top: 24px; padding: 0 40px; display: flex; align-items: center; gap: 12px;">
			<Btn
				variant="primary"
				data-testid="briefings-save"
				disabled={saving}
				onclick={makeSaveHandler()}
			>
				{saving ? 'Speichern …' : 'Briefing-Zeitplan speichern'}
			</Btn>
			{#if statusMsg}
				<span style="font-size: 13px; color: var(--g-ink-muted);">{statusMsg}</span>
			{/if}
		</div>
	{/if}
</div>
