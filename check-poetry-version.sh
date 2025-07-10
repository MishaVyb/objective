#!/bin/bash
# Fail if Poetry version does not match required version
REQUIRED_VERSION="1.8.2"
CURRENT_VERSION=$(poetry --version 2>/dev/null | awk '{print $3}')
if [ "$CURRENT_VERSION" != "$REQUIRED_VERSION" ]; then
  echo "Poetry version $REQUIRED_VERSION required, but found $CURRENT_VERSION."
  exit 1
fi
