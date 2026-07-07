from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Iterable
from urllib.parse import quote_plus, urljoin, urlparse

import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DailyNewsCollector/5.1"
KST = timezone(timedelta(hours=9))

CORE_TERMS = [
    "광고", "캠페인", "마케팅", "브랜드", "브랜딩", "리브랜딩", "프로모션", "팝업", "팝업스토어",
    "소비자", "트렌드", "Z세대", "잘파", "팬덤", "취향", "콜라보", "옥외광고", "OOH", "숏폼",
    "콘텐츠", "인플루언서", "커머스", "리테일미디어", "CRM", "멤버십", "퍼스널라이징", "PR",
    "크리에이티브", "브랜드 경험", "체험", "바이럴", "밈", "굿즈", "캐릭터", "로컬", "공간",
]
CONSUMER_TREND_TERMS = [
    "소비자 트렌드", "소비 트렌드", "Z세대", "MZ세대", "잘파세대", "알파세대", "시니어 소비",
    "팬덤", "취향 소비", "가치소비", "디깅", "커뮤니티", "밈", "숏폼", "리테일", "커머스", "여행 트렌드",
]
MARKETING_TREND_TERMS = [
    "리브랜딩", "브랜딩", "CRM", "퍼포먼스 마케팅", "리테일 미디어", "검색광고", "크리에이터",
    "콘텐츠 마케팅", "커뮤니티 마케팅", "브랜드 경험", "팝업스토어", "옥외광고", "OOH", "프로모션",
]
AI_MARKETING_TERMS = [
    "AI 광고", "AI 마케팅", "생성형 AI 광고", "광고 제작", "AI 캠페인", "AI 크리에이티브", "검색광고",
    "챗GPT 광고", "에이전틱 AI 광고", "AI CRM", "AI 커머스", "AI 검색", "마케팅 자동화", "소비자 분석",
]
AD_AWARD_TERMS = [
    "칸 라이언즈", "Cannes Lions", "스파이크스 아시아", "Spikes Asia", "에피", "Effie", "클리오", "Clio",
    "D&AD", "ADC", "대한민국광고대상", "광고대상", "광고제", "수상작", "그랑프리", "본상", "파이널리스트",
]
PLATFORM_OPEN_TERMS = [
    "광고 플랫폼", "광고 솔루션", "마케팅 플랫폼", "AI 플랫폼", "AI 광고", "검색광고", "리테일 미디어",
    "Google Ads", "구글 광고", "Meta 광고", "틱톡 광고", "TikTok 광고", "네이버 광고", "쿠팡 광고", "카카오 광고",
]
KOREAN_AGENCIES = [
    "제일기획", "이노션", "HSAD", "HS Ad", "HS애드", "대홍기획", "SM C&C", "TBWA", "TBWA코리아",
    "레오버넷", "맥켄", "맥켄코리아", "덴츠", "덴츠코리아", "VML", "VML코리아", "하쿠호도",
    "오리콤", "나스미디어", "메조미디어", "이엠넷", "인크로스", "디지털다임", "펜타클", "애드쿠아",
]
GLOBAL_AGENCIES = [
    "WPP", "Publicis", "퍼블리시스", "Omnicom", "옴니콤", "IPG", "Interpublic", "인터퍼블릭",
    "Dentsu", "덴츠", "Havas", "하바스", "Accenture Song", "액센츄어 송", "Stagwell", "S4 Capital", "Monks", "Media.Monks",
]
# 수상/오픈은 무조건 제외하지 않음. 광고제/플랫폼 오픈 맥락은 가산하고, 단순 자사 보도자료만 감점.
WEAK_PR_PATTERNS = ["선정", "협약", "mou", "업무협약", "후원", "기부", "모집", "채용", "공모전", "임명", "위촉", "출시"]
INVEST_PATTERNS = ["목표주가", "투자의견", "영업이익", "실적 전망", "컨센서스", "공모가"]
TECH_ONLY_AI = ["gpu", "반도체", "llm", "모델 출시", "파라미터", "데이터센터", "클라우드 인프라"]
PR_ONLY_PATTERNS = ["자사", "보도자료", "소비자만족도", "고객만족", "품질만족", "브랜드대상", "ESG 대상"]

# 일반 기업의 보도자료성/홍보성 기사 신호.
# 단, 광고제/마케팅 플랫폼/소비자 트렌드/광고회사 맥락이면 예외로 둡니다.
STRONG_PR_PATTERNS = [
    "업무협약", "mou", "협약", "파트너십 체결", "후원", "기부", "선정", "인증", "획득",
    "고객만족", "소비자만족도", "브랜드대상", "ESG 대상", "품질만족",
    "할인", "특가", "이벤트", "프로모션", "프로모션 진행", "멤버스데이", "당첨자", "회원 대상", "기념", "사은", "경품",
    "신제품", "신메뉴", "출시", "론칭", "선보여", "공개", "전개", "제공", "강화", "시동", "판매", "입점", "팝업스토어 오픈", "매장 오픈",
    "장학", "지원", "소비자 체험", "체험 마케팅", "브랜드 경험", "광고 공개", "캠페인 전개", "브랜드 성장", "거래액", "껑충", "공략", "이모저모", "업계",
]
SYNDICATION_DOMAINS = [
    "nate.com", "zum.com", "msn.com", "daum.net", "naver.com", "newsis.com", "yna.co.kr",
    "fnnews.com", "mk.co.kr", "edaily.co.kr", "hankyung.com", "bizwatch.co.kr",
]


def now_kst() -> datetime:
    return datetime.now(KST)


def get_default_hours(dt: datetime | None = None) -> int:
    """월요일은 금/토/일/월 오전까지 커버하도록 96시간, 그 외 24시간."""
    dt = dt or now_kst()
    return 96 if dt.weekday() == 0 else 24


def normalize_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y", "on", "사용", "사용함"}


def clean_text(text: str) -> str:
    text = BeautifulSoup(str(text or ""), "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = dtparser.parse(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(KST)
    except Exception:
        return None




def parse_date_from_text(text: str) -> datetime | None:
    """목록 페이지/본문 주변 텍스트에서 날짜를 추정합니다. 실패하면 None."""
    text = clean_text(text)
    if not text:
        return None
    patterns = [
        r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})",
        r"(\d{1,2})[.\-/월\s]+(\d{1,2})[일\s]*(\d{1,2}:\d{2})?",
    ]
    now = now_kst()
    for pat in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        try:
            if len(m.groups()) >= 3 and len(m.group(1)) == 4:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return datetime(y, mo, d, tzinfo=KST)
            mo, d = int(m.group(1)), int(m.group(2))
            hh, mm = 0, 0
            if len(m.groups()) >= 3 and m.group(3):
                hh, mm = map(int, m.group(3).split(":"))
            candidate = datetime(now.year, mo, d, hh, mm, tzinfo=KST)
            # 연말/연초 경계 보정
            if candidate - now > timedelta(days=30):
                candidate = candidate.replace(year=now.year - 1)
            return candidate
        except Exception:
            continue
    # 상대시간: 3시간 전, 25분 전, 어제
    m = re.search(r"(\d+)\s*(분|시간|일)\s*전", text)
    if m:
        n = int(m.group(1)); unit = m.group(2)
        if unit == "분": return now - timedelta(minutes=n)
        if unit == "시간": return now - timedelta(hours=n)
        if unit == "일": return now - timedelta(days=n)
    if "어제" in text:
        return now - timedelta(days=1)
    return None


def fetch_article_meta(url: str, timeout: int = 4) -> tuple[datetime | None, str]:
    """원문 페이지에서 발행시각과 요약을 보강합니다."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text or "", "html.parser")
        date_candidates = []
        for sel in [
            ("meta", {"property": "article:published_time"}, "content"),
            ("meta", {"name": "pubdate"}, "content"),
            ("meta", {"name": "publishdate"}, "content"),
            ("meta", {"name": "date"}, "content"),
            ("meta", {"itemprop": "datePublished"}, "content"),
            ("time", {}, "datetime"),
        ]:
            tag = soup.find(sel[0], sel[1])
            val = tag.get(sel[2]) if tag else ""
            if val:
                date_candidates.append(val)
        for val in date_candidates:
            dt = parse_datetime(val) or parse_date_from_text(val)
            if dt:
                desc = ""
                m = soup.find("meta", {"property": "og:description"}) or soup.find("meta", {"name": "description"})
                if m:
                    desc = clean_text(m.get("content", ""))
                return dt, desc
        # 메타가 없으면 페이지 앞부분 텍스트에서 보수적으로 추정
        dt = parse_date_from_text(soup.get_text(" ")[:3000])
        desc = ""
        m = soup.find("meta", {"property": "og:description"}) or soup.find("meta", {"name": "description"})
        if m:
            desc = clean_text(m.get("content", ""))
        return dt, desc
    except Exception:
        return None, ""

def domain_to_source(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return host or ""
    except Exception:
        return ""


def source_name(site_name: str, url: str) -> str:
    return clean_text(site_name) or domain_to_source(url)



def resolve_original_url(url: str, timeout: int = 8) -> str:
    """Google News RSS/redirect URL을 가능한 경우 원문 기사 URL로 변환합니다.

    Google News가 원문 URL을 숨기는 경우가 있어 100% 보장되지는 않지만,
    requests의 redirect 추적과 canonical/og:url 확인을 순서대로 시도합니다.
    실패하면 기존 URL을 반환합니다.
    """
    url = str(url or "").strip()
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower()
        if "news.google." not in host and "google.com" not in host:
            return url

        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        final_url = str(resp.url or "").strip()
        final_host = urlparse(final_url).netloc.lower()
        if final_url and "news.google." not in final_host and "google.com" not in final_host:
            return final_url

        # redirect가 그대로 Google에 머무는 경우, 페이지 내 canonical/og:url 후보 확인
        soup = BeautifulSoup(resp.text or "", "html.parser")
        for selector in [
            ("link", {"rel": "canonical"}, "href"),
            ("meta", {"property": "og:url"}, "content"),
        ]:
            tag = soup.find(selector[0], selector[1])
            candidate = tag.get(selector[2]) if tag else ""
            if candidate:
                cand_host = urlparse(candidate).netloc.lower()
                if "news.google." not in cand_host and "google.com" not in cand_host:
                    return candidate
    except Exception:
        pass
    return url


def active_list(df: pd.DataFrame, col="keyword") -> list[str]:
    if df is None or df.empty or col not in df.columns:
        return []
    return [str(r.get(col, "")).strip() for _, r in df.iterrows() if normalize_bool(r.get("enabled", True)) and str(r.get(col, "")).strip()]


def make_google_news_rss_url(keyword: str, hours: int = 24, lang: str = "ko", country: str = "KR") -> str:
    days = max(1, int((hours + 23) / 24))
    query = f'{keyword} when:{days}d'
    return "https://news.google.com/rss/search?q=" + quote_plus(query) + f"&hl={lang}&gl={country}&ceid={country}:{lang}"


def build_marketing_queries(keywords_df: pd.DataFrame, brands_df: pd.DataFrame, max_brand_queries: int = 30) -> list[tuple[str, str]]:
    keywords = active_list(keywords_df, "keyword")
    brands = active_list(brands_df, "brand")
    base_queries = [
        "소비자 트렌드 OR Z세대 OR 잘파세대 OR 팬덤",
        "마케팅 트렌드 OR 브랜드 캠페인 OR 광고 캠페인",
        "리브랜딩 OR 브랜드 경험 OR 팝업스토어",
        "AI 광고 OR AI 마케팅 OR 생성형 AI 광고 OR AI 크리에이티브",
        "광고제 수상작 OR 칸 라이언즈 OR 에피 어워드",
        "제일기획 OR 이노션 OR HSAD OR 대홍기획",
        "WPP OR Publicis OR Omnicom OR Dentsu OR Accenture Song",
    ]
    out: list[tuple[str, str]] = [(q, "핵심 검색") for q in base_queries]
    # 상위 브랜드는 너무 많으면 Google News 쿼리 폭증 → 앞쪽 N개만 기본 검색. 나머지는 결과 필터에서 사용.
    core_kw = " OR ".join(["광고", "캠페인", "마케팅", "브랜드", "프로모션", "트렌드"])
    for b in brands[:max_brand_queries]:
        out.append((f'{b} ({core_kw})', "브랜드 검색"))
    # 사용자가 추가한 키워드 중 일부도 검색
    for kw in keywords[:20]:
        out.append((kw, "업무 키워드"))
    # dedupe
    seen = set(); dedup=[]
    for q,c in out:
        if q not in seen:
            seen.add(q); dedup.append((q,c))
    return dedup


def fetch_rss(rss_url: str, keyword: str = "", category: str = "", site_name: str = "", timeout: int = 8, resolve_links: bool = False) -> list[dict]:
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(rss_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        return [{"error": f"RSS 수집 실패: {e}", "url": rss_url, "keyword": keyword, "category": category}]

    rows: list[dict] = []
    feed_title = clean_text(getattr(feed.feed, "title", ""))
    for entry in feed.entries:
        title = clean_text(getattr(entry, "title", ""))
        link = getattr(entry, "link", "") or ""
        original_link = resolve_original_url(link, timeout=timeout) if (resolve_links and ("news.google" in link.lower() or "google.com" in link.lower())) else link
        published = None
        for attr in ["published", "updated", "created"]:
            published = parse_datetime(getattr(entry, attr, None))
            if published:
                break
        src = ""
        if hasattr(entry, "source"):
            try:
                src = clean_text(entry.source.get("title", ""))
            except Exception:
                src = ""
        src = src or site_name or domain_to_source(original_link or link) or feed_title
        summary = clean_text(getattr(entry, "summary", ""))
        rows.append({
            "category": category,
            "keyword": keyword,
            "title": title,
            "source": src,
            "published_at": published,
            "link": original_link or link,
            "summary": summary,
            "collection_method": "RSS/Google News RSS",
        })
    return rows


def discover_rss_urls(page_url: str, timeout: int = 6) -> list[str]:
    headers = {"User-Agent": USER_AGENT}
    found: list[str] = []
    try:
        resp = requests.get(page_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all("link"):
            typ = str(tag.get("type", "")).lower()
            rel = " ".join(tag.get("rel", [])).lower() if isinstance(tag.get("rel"), list) else str(tag.get("rel", "")).lower()
            href = tag.get("href")
            if href and ("rss" in typ or "atom" in typ or "alternate" in rel):
                found.append(urljoin(page_url, href))
    except Exception:
        pass
    parsed = urlparse(page_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for suffix in ["/rss", "/feed", "/feed/", "/rss.xml", "/atom.xml"]:
        found.append(base + suffix)
    out = []
    for u in found:
        if u not in out:
            out.append(u)
    return out[:6]


def keyword_match(text: str, keywords: Iterable[str]) -> str:
    t = (text or "").lower().replace(" ", "")
    hits = []
    for kw in keywords:
        k = str(kw or "").strip()
        if not k:
            continue
        if k.lower().replace(" ", "") in t:
            hits.append(k)
    return ", ".join(dict.fromkeys(hits))


def scrape_site_page(page_url: str, site_name: str, category: str, keywords: list[str], timeout: int = 6, extract_dates: bool = True) -> list[dict]:
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(page_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        return [{"error": f"페이지 수집 실패: {e}", "url": page_url, "keyword": site_name, "category": category}]

    soup = BeautifulSoup(resp.text, "html.parser")
    rows: list[dict] = []
    seen = set()
    for a in soup.find_all("a"):
        title = clean_text(a.get_text(" "))
        href = a.get("href")
        if not href:
            continue
        link = urljoin(page_url, href)
        if not link.startswith("http"):
            continue
        if any(x in link.lower() for x in ["javascript:", "mailto:", "#", "login", "signup", "privacy", "terms"]):
            continue
        if len(title) < 8 or len(title) > 160:
            continue
        hit = keyword_match(title + " " + link, keywords + CORE_TERMS)
        if not hit:
            continue
        key = hashlib.md5((title.lower().strip() + "|" + link).encode("utf-8", errors="ignore")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        parent_text = clean_text(a.parent.get_text(" ") if a.parent else "")
        published = parse_date_from_text(parent_text)
        meta_summary = ""
        if extract_dates and published is None:
            published, meta_summary = fetch_article_meta(link, timeout=max(2, min(timeout, 5)))
        rows.append({
            "category": category,
            "keyword": hit or site_name,
            "title": title,
            "source": source_name(site_name, page_url),
            "published_at": published,
            "link": link,
            "summary": meta_summary,
            "collection_method": "사이트 목록 페이지",
        })
    return rows



def _compact(text: str) -> str:
    text = clean_text(text)
    # 언론사/분류/괄호성 군더더기 제거: [단독], (종합), <...> 등
    text = re.sub(r"\[[^\]]{1,12}\]|\([^)]{1,12}\)|<[^>]{1,20}>", " ", text)
    # 흔한 기사 어미/보도자료성 표현 제거로 같은 기사 묶기 강화
    text = re.sub(r"(종합|속보|단독|인터뷰|포토|영상|카드뉴스|보도자료|공식|선보여|밝혀|발표|나서|진행)", " ", text, flags=re.I)
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", str(text or "")).lower()


def _tokens(text: str) -> set[str]:
    text = clean_text(text).lower()
    text = re.sub(r"\[[^\]]+\]|\([^)]{1,20}\)", " ", text)
    toks = re.findall(r"[a-zA-Z0-9가-힣]{2,}", text)
    stop = {"기자", "뉴스", "보도", "발표", "공개", "진행", "한다", "했다", "위해", "통해", "관련", "종합", "단독"}
    return {t for t in toks if t not in stop}



def _core_tokens_for_cluster(text: str) -> set[str]:
    """동일 이슈 재송고를 더 강하게 묶기 위한 핵심 토큰."""
    text = clean_text(text).lower()
    text = re.sub(r"\[[^\]]+\]|\([^)]{1,30}\)|[\"'`“”‘’]", " ", text)
    toks = re.findall(r"[a-zA-Z0-9가-힣]{2,}", text)
    stop = {
        "기자", "뉴스", "보도", "발표", "공개", "진행", "한다", "했다", "위해", "통해", "관련", "종합", "단독",
        "브랜드", "마케팅", "캠페인", "전략", "기업", "업계", "강화", "제공", "공략", "성장", "통했다", "껑충",
        "이모저모", "프로모션", "출시", "신제품", "할인행사", "소식", "오늘", "대상"
    }
    return {t for t in toks if t not in stop and len(t) >= 2}

def title_similarity(a: str, b: str) -> float:
    """제목이 약간 다르게 재송고된 동일 기사를 묶기 위한 유사도."""
    ca, cb = _compact(a), _compact(b)
    if not ca or not cb:
        return 0.0
    if ca in cb or cb in ca:
        shorter = min(len(ca), len(cb)); longer = max(len(ca), len(cb))
        if shorter / max(1, longer) >= 0.55:
            return 0.97
    seq = SequenceMatcher(None, ca, cb).ratio()
    ta, tb = _tokens(a), _tokens(b)
    jac = len(ta & tb) / max(1, len(ta | tb))
    # 제목은 조금 달라도 핵심 토큰이 같으면 같은 재송고 기사로 봄
    if len(ta & tb) >= 4 and jac >= 0.55:
        return max(seq, 0.93)
    if len(ta & tb) >= 3 and jac >= 0.70:
        return max(seq, 0.92)
    ca2, cb2 = _core_tokens_for_cluster(a), _core_tokens_for_cluster(b)
    overlap = ca2 & cb2
    # 브랜드/핵심명사 3개 이상이 겹치면 제목이 달라도 같은 이슈로 묶음
    if len(overlap) >= 3:
        small = min(len(ca2), len(cb2)) or 1
        if len(overlap) / small >= 0.60:
            return max(seq, jac, 0.91)
    # 특정 브랜드명 + 핵심 토픽 2개 이상 겹치면 재송고 가능성이 높음
    if len(overlap) >= 2 and any(t in overlap for t in ["무신사", "롯데", "오뚜기", "일동제약", "롯데호텔", "롯데웰푸드", "롯데칠성"]):
        return max(seq, jac, 0.88)
    return max(seq, jac)


def _is_designated_source(method: str, source: str, source_group: str = "") -> bool:
    """사용자가 지정한 사이트에서 직접 수집된 기사인지 판별합니다.

    v5부터는 Google News/RSS와 지정 사이트 RSS를 분리하기 위해
    source_group 값을 최우선으로 사용합니다.
    """
    group = str(source_group or "")
    method = str(method or "")
    source = str(source or "").lower()
    if group == "지정 사이트":
        return True
    if "google news" in method.lower() or source in {"google", "google news"}:
        return False
    return False


def _syndication_penalty_source(source: str, link: str) -> int:
    text = f"{source} {link}".lower()
    return 1 if any(d in text for d in SYNDICATION_DOMAINS) else 0



def _is_general_company_pr_case(title: str, summary: str, reason: str, source_group: str) -> bool:
    """일반 매체의 개별 기업 홍보성 기사 차단.
    광고제/플랫폼/명확한 소비자·마케팅 트렌드는 예외로 둔다.
    """
    text = f"{title} {summary}".lower().replace(" ", "")
    reason = str(reason or "")
    source_group = str(source_group or "")
    protected = any(k in reason for k in ["광고제/수상작", "플랫폼 오픈", "국내 광고회사", "글로벌 광고회사"])
    # 지정 사이트의 인사이트성 글은 과도하게 제거하지 않음
    if source_group == "지정 사이트" and any(k in reason for k in ["소비자 트렌드", "마케팅 트렌드", "AI×마케팅"]):
        return False
    if protected:
        return False
    promo_terms = [
        "장학지원", "소비자체험", "체험마케팅", "브랜드경험", "프로모션", "할인행사", "신제품", "출시",
        "광고공개", "캠페인전개", "이벤트", "회원대상", "굿즈", "증정", "당첨자", "출국",
        "브랜드성장", "거래액", "껑충", "리브랜딩", "럭셔리시장공략", "야구장연계", "행사", "소식", "이모저모"
    ]
    brand_terms = [
        "롯데", "교촌", "오뚜기", "일동제약", "이마트", "gs25", "현대백화점", "롯데호텔",
        "롯데웰푸드", "롯데칠성", "역전우동", "무신사", "롯데뮤지엄", "파라다이스", "현대건설", "힐스테이트"
    ]
    if any(b in text for b in brand_terms) and any(p in text for p in promo_terms):
        # 트렌드 용어가 있어도 기사 제목이 개별 기업 성과/행사 중심이면 제외
        return True
    # [식품업계]/[유통업계] 류 묶음 홍보 기사
    if ("식품업계" in text or "유통업계" in text or "산업이모저모" in text) and any(p in text for p in promo_terms):
        return True
    return False

def dedupe_similar_articles(df: pd.DataFrame) -> pd.DataFrame:
    """출처만 다른 같은 기사 제거. 지정 사이트·고추천도·원문성이 높은 행을 우선 보존."""
    if df.empty or "title" not in df.columns:
        return df
    work = df.copy().reset_index(drop=True)
    work["_rank_direct"] = work.apply(lambda r: int(_is_designated_source(r.get("collection_method", ""), r.get("source", ""), r.get("source_group", ""))), axis=1)
    work["_rank_synd"] = work.apply(lambda r: _syndication_penalty_source(r.get("source", ""), r.get("link", "")), axis=1)
    work = work.sort_values(["_rank_direct", "score", "_rank_synd", "published_at"], ascending=[False, False, True, False], na_position="last").reset_index(drop=True)
    keep_idx: list[int] = []
    kept_titles: list[str] = []
    kept_links: set[str] = set()
    for idx, r in work.iterrows():
        title = str(r.get("title", ""))
        link = str(r.get("link", ""))
        # URL 경로가 같거나 제목 유사도가 높은 경우 중복으로 간주
        parsed = urlparse(link)
        normalized_link_key = f"{parsed.netloc.lower().replace('www.','')}{parsed.path}".rstrip("/")
        if normalized_link_key and normalized_link_key in kept_links:
            continue
        is_dup = False
        for kt in kept_titles:
            if title_similarity(title, kt) >= 0.75:
                is_dup = True
                break
        if not is_dup:
            keep_idx.append(idx)
            kept_titles.append(title)
            if normalized_link_key:
                kept_links.add(normalized_link_key)
    return work.loc[keep_idx].drop(columns=["_rank_direct", "_rank_synd"], errors="ignore").reset_index(drop=True)

def relevance_score(row: dict, brands: list[str], include_keywords: list[str], exclude_keywords: list[str]) -> tuple[int, str, str]:
    title = clean_text(row.get("title", ""))
    summary = clean_text(row.get("summary", ""))
    source = clean_text(row.get("source", ""))
    method = clean_text(row.get("collection_method", ""))
    direct_source = _is_designated_source(method, source, row.get("source_group", ""))
    text = f"{title} {summary} {source}".lower()
    text_no_space = text.replace(" ", "")

    score = 0
    reasons = []
    exclude_reasons = []

    # 1순위: 지정 사이트 직접 수집/RSS 수집 우대
    if direct_source:
        score += 55
        reasons.append("지정 사이트")
    if "사이트 목록" in method:
        score += 12
        reasons.append("직접 수집")

    # 2순위: 소비자 트렌드
    consumer_hits = [t for t in CONSUMER_TREND_TERMS if t.lower().replace(" ", "") in text_no_space]
    if consumer_hits:
        score += min(30, 14 + len(consumer_hits) * 5)
        reasons.append("소비자 트렌드:" + ",".join(consumer_hits[:3]))

    # 3순위: 두드러지는 마케팅 트렌드
    marketing_hits = [t for t in MARKETING_TREND_TERMS if t.lower().replace(" ", "") in text_no_space]
    if marketing_hits:
        score += min(28, 12 + len(marketing_hits) * 4)
        reasons.append("마케팅 트렌드:" + ",".join(marketing_hits[:3]))

    # 광고/마케팅 관련 AI는 유지·가산
    ai_hits = [k for k in AI_MARKETING_TERMS if k.lower().replace(" ", "") in text_no_space]
    if ai_hits:
        score += 24
        reasons.append("AI×마케팅")

    # 주요 광고제/수상작 기사 유지
    award_hits = [k for k in AD_AWARD_TERMS if k.lower().replace(" ", "") in text_no_space]
    if award_hits:
        score += 24
        reasons.append("광고제/수상작")

    # 주요 광고·AI 플랫폼 오픈 기사 유지
    platform_hits = [k for k in PLATFORM_OPEN_TERMS if k.lower().replace(" ", "") in text_no_space]
    if platform_hits and ("오픈" in text or "공개" in text or "출시" in text or "도입" in text):
        score += 20
        reasons.append("플랫폼 오픈")

    # 4순위: 국내 주요 광고 에이전시
    kr_agency_hits = [a for a in KOREAN_AGENCIES if a.lower().replace(" ", "") in text_no_space]
    if kr_agency_hits:
        score += 20
        reasons.append("국내 광고회사:" + ",".join(kr_agency_hits[:3]))

    # 5순위: 글로벌 주요 광고 에이전시
    global_agency_hits = [a for a in GLOBAL_AGENCIES if a.lower().replace(" ", "") in text_no_space]
    if global_agency_hits:
        score += 18
        reasons.append("글로벌 광고회사:" + ",".join(global_agency_hits[:3]))

    brand_hits = [b for b in brands if b and b.lower().replace(" ", "") in text_no_space]
    if brand_hits:
        # 브랜드 단독 기사는 약하게, 트렌드/캠페인 맥락이 있으면 더 높게
        brand_score = 8 if not (consumer_hits or marketing_hits or ai_hits or award_hits) else 18
        score += min(24, brand_score + len(brand_hits) * 2)
        reasons.append("브랜드 사례:" + ",".join(brand_hits[:3]))

    core_hits = [t for t in CORE_TERMS if t.lower().replace(" ", "") in text_no_space]
    if core_hits:
        score += min(26, 8 + len(core_hits) * 3)
        reasons.append("광고/브랜드 키워드:" + ",".join(core_hits[:3]))

    inc_hits = [k for k in include_keywords if k and k.lower().replace(" ", "") in text_no_space]
    if inc_hits:
        score += min(16, 4 + len(inc_hits) * 2)
        reasons.append("설정키워드:" + ",".join(inc_hits[:3]))

    # 홍보성/IR성 감점. v4.3: Google News/일반 매체의 브랜드 PR은 훨씬 엄격하게 컷.
    exc_hits = [k for k in exclude_keywords if k and k.lower().replace(" ", "") in text_no_space]
    strong_pr_hits = [p for p in STRONG_PR_PATTERNS if p.lower().replace(" ", "") in text_no_space]
    weak_pr_hit = any(p.lower().replace(" ", "") in text_no_space for p in WEAK_PR_PATTERNS)

    # 예외 보호: 광고제 전체 수상, 광고/AI 플랫폼 오픈, 주요 광고회사, 지정 전문 사이트의 트렌드/AI 기사
    hard_protected = bool(award_hits or platform_hits or kr_agency_hits or global_agency_hits)
    soft_protected = bool(direct_source and (consumer_hits or marketing_hits or ai_hits or core_hits))
    trend_protected = bool((consumer_hits or marketing_hits) and not brand_hits and not strong_pr_hits)
    ai_protected = bool(ai_hits and (direct_source or platform_hits or kr_agency_hits or global_agency_hits or consumer_hits or marketing_hits))
    protected_context = bool(hard_protected or soft_protected or trend_protected or ai_protected)

    if exc_hits and not protected_context:
        score -= min(48, 18 + len(exc_hits) * 8)
        exclude_reasons.append("제외키워드:" + ",".join(exc_hits[:3]))

    # 일반 기업의 자사 홍보성 기사는 강하게 배제.
    if (strong_pr_hits or weak_pr_hit) and not protected_context:
        penalty = 46 if not direct_source else 24
        score -= penalty
        exclude_reasons.append("홍보성 기사 가능:" + ",".join(strong_pr_hits[:3]) if strong_pr_hits else "단순 홍보 가능")

    # Google News/일반 매체에서 들어온 브랜드+프로모션/출시/체험 기사 대부분은 제외.
    # 단, 광고제 전체 결과·플랫폼 오픈·주요 광고회사·명확한 소비자 트렌드 분석은 유지.
    if brand_hits and (strong_pr_hits or exc_hits or weak_pr_hit) and not direct_source and not protected_context:
        score = 0
        exclude_reasons.append("일반 매체 브랜드 홍보성")

    # '문화 마케팅/체험 마케팅/브랜드 경험'이라는 표현만 있고 실제 트렌드 분석이 없는 일반 매체 기사는 감점
    generic_case_terms = ["문화마케팅", "체험마케팅", "브랜드경험", "프로모션", "멤버십", "회원대상"]
    if not direct_source and brand_hits and any(t in text_no_space for t in generic_case_terms) and not hard_protected:
        score = min(score, 10)
        exclude_reasons.append("개별 기업 사례성")

    # 단순 자사 수상/선정 홍보는 감점하되, 광고제 전체 수상/수상작 트렌드는 유지
    if ("수상" in text or "선정" in text) and not award_hits:
        if any(p.lower().replace(" ", "") in text_no_space for p in PR_ONLY_PATTERNS) or not (core_hits or consumer_hits or marketing_hits):
            score -= 16
            exclude_reasons.append("자사 수상 홍보 가능")

    # 단순 오픈은 감점하되, 광고/AI 플랫폼 오픈은 유지
    if "오픈" in text and not platform_hits and not (consumer_hits or marketing_hits):
        if any(x in text for x in ["매장", "팝업", "브랜드관", "플래그십", "점포"]):
            score -= 8
            exclude_reasons.append("단순 오픈 가능")

    if any(p.lower().replace(" ", "") in text_no_space for p in INVEST_PATTERNS):
        # IPO는 마케팅/소비자 맥락이 있을 때만 약감점, 순수 증권은 강감점
        penalty = 10 if protected_context else 24
        score -= penalty
        exclude_reasons.append("투자/증권 가능")

    if any(p.lower().replace(" ", "") in text_no_space for p in TECH_ONLY_AI) and not (ai_hits or core_hits or consumer_hits or marketing_hits):
        score -= 24
        exclude_reasons.append("AI 기술 단독 가능")

    if ("ai" in text.lower() or "인공지능" in text) and not (core_hits or ai_hits or consumer_hits or marketing_hits):
        score -= 18
        exclude_reasons.append("브랜드/마케팅 맥락 약함")

    # Google News에서 온 일반 기업 홍보성 재송고는 더 엄격하게 컷
    if not direct_source and (strong_pr_hits if 'strong_pr_hits' in locals() else False) and not protected_context:
        score = min(score, 6)

    return max(0, score), " / ".join(dict.fromkeys(reasons)), " / ".join(dict.fromkeys(exclude_reasons))


def collect_designated_site_news(
    sites_df: pd.DataFrame,
    active_keywords: list[str],
    brands: list[str],
    use_site_scrape: bool = True,
    request_timeout: int = 6,
    extract_site_dates: bool = True,
) -> list[dict]:
    """STEP 1. 지정 사이트 직접 수집.

    v5 핵심: Google News보다 먼저 지정 사이트를 수집하고 source_group을 명시합니다.
    """
    rows: list[dict] = []
    for _, row in sites_df.iterrows():
        if not normalize_bool(row.get("enabled", True)):
            continue
        url = str(row.get("url", row.get("rss_url", ""))).strip()
        rss_url = str(row.get("rss_url", "")).strip()
        if not url and not rss_url:
            continue
        site = str(row.get("site_name", "")).strip()
        category = str(row.get("category", "지정 사이트")).strip()

        if rss_url:
            fetched = fetch_rss(rss_url, keyword=site, category=category, site_name=site, timeout=request_timeout, resolve_links=False)
            for item in fetched:
                item["source_group"] = "지정 사이트"
            rows.extend(fetched)
            continue

        rss_success = False
        for candidate in discover_rss_urls(url, timeout=request_timeout):
            fetched = fetch_rss(candidate, keyword=site, category=category, site_name=site, timeout=request_timeout, resolve_links=False)
            valid = [x for x in fetched if not x.get("error")]
            if valid:
                for item in valid:
                    item["source_group"] = "지정 사이트"
                rows.extend(valid)
                rss_success = True
                break

        if use_site_scrape and not rss_success:
            scraped = scrape_site_page(url, site, category, active_keywords + brands, timeout=request_timeout, extract_dates=extract_site_dates)
            for item in scraped:
                item["source_group"] = "지정 사이트"
            rows.extend(scraped)
    return rows


def collect_external_news(
    keywords_df: pd.DataFrame,
    brands_df: pd.DataFrame | None,
    hours: int = 24,
    use_google_news: bool = True,
    max_per_query: int = 20,
    request_timeout: int = 6,
    resolve_links: bool = False,
) -> list[dict]:
    """STEP 3. 지정 사이트 정리 후 추가 검색 수행."""
    rows: list[dict] = []
    if not use_google_news:
        return rows
    for query, category in build_marketing_queries(keywords_df, brands_df if brands_df is not None else pd.DataFrame(), max_brand_queries=30):
        rss_url = make_google_news_rss_url(query, hours=hours)
        fetched = fetch_rss(rss_url, keyword=query, category=category, site_name="Google News", timeout=request_timeout, resolve_links=resolve_links)
        for item in fetched[:max_per_query]:
            item["source_group"] = "추가 검색"
            rows.append(item)
    return rows


def collect_news(
    keywords_df: pd.DataFrame,
    sites_df: pd.DataFrame,
    brands_df: pd.DataFrame | None = None,
    exclude_df: pd.DataFrame | None = None,
    hours: int = 24,
    use_google_news: bool = True,
    max_per_query: int = 20,
    use_site_scrape: bool = True,
    min_score: int = 18,
    monday_mode: bool = True,
    resolve_links: bool = False,
    request_timeout: int = 6,
    max_results: int = 100,
    strict_recent: bool = True,
    extract_site_dates: bool = True,
) -> pd.DataFrame:
    if monday_mode and now_kst().weekday() == 0 and hours <= 24:
        hours = 96
    cutoff = now_kst() - timedelta(hours=hours)

    active_keywords = active_list(keywords_df, "keyword")
    brands = active_list(brands_df, "brand") if brands_df is not None else []
    exclude_keywords = active_list(exclude_df, "keyword") if exclude_df is not None else []

    # STEP 1~2: 지정 사이트 먼저 수집/정리
    site_rows = collect_designated_site_news(
        sites_df,
        active_keywords,
        brands,
        use_site_scrape=use_site_scrape,
        request_timeout=request_timeout,
        extract_site_dates=extract_site_dates,
    )
    site_df = normalize_output(
        site_rows,
        cutoff,
        brands,
        active_keywords,
        exclude_keywords,
        min_score=max(10, int(min_score) - 10),
        max_results=max_results,
        strict_recent=strict_recent,
        stage="site",
    )

    # STEP 3~4: 이후 추가 검색 수행/정리
    external_rows = collect_external_news(
        keywords_df,
        brands_df,
        hours=hours,
        use_google_news=use_google_news,
        max_per_query=max_per_query,
        request_timeout=request_timeout,
        resolve_links=resolve_links,
    )
    external_df = normalize_output(
        external_rows,
        cutoff,
        brands,
        active_keywords,
        exclude_keywords,
        min_score=min_score,
        max_results=max_results,
        strict_recent=strict_recent,
        stage="external",
    )

    # STEP 5~6: 통합 후 재중복 제거. 지정 사이트 보존 우선.
    combined = pd.concat([site_df, external_df], ignore_index=True)
    if combined.empty:
        return combined

    # normalize_output 이후 컬럼명을 내부 dedupe용으로 임시 변환
    work = pd.DataFrame({
        "title": combined.get("기사제목", ""),
        "source": combined.get("출처", ""),
        "published_at": pd.to_datetime(combined.get("발행시각", ""), errors="coerce"),
        "link": combined.get("링크", ""),
        "summary": combined.get("요약", ""),
        "category": combined.get("카테고리", ""),
        "keyword": combined.get("키워드", ""),
        "score": combined.get("추천도", 0),
        "reason": combined.get("추천사유", ""),
        "exclude_reason": combined.get("제외근거", ""),
        "source_group": combined.get("수집구분", ""),
        "collection_method": combined.get("수집구분", ""),
    })
    work = dedupe_similar_articles(work)
    work = work.sort_values(["source_group", "score", "published_at"], ascending=[True, False, False], na_position="last")
    # 지정 사이트가 먼저 오도록 categorical sort
    order = {"지정 사이트": 0, "추가 검색": 1}
    work["_group_order"] = work["source_group"].map(order).fillna(2)
    work = work.sort_values(["_group_order", "score", "published_at"], ascending=[True, False, False], na_position="last").drop(columns=["_group_order"], errors="ignore")
    if max_results:
        work = work.head(int(max_results))

    out = pd.DataFrame({
        "선택": True,
        "추천도": work["score"].fillna(0).astype(int),
        "기사제목": work["title"].fillna(""),
        "발행시각": work["published_at"].dt.strftime("%Y-%m-%d %H:%M").fillna(""),
        "출처": work["source"].fillna(""),
        "링크": work["link"].fillna(""),
        "요약": work["summary"].fillna(""),
        "카테고리": work["category"].fillna(""),
        "키워드": work["keyword"].fillna(""),
        "추천사유": work["reason"].fillna(""),
        "수집구분": work["source_group"].fillna(""),
        "제외근거": work["exclude_reason"].fillna(""),
    })
    return out.reset_index(drop=True)

def normalize_output(rows: list[dict], cutoff: datetime, brands: list[str], include_keywords: list[str], exclude_keywords: list[str], min_score: int, max_results: int = 100, strict_recent: bool = True, stage: str = "combined") -> pd.DataFrame:
    df = pd.DataFrame(rows)
    columns = ["선택", "추천도", "기사제목", "발행시각", "출처", "링크", "요약", "카테고리", "키워드", "추천사유", "수집구분", "제외근거"]
    if df.empty:
        return pd.DataFrame(columns=columns)

    if "error" in df.columns:
        df = df[df.get("error").isna()]
    if df.empty:
        return pd.DataFrame(columns=columns)

    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    dated = df[df["published_at"].notna()]
    undated = df[df["published_at"].isna()]
    dated = dated[dated["published_at"] >= cutoff]
    # v4.1: 기본은 발행시각이 확인된 기사만 유지. 오래된 목록 페이지 기사 유입 방지.
    if strict_recent:
        df = dated.copy()
    else:
        # 사용자가 직접 허용한 경우에만 날짜 없는 사이트 직접 수집 결과를 포함
        df = pd.concat([dated, undated], ignore_index=True)

    df["_dedupe"] = (df["title"].fillna("").str.lower().str.strip() + "|" + df["link"].fillna("")).map(lambda x: hashlib.md5(x.encode("utf-8", errors="ignore")).hexdigest())
    df = df.drop_duplicates("_dedupe")

    scores, reasons, ex_reasons = [], [], []
    for _, r in df.iterrows():
        s, rs, ex = relevance_score(r.to_dict(), brands, include_keywords, exclude_keywords)
        scores.append(s); reasons.append(rs); ex_reasons.append(ex)
    df["score"] = scores; df["reason"] = reasons; df["exclude_reason"] = ex_reasons

    # v4.3: 일반 포털/재송고 매체의 홍보성 기사 재유입 차단.
    # 지정 사이트 직접/RSS 기사는 min_score 기준, Google News 일반 기사는 더 높은 기준과 추천사유를 요구.
    def _pass_quality_gate(r):
        method = str(r.get("collection_method", ""))
        source = str(r.get("source", ""))
        direct = _is_designated_source(method, source, r.get("source_group", ""))
        score = int(r.get("score", 0) or 0)
        reason = str(r.get("reason", ""))
        ex = str(r.get("exclude_reason", ""))
        title = str(r.get("title", ""))
        text = (title + " " + str(r.get("summary", ""))).lower().replace(" ", "")
        if score < int(min_score):
            return False
        # 지정 사이트는 우선 보존하되, 명백한 홍보/IR성은 제외
        if direct:
            direct_noisy = any(k in ex for k in ["투자/증권", "AI 기술 단독", "자사 수상 홍보"])
            return not direct_noisy
        # 추가 검색/일반 매체는 매우 엄격: 명확한 인사이트 카테고리 + 홍보성 없음
        valuable = any(k in reason for k in ["소비자 트렌드", "마케팅 트렌드", "AI×마케팅", "광고제/수상작", "국내 광고회사", "글로벌 광고회사", "플랫폼 오픈"])
        noisy = any(k in ex for k in ["홍보성", "브랜드 자사", "개별 기업 사례성", "단순 홍보", "투자/증권", "AI 기술 단독"])
        # 일반 매체 브랜드+프로모션/출시/체험성은 대부분 제외
        pr_combo = any(x in text for x in ["프로모션", "할인", "당첨자", "회원대상", "브랜드경험", "체험마케팅", "행사", "이벤트", "출국", "증정", "광고공개", "캠페인전개", "신제품", "출시", "굿즈", "이모저모"])
        if pr_combo and not any(k in reason for k in ["광고제/수상작", "플랫폼 오픈"]):
            return False
        if _is_general_company_pr_case(title, r.get("summary", ""), reason, r.get("source_group", "")):
            return False
        return bool(score >= max(45, int(min_score) + 15) and valuable and not noisy)

    df = df[df.apply(_pass_quality_gate, axis=1)]
    # v5.1: 일반 기업 홍보성/재송고성 개별 사례 추가 차단
    if not df.empty:
        df = df[~df.apply(lambda r: _is_general_company_pr_case(r.get("title", ""), r.get("summary", ""), r.get("reason", ""), r.get("source_group", "")), axis=1)]
    if df.empty:
        return pd.DataFrame(columns=columns)

    # 같은 기사 재송고 제거: 제목 유사도 90% 이상이면 1건만 보존
    df = dedupe_similar_articles(df)

    df = df.sort_values(["score", "published_at", "source"], ascending=[False, False, True], na_position="last")
    if max_results:
        df = df.head(int(max_results))

    out = pd.DataFrame({
        "선택": True,
        "추천도": df["score"].fillna(0).astype(int),
        "기사제목": df["title"].fillna(""),
        "발행시각": df["published_at"].dt.strftime("%Y-%m-%d %H:%M").fillna(""),
        "출처": df["source"].fillna(""),
        "링크": df["link"].fillna(""),
        "요약": df["summary"].fillna(""),
        "카테고리": df["category"].fillna(""),
        "키워드": df["keyword"].fillna(""),
        "추천사유": df["reason"].fillna(""),
        "수집구분": df.get("source_group", pd.Series([""] * len(df))).fillna(""),
        "제외근거": df["exclude_reason"].fillna(""),
    })
    return out.reset_index(drop=True)


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="뉴스취합")
        ws = writer.sheets["뉴스취합"]
        wb = writer.book
        header_fmt = wb.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        link_fmt = wb.add_format({"font_color": "blue", "underline": 1})
        for col_idx, col_name in enumerate(df.columns):
            ws.write(0, col_idx, col_name, header_fmt)
            width = min(max(12, int(df[col_name].astype(str).str.len().quantile(0.90) if len(df) else 12) + 2), 60)
            if col_name == "기사제목": width = 65
            elif col_name == "링크": width = 45
            elif col_name == "요약": width = 70
            ws.set_column(col_idx, col_idx, width)
        if "링크" in df.columns:
            link_col = list(df.columns).index("링크")
            for i, url in enumerate(df["링크"].astype(str).tolist(), start=1):
                if url.startswith("http"):
                    ws.write_url(i, link_col, url, link_fmt, string=url)
        ws.autofilter(0, 0, max(0, len(df)), max(0, len(df.columns) - 1))
        ws.freeze_panes(1, 0)
    return bio.getvalue()


def to_html_report(df: pd.DataFrame, title: str = "Daily News Report") -> str:
    display_df = df.copy()
    if "링크" in display_df.columns:
        display_df["링크"] = display_df["링크"].apply(lambda u: f'<a href="{u}" target="_blank">기사 링크</a>' if str(u).startswith("http") else "")
    table = display_df.to_html(index=False, escape=False)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{title}</title>
<style>body {{ font-family: Arial, 'Malgun Gothic', sans-serif; margin: 28px; }} h1 {{ font-size: 24px; }} table {{ border-collapse: collapse; width: 100%; font-size: 12px; }} th, td {{ border: 1px solid #ddd; padding: 7px; vertical-align: top; }} th {{ background: #eaf3ff; }} tr:nth-child(even) {{ background: #fafafa; }}</style></head>
<body><h1>{title}</h1><p>생성시각: {now_kst().strftime('%Y-%m-%d %H:%M')}</p>{table}</body></html>"""
