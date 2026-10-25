// Pi >=1.4 resources_discover runs after user, project and package skills load.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

function contentKey(text) {
  const body = text.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/u, "");
  return crypto
    .createHash("sha256")
    .update(body.trim().replace(/\s+/gu, " "))
    .digest("hex");
}

function selectedPaths(catalog, commands) {
  const names = new Set();
  const contents = new Set();
  for (const command of commands) {
    if (command.source !== "skill") continue;
    names.add(command.name.replace(/^skill:/u, "").toLowerCase());
    try {
      let file = command.sourceInfo.path;
      if (fs.statSync(file).isDirectory()) file = path.join(file, "SKILL.md");
      names.add(path.basename(path.dirname(file)).toLowerCase());
      contents.add(contentKey(fs.readFileSync(file, "utf8")));
    } catch {
      // An unreadable user resource still reserves its advertised command name.
    }
  }
  const result = [];
  for (const skill of catalog) {
    const aliases = skill.aliases.map((name) => name.toLowerCase());
    if (
      aliases.some((name) => names.has(name)) ||
      contents.has(skill.contentKey)
    )
      continue;
    result.push(skill.directory);
    for (const name of aliases) names.add(name);
    if (skill.contentKey) contents.add(skill.contentKey);
  }
  return result;
}

module.exports = function registerNativeSkills(pi) {
  let catalog;
  try {
    catalog = JSON.parse(process.env.OMNIGENT_PI_SKILL_CATALOG || "[]");
  } catch {
    return;
  }
  if (!Array.isArray(catalog) || catalog.length === 0) return;
  pi.on("resources_discover", () => ({
    skillPaths: selectedPaths(catalog, pi.getCommands()),
  }));
};
module.exports.selectedPaths = selectedPaths;
module.exports.contentKey = contentKey;
