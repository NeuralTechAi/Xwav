import json
import subprocess
from pathlib import Path

payload = {
    "runtime": Path("omnigent/preproduction_runtime.py").read_text(),
    "preview": Path("omnigent/preview_runtime.py").read_text(),
}
program = r"""
import sys,json,tempfile,os,runpy
from pathlib import Path
payload=json.load(sys.stdin)
os.environ.pop('PLAYWRIGHT_BROWSERS_PATH',None)
base=Path(tempfile.mkdtemp(prefix='native-quality-'))
runtime=base/'runtime.py';runtime.write_text(payload['runtime'])
preview=base/'preview.py';preview.write_text(payload['preview'])
audit=runpy.run_path(str(runtime))['browser_audit']
root=base/'project';root.mkdir();os.chdir(root)
root.joinpath('index.html').write_text(
 '<!doctype html><html lang="en"><head><meta name="viewport" '
 'content="width=device-width,initial-scale=1"><title>Native quality fixture</title>'
 '</head><body><main><h1>Ready</h1><button type="button">Action</button>'
 '</main></body></html>')
assert not root.joinpath('node_modules').exists()
for platform in ('web','android','ios'):
 result=audit(root,platform,preview)
 print(platform,json.dumps(result),flush=True)
 assert all(row['status']=='passed' for row in result.values()),result
root.joinpath('index.html').write_text(
 '<html><body><div style="width:3000px">broken</div>'
 '<script>throw Error("injected failure")</script></body></html>')
result=audit(root,'web',preview)
assert result['functional']['status']=='failed',result
assert result['usability']['status']=='failed',result
assert result['accessibility']['status']=='failed',result
from omnigent.native_skills import discover_native_skills
assert discover_native_skills(['preproduction-tests'])
print('Native tools work for fresh unprivileged jobs; defect detection verified.',flush=True)
"""
r = subprocess.run(
    [
        "docker",
        "run",
        "--rm",
        "--init",
        "--interactive",
        "--user",
        "sandbox",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--workdir",
        "/sandbox",
        "--env",
        "HOME=/sandbox",
        "xwav-host:local",
        "python",
        "-c",
        program,
    ],
    input=json.dumps(payload),
    text=True,
    timeout=180,
)
raise SystemExit(r.returncode)
