PRAGMA foreign_keys = ON;


-- =========================================================
-- USERS
-- =========================================================

CREATE TABLE IF NOT EXISTS users (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    email TEXT NOT NULL UNIQUE,

    password_hash TEXT NOT NULL,

    role TEXT NOT NULL DEFAULT 'user',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        role IN ('user', 'admin')
    )
);


-- =========================================================
-- UPLOAD SOURCES
--
-- IMPORTANT:
-- Users do NOT upload files.
-- They submit links only.
-- =========================================================

CREATE TABLE IF NOT EXISTS uploads (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    uploaded_by INTEGER NOT NULL,

    title TEXT NOT NULL,

    source_url TEXT NOT NULL,

    upload_method TEXT NOT NULL DEFAULT 'link',

    source_type TEXT NOT NULL DEFAULT 'other',

    upload_mode TEXT NOT NULL DEFAULT 'mixed',

    target_module TEXT,

    target_category TEXT,

    status TEXT NOT NULL DEFAULT 'pending',

    error_message TEXT,

    row_count INTEGER NOT NULL DEFAULT 0,

    column_count INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (
        uploaded_by
    )
    REFERENCES users(id)
    ON DELETE CASCADE,

    CHECK (
        upload_method = 'link'
    ),

    CHECK (
        source_type IN (
            'google_drive',
            'google_sheets',
            'excel',
            'csv',
            'other'
        )
    ),

    CHECK (
        upload_mode IN (
            'mixed',
            'specific'
        )
    ),

    CHECK (
        status IN (
            'pending',
            'processing',
            'completed',
            'failed'
        )
    )
);


-- =========================================================
-- DATA RECORDS
--
-- Each imported spreadsheet row is stored here.
-- =========================================================

CREATE TABLE IF NOT EXISTS records (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    upload_id INTEGER NOT NULL,

    module_key TEXT NOT NULL,

    category_key TEXT,

    sheet_name TEXT,

    row_number INTEGER NOT NULL,

    row_data TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (
        upload_id
    )
    REFERENCES uploads(id)
    ON DELETE CASCADE
);


-- =========================================================
-- DATASET COLUMNS
--
-- Stores discovered spreadsheet columns.
-- =========================================================

CREATE TABLE IF NOT EXISTS dataset_columns (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    upload_id INTEGER NOT NULL,

    column_index INTEGER NOT NULL,

    column_name TEXT NOT NULL,

    data_type TEXT DEFAULT 'text',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (
        upload_id
    )
    REFERENCES uploads(id)
    ON DELETE CASCADE,

    UNIQUE (
        upload_id,
        column_index
    )
);


-- =========================================================
-- REFRESH / PROCESSING LOG
-- =========================================================

CREATE TABLE IF NOT EXISTS dataset_refresh_logs (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    upload_id INTEGER NOT NULL,

    status TEXT NOT NULL,

    rows_imported INTEGER NOT NULL DEFAULT 0,

    columns_imported INTEGER NOT NULL DEFAULT 0,

    message TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (
        upload_id
    )
    REFERENCES uploads(id)
    ON DELETE CASCADE,

    CHECK (
        status IN (
            'started',
            'completed',
            'failed'
        )
    )
);


-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_users_email
ON users(email);


CREATE INDEX IF NOT EXISTS idx_users_role
ON users(role);


CREATE INDEX IF NOT EXISTS idx_uploads_user
ON uploads(uploaded_by);


CREATE INDEX IF NOT EXISTS idx_uploads_status
ON uploads(status);


CREATE INDEX IF NOT EXISTS idx_uploads_created
ON uploads(created_at);


CREATE INDEX IF NOT EXISTS idx_records_upload
ON records(upload_id);


CREATE INDEX IF NOT EXISTS idx_records_module
ON records(module_key);


CREATE INDEX IF NOT EXISTS idx_records_category
ON records(category_key);


CREATE INDEX IF NOT EXISTS idx_columns_upload
ON dataset_columns(upload_id);


CREATE INDEX IF NOT EXISTS idx_refresh_upload
ON dataset_refresh_logs(upload_id);


-- =========================================================
-- TIMESTAMP TRIGGERS
-- =========================================================

CREATE TRIGGER IF NOT EXISTS update_users_timestamp
AFTER UPDATE ON users
FOR EACH ROW
BEGIN

    UPDATE users
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;

END;


CREATE TRIGGER IF NOT EXISTS update_upload_timestamp
AFTER UPDATE ON uploads
FOR EACH ROW
BEGIN

    UPDATE uploads
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;

END;