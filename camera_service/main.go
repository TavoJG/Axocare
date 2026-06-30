package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const boundary = "frame"

type streamManager struct {
	cfg          appConfig
	hub          *frameHub
	mu           sync.RWMutex
	running      bool
	lastError    string
	lastStart    time.Time
	lastExitCode int
}

func newStreamManager(cfg appConfig) *streamManager {
	return &streamManager{
		cfg: cfg,
		hub: newFrameHub(),
	}
}

func (m *streamManager) run(ctx context.Context) {
	restartDelay := time.Duration(maxInt(m.cfg.Service.RestartDelayMS, 250)) * time.Millisecond
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		if err := m.captureOnce(ctx); err != nil {
			if ctx.Err() != nil {
				return
			}
			log.Printf("capture stopped: %v", err)
			m.setStopped(err, -1)
		}

		timer := time.NewTimer(restartDelay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
		}
	}
}

func (m *streamManager) captureOnce(ctx context.Context) error {
	cmd := exec.CommandContext(ctx, m.cfg.Service.FFmpegPath, ffmpegArgs(m.cfg.Camera)...)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("stdout pipe: %w", err)
	}
	cmd.Stderr = os.Stderr

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start ffmpeg: %w", err)
	}
	m.setRunning()

	parseErr := parseMJPEG(stdout, m.hub.publish)
	waitErr := cmd.Wait()
	if parseErr != nil {
		return fmt.Errorf("parse mjpeg: %w", parseErr)
	}
	if waitErr != nil {
		if exitErr, ok := waitErr.(*exec.ExitError); ok {
			m.setStopped(waitErr, exitErr.ExitCode())
		}
		return fmt.Errorf("wait ffmpeg: %w", waitErr)
	}

	m.setStopped(nil, 0)
	return io.EOF
}

func (m *streamManager) setRunning() {
	m.mu.Lock()
	m.running = true
	m.lastError = ""
	m.lastStart = time.Now()
	m.lastExitCode = 0
	m.mu.Unlock()
}

func (m *streamManager) setStopped(err error, exitCode int) {
	m.mu.Lock()
	m.running = false
	if err != nil {
		m.lastError = err.Error()
	}
	m.lastExitCode = exitCode
	m.mu.Unlock()
}

func (m *streamManager) health() map[string]any {
	clients, latestAt := m.hub.stats()
	m.mu.RLock()
	running := m.running
	lastError := m.lastError
	lastStart := m.lastStart
	lastExitCode := m.lastExitCode
	m.mu.RUnlock()

	var frameAgeSeconds *int
	if !latestAt.IsZero() {
		age := int(time.Since(latestAt).Seconds())
		frameAgeSeconds = &age
	}

	return map[string]any{
		"status":            healthStatus(running, latestAt, lastError),
		"running":           running,
		"clients":           clients,
		"last_frame_at":     formatTime(latestAt),
		"frame_age_seconds": frameAgeSeconds,
		"last_start_at":     formatTime(lastStart),
		"last_error":        emptyToNil(lastError),
		"last_exit_code":    exitCodeValue(lastExitCode),
		"stream_path":       m.cfg.Service.StreamPath,
	}
}

func main() {
	configPath := flag.String("config", "config.toml", "Path to Axocare config.toml")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
	if err != nil {
		log.Fatalf("load config: %v", err)
	}
	if !cfg.Camera.Enabled {
		log.Fatal("camera.enabled must be true to run the camera service")
	}

	manager := newStreamManager(cfg)
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	go manager.run(ctx)

	mux := http.NewServeMux()
	mux.HandleFunc(cfg.Service.StreamPath, manager.handleStream)
	mux.HandleFunc(cfg.Service.HealthPath, manager.handleHealth)
	mux.HandleFunc("/", handleRoot(cfg))

	server := &http.Server{
		Addr:              cfg.Service.Listen,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx)
	}()

	log.Printf("camera service listening on %s%s", cfg.Service.Listen, cfg.Service.StreamPath)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("http server: %v", err)
	}
}

func (m *streamManager) handleStream(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
	w.Header().Set("Pragma", "no-cache")
	w.Header().Set("Expires", "0")
	w.Header().Set("X-Accel-Buffering", "no")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Content-Type", "multipart/x-mixed-replace; boundary="+boundary)

	frames, latest := m.hub.subscribe()
	defer m.hub.unsubscribe(frames)

	if len(latest) > 0 {
		if err := writeFrame(w, latest); err != nil {
			return
		}
		flusher.Flush()
	}

	for {
		select {
		case <-r.Context().Done():
			return
		case frame, ok := <-frames:
			if !ok {
				return
			}
			if err := writeFrame(w, frame); err != nil {
				return
			}
			flusher.Flush()
		}
	}
}

func (m *streamManager) handleHealth(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(m.health())
}

func handleRoot(cfg appConfig) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		payload := map[string]any{
			"name":        "Axocare Camera Service",
			"stream_url":  cfg.Camera.StreamURL,
			"stream_path": cfg.Service.StreamPath,
			"health_path": cfg.Service.HealthPath,
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(payload)
	}
}

func writeFrame(w io.Writer, frame []byte) error {
	if _, err := fmt.Fprintf(
		w,
		"--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n",
		boundary,
		len(frame),
	); err != nil {
		return err
	}
	if _, err := w.Write(frame); err != nil {
		return err
	}
	_, err := w.Write([]byte("\r\n"))
	return err
}

func parseMJPEG(reader io.Reader, onFrame func([]byte)) error {
	buffer := make([]byte, 32*1024)
	var data []byte
	for {
		n, err := reader.Read(buffer)
		if n > 0 {
			data = append(data, buffer[:n]...)
			for {
				start := bytes.Index(data, []byte{0xff, 0xd8})
				if start < 0 {
					if len(data) > len(buffer) {
						data = data[len(data)-2:]
					}
					break
				}
				end := bytes.Index(data[start+2:], []byte{0xff, 0xd9})
				if end < 0 {
					if start > 0 {
						data = data[start:]
					}
					break
				}
				end += start + 4
				frame := append([]byte(nil), data[start:end]...)
				onFrame(frame)
				data = data[end:]
			}
		}
		if err != nil {
			if err == io.EOF {
				return nil
			}
			return err
		}
	}
}

func ffmpegArgs(cfg cameraConfig) []string {
	return []string{
		"-hide_banner",
		"-loglevel", "error",
		"-fflags", "nobuffer",
		"-f", "video4linux2",
		"-framerate", strconv.Itoa(maxInt(cfg.FPS, 1)),
		"-video_size", fmt.Sprintf("%dx%d", maxInt(cfg.Width, 1), maxInt(cfg.Height, 1)),
		"-i", normalizeDevice(cfg.Device),
		"-vf", fmt.Sprintf("fps=%d", maxInt(cfg.FPS, 1)),
		"-q:v", strconv.Itoa(ffmpegQuality(cfg.JPEGQuality)),
		"-f", "image2pipe",
		"-vcodec", "mjpeg",
		"pipe:1",
	}
}

func normalizeDevice(device string) string {
	device = strings.TrimSpace(device)
	if _, err := strconv.Atoi(device); err == nil {
		return "/dev/video" + device
	}
	return device
}

func ffmpegQuality(jpegQuality int) int {
	if jpegQuality < 1 {
		jpegQuality = 1
	}
	if jpegQuality > 100 {
		jpegQuality = 100
	}
	return 2 + (100-jpegQuality)*29/99
}

func healthStatus(running bool, latestAt time.Time, lastError string) string {
	if !running && lastError != "" {
		return "error"
	}
	if latestAt.IsZero() {
		return "starting"
	}
	return "ok"
}

func emptyToNil(value string) any {
	if value == "" {
		return nil
	}
	return value
}

func exitCodeValue(code int) any {
	if code < 0 {
		return nil
	}
	return code
}

func formatTime(value time.Time) any {
	if value.IsZero() {
		return nil
	}
	return value.UTC().Format(time.RFC3339)
}

func maxInt(value, fallback int) int {
	if value < fallback {
		return fallback
	}
	return value
}
