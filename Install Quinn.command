#!/bin/bash
# ============================================================
#  Install Quinn — double-click me!
#  This window walks you through the whole setup in plain words.
#  Safe to run again any time.
# ============================================================

cd "$(dirname "$0")"

on_error() {
  printf "\n\033[1;31m✗ Something went wrong during setup.\033[0m\n"
  printf "  Don't worry — nothing is broken. You can close this window,\n"
  printf "  then double-click Install Quinn again to retry.\n\n"
  read -r -p "Press return to close this window… " _
  exit 1
}
trap on_error ERR

bash ./setup.sh
