#!/bin/sh
set -e

case "${ATLAS_PROCESS:-web}" in
  worker)
    python -m app.worker_health &
    exec sh ./docker-entrypoint.sh python -m app.worker
    ;;
  web)
    exec sh ./docker-entrypoint.sh
    ;;
  *)
    echo "Unknown ATLAS_PROCESS '${ATLAS_PROCESS}'. Expected 'web' or 'worker'." >&2
    exit 1
    ;;
esac
