"""Lazy, rootless release toolchains. No downloads occur during planning."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

SDK_VERSION = "15859902"
SDK_ARCHIVES = {
    "Linux": ("linux", "4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583"),
    "Darwin-x86_64": (
        "mac_x86_64",
        "c5a6378ab5cf7e0d5701921405115befff13e9ff7417fb588389338f8bd050f3",
    ),
    "Darwin-arm64": (
        "mac_arm64",
        "835b62a26162b229b441d1f6d4680383815a270809eb33522c0d480fa5002c4e",
    ),
}


def cache_root() -> Path:
    return Path(
        os.environ.get("XWAV_BUILD_CACHE", str(Path.home() / ".cache/xwav/build-tools/v1"))
    )


def supported() -> bool:
    return platform.system() in {"Linux", "Darwin"} and platform.machine() in {
        "x86_64",
        "amd64",
        "aarch64",
        "arm64",
    }


def wine_bootstrap_supported() -> bool:
    return (
        platform.system() == "Linux"
        and platform.machine() in {"x86_64", "amd64"}
        and Path("/etc/debian_version").exists()
        and bool(shutil.which("apt-get") and shutil.which("dpkg-deb"))
    )


def checkpoint(cancel: Path, deadline: float) -> None:
    if cancel.exists():
        raise RuntimeError("Cancelled")
    if time.monotonic() > deadline:
        raise RuntimeError("Toolchain setup timed out")


def download(
    url: str,
    path: Path,
    cancel: Path,
    deadline: float,
    checksum: str | None = None,
    limit: int = 512 * 1024 * 1024,
) -> None:
    if not url.startswith("https://"):
        raise ValueError("Toolchain downloads require HTTPS")
    digest = hashlib.sha256()
    total = 0
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Xwav-Release-Studio/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response, path.open("wb") as output:
            if not response.url.startswith("https://"):
                raise ValueError("Toolchain redirect must use HTTPS")
            while True:
                checkpoint(cancel, deadline)
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise ValueError("Toolchain download exceeds its size limit")
                digest.update(chunk)
                output.write(chunk)
        if checksum and digest.hexdigest() != checksum.lower():
            raise ValueError("Toolchain checksum mismatch; download discarded")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def metadata(url: str, temp: Path, cancel: Path, deadline: float) -> str:
    file = temp / "metadata"
    download(url, file, cancel, deadline, limit=4 * 1024 * 1024)
    return file.read_text()


def unpack(archive: Path, destination: Path) -> None:
    destination.mkdir()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            if sum(item.file_size for item in bundle.infolist()) > 2 * 1024**3:
                raise ValueError("Toolchain archive exceeds extraction limit")
            for item in bundle.infolist():
                file = destination / item.filename
                if not file.resolve().is_relative_to(destination.resolve()):
                    raise ValueError("Unsafe toolchain archive path")
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError("SDK ZIP must not contain symlinks")
                bundle.extract(item, destination)
                if file.is_file() and item.external_attr >> 16 & 0o111:
                    file.chmod(0o755)
    else:
        try:
            with tarfile.open(archive) as bundle:
                if sum(item.size for item in bundle.getmembers()) > 2 * 1024**3:
                    raise ValueError("Toolchain archive exceeds extraction limit")
                bundle.extractall(destination, filter="data")
        except tarfile.TarError as exc:
            raise ValueError("Invalid or unsafe toolchain archive") from exc


@contextlib.contextmanager
def locked(cache: Path, cancel: Path, deadline: float):
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (cache / "setup.lock").open("a") as lock:
        while True:
            checkpoint(cancel, deadline)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(0.2)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def portable(name: str, cache: Path, cancel: Path, deadline: float, progress) -> Path:
    destination = cache / name
    marker = destination / ".complete"
    binary = (
        destination
        / "bin"
        / ("node" if name == "node-22" else "java" if name == "jdk-21" else "sdkmanager")
    )
    if marker.exists() and binary.is_file():
        return destination
    progress(f"Downloading and verifying {name}")
    with tempfile.TemporaryDirectory(dir=cache, prefix="setup-") as folder:
        temp = Path(folder)
        system = "darwin" if platform.system() == "Darwin" else "linux"
        arch = "arm64" if platform.machine() in {"arm64", "aarch64"} else "x64"
        if name == "node-22":
            base = "https://nodejs.org/dist/latest-v22.x/"
            sums = metadata(base + "SHASUMS256.txt", temp, cancel, deadline)
            match = re.search(
                r"^([a-f0-9]{64})\s+(node-v[\d.]+-" + system + "-" + arch + r"\.tar\.gz)$",
                sums,
                re.M,
            )
            if not match:
                raise ValueError("No supported Node.js release in official checksums")
            checksum, filename = match.groups()
            url = base + filename
        elif name == "jdk-21":
            try:
                assets = json.loads(
                    metadata(
                        "https://api.adoptium.net/v3/assets/latest/21/hotspot?image_type=jdk&os="
                        + ("mac" if system == "darwin" else system)
                        + "&architecture="
                        + ("aarch64" if arch == "arm64" else arch),
                        temp,
                        cancel,
                        deadline,
                    )
                )
                if not isinstance(assets, list) or not assets:
                    raise ValueError("No supported JDK found in the official release metadata")
                package = assets[0]["binary"]["package"]
                url, checksum = package["link"], package["checksum"]
            except urllib.error.URLError:
                release = json.loads(
                    metadata(
                        "https://api.github.com/repos/adoptium/temurin21-binaries/releases/latest",
                        temp,
                        cancel,
                        deadline,
                    )
                )
                pattern = (
                    "OpenJDK21U-jdk_"
                    + ("aarch64" if arch == "arm64" else arch)
                    + "_"
                    + ("mac" if system == "darwin" else system)
                    + r"_hotspot_.+\.tar\.gz"
                )
                package = next(
                    (
                        item
                        for item in release.get("assets", [])
                        if re.fullmatch(pattern, item.get("name", ""))
                    ),
                    None,
                )
                if not package:
                    raise ValueError(
                        "No supported JDK found in official GitHub releases"
                    ) from None
                url = package["browser_download_url"]
                checksum = metadata(url + ".sha256.txt", temp, cancel, deadline).split()[0]
        else:
            key = platform.system()
            if key == "Darwin":
                key += "-arm64" if arch == "arm64" else "-x86_64"
            sdk_os, checksum = SDK_ARCHIVES[key]
            url = f"https://dl.google.com/android/repository/commandlinetools-{sdk_os}-{SDK_VERSION}_latest.zip"
        archive = temp / "archive"
        download(url, archive, cancel, deadline, checksum)
        extracted = temp / "extracted"
        unpack(archive, extracted)
        source = next(extracted.iterdir())
        if system == "darwin" and name == "jdk-21":
            source = source / "Contents/Home"
        if destination.exists():
            shutil.rmtree(destination)
        source.rename(destination)
        marker.write_text(json.dumps({"url": url, "sha256": checksum}))
    return destination


def node_ready() -> bool:
    if not shutil.which("node") or not shutil.which("npm"):
        return False
    try:
        version = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5, check=True
        ).stdout.strip()
        return int(version.removeprefix("v").split(".")[0]) >= 22
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def prepare(
    target: str,
    *,
    needs_node: bool,
    accept_android_licenses: bool,
    cancel: Path,
    deadline: float,
    run,
    progress,
    package_manager: str | None = None,
) -> None:
    """Only the detached worker calls this; cache locks serialize tool installation."""
    if not supported():
        if needs_node and not shutil.which("npm"):
            raise ValueError("Automatic Node setup is unavailable on this platform")
        return
    cache = cache_root()
    for key, folder in {
        "NPM_CONFIG_CACHE": "npm",
        "ELECTRON_CACHE": "electron",
        "ELECTRON_BUILDER_CACHE": "electron-builder",
        "GRADLE_USER_HOME": "gradle",
        "npm_config_store_dir": "pnpm-store",
        "YARN_CACHE_FOLDER": "yarn",
        "BUN_INSTALL_CACHE_DIR": "bun",
    }.items():
        os.environ.setdefault(key, str(cache / folder))
    if target == "android" and not accept_android_licenses:
        sdk = Path(
            os.environ.get("ANDROID_HOME")
            or os.environ.get("ANDROID_SDK_ROOT")
            or cache / "android-sdk"
        )
        if not (sdk / "licenses/android-sdk-license").is_file():
            raise ValueError(
                "Accept the Android SDK licence in Release Studio before automatic setup"
            )
    with locked(cache, cancel, deadline):
        if needs_node and not node_ready():
            node = portable("node-22", cache, cancel, deadline, progress)
            os.environ["PATH"] = str(node / "bin") + os.pathsep + os.environ.get("PATH", "")
        if package_manager and package_manager.split("@")[0] != "npm":
            if not re.fullmatch(
                r"(pnpm|yarn|bun)@[0-9]+(?:\.[0-9]+){0,2}(?:[-+][A-Za-z0-9.-]+)?", package_manager
            ):
                raise ValueError("Unsupported project package manager version")
            manager = package_manager.split("@")[0]
            destination = (
                cache
                / "package-managers"
                / hashlib.sha256(package_manager.encode()).hexdigest()[:16]
            )
            binary = destination / "node_modules/.bin" / manager
            if not binary.is_file():
                destination.mkdir(parents=True, exist_ok=True)
                run(
                    [
                        "npm",
                        "install",
                        "--prefix",
                        str(destination),
                        "--no-audit",
                        "--no-fund",
                        "--package-lock=false",
                        package_manager,
                    ],
                    cache,
                    f"Preparing cached {package_manager}",
                )
            os.environ["PATH"] = str(binary.parent) + os.pathsep + os.environ.get("PATH", "")
        if target == "android":
            # Capacitor 8 requires JDK 21. A project-supplied JAVA_HOME takes precedence.
            if not os.environ.get("JAVA_HOME"):
                jdk = portable("jdk-21", cache, cancel, deadline, progress)
                os.environ["JAVA_HOME"] = str(jdk)
                os.environ["PATH"] = str(jdk / "bin") + os.pathsep + os.environ.get("PATH", "")
            sdk = Path(
                os.environ.get("ANDROID_HOME")
                or os.environ.get("ANDROID_SDK_ROOT")
                or cache / "android-sdk"
            )
            manager = sdk / "cmdline-tools/latest/bin/sdkmanager"
            if not manager.is_file():
                if not accept_android_licenses:
                    raise ValueError(
                        "Accept the Android SDK licence in Release Studio before automatic setup"
                    )
                tools = portable("android-tools-" + SDK_VERSION, cache, cancel, deadline, progress)
                manager.parent.parent.parent.mkdir(parents=True, exist_ok=True)
                (manager.parent.parent).symlink_to(tools, target_is_directory=True)
            os.environ["ANDROID_HOME"] = os.environ["ANDROID_SDK_ROOT"] = str(sdk)
            if accept_android_licenses:
                # Input is finite; no shell pipe or privileged host installation.
                run(
                    [
                        "python3",
                        "-c",
                        "import subprocess,sys; "
                        "sys.exit(subprocess.run(sys.argv[1:],input=b'y\\n'*200).returncode)",
                        str(manager),
                        "--licenses",
                        f"--sdk_root={sdk}",
                    ],
                    cache,
                    "Accepting Android SDK licences",
                )
            if not (sdk / "licenses/android-sdk-license").is_file():
                raise ValueError("Android SDK licences need acceptance in Release Studio")
            progress("Android tools ready; Gradle will download required SDK packages")
        if target == "windows" and platform.system() != "Windows" and not shutil.which("wine"):
            if not wine_bootstrap_supported():
                raise ValueError("Use a Windows/Wine computer or configure a cloud build workflow")
            wine = cache / "wine-debian"
            launcher = wine / "bin/wine"
            options = [
                "-o",
                f"Dir::State={wine / 'state'}",
                "-o",
                "Dir::State::status=/var/lib/dpkg/status",
                "-o",
                f"Dir::Cache::archives={wine / 'archives'}",
                "-o",
                "Debug::NoLocking=1",
                "-o",
                "APT::Architectures::=amd64",
                "-o",
                "APT::Architectures::=i386",
                "-o",
                "APT::Get::List-Cleanup=0",
            ]
            if (
                not (wine / ".complete").exists()
                or not (wine / "root/usr/share/wine/nls/l_intl.nls").is_file()
            ):
                wine.mkdir(exist_ok=True)
                for folder in ("state/lists/partial", "archives/partial"):
                    (wine / folder).mkdir(parents=True, exist_ok=True)
                run(
                    ["apt-get", *options, "update"], cache, "Fetching signed Wine package metadata"
                )
                run(
                    [
                        "apt-get",
                        *options,
                        "--download-only",
                        "--no-install-recommends",
                        "-y",
                        "install",
                        "wine64",
                        "wine",
                    ],
                    cache,
                    "Downloading Wine and required libraries",
                )
                prefix = wine / "root"
                prefix.mkdir(exist_ok=True)
                for deb in sorted((wine / "archives").glob("*.deb")):
                    run(
                        ["dpkg-deb", "-x", str(deb), str(prefix)],
                        cache,
                        "Preparing isolated Wine libraries",
                    )
                binary = prefix / "usr/lib/wine/wine64"
                if not binary.is_file():
                    raise ValueError("Wine packages did not contain a usable wine64 runtime")
                launcher.parent.mkdir(exist_ok=True)
                launcher.write_text("#!/bin/sh\nexec " + shlex.quote(str(binary)) + ' "$@"\n')
                launcher.chmod(0o755)
                (wine / ".complete").touch()
                shutil.rmtree(wine / "archives")
            prefix = wine / "root"
            windows32 = prefix / "usr/lib/i386-linux-gnu/wine/i386-windows/ntdll.dll"
            compatibility_marker = wine / ".wow64-complete"
            if not compatibility_marker.is_file() or not windows32.is_file():
                (wine / "archives/partial").mkdir(parents=True, exist_ok=True)
                run(
                    ["apt-get", *options, "update"],
                    cache,
                    "Fetching signed 32-bit Windows runtime metadata",
                )
                run(
                    ["apt-get", *options, "download", "libwine:i386"],
                    wine / "archives",
                    "Downloading 32-bit Windows DLLs for installers",
                )
                for deb in (wine / "archives").glob("libwine_*_i386.deb"):
                    run(
                        ["dpkg-deb", "-x", str(deb), str(prefix)],
                        cache,
                        "Preparing Windows installer compatibility",
                    )
                if not windows32.is_file():
                    raise ValueError("Wine's 32-bit Windows runtime is unavailable")
                shutil.rmtree(cache / "wine-prefix", ignore_errors=True)
                shutil.rmtree(wine / "archives")
                compatibility_marker.touch()
            for link in (prefix / "usr/lib/x86_64-linux-gnu/wine").rglob("*.dll"):
                if link.is_symlink():
                    target_path = link.readlink()
                    relocated = prefix / str(target_path).lstrip("/")
                    if target_path.is_absolute() and relocated.is_file():
                        link.unlink()
                        link.symlink_to(os.path.relpath(relocated, link.parent))
            for architecture, mingw in (("x86_64", "x86_64"), ("i386", "i686")):
                zlib = prefix / f"usr/{mingw}-w64-mingw32/lib/zlib1.dll"
                link = prefix / f"usr/lib/x86_64-linux-gnu/wine/{architecture}-windows/zlib1.dll"
                if zlib.is_file() and not link.exists():
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(os.path.relpath(zlib, link.parent))
            # Debian's compiled relative lookup appends wine to its wine data directory.
            data_link = prefix / "usr/share/wine/wine"
            data_link.parent.mkdir(parents=True, exist_ok=True)
            if not data_link.exists():
                data_link.symlink_to(".", target_is_directory=True)
            # Debian's dispatcher hardcodes /usr/lib; relocate our private copy.
            server = prefix / "usr/lib/wine/wineserver"
            server.parent.mkdir(parents=True, exist_ok=True)
            server.write_text('#!/bin/sh\nexec "$(dirname "$0")/wineserver64" -p0 "$@"\n')
            server.chmod(0o755)
            os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(
                [
                    str(prefix / "usr/lib/x86_64-linux-gnu"),
                    str(prefix / "lib/x86_64-linux-gnu"),
                    os.environ.get("LD_LIBRARY_PATH", ""),
                ]
            ).rstrip(os.pathsep)
            os.environ["WINEDLLPATH"] = os.pathsep.join(
                [
                    str(prefix / "usr/lib/x86_64-linux-gnu/wine"),
                    str(prefix / "usr/lib/i386-linux-gnu/wine"),
                ]
            )
            os.environ["WINESERVER"] = str(prefix / "usr/lib/wine/wineserver64")
            os.environ["WINELOADER"] = str(prefix / "usr/lib/wine/wine64")
            wine_prefix = cache / "wine-prefix"
            if (
                wine_prefix.exists()
                and not (wine_prefix / "drive_c/windows/system32/kernel32.dll").exists()
            ):
                shutil.rmtree(wine_prefix)
            for directory, mingw in (("system32", "x86_64"), ("syswow64", "i686")):
                zlib = prefix / f"usr/{mingw}-w64-mingw32/lib/zlib1.dll"
                if zlib.is_file():
                    destination = wine_prefix / "drive_c/windows" / directory / "zlib1.dll"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(zlib, destination)
            os.environ["WINEPREFIX"] = str(wine_prefix)
            os.environ["WINEDEBUG"] = "-all"
            os.environ.setdefault("WINEDLLOVERRIDES", "mscoree,mshtml=")
            if not os.environ.get("XDG_RUNTIME_DIR"):
                runtime_dir = cache / "runtime"
                runtime_dir.mkdir(mode=0o700, exist_ok=True)
                os.environ["XDG_RUNTIME_DIR"] = str(runtime_dir)
            os.environ["PATH"] = str(launcher.parent) + os.pathsep + os.environ.get("PATH", "")
            run([str(launcher), "--version"], cache, "Checking cached Wine runtime")
            run(
                [str(launcher), "cmd", "/c", "exit", "0"],
                cache,
                "Initializing cached Windows runtime",
            )
    progress("Build environment ready")
