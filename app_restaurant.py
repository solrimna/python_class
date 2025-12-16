import streamlit as st
import requests
import json
from datetime import datetime
import os, re, html
import time
from collections import defaultdict
from streamlit_folium import st_folium
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from streamlit_lottie import st_lottie
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import pickle
import bs4                      # 파싱.
from PIL import Image
from wordcloud import WordCloud

@st.cache_data
def load_lottiefile(filepath: str):
    """로컬 JSON 파일에서 Lottie 애니메이션 로드"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

NAVER_LOCAL_URL = "https://openapi.naver.com/v1/search/local.json"
NAVER_BLOG_URL  = "https://openapi.naver.com/v1/search/blog.json"
NAVER_IMAGE_URL = "https://openapi.naver.com/v1/search/image.json"

@st.cache_data(ttl=300)
def get_lat_lon(address: str):
    geolocator = Nominatim(user_agent="streamlit-folium-demo", timeout=10)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    location = geocode(
        address,
        exactly_one=True,
        country_codes="kr",
        language="ko",
    )

    if location:
        return location.latitude, location.longitude
    return None, None


# 페이지 설정
st.set_page_config(
    page_title="맛집 추천 Application",
    page_icon="🍽️",
    layout="wide"
)

# API 키 설정 ####################!!!!!!!!!!!!!!!!!!!!!!!!개인 API넣기!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID","bAZehsWIFzpW3ZcTG1Hn")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET","YV3IWu8E6m")

try:
    if not NAVER_CLIENT_ID:
        NAVER_CLIENT_ID = st.secrets["naver"]["client_id"]
    if not NAVER_CLIENT_SECRET:
        NAVER_CLIENT_SECRET = st.secrets["naver"]["client_secret"]
except:
    pass

API_CONFIGURED = bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)

# 세션 스테이트 초기화
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1

if 'current_search_query' not in st.session_state:
    st.session_state.current_search_query = ""

if 'current_results' not in st.session_state:
    st.session_state.current_results = []

if 'favorites' not in st.session_state:
    st.session_state.favorites = []

if 'search_key' not in st.session_state:
    st.session_state.search_key = []

if 'show_favorites' not in st.session_state:
    st.session_state.show_favorites = False

if 'current_tab' not in st.session_state:
    st.session_state.current_tab = 1

# 주요 도시 세부 지역 데이터베이스
MAJOR_CITIES_SUBDIVISIONS = {
    # 대전
    "대전": [
        "유성구", "서구", "동구", "중구", "대덕구",
        "대전역", "서대전", "유성", "둔산", "은행동", "탄방동",
        "궁동", "도마동", "용문동", "대흥동", "선화동",
        "노은동", "관평동", "유성온천", "대전시청",
        "충남대", "대전터미널", "중앙로", "신탄진", "대동",
        "가양동", "변동", "목동"
    ],
    
    # 서울 - 강남/서초
    "강남": [
        "강남역", "역삼역", "선릉역", "삼성역", "청담역", "압구정역",
        "역삼동", "삼성동", "청담동", "논현동", "신사동", "압구정동",
        "도산공원", "강남대로", "테헤란로", "신사동 가로수길", "청담동 명품거리"
    ],
    "서초": [
        "서초역", "교대역", "강남역", "양재역", "남부터미널",
        "서초동", "반포동", "양재동", "잠원동"
    ],
    
    # 서울 - 강서/마포
    "홍대": [
        "홍대입구역", "상수역", "합정역", "망원역",
        "홍대거리", "홍대앞", "연남동", "서교동", "동교동", "창천동"
    ],
    "신촌": [
        "신촌역", "이대역", "신촌로터리", "연세대", "이화여대"
    ],
    "여의도": [
        "여의도역", "국회의사당역", "여의나루역", "IFC몰", "여의도 한강공원"
    ],
    
    # 서울 - 강북/종로
    "강북": [
        "미아역", "수유역", "강북구청역", "4.19민주묘지역",
        "수유리", "미아동", "번동"
    ],
    "종로": [
        "종각역", "광화문역", "안국역", "종로3가역", "종로5가역",
        "인사동", "삼청동", "북촌", "서촌", "광화문"
    ],
    "명동": [
        "명동역", "을지로입구역", "회현역", "명동거리", "남대문시장", "중구청"
    ],
    
    # 서울 - 강동/송파
    "잠실": [
        "잠실역", "잠실새내역", "종합운동장역", "석촌역",
        "롯데월드", "잠실새내", "석촌호수", "신천동"
    ],
    "강동": [
        "강동구청역", "길동역", "둔촌동역", "명일역", "고덕역",
        "천호동", "성내동", "둔촌동", "암사동"
    ],
    
    # 서울 - 기타 주요 지역
    "건대": [
        "건대입구역", "구의역", "광진구청역", "건국대학교", "건대 로데오거리"
    ],
    "이태원": [
        "이태원역", "녹사평역", "한남역", "이태원 거리", "경리단길", "해방촌"
    ],
    "성수": [
        "성수역", "뚝섬역", "성수동1가", "성수동2가", "서울숲", "성수 카페거리"
    ],
    
    # 부산
    "부산": [
        "해운대", "광안리", "서면", "남포동", "자갈치", "센텀시티",
        "해운대해수욕장", "광안리해수욕장", "서면역", "부산역",
        "남포역", "자갈치시장", "벡스코", "신세계백화점",
        "동래", "온천장", "연산동", "부산대", "경성대", "송정"
    ],
    
    # 대구
    "대구": [
        "동성로", "반월당", "수성구", "중구", "달서구",
        "동성로역", "반월당역", "중앙로역", "명덕역",
        "동대구역", "범어동", "수성못", "두류동", "성서",
        "경북대", "계명대", "칠성시장", "서문시장"
    ],
    
    # 인천
    "인천": [
        "구월동", "부평", "송도", "주안", "인천역",
        "구월동역", "부평역", "부평시장", "송도국제도시",
        "주안역", "간석동", "작전동", "계양", "검단",
        "인천공항", "을왕리", "월미도"
    ],
    
    # 광주
    "광주": [
        "충장로", "금남로", "상무지구", "첨단", "수완",
        "광주역", "광주송정역", "광천동", "봉선동",
        "전남대", "조선대", "양동시장", "말바우시장"
    ],
    
    # 울산
    "울산": [
        "삼산동", "성남동", "달동", "옥동", "무거동",
        "울산역", "태화강역", "현대백화점", "롯데백화점",
        "울산대", "울산공항", "일산해수욕장"
    ],
    
    # 경기 - 수원
    "수원": [
        "수원역", "수원시청역", "영통역", "망포역", "매탄역",
        "인계동", "영통", "광교", "행궁동", "수원화성",
        "성균관대", "아주대", "수원시청", "롯데백화점"
    ],
    
    # 경기 - 성남
    "분당": [
        "서현역", "수내역", "정자역", "미금역", "오리역",
        "야탑역", "모란역", "판교역", "판교테크노밸리"
    ],
    
    # 경기 - 고양
    "일산": [
        "일산역", "주엽역", "정발산역", "마두역", "백석역",
        "일산동구", "일산서구", "라페스타", "웨스턴돔"
    ],
    
    # 경기 - 기타
    "안양": [
        "안양역", "평촌역", "범계역", "인덕원역", "안양시청"
    ],
    "부천": [
        "부천역", "중동역", "상동역", "부천시청", "부천터미널"
    ],
}

#util 함수
def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s)

def cut_to_dong(address: str) -> str:
    if not address:
        return ""

    m = re.search(r"^(.+?동)(?=\s|$)", address)
    return m.group(1) if m else address

def naver_headers():
    cid = NAVER_CLIENT_ID
    csec = NAVER_CLIENT_SECRET
    if not cid or not csec:
        raise RuntimeError("환경변수 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 설정 필요")
    return {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}

@st.cache_data(ttl=300)
def naver_search(url, params):
    r = requests.get(url, headers=naver_headers(), params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# 지역 세분화 함수 (하이브리드 방식)
def generate_location_variations(base_location):
    """
    지역별 세부 검색어 생성 (하이브리드 방식)
    
    1단계: 주요 도시는 미리 정의된 세부 지역 사용
    2단계: 없으면 기본 변형 패턴 생성
    
    네이버 API의 5개 제한을 우회하기 위해 지역을 세분화
    """
    base = base_location.lower().strip()
    variations = [base_location]
    
    # 1단계: 주요 도시 세부 지역 확인
    for city_key, subdivisions in MAJOR_CITIES_SUBDIVISIONS.items():
        if city_key.lower() in base or base in city_key.lower():
            variations.extend(subdivisions)
            return variations
    
    # 2단계: 주요 도시가 아니면 기본 변형 패턴 생성
    variations.extend([
        f"{base_location}역",
        f"{base_location} 시내",
        f"{base_location} 중심가",
        f"{base_location} 번화가",
        f"{base_location} 구도심",
        f"{base_location} 신도심",
        f"{base_location} 터미널",
        f"{base_location} 시청"
    ])
    
    # 3단계: "구" 단위가 포함되어 있으면 동 단위도 추가
    if "구" in base_location:
        variations.extend([
            f"{base_location} 1동",
            f"{base_location} 2동",
            f"{base_location} 3동"
        ])
    
    return variations

# API 호출 함수
def fetch_restaurants_by_location(location, food_type="전체", max_per_location=5, detail_type=False):
    """
    특정 지역의 맛집 정보를 가져옴
    
    Parameters:
    - location: 검색할 지역, 혹은 상세 매장
    - food_type: 음식 종류
    - max_per_location: 해당 지역에서 가져올 최대 개수 (기본 5개)
    - detail_type : 한 음식점 검색일 경우 True
    
    Returns:
    - 맛집 리스트
    """
    if not API_CONFIGURED:
        return []
    
    url = NAVER_LOCAL_URL
    
    # 검색어 생성
    if detail_type :
        search_query = {location}
    elif food_type == "전체":
        search_query = f"{location} 맛집"
    else:
        search_query = f"{location} {food_type}"
    
    params = {
        "query": search_query,
        "display": max_per_location,
        "start": 1,
        "sort": "random"
    }
    
    try:
        response = requests.get(url, headers=naver_headers(), params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            # 각 항목에 검색된 세부 지역 정보 추가
            for item in items:
                item['search_location'] = location
                #st.write(item['title'] + "중간체크")
            
            return items
        elif response.status_code == 429:
            st.warning(f"⚠️ API 호출 한도 도달: {location}")
            return []
        else:
            return []
            
    except Exception as e:
        return []

def is_address_match(address, road_address, base_location):
    """
    주소가 검색한 지역과 일치하는지 확인
    
    Parameters:
    - address: 지번 주소
    - road_address: 도로명 주소
    - base_location: 검색한 기본 지역명
    
    Returns:
    - True: 일치함, False: 일치하지 않음
    """
   
    # 모든 주소 합치기
    full_address = (address + " " + road_address).replace(" ", "").lower()
    base = base_location.replace(" ", "").lower()
    
    # 주요 도시 특별 처리
    city_mappings = {
        "세종": ["세종특별자치시", "세종시"],
        "대전": ["대전광역시", "대전시"],
        "부산": ["부산광역시", "부산시"],
        "대구": ["대구광역시", "대구시"],
        "인천": ["인천광역시", "인천시"],
        "광주": ["광주광역시", "광주시"],
        "울산": ["울산광역시", "울산시"],
        "강남": ["서울특별시강남구", "서울강남구"],
        "홍대": ["서울특별시마포구", "서울마포구"],
        "신촌": ["서울특별시서대문구", "서울서대문구"],
        "명동": ["서울특별시중구", "서울중구"],
        "강북": ["서울특별시강북구", "서울강북구"],
        "종로": ["서울특별시종로구", "서울종로구"],
        "잠실": ["서울특별시송파구", "서울송파구"],
        "건대": ["서울특별시광진구", "서울광진구"],
        "이태원": ["서울특별시용산구", "서울용산구"],
        "성수": ["서울특별시성동구", "서울성동구"],
        "수원": ["경기도수원시", "수원시"],
        "분당": ["경기도성남시분당구", "성남시분당구"],
        "일산": ["경기도고양시일산동구", "경기도고양시일산서구", "고양시일산"],
    }
    
    # 검색한 지역에 대한 매핑이 있으면 확인
    if base in city_mappings:
        for city_name in city_mappings[base]:
            if city_name.replace(" ", "").lower() in full_address:
                return True
        return False
    
    # 기본: 검색어가 주소에 포함되어 있는지 확인
    return base in full_address

def detail_search_restaurants(search_key, target_count=50):
    # 즐겨찾기 - 타겟 매장 정보 가져오기
    st.write(search_key)
    items = fetch_restaurants_by_location(location = search_key, max_per_location=5, detail_type=True)
    return items

def fetch_all_restaurants_with_variations(base_location, food_type, target_count=50):
    """
    지역 변형을 활용하여 더 많은 맛집 정보를 수집
    
    Parameters:
    - base_location: 기본 지역명
    - food_type: 음식 종류
    - target_count: 목표 수집 개수
    
    Returns:
    - 수집된 전체 맛집 리스트 (중복 제거됨)
    """
   
    # 지역 세분화
    location_variations = generate_location_variations(base_location)
    
    all_items = []
    seen_ids = set()  # 중복 제거를 위한 ID 세트
    
    # 프로그레스 바 생성
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, location in enumerate(location_variations):
        
        # 프로그레스 업데이트
        progress = (idx + 1) / len(location_variations)
        progress_bar.progress(progress)
        status_text.text("🔍 Searching ...")
        
        # 해당 지역의 맛집 정보 가져오기
        items = fetch_restaurants_by_location(location, food_type, max_per_location=5)
        
        # 중복 제거 및 지역 필터링하면서 추가
        for item in items:
           
           # ID로 중복 체크 (title + address 조합)
            item_id = f"{item.get('title', '')}_{item.get('address', '')}"
            
            if item_id not in seen_ids:
                
                # 주소 필터링
                address = item.get('address', '')
                road_address = item.get('roadAddress', '')
                
                # 주소가 검색 지역과 일치하는지 확인
                if is_address_match(address, road_address, base_location):
                    seen_ids.add(item_id)
                    all_items.append(item)
        
        # 목표 개수에 도달하면 중단
        if len(all_items) >= target_count:
            break
        
        # API 호출 제한 방지를 위한 딜레이
        time.sleep(0.15)
    
    progress_bar.empty()
    status_text.empty()
    
    return all_items


# 텍스트 데이터를 정제해 주는 함수.
# 주로 정규 표현식을 사용한다.
@st.cache_data
def cleanText(text):
    text = re.sub(r'\d|[a-zA-Z]|\W',' ', text)   # 수치, 알파벳, 특수문자 제거.
    text = re.sub(r'\s+',' ', text)              # 잉여 공백 1개로 줄임.
    return text

# 사전 트레이닝된 토크나이저를 불러오는 함수.
@st.cache_resource
def getTokenizer():
    f = open('./resources/my_tokenizer1.model','rb')
    tokenizer = pickle.load(f)
    f.close()
    return tokenizer

# 토큰화된 텍스트를 도수표로 정리해서 딕셔너리 형태로 변환해 주는 함수.
def makeTable(tokens, nmin=2, nmax=5, ncut=1):
    tokens_new = []
    # 조건에 맞는 토큰만 가져옴.
    for token in tokens:
        if len(token) >= nmin and len(token) <= nmax:         
            tokens_new.append(token)
    # Pandas 시리즈로 테이블화.
    ser = pd.Series(tokens_new)
    ser = ser.value_counts()
    ser = ser[ser >= ncut]                          # 최소 횟수 이상만.
    return dict(ser.sort_values(ascending=False))   # 내림차순 정렬해서 반환.

# 워드 클라우드 시각화 함수.
def plotChart(count_dict, max_words_, container):
    img = Image.open('./resources/background_1.png')                    # 타원형.
    my_mask=np.array(img)  
    # 워드 클라우드 객체.
    wc = WordCloud(font_path='./resources/NanumSquareR.ttf',                # 한글글꼴 파일 경로.
                    background_color='white',
                    contour_color='grey',
                    contour_width=3,
                    max_words=max_words_,
                    mask=my_mask)   
    
    # 토큰 (단어)의 도수표 (dict)를 사용해서 생성.
    wc.generate_from_frequencies(count_dict)
    fig = plt.figure(figsize=(10,10))

    # st.write("wc type:", type(wc))
    # st.write("dict empty?:", not bool(count_dict))

    plt.imshow(wc.to_array(), interpolation='bilinear')
    #plt.imshow(wc, interpolation='bilinear')
    plt.axis("off")                                                         # 가로/세로 축을 꺼줌.
    container.pyplot(fig)

# UI 구성 시작

col1, col2 = st.columns([0.8, 8], gap="small")
with col1:
    # Lottie 애니메이션 FILE (음식 관련 애니메이션)
    lottie_food = load_lottiefile("animation.json")
    if lottie_food:
        st_lottie(lottie_food, height=150, key="food_animation")
with col2:
    st.markdown("<h1 style='margin-top: 25px; margin-left: -10px;'>지역별 맛집 추천</h1>", unsafe_allow_html=True)

st.markdown("---")

# 사이드바 - 검색 옵션
with st.sidebar:
    st.header("🔍 검색")
    
    # 지역 입력
    location = st.text_input(
        "📍 지역 입력", 
        placeholder="예: 대전, 강남, 홍대, 부산",
        help="검색하고 싶은 지역을 입력하세요."
    )
    
    # 카테고리 선택
    food_type = st.selectbox(
        "🍴 카테고리",
        ["전체", "한식", "중식", "일식", "양식", "카페", "디저트", "분식", "치킨", "피자", "고기", "회/해산물"],
        help="원하는 카테고리를 선택하세요."
    )
    
    # 검색 버튼
    search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    if search_button:
        st.session_state.current_tab = 1

    st.markdown("---")
    
    # 저장 목록
    st.subheader("💖 저장 목록")
    if st.session_state.favorites:
        
        # 저장한 맛집 리스트 표시
        for idx, fav in enumerate(st.session_state.favorites, start=1):
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.write(f"{idx}. {fav['title'].replace('<b>', '').replace('</b>', '')}")
            with col2:
                if st.button("🔍", key=f"search_{idx}", use_container_width=True):
                    st.session_state.search_key = st.session_state.favorites[idx-1]
                    st.session_state.current_tab = 2
            with col3:
                if st.button("X", key=f"remove_{idx}", use_container_width=True):
                    st.session_state.favorites.pop(idx-1)
                    st.rerun()
        if st.button("🗑️ Delete", use_container_width=True):
            st.session_state.favorites = []
            st.success("저장 목록이 초기화되었습니다.")
            st.rerun()
    else:
        st.write("아직 저장한 맛집이 없습니다.")

# 메인 컨텐츠 영역
def display_restaurant(item, index):
    """
    맛집 정보를 화면에 표시하는 함수
    """
    # 저장 여부 확인
    item_id = f"{item.get('title', '')}_{item.get('address', '')}"
    is_favorited = item_id in [f"{fav.get('title', '')}_{fav.get('address', '')}" for fav in st.session_state.favorites]
    
    with st.container():
        col_title, col_location, col_favorite = st.columns([2.5, 1, 0.5])
        
        with col_title:
            #st.markdown(f"### {index}. {item['title'].replace('<b>', '').replace('</b>', '')}")
            # 제목 클릭시 -> 상세 검색 페이지로 넘어가도록
            if st.button(f"{index}. {item['title'].replace('<b>', '').replace('</b>', '')}", key=f"title_btn_{index}") :
                st.session_state.search_key = item
                st.session_state.current_tab = 2
                st.rerun()

        with col_location:
            if 'search_location' in item:
                st.markdown(f"<div style='text-align: right; color: #666; font-size: 0.9em;'>🔍 {item['search_location']}</div>", unsafe_allow_html=True)
        
        with col_favorite:
           
            # 저장 버튼
            if is_favorited:
                if st.button("💖", key=f"unfav_{index}", help="저장 취소"):
                    st.session_state.favorites = [fav for fav in st.session_state.favorites 
                                                   if f"{fav.get('title', '')}_{fav.get('address', '')}" != item_id]
                    st.rerun()
            else:
                if st.button("🤍", key=f"fav_{index}", help="저장하기"):
                    st.session_state.favorites.append(item)
                    st.rerun()
        
        info_col1, info_col2, info_col3 = st.columns([2, 1, 2])
        
        with info_col1:
            st.markdown(f"**🏷️ 카테고리:** {item.get('category', '정보 없음')}")
            st.markdown(f"**📍 주소:** {item.get('roadAddress', item.get('address', '정보 없음'))}")
        
        with info_col2:
            if item.get('link'):
                st.markdown(f"**🔗 [link]({item['link']})**")

        with info_col3:
            pass
            address = item.get('roadAddress') or item.get('address')
            place_name = item.get('title', '').replace('<b>', '').replace('</b>', '')

            if address:
                lat, lon = get_lat_lon(address)

                if lat is not None and lon is not None:
                    m = folium.Map(location=[lat, lon], zoom_start=16)

                    folium.Marker(
                    [lat, lon],
                    popup=place_name,
                    tooltip=place_name
                    ).add_to(m)

                    st_folium(m, width=320, height=220)
                else:             
                    st.caption("📍 위치 정보 없음")
            else:
                st.caption("📍 주소 없음")       
        st.markdown("---")

# 상세정보 컨텐츠 함수 
def detail_view_restaurants(items):
    #st.write(items)
    # 각 항목에 검색된 세부 지역 정보 추가
    for item in items:
        #item['search_location'] = location
        #st.write(item['title'] + "들어왔다 detail_view_restaurants!")
        # # 대표 이미지 1장
        img_data = naver_search(NAVER_IMAGE_URL, {"query": search_key, "display": 3, "start": 1, "sort": "sim"})
        img_items = img_data.get("items", [])
        
        # 후기(블로그) 여러 개
        blog_q = f"{search_key} 후기"
        blog_data = naver_search(NAVER_BLOG_URL, {"query": blog_q, "display": 3, "start": 1, "sort": "sim"})
        blog_items = blog_data.get("items", [])

        cols = st.columns(3)
        for i, it in enumerate(blog_items[:3]):
            with cols[i % 3]:
                with st.container(border=True):
                    # 이미지 먼저
                    if img_items:
                        thumb = img_items[i].get("link") or img_items[i].get("thumbnail")
                        if thumb:
                            st.image(thumb, use_container_width=True)

                    # 후기 내용
                    title = strip_tags(it.get("title",""))
                    desc  = strip_tags(it.get("description",""))
                    link  = it.get("link","")

                    st.markdown(f"**{title}**")
                    st.write(desc[:150] + ("..." if len(desc) > 150 else ""))
                    if link:
                        st.link_button("후기 열기", link)

# current_tab = 1
if st.session_state.current_tab == 1:
    title_name = f'{location} 지역 '
    if food_type:
        title_name += f'{food_type} 카테고리'
    st.subheader(f'{title_name}검색 결과 입니다.')
    # st.image('https://static.streamlit.io/examples/cat.jpg')
    
    # 검색 버튼이 클릭되었을 때
    if search_button:
        if not API_CONFIGURED:
            st.error("⚠️ API 키가 설정되지 않았습니다.")
        elif not location:
            st.warning("⚠️ 지역을 입력해주세요.")
        else:
            # 검색 실행
            target_count = 50  # 고정값으로 설정
            all_items = fetch_all_restaurants_with_variations(location, food_type, target_count)
            
            if all_items:
            
                # 검색 결과를 세션에 저장
                st.session_state.current_results = all_items
                st.session_state.current_search_query = f"{location} {food_type}"
                st.session_state.current_page = 1  # 새 검색 시 1페이지로 리셋
            else:
                st.warning("😢 검색 결과가 없습니다. 다른 지역이나 음식 종류를 시도해보세요.")



    # 저장된 검색 결과가 있으면 표시
    if st.session_state.current_results:
        all_items = st.session_state.current_results
        
        # 페이지네이션 설정
        ITEMS_PER_PAGE = 10
        total_items = len(all_items)
        total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        
        # 현재 페이지에 표시할 항목 계산
        start_idx = (st.session_state.current_page - 1) * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
        display_items = all_items[start_idx:end_idx]
        
        # 검색 결과 헤더
        st.success(f"✅ 총 {total_items}개의 맛집을 찾았습니다.")
        
        st.markdown("---")
        
        # 각 맛집 정보 표시
        for idx, item in enumerate(display_items, start=start_idx + 1):
            display_restaurant(item, idx)
        
        # 페이지네이션 버튼
        if total_pages > 1:
            st.markdown("---")
            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
            
            with col1:
                if st.button("⏮️ 처음", disabled=(st.session_state.current_page == 1), key="first_page"):
                    st.session_state.current_page = 1
                    st.rerun()
            
            with col2:
                if st.button("◀️ 이전", disabled=(st.session_state.current_page == 1), key="prev_page"):
                    st.session_state.current_page -= 1
                    st.rerun()
            
            with col3:
                st.markdown(f"<div style='text-align: center; padding: 8px;'><b>{st.session_state.current_page} / {total_pages}</b></div>", unsafe_allow_html=True)
            
            with col4:
                if st.button("다음 ▶️", disabled=(st.session_state.current_page == total_pages), key="next_page"):
                    st.session_state.current_page += 1
                    st.rerun()
            
            with col5:
                if st.button("마지막 ⏭️", disabled=(st.session_state.current_page == total_pages), key="last_page"):
                    st.session_state.current_page = total_pages
                    st.rerun()
else: # current_tab = 2
    # 즐겨찾기 검색 버튼이 클릭되었을 때 
    if st.session_state.search_key:
        search_key = st.session_state.search_key.get('title', '').replace('<b>', '').replace('</b>', '') + ("_") + st.session_state.search_key.get('address', '').replace('<b>', '').replace('</b>', '')
        title_name = st.session_state.search_key.get('title', '').replace('<b>', '').replace('</b>', '')
        st.subheader(f'{title_name} 상세 검색 결과 입니다.')
    
        address = st.session_state.search_key.get('address', '').replace('<b>', '').replace('</b>', '')
        items = detail_search_restaurants(search_key, target_count=50)

        # 주소까지 포함된 주소로 상세 검색 시도
        if items : 
            pass
        # 주소에 동이 포함된 경우 2차 검색 시도
        elif '동' in address :
            address = cut_to_dong(address)
            search_key = title_name + (" ") + address
            items = detail_search_restaurants(search_key, target_count=50)
        # 동이 미포함된 경우 title만으로 재검색 수행
        else :
            search_key = st.session_state.search_key.get('title', '').replace('<b>', '').replace('</b>', '')
            items = detail_search_restaurants(search_key, target_count=50)

        if items:
            # 1. 블로그 카드형 노출
            detail_view_restaurants(items)

            # 2. 블로그 세 개 크롤링
            corpus = ''
            blog_data = naver_search(NAVER_BLOG_URL, {"query": f"{search_key} 후기", "display": 3, "start": 1, "sort": "sim"})
            blog_items = blog_data.get("items", [])

            # 한개씩 직접 들어가서 크롤링해서 가져온다.
            for item in blog_items:
                news_url = item['link']

                res = requests.get(news_url, headers={'User-Agent':'Mozilla'})    # 헤더에 User-Agent 정보를 넣어서 차단을 피한다.
                soup = bs4.BeautifulSoup(res.text, 'html.parser')           # 파싱 진행.
                posts = soup.select("ul.lst_view > li.bx")
                iframe = soup.select_one("iframe#mainFrame")
                if iframe:
                    real_url = "https://blog.naver.com" + iframe.get("src")
                else:
                    real_url = news_url

                res2 = requests.get(real_url, headers={'User-Agent':'Mozilla/5.0'})
                soup2 = bs4.BeautifulSoup(res2.text, 'html.parser')

                content = soup2.select_one("div.se-main-container")
                if not content:
                    content = soup2.select_one("#postViewArea")

                if content:
                    text = content.get_text(" ", strip=True)
                    corpus += text

                # 워드 클라우드 차트가 출력될 위치.
                chart_container = st.empty()
                
            # 충분한 데이터가 확보되었으면, 데이터 전처리를 수행하고 시각화를 출력한다.
            if len(corpus) > 100:                                               # 말뭉치에 최소 100개 이상의 문자가 들어있는 경우.
                chart_container.info(':red[이미지 생성 중...]')
                corpus = cleanText(corpus)
                my_tokenizer = getTokenizer()
                # tokens = my_tokenizer.tokenize(corpus, flatten=True)          # 왼쪽 + 오른쪽 토큰.
                tokens = [t1 for t1, t2 in my_tokenizer.tokenize(corpus, flatten=False)] # 왼쪽 토큰 only!
                count_dict = makeTable(tokens)
                plotChart(count_dict, 70, chart_container)
            else:
                chart_container.error(':red[블로그 데이터 불충분!]')

# 푸터
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
    <p>본 서비스는 네이버 검색 API를 활용합니다.</p>
    </div>
    """,
    unsafe_allow_html=True
)