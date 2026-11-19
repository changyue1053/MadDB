#!/usr/bin/env bash
# Anonymous exact public source staging. No inherited Git config/authentication.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
root=$PWD
mkdir -p target/obs-real
exec 3>&1
exec >>target/obs-real/header-stage.log 2>&1
stage=public-obs-header
trap 'printf "FAIL: %s\n" "$stage" >&3' ERR
pin=4af77ffa464a48307e5ff2d95f10b835919d205b
blob=2fd8c8cc81b2e38569c2b2ce3cd5fec03ffcf001
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
mkdir "$scratch/home" "$scratch/repo"
# env -i removes GIT_CONFIG_COUNT/PARAMETERS, askpass, tokens, SSH commands,
# URL rewrites and all other inherited environment authentication mechanisms.
# Fresh HOME/repo plus disabled system/global config also exclude local helpers.
public_git() {
  env -i PATH="$PATH" HOME="$scratch/home" LC_ALL=C \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
    git -C "$scratch/repo" -c credential.helper= -c http.extraHeader= "$@"
}
public_git init -q
public_git fetch --depth=1 --no-tags https://github.com/changyue1053/MadObs.git "$pin"
[[ $(public_git rev-parse FETCH_HEAD) == "$pin" ]]
[[ $(public_git rev-parse "FETCH_HEAD:include/madobs/observer.h") == "$blob" ]]
# Do not copy a checkout, archive, library or any other upstream file.
out="$root/target/obs-header/include/madobs"
mkdir -p "$out"
[[ ! -e "$out/observer.h" ]]
public_git show 'FETCH_HEAD:include/madobs/observer.h' >"$scratch/observer.h"
[[ $(public_git hash-object "$scratch/observer.h") == "$blob" ]]
cp "$scratch/observer.h" "$out/observer.h"
printf 'PASS: exact anonymous public observer header staged\n' >&3
