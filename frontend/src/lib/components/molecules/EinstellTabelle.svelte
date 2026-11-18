<script lang="ts" module>
	import type { Darstellung } from '$lib/components/atoms/RohEinfachKnopf.svelte';

	/** Zustand einer Zelle, Vokabular des View-Models (Spec #3122 Teil A Nr. 7). */
	export type ZellenZustand = 'on' | 'off' | 'locked' | 'not_in_email';

	export interface EinstellStelle {
		/** Kennung der Stelle (email, telegram, sms, hourly, outlook); steht in jedem Ereignis. */
		id: string;
		titel: string;
		/** Kurztitel für das enge Raster (Handy, höchstens etwa acht Zeichen); ohne Angabe der Titel. */
		titelKurz?: string;
		unterzeile?: string;
		/** Mit Trennlinie abgesetzt (Stundenverlauf, 3-Tages-Ausblick). */
		abgesetzt?: boolean;
		/** Schmale Spalte ohne Platz für Beispielwerte. */
		schmal?: boolean;
		/** false: Block aus bzw. Kurzstil — Haken der Spalte nicht bedienbar, kein Knopf, kein Beispielwert. */
		bedienbar?: boolean;
		/** Zugänglicher Name der Zelle, z. B. (m) => „Wind in E-Mail“. */
		zellenName: (metrik: string) => string;
	}
	export interface EinstellZelle {
		zustand: ZellenZustand;
		/** Grund bei locked („kein Stundenwert“) und not_in_email. */
		grund?: string;
		/** Gewählte Form; null oder fehlend: die Stelle hat nur eine Form, kein Knopf. */
		format?: Darstellung | null;
		beispiel?: string;
		/** warn = „passt nicht mehr“, leise = „nur Tageswert“. */
		marke?: { text: string; ton: 'warn' | 'leise' };
	}
	export interface EinstellMetrik {
		id: string;
		name: string;
		zellen: Record<string, EinstellZelle>;
	}
	export interface EinstellFesteZeile {
		name: string;
		hinweis?: string;
		/** Warum es keine Abwahl gibt („immer dabei“). */
		grund: string;
		/** Stellen mit festem Haken; die übrigen Zellen bleiben leer. */
		stellen: string[];
	}
</script>

<script lang="ts">
	// Issue #3122 B3a — Einstell-Tabelle „Was steht wo“ (Mockup Fassung 4: `.kx`; Charter §3, vierte
	// Tabellen-Ausnahme, ADR-0124). Zeile = Metrik, Spalte = Stelle. Spalten, Zeilen und alle Texte kommen
	// als Props; der Baustein ruft keine API und hält keinen eigenen Zustand: Haken, Format und
	// Reihenfolge meldet er nach außen. Umsortieren (Ziehen und Tastatur) über SortableList (ADR-0024).
	// Trip (vier Stellen) und Orte (fünf Stellen) nutzen denselben Baustein.
	import { Haken, RohEinfachKnopf } from '$lib/components/atoms';
	import type { HakenZustand } from '$lib/components/atoms/Haken.svelte';
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		/** Kopf der Namensspalte. */
		metrikTitel: string;
		stellen: EinstellStelle[];
		metriken: EinstellMetrik[];
		/** Feste Zeile ohne Griff und ohne Abwahl, immer an erster Stelle (amtliche Warnungen). */
		festeZeile?: EinstellFesteZeile;
		onHaken?: (e: { metrik: string; stelle: string; an: boolean }) => void;
		onFormat?: (e: { metrik: string; stelle: string; format: Darstellung }) => void;
		/** Neue Reihenfolge aller Metrik-Kennungen, einmal je abgeschlossener Geste. */
		onReihenfolge?: (metriken: string[]) => void;
		testid?: string;
	}
	let { metrikTitel, stellen, metriken, festeZeile, onHaken, onFormat, onReihenfolge, testid }: Props = $props();

	const HAKEN: Record<ZellenZustand, HakenZustand> = { on: 'an', off: 'aus', locked: 'gesperrt', not_in_email: 'nicht_in_email' };
	const proId = $derived(new Map(metriken.map((m) => [m.id, m])));
	const kennungen = $derived(metriken.map((m) => m.id));
	// Breites Raster (Mockup `.kx.s4`/`.s5`): Griff, Name, je Stelle eine Spalte. Maße nur aus Tokens.
	const raster = $derived(
		['var(--g-size-22px)', 'minmax(var(--g-size-130px), 0.9fr)', ...stellen.map((s) => (s.schmal ? 'var(--g-size-120px)' : 'minmax(var(--g-size-120px), 1fr)'))].join(' ')
	);
</script>

<div class="et" data-slot="einstell-tabelle" data-stellen={stellen.length} data-testid={testid}>
	<div class="et-raster et-kopf" data-slot="et-kopf" style:grid-template-columns={raster}>
		<span></span>
		<span>{metrikTitel}</span>
		{#each stellen as s (s.id)}
			<span class="et-kopfzelle" class:et-abgesetzt={s.abgesetzt} data-slot="et-kopf-stelle" data-stelle={s.id}>
				<span class="et-lang">{s.titel}</span><span class="et-kurz">{s.titelKurz ?? s.titel}</span>
				{#if s.unterzeile}<small>{s.unterzeile}</small>{/if}
			</span>
		{/each}
	</div>
	{#if festeZeile}
		<div class="et-raster et-fest" data-slot="et-fest" style:grid-template-columns={raster}>
			<span></span>
			<span class="et-name">
				{festeZeile.name}
				{#if festeZeile.hinweis}<small>{festeZeile.hinweis}</small>{/if}
			</span>
			{#each stellen as s (s.id)}
				<span class="et-zelle" class:et-abgesetzt={s.abgesetzt} data-slot="et-zelle" data-stelle={s.id}>
					{#if festeZeile.stellen.includes(s.id)}
						<Haken zustand="fest" name={s.zellenName(festeZeile.name)} grund={festeZeile.grund} />
					{/if}
				</span>
			{/each}
		</div>
	{/if}
	<SortableList items={kennungen} onDndReorder={(ids) => onReihenfolge?.(ids)} ariaLabel={$t('bausteine.einstelltabelle.zeilen_sortieren')} itemLabel={(id) => proId.get(id)?.name ?? id}>
		{#snippet row(id: string)}
			{@const m = proId.get(id)}
			{#if m}
				<div class="et-raster et-zeile" data-slot="et-zeile" data-metrik={m.id} style:grid-template-columns={raster}>
					<DragHandle size={14} label={$t('bausteine.einstelltabelle.zeile_verschieben', { name: m.name })} />
					<span class="et-name">{m.name}</span>
					{#each stellen as s (s.id)}
						{@const z = m.zellen[s.id]}
						{@const bedienbar = s.bedienbar !== false}
						{@const name = s.zellenName(m.name)}
						<span class="et-zelle" class:et-abgesetzt={s.abgesetzt} data-slot="et-zelle" data-stelle={s.id} data-zustand={z?.zustand} data-bedienbar={bedienbar ? 'true' : 'false'}>
							{#if z}
								<Haken zustand={HAKEN[z.zustand]} {name} grund={z.grund} {bedienbar} onAenderung={(an) => onHaken?.({ metrik: m.id, stelle: s.id, an })} />
								{#if z.zustand === 'on' && bedienbar}
									<RohEinfachKnopf wert={z.format ?? null} {name} onAenderung={(format) => onFormat?.({ metrik: m.id, stelle: s.id, format })} />
									{#if z.beispiel}<span class="et-beispiel" data-slot="et-beispiel">{z.beispiel}</span>{/if}
									{#if z.marke}<em class="et-marke" data-slot="et-marke" data-ton={z.marke.ton}>{z.marke.text}</em>{/if}
								{/if}
							{/if}
						</span>
					{/each}
				</div>
			{/if}
		{/snippet}
	</SortableList>
</div>

<style>
	/* Zwischen eng und breit kann die Tabelle in sich scrollen; die Seite scrollt nie seitlich. */
	.et {
		overflow-x: auto;
	}
	.et-raster {
		display: grid;
		gap: var(--g-s-1) var(--g-size-14px);
		align-items: center;
		min-width: min-content;
		padding: var(--g-size-10px) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
		background: var(--g-card);
	}
	.et-abgesetzt {
		align-self: stretch;
		padding-left: var(--g-s-3);
		border-left: 1px solid var(--g-rule-soft);
	}
	.et-kopf {
		align-items: start;
		border-top-color: var(--g-rule);
		background: var(--g-card-alt);
		color: var(--g-ink-2);
		font-family: var(--g-font-mono);
		font-size: var(--g-size-10px);
		letter-spacing: var(--g-size-0-08em);
		text-transform: uppercase;
	}
	.et-kopfzelle {
		min-width: 0;
		overflow-wrap: anywhere;
	}
	.et-kopf small {
		display: block;
		margin-top: var(--g-size-2px);
		color: var(--g-ink-3);
		font-family: var(--g-font-ui);
		font-size: var(--g-text-xs);
		letter-spacing: 0;
		text-transform: none;
	}
	.et-kurz {
		display: none;
	}
	.et-name {
		min-width: 0;
		color: var(--g-ink);
		font-size: var(--g-size-14px);
		font-weight: 600;
		hyphens: auto;
		overflow-wrap: anywhere;
	}
	.et-name small {
		display: block;
		color: var(--g-ink-3);
		font-size: var(--g-s-3);
		font-weight: 400;
	}
	.et-fest {
		background: var(--g-card-alt);
	}
	.et-fest .et-name {
		color: var(--g-ink-2);
		font-weight: 500;
	}
	.et-zelle {
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: var(--g-s-2);
		min-width: 0;
	}
	/* Der Beispielwert bekommt nur den Platz, den Haken, Knopf und Marke übrig lassen (Auslassungspunkte),
	   höchstens seine eigene Breite. Erst wenn auch ohne ihn kein Platz ist, bricht die Marke um. */
	.et-beispiel {
		flex: 1 1 0;
		min-width: 0;
		max-width: max-content;
		overflow: hidden;
		color: var(--g-ink-2);
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	/* Die Marke bleibt in ihrer Zelle: einzeilig, solange Platz ist, sonst bricht sie um. */
	.et-marke {
		flex: 0 1 auto;
		min-width: 0;
		color: var(--g-bad);
		font-size: var(--g-text-xs);
		font-style: normal;
		font-weight: 600;
		line-height: 1.2;
		overflow-wrap: anywhere;
	}
	.et-marke[data-ton='leise'] {
		color: var(--g-ink-3);
		font-weight: 500;
	}

	/* Enges Raster (Mockup `@media (max-width:760px)`): jede Stelle eine schmale Spalte, die Zelle stapelt
	   Haken, Knopf und Marke; Beispielwerte und Unterzeilen entfallen. Die Regeln hängen an der Zeile
	   (nicht an `.et`), weil SortableList die gezogene Zeile als Kopie an <body> hängt. Schwelle 1199 px:
	   ab 1200 px ist neben der Seitenleiste Platz für das breite Raster mit fünf Stellen. */
	@media (max-width: 1199px) {
		.et-raster {
			grid-template-columns: var(--g-size-14px) minmax(var(--g-size-130px), 1.4fr) !important;
			grid-auto-flow: column;
			grid-auto-columns: minmax(var(--g-tap-min), 1fr);
			gap: var(--g-s-1) var(--g-size-3px);
			min-width: 0;
			padding: var(--g-s-2) var(--g-s-3);
		}
		.et-abgesetzt {
			align-self: center;
			padding-left: 0;
			border-left: 0;
		}
		.et-raster :global([data-slot='roh-einfach-pille']) {
			padding: var(--g-size-3px) var(--g-s-1);
			font-size: var(--g-size-10px);
		}
		.et-lang,
		.et-kopf small,
		.et-beispiel,
		.et-raster :global([data-slot='roh-einfach-lang']) {
			display: none;
		}
		.et-kurz,
		.et-raster :global([data-slot='roh-einfach-kurz']) {
			display: inline;
		}
		.et-kopf {
			letter-spacing: 0;
		}
		.et-kopfzelle {
			text-align: center;
		}
		.et-zelle,
		.et-raster :global([data-slot='haken'][data-zustand='gesperrt']) {
			flex-direction: column;
			gap: 0;
		}
		.et-raster :global([data-slot='haken'][data-zustand='gesperrt']) {
			max-width: 100%;
		}
		.et-marke,
		.et-raster :global(em[data-slot='haken-grund']) {
			max-width: 100%;
			font-size: var(--g-size-10px);
			line-height: 1.15;
			text-align: center;
			white-space: normal;
			hyphens: auto;
			overflow-wrap: anywhere;
		}
	}
	/* Handy: feste Spaltenbreite = Tippfläche, der Name bekommt den Rest (Mockup `.kx.s5`). */
	@media (max-width: 899px) {
		.et-raster {
			grid-template-columns: var(--g-size-14px) minmax(0, 1fr) !important;
			grid-auto-columns: var(--g-tap-min);
			column-gap: var(--g-size-2px);
			padding-block: var(--g-s-1);
		}
		.et-kopf {
			padding-block: var(--g-s-2);
		}
		/* Kurztitel bleiben einzeilig und mittig über ihrer Spalte (bis etwa acht Zeichen). */
		.et-kopfzelle {
			display: flex;
			justify-content: center;
			white-space: nowrap;
		}
		.et-name {
			font-size: var(--g-size-13px);
		}
		/* Haken und Knopf rücken optisch zusammen, ihre Tippflächen bleiben getrennt je 44 px. */
		.et-zelle:has(:global([data-slot='roh-einfach'])) :global([data-slot='haken']) {
			align-items: end;
			padding-bottom: var(--g-s-1);
		}
		.et-raster :global([data-slot='roh-einfach']) {
			align-items: start;
			padding-top: var(--g-s-1);
		}
	}
</style>
