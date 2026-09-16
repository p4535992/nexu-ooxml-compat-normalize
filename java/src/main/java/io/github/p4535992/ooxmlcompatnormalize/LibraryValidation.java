package io.github.p4535992.ooxmlcompatnormalize;

import java.nio.file.Path;
import org.apache.poi.openxml4j.opc.OPCPackage;
import org.apache.poi.openxml4j.opc.PackageAccess;
import org.docx4j.openpackaging.packages.OpcPackage;

/** Independent open-source Java parser checks used before and after normalization. */
public final class LibraryValidation {
    private LibraryValidation() {}

    public record Result(
            boolean poiValid,
            int poiPartCount,
            boolean docx4jValid,
            String docx4jPackageType,
            String poiError,
            String docx4jError) {
        public boolean valid() {
            return poiValid && docx4jValid;
        }
    }

    public static Result validate(Path path) {
        boolean poiValid = false;
        int poiParts = -1;
        String poiError = null;
        try (OPCPackage pkg = OPCPackage.open(path.toFile(), PackageAccess.READ)) {
            poiParts = pkg.getParts().size();
            poiValid = true;
        } catch (Exception ex) {
            poiError = ex.getClass().getSimpleName() + ": " + safeMessage(ex);
        }

        boolean docx4jValid = false;
        String docx4jType = null;
        String docx4jError = null;
        try {
            OpcPackage pkg = OpcPackage.load(path.toFile());
            docx4jType = pkg.getClass().getSimpleName();
            docx4jValid = true;
        } catch (Exception ex) {
            docx4jError = ex.getClass().getSimpleName() + ": " + safeMessage(ex);
        }

        return new Result(poiValid, poiParts, docx4jValid, docx4jType, poiError, docx4jError);
    }

    private static String safeMessage(Throwable ex) {
        String message = ex.getMessage();
        return message == null || message.isBlank() ? "no message" : message.replace('\n', ' ').replace('\r', ' ');
    }
}
