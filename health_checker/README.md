# Axocare Health Checker

Small Go checker intended for cron or a systemd timer. It calls the Axocare API
health endpoint and sends a Pushover notification when the API is unreachable,
returns a bad status, or reports the control loop as anything other than `ok`.
It also sends a recovery notification when a later check succeeds after a
recorded failure. When `AXOCARE_HEALTH_STATE_FILE` is enabled, repeated runs
during the same outage only notify once unless the failure mode changes
(for example DNS failure, timeout, or control-loop error). If the same outage
continues, it sends a reminder every 20 minutes by default.

By default it checks:

```text
http://127.0.0.1:8000/api/health
```

Configure it with a `.env` file in this directory:

```bash
cp .env.example .env
$EDITOR .env
go run .
```

Variables already exported by cron, systemd, or your shell take precedence over
values in `.env`.

Optional settings:

```bash
AXOCARE_HEALTH_URL=http://127.0.0.1:8000/api/health
AXOCARE_HEALTH_STATE_FILE=.health-checker-state.json
AXOCARE_HEALTH_REMINDER_INTERVAL=20m
PUSHOVER_TITLE="Axocare health alert"
```

`AXOCARE_HEALTH_STATE_FILE` stores the previous run status so a oneshot timer can
detect recovery across separate executions. The default path is relative to the
checker working directory. Set `AXOCARE_HEALTH_REMINDER_INTERVAL=0` to disable
reminders for a prolonged outage.

Build for a Raspberry Pi 4 running 64-bit Raspberry Pi OS:

```bash
./build-pi4.sh
```

For 32-bit Raspberry Pi OS:

```bash
GOARCH=arm GOARM=7 OUTPUT=dist/axocare-health-checker-pi4-armv7 ./build-pi4.sh
```

Example systemd service and timer files live in `systemd/`. Adjust paths or user
names if your checkout is not under `/home/pi/axocare`.

```bash
sudo cp systemd/axocare-health-checker.service.example /etc/systemd/system/axocare-health-checker.service
sudo cp systemd/axocare-health-checker.timer.example /etc/systemd/system/axocare-health-checker.timer
sudo systemctl daemon-reload
sudo systemctl enable --now axocare-health-checker.timer
```

Check recent runs with:

```bash
journalctl -u axocare-health-checker.service -n 50
```
