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
	_, err = db.Exec("PRAGMA foreign_keys = ON")
	if err != nil {
		log.Printf("PRAGMA foreign_keys: %v", err)
	}
	return db, nil
}