# Filebrowser Sidecar Integration
An admin interface for managing files on Bots in a cloud native environment.

## Methods
- Download the latest binary for your arch from bots repo
- extract filebrowser directory 
- run docker build and push to your preferred repo for use

## Purpose
- Added to allow superadmin manual management of files in the usersys directory

## Deployment Strategy

- Sidecar to webserver deployment
- bots environment aware
- mounts existing RWX pvc on a specified path
- bots file channels respect the configured `path`.
- if `path` is absolute, it is used as-is.
- if `path` is relative, it is resolved under `botsenv` (from `bots.ini`).
- ideally root for filebrowser is `/home/bots/.bots/env/$BOTSENV/` (uses `BOTSENV` from `bots-env-config`)
- uses the latest public Filebrowser image (currently `filebrowser/filebrowser:v2-s6`)
- served on its own ingress host (example: `https://edifiles.k8.pminc.me/`)
- creates directory structure when launched idempotent 
    ROOT/files/incoming, ROOT/files/outgoing, ROOT/files/drop, ROOT/files/pickup
- reads in superuser creation data and creates same user from namespace secret same secret used in the create-superuser-job.yaml
- ingress uses a dedicated host to avoid Django path interception
    - example: https://filebrowser.edi-dev.k8.pminc.me/
- deployed with manifests and added to kustomize deployment method
**note** I am not using overlays I have distinct dev and prod directories I've moved my current deployment tree into the k3s directory.

## Directory Mapping
The four directories may be redundant.
- incoming: files that Bots will pick up (in-channel)
- outgoing: files written by Bots (out-channel)
- drop: organization-facing drop for inbound (optional, flow-specific)
- pickup: organization-facing pickup for outbound (optional, flow-specific)


## Releative vs. Absolute Paths in Channels

When defining `file` channel bots uses the  `botsenv path` as the base directory

### In channels
With an `in` file channel type the path specified is not created by bots and must be created by the user or another process. 

### Out channels 
With an out file channel type the directories are created by bots if they don't exist. Make sure bots has the proper permissions for the path specified. 
