import { useRef, useState } from "react";
import { WrenchIcon } from "lucide-react";
import { Link } from "@/lib/routing";
import { postEvent } from "@/lib/sessionsApi";

const LABELS = {
  preproduction: "Pre-Production Tests",
  loadtesting: "Load Testing",
  penetration: "Penetration Test",
  releases: "Build and deployment",
};

export function FixDashboardIssues({
  sessionId,
  kind,
  runId,
  disabled = false,
}: {
  sessionId: string | null;
  kind: keyof typeof LABELS;
  runId?: string;
  disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const stableId = useRef(crypto.randomUUID().replaceAll("-", ""));
  async function send() {
    if (!sessionId || inFlight.current || sent) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await postEvent(sessionId, {
        type: "message",
        data: {
          role: "user",
          stable_id: stableId.current,
          content: [
            {
              type: "input_text",
              text:
                `Check the ${LABELS[kind]} dashboard for this job${runId ? ` (run ${runId})` : ""}. ` +
                "Use its actual report, identify the root causes and fix all actionable issues. " +
                "If the attached report is a different run, explain that before proceeding. " +
                "Rerun relevant checks to verify the fixes and show progress and code changes here. " +
                "Report missing credentials, licences or unavailable services as blockers. " +
                "Do not weaken checks or publish a release without my approval.",
            },
          ],
        },
      });
      if (result.denied) throw new Error("This job’s policy did not allow the repair request.");
      setSent(true);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not send. Try again.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <button
        type="button"
        disabled={!sessionId || disabled || busy || sent}
        title="Send this dashboard’s issues to the job’s agent for diagnosis, fixes and verification"
        onClick={() => void send()}
      >
        <WrenchIcon size={15} /> {busy ? "Sending…" : sent ? "Sent to job" : "Fix issues"}
      </button>
      {sent && sessionId && (
        <Link to={`/c/${encodeURIComponent(sessionId)}`}>View repair in job</Link>
      )}
      {error && <span role="alert">{error}</span>}
    </>
  );
}
