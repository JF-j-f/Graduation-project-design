<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.Song" %>
        <% /* Extract Attributes */ Song song=(Song) request.getAttribute("song"); Boolean isFavorited=(Boolean)
            request.getAttribute("isFavorited"); String playTime=(String) request.getAttribute("playTime"); %>
            <div class="song-item fade-in">
                <div class="song-cover">
                    <% if (song.getCoverImage() !=null && !song.getCoverImage().isEmpty()) { String
                        coverUrl=song.getCoverImage(); if (!coverUrl.startsWith("http") && !coverUrl.startsWith("/")) {
                        coverUrl=request.getContextPath() + "/" + coverUrl; } %>
                        <img src="<%= coverUrl %>" alt="封面"
                            style="width: 100%; height: 100%; border-radius: 8px; object-fit: cover;">
                        <% } else { %>
                            <div
                                style="font-size: 24px; display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; background: #eee; border-radius: 8px;">
                                🎵</div>
                            <% } %>
                </div>
                <div class="song-info">
                    <div class="song-title">
                        <%= song.getTitle() %>
                    </div>
                    <div class="song-artist">
                        <%= song.getArtist() %> - <%= song.getAlbum() %>
                    </div>
                    <% if (playTime !=null) { %>
                        <div style="font-size: 0.8rem; color: var(--text-light);">播放于 <%= playTime %>
                        </div>
                        <% } %>
                </div>
                <div class="song-actions">
                    <!-- 添加到歌单按钮 -->
                    <div class="add-to-playlist-wrapper" style="position: relative; display: inline-block;">
                        <button class="add-to-playlist-btn" data-song-id="<%= song.getId() %>"
                            data-song-title="<%= song.getTitle() %>" title="添加到歌单"
                            style="background: none; border: none; font-size: 1.1rem; cursor: pointer; padding: 0.3rem 0.5rem; color: #666; transition: all 0.2s ease;">➕</button>
                        <div class="playlist-dropdown"
                            style="display: none; position: absolute; top: 100%; right: 0; min-width: 180px; background: white; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 1000; overflow: hidden;">
                            <div class="playlist-dropdown-loading"
                                style="padding: 1rem; text-align: center; color: #888;">加载中...</div>
                        </div>
                    </div>

                    <button class="play-btn" data-song-id="<%= song.getId() %>" data-song-title="<%= song.getTitle() %>"
                        data-song-artist="<%= song.getArtist() %>" data-song-album="<%= song.getAlbum() %>"
                        data-song-duration="<%= song.getDuration() %>" title="播放">▶️</button>

                    <button class="favorite-btn-ajax <%= (isFavorited != null && isFavorited) ? " favorited" : "" %>"
                        data-action="<%= (isFavorited !=null && isFavorited) ? "remove" : "add" %>"
                            data-song-id="<%= song.getId() %>"
                                style="color: <%= (isFavorited !=null && isFavorited) ? "red" : "inherit" %>;"
                                    title="<%= (isFavorited !=null && isFavorited) ? "取消收藏" : "收藏" %>">
                                        <%= (isFavorited !=null && isFavorited) ? "❤️" : "🤍" %>
                    </button>
                </div>
            </div>