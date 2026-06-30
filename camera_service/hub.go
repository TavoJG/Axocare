package main

import (
	"sync"
	"time"
)

type frameHub struct {
	mu          sync.RWMutex
	subscribers map[chan []byte]struct{}
	latest      []byte
	latestAt    time.Time
}

func newFrameHub() *frameHub {
	return &frameHub{
		subscribers: make(map[chan []byte]struct{}),
	}
}

func (h *frameHub) publish(frame []byte) {
	h.mu.Lock()
	h.latest = frame
	h.latestAt = time.Now()
	for ch := range h.subscribers {
		select {
		case ch <- frame:
		default:
			select {
			case <-ch:
			default:
			}
			select {
			case ch <- frame:
			default:
			}
		}
	}
	h.mu.Unlock()
}

func (h *frameHub) subscribe() (chan []byte, []byte) {
	ch := make(chan []byte, 1)
	h.mu.Lock()
	h.subscribers[ch] = struct{}{}
	latest := h.latest
	h.mu.Unlock()
	return ch, latest
}

func (h *frameHub) unsubscribe(ch chan []byte) {
	h.mu.Lock()
	if _, ok := h.subscribers[ch]; ok {
		delete(h.subscribers, ch)
		close(ch)
	}
	h.mu.Unlock()
}

func (h *frameHub) stats() (clients int, latestAt time.Time) {
	h.mu.RLock()
	clients = len(h.subscribers)
	latestAt = h.latestAt
	h.mu.RUnlock()
	return clients, latestAt
}
