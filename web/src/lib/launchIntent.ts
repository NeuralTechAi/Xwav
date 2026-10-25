/** Portable launch instructions; native read-only plan modes remain separate. */
export function composeLaunchIntent(message: string, goal: string, planRequested: boolean): string {
  return [
    message,
    goal.trim() && `Completion condition:\n${goal.trim()}`,
    planRequested &&
      "Planning request: inspect the task and propose a plan. Wait for my approval before editing files or running commands that change state.",
  ]
    .filter(Boolean)
    .join("\n\n");
}
