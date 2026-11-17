SELECT
    id_client,
    COUNT(DISTINCT id_tran) AS tran_count_30d,
    ROUND(SUM(sum_tran)::numeric, 2) AS total_spent_30d
FROM transact
WHERE tran_time >= CURRENT_DATE - INTERVAL '30 days'
  AND tran_time < CURRENT_DATE + INTERVAL '1 day'
  AND sum_tran > 0
  AND id_client IS NOT NULL
GROUP BY id_client
ORDER BY total_spent_30d DESC;

WITH client_dedup AS (
    SELECT DISTINCT
        id_tran,
        id_client,
        tran_time,
        sum_tran
    FROM transact
    WHERE sum_tran > 0
      AND id_client IS NOT NULL
),
top_100_clients AS (
    SELECT
        id_client,
        SUM(sum_tran) AS total_lifetime_spent
    FROM client_dedup
    GROUP BY id_client
    ORDER BY total_lifetime_spent DESC
    LIMIT 100
)
SELECT
    c.id_client,
    DATE_TRUNC('month', c.tran_time)::date AS tran_month,
    COUNT(c.id_tran) AS monthly_tran_count,
    ROUND(SUM(c.sum_tran)::numeric, 2) AS monthly_spent
FROM client_dedup c
INNER JOIN top_100_clients t ON c.id_client = t.id_client
GROUP BY c.id_client, DATE_TRUNC('month', c.tran_time)
ORDER BY t.total_lifetime_spent DESC, c.id_client, tran_month;

WITH valid_transact AS (
    SELECT DISTINCT
        id_client,
        id_tran,
        DATE_TRUNC('month', tran_time)::date AS activity_month
    FROM transact
    WHERE sum_tran > 0
      AND id_client IS NOT NULL
      AND tran_time >= '2021-01-01'
),
first_purchase AS (
    SELECT
        id_client,
        MIN(activity_month) AS cohort_month
    FROM valid_transact
    GROUP BY id_client
),
cohort_activity AS (
    SELECT
        fp.cohort_month,
        (EXTRACT(YEAR FROM AGE(vt.activity_month, fp.cohort_month)) * 12 +
         EXTRACT(MONTH FROM AGE(vt.activity_month, fp.cohort_month)))::int AS month_number,
        COUNT(DISTINCT vt.id_client) AS active_clients
    FROM first_purchase fp
    INNER JOIN valid_transact vt ON fp.id_client = vt.id_client
    GROUP BY fp.cohort_month, month_number
),
cohort_sizes AS (
    SELECT
        cohort_month,
        active_clients AS cohort_size
    FROM cohort_activity
    WHERE month_number = 0
)
SELECT
    ca.cohort_month,
    cs.cohort_size,
    ca.month_number,
    ca.active_clients,
    ROUND(100.0 * ca.active_clients / NULLIF(cs.cohort_size, 0), 2) AS retention_rate_pct
FROM cohort_activity ca
INNER JOIN cohort_sizes cs ON ca.cohort_month = cs.cohort_month
WHERE ca.month_number BETWEEN 0 AND 12
ORDER BY ca.cohort_month, ca.month_number;
