package com.music.util;

import jakarta.mail.*;
import jakarta.mail.internet.*;
import java.io.InputStream;
import java.util.Properties;

/**
 * 邮件发送工具类
 * <p>
 * 该类负责读取配置文件中的邮件服务器信息，并提供发送 HTML 格式邮件的静态方法。
 * 基于 Jakarta Mail (原 JavaMail) 实现。
 */
public class EmailUtil {
    // 邮件服务器配置变量
    private static String host;     // SMTP 服务器主机，例如: smtp.qq.com
    private static String port;     // SMTP 服务器端口，例如: 465 或 587
    private static String username; // 发件人账号/用户名
    private static String password; // 发件人授权码或密码
    private static String from;     // 发件人邮箱地址

    /*
     * 静态初始化块
     * 在类加载时自动执行，用于从 email.properties 配置文件中读取配置信息。
     * 确保 email.properties 文件位于 classpath 根目录下（如 src/main/resources）。
     */
    static {
        try (InputStream input = EmailUtil.class.getClassLoader().getResourceAsStream("email.properties")) {
            Properties props = new Properties();
            if (input != null) {
                // 加载配置文件
                props.load(input);
                // 读取具体的配置项
                host = props.getProperty("mail.smtp.host");
                port = props.getProperty("mail.smtp.port");
                username = props.getProperty("mail.username");
                password = props.getProperty("mail.password");
                from = props.getProperty("mail.from");
            } else {
                System.err.println("未找到 email.properties 配置文件");
            }
        } catch (Exception e) {
            System.err.println("读取邮件配置文件失败");
            e.printStackTrace();
        }
    }

    /**
     * 发送邮件的核心方法
     *
     * @param to      收件人邮箱地址
     * @param subject 邮件主题
     * @param content 邮件内容（支持 HTML 格式）
     * @return boolean 发送成功返回 true，失败返回 false
     */
    public static boolean sendEmail(String to, String subject, String content) {
        // 1. 设置邮件服务器参数
        Properties props = new Properties();
        props.put("mail.smtp.host", host);             // 设置 SMTP 主机
        props.put("mail.smtp.port", port);             // 设置端口
        props.put("mail.smtp.auth", "true");           // 开启认证
        props.put("mail.smtp.ssl.enable", "true");     // 开启 SSL 加密连接
        props.put("mail.smtp.ssl.protocols", "TLSv1.2"); // 指定 SSL 协议版本

        // 2. 创建邮件会话 Session
        // 使用 Authenticator 进行账号密码验证
        Session session = Session.getInstance(props, new Authenticator() {
            @Override
            protected PasswordAuthentication getPasswordAuthentication() {
                return new PasswordAuthentication(username, password);
            }
        });

        try {
            // 3. 创建邮件消息对象
            Message message = new MimeMessage(session);

            // 设置发件人 (参数：邮箱地址, 显示名称, 编码格式)
            try {
                message.setFrom(new InternetAddress(from, "管理员", "UTF-8"));
            } catch (java.io.UnsupportedEncodingException e) {
                e.printStackTrace();
            }

            // 设置收件人 (InternetAddress.parse 支持多个收件人，用逗号分隔)
            message.setRecipients(Message.RecipientType.TO, InternetAddress.parse(to));

            // 设置邮件主题
            message.setSubject(subject);

            // 设置邮件内容，指定内容类型为 HTML，字符集为 UTF-8
            message.setContent(content, "text/html;charset=UTF-8");

            // 4. 发送邮件
            Transport.send(message);

            System.out.println("邮件发送成功: " + to);
            return true;
        } catch (MessagingException e) {
            // 5. 异常处理
            System.err.println("邮件发送失败: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }
}