import sqlite3
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def analyze_ab_test():
    n_a, clicks_a = 2574, 350
    n_b, clicks_b = 2855, 375

    if n_a <= 0 or n_b <= 0:
        raise ValueError("Размер выборки должен быть положительным")

    ctr_a = clicks_a / n_a
    ctr_b = clicks_b / n_b
    diff = ctr_b - ctr_a

    p_pool = (clicks_a + clicks_b) / (n_a + n_b)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    z_stat = diff / se
    p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))

    se_unpooled = np.sqrt(ctr_a * (1 - ctr_a) / n_a + ctr_b * (1 - ctr_b) / n_b)
    ci_low = diff - 1.96 * se_unpooled
    ci_high = diff + 1.96 * se_unpooled

    print(f"CTR A: {ctr_a:.2%}, CTR B: {ctr_b:.2%}, p-value: {p_value:.4f}")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(['Вариант А', 'Вариант Б'], [ctr_a * 100, ctr_b * 100], color=['#2b5c8f', '#e30611'], width=0.45)
    ax.errorbar(['Вариант А', 'Вариант Б'], [ctr_a * 100, ctr_b * 100],
                yerr=[1.96 * np.sqrt(ctr_a*(1-ctr_a)/n_a) * 100, 1.96 * np.sqrt(ctr_b*(1-ctr_b)/n_b) * 100],
                fmt='none', ecolor='black', capsize=6, linewidth=1.5)
    ax.set_ylabel('CTR (%)')
    ax.set_title('A/B Test CTR Comparison')
    ax.set_ylim(0, 18)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig('ab_test_result.png', dpi=150)
    plt.close()

def create_demo_db(db_path='mts_transact.db'):
    np.random.seed(42)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS transact;")
    cur.execute("""
        CREATE TABLE transact (
            id_client INTEGER,
            tran_time TEXT,
            id_tran   INTEGER PRIMARY KEY,
            sum_tran  REAL
        );
    """)

    base_date = datetime(2026, 11, 17, 12, 0, 0)
    start_date = datetime(2021, 1, 1)
    total_days = (base_date - start_date).days

    rows = []
    client_ids = np.arange(1001, 1151)
    weights = np.random.pareto(1.5, size=len(client_ids)) + 0.2
    weights /= weights.sum()

    for id_tran in range(1, 3001):
        cid = int(np.random.choice(client_ids, p=weights))
        rand_days = int(np.random.randint(0, total_days + 1))
        rand_secs = int(np.random.randint(0, 86400))
        dt = start_date + timedelta(days=rand_days, seconds=rand_secs)
        amount = round(float(np.random.lognormal(mean=7.2, sigma=0.8)), 2)
        rows.append((cid, dt.strftime('%Y-%m-%d %H:%M:%S'), id_tran, amount))

    cur.executemany("INSERT INTO transact VALUES (?, ?, ?, ?);", rows)
    conn.commit()
    return conn

def run_sql_tasks(conn):
    query_30d = """
    SELECT
        id_client,
        COUNT(DISTINCT id_tran) AS tran_count_30d,
        ROUND(SUM(sum_tran), 2) AS total_spent_30d
    FROM transact
    WHERE tran_time >= DATETIME('2026-11-17 23:59:59', '-30 days')
      AND sum_tran > 0
      AND id_client IS NOT NULL
    GROUP BY id_client
    ORDER BY total_spent_30d DESC;
    """
    df_30d = pd.read_sql_query(query_30d, conn)

    query_top100_monthly = """
    WITH top_clients AS (
        SELECT
            id_client,
            SUM(sum_tran) AS lifetime_spent
        FROM transact
        WHERE sum_tran > 0
          AND id_client IS NOT NULL
        GROUP BY id_client
        ORDER BY lifetime_spent DESC
        LIMIT 100
    )
    SELECT
        t.id_client,
        STRFTIME('%Y-%m', t.tran_time) AS tran_month,
        COUNT(DISTINCT t.id_tran) AS monthly_tran_cnt,
        ROUND(SUM(t.sum_tran), 2) AS monthly_spent
    FROM transact t
    INNER JOIN top_clients tc ON t.id_client = tc.id_client
    WHERE t.sum_tran > 0
    GROUP BY t.id_client, STRFTIME('%Y-%m', t.tran_time)
    ORDER BY tc.lifetime_spent DESC, t.id_client, tran_month;
    """
    df_top100 = pd.read_sql_query(query_top100_monthly, conn)

    monthly_agg = df_top100.groupby('tran_month')['monthly_spent'].sum().reset_index()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(monthly_agg['tran_month'], monthly_agg['monthly_spent'] / 1e6, color='#e30611', linewidth=1.8)
    ax.set_title('Top 100 Clients Monthly Spend')
    ax.set_ylabel('Million RUB')
    ax.set_xlabel('Month')
    ticks = monthly_agg['tran_month'][::6]
    ax.set_xticks(ticks)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig('top100_monthly_spend.png', dpi=150)
    plt.close()

if __name__ == '__main__':
    analyze_ab_test()
    connection = create_demo_db()
    run_sql_tasks(connection)
    connection.close()
