package main

import (
	"fmt"
	"net/http"
	"os"
	"strconv"
	"time"
)

func main() {
	url := os.Getenv("VERIFY_URL")
	if url == "" {
		url = "http://localhost:8080"
	}
	
	expectedStatusStr := os.Getenv("EXPECTED_STATUS")
	expectedStatus := 200
	if expectedStatusStr != "" {
		if status, err := strconv.Atoi(expectedStatusStr); err == nil {
			expectedStatus = status
		}
	}
	
	fmt.Printf("Verifying HTTP endpoint: %s\n", url)
	fmt.Printf("Expected status: %d\n", expectedStatus)
	
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		fmt.Printf("HTTP request failed: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode == expectedStatus {
		fmt.Printf("✓ HTTP verification successful: %d\n", resp.StatusCode)
		os.Exit(0)
	} else {
		fmt.Printf("✗ HTTP verification failed: expected %d, got %d\n", expectedStatus, resp.StatusCode)
		os.Exit(1)
	}
}
