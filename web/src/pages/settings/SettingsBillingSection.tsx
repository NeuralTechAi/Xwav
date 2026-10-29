import { useEffect, useState } from "react";
import { CreditCardIcon, KeyRoundIcon, RefreshCwIcon, DownloadIcon } from "lucide-react";
import { authenticatedFetch } from "@/lib/identity";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Plan {
  id: string;
  label: string;
  monthly_usd: number;
  included_micro_usd: number;
  request_limit: number;
  purchasable: boolean;
  token_limit: number;
  rollover: boolean;
  annual_monthly_usd: number | null;
  per_seat: boolean;
  included_credits: number | null;
}
interface Model {
  id: string;
  label?: string;
  auto_candidates?: string[];
  free: boolean;
  protocol: string;
  input_usd_per_million: number;
  output_usd_per_million: number;
}
interface Provider {
  id: string;
  label: string;
  managed_ready: boolean;
  models: Model[];
}
interface Status {
  enabled: boolean;
  free_failover?: boolean;
  message?: string;
  plan: string;
  mode: string;
  model: string;
  status: string;
  period: string;
  usage: { spent_micro_usd: number; requests: number; tokens: number };
  token_allowance: number;
  included_credits: number | null;
  credits_used: number | null;
  seats: number;
  team: { team: string; accepted: boolean } | null;
  members: { member: string; accepted: boolean }[];
  included_micro_usd: number;
  request_limit: number;
  keys: string[];
  has_gateway_token: boolean;
  checkout_enabled: boolean;
  portal_enabled: boolean;
  plans: Plan[];
  providers: Provider[];
}

async function api<T>(path: string, method = "GET", body?: object): Promise<T> {
  const response = await authenticatedFetch(`/v1/billing${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Account operation failed. Please retry.",
    );
  }
  return response.json() as Promise<T>;
}

const dollars = (micro: number) => `$${(micro / 1_000_000).toFixed(2)}`;

export function SettingsBillingSection() {
  const [status, setStatus] = useState<Status | null>(null);
  const [mode, setMode] = useState("free");
  const [model, setModel] = useState("");
  const [provider, setProvider] = useState("");
  const [annual, setAnnual] = useState(false);
  const [seats, setSeats] = useState(1);
  const [member, setMember] = useState("");
  const [key, setKey] = useState("");
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh(syncSelection = true) {
    const data = await api<Status>("");
    setStatus(data);
    if (syncSelection) {
      setMode(data.mode || "free");
      setModel(data.model || "");
    }
  }
  useEffect(() => {
    void refresh().catch((error: Error) => setMessage(error.message));
  }, []);
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await action();
      await refresh(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }
  async function redirect(path: string, body?: object) {
    const result = await api<{ url: string }>(path, "POST", body);
    const url = new URL(result.url);
    if (
      url.protocol !== "https:" ||
      !["checkout.stripe.com", "billing.stripe.com"].includes(url.hostname)
    )
      throw new Error("Invalid billing redirect");
    window.location.assign(url.href);
  }
  return (
    <section className="space-y-6" aria-label="Plans and models">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Plans &amp; models</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Free models, a managed subscription, or your own provider keys. Choose how each job uses
            AI.
          </p>
        </div>
        <Button
          variant="outline"
          aria-label="Refresh billing"
          disabled={busy}
          onClick={() => void act(refresh)}
        >
          <RefreshCwIcon size={16} />
        </Button>
      </header>
      {message && (
        <p role="status" className="rounded-lg border p-3 text-sm">
          {message}
        </p>
      )}
      {!status ? (
        <p>Loading account…</p>
      ) : !status.enabled ? (
        <p className="rounded-lg border p-4">{status.message}</p>
      ) : (
        <>
          <div className="rounded-xl border bg-muted/30 p-5 space-y-3">
            <h2 className="font-semibold">
              Current plan: {status.plans.find((p) => p.id === status.plan)?.label} ·{" "}
              {status.status}
            </h2>
            <p className="text-sm">
              {status.token_allowance
                ? `${status.usage.tokens.toLocaleString()} / ${status.token_allowance.toLocaleString()} tokens · `
                : ""}
              {status.mode === "byok"
                ? "Billed directly by your provider"
                : status.mode === "free" && !status.included_micro_usd
                  ? "Free model access"
                  : status.token_allowance
                    ? `${dollars(status.usage.spent_micro_usd)} estimated model cost`
                    : `${dollars(status.usage.spent_micro_usd)} / ${dollars(status.included_micro_usd)} model allowance`}{" "}
              · {status.usage.requests.toLocaleString()} / {status.request_limit.toLocaleString()}{" "}
              requests · Period{" "}
              {status.period.match(/\d{4}-\d{2}(?:-\d{2})?/)?.[0] || status.period}
            </p>
            {status.included_credits != null && status.included_credits > 0 && (
              <p className="text-sm">
                {(status.credits_used || 0).toFixed(2)} / {status.included_credits.toLocaleString()}{" "}
                credits used · 1 credit ={" "}
                {dollars(status.included_micro_usd / status.included_credits)} of model usage.
              </p>
            )}
            <progress
              aria-label="Included usage consumed"
              className="w-full"
              value={
                status.token_allowance
                  ? status.usage.tokens
                  : status.included_micro_usd
                    ? status.usage.spent_micro_usd
                    : status.usage.requests
              }
              max={Math.max(
                1,
                status.token_allowance || status.included_micro_usd || status.request_limit,
              )}
            />
            <p className="text-xs text-muted-foreground">
              Reservations count until final provider usage arrives. Requests stop at the limit; no
              automatic overage charges. BYOK provider charges are separate.
            </p>
            {status.portal_enabled && (
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => void act(() => redirect("/portal"))}
              >
                Manage subscription
              </Button>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={annual} onChange={(e) => setAnnual(e.target.checked)} />
            Annual billing · pay for 12 months upfront
          </label>
          <label className="block text-sm">
            Teams seats (including you)
            <Input
              aria-label="Teams seats"
              type="number"
              min={1}
              max={10000}
              value={seats}
              onChange={(e) => setSeats(Math.max(1, Math.min(10000, Number(e.target.value) || 1)))}
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {status.plans.map((plan) => (
              <article key={plan.id} className="rounded-xl border p-4 space-y-3">
                <CreditCardIcon size={20} />
                <h2 className="font-semibold">{plan.label}</h2>
                <p className="text-2xl font-semibold">
                  ${annual && plan.annual_monthly_usd ? plan.annual_monthly_usd : plan.monthly_usd}
                  <span className="text-sm font-normal text-muted-foreground">
                    {" "}
                    / {plan.per_seat ? "member / " : ""}month
                  </span>
                </p>
                <p className="text-sm">
                  {plan.token_limit
                    ? `${(plan.token_limit / 1_000_000).toLocaleString()} million tokens / month${plan.per_seat ? " per member" : ""}`
                    : plan.included_credits
                      ? `${plan.included_credits.toLocaleString()} credits / month`
                      : "Limited free models"}
                </p>
                {plan.rollover && (
                  <p className="text-xs text-muted-foreground">
                    No daily token cap · unused base tokens roll into the following month.
                  </p>
                )}
                {annual && plan.annual_monthly_usd && (
                  <p className="text-xs">
                    ${plan.annual_monthly_usd * 12}
                    {plan.per_seat ? " per member" : ""} billed annually.
                  </p>
                )}
                {plan.id !== "free" && (
                  <Button
                    disabled={
                      busy ||
                      !plan.purchasable ||
                      !status.checkout_enabled ||
                      status.plan === plan.id
                    }
                    onClick={() =>
                      void act(() =>
                        redirect(status.portal_enabled ? "/portal" : "/checkout", {
                          plan: plan.id,
                          seats: plan.per_seat ? seats : 1,
                          annual: annual && !!plan.annual_monthly_usd,
                        }),
                      )
                    }
                  >
                    {status.plan === plan.id
                      ? "Current plan"
                      : plan.purchasable
                        ? "Choose plan"
                        : "Not configured"}
                  </Button>
                )}
              </article>
            ))}
          </div>
          {(status.plan === "teams" || status.team) && (
            <div className="rounded-xl border p-5 space-y-3">
              <h2 className="font-semibold">Team access</h2>
              {status.team && !status.team.accepted && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    void act(async () => {
                      await api("/members/accept", "POST");
                    })
                  }
                >
                  Accept Teams invitation
                </Button>
              )}
              {status.team?.accepted && (
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() =>
                    void act(async () => {
                      await api(`/members/${encodeURIComponent("me")}`, "DELETE");
                    })
                  }
                >
                  Leave team
                </Button>
              )}
              {!status.team && (
                <>
                  <p className="text-sm">
                    {status.members.length + 1} / {status.seats} seats allocated. Members accept
                    invitations in their Plans &amp; models settings. Keys and conversations remain
                    private.
                  </p>
                  <Input
                    aria-label="Member account ID"
                    placeholder="Exact Xwav account ID"
                    value={member}
                    onChange={(e) => setMember(e.target.value)}
                  />
                  <Button
                    disabled={busy || !member}
                    onClick={() =>
                      void act(async () => {
                        await api("/members", "POST", { member });
                        setMember("");
                      })
                    }
                  >
                    Invite member
                  </Button>
                  {status.members.map((m) => (
                    <div key={m.member} className="flex items-center justify-between gap-3 text-sm">
                      <span>
                        {m.member} · {m.accepted ? "Accepted" : "Pending"}
                      </span>
                      <Button
                        variant="outline"
                        disabled={busy}
                        onClick={() =>
                          void act(async () => {
                            await api(`/members/${encodeURIComponent(m.member)}`, "DELETE");
                          })
                        }
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
          <div className="rounded-xl border p-5 space-y-4">
            <h2 className="font-semibold">Choose your model and usage mode</h2>
            <label className="block text-sm">
              Usage mode
              <select
                aria-label="Usage mode"
                className="mt-2 block w-full rounded-md border bg-background p-2"
                value={mode}
                onChange={(event) => {
                  setMode(event.target.value);
                  setModel("");
                }}
              >
                <option value="free">Free · configured free models</option>
                <option value="managed">Subscription · included model usage</option>
                <option value="byok">BYOK · billed by your provider</option>
              </select>
            </label>
            <label className="block text-sm">
              Provider / model
              <select
                aria-label="Provider and model"
                className="mt-2 block w-full rounded-md border bg-background p-2"
                value={model}
                onChange={(event) => setModel(event.target.value)}
              >
                <option value="">Select a model</option>
                {status.providers.map((p) => (
                  <optgroup key={p.id} label={p.label}>
                    {p.models
                      .filter((m) => mode !== "free" || m.free)
                      .map((m) => (
                        <option key={m.id} value={`${p.id}/${m.id}`}>
                          {m.label || m.id} · ${m.input_usd_per_million}/${m.output_usd_per_million}{" "}
                          per million input/output tokens
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
            </label>
            {mode !== "byok" && status.free_failover && (
              <p className="rounded-lg border bg-muted/30 p-3 text-sm">
                Automatic Free failover is on for zero-cost free models. If one reaches capacity or
                its response fails, Xwav tries another configured zero-cost model. Responses are
                checked before delivery so interrupted answers and tool calls are not mixed. Paid
                models are never used as a fallback. If every free route is unavailable, retry after
                its cooldown. Your Xwav plan allowance still applies.
              </p>
            )}
            {status.providers.flatMap((poolProvider) =>
              poolProvider.models
                .filter(
                  (entry) =>
                    `${poolProvider.id}/${entry.id}` === model && entry.auto_candidates?.length,
                )
                .map((entry) => (
                  <div
                    key={poolProvider.id}
                    className="rounded-lg border bg-muted/30 p-4 text-sm"
                    aria-label="Auto model pool"
                  >
                    <h3 className="font-semibold">Models available under Auto</h3>
                    <p className="mt-1 text-muted-foreground">
                      {poolProvider.label} chooses from this configured pool according to routing
                      priority, availability and cooldowns. Auto uses one model per request;
                      capacity can change.
                    </p>
                    <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                      {entry.auto_candidates?.map((candidate) => (
                        <li key={candidate}>
                          {poolProvider.models.find((item) => item.id === candidate)?.label ||
                            candidate}
                        </li>
                      ))}
                    </ul>
                  </div>
                )),
            )}
            <Button
              disabled={busy || !model}
              onClick={() =>
                void act(async () => {
                  await api("/selection", "PUT", { mode, model });
                  setMessage(
                    mode !== "byok"
                      ? "Selection saved. New sandbox jobs use this profile automatically."
                      : "Selection saved. Download the agent configuration for a new job.",
                  );
                })
              }
            >
              Save selection
            </Button>
            <p className="text-xs text-muted-foreground">
              Free and subscription sandbox jobs automatically configure compatible harnesses with
              Xwav model access. Existing jobs retain their configured endpoint and model.
              Vendor-only harnesses require their own account.
            </p>
          </div>
          <div className="rounded-xl border p-5 space-y-4">
            <h2 className="flex items-center gap-2 font-semibold">
              <KeyRoundIcon size={18} />
              Bring your own key
            </h2>
            <p className="text-sm text-muted-foreground">
              Keys are encrypted on the server and never returned to the browser or included in
              downloads.
            </p>
            <label className="block text-sm">
              Key provider
              <select
                aria-label="Key provider"
                className="mt-2 block w-full rounded-md border bg-background p-2"
                value={provider}
                onChange={(event) => setProvider(event.target.value)}
              >
                <option value="">Select provider</option>
                {status.providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                    {status.keys.includes(p.id) ? " · key saved" : ""}
                  </option>
                ))}
              </select>
            </label>
            <Input
              type="password"
              aria-label="Provider API key"
              autoComplete="off"
              value={key}
              onChange={(event) => setKey(event.target.value)}
              placeholder="Paste your provider API key"
            />
            <div className="flex gap-2">
              <Button
                disabled={busy || !provider || !key}
                onClick={() => {
                  const value = key;
                  setKey("");
                  void act(async () => {
                    await api(`/keys/${provider}`, "PUT", { key: value });
                    setMessage("Provider key saved.");
                  });
                }}
              >
                Save key
              </Button>
              <Button
                variant="outline"
                disabled={busy || !status.keys.includes(provider)}
                onClick={() =>
                  void act(async () => {
                    await api(`/keys/${provider}`, "DELETE");
                    setMessage("Provider key removed.");
                  })
                }
              >
                Remove key
              </Button>
            </div>
          </div>
          <div className="rounded-xl border p-5 space-y-4">
            <h2 className="font-semibold">Use this profile in a job</h2>
            <p className="text-sm">
              Create a gateway token, set it as XWAV_GATEWAY_TOKEN on the job host, then import the
              downloaded agent configuration in Custom agents. Use a server URL reachable from your
              sandbox.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    setToken((await api<{ token: string }>("/token", "POST")).token);
                  })
                }
              >
                {status.has_gateway_token ? "Rotate gateway token" : "Create gateway token"}
              </Button>
              <Button
                variant="outline"
                disabled={busy || !status.has_gateway_token}
                onClick={() =>
                  void act(async () => {
                    await api("/token", "DELETE");
                    setToken("");
                  })
                }
              >
                Revoke token
              </Button>
              <Button
                variant="outline"
                disabled={busy || !status.model}
                onClick={() =>
                  void act(async () => {
                    const response = await authenticatedFetch("/v1/billing/agent");
                    if (!response.ok)
                      throw new Error(
                        "Save a Chat Completions model before downloading the agent.",
                      );
                    const url = URL.createObjectURL(await response.blob());
                    const link = document.createElement("a");
                    link.href = url;
                    link.download = "xwav-subscription-agent.tar.gz";
                    link.click();
                    URL.revokeObjectURL(url);
                  })
                }
              >
                <DownloadIcon size={16} />
                Download agent
              </Button>
            </div>
            {token && (
              <div className="space-y-2">
                <p className="text-xs">
                  Shown once. Rotating revokes the previous token. This token authorizes account
                  inference spending.
                </p>
                <Input
                  readOnly
                  type="password"
                  aria-label="New gateway token"
                  value={token}
                  onFocus={(event) => event.target.select()}
                />
                <Button
                  variant="outline"
                  onClick={() =>
                    void navigator.clipboard.writeText(token).then(
                      () => setMessage("Gateway token copied."),
                      () => setMessage("Select the token field and copy it manually."),
                    )
                  }
                >
                  Copy token
                </Button>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
