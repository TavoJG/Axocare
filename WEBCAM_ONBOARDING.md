# Guia De Onboarding De Webcam

Esta guia explica como conectar una webcam a la Raspberry Pi 4 y hacer que
aparezca en el dashboard de Axocare.

## 1. Conectar La Webcam

Conecta la webcam USB a la Raspberry Pi 4.

Verifica que Linux la detecte:

```bash
ls /dev/video*
```

Para la primera webcam USB, normalmente deberias ver:

```text
/dev/video0
```

Si no aparece ningun dispositivo `/dev/video*`, prueba otro puerto USB,
confirma que la webcam funcione en otra computadora y reinicia la Pi.

## 2. Instalar Dependencias

Axocare usa un servicio dedicado en Go para publicar el stream MJPEG, y ese
servicio usa FFmpeg para capturar la webcam.

Instala FFmpeg en la Raspberry Pi:

```bash
sudo apt update
sudo apt install ffmpeg
```

## 3. Configurar Axocare

Edita `config.toml` y agrega o actualiza la seccion de camara:

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

Si vas a servir el dashboard con NGINX, esta opcion relativa es la mas limpia
porque el navegador no necesita conocer el puerto `8081`. Si vas a conectarte
directamente al servicio de camara, usa una URL completa como
`http://<pi-ip>:8081/stream`.

`device = "0"` se traduce a `/dev/video0`. Tambien puedes usar la ruta explicita
del dispositivo:

```toml
device = "/dev/video0"
```

Empieza con `640x480` a `15 fps`. Si el dashboard se siente lento o la Pi se
calienta demasiado, reduce `fps` o la resolucion. Si la imagen se ve demasiado
comprimida, sube `jpeg_quality` hasta `100`.

## 4. Iniciar La API Y El Servicio De Camara

Si estas corriendo la API manualmente:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Compila y arranca el servicio de streaming:

```bash
cd camera_service
./build-pi4.sh
./dist/axocare-camera-pi4 --config ../config.toml
```

Para Raspberry Pi OS de 32 bits:

```bash
cd camera_service
GOARCH=arm GOARM=7 OUTPUT=dist/axocare-camera-pi4-armv7 ./build-pi4.sh
```

Si estas usando systemd:

```bash
sudo systemctl restart axocare-api.service
sudo systemctl status axocare-api.service
sudo systemctl restart axocare-camera.service
sudo systemctl status axocare-camera.service
```

## 5. Probar El Stream Directamente

Abre la URL del stream en un navegador:

```text
http://<pi-ip>/camera/stream
```

La API mantiene `/api/camera/stream` como redireccion ligera, asi que tambien
puedes probar:

```text
http://<pi-ip>:8000/api/camera/stream
```

Deberias ver una imagen MJPEG en vivo. Algunos navegadores la muestran como una
imagen que se actualiza continuamente en vez de un reproductor de video; eso es
normal.

## 6. Revisar El Dashboard

Abre el dashboard de Axocare:

```text
http://<pi-ip>:5173
```

o, si esta servido por NGINX:

```text
http://<pi-ip>
```

Cuando `camera.enabled = true`, el dashboard muestra un panel `Live camera`
arriba de la grafica de temperatura.

## 7. Troubleshooting

### No Aparece `/dev/video0`

Ejecuta:

```bash
lsusb
ls /dev/video*
```

Si la webcam aparece en `lsusb` pero no aparece como `/dev/video*`, reinicia la
Pi y revisa si la camara necesita drivers adicionales para Linux.

### La API Responde `Camera streaming is disabled`

Confirma que `config.toml` tenga:

```toml
[camera]
enabled = true
```

Luego reinicia la API.

### El Servicio De Camara No Arranca

Confirma que FFmpeg este instalado:

```bash
ffmpeg -version
```

Luego prueba correr el binario manualmente:

```bash
cd camera_service
go run . --config ../config.toml
```

### La API Responde `Camera stream URL is not configured`

Confirma que `config.toml` tenga:

```toml
[camera]
enabled = true
stream_url = "/camera/stream"
```

### FFmpeg No Puede Abrir La Camara

Revisa que dispositivo existe:

```bash
ls /dev/video*
```

Luego ajusta `config.toml`, por ejemplo:

```toml
device = "/dev/video0"
```

Tambien confirma que ningun otro servicio este usando la webcam.

### El Stream Funciona Pero No Sale En El Dashboard

Confirma que el dashboard reciba la configuracion actualizada:

```bash
curl http://<pi-ip>:8000/api/dashboard
```

Busca:

```json
"camera_enabled": true,
"camera_stream_url": "/camera/stream"
```

Si usas el servidor de desarrollo de Vite desde otra maquina, asegurate de que
pueda llegar a la API y configura `VITE_API_BASE` si hace falta:

```bash
VITE_API_BASE=http://<pi-ip>:8000 npm run dev
```

### El Stream Va Lento

Baja la carga de la camara:

```toml
width = 640
height = 360
fps = 10
jpeg_quality = 70
```

Luego reinicia la API y el servicio de camara.

## 8. Configuracion Recomendada Inicial

Para una Raspberry Pi 4 con una webcam USB comun:

```toml
[camera]
enabled = true
stream_url = "/camera/stream"
device = "/dev/video0"
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
