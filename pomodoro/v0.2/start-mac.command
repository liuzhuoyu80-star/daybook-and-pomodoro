#!/bin/sh
set -eu

cd "$(dirname "$0")"
app_dir=$(pwd -P)
if [ "$(uname -s)" != Darwin ]; then
    echo '请在 Mac 上打开这个启动文件。' >&2
    exit 1
fi
os_version=$(/usr/bin/sw_vers -productVersion)
if [ "${os_version%%.*}" -lt 12 ]; then
    echo '浮动番茄钟 v0.2 需要 macOS 12 或更高版本。' >&2
    exit 1
fi
case "$(uname -m)" in
    arm64) arch=aarch64; digest=0de87cfc2649849da10a54084f87fd01fa1e653478e32eee92198c213550e15c ;;
    x86_64) arch=x86_64; digest=da628e539cebac13f43a3dc42dd99826aeab254387d3bc43478a73267a362713 ;;
    *) echo '此包适用于 Apple 芯片和 Intel 芯片的 Mac。' >&2; exit 1 ;;
esac

cache="$HOME/Library/Application Support/FloatingTimer/v0.2"
runtime="$cache/python-3.12.16-qt-6.8.3-$arch"
if [ ! -x "$runtime/bin/python3" ]; then
    echo '正在准备浮动番茄钟。首次启动需要联网下载约 160 MB，请保持终端窗口打开。'
    umask 077
    mkdir -p "$cache"
    work=$(mktemp -d "$cache/setup.XXXXXXXX")
    trap 'rm -rf "$work"' EXIT
    trap 'exit 1' HUP INT TERM
    archive="cpython-3.12.16%2B20261123-$arch-apple-darwin-install_only_stripped.tar.gz"
    /usr/bin/curl --fail --location --retry 3 --connect-timeout 20 --progress-bar \
        "https://github.com/astral-sh/python-build-standalone/releases/download/20261123/$archive" -o "$work/python.tar.gz"
    (cd "$work" && printf '%s  python.tar.gz\n' "$digest" | /usr/bin/shasum -a 256 -c -)
    /usr/bin/tar -xzf "$work/python.tar.gz" -C "$work"
    "$work/python/bin/python3" -I -m pip --isolated --disable-pip-version-check install \
        --index-url https://pypi.org/simple --only-binary=:all: --require-hashes \
        --no-cache-dir -r "$app_dir/requirements.txt"
    "$work/python/bin/python3" -I -c 'from PySide6 import QtWidgets, QtSvg'
    # Publish only a complete runtime, even when two launches finish setup together.
    "$work/python/bin/python3" -I - "$work/python" "$runtime" <<'PY'
import errno
import os
import sys

source, target = sys.argv[1:]
try:
    os.rename(source, target)
except OSError as exc:
    if exc.errno not in (errno.EEXIST, errno.ENOTEMPTY) or not os.path.isfile(target + "/bin/python3"):
        raise
PY
    rm -rf "$work"
    trap - EXIT HUP INT TERM
fi
exec "$runtime/bin/python3" -E -s -B "$app_dir/main.py"
