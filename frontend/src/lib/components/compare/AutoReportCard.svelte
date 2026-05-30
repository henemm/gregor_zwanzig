<script lang="ts">
	// Issue #459 — Anzeige-Kachel pro Auto-Briefing (ComparePreset).
	//
	// Spec: docs/specs/modules/issue_459_auto_briefings_sidepanel.md (§6)
	// Vorher (#301): subscription-basiert. Jetzt: ComparePreset + manueller
	// Send-Button (POST /api/compare/presets/{id}/send).

	import type { ComparePreset } from '$lib/types.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import SendIcon from '@lucide/svelte/icons/send';
	import { api } from '$lib/api.js';
	import { presetScheduleLabel, formatLastSent } from './subscriptionHelpers.js';

	interface Props {
		preset: ComparePreset;
	}

	let { preset }: Props = $props();
	let sending = $state(false);
	let sendError: string | null = $state(null);

	async function handleSend() {
		if (sending) return;
		sending = true;
		sendError = null;
		try {
			await api.post(`/api/compare/presets/${preset.id}/send`, {});
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			sendError = body?.detail ?? body?.error ?? 'Versand fehlgeschlagen';
		} finally {
			sending = false;
		}
	}
</script>

<Card.Root data-testid="auto-report-card-{preset.id}">
	<Card.Content class="card-body">
		<div class="card-header">
			<span class="card-name" data-testid="card-name-{preset.id}">{preset.name}</span>
			<Btn
				size="icon-sm"
				variant="ghost"
				disabled={sending}
				onclick={handleSend}
				data-testid="auto-report-send-{preset.id}"
				aria-label="Jetzt senden"
			>
				<SendIcon size={14} />
			</Btn>
		</div>
		<div class="card-schedule">
			<span class="mono">{presetScheduleLabel(preset)}</span>
		</div>
		<div class="card-last-sent">
			{formatLastSent(preset.letzter_versand)}
		</div>
		{#if preset.top_ort_letzter_versand}
			<div class="card-top-ort" data-testid="top-ort-{preset.id}">
				Top-Ort: {preset.top_ort_letzter_versand}
			</div>
		{/if}
		{#if sendError}
			<p class="send-error" data-testid="auto-report-send-error-{preset.id}">{sendError}</p>
		{/if}
	</Card.Content>
</Card.Root>

<style>
	.card-body {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}
	.card-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-s-2);
		min-width: 0;
	}
	.card-name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex: 1;
		min-width: 0;
	}
	.card-schedule {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
	}
	.mono {
		font-family: var(--g-font-data);
	}
	.card-last-sent {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
	}
	.card-top-ort {
		font-size: var(--g-text-xs);
		color: var(--g-ink-3);
	}
	.send-error {
		font-size: var(--g-text-xs);
		color: var(--g-danger);
	}
</style>
