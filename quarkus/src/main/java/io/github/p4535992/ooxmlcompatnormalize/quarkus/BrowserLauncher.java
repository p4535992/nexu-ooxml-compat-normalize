package io.github.p4535992.ooxmlcompatnormalize.quarkus;

import io.quarkus.runtime.StartupEvent;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.jboss.logging.Logger;

import java.awt.Desktop;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;

/** Opens the local web UI when the packaged desktop launcher opts in. */
@ApplicationScoped
public class BrowserLauncher {

    private static final Logger LOG = Logger.getLogger(BrowserLauncher.class);

    @ConfigProperty(name = "ooxml.open-browser", defaultValue = "false")
    boolean openBrowser;

    @ConfigProperty(name = "quarkus.http.port", defaultValue = "8080")
    int port;

    @ConfigProperty(name = "quarkus.http.root-path", defaultValue = "/ooxml-compat-normalize")
    String rootPath;

    void onStart(@Observes StartupEvent event) {
        // GitHub runners and other CI environments must never try to launch a desktop browser.
        if (!openBrowser || System.getenv("CI") != null) {
            return;
        }

        Thread thread = new Thread(this::openWhenReady, "ooxml-open-local-ui");
        thread.setDaemon(true);
        thread.start();
    }

    private void openWhenReady() {
        String context = normalizeContextPath(rootPath);
        String base = "http://127.0.0.1:" + port + context;
        String info = base + "/api/info";

        try {
            for (int attempt = 0; attempt < 60; attempt++) {
                if (isReady(info)) {
                    if (!Desktop.isDesktopSupported()
                            || !Desktop.getDesktop().isSupported(Desktop.Action.BROWSE)) {
                        LOG.infof("Local UI ready at %s/ (automatic browser opening is not supported)", base);
                        return;
                    }
                    Desktop.getDesktop().browse(URI.create(base + "/"));
                    LOG.infof("Opened local UI at %s/", base);
                    return;
                }
                Thread.sleep(250L);
            }
            LOG.warnf("Local UI did not become ready for automatic opening: %s/", base);
        } catch (Exception ex) {
            LOG.warnf(ex, "Could not open local UI automatically: %s/", base);
        }
    }

    private static String normalizeContextPath(String value) {
        if (value == null || value.isBlank() || "/".equals(value.trim())) {
            return "";
        }
        String normalized = value.trim();
        if (!normalized.startsWith("/")) {
            normalized = "/" + normalized;
        }
        while (normalized.endsWith("/") && normalized.length() > 1) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        return normalized;
    }

    private static boolean isReady(String url) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(url).openConnection();
            connection.setConnectTimeout(400);
            connection.setReadTimeout(400);
            connection.setRequestMethod("GET");
            int status = connection.getResponseCode();
            try (InputStream ignored = status >= 400 ? connection.getErrorStream() : connection.getInputStream()) {
                return status >= 200 && status < 300;
            }
        } catch (Exception ignored) {
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }
}
