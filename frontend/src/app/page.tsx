"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth/auth-context";

// Deploy-freshness marker — no functional purpose, only so a build can be
// confirmed live (via view-source or browser console) without relying on
// HTTP caching headers/etags, which is what made the last stuck deploy hard
// to tell apart from a slow one. Bump the literal string on any change that
// needs to be independently verifiable this way.
const BUILD_MARKER = "nexara-build-2026-09-14T01";

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    console.log("BUILD_MARKER:", BUILD_MARKER);
    if (isLoading) return;
    router.replace(isAuthenticated ? "/dashboard" : "/login");
  }, [isLoading, isAuthenticated, router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background">
      <p className="text-sm text-muted-foreground">Loading Nexara…</p>
    </main>
  );
}
