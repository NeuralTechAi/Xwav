// Offline acceptance: real Pi extension loading and exact observation recall.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [piRoot, bundle, workspace] = process.argv.slice(2);
const { createAgentSession, DefaultResourceLoader, ModelRuntime, SessionManager, SettingsManager } =
  await import(pathToFileURL(path.join(piRoot, 'dist/index.js')).href);
const { fauxProvider, fauxAssistantMessage, fauxToolCall } =
  await import(pathToFileURL(path.join(piRoot, '../pi-ai/dist/providers/faux.js')).href);
const agentDir = path.join(workspace, 'private-agent');
await fs.mkdir(agentDir);
const original = Array.from({length: 200}, (_, i) => `evidence-${i}: ${'verifiable '.repeat(13)}`).join('\n');
await fs.writeFile(path.join(workspace, 'large.log'), original);
await fs.writeFile(path.join(workspace, 'small.txt'), 'small observation');
const faux = fauxProvider();
let packed = false;
faux.setResponses([
  fauxAssistantMessage(fauxToolCall('read', {path: 'large.log'}), {stopReason: 'toolUse'}),
  fauxAssistantMessage(fauxToolCall('read', {path: 'small.txt'}), {stopReason: 'toolUse'}),
  fauxAssistantMessage(fauxToolCall('read', {path: 'small.txt'}), {stopReason: 'toolUse'}),
  (context) => {
    const text = JSON.stringify(context);
    packed = text.includes('large tool result replaced');
    assert.ok(packed, 'Repeated large result must be packed in the provider context');
    const id = text.match(/obs_[a-f0-9]{24}/)?.[0];
    assert.ok(id);
    return fauxAssistantMessage(fauxToolCall('obs_recall', {id, offset: 0}), {stopReason: 'toolUse'});
  },
  fauxAssistantMessage('Verified local packing and exact recall.'),
]);
const runtime = await ModelRuntime.create({
  authPath: path.join(agentDir, 'auth.json'), modelsPath: null,
  allowModelNetwork: false, refreshOnCreate: false,
});
runtime.registerNativeProvider(faux.provider);
const settings = SettingsManager.inMemory({compaction: {enabled: false}, retry: {enabled: false}}, {projectTrusted: true});
const loader = new DefaultResourceLoader({
  cwd: workspace, agentDir, settingsManager: settings,
  additionalExtensionPaths: [path.join(bundle, '.pi/extensions/sol-pi/index.ts')],
  noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true,
  systemPrompt: 'Offline scripted test. No external model calls.',
});
await loader.reload();
assert.deepEqual(loader.getExtensions().errors, []);
const {session} = await createAgentSession({
  cwd: workspace, agentDir, modelRuntime: runtime, resourceLoader: loader,
  settingsManager: settings, sessionManager: SessionManager.create(workspace, path.join(agentDir, 'sessions')),
  model: faux.getModel(), thinkingLevel: 'off',
});
try {
  const errors = [];
  await session.bindExtensions({onError: error => errors.push(error)});
  assert.ok(session.getActiveToolNames().includes('obs_recall'));
  assert.ok(!session.getActiveToolNames().includes('update_plan'));
  const writeTool = session.getAllTools().find(tool => tool.name === 'write');
  assert.ok(!JSON.stringify(writeTool).includes('then_run'));
  await session.prompt('Read the large file, then the small file twice, and recall the archived evidence.');
  assert.deepEqual(errors, []);
  assert.ok(packed);
  const results = session.messages.filter(message => message.role === 'toolResult');
  const source = results.find(message => message.toolName === 'read');
  assert.ok(JSON.stringify(source).includes('evidence-199'), 'Stored history must retain source');
  const recall = results.find(message => message.toolName === 'obs_recall');
  assert.ok(recall && !recall.isError);
  const recalled = recall.content.filter(item => item.type === 'text').map(item => item.text).join('\n');
  const chunk = recalled.split('\n').slice(2).join('\n');
  assert.ok(original.startsWith(chunk), 'Recall must match exact archived bytes');
  assert.ok(Buffer.byteLength(recalled) <= 16384);
  console.log(JSON.stringify({pi: '1.4.0', packed, exact_recall: true, preserved_history: true, model_calls: 'scripted local only'}));
} finally {
  session.dispose();
}
