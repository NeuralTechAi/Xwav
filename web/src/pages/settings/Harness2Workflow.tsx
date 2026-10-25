import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FlaskConicalIcon } from "lucide-react";
import { Link } from "@/lib/routing";
import { authenticatedFetch } from "@/lib/identity";
import { copyText } from "@/lib/clipboard";
import { Button } from "@/components/ui/button";
import { BackButton } from "./HarnessCatalog";

export const HARNESS2_DESCRIPTION =
  "Google’s benchmark optimization harness. Run, evaluate, and improve agent workflows.";

export function useHarness2Status() {
  return useQuery({
    queryKey: ["harness2-status"],
    queryFn: async (): Promise<{ installed: boolean; pinned: boolean; version: string | null }> => {
      const response = await authenticatedFetch("/v1/harnesses/harness2/status");
      if (!response.ok) throw new Error("Could not check the benchmark runtime");
      return response.json();
    },
    staleTime: 30_000,
    retry: false,
  });
}

export function Harness2Card({ status }: { status: ReturnType<typeof useHarness2Status> }) {
  return (
    <Link
      to="/settings/harnesses/harness2"
      data-testid="harness-card-harness2"
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
    >
      <div className="flex items-center gap-2 font-semibold">
        <FlaskConicalIcon className="size-5" />
        Google Harness²
      </div>
      <p className="text-ui text-muted-foreground">{HARNESS2_DESCRIPTION}</p>
      <div className="text-xs font-medium text-primary">
        Benchmark workflow ·{" "}
        {status.isPending
          ? "Checking server runtime…"
          : status.isError
            ? "Status unavailable"
            : status.data?.pinned
              ? "Configured on this server"
              : "Setup required on this server"}
      </div>
    </Link>
  );
}

export function Harness2Workflow({ status }: { status: ReturnType<typeof useHarness2Status> }) {
  const [copyNotice, setCopyNotice] = useState("");
  const copyCommand = async (command: string) => {
    try {
      await copyText(command);
      setCopyNotice(`Copied ${command}`);
    } catch {
      setCopyNotice("Copy unavailable. Select the command and copy it manually.");
    }
  };
  return (
    <div className="space-y-6" data-testid="harness2-workflow">
      <BackButton label="Harnesses" to="/settings/harnesses" />
      <div className="space-y-2">
        <h1 className="settings-page-title text-2xl font-semibold">Google Harness²</h1>
        <p className="text-base text-muted-foreground">{HARNESS2_DESCRIPTION}</p>
        <p className="text-ui">
          Primary benchmark workflow. Chat sessions use a separate interactive harness.
        </p>
      </div>
      <section
        className="space-y-3 rounded-xl border border-border bg-card p-5"
        aria-label="Benchmark runtime"
      >
        <h2 className="font-semibold">Runtime on this server</h2>
        <p role="status">
          {status.isPending
            ? "Checking runtime…"
            : status.isError
              ? "Runtime status unavailable. Retry or check from the terminal."
              : status.data?.pinned
                ? `Configured · version ${status.data.version}`
                : status.data?.installed
                  ? "Installed runtime differs from the reviewed revision. Run the status command for setup instructions."
                  : "Optional runtime is not installed. Run the status command for setup instructions."}
        </p>
        <Button
          variant="outline"
          onClick={() => void status.refetch()}
          disabled={status.isFetching}
        >
          Refresh status
        </Button>
        <p className="text-ui text-muted-foreground">
          This status describes the Xwav server, independently of the selected chat host. Run the
          commands below in a terminal on the machine where you want to benchmark, with the Xwav
          environment activated.
        </p>
      </section>
      <section className="space-y-3" aria-label="Benchmark commands">
        <h2 className="font-semibold">Start a benchmark</h2>
        <p className="text-ui text-muted-foreground">
          The demo runs locally without model credentials. A full sweep requires benchmark
          configuration and may incur model costs.
        </p>
        {[
          ["Check installation", "xwav harness2 status"],
          ["Run the local demo", "xwav harness2 demo"],
          ["Configure a benchmark sweep", "xwav harness2 run --help"],
          ["Inspect benchmark reports", "xwav harness2 report --help"],
        ].map(([label, command]) => (
          <div
            key={command}
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-4"
          >
            <div className="min-w-0 space-y-1">
              <div className="text-sm font-medium">{label}</div>
              <code className="select-text break-all text-sm">{command}</code>
            </div>
            <Button
              variant="outline"
              size="sm"
              aria-label={`Copy ${command}`}
              onClick={() => void copyCommand(command)}
            >
              Copy command
            </Button>
          </div>
        ))}
        <p role="status" className="text-ui">
          {copyNotice}
        </p>
        <a
          className="text-link underline"
          href="https://github.com/google-research/harness2"
          target="_blank"
          rel="noreferrer"
        >
          Google Harness² documentation
        </a>
      </section>
    </div>
  );
}
