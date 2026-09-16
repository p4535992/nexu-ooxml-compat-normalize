package io.github.p4535992.ooxmlcompatnormalize;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Standalone Java CLI for the OOXML normalizer. */
public final class Main {
    private Main() {}

    public static void main(String[] args) {
        int code;
        try {
            code = run(args);
        } catch (Exception ex) {
            System.err.println("error: " + ex.getMessage());
            code = 2;
        }
        if (code != 0) System.exit(code);
    }

    static int run(String[] args) throws Exception {
        if (args.length == 0 || has(args, "--help") || has(args, "-h")) {
            printHelp();
            return 0;
        }

        List<String> positional = new ArrayList<>();
        String profile = "interop-transitional-v1";
        boolean normalizeColors = true;
        boolean auditOnly = false;
        boolean requireJavaParsers = true;
        Map<String, String> fontMap = new LinkedHashMap<>();

        for (int i = 0; i < args.length; i++) {
            String arg = args[i];
            switch (arg) {
                case "--audit-only" -> auditOnly = true;
                case "--no-semantic-colors" -> normalizeColors = false;
                case "--no-library-validation" -> requireJavaParsers = false;
                case "--profile" -> profile = requireValue(args, ++i, arg);
                case "--font-profile" -> {
                    String value = requireValue(args, ++i, arg);
                    if ("compat".equalsIgnoreCase(value) || "liberation".equalsIgnoreCase(value)) {
                        fontMap.putAll(Normalizer.COMPAT_FONT_MAP);
                    } else if (!"preserve".equalsIgnoreCase(value)) {
                        throw new IllegalArgumentException("Unknown --font-profile: " + value);
                    }
                }
                case "--font-map" -> {
                    String value = requireValue(args, ++i, arg);
                    int eq = value.indexOf('=');
                    if (eq <= 0 || eq == value.length() - 1) {
                        throw new IllegalArgumentException("--font-map expects OLD=NEW");
                    }
                    fontMap.put(value.substring(0, eq).trim(), value.substring(eq + 1).trim());
                }
                default -> {
                    if (arg.startsWith("-")) throw new IllegalArgumentException("Unknown option: " + arg);
                    positional.add(arg);
                }
            }
        }

        if (!Set.of("preserve-v1", "interop-transitional-v1", "portable-explicit-v1").contains(profile)) {
            throw new IllegalArgumentException("Unsupported profile: " + profile);
        }

        if (positional.isEmpty()) throw new IllegalArgumentException("Missing input file");
        Path input = Path.of(positional.get(0));

        if (auditOnly) {
            printAudit(input, requireJavaParsers);
            return 0;
        }
        if (positional.size() < 2) throw new IllegalArgumentException("Missing output file");
        Path output = Path.of(positional.get(1));

        LibraryValidation.Result pre = LibraryValidation.validate(input);
        if (requireJavaParsers && !pre.valid()) {
            throw new IllegalStateException("Java pre-flight validation failed: " + validationSummary(pre));
        }

        Normalizer.Options options = new Normalizer.Options(profile, fontMap, normalizeColors);
        Normalizer.Result result = Normalizer.normalize(input, output, options);

        LibraryValidation.Result post = LibraryValidation.validate(output);
        if (requireJavaParsers && !post.valid()) {
            throw new IllegalStateException("Java post-flight validation failed: " + validationSummary(post));
        }

        System.out.println("OK " + input + " -> " + output);
        System.out.println("kind=" + result.kind());
        System.out.println("profile=" + profile);
        System.out.println("parts=" + result.partCount());
        System.out.println("changedParts=" + result.changedParts());
        System.out.println("fontMappings=" + result.fontMappings());
        System.out.println("semanticColorMappings=" + result.semanticColorMappings());
        System.out.println("preflight.poi=" + pre.poiValid() + " parts=" + pre.poiPartCount());
        System.out.println("preflight.docx4j=" + pre.docx4jValid() + " type=" + pre.docx4jPackageType());
        System.out.println("postflight.poi=" + post.poiValid() + " parts=" + post.poiPartCount());
        System.out.println("postflight.docx4j=" + post.docx4jValid() + " type=" + post.docx4jPackageType());
        if ("portable-explicit-v1".equals(profile)) {
            System.out.println("warning=Java companion currently implements the conservative package/font/semantic-color layer; advanced theme/default materialization remains in the Python engine until ported and cross-tested.");
        }
        return 0;
    }

    private static void printAudit(Path input, boolean requireJavaParsers) throws IOException {
        Set<String> parts = Normalizer.packageNames(input);
        Normalizer.Kind kind = Normalizer.detectKind(parts);
        Set<String> fonts = FontInventory.scan(input);
        LibraryValidation.Result libraries = LibraryValidation.validate(input);

        System.out.println("file=" + input);
        System.out.println("kind=" + kind);
        System.out.println("parts=" + parts.size());
        System.out.println("fonts=" + fonts);
        System.out.println("poi.valid=" + libraries.poiValid());
        System.out.println("poi.parts=" + libraries.poiPartCount());
        System.out.println("docx4j.valid=" + libraries.docx4jValid());
        System.out.println("docx4j.packageType=" + libraries.docx4jPackageType());
        if (!libraries.poiValid()) System.out.println("poi.error=" + libraries.poiError());
        if (!libraries.docx4jValid()) System.out.println("docx4j.error=" + libraries.docx4jError());
        if (requireJavaParsers && !libraries.valid()) {
            throw new IllegalStateException("Java library validation failed: " + validationSummary(libraries));
        }
    }

    private static String validationSummary(LibraryValidation.Result result) {
        return "POI=" + result.poiValid()
                + (result.poiError() == null ? "" : " (" + result.poiError() + ")")
                + ", docx4j=" + result.docx4jValid()
                + (result.docx4jError() == null ? "" : " (" + result.docx4jError() + ")");
    }

    private static boolean has(String[] args, String value) {
        for (String arg : args) if (value.equals(arg)) return true;
        return false;
    }

    private static String requireValue(String[] args, int index, String option) {
        if (index >= args.length) throw new IllegalArgumentException(option + " requires a value");
        return args[index];
    }

    private static void printHelp() {
        System.out.println("ooxml-compat-normalize Java companion");
        System.out.println();
        System.out.println("Usage:");
        System.out.println("  java -jar ooxml-compat-normalize-java.jar INPUT OUTPUT [options]");
        System.out.println("  java -jar ooxml-compat-normalize-java.jar INPUT --audit-only");
        System.out.println();
        System.out.println("Options:");
        System.out.println("  --profile preserve-v1|interop-transitional-v1|portable-explicit-v1");
        System.out.println("  --font-profile preserve|compat");
        System.out.println("  --font-map OLD=NEW        repeatable explicit mapping");
        System.out.println("  --no-semantic-colors      preserve renderer-dependent color emoji/symbols");
        System.out.println("  --no-library-validation   do not fail when POI/docx4j cannot parse the file");
        System.out.println();
        System.out.println("Default font policy: preserve declared font identities exactly.");
        System.out.println("Validation: Apache POI + docx4j before and after normalization.");
    }
}
