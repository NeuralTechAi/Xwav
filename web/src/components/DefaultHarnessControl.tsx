import { useId, useState } from "react";
import { NATIVE_CODING_AGENTS } from "@/lib/nativeCodingAgents";
import { readDefaultChatHarness, writeDefaultChatHarness } from "@/lib/defaultHarnessPreferences";

export function DefaultHarnessControl() {
  const id = useId();
  const [value, setValue] = useState(readDefaultChatHarness);
  const [notice, setNotice] = useState("");
  return (
    <div className="space-y-2" data-testid="default-harness-control">
      <label htmlFor={id} className="block text-sm font-semibold">
        Default chat harness
      </label>
      <p id={`${id}-description`} className="text-ui text-muted-foreground">
        Used for new jobs in this browser. Project defaults and session choices take precedence.
        Harness² is a separate benchmark workflow.
      </p>
      <select
        id={id}
        aria-describedby={`${id}-description`}
        value={value ?? ""}
        className="h-11 w-full max-w-sm md:h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-ring"
        onChange={(event) => {
          const next = event.currentTarget.value || null;
          if (writeDefaultChatHarness(next)) {
            setValue(next);
            setNotice(next ? "Default harness saved." : "Using automatic harness selection.");
          } else
            setNotice(
              "Could not save the default harness. Check browser storage permissions and try again.",
            );
        }}
      >
        <option value="">Automatic (remember last choice)</option>
        {[...NATIVE_CODING_AGENTS]
          .sort((a, b) => a.sortRank - b.sortRank)
          .map((agent) => (
            <option value={agent.harness} key={agent.harness}>
              {agent.displayName}
            </option>
          ))}
      </select>
      <p role="status" className="text-ui">
        {notice}
      </p>
    </div>
  );
}
