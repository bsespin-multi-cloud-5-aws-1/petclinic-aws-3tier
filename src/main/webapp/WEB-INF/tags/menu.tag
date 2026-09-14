<%@ tag pageEncoding="UTF-8" %>
<%@ taglib prefix="spring" uri="http://www.springframework.org/tags" %>
<%@ attribute name="name" required="true" rtexprvalue="true" %>
<a class="skip-link" href="#content">본문 바로가기</a>
<header class="site-header" id="top"><div class="header-inner">
<a class="brand" href="<spring:url value="/" htmlEscape="true" />" aria-label="미션 동물병원 홈"><span class="brand-mark" aria-hidden="true">m<span>+</span></span><span class="brand-name">미션 동물병원<small>MISSION ANIMAL HOSPITAL</small></span></a>
<div class="header-right"><div class="utility-nav"><a href="<spring:url value="/" htmlEscape="true" />#visit">진료시간 · 오시는 길</a><a href="<spring:url value="/owners/find" htmlEscape="true" />">진료기록 조회 ↗</a><span>함께하는 건강한 일상</span></div>
<button class="menu-toggle" aria-expanded="false" aria-controls="main-nav" type="button">메뉴 <span aria-hidden="true">☰</span></button>
<nav id="main-nav" class="main-nav" aria-label="주 메뉴"><a href="<spring:url value="/" htmlEscape="true" />#about">병원 소개</a><a href="<spring:url value="/" htmlEscape="true" />#care">진료 안내</a><a href="<spring:url value="/vets" htmlEscape="true" />">수의사 소개</a><a href="<spring:url value="/owners/find" htmlEscape="true" />">보호자 · 반려동물</a><a class="button small light" href="<spring:url value="/owners/new" htmlEscape="true" />">첫 방문 등록 <span>↗</span></a></nav></div>
</div></header>