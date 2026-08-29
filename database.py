import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_type="sqlite", db_url=None, sqlite_path="backtest_history.db"):
        self.db_type = os.environ.get("DB_TYPE", db_type)
        self.db_url = os.environ.get("DATABASE_URL", db_url)
        self.sqlite_path = sqlite_path
        self.init_db()

    def get_connection(self):
        if self.db_type == "postgres" and self.db_url:
            return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
        return sqlite3.connect(self.sqlite_path)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.db_type == "sqlite":
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    job_id TEXT PRIMARY KEY,
                    ea_name TEXT,
                    symbol TEXT,
                    year TEXT,
                    initial_balance REAL,
                    final_balance REAL,
                    net_profit REAL,
                    profit_factor REAL,
                    win_rate REAL,
                    sortino_ratio REAL,
                    max_drawdown_pct REAL,
                    total_trades INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT, order_id TEXT, ea_name TEXT, symbol TEXT, arah TEXT,
                    harga_entry REAL, open_time TEXT, close_time TEXT, profit REAL,
                    lot REAL, balance REAL, comment TEXT,
                    FOREIGN KEY(job_id) REFERENCES backtest_runs(job_id)
                )
            ''')
        else: # PostgreSQL
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    job_id VARCHAR(64) PRIMARY KEY,
                    ea_name VARCHAR(128),
                    symbol VARCHAR(32),
                    year VARCHAR(16),
                    initial_balance NUMERIC,
                    final_balance NUMERIC,
                    net_profit NUMERIC,
                    profit_factor NUMERIC,
                    win_rate NUMERIC,
                    sortino_ratio NUMERIC,
                    max_drawdown_pct NUMERIC,
                    total_trades INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS trade_history (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(64) REFERENCES backtest_runs(job_id),
                    order_id VARCHAR(64), ea_name VARCHAR(128), symbol VARCHAR(32),
                    arah VARCHAR(8), harga_entry NUMERIC, open_time VARCHAR(64),
                    close_time VARCHAR(64), profit NUMERIC, lot NUMERIC,
                    balance NUMERIC, comment TEXT
                );
            ''')
        conn.commit()
        conn.close()

    def save_run(self, job_id, params, result):
        conn = self.get_connection()
        cursor = conn.cursor()
        q_mark = "%s" if self.db_type == "postgres" else "?"
        
        query_run = f'''
            INSERT INTO backtest_runs 
            (job_id, ea_name, symbol, year, initial_balance, final_balance, net_profit, profit_factor, win_rate, sortino_ratio, max_drawdown_pct, total_trades)
            VALUES ({','.join([q_mark]*12)})
        '''
        cursor.execute(query_run, (
            job_id, params.get("ea_name", "EA_MQL5"), params.get("symbol", "XAUUSD"),
            str(params.get("year", "2024")), result["initial_balance"], result["final_balance"],
            result["net_profit"], result["profit_factor"], result["win_rate"],
            result.get("sortino_ratio", 0.0), result.get("max_drawdown_pct", 0.0), result["total_trades"]
        ))

        query_trade = f'''
            INSERT INTO trade_history 
            (job_id, order_id, ea_name, symbol, arah, harga_entry, open_time, close_time, profit, lot, balance, comment)
            VALUES ({','.join([q_mark]*12)})
        '''
        for t in result.get("trades", []):
            cursor.execute(query_trade, (
                job_id, t["order_id"], t["ea_name"], t["symbol"], t["arah"], 
                t["harga_entry"], t["open_time"], t["close_time"], t["profit"], 
                t["lot"], t["balance"], t["comment"]
            ))
        conn.commit()
        conn.close()

    def get_history(self, limit=20):
        conn = self.get_connection()
        if self.db_type == "sqlite":
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            runs = cursor.execute("SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            conn.close()
            return [dict(r) for r in runs]
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT %s", (limit,))
            runs = cursor.fetchall()
            conn.close()
            return runs
