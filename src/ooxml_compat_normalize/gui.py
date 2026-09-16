from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText

from .analysis import analyze_ooxml
from .normalizer import DEFAULT_LIBERATION_FONT_MAP, NormalizationOptions, normalize_ooxml
from .sdk_validator import find_openxml_sdk_validator, validate_with_openxml_sdk
from .profile import (
    INTEROP_TRANSITIONAL_V1,
    PORTABLE_EXPLICIT_V1,
    PRESERVE_V1,
    FontPolicy,
)


PROFILE_LABELS = {
    "Interop consigliato": INTEROP_TRANSITIONAL_V1,
    "Portable esplicito": PORTABLE_EXPLICIT_V1,
    "Preserva struttura": PRESERVE_V1,
}

PROFILE_SUFFIXES = {
    "Interop consigliato": "normalized",
    "Portable esplicito": "portable",
    "Preserva struttura": "preserved",
}

FONT_MODE_PRESERVE = "Preserva esattamente i font originali"
FONT_MODE_MISSING = "Sostituisci solo i font mancanti"
FONT_MODE_COMPAT = "Forza profilo compatibile"
FONT_MODE_CUSTOM = "Mapping personalizzato"
FONT_MODE_LABELS = (
    FONT_MODE_PRESERVE,
    FONT_MODE_MISSING,
    FONT_MODE_COMPAT,
    FONT_MODE_CUSTOM,
)

FONT_MODE_HELP = {
    FONT_MODE_PRESERVE: (
        "Default consigliato: mantiene esattamente le famiglie dichiarate nel documento. "
        "Non applica mapping automatici."
    ),
    FONT_MODE_MISSING: (
        "Mantiene ogni font già disponibile su questo computer. Solo per i font mancanti prova "
        "un fallback metrico noto (Liberation/Carlito/Caladea) e solo se il fallback è installato."
    ),
    FONT_MODE_COMPAT: (
        "Applica sempre il profilo compatibile noto: Times New Roman→Liberation Serif, "
        "Arial→Liberation Sans, Courier New→Liberation Mono, Calibri→Carlito, Cambria→Caladea."
    ),
    FONT_MODE_CUSTOM: (
        "Applica il mapping definito qui sotto. Usa OLD=NEW separati da punto e virgola o nuova riga."
    ),
}

SUPPORTED_EXTENSIONS = {".docx", ".xlsx", ".pptx"}


def _suggest_output(src: Path, output_dir: Path, label: str) -> Path:
    return output_dir / f"{src.stem}-{PROFILE_SUFFIXES[label]}{src.suffix.lower()}"


def _parse_custom_font_map(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in re.split(r"[;\n]+", text):
        value = raw.strip()
        if not value:
            continue
        if "=" not in value:
            raise ValueError(f"Mapping font non valido: {value!r}. Usa OLD=NEW")
        old, new = value.split("=", 1)
        old, new = old.strip(), new.strip()
        if not old or not new:
            raise ValueError(f"Mapping font non valido: {value!r}. Usa OLD=NEW")
        mapping[old] = new
    return mapping


def _build_missing_only_font_map(
    required_fonts: list[str] | tuple[str, ...],
    available_fonts: frozenset[str],
    fallback_map: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    """Return safe known mappings only for source fonts missing on the target machine.

    A mapping is applied only when both conditions are true:
    - the source family is not installed;
    - the known fallback family is installed.

    Missing fonts without an installed known fallback remain unchanged and are reported.
    """
    available_folded = {font.casefold() for font in available_fonts}
    mapping: dict[str, str] = {}
    unresolved: list[str] = []

    for font in required_fonts:
        if font.casefold() in available_folded:
            continue
        fallback = fallback_map.get(font)
        if fallback and fallback.casefold() in available_folded:
            mapping[font] = fallback
        else:
            unresolved.append(font)

    return mapping, sorted(set(unresolved), key=str.casefold)


def _filter_custom_map_to_missing(
    custom_map: dict[str, str],
    required_fonts: list[str] | tuple[str, ...],
    available_fonts: frozenset[str],
) -> tuple[dict[str, str], list[str]]:
    """Apply a user mapping only to missing source fonts and verify target availability."""
    available_folded = {font.casefold() for font in available_fonts}
    required_folded = {font.casefold(): font for font in required_fonts}
    mapping: dict[str, str] = {}
    unresolved: list[str] = []

    for old, new in custom_map.items():
        actual = required_folded.get(old.casefold())
        if actual is None or actual.casefold() in available_folded:
            continue
        if new.casefold() in available_folded:
            mapping[actual] = new
        else:
            unresolved.append(f"{actual} → {new}")

    return mapping, sorted(set(unresolved), key=str.casefold)


def _format_analysis(path: Path, available_fonts: frozenset[str] | None = None) -> str:
    analysis = analyze_ooxml(path).to_dict()
    sdk = validate_with_openxml_sdk(path, mode="auto")
    required_fonts = list(analysis["required_fonts"])
    lines = [
        f"File: {path.name}",
        f"Tipo: {analysis['document_kind'].upper()}",
        f"Produttore: {analysis.get('producer') or 'non dichiarato'}",
        f"Conformance: {analysis['conformance']}",
        f"Font richiesti: {', '.join(required_fonts) or 'nessuno rilevato'}",
        f"Theme: {'sì' if analysis['has_theme'] else 'no'}",
    ]

    if available_fonts is not None and required_fonts:
        available_folded = {font.casefold() for font in available_fonts}
        missing = [font for font in required_fonts if font.casefold() not in available_folded]
        lines.append(f"Font locali disponibili: {len(required_fonts) - len(missing)}/{len(required_fonts)}")
        if missing:
            lines.append("Font mancanti su questo computer: " + ", ".join(missing))
        else:
            lines.append("Font mancanti su questo computer: nessuno")

    if sdk.get("available"):
        if sdk.get("valid") is True:
            lines.append(f"Open XML SDK: valido ({sdk.get('sdkVersion', 'versione sconosciuta')})")
        elif sdk.get("valid") is False:
            lines.append(f"Open XML SDK: {sdk.get('errorCount', '?')} errore/i")
    else:
        lines.append("Open XML SDK: validator non disponibile in questa build")
    if analysis["semantic_color_symbols"]:
        lines.append(
            "Simboli colore: "
            + ", ".join(f"{k}×{v}" for k, v in analysis["semantic_color_symbols"].items())
        )
    if analysis["diagnostics"]:
        lines.append("Diagnostica: " + json.dumps(analysis["diagnostics"], ensure_ascii=False))
    if analysis["risks"]:
        lines.append("Rischi:")
        for risk in analysis["risks"]:
            where = f" [{risk['part']}]" if risk.get("part") else ""
            lines.append(f"  - {risk['severity'].upper()} {risk['code']}{where}: {risk['message']}")
    else:
        lines.append("Rischi: nessuno rilevato dalle regole correnti")
    return "\n".join(lines)


class NormalizerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OOXML Compat Normalizer")
        self.geometry("900x720")
        self.minsize(760, 600)
        self.files: list[Path] = []
        self._font_inventory_snapshot: frozenset[str] = frozenset()

        try:
            if os.name == "nt":
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self.profile_var = tk.StringVar(value="Interop consigliato")
        self.font_mode_var = tk.StringVar(value=FONT_MODE_PRESERVE)
        self.custom_font_map_var = tk.StringVar(value="")
        self.custom_missing_only_var = tk.BooleanVar(value=False)
        self.font_help_var = tk.StringVar(value=FONT_MODE_HELP[FONT_MODE_PRESERVE])
        self.font_inventory_var = tk.StringVar(value="Inventario font locale: non ancora analizzato")
        self.report_var = tk.BooleanVar(value=True)
        self.output_dir_var = tk.StringVar(value=str(Path.home() / "Documents"))
        validator = find_openxml_sdk_validator()
        sdk_text = "Open XML SDK integrato" if validator else "Open XML SDK non disponibile"
        self.status_var = tk.StringVar(value=f"Seleziona uno o più file DOCX, XLSX o PPTX. {sdk_text}.")

        self._build_ui()
        self._on_font_mode_changed()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 7}
        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Button(top, text="Seleziona file…", command=self.select_files).pack(side="left")
        ttk.Button(top, text="Rimuovi tutti", command=self.clear_files).pack(side="left", padx=8)
        ttk.Button(top, text="Analizza", command=self.analyze_selected).pack(side="right")

        self.file_list = tk.Listbox(self, height=6, selectmode=tk.EXTENDED)
        self.file_list.pack(fill="x", **pad)

        settings = ttk.LabelFrame(self, text="Output")
        settings.pack(fill="x", **pad)

        ttk.Label(settings, text="Profilo:").grid(row=0, column=0, sticky="w", padx=8, pady=7)
        profile = ttk.Combobox(
            settings,
            textvariable=self.profile_var,
            values=list(PROFILE_LABELS),
            state="readonly",
            width=24,
        )
        profile.grid(row=0, column=1, sticky="w", padx=8, pady=7)

        ttk.Label(settings, text="Cartella:").grid(row=1, column=0, sticky="w", padx=8, pady=7)
        ttk.Entry(settings, textvariable=self.output_dir_var).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=7
        )
        ttk.Button(settings, text="Sfoglia…", command=self.select_output_dir).grid(
            row=1, column=3, sticky="e", padx=8, pady=7
        )
        ttk.Checkbutton(settings, text="Salva report JSON", variable=self.report_var).grid(
            row=2, column=1, sticky="w", padx=8, pady=7
        )
        settings.columnconfigure(2, weight=1)

        fonts = ttk.LabelFrame(self, text="Gestione font")
        fonts.pack(fill="x", **pad)
        ttk.Label(fonts, text="Modalità:").grid(row=0, column=0, sticky="w", padx=8, pady=7)
        font_mode = ttk.Combobox(
            fonts,
            textvariable=self.font_mode_var,
            values=FONT_MODE_LABELS,
            state="readonly",
            width=42,
        )
        font_mode.grid(row=0, column=1, sticky="w", padx=8, pady=7)
        font_mode.bind("<<ComboboxSelected>>", lambda _event: self._on_font_mode_changed())

        ttk.Label(
            fonts,
            textvariable=self.font_help_var,
            wraplength=760,
            justify="left",
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 7))

        ttk.Label(fonts, text="Mapping custom:").grid(row=2, column=0, sticky="w", padx=8, pady=7)
        self.custom_font_map_entry = ttk.Entry(fonts, textvariable=self.custom_font_map_var)
        self.custom_font_map_entry.grid(row=2, column=1, columnspan=3, sticky="ew", padx=8, pady=7)

        self.custom_missing_only_check = ttk.Checkbutton(
            fonts,
            text="Nel mapping personalizzato, sostituisci solo se il font originale manca",
            variable=self.custom_missing_only_var,
        )
        self.custom_missing_only_check.grid(row=3, column=1, columnspan=3, sticky="w", padx=8, pady=(0, 7))

        ttk.Label(
            fonts,
            text="Esempio: Arial=Liberation Sans; Times New Roman=Liberation Serif",
        ).grid(row=4, column=1, columnspan=3, sticky="w", padx=8, pady=(0, 7))

        ttk.Label(fonts, textvariable=self.font_inventory_var).grid(
            row=5, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 7)
        )
        fonts.columnconfigure(3, weight=1)

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)
        self.normalize_button = ttk.Button(actions, text="Normalizza / Esporta", command=self.normalize_selected)
        self.normalize_button.pack(side="right")
        ttk.Label(actions, textvariable=self.status_var).pack(side="left")

        self.log = ScrolledText(self, height=16, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, **pad)

    def _on_font_mode_changed(self) -> None:
        mode = self.font_mode_var.get()
        self.font_help_var.set(FONT_MODE_HELP.get(mode, ""))
        custom = mode == FONT_MODE_CUSTOM
        self.custom_font_map_entry.configure(state="normal" if custom else "disabled")
        self.custom_missing_only_check.configure(state="normal" if custom else "disabled")

    def _collect_local_font_inventory(self) -> frozenset[str]:
        try:
            families = {
                str(name).strip()
                for name in tkfont.families(self)
                if str(name).strip()
            }
        except tk.TclError:
            families = set()
        inventory = frozenset(families)
        self._font_inventory_snapshot = inventory
        self.font_inventory_var.set(f"Inventario font locale: {len(inventory)} famiglie rilevate")
        return inventory

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def select_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Seleziona documenti OOXML",
            filetypes=[
                ("OOXML", "*.docx *.xlsx *.pptx"),
                ("Word DOCX", "*.docx"),
                ("Excel XLSX", "*.xlsx"),
                ("PowerPoint PPTX", "*.pptx"),
                ("Tutti i file", "*.*"),
            ],
        )
        if not paths:
            return
        for raw in paths:
            path = Path(raw)
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                self._append_log(f"Ignorato formato non supportato: {path}")
                continue
            if path not in self.files:
                self.files.append(path)
                self.file_list.insert("end", str(path))
        if self.files:
            self.output_dir_var.set(str(self.files[0].parent))
            self.status_var.set(f"{len(self.files)} file selezionati")

    def clear_files(self) -> None:
        self.files.clear()
        self.file_list.delete(0, "end")
        self.status_var.set("Nessun file selezionato")

    def select_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Cartella di output", initialdir=self.output_dir_var.get())
        if path:
            self.output_dir_var.set(path)

    def analyze_selected(self) -> None:
        if not self.files:
            messagebox.showinfo("OOXML Compat Normalizer", "Seleziona almeno un file.")
            return
        self._collect_local_font_inventory()
        self._run_worker(self._analyze_worker, "Analisi in corso…")

    def normalize_selected(self) -> None:
        if not self.files:
            messagebox.showinfo("OOXML Compat Normalizer", "Seleziona almeno un file.")
            return
        if self.font_mode_var.get() == FONT_MODE_CUSTOM:
            try:
                custom = _parse_custom_font_map(self.custom_font_map_var.get())
            except ValueError as exc:
                messagebox.showerror("Mapping font non valido", str(exc))
                return
            if not custom:
                messagebox.showerror("Mapping font non valido", "Inserisci almeno un mapping OLD=NEW.")
                return
        self._collect_local_font_inventory()
        self._run_worker(self._normalize_worker, "Normalizzazione in corso…")

    def _run_worker(self, callback, status: str) -> None:
        self.normalize_button.configure(state="disabled")
        self.status_var.set(status)

        def run() -> None:
            try:
                callback()
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Errore", str(exc)))
                self.after(0, lambda: self._append_log(f"ERRORE: {exc}"))
            finally:
                self.after(0, lambda: self.normalize_button.configure(state="normal"))
                self.after(0, lambda: self.status_var.set("Operazione completata"))

        threading.Thread(target=run, daemon=True).start()

    def _analyze_worker(self) -> None:
        inventory = self._font_inventory_snapshot
        for path in list(self.files):
            text = _format_analysis(path, inventory)
            self.after(0, lambda t=text: self._append_log(t + "\n" + ("-" * 60)))

    def _font_configuration_for_file(self, src: Path) -> tuple[dict[str, str], list[str], str]:
        mode = self.font_mode_var.get()
        if mode == FONT_MODE_PRESERVE:
            return {}, [], "preserva-originali"

        analysis = analyze_ooxml(src).to_dict()
        required_fonts = list(analysis["required_fonts"])
        inventory = self._font_inventory_snapshot

        if mode == FONT_MODE_MISSING:
            mapping, unresolved = _build_missing_only_font_map(
                required_fonts,
                inventory,
                DEFAULT_LIBERATION_FONT_MAP,
            )
            return mapping, unresolved, "solo-mancanti"

        if mode == FONT_MODE_COMPAT:
            available_folded = {font.casefold() for font in inventory}
            unresolved = sorted(
                {
                    f"{old} → {new} (fallback non installato)"
                    for old, new in DEFAULT_LIBERATION_FONT_MAP.items()
                    if old in required_fonts and new.casefold() not in available_folded
                },
                key=str.casefold,
            )
            return dict(DEFAULT_LIBERATION_FONT_MAP), unresolved, "profilo-compatibile-forzato"

        custom = _parse_custom_font_map(self.custom_font_map_var.get())
        if self.custom_missing_only_var.get():
            mapping, unresolved = _filter_custom_map_to_missing(custom, required_fonts, inventory)
            return mapping, unresolved, "custom-solo-mancanti"

        available_folded = {font.casefold() for font in inventory}
        unresolved = sorted(
            {
                f"{old} → {new} (destinazione non installata)"
                for old, new in custom.items()
                if old in required_fonts and new.casefold() not in available_folded
            },
            key=str.casefold,
        )
        return custom, unresolved, "custom-forzato"

    def _normalize_worker(self) -> None:
        output_dir = Path(self.output_dir_var.get()).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        label = self.profile_var.get()
        base_profile = PROFILE_LABELS[label]

        failures: list[str] = []
        for src in list(self.files):
            dst = _suggest_output(src, output_dir, label)
            try:
                font_map, unresolved_fonts, font_mode = self._font_configuration_for_file(src)
                profile = replace(base_profile, font_policy=FontPolicy.MAP) if font_map else base_profile
                report = normalize_ooxml(
                    src,
                    dst,
                    options=NormalizationOptions(
                        profile=profile,
                        font_map=font_map,
                        available_fonts=self._font_inventory_snapshot,
                        sdk_validation="auto",
                    ),
                )
                report["gui_font_mode"] = font_mode
                report["gui_font_inventory_count"] = len(self._font_inventory_snapshot)
                if unresolved_fonts:
                    report.setdefault("warnings", []).append(
                        "Font senza fallback verificato: " + ", ".join(unresolved_fonts)
                    )

                if self.report_var.get():
                    report_path = dst.with_suffix(dst.suffix + ".report.json")
                    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                summary = (
                    f"OK: {src.name} -> {dst.name}\n"
                    f"  profilo={report['profile']}  font={font_mode}  "
                    f"parti modificate={report['changed_part_count']}  garanzia={report['guarantee_level']}"
                )
                if font_map:
                    summary += "\n  mapping font: " + ", ".join(f"{k}→{v}" for k, v in font_map.items())
                if unresolved_fonts:
                    summary += "\n  font non risolti: " + " | ".join(unresolved_fonts)
                if report["warnings"]:
                    summary += "\n  warning: " + " | ".join(report["warnings"])
                self.after(0, lambda t=summary: self._append_log(t))
            except Exception as exc:
                failures.append(f"{src.name}: {exc}")
                self.after(0, lambda s=src.name, e=str(exc): self._append_log(f"ERRORE {s}: {e}"))

        if failures:
            message = "Alcuni file non sono stati esportati:\n\n" + "\n".join(failures)
            self.after(0, lambda m=message: messagebox.showwarning("Completato con errori", m))
        else:
            self.after(0, lambda: messagebox.showinfo("Completato", "Normalizzazione completata."))


def main() -> int:
    app = NormalizerApp()
    app.mainloop()
    return 0
