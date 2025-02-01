#!/bin/bash

# exit when any command fails
set -e

# Use first argument as version if provided, otherwise default to v0.0.1
VERSION=${1:-v0.0.1}
./scripts/blame.py "$VERSION" --all --output llmcode/website/_data/blame.yml
