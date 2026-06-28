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
	"net"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	defaultHealthURL        = "http://127.0.0.1:8000/api/health"
	defaultStatePath        = ".health-checker-state.json"
	defaultReminderInterval = 20 * time.Minute
	pushoverAPIURL          = "https://api.pushover.net/1/messages.json"
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
	Healthy        bool      `json:"healthy"`
	Failure        string    `json:"failure,omitempty"`
	LastNotifiedAt time.Time `json:"last_notified_at,omitempty"`
}

func main() {
	if err := loadEnvFile(".env"); err != nil {
		log.Fatal(err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	healthURL := getenv("AXOCARE_HEALTH_URL", defaultHealthURL)
	statePath := getenv("AXOCARE_HEALTH_STATE_FILE", defaultStatePath)
	reminderInterval, err := getenvDuration("AXOCARE_HEALTH_REMINDER_INTERVAL", defaultReminderInterval)
	if err != nil {
		log.Fatal(err)
	}
	pushover := PushoverConfig{
		AppToken: os.Getenv("PUSHOVER_APP_TOKEN"),
		UserKey:  os.Getenv("PUSHOVER_USER_KEY"),
		Title:    getenv("PUSHOVER_TITLE", "Axocare health alert"),
	}

	if err := checkHealth(ctx, http.DefaultClient, healthURL, pushover, statePath, time.Now(), reminderInterval); err != nil {
		log.Fatal(err)
	}
}

func CheckHealth(
	ctx context.Context,
	client *http.Client,
	healthURL string,
	pushover PushoverConfig,
) error {
	return checkHealth(ctx, client, healthURL, pushover, "", time.Now(), defaultReminderInterval)
}

func CheckHealthWithState(
	ctx context.Context,
	client *http.Client,
	healthURL string,
	pushover PushoverConfig,
	statePath string,
) error {
	return checkHealth(ctx, client, healthURL, pushover, statePath, time.Now(), defaultReminderInterval)
}

func checkHealth(
	ctx context.Context,
	client *http.Client,
	healthURL string,
	pushover PushoverConfig,
	statePath string,
	now time.Time,
	reminderInterval time.Duration,
) error {
	previousState, err := readHealthState(statePath)
	if err != nil {
		return err
	}

	health, err := fetchHealth(ctx, client, healthURL)
	if err != nil {
		return handleFailure(ctx, client, pushover, statePath, previousState, apiFailureDetails(err), now, reminderInterval)
	}

	if health.Status != "ok" {
		return handleFailure(ctx, client, pushover, statePath, previousState, apiStatusFailureDetails(health.Status), now, reminderInterval)
	}

	if health.Control.Status != "ok" {
		return handleFailure(ctx, client, pushover, statePath, previousState, controlFailureDetails(health.Control), now, reminderInterval)
	}

	if previousState != nil && !previousState.Healthy {
		message := "Axocare health check recovered; API and control loop are ok."
		if err := notifyPushover(ctx, client, pushover, message); err != nil {
			return err
		}
	}

	return writeHealthState(statePath, HealthCheckState{Healthy: true})
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

type failureDetails struct {
	Signature string
	Message   string
}

func handleFailure(
	ctx context.Context,
	client *http.Client,
	pushover PushoverConfig,
	statePath string,
	previousState *HealthCheckState,
	failure failureDetails,
	now time.Time,
	reminderInterval time.Duration,
) error {
	shouldNotify := shouldNotifyFailure(previousState, failure.Signature, now, reminderInterval)
	lastNotifiedAt := previousStateLastNotifiedAt(previousState)
	if shouldNotify {
		if err := notifyPushover(ctx, client, pushover, failure.Message); err != nil {
			return err
		}
		lastNotifiedAt = now.UTC()
	}

	return writeHealthState(statePath, HealthCheckState{
		Healthy:        false,
		Failure:        failure.Signature,
		LastNotifiedAt: lastNotifiedAt,
	})
}

func shouldNotifyFailure(
	previousState *HealthCheckState,
	signature string,
	now time.Time,
	reminderInterval time.Duration,
) bool {
	if previousState == nil {
		return true
	}
	if previousState.Healthy {
		return true
	}
	if previousState.Failure != signature {
		return true
	}
	if reminderInterval <= 0 {
		return false
	}
	if previousState.LastNotifiedAt.IsZero() {
		return true
	}
	return !now.Before(previousState.LastNotifiedAt.Add(reminderInterval))
}

func previousStateLastNotifiedAt(previousState *HealthCheckState) time.Time {
	if previousState == nil {
		return time.Time{}
	}
	return previousState.LastNotifiedAt
}

func apiFailureDetails(err error) failureDetails {
	kind, description := classifyRequestError(err)
	return failureDetails{
		Signature: "api_request:" + kind,
		Message:   fmt.Sprintf("Axocare API health check failed (%s): %v", description, err),
	}
}

func apiStatusFailureDetails(status string) failureDetails {
	return failureDetails{
		Signature: "api_status:" + status,
		Message:   fmt.Sprintf("Axocare API status is %q.", status),
	}
}

func controlFailureDetails(control ControlHealth) failureDetails {
	signatureParts := []string{"control_status", control.Status}
	if control.LastError != nil && *control.LastError != "" {
		signatureParts = append(signatureParts, *control.LastError)
	}

	return failureDetails{
		Signature: strings.Join(signatureParts, ":"),
		Message:   controlProblemMessage(control),
	}
}

func classifyRequestError(err error) (kind string, description string) {
	var dnsErr *net.DNSError
	if errors.As(err, &dnsErr) {
		return "dns", "DNS lookup failed"
	}

	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return "timeout", "request timed out"
	}

	message := strings.ToLower(err.Error())
	switch {
	case strings.Contains(message, "no such host"):
		return "dns", "DNS lookup failed"
	case strings.Contains(message, "connection refused"):
		return "connection_refused", "connection refused"
	case strings.Contains(message, "context deadline exceeded"),
		strings.Contains(message, "i/o timeout"):
		return "timeout", "request timed out"
	default:
		return "request_error", "request error"
	}
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

func writeHealthState(path string, state HealthCheckState) error {
	if path == "" {
		return nil
	}

	body, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}
	body = append(body, '\n')

	return os.WriteFile(path, body, 0o600)
}

func getenvDuration(key string, fallback time.Duration) (time.Duration, error) {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback, nil
	}

	duration, err := time.ParseDuration(value)
	if err != nil {
		return 0, fmt.Errorf("parse %s: %w", key, err)
	}
	if duration < 0 {
		return 0, fmt.Errorf("parse %s: duration must be zero or greater", key)
	}

	return duration, nil
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
