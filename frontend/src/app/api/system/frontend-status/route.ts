import { NextResponse } from "next/server";

// Process-start timestamp — captured once, at module load, i.e. the moment
// this server process actually came up. Reachability of this route is
// itself the signal: if the process had crashed before listening, this
// code would never run either, so "status" can only ever report "running"
// here — there is no in-process way to report "crashed" about yourself.
// Genuinely useful for a *future* incident where the app is up but
// something else regressed (e.g. a memory leak causing periodic restarts —
// process_started_at resetting on every request would reveal that); not a
// diagnostic for a process that never boots at all, which is a Railway
// Deploy Log question, not an application one.
const processStartedAt = new Date().toISOString();

export async function GET() {
  return NextResponse.json({
    status: "running",
    process_started_at: processStartedAt,
    checked_at: new Date().toISOString(),
  });
}
