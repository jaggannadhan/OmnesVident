import { useState, useEffect, useRef, useCallback } from "react";
import type { StoryOut } from "../services/api";

// ─── Constants ────────────────────────────────────────────────────────────────

const ROTATE_INTERVAL_MS = 6000;   // auto-advance every 6 s
const BREAKING_COLOR     = "#FF2020";
const SWIPE_THRESHOLD_PX = 60;     // distance required to commit a swipe

// ─── HeatBar — visual urgency indicator ──────────────────────────────────────

function HeatBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  const color =
    pct >= 90 ? "#FF2020" :
    pct >= 70 ? "#ff6b35" :
    pct >= 40 ? "#facc15" :
               "#4ade80";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
      <div
        style={{
          flex: 1,
          height: "3px",
          borderRadius: "2px",
          background: "rgba(255,255,255,0.08)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            boxShadow: `0 0 6px ${color}`,
            transition: "width 0.4s ease",
          }}
        />
      </div>
      <span style={{ fontSize: "8px", fontFamily: "monospace", color, fontWeight: 700, minWidth: "22px" }}>
        {pct}
      </span>
    </div>
  );
}

// ─── BreakingNewsCarousel ─────────────────────────────────────────────────────

interface BreakingNewsCarouselProps {
  stories: StoryOut[];
}

export function BreakingNewsCarousel({ stories }: BreakingNewsCarouselProps) {
  // Sort by heat_score desc, then timestamp desc
  const sorted = [...stories].sort((a, b) => {
    if (b.heat_score !== a.heat_score) return b.heat_score - a.heat_score;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  const [activeIdx, setActiveIdx] = useState(0);
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartXRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const advance = useCallback(() => {
    setActiveIdx((i) => (i + 1) % sorted.length);
  }, [sorted.length]);

  const rewind = useCallback(() => {
    setActiveIdx((i) => (i - 1 + sorted.length) % sorted.length);
  }, [sorted.length]);

  const resetTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(advance, ROTATE_INTERVAL_MS);
  }, [advance]);

  useEffect(() => {
    if (sorted.length === 0) return;
    resetTimer();
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [sorted.length, resetTimer]);

  // Reset index when the stories list changes
  useEffect(() => { setActiveIdx(0); }, [sorted.length]);

  // ─── Swipe handlers (pointer events unify touch + mouse + pen) ──────────────
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    // Don't hijack clicks on interactive children (link, dot buttons, arrows)
    if ((e.target as HTMLElement).closest("a, button")) return;
    dragStartXRef.current = e.clientX;
    setIsDragging(true);
    if (timerRef.current) clearInterval(timerRef.current);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (dragStartXRef.current === null) return;
    setDragOffset(e.clientX - dragStartXRef.current);
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (dragStartXRef.current === null) return;
    const delta = e.clientX - dragStartXRef.current;
    dragStartXRef.current = null;
    setIsDragging(false);
    setDragOffset(0);

    if (sorted.length > 1 && Math.abs(delta) > SWIPE_THRESHOLD_PX) {
      if (delta < 0) advance();
      else          rewind();
    }
    resetTimer();

    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  };

  if (sorted.length === 0) return null;

  const story = sorted[Math.min(activeIdx, sorted.length - 1)];

  function relativeTime(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const m = Math.floor(diff / 60_000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    return `${Math.floor(m / 60)}h ago`;
  }

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "rgba(8,10,24,0.96)",
        border: `1px solid ${BREAKING_COLOR}33`,
        borderLeft: `3px solid ${BREAKING_COLOR}`,
        borderRadius: "12px",
        overflow: "hidden",
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px 8px",
          borderBottom: `1px solid ${BREAKING_COLOR}22`,
          background: `${BREAKING_COLOR}0d`,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {/* Pulsing dot */}
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: BREAKING_COLOR,
              boxShadow: `0 0 8px ${BREAKING_COLOR}`,
              display: "inline-block",
              animation: "pulse 1.2s ease-in-out infinite",
            }}
          />
          <span
            style={{
              fontSize: "10px",
              fontWeight: 800,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: BREAKING_COLOR,
            }}
          >
            Breaking News
          </span>
        </div>
        <span style={{ fontSize: "9px", fontFamily: "monospace", color: "#475569" }}>
          {sorted.length} alert{sorted.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Active story card — swipeable */}
      <div
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        style={{
          flex: 1,
          padding: "12px 14px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          minHeight: 0,
          touchAction: "pan-y",
          cursor: sorted.length > 1 ? (isDragging ? "grabbing" : "grab") : "default",
          userSelect: isDragging ? "none" : "auto",
          transform: `translateX(${dragOffset}px)`,
          opacity: 1 - Math.min(0.4, Math.abs(dragOffset) / 400),
          transition: isDragging ? "none" : "transform 0.25s ease, opacity 0.25s ease",
        }}
      >
        {/* Heat bar */}
        <HeatBar score={story.heat_score} />

        {/* Meta: category + region + time */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          <span
            style={{
              fontSize: "8px",
              fontWeight: 700,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: BREAKING_COLOR,
              background: `${BREAKING_COLOR}18`,
              padding: "2px 5px",
              borderRadius: "3px",
            }}
          >
            {story.category}
          </span>
          <span style={{ fontSize: "8px", fontFamily: "monospace", color: "#64748b", fontWeight: 600 }}>
            {story.region_code}
          </span>
          <span style={{ fontSize: "8px", color: "#334155", fontFamily: "monospace" }}>
            {relativeTime(story.timestamp)}
          </span>
        </div>

        {/* Source */}
        <p style={{ margin: 0, fontSize: "8px", color: "#475569", textTransform: "uppercase", letterSpacing: "0.1em" }}>
          {story.source_name}
        </p>

        {/* Title */}
        <p
          style={{
            margin: 0,
            fontSize: "12px",
            fontWeight: 700,
            color: "#f1f5f9",
            lineHeight: 1.45,
            flex: 1,
          }}
        >
          {story.title.length > 120 ? story.title.slice(0, 117) + "…" : story.title}
        </p>

        {/* Snippet */}
        <p style={{ margin: 0, fontSize: "10px", color: "#64748b", lineHeight: 1.5 }}>
          {story.snippet.length > 100 ? story.snippet.slice(0, 97) + "…" : story.snippet}
        </p>

        {/* Read link */}
        <a
          href={story.source_url}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            fontSize: "9px",
            fontWeight: 700,
            color: BREAKING_COLOR,
            textDecoration: "none",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            marginTop: "auto",
          }}
        >
          Read full story ↗
        </a>
      </div>

      {/* Dot navigation + arrows */}
      {sorted.length > 1 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "10px",
            padding: "8px 14px 10px",
            borderTop: `1px solid ${BREAKING_COLOR}14`,
            flexShrink: 0,
          }}
        >
          <button
            onClick={() => { rewind(); resetTimer(); }}
            style={{ background: "none", border: "none", color: "#475569", cursor: "pointer", fontSize: "12px", padding: "0 4px", lineHeight: 1 }}
            aria-label="Previous"
          >
            ‹
          </button>

          <div style={{ display: "flex", gap: "5px", alignItems: "center" }}>
            {sorted.map((_, i) => (
              <button
                key={i}
                onClick={() => { setActiveIdx(i); resetTimer(); }}
                style={{
                  width: i === activeIdx ? "16px" : "5px",
                  height: "5px",
                  borderRadius: "3px",
                  background: i === activeIdx ? BREAKING_COLOR : "#334155",
                  border: "none",
                  cursor: "pointer",
                  padding: 0,
                  transition: "width 0.2s ease, background 0.2s ease",
                  boxShadow: i === activeIdx ? `0 0 6px ${BREAKING_COLOR}` : "none",
                }}
                aria-label={`Go to story ${i + 1}`}
              />
            ))}
          </div>

          <button
            onClick={() => { advance(); resetTimer(); }}
            style={{ background: "none", border: "none", color: "#475569", cursor: "pointer", fontSize: "12px", padding: "0 4px", lineHeight: 1 }}
            aria-label="Next"
          >
            ›
          </button>
        </div>
      )}

      {/* Inline keyframes for the pulsing dot */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.5; transform: scale(0.75); }
        }
      `}</style>
    </div>
  );
}
