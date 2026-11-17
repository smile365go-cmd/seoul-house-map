"""서울시 집값 지도 — 실행: streamlit run app.py (또는 지도열기.bat 더블클릭)"""
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import collect
import db
import mapview
from config import DB_PATH, GEOJSON_PATH, SEOUL_API_KEY
from mapview import build_map, won

st.set_page_config(page_title="서울시 집값 지도", page_icon="🏠", layout="wide")


# ---------------------------------------------------------------- 데이터
load_geojson = st.cache_data(mapview.load_geojson)
load_months = st.cache_data(mapview.load_months)
gu_summary = st.cache_data(mapview.gu_summary)


@st.cache_data
def load_building_types():
    return db.query(
        "SELECT building_type, SUM(deal_count) AS n FROM gu_monthly GROUP BY building_type ORDER BY n DESC"
    )["building_type"].tolist()


@st.cache_data
def gu_trend(gu, building_type):
    return db.query(
        "SELECT ym AS 월, avg_price_per_pyeong_10k AS 평당가, deal_count AS 거래건수 "
        "FROM gu_monthly WHERE gu = ? AND building_type = ? ORDER BY ym",
        (gu, building_type),
    )


@st.cache_data
def recent_deals(gu, building_type, start_ym):
    return db.query(
        """SELECT deal_date AS 계약일, dong AS 법정동, building_name AS 건물명,
                  price_10k AS "거래가(만원)", area_m2 AS "면적(㎡)", floor AS 층, build_year AS 건축년도
           FROM deals
           WHERE gu = ? AND building_type = ? AND cancelled = 0 AND deal_date >= ?
           ORDER BY deal_date DESC LIMIT 200""",
        (gu, building_type, start_ym + "-01"),
    )


# ---------------------------------------------------------------- 화면
st.title("서울시 집값 지도")

if not SEOUL_API_KEY:
    st.error("`.env` 파일에 `SEOUL_API_KEY`가 없습니다. README의 'API 키 넣기'를 따라 주세요.")
    st.stop()

with st.sidebar:
    st.header("조건")
    if st.button("데이터 새로 받기 (올해)", help="서울 열린데이터광장에서 올해 거래를 다시 받습니다. 몇 분 걸립니다."):
        with st.spinner("받는 중..."):
            if not GEOJSON_PATH.exists():
                collect.download_geojson()
            collect.run([pd.Timestamp.today().year])
        st.cache_data.clear()
        st.success("완료")

if not DB_PATH.exists() or not load_months():
    st.info("아직 데이터가 없습니다. 터미널에서 `python collect.py`를 먼저 실행하거나, 왼쪽 '데이터 새로 받기'를 누르세요.")
    st.stop()
if not GEOJSON_PATH.exists():
    collect.download_geojson()

months = load_months()
with st.sidebar:
    types = load_building_types()
    building_type = st.selectbox("건물 용도", types, index=types.index("아파트") if "아파트" in types else 0)
    period = st.radio("기간", [3, 6, 12], index=2, format_func=lambda n: f"최근 {n}개월", horizontal=True)
    end_ym = months[-1]
    start_ym = months[max(0, len(months) - period)]
    st.caption(f"{start_ym} ~ {end_ym} 계약 기준")
    st.caption("실거래는 계약 후 30일 안에 신고되므로 최근 달은 아직 집계 중입니다.")

summary = gu_summary(building_type, start_ym, end_ym)

col_map, col_rank = st.columns([3, 2])
with col_map:
    st_folium(build_map(load_geojson(), summary), height=620, use_container_width=True, returned_objects=[])
with col_rank:
    st.subheader("구별 평당가 순위")
    table = summary.assign(
        순위=range(1, len(summary) + 1),
        평당가=summary["평당가"].map(won),
        평균거래가=summary["평균거래가"].map(won),
    )[["순위", "gu", "평당가", "평균거래가", "거래건수"]].rename(columns={"gu": "자치구"})
    st.dataframe(table, hide_index=True, width="stretch", height=620)

st.divider()
st.subheader("구 상세")
gu = st.selectbox("자치구 선택", summary["gu"].tolist() or sorted(f["properties"]["gu"] for f in load_geojson()["features"]))
trend = gu_trend(gu, building_type)
c1, c2 = st.columns(2)
with c1:
    st.markdown(f"**{gu} 월별 평당가 (만원)**")
    st.line_chart(trend.set_index("월")["평당가"])
with c2:
    st.markdown(f"**{gu} 월별 거래 건수**")
    st.bar_chart(trend.set_index("월")["거래건수"])
st.markdown(f"**{gu} 최근 거래 (최대 200건)**")
st.dataframe(recent_deals(gu, building_type, start_ym), hide_index=True, width="stretch")

st.caption("데이터: 서울 열린데이터광장 「서울시 부동산 실거래가 정보」 · 지도: 국토교통부 브이월드")
