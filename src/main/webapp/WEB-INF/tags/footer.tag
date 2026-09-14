<%@ tag pageEncoding="UTF-8" %>
<%@ taglib prefix="spring" uri="http://www.springframework.org/tags" %>
<footer class="site-footer" id="footer"><div class="wrap"><div class="footer-top"><a class="brand" href="<spring:url value="/" htmlEscape="true" />"><span class="brand-mark" aria-hidden="true">m<span>+</span></span><span class="brand-name">미션 동물병원<small>MISSION ANIMAL HOSPITAL</small></span></a><p>작은 생명에게 큰 진심을.<br>함께하는 오늘, 더 건강한 내일.</p><nav aria-label="하단 메뉴"><a href="<spring:url value="/owners/find" htmlEscape="true" />">보호자 조회 ↗</a><a href="<spring:url value="/vets" htmlEscape="true" />">수의사 소개 ↗</a><a href="<spring:url value="/" htmlEscape="true" />#visit">진료시간 · 오시는 길 ↗</a></nav></div><div class="footer-bottom"><span>© 2026 Mission Animal Hospital</span><span>소중한 가족의 모든 순간에 함께합니다.</span><a href="#top">맨 위로 ↑</a></div></div></footer>
<%-- Placed at the end of the document so the pages load faster --%>
<spring:url value="/webjars/jquery/3.5.1/jquery.min.js" var="jQuery"/>
<script src="${jQuery}"></script>

<%-- jquery-ui.js file is really big so we only load what we need instead of loading everything --%>
<spring:url value="/webjars/jquery-ui/1.12.1/jquery-ui.min.js" var="jQueryUiCore"/>
<script src="${jQueryUiCore}"></script>

<%-- Bootstrap --%>
<spring:url value="/webjars/bootstrap/3.3.6/js/bootstrap.min.js" var="bootstrapJs"/>
<script src="${bootstrapJs}"></script>

<spring:url value="/resources/js/mission.js" var="missionJs"/><script src="${missionJs}" defer></script>