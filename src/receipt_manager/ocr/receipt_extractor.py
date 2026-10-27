"""
Collection Receipt Extractor (local Tkinter GUI) - 100% free OCR options

Workflow: Upload image(s) -> text is extracted -> edit fields -> Save Record
(appends to receipts.csv) -> next image loads automatically. Repeat as needed.

Pick ONE backend (set the OCR_BACKEND variable below, or the env var of same name):

  "gemini" (default) - Google Gemini free tier. Best accuracy on handwriting,
      no credit card. Get a key at https://aistudio.google.com/apikey then:
          pip install -e .   (pillow and google-genai are in pyproject.toml)
          set GEMINI_API_KEY=your_key        (Mac/Linux: export GEMINI_API_KEY=...)
      Note: on the free tier Google may use your inputs to improve its models,
      so the receipt images (names, TINs) leave your computer.

  "ollama" - fully local/offline vision model. Free, private, needs a decent
      PC (8GB+ RAM; GPU helps). Install https://ollama.com then:
          ollama pull qwen2.5vl:7b
          pip install pillow ollama
"""

import csv
import io
import json
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image

OCR_BACKEND = os.environ.get("OCR_BACKEND", "gemini")  # "gemini" or "ollama"
# Comma-separated list of models, tried in order if one is overloaded/unavailable.
GEMINI_MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_MODEL", "gemini-3.8-flash,gemini-2.5-flash,gemini-2.5-flash-lite").split(",")]
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5vl:7b")
CSV_PATH = "receipts.csv"

# (key, label shown in GUI)
FIELDS = [
    ("receipt_no", "No."),
    ("in_payment_of", "In Payment of the Following (particulars + amount)"),
    ("received_from", "Received From"),
    ("address", "Address"),
    ("tin", "With TIN"),
    ("sum_of", "The Sum Of (in words)"),
    ("pesos", "Pesos (P)"),
    ("payment_for", "In Full/Partial Payment For"),
]
CSV_COLUMNS = ["source_file"] + [k for k, _ in FIELDS]


# --------------------------------------------------------------------------
# OCR backends
# --------------------------------------------------------------------------
PROMPT = (
    "This is a photo of a Philippine collection receipt with handwritten entries. "
    "Extract the handwritten/filled-in values and reply with ONLY a JSON object "
    "(no markdown, no commentary) with these keys:\n"
    + "\n".join(f'- "{k}": value for "{label}"' for k, label in FIELDS)
    + '\nFor "receipt_no" use the printed number at the top right (e.g. 0004). '
    'For "in_payment_of" combine the particulars and amount from the left table. '
    'Use an empty string for any blank field. Do not guess.'
)


def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    data = json.loads(text)
    return {k: str(data.get(k, "") or "") for k, _ in FIELDS}


def load_resized(path, size=1800):
    img = Image.open(path).convert("RGB")
    img.thumbnail((size, size))
    return img


def ocr_gemini(path, retries=4):
    import time

    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    client = genai.Client(api_key=api_key)
    img = load_resized(path)
    last_err = None
    for model in GEMINI_MODELS:
        for attempt in range(retries):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[img, PROMPT],
                    config={"response_mime_type": "application/json"},
                )
                return parse_json(resp.text), model
            except Exception as e:  # noqa: BLE001 - the SDK raises many error types
                last_err = e
                msg = str(e)
                temporary = any(s in msg for s in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "504"))
                if not temporary:
                    break  # e.g. bad key / model not found: move to next model
                time.sleep(2 ** (attempt + 1))  # 2s, 4s, 8s, 16s
    raise last_err


def ocr_ollama(path):
    import ollama

    buf = io.BytesIO()
    load_resized(path).save(buf, "JPEG", quality=90)
    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": PROMPT, "images": [buf.getvalue()]}],
        format="json",
    )
    return parse_json(resp["message"]["content"])


def extract(path):
    if OCR_BACKEND == "ollama":
        return ocr_ollama(path), f"Ollama ({OLLAMA_MODEL})"
    result, model = ocr_gemini(path)
    return result, f"Gemini ({model})"


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("Receipt Extractor")
        self.queue = []
        self.current = None
        self.vars = {k: tk.StringVar() for k, _ in FIELDS}

        top = tk.Frame(root)
        top.pack(fill="x", padx=8, pady=6)
        tk.Button(top, text="Upload Image(s)", command=self.upload).pack(side="left")
        tk.Button(top, text="Save Record", command=self.save).pack(side="left", padx=6)
        tk.Button(top, text="Skip", command=self.next_image).pack(side="left")
        tk.Button(top, text="Export CSV As...", command=self.export_as).pack(side="left", padx=6)
        self.status = tk.Label(top, text="No image loaded", anchor="w")
        self.status.pack(side="left", padx=10)

        body = tk.Frame(root)
        body.pack(fill="both", expand=True, padx=8)

        self.preview = tk.Label(body, text="(image preview)", width=60, height=20, bg="#ddd")
        self.preview.pack(side="left", padx=(0, 8))

        form = tk.Frame(body)
        form.pack(side="left", fill="both", expand=True)
        for i, (k, label) in enumerate(FIELDS):
            tk.Label(form, text=label, anchor="w").grid(row=i, column=0, sticky="w", pady=2)
            tk.Entry(form, textvariable=self.vars[k], width=50).grid(row=i, column=1, pady=2)

        self.table = ttk.Treeview(root, columns=CSV_COLUMNS, show="headings", height=6)
        for c in CSV_COLUMNS:
            self.table.heading(c, text=c)
            self.table.column(c, width=110)
        self.table.pack(fill="x", padx=8, pady=8)
        self.load_existing()

    # ---- helpers ----
    def set_status(self, text):
        self.status.config(text=text)

    def load_existing(self):
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    self.table.insert("", "end", values=[row.get(c, "") for c in CSV_COLUMNS])

    # ---- actions ----
    def upload(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp")])
        if not paths:
            return
        self.queue.extend(paths)
        if self.current is None:
            self.next_image()
        else:
            self.set_status(f"{os.path.basename(self.current)} | {len(self.queue)} more queued")

    def next_image(self):
        for v in self.vars.values():
            v.set("")
        if not self.queue:
            self.current = None
            self.preview.config(image="", text="(image preview)")
            self.set_status("Queue empty - upload more images")
            return
        self.current = self.queue.pop(0)
        self.show_preview(self.current)
        self.set_status(f"Extracting {os.path.basename(self.current)} ...")
        threading.Thread(target=self.run_ocr, args=(self.current,), daemon=True).start()

    def run_ocr(self, path):
        try:
            result, backend = extract(path)
            self.root.after(0, lambda: self.fill(path, result, backend))
        except Exception as e:  # noqa: BLE001 - show any failure, user fills in manually
            msg = f"OCR failed: {e} (fill in manually)"
            self.root.after(0, lambda: self.set_status(msg))

    def fill(self, path, result, backend):
        if path != self.current:
            return
        for k, _ in FIELDS:
            self.vars[k].set(result.get(k, ""))
        self.set_status(f"{os.path.basename(path)} via {backend} | "
                        f"{len(self.queue)} more queued - review, then Save")

    def show_preview(self, path):
        from PIL import ImageTk
        img = Image.open(path)
        img.thumbnail((480, 360))
        self._photo = ImageTk.PhotoImage(img)  # keep a reference
        self.preview.config(image=self._photo, text="", width=img.width, height=img.height)

    def save(self):
        if self.current is None:
            messagebox.showinfo("Nothing to save", "Upload an image first.")
            return
        row = {"source_file": os.path.basename(self.current)}
        row.update({k: self.vars[k].get().strip() for k, _ in FIELDS})
        new_file = not os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            if new_file:
                w.writeheader()
            w.writerow(row)
        self.table.insert("", "end", values=[row[c] for c in CSV_COLUMNS])
        self.next_image()

    def export_as(self):
        if not os.path.exists(CSV_PATH):
            messagebox.showinfo("Nothing to export", "No records saved yet.")
            return
        dest = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if dest:
            with open(CSV_PATH, "rb") as src, open(dest, "wb") as out:
                out.write(src.read())
            messagebox.showinfo("Exported", f"Saved to {dest}")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
