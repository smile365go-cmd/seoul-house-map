"""SQLite 테이블 생성, 저장, 집계, 조회."""
import sqlite3

import pandas as pd

from config import DB_PATH, PYEONG_M2

SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    gu            TEXT NOT NULL,      -- 자치구명
    gu_code       TEXT,               -- 자치구 코드 (5자리)
    dong          TEXT,               -- 법정동
    jibun         TEXT,               -- 지번 (본번-부번)
    building_type TEXT,               -- 아파트 / 연립다세대 / 오피스텔 / 단독다가구
    building_name TEXT,               -- 건물(단지)명
    deal_date     TEXT NOT NULL,      -- 계약일 YYYY-MM-DD
    price_10k     INTEGER NOT NULL,   -- 거래금액 (만원)
    area_m2       REAL,               -- 건물면적 (㎡)
    floor         INTEGER,            -- 층
    build_year    INTEGER,            -- 건축년도
    cancelled     INTEGER DEFAULT 0,  -- 해제(취소)된 거래면 1
    UNIQUE (gu_code, dong, jibun, building_name, deal_date, price_10k, area_m2, floor)
);
CREATE INDEX IF NOT EXISTS idx_deals_gu_date ON deals (gu, deal_date);

CREATE TABLE IF NOT EXISTS gu_monthly (
    gu                        TEXT NOT NULL,
    ym                        TEXT NOT NULL,   -- YYYY-MM
    building_type             TEXT NOT NULL,
    deal_count                INTEGER,
    avg_price_10k             INTEGER,         -- 평균 거래금액 (만원)
    avg_price_per_pyeong_10k  INTEGER,         -- 평당 평균가 (만원)
    PRIMARY KEY (gu, ym, building_type)
);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def insert_deals(conn, rows):
    """rows: dict 목록. 이미 있는 거래는 다시 넣지 않는다. 바뀐 건수 반환.

    API는 해제(취소)된 거래를 '원래 거래' 한 줄 + '해제일이 적힌' 한 줄로 두 번 준다.
    그래서 같은 거래가 다시 오면, 해제 표시만 반영한다.
    """
    before = conn.total_changes
    conn.executemany(
        """INSERT INTO deals
           (gu, gu_code, dong, jibun, building_type, building_name, deal_date,
            price_10k, area_m2, floor, build_year, cancelled)
           VALUES (:gu, :gu_code, :dong, :jibun, :building_type, :building_name, :deal_date,
                   :price_10k, :area_m2, :floor, :build_year, :cancelled)
           ON CONFLICT (gu_code, dong, jibun, building_name, deal_date, price_10k, area_m2, floor)
           DO UPDATE SET cancelled = 1 WHERE excluded.cancelled = 1 AND cancelled = 0""",
        rows,
    )
    conn.commit()
    return conn.total_changes - before


def rebuild_gu_monthly(conn):
    """deals 테이블에서 구 × 월 × 용도별 평균을 다시 계산한다. 해제된 거래는 뺀다."""
    conn.execute("DELETE FROM gu_monthly")
    conn.execute(
        f"""INSERT INTO gu_monthly
            SELECT gu,
                   substr(deal_date, 1, 7)                          AS ym,
                   building_type,
                   COUNT(*)                                         AS deal_count,
                   CAST(ROUND(AVG(price_10k)) AS INTEGER)           AS avg_price_10k,
                   CAST(ROUND(AVG(price_10k / (area_m2 / {PYEONG_M2}))) AS INTEGER)
                                                                    AS avg_price_per_pyeong_10k
            FROM deals
            WHERE cancelled = 0 AND area_m2 > 0
            GROUP BY gu, ym, building_type"""
    )
    conn.commit()


def query(sql, params=()):
    conn = connect()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()
