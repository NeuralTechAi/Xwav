import { useRef, useState } from "react";
import { toast } from "sonner";
import { useAddPolicy, useDeletePolicy, usePolicies } from "@/hooks/usePolicies";
import { ComposerPermissionPicker } from "./ComposerControls";

const POLICY_NAME = "xwav_composer_tool_approval";
const POLICY_HANDLER = "omnigent.policies.builtins.safety.ask_on_os_tools";

/** Approval controls for harnesses without a live native permission switch. */
export function ComposerApprovalPicker({
  sessionId,
  disabled,
  disabledReason,
}: {
  sessionId: string;
  disabled: boolean;
  disabledReason?: string;
}) {
  const policies = usePolicies(sessionId);
  const add = useAddPolicy(sessionId);
  const remove = useDeletePolicy(sessionId);
  const changing = useRef(false);
  const [busy, setBusy] = useState(false);
  const owned =
    policies.data?.filter(
      (policy) =>
        policy.source === "session" &&
        policy.id &&
        policy.name === POLICY_NAME &&
        policy.handler === POLICY_HANDLER,
    ) ?? [];
  const asking = owned.some((policy) => policy.enabled);

  async function select(mode: string) {
    if (disabled || changing.current || !policies.data || policies.isError) return;
    changing.current = true;
    setBusy(true);
    try {
      if (mode === "ask" && !asking) {
        // Remove a disabled copy before recreating the enabled policy.
        await Promise.all(owned.map((policy) => remove.mutateAsync(policy.id!)));
        await add.mutateAsync({ name: POLICY_NAME, type: "python", handler: POLICY_HANDLER });
      } else if (mode === "default") {
        await Promise.all(owned.map((policy) => remove.mutateAsync(policy.id!)));
      }
      await policies.refetch();
    } catch {
      toast.error("Unable to change approval mode. Please try again.");
    } finally {
      changing.current = false;
      setBusy(false);
    }
  }

  return (
    <ComposerPermissionPicker
      label="Approval mode"
      value={
        policies.isError
          ? "Approvals unavailable"
          : asking
            ? "Ask before tools"
            : "Harness defaults"
      }
      selectedValue={asking ? "ask" : "default"}
      options={[
        { value: "default", label: "Harness defaults (keep other policies)" },
        { value: "ask", label: "Ask before file and command tools" },
      ]}
      loading={policies.isPending || busy}
      disabled={disabled || policies.isError}
      disabledReason={
        policies.isError ? "Unable to load approval policies. Refresh to retry." : disabledReason
      }
      onSelect={(mode) => void select(mode)}
    />
  );
}
