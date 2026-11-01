<script lang="ts">
	// Issue #2278 — kind-neutrales Kebab-Menue (verallgemeinert CompareKebab). Zeigt genau die
	// uebergebenen Aktionen und emittiert onSelect(id); API-Aufrufe/Dialoge liegen beim Aufrufer.

	import { DropdownMenu } from 'bits-ui';
	import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
	import { t } from '$lib/i18n';

	interface Props {
		actions: Array<{ id: string; label: string; danger?: boolean }>;
		onSelect?: (id: string) => void;
		class?: string;
		'data-testid'?: string;
	}

	let { actions, onSelect, class: className = '', 'data-testid': testid }: Props = $props();
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger>
		{#snippet child({ props })}
			<button
				{...props}
				type="button"
				class="kebab-trigger {className}"
				data-testid={testid}
				onclick={(e: MouseEvent) => {
					e.stopPropagation();
				}}
				aria-label={$t('aktionen.weitere')}
				title={$t('aktionen.weitere')}
				style:display="inline-flex"
				style:align-items="center"
				style:justify-content="center"
				style:width="28px"
				style:height="28px"
				style:border-radius="var(--g-r-2)"
				style:border="1px solid var(--g-rule-soft)"
				style:background="transparent"
				style:color="var(--g-ink-2)"
				style:cursor="pointer"
			>
				<EllipsisVerticalIcon size={16} />
			</button>
		{/snippet}
	</DropdownMenu.Trigger>

	<DropdownMenu.Portal>
		<DropdownMenu.Content
			align="end"
			sideOffset={4}
			class="z-50 min-w-[180px] rounded-md border bg-popover shadow-md py-1"
		>
			{#each actions as action (action.id)}
				<DropdownMenu.Item
					data-testid="subscription-action-{action.id}"
					class={'w-full text-left px-3 py-1.5 text-sm cursor-default outline-none hover:bg-muted ' +
						(action.danger ? 'text-destructive' : '')}
					onSelect={() => onSelect?.(action.id)}
					onclick={(e: MouseEvent) => e.stopPropagation()}
				>
					{action.label}
				</DropdownMenu.Item>
			{/each}
		</DropdownMenu.Content>
	</DropdownMenu.Portal>
</DropdownMenu.Root>

<style>
	@media (pointer: coarse) {
		.kebab-trigger {
			position: relative;
		}
		.kebab-trigger::after {
			content: '';
			position: absolute;
			inset: -8px;
		}
	}
</style>
