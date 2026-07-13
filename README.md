# Axocare

Axocare is a Raspberry Pi aquarium temperature controller. It reads a DS18B20
temperature sensor, switches a cooling relay through GPIO, stores readings in
SQLite, exposes a FastAPI JSON API, and serves a Vite/TypeScript dashboard for
recent temperature history. It can also persist ambient telemetry from a
combined AHT20 + BMP280 I2C module.

## Hardware

- Raspberry Pi with 1-Wire enabled
- Raspberry Pi with I2C enabled when using the optional AHT20 + BMP280 module
- DS18B20 temperature sensor on GPIO 4
- Optional AHT20 (`0x38`) + BMP280 (`0x77`) combo module on the I2C bus
- Waveshare RPi Relay Board using CH1 on BCM GPIO 26 / physical pin 37
  and CH2 on BCM GPIO 20 / physical pin 38
- Cooling device connected through the relay

The Waveshare RPi Relay Board is low-active, so relay on means GPIO LOW.

## Setup

Install system packages on the Raspberry Pi:

```bash
sudo apt update
sudo apt install git python3-venv python3-rpi.gpio
```

Enable 1-Wire and, if you will use the ambient module, I2C with
`sudo raspi-config`, then reboot.

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
notification_threshold_c = 20.0

[control]
interval_seconds = 60

[camera]
enabled = false
device = "0"
width = 640
height = 480
fps = 15
jpeg_quality = 80

[relay]
active_high = false
pins = [26, 20]

[sensor]
id = ""

[i2c_sensor]
enabled = false
aht20_address = 0x38
bmp280_address = 0x77

[pushover]
app_token = ""
user_key = ""
title = "Axocare temperature alert"
```

The controller turns the relay on when temperature is greater than or equal to
`cooling_on_c`, turns it off when temperature is less than or equal to
`cooling_off_c`, and keeps the previous relay state between those values.

Set `temperature.notification_threshold_c` to send a Pushover alert when the
temperature is greater than that value. The alert is sent once per high
temperature excursion and resets after the temperature returns to or below the
threshold. Add your Pushover application token and user key under `[pushover]`,
or provide them with `PUSHOVER_APP_TOKEN` and `PUSHOVER_USER_KEY`.

Leave `sensor.id` empty to use the first detected DS18B20 sensor.

Set `i2c_sensor.enabled = true` to record ambient temperature, humidity, and
pressure from the AHT20 + BMP280 module in the same `temperature_readings` row
as the tank temperature and relay state.

## Camera Streaming

Axocare can expose an MJPEG stream for a webcam connected to the Raspberry Pi
through a dedicated Go service. The API no longer captures video directly;
instead it publishes the external stream URL and the dashboard connects to that
service.

Install FFmpeg on the Raspberry Pi:

```bash
sudo apt install ffmpeg
```

For a USB webcam, enable the camera and point the dashboard at the dedicated
stream URL in `config.toml`:

```toml
[camera]
enabled = true
stream_url = "/camera/stream"
device = "0"
width = 640
height = 480
fps = 15
jpeg_quality = 80

[camera_service]
listen = ":8081"
stream_path = "/stream"
health_path = "/health"
ffmpeg_path = "ffmpeg"
restart_delay_ms = 2000
```

`device = "0"` maps to `/dev/video0`. You can also use an explicit device path
such as `device = "/dev/video0"`.

If you put NGINX in front of Axocare, `stream_url = "/camera/stream"` keeps the
browser on the same origin while NGINX proxies internally to the camera
service. If you want to connect directly to the service without NGINX, use a
full URL such as `http://<pi-ip>:8081/stream`.

Build and run the camera service:

```bash
cd camera_service
./build-pi4.sh
./dist/axocare-camera-pi4 --config ../config.toml
```

For a 32-bit Raspberry Pi OS build:

```bash
cd camera_service
GOARCH=arm GOARM=7 OUTPUT=dist/axocare-camera-pi4-armv7 ./build-pi4.sh
```

The dedicated MJPEG endpoint will be available at:

```text
http://<pi-ip>:8081/stream
```

The API keeps `/api/camera/stream` as a lightweight `307` redirect to the
dedicated stream URL, and the Vite dashboard automatically uses
`camera.stream_url` when `camera.enabled` is true.

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

Start the dedicated camera streaming service:

```bash
cd camera_service
go run . --config ../config.toml
```

Start the Vite dashboard during development:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://<pi-ip>:5173
```

Vite proxies `/api` requests to `http://127.0.0.1:8000`. For a backend hosted
elsewhere, set `VITE_API_BASE` before building or running the dashboard:

```bash
VITE_API_BASE=http://<pi-ip>:8000 npm run dev
```

Build the production dashboard:

```bash
cd frontend
npm run build
```

The dashboard is implemented with Vue 3 and TypeScript. Run its unit and
component tests with:

```bash
cd frontend
npm test
```

When you change frontend source or assets, rebuild the production bundle and
commit the resulting `frontend/dist` updates with your branch:

```bash
cd frontend
npm run build
```

The **Ask Axocare** panel uses `POST /api/agent/chat/stream` and displays the
agent's SSE lifecycle and final response. Configure the `[agent]` section in
`config.toml` before starting FastAPI; provider credentials remain server-side.
The API returns a `conversation_id` so the frontend can resume a persisted chat
without resending the full transcript.

Open the interactive API docs:

```text
http://<pi-ip>:8000/api/docs
```

The main frontend-oriented endpoints are:

- `GET /api/dashboard?span_minutes=60`
- `GET /api/current`
- `GET /api/temperature-readings?span_minutes=60`
- `GET /api/relay-events?limit=50`
- `GET /api/health`

Set `AXOCARE_CONFIG=/path/to/config.toml` to load a non-default config file.
Set `AXOCARE_CORS_ORIGINS=http://localhost:5173,http://<pi-ip>` to restrict
browser origins for a frontend. By default, the API allows all origins.

## NGINX HTTP Proxy

To serve the dashboard over plain HTTP on port 80, build the Vite dashboard and
proxy both backend services through NGINX. The included NGINX config serves
`/home/pi/axocare/frontend/dist`, forwards `/api/` to FastAPI at
`http://127.0.0.1:8000`, and forwards `/camera/stream` plus `/camera/health` to
the dedicated camera service at `http://127.0.0.1:8081`.

Install NGINX:

```bash
sudo apt install nginx
```

Build the frontend on the Raspberry Pi:

```bash
cd /home/pi/axocare/frontend
npm install
npm run build
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

Open:

```text
http://<pi-ip>
```

With that setup, the recommended camera config is:

```toml
[camera]
enabled = true
stream_url = "/camera/stream"
device = "/dev/video0"
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

Create `/etc/systemd/system/axocare-dashboard-build.service` if you want a
manual systemd unit for rebuilding the static dashboard after updates:

```ini
[Unit]
Description=Build Axocare Vite Dashboard

[Service]
Type=oneshot
WorkingDirectory=/home/pi/axocare/frontend
ExecStart=/usr/bin/npm run build
User=pi
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
