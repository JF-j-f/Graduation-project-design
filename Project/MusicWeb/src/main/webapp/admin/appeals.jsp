<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="java.util.List" %>
        <%@ page import="com.music.javabean.Appeal" %>
            <% List<Appeal> appeals = (List<Appeal>) request.getAttribute("appeals");
                    String message = request.getParameter("message");
                    String messageType = request.getParameter("messageType");
                    %>
                    <!DOCTYPE html>
                    <html lang="zh-CN">

                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>申诉管理 - MusicWeb Admin</title>
                        <link rel="stylesheet" href="${pageContext.request.contextPath}/css/admin/admin.css">
                        <link rel="stylesheet" href="${pageContext.request.contextPath}/css/admin/appeals.css">
                    </head>

                    <body class="admin-page">
                        <div class="admin-sidebar">
                            <div class="sidebar-logo">Music<span>Web</span></div>
                            <div class="sidebar-menu">
                                <a href="${pageContext.request.contextPath}/admin?action=dashboard"
                                    class="sidebar-item"><span class="sidebar-item-icon">&#x1F4CA;</span> 仪表盘</a>
                                <a href="${pageContext.request.contextPath}/admin?action=users"
                                    class="sidebar-item"><span class="sidebar-item-icon">&#x1F465;</span> 用户管理</a>
                                <a href="${pageContext.request.contextPath}/admin?action=songs"
                                    class="sidebar-item"><span class="sidebar-item-icon">&#x1F3B5;</span> 歌曲管理</a>
                                <a href="${pageContext.request.contextPath}/admin?action=playlists"
                                    class="sidebar-item"><span class="sidebar-item-icon">&#x1F4CB;</span> 歌单管理</a>
                                <a href="${pageContext.request.contextPath}/admin?action=appeals"
                                    class="sidebar-item active"><span class="sidebar-item-icon">&#x1F4DD;</span>
                                    申诉管理</a>
                            </div>
                        </div>
                        <div class="admin-wrapper">
                            <header class="admin-header">
                                <div class="user-info">
                                    <span class="admin-badge">SYSTEM ADMIN</span>
                                    <span style="font-weight:500;">Admin</span>
                                    <a href="${pageContext.request.contextPath}/admin?action=dashboard"
                                        class="btn btn-sm btn-light">返回仪表盘</a>
                                    <a href="${pageContext.request.contextPath}/logout"
                                        class="btn btn-sm btn-danger">注销登出</a>
                                </div>
                            </header>
                            <div class="admin-content">
                                <h1 class="page-title"><span
                                        style="margin-right:10px;color:var(--primary);">&#x1F4DD;</span> 申诉管理</h1>
                                <% if (message !=null) { %>
                                    <div class="alert alert-<%= " success".equals(messageType) ? "success" : "error" %>
                                        "><%= message %>
                                    </div>
                                    <% } %>
                                        <div class="card">
                                            <div class="card-body" style="padding:0;">
                                                <div class="table-container">
                                                    <table class="table">
                                                        <thead>
                                                            <tr>
                                                                <th style="padding-left:1rem;">ID</th>
                                                                <th>用户名</th>
                                                                <th>申诉类型</th>
                                                                <th>联系邮箱</th>
                                                                <th>状态</th>
                                                                <th>提交时间</th>
                                                                <th style="text-align:right;padding-right:1rem;">操作</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            <% if (appeals !=null && !appeals.isEmpty()) { for (Appeal
                                                                appeal : appeals) { %>
                                                                <tr>
                                                                    <td style="padding-left:1rem;"><span
                                                                            class="badge badge-light-dark">#<%=
                                                                                appeal.getId() %></span></td>
                                                                    <td style="font-weight:500;">
                                                                        <%= appeal.getUsername() %>
                                                                    </td>
                                                                    <td>
                                                                        <% String type=appeal.getAppealType(); if
                                                                            ("unfreeze".equals(type)) out.print("解冻申诉");
                                                                            else if ("undelete".equals(type))
                                                                            out.print("恢复申诉"); else out.print(type
                                                                            !=null ? type : "未知" ); %>
                                                                    </td>
                                                                    <td style="font-size:0.9rem;">
                                                                        <%= appeal.getContactEmail() %>
                                                                    </td>
                                                                    <td>
                                                                        <% String st=appeal.getStatus(); String
                                                                            stText="待处理" ; String
                                                                            stClass="status-pending" ; if
                                                                            ("approved".equals(st)) { stText="已通过" ;
                                                                            stClass="status-approved" ; } else if
                                                                            ("rejected".equals(st)) { stText="已驳回" ;
                                                                            stClass="status-rejected" ; } %><span
                                                                                class="status-tag <%= stClass %>">
                                                                                <%= stText %>
                                                                            </span>
                                                                    </td>
                                                                    <td
                                                                        style="font-size:0.88rem;color:var(--text-muted);">
                                                                        <%= appeal.getCreateTime() %>
                                                                    </td>
                                                                    <td style="text-align:right;padding-right:1rem;">
                                                                        <% if ("pending".equals(appeal.getStatus())) {
                                                                            %>
                                                                            <div class="btn-group">
                                                                                <button class="btn btn-sm btn-primary"
                                                                                    onclick="showApproveModal(<%= appeal.getId() %>, '<%= appeal.getUsername() %>')">通过</button>
                                                                                <button class="btn btn-sm btn-danger"
                                                                                    onclick="showRejectModal(<%= appeal.getId() %>, '<%= appeal.getUsername() %>')">驳回</button>
                                                                                <button class="btn btn-sm btn-light"
                                                                                    onclick="showAppealDetail(<%= appeal.getId() %>)">查看</button>
                                                                            </div>
                                                                            <% } else { %>
                                                                                <button class="btn btn-sm btn-light"
                                                                                    onclick="showAppealDetail(<%= appeal.getId() %>)">查看</button>
                                                                                <% } %>
                                                                    </td>
                                                                </tr>
                                                                <% } } else { %>
                                                                    <tr>
                                                                        <td colspan="7"
                                                                            style="text-align:center;padding:40px;color:var(--text-muted);">
                                                                            暂无申诉记录</td>
                                                                    </tr>
                                                                    <% } %>
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        </div>
                            </div>
                        </div>
                        <div id="approveModal" class="modal">
                            <div class="modal-dialog" style="background:#ffffff !important; opacity:1 !important;">
                                <div class="modal-header">
                                    <h3>同意申诉</h3>
                                </div>
                                <form id="approveForm">
                                    <div class="modal-body">
                                        <p>确定同意用户 <strong id="approveUsername"></strong> 的申诉吗？</p>
                                        <label>回复内容（可选）：</label>
                                        <textarea name="reply" rows="3"></textarea>
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-sm btn-light"
                                            onclick="closeModal('approveModal')">取消</button>
                                        <button type="button" class="btn-success-action"
                                            onclick="submitApprove()">确认同意</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                        <div id="rejectModal" class="modal">
                            <div class="modal-dialog" style="background:#ffffff !important; opacity:1 !important;">
                                <div class="modal-header">
                                    <h3>驳回申诉</h3>
                                </div>
                                <form id="rejectForm">
                                    <div class="modal-body">
                                        <p>确定驳回用户 <strong id="rejectUsername"></strong> 的申诉吗？</p>
                                        <label>驳回原因（可选）：</label>
                                        <textarea name="reply" rows="3"></textarea>
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-sm btn-light"
                                            onclick="closeModal('rejectModal')">取消</button>
                                        <button type="button" class="btn-danger-action"
                                            onclick="submitReject()">确认驳回</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                        <div id="detailModal" class="modal">
                            <div class="modal-dialog" style="background:#ffffff !important; opacity:1 !important;">
                                <div class="modal-header">
                                    <h3>申诉详情</h3>
                                </div>
                                <div class="modal-body" style="background:#ffffff; position:relative; z-index:1001;">
                                    <p><strong>申诉原因：</strong></p>
                                    <p id="detailReason" style="white-space:pre-wrap;"></p>
                                    <div id="detailReplySection" style="display:none;margin-top:14px;">
                                        <p><strong>管理员回复：</strong></p>
                                        <p id="detailReply" style="white-space:pre-wrap;"></p>
                                    </div>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-sm btn-light"
                                        onclick="closeModal('detailModal')">关闭</button>
                                </div>
                            </div>
                        </div>
                        <script>
                            var contextPath = '${pageContext.request.contextPath}';
                            var currentAppealId = null;
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
                                var params = new URLSearchParams(new FormData(document.getElementById('approveForm')));
                                fetch(contextPath + '/admin?action=approveAppeal&id=' + currentAppealId, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                                    body: params
                                }).then(function (resp) {
                                    if (resp.ok) window.location.href = contextPath + '/admin?action=appeals';
                                    else alert('操作失败');
                                }).catch(function () { alert('操作失败'); });
                            }
                            function submitReject() {
                                var params = new URLSearchParams(new FormData(document.getElementById('rejectForm')));
                                fetch(contextPath + '/admin?action=rejectAppeal&id=' + currentAppealId, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                                    body: params
                                }).then(function (resp) {
                                    if (resp.ok) window.location.href = contextPath + '/admin?action=appeals';
                                    else alert('操作失败');
                                }).catch(function () { alert('操作失败'); });
                            }
                            function showAppealDetail(appealId) {
                                document.getElementById('detailReason').textContent = '正在加载...';
                                document.getElementById('detailReplySection').style.display = 'none';
                                document.getElementById('detailModal').classList.add('show');
                                fetch(contextPath + '/admin?action=getAppealDetail&id=' + appealId)
                                    .then(function (resp) {
                                        if (resp.ok) return resp.json();
                                        else if (resp.status === 404) throw new Error('申诉记录不存在');
                                        else throw new Error('获取申诉详情失败');
                                    })
                                    .then(function (data) {
                                        document.getElementById('detailReason').textContent = data.reason || '无申诉原因';
                                        if (data.adminReply) {
                                            document.getElementById('detailReply').textContent = data.adminReply;
                                            document.getElementById('detailReplySection').style.display = 'block';
                                        }
                                    })
                                    .catch(function (err) {
                                        document.getElementById('detailReason').textContent = '错误：' + err.message;
                                    });
                            }
                            function closeModal(id) {
                                document.getElementById(id).classList.remove('show');
                            }
                        </script>
                    </body>

                    </html>