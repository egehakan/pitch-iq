export function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden>
      <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.2 1.3-1.6 3.8-5.5 3.8-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.9 2.9 14.7 2 12 2 6.9 2 2.8 6.1 2.8 11.2S6.9 20.4 12 20.4c5.2 0 8.6-3.6 8.6-8.7 0-.6-.1-1-.2-1.5H12z" />
    </svg>
  );
}

export function AuthBrand() {
  return (
    <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden border-r border-line p-12 lg:flex">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.5]"
        style={{
          backgroundImage:
            "radial-gradient(60rem 30rem at 10% -10%, color-mix(in oklch, var(--accent) 12%, transparent), transparent)",
        }}
        aria-hidden
      />
      <div className="relative flex items-center gap-2">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden>
          <rect x="1.5" y="1.5" width="21" height="21" rx="5" stroke="var(--accent)" strokeWidth="1.5" />
          <circle cx="12" cy="12" r="3.4" stroke="var(--accent)" strokeWidth="1.5" />
          <path d="M12 1.5v4.1M12 18.4v4.1" stroke="var(--accent)" strokeWidth="1.5" />
        </svg>
        <span className="font-display text-base font-bold tracking-tight text-text">
          Pitch <span className="text-accent">IQ</span>
        </span>
      </div>

      <div className="relative max-w-md">
        <h2 className="font-display text-[2.6rem] font-extrabold leading-[1.04] tracking-tight text-text">
          Know more than the broadcast.
        </h2>
        <p className="mt-4 text-[15px] leading-relaxed text-muted">
          A companion that watches the knockouts with you: it reads the live data, argues with
          itself over predictions, and never makes up a scoreline.
        </p>
      </div>

      <div className="relative eyebrow">Live · Grounded · Yours</div>
    </div>
  );
}
