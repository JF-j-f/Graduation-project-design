<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.Song" %>
        <% /* Extract Attributes */ Song song=(Song) request.getAttribute("song"); Boolean isFavorited=(Boolean)
            request.getAttribute("isFavorited"); String playTime=(String) request.getAttribute("playTime"); %>
            <div class="song-item fade-in">
                <div class="song-cover">
                    <% if (song.getCoverImage() !=null && !song.getCoverImage().isEmpty()) { %>
                        <img src="<%= song.getCoverImage() %>" alt="封面"
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