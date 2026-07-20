# SUPROC Submission Details

### Submission Format

- **Repository URL**: `https://github.com/<your-username>/suproc-agentic-system`
- **Demo Video URL**: `https://www.loom.com/share/<your-demo-video-id>`
- **Model Used**: `Qwen3 4B` (Local Ollama) / `Qwen3 1.7B` (Low-Resource Option) with Thread-Safe Deterministic Fallback Engine

---

### Known Limitations

1. **Static Logistics Lead Times**:
   The local synthetic dataset utilizes static baseline lead times. Production enterprise deployment would integrate real-time shipping courier APIs (e.g., BlueDart, Delhivery) for dynamic transit calculation.

2. **Hardware-Dependent Local LLM Inference**:
   Running `qwen3:4b` locally via Ollama relies on host CPU/GPU capabilities. Inference latency may range from 500ms to 3s depending on hardware specs. To guarantee 100% availability during evaluation, the system includes a zero-latency fallback engine.

3. **Macro-Regional Spatial Indexing**:
   The location engine performs fuzzy regional state mapping (e.g., South India $\rightarrow$ Karnataka, Tamil Nadu, Kerala, Andhra Pradesh, Telangana). Hyper-local radius searches (e.g., within 15 km of a specific PIN code) require PostGIS spatial database extensions.
