<script lang="ts">
	// Issue #568 — SetupResumeCard-Molecule (Startseite-Planungs-Zustand).
	// Spec: docs/specs/modules/issue_568_home_redesign.md
	//
	// Zeigt einen offenen Wizard mit Schritt-Checkliste + Fortschrittsbalken +
	// CTA-Button („Setup fortsetzen"). tone='accent' = Trip (Akzent-Farbe),
	// tone='default' = Vergleich. CTA-Touch-Target ≥ 44 px (AC-7).

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

	const ctaBg = $derived(isAccent ? 'var(--g-accent)' : 'var(--g-ink-2)');
	const ctaInk = $derived(isAccent ? 'var(--g-ink-on-accent, #ffffff)' : '#ffffff');
	const barColor = $derived(isAccent ? 'var(--g-accent)' : 'var(--g-ink-2)');
</script>

<article
	class={className}
	data-tone={tone}
	style:background="var(--g-card)"
	style:border="1px solid var(--g-rule-soft)"
	style:border-radius="var(--g-r-3)"
	style:padding="20px 22px"
	style:display="flex"
	style:flex-direction="column"
	style:gap="14px"
>
	<header style:display="flex" style:flex-direction="column" style:gap="4px">
		<span
			style:font-family="var(--g-font-mono)"
			style:font-size="11px"
			style:text-transform="uppercase"
			style:letter-spacing="0.08em"
			style:color="var(--g-ink-3)"
		>{eyebrow}</span>
		<h3
			style:margin="0"
			style:font-size="20px"
			style:font-weight="600"
			style:line-height="1.2"
			style:letter-spacing="-0.01em"
			style:color="var(--g-ink)"
		>{title}</h3>
		{#if subtitle}
			<p style:margin="0" style:font-size="13px" style:color="var(--g-ink-2)" style:line-height="1.5">
				{subtitle}
			</p>
		{/if}
	</header>

	<!-- Fortschrittsbalken -->
	<div style:display="flex" style:flex-direction="column" style:gap="6px">
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
			style:font-size="11px"
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
		style:gap="6px"
	>
		{#each steps as step (step.label)}
			<li
				style:display="flex"
				style:align-items="center"
				style:gap="8px"
				style:font-size="13px"
				style:color={step.done ? 'var(--g-ink-3)' : 'var(--g-ink)'}
			>
				<span
					style:display="inline-flex"
					style:align-items="center"
					style:justify-content="center"
					style:width="16px"
					style:height="16px"
					style:flex-shrink="0"
					style:border-radius="50%"
					style:font-size="11px"
					style:font-weight="700"
					style:background={step.done ? 'var(--g-success, #2f8f3a)' : 'transparent'}
					style:border={step.done ? 'none' : '1.5px solid var(--g-rule)'}
					style:color={step.done ? '#ffffff' : 'var(--g-ink-3)'}
					aria-hidden="true"
				>{step.done ? '✓' : '○'}</span>
				<span>{step.label}</span>
			</li>
		{/each}
	</ul>

	<!-- CTAs -->
	<div style:display="flex" style:gap="10px" style:align-items="center" style:margin-top="2px">
		<a
			href={ctaHref}
			style:display="inline-flex"
			style:align-items="center"
			style:justify-content="center"
			style:gap="6px"
			style:min-height="44px"
			style:padding="10px 18px"
			style:background={ctaBg}
			style:color={ctaInk}
			style:font-size="14px"
			style:font-weight="600"
			style:text-decoration="none"
			style:border-radius="var(--g-r-2)"
			style:border="1px solid {ctaBg}"
		>{ctaLabel} →</a>
		{#if secondary}
			<a
				href={secondary.href}
				style:font-size="13px"
				style:color="var(--g-ink-3)"
				style:text-decoration="none"
				style:padding="8px 10px"
				style:min-height="44px"
				style:display="inline-flex"
				style:align-items="center"
			>{secondary.label}</a>
		{/if}
	</div>
</article>
