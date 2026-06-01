#!/bin/sh
# Auto-renew Lets Encrypt certs for objective.services (prod + staging) and reload nginx.
# certbot renew is a no-op until a cert is within 30 days of expiry.
# Installed in root crontab; runs weekly. See root: crontab -l
set -e
COMPOSE="/usr/bin/docker-compose -f /home/vybornyy/objective/deploy/production/docker-compose.yml --project-name objective-production"
LOG=/var/log/objective-certbot-renew.log
echo "===== $(date -u) renewal run start =====" >> "$LOG"
$COMPOSE run --rm certbot renew >> "$LOG" 2>&1
$COMPOSE restart nginx >> "$LOG" 2>&1
echo "===== $(date -u) renewal run done =====" >> "$LOG"
