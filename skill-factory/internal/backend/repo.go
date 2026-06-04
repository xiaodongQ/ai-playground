package backend

import (
	"database/sql"
	"fmt"
	"strings"
	"time"
)

func InitSchema(db *sql.DB) error {
	schema := `
	CREATE TABLE IF NOT EXISTS tasks (
		id TEXT PRIMARY KEY,
		title TEXT NOT NULL,
		description TEXT,
		status TEXT DEFAULT 'pending',
		experience_id TEXT,
		resources TEXT,
		acceptance TEXT,
		version TEXT DEFAULT 'v0.0.1',
		created_at DATETIME,
		claimed_at DATETIME,
		maintainer TEXT,
		repo_address TEXT,
		archived_at DATETIME,
		result TEXT
	);
	CREATE TABLE IF NOT EXISTS experiences (
		id TEXT PRIMARY KEY,
		module TEXT NOT NULL,
		keywords TEXT,
		log_paths TEXT,
		tool_usage TEXT,
		scene TEXT,
		log_samples TEXT,
		code_snippets TEXT,
		version TEXT,
		created_at DATETIME,
		updated_at DATETIME
	);
	CREATE TABLE IF NOT EXISTS skill_versions (
		id TEXT PRIMARY KEY,
		task_id TEXT,
		version TEXT,
		test_cases TEXT,
		accuracy REAL,
		iter_count INTEGER,
		status TEXT,
		created_at DATETIME
	);
	`
	_, err := db.Exec(schema)
	return err
}

type TaskRepo struct{ db *sql.DB }

func NewTaskRepo(db *sql.DB) *TaskRepo { return &TaskRepo{db: db} }

func (r *TaskRepo) Create(t *Task) error {
	q := `INSERT INTO tasks (id,title,description,status,experience_id,resources,acceptance,version,created_at)
	        VALUES (?,?,?,?,?,?,?,?,?)`
	_, err := r.db.Exec(q, t.ID, t.Title, t.Description, t.Status,
		t.ExperienceID, t.Resources, t.Acceptance, t.Version, t.CreatedAt)
	return err
}

func (r *TaskRepo) Get(id string) (*Task, error) {
	q := `SELECT id,title,description,status,experience_id,resources,acceptance,version,created_at,claimed_at,maintainer,repo_address,archived_at,result FROM tasks WHERE id=?`
	var t Task
	var claimedAt, archivedAt sql.NullTime
	var acc, res, maintainer, repoAddr sql.NullString
	err := r.db.QueryRow(q, id).Scan(&t.ID, &t.Title, &t.Description, &t.Status,
		&t.ExperienceID, &t.Resources, &acc, &t.Version, &t.CreatedAt,
		&claimedAt, &maintainer, &repoAddr, &archivedAt, &res)
	t.Acceptance = acc.String
	t.Result = res.String
	t.Maintainer = maintainer.String
	t.RepoAddress = repoAddr.String
	if claimedAt.Valid { t.ClaimedAt = &claimedAt.Time }
	if archivedAt.Valid { t.ArchivedAt = &archivedAt.Time }
	if err == sql.ErrNoRows { return nil, fmt.Errorf("task %s not found", id) }
	return &t, err
}

func (r *TaskRepo) UpdateStatus(id, status, maintainer string) error {
	now := time.Now()
	switch status {
	case TaskStatusInProgress:
		q := `UPDATE tasks SET status=?, maintainer=?, claimed_at=? WHERE id=?`
		_, err := r.db.Exec(q, status, maintainer, now, id)
		return err
	case TaskStatusArchived:
		q := `UPDATE tasks SET status=?, archived_at=? WHERE id=?`
		_, err := r.db.Exec(q, status, now, id)
		return err
	default:
		q := `UPDATE tasks SET status=? WHERE id=?`
		_, err := r.db.Exec(q, status, id)
		return err
	}
}

func (r *TaskRepo) List(filter TaskFilter) ([]*Task, error) {
	q := `SELECT id,title,description,status,experience_id,resources,acceptance,version,created_at,claimed_at,maintainer,repo_address,archived_at,result FROM tasks`
	var args []any
	if filter.Status != "" {
		q += ` WHERE status=?`
		args = append(args, filter.Status)
	}
	q += ` ORDER BY created_at DESC LIMIT ? OFFSET ?`
	args = append(args, filter.Limit, filter.Offset)
	rows, err := r.db.Query(q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var tasks []*Task
	for rows.Next() {
		var t Task
		var claimedAt, archivedAt sql.NullTime
		var acc, res, maintainer, repoAddr sql.NullString
		err := rows.Scan(&t.ID, &t.Title, &t.Description, &t.Status,
			&t.ExperienceID, &t.Resources, &acc, &t.Version, &t.CreatedAt,
			&claimedAt, &maintainer, &repoAddr, &archivedAt, &res)
		t.Acceptance = acc.String
		t.Result = res.String
		t.Maintainer = maintainer.String
		t.RepoAddress = repoAddr.String
		if claimedAt.Valid { t.ClaimedAt = &claimedAt.Time }
		if archivedAt.Valid { t.ArchivedAt = &archivedAt.Time }
		if err != nil { return nil, err }
		tasks = append(tasks, &t)
	}
	return tasks, rows.Err()
}

type ExperienceRepo struct{ db *sql.DB }

func NewExperienceRepo(db *sql.DB) *ExperienceRepo { return &ExperienceRepo{db: db} }

func (r *ExperienceRepo) Create(e *Experience) error {
	q := `INSERT INTO experiences (id,module,keywords,log_paths,tool_usage,scene,log_samples,code_snippets,version,created_at,updated_at)
	        VALUES (?,?,?,?,?,?,?,?,?,?,?)`
	_, err := r.db.Exec(q, e.ID, e.Module, e.Keywords, e.LogPaths,
		e.ToolUsage, e.Scene, e.LogSamples, e.CodeSnippets, e.Version, e.CreatedAt, e.UpdatedAt)
	return err
}

func (r *ExperienceRepo) Get(id string) (*Experience, error) {
	q := `SELECT id,module,keywords,log_paths,tool_usage,scene,log_samples,code_snippets,version,created_at,updated_at FROM experiences WHERE id=?`
	var e Experience
	err := r.db.QueryRow(q, id).Scan(&e.ID, &e.Module, &e.Keywords, &e.LogPaths, &e.ToolUsage, &e.Scene, &e.LogSamples, &e.CodeSnippets, &e.Version, &e.CreatedAt, &e.UpdatedAt)
	if err == sql.ErrNoRows { return nil, fmt.Errorf("experience %s not found", id) }
	return &e, err
}

func (r *ExperienceRepo) Search(module string) ([]*Experience, error) {
	q := `SELECT id,module,keywords,log_paths,tool_usage,scene,log_samples,code_snippets,version,created_at,updated_at FROM experiences WHERE 1=1`
	var args []any
	if module != "" {
		q += ` AND module LIKE ?`
		args = append(args, "%"+module+"%")
	}
	rows, err := r.db.Query(q, args...)
	if err != nil { return nil, err }
	defer rows.Close()
	var list []*Experience
	for rows.Next() {
		var e Experience
		err := rows.Scan(&e.ID, &e.Module, &e.Keywords, &e.LogPaths, &e.ToolUsage, &e.Scene, &e.LogSamples, &e.CodeSnippets, &e.Version, &e.CreatedAt, &e.UpdatedAt)
		if err != nil { return nil, err }
		list = append(list, &e)
	}
	return list, rows.Err()
}

func TestDB() (*sql.DB, func(), error) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil { return nil, nil, err }
	if err := InitSchema(db); err != nil { db.Close(); return nil, nil, err }
	return db, func() { db.Close() }, nil
}

func ExportExperienceMD(e *Experience) string {
	var sb strings.Builder
	sb.WriteString("# Experience: " + e.Module + "\n\n")
	if e.Keywords != "" { sb.WriteString("## Keywords\n" + e.Keywords + "\n\n") }
	if e.LogPaths != "" { sb.WriteString("## Log Paths\n" + e.LogPaths + "\n\n") }
	if e.ToolUsage != "" { sb.WriteString("## Tool Usage\n" + e.ToolUsage + "\n\n") }
	if e.Scene != "" { sb.WriteString("## Scenes\n" + e.Scene + "\n\n") }
	if e.LogSamples != "" { sb.WriteString("## Log Samples\n```\n" + e.LogSamples + "\n```\n\n") }
	if e.CodeSnippets != "" { sb.WriteString("## Code Snippets\n```\n" + e.CodeSnippets + "\n```\n\n") }
	return sb.String()
}