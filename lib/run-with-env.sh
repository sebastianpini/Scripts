#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <environment> <command> [args...]"
  echo
  echo "Available environments:"
  find env -maxdepth 1 -type f -name '*.env' ! -name 'example.env' -exec basename {} .env \; | sort
  exit 1
fi

ENV_NAME="$1"
shift

ENV_FILE="env/${ENV_NAME}.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Unknown environment: $ENV_NAME"
  echo
  echo "Expected a file at: $ENV_FILE"
  echo "Create it from env/example.env, for example:"
  echo "  cp env/example.env $ENV_FILE"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

exec "$@"
