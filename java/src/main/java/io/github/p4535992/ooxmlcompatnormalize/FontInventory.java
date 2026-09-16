package io.github.p4535992.ooxmlcompatnormalize;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Enumeration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Schema-aware font-family inventory for DOCX/XLSX/PPTX. */
public final class FontInventory {
    private FontInventory() {}

    public static Set<String> scan(Path path) throws IOException {
        Set<String> names = Normalizer.packageNames(path);
        Normalizer.Kind kind = Normalizer.detectKind(names);
        Set<String> fonts = new LinkedHashSet<>();

        try (ZipFile zip = new ZipFile(path.toFile())) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (entry.isDirectory() || !(entry.getName().endsWith(".xml") || entry.getName().endsWith(".rels"))) {
                    continue;
                }
                byte[] raw = zip.getInputStream(entry).readAllBytes();
                if (isUtf16(raw)) continue;
                String xml = new String(raw, StandardCharsets.UTF_8);

                // DrawingML theme/run font declarations used across OOXML families.
                collectAttribute(xml, "typeface", fonts);

                if (kind == Normalizer.Kind.DOCX && entry.getName().startsWith("word/")) {
                    // Only inspect w:rFonts tags. A global eastAsia search would incorrectly
                    // treat w:lang/@w:eastAsia="zh-CN" as a font family.
                    Matcher tags = Pattern.compile("<(?:w:)?rFonts\\b[^>]*>").matcher(xml);
                    while (tags.find()) {
                        String tag = tags.group();
                        for (String attr : List.of("(?:w:)?ascii", "(?:w:)?hAnsi", "(?:w:)?eastAsia", "(?:w:)?cs")) {
                            collectAttribute(tag, attr, fonts);
                        }
                    }
                    if (entry.getName().equals("word/fontTable.xml")) {
                        Matcher m = Pattern.compile("<(?:w:)?font\\b[^>]*\\b(?:w:)?name\\s*=\\s*([\"'])(.*?)\\1").matcher(xml);
                        while (m.find()) add(fonts, m.group(2));
                    }
                }

                if (kind == Normalizer.Kind.XLSX && entry.getName().startsWith("xl/")) {
                    Matcher m = Pattern.compile("<(?:\\w+:)?rFont\\b[^>]*\\bval\\s*=\\s*([\"'])(.*?)\\1").matcher(xml);
                    while (m.find()) add(fonts, m.group(2));
                    if (entry.getName().equals("xl/styles.xml")) {
                        // Cell-style font names are <font><name val="..."/>...</font>.
                        Matcher fontBlocks = Pattern.compile("<(?:\\w+:)?font\\b[^>]*>.*?</(?:\\w+:)?font>", Pattern.DOTALL).matcher(xml);
                        while (fontBlocks.find()) {
                            Matcher name = Pattern.compile("<(?:\\w+:)?name\\b[^>]*\\bval\\s*=\\s*([\"'])(.*?)\\1").matcher(fontBlocks.group());
                            while (name.find()) add(fonts, name.group(2));
                        }
                    }
                }
            }
        }
        return fonts;
    }

    private static void collectAttribute(String text, String attrRegex, Set<String> fonts) {
        Matcher m = Pattern.compile("\\b" + attrRegex + "\\s*=\\s*([\"'])(.*?)\\1").matcher(text);
        while (m.find()) add(fonts, m.group(2));
    }

    private static void add(Set<String> fonts, String raw) {
        if (raw == null) return;
        String value = raw.trim();
        if (value.isEmpty() || value.startsWith("+") || value.startsWith("major") || value.startsWith("minor")) return;
        fonts.add(value);
    }

    private static boolean isUtf16(byte[] raw) {
        if (raw.length >= 2) {
            if ((raw[0] == (byte) 0xFF && raw[1] == (byte) 0xFE)
                    || (raw[0] == (byte) 0xFE && raw[1] == (byte) 0xFF)) return true;
        }
        String head = new String(raw, 0, Math.min(raw.length, 200), StandardCharsets.US_ASCII).toLowerCase();
        return head.contains("encoding=\"utf-16") || head.contains("encoding='utf-16");
    }
}
