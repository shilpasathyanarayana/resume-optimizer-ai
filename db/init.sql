-- ============================================================
--  Resume Optimizer AI — Database Schema
--  Database: resume_db
-- ============================================================

USE resume_db;

-- ============================================================
--  USERS
--  Stores registered user accounts
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id            INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    name          VARCHAR(100)     NOT NULL,
    email         VARCHAR(255)     NOT NULL,
    password_hash VARCHAR(255)     NOT NULL,
    is_active     TINYINT(1)       NOT NULL DEFAULT 1,
    is_verified   TINYINT(1)       NOT NULL DEFAULT 0,
    monthly_usage TINYINT UNSIGNED NOT NULL DEFAULT 0,
    plan          ENUM('free','pro') NOT NULL DEFAULT 'free',
    created_at    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    usage_reset_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
--  USER LOGIN LOG
--  Tracks every login attempt (success and failure)
--  Useful for security auditing and detecting brute force
-- ============================================================
CREATE TABLE IF NOT EXISTS user_login_log (
    id            INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    user_id       INT UNSIGNED     NULL,                        -- NULL if email not found
    email         VARCHAR(255)     NOT NULL,                    -- always log the attempted email
    ip_address    VARCHAR(45)      NULL,                        -- supports IPv4 and IPv6
    user_agent    VARCHAR(500)     NULL,
    status        ENUM('success','failed','blocked') NOT NULL,
    fail_reason   VARCHAR(255)     NULL,                        -- e.g. 'wrong_password', 'user_not_found'
    created_at    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_login_log_user_id   (user_id),
    KEY idx_login_log_email     (email),
    KEY idx_login_log_created   (created_at),

    CONSTRAINT fk_login_log_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
--  RESUMES
--  Stores each resume optimization job
-- ============================================================
CREATE TABLE IF NOT EXISTS resumes (
    id                  INT UNSIGNED        NOT NULL AUTO_INCREMENT,
    user_id             INT UNSIGNED        NULL,               -- NULL = guest (free, no account)
    original_filename   VARCHAR(255)        NULL,               -- uploaded file name
    original_text       LONGTEXT            NOT NULL,           -- extracted plain text from resume
    job_title           VARCHAR(255)        NULL,               -- parsed from job description
    job_description     LONGTEXT            NOT NULL,           -- full job description provided by user
    ats_score           TINYINT UNSIGNED    NULL,               -- 0–100, NULL until processed
    missing_keywords    JSON                NULL,               -- ["keyword1", "keyword2", ...]
    improvements        JSON                NULL,               -- ["suggestion1", "suggestion2", ...]
    optimized_text      LONGTEXT            NULL,               -- AI rewritten resume text
    file_format         ENUM('pdf','docx','txt') NULL,          -- original upload format
    status              ENUM('pending','processing','completed','failed') NOT NULL DEFAULT 'pending',
    error_message       VARCHAR(500)        NULL,               -- populated if status = failed
    celery_task_id      VARCHAR(255)        NULL,               -- Celery async task ID for polling
    created_at          DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_resumes_user_id     (user_id),
    KEY idx_resumes_status      (status),
    KEY idx_resumes_created     (created_at),

    CONSTRAINT fk_resumes_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
--  GUEST USAGE TRACKING
--  Server-side tracking of free uses per guest session
--  Works alongside the localStorage counter on the frontend
--  Prevents users bypassing the limit by clearing localStorage
-- ============================================================
CREATE TABLE IF NOT EXISTS guest_usage (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    session_id      VARCHAR(64)     NOT NULL,                   -- UUID generated on first visit
    ip_address      VARCHAR(45)     NULL,
    use_count       TINYINT UNSIGNED NOT NULL DEFAULT 0,        -- max 5
    first_seen_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_guest_session (session_id),
    KEY idx_guest_ip (ip_address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
--  SAMPLE DATA (for development only — remove in production)
-- ============================================================

-- Test user (password = "password123" hashed with bcrypt)
INSERT IGNORE INTO users (name, email, password_hash, is_active, is_verified, plan)
VALUES (
    'Test User',
    'shilpa.sathyanarayana5@gmail.com',
    '$2y$10$9gfDMG9HrHMHWyiMtLQWu.m5UAEXh1JxLusQDPshZOPjymT/4Yf.m',
    1,
    1,
    'free'
);
