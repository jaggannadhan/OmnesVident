import { Link } from "react-router-dom";
import { AppFooter } from "./AppFooter";

// Privacy Policy — reflects our actual data practices: an account system
// (email + hashed password), an API-key tier system with rate-limit logs,
// localStorage for theme + auth token, and third-party news aggregation.
// No analytics, no ads, no data brokers.

const LAST_UPDATED = "May 2026";
const CONTACT = "jegsirox@gmail.com";

export function PrivacyPolicyPage() {
  return (
    <div className="flex flex-col min-h-screen bg-base">

      {/* Slim top bar — brand only, no filter controls */}
      <header className="sticky top-0 z-50 bg-base/80 backdrop-blur-xl border-b border-rim">
        <div className="max-w-[1440px] mx-auto px-6 py-4 flex justify-between items-center gap-6">
          <Link to="/" className="flex items-center gap-2.5 shrink-0" style={{ color: "var(--color-text)", cursor: "pointer" }}>
            <span
              className="font-headline text-3xl font-bold tracking-tighter leading-none"
              style={{ cursor: "pointer" }}
            >
              <span className="hover:text-accent transition-colors" style={{ cursor: "pointer" }}>Omnes</span>
              <span className="hover:text-accent transition-colors" style={{ cursor: "pointer" }}>Vident</span>
            </span>
            <img
              src="/favicon.png"
              alt=""
              aria-hidden="true"
              className="w-9 h-9 object-contain"
              style={{ cursor: "pointer" }}
            />
          </Link>
          <Link
            to="/"
            className="font-mono text-[10px] uppercase tracking-widest hover:text-accent transition-colors"
            style={{ color: "var(--color-text)", opacity: 0.7 }}
          >
            ← Back to Feed
          </Link>
        </div>
      </header>

      <main className="flex-grow w-full max-w-3xl mx-auto px-6 py-12">

        <div className="mb-10">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] mb-3" style={{ color: "var(--color-text)", opacity: 0.55 }}>
            LEGAL PROTOCOLS
          </p>
          <h1 className="font-headline text-5xl font-bold tracking-tight" style={{ color: "var(--color-text)" }}>
            Privacy Policy
          </h1>
          <p className="font-mono text-[10px] uppercase tracking-widest mt-4" style={{ color: "var(--color-text)", opacity: 0.5 }}>
            Last updated: {LAST_UPDATED}
          </p>
        </div>

        <div className="flex flex-col gap-10 font-sans text-[14px] leading-relaxed" style={{ color: "var(--color-text)" }}>

          <Section title="1. Who We Are">
            <p>
              OmnesVident ("we", "us", "our") operates a global news discovery
              platform that aggregates publicly available headlines from
              third-party news providers. This Privacy Policy describes what
              information we collect, how we use it, and what choices you have.
            </p>
            <p>
              We are a small, independent operator. You can reach us about
              anything in this policy at{" "}
              <a href={`mailto:${CONTACT}`} className="text-accent hover:underline">
                {CONTACT}
              </a>.
            </p>
          </Section>

          <Section title="2. Information We Collect">
            <p>The information we hold falls into three buckets:</p>
            <ul className="list-disc list-outside pl-6 flex flex-col gap-2">
              <li>
                <strong>Account information.</strong> If you create an account
                we collect your email address, a one-way hashed password, and
                the access tier(s) associated with your account (e.g. basic,
                premium, super_user). Passwords are never stored in plain text
                and never leave our systems.
              </li>
              <li>
                <strong>API usage.</strong> When you use our public REST API we
                log request counts, timestamps, and the response status code
                tied to your API key. We use these logs to enforce rate limits,
                bill premium tiers, and detect abuse. We do not log request
                bodies or response payloads.
              </li>
              <li>
                <strong>Local browser storage.</strong> We use{" "}
                <code className="font-mono text-accent text-[12px]">localStorage</code>{" "}
                on your device to remember your theme preference (light /
                dark) and to keep you signed in between visits. None of this
                leaves your browser unless you make an authenticated request.
              </li>
            </ul>
            <p>
              We do <strong>not</strong> collect IP-based geolocation, set
              advertising identifiers, run behavioural analytics, or load
              third-party tracking scripts. There is no Google Analytics, no
              Meta Pixel, no Hotjar.
            </p>
          </Section>

          <Section title="3. How We Use Your Information">
            <ul className="list-disc list-outside pl-6 flex flex-col gap-2">
              <li>To authenticate you when you sign in.</li>
              <li>To send transactional email — password resets, account verification, and security notices.</li>
              <li>To enforce per-tier API rate limits and respond to abuse.</li>
              <li>To debug, operate, and improve the service.</li>
            </ul>
            <p>
              We do not sell, rent, or trade your personal information. We do
              not show you ads. We do not build advertising profiles.
            </p>
          </Section>

          <Section title="4. Where Our News Content Comes From">
            <p>
              OmnesVident is an aggregator. The headlines, snippets, and
              source attributions you see in the feed are retrieved from
              public news APIs and RSS feeds, including NewsData.io, WorldNews
              API, Mediastack, NewsCatcher, GNews, Currents API, Reddit, and a
              curated list of verified RSS sources. We display only headlines
              and short excerpts; clicking a story opens the full article on
              the original publisher's site.
            </p>
            <p>
              When you leave OmnesVident by clicking through to a publisher,
              you become subject to that publisher's own privacy practices.
              We have no control over how third-party sites handle your data.
            </p>
          </Section>

          <Section title="5. Storage and Security">
            <p>
              Account data is stored in Google Cloud Firestore (US region),
              with a local SQLite database used during development. All
              traffic between your browser and our servers is encrypted in
              transit over HTTPS. Passwords are hashed with industry-standard
              algorithms before storage.
            </p>
            <p>
              No system is perfectly secure. If we ever become aware of a
              breach that affects your data, we will notify affected users
              without unreasonable delay and as required by applicable law.
            </p>
          </Section>

          <Section title="6. Data Retention">
            <p>
              We keep your account information for as long as your account is
              active. API usage logs are retained for up to 90 days for
              rate-limiting and abuse-detection purposes, after which they are
              aggregated into anonymous statistics or deleted.
            </p>
            <p>
              When you delete your account, we remove your personal data
              within 30 days, except where retention is required by law (for
              example, financial records related to paid tiers).
            </p>
          </Section>

          <Section title="7. Your Rights">
            <p>Depending on your jurisdiction, you may have the right to:</p>
            <ul className="list-disc list-outside pl-6 flex flex-col gap-2">
              <li>Access the personal information we hold about you.</li>
              <li>Correct information that is inaccurate or incomplete.</li>
              <li>Delete your account and the associated personal data.</li>
              <li>Export your data in a portable format.</li>
              <li>Object to or restrict certain types of processing.</li>
              <li>Withdraw consent at any time, where processing is based on consent.</li>
            </ul>
            <p>
              To exercise any of these rights, email us at{" "}
              <a href={`mailto:${CONTACT}`} className="text-accent hover:underline">
                {CONTACT}
              </a>.
              We will respond within 30 days.
            </p>
          </Section>

          <Section title="8. Children">
            <p>
              OmnesVident is not directed at children under 13, and we do not
              knowingly collect personal information from them. If you believe
              a child has provided us with personal information, please contact
              us and we will delete it.
            </p>
          </Section>

          <Section title="9. International Users">
            <p>
              OmnesVident is operated from the United States and stores data on
              servers located in the United States. If you access the service
              from outside the U.S., your information will be transferred to,
              stored, and processed in the U.S. By using the service you
              acknowledge this transfer.
            </p>
          </Section>

          <Section title="10. Changes to This Policy">
            <p>
              We may revise this policy from time to time. When we make
              material changes, we will update the "Last updated" date above
              and, where appropriate, notify registered users by email.
              Continued use of the service after a revision constitutes
              acceptance of the updated policy.
            </p>
          </Section>

          <Section title="11. Contact">
            <p>
              Questions, requests, or concerns about this policy or your data?
              Email{" "}
              <a href={`mailto:${CONTACT}`} className="text-accent hover:underline">
                {CONTACT}
              </a>.
            </p>
          </Section>

        </div>
      </main>

      <AppFooter />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-headline text-2xl font-semibold tracking-tight" style={{ color: "var(--color-text)" }}>
        {title}
      </h2>
      <div className="flex flex-col gap-3" style={{ opacity: 0.85 }}>
        {children}
      </div>
    </section>
  );
}
