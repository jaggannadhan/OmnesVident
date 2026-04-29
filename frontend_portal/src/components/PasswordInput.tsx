import { useState, forwardRef } from "react";

/**
 * PasswordInput — a single-line password field with a "show/hide" eye toggle.
 * Forwards every input prop through to the underlying <input>; just wraps it
 * in a relative container and overlays an icon button on the right edge.
 */
type PasswordInputProps = React.InputHTMLAttributes<HTMLInputElement>;

function EyeIcon() {
  // Heroicons-style "eye" outline
  return (
    <svg
      width="16" height="16" viewBox="0 0 20 20" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M1.5 10C2.7 6.5 6.1 4 10 4s7.3 2.5 8.5 6c-1.2 3.5-4.6 6-8.5 6s-7.3-2.5-8.5-6Z" />
      <circle cx="10" cy="10" r="2.5" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg
      width="16" height="16" viewBox="0 0 20 20" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 3l14 14" />
      <path d="M9.5 4.07A7.6 7.6 0 0 1 10 4c3.9 0 7.3 2.5 8.5 6a8.55 8.55 0 0 1-2.9 4" />
      <path d="M6.5 6.5C4.34 7.6 2.55 9.5 1.5 12 2.7 15.5 6.1 18 10 18c1.43 0 2.8-.34 4.02-.95" />
      <path d="M8.5 8.5a2.5 2.5 0 0 0 3 3" />
    </svg>
  );
}

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  function PasswordInput({ style, ...rest }, ref) {
    const [shown, setShown] = useState(false);

    return (
      <div style={{ position: "relative", display: "flex", alignItems: "stretch" }}>
        <input
          ref={ref}
          {...rest}
          type={shown ? "text" : "password"}
          style={{ ...style, paddingRight: "36px", width: "100%" }}
        />
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          tabIndex={-1}
          aria-label={shown ? "Hide password" : "Show password"}
          title={shown ? "Hide password" : "Show password"}
          style={{
            position: "absolute",
            right: "6px",
            top: "50%",
            transform: "translateY(-50%)",
            background: "none",
            border: "none",
            padding: "5px",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            color: shown ? "#a78bfa" : "#64748b",
            cursor: "pointer",
            transition: "color 0.15s ease",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = shown ? "#c4b5fd" : "#94a3b8")}
          onMouseLeave={(e) => (e.currentTarget.style.color = shown ? "#a78bfa" : "#64748b")}
        >
          {shown ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
    );
  }
);
