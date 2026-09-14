"use client";

// App Router's root error boundary — catches otherwise-uncaught React
// rendering errors anywhere below the root layout (it replaces <html>/<body>
// entirely while active, which is why it must define both itself). This
// only fires for errors thrown AFTER the Next.js server process is already
// up and rendering — it cannot catch a process crash that happens before
// the app starts (Railway's own edge returns its own 404 for that case,
// with no app code involved at all).
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body>
        <main
          style={{
            display: "flex",
            minHeight: "100vh",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            textAlign: "center",
            padding: "1rem",
          }}
        >
          <h1 style={{ fontSize: "1.25rem", fontWeight: 600 }}>Something went wrong</h1>
          <p style={{ fontSize: "0.875rem", color: "#71717a" }}>
            {error.digest ? `Error reference: ${error.digest}` : "Please try again."}
          </p>
          <button
            onClick={() => reset()}
            style={{
              borderRadius: "0.375rem",
              border: "1px solid #e4e4e7",
              padding: "0.5rem 1rem",
              fontSize: "0.875rem",
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
