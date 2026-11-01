<script lang="ts">
	// Issue #2278 (AC-3/AC-4) — EIN Sende-Dialog fuer Liste, Hub und Mobil beider Arten.
	// Sendet NICHT selbst: der Request haengt allein am onConfirm des Aufrufers.
	// Ziel + Sperre kommen aus sendConfirmModel (sendTargetLabel); Morgen/Abend nur beim Trip.

	import ConfirmDialog from './ConfirmDialog.svelte';
	import { sendConfirmModel, type Berichtsart } from './sendConfirmModel.js';
	import type { ConnectionProfile } from '$lib/components/shared/versand-tab/channelConnectionStatus.js';
	import type { SendTargetChannels } from '$lib/components/shared/versand-tab/sendTargetLabel.js';
	import type { SubscriptionKind } from '$lib/components/shared/subscriptionTabs.js';
	import { t } from '$lib/i18n';

	interface Props {
		open: boolean;
		kind: SubscriptionKind;
		profile: ConnectionProfile | null | undefined;
		subscription: SendTargetChannels | null | undefined;
		running?: boolean;
		onConfirm: (berichtsart?: Berichtsart) => void;
		onCancel: () => void;
	}

	let { open, kind, profile, subscription, running = false, onConfirm, onCancel }: Props = $props();

	let auswahl: Berichtsart = $state('morning');
	// AC-4/F010: bei jedem Oeffnen wieder Vorauswahl Morgen (die Komponente bleibt eingehaengt,
	// die letzte Wahl wuerde sonst beim naechsten Oeffnen stehen bleiben). Liest nur `open`.
	$effect(() => {
		if (open) auswahl = 'morning';
	});
	const modell = $derived(sendConfirmModel(kind, profile, subscription, auswahl));
	const gesperrt = $derived(modell.gesperrt || running);
</script>

<ConfirmDialog
	{open}
	title={$t('bausteine.senden_dialog.titel')}
	description={modell.beschreibung}
	confirmLabel={$t('aktionen.senden')}
	disabled={gesperrt}
	data-testid="send-confirm-dialog"
	cancelTestid="send-confirm-cancel"
	confirmTestid="send-confirm-yes"
	onConfirm={() => onConfirm(modell.berichtsart)}
	onCancel={() => onCancel()}
	onOpenChange={(o) => {
		if (!o) onCancel();
	}}
>
	{#if modell.berichtsartWahl}
		<div class="flex gap-4" role="radiogroup" aria-label={$t('bausteine.senden_dialog.berichtsart')}>
			{#each modell.berichtsartWahl as w (w.value)}
				<label class="inline-flex items-center gap-2 min-h-[44px] text-sm cursor-pointer">
					<input
						type="radio"
						name="berichtsart"
						value={w.value}
						data-testid="send-confirm-berichtsart-{w.value}"
						checked={auswahl === w.value}
						onchange={() => (auswahl = w.value)}
					/>
					{w.label}
				</label>
			{/each}
		</div>
	{/if}
</ConfirmDialog>
