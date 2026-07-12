<script lang="ts">
	import { api } from '$lib/api.js';
	import { Btn } from '$lib/components/atoms';
	import VersandTab from '$lib/components/shared/VersandTab.svelte';
	import type { Trip, ReportConfig } from '$lib/types';
	import type { ChannelConfig } from './briefingChannelGating.ts';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

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

	// Issue #617: Wetter-Kanäle aus display_config.channels durchreichen.
	// Issue #736: Mutable state (nicht const) damit Auto-Save-Aktualisierungen sichtbar werden.
	// Cast über unknown wie in WeatherMetricsTab (#587). Default: Email+Telegram aktiv, SMS aus.
	let weatherChannels = $state<ChannelConfig>(
		((trip.display_config as unknown as Record<string, unknown>)?.channels as ChannelConfig | undefined)
		?? { email: true, telegram: true, sms: false }
	);

	// Legacy save state (only used when saveController is not present)
	let saving = $state(false);
	let statusMsg = $state('');

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
	let _prevConfigJson = JSON.stringify(reportConfig);
	$effect(() => {
		const currentJson = JSON.stringify(reportConfig);
		if (currentJson === _prevConfigJson) return;
		_prevConfigJson = currentJson;
		if (saveController) {
			// Fire-and-forget: doSave starts the fetch immediately.
			// beforeNavigate + flush handles SvelteKit client-side navigations (AC-5 belt).
			void saveController.doSave(buildSaveFn());
		}
	});

	// Issue #736: Auto-Save bei Kanal-Toggle — display_config.channels sofort persistieren.
	async function handleChannelChange(channel: 'email' | 'telegram' | 'sms', value: boolean) {
		weatherChannels = { ...weatherChannels, [channel]: value };
		const updatedDisplayConfig = {
			...(trip.display_config as unknown as Record<string, unknown> ?? {}),
			channels: { ...weatherChannels },
		};
		if (saveController) {
			saveController.schedule(async () => {
				await api.put(`/api/trips/${trip.id}`, { display_config: updatedDisplayConfig });
				onTripUpdate?.({ ...trip, display_config: updatedDisplayConfig as Trip['display_config'] });
			});
		} else {
			try {
				await api.put(`/api/trips/${trip.id}`, { display_config: updatedDisplayConfig });
				onTripUpdate?.({ ...trip, display_config: updatedDisplayConfig as Trip['display_config'] });
			} catch (e: unknown) {
				console.error(e);
			}
		}
	}
</script>

<div class="briefing-schedule-tab">
	<!-- Issue #1232 Scheibe 1: VersandTab (context="route") ersetzt EditReportConfigSection
	     für Kanäle/Zeitplan/Laufzeit/Alert-Zustellung. Mail-Inhalt bleibt unangetastet im
	     Inhalt-Tab (WeatherMetricsTab, Issue #736 AC-10-Korrektur). -->
	<VersandTab
		context="route"
		{trip}
		{onTripUpdate}
		{saveController}
		bind:reportConfig
		onChannelChange={handleChannelChange}
		{onJump}
	/>

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
