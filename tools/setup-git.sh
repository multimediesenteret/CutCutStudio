#!/usr/bin/env sh
# Sets the required git identity for this repo (see AGENTS.md section 3).
set -e
git config user.name "Multimediesenteret"
git config user.email "magnus.lian@ntnu.no"
echo "git identity: $(git config user.name) <$(git config user.email)>"
