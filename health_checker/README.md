# Axocare Health Checker

Small Go checker intended for cron or a systemd timer. It calls the Axocare API
health endpoint and sends a Pushover notification when the API is unreachable,
returns a bad status, or reports the control loop as anything other than `ok`.

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
