package com.music.listener;

import jakarta.servlet.ServletContextEvent;
import jakarta.servlet.ServletContextListener;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;

/**
 * 隐私配置加载器
 * <p>
 * Web 应用启动时自动执行，从项目根目录的 secrets.txt 文件读取敏感配置，
 * 将键值对注入到 System.properties 中，供其他组件（DBUtil、EmailUtil 等）使用。
 * <p>
 * secrets.txt 格式为每行 KEY=VALUE，以 # 开头的行视为注释，空行忽略。
 * 该文件已加入 .gitignore，不会被提交到版本库。
 * <p>
 * 注册方式：通过 WEB-INF/web.xml 的 &lt;listener&gt; 显式注册，不使用 @WebListener 注解，
 * 避免注解扫描时重复实例化。
 */
public class SecretsLoader implements ServletContextListener {

    @Override
    public void contextInitialized(ServletContextEvent sce) {
        // 获取 secrets.txt 的路径：Tomcat 部署目录的父级（即项目根目录）
        // 实际运行时通过 getRealPath 获取 webapp 路径，再向上四级到项目根目录
        String webappRoot = sce.getServletContext().getRealPath("/");
        File secretsFile = resolveSecretsFile(webappRoot);

        if (secretsFile == null || !secretsFile.exists()) {
            System.err.println("⚠️  SecretsLoader: 未找到 secrets.txt，隐私配置未加载");
            System.err.println("    请复制 secrets.txt.example 为 secrets.txt 并填写配置值");
            return;
        }

        int count = 0;
        try (BufferedReader reader = new BufferedReader(new FileReader(secretsFile, java.nio.charset.StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                // 跳过空行和注释行
                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }
                int eqIndex = line.indexOf('=');
                if (eqIndex <= 0) {
                    continue;
                }
                String key = line.substring(0, eqIndex).trim();
                String value = line.substring(eqIndex + 1).trim();
                // 注入到 System.properties，供 DBUtil / EmailUtil 等读取
                System.setProperty(key, value);
                count++;
            }
            System.out.println("✅ SecretsLoader: 成功加载 " + count + " 项隐私配置");
        } catch (IOException e) {
            System.err.println("❌ SecretsLoader: 读取 secrets.txt 失败: " + e.getMessage());
        }
    }

    @Override
    public void contextDestroyed(ServletContextEvent sce) {
        // 应用关闭时无需特殊处理
    }

    /**
     * 根据 webapp 路径向上查找 secrets.txt。
     * <p>
     * 开发环境（IDE 启动）：webapp 路径通常为 target/musicweb，需向上多级找到项目根目录。
     * 生产环境（独立 Tomcat）：webapp 路径为 webapps/musicweb，secrets.txt 放在 Tomcat 根目录或
     * 与 webapps 同级目录时也可找到。
     * <p>
     * 查找策略：从 webapp 路径开始，逐级向上最多查找 12 层，找到 secrets.txt 即返回。
     * Cargo 嵌入式 Tomcat 的 webapp 路径为 target/cargo/configurations/tomcat10x/webapps/musicweb，
     * 需向上 8 层才能到项目根目录，设为 12 层以兼容不同部署结构。
     *
     * @param webappRoot webapp 根目录的绝对路径
     * @return secrets.txt 的 File 对象，未找到则返回 null
     */
    private File resolveSecretsFile(String webappRoot) {
        if (webappRoot == null) {
            return null;
        }
        File dir = new File(webappRoot);
        for (int i = 0; i < 12; i++) {
            File candidate = new File(dir, "secrets.txt");
            if (candidate.exists()) {
                System.out.println("✅ SecretsLoader: 找到 secrets.txt -> " + candidate.getAbsolutePath());
                return candidate;
            }
            File parent = dir.getParentFile();
            if (parent == null) {
                break;
            }
            dir = parent;
        }
        return null;
    }
}
