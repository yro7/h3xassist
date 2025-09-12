#!/usr/bin/env bash
set -Eeuo pipefail

# -------- Config --------
CUDNN_VER="8.9.7.29"                             # cuDNN 8.x (provides libcudnn_ops_infer.so.8)
WHEEL_SPEC="nvidia-cudnn-cu12==${CUDNN_VER}"
CACHE_DIR="${HOME}/.cache/cudnn8"
EXTRACT_DIR="${CACHE_DIR}/extracted"
SYS_LIB_DIR="/var/opt/cudnn8/lib"
CONF_FILE="/etc/ld.so.conf.d/cudnn8.conf"

have() { command -v "$1" >/dev/null 2>&1; }

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m✔\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m✘ %s\033[0m\n' "$*" >&2; exit 1; }

trap 'die "Error on line $LINENO"' ERR

log "Preparing directories"
mkdir -p "$CACHE_DIR" "$EXTRACT_DIR"

# -------- 1) Download cuDNN 8 wheel (no env install) --------
log "Downloading ${WHEEL_SPEC}"
if have uvx; then
  uvx pip download "$WHEEL_SPEC" -d "$CACHE_DIR"
elif have python3; then
  python3 -m ensurepip --upgrade >/dev/null 2>&1 || true
  python3 -m pip download "$WHEEL_SPEC" -d "$CACHE_DIR"
else
  die "Need either 'uvx' or 'python3' with pip"
fi

WHEEL="$(ls -1 "${CACHE_DIR}"/nvidia_cudnn_cu12-"${CUDNN_VER}"*.whl 2>/dev/null | head -n1)"
[ -f "$WHEEL" ] || die "Wheel not found in ${CACHE_DIR}"

ok "Wheel: $(basename "$WHEEL")"

# -------- 2) Extract wheel --------
log "Extracting into ${EXTRACT_DIR}"
python3 - "$WHEEL" "$EXTRACT_DIR" <<'PY'
import sys, zipfile, os
wheel, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(wheel) as z: z.extractall(dst)
print(os.path.join(dst, "nvidia", "cudnn", "lib"))
PY

LIB_SRC="${EXTRACT_DIR}/nvidia/cudnn/lib"
[ -d "$LIB_SRC" ] || die "Library dir not found: $LIB_SRC"
ok "Found libraries in ${LIB_SRC}"

# -------- 3) Copy .so.8 to system dir --------
log "Copying .so.8 files into ${SYS_LIB_DIR}"
sudo install -d -m 0755 "$SYS_LIB_DIR"
shopt -s nullglob
CAND=("$LIB_SRC"/libcudnn*so.8*)
[ ${#CAND[@]} -gt 0 ] || die "No libcudnn*.so.8* files in the wheel; check version"
sudo cp -f "$LIB_SRC"/libcudnn*so.8* "$SYS_LIB_DIR"/

# Create short *.so.8 symlinks if missing
log "Creating *.so.8 symlinks"
pushd "$SYS_LIB_DIR" >/dev/null
for f in libcudnn*.so.8.*; do
  base="${f%.so.*}.so.8"
  sudo ln -sf "$f" "$base"
done
if ls libcudnn.so.8.* >/dev/null 2>&1; then
  sudo ln -sf "$(ls -1 libcudnn.so.8.* | head -n1)" "libcudnn.so.8"
fi
popd >/dev/null
ok "Symlinks ensured"

# -------- 4) Register with ldconfig --------
log "Registering path with ldconfig"
echo "$SYS_LIB_DIR" | sudo tee "$CONF_FILE" >/dev/null
sudo ldconfig
command -v restorecon >/dev/null 2>&1 && sudo restorecon -RFv /var/opt/cudnn8 >/dev/null || true
ok "ldconfig updated"

# -------- 5) Checks --------
log "System-level check"
if ! ldconfig -p | grep -E 'libcudnn_ops_infer\.so\.8' >/dev/null; then
  die "ldconfig does not see libcudnn_ops_infer.so.8 in ${SYS_LIB_DIR}"
fi
ok "libcudnn_ops_infer.so.8 is visible to the system"

if have uv; then
  log "Python load check (via uv)"
  uv run python - <<'PY'
import ctypes
ctypes.CDLL("libcudnn_ops_infer.so.8")
print("OK: libcudnn_ops_infer.so.8 loadable via system ldconfig")
PY
  ok "Python confirmed .so.8 availability"
else
  ok "uv not found — skipping Python check"
fi

log "Done. You can run h3xassist without LD_LIBRARY_PATH"
