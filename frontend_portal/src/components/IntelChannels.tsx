// Data sources powering the feed — the news APIs and aggregators wired
// into the ingestion engine. Click-through goes to each provider's site.

const SOURCES = [
  { kind: "NEWS API", title: "NewsData.io",      url: "https://newsdata.io" },
  { kind: "NEWS API", title: "WorldNews API",    url: "https://worldnewsapi.com" },
  { kind: "NEWS API", title: "Mediastack",       url: "https://mediastack.com" },
  { kind: "NEWS API", title: "NewsCatcher",      url: "https://newscatcherapi.com" },
  { kind: "NEWS API", title: "GNews",            url: "https://gnews.io" },
  { kind: "NEWS API", title: "Currents API",     url: "https://currentsapi.services" },
  { kind: "SOCIAL",   title: "Reddit Communities", url: "https://reddit.com" },
  { kind: "RSS",      title: "Verified RSS Feeds" },
];

export function IntelChannels() {
  return (
    <section className="p-6">
      <h4 className="font-mono text-[10px] uppercase tracking-[0.3em] font-bold mb-5" style={{ color: "var(--color-text)", opacity: 0.6 }}>
        INTEL CHANNELS
      </h4>
      <div className="flex flex-col gap-4">
        {SOURCES.map((s) => {
          const Inner = (
            <>
              <span className="font-mono text-[9px] uppercase" style={{ color: "var(--color-text)", opacity: 0.6 }}>
                {s.kind}
              </span>
              <p className="font-headline text-base leading-tight group-hover:text-accent transition-colors" style={{ color: "var(--color-text)" }}>
                {s.title}
              </p>
            </>
          );
          return s.url ? (
            <a
              key={s.title}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group block border-l-2 border-rim/70 pl-4 py-1 hover:border-accent transition-all"
            >
              {Inner}
            </a>
          ) : (
            <div
              key={s.title}
              className="group block border-l-2 border-rim/70 pl-4 py-1"
            >
              {Inner}
            </div>
          );
        })}
      </div>
    </section>
  );
}
