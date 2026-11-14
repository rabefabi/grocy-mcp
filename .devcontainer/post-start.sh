#!/bin/bash
# The devcontainer feature `docker-in-docker` installs dockerd but doesn't start
# it automatically when a custom postStartCommand is set, because devcontainer
# merges feature lifecycle hooks only when no override is present. We call the
# feature's own init script explicitly to start the daemon and block until it
# responds to `docker info`.
#
# iptables-nft must be active before dockerd starts: the kernel in this container
# exposes the nftables (nf_tables) backend only — the legacy iptables `nat` module
# is absent, which causes dockerd to abort with "Table does not exist (do you need
# to insmod?)". Switching the system alternative to iptables-nft makes dockerd use
# the available backend.
sudo update-alternatives --set iptables /usr/sbin/iptables-nft
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-nft
sudo /usr/local/share/docker-init.sh
