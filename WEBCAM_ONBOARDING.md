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

Axocare usa OpenCV para leer frames de la webcam y servirlos como un stream
MJPEG.

Instala OpenCV en la Raspberry Pi:

```bash
sudo apt update
sudo apt install python3-opencv
```

Si Axocare usa un entorno virtual creado con `--system-site-packages`, la API
deberia poder importar el paquete OpenCV instalado por el sistema:

```bash
python3 -m venv --system-site-packages .venv
```

Verifica que OpenCV se pueda importar:

```bash
source .venv/bin/activate
python -c "import cv2; print(cv2.__version__)"
```

## 3. Configurar Axocare

Edita `config.toml` y agrega o actualiza la seccion de camara:

```toml
[camera]
enabled = true
device = "0"
width = 640
height = 480
fps = 15
jpeg_quality = 80
```

`device = "0"` le indica a OpenCV que use la primera webcam disponible.
Tambien puedes usar la ruta explicita del dispositivo:

```toml
device = "/dev/video0"
```

Empieza con `640x480` a `15 fps`. Si el dashboard se siente lento o la Pi se
calienta demasiado, reduce `fps` o la resolucion. Si la imagen se ve demasiado
comprimida, sube `jpeg_quality` hasta `100`.

## 4. Reiniciar La API

Si estas corriendo la API manualmente:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Si estas usando systemd:

```bash
sudo systemctl restart axocare-api.service
sudo systemctl status axocare-api.service
```

## 5. Probar El Stream Directamente

Abre la URL del stream en un navegador:

```text
http://<pi-ip>:8000/api/camera/stream
```

Si NGINX sirve el dashboard de produccion en el puerto 80, usa:

```text
http://<pi-ip>/api/camera/stream
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

### La API Responde `Camera streaming requires OpenCV`

Instala OpenCV:

```bash
sudo apt install python3-opencv
```

Si usas un entorno virtual, recrealo con paquetes del sistema habilitados:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### La API Responde `Could not open camera device`

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
"camera_enabled": true
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

Luego reinicia la API.

## 8. Configuracion Recomendada Inicial

Para una Raspberry Pi 4 con una webcam USB comun:

```toml
[camera]
enabled = true
device = "/dev/video0"
width = 640
height = 480
fps = 15
jpeg_quality = 80
```
