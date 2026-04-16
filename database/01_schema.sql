-- RaceDB Schema
-- Run this first to set up the database

CREATE DATABASE IF NOT EXISTS racedb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE racedb;

-- ══════════════════════════════════════════════════════════════════════
-- Banking Domain Tables
-- ══════════════════════════════════════════════════════════════════════

-- Users: customers of the banking system
CREATE TABLE IF NOT EXISTS users (
    user_id     INT           PRIMARY KEY AUTO_INCREMENT,
    first_name  VARCHAR(50)   NOT NULL,
    last_name   VARCHAR(50)   NOT NULL,
    email       VARCHAR(120)  NOT NULL UNIQUE,
    phone       VARCHAR(20),
    date_of_birth DATE,
    created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ;

-- Banks: parent financial institutions
CREATE TABLE IF NOT EXISTS banks (
    bank_id     INT           PRIMARY KEY AUTO_INCREMENT,
    bank_name   VARCHAR(100)  NOT NULL,
    swift_code  VARCHAR(11)   NOT NULL UNIQUE,
    headquarters VARCHAR(100),
    founded_year SMALLINT UNSIGNED,
    created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
) ;

-- Branches: physical locations belonging to a bank
CREATE TABLE IF NOT EXISTS branches (
    branch_id   INT           PRIMARY KEY AUTO_INCREMENT,
    bank_id     INT           NOT NULL,
    branch_name VARCHAR(100)  NOT NULL,
    city        VARCHAR(60)   NOT NULL,
    state       VARCHAR(60),
    ifsc_code   VARCHAR(11)   NOT NULL UNIQUE,
    created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_id) REFERENCES banks(bank_id) ON DELETE CASCADE
) ;

-- Accounts: subject of all concurrent transactions
CREATE TABLE IF NOT EXISTS accounts (
    account_id  INT           PRIMARY KEY AUTO_INCREMENT,
    user_id     INT,
    branch_id   INT,
    owner       VARCHAR(100)  NOT NULL,
    account_type ENUM('SAVINGS','CURRENT','SALARY','FIXED_DEPOSIT') NOT NULL DEFAULT 'SAVINGS',
    balance     DECIMAL(15,2) NOT NULL DEFAULT 1000.00,
    version     INT           NOT NULL DEFAULT 0,
    created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)   REFERENCES users(user_id)     ON DELETE SET NULL,
    FOREIGN KEY (branch_id) REFERENCES branches(branch_id) ON DELETE SET NULL
) ;

-- Cards: debit/credit cards linked to accounts
CREATE TABLE IF NOT EXISTS cards (
    card_id       INT           PRIMARY KEY AUTO_INCREMENT,
    account_id    INT           NOT NULL,
    card_number   VARCHAR(19)   NOT NULL UNIQUE,
    card_type     ENUM('DEBIT','CREDIT') NOT NULL DEFAULT 'DEBIT',
    expiry_date   DATE          NOT NULL,
    daily_limit   DECIMAL(12,2) NOT NULL DEFAULT 50000.00,
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
) ;

-- Loans: loan products issued to users against branches
CREATE TABLE IF NOT EXISTS loans (
    loan_id       INT           PRIMARY KEY AUTO_INCREMENT,
    user_id       INT           NOT NULL,
    branch_id     INT           NOT NULL,
    loan_type     ENUM('HOME','AUTO','PERSONAL','EDUCATION') NOT NULL,
    principal     DECIMAL(15,2) NOT NULL,
    interest_rate DECIMAL(5,2)  NOT NULL,
    tenure_months INT           NOT NULL,
    status        ENUM('ACTIVE','CLOSED','DEFAULTED') NOT NULL DEFAULT 'ACTIVE',
    disbursed_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)   REFERENCES users(user_id)     ON DELETE CASCADE,
    FOREIGN KEY (branch_id) REFERENCES branches(branch_id) ON DELETE CASCADE
) ;

-- ══════════════════════════════════════════════════════════════════════
-- Concurrency Engine Tables (existing)
-- ══════════════════════════════════════════════════════════════════════

-- Every individual query executed is recorded here
CREATE TABLE IF NOT EXISTS execution_log (
    log_id      INT           PRIMARY KEY AUTO_INCREMENT,
    run_id      VARCHAR(64),
    session_id  VARCHAR(64),
    txn_id      VARCHAR(64),
    query_text  TEXT,
    status      ENUM('SUCCESS','FAILED','DEADLOCK','ROLLBACK','TIMEOUT','COMMIT','WAITING','BLOCKED','ABORTED') NOT NULL DEFAULT 'SUCCESS',
    latency_ms  FLOAT,
    error_msg   TEXT,
    executed_at TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run_id (run_id),
    INDEX idx_txn_id (txn_id),
    INDEX idx_status (status)
) ;

-- Aggregate metrics per benchmark run
CREATE TABLE IF NOT EXISTS benchmark_results (
    run_id              INT           PRIMARY KEY AUTO_INCREMENT,
    total_transactions  INT           NOT NULL DEFAULT 0,
    successful          INT           NOT NULL DEFAULT 0,
    aborted             INT           NOT NULL DEFAULT 0,
    deadlocks           INT           NOT NULL DEFAULT 0,
    anomalies_detected  INT           NOT NULL DEFAULT 0,
    avg_latency_ms      FLOAT         NOT NULL DEFAULT 0,
    throughput_tps      FLOAT         NOT NULL DEFAULT 0,
    isolation_level     VARCHAR(50)   NOT NULL DEFAULT 'REPEATABLE READ',
    pattern             VARCHAR(50)   NOT NULL DEFAULT 'mixed',
    concurrency_level   INT           NOT NULL DEFAULT 5,
    timestamp           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
) ;

-- Individual anomaly instances per run
CREATE TABLE IF NOT EXISTS anomaly_log (
    anomaly_id  INT           PRIMARY KEY AUTO_INCREMENT,
    run_id      INT,
    type        ENUM('LOST_UPDATE','DIRTY_READ','NON_REPEATABLE_READ','PHANTOM_READ','DEADLOCK') NOT NULL,
    description TEXT,
    txn_ids     VARCHAR(256),
    detected_at TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES benchmark_results(run_id) ON DELETE CASCADE,
    INDEX idx_run_id (run_id)
) ;
