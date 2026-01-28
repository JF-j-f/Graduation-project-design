package com.music.javabean;

public class PlayHistory {
    private int id;
    private int userId;
    private int songId;
    private String playTime;
    private int playDuration;
    private User user; // 关联的用户信息
    private Song song; // 关联的歌曲信息

    // getter和setter方法
    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public int getUserId() { return userId; }
    public void setUserId(int userId) { this.userId = userId; }

    public int getSongId() { return songId; }
    public void setSongId(int songId) { this.songId = songId; }

    public String getPlayTime() { return playTime; }
    public void setPlayTime(String playTime) { this.playTime = playTime; }

    public int getPlayDuration() { return playDuration; }
    public void setPlayDuration(int playDuration) { this.playDuration = playDuration; }

    public User getUser() { return user; }
    public void setUser(User user) { this.user = user; }

    public Song getSong() { return song; }
    public void setSong(Song song) { this.song = song; }
}
