"""
Face Lock — reusable core logic.

Extracted from face_lock_app.py so it can be imported by both the Streamlit
app and the image-to-video pipeline bridge without pulling in Streamlit.

Heavy vision dependencies (cv2, mediapipe) are imported lazily inside
FaceAnalyzer, so the pure-logic classes (FacialMeasurements, PromptGenerator,
DriftDetector, AnalogFilmProcessor) import fine in environments without them.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Dict, Optional

import numpy as np
from PIL import Image, ImageEnhance


@dataclass
class FacialMeasurements:
    gonial_angle: float
    canthal_tilt: float
    facial_index: float
    nasal_rotation: float
    zygomatic_prominence: float
    eye_shape_ratio: float
    fitzpatrick_scale: int

    def to_dict(self):
        return asdict(self)


class AnalogFilmProcessor:
    """Emulates film stocks described in the commit."""

    @staticmethod
    def apply_preset(image: Image.Image, preset: str) -> Image.Image:
        img = image.copy()

        if preset == "Kodachrome 25":
            # High contrast, rich saturation, slight warm shift
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.4)
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.4)
            # Slight red tint for warmth
            r, g, b = img.split()
            r = r.point(lambda i: i * 1.05)
            img = Image.merge("RGB", (r, g, b))

        elif preset == "Agfa CNS2":
            # Muted colors, slight green/cyan cast, grainy look
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(0.8)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)
            # Add subtle green tint
            r, g, b = img.split()
            g = g.point(lambda i: i * 1.02)
            img = Image.merge("RGB", (r, g, b))

        elif preset == "Kodak Vision3 500T":
            # Cinematic, tungsten balanced (cooler), Halation simulation (soft glow)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)
            # Cool shift
            r, g, b = img.split()
            b = b.point(lambda i: i * 1.05)
            img = Image.merge("RGB", (r, g, b))

        return img


class FaceAnalyzer:
    """Extracts 468-landmark mesh and calculates biometric metrics."""

    def __init__(self):
        import mediapipe as mp  # lazy — only needed when analysis runs

        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        )

    def _calculate_angle(self, p1, p2, p3):
        """Calculates angle P1-P2-P3."""
        v1 = np.array([p1.x - p2.x, p1.y - p2.y])
        v2 = np.array([p3.x - p2.x, p3.y - p2.y])

        cosine_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
        return np.degrees(angle)

    def _calculate_slope(self, p1, p2):
        return np.degrees(math.atan2(p2.y - p1.y, p2.x - p1.x))

    def _estimate_skin_tone(self, image_np, landmarks) -> int:
        # Sample cheek area
        h, w, _ = image_np.shape
        cheek_landmark = landmarks[234]  # Left cheek area
        cx, cy = int(cheek_landmark.x * w), int(cheek_landmark.y * h)

        # Extract 10x10 patch
        patch = image_np[
            max(0, cy - 5) : min(h, cy + 5), max(0, cx - 5) : min(w, cx + 5)
        ]
        if patch.size == 0:
            return 3

        avg_color = np.mean(patch, axis=(0, 1))
        # Very rough luminosity to Fitzpatrick mapping
        lum = 0.299 * avg_color[0] + 0.587 * avg_color[1] + 0.114 * avg_color[2]

        if lum > 220:
            return 1
        elif lum > 190:
            return 2
        elif lum > 160:
            return 3
        elif lum > 130:
            return 4
        elif lum > 80:
            return 5
        else:
            return 6

    def analyze(self, image_np) -> Optional[FacialMeasurements]:
        import cv2  # lazy — only needed when analysis runs

        results = self.face_mesh.process(cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB))

        if not results.multi_face_landmarks:
            return None

        lm = results.multi_face_landmarks[0].landmark
        h, w, _ = image_np.shape

        # --- BIOMETRIC CALCULATIONS ---

        # 1. Gonial Angle (Jaw)
        # Approx landmarks: 172 (Left Jaw Top), 132 (Left Gonion/Jaw Corner), 152 (Chin/Menton)
        gonial = self._calculate_angle(lm[172], lm[132], lm[152])

        # 2. Canthal Tilt
        # Left eye: 362 (inner), 263 (outer)
        inner_eye = lm[133]
        outer_eye = lm[33]
        tilt = -1 * self._calculate_slope(inner_eye, outer_eye)

        # 3. Facial Index (Height / Width)
        height = math.hypot(lm[168].x - lm[152].x, lm[168].y - lm[152].y)
        width = math.hypot(lm[234].x - lm[454].x, lm[234].y - lm[454].y)
        f_index = (height / width) * 100 if width > 0 else 0

        # 4. Nasal Rotation (Tip inclination)
        n_rot = (lm[2].y - lm[1].y) * 1000

        # 5. Zygomatic Prominence
        jaw_width = math.hypot(lm[132].x - lm[361].x, lm[132].y - lm[361].y)
        zyg_prom = (width / jaw_width) if jaw_width > 0 else 1.0

        # 6. Eye Shape Ratio (Height / Width)
        eye_h = math.hypot(lm[159].x - lm[145].x, lm[159].y - lm[145].y)
        eye_w = math.hypot(lm[133].x - lm[33].x, lm[133].y - lm[33].y)
        e_shape = eye_h / eye_w if eye_w > 0 else 0

        # 7. Fitzpatrick
        fitz = self._estimate_skin_tone(image_np, lm)

        return FacialMeasurements(
            gonial_angle=round(gonial, 2),
            canthal_tilt=round(tilt, 2),
            facial_index=round(f_index, 2),
            nasal_rotation=round(n_rot, 2),
            zygomatic_prominence=round(zyg_prom, 2),
            eye_shape_ratio=round(e_shape, 2),
            fitzpatrick_scale=fitz,
        )


class PromptGenerator:
    """Translates measurements into platform-specific prompts."""

    def _generate_anti_drift_negatives(self, metrics: FacialMeasurements) -> str:
        """Generates specific negative constraints based on biometric readings."""
        negatives = []

        # Gonial Angle (Jaw)
        if metrics.gonial_angle < 125:  # Sharp/Square
            negatives.extend(
                ["receding chin", "weak jaw", "round face", "soft jawline", "fat neck"]
            )
        elif metrics.gonial_angle > 145:  # Soft/Round
            negatives.extend(
                ["square jaw", "chiseled jaw", "masculine jaw", "sharp angles"]
            )

        # Canthal Tilt
        if metrics.canthal_tilt > 2:  # Positive/Hunter
            negatives.extend(
                ["downturned eyes", "sad eyes", "droopy eyelids", "prey eyes"]
            )
        elif metrics.canthal_tilt < -2:  # Negative/Doe
            negatives.extend(["upturned eyes", "cat eyes", "aggressive expression"])

        # Facial Index
        if metrics.facial_index > 90:  # Oblong
            negatives.extend(
                ["wide face", "square face", "short face", "compressed face"]
            )
        elif metrics.facial_index < 80:  # Square/Round
            negatives.extend(["long face", "oblong face", "horse face"])

        return ", ".join(negatives)

    def generate(
        self, metrics: FacialMeasurements, platform: str, subject_name: str
    ) -> Dict[str, str]:
        # -- POSITIVE DESCRIPTORS --
        jaw_desc = (
            f"jaw angle {int(metrics.gonial_angle)} degrees, sharp definition"
            if metrics.gonial_angle < 125
            else "soft rounded jawline"
        )
        eye_desc = (
            "positive canthal tilt, hunter eyes"
            if metrics.canthal_tilt > 2
            else "neutral almond eyes"
        )
        if metrics.canthal_tilt < -2:
            eye_desc = "negative canthal tilt, doe eyes"

        face_shape = (
            "oblong face structure"
            if metrics.facial_index > 90
            else "broad face structure"
        )
        cheekbones = (
            "high zygomatic arches"
            if metrics.zygomatic_prominence > 1.4
            else "soft cheeks"
        )
        skin_tone = f"Fitzpatrick skin type {metrics.fitzpatrick_scale}"

        # Construct Core Prompt
        core_prompt = (
            f"photo of {subject_name}, {skin_tone}, {face_shape}, {jaw_desc}, {cheekbones}, {eye_desc}, "
            f"maintaining biometric consistency: nasal rotation {metrics.nasal_rotation}, "
            f"highly detailed skin texture, 8k, photorealistic"
        )

        # -- NEGATIVE DRIFT PROTECTION --
        anti_drift = self._generate_anti_drift_negatives(metrics)

        if platform.lower() == "midjourney":
            return {
                "positive": f"/imagine prompt: {core_prompt} --v 6.0 --style raw",
                "negative": f"--no {anti_drift}, cartoon, illustration, plastic, deformities",
            }
        elif platform.lower() == "flux":
            return {
                "positive": f"{core_prompt}, cinematic lighting, shot on 35mm, depth of field",
                "negative": f"{anti_drift}, blur, distortion, anime, illustration, bad anatomy",
            }
        else:  # Reve / Generic
            return {
                "positive": core_prompt,
                "negative": f"{anti_drift}, low quality, jpeg artifacts, bad anatomy",
            }


class DriftDetector:
    """Detects if a generated image has drifted from the biometric lock."""

    def check_drift(
        self,
        target: FacialMeasurements,
        generated: FacialMeasurements,
        tolerance: float = 0.15,
    ) -> Dict:
        report = []
        drift_detected = False

        # Compare key metrics
        metrics = {
            "Gonial Angle (Jaw)": (
                target.gonial_angle,
                generated.gonial_angle,
                10.0,
            ),  # Higher absolute tolerance for angles
            "Canthal Tilt": (
                target.canthal_tilt,
                generated.canthal_tilt,
                2.0,
            ),  # Tight tolerance
            "Facial Index": (target.facial_index, generated.facial_index, 5.0),
            "Eye Shape Ratio": (target.eye_shape_ratio, generated.eye_shape_ratio, 0.1),
        }

        for name, (t, g, tol) in metrics.items():
            diff = abs(t - g)
            is_drift = diff > tol

            status = "FAIL ❌" if is_drift else "PASS ✅"
            if is_drift:
                drift_detected = True

            report.append(
                {
                    "Metric": name,
                    "Target": t,
                    "Generated": g,
                    "Diff": f"{diff:.2f}",
                    "Status": status,
                }
            )

        return {"has_drift": drift_detected, "details": report}
