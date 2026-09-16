<%@ page session="false" trimDirectiveWhitespaces="true" pageEncoding="UTF-8" contentType="text/html; charset=UTF-8" %>
<%@ taglib prefix="spring" uri="http://www.springframework.org/tags" %>
<%@ taglib prefix="petclinic" tagdir="/WEB-INF/tags" %>

<petclinic:layout pageName="home">

    <jsp:attribute name="hero">
        <%-- 배경 영상은 WAS가 아니라 CloudFront → S3(mc-images)에서 서빙: /images/hero/hero.mp4 --%>
        <spring:url value="/resources/images/hero-poster.jpg" htmlEscape="true" var="heroPoster"/>
        <section class="mc-hero" id="mc-hero">
            <div class="mc-hero-video" style="background-image: url('${heroPoster}')">
                <video id="mc-hero-video" src="/images/hero/hero.mp4" poster="${heroPoster}"
                       muted autoplay loop playsinline preload="metadata"
                       aria-hidden="true"></video>
            </div>
            <div class="mc-hero-main">
                <div class="mc-hero-wrap">
                    <span class="mc-hero-eyebrow">MISSION ANIMAL HOSPITAL · 24H EMERGENCY</span>
                    <h1>가족의 <span>건강한 하루</span>를 함께 지키는<br/>미션 동물병원</h1>
                    <p class="mc-hero-lead">예방접종·건강검진부터 응급 진료까지.<br class="hidden-xs"/>
                        보호자 정보를 등록하면 반려동물의 진료 기록을 한곳에서 관리할 수 있습니다.</p>
                    <p class="mc-hero-actions">
                        <a class="btn btn-mc-primary" href="<spring:url value="/owners/new" htmlEscape="true" />">진료 예약하기</a>
                        <a class="btn btn-mc-ghost" href="<spring:url value="/vets" htmlEscape="true" />">수의사 소개</a>
                    </p>
                </div>
            </div>
            <p class="mc-hero-controls">
                <button type="button" id="mc-hero-toggle" aria-label="배경 영상 일시정지"><span class="glyphicon glyphicon-pause"></span></button>
            </p>
        </section>
    </jsp:attribute>

    <jsp:attribute name="customScript">
        <script>
            (function () {
                var v = document.getElementById('mc-hero-video'), b = document.getElementById('mc-hero-toggle');
                if (!v || !b) return;
                v.addEventListener('error', function () { v.style.display = 'none'; b.style.display = 'none'; });
                b.addEventListener('click', function () {
                    if (v.paused) { v.play(); b.firstChild.className = 'glyphicon glyphicon-pause'; b.setAttribute('aria-label', '배경 영상 일시정지'); }
                    else { v.pause(); b.firstChild.className = 'glyphicon glyphicon-play'; b.setAttribute('aria-label', '배경 영상 재생'); }
                });
            })();
        </script>
    </jsp:attribute>

    <jsp:body>
        <div class="mc-home-body">
            <div class="mc-info-strip">
                <div class="row">
                    <div class="col-md-4"><div class="mc-info-item">
                        <div class="mc-info-icon"><span class="glyphicon glyphicon-time"></span></div>
                        <div><strong>진료 시간</strong><p>평일 09:00–20:00 · 토 09:00–17:00<br/>일·공휴일은 응급 진료</p></div>
                    </div></div>
                    <div class="col-md-4"><div class="mc-info-item">
                        <div class="mc-info-icon"><span class="glyphicon glyphicon-earphone"></span></div>
                        <div><strong>24시간 응급</strong><p>02-1234-5678<br/>야간·주말 응급 010-1234-5678</p></div>
                    </div></div>
                    <div class="col-md-4"><div class="mc-info-item">
                        <div class="mc-info-icon"><span class="glyphicon glyphicon-map-marker"></span></div>
                        <div><strong>오시는 길</strong><p>서울 강남구 테헤란로 123 미션빌딩 1층<br/>지하 주차 2시간 무료</p></div>
                    </div></div>
                </div>
            </div>

            <h2 class="mc-section-title">진료 안내</h2>
            <p class="mc-section-lead">반려동물의 생애 주기에 맞춘 진료를 제공합니다.</p>
            <div class="row mc-card-row">
                <div class="col-md-4 col-sm-6">
                    <a class="mc-card" href="<spring:url value="/owners/find" htmlEscape="true" />">
                        <div class="mc-card-icon"><span class="glyphicon glyphicon-search"></span></div>
                        <h3>보호자 · 반려동물 조회</h3>
                        <p>보호자 성(姓)으로 등록된 반려동물과 진료(방문) 이력을 확인합니다.</p>
                        <span class="mc-card-link">조회하기 →</span>
                    </a>
                </div>
                <div class="col-md-4 col-sm-6">
                    <a class="mc-card" href="<spring:url value="/owners/new" htmlEscape="true" />">
                        <div class="mc-card-icon"><span class="glyphicon glyphicon-calendar"></span></div>
                        <h3>진료 예약 · 보호자 등록</h3>
                        <p>처음 방문이라면 보호자 정보를 등록하고 반려동물을 추가한 뒤 방문 일정을 잡습니다.</p>
                        <span class="mc-card-link">등록하기 →</span>
                    </a>
                </div>
                <div class="col-md-4 col-sm-6">
                    <a class="mc-card" href="<spring:url value="/vets" htmlEscape="true" />">
                        <div class="mc-card-icon"><span class="glyphicon glyphicon-user"></span></div>
                        <h3>수의사 소개</h3>
                        <p>내과·외과·치과·방사선 전문 수의사가 함께 진료합니다. 전문 분야를 확인해 보세요.</p>
                        <span class="mc-card-link">수의사 보기 →</span>
                    </a>
                </div>
            </div>

            <div class="row mc-card-row">
                <div class="col-md-4 col-sm-6">
                    <div class="mc-card">
                        <div class="mc-card-icon"><span class="glyphicon glyphicon-heart"></span></div>
                        <h3>예방접종 · 건강검진</h3>
                        <p>연령별 종합 백신, 심장사상충 예방, 연 1회 혈액·영상 검진 프로그램.</p>
                    </div>
                </div>
                <div class="col-md-4 col-sm-6">
                    <div class="mc-card">
                        <div class="mc-card-icon"><span class="glyphicon glyphicon-plus-sign"></span></div>
                        <h3>내과 · 외과 수술</h3>
                        <p>중성화, 슬개골, 종양 제거 등 외과 수술과 입원 집중 관리.</p>
                    </div>
                </div>
                <div class="col-md-4 col-sm-6">
                    <div class="mc-card">
                        <div class="mc-card-icon"><span class="glyphicon glyphicon-bell"></span></div>
                        <h3>24시간 응급 진료</h3>
                        <p>야간·주말에도 응급 수의사가 상주합니다. 내원 전 전화 주시면 준비해 두겠습니다.</p>
                    </div>
                </div>
            </div>
        </div>
    </jsp:body>
</petclinic:layout>
