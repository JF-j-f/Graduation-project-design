package com.music.utils;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 元数据清洗工具类
 * 用于处理外部音乐源（特别是QQ音乐）的非标准化元数据
 */
public class MetadataCleaner {

    // 正则：匹配 "歌手名字《歌名》(后缀)" 格式
    // Group 1: 潜在歌手名
    // Group 2: 核心歌名
    // Group 3: 后缀（如 " (Live版)"）
    private static final Pattern QQ_TITLE_PATTERN = Pattern.compile("^(.+?)《(.+?)》(.*)$");

    public static class CleanResult {
        private String title;
        private String artist;
        private String album;
        private boolean modified;

        public CleanResult(String title, String artist, String album, boolean modified) {
            this.title = title;
            this.artist = artist;
            this.album = album;
            this.modified = modified;
        }

        public String getTitle() { return title; }
        public String getArtist() { return artist; }
        public String getAlbum() { return album; }
        public boolean isModified() { return modified; }
    }

    /**
     * 清洗 QQ 音乐源的元数据
     * 
     * 策略：
     * 1. 仅针对 source="qq" 且 title 匹配 "某某《某某》" 格式的数据
     * 2. 提取出真实歌手和歌名
     * 3. 如果提取出的歌手与原 artist 字段不一致，则认为原 artist 字段是专辑名，将其移动到 album 字段
     * 
     * @param title 原始标题
     * @param artist 原始歌手
     * @param album 原始专辑
     * @param source 来源
     * @return 清洗后的结果
     */
    public static CleanResult clean(String title, String artist, String album, String source) {
        // 0. 门槛检查：只处理有效数据
        if (title == null || title.isEmpty() || source == null) {
            return new CleanResult(title, artist, album, false);
        }

        // 1. 源头检查：只处理 QQ 来源
        if (!"qq".equalsIgnoreCase(source)) {
            return new CleanResult(title, artist, album, false);
        }

        // 2. 格式匹配
        Matcher matcher = QQ_TITLE_PATTERN.matcher(title);
        if (matcher.find()) {
            String extractedArtist = matcher.group(1).trim();
            String titleCore = matcher.group(2).trim();
            String titleSuffix = matcher.group(3); // 不需要trim，保留空格格式
            if (titleSuffix == null) titleSuffix = "";

            String realTitle = titleCore + titleSuffix;

            // 3. 决策逻辑
            // 情况 A: 提取出的歌手与原字段不一致 -> 判定原 Artist 其实是 Album
            if (artist != null && !artist.isEmpty() && !extractedArtist.equalsIgnoreCase(artist.trim())) {
                String newAlbum = album;
                // 只有当原 album 为空或相同时，才把"假Artist"填入 album
                if (album == null || album.isEmpty() || album.equals(artist)) {
                    newAlbum = artist;
                }
                
                System.out.println("🧹 [MetadataCleaner] Hit! '" + title + "' -> Title:'" + realTitle + 
                                   "', Artist:'" + extractedArtist + "', Album:'" + newAlbum + "'");
                
                return new CleanResult(realTitle, extractedArtist, newAlbum, true);
            } 
            
            // 情况 B: 歌手一致 -> 仅清洗标题
            else {
                System.out.println("🧹 [MetadataCleaner] Title Fix! '" + title + "' -> '" + realTitle + "'");
                return new CleanResult(realTitle, artist, album, true);
            }
        }

        return new CleanResult(title, artist, album, false);
    }
}
