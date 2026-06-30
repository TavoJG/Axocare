package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

type cameraConfig struct {
	Enabled     bool
	Device      string
	Width       int
	Height      int
	FPS         int
	JPEGQuality int
	StreamURL   string
}

type serviceConfig struct {
	Listen         string
	StreamPath     string
	HealthPath     string
	FFmpegPath     string
	RestartDelayMS int
}

type appConfig struct {
	Camera  cameraConfig
	Service serviceConfig
}

func loadConfig(path string) (appConfig, error) {
	cfg := appConfig{
		Camera: cameraConfig{
			Device:      "0",
			Width:       640,
			Height:      480,
			FPS:         15,
			JPEGQuality: 80,
		},
		Service: serviceConfig{
			Listen:         ":8081",
			StreamPath:     "/stream",
			HealthPath:     "/health",
			FFmpegPath:     "ffmpeg",
			RestartDelayMS: 2000,
		},
	}

	file, err := os.Open(path)
	if err != nil {
		return cfg, fmt.Errorf("open config: %w", err)
	}
	defer file.Close()

	section := ""
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(stripComments(scanner.Text()))
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			section = strings.TrimSpace(line[1 : len(line)-1])
			continue
		}

		key, value, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)

		switch section {
		case "camera":
			if err := applyCameraValue(&cfg.Camera, key, value); err != nil {
				return cfg, err
			}
		case "camera_service":
			if err := applyServiceValue(&cfg.Service, key, value); err != nil {
				return cfg, err
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return cfg, fmt.Errorf("scan config: %w", err)
	}

	return cfg, nil
}

func applyCameraValue(cfg *cameraConfig, key, raw string) error {
	switch key {
	case "enabled":
		value, err := strconv.ParseBool(raw)
		if err != nil {
			return fmt.Errorf("parse camera.enabled: %w", err)
		}
		cfg.Enabled = value
	case "device":
		cfg.Device = trimQuoted(raw)
	case "width":
		return setInt(raw, &cfg.Width, "camera.width")
	case "height":
		return setInt(raw, &cfg.Height, "camera.height")
	case "fps":
		return setInt(raw, &cfg.FPS, "camera.fps")
	case "jpeg_quality":
		return setInt(raw, &cfg.JPEGQuality, "camera.jpeg_quality")
	case "stream_url":
		cfg.StreamURL = trimQuoted(raw)
	}
	return nil
}

func applyServiceValue(cfg *serviceConfig, key, raw string) error {
	switch key {
	case "listen":
		cfg.Listen = trimQuoted(raw)
	case "stream_path":
		cfg.StreamPath = trimQuoted(raw)
	case "health_path":
		cfg.HealthPath = trimQuoted(raw)
	case "ffmpeg_path":
		cfg.FFmpegPath = trimQuoted(raw)
	case "restart_delay_ms":
		return setInt(raw, &cfg.RestartDelayMS, "camera_service.restart_delay_ms")
	}
	return nil
}

func setInt(raw string, target *int, field string) error {
	value, err := strconv.Atoi(trimQuoted(raw))
	if err != nil {
		return fmt.Errorf("parse %s: %w", field, err)
	}
	*target = value
	return nil
}

func stripComments(line string) string {
	var builder strings.Builder
	inQuotes := false
	for i := 0; i < len(line); i++ {
		ch := line[i]
		if ch == '"' {
			inQuotes = !inQuotes
		}
		if ch == '#' && !inQuotes {
			break
		}
		builder.WriteByte(ch)
	}
	return builder.String()
}

func trimQuoted(value string) string {
	value = strings.TrimSpace(value)
	value = strings.TrimPrefix(value, `"`)
	value = strings.TrimSuffix(value, `"`)
	return value
}
