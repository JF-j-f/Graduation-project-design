package com.music.util;

import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;

/**
 * 封面下载工具类
 * 用于下载外部封面图片到本地 img/ 目录
 * 
 * @version v3.3.0 - ImageProxy 专用版 (只保存到源码目录)
 */
public class CoverDownloadUtil {

    // 源码目录路径（从 secrets.txt 注入 System.properties，避免硬编码）
    private static final String SOURCE_WEBAPP_PATH = System.getProperty("SOURCE_WEBAPP_PATH", "");

    // HTTP 客户端（复用以提高性能）
    private static final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .followRedirects(HttpClient.Redirect.NORMAL)
            .build();

    /**
     * 下载外部封面到本地
     * 
     * @param coverUrl   外部封面 URL（如 https://y.qq.com/xxx.jpg）
     * @param songId     歌曲 ID（用于命名：cover_123.jpg）
     * @param webappPath (不再使用，仅保留参数兼容)
     * @return 本地相对路径（如 "img/cover_123.jpg"），失败返回 null
     */
    public static String downloadCover(String coverUrl, int songId, String webappPath) {
        if (coverUrl == null || coverUrl.isEmpty() || songId <= 0) {
            // System.out.println("⚠️ [封面下载] 参数无效");
            return null;
        }

        try {
            // 1. 确定文件名
            String extension = getExtension(coverUrl);
            String fileName = "cover_" + songId + extension;
            String relativePath = "img/" + fileName;

            // 2. 策略：只保存到源码目录
            // 前端访问 /img/xxx.jpg 时，由 ImageProxyServlet 代理读取源码目录
            if (Files.exists(Paths.get(SOURCE_WEBAPP_PATH))) {
                Path sourceDir = Paths.get(SOURCE_WEBAPP_PATH, "img");
                if (!Files.exists(sourceDir))
                    Files.createDirectories(sourceDir);

                Path sourceFile = sourceDir.resolve(fileName);

                // 只有文件不存在时才下载，避免重复下载
                if (!Files.exists(sourceFile)) {
                    saveUrlToFile(coverUrl, sourceFile);
                    System.out.println("✅ [封面下载] 已保存到源码目录: " + sourceFile);
                } else {
                    // 文件已存在，直接返回
                }

                return relativePath;
            } else {
                System.err.println("❌ [封面下载] 源码目录不存在 (SOURCE_WEBAPP_PATH)，无法保存封面！");
                return null;
            }

        } catch (Exception e) {
            System.err.println("❌ [封面下载] 失败: " + e.getMessage());
            e.printStackTrace();
            return null;
        }
    }

    /**
     * 将 URL 内容保存到文件
     */
    private static void saveUrlToFile(String url, Path targetFile) throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .timeout(Duration.ofSeconds(15))
                .header("User-Agent", "MusicWeb/3.2.0")
                .GET()
                .build();

        HttpResponse<InputStream> response = httpClient.send(request,
                HttpResponse.BodyHandlers.ofInputStream());

        if (response.statusCode() != 200) {
            throw new Exception("HTTP " + response.statusCode());
        }

        try (InputStream in = response.body();
                FileOutputStream out = new FileOutputStream(targetFile.toFile())) {
            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = in.read(buffer)) != -1) {
                out.write(buffer, 0, bytesRead);
            }
        }
    }

    /**
     * 从 URL 中提取文件扩展名
     */
    private static String getExtension(String url) {
        String path = url.split("\\?")[0];
        if (path.endsWith(".png"))
            return ".png";
        if (path.endsWith(".webp"))
            return ".webp";
        if (path.endsWith(".gif"))
            return ".gif";
        return ".jpg";
    }
}
