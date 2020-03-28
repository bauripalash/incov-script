#!/usr/bin/env bash

set -eu

REPO_URL="https://x-access-token:${GHTOKEN}@github.com/bauripalash/ncov-19-india.git"
REPO_BRANCH="master"

mkdir data
cd data
git config user.name "$GITHUB_ACTOR"
git config user.email "${GITHUB_ACTOR}@bots.github.com"
git clone https://github.com/bauripalash/ncov-19-india.git
cd ..
python incov.py
cd data
git add *.csv
git add *.json
set +e
git status | grep "new file\|modified"
if [ $? -eq 0 ]
then
    set -e
    git commit -am ":bug: $(date)"
    git remote set-url "origin" "$REPO_URL"
    git push --force-with-lease "origin" "$REPO_BRANCH"
else
    set -e
    echo "[X] ALREADY UPDATED"
fi

echo "finish"