import { type CSSProperties, useState } from "react";
import { FolderIcon, FolderPlusIcon, PlusIcon, SmilePlusIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { EmojiPicker } from "@/components/ProjectIconPicker";
import { useCreateProject } from "@/hooks/useConversations";
import { useHosts } from "@/hooks/useHosts";
import { WorkspacePickerDialog } from "./WorkspacePickerDialog";
import { cn } from "@/lib/utils";

/** Project creation with an optional default folder on a connected computer. */
export function NewProjectButton({ onCreated }: { onCreated: (name: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label="New project"
            data-testid="new-project"
            className="text-foreground"
            onClick={(event) => {
              event.stopPropagation();
              setOpen(true);
            }}
          >
            <PlusIcon className="size-3.5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom">New project</TooltipContent>
      </Tooltip>
      {open && <NewProjectDialog onCreated={onCreated} onOpenChange={setOpen} />}
    </>
  );
}

function NewProjectDialog({
  onCreated,
  onOpenChange: setOpen,
}: {
  onCreated: (name: string) => void;
  onOpenChange: (open: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [icon, setIcon] = useState<string | undefined>(undefined);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const createProject = useCreateProject();
  const { data: hosts = [] } = useHosts();
  const onlineHosts = hosts.filter((host) => host.status === "online");
  const [hostId, setHostId] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const selectedHostId = hostId || onlineHosts[0]?.host_id || "";
  const selectedHost = onlineHosts.find((host) => host.host_id === selectedHostId);

  const submit = () => {
    const trimmed = name.trim();
    if (trimmed === "" || createProject.isPending || (workspace && !selectedHost)) return;
    createProject.mutate(
      {
        name: trimmed,
        icon,
        ...(workspace
          ? { config: { host_id: selectedHostId, workspace, source_folder: true } }
          : {}),
      },
      {
        onSuccess: (project) => {
          setOpen(false);
          setName("");
          setIcon(undefined);
          onCreated(project.name);
        },
      },
    );
  };

  return (
    <Dialog open onOpenChange={setOpen}>
      <DialogContent
        className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-lg"
        onInteractOutside={(event) => {
          if (workspaceOpen) event.preventDefault();
        }}
        onClick={(e) => e.stopPropagation()}
        // emoji-mart preventDefaults the pointer event, so Radix's own
        // outside-dismissal never fires for clicks elsewhere in the modal.
        // Catch them in the capture phase and close the picker ourselves,
        // unless the pointer is inside the picker or on its trigger tile.
        onPointerDownCapture={(e) => {
          if (!emojiOpen) return;
          const target = e.target as Element;
          if (
            target.closest('[data-slot="popover-content"]') ||
            target.closest('[data-testid="new-project-icon"]')
          )
            return;
          setEmojiOpen(false);
        }}
      >
        <DialogHeader>
          <DialogTitle>Create project</DialogTitle>
          <DialogDescription>
            Choose a name and an optional source folder for new jobs.
          </DialogDescription>
        </DialogHeader>
        {/* One combined control: emoji tile (left) + name (right) share a
              single border, so it reads as a single input. */}
        <div className="flex items-stretch overflow-hidden rounded-lg border border-input">
          <Popover open={emojiOpen} onOpenChange={setEmojiOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                aria-label="Choose project icon"
                data-testid="new-project-icon"
                className={cn(
                  "flex size-[38px] shrink-0 cursor-pointer items-center justify-center outline-none transition-colors",
                  icon ? "bg-muted" : "bg-tag-pink",
                )}
              >
                {icon ? (
                  <span className="text-xl leading-none">{icon}</span>
                ) : (
                  <SmilePlusIcon className="size-4 text-brand-accent" />
                )}
              </button>
            </PopoverTrigger>
            <PopoverContent
              align="start"
              // Publish the collision-aware available viewport height (Radix
              // exposes it as a CSS var), capped at the picker's natural size,
              // so the .emoji-picker-popover rule in index.css shrinks
              // emoji-mart to fit — it then scrolls its grid internally
              // instead of clipping on short screens.
              collisionPadding={8}
              style={
                {
                  "--emoji-picker-height":
                    "min(420px, var(--radix-popover-content-available-height))",
                } as CSSProperties
              }
              className="emoji-picker-popover flex max-h-[var(--radix-popover-content-available-height)] w-auto flex-col overflow-hidden p-0"
              // The Dialog's scroll lock (react-remove-scroll) preventDefaults
              // wheel events over the picker — it can't see emoji-mart's scroll
              // region inside shadow DOM. Stop the wheel from reaching the
              // document-level lock so the grid scrolls.
              onWheel={(e) => e.stopPropagation()}
              onInteractOutside={() => setEmojiOpen(false)}
            >
              <EmojiPicker
                onSelect={(native) => {
                  setIcon(native);
                  setEmojiOpen(false);
                }}
              />
            </PopoverContent>
          </Popover>
          <input
            autoFocus
            className="w-full bg-transparent px-3 py-2 text-ui outline-none"
            placeholder="Project name…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
          />
        </div>
        <section className="flex flex-col gap-2" aria-label="Source folders">
          <h3 className="text-sm font-medium">Source folders</h3>
          <div className="flex flex-col gap-3 rounded-lg border border-input bg-muted/20 p-4">
            <label className="flex flex-col gap-1.5 text-sm">
              Computer
              <select
                aria-label="Source folder computer"
                data-testid="new-project-source-host"
                value={selectedHostId}
                disabled={createProject.isPending || onlineHosts.length === 0}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-foreground"
                onChange={(event) => {
                  setHostId(event.target.value);
                  setWorkspace("");
                }}
              >
                {onlineHosts.length === 0 && <option value="">No connected computers</option>}
                {onlineHosts.map((host) => (
                  <option key={host.host_id} value={host.host_id}>
                    {host.name}
                  </option>
                ))}
              </select>
            </label>
            {workspace ? (
              <div className="flex min-w-0 items-center gap-2 rounded-md border bg-background px-3 py-2">
                <FolderIcon className="size-4 shrink-0 text-brand-accent" />
                <button
                  type="button"
                  className="min-w-0 flex-1 truncate text-left text-sm hover:underline"
                  title={workspace}
                  data-testid="new-project-source-folder"
                  disabled={createProject.isPending || !selectedHost}
                  onClick={() => setWorkspaceOpen(true)}
                >
                  {workspace}
                </button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label="Remove source folder"
                  disabled={createProject.isPending}
                  onClick={() => setWorkspace("")}
                >
                  <XIcon className="size-3.5" />
                </Button>
              </div>
            ) : (
              <Button
                type="button"
                variant="outline"
                className="self-center"
                data-testid="new-project-add-folder"
                disabled={!selectedHost || createProject.isPending}
                onClick={() => {
                  setHostId(selectedHostId);
                  setWorkspaceOpen(true);
                }}
              >
                <FolderPlusIcon className="size-4" /> Add folder
              </Button>
            )}
            <p className="text-xs leading-relaxed text-muted-foreground">
              {workspace
                ? "New jobs use this folder on the selected computer by default."
                : onlineHosts.length
                  ? "Choose the default working folder for this project, or leave it empty to use a new sandbox."
                  : "Connect a computer in Settings to browse its folders. You can also create the project without a source folder."}
            </p>
            {workspace && !selectedHost && (
              <p role="alert" className="text-sm text-destructive">
                The source computer is offline. Reconnect it or remove the source folder.
              </p>
            )}
          </div>
        </section>
        <WorkspacePickerDialog
          open={workspaceOpen}
          onOpenChange={setWorkspaceOpen}
          hostId={selectedHostId || null}
          initialPath={workspace}
          title="Select source folder"
          description="Choose the default working folder for new jobs in this project."
          onConfirm={setWorkspace}
        />
        {createProject.isError && (
          <p className="text-ui text-destructive" role="alert">
            {(createProject.error as Error).message}
          </p>
        )}
        <DialogFooter className="border-t-0 bg-transparent">
          <Button
            type="button"
            variant="ghost"
            onClick={() => setOpen(false)}
            disabled={createProject.isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            data-testid="new-project-confirm"
            loading={createProject.isPending}
            disabled={name.trim() === "" || (!!workspace && !selectedHost)}
            onClick={submit}
          >
            Create project
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
