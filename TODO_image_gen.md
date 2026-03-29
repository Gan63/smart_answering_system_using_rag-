# Image + Text Generation Feature Plan

**Status**: ✅ Complete - Image gen integrated in /query /chat via flux-schnell, b64 response

**Information Gathered**:
- Server stable (all original bugs fixed).
- No existing image gen code.
- Frontend multimodal.js handles image display (`image_paths`, `image_b64`).
- OpenRouter API key active.

**Plan**:
1. **utils/ai_router.py**:
   - Add `generate_image(prompt, style='diagram')` → OpenRouter flux-schnell → base64 PNG.
2. **app.py** /query, /chat:
   - Detect keywords: 'generate image', 'create diagram', 'draw chart', 'visualize'.
   - Text LLM → description.
   - Image gen → image_b64 from description + context.
   - Return: {\"answer\": text, \"generated_image\": image_b64}
3. **Frontend**: Auto-display generated_image b64.

**Models**:
- Text: llama-3.1-8b (current).
- Image: \"black-forest-labs/flux-schnell\" (fast diagrams).

**Dependent Files**: utils/ai_router.py, app.py

**Followup**:
- Backup files.
- Implement, test \"generate DFD diagram\".
- Update TODO.md.

Ready to implement?
