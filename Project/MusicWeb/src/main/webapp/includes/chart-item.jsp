<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.Song" %>
        <% /* Extract Attributes */ Song song=(Song) request.getAttribute("song"); Boolean isFavorited=(Boolean)
            request.getAttribute("isFavorited"); Integer rank=(Integer) request.getAttribute("rank"); %>
            <div class="chart-item <%= (rank != null && rank <= 3) ? " top-" + rank : "" %>">
                <div class="chart-rank">
                    <%= rank %>
                </div>
                <div class="chart-song-info">
                    <div class="chart-song-title">
                        <%= song.getTitle() %>
                    </div>
                    <div class="chart-song-artist">
                        <%= song.getArtist() %>
                    </div>
                </div>
                <div class="chart-actions">
                    <button class="play-btn chart-play-btn" data-song-id="<%= song.getId() %>"
                        data-song-title="<%= song.getTitle() %>" data-song-artist="<%= song.getArtist() %>"
                        data-song-album="<%= song.getAlbum() %>" data-song-duration="<%= song.getDuration() %>"
                        title="播放">▶️</button>

                    <button class="favorite-btn-ajax <%= (isFavorited != null && isFavorited) ? " favorited" : "" %>"
                        data-action="<%= (isFavorited !=null && isFavorited) ? "remove" : "add" %>"
                            data-song-id="<%= song.getId() %>"
                                style="color: <%= (isFavorited !=null && isFavorited) ? "red" : "inherit" %>;"
                                    title="<%= (isFavorited !=null && isFavorited) ? "取消收藏" : "收藏" %>">
                                        <%= (isFavorited !=null && isFavorited) ? "❤️" : "🤍" %>
                    </button>
                </div>
            </div>