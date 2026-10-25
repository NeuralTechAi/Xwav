import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it } from "vitest";
import { ComposerPreviewLink } from "./ComposerPreviewLink";

afterEach(cleanup);
it("opens a separate tab pinned to this job without exposing its opener", () => {
  render(
    <MemoryRouter>
      <ComposerPreviewLink sessionId="job-a" project="Project A" />
    </MemoryRouter>,
  );
  const link = screen.getByRole("link", { name: "Preview this job’s app" });
  expect(link).toHaveAttribute("href", "/preview?session=job-a");
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
  expect(link).toHaveAttribute("title", expect.stringContaining("separate live preview tab"));
});
it("preserves project context before the job exists", () => {
  render(
    <MemoryRouter>
      <ComposerPreviewLink project="Project A" />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: "Load Testing" })).toHaveAttribute(
    "href",
    "/loadtesting?project=Project+A",
  );
  expect(screen.getByRole("link", { name: "Preview this job’s app" })).toHaveAttribute(
    "href",
    "/preview?project=Project+A",
  );
});

it("places the test dashboard icon after Preview and preserves new-page job context", () => {
  render(
    <MemoryRouter>
      <ComposerPreviewLink sessionId="job-a" />
    </MemoryRouter>,
  );
  const links = screen.getAllByRole("link");
  expect(links[2]).toHaveAccessibleName("Load Testing");
  expect(links[2]).toHaveAttribute("href", "/loadtesting?session=job-a");
  expect(links[2]).toHaveAttribute("target", "_blank");
  expect(links[2]).toHaveAttribute("rel", "noopener noreferrer");
  expect(links[2]).toHaveAttribute("title", expect.stringContaining("endurance"));
  expect(links[1]).toHaveAccessibleName("Pre-Production Tests");
  expect(links[1]).toHaveAttribute("href", "/preproduction?session=job-a");
  expect(links[1]).toHaveAttribute("target", "_blank");
  expect(links[1]).toHaveAttribute("rel", "noopener noreferrer");
  expect(links[1]).toHaveAttribute("title", expect.stringContaining("accessibility"));
});

it("places deployment and installer icons after Load Testing in separate job tabs", () => {
  render(
    <MemoryRouter>
      <ComposerPreviewLink sessionId="job-a" />
    </MemoryRouter>,
  );
  const links = screen.getAllByRole("link");
  expect(links[3]).toHaveAccessibleName("Deployments");
  expect(links[4]).toHaveAccessibleName("Installable downloads");
  for (const [index, path] of [
    [3, "deployments"],
    [4, "installables"],
  ] as const) {
    expect(links[index]).toHaveAttribute("href", `/${path}?session=job-a`);
    expect(links[index]).toHaveAttribute("target", "_blank");
    expect(links[index]).toHaveAttribute("rel", "noopener noreferrer");
    expect(links[index]).toHaveAttribute("title", expect.any(String));
  }
});
