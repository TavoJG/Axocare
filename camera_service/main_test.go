package main

import (
	"bytes"
	"testing"
)

func TestParseMJPEGExtractsMultipleFrames(t *testing.T) {
	t.Parallel()

	stream := append([]byte("noise"), jpegFrame("one")...)
	stream = append(stream, jpegFrame("two")...)

	var frames [][]byte
	if err := parseMJPEG(bytes.NewReader(stream), func(frame []byte) {
		frames = append(frames, frame)
	}); err != nil {
		t.Fatalf("parseMJPEG: %v", err)
	}

	if len(frames) != 2 {
		t.Fatalf("expected 2 frames, got %d", len(frames))
	}
	if !bytes.Contains(frames[0], []byte("one")) || !bytes.Contains(frames[1], []byte("two")) {
		t.Fatalf("unexpected frames: %q %q", frames[0], frames[1])
	}
}

func TestFFmpegArgsNormalizesCameraDevice(t *testing.T) {
	t.Parallel()

	args := ffmpegArgs(cameraConfig{
		Device:      "0",
		Width:       640,
		Height:      480,
		FPS:         15,
		JPEGQuality: 80,
	})

	found := false
	for index := 0; index < len(args)-1; index++ {
		if args[index] == "-i" && args[index+1] == "/dev/video0" {
			found = true
		}
	}
	if !found {
		t.Fatalf("expected /dev/video0 input, got %v", args)
	}
}

func jpegFrame(body string) []byte {
	return append([]byte{0xff, 0xd8}, append([]byte(body), 0xff, 0xd9)...)
}
