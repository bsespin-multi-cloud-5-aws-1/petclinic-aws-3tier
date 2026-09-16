<%@ tag pageEncoding="UTF-8" %>
<%@ taglib prefix="spring" uri="http://www.springframework.org/tags" %>

<footer class="mc-footer">
    <div class="container">
        <div class="row">
            <div class="col-md-4">
                <h4>미션 동물병원</h4>
                <p>서울특별시 강남구 테헤란로 123 미션빌딩 1층<br/>
                   대표전화 02-1234-5678 · 응급 010-1234-5678</p>
            </div>
            <div class="col-md-4">
                <h4>진료 시간</h4>
                <ul>
                    <li>평일 09:00 – 20:00</li>
                    <li>토요일 09:00 – 17:00</li>
                    <li>일요일·공휴일 응급 진료만</li>
                </ul>
            </div>
            <div class="col-md-4">
                <h4>바로가기</h4>
                <ul>
                    <li><a href="<spring:url value="/owners/find" htmlEscape="true" />">보호자·반려동물 조회</a></li>
                    <li><a href="<spring:url value="/owners/new" htmlEscape="true" />">보호자 등록 (진료 예약)</a></li>
                    <li><a href="<spring:url value="/vets" htmlEscape="true" />">수의사 소개</a></li>
                </ul>
            </div>
        </div>
        <div class="mc-footer-bottom">
            © 2026 Mission Animal Hospital · KDT 베스핀글로벌 멀티클라우드 5기 1팀 Mission Critical ·
            Built on Spring PetClinic · AWS 3-Tier (CloudFront → ALB → Apache → Tomcat → RDS)
        </div>
    </div>
</footer>

<%-- Placed at the end of the document so the pages load faster --%>
<spring:url value="/webjars/jquery/3.5.1/jquery.min.js" var="jQuery"/>
<script src="${jQuery}"></script>

<%-- jquery-ui.js file is really big so we only load what we need instead of loading everything --%>
<spring:url value="/webjars/jquery-ui/1.12.1/jquery-ui.min.js" var="jQueryUiCore"/>
<script src="${jQueryUiCore}"></script>

<%-- Bootstrap --%>
<spring:url value="/webjars/bootstrap/3.3.6/js/bootstrap.min.js" var="bootstrapJs"/>
<script src="${bootstrapJs}"></script>
