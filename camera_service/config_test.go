package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadConfigReadsCameraAndServiceSections(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	path := filepath.Join(dir, "config.toml")
	content := `
[camera]
enabled = true
stream_url = "http://pi.local:8081/stream"
device = "/dev/video2"
width = 1280
height = 720
fps = 12
jpeg_quality = 65

[camera_service]
listen = ":9090"
stream_path = "/camera/stream"
health_path = "/healthz"
ffmpeg_path = "/usr/bin/ffmpeg"
restart_delay_ms = 3500
`
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write config: %v", err)
	}

	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("load config: %v", err)
	}

	if !cfg.Camera.Enabled {
		t.Fatal("expected camera to be enabled")
	}
	if cfg.Camera.StreamURL != "http://pi.local:8081/stream" {
		t.Fatalf("unexpected stream URL: %q", cfg.Camera.StreamURL)
	}
	if cfg.Camera.Device != "/dev/video2" || cfg.Camera.Width != 1280 || cfg.Camera.Height != 720 {
		t.Fatalf("unexpected camera dimensions: %+v", cfg.Camera)
	}
	if cfg.Service.Listen != ":9090" || cfg.Service.StreamPath != "/camera/stream" {
		t.Fatalf("unexpected service config: %+v", cfg.Service)
	}
	if cfg.Service.HealthPath != "/healthz" || cfg.Service.FFmpegPath != "/usr/bin/ffmpeg" {
		t.Fatalf("unexpected service paths: %+v", cfg.Service)
	}
	if cfg.Service.RestartDelayMS != 3500 {
		t.Fatalf("unexpected restart delay: %d", cfg.Service.RestartDelayMS)
	}
}
