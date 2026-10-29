import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SettingsBillingSection } from "./SettingsBillingSection";
import { authenticatedFetch } from "@/lib/identity";

vi.mock("@/lib/identity", () => ({ authenticatedFetch: vi.fn() }));
afterEach(cleanup);
const state = {
  enabled: true,
  plan: "pro",
  mode: "managed",
  model: "openai/test",
  status: "active",
  period: "2026-10",
  usage: { spent_micro_usd: 1000000, requests: 2, tokens: 3000 },
  included_micro_usd: 0,
  token_allowance: 10000000,
  request_limit: 10000,
  keys: ["openai"],
  has_gateway_token: false,
  checkout_enabled: true,
  portal_enabled: true,
  team: null,
  members: [],
  seats: 1,
  plans: [
    {
      id: "pro",
      label: "Pro",
      monthly_usd: 25,
      annual_monthly_usd: 18,
      token_limit: 10000000,
      rollover: true,
      included_micro_usd: 0,
      request_limit: 10000,
      purchasable: true,
    },
    {
      id: "teams",
      label: "Teams",
      monthly_usd: 30,
      annual_monthly_usd: 27,
      token_limit: 10000000,
      per_seat: true,
      rollover: true,
      included_micro_usd: 0,
      request_limit: 10000,
      purchasable: true,
    },
    {
      id: "scale",
      label: "Scale",
      monthly_usd: 200,
      included_credits: 1000,
      included_micro_usd: 50000000,
      request_limit: 10000,
      purchasable: true,
    },
  ],
  providers: [
    {
      id: "openai",
      label: "OpenAI",
      managed_ready: true,
      models: [
        {
          id: "test",
          free: false,
          protocol: "chat/completions",
          input_usd_per_million: 1,
          output_usd_per_million: 2,
        },
      ],
    },
  ],
};
beforeEach(() => {
  vi.mocked(authenticatedFetch).mockReset();
  vi.mocked(authenticatedFetch).mockImplementation(
    async (_url, options) =>
      new Response(
        JSON.stringify(options?.method && options.method !== "GET" ? { saved: true } : state),
        { status: 200 },
      ),
  );
});
it("shows supplied prices, monthly tokens, rollover, annual totals and credit tiers", async () => {
  render(<SettingsBillingSection />);
  await screen.findByText("Current plan: Pro · active");
  expect(screen.getByText(/3,000 \/ 10,000,000 tokens/)).toBeInTheDocument();
  expect(screen.getByText("1,000 credits / month")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox"));
  expect(screen.getByText("$216 billed annually.")).toBeInTheDocument();
  expect(screen.getByText("$324 per member billed annually.")).toBeInTheDocument();
});
it("saves BYOK without retaining the key in its input", async () => {
  render(<SettingsBillingSection />);
  await screen.findByText("Current plan: Pro · active");
  fireEvent.change(screen.getByLabelText("Key provider"), { target: { value: "openai" } });
  fireEvent.change(screen.getByLabelText("Provider API key"), {
    target: { value: "private-test-key" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save key" }));
  await waitFor(() =>
    expect(authenticatedFetch).toHaveBeenCalledWith(
      "/v1/billing/keys/openai",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ key: "private-test-key" }) }),
    ),
  );
  expect(screen.getByLabelText("Provider API key")).toHaveValue("");
  expect(await screen.findByText("Provider key saved.")).toBeInTheDocument();
});
it("explains missing operator configuration without presenting working checkout", async () => {
  vi.mocked(authenticatedFetch).mockResolvedValue(
    new Response(JSON.stringify({ enabled: false, message: "Configure Stripe and providers" })),
  );
  render(<SettingsBillingSection />);
  expect(await screen.findByText("Configure Stripe and providers")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Choose plan" })).not.toBeInTheDocument();
});

it("lists the configured Auto pool and hides it for a concrete model", async () => {
  const freeState = {
    ...state,
    free_failover: true,
    mode: "free",
    model: "free-gateway/auto",
    providers: [
      {
        id: "free-gateway",
        label: "FreeLLMAPI",
        managed_ready: true,
        models: [
          { id: "auto", free: true, auto_candidates: ["qwen-new", "gpt-oss-large"] },
          { id: "qwen-new", free: true },
          { id: "gpt-oss-large", free: true },
        ],
      },
    ],
  };
  vi.mocked(authenticatedFetch).mockResolvedValue(new Response(JSON.stringify(freeState)));
  render(<SettingsBillingSection />);
  const pool = await screen.findByLabelText("Auto model pool");
  expect(pool).toHaveTextContent("qwen-new");
  expect(pool).toHaveTextContent("gpt-oss-large");
  expect(pool).toHaveTextContent("one model per request");
  expect(screen.getByText(/Automatic Free failover is on/)).toBeVisible();
  fireEvent.change(screen.getByLabelText("Provider and model"), {
    target: { value: "free-gateway/qwen-new" },
  });
  expect(screen.queryByLabelText("Auto model pool")).not.toBeInTheDocument();
});
