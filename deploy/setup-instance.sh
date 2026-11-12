#!/usr/bin/env bash
# Sets up and (re)starts Patternly on an Ubuntu 24.04 EC2 instance. Safe to run again: the first run
# installs Docker, adds swap, and creates the secrets; later runs pull the latest code and rebuild.
#
# Usage (as root): setup-instance.sh <aws-region> <ssm-parameter-prefix>
# The tutor's API key is read from the SecureString parameter <prefix>/anthropic-api-key. If it is
# missing, the API runs with --offline (word matching, no API calls). Also installs an hourly systemd
# timer that sends reminder emails (deploy/remind.sh).
set -euo pipefail

REGION=${1:?region}
PREFIX=${2:?ssm parameter prefix, e.g. /patternly}
APP_DIR=/opt/patternly
REPO=https://github.com/contract-s/patternly.git

log() { echo "[setup] $*"; }

if ! command -v docker >/dev/null; then
  log "installing Docker"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  apt-get install -y -q docker.io docker-compose-v2 docker-buildx git unzip
  systemctl enable --now docker
fi

if ! command -v aws >/dev/null; then
  log "installing the AWS CLI"
  snap install aws-cli --classic
fi

if [ ! -f /swapfile ]; then
  log "adding 2 GB of swap"
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

if [ -d "$APP_DIR/.git" ]; then
  log "updating to the latest main"
  # fetch + reset rather than pull: the server never has commits of its own, and this also follows a
  # rewritten history. Untracked secrets (.env, backend/.env, deploy/jwt-secret) are gitignored and kept.
  git -C "$APP_DIR" fetch --quiet origin main
  git -C "$APP_DIR" reset --quiet --hard origin/main
else
  log "cloning $REPO"
  git clone "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

# Secrets generated on the instance stay on it (root-only files, never in git or CloudFormation).
umask 077
if [ ! -f .env ]; then
  log "generating the database password"
  echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)" >.env
fi
grep -q '^AWS_REGION=' .env || echo "AWS_REGION=$REGION" >>.env
if [ ! -f deploy/jwt-secret ]; then
  openssl rand -hex 32 >deploy/jwt-secret
fi

if key=$(aws ssm get-parameter --region "$REGION" --name "$PREFIX/anthropic-api-key" \
  --with-decryption --query Parameter.Value --output text 2>/dev/null); then
  api_flags=""
else
  log "no $PREFIX/anthropic-api-key parameter; the API will grade offline"
  key=""
  api_flags="--offline"
fi
{
  echo "ANTHROPIC_API_KEY=$key"
  echo "JWT_SECRET=$(cat deploy/jwt-secret)"
  echo "API_FLAGS=$api_flags"
} >backend/.env
umask 022

log "building and starting the app"
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml --profile app up -d --build --remove-orphans
docker image prune -f >/dev/null

log "installing the hourly reminder timer"
printf 'REGION=%s\nPREFIX=%s\n' "$REGION" "$PREFIX" >/etc/patternly-remind.env
cp deploy/systemd/patternly-remind.service deploy/systemd/patternly-remind.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now patternly-remind.timer
log "done"
