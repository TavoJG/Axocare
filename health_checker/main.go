package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	defaultHealthURL = "http://127.0.0.1:8000/api/health"
	defaultStatePath = ".health-checker-state.json"
	pushoverAPIURL   = "https://api.pushover.net/1/messages.json"
)

type HealthResponse struct {
	Status  string        `json:"status"`
	DBPath  string        `json:"db_path"`
	Control ControlHealth `json:"control"`
}

type ControlHealth struct {
	Status        string   `json:"status"`
	LatestReading *string  `json:"latest_reading_at"`
	AgeSeconds    *int     `json:"age_seconds"`
	MaxAgeSeconds int      `json:"max_age_seconds"`
	TemperatureC  *float64 `json:"temperature_c"`
	RelayOn       *bool    `json:"relay_on"`
	LastError     *string  `json:"last_error"`
}

type PushoverConfig struct {
	AppToken string
	UserKey  string
	Title    string
}

type HealthCheckState struct {
	Healthy bool `json:"healthy"`
}

func main() {
	if err := loadEnvFile(".env"); err != nil {
		log.Fatal(err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	healthURL := getenv("AXOCARE_HEALTH_URL", defaultHealthURL)
	statePath := getenv("AXOCARE_HEALTH_STATE_FILE", defaultStatePath)
	pushover := PushoverConfig{
		AppToken: os.Getenv("PUSHOVER_APP_TOKEN"),
		UserKey:  os.Getenv("PUSHOVER_USER_KEY"),
		Title:    getenv("PUSHOVER_TITLE", "Axocare health alert"),
	}

	if err := CheckHealthWithState(ctx, http.DefaultClient, healthURL, pushover, statePath); err != nil {
		log.Fatal(err)
	}
}

func CheckHealth(
	ctx context.Context,
	client *http.Client,
	healthURL string,
	pushover PushoverConfig,
) error {
	return checkHealth(ctx, client, healthURL, pushover, "")
}

func CheckHealthWithState(
	ctx context.Context,
	client *http.Client,
	healthURL string,
	pushover PushoverConfig,
	statePath string,
) error {
	return checkHealth(ctx, client, healthURL, pushover, statePath)
}

func checkHealth(
	ctx context.Context,
	client *http.Client,
	healthURL string,
	pushover PushoverConfig,
	statePath string,
) error {
	health, err := fetchHealth(ctx, client, healthURL)
	if err != nil {
		message := fmt.Sprintf("Axocare API health check failed: %v", err)
		if err := notifyPushover(ctx, client, pushover, message); err != nil {
			return err
		}
		return writeHealthState(statePath, false)
	}

	if health.Status != "ok" {
		message := fmt.Sprintf("Axocare API status is %q.", health.Status)
		if err := notifyPushover(ctx, client, pushover, message); err != nil {
			return err
		}
		return writeHealthState(statePath, false)
	}

	if health.Control.Status != "ok" {
		message := controlProblemMessage(health.Control)
		if err := notifyPushover(ctx, client, pushover, message); err != nil {
			return err
		}
		return writeHealthState(statePath, false)
	}

	previousState, err := readHealthState(statePath)
	if err != nil {
		return err
	}
	if previousState != nil && !previousState.Healthy {
		message := "Axocare health check recovered; API and control loop are ok."
		if err := notifyPushover(ctx, client, pushover, message); err != nil {
			return err
		}
	}

	return writeHealthState(statePath, true)
}

func fetchHealth(ctx context.Context, client *http.Client, healthURL string) (*HealthResponse, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, healthURL, nil)
	if err != nil {
		return nil, err
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, err
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("unexpected HTTP status %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	var health HealthResponse
	if err := json.Unmarshal(body, &health); err != nil {
		return nil, err
	}

	return &health, nil
}

func controlProblemMessage(control ControlHealth) string {
	parts := []string{
		fmt.Sprintf("Axocare control process is %q.", control.Status),
	}

	if control.AgeSeconds != nil {
		parts = append(parts, fmt.Sprintf("Latest reading age: %ds.", *control.AgeSeconds))
	}
	if control.MaxAgeSeconds > 0 {
		parts = append(parts, fmt.Sprintf("Expected max age: %ds.", control.MaxAgeSeconds))
	}
	if control.LastError != nil && *control.LastError != "" {
		parts = append(parts, fmt.Sprintf("Last error: %s.", *control.LastError))
	}

	return strings.Join(parts, " ")
}

func notifyPushover(
	ctx context.Context,
	client *http.Client,
	config PushoverConfig,
	message string,
) error {
	if config.AppToken == "" || config.UserKey == "" {
		return errors.New("Pushover credentials are missing; set PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY")
	}

	form := url.Values{}
	form.Set("token", config.AppToken)
	form.Set("user", config.UserKey)
	form.Set("title", config.Title)
	form.Set("message", message)

	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		pushoverAPIURL,
		bytes.NewBufferString(form.Encode()),
	)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("Pushover returned HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	return nil
}

func readHealthState(path string) (*HealthCheckState, error) {
	if path == "" {
		return nil, nil
	}

	body, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	var state HealthCheckState
	if err := json.Unmarshal(body, &state); err != nil {
		return nil, fmt.Errorf("read health check state: %w", err)
	}

	return &state, nil
}

func writeHealthState(path string, healthy bool) error {
	if path == "" {
		return nil
	}

	body, err := json.MarshalIndent(HealthCheckState{Healthy: healthy}, "", "  ")
	if err != nil {
		return err
	}
	body = append(body, '\n')

	return os.WriteFile(path, body, 0o600)
}

func getenv(name string, fallback string) string {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	return value
}

func loadEnvFile(path string) error {
	file, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for lineNumber := 1; scanner.Scan(); lineNumber++ {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		line = strings.TrimSpace(strings.TrimPrefix(line, "export "))
		key, value, found := strings.Cut(line, "=")
		if !found {
			return fmt.Errorf("%s:%d: expected KEY=value", path, lineNumber)
		}

		key = strings.TrimSpace(key)
		if key == "" {
			return fmt.Errorf("%s:%d: environment variable name is empty", path, lineNumber)
		}
		if _, exists := os.LookupEnv(key); exists {
			continue
		}

		parsedValue, err := parseEnvValue(strings.TrimSpace(value))
		if err != nil {
			return fmt.Errorf("%s:%d: %w", path, lineNumber, err)
		}
		if err := os.Setenv(key, parsedValue); err != nil {
			return fmt.Errorf("%s:%d: %w", path, lineNumber, err)
		}
	}

	return scanner.Err()
}

func parseEnvValue(value string) (string, error) {
	if value == "" {
		return "", nil
	}

	quote := value[0]
	if quote != '\'' && quote != '"' {
		return value, nil
	}
	if len(value) < 2 || value[len(value)-1] != quote {
		return "", errors.New("unterminated quoted value")
	}

	if quote == '\'' {
		return value[1 : len(value)-1], nil
	}

	return strconv.Unquote(value)
}
