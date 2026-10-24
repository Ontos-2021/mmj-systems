#!/bin/sh
# Verify the static HTTP surface only; this never calls the contact API.
set -eu
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
trap 'exit 1' HUP INT TERM
root=/usr/share/nginx/html

for asset in index.html styles.css main.js; do
    test -s "$root/$asset" || exit 1
    path=/$asset
    if [ "$asset" = index.html ]; then path=/; fi
    status=$(curl -q --noproxy '*' --silent --output "$work/body" \
        --write-out '%{http_code}' --connect-timeout 1 --max-time 1 \
        --max-filesize 2097152 "http://127.0.0.1$path") || exit 1
    [ "$status" = 200 ] || exit 1
    cmp -s "$root/$asset" "$work/body" || exit 1
done

status=$(curl -q --noproxy '*' --silent --output "$work/body" \
    --write-out '%{http_code}' --connect-timeout 1 --max-time 1 \
    --max-filesize 2097152 'http://127.0.0.1/__mmj_health_missing__') || exit 1
[ "$status" = 404 ] || exit 1
