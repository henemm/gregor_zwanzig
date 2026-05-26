<script lang="ts" module>
	export interface MTabItem {
		id: string;
		label: string;
		badge?: string | number | null;
		accent?: boolean;
	}
</script>

<script lang="ts">
	// Issue #373 — MTab (kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Horizontale, optional scrollbare Tableiste. role="tablist", aktiver Tab
	// mit Accent-Unterstrich. Token-basiert, Touch-Hoehe >= 44px.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md
	interface Props {
		items: MTabItem[];
		active?: string;
		onChange?: (id: string) => void;
		scrollable?: boolean;
	}

	let { items, active, onChange, scrollable = true }: Props = $props();
</script>

<div
	role="tablist"
	style:display="flex"
	style:gap="0"
	style:overflow-x={scrollable ? 'auto' : 'hidden'}
	style:border-bottom="1px solid var(--g-rule-soft)"
	style:-webkit-overflow-scrolling="touch"
	style:scrollbar-width="none"
>
	{#each items as it (it.id)}
		{@const isActive = active === it.id}
		<button
			type="button"
			role="tab"
			aria-selected={isActive}
			onclick={() => onChange?.(it.id)}
			style:display="inline-flex"
			style:align-items="center"
			style:gap="6px"
			style:padding="14px 14px"
			style:min-height="44px"
			style:flex-shrink="0"
			style:background="transparent"
			style:border="none"
			style:cursor="pointer"
			style:font-size="14px"
			style:font-weight={isActive ? '600' : '500'}
			style:color={isActive ? 'var(--g-ink)' : 'var(--g-ink-3)'}
			style:border-bottom={isActive ? '2px solid var(--g-accent)' : '2px solid transparent'}
			style:margin-bottom="-1px"
			style:white-space="nowrap"
			style:font-family="var(--g-font-sans)"
		>
			{it.label}
			{#if it.badge != null}
				<span
					class="mono"
					style:font-size="10px"
					style:padding="1px 6px"
					style:border-radius="3px"
					style:background={it.accent ? 'var(--g-accent)' : 'var(--g-paper-deep)'}
					style:color={it.accent ? '#fff' : 'var(--g-ink-3)'}
				>{it.badge}</span>
			{/if}
		</button>
	{/each}
</div>
