#!/usr/bin/env bash
set -e

# ==============================================================================
#   Sverchok Spotlight Suite - Installer for Linux & macOS
#   Target: Blender 4.2 LTS + Sverchok v1.4.0+
# ==============================================================================

echo "================================================================"
echo "  Sverchok Spotlight Suite - Installer for Linux & macOS"
echo "  Target: Blender 4.2 LTS + Sverchok v1.4.0+"
echo "================================================================"
echo ""

# 1. Detect Operating System
OS="$(uname -s)"
ARCH="$(uname -m)"
echo "[*] Detected Platform: ${OS} (${ARCH})"

# 2. Locate or Install Blender 4.2
BLENDER_BIN=""

if command -v blender >/dev/null 2>&1; then
    VER=$(blender -v | head -n 1 || true)
    echo "[*] Found blender command in PATH: ${VER}"
    BLENDER_BIN="blender"
elif [ "${OS}" = "Darwin" ]; then
    if [ -x "/Applications/Blender.app/Contents/MacOS/Blender" ]; then
        BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
    elif [ -x "$HOME/Applications/Blender.app/Contents/MacOS/Blender" ]; then
        BLENDER_BIN="$HOME/Applications/Blender.app/Contents/MacOS/Blender"
    fi
fi

if [ -z "${BLENDER_BIN}" ]; then
    echo "[!] Blender 4.2 not found in standard system locations."
    if [ "${OS}" = "Darwin" ]; then
        if command -v brew >/dev/null 2>&1; then
            echo "[*] Installing Blender via Homebrew..."
            brew install --cask blender
            BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
        else
            echo "[*] Downloading official Blender 4.2 for macOS..."
            DMG_NAME="blender-4.2.0-macos-arm64.dmg"
            if [ "${ARCH}" = "x86_64" ]; then
                DMG_NAME="blender-4.2.0-macos-x64.dmg"
            fi
            curl -L -o "/tmp/${DMG_NAME}" "https://download.blender.org/release/Blender4.2/${DMG_NAME}"
            echo "[*] Mounting DMG..."
            hdiutil attach "/tmp/${DMG_NAME}" -mountpoint /Volumes/Blender
            echo "[*] Copying Blender to /Applications..."
            cp -R "/Volumes/Blender/Blender.app" /Applications/
            hdiutil detach /Volumes/Blender
            rm "/tmp/${DMG_NAME}"
            BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
        fi
    elif [ "${OS}" = "Linux" ]; then
        echo "[*] Downloading portable Blender 4.2 LTS for Linux x86_64..."
        INSTALL_DIR="$HOME/.local/opt/blender-4.2"
        mkdir -p "${INSTALL_DIR}"
        curl -L -o "/tmp/blender-4.2.tar.xz" "https://download.blender.org/release/Blender4.2/blender-4.2.0-linux-x64.tar.xz"
        echo "[*] Extracting to ${INSTALL_DIR}..."
        tar -xf "/tmp/blender-4.2.tar.xz" -C "${INSTALL_DIR}" --strip-components=1
        rm "/tmp/blender-4.2.tar.xz"
        BLENDER_BIN="${INSTALL_DIR}/blender"
    fi
fi

if [ -z "${BLENDER_BIN}" ] || [ ! -x "$(command -v "${BLENDER_BIN}" || echo "${BLENDER_BIN}")" ]; then
    echo "[ERROR] Could not automatically locate or install Blender 4.2."
    echo "Please install Blender 4.2 from https://www.blender.org/download/ and re-run."
    exit 1
fi

echo "[OK] Using Blender: ${BLENDER_BIN}"
echo ""

# 3. Determine Blender 4.2 Addons Directory
if [ "${OS}" = "Darwin" ]; then
    ADDONS_DIR="$HOME/Library/Application Support/Blender/4.2/scripts/addons"
else
    ADDONS_DIR="$HOME/.config/blender/4.2/scripts/addons"
fi

echo "[*] Addons Directory: ${ADDONS_DIR}"
mkdir -p "${ADDONS_DIR}"

# 4. Install Sverchok v1.4.0+
if [ -f "${ADDONS_DIR}/sverchok/__init__.py" ]; then
    echo "[OK] Sverchok addon already installed in ${ADDONS_DIR}/sverchok."
else
    echo "[*] Installing Sverchok v1.4.0+..."
    if command -v git >/dev/null 2>&1; then
        echo "[*] Cloning Sverchok repository via git..."
        git clone --depth 1 https://github.com/nortikin/sverchok.git "${ADDONS_DIR}/sverchok"
    else
        echo "[*] Downloading Sverchok master zip..."
        curl -L -o "/tmp/sverchok.zip" "https://github.com/nortikin/sverchok/archive/refs/heads/master.zip"
        unzip -q "/tmp/sverchok.zip" -d "${ADDONS_DIR}"
        mv "${ADDONS_DIR}/sverchok-master" "${ADDONS_DIR}/sverchok"
        rm "/tmp/sverchok.zip"
    fi
    echo "[OK] Sverchok installed successfully."
fi
echo ""

# 5. Install Sverchok Spotlight Addon
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_SPOTLIGHT="${ADDONS_DIR}/sverchok_spotlight"

echo "[*] Installing Sverchok Spotlight from: ${SCRIPT_DIR}"
echo "[*] Target: ${TARGET_SPOTLIGHT}"

if [ "${SCRIPT_DIR}" = "${TARGET_SPOTLIGHT}" ]; then
    echo "[OK] Already in Blender addons directory."
else
    mkdir -p "${TARGET_SPOTLIGHT}"
    if command -v rsync >/dev/null 2>&1; then
        rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.zip' --exclude='*.log' "${SCRIPT_DIR}/" "${TARGET_SPOTLIGHT}/"
    else
        cp -R "${SCRIPT_DIR}/"* "${TARGET_SPOTLIGHT}/"
    fi
    echo "[OK] Sverchok Spotlight copied to Blender addons directory."
fi
echo ""

# 6. Enable Addons in Blender 4.2
echo "[*] Enabling Sverchok and Sverchok Spotlight in Blender user preferences..."
"${BLENDER_BIN}" -b --python-expr "import bpy; bpy.ops.preferences.addon_enable(module='sverchok'); bpy.ops.preferences.addon_enable(module='sverchok_spotlight'); bpy.ops.wm.save_userpref(); print('\n[VERIFIED] Sverchok & Sverchok Spotlight enabled in Blender 4.2!')"

# 7. Run Verification Test Suite
echo ""
echo "[*] Running verification test suite..."
if "${BLENDER_BIN}" -b --python "${TARGET_SPOTLIGHT}/test_spotlight_v2.py"; then
    echo ""
    echo "================================================================"
    echo "  INSTALLATION AND VERIFICATION COMPLETED SUCCESSFULLY (100%)!"
    echo "  Launch Blender 4.2 to use the Spotlight node suite in Sverchok."
    echo "================================================================"
else
    echo ""
    echo "[!] Addons installed, but one or more verification tests raised a warning."
fi
