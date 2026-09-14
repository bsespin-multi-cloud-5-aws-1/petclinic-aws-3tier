<%@ tag pageEncoding="UTF-8" %>
<%@ tag trimDirectiveWhitespaces="true" %>
<%@ taglib prefix="petclinic" tagdir="/WEB-INF/tags" %>

<%@ attribute name="pageName" required="true" %>
<%@ attribute name="hero" required="false" fragment="true" description="풀블리드 히어로 영역(홈 전용). 컨테이너 바깥에 렌더링" %>
<%@ attribute name="customScript" required="false" fragment="true"%>

<!doctype html>
<html lang="ko">
<petclinic:htmlHeader/>

<body>
<petclinic:bodyHeader menuName="${pageName}"/>

<jsp:invoke fragment="hero"/>

<div class="container-fluid">
    <div class="container xd-container">

        <jsp:doBody/>

    </div>
</div>
<petclinic:footer/>
<jsp:invoke fragment="customScript" />

</body>

</html>
