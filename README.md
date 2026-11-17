# 서울시 집값 지도

서울 25개 자치구의 부동산 실거래가를 공공 API에서 받아 SQLite에 저장하고, 구별 평당 평균가를 색칠한 지도로 보여주는 로컬 웹앱입니다.

- 지도: 구에 마우스를 올리면 평당가, 평균 거래가, 거래 건수가 나옵니다
- 필터: 건물 용도(아파트, 연립다세대, 오피스텔, 단독다가구), 기간(최근 3/6/12개월)
- 구 상세: 월별 평당가 추이, 월별 거래 건수, 최근 거래 목록

## 준비물

- Python 3.11 이상
- 서울 열린데이터광장 인증키: [data.seoul.go.kr](https://data.seoul.go.kr) → 로그인 → 마이페이지 → 인증키 신청
- (선택) 브이월드 인증키: [vworld.kr](https://www.vworld.kr) → 인증키 발급. 없으면 기본 지도와 GitHub 공개 경계 파일을 씁니다.

## API 키 넣기

1. 프로젝트 폴더의 `.env.example`을 복사해서 이름을 `.env`로 바꿉니다.
2. `.env`를 메모장으로 열어 `=` 뒤에 키를 붙여 넣습니다.

```
SEOUL_API_KEY=여기에_서울시_키
VWORLD_API_KEY=여기에_브이월드_키
```

`.env`는 `.gitignore`에 등록되어 있어 GitHub에 올라가지 않습니다.

## 가장 쉬운 실행 (더블클릭)

`.env`에 키를 넣은 뒤, 폴더에서 아래 파일을 더블클릭합니다.

| 파일 | 하는 일 |
| --- | --- |
| `지도열기.bat` | 앱을 켜고 브라우저를 엽니다. 처음이면 설치와 데이터 수집까지 자동으로 합니다. 검은 창을 닫으면 앱이 꺼집니다. |
| `데이터받기.bat` | 최신 실거래가를 다시 받고, 지도 파일도 새로 만듭니다. |
| `서울집값지도.html` | 앱을 켜지 않고 바로 보는 지도 (아파트, 최근 12개월). 데이터를 받으면 자동으로 생깁니다. 필터와 구 상세는 앱에서만 됩니다. |

## 실행 (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python collect.py        # 데이터 받기: 작년 + 올해 (처음 한 번, 약 5~10분)
streamlit run app.py     # 브라우저에서 http://localhost:8501 열림
```

`collect.py` 옵션:

| 명령 | 하는 일 |
| --- | --- |
| `python collect.py` | 작년과 올해 거래 수집 |
| `python collect.py --years 2024 2025 2026` | 원하는 연도 수집 |
| `python collect.py --geo-only` | 구 경계 지도만 다시 받기 |

이미 받은 거래는 건너뛰므로 여러 번 실행해도 중복되지 않습니다. 앱 왼쪽의 "데이터 새로 받기" 버튼으로도 올해 데이터를 갱신할 수 있습니다.

## 구조

| 파일 | 역할 |
| --- | --- |
| `collect.py` | 서울시 API → `deals` 테이블 저장, 브이월드 → 구 경계 GeoJSON 저장 |
| `db.py` | SQLite 테이블 생성, 구 × 월 평균(`gu_monthly`) 계산, 조회 |
| `app.py` | Streamlit 화면 (필터, 순위표, 구 상세) |
| `mapview.py` | Folium 지도 그리기, `서울집값지도.html` 만들기 (`python mapview.py`) |
| `config.py` | `.env`에서 키 읽기, 파일 경로 |
| `data/realestate.db` | SQLite DB (자동 생성, GitHub 제외) |
| `data/seoul_gu.geojson` | 구 경계 (자동 생성) |

## 참고

- 실거래는 계약 후 30일 안에 신고되므로 최근 한 달 값은 건수가 적고 바뀔 수 있습니다.
- 해제(취소)된 거래는 평균 계산에서 뺍니다.
- 평당가 = 거래금액 ÷ (건물면적 ÷ 3.3058)

## 데이터 출처

- [서울 열린데이터광장 「서울시 부동산 실거래가 정보」](https://data.seoul.go.kr/dataList/OA-21275/S/1/datasetView.do)
- [국토교통부 브이월드](https://www.vworld.kr) 배경지도, 시군구 경계
- 예비 경계: [southkorea/seoul-maps](https://github.com/southkorea/seoul-maps) (Apache 2.0)
