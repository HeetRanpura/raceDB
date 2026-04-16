-- RaceDB Seed Data
USE racedb;

-- ── Users ────────────────────────────────────────────────────────────
INSERT INTO users (first_name, last_name, email, phone, date_of_birth) VALUES
    ('Alice',   'Sharma',   'alice.sharma@mail.com',   '+91-9876543210', '1995-03-15'),
    ('Bob',     'Patel',    'bob.patel@mail.com',      '+91-9876543211', '1990-07-22'),
    ('Charlie', 'Mehta',    'charlie.mehta@mail.com',   '+91-9876543212', '1988-12-05'),
    ('Diana',   'Gupta',    'diana.gupta@mail.com',     '+91-9876543213', '1992-01-30'),
    ('Eve',     'Reddy',    'eve.reddy@mail.com',       '+91-9876543214', '1997-06-18'),
    ('Frank',   'Kumar',    'frank.kumar@mail.com',     '+91-9876543215', '1985-09-10'),
    ('Grace',   'Singh',    'grace.singh@mail.com',     '+91-9876543216', '1993-11-25'),
    ('Hank',    'Joshi',    'hank.joshi@mail.com',      '+91-9876543217', '1991-04-08'),
    ('Iris',    'Verma',    'iris.verma@mail.com',      '+91-9876543218', '1996-08-14'),
    ('Jack',    'Desai',    'jack.desai@mail.com',      '+91-9876543219', '1989-02-28');

-- ── Banks ────────────────────────────────────────────────────────────
INSERT INTO banks (bank_name, swift_code, headquarters, founded_year) VALUES
    ('National Trust Bank',  'NTBKINBB',  'Mumbai',    1960),
    ('Citizens Federal',     'CFEDUS33',  'New York',  1812),
    ('Pacific Commerce Bank','PCMBAU2S',  'Sydney',    1935);

-- ── Branches ─────────────────────────────────────────────────────────
INSERT INTO branches (bank_id, branch_name, city, state, ifsc_code) VALUES
    (1, 'NTB Andheri',         'Mumbai',     'Maharashtra', 'NTB0001001'),
    (1, 'NTB Connaught Place', 'New Delhi',  'Delhi',       'NTB0001002'),
    (2, 'CF Wall Street',      'New York',   'NY',          'CFED000101'),
    (2, 'CF Bay Area',         'San Francisco','CA',        'CFED000102'),
    (3, 'PCB CBD',             'Sydney',     'NSW',         'PCMB000201');

-- ── Accounts (linked to users + branches) ────────────────────────────
INSERT INTO accounts (user_id, branch_id, owner, account_type, balance, version) VALUES
    (1,  1, 'Alice',   'SAVINGS',       5000.00, 0),
    (2,  1, 'Bob',     'CURRENT',       3200.00, 0),
    (3,  2, 'Charlie', 'SAVINGS',       8750.00, 0),
    (4,  2, 'Diana',   'SALARY',        1200.00, 0),
    (5,  3, 'Eve',     'SAVINGS',      15000.00, 0),
    (6,  3, 'Frank',   'CURRENT',       4500.00, 0),
    (7,  4, 'Grace',   'SAVINGS',       2800.00, 0),
    (8,  4, 'Hank',    'FIXED_DEPOSIT', 9300.00, 0),
    (9,  5, 'Iris',    'SAVINGS',       6100.00, 0),
    (10, 5, 'Jack',    'CURRENT',       3750.00, 0);

-- ── Cards ────────────────────────────────────────────────────────────
INSERT INTO cards (account_id, card_number, card_type, expiry_date, daily_limit, is_active) VALUES
    (1,  '4111-1111-1111-1111', 'DEBIT',  '2028-12-31', 50000.00,  TRUE),
    (2,  '4222-2222-2222-2222', 'DEBIT',  '2027-06-30', 40000.00,  TRUE),
    (3,  '5333-3333-3333-3333', 'CREDIT', '2029-03-31', 100000.00, TRUE),
    (5,  '4555-5555-5555-5555', 'DEBIT',  '2028-09-30', 75000.00,  TRUE),
    (6,  '5666-6666-6666-6666', 'CREDIT', '2027-11-30', 200000.00, TRUE),
    (8,  '4888-8888-8888-8888', 'DEBIT',  '2029-01-31', 30000.00,  TRUE),
    (10, '5100-1000-1000-1000', 'CREDIT', '2028-07-31', 150000.00, TRUE);

-- ── Loans ────────────────────────────────────────────────────────────
INSERT INTO loans (user_id, branch_id, loan_type, principal, interest_rate, tenure_months, status) VALUES
    (1, 1, 'HOME',      2500000.00, 7.50, 240, 'ACTIVE'),
    (3, 2, 'AUTO',       800000.00, 9.25,  60, 'ACTIVE'),
    (4, 2, 'PERSONAL',   150000.00, 12.00, 36, 'ACTIVE'),
    (5, 3, 'EDUCATION', 1200000.00, 6.75,  84, 'ACTIVE'),
    (7, 4, 'HOME',      3500000.00, 7.25, 300, 'ACTIVE'),
    (9, 5, 'AUTO',       600000.00, 8.90,  48, 'CLOSED');
