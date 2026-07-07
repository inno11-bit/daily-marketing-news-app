# 업무 뉴스 취합 자동화 v5.2 Mobile

종합 광고대행사용 Daily Intelligence 앱입니다.

## v5.2 변경사항

- 아이폰 카드형 보기 추가
- 모바일 화면 최적화 CSS 적용
- PC 표 검수 모드 유지
- 결과표 기본 컬럼 순서 유지
  - 선택 / 추천도 / 기사제목 / 발행시각 / 출처 / 링크 / 요약 / 카테고리 / 키워드
- 아이폰 홈 화면 추가 안내 포함

## 실행

```cmd
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

또는 Windows에서 `start_daily_news_app.bat` 실행.

## 아이폰에서 앱처럼 쓰는 방법

1. 앱을 서버 또는 사내 PC에서 실행합니다.
2. 아이폰 Safari에서 앱 주소로 접속합니다.
3. 공유 버튼 → 홈 화면에 추가.

주의: `localhost:8501`은 PC 자기 자신을 뜻하므로 아이폰에서는 PC의 내부 IP 또는 배포 주소로 접속해야 합니다.
