package io.github.p4535992.ooxmlcompatnormalize;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class NormalizerTest {
    @TempDir
    Path tempDir;

    @Test
    void preservesPartsAndNormalizesKnownDocxMarkup() throws Exception {
        Path input = tempDir.resolve("input.docx");
        Path output = tempDir.resolve("output.docx");

        String document = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
                + "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
                + "<w:body><w:p><w:r><w:rPr><w:rFonts w:ascii=\"Arial\" w:hAnsi=\"Arial\"/></w:rPr>"
                + "<w:t>Hello</w:t></w:r><w:r><w:t>🔴 </w:t></w:r></w:p></w:body></w:document>";

        try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(input))) {
            add(zip, "[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>");
            add(zip, "word/document.xml", document);
            add(zip, "custom/unknown.bin", "opaque");
        }

        Normalizer.Result result = Normalizer.normalize(
                input,
                output,
                new Normalizer.Options(
                        "interop-transitional-v1",
                        Map.of("Arial", "Liberation Sans"),
                        true));

        assertEquals(Normalizer.Kind.DOCX, result.kind());
        assertEquals(Set.of("[Content_Types].xml", "word/document.xml", "custom/unknown.bin"), Normalizer.packageNames(output));
        assertTrue(result.changedParts().contains("word/document.xml"));

        try (ZipFile zip = new ZipFile(output.toFile())) {
            String xml = new String(zip.getInputStream(zip.getEntry("word/document.xml")).readAllBytes(), StandardCharsets.UTF_8);
            assertTrue(xml.contains("Liberation Sans"));
            assertTrue(xml.contains("w:color w:val=\"FF0000\""));
            assertTrue(xml.contains("● "));
            assertFalse(xml.contains("🔴"));
            assertEquals("opaque", new String(zip.getInputStream(zip.getEntry("custom/unknown.bin")).readAllBytes(), StandardCharsets.UTF_8));
        }
    }

    private static void add(ZipOutputStream zip, String name, String text) throws Exception {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(text.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }
}
