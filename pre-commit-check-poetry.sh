#!/bin/bash
# Fail if Poetry version does not match required version
REQUIRED_VERSION="2.1.3"
CURRENT_VERSION=$(poetry --version 2>/dev/null | awk '{print $3}' | tr -d '[:space:])')
if [ "$CURRENT_VERSION" != "$REQUIRED_VERSION" ]; then
  echo "Poetry version $REQUIRED_VERSION required, but found $CURRENT_VERSION."
  exit 1
fi
