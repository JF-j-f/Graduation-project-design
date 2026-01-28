package com.music.javabean;

public class Appeal {
    private int id;
    private String username;
    private Integer userId;
    private String appealType;
    private String reason;
    private String contactEmail;
    private String status;
    private String adminReply;
    private String createTime;
    private String updateTime;

    public Appeal() {}

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public Integer getUserId() { return userId; }
    public void setUserId(Integer userId) { this.userId = userId; }

    public String getAppealType() { return appealType; }
    public void setAppealType(String appealType) { this.appealType = appealType; }

    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }

    public String getContactEmail() { return contactEmail; }
    public void setContactEmail(String contactEmail) { this.contactEmail = contactEmail; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getAdminReply() { return adminReply; }
    public void setAdminReply(String adminReply) { this.adminReply = adminReply; }

    public String getCreateTime() { return createTime; }
    public void setCreateTime(String createTime) { this.createTime = createTime; }

    public String getUpdateTime() { return updateTime; }
    public void setUpdateTime(String updateTime) { this.updateTime = updateTime; }
}
