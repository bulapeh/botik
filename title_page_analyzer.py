from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from utils import TitleAnalysisResult


class TitlePageAnalyzer:
    def analyze(self, title_image: bytes) -> TitleAnalysisResult:
        raise NotImplementedError


@dataclass
class StubTitleAnalyzer(TitlePageAnalyzer):
    def analyze(self, title_image: bytes) -> TitleAnalysisResult:
        return TitleAnalysisResult(
            signature_confidence=0.0,
            zacheno_confidence=0.0,
            flags=["not_checked"],
            debug={},
        )


@dataclass
class YoloTesseractTitleAnalyzer(TitlePageAnalyzer):
    yolo_weights_path: str
    tesseract_cmd: str

    def analyze(self, title_image: bytes) -> TitleAnalysisResult:
        try:
            import cv2
            import numpy as np
            import pytesseract
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("CV модули не установлены") from exc

        pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        image_array = np.frombuffer(title_image, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        model = YOLO(self.yolo_weights_path)
        results = model(image)

        signature_confidence = 0.0
        zacheno_confidence = 0.0
        flags: list[str] = []
        debug: dict[str, Any] = {}

        for result in results:
            for box in result.boxes:
                label = result.names.get(int(box.cls), "")
                conf = float(box.conf)
                if label == "signature":
                    signature_confidence = max(signature_confidence, conf)
                if label == "zacheno":
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    crop = image[y1:y2, x1:x2]
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    text = pytesseract.image_to_string(gray, lang="rus").lower()
                    if "зачт" in text:
                        zacheno_confidence = max(zacheno_confidence, conf)

        debug["signature_confidence"] = signature_confidence
        debug["zacheno_confidence"] = zacheno_confidence
        return TitleAnalysisResult(
            signature_confidence=signature_confidence,
            zacheno_confidence=zacheno_confidence,
            flags=flags,
            debug=debug,
        )
