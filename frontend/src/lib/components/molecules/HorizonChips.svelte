<script lang="ts">
	// Issue #578 — HorizonChips-Molecule.
	// Kanonische Quelle: molecules.jsx::HorizonChips
	//
	// Drei Pills HEUTE / MORGEN / ÜBERMORGEN für die pro-Metrik-Horizont-Wahl
	// (Trip-Kontext). Aktiv = ink-on-paper; inaktiv = ghost.

	import { t, type MessageKey } from '$lib/i18n';

	interface Props {
		value?: Record<string, boolean>;
		onToggle?: (key: string) => void;
		compact?: boolean;
		class?: string;
	}

	let { value = {}, onToggle, compact = false, class: className = '' }: Props = $props();

	const items: { key: string; label: MessageKey }[] = [
		{ key: 'today',     label: 'bausteine.horizont.heute' },
		{ key: 'tomorrow',  label: 'bausteine.horizont.morgen' },
		{ key: 'day_after', label: 'bausteine.horizont.uebermorgen_kurz' },
	];
</script>

<div class={className} style:display="inline-flex" style:gap="4px">
	{#each items as it (it.key)}
		{@const on = !!value[it.key]}
		<button
			onclick={() => onToggle && onToggle(it.key)}
			aria-pressed={on}
			style:padding={compact ? '3px 7px' : '3px 9px'}
			style:font-size={compact ? '9px' : '9.5px'}
			style:font-weight="600"
			style:letter-spacing="0.08em"
			style:font-family="var(--g-font-mono)"
			style:background={on ? 'var(--g-accent-tint)' : 'transparent'}
			style:color={on ? 'var(--g-accent-deep)' : 'var(--g-ink-4)' /* audit:exempt: inactive chip (JSX canonical) */}
			style:border={on ? '1px solid var(--g-accent)' : '1px solid var(--g-rule)'}
			style:border-radius="var(--g-r-pill)"
			style:cursor="pointer"
		>{$t(it.label)}</button>
	{/each}
</div>
