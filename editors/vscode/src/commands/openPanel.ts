/**
 * "Xwav: Open" command.
 *
 * The Xwav UI renders only in the editor-beside `WebviewPanel`, owned by the
 * shared `EditorPanelController`. `xwav.open` simply ensures that panel is
 * open and revealed; the controller owns the singleton and the resolved local
 * server target.
 */
import * as vscode from "vscode";
import type { EditorPanelController } from "../panel/EditorPanelController";

export const OPEN_PANEL_COMMAND = "xwav.open";

/** Register the `xwav.open` command. Returns the disposable command. */
export function registerOpenPanel(
  context: vscode.ExtensionContext,
  controller: EditorPanelController,
): vscode.Disposable {
  const cmd = vscode.commands.registerCommand(OPEN_PANEL_COMMAND, () => {
    controller.ensure();
  });

  const legacyCommand = vscode.commands.registerCommand("omnigent.open", () => {
    controller.ensure();
  });
  const previousBrandCommand = vscode.commands.registerCommand(
    "xvaw.open",
    () => {
      controller.ensure();
    },
  );
  context.subscriptions.push(cmd, previousBrandCommand, legacyCommand);
  return cmd;
}
