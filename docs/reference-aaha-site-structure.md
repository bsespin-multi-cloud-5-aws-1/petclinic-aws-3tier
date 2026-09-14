# aaha.org 웹사이트 구조 분석 (참고용)

- 분석일: 2026-09-14 · 대상: https://www.aaha.org/ 홈페이지 · 방법: 브라우저에서 DOM · 계산된 CSS 규칙 추출
- 용도: PetClinic 첫 화면 리디자인 참고. **원본 CSS/HTML 원문은 저작물이므로 옮기지 않았고, 구조·규칙·토큰만 정리.** 실제 코드는 DevTools → Sources → `wp-content/themes/aaha/_html/source/assets/styles/app.css` 에서 확인.

---

## 1. 기술 스택

| 구분 | 내용 |
|---|---|
| CMS | WordPress · 자체 테마 `aaha` (부모 테마 `fritz`) · jQuery 동봉 |
| CSS | 단일 컴파일 파일 `app.css` (규칙 약 2,200개) + 아이콘 폰트 `icomoon.woff` |
| 폰트 | Adobe Typekit `use.typekit.net/rti6xwt.css` — 본문 `tenon`(→ Helvetica Neue, Arial) · 세리프 `utopia-std`, `utopia-std-display`(→ Georgia) |
| JS | `libs.js` + `app.js`(테마) · Alpine.js 문법(`x-data`, `x-effect`, `@click`) · lazysizes(`lazyload` 클래스) · 자체 `reveal` 스크롤 애니메이션 |
| 서드파티 | GTM · HubSpot(CTA 팝업·폼·챗) · Usercentrics(쿠키 배너) · reCAPTCHA · Facebook/LinkedIn 픽셀 · StackAdapt · Hotjar |
| 브레이크포인트 | `719px` / `1023px` / `1521px` · `orientation` 쿼리 · `prefers-reduced-motion` |

---

## 2. HTML 구조 (랜드마크 트리)

```
body.home.page-template-default.page …
└─ div.root1
   ├─ header#top.top1 -cs:i
   │   └─ div.top1-wrap -restrain
   │       ├─ p.logo1 > a > svg                 로고 (흰색 + 빨강 #c02043)
   │       ├─ nav.skips1 > ul (3)               스킵 링크 (accesskey n/c/f)
   │       ├─ p.top1-toggler -search > a.icon-search-bold
   │       ├─ p.top1-toggler -menu   > a.icon-menu-bold
   │       └─ nav.nav1
   │           ├─ ul.nav1-main -t:21 (6)        주 메뉴 (About / For Professionals / …)
   │           └─ ul.nav1-side -t:11 (7)        보조 메뉴 (AAHA CON / Learning / Store / Sign in / Trends)
   ├─ div#search.drawer1 -top -search           검색 서랍 (p.drawer1-close + div.drawer1-wrap)
   ├─ section#content.content1
   │   ├─ div.hero1                             ★ 영상 히어로 (§4)
   │   ├─ div.wrap1 -py:1 -cs:b6 -cs:i -paw     자주 배경 + 발자국 패턴 → div.highlights1 (image-wrap / action / text)
   │   ├─ div.wrap1 -py:1 -cs:b6                whats-new (카드 3열: .whats-new-card > .overlink + .whats-new-image.-rounded + title/lead)
   │   ├─ div.wrap1 -py:2 -cs:b3 -breakout      promo (이미지 + 텍스트, -flip 으로 좌우 반전)
   │   ├─ div.wrap1 -py:2 -cs:b7 -cs:i          진자주 배경 섹션
   │   ├─ div.wrap1 -mt:2 -mb:2 -breakout       전체폭 섹션
   │   ├─ div.wrap1.event-cards                 이벤트 카드(.card1 -boxed, .label1, .icon-cat)
   │   ├─ h5 -mt:4 -ta:c                        소제목
   │   └─ div.carousel1 -breakout               로고/후기 캐러셀 (icon-angle-left/right-bold)
   ├─ footer#footer.footer1 -mt:1
   │   └─ div.footer1-wrap -restrain
   │       ├─ div.footer1-signup                뉴스레터 박스 2개 (.signup1 -cs:b7 / -cs:b8)
   │       └─ div.footer1-bottom                .footer1-follow(SNS) · .footer1-questions(연락) · .footer1-notes(저작권·링크)
   ├─ div#sidenav.sidenav1 -cs:i -cs:b7         모바일 사이드 메뉴 (header + wrap)
   ├─ div.flyout1 > div.flyout1-box             플라이아웃
   └─ a.overlay1 / a.overlay2 -as:0             오버레이 (메뉴·검색 열렸을 때 배경 클릭 닫기)
+ body 직속: HubSpot 앵커 div들, iframe(광고·챗), div.toaster1, grecaptcha-badge
```

- 제목 계층: `h1` 1개(히어로) → 섹션은 `h2~h5`.
- 각 섹션은 `div.wrap1[유틸리티]` > `div.wrap1-inner.-restrain` > 컴포넌트 패턴으로 통일.

---

## 3. CSS 설계 체계

### 3-1. 명명 규칙
- **블록 + 숫자 접미사**: `hero1`, `wrap1`, `card1`, `footer1`, `signup1`, `carousel1` … 자식은 `블록-요소` (`hero1-wrap`, `footer1-bottom`). BEM의 변형.
- **`-` 접두 유틸리티 수정자** (자체 규칙, `:` 로 값 지정):

| 클래스 | 의미 | 비고 |
|---|---|---|
| `-restrain` | 가운데 컨테이너 `max-width ≈ 1190px` | `.wrap1-inner`, `.top1-wrap`, `.footer1-wrap` |
| `-breakout` | 컨테이너를 뚫고 전체폭 | 캐러셀·프로모 |
| `-cs:b1`~`-cs:b8` | 배경 컬러 스킴 (§3-2 `--c_b*`) | 섹션 배경색 |
| `-cs:i` | invert — 흰 글씨 스킴 | 어두운 배경 섹션과 짝 |
| `-py:1` `-pt:0` `-pb:2` `-mt:4` `-mb:2` | padding/margin 스케일 | `--s05`=2rem `--s1`=4rem `--s2`=6.4rem `--s3`=8rem `--s4`=9.6rem `--s5`=12rem |
| `-t:2` `-t:11` `-t:17` `-t:21` | 타이포 스케일 (숫자 = 프리셋 번호) | h1은 `-t:2` |
| `-ta:c` | text-align center | |
| `-xw:4` | 최대 폭 제한 | 히어로 텍스트 |
| `-as:0` | 접근성 숨김(시각적 제거) | 스킵링크·오버레이 |
| `-us:n` | user-select none | 버튼 |
| `-rounded` `-boxed` `-ghost` `-flip` `-paw` `-cover` | 모양/변형 | 카드 둥글게 · 박스 · 외곽선 버튼 · 좌우반전 · 발자국 패턴 · 꽉 채움 |
| `[reveal="2+/1"]` | 스크롤 진입 시 순차 페이드인(속성 셀렉터) | `--rvd` 로 지연 |

### 3-2. 디자인 토큰 (`:root` CSS 변수)

**배경 팔레트 `--c_b1 ~ b8`**

| 변수 | 값 | 느낌 |
|---|---|---|
| `--c_b1` | `#ffffff` | 흰색 |
| `--c_b2` | `#ede2d8` | 베이지 |
| `--c_b3` | `#f5eee8` | 연베이지(섹션 배경) |
| `--c_b4` | `#ebc8e3` | 연분홍 |
| `--c_b5` | `#91d7d2` | 민트(밑줄 강조) |
| `--c_b6` | `#69045c` | **자주 — 메인 브랜드** |
| `--c_b7` | `#400035` | **진자주 — 헤더·푸터** |
| `--c_b8` | `#00403e` | 진녹 |

**강조 팔레트 `--c_a1 ~ a9`**: `#bf6f10`(주황) · `--c_b5`(민트) · `--c_b4`(분홍) · `#4367a6`(파랑) · `#f4b136`(노랑) · `#008b86`(청록) · `#4e586a`(회청) · `#8aa34b`(올리브) · `#bf2043`(빨강, 로고)

**기타**
- 텍스트: `--c_d1: #2A2D33` (거의 검정) · 반전 텍스트 `--c_i1: #fff`, `--c_i2: #ccc`
- 폰트: `--ff_1: tenon…` `--ff_2: utopia-std…` `--ff_3: utopia-std-display…`
- 유동 단위: `--us: 1366`(기준 폭) → `--uu: calc(10 / var(--us) * 100vw)` — 글자·간격이 뷰포트 비례
- 간격: `--sx`(가로 4rem) `--sy`(세로 min(1.2em, 2.4rem)) `--nx/--ny`(음수)
- 모서리: `--br_3` (히어로 다음 섹션 상단 둥근 모서리)

### 3-3. 계산된 대표 스타일

| 요소 | 값 |
|---|---|
| body | `tenon` 17.6px · `#2A2D33` |
| h1 | 46px · 700 · 흰색 |
| 컨테이너 | `max-width 1190.92px` |
| 버튼 | 14.8px · 700 · `border-radius 4px` · padding `0 18px 0 9px` |
| 헤더 | 투명(진자주 섹션 위) · 흰 글씨 |
| 푸터 | padding `37px 0` |

---

## 4. 히어로 배경 영상 구조 ★

### 4-1. HTML
```html
<div class="hero1" x-data="{playing: true}" :class="{'-paused': !playing}">
  <!-- 배경 영상 2벌 (가로/세로), 같은 mp4 1920×1080 -->
  <span class="img1 hero1-video -landscape -cover" style="--w:1440; --rl:0.625">
    <video src="…/Website-Video_V5_1.mp4" muted playsinline loop autoplay preload="auto"
           x-effect="$el[playing ? 'play' : 'pause']()"></video>
    <i class="loader1"></i>
  </span>
  <span class="img1 hero1-video -portrait -cover" style="--w:420; --rl:2.333">
    <video src="…같은 파일…" muted playsinline loop autoplay preload="none" class="lazyload"></video>
  </span>

  <!-- 전경 텍스트 -->
  <div class="hero1-main -cs:i">
    <div class="hero1-wrap -restrain -xw:4">
      <h1 class="hero1-title -t:2" reveal="2+/1">… <span>simplifies the journey</span> …</h1>
      <p class="hero1-action" reveal="2+/2">
        <a href="https://www.youtube.com/watch?v=…" class="button1 -b1 -ghost" lightbox="#hero1video"><i class="icon-play"></i><span>Play</span></a>
      </p>
    </div>
  </div>

  <!-- 재생/정지 토글 -->
  <p class="hero1-controls -t:17" reveal="1+/3">
    <span clickable @click.prevent="playing = !playing" class="-us:n"><i :class="{'icon-play': !playing, 'icon-pause': playing}"></i></span>
  </p>
</div>
```

### 4-2. CSS 규칙 (app.css에서 추출한 핵심)
```css
/* ① 컨테이너: grid 1칸, 화면 높이 기준, 넘침 숨김 */
.hero1        { --sy: 0; display: grid; position: relative; overflow: hidden;
                min-height: calc(100svh - 10rem); margin-bottom: calc(var(--br_3) * -1); }
.hero1 > *    { grid-area: 1 / 1 / 2 / 2; }        /* 자식 전부 같은 칸에 겹침 */

/* ② 영상 레이어: 절대배치로 꽉 채움 */
.img1         { display: block; position: relative; overflow: hidden; width: 100%; will-change: transform, opacity; }
.img1.-cover  { position: absolute; left: 0; top: 0; height: 100%; margin: 0; }
.hero1-video  { background: #000; color: var(--c_i1); }
.hero1-video video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
[js] .hero1-video[class] video { transition-duration: 3s; }

/* ③ 어둡게 하는 막 — 영상 위, 텍스트 아래 */
.hero1-video::after { content: ""; position: absolute; inset: 0; background: rgba(0,0,0,.55); }

/* ④ 가로/세로 화면에 따라 한 벌만 표시 */
@media screen and (orientation: portrait)  { .hero1-video.-landscape { display: none; } }
@media screen and (orientation: landscape) { .hero1-video.-portrait  { display: none; } }

/* ⑤ 텍스트 레이어 */
.hero1-main   { --sy: 0; display: flex; align-items: center; justify-content: center; position: relative;
                padding: var(--s4) 0 var(--br_3); color: var(--c_d1t); text-align: center; }
.hero1-wrap   { flex: 0 0 auto; padding: var(--s5) 0; }
.hero1-title span { background: linear-gradient(var(--c_a2t), var(--c_a2t)) 0 90% / 100% .05em no-repeat; } /* 민트 밑줄 */
.hero1-action .button1 { padding-left: 1rem; padding-right: 2rem; }
.hero1-action .button1 i { font-size: 2em; }

/* ⑥ 재생 버튼: 왼쪽 아래, 원형 테두리 */
.hero1-controls { --lh: 1; position: relative; align-self: flex-end; left: 2rem;
                  bottom: calc(var(--br_3) + 2rem); z-index: 2; isolation: isolate; color: var(--c_i1); }
.hero1-controls i[class] { display: flex; justify-content: center; align-items: center; width: 1em; height: 1em;
                  padding-left: .5px; border-radius: 50%; box-shadow: inset 0 0 0 1px var(--c_i1); font-size: 3.2rem; }

/* ⑦ 다음 섹션이 히어로 위로 둥글게 올라옴 */
.hero1 + .wrap1 { border-top-right-radius: var(--br_3); }

/* 인쇄 */
@media print { .hero1 { margin-bottom: 0; } .hero1-video { background: none; opacity: .2; } }
```

### 4-3. 동작 요약

| 요소 | 역할 |
|---|---|
| `muted autoplay loop playsinline` | 브라우저 자동재생 정책 충족(음소거 필수) · 모바일 인라인 재생 |
| `object-fit: cover` | 1920×1080 영상을 어떤 화면 비율에도 잘라서 꽉 채움 |
| `::after` 검은 55% 막 | 영상 위 흰 글씨 가독성 |
| 가로/세로 2벌 + `lazyload` | 세로용은 `preload="none"` → 필요할 때만 다운로드 |
| Alpine.js `x-data / x-effect / @click` | 재생·정지 버튼 상태 ↔ `video.play()/pause()` |
| `reveal="2+/1"` | 스크롤 진입 시 텍스트 순차 페이드인 (`--rvd` 지연) |
| `prefers-reduced-motion` | 움직임 줄이기 설정 시 전환 끔 |
| `--w`, `--rl` 인라인 변수 | 이미지/영상 고유 폭·비율 → 레이아웃 시프트 방지 |

---

## 5. PetClinic에 적용할 때 (제안)

- Alpine · lazysizes 없이 **①~⑤**만으로 동일 효과. `welcome.jsp` 상단에 `<section class="hero">` + `<video muted autoplay loop playsinline>` + `::after` 막 + 텍스트, CSS 20줄.
- 영상은 WAR가 아니라 **S3 `mc-images` → CloudFront `/images/*` Behavior**로 서빙 → WAS 트래픽에 안 잡히고 "정적은 CDN" 설계와 일치. 첫 프레임 `poster` 이미지는 같은 버킷.
- 팔레트는 `--c_b6 #69045c`(자주) · `--c_b7 #400035`(진자주) · `--c_b5 #91d7d2`(민트) 3개만 가져와도 충분.
- 동반 파일: `reference-aaha-hero-skeleton.html` — 위 구조를 자체 CSS로 재구성한 독립 실행 예시(스톡 영상 URL만 바꾸면 됨).
