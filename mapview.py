"""지도 그리기. 앱(app.py)과 HTML 지도 파일 만들기에서 같이 쓴다.

직접 실행하면 폴더에 '서울집값지도.html'을 만든다:
    python mapview.py
"""
import json

import branca.colormap as cm
import folium
import pandas as pd

import db
from config import BASE_DIR, GEOJSON_PATH, VWORLD_API_KEY

SEOUL_CENTER = [37.5665, 126.9780]
SEOUL_BOUNDS = [[37.41, 126.73], [37.72, 127.27]]  # 서울 바깥으로 못 나가게
SEOUL_VIEW = [[37.43, 126.76], [37.70, 127.19]]    # 처음 화면: 서울 25개 구가 꽉 차게
HTML_PATH = BASE_DIR / "서울집값지도.html"


def load_geojson():
    return json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))


def load_months():
    return db.query("SELECT DISTINCT ym FROM gu_monthly ORDER BY ym")["ym"].tolist()


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


def won(v_10k):
    """만원 → '12억 3,400만' 형식."""
    if v_10k is None or pd.isna(v_10k):
        return "-"
    v = int(v_10k)
    eok, man = divmod(v, 10000)
    if eok and man:
        return f"{eok}억 {man:,}만"
    return f"{eok}억" if eok else f"{man:,}만"


def build_map(geo, summary):
    m = folium.Map(
        location=SEOUL_CENTER,
        zoom_start=11,
        min_zoom=10,
        max_zoom=16,
        max_bounds=True,
        min_lat=SEOUL_BOUNDS[0][0], max_lat=SEOUL_BOUNDS[1][0],
        min_lon=SEOUL_BOUNDS[0][1], max_lon=SEOUL_BOUNDS[1][1],
        zoom_snap=0.25,  # 0.25 단위로 확대해 서울이 화면에 꽉 차게
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
    m.fit_bounds(SEOUL_VIEW)
    return m


def export_html(building_type="아파트", months=12):
    """폴더에서 바로 여는 지도 파일을 만든다. 만든 경로를 반환 (데이터가 없으면 None)."""
    all_months = load_months()
    if not all_months or not GEOJSON_PATH.exists():
        return None
    start_ym, end_ym = all_months[max(0, len(all_months) - months)], all_months[-1]
    m = build_map(load_geojson(), gu_summary(building_type, start_ym, end_ym))
    title = f"서울시 {building_type} 평당가 지도 · {start_ym} ~ {end_ym} 계약 · 구에 마우스를 올려 보세요"
    m.get_root().header.add_child(folium.Element("<title>서울시 집값 지도</title>"))
    m.get_root().html.add_child(folium.Element(
        '<div style="position:fixed;bottom:12px;left:12px;z-index:9999;background:white;'
        'padding:8px 12px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.3);'
        f'font:14px sans-serif">{title}</div>'
    ))
    m.save(str(HTML_PATH))
    return HTML_PATH


if __name__ == "__main__":
    path = export_html()
    print(f"지도 파일 저장: {path}" if path else "데이터가 없습니다. 먼저 python collect.py 를 실행하세요.")
