<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<%@ page import="java.util.List" %>
<%@ page import="com.music.javabean.Appeal" %>
<%
    List<Appeal> appeals = (List<Appeal>) request.getAttribute("appeals");
    String message = request.getParameter("message");
    String messageType = request.getParameter("messageType");
%>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>申诉管理 - 管理员后台</title>
    <link rel="stylesheet" href="../css/style.css">
    <style>
        .admin-page { background: #f7fafc; min-height: 100vh; }
        .admin-header { background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; padding: 1rem 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .admin-container { display: flex; max-width: 1400px; margin: 2rem auto; gap: 2rem; padding: 0 2rem; }
        .admin-sidebar { width: 250px; background: #f8f9fa; padding: 1.5rem; border-radius: 8px; height: fit-content; }
        .sidebar-item { width: 100%; padding: 0.75rem 1rem; margin-bottom: 0.5rem; border: none; background: transparent; text-align: left; border-radius: 6px; cursor: pointer; transition: all 0.3s; font-size: 1rem; }
        .sidebar-item:hover { background: #e9ecef; }
        .sidebar-item.active { background: #007bff; color: white; }
        .admin-content { flex: 1; background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .content-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
        .content-header h2 { margin: 0; color: #2d3748; }
        .alert { padding: 1rem; border-radius: 6px; margin-bottom: 1.5rem; }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .appeals-table { width: 100%; border-collapse: collapse; }
        .appeals-table th, .appeals-table td { padding: 1rem; text-align: left; border-bottom: 1px solid #e9ecef; }
        .appeals-table th { background: #f8f9fa; font-weight: 600; color: #2d3748; }
        .appeals-table tr:hover { background: #f8f9fa; }
        .badge { padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.85rem; font-weight: 500; }
        .badge-pending { background: #ffc107; color: #000; }
        .badge-approved { background: #28a745; color: white; }
        .badge-rejected { background: #dc3545; color: white; }
        .badge-frozen { background: #17a2b8; color: white; }
        .badge-deleted { background: #6c757d; color: white; }
        .btn-group { display: flex; gap: 0.5rem; }
        .btn-sm { padding: 0.4rem 0.8rem; font-size: 0.875rem; border: none; border-radius: 4px; cursor: pointer; transition: all 0.3s; }
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover { background: #218838; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover { background: #c82333; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 9999; }
        .modal.show { display: flex; justify-content: center; align-items: center; }
        .modal-dialog { background: white; padding: 2rem; border-radius: 8px; max-width: 500px; width: 90%; }
        .modal-header { margin-bottom: 1rem; }
        .modal-body { margin-bottom: 1.5rem; }
        .modal-footer { display: flex; gap: 1rem; justify-content: flex-end; }
    </style>
</head>
<body class="admin-page">
    <header class="admin-header">
        <div class="nav-container">
            <a href="admin" class="logo" style="color: white;">🔧 管理员后台</a>
            <div class="user-info">
                <span>👤 管理员</span>
                <span class="admin-badge">ADMIN</span>
                <a href="admin?action=dashboard" class="logout-btn" style="background: #28a745;">返回前台</a>
                <a href="${pageContext.request.contextPath}/logout" class="logout-btn">退出登录</a>
            </div>
        </div>
    </header>

    <div class="admin-container">
        <div class="admin-sidebar">
            <button class="sidebar-item" onclick="window.location.href='admin?action=dashboard'">📊 仪表板</button>
            <button class="sidebar-item" onclick="window.location.href='admin?action=users'">👥 用户管理</button>
            <button class="sidebar-item" onclick="window.location.href='admin?action=songs'">🎵 音乐管理</button>
            <button class="sidebar-item" onclick="window.location.href='admin?action=favorites'">❤️ 收藏管理</button>
            <button class="sidebar-item active" onclick="window.location.href='admin?action=appeals'">📝 申诉管理</button>
        </div>

        <div class="admin-content">
            <div class="content-header">
                <h2>📝 申诉管理</h2>
            </div>

            <% if (message != null) { %>
                <div class="alert alert-<%= messageType %>"><%= message %></div>
            <% } %>

            <table class="appeals-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>用户名</th>
                        <th>申诉类型</th>
                        <th>联系邮箱</th>
                        <th>状态</th>
                        <th>提交时间</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    <% if (appeals != null && !appeals.isEmpty()) {
                        for (Appeal appeal : appeals) { %>
                            <tr>
                                <td><%= appeal.getId() %></td>
                                <td><%= appeal.getUsername() %></td>
                                <td>
                                    <span class="badge badge-<%= appeal.getAppealType() %>">
                                        <%= "frozen".equals(appeal.getAppealType()) ? "冻结申诉" : "删除申诉" %>
                                    </span>
                                </td>
                                <td><%= appeal.getContactEmail() %></td>
                                <td>
                                    <span class="badge badge-<%= appeal.getStatus() %>">
                                        <%= "pending".equals(appeal.getStatus()) ? "待处理" :
                                            "approved".equals(appeal.getStatus()) ? "已同意" : "已拒绝" %>
                                    </span>
                                </td>
                                <td><%= appeal.getCreateTime() %></td>
                                <td>
                                    <% if ("pending".equals(appeal.getStatus())) { %>
                                        <div class="btn-group">
                                            <button class="btn-sm btn-success" onclick="showApproveModal(<%= appeal.getId() %>, '<%= appeal.getUsername() %>')">同意</button>
                                            <button class="btn-sm btn-danger" onclick="showRejectModal(<%= appeal.getId() %>, '<%= appeal.getUsername() %>')">拒绝</button>
                                            <button class="btn-sm" onclick="showAppealDetail(<%= appeal.getId() %>)">详情</button>
                                        </div>
                                    <% } else { %>
                                        <button class="btn-sm" onclick="showAppealDetail(<%= appeal.getId() %>)">查看</button>
                                    <% } %>
                                </td>
                            </tr>
                        <% }
                    } else { %>
                        <tr><td colspan="7" style="text-align: center; padding: 2rem;">暂无申诉记录</td></tr>
                    <% } %>
                </tbody>
            </table>
        </div>
    </div>

    <div id="approveModal" class="modal">
        <div class="modal-dialog">
            <div class="modal-header"><h3>同意申诉</h3></div>
            <form id="approveForm">
                <div class="modal-body">
                    <p>确定同意用户 <strong id="approveUsername"></strong> 的申诉吗？</p>
                    <label>回复内容（可选）：</label>
                    <textarea name="reply" rows="3" style="width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px;"></textarea>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn-sm" onclick="closeModal('approveModal')">取消</button>
                    <button type="button" class="btn-sm btn-success" onclick="submitApprove()">确认同意</button>
                </div>
            </form>
        </div>
    </div>

    <div id="rejectModal" class="modal">
        <div class="modal-dialog">
            <div class="modal-header"><h3>拒绝申诉</h3></div>
            <form id="rejectForm">
                <div class="modal-body">
                    <p>确定拒绝用户 <strong id="rejectUsername"></strong> 的申诉吗？</p>
                    <label>拒绝原因（可选）：</label>
                    <textarea name="reply" rows="3" style="width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px;"></textarea>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn-sm" onclick="closeModal('rejectModal')">取消</button>
                    <button type="button" class="btn-sm btn-danger" onclick="submitReject()">确认拒绝</button>
                </div>
            </form>
        </div>
    </div>

    <div id="detailModal" class="modal">
        <div class="modal-dialog">
            <div class="modal-header"><h3>申诉详情</h3></div>
            <div class="modal-body">
                <p><strong>申诉原因：</strong></p>
                <p id="detailReason" style="white-space: pre-wrap;"></p>
                <div id="detailReplySection" style="display: none; margin-top: 1rem;">
                    <p><strong>管理员回复：</strong></p>
                    <p id="detailReply" style="white-space: pre-wrap;"></p>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-sm" onclick="closeModal('detailModal')">关闭</button>
            </div>
        </div>
    </div>

    <script>
        const contextPath = '${pageContext.request.contextPath}';
        let currentAppealId = null;

        function showApproveModal(id, username) {
            currentAppealId = id;
            document.getElementById('approveUsername').textContent = username;
            document.getElementById('approveModal').classList.add('show');
        }

        function showRejectModal(id, username) {
            currentAppealId = id;
            document.getElementById('rejectUsername').textContent = username;
            document.getElementById('rejectModal').classList.add('show');
        }

        function submitApprove() {
            const form = document.getElementById('approveForm');
            const formData = new FormData(form);
            const params = new URLSearchParams(formData);

            fetch(contextPath + '/admin?action=approveAppeal&id=' + currentAppealId, {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: params
            }).then(response => {
                if (response.ok) {
                    window.location.href = contextPath + '/admin?action=appeals';
                } else {
                    alert('操作失败');
                }
            }).catch(() => {
                alert('操作失败');
            });
        }

        function submitReject() {
            const form = document.getElementById('rejectForm');
            const formData = new FormData(form);
            const params = new URLSearchParams(formData);

            fetch(contextPath + '/admin?action=rejectAppeal&id=' + currentAppealId, {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: params
            }).then(response => {
                if (response.ok) {
                    window.location.href = contextPath + '/admin?action=appeals';
                } else {
                    alert('操作失败');
                }
            }).catch(() => {
                alert('操作失败');
            });
        }

        function showAppealDetail(appealId) {
            // 显示加载提示
            document.getElementById('detailReason').textContent = '正在加载...';
            document.getElementById('detailReplySection').style.display = 'none';
            document.getElementById('detailModal').classList.add('show');

            fetch(contextPath + '/admin?action=getAppealDetail&id=' + appealId)
                .then(response => {
                    if (response.ok) {
                        return response.json();
                    } else if (response.status === 404) {
                        throw new Error('申诉记录不存在');
                    } else {
                        throw new Error('获取申诉详情失败');
                    }
                })
                .then(data => {
                    document.getElementById('detailReason').textContent = data.reason || '无申诉原因';
                    if (data.adminReply) {
                        document.getElementById('detailReply').textContent = data.adminReply;
                        document.getElementById('detailReplySection').style.display = 'block';
                    } else {
                        document.getElementById('detailReplySection').style.display = 'none';
                    }
                })
                .catch(error => {
                    document.getElementById('detailReason').textContent = '错误：' + error.message;
                    document.getElementById('detailReplySection').style.display = 'none';
                });
        }

        function showDetailModal(reason, reply) {
            document.getElementById('detailReason').textContent = reason;
            if (reply) {
                document.getElementById('detailReply').textContent = reply;
                document.getElementById('detailReplySection').style.display = 'block';
            } else {
                document.getElementById('detailReplySection').style.display = 'none';
            }
            document.getElementById('detailModal').classList.add('show');
        }

        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('show');
        }
    </script>
</body>
</html>
