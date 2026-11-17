"""공공 API에서 데이터를 받아 SQLite에 저장한다.

사용법:
    python collect.py                 # 올해 + 작년 실거래가 수집
    python collect.py --years 2024 2025 2026
    python collect.py --geo-only      # 구 경계 지도만 다시 받기
"""
import argparse
import json
import sys
import time
from datetime import date

import requests

import db
from config import GEOJSON_PATH, SEOUL_API_KEY, VWORLD_API_KEY

SEOUL_URL = "http://openapi.seoul.go.kr:8088/{key}/json/tbLnOpendataRtmsV/{start}/{end}/{year}"
PAGE_SIZE = 1000  # 서울 열린데이터광장 1회 최대 1,000건
VWORLD_URL = "https://api.vworld.kr/req/data"
FALLBACK_GEOJSON_URL = (
    "https://raw.githubusercontent.com/southkorea/seoul-maps/master/"
    "juso/2015/json/seoul_municipalities_geo_simple.json"
)


# ---------------------------------------------------------------- 실거래가
def fetch_page(year, start):
    url = SEOUL_URL.format(key=SEOUL_API_KEY, start=start, end=start + PAGE_SIZE - 1, year=year)
    for attempt in range(3):
        try:
            res = requests.get(url, timeout=60)
            res.raise_for_status()
            data = res.json()
            break
        except (requests.RequestException, ValueError) as e:
            if attempt == 2:
                raise
            print(f"  재시도 ({e})")
            time.sleep(3)

    body = data.get("tbLnOpendataRtmsV")
    if body is None:  # 키 오류, 데이터 없음 등
        result = data.get("RESULT", {})
        if result.get("CODE") == "INFO-200":
            return 0, []
        raise RuntimeError(f"API 오류: {result.get('CODE')} {result.get('MESSAGE')}")
    return body["list_total_count"], body.get("row", [])


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def clean(row):
    """API 한 행 → DB 한 행. 필수값이 없으면 None."""
    day = row.get("CTRT_DAY", "")
    price = to_int(str(row.get("THING_AMT", "")).replace(",", ""))
    if len(day) != 8 or not price or not row.get("CGG_NM"):
        return None
    return {
        "gu": row["CGG_NM"],
        "gu_code": row.get("CGG_CD"),
        "dong": row.get("STDG_NM"),
        "jibun": f"{row.get('MNO', '')}-{row.get('SNO', '')}",
        "building_type": row.get("BLDG_USG") or "기타",
        "building_name": row.get("BLDG_NM") or "",
        "deal_date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
        "price_10k": price,
        "area_m2": row.get("ARCH_AREA"),
        "floor": to_int(row.get("FLR")),
        "build_year": to_int(row.get("ARCH_YR")),
        "cancelled": 1 if (row.get("RTRCN_DAY") or "").strip() else 0,
    }


def collect_year(conn, year):
    total, rows = fetch_page(year, 1)
    print(f"[{year}년] 총 {total:,}건")
    added, start = 0, 1
    while rows:
        cleaned = [r for r in (clean(x) for x in rows) if r]
        added += db.insert_deals(conn, cleaned)
        done = min(start + PAGE_SIZE - 1, total)
        print(f"\r  {done:,} / {total:,} 받음 (새로 저장 {added:,}건)", end="", flush=True)
        start += PAGE_SIZE
        if start > total:
            break
        time.sleep(0.2)
        _, rows = fetch_page(year, start)
    print()
    return added


# ---------------------------------------------------------------- 구 경계
def download_geojson():
    """브이월드에서 서울 25개 구 경계를 받는다. 실패하면 GitHub 공개 파일을 쓴다."""
    if VWORLD_API_KEY:
        try:
            res = requests.get(
                VWORLD_URL,
                params={
                    "service": "data",
                    "request": "GetFeature",
                    "data": "LT_C_ADSIGG_INFO",  # 시군구 경계
                    "key": VWORLD_API_KEY,
                    "attrFilter": "sig_cd:like:11",  # 11 = 서울
                    "size": 1000,
                    "format": "json",
                    "geometry": "true",
                    "crs": "EPSG:4326",
                    "domain": "localhost",
                },
                timeout=60,
            )
            fc = res.json()["response"]["result"]["featureCollection"]
            features = [
                {
                    "type": "Feature",
                    "properties": {"gu": f["properties"]["sig_kor_nm"]},
                    "geometry": f["geometry"],
                }
                for f in fc["features"]
            ]
            if len(features) == 25:
                save_geojson(features, "브이월드")
                return
            print(f"브이월드 경계가 {len(features)}개라 예비 파일을 씁니다.")
        except Exception as e:  # noqa: BLE001
            print(f"브이월드 경계 받기 실패 ({e}). 예비 파일을 씁니다.")

    data = requests.get(FALLBACK_GEOJSON_URL, timeout=60).json()
    features = [
        {"type": "Feature", "properties": {"gu": f["properties"]["name"]}, "geometry": f["geometry"]}
        for f in data["features"]
    ]
    save_geojson(features, "GitHub seoul-maps")


def save_geojson(features, source):
    GEOJSON_PATH.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"구 경계 {len(features)}개 저장 ({source}) → {GEOJSON_PATH.name}")


# ---------------------------------------------------------------- 실행
def run(years):
    if not SEOUL_API_KEY:
        sys.exit("SEOUL_API_KEY가 없습니다. .env 파일에 서울 열린데이터광장 키를 넣어 주세요.")
    conn = db.connect()
    try:
        for y in years:
            collect_year(conn, y)
        db.rebuild_gu_monthly(conn)
        n = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        print(f"완료: DB에 거래 {n:,}건, 구별 월평균 재계산")
    finally:
        conn.close()


def main():
    this_year = date.today().year
    p = argparse.ArgumentParser(description="서울 실거래가 수집")
    p.add_argument("--years", type=int, nargs="+", default=[this_year - 1, this_year])
    p.add_argument("--geo-only", action="store_true", help="구 경계 지도만 받기")
    args = p.parse_args()

    if args.geo_only or not GEOJSON_PATH.exists():
        download_geojson()
    if not args.geo_only:
        run(args.years)


if __name__ == "__main__":
    main()
