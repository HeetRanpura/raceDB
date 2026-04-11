-- RaceDB Seed Data
USE racedb;

-- 10 sample accounts for transactions to operate on
INSERT INTO accounts (owner, balance, version) VALUES
    ('Alice',   5000.00, 0),
    ('Bob',     3200.00, 0),
    ('Charlie', 8750.00, 0),
    ('Diana',   1200.00, 0),
    ('Eve',    15000.00, 0),
    ('Frank',   4500.00, 0),
    ('Grace',   2800.00, 0),
    ('Hank',    9300.00, 0),
    ('Iris',    6100.00, 0),
    ('Jack',    3750.00, 0);
