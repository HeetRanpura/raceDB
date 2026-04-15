-- RaceDB Schema
-- Run this first to set up the database

CREATE DATABASE IF NOT EXISTS racedb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE racedb;

-- Accounts: subject of all concurrent transactions
CREATE TABLE IF NOT EXISTS accounts (
    account_id  INT           PRIMARY KEY AUTO_INCREMENT,
    owner       VARCHAR(100)  NOT NULL,
    balance     DECIMAL(15,2) NOT NULL DEFAULT 1000.00,
    version     INT           NOT NULL DEFAULT 0,
    created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ;

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
