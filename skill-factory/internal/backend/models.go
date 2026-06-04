package backend

import (
	"time"
)

// TaskStatus values
const (
	TaskStatusPending    = "pending"
	TaskStatusInProgress = "in_progress"
	TaskStatusArchived   = "archived"
	TaskStatusException  = "exception"
)

type Task struct {
	ID           string     `json:"id"`
	Title        string     `json:"title"`
	Description  string     `json:"description,omitempty"`
	Status       string     `json:"status"`
	ExperienceID string     `json:"experience_id,omitempty"`
	Resources    string     `json:"resources,omitempty"`
	Acceptance   string     `json:"acceptance,omitempty"`
	Version      string     `json:"version"`
	CreatedAt    time.Time  `json:"created_at"`
	ClaimedAt    *time.Time `json:"claimed_at,omitempty"`
	Maintainer   string     `json:"maintainer,omitempty"`
	RepoAddress  string     `json:"repo_address,omitempty"`
	ArchivedAt   *time.Time `json:"archived_at,omitempty"`
	Result       string     `json:"result,omitempty"`
}

type Experience struct {
	ID           string    `json:"id"`
	Module       string    `json:"module"`
	Keywords     string    `json:"keywords,omitempty"`
	LogPaths     string    `json:"log_paths,omitempty"`
	ToolUsage    string    `json:"tool_usage,omitempty"`
	Scene        string    `json:"scene,omitempty"`
	LogSamples   string    `json:"log_samples,omitempty"`
	CodeSnippets string    `json:"code_snippets,omitempty"`
	Version      string    `json:"version"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

type SkillVersion struct {
	ID        string    `json:"id"`
	TaskID    string    `json:"task_id"`
	Version   string    `json:"version"`
	TestCases string    `json:"test_cases"`
	Accuracy  float64   `json:"accuracy"`
	IterCount int       `json:"iter_count"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

type TaskFilter struct {
	Status string
	Offset int
	Limit  int
}

type TaskResult struct {
	SkillFile  string `json:"skill_file,omitempty"`
	Iterations string `json:"iterations,omitempty"`
	FinalAcc   float64 `json:"final_accuracy"`
	PassCount  int     `json:"pass_count"`
	FailCount  int     `json:"fail_count"`
	Message    string `json:"message,omitempty"`
}