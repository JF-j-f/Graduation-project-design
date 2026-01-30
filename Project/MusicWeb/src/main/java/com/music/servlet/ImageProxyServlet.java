package com.music.servlet;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;

/**
 * 封面图片代理 Servlet
 * 
 * 核心功能：
 * 拦截 /img/* 请求，优先从源码目录读取图片。
 * 解决 Tomcat 部署目录与源码目录不一致导致的 404 问题。
 * 实现 "所见即所得" 的开发体验，无需频繁重启部署。
 */
@WebServlet(name = "ImageProxyServlet", urlPatterns = "/img/*")
public class ImageProxyServlet extends HttpServlet {

    // 源码目录路径 (硬编码为开发环境路径)
    private static final String SOURCE_WEBAPP_PATH = "E:/Graduation-project-design/Project/MusicWeb/src/main/webapp";

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        // 1. 获取请求的文件名 (如 /img/cover_123.jpg -> cover_123.jpg)
        String requestURI = request.getRequestURI();
        // 假设 contextPath 为 /musicweb
        // requestURI: /musicweb/img/cover_123.jpg
        // 提取 /img/ 之后的部分
        String pathInfo = requestURI.substring(requestURI.indexOf("/img/") + 5);

        // URL 解码 (处理中文文件名)
        String fileName = URLDecoder.decode(pathInfo, StandardCharsets.UTF_8);

        // 2. 尝试从源码目录读取
        File sourceFile = new File(SOURCE_WEBAPP_PATH + "/img", fileName);
        File targetFile = null;

        if (sourceFile.exists() && sourceFile.isFile()) {
            targetFile = sourceFile;
            // System.out.println("🖼️ [ImageProxy] Serving from Source: " + fileName);
        } else {
            // 3. 回退到运行时目录 (Tomcat Deploy Dir)
            String realPath = getServletContext().getRealPath("/img/" + fileName);
            if (realPath != null) {
                targetFile = new File(realPath);
            }
        }

        // 4. 如果文件存在，写入响应流
        if (targetFile != null && targetFile.exists() && targetFile.isFile()) {
            // 设置 Content-Type
            String mimeType = getServletContext().getMimeType(targetFile.getName());
            if (mimeType == null) {
                if (fileName.endsWith(".jpg") || fileName.endsWith(".jpeg"))
                    mimeType = "image/jpeg";
                else if (fileName.endsWith(".png"))
                    mimeType = "image/png";
                else if (fileName.endsWith(".gif"))
                    mimeType = "image/gif";
                else if (fileName.endsWith(".webp"))
                    mimeType = "image/webp";
                else
                    mimeType = "application/octet-stream";
            }
            response.setContentType(mimeType);
            response.setContentLength((int) targetFile.length());

            // 写入流
            try (FileInputStream in = new FileInputStream(targetFile);
                    OutputStream out = response.getOutputStream()) {
                byte[] buffer = new byte[4096];
                int bytesRead;
                while ((bytesRead = in.read(buffer)) != -1) {
                    out.write(buffer, 0, bytesRead);
                }
            }
        } else {
            // 5. 404 处理
            // System.out.println("⚠️ [ImageProxy] 404 Not Found: " + fileName);
            response.sendError(HttpServletResponse.SC_NOT_FOUND);
        }
    }
}
