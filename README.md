# Axocare

Axocare is a Raspberry Pi aquarium temperature controller. It reads a DS18B20
temperature sensor, switches a cooling relay through GPIO, stores readings in
SQLite, and exposes a Streamlit dashboard for recent temperature history.

## Hardware

- Raspberry Pi with 1-Wire enabled
- DS18B20 temperature sensor on GPIO 4
- Waveshare RPi Relay Board using CH1 on BCM GPIO 26 / physical pin 37
- Cooling device connected through the relay

The Waveshare RPi Relay Board is low-active, so relay on means GPIO LOW.

## Setup

Install system packages on the Raspberry Pi:

```bash
sudo apt update
sudo apt install git python3-venv python3-rpi.gpio
```

Enable 1-Wire with `sudo raspi-config`, then reboot.

Clone the repo and install Python dependencies:

```bash
git clone https://github.com/TavoJG/axocare.git
cd axocare
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Edit `config.toml`:

```toml
[database]
path = "axocare.db"

[temperature]
target_c = 18.0
cooling_on_c = 18.6
cooling_off_c = 18.0

[control]
interval_seconds = 60

[relay]
pin = 26
active_high = false

[sensor]
id = ""
```

The controller turns the relay on when temperature is greater than or equal to
`cooling_on_c`, turns it off when temperature is less than or equal to
`cooling_off_c`, and keeps the previous relay state between those values.

Leave `sensor.id` empty to use the first detected DS18B20 sensor.

## Run

Start the controller:

```bash
python control.py --config config.toml
```

Run one local dry-run cycle without GPIO or a real sensor:

```bash
python control.py --config config.toml --dry-run --once --dry-run-temperature 18.7
```

Start the dashboard:

```bash
streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
```

Open:

```text
http://<pi-ip>:8501
```

## Systemd Services

Create `/etc/systemd/system/axocare-control.service`:

```ini
[Unit]
Description=Axocare Temperature Controller
After=network.target

[Service]
WorkingDirectory=/home/pi/axocare
ExecStart=/home/pi/axocare/.venv/bin/python control.py --config config.toml
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/axocare-dashboard.service`:

```ini
[Unit]
Description=Axocare Streamlit Dashboard
After=network.target

[Service]
WorkingDirectory=/home/pi/axocare
ExecStart=/home/pi/axocare/.venv/bin/streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Enable and start both services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now axocare-control
sudo systemctl enable --now axocare-dashboard
```

Check logs:

```bash
journalctl -u axocare-control -f
journalctl -u axocare-dashboard -f
```

## Database

SQLite migrations live in `migrations/` and are applied automatically by both
the controller and dashboard. Runtime database files such as `axocare.db` are
ignored by Git.

## License

MIT
