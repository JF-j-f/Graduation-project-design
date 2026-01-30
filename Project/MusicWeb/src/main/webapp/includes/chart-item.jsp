<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.Song" %>
        <% /* Extract Attributes */ Song song=(Song) request.getAttribute("song"); Boolean isFavorited=(Boolean)
            request.getAttribute("isFavorited"); Integer rank=(Integer) request.getAttribute("rank"); %>
            <div class="chart-item fade-in">
                <div class="chart-rank">
                    <%= rank %>
                </div>

                <div class="song-cover" style="width: 40px; height: 40px; flex-shrink: 0;">
                    <% if (song.getCoverImage() !=null && !song.getCoverImage().isEmpty()) { String
                        coverUrl=song.getCoverImage(); if (!coverUrl.startsWith("http") && !coverUrl.startsWith("/")) {
                        coverUrl=request.getContextPath() + "/" + coverUrl; } %>
                        <img src="<%= coverUrl %>" alt="封面"
                            style="width: 100%; height: 100%; border-radius: 4px; object-fit: cover;">
                        <% } else { %>
                            <div
                                style="font-size: 20px; display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; background: #eee; border-radius: 4px;">
                                🎵</div>
                            <% } %>
                </div>

                <div class="chart-song-info">
                    <div class="chart-song-title" title="<%= song.getTitle() %>">
                        <%= song.getTitle() %>
                    </div>
                    <div class="chart-song-artist" title="<%= song.getArtist() %>">
                        <%= song.getArtist() %>
                    </div>
                </div>

                <div class="chart-actions">
                    <button class="play-btn" style="background: none; border: none; cursor: pointer; font-size: 1.1rem;"
                        data-song-id="<%= song.getId() %>" data-song-title="<%= song.getTitle() %>"
                        data-song-artist="<%= song.getArtist() %>" data-song-album="<%= song.getAlbum() %>"
                        data-song-duration="<%= song.getDuration() %>" title="播放">▶️</button>

                    <button class="favorite-btn-ajax <%= (isFavorited != null && isFavorited) ? " favorited" : "" %>"
                        style="background: none; border: none; cursor: pointer; font-size: 1.1rem; color: <%=
                            (isFavorited !=null && isFavorited) ? "red" : "#ccc" %>;"
                            data-action="<%= (isFavorited !=null && isFavorited) ? "remove" : "add" %>"
                                data-song-id="<%= song.getId() %>"
                                    title="<%= (isFavorited !=null && isFavorited) ? "取消收藏" : "收藏" %>">
                                        <%= (isFavorited !=null && isFavorited) ? "❤️" : "🤍" %>
                    </button>
                </div>
            </div>