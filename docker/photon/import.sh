#!/bin/sh
set -eu
cd /data
if [ -d photon_data ]; then
    echo 'photon_data already exists; use a fresh volume for an index refresh.' >&2
    exit 1
fi
# Preprocessed regional OSM index: Photon cannot import a Geofabrik .osm.pbf directly.
curl -fL --retry 3 https://download1.graphhopper.com/public/asia/india/photon-db-india-1.0-latest.tar.bz2 -o india.tar.bz2
tar -tjf india.tar.bz2 > archive-list.txt
if grep -Eq '(^/|(^|/)\.\.(/|$))' archive-list.txt; then
    echo 'Unsafe archive paths' >&2
    exit 1
fi
tar -xjf india.tar.bz2
test -d photon_data
rm india.tar.bz2 archive-list.txt
echo 'India index loaded. Retain OSM attribution and ODbL notice when distributing the index.'
