import { useState } from "react";
import { Button } from "@/components/ui/button";
import { OnboardingBackButton, OnboardingHeading } from "./primitives";

export function CliInstallStep({
  onBack,
  onRecheck,
  onConnectAnyway,
}: {
  onBack: () => void;
  onRecheck?: () => Promise<boolean>;
  onConnectAnyway?: () => void;
}) {
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string>();
  const recheck = async () => {
    setChecking(true);
    setError(undefined);
    try {
      if (!(await onRecheck?.())) {
        setError("Xwav CLI not found. Make sure xwav is on your PATH, then check again.");
      }
    } catch {
      setError("Could not check for the Xwav CLI. Please try again.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-4 px-2 pb-1 pt-8">
      <OnboardingHeading>Install the Xwav CLI</OnboardingHeading>
      <p className="text-base text-muted-foreground">
        Automatic installation is unavailable on this platform. Follow the installation instructions
        for your operating system, then return here and check again.
      </p>
      <Button asChild variant="outline">
        <a
          href="https://github.com/NeuralTechAi/Xwav#run-this-fork-locally"
          target="_blank"
          rel="noreferrer"
        >
          Installation instructions
        </a>
      </Button>
      <p className="text-sm text-muted-foreground">
        Check that <code>xwav --version</code> works in a new terminal.
      </p>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="mt-auto flex justify-between gap-2">
        <OnboardingBackButton onClick={onBack} />
        {onConnectAnyway && (
          <Button variant="outline" onClick={onConnectAnyway}>
            Continue anyway
          </Button>
        )}
        <Button loading={checking} disabled={!onRecheck} onClick={recheck}>
          Check again
        </Button>
      </div>
    </div>
  );
}
