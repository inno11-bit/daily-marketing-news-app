from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from core import collect_news, to_excel_bytes, to_html_report, now_kst, get_default_hours

APP_DIR = Path(__file__).resolve().parent
DEFAULT_SITES = APP_DIR / "config_sites.csv"
DEFAULT_KEYWORDS = APP_DIR / "config_keywords.csv"
DEFAULT_BRANDS = APP_DIR / "config_brands.csv"
DEFAULT_EXCLUDE = APP_DIR / "config_exclude_keywords.csv"

st.set_page_config(page_title="업무 뉴스 취합 자동화 v5.2 Mobile", layout="wide")

st.title("업무 뉴스 취합 자동화 v5.2 Mobile")
st.caption("종합 광고대행사용 Daily Intelligence: PC 표 검수 + 아이폰 카드형 보기 지원")

st.markdown("""
<style>
@media (max-width: 768px) {
    .block-container { padding: 0.8rem 0.7rem 2rem 0.7rem; }
    h1 { font-size: 1.45rem !important; }
    h2, h3 { font-size: 1.05rem !important; }
    div[data-testid="stSidebar"] { width: 100% !important; }
    .stDataFrame, .stDataEditor { font-size: 0.78rem; }
}
.news-card {
    border: 1px solid #e6e6e6;
    border-radius: 14px;
    padding: 14px 14px 12px 14px;
    margin-bottom: 12px;
    background: #ffffff;
    box-shadow: 0 1px 5px rgba(0,0,0,0.05);
}
.news-card-title {
    font-size: 1.02rem;
    line-height: 1.35;
    font-weight: 700;
    margin-bottom: 7px;
}
.news-card-meta {
    color: #666;
    font-size: 0.82rem;
    margin-bottom: 8px;
}
.news-card-summary {
    font-size: 0.9rem;
    line-height: 1.45;
    margin-bottom: 8px;
}
.news-chip {
    display: inline-block;
    background: #f2f4f7;
    border-radius: 999px;
    padding: 3px 8px;
    font-size: 0.75rem;
    margin-right: 4px;
    margin-bottom: 4px;
}
.news-link {
    font-size: 0.9rem;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("기본 설정")
    default_hours = get_default_hours()
    hours = st.number_input("수집 기간(시간)", min_value=1, max_value=168, value=default_hours, step=1)
    monday_mode = st.checkbox("월요일 자동 예외 적용(금~월 오전)", value=True)
    st.caption("월요일 실행 시 기본 96시간. 그 외 요일은 기본 24시간.")
    st.divider()
    speed_mode = st.radio("수집 모드", ["빠른 모드", "정밀 모드"], index=0, horizontal=True)
    is_fast = speed_mode == "빠른 모드"
    st.caption("빠른 모드: RSS/Google News 중심, 원문 링크 변환 최소화. 정밀 모드: 사이트 직접 수집·원문 링크 변환 포함.")
    mobile_view = st.checkbox("아이폰 카드형 보기 우선", value=True)
    use_google = st.checkbox("Google News 정교 검색 사용", value=True)
    use_site_scrape = st.checkbox("지정 사이트 직접 수집 사용", value=True)
    resolve_links = st.checkbox("Google News 원문 링크 변환", value=not is_fast)
    strict_recent = st.checkbox("발행시각 확인된 최근 기사만 표시", value=True)
    extract_site_dates = st.checkbox("원문에서 발행시각 보강", value=True)
    st.caption("오래된 기사 유입을 줄이려면 두 옵션을 켜두세요. 발행시각이 없는 기사는 기본 제외됩니다.")
    max_per_query = st.number_input("검색어별 최대 수집 건수", min_value=3, max_value=60, value=(8 if is_fast else 15), step=1)
    max_results = st.number_input("최대 표시 기사 수", min_value=20, max_value=300, value=(50 if is_fast else 100), step=10)
    request_timeout = st.number_input("사이트별 제한 시간(초)", min_value=2, max_value=20, value=(4 if is_fast else 8), step=1)
    min_score = st.slider("최소 추천도 필터", min_value=0, max_value=100, value=(35 if is_fast else 28), step=1)
    st.caption("추천도를 올리면 홍보성/잡음 기사가 줄고, 낮추면 누락이 줄어듭니다.")
    st.divider()
    st.markdown("**설정 파일 업로드(선택)**")
    sites_upload = st.file_uploader("사이트 목록 CSV", type=["csv"], key="sites")
    keywords_upload = st.file_uploader("업무 키워드 CSV", type=["csv"], key="keywords")
    brands_upload = st.file_uploader("브랜드/기업 목록 CSV", type=["csv"], key="brands")
    exclude_upload = st.file_uploader("제외 키워드 CSV", type=["csv"], key="exclude")


def load_csv(upload, default_path: Path) -> pd.DataFrame:
    if upload is not None:
        return pd.read_csv(upload)
    return pd.read_csv(default_path)


def safe_text(v, default="") -> str:
    if pd.isna(v):
        return default
    return str(v)


PRIMARY_COLUMNS = ["선택", "추천도", "기사제목", "발행시각", "출처", "링크", "요약", "카테고리", "키워드"]
EXTRA_COLUMNS = ["추천사유", "수집구분", "수집방식", "제외근거"]


def reorder_display_columns(data: pd.DataFrame) -> pd.DataFrame:
    if data is None or data.empty:
        return data
    cols = [c for c in PRIMARY_COLUMNS if c in data.columns]
    cols += [c for c in EXTRA_COLUMNS if c in data.columns and c not in cols]
    cols += [c for c in data.columns if c not in cols]
    return data[cols].copy()


def render_mobile_cards(data: pd.DataFrame, limit: int = 40):
    if data is None or data.empty:
        st.info("표시할 기사가 없습니다.")
        return
    data = data.head(limit).copy()
    for _, r in data.iterrows():
        title = safe_text(r.get("기사제목", r.get("기사 제목", r.get("title", ""))))
        score = safe_text(r.get("추천도", ""))
        source = safe_text(r.get("출처", r.get("source", "")))
        published = safe_text(r.get("발행시각", r.get("published_at", "")))
        link = safe_text(r.get("링크", r.get("link", "")))
        summary = safe_text(r.get("요약", r.get("summary", "")))
        category = safe_text(r.get("카테고리", ""))
        keywords = safe_text(r.get("키워드", ""))
        reason = safe_text(r.get("추천사유", ""))
        chips = ""
        for chip in [category, reason, keywords]:
            if chip:
                chips += f'<span class="news-chip">{chip}</span>'
        link_html = f'<a class="news-link" href="{link}" target="_blank">원문 보기</a>' if link else ""
        st.markdown(f"""
<div class="news-card">
  <div class="news-card-title">{title}</div>
  <div class="news-card-meta">추천도 {score} · {source} · {published}</div>
  <div class="news-card-summary">{summary}</div>
  <div>{chips}</div>
  <div style="margin-top:8px;">{link_html}</div>
</div>
""", unsafe_allow_html=True)


sites_df = load_csv(sites_upload, DEFAULT_SITES)
keywords_df = load_csv(keywords_upload, DEFAULT_KEYWORDS)
brands_df = load_csv(brands_upload, DEFAULT_BRANDS)
exclude_df = load_csv(exclude_upload, DEFAULT_EXCLUDE)

st.subheader("1) 수집 기준")
st.info("수집 순서: ① 지정 사이트 직접 수집·정리 ② Google News/추가 검색 ③ 통합 재중복 제거 ④ 지정 사이트 우선 정렬. 광고·소비자 트렌드 관련 AI와 주요 광고제 수상 기사는 유지합니다.")

tab1, tab2, tab3, tab4 = st.tabs(["확인 사이트", "업무 키워드", "브랜드/기업", "제외 키워드"])
with tab1:
    st.markdown("**매일 확인하는 사이트**")
    sites_edit = st.data_editor(
        sites_df,
        num_rows="dynamic",
        use_container_width=True,
        height=420,
        key="sites_edit",
        column_config={"enabled": st.column_config.CheckboxColumn("사용"), "url": st.column_config.LinkColumn("url")},
    )
with tab2:
    st.markdown("**광고·마케팅·브랜드·소비자 트렌드 키워드**")
    keywords_edit = st.data_editor(
        keywords_df,
        num_rows="dynamic",
        use_container_width=True,
        height=420,
        key="keywords_edit",
        column_config={"enabled": st.column_config.CheckboxColumn("사용")},
    )
with tab3:
    st.markdown("**국내 주요 브랜드/기업 중심 필터**")
    st.caption("공식 순위 데이터가 아니라 업무용 기본 목록입니다. 필요한 브랜드를 추가/삭제해 사용하세요.")
    brands_edit = st.data_editor(
        brands_df,
        num_rows="dynamic",
        use_container_width=True,
        height=420,
        key="brands_edit",
        column_config={"enabled": st.column_config.CheckboxColumn("사용")},
    )
with tab4:
    st.markdown("**제외/감점 키워드**")
    exclude_edit = st.data_editor(
        exclude_df,
        num_rows="dynamic",
        use_container_width=True,
        height=420,
        key="exclude_edit",
        column_config={"enabled": st.column_config.CheckboxColumn("사용")},
    )

st.divider()

col_a, col_b, col_c = st.columns([1, 1, 4])
with col_a:
    run = st.button("뉴스 수집", type="primary", use_container_width=True)
with col_b:
    clear = st.button("결과 초기화", use_container_width=True)

if clear:
    st.session_state.pop("news_df", None)

if run:
    with st.spinner(f"{speed_mode}로 뉴스 수집/필터링 중... 빠른 모드는 보통 더 짧게 걸립니다."):
        df = collect_news(
            keywords_edit,
            sites_edit,
            brands_df=brands_edit,
            exclude_df=exclude_edit,
            hours=int(hours),
            use_google_news=use_google,
            max_per_query=int(max_per_query),
            use_site_scrape=use_site_scrape,
            min_score=int(min_score),
            monday_mode=bool(monday_mode),
            resolve_links=bool(resolve_links),
            request_timeout=int(request_timeout),
            max_results=int(max_results),
            strict_recent=bool(strict_recent),
            extract_site_dates=bool(extract_site_dates),
        )
        st.session_state.news_df = reorder_display_columns(df)

if "news_df" in st.session_state:
    df = st.session_state.news_df
    st.success(f"수집 완료(v5.2 모바일 카드 지원): {len(df)}건 / 기준시각 {now_kst().strftime('%Y-%m-%d %H:%M')} / 최소 추천도 {min_score}")
    st.subheader("2) 결과 검수/수정")
    st.caption("아이폰에서는 카드형 보기를 권장합니다. PC에서는 표 검수 모드로 선택/수정 후 다운로드하세요.")

    view_mode = st.radio("보기 방식", ["아이폰 카드형", "PC 표 검수"], index=(0 if mobile_view else 1), horizontal=True)
    result_tabs = st.tabs(["전체 결과", "지정 사이트", "추가 검색", "소비자 트렌드", "AI×마케팅", "광고회사", "광고제·수상작"])

    def show_result_editor(data, key):
        data = reorder_display_columns(data)
        return st.data_editor(
            data,
            num_rows="dynamic",
            use_container_width=True,
            height=620,
            key=key,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택"),
                "링크": st.column_config.LinkColumn("링크"),
                "추천도": st.column_config.ProgressColumn("추천도", min_value=0, max_value=100),
                "추천사유": st.column_config.TextColumn("추천사유", width="medium"),
                "제외근거": st.column_config.TextColumn("제외근거", width="medium"),
                "출처": st.column_config.TextColumn("출처", width="small"),
            },
        )

    if view_mode == "아이폰 카드형":
        edited = reorder_display_columns(df).copy()
        with result_tabs[0]:
            render_mobile_cards(reorder_display_columns(df), limit=int(max_results))
        with result_tabs[1]:
            render_mobile_cards(reorder_display_columns(df[df.get("수집구분", "") == "지정 사이트"].copy()), limit=int(max_results))
        with result_tabs[2]:
            render_mobile_cards(reorder_display_columns(df[df.get("수집구분", "") == "추가 검색"].copy()), limit=int(max_results))
        with result_tabs[3]:
            render_mobile_cards(reorder_display_columns(df[df.get("추천사유", "").astype(str).str.contains("소비자 트렌드", na=False)].copy()), limit=int(max_results))
        with result_tabs[4]:
            render_mobile_cards(reorder_display_columns(df[df.get("추천사유", "").astype(str).str.contains("AI×마케팅|플랫폼 오픈", na=False)].copy()), limit=int(max_results))
        with result_tabs[5]:
            render_mobile_cards(reorder_display_columns(df[df.get("추천사유", "").astype(str).str.contains("광고회사", na=False)].copy()), limit=int(max_results))
        with result_tabs[6]:
            render_mobile_cards(reorder_display_columns(df[df.get("추천사유", "").astype(str).str.contains("광고제/수상작", na=False)].copy()), limit=int(max_results))
        with st.expander("PC용 표 검수 열기"):
            edited = show_result_editor(df, "result_edit_all_mobile_fallback")
    else:
        with result_tabs[0]:
            edited = show_result_editor(df, "result_edit_all")
        with result_tabs[1]:
            show_result_editor(df[df.get("수집구분", "") == "지정 사이트"].copy(), "result_edit_site")
        with result_tabs[2]:
            show_result_editor(df[df.get("수집구분", "") == "추가 검색"].copy(), "result_edit_external")
        with result_tabs[3]:
            show_result_editor(df[df.get("추천사유", "").astype(str).str.contains("소비자 트렌드", na=False)].copy(), "result_edit_consumer")
        with result_tabs[4]:
            show_result_editor(df[df.get("추천사유", "").astype(str).str.contains("AI×마케팅|플랫폼 오픈", na=False)].copy(), "result_edit_ai")
        with result_tabs[5]:
            show_result_editor(df[df.get("추천사유", "").astype(str).str.contains("광고회사", na=False)].copy(), "result_edit_agency")
        with result_tabs[6]:
            show_result_editor(df[df.get("추천사유", "").astype(str).str.contains("광고제/수상작", na=False)].copy(), "result_edit_award")

    selected = edited[edited.get("선택", True) == True].copy() if "선택" in edited.columns else edited.copy()
    selected = reorder_display_columns(selected)
    st.caption(f"선택된 기사: {len(selected)}건")

    export_name = f"daily_marketing_news_{datetime.now().strftime('%Y%m%d_%H%M')}"
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("Excel 다운로드", data=to_excel_bytes(selected), file_name=f"{export_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with c2:
        st.download_button("CSV 다운로드", data=selected.to_csv(index=False).encode("utf-8-sig"), file_name=f"{export_name}.csv", mime="text/csv", use_container_width=True)
    with c3:
        st.download_button("HTML 리포트 다운로드", data=to_html_report(selected, "업무 뉴스 데일리 리포트").encode("utf-8"), file_name=f"{export_name}.html", mime="text/html", use_container_width=True)
else:
    st.info("사이트/키워드/브랜드/제외 기준을 확인한 뒤 [뉴스 수집]을 누르세요. 평소에는 빠른 모드를 권장합니다.")

with st.expander("아이폰 홈 화면 추가 방법"):
    st.markdown(
        """
1. 이 앱을 서버나 사내 PC에서 실행합니다.
2. 아이폰 Safari에서 앱 주소에 접속합니다.
3. 하단 공유 버튼을 누릅니다.
4. **홈 화면에 추가**를 선택합니다.
5. 이름을 `데일리 뉴스` 등으로 지정하면 아이폰 앱처럼 실행할 수 있습니다.

※ `localhost:8501`은 실행 중인 PC 자기 자신만 의미합니다. 아이폰에서 쓰려면 같은 네트워크의 PC IP 주소나 서버 배포 주소로 접속해야 합니다.
"""
    )

with st.expander("필터 기준 설명"):
    st.markdown(
        """
- **1순위**: 지정 사이트 직접 수집/RSS 기사. Google News보다 먼저 수집하고 결과 상단에 우선 배치합니다.
- **2순위**: 소비자 트렌드(Z세대, 잘파세대, 팬덤, 취향 소비, 커머스 변화 등).
- **3순위**: 두드러지는 마케팅 트렌드(리브랜딩, CRM, 리테일 미디어, 크리에이터, 팝업 등).
- **4순위**: 국내 주요 광고회사(제일기획, 이노션, HSAD, 대홍기획 등).
- **5순위**: 글로벌 광고회사(WPP, Publicis, Omnicom, Dentsu, Accenture Song 등).
- **AI 기준**: 광고·마케팅·브랜드 경험·소비자 분석과 연결된 AI 기사는 유지하고, 기술 단독 AI 기사는 감점합니다.
- **수상/오픈 기준**: 주요 광고제 수상·수상작 트렌드, 광고/AI 플랫폼 오픈은 유지합니다. 단순 자사 수상 홍보·매장 오픈은 감점합니다.
- **중복 제거**: 제목 유사도 75~85% 이상인 재송고 기사는 지정 사이트/고추천도 기사 1건만 남깁니다.
- **기간 기준**: 기본 24시간. 월요일은 금요일~월요일 오전 뉴스를 포함하도록 96시간을 기본값으로 둡니다.
"""
    )
