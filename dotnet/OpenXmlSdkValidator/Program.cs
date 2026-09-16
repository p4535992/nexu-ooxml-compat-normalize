using System.Reflection;
using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;

namespace OpenXmlSdkValidator;

internal static class Program
{
    private const int DefaultMaxErrors = 200;

    private sealed record ValidationItem(
        string Description,
        string? Part,
        string? Path,
        string? Node,
        string? ErrorType,
        string? Id);

    private sealed record ValidationResult(
        bool Valid,
        string DocumentKind,
        string SdkVersion,
        string FileFormatVersion,
        int ErrorCount,
        bool Truncated,
        IReadOnlyList<ValidationItem> Errors);

    public static int Main(string[] args)
    {
        if (args.Length == 0 || args.Contains("--help") || args.Contains("-h"))
        {
            Console.WriteLine("Usage: OpenXmlSdkValidator <file.docx|file.xlsx|file.pptx> [--max-errors N]");
            return args.Length == 0 ? 2 : 0;
        }

        var path = args[0];
        var maxErrors = ParseMaxErrors(args) ?? DefaultMaxErrors;
        if (!File.Exists(path))
        {
            WriteFailure("File not found: " + path);
            return 2;
        }

        try
        {
            var result = Validate(path, maxErrors);
            Console.WriteLine(JsonSerializer.Serialize(result, new JsonSerializerOptions
            {
                WriteIndented = true,
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            }));
            return result.Valid ? 0 : 3;
        }
        catch (Exception ex)
        {
            WriteFailure(ex.Message, ex.GetType().FullName);
            return 2;
        }
    }

    private static int? ParseMaxErrors(string[] args)
    {
        for (var i = 1; i < args.Length - 1; i++)
        {
            if (args[i] == "--max-errors" && int.TryParse(args[i + 1], out var parsed) && parsed > 0)
            {
                return parsed;
            }
        }
        return null;
    }

    private static ValidationResult Validate(string path, int maxErrors)
    {
        var extension = Path.GetExtension(path).ToLowerInvariant();
        var kind = extension switch
        {
            ".docx" => "docx",
            ".xlsx" => "xlsx",
            ".pptx" => "pptx",
            _ => throw new InvalidOperationException("Unsupported extension. Expected DOCX, XLSX or PPTX."),
        };

        using OpenXmlPackage package = extension switch
        {
            ".docx" => WordprocessingDocument.Open(path, false),
            ".xlsx" => SpreadsheetDocument.Open(path, false),
            ".pptx" => PresentationDocument.Open(path, false),
            _ => throw new InvalidOperationException("Unsupported OOXML package."),
        };

        // Microsoft365 is intentionally used as the broad validation target. The
        // normalizer's own pre-flight separately records Strict/Transitional details.
        var target = FileFormatVersions.Microsoft365;
        var validator = new OpenXmlValidator(target);
        var collected = new List<ValidationItem>();
        var total = 0;

        foreach (var error in validator.Validate(package))
        {
            total++;
            if (collected.Count >= maxErrors)
            {
                continue;
            }

            collected.Add(new ValidationItem(
                error.Description ?? "Open XML SDK validation error",
                error.Part?.Uri?.ToString(),
                error.Path?.XPath,
                error.Node?.LocalName,
                error.ErrorType.ToString(),
                error.Id));
        }

        var sdkVersion = typeof(OpenXmlPackage).Assembly
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion
            ?? typeof(OpenXmlPackage).Assembly.GetName().Version?.ToString()
            ?? "unknown";

        return new ValidationResult(
            Valid: total == 0,
            DocumentKind: kind,
            SdkVersion: sdkVersion,
            FileFormatVersion: target.ToString(),
            ErrorCount: total,
            Truncated: total > collected.Count,
            Errors: collected);
    }

    private static void WriteFailure(string message, string? exceptionType = null)
    {
        var payload = new
        {
            valid = false,
            operationalError = true,
            message,
            exceptionType,
        };
        Console.WriteLine(JsonSerializer.Serialize(payload, new JsonSerializerOptions
        {
            WriteIndented = true,
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        }));
    }
}
