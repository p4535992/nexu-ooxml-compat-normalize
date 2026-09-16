package io.github.p4535992.ooxmlcompatnormalize.quarkus;

import io.github.p4535992.ooxmlcompatnormalize.LibraryValidation;
import io.github.p4535992.ooxmlcompatnormalize.Normalizer;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.DefaultValue;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.WebApplicationException;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import org.jboss.logging.Logger;

import java.io.IOException;
import java.nio.file.Files;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Path("/api")
public class NormalizeResource {

    private static final Logger LOG = Logger.getLogger(NormalizeResource.class);

    private static final Set<String> PROFILES = Set.of(
            "preserve-v1",
            "interop-transitional-v1",
            "portable-explicit-v1"
    );

    @GET
    @Path("/info")
    @Produces(MediaType.APPLICATION_JSON)
    public InfoResponse info() {
        return new InfoResponse(
                "ooxml-compat-normalize-quarkus",
                "0.4.0-rc.9",
                List.of("docx", "xlsx", "pptx"),
                List.copyOf(PROFILES)
        );
    }

    @POST
    @Path("/audit")
    @Consumes(MediaType.APPLICATION_OCTET_STREAM)
    @Produces(MediaType.APPLICATION_JSON)
    public AuditResponse audit(byte[] body, @HeaderParam("X-Filename") String filename) throws IOException {
        String safeName = validateFilename(filename);
        LOG.infof("Audit requested: file=%s bytes=%d", safeName, body == null ? 0 : body.length);
        java.nio.file.Path input = writeTemp(body, safeName);
        try {
            Set<String> parts = Normalizer.packageNames(input);
            Normalizer.Kind kind = Normalizer.detectKind(parts);
            LibraryValidation.Result validation = LibraryValidation.validate(input);
            LOG.infof(
                    "Audit completed: file=%s kind=%s parts=%d poi=%s docx4j=%s",
                    safeName,
                    kind,
                    parts.size(),
                    validation.poiValid(),
                    validation.docx4jValid()
            );
            return new AuditResponse(
                    safeName,
                    kind.name(),
                    parts.size(),
                    Normalizer.inventoryFonts(input),
                    validation.poiValid(),
                    validation.poiPartCount(),
                    validation.docx4jValid(),
                    validation.docx4jPackageType(),
                    validation.poiError(),
                    validation.docx4jError()
            );
        } finally {
            Files.deleteIfExists(input);
        }
    }

    @POST
    @Path("/normalize")
    @Consumes(MediaType.APPLICATION_OCTET_STREAM)
    @Produces(MediaType.APPLICATION_OCTET_STREAM)
    public Response normalize(
            byte[] body,
            @HeaderParam("X-Filename") String filename,
            @QueryParam("profile") @DefaultValue("interop-transitional-v1") String profile
    ) throws IOException {
        String safeName = validateFilename(filename);
        if (!PROFILES.contains(profile)) {
            throw new WebApplicationException("Unsupported profile: " + profile, Response.Status.BAD_REQUEST);
        }

        LOG.infof(
                "Normalization requested: file=%s bytes=%d profile=%s",
                safeName,
                body == null ? 0 : body.length,
                profile
        );

        java.nio.file.Path input = writeTemp(body, safeName);
        String suffix = extensionOf(safeName);
        java.nio.file.Path output = Files.createTempFile("ooxml-normalized-", suffix);
        try {
            LibraryValidation.Result pre = LibraryValidation.validate(input);
            if (!pre.valid()) {
                LOG.warnf("Pre-flight rejected file=%s poi=%s docx4j=%s", safeName, pre.poiValid(), pre.docx4jValid());
                throw new WebApplicationException(
                        "Input cannot be parsed by both Apache POI and docx4j",
                        422
                );
            }

            Normalizer.Result result = Normalizer.normalize(
                    input,
                    output,
                    new Normalizer.Options(profile, Map.of(), true)
            );

            LibraryValidation.Result post = LibraryValidation.validate(output);
            if (!post.valid()) {
                LOG.errorf("Post-flight failed file=%s poi=%s docx4j=%s", safeName, post.poiValid(), post.docx4jValid());
                throw new WebApplicationException(
                        "Normalized output failed Java post-flight validation",
                        Response.Status.INTERNAL_SERVER_ERROR
                );
            }

            byte[] normalized = Files.readAllBytes(output);
            String outputName = stemOf(safeName) + "-normalized" + suffix;
            LOG.infof(
                    "Normalization completed: file=%s kind=%s changedParts=%d outputBytes=%d",
                    safeName,
                    result.kind(),
                    result.changedParts().size(),
                    normalized.length
            );
            return Response.ok(normalized, MediaType.APPLICATION_OCTET_STREAM_TYPE)
                    .header("Content-Disposition", "attachment; filename=\"" + outputName + "\"")
                    .header("X-OOXML-Kind", result.kind().name())
                    .header("X-OOXML-Changed-Parts", Integer.toString(result.changedParts().size()))
                    .build();
        } finally {
            Files.deleteIfExists(input);
            Files.deleteIfExists(output);
        }
    }

    private static java.nio.file.Path writeTemp(byte[] body, String filename) throws IOException {
        if (body == null || body.length == 0) {
            throw new WebApplicationException("Empty file", Response.Status.BAD_REQUEST);
        }
        java.nio.file.Path path = Files.createTempFile("ooxml-input-", extensionOf(filename));
        Files.write(path, body);
        return path;
    }

    private static String validateFilename(String filename) {
        if (filename == null || filename.isBlank()) {
            throw new WebApplicationException("X-Filename header is required", Response.Status.BAD_REQUEST);
        }
        String normalized = filename.replace('\\', '/');
        String safe = normalized.substring(normalized.lastIndexOf('/') + 1).trim();
        String ext = extensionOf(safe);
        if (!Set.of(".docx", ".xlsx", ".pptx").contains(ext)) {
            throw new WebApplicationException("Only DOCX, XLSX and PPTX are supported", Response.Status.BAD_REQUEST);
        }
        return safe.replace("\"", "_");
    }

    private static String extensionOf(String filename) {
        int dot = filename.lastIndexOf('.');
        return dot < 0 ? "" : filename.substring(dot).toLowerCase();
    }

    private static String stemOf(String filename) {
        int dot = filename.lastIndexOf('.');
        return dot < 0 ? filename : filename.substring(0, dot);
    }

    public record InfoResponse(String name, String version, List<String> formats, List<String> profiles) {}

    public record AuditResponse(
            String filename,
            String kind,
            int packageParts,
            Set<String> fonts,
            boolean poiValid,
            int poiPartCount,
            boolean docx4jValid,
            String docx4jPackageType,
            String poiError,
            String docx4jError
    ) {}
}
