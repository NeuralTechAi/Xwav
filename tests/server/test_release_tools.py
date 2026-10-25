"""Rootless provisioning contracts; real downloads are a separate smoke check."""

import hashlib
import io
import json
import os
import tarfile
import time
import zipfile
from unittest.mock import Mock

import pytest

from omnigent import release_tools as tools


@pytest.fixture
def environment(tmp_path, monkeypatch):
    for key in (
        "ANDROID_HOME",
        "ANDROID_SDK_ROOT",
        "JAVA_HOME",
        "PATH",
        "NPM_CONFIG_CACHE",
        "ELECTRON_CACHE",
        "ELECTRON_BUILDER_CACHE",
        "GRADLE_USER_HOME",
        "npm_config_store_dir",
        "YARN_CACHE_FOLDER",
        "BUN_INSTALL_CACHE_DIR",
    ):
        value = os.environ.get(key)
        monkeypatch.setenv(key, value or "")
        if value is None:
            monkeypatch.delenv(key)
    monkeypatch.setenv("XWAV_BUILD_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(tools.platform, "system", lambda: "Linux")
    monkeypatch.setattr(tools.platform, "machine", lambda: "x86_64")
    return {
        "cancel": tmp_path / "cancel",
        "deadline": time.monotonic() + 60,
        "run": Mock(),
        "progress": Mock(),
    }


def test_node_setup_is_rootless_and_reuses_completed_cache(tmp_path, monkeypatch, environment):
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    original_path = os.environ["PATH"]
    with monkeypatch.context() as scope:
        scope.setenv("PATH", original_path)
        node = tools.cache_root() / "node-22"

        def install(name, *args):
            assert name == "node-22"
            (node / "bin").mkdir(parents=True, exist_ok=True)
            return node

        scope.setattr(tools, "portable", Mock(side_effect=install))
        tools.prepare("web", needs_node=True, accept_android_licenses=False, **environment)
        assert os.environ["PATH"].startswith(str(node / "bin"))
        assert not environment["run"].called


def test_android_no_licence_does_not_download(tmp_path, monkeypatch, environment):
    monkeypatch.setenv("JAVA_HOME", "/configured/jdk")
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    fetch = Mock()
    monkeypatch.setattr(tools, "portable", fetch)
    with pytest.raises(ValueError, match="Accept the Android"):
        tools.prepare("android", needs_node=False, accept_android_licenses=False, **environment)
    fetch.assert_not_called()


def test_android_acceptance_runs_in_worker_and_reuses_sdk(tmp_path, monkeypatch, environment):
    monkeypatch.setenv("JAVA_HOME", "/configured/jdk")
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    sdk = tools.cache_root() / "android-sdk"
    package = tmp_path / "downloaded-tools"
    (package / "bin").mkdir(parents=True)
    (package / "bin/sdkmanager").touch()
    install = Mock(return_value=package)
    monkeypatch.setattr(tools, "portable", install)

    def run(command, cwd, phase):
        assert "--licenses" in command
        (sdk / "licenses").mkdir(exist_ok=True)
        (sdk / "licenses/android-sdk-license").write_text("accepted")

    environment["run"].side_effect = run
    tools.prepare("android", needs_node=False, accept_android_licenses=True, **environment)
    tools.prepare("android", needs_node=False, accept_android_licenses=False, **environment)
    assert install.call_count == 1
    assert environment["run"].call_count == 1
    assert os.environ["ANDROID_HOME"] == str(sdk)


def test_lock_and_download_are_cancellable(environment):
    environment["cancel"].touch()
    with pytest.raises(RuntimeError, match="Cancelled"):
        with tools.locked(tools.cache_root(), environment["cancel"], environment["deadline"]):
            pytest.fail("cancelled setup entered cache lock")


@pytest.mark.parametrize("member", ["../../escape", "/absolute"])
def test_archive_traversal_is_rejected(tmp_path, member):
    archive = tmp_path / "sdk.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(member, "unsafe")
    with pytest.raises(ValueError, match="Unsafe"):
        tools.unpack(archive, tmp_path / "out")


def test_tar_preserves_safe_npm_links(tmp_path):
    archive = tmp_path / "node.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        file = tarfile.TarInfo("node/lib/npm.js")
        file.size = 2
        bundle.addfile(file, io.BytesIO(b"ok"))
        link = tarfile.TarInfo("node/bin/npm")
        link.type, link.linkname = tarfile.SYMTYPE, "../lib/npm.js"
        bundle.addfile(link)
    tools.unpack(archive, tmp_path / "out")
    assert (tmp_path / "out/node/bin/npm").read_text() == "ok"


def test_download_checksum_and_https_enforced(tmp_path, monkeypatch, environment):
    response = io.BytesIO(b"corrupt")
    response.url = "https://example.test/tool"
    monkeypatch.setattr(tools.urllib.request, "urlopen", lambda *a, **k: response)
    destination = tmp_path / "download"
    with pytest.raises(ValueError, match="checksum"):
        tools.download(
            response.url,
            destination,
            environment["cancel"],
            environment["deadline"],
            hashlib.sha256(b"correct").hexdigest(),
        )
    assert not destination.exists()
    with pytest.raises(ValueError, match="HTTPS"):
        tools.download(
            "http://example.test/tool", destination, environment["cancel"], environment["deadline"]
        )


def test_completed_portable_tool_never_downloads(tmp_path, monkeypatch, environment):
    destination = tools.cache_root() / "node-22"
    destination.mkdir(parents=True)
    (destination / ".complete").write_text(json.dumps({"sha256": "verified"}))
    (destination / "bin").mkdir()
    (destination / "bin/node").touch()
    download = Mock(side_effect=AssertionError("cached tool downloaded again"))
    monkeypatch.setattr(tools, "download", download)
    assert (
        tools.portable(
            "node-22",
            tools.cache_root(),
            environment["cancel"],
            environment["deadline"],
            environment["progress"],
        )
        == destination
    )


@pytest.mark.parametrize(
    "version,ready", [("v20.19.0", False), ("v22.23.0", True), ("bad", False)]
)
def test_node_requires_supported_runtime(monkeypatch, version, ready):
    monkeypatch.setattr(tools.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(tools.subprocess, "run", lambda *a, **k: Mock(stdout=version))
    assert tools.node_ready() is ready


def test_invalid_tar_is_a_reportable_error(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    archive.write_bytes(b"invalid archive")
    with pytest.raises(ValueError, match="Invalid or unsafe"):
        tools.unpack(archive, tmp_path / "out")


def test_cached_wine_sets_relocated_loader_and_server(monkeypatch, environment):
    monkeypatch.setattr(tools, "wine_bootstrap_supported", lambda: True)
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    for key in (
        "WINESERVER",
        "WINELOADER",
        "WINEDLLPATH",
        "WINEPREFIX",
        "WINEDEBUG",
        "LD_LIBRARY_PATH",
        "XDG_RUNTIME_DIR",
        "WINEDLLOVERRIDES",
    ):
        monkeypatch.setenv(key, os.environ.get(key, ""))
    wine = tools.cache_root() / "wine-debian"
    wine.mkdir(parents=True)
    (wine / ".complete").touch()
    data = wine / "root/usr/share/wine/nls/l_intl.nls"
    data.parent.mkdir(parents=True)
    data.touch()
    windows32 = wine / "root/usr/lib/i386-linux-gnu/wine/i386-windows/ntdll.dll"
    windows32.parent.mkdir(parents=True)
    windows32.touch()
    (wine / ".wow64-complete").touch()
    dll = wine / "root/usr/lib/x86_64-linux-gnu/wine/x86_64-windows/zlib1.dll"
    dll.parent.mkdir(parents=True)
    original = wine / "root/usr/x86_64-w64-mingw32/lib/zlib1.dll"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"DLL")
    dll.symlink_to("/usr/x86_64-w64-mingw32/lib/zlib1.dll")
    zlib32 = wine / "root/usr/i686-w64-mingw32/lib/zlib1.dll"
    zlib32.parent.mkdir(parents=True)
    zlib32.write_bytes(b"DLL32")
    tools.prepare("windows", needs_node=False, accept_android_licenses=False, **environment)
    assert (
        wine / "root/usr/lib/x86_64-linux-gnu/wine/i386-windows/zlib1.dll"
    ).read_bytes() == b"DLL32"
    assert (
        tools.cache_root() / "wine-prefix/drive_c/windows/system32/zlib1.dll"
    ).read_bytes() == b"DLL"
    assert dll.read_bytes() == b"DLL"
    assert not dll.readlink().is_absolute()
    assert (wine / "root/usr/share/wine/wine").resolve() == wine / "root/usr/share/wine"
    assert os.environ["WINESERVER"] == str(wine / "root/usr/lib/wine/wineserver64")
    assert os.environ["WINELOADER"] == str(wine / "root/usr/lib/wine/wine64")
    assert '$(dirname "$0")/wineserver64' in (wine / "root/usr/lib/wine/wineserver").read_text()
    assert environment["run"].call_count == 2
    assert environment["run"].call_args_list[0].args[0] == [str(wine / "bin/wine"), "--version"]
    assert environment["run"].call_args.args[0] == [
        str(wine / "bin/wine"),
        "cmd",
        "/c",
        "exit",
        "0",
    ]


def test_project_package_manager_is_cached_privately(monkeypatch, environment):
    monkeypatch.setattr(tools, "node_ready", lambda: True)

    def run(command, cwd, phase):
        destination = (
            tools.cache_root()
            / "package-managers"
            / hashlib.sha256(b"pnpm@9.15.0").hexdigest()[:16]
        )
        binary = destination / "node_modules/.bin/pnpm"
        binary.parent.mkdir(parents=True)
        binary.touch()
        assert command[-1] == "pnpm@9.15.0"

    environment["run"].side_effect = run
    for _ in range(2):
        tools.prepare(
            "web",
            needs_node=True,
            accept_android_licenses=False,
            package_manager="pnpm@9.15.0",
            **environment,
        )
    assert environment["run"].call_count == 1


def test_missing_cached_node_binary_is_reinstalled(monkeypatch, environment):
    destination = tools.cache_root() / "node-22"
    destination.mkdir(parents=True)
    (destination / ".complete").touch()
    download = Mock(side_effect=RuntimeError("download attempted"))
    monkeypatch.setattr(tools, "metadata", download)
    with pytest.raises(RuntimeError, match="download attempted"):
        tools.portable(
            "node-22",
            tools.cache_root(),
            environment["cancel"],
            environment["deadline"],
            environment["progress"],
        )
    download.assert_called_once()
