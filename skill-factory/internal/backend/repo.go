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
		priority INTEGER DEFAULT 5,
		experience_id TEXT,
		resources TEXT,
		acceptance TEXT,
		version TEXT DEFAULT 'v0.0.1',
		created_at DATETIME,
		claimed_at DATETIME,
		started_at DATETIME,
		completed_at DATETIME,
		maintainer TEXT,
		repo_address TEXT,
		archived_at DATETIME,
		result TEXT,
		executor_model TEXT,
		cbc_model TEXT,
		iteration_count INTEGER DEFAULT 0,
		max_iterations INTEGER DEFAULT 20,
		improvement_threshold REAL,
		last_heartbeat DATETIME,
		last_error TEXT
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
	CREATE TABLE IF NOT EXISTS executions (
		id TEXT PRIMARY KEY,
		task_id TEXT,
		scheduled_task_id TEXT,
		source TEXT NOT NULL,
		command TEXT NOT NULL,
		model TEXT,
		started_at DATETIME,
		completed_at DATETIME,
		output TEXT NOT NULL DEFAULT '',
		error TEXT NOT NULL DEFAULT '',
		exit_code INTEGER NOT NULL DEFAULT 0
	);
	CREATE INDEX IF NOT EXISTS idx_executions_task ON executions(task_id, started_at DESC);
	CREATE INDEX IF NOT EXISTS idx_executions_scheduled ON executions(scheduled_task_id, started_at DESC);
	CREATE TABLE IF NOT EXISTS evaluations (
		id TEXT PRIMARY KEY,
		task_id TEXT,
		execution_id TEXT,
		evaluator_model TEXT,
		score REAL,
		comments TEXT,
		created_at DATETIME
	);
	CREATE TABLE IF NOT EXISTS web_links (
		id TEXT PRIMARY KEY,
		name TEXT NOT NULL,
		url TEXT NOT NULL,
		icon_url TEXT,
		sort_order INTEGER DEFAULT 0,
		created_at DATETIME
	);
	CREATE TABLE IF NOT EXISTS dir_shortcuts (
		id TEXT PRIMARY KEY,
		name TEXT NOT NULL,
		path TEXT NOT NULL,
		sort_order INTEGER DEFAULT 0,
		created_at DATETIME,
		last_accessed_at DATETIME
	);
	CREATE TABLE IF NOT EXISTS scheduled_tasks (
		id TEXT PRIMARY KEY,
		name TEXT NOT NULL,
		cron_expr TEXT NOT NULL,
		command_type TEXT NOT NULL,
		model TEXT,
		prompt TEXT,
		working_dir TEXT,
		enabled INTEGER DEFAULT 1,
		last_run_at DATETIME,
		last_status TEXT,
		last_execution_id TEXT,
		created_at DATETIME
	);
	CREATE TABLE IF NOT EXISTS app_settings (
		key TEXT PRIMARY KEY,
		value TEXT NOT NULL,
		updated_at DATETIME
	);
	CREATE TABLE IF NOT EXISTS app_meta (
		key TEXT PRIMARY KEY,
		value TEXT NOT NULL
	);
	`
	if _, err := db.Exec(schema); err != nil {
		return err
	}
	// 增量迁移：旧 db 的 tasks 表可能缺新字段
	if err := migrateTasksColumns(db); err != nil {
		return err
	}
	if _, err := db.Exec(`PRAGMA user_version = 2`); err != nil {
		return err
	}
	return nil
}

// migrateTasksColumns 对已存在的 tasks 表补充 v2 新字段
func migrateTasksColumns(db *sql.DB) error {
	rows, err := db.Query(`PRAGMA table_info(tasks)`)
	if err != nil {
		// 表可能还没建好，正常情况（schema 刚建好）
		return nil
	}
	defer rows.Close()
	cols := map[string]bool{}
	for rows.Next() {
		var cid, notnull, pk int
		var name, ctype string
		var dflt sql.NullString
		_ = rows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk)
		cols[name] = true
	}
	addCol := func(name, decl string) error {
		if cols[name] { return nil }
		_, err := db.Exec(`ALTER TABLE tasks ADD COLUMN ` + decl)
		return err
	}
	add := []struct{ n, d string }{
		{"priority", "priority INTEGER DEFAULT 5"},
		{"started_at", "started_at DATETIME"},
		{"completed_at", "completed_at DATETIME"},
		{"executor_model", "executor_model TEXT"},
		{"cbc_model", "cbc_model TEXT"},
		{"iteration_count", "iteration_count INTEGER DEFAULT 0"},
		{"max_iterations", "max_iterations INTEGER DEFAULT 20"},
		{"improvement_threshold", "improvement_threshold REAL"},
		{"last_heartbeat", "last_heartbeat DATETIME"},
		{"last_error", "last_error TEXT"},
	}
	for _, a := range add {
		if err := addCol(a.n, a.d); err != nil {
			return err
		}
	}
	return nil
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
		// 认领：设 maintainer + claimed_at + started_at + last_heartbeat
		q := `UPDATE tasks SET status=?, maintainer=?, claimed_at=?, started_at=COALESCE(started_at, ?), last_heartbeat=? WHERE id=?`
		_, err := r.db.Exec(q, status, maintainer, now, now, now, id)
		return err
	case TaskStatusArchived:
		q := `UPDATE tasks SET status=?, archived_at=?, completed_at=COALESCE(completed_at, ?) WHERE id=?`
		_, err := r.db.Exec(q, status, now, now, id)
		return err
	case TaskStatusPending:
		// 取消认领：清空 maintainer/claimed_at/started_at/last_heartbeat
		q := `UPDATE tasks SET status=?, maintainer='', claimed_at=NULL, started_at=NULL, last_heartbeat=NULL WHERE id=?`
		_, err := r.db.Exec(q, status, id)
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

// ===== ExecutionRepo =====

type ExecutionRepo struct{ db *sql.DB }

func NewExecutionRepo(db *sql.DB) *ExecutionRepo { return &ExecutionRepo{db: db} }

func (r *ExecutionRepo) Create(e *Execution) error {
	// 显式插入所有字段，completed_at/output/error/exit_code 传 NULL/空/0，
	// 避免"在跑中"行（未 Finish）这些字段为 NULL 时 ListRecent scan 炸。
	q := `INSERT INTO executions (id,task_id,scheduled_task_id,source,command,model,started_at,completed_at,output,error,exit_code)
	        VALUES (?,?,?,?,?,?,?,NULL,'','',0)`
	_, err := r.db.Exec(q, e.ID, e.TaskID, e.ScheduledTaskID, e.Source, e.Command, e.Model, e.StartedAt)
	return err
}

func (r *ExecutionRepo) Finish(id string, output, errOut string, exitCode int) error {
	now := time.Now()
	_, err := r.db.Exec(`UPDATE executions SET completed_at=?, output=?, error=?, exit_code=? WHERE id=?`,
		now, output, errOut, exitCode, id)
	return err
}

func (r *ExecutionRepo) Get(id string) (*Execution, error) {
	q := `SELECT id,task_id,scheduled_task_id,source,command,model,started_at,completed_at,output,error,exit_code
	        FROM executions WHERE id=?`
	var e Execution
	var taskID, schedID, model, output, errOut sql.NullString
	var completedAt sql.NullTime
	err := r.db.QueryRow(q, id).Scan(&e.ID, &taskID, &schedID, &e.Source, &e.Command, &model,
		&e.StartedAt, &completedAt, &output, &errOut, &e.ExitCode)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("execution %s not found", id)
	}
	if err != nil {
		return nil, err
	}
	e.TaskID = taskID.String
	e.ScheduledTaskID = schedID.String
	e.Model = model.String
	e.Output = output.String
	e.Error = errOut.String
	if completedAt.Valid {
		e.CompletedAt = &completedAt.Time
	}
	return &e, nil
}

// ListByTask 返回某任务的最近 N 次执行。
func (r *ExecutionRepo) ListByTask(taskID string, limit int) ([]*Execution, error) {
	if limit <= 0 {
		limit = 20
	}
	q := `SELECT id,task_id,scheduled_task_id,source,command,model,started_at,completed_at,output,error,exit_code
	        FROM executions WHERE task_id=? ORDER BY started_at DESC LIMIT ?`
	rows, err := r.db.Query(q, taskID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Execution
	for rows.Next() {
		var e Execution
		var taskID, schedID, model, output, errOut sql.NullString
		var completedAt sql.NullTime
		if err := rows.Scan(&e.ID, &taskID, &schedID, &e.Source, &e.Command, &model,
			&e.StartedAt, &completedAt, &output, &errOut, &e.ExitCode); err != nil {
			return nil, err
		}
		e.TaskID = taskID.String
		e.ScheduledTaskID = schedID.String
		e.Model = model.String
		e.Output = output.String
		e.Error = errOut.String
		if completedAt.Valid {
			e.CompletedAt = &completedAt.Time
		}
		out = append(out, &e)
	}
	return out, rows.Err()
}

// ListRecent 返回所有最近执行（无 task 过滤），用于 stats/dashboard。
func (r *ExecutionRepo) ListRecent(limit int) ([]*Execution, error) {
	if limit <= 0 {
		limit = 50
	}
	// LEFT JOIN evaluations 取最近一次分数（每 exec 只关联最新一条）
	q := `SELECT e.id,e.task_id,e.scheduled_task_id,e.source,e.command,e.model,
	             e.started_at,e.completed_at,e.output,e.error,e.exit_code,
	             (SELECT ev.score FROM evaluations ev
	                WHERE ev.execution_id = e.id
	                ORDER BY ev.created_at DESC LIMIT 1) AS eval_score
	        FROM executions e ORDER BY e.started_at DESC LIMIT ?`
	rows, err := r.db.Query(q, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Execution
	for rows.Next() {
		var e Execution
		var taskID, schedID, model, output, errOut sql.NullString
		var completedAt sql.NullTime
		var evalScore sql.NullFloat64
		if err := rows.Scan(&e.ID, &taskID, &schedID, &e.Source, &e.Command, &model,
			&e.StartedAt, &completedAt, &output, &errOut, &e.ExitCode, &evalScore); err != nil {
			return nil, err
		}
		if evalScore.Valid {
			v := evalScore.Float64
			e.EvaluationScore = &v
		}
		e.TaskID = taskID.String
		e.ScheduledTaskID = schedID.String
		e.Model = model.String
		e.Output = output.String
		e.Error = errOut.String
		if completedAt.Valid {
			e.CompletedAt = &completedAt.Time
		}
		out = append(out, &e)
	}
	return out, rows.Err()
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

// ===== WebLinkRepo =====

type WebLinkRepo struct{ db *sql.DB }

func NewWebLinkRepo(db *sql.DB) *WebLinkRepo { return &WebLinkRepo{db: db} }

func (r *WebLinkRepo) Create(w *WebLink) error {
	q := `INSERT INTO web_links (id,name,url,icon_url,sort_order,created_at)
	        VALUES (?,?,?,?,?,?)`
	_, err := r.db.Exec(q, w.ID, w.Name, w.URL, w.IconURL, w.SortOrder, w.CreatedAt)
	return err
}

func (r *WebLinkRepo) Update(w *WebLink) error {
	_, err := r.db.Exec(`UPDATE web_links SET name=?, url=?, icon_url=?, sort_order=? WHERE id=?`,
		w.Name, w.URL, w.IconURL, w.SortOrder, w.ID)
	return err
}

func (r *WebLinkRepo) Delete(id string) error {
	_, err := r.db.Exec(`DELETE FROM web_links WHERE id=?`, id)
	return err
}

func (r *WebLinkRepo) List() ([]*WebLink, error) {
	rows, err := r.db.Query(`SELECT id,name,url,icon_url,sort_order,created_at FROM web_links ORDER BY sort_order ASC, created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*WebLink
	for rows.Next() {
		var w WebLink
		var icon sql.NullString
		if err := rows.Scan(&w.ID, &w.Name, &w.URL, &icon, &w.SortOrder, &w.CreatedAt); err != nil {
			return nil, err
		}
		w.IconURL = icon.String
		out = append(out, &w)
	}
	return out, rows.Err()
}

// ===== DirShortcutRepo =====

type DirShortcutRepo struct{ db *sql.DB }

func NewDirShortcutRepo(db *sql.DB) *DirShortcutRepo { return &DirShortcutRepo{db: db} }

func (r *DirShortcutRepo) Create(d *DirShortcut) error {
	q := `INSERT INTO dir_shortcuts (id,name,path,sort_order,created_at)
	        VALUES (?,?,?,?,?)`
	_, err := r.db.Exec(q, d.ID, d.Name, d.Path, d.SortOrder, d.CreatedAt)
	return err
}

func (r *DirShortcutRepo) Update(d *DirShortcut) error {
	_, err := r.db.Exec(`UPDATE dir_shortcuts SET name=?, path=?, sort_order=? WHERE id=?`,
		d.Name, d.Path, d.SortOrder, d.ID)
	return err
}

func (r *DirShortcutRepo) Delete(id string) error {
	_, err := r.db.Exec(`DELETE FROM dir_shortcuts WHERE id=?`, id)
	return err
}

func (r *DirShortcutRepo) Touch(id string) error {
	_, err := r.db.Exec(`UPDATE dir_shortcuts SET last_accessed_at=? WHERE id=?`, time.Now(), id)
	return err
}

func (r *DirShortcutRepo) List() ([]*DirShortcut, error) {
	rows, err := r.db.Query(`SELECT id,name,path,sort_order,created_at,last_accessed_at FROM dir_shortcuts ORDER BY sort_order ASC, created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*DirShortcut
	for rows.Next() {
		var d DirShortcut
		var lastAcc sql.NullTime
		if err := rows.Scan(&d.ID, &d.Name, &d.Path, &d.SortOrder, &d.CreatedAt, &lastAcc); err != nil {
			return nil, err
		}
		if lastAcc.Valid {
			d.LastAccessedAt = &lastAcc.Time
		}
		out = append(out, &d)
	}
	return out, rows.Err()
}

// ===== ScheduledTaskRepo =====

type ScheduledTaskRepo struct{ db *sql.DB }

func NewScheduledTaskRepo(db *sql.DB) *ScheduledTaskRepo { return &ScheduledTaskRepo{db: db} }

func (r *ScheduledTaskRepo) Create(t *ScheduledTask) error {
	q := `INSERT INTO scheduled_tasks (id,name,cron_expr,command_type,model,prompt,working_dir,enabled,created_at)
	        VALUES (?,?,?,?,?,?,?,?,?)`
	_, err := r.db.Exec(q, t.ID, t.Name, t.CronExpr, t.CommandType, t.Model, t.Prompt,
		t.WorkingDir, boolToInt(t.Enabled), t.CreatedAt)
	return err
}

func (r *ScheduledTaskRepo) Update(t *ScheduledTask) error {
	_, err := r.db.Exec(`UPDATE scheduled_tasks SET name=?, cron_expr=?, command_type=?, model=?, prompt=?, working_dir=?, enabled=? WHERE id=?`,
		t.Name, t.CronExpr, t.CommandType, t.Model, t.Prompt, t.WorkingDir, boolToInt(t.Enabled), t.ID)
	return err
}

func (r *ScheduledTaskRepo) Delete(id string) error {
	_, err := r.db.Exec(`DELETE FROM scheduled_tasks WHERE id=?`, id)
	return err
}

func (r *ScheduledTaskRepo) Get(id string) (*ScheduledTask, error) {
	var t ScheduledTask
	var model, prompt, workdir, lastStatus, lastExecID sql.NullString
	var lastRunAt sql.NullTime
	var enabled int
	err := r.db.QueryRow(`SELECT id,name,cron_expr,command_type,model,prompt,working_dir,enabled,last_run_at,last_status,last_execution_id,created_at
	        FROM scheduled_tasks WHERE id=?`, id).Scan(&t.ID, &t.Name, &t.CronExpr, &t.CommandType,
		&model, &prompt, &workdir, &enabled, &lastRunAt, &lastStatus, &lastExecID, &t.CreatedAt)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("scheduled_task %s not found", id)
	}
	if err != nil {
		return nil, err
	}
	t.Model = model.String
	t.Prompt = prompt.String
	t.WorkingDir = workdir.String
	t.LastStatus = lastStatus.String
	t.LastExecutionID = lastExecID.String
	t.Enabled = enabled != 0
	if lastRunAt.Valid {
		t.LastRunAt = &lastRunAt.Time
	}
	return &t, nil
}

func (r *ScheduledTaskRepo) List() ([]*ScheduledTask, error) {
	return r.listWhere("")
}

func (r *ScheduledTaskRepo) ListEnabled() ([]*ScheduledTask, error) {
	return r.listWhere("WHERE enabled=1")
}

func (r *ScheduledTaskRepo) listWhere(where string) ([]*ScheduledTask, error) {
	q := `SELECT id,name,cron_expr,command_type,model,prompt,working_dir,enabled,last_run_at,last_status,last_execution_id,created_at
	        FROM scheduled_tasks ` + where + ` ORDER BY created_at DESC`
	rows, err := r.db.Query(q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*ScheduledTask
	for rows.Next() {
		var t ScheduledTask
		var model, prompt, workdir, lastStatus, lastExecID sql.NullString
		var lastRunAt sql.NullTime
		var enabled int
		if err := rows.Scan(&t.ID, &t.Name, &t.CronExpr, &t.CommandType,
			&model, &prompt, &workdir, &enabled, &lastRunAt, &lastStatus, &lastExecID, &t.CreatedAt); err != nil {
			return nil, err
		}
		t.Model = model.String
		t.Prompt = prompt.String
		t.WorkingDir = workdir.String
		t.LastStatus = lastStatus.String
		t.LastExecutionID = lastExecID.String
		t.Enabled = enabled != 0
		if lastRunAt.Valid {
			t.LastRunAt = &lastRunAt.Time
		}
		out = append(out, &t)
	}
	return out, rows.Err()
}

func (r *ScheduledTaskRepo) UpdateAfterRun(id, status, executionID string) error {
	_, err := r.db.Exec(`UPDATE scheduled_tasks SET last_run_at=?, last_status=?, last_execution_id=? WHERE id=?`,
		time.Now(), status, executionID, id)
	return err
}

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

// ===== AppSettingsRepo =====

type AppSettingsRepo struct{ db *sql.DB }

func NewAppSettingsRepo(db *sql.DB) *AppSettingsRepo { return &AppSettingsRepo{db: db} }

func (r *AppSettingsRepo) Get(key string) (string, error) {
	var v string
	err := r.db.QueryRow(`SELECT value FROM app_settings WHERE key=?`, key).Scan(&v)
	if err == sql.ErrNoRows {
		return "", nil
	}
	return v, err
}

func (r *AppSettingsRepo) Set(key, value string) error {
	now := time.Now()
	_, err := r.db.Exec(`INSERT INTO app_settings (key,value,updated_at) VALUES (?,?,?)
	        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at`,
		key, value, now)
	return err
}

func (r *AppSettingsRepo) All() (map[string]string, error) {
	rows, err := r.db.Query(`SELECT key, value FROM app_settings`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	m := map[string]string{}
	for rows.Next() {
		var k, v string
		if err := rows.Scan(&k, &v); err != nil {
			return nil, err
		}
		m[k] = v
	}
	return m, rows.Err()
}

// ===== EvaluationRepo =====

type EvaluationRepo struct{ db *sql.DB }

func NewEvaluationRepo(db *sql.DB) *EvaluationRepo { return &EvaluationRepo{db: db} }

func (r *EvaluationRepo) Create(e *Evaluation) error {
	_, err := r.db.Exec(`INSERT INTO evaluations (id,task_id,execution_id,evaluator_model,score,comments,created_at)
	        VALUES (?,?,?,?,?,?,?)`,
		e.ID, e.TaskID, e.ExecutionID, e.EvaluatorModel, e.Score, e.Comments, e.CreatedAt)
	return err
}

func (r *EvaluationRepo) ListByTask(taskID string) ([]*Evaluation, error) {
	rows, err := r.db.Query(`SELECT id,task_id,execution_id,evaluator_model,score,comments,created_at
	        FROM evaluations WHERE task_id=? ORDER BY created_at DESC`, taskID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Evaluation
	for rows.Next() {
		var e Evaluation
		var taskID, execID, model, comments sql.NullString
		if err := rows.Scan(&e.ID, &taskID, &execID, &model, &e.Score, &comments, &e.CreatedAt); err != nil {
			return nil, err
		}
		e.TaskID = taskID.String
		e.ExecutionID = execID.String
		e.EvaluatorModel = model.String
		e.Comments = comments.String
		out = append(out, &e)
	}
	return out, rows.Err()
}

// ListByExecution 查某次 execution 的所有 evaluation（按时间倒序）。
func (r *EvaluationRepo) ListByExecution(execID string) ([]*Evaluation, error) {
	rows, err := r.db.Query(`SELECT id,task_id,execution_id,evaluator_model,score,comments,created_at
	        FROM evaluations WHERE execution_id=? ORDER BY created_at DESC`, execID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Evaluation
	for rows.Next() {
		var e Evaluation
		var taskID, execModel, model, comments sql.NullString
		if err := rows.Scan(&e.ID, &taskID, &execModel, &model, &e.Score, &comments, &e.CreatedAt); err != nil {
			return nil, err
		}
		e.TaskID = taskID.String
		e.ExecutionID = execModel.String
		e.EvaluatorModel = model.String
		e.Comments = comments.String
		out = append(out, &e)
	}
	return out, rows.Err()
}
