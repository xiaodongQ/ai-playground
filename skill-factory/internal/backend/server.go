package backend

import (
	"database/sql"
	"log"
)

func OpenDB(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, err
	}
	// 强制单连接，避免并发写导致 SQLITE_BUSY
	db.SetMaxOpenConns(1)
	// foreign_keys 必须每次连接都设（连接级）
	if _, err := db.Exec("PRAGMA foreign_keys = ON"); err != nil {
		log.Printf("PRAGMA foreign_keys: %v", err)
	}
	// WAL：读写并发，写不再阻塞读（之前默认 rollback journal 模式下，
	// scheduler 写 executions 表期间，前端读 ListRecent 会被锁、立即 SQLITE_BUSY → 500）
	if _, err := db.Exec("PRAGMA journal_mode = WAL"); err != nil {
		log.Printf("PRAGMA journal_mode: %v", err)
	}
	// busy_timeout：万一还是遇到锁竞争，等 5s 再报 BUSY，而不是 0ms 立即失败
	if _, err := db.Exec("PRAGMA busy_timeout = 5000"); err != nil {
		log.Printf("PRAGMA busy_timeout: %v", err)
	}
	return db, nil
}