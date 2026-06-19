import streamlit as st
import numpy as np
from datetime import datetime
import hashlib
from PIL import Image

from face_lock_core import (
    AnalogFilmProcessor,
    FaceAnalyzer,
    PromptGenerator,
    DriftDetector,
)

# --- CONFIGURATION & SETUP ---
st.set_page_config(
    page_title="Face Lock: Biometric Character Consistency",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CORE CLASSES ---


class BIPAConsent:
    """Handles BIPA compliance, consent logging, and audit trails."""

    def __init__(self):
        # In a real app, this would be a persistent database connection
        if "consent_db" not in st.session_state:
            st.session_state.consent_db = []

    def register_consent(self, subject_id: str, method: str = "Written"):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "subject_hash": hashlib.sha256(subject_id.encode()).hexdigest(),
            "consent_method": method,
            "status": "ACTIVE",
            "data_retention_policy": "3_YEARS",
        }
        st.session_state.consent_db.append(entry)
        return entry

    def verify_consent(self, subject_id: str) -> bool:
        h = hashlib.sha256(subject_id.encode()).hexdigest()
        return any(
            e["subject_hash"] == h and e["status"] == "ACTIVE"
            for e in st.session_state.consent_db
        )


# --- STREAMLIT UI ---


def main():
    st.sidebar.title("Face Lock 🔒")
    st.sidebar.markdown("Biometric Character Consistency Pack")

    mode = st.sidebar.radio(
        "Workflow Mode", ["Synthetic (BIPA-Safe)", "Real Face (BIPA-Regulated)"]
    )

    analyzer = FaceAnalyzer()
    generator = PromptGenerator()
    film_processor = AnalogFilmProcessor()
    drift_detector = DriftDetector()
    bipa = BIPAConsent()

    # --- SESSION STATE ---
    if "locked_metrics" not in st.session_state:
        st.session_state.locked_metrics = None
    if "subject_name" not in st.session_state:
        st.session_state.subject_name = "Character_01"

    # --- MAIN AREA ---

    st.title("Biometric Extraction & Consistency")

    # 1. REFERENCE UPLOAD
    st.subheader("1. Reference Biometrics")

    if mode == "Real Face (BIPA-Regulated)":
        st.warning("⚠️ BIPA MODE ACTIVE: Consent required for real facial analysis.")
        subject_id = st.text_input("Subject Identifier (e.g., Email/ID)")
        consent_check = st.checkbox(
            "I certify that written consent has been obtained from the subject."
        )

        if not consent_check or not subject_id:
            st.info("Waiting for consent to unlock analysis...")
            st.stop()

        # Log consent (mock)
        if st.button("Log Consent Audit Trail"):
            entry = bipa.register_consent(subject_id)
            st.success(
                f"Consent logged: {entry['timestamp']} | Hash: {entry['subject_hash'][:8]}..."
            )

    uploaded_file = st.file_uploader(
        "Upload Reference Face", type=["jpg", "png", "jpeg"]
    )

    if uploaded_file:
        image = Image.open(uploaded_file)
        image_np = np.array(image)

        col1, col2 = st.columns([1, 1])
        with col1:
            st.image(image, caption="Reference Image", use_container_width=True)

        # Run Analysis
        if st.button("Extract Biometrics"):
            with st.spinner("Analyzing Mesh Geometry..."):
                metrics = analyzer.analyze(image_np)

                if metrics:
                    st.session_state.locked_metrics = metrics
                    with col2:
                        st.json(metrics.to_dict())
                        st.success("✅ Biometrics Locked")
                else:
                    st.error("No face detected in reference image.")

    # 2. PROMPT GENERATION
    if st.session_state.locked_metrics:
        st.divider()
        st.subheader("2. Prompt Engineering")

        c_name = st.text_input("Character Name", value=st.session_state.subject_name)
        platform = st.selectbox("Target Platform", ["Flux", "Midjourney", "Reve"])

        if st.button("Generate Prompts"):
            prompts = generator.generate(
                st.session_state.locked_metrics, platform, c_name
            )

            st.markdown("### Positive Prompt")
            st.code(prompts["positive"], language="text")

            st.markdown("### Anti-Drift Negative Prompt")
            st.code(prompts["negative"], language="text")

        # 3. ANALOG FILM PROCESSING
        st.divider()
        st.subheader("3. Analog Film Emulation")

        film_preset = st.selectbox(
            "Film Stock Preset",
            ["None", "Kodachrome 25", "Agfa CNS2", "Kodak Vision3 500T"],
        )

        if film_preset != "None" and uploaded_file:
            processed_img = film_processor.apply_preset(image, film_preset)
            st.image(
                processed_img,
                caption=f"Emulation: {film_preset}",
                use_container_width=True,
            )

        # 4. DRIFT DETECTION
        st.divider()
        st.subheader("4. Drift Detection (Validation)")

        gen_file = st.file_uploader(
            "Upload Generated Image to Verify", type=["jpg", "png"]
        )

        if gen_file:
            gen_image = Image.open(gen_file)
            gen_np = np.array(gen_image)

            gen_metrics = analyzer.analyze(gen_np)

            if gen_metrics:
                report = drift_detector.check_drift(
                    st.session_state.locked_metrics, gen_metrics
                )

                c1, c2 = st.columns(2)
                with c1:
                    st.image(
                        gen_image,
                        caption="Generated Candidate",
                        use_container_width=True,
                    )
                with c2:
                    st.write("### Drift Report")
                    if report["has_drift"]:
                        st.error("❌ DRIFT DETECTED")
                    else:
                        st.success("✅ CONSISTENT")

                    st.dataframe(report["details"])
            else:
                st.error("No face detected in generated image.")


if __name__ == "__main__":
    main()
