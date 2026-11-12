#!/usr/bin/env bash
# Runs `patternly remind` inside the API container. Started hourly by patternly-remind.timer.
# The sender address and app URL come from SSM parameters the CloudFormation stack writes.
set -euo pipefail

REGION=${1:?region}
PREFIX=${2:?ssm parameter prefix}
cd /opt/patternly

param() {
  aws ssm get-parameter --region "$REGION" --name "$PREFIX/$1" --query Parameter.Value --output text 2>/dev/null || true
}
from=$(param reminder-from)
url=$(param app-url)
if [ -z "$from" ] || [ -z "$url" ]; then
  echo "no $PREFIX/reminder-from or $PREFIX/app-url parameter; skipping"
  exit 0
fi

exec docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml --profile app \
  exec -T -e REMINDER_FROM="$from" -e APP_URL="$url" api patternly remind
