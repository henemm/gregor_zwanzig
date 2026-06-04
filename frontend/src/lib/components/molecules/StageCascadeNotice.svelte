<script lang="ts">
	// Issue #578 — StageCascadeNotice-Molecule.
	// Kanonische Quelle: molecules.jsx::StageCascadeNotice
	//
	// Inline, nicht-blockierender Vorschlag beim Verschieben der ersten Etappe:
	// „Folge-Etappen mitverschieben?" Zwei Zustände (Vorschlag / erledigt).

	import { Dot, Btn } from '$lib/components/atoms';

	interface Props {
		days: number;
		count: number;
		done?: boolean;
		onApply?: () => void;
		onDismiss?: () => void;
		class?: string;
	}

	let { days, count, done = false, onApply, onDismiss, class: className = '' }: Props = $props();

	const sign = $derived(days > 0 ? '+' : '−');
	const abs = $derived(Math.abs(days));
	const dayWord = $derived(abs === 1 ? 'Tag' : 'Tage');
</script>

{#if done}
	<div
		class={className}
		style:margin-top="16px"
		style:display="flex"
		style:align-items="center"
		style:gap="12px"
		style:flex-wrap="wrap"
		style:padding="12px 16px"
		style:background="rgba(61,107,58,0.10)"
		style:border-left="3px solid var(--g-good)"
		style:border-radius="var(--g-r-2)"
		style:font-size="13px"
		style:color="var(--g-ink-2)"
	>
		<Dot tone="good" />
		<span><strong style:color="var(--g-ink)">{count} Folge-Etappen verschoben</strong> · alle Daten um {sign}{abs} {dayWord} angepasst.</span>
		<button
			onclick={onDismiss}
			style:margin-left="auto"
			style:background="none"
			style:border="none"
			style:padding="0"
			style:color="var(--g-ink-3)"
			style:font-size="12px"
			style:cursor="pointer"
			style:text-decoration="underline"
		>Schließen</button>
	</div>
{:else}
	<div
		class={className}
		style:margin-top="16px"
		style:display="flex"
		style:align-items="center"
		style:gap="16px"
		style:flex-wrap="wrap"
		style:padding="12px 16px"
		style:background="var(--g-accent-tint)"
		style:border-left="3px solid var(--g-accent)"
		style:border-radius="var(--g-r-2)"
	>
		<div style:font-size="13px" style:color="var(--g-ink-2)" style:flex="1" style:min-width="240px" style:line-height="1.45">
			<strong style:color="var(--g-ink)">Tourstart um {sign}{abs} {dayWord} verschoben.</strong>{' '}
			Sollen die {count} Folge-Etappen um denselben Betrag mitverschoben werden?
		</div>
		<div style:display="flex" style:gap="8px">
			<Btn variant="accent" size="sm" onclick={onApply}>Alle mitverschieben</Btn>
			<Btn variant="ghost" size="sm" onclick={onDismiss}>Nur diese Etappe</Btn>
		</div>
	</div>
{/if}
