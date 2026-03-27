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
--  User Profiles
--  Stores users job title,location and experience level- 
--  user can have multile job profiles.
-- ============================================================

CREATE TABLE user_profiles (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,

    job_title VARCHAR(150),
    experience_level ENUM('student','fresher','junior','intermediate','senior'),
    location VARCHAR(150),

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

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

CREATE TABLE IF NOT EXISTS subscriptions (
    id                      INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id                 INT UNSIGNED    NOT NULL,
    stripe_customer_id      VARCHAR(64)     NULL,
    stripe_subscription_id  VARCHAR(64)     NULL,
    stripe_price_id         VARCHAR(64)     NULL,
    plan    ENUM('free','pro_monthly','pro_yearly')                     NOT NULL DEFAULT 'free',
    status  ENUM('active','trialing','past_due','cancelled','inactive') NOT NULL DEFAULT 'inactive',
    is_pro                  TINYINT(1)      NOT NULL DEFAULT 0,
    current_period_start    DATETIME        NULL,
    current_period_end      DATETIME        NULL,
    cancel_at_period_end    TINYINT(1)      NOT NULL DEFAULT 0,
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE  KEY uq_subscriptions_user_id           (user_id),
    KEY         idx_subscriptions_customer_id      (stripe_customer_id),
    KEY         idx_subscriptions_subscription_id  (stripe_subscription_id),

    CONSTRAINT fk_subscriptions_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE ON UPDATE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- JOB Tracker
CREATE TABLE IF NOT EXISTS job_stages (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id     INT UNSIGNED NOT NULL,

    name        VARCHAR(100) NOT NULL,       -- e.g. Applied, Interview Scheduled
    position    INT UNSIGNED NOT NULL,       -- order in Kanban board

    is_default  TINYINT(1) DEFAULT 1,

    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_stage_user (user_id),

    CONSTRAINT fk_stage_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS job_applications (
    id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED NOT NULL,

    company         VARCHAR(255) NOT NULL,
    role            VARCHAR(255) NOT NULL,
    job_url         VARCHAR(500) NULL,

    stage_id        INT UNSIGNED NOT NULL,   -- current Kanban column
    description TEXT NULL,
    applied_at      DATETIME NULL,
    next_action     VARCHAR(255) NULL,
    next_action_due DATETIME NULL,

    notes           TEXT NULL,

    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    KEY idx_app_user (user_id),
    KEY idx_app_stage (stage_id),

    CONSTRAINT fk_app_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_app_stage
        FOREIGN KEY (stage_id) REFERENCES job_stages(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS interview_questions (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    job_application_id INT UNSIGNED NOT NULL,
    question TEXT NOT NULL,
    user_answer TEXT NULL,
    ai_feedback TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    CONSTRAINT fk_question_job_app
        FOREIGN KEY (job_application_id) REFERENCES job_applications(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;