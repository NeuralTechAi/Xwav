import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CommandGoalDialog } from "./CommandGoalDialog";

afterEach(cleanup);

describe("CommandGoalDialog", () => {
  it("submits a trimmed completion condition", () => {
    const onStartGoal = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <CommandGoalDialog
        open
        onOpenChange={onOpenChange}
        readOnly={false}
        onStartGoal={onStartGoal}
      />,
    );

    fireEvent.change(screen.getByTestId("goal-condition"), {
      target: { value: "  All tests pass  " },
    });
    fireEvent.click(screen.getByTestId("goal-start"));

    expect(onStartGoal).toHaveBeenCalledWith("All tests pass");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("describes the selected goal backend", () => {
    render(
      <CommandGoalDialog
        open
        onOpenChange={vi.fn()}
        readOnly={false}
        onStartGoal={vi.fn()}
        backendLabel="Codex"
      />,
    );

    expect(screen.getByText(/Codex keeps working until this condition is met/)).toBeInTheDocument();
  });

  it("edits a saved launch condition with accurate launch copy", () => {
    const save = vi.fn();
    render(
      <CommandGoalDialog
        open
        readOnly={false}
        onOpenChange={vi.fn()}
        onStartGoal={save}
        initialCondition="Existing goal"
        submitLabel="Save goal"
        description="Add a completion condition to the first task."
      />,
    );
    expect(screen.getByTestId("goal-condition")).toHaveValue("Existing goal");
    expect(screen.getByText("Add a completion condition to the first task.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Save goal" }));
    expect(save).toHaveBeenCalledWith("Existing goal");
  });

  it("rejects an empty condition", () => {
    const onStartGoal = vi.fn();
    render(
      <CommandGoalDialog open onOpenChange={vi.fn()} readOnly={false} onStartGoal={onStartGoal} />,
    );

    fireEvent.click(screen.getByTestId("goal-start"));

    expect(screen.getByText("Goal condition cannot be empty.")).toBeInTheDocument();
    expect(onStartGoal).not.toHaveBeenCalled();
  });

  it("disables editing in read-only sessions", () => {
    render(<CommandGoalDialog open onOpenChange={vi.fn()} readOnly onStartGoal={vi.fn()} />);

    expect(screen.getByTestId("goal-condition")).toBeDisabled();
    expect(screen.getByTestId("goal-start")).toBeDisabled();
  });
});
