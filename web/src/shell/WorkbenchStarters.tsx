import { ArrowUpRightIcon, BugIcon, GitPullRequestIcon, ScanSearchIcon } from "lucide-react";

const starters = [
  {
    title: "Explore a codebase",
    description: "Find the architecture and the next step",
    icon: ScanSearchIcon,
    prompt:
      "Explore this repository. Explain its architecture, the main entry points, and how to run its tests. Make no changes yet.",
  },
  {
    title: "Investigate a bug",
    description: "Trace the failure before changing code",
    icon: BugIcon,
    prompt:
      "Help me investigate a bug in this repository. First inspect the project and ask me for the failing behavior or test before making changes.",
  },
  {
    title: "Review changes",
    description: "Inspect the diff and prepare for review",
    icon: GitPullRequestIcon,
    prompt:
      "Review the current Git diff for correctness, security, and missing tests. Summarize findings by severity. Do not commit, push, or open a pull request.",
  },
];

/** Draft-only shortcuts: choosing a starting point never submits a session. */
export function WorkbenchStarters({
  onPick,
  disabled = false,
}: {
  onPick: (prompt: string) => void;
  disabled?: boolean;
}) {
  return (
    <section className="xwav-starters" aria-label="Task starting points">
      <div className="xwav-section-label">
        <span>A place to start</span>
        <span>YOUR NEXT MOVE</span>
      </div>
      <div className="xwav-starter-grid">
        {starters.map(({ title, description, icon: Icon, prompt }) => (
          <button
            key={title}
            type="button"
            disabled={disabled}
            onClick={() => onPick(prompt)}
            className="xwav-starter"
          >
            <span className="xwav-starter-icon">
              <Icon className="size-5" />
            </span>
            <span className="min-w-0">
              <strong>{title}</strong>
              <span className="xwav-starter-description">{description}</span>
            </span>
            <ArrowUpRightIcon className="xwav-starter-arrow size-4" aria-hidden="true" />
          </button>
        ))}
      </div>
    </section>
  );
}
