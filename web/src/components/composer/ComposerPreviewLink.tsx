import { GaugeIcon, ShieldCheckIcon, RocketIcon, PackageCheckIcon } from "lucide-react";
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
        title="Open a separate live preview tab for this job. Web, Android and iOS previews keep updating while you work."
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
        title="Open Pre-Production Tests in a new page: run available test suites, security, static analysis and accessibility checks, and download the results."
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
        title="Open Load Testing in a new page: measure load, stress, spike and endurance against this job’s app with controlled traffic, live metrics and downloadable results."
        className="inline-flex size-8 items-center justify-center rounded-md text-primary hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring"
        data-testid="composer-loadtesting-link"
      >
        <GaugeIcon className="size-5" />
      </Link>
      {(
        [
          [
            "deployments",
            "Deployments",
            RocketIcon,
            "Build and deploy web, Android or iOS apps. Choose a web provider or use your configured store workflow.",
          ],
          [
            "installables",
            "Installable downloads",
            PackageCheckIcon,
            "Build and download Windows, Android or signed iOS app packages. Platform tools and signing may be required.",
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
