# ============================================================================
# OCR Skill — Standard Operating Procedure (SOP) + Multi-Engine Pluggable Arch
# ============================================================================
# Architecture:
#   Image → Preprocess → Engine (Step-1V / Tesseract / PaddleOCR) → Postprocess → Result
#
# Fallback Chain: Step-1V → Tesseract → Error
#
# Usage:
#   from ocr_skills import OCRAnalyzer, get_analyzer
#   result = get_analyzer().analyze("image.jpg")
#   print(result.text)       # raw text
#   print(result.tables)     # structured tables
#
# CLI:
#   python ocr_skills.py screenshot.jpg --engine step1v
#   python ocr_skills.py screenshot.jpg --compare
# ============================================================================

import sys, os, json, base64, hashlib, time, io, logging
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

# ── Logging ──────────────────────────────────────────────────────────────────
log = logging.getLogger("ocr_skills")
log.setLevel(logging.INFO)
if not log.handlers:
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    log.addHandler(h)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 1 — Configuration                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@dataclass
class OCRConfig:
    """One-stop OCR configuration. Override any field when creating OCRAnalyzer."""

    # ── Step-1V (阶跃星辰) ──
    step1v_api_key: str = "30BFcJBkyvp0zVAAflWmX0IFxcw53sN3jWYqfrWVNxUzgLNZJvwV1a0lTxJu9RRRS"
    step1v_base_url: str = "https://api.stepfun.com/v1"
    step1v_model: str = "step-1v-8k"
    step1v_timeout: int = 90
    step1v_max_tokens: int = 2000     # hard limit to prevent hallucination loops
    step1v_temperature: float = 0.0   # deterministic output

    # ── Tesseract ──
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    tesseract_lang: str = "chi_sim+eng"
    tessdata_dir: str = ""

    # ── Image Preprocessing ──
    max_image_width: int = 1024       # resize if wider
    jpeg_quality: int = 75            # 70-85 recommended, lower = faster/cheaper
    enhance_contrast: float = 1.5     # >1 increases contrast for Tesseract
    convert_grayscale: bool = True

    # ── Pipeline ──
    primary_engine: str = "step1v"    # "step1v" | "tesseract" | "paddleocr"
    fallback_chain: Tuple[str, ...] = ("step1v", "tesseract")
    enable_cache: bool = True
    cache_dir: str = ""
    retry_count: int = 2

    def __post_init__(self):
        if not self.tessdata_dir:
            self.tessdata_dir = os.path.join(os.environ.get("USERPROFILE", ""), ".tesseract")
        if not self.cache_dir:
            self.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ocr_cache")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 2 — Result Data Classes                                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@dataclass
class TableData:
    """A single table extracted from the image."""
    caption: str = ""                       # e.g. "合同明细表"
    headers: List[str] = field(default_factory=list)
    rows: List[Dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0                 # engine-reported or estimated


@dataclass
class OCRResult:
    """Full OCR result from a single engine."""
    engine: str = ""                        # "step1v" | "tesseract" | "paddleocr"
    success: bool = False
    text: str = ""                          # raw full text
    tables: List[TableData] = field(default_factory=list)
    confidence: float = 0.0                 # 0.0–1.0 overall confidence
    elapsed_ms: float = 0.0
    tokens_used: int = 0
    cost_rmb: float = 0.0
    image_hash: str = ""
    error: str = ""                         # error message if failed
    raw_response: str = ""                  # for debugging

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "success": self.success,
            "text": self.text,
            "tables": [asdict(t) for t in self.tables],
            "confidence": round(self.confidence, 4),
            "elapsed_ms": round(self.elapsed_ms, 1),
            "tokens_used": self.tokens_used,
            "cost_rmb": round(self.cost_rmb, 6),
            "image_hash": self.image_hash,
            "error": self.error,
        }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 3 — Image Preprocessing                                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class ImagePreprocessor:
    """
    SOP Step 1: Preprocess image for optimal OCR.

    - Resize to max_width (maintains aspect ratio)
    - Convert to grayscale (removes color noise)
    - Enhance contrast (sharpens text edges)
    - Compress to JPEG (reduces API payload size & cost)
    """

    def __init__(self, config: OCRConfig):
        self.config = config

    def process(self, image_path: str) -> Tuple[str, bytes]:
        """
        Returns (base64_string, raw_bytes) ready for API / tesseract.
        """
        try:
            from PIL import Image, ImageEnhance
        except ImportError:
            log.warning("Pillow not installed, returning raw image bytes")
            with open(image_path, "rb") as f:
                raw = f.read()
            return base64.b64encode(raw).decode(), raw

        img = Image.open(image_path)
        log.debug(f"Original: {img.size}, mode={img.mode}")

        # Resize
        w, h = img.size
        if w > self.config.max_image_width:
            ratio = self.config.max_image_width / w
            img = img.resize((self.config.max_image_width, int(h * ratio)), Image.LANCZOS)
            log.debug(f"Resized to {img.size}")

        # Grayscale
        if self.config.convert_grayscale and img.mode != "L":
            img = img.convert("L")

        # Contrast enhancement
        if self.config.enhance_contrast != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(self.config.enhance_contrast)

        # Compress to JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self.config.jpeg_quality)
        raw = buf.getvalue()

        b64 = base64.b64encode(raw).decode()
        log.debug(f"Encoded: {len(raw):,} bytes → {len(b64):,} base64 chars")
        return b64, raw

    def process_for_tesseract(self, image_path: str):
        """Tesseract-specific: returns PIL Image with stronger enhancement."""
        try:
            from PIL import Image, ImageEnhance
        except ImportError:
            return None

        img = Image.open(image_path)
        img = img.convert("L")  # grayscale
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(self.config.enhance_contrast)
        return img


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 4 — Cache Layer                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class ResultCache:
    """
    File-based cache keyed by SHA256 of image bytes.
    Avoids re-processing identical images — critical for iterative development.
    """

    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:16]

    @staticmethod
    def hash_file(path: str) -> str:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def get(self, image_hash: str) -> Optional[dict]:
        cache_file = self.cache_dir / f"{image_hash}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                log.info(f"Cache HIT: {image_hash}")
                return data
            except Exception as e:
                log.warning(f"Cache read error: {e}")
        return None

    def put(self, image_hash: str, result: dict):
        cache_file = self.cache_dir / f"{image_hash}.json"
        try:
            result["cached_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            log.debug(f"Cache stored: {image_hash}")
        except Exception as e:
            log.warning(f"Cache write error: {e}")

    def clear(self) -> int:
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 5 — OCR Engine: Step-1V (阶跃星辰 Vision Model)                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

STEP1V_SYSTEM_PROMPT = """你是一个专业OCR引擎。请精确识别图片中的所有文字，输出JSON。

【核心规则】
1. 逐字识别，不添加原文没有的内容
2. 数字金额精确保留，包括小数点、逗号分隔符
3. 表格数据按行列对应输出
4. 中文生僻字也要准确识别

【输出格式】严格按以下JSON格式，不要输出任何额外文字：
{"title":"报表标题","headers":["列1","列2","列3"],"rows":[{"列1":"值","列2":"值"},...],"extra_text":"表格之外的文字"}

【防幻觉规则 — 重要！】
- 只输出实际识别到的文字，绝不编造数据
- 输出完整JSON后立即停止，不要重复、不要循环
- 如果看不清某个单元格，填写""空字符串
- rows数量等于实际表格行数，不要多也不要少"""


class Step1VEngine:
    """SOP Step-2a: Call Step-1V vision model for OCR."""

    def __init__(self, config: OCRConfig):
        self.config = config

    def analyze(self, image_b64: str) -> OCRResult:
        start = time.time()
        result = OCRResult(engine="step1v")

        try:
            import requests
        except ImportError:
            result.error = "requests not installed. Run: pip install requests"
            return result

        url = f"{self.config.step1v_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.step1v_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.step1v_model,
            "messages": [
                {
                    "role": "system",
                    "content": STEP1V_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        {"type": "text", "text": "请识别这张图片。"},
                    ],
                },
            ],
            "max_tokens": self.config.step1v_max_tokens,
            "temperature": self.config.step1v_temperature,
        }

        for attempt in range(self.config.retry_count + 1):
            try:
                if attempt > 0:
                    log.info(f"Step-1V retry {attempt}/{self.config.retry_count}")
                    time.sleep(2 ** attempt)

                resp = requests.post(url, headers=headers, json=payload,
                                     timeout=self.config.step1v_timeout)

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})

                    result.tokens_used = usage.get("total_tokens", 0)
                    result.cost_rmb = (
                        usage.get("prompt_tokens", 0) * 0.001 +
                        usage.get("completion_tokens", 0) * 0.001
                    ) / 1000
                    result.raw_response = content
                    result.elapsed_ms = (time.time() - start) * 1000

                    # Parse structured JSON from response
                    self._parse_response(result, content)
                    break

                else:
                    log.warning(f"Step-1V attempt {attempt+1}: HTTP {resp.status_code} — {resp.text[:200]}")

            except Exception as e:
                log.warning(f"Step-1V attempt {attempt+1}: {e}")
                if attempt == self.config.retry_count:
                    result.error = f"Step-1V failed after {self.config.retry_count+1} attempts: {e}"

        if not result.success and not result.error:
            result.error = "Step-1V: no successful attempts"
        return result

    def _parse_response(self, result: OCRResult, content: str):
        """Extract structured table data from model response. Anti-hallucination measures included."""
        # Strip markdown code fences
        text = content.strip()
        if text.startswith("```"):
            # Remove ```json ... ``` or ``` ... ```
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # Try to parse as JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON block
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    # Fallback: treat whole response as raw text
                    result.success = True
                    result.text = content.strip()
                    result.confidence = 0.5
                    return
            else:
                result.success = True
                result.text = content.strip()
                result.confidence = 0.5
                return

        # Populate result
        result.success = True
        result.text = data.get("extra_text", "") or ""

        # Extract title
        title = data.get("title", "")

        # Extract headers and rows
        headers = data.get("headers", [])
        rows_raw = data.get("rows", [])

        # ── Anti-hallucination: deduplicate rows ──
        seen = set()
        deduped_rows = []
        for row in rows_raw:
            if not isinstance(row, dict):
                continue
            # Skip empty/incomplete rows
            values = [v for v in row.values() if v and str(v).strip()]
            if not values:
                continue
            # Dedup key
            row_key = json.dumps(row, ensure_ascii=False, sort_keys=True)
            if row_key in seen:
                log.debug(f"Dedup: skipped duplicate row")
                continue
            seen.add(row_key)
            deduped_rows.append(row)

        # ── Confidence estimation ──
        total_cells = len(headers) * max(len(deduped_rows), 1)
        empty_cells = sum(
            1 for row in deduped_rows
            for v in row.values()
            if not v or str(v).strip() == ""
        )
        if total_cells > 0:
            result.confidence = max(0.3, 1.0 - (empty_cells / total_cells))
        else:
            result.confidence = 0.6

        # Build table
        table = TableData(
            caption=title,
            headers=headers,
            rows=deduped_rows,
            confidence=result.confidence,
        )
        result.tables = [table]

        # Build full text from table
        lines = [title] if title else []
        if headers:
            lines.append(" | ".join(headers))
        for row in deduped_rows:
            line = " | ".join(str(row.get(h, "")) for h in headers) if headers else str(row)
            lines.append(line)
        result.text = "\n".join(lines)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 6 — OCR Engine: Tesseract                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class TesseractEngine:
    """SOP Step-2b: Local Tesseract OCR — free, fast, fallback engine."""

    def __init__(self, config: OCRConfig):
        self.config = config

    def analyze(self, image_path: str) -> OCRResult:
        start = time.time()
        result = OCRResult(engine="tesseract")

        try:
            import pytesseract
        except ImportError:
            result.error = "pytesseract not installed. Run: pip install pytesseract"
            return result

        if not os.path.exists(self.config.tesseract_cmd):
            result.error = f"Tesseract not found at: {self.config.tesseract_cmd}"
            return result

        # Setup tessdata
        if os.path.isdir(self.config.tessdata_dir):
            os.environ["TESSDATA_PREFIX"] = self.config.tessdata_dir

        pytesseract.pytesseract.tesseract_cmd = self.config.tesseract_cmd

        # Preprocess for Tesseract
        preprocessor = ImagePreprocessor(self.config)
        img = preprocessor.process_for_tesseract(image_path)

        if img is None:
            # Fallback: open raw
            from PIL import Image
            img = Image.open(image_path).convert("L")

        # Run OCR
        try:
            text = pytesseract.image_to_string(img, lang=self.config.tesseract_lang).strip()
        except Exception:
            log.warning("chi_sim+eng failed, trying eng only")
            try:
                text = pytesseract.image_to_string(img, lang="eng").strip()
            except Exception as e:
                result.error = f"Tesseract execution failed: {e}"
                return result

        result.success = True
        result.text = text
        result.elapsed_ms = (time.time() - start) * 1000
        result.confidence = min(0.8, len(text) / 2000) if text else 0.0

        # Try to parse as table (basic heuristic: pipe-delimited or tabular text)
        lines = text.split("\n")
        if lines:
            table = TableData(
                caption="",
                headers=["raw_text"],
                rows=[{"raw_text": line} for line in lines if line.strip()],
                confidence=result.confidence,
            )
            result.tables = [table]

        return result


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 7 — Pipeline Orchestrator (SOP Core)                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class OCRAnalyzer:
    """
    SOP Coordinator: Orchestrates the full OCR pipeline.

    Workflow:
      1. Hash image → check cache
      2. Preprocess image
      3. Try primary engine
      4. On failure, iterate fallback chain
      5. Post-process & cache result
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig()
        self.preprocessor = ImagePreprocessor(self.config)
        self.cache = ResultCache(self.config.cache_dir)
        self._engines: Dict[str, Any] = {}

    def _get_engine(self, name: str):
        if name not in self._engines:
            if name == "step1v":
                self._engines[name] = Step1VEngine(self.config)
            elif name == "tesseract":
                self._engines[name] = TesseractEngine(self.config)
            else:
                return None
        return self._engines[name]

    def analyze(self, image_path: str, preferred: Optional[str] = None,
                force: bool = False) -> OCRResult:
        """
        Main entry point. Analyze an image and return structured OCR result.

        Args:
            image_path: Path to the image file
            preferred: Force a specific engine ("step1v", "tesseract", "paddleocr").
                       None = use config.primary_engine.
            force: Skip cache, always re-process.

        Returns:
            OCRResult with text, tables, confidence, cost, timing.
        """
        if not os.path.exists(image_path):
            return OCRResult(engine="none", success=False, error=f"File not found: {image_path}")

        # ── Step 1: Hash & Check Cache ──
        img_hash = ResultCache.hash_file(image_path)

        # cache check moved to per-engine loop

        # ── Step 2: Determine engine order ──
        if preferred:
            engine_order = [preferred]
        else:
            engine_order = [self.config.primary_engine] + [
                e for e in self.config.fallback_chain
                if e != self.config.primary_engine
            ]

        # ── Step 3: Try engines (with per-engine cache key) ──
        final_result = None
        image_b64_cache = None  # lazy preprocess

        for engine_name in engine_order:
            engine = self._get_engine(engine_name)
            if engine is None:
                log.warning(f"Unknown engine: {engine_name}, skipping")
                continue

            # Per-engine cache key: {hash}_{engine}
            cache_key = f"{img_hash}_{engine_name}"

            if self.config.enable_cache and not force:
                cached = self.cache.get(cache_key)
                if cached:
                    log.info(f"Cache HIT: {cache_key}")
                    final_result = self._result_from_cache(cached)
                    break

            log.info(f"Trying engine: {engine_name}")

            if engine_name == "tesseract":
                result = engine.analyze(image_path)
            else:
                # Lazy preprocess for API engines
                if image_b64_cache is None:
                    try:
                        image_b64_cache, _ = self.preprocessor.process(image_path)
                    except Exception as e:
                        log.error(f"Preprocessing failed: {e}")
                        with open(image_path, "rb") as f:
                            image_b64_cache = base64.b64encode(f.read()).decode()
                result = engine.analyze(image_b64_cache)

            result.image_hash = img_hash

            if result.success:
                final_result = result
                # Cache engine-specific result
                if self.config.enable_cache:
                    self.cache.put(cache_key, final_result.to_dict())
                break
            else:
                log.warning(f"Engine {engine_name} failed: {result.error[:100] if result.error else 'None'}")
                final_result = result  # keep last error

        if final_result is None:
            final_result = OCRResult(engine="none", success=False, error="No engine available", image_hash=img_hash)


        return final_result

    def _result_from_cache(self, cached: dict) -> OCRResult:
        """Reconstruct OCRResult from cached dict."""
        result = OCRResult(
            engine=cached.get("engine", "cache"),
            success=cached.get("success", True),
            text=cached.get("text", ""),
            confidence=cached.get("confidence", 1.0),
            elapsed_ms=0,  # cached
            tokens_used=cached.get("tokens_used", 0),
            cost_rmb=cached.get("cost_rmb", 0),
            image_hash=cached.get("image_hash", ""),
        )
        for t in cached.get("tables", []):
            result.tables.append(TableData(**t))
        return result

    def analyze_all(self, image_path: str, force: bool = False) -> Dict[str, OCRResult]:
        """Run ALL available engines for comparison."""
        results = {}
        for engine_name in ["step1v", "tesseract"]:
            results[engine_name] = self.analyze(image_path, preferred=engine_name, force=force)
        return results

    def clear_cache(self) -> int:
        return self.cache.clear()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 8 — Module-Level Shortcuts                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

_global_analyzer: Optional[OCRAnalyzer] = None


def get_analyzer(config: Optional[OCRConfig] = None) -> OCRAnalyzer:
    """Get or create a global OCRAnalyzer instance (singleton)."""
    global _global_analyzer
    if config is not None:
        _global_analyzer = OCRAnalyzer(config)
    elif _global_analyzer is None:
        _global_analyzer = OCRAnalyzer()
    return _global_analyzer


def ocr_analyze(image_path: str, preferred: Optional[str] = None, force: bool = False) -> OCRResult:
    """One-liner: analyze an image with default config."""
    return get_analyzer().analyze(image_path, preferred=preferred, force=force)


def ocr_json(image_path: str, preferred: Optional[str] = None, force: bool = False) -> dict:
    """One-liner: return dict directly."""
    return ocr_analyze(image_path, preferred=preferred, force=force).to_dict()


def ocr_compare(image_path: str) -> Dict[str, OCRResult]:
    """One-liner: compare all engines."""
    return get_analyzer().analyze_all(image_path)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 9 — CLI                                                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="OCR Skill — Multi-engine image text extraction")
    p.add_argument("image", nargs="?", help="Path to image file")
    p.add_argument("-e", "--engine", default="auto",
                   choices=["auto", "step1v", "tesseract", "paddleocr"],
                   help="Engine (default: auto = step1v → tesseract)")
    p.add_argument("-c", "--compare", action="store_true", help="Compare all engines")
    p.add_argument("-j", "--json", action="store_true", help="Output as JSON")
    p.add_argument("--no-cache", action="store_true", help="Force re-analysis")
    p.add_argument("--clear-cache", action="store_true", help="Clear all cached results")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    if args.clear_cache:
        count = get_analyzer().clear_cache()
        print(f"Cleared {count} cached results")
        sys.exit(0)

    if not args.image:
        p.print_help()
        sys.exit(1)

    preferred = None if args.engine == "auto" else args.engine

    if args.compare:
        results = ocr_compare(args.image)
        for name, r in results.items():
            status = "✅" if r.success else "❌"
            print(f"{status} {name:12s} | {r.elapsed_ms:6.0f}ms | "
                  f"{len(r.text):5d} chars | {r.error[:80] if r.error else ''}")
    elif args.json:
        print(json.dumps(ocr_json(args.image, preferred=preferred, force=args.no_cache),
                         ensure_ascii=False, indent=2))
    else:
        result = ocr_analyze(args.image, preferred=preferred, force=args.no_cache)
        if result.success:
            print(f"Engine: {result.engine}  Time: {result.elapsed_ms/1000:.1f}s  "
                  f"Tokens: {result.tokens_used}  Cost: ¥{result.cost_rmb:.4f}  "
                  f"Confidence: {result.confidence:.0%}")
            print(f"\n{'='*60}")
            if result.tables:
                for t in result.tables:
                    print(f"[{t.caption}]  headers={t.headers}  rows={len(t.rows)}")
                    for i, row in enumerate(t.rows[:5]):
                        print(f"  [{i+1}] {row}")
                    if len(t.rows) > 5:
                        print(f"  ... ({len(t.rows) - 5} more rows)")
            else:
                print(result.text[:2000])
            print(f"{'='*60}")
        else:
            print(f"❌ Failed: {result.error}")
