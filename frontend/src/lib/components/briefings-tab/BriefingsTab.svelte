<script lang="ts">
	import { api } from '$lib/api';
	import type { Trip, ReportConfig } from '$lib/types';
	import EditReportConfigSection from '$lib/components/edit/EditReportConfigSection.svelte';

	let { trip }: { trip: Trip } = $props();

	let reportConfig = $state<ReportConfig>(
		JSON.parse(JSON.stringify(trip.report_config ?? {}))
	);
	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError = $state<string | null>(null);

	async function save() {
		saving = true;
		saveSuccess = false;
		saveError = null;
		try {
			await api.put(`/api/trips/${trip.id}`, { report_config: reportConfig });
			saveSuccess = true;
			setTimeout(() => {
				saveSuccess = false;
			}, 3000);
		} catch (e: unknown) {
			const msg =
				e && typeof e === 'object' && 'error' in e
					? String((e as { error: unknown }).error)
					: e instanceof Error
						? e.message
						: 'Speichern fehlgeschlagen';
			saveError = msg;
		} finally {
			saving = false;
		}
	}
</script>

<div class="briefings-tab" data-testid="briefings-tab">
	<EditReportConfigSection bind:reportConfig mode="edit" />

	<div class="actions">
		<button
			type="button"
			class="btn-primary"
			data-testid="briefings-tab-save"
			disabled={saving}
			onclick={save}
		>{saving ? 'Speichere…' : 'Speichern'}</button>

		{#if saveSuccess}
			<span class="success-msg" data-testid="briefings-tab-save-success">Gespeichert.</span>
		{/if}
		{#if saveError}
			<span class="error-msg" data-testid="briefings-tab-save-error">{saveError}</span>
		{/if}
	</div>
</div>

<style>
	.briefings-tab {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.btn-primary {
		min-height: 40px;
		padding: 0.5rem 1rem;
		border-radius: 0.375rem;
		border: 1px solid var(--g-ink);
		background: var(--g-ink);
		color: #fff;
		font-size: 0.875rem;
		cursor: pointer;
	}

	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.success-msg {
		color: var(--g-good, #16a34a);
		font-size: 0.875rem;
	}

	.error-msg {
		color: var(--g-danger, #dc2626);
		font-size: 0.875rem;
	}
</style>
