<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" import="java.util.*,java.io.*,java.net.*,java.sql.*" %>
<%!
  // WEB-WAS-DB 연동 및 요청 전달 확인용 (OT 제공 test.jsp 목적 동일). DB 접속정보는 WAR 안의 data-access.properties에서 읽음
  private String h(String s){ return s==null ? "-" : s.replace("&","&amp;").replace("<","&lt;"); }
  private String mask(String s){ return (s==null||s.length()<6) ? "(설정)" : s.substring(0,3)+"***"; }
%>
<%
  Properties p = new Properties();
  try (InputStream in = application.getResourceAsStream("/WEB-INF/classes/spring/data-access.properties")) { if (in != null) p.load(in); }
  String url = p.getProperty("jdbc.url",""), user = p.getProperty("jdbc.username",""), pw = p.getProperty("jdbc.password","");
  String dbStatus, dbHost = url.replaceAll("jdbc:mysql://([^:/]+).*", "$1"), vets = "-", version = "-", ssl = "-";
  long t0 = System.currentTimeMillis();
  try {
    Class.forName("com.mysql.cj.jdbc.Driver");
    try (Connection c = DriverManager.getConnection(url, user, pw); Statement st = c.createStatement()) {
      try (ResultSet rs = st.executeQuery("SELECT COUNT(*) FROM vets")) { if (rs.next()) vets = rs.getString(1); }
      try (ResultSet rs = st.executeQuery("SELECT VERSION()")) { if (rs.next()) version = rs.getString(1); }
      try (ResultSet rs = st.executeQuery("SHOW STATUS LIKE 'Ssl_cipher'")) { if (rs.next()) ssl = rs.getString(2); }
      dbStatus = "OK (" + (System.currentTimeMillis()-t0) + " ms)";
    }
  } catch (Exception e) { dbStatus = "FAIL: " + h(e.getClass().getSimpleName() + ": " + e.getMessage()); }
  String host = "-", ip = "-";
  try { InetAddress a = InetAddress.getLocalHost(); host = a.getHostName(); ip = a.getHostAddress(); } catch (Exception ignore) {}
%>
<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>test.jsp - WEB/WAS/DB 연동 확인</title>
<style>body{font-family:Arial,sans-serif;margin:32px;color:#222}h1{font-size:20px}table{border-collapse:collapse;margin:12px 0 24px}td,th{border:1px solid #ccc;padding:6px 12px;text-align:left;font-size:14px}th{background:#f3f3f3;width:220px}.ok{color:#1a7f37;font-weight:bold}.fail{color:#b00020;font-weight:bold}</style></head><body>
<h1>Mission Critical Pet Clinic — test.jsp</h1>
<h2>1. WAS (이 요청을 처리한 서버)</h2>
<table>
<tr><th>호스트 / 사설 IP</th><td><%= h(host) %> / <%= h(ip) %></td></tr>
<tr><th>Java</th><td><%= h(System.getProperty("java.vendor")) %> <%= h(System.getProperty("java.version")) %> (<%= h(System.getProperty("java.runtime.name")) %>)</td></tr>
<tr><th>Servlet 컨테이너</th><td><%= h(application.getServerInfo()) %></td></tr>
<tr><th>서버 시각</th><td><%= new java.util.Date() %></td></tr>
</table>
<h2>2. 요청 전달 (WEB → Internal ALB → WAS 헤더)</h2>
<table>
<tr><th>클라이언트 → ALB 공인 IP (X-Forwarded-For)</th><td><%= h(request.getHeader("X-Forwarded-For")) %></td></tr>
<tr><th>X-Forwarded-Proto</th><td><%= h(request.getHeader("X-Forwarded-Proto")) %></td></tr>
<tr><th>Host (ProxyPreserveHost)</th><td><%= h(request.getHeader("Host")) %></td></tr>
<tr><th>CloudFront 경유 (Via)</th><td><%= h(request.getHeader("Via")) %></td></tr>
<tr><th>WAS가 본 원격 주소</th><td><%= h(request.getRemoteAddr()) %> (Apache/ALB 사설 IP)</td></tr>
<tr><th>User-Agent</th><td><%= h(request.getHeader("User-Agent")) %></td></tr>
</table>
<h2>3. DB (WAS → RDS Proxy → RDS MySQL)</h2>
<table>
<tr><th>접속 대상</th><td><%= h(dbHost) %> (user: <%= h(user) %>, password: <%= mask(pw) %>)</td></tr>
<tr><th>연결 상태</th><td class="<%= dbStatus.startsWith("OK") ? "ok" : "fail" %>"><%= dbStatus %></td></tr>
<tr><th>MySQL 버전</th><td><%= h(version) %></td></tr>
<tr><th>TLS (Ssl_cipher)</th><td><%= h(ssl) %></td></tr>
<tr><th>vets 테이블 행 수</th><td><%= h(vets) %></td></tr>
</table>
<p><a href="/petclinic/">← PetClinic 홈</a> · <a href="/petclinic/vets.json">/vets.json</a></p>
</body></html>
