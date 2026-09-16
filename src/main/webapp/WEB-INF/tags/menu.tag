<%@ tag pageEncoding="UTF-8" %>
<%@ taglib prefix="spring" uri="http://www.springframework.org/tags" %>
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %>
<%@ taglib prefix="petclinic" tagdir="/WEB-INF/tags" %>
<%@ attribute name="name" required="true" rtexprvalue="true"
              description="Name of the active menu: home, owners, vets or error" %>

<nav class="navbar navbar-default" role="navigation">
    <div class="container">
        <div class="navbar-header">
            <a class="navbar-brand mc-brand" href="<spring:url value="/" htmlEscape="true" />">
                <svg class="mc-brand-paw" viewBox="0 0 32 32" aria-hidden="true" fill="currentColor">
                    <ellipse cx="9" cy="10" rx="3.2" ry="4"/><ellipse cx="23" cy="10" rx="3.2" ry="4"/>
                    <ellipse cx="4.5" cy="17" rx="2.8" ry="3.6"/><ellipse cx="27.5" cy="17" rx="2.8" ry="3.6"/>
                    <path d="M16 15c-5 0-9 4.2-9 8.3 0 2.6 1.9 4.2 4.3 4.2 1.9 0 3.1-1 4.7-1s2.8 1 4.7 1c2.4 0 4.3-1.6 4.3-4.2C25 19.2 21 15 16 15z"/>
                </svg>미션 동물병원<small>Mission Animal Hospital</small>
            </a>
            <button type="button" class="navbar-toggle" data-toggle="collapse" data-target="#main-navbar">
                <span class="sr-only">메뉴 열기</span>
                <span class="icon-bar"></span>
                <span class="icon-bar"></span>
                <span class="icon-bar"></span>
            </button>
        </div>
        <div class="navbar-collapse collapse" id="main-navbar">
            <ul class="nav navbar-nav navbar-right">

                <petclinic:menuItem active="${name eq 'home'}" url="/" title="홈">
                    <span class="glyphicon glyphicon-home" aria-hidden="true"></span>
                    <span>홈</span>
                </petclinic:menuItem>

                <petclinic:menuItem active="${name eq 'owners'}" url="/owners/find" title="보호자·반려동물 조회">
                    <span class="glyphicon glyphicon-search" aria-hidden="true"></span>
                    <span>보호자 조회</span>
                </petclinic:menuItem>

                <petclinic:menuItem active="${name eq 'vets'}" url="/vets" title="수의사 소개">
                    <span class="glyphicon glyphicon-user" aria-hidden="true"></span>
                    <span>수의사</span>
                </petclinic:menuItem>

                <petclinic:menuItem active="${name eq 'error'}" url="/oups" title="오류 페이지 테스트 (RuntimeException)">
                    <span class="glyphicon glyphicon-warning-sign" aria-hidden="true"></span>
                    <span>오류 테스트</span>
                </petclinic:menuItem>

                <li class="mc-nav-cta">
                    <a href="<spring:url value="/owners/new" htmlEscape="true" />" title="보호자 등록 후 진료 예약">진료 예약</a>
                </li>

            </ul>
        </div>
    </div>
</nav>
