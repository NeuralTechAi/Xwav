import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { WorkbenchStarters } from "./WorkbenchStarters";

afterEach(cleanup);
describe("Xwav task starting points", () => {
  it.each(["Explore a codebase", "Investigate a bug", "Review changes"])(
    "provides a draft for %s",
    (name) => {
      const onPick = vi.fn();
      render(<WorkbenchStarters onPick={onPick} />);
      fireEvent.click(screen.getByRole("button", { name: new RegExp(name) }));
      expect(onPick).toHaveBeenCalledOnce();
      expect(onPick.mock.calls[0][0].length).toBeGreaterThan(50);
    },
  );
  it("keeps changes in review scope", () => {
    const onPick = vi.fn();
    render(<WorkbenchStarters onPick={onPick} />);
    fireEvent.click(screen.getByRole("button", { name: /Review changes/ }));
    expect(onPick).toHaveBeenCalledWith(
      expect.stringContaining("Do not commit, push, or open a pull request"),
    );
  });
  it("blocks draft changes while session creation is pending", () => {
    const onPick = vi.fn();
    render(<WorkbenchStarters onPick={onPick} disabled />);
    for (const button of screen.getAllByRole("button")) {
      expect(button).toBeDisabled();
      fireEvent.click(button);
    }
    expect(onPick).not.toHaveBeenCalled();
  });
});
