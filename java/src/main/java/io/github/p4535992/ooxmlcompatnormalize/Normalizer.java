package io.github.p4535992.ooxmlcompatnormalize;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

/**
 * Byte-local/package-preserving OOXML normalizer.
 *
 * <p>The implementation deliberately does not save a document through POI or docx4j.
 * Those libraries are used as independent parsers/validators by {@link LibraryValidation}.
 * This writer copies every OPC part and changes only explicitly supported XML markup.
 */
public final class Normalizer {
    private Normalizer() {}

    public enum Kind { DOCX, XLSX, PPTX }

    public record Options(
            String profile,
            Map<String, String> fontMap,
            boolean normalizeSemanticColors) {
        public Options {
            profile = profile == null ? "interop-transitional-v1" : profile;
            fontMap = fontMap == null ? Map.of() : Map.copyOf(fontMap);
        }

        public static Options defaults() {
            return new Options("interop-transitional-v1", Map.of(), true);
        }
    }

    public record Result(
            Kind kind,
            int partCount,
            List<String> changedParts,
            Map<String, Integer> fontMappings,
            Map<String, Integer> semanticColorMappings) {}

    public static final Map<String, String> COMPAT_FONT_MAP;
    private static final Map<String, SymbolRule> SYMBOLS;

    static {
        Map<String, String> fonts = new LinkedHashMap<>();
        fonts.put("Times New Roman", "Liberation Serif");
        fonts.put("Arial", "Liberation Sans");
        fonts.put("Courier New", "Liberation Mono");
        fonts.put("Calibri", "Carlito");
        fonts.put("Cambria", "Caladea");
        COMPAT_FONT_MAP = Collections.unmodifiableMap(fonts);

        Map<String, SymbolRule> symbols = new LinkedHashMap<>();
        symbols.put("🔴", new SymbolRule("●", "FF0000"));
        symbols.put("🟠", new SymbolRule("●", "ED7D31"));
        symbols.put("🟡", new SymbolRule("●", "FFC000"));
        symbols.put("🟢", new SymbolRule("●", "00B050"));
        symbols.put("🔵", new SymbolRule("●", "0070C0"));
        symbols.put("🟣", new SymbolRule("●", "7030A0"));
        symbols.put("🟤", new SymbolRule("●", "8B4513"));
        symbols.put("⚫", new SymbolRule("●", "000000"));
        symbols.put("⚪", new SymbolRule("●", "FFFFFF"));
        symbols.put("🟥", new SymbolRule("■", "FF0000"));
        symbols.put("🟧", new SymbolRule("■", "ED7D31"));
        symbols.put("🟨", new SymbolRule("■", "FFC000"));
        symbols.put("🟩", new SymbolRule("■", "00B050"));
        symbols.put("🟦", new SymbolRule("■", "0070C0"));
        symbols.put("🟪", new SymbolRule("■", "7030A0"));
        symbols.put("🟫", new SymbolRule("■", "8B4513"));
        symbols.put("⬛", new SymbolRule("■", "000000"));
        symbols.put("⬜", new SymbolRule("■", "FFFFFF"));
        SYMBOLS = Collections.unmodifiableMap(symbols);
    }

    private record SymbolRule(String replacement, String rgb) {}

    public static Kind detectKind(Set<String> names) {
        if (names.contains("word/document.xml")) return Kind.DOCX;
        if (names.contains("xl/workbook.xml")) return Kind.XLSX;
        if (names.contains("ppt/presentation.xml")) return Kind.PPTX;
        throw new IllegalArgumentException("Not a supported DOCX/XLSX/PPTX OOXML package");
    }

    public static Set<String> packageNames(Path path) throws IOException {
        Set<String> names = new LinkedHashSet<>();
        try (ZipFile zip = new ZipFile(path.toFile())) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) names.add(entries.nextElement().getName());
        }
        return names;
    }

    public static Set<String> inventoryFonts(Path path) throws IOException {
        Set<String> fonts = new LinkedHashSet<>();
        Set<String> names = packageNames(path);
        Kind kind = detectKind(names);
        try (ZipFile zip = new ZipFile(path.toFile())) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (!isXml(entry.getName()) || entry.isDirectory()) continue;
                byte[] raw = zip.getInputStream(entry).readAllBytes();
                if (!looksUtf8Xml(raw)) continue;
                String xml = new String(raw, StandardCharsets.UTF_8);
                collectAttribute(xml, "typeface", fonts);
                if (kind == Kind.DOCX && entry.getName().startsWith("word/")) {
                    for (String attr : List.of("ascii", "hAnsi", "eastAsia", "cs")) {
                        collectAttribute(xml, "(?:w:)?" + attr, fonts);
                    }
                    if (entry.getName().equals("word/fontTable.xml")) {
                        Matcher m = Pattern.compile("<(?:w:)?font\\b[^>]*\\b(?:w:)?name\\s*=\\s*([\"'])(.*?)\\1").matcher(xml);
                        while (m.find()) addFont(fonts, m.group(2));
                    }
                }
                if (kind == Kind.XLSX && entry.getName().startsWith("xl/")) {
                    Matcher m = Pattern.compile("<(?:\\w+:)?rFont\\b[^>]*\\bval\\s*=\\s*([\"'])(.*?)\\1").matcher(xml);
                    while (m.find()) addFont(fonts, m.group(2));
                }
            }
        }
        return fonts;
    }

    private static void collectAttribute(String xml, String attrRegex, Set<String> fonts) {
        Pattern p = Pattern.compile("\\b" + attrRegex + "\\s*=\\s*([\"'])(.*?)\\1");
        Matcher m = p.matcher(xml);
        while (m.find()) addFont(fonts, m.group(2));
    }

    private static void addFont(Set<String> fonts, String value) {
        if (value == null) return;
        String v = value.trim();
        if (v.isEmpty() || v.startsWith("+") || v.startsWith("major") || v.startsWith("minor")) return;
        fonts.add(v);
    }

    public static Result normalize(Path source, Path target, Options options) throws IOException {
        if (!Files.isRegularFile(source)) throw new IOException("Input does not exist: " + source);
        if (source.toAbsolutePath().normalize().equals(target.toAbsolutePath().normalize())) {
            throw new IllegalArgumentException("Input and output must be different paths");
        }

        Set<String> beforeNames = packageNames(source);
        Kind kind = detectKind(beforeNames);
        Files.createDirectories(target.toAbsolutePath().getParent());
        Path tmp = Files.createTempFile(target.toAbsolutePath().getParent(), ".ooxml-normalize-", ".tmp");

        List<String> changed = new ArrayList<>();
        Map<String, Integer> fontCounts = new LinkedHashMap<>();
        Map<String, Integer> symbolCounts = new LinkedHashMap<>();

        try (ZipFile zip = new ZipFile(source.toFile());
             ZipOutputStream out = new ZipOutputStream(Files.newOutputStream(tmp))) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                byte[] raw = entry.isDirectory() ? new byte[0] : zip.getInputStream(entry).readAllBytes();
                byte[] normalized = raw;

                if (!entry.isDirectory() && isXml(entry.getName()) && looksUtf8Xml(raw)) {
                    String xml = new String(raw, StandardCharsets.UTF_8);
                    String updated = xml;

                    if (!options.fontMap().isEmpty()) {
                        Map<String, Integer> local = new LinkedHashMap<>();
                        updated = mapFonts(updated, kind, entry.getName(), options.fontMap(), local);
                        mergeCounts(fontCounts, local);
                    }

                    if (options.normalizeSemanticColors() && !"preserve-v1".equals(options.profile())) {
                        Map<String, Integer> local = new LinkedHashMap<>();
                        updated = normalizeSemanticColors(updated, kind, entry.getName(), local);
                        mergeCounts(symbolCounts, local);
                    }

                    if (!updated.equals(xml)) {
                        normalized = updated.getBytes(StandardCharsets.UTF_8);
                        changed.add(entry.getName());
                    }
                }

                ZipEntry dst = new ZipEntry(entry.getName());
                if (entry.getTime() >= 0) dst.setTime(entry.getTime());
                if (entry.getComment() != null) dst.setComment(entry.getComment());
                if (entry.getExtra() != null) dst.setExtra(entry.getExtra());
                out.putNextEntry(dst);
                if (normalized.length > 0) out.write(normalized);
                out.closeEntry();
            }
        } catch (Throwable t) {
            Files.deleteIfExists(tmp);
            throw t;
        }

        Set<String> afterNames = packageNames(tmp);
        if (!beforeNames.equals(afterNames)) {
            Files.deleteIfExists(tmp);
            throw new IOException("Package part set changed during normalization");
        }
        Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        return new Result(kind, beforeNames.size(), List.copyOf(changed), Map.copyOf(fontCounts), Map.copyOf(symbolCounts));
    }

    private static boolean isXml(String name) {
        return name.endsWith(".xml") || name.endsWith(".rels");
    }

    private static boolean looksUtf8Xml(byte[] raw) {
        if (raw.length == 0) return false;
        if (raw.length >= 2 && ((raw[0] == (byte)0xFF && raw[1] == (byte)0xFE)
                || (raw[0] == (byte)0xFE && raw[1] == (byte)0xFF))) return false;
        String head = new String(raw, 0, Math.min(raw.length, 200), StandardCharsets.US_ASCII).toLowerCase();
        return !head.contains("encoding=\"utf-16") && !head.contains("encoding='utf-16");
    }

    private static void mergeCounts(Map<String, Integer> dst, Map<String, Integer> src) {
        src.forEach((k, v) -> { if (v != null && v > 0) dst.merge(k, v, Integer::sum); });
    }

    private static String mapFonts(
            String xml, Kind kind, String part, Map<String, String> mapping, Map<String, Integer> counts) {
        String out = xml;
        for (Map.Entry<String, String> e : mapping.entrySet()) {
            String oldFont = e.getKey();
            String newFont = e.getValue();
            int before = countExactFontOccurrences(out, kind, part, oldFont);
            if (before == 0) continue;

            out = replaceAttribute(out, "typeface", oldFont, newFont);

            if (kind == Kind.DOCX && part.startsWith("word/")) {
                Pattern tagPattern = Pattern.compile("<(?:w:)?rFonts\\b[^>]*>");
                Matcher tm = tagPattern.matcher(out);
                StringBuffer sb = new StringBuffer();
                while (tm.find()) {
                    String tag = tm.group();
                    for (String attr : List.of("(?:w:)?ascii", "(?:w:)?hAnsi", "(?:w:)?eastAsia", "(?:w:)?cs")) {
                        tag = replaceAttribute(tag, attr, oldFont, newFont);
                    }
                    tm.appendReplacement(sb, Matcher.quoteReplacement(tag));
                }
                tm.appendTail(sb);
                out = sb.toString();

                if (part.equals("word/fontTable.xml")) {
                    out = replaceAttributeInTag(out, "(?:w:)?font", "(?:w:)?name", oldFont, newFont);
                }
            }

            if (kind == Kind.XLSX && part.startsWith("xl/")) {
                out = replaceAttributeInTag(out, "(?:\\w+:)?rFont", "val", oldFont, newFont);
                if (part.equals("xl/styles.xml")) {
                    out = replaceAttributeInTag(out, "(?:\\w+:)?name", "val", oldFont, newFont);
                }
            }

            int after = countExactFontOccurrences(out, kind, part, oldFont);
            int changed = Math.max(0, before - after);
            if (changed > 0) counts.merge(oldFont, changed, Integer::sum);
        }
        return out;
    }

    private static int countExactFontOccurrences(String xml, Kind kind, String part, String font) {
        int count = countAttribute(xml, "typeface", font);
        if (kind == Kind.DOCX && part.startsWith("word/")) {
            for (String attr : List.of("(?:w:)?ascii", "(?:w:)?hAnsi", "(?:w:)?eastAsia", "(?:w:)?cs")) {
                count += countAttribute(xml, attr, font);
            }
            if (part.equals("word/fontTable.xml")) count += countAttribute(xml, "(?:w:)?name", font);
        }
        if (kind == Kind.XLSX && part.startsWith("xl/")) count += countAttribute(xml, "val", font);
        return count;
    }

    private static int countAttribute(String xml, String attrRegex, String value) {
        Pattern p = Pattern.compile("\\b" + attrRegex + "\\s*=\\s*([\"'])" + Pattern.quote(value) + "\\1");
        int n = 0;
        Matcher m = p.matcher(xml);
        while (m.find()) n++;
        return n;
    }

    private static String replaceAttribute(String text, String attrRegex, String oldValue, String newValue) {
        Pattern p = Pattern.compile("(\\b" + attrRegex + "\\s*=\\s*)([\"'])" + Pattern.quote(oldValue) + "\\2");
        Matcher m = p.matcher(text);
        StringBuffer sb = new StringBuffer();
        while (m.find()) {
            m.appendReplacement(sb, Matcher.quoteReplacement(m.group(1) + m.group(2) + newValue + m.group(2)));
        }
        m.appendTail(sb);
        return sb.toString();
    }

    private static String replaceAttributeInTag(
            String text, String tagRegex, String attrRegex, String oldValue, String newValue) {
        Pattern tags = Pattern.compile("<" + tagRegex + "\\b[^>]*>");
        Matcher m = tags.matcher(text);
        StringBuffer sb = new StringBuffer();
        while (m.find()) {
            String tag = replaceAttribute(m.group(), attrRegex, oldValue, newValue);
            m.appendReplacement(sb, Matcher.quoteReplacement(tag));
        }
        m.appendTail(sb);
        return sb.toString();
    }

    private static String normalizeSemanticColors(
            String xml, Kind kind, String part, Map<String, Integer> counts) {
        if (kind == Kind.DOCX && part.equals("word/document.xml")) return normalizeDocxSymbols(xml, counts);
        if (kind == Kind.PPTX && part.startsWith("ppt/") && part.endsWith(".xml")) return normalizePptxSymbols(xml, counts);
        if (kind == Kind.XLSX && part.startsWith("xl/") && part.endsWith(".xml")) return normalizeXlsxSymbols(xml, counts);
        return xml;
    }

    private static String normalizeDocxSymbols(String xml, Map<String, Integer> counts) {
        String out = xml;
        for (Map.Entry<String, SymbolRule> e : SYMBOLS.entrySet()) {
            String symbol = e.getKey();
            SymbolRule rule = e.getValue();
            List<Pattern> patterns = List.of(
                    Pattern.compile("<w:r><w:rPr></w:rPr><w:t([^>]*)>" + Pattern.quote(symbol) + "( ?)</w:t></w:r>"),
                    Pattern.compile("<w:r><w:rPr\\s*/><w:t([^>]*)>" + Pattern.quote(symbol) + "( ?)</w:t></w:r>"),
                    Pattern.compile("<w:r><w:t([^>]*)>" + Pattern.quote(symbol) + "( ?)</w:t></w:r>"));
            String rpr = "<w:rPr><w:rFonts w:ascii=\"DejaVu Sans\" w:hAnsi=\"DejaVu Sans\" "
                    + "w:eastAsia=\"DejaVu Sans\" w:cs=\"DejaVu Sans\"/>"
                    + "<w:color w:val=\"" + rule.rgb() + "\"/></w:rPr>";
            for (Pattern p : patterns) {
                Matcher m = p.matcher(out);
                StringBuffer sb = new StringBuffer();
                while (m.find()) {
                    counts.merge(symbol, 1, Integer::sum);
                    String replacement = "<w:r>" + rpr + "<w:t" + m.group(1) + ">"
                            + rule.replacement() + m.group(2) + "</w:t></w:r>";
                    m.appendReplacement(sb, Matcher.quoteReplacement(replacement));
                }
                m.appendTail(sb);
                out = sb.toString();
            }
        }
        return out;
    }

    private static String normalizePptxSymbols(String xml, Map<String, Integer> counts) {
        String out = xml;
        for (Map.Entry<String, SymbolRule> e : SYMBOLS.entrySet()) {
            String symbol = e.getKey();
            SymbolRule rule = e.getValue();
            List<Pattern> patterns = List.of(
                    Pattern.compile("<a:r><a:rPr\\s*/><a:t>" + Pattern.quote(symbol) + "( ?)</a:t></a:r>"),
                    Pattern.compile("<a:r><a:t>" + Pattern.quote(symbol) + "( ?)</a:t></a:r>"));
            String rpr = "<a:rPr><a:solidFill><a:srgbClr val=\"" + rule.rgb()
                    + "\"/></a:solidFill><a:latin typeface=\"DejaVu Sans\"/></a:rPr>";
            for (Pattern p : patterns) {
                Matcher m = p.matcher(out);
                StringBuffer sb = new StringBuffer();
                while (m.find()) {
                    counts.merge(symbol, 1, Integer::sum);
                    String replacement = "<a:r>" + rpr + "<a:t>" + rule.replacement() + m.group(1) + "</a:t></a:r>";
                    m.appendReplacement(sb, Matcher.quoteReplacement(replacement));
                }
                m.appendTail(sb);
                out = sb.toString();
            }
        }
        return out;
    }

    private static String normalizeXlsxSymbols(String xml, Map<String, Integer> counts) {
        String out = xml;
        for (Map.Entry<String, SymbolRule> e : SYMBOLS.entrySet()) {
            String symbol = e.getKey();
            SymbolRule rule = e.getValue();
            List<Pattern> patterns = List.of(
                    Pattern.compile("<r><rPr\\s*/><t([^>]*)>" + Pattern.quote(symbol) + "( ?)</t></r>"),
                    Pattern.compile("<r><t([^>]*)>" + Pattern.quote(symbol) + "( ?)</t></r>"));
            String rpr = "<rPr><rFont val=\"DejaVu Sans\"/><color rgb=\"FF" + rule.rgb() + "\"/></rPr>";
            for (Pattern p : patterns) {
                Matcher m = p.matcher(out);
                StringBuffer sb = new StringBuffer();
                while (m.find()) {
                    counts.merge(symbol, 1, Integer::sum);
                    String replacement = "<r>" + rpr + "<t" + m.group(1) + ">"
                            + rule.replacement() + m.group(2) + "</t></r>";
                    m.appendReplacement(sb, Matcher.quoteReplacement(replacement));
                }
                m.appendTail(sb);
                out = sb.toString();
            }
        }
        return out;
    }
}
