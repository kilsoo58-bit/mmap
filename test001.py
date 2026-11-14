import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import networkx as nx
from geopy.distance import geodesic
from datetime import datetime, timedelta
import requests

st.set_page_config(
    page_title="맞춤형 경로 및 지름길 탐색기",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    [data-testid="stSidebarCollapseButton"] {
        visibility: visible !important;
        opacity: 1 !important;
    }
    [data-testid="collapsedControl"] {
        visibility: visible !important;
        opacity: 1 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 1. 도보 경로 및 다중 경유지 경로 계산 함수
# ---------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_actual_walk_route(start_coord, end_coord):
    try:
        url = (
            f"http://router.project-osrm.org/route/v1/foot/"
            f"{start_coord[1]},{start_coord[0]};{end_coord[1]},{end_coord[0]}"
            f"?overview=full&geometries=geojson"
        )
        res = requests.get(url, timeout=3).json()
        if res.get("code") == "Ok" and res.get("routes"):
            route = res["routes"][0]
            dist_m = int(route["distance"])
            coords = [[pt[1], pt[0]] for pt in route["geometry"]["coordinates"]]
            return coords, dist_m
    except Exception:
        pass

    fallback_dist = int(geodesic(start_coord, end_coord).meters * 1.2)
    return [list(start_coord), list(end_coord)], fallback_dist


def get_multi_waypoint_walk_route(waypoints):
    """찍은 점들을 경유지로 삼아 실제 도로망을 따라가는 경로와 거리(m) 반환"""
    if len(waypoints) < 2:
        return waypoints, 0

    full_coords = []
    total_dist_m = 0

    for i in range(len(waypoints) - 1):
        seg_coords, seg_dist = get_actual_walk_route(waypoints[i], waypoints[i + 1])
        if i > 0 and full_coords:
            full_coords.extend(seg_coords[1:])
        else:
            full_coords.extend(seg_coords)
        total_dist_m += seg_dist

    return full_coords, total_dist_m


def calc_polyline_distance(coords):
    """찍은 점들을 직선으로 그대로 연결한 거리(m) 반환"""
    if len(coords) < 2:
        return 0
    total_m = 0
    for i in range(len(coords) - 1):
        total_m += geodesic(coords[i], coords[i + 1]).meters
    return int(total_m)


def format_duration(total_seconds, include_sec=True):
    total_seconds = int(round(total_seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}시간")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}분")
    if include_sec and (seconds > 0 or not parts):
        parts.append(f"{seconds}초")
    return " ".join(parts)

# ---------------------------------------------------------
# 2. 노선별 배차 간격(분) 및 지하철 표정속도(km/h)
# ---------------------------------------------------------
LINE_SPECS = {
    "1호선": {"speed_kmh": 32.5, "headway_min": 5.5},
    "2호선": {"speed_kmh": 33.0, "headway_min": 6.0},
    "3호선": {"speed_kmh": 34.0, "headway_min": 6.0},
    "4호선": {"speed_kmh": 30.0, "headway_min": 7.0},
    "동해선": {"speed_kmh": 45.0, "headway_min": 15.0},
    "부산김해경전철": {"speed_kmh": 35.0, "headway_min": 6.0}
}

# ---------------------------------------------------------
# 3. 부산 도시철도 호선별 전체 역 데이터
# ---------------------------------------------------------
BUSAN_LINES = {
    "1호선": {
        "다대포해수욕장역": (35.0485, 128.9642), "다대포항역": (35.0594, 128.9715),
        "낫개역": (35.0685, 128.9734), "신장림역": (35.0772, 128.9733),
        "장림역": (35.0865, 128.9718), "동매역": (35.0970, 128.9682),
        "신평역": (35.0955, 128.9606), "하단역": (35.1062, 128.9664),
        "당리역": (35.1067, 128.9748), "사하역": (35.1042, 128.9839),
        "괴정역": (35.0998, 128.9926), "대티역": (35.1026, 129.0062),
        "서대신역": (35.1118, 129.0181), "동대신역": (35.1105, 129.0232),
        "토성역": (35.1009, 129.0195), "자갈치역": (35.0974, 129.0267),
        "남포역": (35.0979, 129.0348), "중앙역": (35.1039, 129.0367),
        "부산역": (35.1152, 129.0422), "초량역": (35.1206, 129.0410),
        "부산진역": (35.1293, 129.0465), "좌천역(1호선)": (35.1345, 129.0526),
        "범일역": (35.1408, 129.0591), "범내골역": (35.1481, 129.0597),
        "서면역(1호선)": (35.1578, 129.0592), "부전역(1호선)": (35.1627, 129.0631),
        "양정역": (35.1729, 129.0712), "시청역": (35.1798, 129.0768),
        "연산역(1호선)": (35.1862, 129.0815), "교대역(1호선)": (35.1959, 129.0800),
        "동래역(1호선)": (35.2054, 129.0784), "명륜역": (35.2127, 129.0792),
        "온천장역": (35.2205, 129.0863), "부산대역": (35.2299, 129.0894),
        "장전역": (35.2381, 129.0881), "구서역": (35.2475, 129.0913),
        "두실역": (35.2575, 129.0924), "남산역": (35.2655, 129.0927),
        "범어사역": (35.2731, 129.0928), "노포역": (35.2846, 129.0950)
    },
    "2호선": {
        "장산역": (35.1699, 129.1768), "중동역": (35.1666, 129.1685),
        "해운대역": (35.1636, 129.1585), "동백역": (35.1586, 129.1481),
        "벡스코역(2호선)": (35.1689, 129.1388), "센텀시티역": (35.1689, 129.1317),
        "민락역": (35.1663, 129.1233), "수영역(2호선)": (35.1652, 129.1147),
        "광안역": (35.1579, 129.1130), "금련산역": (35.1485, 129.1105),
        "남천역": (35.1415, 129.1077), "경성대·부경대역": (35.1375, 129.1006),
        "대연역": (35.1345, 129.0925), "못골역": (35.1340, 129.0842),
        "지게골역": (35.1362, 129.0772), "문현역": (35.1383, 129.0688),
        "국제금융센터·부산은행역": (35.1472, 129.0645), "전포역": (35.1549, 129.0658),
        "서면역(2호선)": (35.1578, 129.0592), "부암역": (35.1576, 129.0506),
        "가야역": (35.1558, 129.0430), "동의대역": (35.1537, 129.0336),
        "개금역": (35.1530, 129.0242), "냉정역": (35.1517, 129.0142),
        "주례역": (35.1504, 129.0044), "감전역": (35.1555, 128.9912),
        "사상역(2호선)": (35.1624, 128.9856), "덕포역": (35.1724, 128.9845),
        "모덕역": (35.1805, 128.9855), "모라역": (35.1889, 128.9882),
        "구남역": (35.1973, 128.9955), "구명역": (35.2030, 129.0016),
        "덕천역(2호선)": (35.2100, 129.0062), "수정역": (35.2198, 129.0117),
        "화명역": (35.2361, 129.0135), "율리역": (35.2471, 129.0110),
        "동원역": (35.2575, 129.0084), "금곡역": (35.2678, 129.0064),
        "호포역": (35.2801, 129.0152), "증산역": (35.3055, 129.0095),
        "부산대양산캠퍼스역": (35.3182, 129.0108), "남양산역": (35.3283, 129.0185),
        "양산역": (35.3387, 129.0264)
    },
    "3호선": {
        "수영역(3호선)": (35.1652, 129.1147), "망미역": (35.1718, 129.1078),
        "배산역": (35.1765, 129.0970), "물만골역": (35.1772, 129.0874),
        "연산역(3호선)": (35.1862, 129.0815), "거제역": (35.1885, 129.0739),
        "종합운동장역": (35.1913, 129.0628), "사직역": (35.1989, 129.0617),
        "미남역(3호선)": (35.2057, 129.0683), "만덕역": (35.2131, 129.0401),
        "남산정역": (35.2139, 129.0252), "숙등역": (35.2120, 129.0142),
        "덕천역(3호선)": (35.2100, 129.0062), "구포역": (35.2067, 128.9961),
        "강서구청역": (35.2117, 128.9806), "체육공원역": (35.2140, 128.9680),
        "대저역(3호선)": (35.2133, 128.9607)
    },
    "4호선": {
        "미남역(4호선)": (35.2057, 129.0683), "동래역(4호선)": (35.2054, 129.0784),
        "수안역": (35.2014, 129.0838), "낙민역": (35.1999, 129.0903),
        "충렬사역": (35.1998, 129.0991), "명장역": (35.2053, 129.1077),
        "서동역": (35.2136, 129.1128), "금사역": (35.2157, 129.1197),
        "반여농산물시장역": (35.2173, 129.1278), "석대역": (35.2185, 129.1373),
        "영산대역": (35.2268, 129.1465), "윗반송역": (35.2325, 129.1539),
        "고촌역": (35.2361, 129.1627), "안평역": (35.2372, 129.1558)
    },
    "동해선": {
        "부전역(동해선)": (35.1643, 129.0645), "거제해맞이역": (35.1809, 129.0694),
        "거제역(동해선)": (35.1885, 129.0739), "교대역(동해선)": (35.1959, 129.0800),
        "동래역(동해선)": (35.1963, 129.0863), "안락역": (35.1952, 129.1023),
        "부산원동역": (35.1915, 129.1167), "재송역": (35.1843, 129.1242),
        "센텀역": (35.1788, 129.1319), "벡스코역(동해선)": (35.1691, 129.1396),
        "신해운대역": (35.1795, 129.1764), "송정역": (35.1852, 129.2001),
        "오시리아역": (35.1963, 129.2104), "기장역": (35.2443, 129.2155),
        "일광역": (35.2652, 129.2333), "좌천역(동해선)": (35.3117, 129.2483)
    },
    "부산김해경전철": {
        "사상역(경전철)": (35.1630, 128.9840), "괘법르네시떼역": (35.1698, 128.9822),
        "서부산유통지구역": (35.1683, 128.9567), "공항역": (35.1728, 128.9463),
        "덕두역": (35.1842, 128.9507), "등구역": (35.2016, 128.9567),
        "대저역(경전철)": (35.2133, 128.9607)
    }
}

ALL_STATIONS = {}
STATION_LINE_MAP = {}
for line_name, stations in BUSAN_LINES.items():
    for st_name, coords in stations.items():
        ALL_STATIONS[st_name] = coords
        STATION_LINE_MAP[st_name] = line_name

DEFAULT_EDGES = [
    ("다대포해수욕장역", "다대포항역"), ("다대포항역", "낫개역"), ("낫개역", "신장림역"),
    ("신장림역", "장림역"), ("장림역", "동매역"), ("동매역", "신평역"), ("신평역", "하단역"),
    ("하단역", "당리역"), ("당리역", "사하역"), ("사하역", "괴정역"), ("괴정역", "대티역"),
    ("대티역", "서대신역"), ("서대신역", "동대신역"), ("동대신역", "토성역"), ("토성역", "자갈치역"),
    ("자갈치역", "남포역"), ("남포역", "중앙역"), ("중앙역", "부산역"), ("부산역", "초량역"),
    ("초량역", "부산진역"), ("부산진역", "좌천역(1호선)"), ("좌천역(1호선)", "범일역"),
    ("범일역", "범내골역"), ("범내골역", "서면역(1호선)"), ("서면역(1호선)", "부전역(1호선)"),
    ("부전역(1호선)", "양정역"), ("양정역", "시청역"), ("시청역", "연산역(1호선)"),
    ("연산역(1호선)", "교대역(1호선)"), ("교대역(1호선)", "동래역(1호선)"), ("동래역(1호선)", "명륜역"),
    ("명륜역", "온천장역"), ("온천장역", "부산대역"), ("부산대역", "장전역"),
    ("장전역", "구서역"), ("구서역", "두실역"), ("두실역", "남산역"),
    ("남산역", "범어사역"), ("범어사역", "노포역"),
    ("장산역", "중동역"), ("중동역", "해운대역"), ("해운대역", "동백역"),
    ("동백역", "벡스코역(2호선)"), ("벡스코역(2호선)", "센텀시티역"), ("센텀시티역", "민락역"),
    ("민락역", "수영역(2호선)"), ("수영역(2호선)", "광안역"), ("광안역", "금련산역"), ("금련산역", "남천역"),
    ("남천역", "경성대·부경대역"), ("경성대·부경대역", "대연역"), ("대연역", "못골역"),
    ("못골역", "지게골역"), ("지게골역", "문현역"), ("문현역", "국제금융센터·부산은행역"),
    ("국제금융센터·부산은행역", "전포역"), ("전포역", "서면역(2호선)"), ("서면역(2호선)", "부암역"),
    ("부암역", "가야역"), ("가야역", "동의대역"), ("동의대역", "개금역"),
    ("개금역", "냉정역"), ("냉정역", "주례역"), ("주례역", "감전역"),
    ("감전역", "사상역(2호선)"), ("사상역(2호선)", "덕포역"), ("덕포역", "모덕역"),
    ("모덕역", "모라역"), ("모라역", "구남역"), ("구남역", "구명역"),
    ("구명역", "덕천역(2호선)"), ("덕천역(2호선)", "수정역"), ("수정역", "화명역"),
    ("화명역", "율리역"), ("율리역", "동원역"), ("동원역", "금곡역"),
    ("금곡역", "호포역"), ("호포역", "증산역"), ("증산역", "부산대양산캠퍼스역"),
    ("부산대양산캠퍼스역", "남양산역"), ("남양산역", "양산역"),
    ("수영역(3호선)", "망미역"), ("망미역", "배산역"), ("배산역", "물만골역"),
    ("물만골역", "연산역(3호선)"), ("연산역(3호선)", "거제역"), ("거제역", "종합운동장역"),
    ("종합운동장역", "사직역"), ("사직역", "미남역(3호선)"), ("미남역(3호선)", "만덕역"),
    ("만덕역", "남산정역"), ("남산정역", "숙등역"), ("숙등역", "덕천역(3호선)"),
    ("덕천역(3호선)", "구포역"), ("구포역", "강서구청역"), ("강서구청역", "체육공원역"),
    ("체육공원역", "대저역(3호선)"),
    ("미남역(4호선)", "동래역(4호선)"), ("동래역(4호선)", "수안역"), ("수안역", "낙민역"),
    ("낙민역", "충렬사역"), ("충렬사역", "명장역"), ("명장역", "서동역"),
    ("서동역", "금사역"), ("금사역", "반여농산물시장역"), ("반여농산물시장역", "석대역"),
    ("석대역", "영산대역"), ("영산대역", "윗반송역"), ("윗반송역", "고촌역"), ("고촌역", "안평역"),
    ("부전역(동해선)", "거제해맞이역"), ("거제해맞이역", "거제역(동해선)"),
    ("거제역(동해선)", "교대역(동해선)"), ("교대역(동해선)", "동래역(동해선)"),
    ("동래역(동해선)", "안락역"), ("안락역", "부산원동역"), ("부산원동역", "재송역"),
    ("재송역", "센텀역"), ("센텀역", "벡스코역(동해선)"), ("벡스코역(동해선)", "신해운대역"),
    ("신해운대역", "송정역"), ("송정역", "오시리아역"), ("오시리아역", "기장역"),
    ("기장역", "일광역"), ("일광역", "좌천역(동해선)"),
    ("사상역(경전철)", "괘법르네시떼역"), ("괘법르네시떼역", "서부산유통지구역"),
    ("서부산유통지구역", "공항역"), ("공항역", "덕두역"), ("덕두역", "등구역"),
    ("등구역", "대저역(경전철)"),
    ("서면역(1호선)", "서면역(2호선)"), ("연산역(1호선)", "연산역(3호선)"),
    ("동래역(1호선)", "동래역(4호선)"), ("미남역(3호선)", "미남역(4호선)"),
    ("수영역(2호선)", "수영역(3호선)"), ("덕천역(2호선)", "덕천역(3호선)"),
    ("교대역(1호선)", "교대역(동해선)"), ("거제역", "거제역(동해선)"),
    ("벡스코역(2호선)", "벡스코역(동해선)"), ("사상역(2호선)", "사상역(경전철)"),
    ("대저역(3호선)", "대저역(경전철)"), ("부전역(1호선)", "부전역(동해선)")
]

# ---------------------------------------------------------
# 4. 세션 상태 초기화
# ---------------------------------------------------------
if "start_pin" not in st.session_state:
    st.session_state.start_pin = (35.1545, 129.0558)
if "end_pin" not in st.session_state:
    st.session_state.end_pin = (35.3145, 129.0155)
if "click_target" not in st.session_state:
    st.session_state.click_target = "🟢 출발지 핀 찍기"
if "saved_shortcuts" not in st.session_state:
    st.session_state.saved_shortcuts = []
if "last_handled_click" not in st.session_state:
    st.session_state.last_handled_click = None

def find_nearest_station(coord):
    nearest_st = None
    min_dist = float("inf")
    for st_name, st_coord in ALL_STATIONS.items():
        d = geodesic(coord, st_coord).meters
        if d < min_dist:
            min_dist = d
            nearest_st = st_name
    return nearest_st

# ---------------------------------------------------------
# 5. 사이드바 설정
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ 사용자 및 시간 설정")
    user_speed = st.slider(
        "개인 걸음 속도 (km/h)",
        min_value=2.0,
        max_value=7.0,
        value=4.5,
        step=0.1
    )
    walk_speed_mps = (user_speed * 1000) / 3600

    depart_time_input = st.time_input(
        "🕒 출발 예정 시각 선택",
        value=datetime.now().time()
    )

    st.markdown("---")
    st.markdown("### 📍 분석 범위 설정")
    center_station = st.selectbox(
        "중심 기준 장소",
        list(ALL_STATIONS.keys()),
        index=list(ALL_STATIONS.keys()).index("서면역(1호선)")
    )
    search_radius = st.slider(
        "탐색 반경 (미터)",
        min_value=1000,
        max_value=40000,
        value=20000,
        step=1000
    )

    center_coords = ALL_STATIONS[center_station]
    in_range_stations = {
        name: coords for name, coords in ALL_STATIONS.items()
        if geodesic(center_coords, coords).meters <= search_radius
    }
    st.caption(f"✓ 반경 내 지하철역: **{len(in_range_stations)}개**")

    use_shortcut = st.checkbox("⚡ 나만의 지름길 우선 반영", value=True)

# ---------------------------------------------------------
# 6. 메인 상단 헤더 + 이용 가이드 팝오버 버튼
# ---------------------------------------------------------
head_col1, head_col2 = st.columns([4, 1])
with head_col1:
    st.markdown("## 🏃 맞춤형 경로 및 지름길 탐색기")
with head_col2:
    st.write("")
    with st.popover("💡 이용 가이드", use_container_width=True):
        st.markdown("""
        - **출발/도착 핀 찍기**: 상단에서 출발지 또는 도착지 핀을 선택한 뒤 지도 원하는 곳을 클릭하세요.
        - **지름길 경로 그리기**: `⭐ 지름길 경로 그리기`를 선택한 뒤 지도 좌측 상단의 **`╱`** 도구를 클릭해 샛길을 그린 후 우측에서 등록하세요.
        - **설정창 접기/펼치기**: 화면 좌측 상단의 **`<<` (또는 `>`)** 버튼으로 사이드바를 접거나 펼칠 수 있습니다.
        """)

st.markdown("---")
input_mode = st.radio(
    "📍 출발지 / 도착지 지정 방식",
    ["🗺️ 지도에서 직접 클릭하여 위치 지정", "🚉 호선별 지하철 역 선택"],
    horizontal=True
)

if input_mode == "🗺️ 지도에서 직접 클릭하여 위치 지정":
    c1, c2, c3 = st.columns([1.4, 1.4, 1.4])
    with c1:
        st.session_state.click_target = st.radio(
            "지도 클릭 모드",
            ["🟢 출발지 핀 찍기", "🔴 도착지 핀 찍기", "⭐ 지름길 경로 그리기"]
        )
    with c2:
        st.info(f"**🟢 출발지 좌표**\n`{st.session_state.start_pin[0]:.5f}, {st.session_state.start_pin[1]:.5f}`")
    with c3:
        st.error(f"**🔴 도착지 좌표**\n`{st.session_state.end_pin[0]:.5f}, {st.session_state.end_pin[1]:.5f}`")

    start_coord = st.session_state.start_pin
    end_coord = st.session_state.end_pin

    board_station = find_nearest_station(start_coord)
    alight_station = find_nearest_station(end_coord)

else:
    col_sl, col_ss, col_dl, col_ds = st.columns(4)
    with col_sl:
        start_line = st.selectbox("출발 호선", list(BUSAN_LINES.keys()), index=0)
    with col_ss:
        s_list = list(BUSAN_LINES[start_line].keys())
        board_station = st.selectbox("승차역", s_list, index=s_list.index("서면역(1호선)") if "서면역(1호선)" in s_list else 0)
    with col_dl:
        dest_line = st.selectbox("도착 호선", list(BUSAN_LINES.keys()), index=1)
    with col_ds:
        d_list = list(BUSAN_LINES[dest_line].keys())
        alight_station = st.selectbox("하차역", d_list, index=d_list.index("부산대양산캠퍼스역") if "부산대양산캠퍼스역" in d_list else 0)

    start_coord = ALL_STATIONS[board_station]
    end_coord = ALL_STATIONS[alight_station]

# ---------------------------------------------------------
# 7. 실제 도보 도로망(OSRM) 및 지하철 그래프 계산
# ---------------------------------------------------------
st_board_coord = ALL_STATIONS[board_station]
st_alight_coord = ALL_STATIONS[alight_station]

if start_coord != st_board_coord:
    orig_first_walk_coords, orig_first_walk_m = get_actual_walk_route(start_coord, st_board_coord)
else:
    orig_first_walk_coords, orig_first_walk_m = [list(start_coord)], 0

if st_alight_coord != end_coord:
    orig_last_walk_coords, orig_last_walk_m = get_actual_walk_route(st_alight_coord, end_coord)
else:
    orig_last_walk_coords, orig_last_walk_m = [list(end_coord)], 0

G = nx.Graph()
for name, coords in ALL_STATIONS.items():
    G.add_node(name, pos=coords, line=STATION_LINE_MAP[name])

for u, v in DEFAULT_EDGES:
    if u in ALL_STATIONS and v in ALL_STATIONS:
        dist_m = int(geodesic(ALL_STATIONS[u], ALL_STATIONS[v]).meters)
        lu, lv = STATION_LINE_MAP[u], STATION_LINE_MAP[v]
        if lu == lv:
            t_mps = (LINE_SPECS[lu]["speed_kmh"] * 1000) / 3600
            G.add_edge(u, v, weight=(dist_m / t_mps) + 30, distance=dist_m, type="subway")
        else:
            w_sec = dist_m / walk_speed_mps
            wait_sec = (LINE_SPECS[lv]["headway_min"] * 60) / 2
            G.add_edge(u, v, weight=w_sec + wait_sec, distance=dist_m, type="transfer")

active_sc_first = None
active_sc_last = None

if use_shortcut:
    for sc in st.session_state.saved_shortcuts:
        if sc["segment"] == "출발지 ➔ 승차역":
            active_sc_first = sc
        elif sc["segment"] == "하차역 ➔ 도착지":
            active_sc_last = sc

final_first_walk_m = active_sc_first["dist_m"] if active_sc_first else orig_first_walk_m
final_last_walk_m = active_sc_last["dist_m"] if active_sc_last else orig_last_walk_m

orig_walk_sec = (orig_first_walk_m + orig_last_walk_m) / walk_speed_mps
final_first_walk_sec = final_first_walk_m / walk_speed_mps
final_last_walk_sec = final_last_walk_m / walk_speed_mps
final_walk_sec = final_first_walk_sec + final_last_walk_sec

subway_ride_sec = 0
subway_wait_sec = 0
transfer_walk_sec = 0
subway_dist_m = 0
subway_path = []

if board_station != alight_station:
    try:
        subway_path = nx.shortest_path(G, source=board_station, target=alight_station, weight="weight")
        init_line = STATION_LINE_MAP[board_station]
        subway_wait_sec += (LINE_SPECS[init_line]["headway_min"] * 60) / 2

        for i in range(len(subway_path) - 1):
            e = G[subway_path[i]][subway_path[i + 1]]
            subway_dist_m += e["distance"]
            if e["type"] == "subway":
                subway_ride_sec += e["weight"]
            elif e["type"] == "transfer":
                lv = STATION_LINE_MAP[subway_path[i + 1]]
                tw = e["distance"] / walk_speed_mps
                twait = (LINE_SPECS[lv]["headway_min"] * 60) / 2
                transfer_walk_sec += tw
                subway_wait_sec += twait
    except nx.NetworkXNoPath:
        pass
else:
    subway_path = [board_station]

subway_total_sec = subway_ride_sec + subway_wait_sec + transfer_walk_sec

orig_total_sec = orig_walk_sec + subway_total_sec
final_total_sec = final_walk_sec + subway_total_sec
saved_sec = orig_total_sec - final_total_sec

orig_total_dist = orig_first_walk_m + subway_dist_m + orig_last_walk_m
final_total_dist = final_first_walk_m + subway_dist_m + final_last_walk_m

today = datetime.now().date()
depart_dt = datetime.combine(today, depart_time_input)
orig_arrive_dt = depart_dt + timedelta(seconds=orig_total_sec)
final_arrive_dt = depart_dt + timedelta(seconds=final_total_sec)

# ---------------------------------------------------------
# 8. 메인 본문: 지도(좌측) vs 이동 경로 요약 & 지름길 등록(우측)
# ---------------------------------------------------------
main_left, main_right = st.columns([1.6, 1])

with main_left:
    st.markdown("#### 🗺️ 실시간 경로 지도")
    if st.session_state.click_target == "⭐ 지름길 경로 그리기":
        st.info("✏️ 지도 좌측 상단의 **선 그리기(╱)** 아이콘을 누른 뒤 지름길 경로를 연속 클릭하여 그려주세요.")
    else:
        st.caption("지도 좌측 상단의 **선 그리기(╱)** 도구로 나만의 지름길을 직접 그릴 수 있습니다.")

    map_center = [
        (start_coord[0] + end_coord[0]) / 2,
        (start_coord[1] + end_coord[1]) / 2
    ]
    m = folium.Map(location=map_center, zoom_start=13, tiles="OpenStreetMap")

    draw = Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": {
                "shapeOptions": {"color": "#FFD600", "weight": 6}
            },
            "polygon": False,
            "circle": False,
            "rectangle": False,
            "marker": False,
            "circlemarker": False
        },
        edit_options={"edit": True, "remove": True}
    )
    draw.add_to(m)

    folium.Circle(
        location=center_coords,
        radius=search_radius,
        color="#3186cc",
        fill=True,
        fill_opacity=0.05,
        tooltip=f"기준 중심: {center_station}"
    ).add_to(m)

    for name, coords in in_range_stations.items():
        if name not in [board_station, alight_station]:
            folium.CircleMarker(
                location=coords,
                radius=4,
                color="#777",
                fill=True,
                fill_color="#fff",
                fill_opacity=0.8,
                tooltip=name
            ).add_to(m)

    folium.Marker(
        start_coord,
        popup="<b>출발지</b>",
        tooltip="🟢 출발지",
        icon=folium.Icon(color="green", icon="home", prefix="fa")
    ).add_to(m)

    folium.Marker(
        st_board_coord,
        popup=f"<b>승차역: {board_station}</b>",
        tooltip=f"🚇 승차역: {board_station}",
        icon=folium.Icon(color="blue", icon="subway", prefix="fa")
    ).add_to(m)

    folium.Marker(
        st_alight_coord,
        popup=f"<b>하차역: {alight_station}</b>",
        tooltip=f"🚇 하차역: {alight_station}",
        icon=folium.Icon(color="purple", icon="subway", prefix="fa")
    ).add_to(m)

    folium.Marker(
        end_coord,
        popup="<b>도착지</b>",
        tooltip="🔴 도착지",
        icon=folium.Icon(color="red", icon="flag", prefix="fa")
    ).add_to(m)

    if len(orig_first_walk_coords) > 1:
        folium.PolyLine(
            orig_first_walk_coords,
            color="#FF7043",
            weight=4,
            dash_array="5, 8",
            opacity=0.8,
            tooltip=f"일반 도로 보행 경로: {orig_first_walk_m}m"
        ).add_to(m)

    if len(orig_last_walk_coords) > 1:
        folium.PolyLine(
            orig_last_walk_coords,
            color="#FF7043",
            weight=4,
            dash_array="5, 8",
            opacity=0.8,
            tooltip=f"일반 도로 보행 경로: {orig_last_walk_m}m"
        ).add_to(m)

    if len(subway_path) > 1:
        sub_coords = [ALL_STATIONS[p] for p in subway_path]
        folium.PolyLine(
            sub_coords,
            color="#0052CC",
            weight=6,
            opacity=0.85,
            tooltip=f"지하철 탑승: {board_station} ➔ {alight_station}"
        ).add_to(m)

    for sc in [active_sc_first, active_sc_last]:
        if sc and len(sc["coords"]) >= 2:
            folium.PolyLine(
                sc["coords"],
                color="#00C853",
                weight=6,
                dash_array="10, 6",
                tooltip=f"⚡ 지름길 ({sc['name']}): {sc['dist_m']}m"
            ).add_to(m)

    map_data = st_folium(
        m,
        width=730,
        height=560,
        returned_objects=["last_clicked", "all_drawings"],
        key="main_route_map_v3"
    )

    if map_data and map_data.get("last_clicked") and input_mode == "🗺️ 지도에서 직접 클릭하여 위치 지정":
        if st.session_state.click_target in ["🟢 출발지 핀 찍기", "🔴 도착지 핀 찍기"]:
            clicked_lat = map_data["last_clicked"]["lat"]
            clicked_lng = map_data["last_clicked"]["lng"]
            new_coord = (clicked_lat, clicked_lng)

            if st.session_state.last_handled_click != new_coord:
                st.session_state.last_handled_click = new_coord
                if st.session_state.click_target == "🟢 출발지 핀 찍기":
                    st.session_state.start_pin = new_coord
                    st.rerun()
                elif st.session_state.click_target == "🔴 도착지 핀 찍기":
                    st.session_state.end_pin = new_coord
                    st.rerun()

    st.caption("🟧 **주황 점선**: 일반 도보 경로 | 🟩 **형광 초록 점선**: 등록된 지름길 | 🟨 **노란 실선**: 직접 그린 지름길 | 🟦 **파란 실선**: 지하철 구간")

# ---------------------------------------------------------
# 9. 우측 컬럼: 이동 경로 요약 & 지름길 등록
# ---------------------------------------------------------
with main_right:
    st.markdown("#### 🧭 이동 경로 요약")

    m1, m2 = st.columns(2)
    with m1:
        st.metric(
            "예상 소요 시간",
            format_duration(final_total_sec, include_sec=False),
            f"총 {final_total_dist:,}m"
        )
    with m2:
        if saved_sec > 0:
            saved_min_rounded = max(1, int(round(saved_sec / 60)))
            delta_text = f"{saved_min_rounded}분 단축 (기존 {orig_arrive_dt.strftime('%H:%M')} 도착)"
        elif saved_sec < 0:
            extra_min_rounded = max(1, int(round(abs(saved_sec) / 60)))
            delta_text = f"-{extra_min_rounded}분 지연"
        else:
            delta_text = f"출발 {depart_dt.strftime('%H:%M')} 기준"

        st.metric(
            "예상 도착 시각",
            final_arrive_dt.strftime("%p %I:%M").replace("AM", "오전").replace("PM", "오후"),
            delta=delta_text,
            delta_color="normal"
        )

    with st.container(border=True):
        st.markdown(f"**1️⃣ 도보 이동 (출발지 ➔ `{board_station}`)**")
        if active_sc_first:
            st.write(f"- ⚡ **지름길 적용 (`{active_sc_first['name']}`)**: **{final_first_walk_m:,}m** (기존 {orig_first_walk_m:,}m)")
            st.write(f"- 소요 시간: **{format_duration(final_first_walk_sec)}**")
        else:
            st.write(f"- 도로 거리: **{final_first_walk_m:,}m** / 소요: **{format_duration(final_first_walk_sec)}**")

        if board_station != alight_station and len(subway_path) > 1:
            st.markdown(f"**2️⃣ 지하철 이동 (`{board_station}` 승차 ➔ `{alight_station}` 하차)**")
            st.write(f"- 이동 구간: **{len(subway_path)-1}개 역** ({subway_dist_m/1000:.1f}km)")
            st.write(f"- 열차 탑승: **{format_duration(subway_ride_sec, False)}** / 배차·환승 대기: **{format_duration(subway_wait_sec, False)}**")
            if transfer_walk_sec > 0:
                st.write(f"- 역내 환승 보행: **{format_duration(transfer_walk_sec)}**")
        else:
            st.markdown("**2️⃣ 지하철 탑승 없음 (도보 권역 이동)**")

        st.markdown(f"**3️⃣ 도보 이동 (`{alight_station}` ➔ 도착지)**")
        if active_sc_last:
            st.write(f"- ⚡ **지름길 적용 (`{active_sc_last['name']}`)**: **{final_last_walk_m:,}m** (기존 {orig_last_walk_m:,}m)")
            st.write(f"- 소요 시간: **{format_duration(final_last_walk_sec)}**")
        else:
            st.write(f"- 도로 거리: **{final_last_walk_m:,}m** / 소요: **{format_duration(final_last_walk_sec)}**")

    st.divider()
    st.subheader("⭐ 나만의 지름길 등록")

    sc_segment = st.selectbox("적용할 도보 구간", ["출발지 ➔ 승차역", "하차역 ➔ 도착지"])

    sc_draw_mode = st.radio(
        "지름길 경로 연결 방식",
        ["✂️ 자유 직선 연결 (지도에 없는 샛길·건물 관통)", "🛣️ 기존 도로망 따라가기"],
        horizontal=True
    )

    raw_drawn_coords = []
    if map_data and map_data.get("all_drawings"):
        last_drawing = map_data["all_drawings"][-1]
        if last_drawing.get("geometry", {}).get("type") == "LineString":
            raw_lon_lat = last_drawing["geometry"]["coordinates"]
            raw_drawn_coords = [[pt[1], pt[0]] for pt in raw_lon_lat]

    if "자유 직선 연결" in sc_draw_mode:
        final_sc_coords = raw_drawn_coords
        drawn_dist_m = calc_polyline_distance(final_sc_coords)
    else:
        final_sc_coords, drawn_dist_m = get_multi_waypoint_walk_route(raw_drawn_coords)

    base_dist = orig_first_walk_m if sc_segment == "출발지 ➔ 승차역" else orig_last_walk_m

    if raw_drawn_coords:
        st.success(f"✏️ 지름길 경로 선택됨 (총 **{len(raw_drawn_coords)}개 지점**, 거리 약 **{drawn_dist_m:,}m**)")
        saved_preview = base_dist - drawn_dist_m
        if saved_preview > 0:
            st.caption(f"✨ 기존 도로 대비 **{saved_preview:,}m ({format_duration(saved_preview / walk_speed_mps)}) 단축 예상**")
    else:
        st.info("지도 좌측 상단의 **선 그리기(╱)** 도구로 지름길을 그린 뒤 아래에서 등록하세요.")

    safe_default_val = min(max(10, drawn_dist_m if drawn_dist_m > 0 else 250), 200000)

    with st.form("draw_shortcut_form"):
        sc_name = st.text_input("지름길 이름", placeholder="예: 아파트 단지 샛길 / 상가 관통 통로")
        sc_dist_override = st.number_input(
            "지름길 거리(m)",
            min_value=10,
            max_value=200000,
            value=safe_default_val,
            step=10
        )
        sc_desc = st.text_input("간단 메모 (선택)", placeholder="예: 공원 가로질러 역 출구 바로 진입")
        submitted = st.form_submit_button("지름길 등록하기", type="primary")

        if submitted:
            if not sc_name.strip():
                st.error("지름길 이름을 입력해주세요.")
            elif not final_sc_coords:
                st.error("먼저 지도 좌측 상단의 선 그리기(╱) 도구로 지름길을 그려주세요.")
            else:
                st.session_state.saved_shortcuts = [
                    s for s in st.session_state.saved_shortcuts if s["segment"] != sc_segment
                ]
                st.session_state.saved_shortcuts.append({
                    "segment": sc_segment,
                    "name": sc_name.strip(),
                    "dist_m": sc_dist_override,
                    "coords": final_sc_coords,
                    "desc": sc_desc.strip()
                })
                st.success(f"'{sc_name}' 등록 완료!")
                st.rerun()

    if st.session_state.saved_shortcuts:
        st.markdown("#### 📋 등록된 지름길 목록")
        for idx, sc in enumerate(st.session_state.saved_shortcuts):
            st.caption(f"{idx+1}. **[{sc['segment']}] {sc['name']}** ({sc['dist_m']}m) - *{sc['desc']}*")
        if st.button("등록된 지름길 전체 삭제"):
            st.session_state.saved_shortcuts = []
            st.rerun()
