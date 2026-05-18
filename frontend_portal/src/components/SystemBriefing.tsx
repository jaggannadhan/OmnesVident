// Static "System Briefing" newsletter card shown in the aside.
// Placeholder for now — there is no newsletter backend yet, so the form
// only animates a "submitted" state in-memory.
import { useState } from "react";

export function SystemBriefing() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setSubmitted(true);
    setTimeout(() => setSubmitted(false), 3000);
    setEmail("");
  }

  return (
    <section className="p-6 border-b border-rim">
      <h4 className="font-mono text-[10px] text-accent uppercase tracking-[0.3em] font-bold mb-5 flex items-center gap-2">
        <span className="w-1 h-3 bg-accent animate-blink" />
        SYSTEM BRIEFING
      </h4>
      <div className="bg-card p-5 border border-rim/70 rounded-sm">
        <h2 className="font-headline text-2xl leading-tight mb-2" style={{ color: "var(--color-text)" }}>
          Signal over Noise.
        </h2>
        <p className="font-sans text-[13px] leading-relaxed mb-5" style={{ color: "var(--color-text)", opacity: 0.72 }}>
          No fluff. No distraction. Pure data streams for you - "The Gobal Audience".
          All intelligence is verified by dual-protocol consensus.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-2.5">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Enter your email"
            className="bg-base border border-rim px-4 py-2.5 font-mono text-[11px] tracking-wider focus:border-accent focus:outline-none placeholder:opacity-30"
            style={{ color: "var(--color-text)" }}
          />
          <button
            type="submit"
            className="bg-accent text-[var(--color-accent-ink)] py-2.5 font-mono text-[11px] font-bold uppercase tracking-widest hover:opacity-90 transition-opacity"
          >
            {submitted ? "Subscribed" : "Subscribe"}
          </button>
        </form>
      </div>
    </section>
  );
}
