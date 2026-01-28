<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<%
    String username = request.getParameter("username");
    String type = request.getParameter("type");
%>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>账号申诉</title>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/appeal.css">
</head>
<body>
    <div class="appeal-container">
        <div class="appeal-card">
            <h1>📝 账号申诉</h1>
            <p class="subtitle">请填写以下信息提交申诉，我们会尽快处理</p>

            <form action="appeal" method="post">
                <div class="form-group">
                    <label>用户名</label>
                    <input type="text" name="username" value="<%= username != null ? username : "" %>" readonly class="form-control">
                </div>

                <div class="form-group">
                    <label>账号密码 <span class="required">*</span></label>
                    <input type="password" name="password" required class="form-control" placeholder="请输入密码以验证身份">
                </div>

                <input type="hidden" name="appealType" value="<%= type %>">

                <div class="form-group">
                    <label>联系邮箱 <span class="required">*</span></label>
                    <input type="email" name="contactEmail" required class="form-control" placeholder="用于接收审批结果通知">
                </div>

                <div class="form-group">
                    <label>申诉原因 <span class="required">*</span></label>
                    <textarea name="reason" required class="form-control" rows="6" placeholder="请详细说明申诉原因..."></textarea>
                </div>

                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="window.location.href='index.jsp'">取消</button>
                    <button type="submit" class="btn btn-primary">提交申诉</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
