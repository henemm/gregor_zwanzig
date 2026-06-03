<script lang="ts">
	// Issue #568 — SetupResumeCard-Molecule (Startseite-Planungs-Zustand).
	// Spec: docs/specs/modules/issue_568_home_redesign.md
	// Issue #573 — Charter-Compliance-Fix: <Dot> statt ✓/○, <Btn> statt hand-styled <a>,
	//              Token-Fixes (--g-good, --g-paper, letter-spacing).
	//
	// Zeigt einen offenen Wizard mit Schritt-Checkliste + Fortschrittsbalken +
	// CTA-Button („Setup fortsetzen"). tone='accent' = Trip (Akzent-Farbe),
	// tone='default' = Vergleich. CTA-Touch-Target ≥ 44 px (AC-7).

	import { Dot, Btn } from '$lib/components/atoms';

	interface Step {
		label: string;
		done: boolean;
	}

	interface Props {
		eyebrow: string;
		title: string;
		subtitle?: string;
		steps: Step[];
		ctaLabel: string;
		ctaHref: string;
		secondary?: { label: string; href: string };
		tone?: 'accent' | 'default';
		class?: string;
	}

	let {
		eyebrow,
		title,
		subtitle,
		steps,
		ctaLabel,
		ctaHref,
		secondary,
		tone = 'default',
		class: className = ''
	}: Props = $props();

	const isAccent = $derived(tone === 'accent');
	const total = $derived(steps?.length ?? 0);
	const doneCount = $derived((steps ?? []).filter((s) => s.done).length);
	const donePct = $derived(total > 0 ? Math.round((doneCount / total) * 100) : 0);

	const barColor = $derived(isAccent ? 'var(--g-accent)' : 'var(--g-ink-2)');
</script>

<article
	class={className}
	data-tone={tone}
	style:background="var(--g-card)"
	style:border="1px solid var(--g-rule-soft)"
	style:border-radius="var(--g-r-3)"
	style:padding="var(--g-s-5) var(--g-s-6)"
	style:display="flex"
	style:flex-direction="column"
	style:gap="var(--g-s-3)"
>
	<header style:display="flex" style:flex-direction="column" style:gap="var(--g-s-1)">
		<span
			style:font-family="var(--g-font-mono)"
			style:font-size="var(--g-text-xs)"
			style:text-transform="uppercase"
			style:letter-spacing="var(--g-track-caps)"
			style:color="var(--g-ink-3)"
		>{eyebrow}</span>
		<h3
			style:margin="0"
			style:font-size="var(--g-text-xl)"
			style:font-weight="600"
			style:line-height="1.2"
			style:letter-spacing="var(--g-track-tight)"
			style:color="var(--g-ink)"
		>{title}</h3>
		{#if subtitle}
			<p style:margin="0" style:font-size="var(--g-text-sm)" style:color="var(--g-ink-2)" style:line-height="1.5">
				{subtitle}
			</p>
		{/if}
	</header>

	<!-- Fortschrittsbalken -->
	<div style:display="flex" style:flex-direction="column" style:gap="var(--g-s-1)">
		<div
			style:height="4px"
			style:background="var(--g-rule-soft)"
			style:border-radius="2px"
			style:overflow="hidden"
		>
			<div
				style:height="100%"
				style:background={barColor}
				style:border-radius="2px"
				style:width="{donePct}%"
				style:transition="width 300ms ease"
			></div>
		</div>
		<div
			style:font-family="var(--g-font-mono)"
			style:font-size="var(--g-text-xs)"
			style:color="var(--g-ink-3)"
		>{doneCount} von {total} Schritten</div>
	</div>

	<!-- Schritt-Checkliste -->
	<ul
		style:list-style="none"
		style:margin="0"
		style:padding="0"
		style:display="flex"
		style:flex-direction="column"
		style:gap="var(--g-s-1)"
	>
		{#each steps as step (step.label)}
			<li
				style:display="flex"
				style:align-items="center"
				style:gap="var(--g-s-2)"
				style:font-size="var(--g-text-sm)"
				style:color={step.done ? 'var(--g-ink-3)' : 'var(--g-ink)'}
			>
				<Dot tone={step.done ? 'good' : 'neutral'} size={8} />
				<span>{step.label}</span>
			</li>
		{/each}
	</ul>

	<!-- CTAs -->
	<div style:display="flex" style:gap="var(--g-s-2)" style:align-items="center" style:margin-top="var(--g-s-1)">
		<Btn href={ctaHref} variant={isAccent ? 'accent' : 'primary'} size="md">
			{ctaLabel} →
		</Btn>
		{#if secondary}
			<a
				href={secondary.href}
				style:font-size="var(--g-text-sm)"
				style:color="var(--g-ink-3)"
				style:text-decoration="none"
				style:padding="var(--g-s-2) var(--g-s-2)"
				style:min-height="44px"
				style:display="inline-flex"
				style:align-items="center"
			>{secondary.label}</a>
		{/if}
	</div>
</article>
