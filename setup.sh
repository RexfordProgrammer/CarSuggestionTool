#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Check for Python
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Error: Python not found. Please install it from https://www.python.org/downloads/."
  exit 1
fi

# Create virtual environment if needed
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  "$PY" -m venv venv
else
  echo "Using existing virtual environment at ./venv"
fi

VENV_PY="./venv/bin/python"

# Upgrade pip and install dependencies
echo "Upgrading pip and core packaging tools..."
"$VENV_PY" -m pip install --upgrade pip setuptools wheel

if [ -f "requirements.txt" ]; then
  echo "Installing or updating dependencies from requirements.txt..."
  "$VENV_PY" -m pip install --upgrade --upgrade-strategy eager -r requirements.txt
else
  echo "No requirements.txt found; skipping dependency installation."
fi

# Create activation helper
cat > enter_venv.sh <<'EOF'
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source ./venv/bin/activate
echo "Virtual environment activated. To deactivate, run: deactivate"
exec "${SHELL:-bash}" -i
EOF
chmod +x enter_venv.sh

echo
echo "Setup complete."
echo "To activate the environment later, run:  ./enter_venv.sh"
echo "Or manually: source venv/bin/activate"
