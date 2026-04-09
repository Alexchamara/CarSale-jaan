-- Daily Expenses module schema and report queries

CREATE TABLE IF NOT EXISTS expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  expense_date DATE NOT NULL,
  description TEXT NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  payment_method VARCHAR(20) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Today expenses (default view)
SELECT
  expense_date,
  description,
  amount,
  payment_method
FROM expenses
WHERE expense_date = CURRENT_DATE
ORDER BY id DESC;

SELECT COALESCE(SUM(amount), 0) AS today_total
FROM expenses
WHERE expense_date = CURRENT_DATE;

-- Last 7 days report (detail rows)
SELECT
  expense_date,
  description,
  amount,
  payment_method
FROM expenses
WHERE expense_date >= DATE('now', '-6 days')
  AND expense_date <= DATE('now')
ORDER BY expense_date DESC, id DESC;

SELECT COALESCE(SUM(amount), 0) AS last_7_days_total
FROM expenses
WHERE expense_date >= DATE('now', '-6 days')
  AND expense_date <= DATE('now');

-- Weekly report (grouped by ISO-like week key)
SELECT
  strftime('%Y-W%W', expense_date) AS week_key,
  MIN(expense_date) AS week_start,
  MAX(expense_date) AS week_end,
  COUNT(*) AS entry_count,
  COALESCE(SUM(amount), 0) AS weekly_total
FROM expenses
GROUP BY strftime('%Y-W%W', expense_date)
ORDER BY week_key DESC;

SELECT COALESCE(SUM(amount), 0) AS weekly_grand_total FROM (
  SELECT SUM(amount) AS amount
  FROM expenses
  GROUP BY strftime('%Y-W%W', expense_date)
);

-- Monthly report (grouped by month)
SELECT
  strftime('%Y-%m', expense_date) AS month_key,
  COUNT(*) AS entry_count,
  COALESCE(SUM(amount), 0) AS monthly_total
FROM expenses
GROUP BY strftime('%Y-%m', expense_date)
ORDER BY month_key DESC;

SELECT COALESCE(SUM(amount), 0) AS monthly_grand_total FROM (
  SELECT SUM(amount) AS amount
  FROM expenses
  GROUP BY strftime('%Y-%m', expense_date)
);
