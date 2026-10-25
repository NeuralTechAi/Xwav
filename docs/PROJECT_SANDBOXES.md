# Isolated project jobs

The main navigation uses **New Job**, **Notifications**, and **Scheduler**.

On a server configured with a managed sandbox provider, every new top-level
project job receives a fresh managed host and workspace. Project jobs can run
concurrently, including multiple jobs in one project. Child agents and side
chats share their parent job's sandbox. Forks receive a fresh sandbox.

Set the project's repository URL in Project settings. Each job clones its own
copy; a blank source creates an empty workspace. Saved machine directories and
worktree hints do not become shared mounts. Unconfigured embedded servers retain
their existing connected-host behavior.

For local Docker, build the host image from the repository root:

```sh
docker build --target host -t xwav-host:local -f deploy/docker/Dockerfile .
```

Merge this into the server configuration and restart the server:

```yaml
sandbox:
  provider: docker
  server_url: http://127.0.0.1:6767
  docker:
    image: xwav-host:local
    cpus: 2
    memory_mib: 2048
```

Docker must be available to the server. Containers run as the image's `sandbox`
user with no host directory or Docker socket mounts, dropped capabilities, and
CPU, memory and process limits. The default uses Linux host networking so hosts
can reach the local server; this is filesystem/process isolation, not a VM or
network isolation boundary. Configure `network: bridge` with a server URL that
containers can reach when network namespaces are required.

Use the existing managed-host credential settings or explicit environment
variable names under `docker.env` for provider access. Credentials are not copied
from a developer's home directory. Closing a job does not delete its sandbox;
use the managed-host termination controls when its work is no longer needed.
