<script lang="ts">
	import { api } from '$lib/api.js';
	import { Btn } from '$lib/components/atoms';
	import EditReportConfigSection from '$lib/components/edit/EditReportConfigSection.svelte';
	import type { Trip, ReportConfig } from '$lib/types';

	interface Props {
		trip: Trip;
		onTripUpdate?: (updated: Trip) => void;
	}
	let { trip, onTripUpdate }: Props = $props();

	let reportConfig = $state<ReportConfig>(
		trip.report_config ? JSON.parse(JSON.stringify(trip.report_config)) : {}
	);
	let saving = $state(false);
	let statusMsg = $state('');

	function makeSaveHandler() {
		return async function doSave() {
			saving = true;
			statusMsg = '';
			try {
				await api.put<Trip>(`/api/trips/${trip.id}`, { ...trip, report_config: reportConfig });
				statusMsg = 'Gespeichert.';
				onTripUpdate?.({ ...trip, report_config: reportConfig });
			} catch (e: unknown) {
				const err = e as { error?: string; detail?: string };
				statusMsg = err.detail ?? err.error ?? 'Fehler beim Speichern';
			} finally {
				saving = false;
			}
		};
	}
</script>

<div class="briefing-schedule-tab" style="padding: 32px 40px 60px; max-width: 720px;">
	<EditReportConfigSection bind:reportConfig mode="edit" />

	<div style="margin-top: 24px; display: flex; align-items: center; gap: 12px;">
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
</div>
