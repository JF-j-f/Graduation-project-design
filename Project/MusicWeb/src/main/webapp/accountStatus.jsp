<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<%
    String status = request.getParameter("status");
    String username = request.getParameter("username");
    String reason = request.getParameter("reason");
    String until = request.getParameter("until");
%>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>账号状态提示</title>
    <link rel="stylesheet" href="css/style.css">
    <style>
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }

        .modal-content {
            background: white;
            padding: 2rem;
            border-radius: 12px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }

        .modal-header {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #dc3545;
        }

        .modal-body {
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }

        .modal-footer {
            display: flex;
            gap: 1rem;
            justify-content: flex-end;
        }

        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.3s;
        }

        .btn-primary {
            background: #667eea;
            color: white;
        }

        .btn-primary:hover {
            background: #5a6fd8;
        }

        .btn-secondary {
            background: #6c757d;
            color: white;
        }

        .btn-secondary:hover {
            background: #5a6268;
        }
    </style>
</head>
<body>
    <div class="modal-overlay">
        <div class="modal-content">
            <div class="modal-header">
                ⚠️ 账号状态异常
            </div>
            <div class="modal-body">
                <% if ("frozen".equals(status)) { %>
                    <p><strong>您的账号已被冻结</strong></p>
                    <p>冻结原因：<%= reason %></p>
                    <p>冻结至：<%= until %></p>
                    <p>如果您认为这是误操作，可以提交申诉。</p>
                <% } else if ("deleted".equals(status)) { %>
                    <p><strong>您的账号已被删除</strong></p>
                    <p>如果您认为这是误操作，可以提交申诉。</p>
                <% } %>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="window.location.href='index.jsp'">返回首页</button>
                <button class="btn btn-primary" onclick="window.location.href='appeal.jsp?username=<%= username %>&type=<%= status %>'">提交申诉</button>
            </div>
        </div>
    </div>
</body>
</html>
