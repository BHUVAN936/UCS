
PRAGMA foreign_keys = ON;


-- =========================================================
-- UCE CONNECT DATABASE SCHEMA
-- =========================================================
--
-- IMPORTANT:
-- 1. Users submit spreadsheet LINKS only.
-- 2. Direct file uploads are NOT supported.
-- 3. Imported spreadsheet rows are stored in records.
-- 4. Imported columns are stored in dataset_columns.
-- 5. Deleting an upload automatically deletes its records,
--    columns and refresh logs because of ON DELETE CASCADE.
-- =========================================================


-- =========================================================
-- USERS
-- =========================================================

CREATE TABLE IF NOT EXISTS users (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL
        CHECK (length(trim(name)) > 0),

    email TEXT NOT NULL
        UNIQUE
        CHECK (length(trim(email)) > 0),

    password_hash TEXT NOT NULL
        CHECK (length(password_hash) > 0),

    role TEXT NOT NULL DEFAULT 'user'
        CHECK (
            role IN (
                'user',
                'admin'
            )
        ),

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- APPLICATION SETTINGS
-- =========================================================

CREATE TABLE IF NOT EXISTS app_settings (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    setting_key TEXT NOT NULL UNIQUE,

    setting_value TEXT,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- UPLOAD SOURCES
-- =========================================================
--
-- Users submit LINKS ONLY.
--
-- upload_method:
--     Always "link"
--
-- source_type:
--     google_drive
--     google_sheets
--     excel
--     csv
--     other
--
-- upload_mode:
--     mixed
--     specific
--
-- status:
--     pending
--     processing
--     completed
--     failed
-- =========================================================

CREATE TABLE IF NOT EXISTS uploads (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    uploaded_by INTEGER NOT NULL,

    title TEXT NOT NULL
        CHECK (length(trim(title)) > 0),

    source_url TEXT NOT NULL
        CHECK (
            length(trim(source_url)) > 0
            AND (
                source_url LIKE 'http://%'
                OR source_url LIKE 'https://%'
            )
        ),

    upload_method TEXT NOT NULL DEFAULT 'link'
        CHECK (
            upload_method = 'link'
        ),

    source_type TEXT NOT NULL DEFAULT 'other'
        CHECK (
            source_type IN (
                'google_drive',
                'google_sheets',
                'excel',
                'csv',
                'other'
            )
        ),

    upload_mode TEXT NOT NULL DEFAULT 'mixed'
        CHECK (
            upload_mode IN (
                'mixed',
                'specific'
            )
        ),

    target_module TEXT,

    target_category TEXT,

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'processing',
                'completed',
                'failed'
            )
        ),

    error_message TEXT,

    row_count INTEGER NOT NULL DEFAULT 0
        CHECK (row_count >= 0),

    column_count INTEGER NOT NULL DEFAULT 0
        CHECK (column_count >= 0),

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (uploaded_by)
        REFERENCES users(id)
        ON DELETE CASCADE
);


-- =========================================================
-- DATA RECORDS
-- =========================================================
--
-- Every imported spreadsheet row is stored here.
--
-- row_data contains JSON.
--
-- Example:
--
-- {
--     "Student Name": "Bhuvan",
--     "Department": "CSE",
--     "Year": "2026"
-- }
--
-- module_key identifies the main module.
--
-- category_key identifies the subtopic/category.
-- =========================================================

CREATE TABLE IF NOT EXISTS records (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    upload_id INTEGER NOT NULL,

    module_key TEXT NOT NULL
        CHECK (length(trim(module_key)) > 0),

    category_key TEXT,

    sheet_name TEXT,

    row_number INTEGER NOT NULL
        CHECK (row_number >= 1),

    row_data TEXT NOT NULL
        CHECK (length(trim(row_data)) > 0),

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (upload_id)
        REFERENCES uploads(id)
        ON DELETE CASCADE
);


-- =========================================================
-- DATASET COLUMNS
-- =========================================================
--
-- Stores the columns discovered from each spreadsheet.
--
-- Example:
--
-- upload_id | column_index | column_name
-- ---------------------------------------
--     1     |      0       | Student Name
--     1     |      1       | Department
--     1     |      2       | Year
-- =========================================================

CREATE TABLE IF NOT EXISTS dataset_columns (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    upload_id INTEGER NOT NULL,

    column_index INTEGER NOT NULL
        CHECK (column_index >= 0),

    column_name TEXT NOT NULL
        CHECK (length(trim(column_name)) > 0),

    data_type TEXT NOT NULL DEFAULT 'text',

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (upload_id)
        REFERENCES uploads(id)
        ON DELETE CASCADE,

    UNIQUE (
        upload_id,
        column_index
    )
);


-- =========================================================
-- DATASET REFRESH / PROCESSING LOG
-- =========================================================
--
-- Keeps a history of import operations.
--
-- status:
--     started
--     completed
--     failed
-- =========================================================

CREATE TABLE IF NOT EXISTS dataset_refresh_logs (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    upload_id INTEGER NOT NULL,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'started',
                'completed',
                'failed'
            )
        ),

    rows_imported INTEGER NOT NULL DEFAULT 0
        CHECK (rows_imported >= 0),

    columns_imported INTEGER NOT NULL DEFAULT 0
        CHECK (columns_imported >= 0),

    message TEXT,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (upload_id)
        REFERENCES uploads(id)
        ON DELETE CASCADE
);


-- =========================================================
-- PASSWORD RESET TOKENS
-- =========================================================

CREATE TABLE IF NOT EXISTS password_reset_tokens (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    token_hash TEXT NOT NULL UNIQUE,

    expires_at TIMESTAMP NOT NULL,

    used_at TIMESTAMP,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);


-- =========================================================
-- INDEXES
-- =========================================================


-- ---------------------------------------------------------
-- USERS
-- ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_users_email
ON users(email);


CREATE INDEX IF NOT EXISTS idx_users_role
ON users(role);


CREATE INDEX IF NOT EXISTS idx_users_created_at
ON users(created_at);


-- ---------------------------------------------------------
-- UPLOADS
-- ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_uploads_uploaded_by
ON uploads(uploaded_by);


CREATE INDEX IF NOT EXISTS idx_uploads_status
ON uploads(status);


CREATE INDEX IF NOT EXISTS idx_uploads_source_type
ON uploads(source_type);


CREATE INDEX IF NOT EXISTS idx_uploads_upload_mode
ON uploads(upload_mode);


CREATE INDEX IF NOT EXISTS idx_uploads_target_module
ON uploads(target_module);


CREATE INDEX IF NOT EXISTS idx_uploads_target_category
ON uploads(target_category);


CREATE INDEX IF NOT EXISTS idx_uploads_created_at
ON uploads(created_at);


-- ---------------------------------------------------------
-- RECORDS
-- ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_records_upload_id
ON records(upload_id);


CREATE INDEX IF NOT EXISTS idx_records_module_key
ON records(module_key);


CREATE INDEX IF NOT EXISTS idx_records_category_key
ON records(category_key);


CREATE INDEX IF NOT EXISTS idx_records_sheet_name
ON records(sheet_name);


CREATE INDEX IF NOT EXISTS idx_records_row_number
ON records(row_number);


CREATE INDEX IF NOT EXISTS idx_records_created_at
ON records(created_at);


-- ---------------------------------------------------------
-- DATASET COLUMNS
-- ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_dataset_columns_upload_id
ON dataset_columns(upload_id);


CREATE INDEX IF NOT EXISTS idx_dataset_columns_name
ON dataset_columns(column_name);


-- ---------------------------------------------------------
-- REFRESH LOGS
-- ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_refresh_logs_upload_id
ON dataset_refresh_logs(upload_id);


CREATE INDEX IF NOT EXISTS idx_refresh_logs_status
ON dataset_refresh_logs(status);


CREATE INDEX IF NOT EXISTS idx_refresh_logs_created_at
ON dataset_refresh_logs(created_at);


-- ---------------------------------------------------------
-- APPLICATION SETTINGS
-- ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_app_settings_key
ON app_settings(setting_key);


-- ---------------------------------------------------------
-- PASSWORD RESET TOKENS
-- ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id
ON password_reset_tokens(user_id);


CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token_hash
ON password_reset_tokens(token_hash);


CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at
ON password_reset_tokens(expires_at);


-- =========================================================
-- TIMESTAMP TRIGGERS
-- =========================================================
--
-- IMPORTANT:
-- The WHEN condition prevents unnecessary recursive
-- timestamp updates.
-- =========================================================


-- ---------------------------------------------------------
-- USERS UPDATED_AT
-- ---------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS update_users_timestamp

AFTER UPDATE ON users

FOR EACH ROW

WHEN NEW.updated_at = OLD.updated_at

BEGIN

    UPDATE users

    SET updated_at = CURRENT_TIMESTAMP

    WHERE id = OLD.id;

END;


-- ---------------------------------------------------------
-- UPLOADS UPDATED_AT
-- ---------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS update_upload_timestamp

AFTER UPDATE ON uploads

FOR EACH ROW

WHEN NEW.updated_at = OLD.updated_at

BEGIN

    UPDATE uploads

    SET updated_at = CURRENT_TIMESTAMP

    WHERE id = OLD.id;

END;


-- ---------------------------------------------------------
-- APPLICATION SETTINGS UPDATED_AT
-- ---------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS update_app_settings_timestamp

AFTER UPDATE ON app_settings

FOR EACH ROW

WHEN NEW.updated_at = OLD.updated_at

BEGIN

    UPDATE app_settings

    SET updated_at = CURRENT_TIMESTAMP

    WHERE id = OLD.id;

END;


-- =========================================================
-- END OF SCHEMA
-- =========================================================
