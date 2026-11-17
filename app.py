"""서울시 집값 지도 — 실행: streamlit run app.py"""
import json

import branca.colormap as cm
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import collect
import db
from config import DB_PATH, GEOJSON_PATH, SEOUL_API_KEY, VWORLD_API_KEY

st.set_page_config(page_title="서울시 집값 지도", page_icon="🏠", layout="wide")

SEOUL_CENTER = [37.5665, 126.9780]
SEOUL_BOUNDS = [[37.41, 126.73], [37.72, 127.27]]  # 서울 바깥으로 못 나가게


# ---------------------------------------------------------------- 데이터
@st.cache_data
def load_geojson():
    return json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))


@st.cache_data
def load_building_types():
    return db.query(
        "SELECT building_type, SUM(deal_count) AS n FROM gu_monthly GROUP BY building_type ORDER BY n DESC"
    )["building_type"].tolist()


@st.cache_data
def load_months():
    return db.query("SELECT DISTINCT ym FROM gu_monthly ORDER BY ym")["ym"].tolist()


@st.cache_data
def gu_summary(building_type, start_ym, end_ym):
    """구별: 거래 건수 가중 평균으로 기간 전체 평당가·평균가를 계산."""
    return db.query(
        """SELECT gu,
                  SUM(deal_count) AS 거래건수,
                  CAST(ROUND(SUM(avg_price_per_pyeong_10k * deal_count) * 1.0 / SUM(deal_count)) AS INTEGER) AS 평당가,
                  CAST(ROUND(SUM(avg_price_10k * deal_count) * 1.0 / SUM(deal_count)) AS INTEGER) AS 평균거래가
           FROM gu_monthly
           WHERE building_type = ? AND ym BETWEEN ? AND ?
           GROUP BY gu
           ORDER BY 평당가 DESC""",
        (building_type, start_ym, end_ym),
    )


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


def won(v_10k):
    """만원 → '12억 3,400만' 형식."""
    if pd.isna(v_10k):
        return "-"
    v = int(v_10k)
    eok, man = divmod(v, 10000)
    if eok and man:
        return f"{eok}억 {man:,}만"
    return f"{eok}억" if eok else f"{man:,}만"


# ---------------------------------------------------------------- 지도
def build_map(geo, summary):
    m = folium.Map(
        location=SEOUL_CENTER,
        zoom_start=11,
        min_zoom=10,
        max_zoom=16,
        max_bounds=True,
        min_lat=SEOUL_BOUNDS[0][0], max_lat=SEOUL_BOUNDS[1][0],
        min_lon=SEOUL_BOUNDS[0][1], max_lon=SEOUL_BOUNDS[1][1],
        tiles=None,
    )
    if VWORLD_API_KEY:
        folium.TileLayer(
            tiles=f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/white/{{z}}/{{y}}/{{x}}.png",
            attr="© 국토교통부 브이월드",
            name="브이월드",
        ).add_to(m)
    else:
        folium.TileLayer("cartodbpositron", name="기본 지도").add_to(m)

    by_gu = summary.set_index("gu").to_dict("index")
    values = summary["평당가"].dropna()
    cmap = cm.LinearColormap(
        ["#fff5eb", "#fdae6b", "#e6550d", "#7f2704"],
        vmin=values.min() if len(values) else 0,
        vmax=values.max() if len(values) else 1,
        caption="평당 평균가 (만원)",
    )

    features = []
    for f in geo["features"]:
        gu = f["properties"]["gu"]
        info = by_gu.get(gu, {})
        props = {
            "gu": gu,
            "price": info.get("평당가"),
            "price_txt": won(info.get("평당가")) + " / 평" if info else "거래 없음",
            "avg_txt": won(info.get("평균거래가")) if info else "-",
            "count_txt": f"{int(info['거래건수']):,}건" if info else "0건",
        }
        features.append({**f, "properties": props})

    folium.GeoJson(
        {"type": "FeatureCollection", "features": features},
        style_function=lambda f: {
            "fillColor": cmap(f["properties"]["price"]) if f["properties"]["price"] else "#dddddd",
            "color": "#555555",
            "weight": 1,
            "fillOpacity": 0.72,
        },
        highlight_function=lambda f: {"weight": 3, "color": "#000000", "fillOpacity": 0.85},
        tooltip=folium.GeoJsonTooltip(
            fields=["gu", "price_txt", "avg_txt", "count_txt"],
            aliases=["자치구", "평당가", "평균 거래가", "거래 건수"],
            sticky=True,
        ),
    ).add_to(m)
    cmap.add_to(m)
    m.fit_bounds(SEOUL_BOUNDS)
    return m


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
