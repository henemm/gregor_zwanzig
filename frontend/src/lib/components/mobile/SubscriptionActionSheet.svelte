<script lang="ts">
	// Issue #2278 (AC-14) — EIN Aktionsblatt fuer Trip und Ortsvergleich (loest MCompareActionSheet ab).
	// Aktionen kommen aus der einen Quelle `subscriptionActions`; Dispatch via onAction(id), danach onClose().

	import Sheet from './Sheet.svelte';
	import { locale } from '$lib/i18n';
	import {
		subscriptionActions,
		type SubscriptionLifecycle,
		type SubscriptionSurface
	} from '$lib/components/shared/subscriptionActions.js';
	import type { SubscriptionKind } from '$lib/components/shared/subscriptionTabs.js';

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
</script>

<Sheet {open} {onClose} snap="half" title={name} eyebrow="AKTIONEN">
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
					onAction(action.id);
					onClose();
				}}
			>{action.label}</button>
		{/each}
	</div>
</Sheet>
