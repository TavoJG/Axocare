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

Start the FastAPI dashboard API:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Open the interactive API docs:

```text
http://<pi-ip>:8000/docs
```

The main frontend-oriented endpoints are:

- `GET /api/dashboard?span_minutes=60`
- `GET /api/current`
- `GET /api/temperature-readings?span_minutes=60`
- `GET /api/relay-events?limit=50`
- `GET /health`

Set `AXOCARE_CONFIG=/path/to/config.toml` to load a non-default config file.
Set `AXOCARE_CORS_ORIGINS=http://localhost:3000,http://<pi-ip>` to restrict
browser origins for a frontend. By default, the API allows all origins.

The old Streamlit dashboard can still be started while the frontend migrates:

```bash
streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
```

Open:

```text
http://<pi-ip>:8501
```

## NGINX HTTP Proxy

To serve the dashboard over plain HTTP on port 80, keep the Streamlit dashboard
running on localhost port 8501 and proxy NGINX to it.

Install NGINX:

```bash
sudo apt install nginx
```

Copy the included site config:

```bash
sudo cp deploy/nginx/axocare-dashboard.conf /etc/nginx/sites-available/axocare-dashboard
sudo ln -s /etc/nginx/sites-available/axocare-dashboard /etc/nginx/sites-enabled/axocare-dashboard
sudo rm -f /etc/nginx/sites-enabled/default
```

Test and reload NGINX:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

If the page shows Streamlit skeleton placeholders forever, update the dashboard
service so Streamlit knows the public browser URL is port 80:

```ini
ExecStart=/home/pi/axocare/.venv/bin/streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501 --browser.serverAddress <pi-ip> --browser.serverPort 80
```

Then restart the dashboard:

```bash
sudo systemctl daemon-reload
sudo systemctl restart axocare-dashboard
```

Open:

```text
http://<pi-ip>
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

Create `/etc/systemd/system/axocare-api.service`:

```ini
[Unit]
Description=Axocare Dashboard API
After=network.target

[Service]
WorkingDirectory=/home/pi/axocare
ExecStart=/home/pi/axocare/.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Or, while migrating, create `/etc/systemd/system/axocare-dashboard.service` for
the old Streamlit dashboard:

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
sudo systemctl enable --now axocare-api
```

Check logs:

```bash
journalctl -u axocare-control -f
journalctl -u axocare-api -f
```

## Database

SQLite migrations live in `migrations/` and are applied automatically by both
the controller and dashboard. Runtime database files such as `axocare.db` are
ignored by Git.

## License

MIT
