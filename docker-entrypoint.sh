#!/bin/sh
# Start as root only long enough to fix ownership of the mounted disk, then drop privileges.
set -e

if [ "$(id -u)" = "0" ]; then
    mkdir -p /data
    chown app:app /data
    exec setpriv --reuid=app --regid=app --init-groups "$@"
fi

exec "$@"
