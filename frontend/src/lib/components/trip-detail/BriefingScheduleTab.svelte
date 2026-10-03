<script lang="ts">
	import { api } from '$lib/api.js';
	import { Btn } from '$lib/components/atoms';
	import VersandTab from '$lib/components/shared/VersandTab.svelte';
	import type { Trip, ReportConfig } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	// Issue #1269 (c): ohne Nutzergeste kein Schreibzugriff — derselbe Gate wie
	// im Inhalt-Tab (weatherSaveGate.ts), kein Sonderweg.
	import { weatherSaveGate } from './weatherSaveGate.ts';
	import { baueTripSpeicherung } from '$lib/components/shared/tripSpeicherung';
	import { pickEigenfelder, VERSAND_REPORT_KEYS } from '$lib/components/shared/pickEigenfelder';
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
	// Issue #1433: kein Dauer-`keepalive` mehr — der PUT laeuft wie bei den anderen
	// Reitern ueber die Warteschlange mit If-Match; `init` (keepalive) kommt nur
	// vom echten Unload-Flush des Controllers. Teilfeld: nur Versand-Schluessel
	// (Spec §2.3), `trip` lokal aus der Server-Antwort.
	function buildSaveFn() {
		const configSnapshot = { ...reportConfig };
		return baueTripSpeicherung<Trip>(
			api,
			trip.id,
			pickEigenfelder({ report_config: configSnapshot }, { report: VERSAND_REPORT_KEYS }),
			(updated) => onTripUpdate?.(updated),
			'versand'
		);
	}

	function makeSaveHandler() {
		return async function doSave() {
			saving = true;
			statusMsg = '';
			try {
				const configSnapshot = { ...reportConfig };
				const updated = await api.put<Trip>(
					`/api/trips/${trip.id}`,
					pickEigenfelder({ report_config: configSnapshot }, { report: VERSAND_REPORT_KEYS })
				);
				statusMsg = 'Gespeichert.';
				onTripUpdate?.(updated);
			} catch (e: unknown) {
				const err = e as { error?: string; detail?: string };
				statusMsg = err.detail ?? err.error ?? 'Fehler beim Speichern';
			} finally {
				saving = false;
			}
		};
	}

	// Issue #758: whenever reportConfig changes (via $effect), auto-save.
	// Issue #1433: der Speichervorgang laeuft ueber `saveController.schedule` (Debounce);
	// beim Verlassen der Seite flusht der Controller ihn mit `{ keepalive: true }` (#1376),
	// bei harter Navigation (page.goto) also ohne Verlust — kein Dauer-keepalive mehr.
	// Issue #1269 (a)+(c): VersandTab normalisiert reportConfig beim Mounten
	// (toHHMMSS, Default-Materialisierung) und schreibt es zurueck. Fix-Loop 1
	// (Adversary F001): Anzeige aus dem INHALTS-DIFF treiben, Schreiben aus
	// der GESTE — dieselbe Regel wie WeatherMetricsTab.svelte scheduleAutoSave()
	// (Zeile ~490-497):
	//   changed=false (reine Mount-Kanonisierung)     -> nichts (fixt (a))
	//   changed=true  UND Gate "save" (echte Geste)   -> doSave() (fixt (c))
	//   changed=true  ABER Gate "skip" (keine Geste)  -> setUnsavedInput() — ehrliche
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
					// Issue #1433: ueber den Controller (Debounce, Flush beim Verlassen,
					// Konflikt-Liste) — wie die anderen Reiter.
					saveController.schedule(buildSaveFn());
				} else {
					saveController.setUnsavedInput();
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
	<!-- Issue #1232 Scheibe 1: VersandTab (context="route") ersetzt die frühere Report-Config-Section (#2277 S5 entfernt)
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
