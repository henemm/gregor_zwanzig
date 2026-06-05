/* Screen: Archiv — abgelegte Trips und Orts-Vergleiche.
 *
 * Reines Archiv. KEINE Retro-Analytik, keine Forecast-Treffer, keine
 * Briefing-Statistik — das war nie spezifiziert. Hier liegen abgeschlossene
 * Trips (auto-archiviert nach Enddatum) und vom Nutzer archivierte Vergleiche.
 *
 * Genau zwei Aktionen pro Eintrag:
 *   · Wieder aktivieren  — zurück in »Meine Trips« bzw. »Orts-Vergleiche«
 *   · Löschen            — endgültig entfernen
 *
 * Filter: Alle · Trips · Vergleiche. Suche über den Namen.
 */

const ARCHIVE_LIST = [
  { id: "ortler-2025",     type: "trip",    name: "Ortler-Überquerung",      detail: "4 Etappen",  archived: "2025-09-16" },
  { id: "zillertal-2025",  type: "trip",    name: "Zillertal mit Steffi",    detail: "1 Etappe",   archived: "2025-12-31" },
  { id: "cmp-skitirol",    type: "compare", name: "Skigebiete Tirol",        detail: "6 Orte",     archived: "2025-11-04" },
  { id: "rofan-2025",      type: "trip",    name: "Rofan Tageswanderung",    detail: "1 Etappe",   archived: "2025-08-24" },
  { id: "venediger-2024",  type: "trip",    name: "Großvenediger Rundtour",  detail: "5 Etappen",  archived: "2024-07-23" },
  { id: "cmp-wochenende",  type: "compare", name: "Wochenend-Touren Süd",    detail: "4 Orte",     archived: "2024-10-12" },
  { id: "stubai-2024",     type: "trip",    name: "Stubaier Höhenweg",       detail: "8 Etappen",  archived: "2024-09-07" },
  { id: "khw-402",         type: "trip",    name: "KHW 402",                 detail: "13 Etappen", archived: "2024-05-19" },
  { id: "cmp-gardseen",    type: "compare", name: "Gardasee vs. Comer See",  detail: "2 Orte",     archived: "2024-04-22" },
  { id: "dachstein-2023",  type: "trip",    name: "Dachstein Überschreitung", detail: "2 Etappen", archived: "2023-09-10" },
];

const ARCHIVE_TYPE_LABEL = { trip: "Trip", compare: "Vergleich" };

function ScreenArchive() {
  return (
    <div style={{ display: "flex", height: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="archive" />
      <ArchiveContent />
    </div>
  );
}

function ArchiveContent() {
  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState("all");

  const filtered = ARCHIVE_LIST
    .filter((t) => filter === "all" || t.type === filter)
    .filter((t) => t.name.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => b.archived.localeCompare(a.archived));

  const nTrips    = ARCHIVE_LIST.filter((t) => t.type === "trip").length;
  const nCompares = ARCHIVE_LIST.filter((t) => t.type === "compare").length;
  const chips = [
    { id: "all",     label: "Alle",       n: ARCHIVE_LIST.length },
    { id: "trip",    label: "Trips",      n: nTrips },
    { id: "compare", label: "Vergleiche", n: nCompares },
  ];

  return (
    <main style={{ flex: 1, padding: "32px 40px", overflow: "auto" }}>

      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <Eyebrow>Workspace · Archiv</Eyebrow>
          <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.025em", marginTop: 4 }}>Archiv</div>
          <div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 6, maxWidth: 620, lineHeight: 1.5 }} data-comment-anchor="6e77049460-div-138-13">
            Abgelegte Trips und Orts-Vergleiche. Trips wandern nach ihrem Enddatum
            automatisch hierher. Jeden Eintrag kannst du wieder aktivieren oder
            endgültig löschen.
          </div>
        </div>
      </div>

      {/* Search + type filter */}
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 20 }}>
        <div style={{ position: "relative", flex: "0 0 380px" }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" strokeWidth="2"
               style={{ position: "absolute", top: 11, left: 12 }}>
            <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
          </svg>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Suchen…"
                 style={{
                   width: "100%", padding: "9px 14px 9px 34px",
                   border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-pill)",
                   background: "var(--g-card)", fontSize: 13, fontFamily: "var(--g-font-sans)",
                   color: "var(--g-ink)", outline: "none"
                 }} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {chips.map((c) => (
            <ArchiveFilterTab key={c.id} id={c.id} count={c.n} filter={filter} setFilter={setFilter}>
              {c.label}
            </ArchiveFilterTab>
          ))}
        </div>
      </div>

      {/* Table */}
      <Card padding={0} style={{ overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 0,
                      padding: "12px 20px", background: "var(--g-paper-deep)",
                      fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.18em",
                      textTransform: "uppercase", color: "var(--g-ink-3)", fontWeight: 500,
                      borderBottom: "1px solid var(--g-rule)" }}>
          <div>Name</div>
          <div>Umfang</div>
          <div>Archiviert</div>
          <div style={{ textAlign: "right" }}>Aktionen</div>
        </div>
        {filtered.map((t, i) => (
          <ArchiveRow key={t.id} item={t} alt={i % 2 === 1} />
        ))}
        {filtered.length === 0 && (
          <div style={{ padding: 40, textAlign: "center", color: "var(--g-ink-3)", fontSize: 13 }}>
            Keine archivierten Einträge für »{query}« gefunden.
          </div>
        )}
      </Card>

      <div style={{ marginTop: 14, fontSize: 11, color: "var(--g-ink-4)",
                    fontFamily: "var(--g-font-mono)", letterSpacing: "0.06em" }}>
        {filtered.length} von {ARCHIVE_LIST.length} Einträgen · Trips auto-archiviert nach Trip-Ende
      </div>
    </main>
  );
}

function ArchiveFilterTab({ id, count, filter, setFilter, children }) {
  const active = filter === id;
  return (
    <button onClick={() => setFilter(id)} style={{
      display: "inline-flex", alignItems: "center", gap: 7,
      padding: "7px 12px", minHeight: 34,
      background: active ? "var(--g-ink)" : "var(--g-card)",
      color: active ? "var(--g-paper)" : "var(--g-ink-2)",
      border: `1px solid ${active ? "var(--g-ink)" : "var(--g-rule)"}`,
      borderRadius: "var(--g-r-pill)", cursor: "pointer",
      fontFamily: "var(--g-font-mono)", fontSize: 12, fontWeight: 500, letterSpacing: "0.02em"
    }}>
      {children}
      <span style={{
        fontSize: 10, padding: "1px 6px", borderRadius: 8,
        background: active ? "rgba(255,255,255,0.18)" : "var(--g-paper-deep)",
        color: active ? "var(--g-paper)" : "var(--g-ink-3)"
      }}>{count}</span>
    </button>
  );
}

function ArchiveRow({ item, alt }) {
  const [hover, setHover] = React.useState(false);
  const isCompare = item.type === "compare";
  const dot = isCompare ? "#3d6b3a" : "var(--g-ink-4)";

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto",
        alignItems: "center", padding: "16px 20px",
        background: hover ? "var(--g-card-alt, #f1eee6)" : (alt ? "var(--g-paper-deep)" : "transparent"),
        borderBottom: "1px solid var(--g-rule-soft)", gap: 0, transition: "background 120ms"
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: dot, flexShrink: 0 }} />
        <span style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em",
                       whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.name}</span>
        <span style={{
          fontSize: 9.5, fontFamily: "var(--g-font-mono)", letterSpacing: "0.14em",
          textTransform: "uppercase", color: isCompare ? "#3d6b3a" : "var(--g-ink-3)",
          border: `1px solid ${isCompare ? "rgba(61,107,58,0.35)" : "var(--g-rule)"}`,
          borderRadius: "var(--g-r-pill)", padding: "2px 8px", flexShrink: 0
        }}>{ARCHIVE_TYPE_LABEL[item.type]}</span>
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", fontVariantNumeric: "tabular-nums" }}>
        {item.detail}
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)",
                    fontFamily: "var(--g-font-mono)", letterSpacing: "0.02em" }}>
        {item.archived}
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", alignItems: "center" }}>
        <Btn variant="ghost" size="sm" icon={archiveIcon("reactivate", "var(--g-ink)")}>Wieder aktivieren</Btn>
        <button title="Endgültig löschen" style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          padding: "6px 10px", minHeight: 30,
          background: "transparent", border: "1px solid var(--g-rule)",
          borderRadius: "var(--g-r-2)", cursor: "pointer",
          fontSize: 12, fontWeight: 500, fontFamily: "var(--g-font-sans)",
          color: "var(--g-bad, #a83232)"
        }}>
          {archiveIcon("trash", "var(--g-bad, #a83232)")}
          Löschen
        </button>
      </div>
    </div>
  );
}

function archiveIcon(kind, c = "var(--g-ink-2)") {
  const p = { width: 14, height: 14, viewBox: "0 0 24 24", fill: "none", stroke: c,
              strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" };
  const map = {
    reactivate: <svg {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /></svg>,
    trash:      <svg {...p}><path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" /></svg>,
  };
  return map[kind] || null;
}

window.ScreenArchive = ScreenArchive;
window.ArchiveContent = ArchiveContent;
window.ARCHIVE_LIST = ARCHIVE_LIST;
