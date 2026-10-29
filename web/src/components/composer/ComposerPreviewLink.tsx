import {
  GaugeIcon,
  ShieldCheckIcon,
  RocketIcon,
  PackageCheckIcon,
  ScanLineIcon,
} from "lucide-react";
import { Link } from "@/lib/routing";
import { PeriscopeIcon } from "@/components/icons/PeriscopeIcon";

export function ComposerPreviewLink({
  sessionId,
  project,
}: {
  sessionId?: string | null;
  project?: string | null;
}) {
  const params = new URLSearchParams();
  if (sessionId) params.set("session", sessionId);
  else if (project) params.set("project", project);
  return (
    <div className="flex w-full items-center px-4 pb-1">
      <Link
        to={`/preview${params.size ? `?${params}` : ""}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Preview this job’s app"
        title="Open a separate live preview tab for this job’s Web, Android and iOS app."
        className="inline-flex size-8 items-center justify-center rounded-md text-primary hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring"
        data-testid="composer-preview-link"
      >
        <PeriscopeIcon className="size-5" />
      </Link>
      <Link
        to={`/preproduction${params.size ? `?${params}` : ""}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Pre-Production Tests"
        title="Run test suites, security and accessibility checks in a new page; download the results."
        className="inline-flex size-8 items-center justify-center rounded-md text-primary hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring"
        data-testid="composer-preproduction-link"
      >
        <ShieldCheckIcon className="size-5" />
      </Link>
      <Link
        to={`/loadtesting${params.size ? `?${params}` : ""}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Load Testing"
        title="Measure load, stress, spikes and endurance in a new page; view and download results."
        className="inline-flex size-8 items-center justify-center rounded-md text-primary hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring"
        data-testid="composer-loadtesting-link"
      >
        <GaugeIcon className="size-5" />
      </Link>
      {(
        [
          [
            "penetration",
            "Penetration Test",
            ScanLineIcon,
            "Scan this project with Strix; review findings and download the report.",
          ],
          [
            "deployments",
            "Deployments",
            RocketIcon,
            "Build and deploy this app to your chosen web or mobile platform.",
          ],
          [
            "installables",
            "Installable downloads",
            PackageCheckIcon,
            "Build and download a Windows, Android or signed iOS app package.",
          ],
        ] as const
      ).map(([path, label, Icon, title]) => (
        <Link
          key={path}
          to={`/${path}${params.size ? `?${params}` : ""}`}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={label}
          title={title}
          className="inline-flex size-8 items-center justify-center rounded-md text-primary hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring"
          data-testid={`composer-${path}-link`}
        >
          <Icon className="size-5" />
        </Link>
      ))}
    </div>
  );
}
