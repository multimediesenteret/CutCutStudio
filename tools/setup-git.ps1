# Sets the required git identity for this repo (see AGENTS.md section 3).
git config user.name "Multimediesenteret"
git config user.email "magnus.lian@ntnu.no"
git config core.hooksPath tools/git-hooks
Write-Host "git identity: $(git config user.name) <$(git config user.email)>"
