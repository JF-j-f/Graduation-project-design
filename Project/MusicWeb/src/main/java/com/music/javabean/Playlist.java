package com.music.javabean;

import java.util.List;

/**
 * 歌单模型类
 * 对应数据库表：user_playlists
 */
public class Playlist {
    private int id;
    private int userId;
    private String name;
    private String description;
    private String coverImage;
    private boolean isDefault;
    private String createTime;
    private String updateTime;
    private User user; // 关联的用户信息
    private List<Song> songs; // 歌单中的歌曲列表
    private int songCount; // 歌曲数量

    // 构造方法
    public Playlist() {}

    public Playlist(String name, int userId) {
        this.name = name;
        this.userId = userId;
        this.isDefault = false;
    }

    public Playlist(String name, int userId, boolean isDefault) {
        this.name = name;
        this.userId = userId;
        this.isDefault = isDefault;
    }

    // getter和setter方法
    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public int getUserId() { return userId; }
    public void setUserId(int userId) { this.userId = userId; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getCoverImage() { return coverImage; }
    public void setCoverImage(String coverImage) { this.coverImage = coverImage; }

    public boolean isDefault() { return isDefault; }
    public void setDefault(boolean isDefault) { this.isDefault = isDefault; }

    public String getCreateTime() { return createTime; }
    public void setCreateTime(String createTime) { this.createTime = createTime; }

    public String getUpdateTime() { return updateTime; }
    public void setUpdateTime(String updateTime) { this.updateTime = updateTime; }

    public User getUser() { return user; }
    public void setUser(User user) { this.user = user; }

    public List<Song> getSongs() { return songs; }
    public void setSongs(List<Song> songs) { this.songs = songs; }

    public int getSongCount() { return songCount; }
    public void setSongCount(int songCount) { this.songCount = songCount; }

    /**
     * 获取歌单封面图片路径
     * 如果没有设置封面，返回默认封面
     */
    public String getDisplayCover() {
        if (coverImage != null && !coverImage.isEmpty()) {
            return coverImage;
        }
        return "img/cover.jpg";
    }

    /**
     * 检查是否为默认歌单
     * 默认歌单不可删除
     */
    public boolean canDelete() {
        return !isDefault;
    }

    @Override
    public String toString() {
        return "Playlist{" +
                "id=" + id +
                ", userId=" + userId +
                ", name='" + name + '\'' +
                ", description='" + description + '\'' +
                ", isDefault=" + isDefault +
                ", songCount=" + songCount +
                '}';
    }
}
