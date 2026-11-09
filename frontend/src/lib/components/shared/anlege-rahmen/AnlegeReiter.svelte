<script lang="ts" module>
	export type AnlegeReiterZustand = 'offen' | 'erledigt' | 'gesperrt';
	export interface AnlegeReiterSchritt {
		id: string;
		label: string;
		zustand: AnlegeReiterZustand;
		optional?: boolean;
		/** Schritt schon erledigt, obwohl (wieder) gesperrt — beide Punkte zugleich (Bestandsverhalten
		 *  beider Editoren, z. B. Trip: Wetter-Metriken besucht, aber GPX fehlt). */
		erledigt?: boolean;
		/** Sperr-Hinweis (Tooltip am gesperrten Reiter). */
		hinweis?: string | null;
	}
</script>

<script lang="ts">
	// Issue #2880 (Epic #2345, ADR-0097/ADR-0111): EINE Schritt-Reiterleiste für das Anlegen von
	// Trip und Ortsvergleich, Computer und Handy. Ersetzt die vier handgebauten Leisten.
	// Jeder Reiter ist ein `button role="tab"`, gesperrt `aria-disabled="true"` (klickbar, damit der
	// Aufrufer Hinweis/Toast zeigen kann). Tastatur nach WAI-ARIA-Tablist (AC-8, Adversary F003):
	// nur der aktive Reiter liegt in der Tab-Reihenfolge (roving tabindex), Pfeil links/rechts,
	// Pos1/Ende bewegen den Fokus über ALLE Reiter, auch gesperrte (Screenreader hören so, dass und
	// warum ein Schritt gesperrt ist); Enter/Leertaste lösen wie ein Klick `onWahl` aus — der
	// Aufrufer wechselt bei gesperrten Schritten nicht, sondern zeigt seinen Hinweis. Gesperrt ohne Opacity und in --g-ink-3 (#2371, ADR-0008:
	// >= 4,5:1); die Sperre zeigen aria-disabled, der Punkt in --g-ink-4 und der Mauszeiger. Die
	// Zustandsmarker (Punkt erledigt --g-good — wie bisher nur am Computer —, Punkt gesperrt
	// --g-ink-4) stehen NUR hier (#2881 Lieferung B, ADR-0111 Punkt 7: Dot statt ✓/⊘).
	// Spec: docs/specs/modules/rework_2880_paritaet_reiterflaeche_anlegefelder.md
	import { t } from '$lib/i18n';
	import { Dot } from '$lib/components/atoms';

	interface Props {
		schritte: AnlegeReiterSchritt[];
		aktiv: string;
		onWahl: (id: string) => void;
		variante?: 'desktop' | 'mobil';
		/** Reiter `${testidPrefix}-<id>`, Leiste `${testidPrefix}bar`. */
		testidPrefix: string;
	}

	let { schritte, aktiv, onWahl, variante = 'desktop', testidPrefix }: Props = $props();

	// Fade-Maske am Rand der waagerecht scrollenden Handy-Leiste (wörtlich wie bisher, inline).
	const VERLAUF = 'linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent)';
	const MASKE = `mask-image: ${VERLAUF}; -webkit-mask-image: ${VERLAUF};`;

	// Roving tabindex: der aktive Reiter (sonst der erste) ist per Tab erreichbar, die übrigen per Pfeil.
	const fokusId = $derived(schritte.some((s) => s.id === aktiv) ? aktiv : schritte[0]?.id);
	let leiste = $state<HTMLDivElement | undefined>();
	function taste(e: KeyboardEvent, i: number): void {
		const n = schritte.length;
		const ziele: Record<string, number> = { ArrowRight: (i + 1) % n, ArrowLeft: (i - 1 + n) % n, Home: 0, End: n - 1 };
		const ziel = ziele[e.key];
		if (ziel === undefined) return;
		e.preventDefault();
		leiste?.querySelectorAll<HTMLElement>('[role="tab"]')[ziel]?.focus();
	}

	// Kurzes Wackeln am gesperrten Reiter (Computer), vorher nur beim Trip.
	let wackelt = $state<string | null>(null);
	function waehle(s: AnlegeReiterSchritt): void {
		if (s.zustand === 'gesperrt' && variante === 'desktop') {
			wackelt = s.id;
			setTimeout(() => {
				if (wackelt === s.id) wackelt = null;
			}, 500);
		}
		onWahl(s.id);
	}
</script>

<div
	class="anlege-reiter"
	class:mobil={variante === 'mobil'}
	role="tablist"
	bind:this={leiste}
	data-testid="{testidPrefix}bar"
	style={variante === 'mobil' ? MASKE : undefined}
>
	{#each schritte as s, i (s.id)}
		{@const an = s.id === aktiv}
		{@const zu = s.zustand === 'gesperrt'}
		{@const fertig = s.zustand === 'erledigt' || s.erledigt === true}
		<button
			type="button"
			role="tab"
			class="reiter"
			class:an
			class:zu
			class:wackelt={wackelt === s.id}
			data-testid="{testidPrefix}-{s.id}"
			data-active={an ? 'true' : 'false'}
			data-locked={zu ? 'true' : 'false'}
			data-done={fertig ? 'true' : 'false'}
			aria-selected={an}
			aria-disabled={zu ? 'true' : undefined}
			tabindex={s.id === fokusId ? 0 : -1}
			title={zu && s.hinweis ? $t('trip.anlegen.gesperrt', { hinweis: s.hinweis }) : undefined}
			onclick={() => waehle(s)}
			onkeydown={(e) => taste(e, i)}
		>
			{s.label}
			{#if s.optional}
				<span class="pille" data-slot="anlege-reiter-optional">{$t(variante === 'mobil' ? 'trip.anlegen.opt' : 'trip.anlegen.optional')}</span>
			{/if}
			<!-- #2881 R3 (ADR-0111 Punkt 7): Dot statt ✓/⊘ — erledigt --g-good (wie bisher nur am
			     Computer, am Handy fehlt der Platz), gesperrt --g-ink-4 neben aria-disabled. -->
			{#if fertig && !an && variante === 'desktop'}
				<Dot tone="good" size="xs" data-zustand="erledigt" />
			{/if}
			{#if zu}
				<Dot tone="neutral" size="xs" data-zustand="gesperrt" style="background: var(--g-ink-4);" />
			{/if}
		</button>
	{/each}
</div>

<style>
	.anlege-reiter {
		display: flex;
		gap: 0;
		overflow-x: auto;
		border-bottom: 1px solid var(--g-rule);
		padding: 0 40px;
	}
	.anlege-reiter.mobil {
		padding: 0;
		flex-shrink: 0;
		border-bottom-color: var(--g-rule-soft);
		-webkit-overflow-scrolling: touch;
		scrollbar-width: none;
	}
	.reiter {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 12px 16px;
		margin-bottom: -1px;
		background: none;
		border: none;
		border-bottom: 2px solid transparent;
		font-family: var(--g-font-sans);
		font-size: 13px;
		font-weight: 500;
		color: var(--g-ink-3);
		white-space: nowrap;
		cursor: pointer;
		user-select: none;
		transition: color 200ms;
	}
	.mobil .reiter {
		display: inline-flex;
		flex-shrink: 0;
		padding: 13px;
		min-height: 44px;
		font-size: 14px;
	}
	.reiter.an {
		font-weight: 600;
		color: var(--g-ink);
		border-bottom-color: var(--g-accent);
	}
	.reiter.zu {
		cursor: not-allowed;
	}
	.reiter.wackelt {
		transform: translateX(2px);
	}
	.pille {
		font-family: var(--g-font-mono);
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		padding: 1px 5px;
		border-radius: 3px;
		background: rgba(196, 90, 42, 0.1);
		color: var(--g-accent-deep);
	}
</style>
