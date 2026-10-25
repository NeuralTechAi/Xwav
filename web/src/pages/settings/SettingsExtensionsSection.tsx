import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BlocksIcon, BotIcon, BookOpenIcon, PlugIcon, UploadIcon, WrenchIcon } from "lucide-react";
import { Link, useNavigate } from "@/lib/routing";
import { useServerInfo } from "@/lib/CapabilitiesContext";
import { customAgentsSettingsEnabled } from "@/lib/capabilities";
import { installAgentBundle } from "@/lib/agentsApi";
import { Button } from "@/components/ui/button";

/** Reuses the validated agent installer and each harness's existing inventory. */
export function SettingsExtensionsSection() {
  const info = useServerInfo();
  const enabled = customAgentsSettingsEnabled(info);
  const navigate = useNavigate();
  const client = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function install(file?: File) {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const agent = await installAgentBundle(file);
      await Promise.all(
        [
          "settings-agents",
          "available-agents",
          "available-agents-user",
          "available-agents-catalog",
        ].map((key) => client.invalidateQueries({ queryKey: [key] })),
      );
      navigate(`/settings/custom-agents/${encodeURIComponent(agent.id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Skills, tools &amp; plugins</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Extend Xwav with reusable skills, MCP tools, custom agents and harness plugins. Configure
          once, then choose your agent when starting a New Job.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[
          {
            icon: BookOpenIcon,
            title: "Skills",
            text: "Attach SKILL.md files when creating an agent, or import a bundle containing skills and supporting files. Describe your task and the agent selects relevant skills automatically. Use / to choose one explicitly.",
            to: "/settings/custom-agents/new",
            action: "Add skills to an agent",
          },
          {
            icon: PlugIcon,
            title: "MCP servers",
            text: "Add HTTP or stdio servers, headers and environment variables to a custom agent. The runtime exposes their tools to that agent. Registered account connections live in MCP settings.",
            to: "/settings/custom-agents/new",
            action: "Configure MCP tools",
          },
          {
            icon: BotIcon,
            title: "Agents",
            text: "Create and save an agent with its own instructions, model, skills and MCP servers. Select it in New Job. Edit or remove your agents in Custom agents.",
            to: "/settings/custom-agents",
            action: "Manage agents",
          },
          {
            icon: BlocksIcon,
            title: "Harness plugins",
            text: "Installed Claude plugins and supported Codex plugin skills are discovered from the connected host. Open a harness to inspect its Skills, MCP servers and Plugins tabs. Plugins remain specific to their harness and host.",
            to: "/settings/harnesses",
            action: "Browse installed integrations",
          },
        ].map(({ icon: Icon, title, text, to, action }) => (
          <section key={title} className="flex flex-col gap-3 rounded-xl border border-border p-4">
            <h2 className="flex items-center gap-2 font-semibold">
              <Icon className="size-5" aria-hidden />
              {title}
            </h2>
            <p className="flex-1 text-sm text-muted-foreground">{text}</p>
            {enabled || title === "Harness plugins" ? (
              <Button asChild variant="outline">
                <Link
                  to={to}
                  componentId={`settings.extensions.${title.toLowerCase().replaceAll(" ", "_")}`}
                >
                  {action}
                </Link>
              </Button>
            ) : (
              <p className="text-sm">Agent management is unavailable on this server.</p>
            )}
          </section>
        ))}
      </div>
      <section className="space-y-3 rounded-xl border border-border p-4">
        <h2 className="flex items-center gap-2 font-semibold">
          <WrenchIcon className="size-5" aria-hidden />
          Import an integration bundle
        </h2>
        <p className="text-sm text-muted-foreground">
          Import an Xwav agent .tar.gz containing config.yaml, optional AGENTS.md,
          skills/&lt;name&gt;/SKILL.md and MCP tool declarations. Use a new agent name to keep
          existing configurations; importing the same name replaces your saved agent. Validation
          errors appear here without starting a job.
        </p>
        <input
          ref={input}
          className="hidden"
          type="file"
          aria-label="Integration bundle"
          accept=".tar.gz,.tgz,application/gzip"
          disabled={busy || !enabled}
          onChange={(event) => void install(event.target.files?.[0])}
        />
        <Button
          variant="outline"
          disabled={busy || !enabled}
          onClick={() => input.current?.click()}
        >
          <UploadIcon className="size-4" />
          {busy ? "Importing…" : "Import bundle"}
        </Button>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </section>
      <details className="rounded-xl border border-border p-4">
        <summary className="cursor-pointer font-medium">
          Plugin installation and project scope
        </summary>
        <div className="mt-3 space-y-3 text-sm text-muted-foreground">
          <p>
            Install Claude plugins with the Claude CLI on the host or inside the job sandbox where
            the agent runs: <code>claude plugin install plugin-name@marketplace</code>. Enable them
            there and open a new job with that harness. Use Codex’s plugin installation flow for
            Codex plugins. Refresh the harness inventory after installation.
          </p>
          <p>
            Local host integrations do not automatically appear in separate Docker sandboxes. For
            portable skills and MCP tools, save them in an agent bundle and select that agent for
            each new job. Stdio tools must be installed in the job’s environment.
          </p>
          <p>
            Custom tools connect through MCP. Server UI extension packages use the separate
            administrator-installed extension system; arbitrary Python server plugins cannot be
            uploaded as agent bundles.
          </p>
        </div>
      </details>
    </div>
  );
}
