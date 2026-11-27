<script lang="ts">
	// Issue #2278 (AC-14) — EIN Aktionsblatt fuer Trip und Ortsvergleich (loest MCompareActionSheet ab).
	// Aktionen kommen aus der einen Quelle `subscriptionActions`; Dispatch via onAction(id), danach onClose().

	import Sheet from './Sheet.svelte';
	import { locale, t } from '$lib/i18n';
	import {
		subscriptionActions,
		type SubscriptionLifecycle,
		type SubscriptionSurface
	} from '$lib/components/shared/subscriptionActions.js';
	import type { SubscriptionKind } from '$lib/components/shared/subscriptionTabs.js';
	import KebabBestaetigungPanel from '$lib/components/shared/KebabBestaetigungPanel.svelte';
	import { braucheRueckfrage, rueckfrage } from '$lib/components/shared/kebabBestaetigung.js';

	interface Props {
		open: boolean;
		onClose: () => void;
		kind: SubscriptionKind;
		status: SubscriptionLifecycle;
		onAction: (id: string) => void;
		name?: string;
		surface?: SubscriptionSurface;
	}

	let { open, onClose, kind, status, onAction, name, surface = 'mobile' }: Props = $props();

	// i18n F9: Aktionsnamen entstehen per tr() — `$locale` haelt die Liste reaktiv.
	const actions = $derived.by(() => (void $locale, subscriptionActions(kind, status, surface)));

	// #3442 (AC-9): Archivieren/Löschen fragen im Blatt nach (geteiltes Panel); das Blatt schließt erst
	// nach Bestätigung oder beim Schließen (das die Rückfrage zurücksetzt).
	let frage = $state<string | null>(null);
	const rf = $derived.by(() => (void $locale, frage ? rueckfrage(frage, name ?? '') : null));
	function schliessen(): void {
		frage = null;
		onClose();
	}
</script>

<Sheet {open} onClose={schliessen} snap="half" title={name} eyebrow={$t('aktionen.sheet.eyebrow')}>
	{#if rf}
		<KebabBestaetigungPanel rueckfrage={rf} onBestaetigen={() => { onAction(rf.id); schliessen(); }} onAbbrechen={() => (frage = null)} />
	{:else}
	<div style:display="flex" style:flex-direction="column" style:gap="2px">
		{#each actions as action (action.id)}
			<button
				type="button"
				class="w-full text-left px-4"
				data-testid="subscription-action-{action.id}"
				style:min-height="52px"
				style:background="transparent"
				style:border="none"
				style:cursor="pointer"
				style:font-size="15px"
				style:color={action.danger ? 'var(--g-danger)' : 'var(--g-ink-1)'}
				onclick={() => {
					// Nur im Hub; die Listen fragen mit ihrem eigenen Dialog nach (AC-16).
					if (surface === 'hub' && braucheRueckfrage(action.id)) frage = action.id;
					else {
						onAction(action.id);
						schliessen();
					}
				}}
			>{action.label}</button>
		{/each}
	</div>
	{/if}
</Sheet>
