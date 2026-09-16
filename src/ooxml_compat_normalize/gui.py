from __future__ import annotations

import json
import os
import threading
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .analysis import analyze_ooxml
from .normalizer import DEFAULT_LIBERATION_FONT_MAP, NormalizationOptions, normalize_ooxml
from .sdk_validator import find_openxml_sdk_validator, validate_with_openxml_sdk
from .profile import (
    INTEROP_TRANSITIONAL_V1,
    PORTABLE_EXPLICIT_V1,
    PRESERVE_V1,
    FontPolicy,
    LossPolicy,
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

SUPPORTED_EXTENSIONS = {".docx", ".xlsx", ".pptx"}


def _suggest_output(src: Path, output_dir: Path, label: str) -> Path:
    return output_dir / f"{src.stem}-{PROFILE_SUFFIXES[label]}{src.suffix.lower()}"


def _format_analysis(path: Path) -> str:
    analysis = analyze_ooxml(path).to_dict()
    sdk = validate_with_openxml_sdk(path, mode="auto")
    lines = [
        f"File: {path.name}",
        f"Tipo: {analysis['document_kind'].upper()}",
        f"Produttore: {analysis.get('producer') or 'non dichiarato'}",
        f"Conformance: {analysis['conformance']}",
        f"Font: {', '.join(analysis['required_fonts']) or 'nessuno rilevato'}",
        f"Theme: {'sì' if analysis['has_theme'] else 'no'}",
    ]
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
        self.geometry("820x600")
        self.minsize(720, 520)
        self.files: list[Path] = []

        try:
            if os.name == "nt":
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self.profile_var = tk.StringVar(value="Interop consigliato")
        self.font_map_var = tk.BooleanVar(value=False)
        self.report_var = tk.BooleanVar(value=True)
        self.output_dir_var = tk.StringVar(value=str(Path.home() / "Documents"))
        validator = find_openxml_sdk_validator()
        sdk_text = "Open XML SDK integrato" if validator else "Open XML SDK non disponibile"
        self.status_var = tk.StringVar(value=f"Seleziona uno o più file DOCX, XLSX o PPTX. {sdk_text}.")

        self._build_ui()

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

        ttk.Checkbutton(
            settings,
            text="Mappa font Microsoft comuni a Liberation/Carlito/Caladea",
            variable=self.font_map_var,
        ).grid(row=0, column=2, sticky="w", padx=8, pady=7)

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

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)
        self.normalize_button = ttk.Button(actions, text="Normalizza / Esporta", command=self.normalize_selected)
        self.normalize_button.pack(side="right")
        ttk.Label(actions, textvariable=self.status_var).pack(side="left")

        self.log = ScrolledText(self, height=16, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, **pad)

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
        self._run_worker(self._analyze_worker, "Analisi in corso…")

    def normalize_selected(self) -> None:
        if not self.files:
            messagebox.showinfo("OOXML Compat Normalizer", "Seleziona almeno un file.")
            return
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
        for path in list(self.files):
            text = _format_analysis(path)
            self.after(0, lambda t=text: self._append_log(t + "\n" + ("-" * 60)))

    def _normalize_worker(self) -> None:
        output_dir = Path(self.output_dir_var.get()).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        label = self.profile_var.get()
        profile = PROFILE_LABELS[label]
        font_map = DEFAULT_LIBERATION_FONT_MAP if self.font_map_var.get() else {}
        if font_map:
            profile = replace(profile, font_policy=FontPolicy.MAP)

        failures: list[str] = []
        for src in list(self.files):
            dst = _suggest_output(src, output_dir, label)
            try:
                report = normalize_ooxml(
                    src,
                    dst,
                    options=NormalizationOptions(profile=profile, font_map=font_map, sdk_validation="auto"),
                )
                if self.report_var.get():
                    report_path = dst.with_suffix(dst.suffix + ".report.json")
                    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                summary = (
                    f"OK: {src.name} -> {dst.name}\n"
                    f"  profilo={report['profile']}  parti modificate={report['changed_part_count']}  "
                    f"garanzia={report['guarantee_level']}"
                )
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
