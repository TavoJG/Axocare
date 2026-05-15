package main

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return fn(req)
}

func TestCheckHealthDoesNotNotifyWhenEverythingIsHealthy(t *testing.T) {
	healthURL := "http://axocare.test/api/health"
	pushoverCalls := 0
	client := &http.Client{
		Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			if req.URL.String() == pushoverAPIURL {
				pushoverCalls++
				return response(http.StatusOK, "{}"), nil
			}

			if req.URL.String() != healthURL {
				t.Fatalf("unexpected request URL: %s", req.URL.String())
			}
			return response(http.StatusOK, `{"status":"ok","db_path":"axocare.db","control":{"status":"ok","latest_reading_at":null,"age_seconds":1,"max_age_seconds":120,"temperature_c":18.4,"relay_on":false,"last_error":null}}`), nil
		}),
	}

	err := CheckHealth(context.Background(), client, healthURL, validPushoverConfig())

	if err != nil {
		t.Fatalf("CheckHealth returned error: %v", err)
	}
	if pushoverCalls != 0 {
		t.Fatalf("expected no Pushover calls, got %d", pushoverCalls)
	}
}

func TestCheckHealthNotifiesWhenControlIsStale(t *testing.T) {
	healthURL := "http://axocare.test/api/health"
	var pushoverForm url.Values
	client := &http.Client{
		Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			if req.URL.String() == pushoverAPIURL {
				pushoverForm = readForm(t, req)
				return response(http.StatusOK, "{}"), nil
			}

			if req.URL.String() != healthURL {
				t.Fatalf("unexpected request URL: %s", req.URL.String())
			}
			return response(http.StatusOK, `{"status":"ok","db_path":"axocare.db","control":{"status":"stale","latest_reading_at":"2026-05-15T10:00:00Z","age_seconds":300,"max_age_seconds":120,"temperature_c":18.4,"relay_on":false,"last_error":null}}`), nil
		}),
	}

	err := CheckHealth(context.Background(), client, healthURL, validPushoverConfig())

	if err != nil {
		t.Fatalf("CheckHealth returned error: %v", err)
	}
	assertPushoverField(t, pushoverForm, "token", "app-token")
	assertPushoverField(t, pushoverForm, "user", "user-key")
	assertPushoverField(t, pushoverForm, "title", "Axocare health alert")
	message := pushoverForm.Get("message")
	for _, want := range []string{
		`Axocare control process is "stale".`,
		"Latest reading age: 300s.",
		"Expected max age: 120s.",
	} {
		if !strings.Contains(message, want) {
			t.Fatalf("expected message %q to contain %q", message, want)
		}
	}
}

func TestCheckHealthNotifiesWhenHealthRequestFails(t *testing.T) {
	healthURL := "http://axocare.test/api/health"
	var pushoverForm url.Values
	client := &http.Client{
		Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			if req.URL.String() == pushoverAPIURL {
				pushoverForm = readForm(t, req)
				return response(http.StatusOK, "{}"), nil
			}

			return nil, errors.New("connection refused")
		}),
	}

	err := CheckHealth(context.Background(), client, healthURL, validPushoverConfig())

	if err != nil {
		t.Fatalf("CheckHealth returned error: %v", err)
	}
	message := pushoverForm.Get("message")
	if !strings.Contains(message, "Axocare API health check failed") {
		t.Fatalf("expected API failure message, got %q", message)
	}
	if !strings.Contains(message, "connection refused") {
		t.Fatalf("expected connection error in message, got %q", message)
	}
}

func TestCheckHealthReturnsErrorWhenNotificationCredentialsAreMissing(t *testing.T) {
	healthURL := "http://axocare.test/api/health"
	client := &http.Client{
		Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			return response(http.StatusOK, `{"status":"ok","db_path":"axocare.db","control":{"status":"error","latest_reading_at":null,"age_seconds":null,"max_age_seconds":120,"temperature_c":null,"relay_on":null,"last_error":"sensor disconnected"}}`), nil
		}),
	}

	err := CheckHealth(context.Background(), client, healthURL, PushoverConfig{})

	if err == nil {
		t.Fatal("expected missing credentials error")
	}
	if !strings.Contains(err.Error(), "Pushover credentials are missing") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestLoadEnvFileSetsVariablesAndPreservesExistingEnvironment(t *testing.T) {
	dir := t.TempDir()
	envPath := filepath.Join(dir, ".env")
	newKey := "AXOCARE_TEST_FROM_ENV_FILE"
	quotedKey := "AXOCARE_TEST_QUOTED_ENV_FILE"
	keepKey := "AXOCARE_TEST_KEEP_ENV_VALUE"

	for _, key := range []string{newKey, quotedKey} {
		if err := os.Unsetenv(key); err != nil {
			t.Fatalf("failed to unset %s: %v", key, err)
		}
		t.Cleanup(func() {
			_ = os.Unsetenv(key)
		})
	}
	t.Setenv(keepKey, "from-env")

	content := strings.Join([]string{
		"# comment",
		"AXOCARE_TEST_FROM_ENV_FILE=from-file",
		`export AXOCARE_TEST_QUOTED_ENV_FILE="quoted value"`,
		"AXOCARE_TEST_KEEP_ENV_VALUE=from-file",
		"",
	}, "\n")
	if err := os.WriteFile(envPath, []byte(content), 0o600); err != nil {
		t.Fatalf("failed to write env file: %v", err)
	}

	if err := loadEnvFile(envPath); err != nil {
		t.Fatalf("loadEnvFile returned error: %v", err)
	}

	if got := os.Getenv(newKey); got != "from-file" {
		t.Fatalf("expected %s=from-file, got %q", newKey, got)
	}
	if got := os.Getenv(quotedKey); got != "quoted value" {
		t.Fatalf("expected %s to parse quoted value, got %q", quotedKey, got)
	}
	if got := os.Getenv(keepKey); got != "from-env" {
		t.Fatalf("expected existing %s to be preserved, got %q", keepKey, got)
	}
}

func TestLoadEnvFileReturnsErrorForMalformedLine(t *testing.T) {
	dir := t.TempDir()
	envPath := filepath.Join(dir, ".env")
	if err := os.WriteFile(envPath, []byte("BROKEN_LINE\n"), 0o600); err != nil {
		t.Fatalf("failed to write env file: %v", err)
	}

	err := loadEnvFile(envPath)

	if err == nil {
		t.Fatal("expected malformed env error")
	}
	if !strings.Contains(err.Error(), "expected KEY=value") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func response(statusCode int, body string) *http.Response {
	return &http.Response{
		StatusCode: statusCode,
		Body:       io.NopCloser(strings.NewReader(body)),
		Header:     make(http.Header),
	}
}

func readForm(t *testing.T, req *http.Request) url.Values {
	t.Helper()

	body, err := io.ReadAll(req.Body)
	if err != nil {
		t.Fatalf("failed to read request body: %v", err)
	}
	form, err := url.ParseQuery(string(body))
	if err != nil {
		t.Fatalf("failed to parse form: %v", err)
	}
	return form
}

func assertPushoverField(t *testing.T, form url.Values, name string, want string) {
	t.Helper()

	if got := form.Get(name); got != want {
		t.Fatalf("expected Pushover %s=%q, got %q", name, want, got)
	}
}

func validPushoverConfig() PushoverConfig {
	return PushoverConfig{
		AppToken: "app-token",
		UserKey:  "user-key",
		Title:    "Axocare health alert",
	}
}
