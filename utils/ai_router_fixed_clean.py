import base64
from typing import Dict, List, Optional, Any
from openai import OpenAI
import os

class AIRouter:
    def __init__(self, client: OpenAI):
        self.client = client

    def is_image_request(self, query: str) -> bool:
        keywords = ['show diagram', 'give architecture image', 'visualize', 'generate image', 'draw', 'create diagram']
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in keywords)

    def generate_image_response(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        text_context = context.get('text_context', '')
        prompt = f"{query}. Context: {text_context[:200]}"
        image_b64 = self.generate_image(prompt)
        if image_b64:
            return {"images": [image_b64]}
        return {"answer": "Image generation failed."}

    def generate_response(self, query: str, context: Dict[str, Any], images: Optional[List[str]] = None) -> Dict[str, Any]:
        text_context = context.get('text_context', '')
        has_images = images and len(images) > 0
        
        if has_images:
            return self._vision_mode(query, text_context, images, context)
        elif self.is_image_request(query):
            return self.generate_image_response(query, context)
        return self._text_mode(query, text_context, context)

    def _load_image_b64(self, image_path: str) -> str:
        if not os.path.exists(image_path):
            raise ValueError(f"Image not found: {image_path}")
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def _vision_mode(self, query: str, text_context: str, images: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            vision_prompt = """You are Smart AI Assistant with RAG. IMAGE ANALYSIS MODE (image present):
Carefully analyze image content first:
- Identify objects, people, colors, actions, context
- Describe scene clearly/detailed
- Extract ALL visible text accurately
Then combine with text context to answer: """ + query + """
Text context: """ + text_context + """
RULES:
1. Clear, structured, direct output
2. Confident/precise - based on visual evidence + context
3. NEVER: 'cannot see image', ASCII diagrams
4. Prioritize image understanding when present
Structure:
IMAGE ANALYSIS: [detailed]
Answer: [direct answer]"""
            
            messages = [{"role": "user", "content": [{"type": "text", "text": vision_prompt}]}]
            
            for img_path in images[:4]:
                try:
                    img_b64 = self._load_image_b64(img_path)
                    messages[0]["content"].append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                    })
                except Exception as e:
                    print(f"Warning: skipped image {img_path}: {e}")
            
            response = self.client.chat.completions.create(
                model="meta-llama/llama-3.2-11b-vision-instruct:free",
                messages=messages,
                temperature=0.1
            )
            
            full_resp = response.choices[0].message.content
            
            if "IMAGE DESCRIPTION:" in full_resp and "Answer:" in full_resp:
                desc = full_resp.split("IMAGE DESCRIPTION:")[1].split("Answer:")[0].strip()
                answer = full_resp.split("Answer:")[1].strip()
            else:
                desc = "Detailed image analysis performed."
                answer = full_resp
            
            return {
                "answer": answer,
                "image_analysis": desc,
                "used_vision": True,
                "sources": context.get('image_paths', []) + context.get('text_sources', []),
                "tokens": {
                    "prompt_tokens": (len(text_context) + len(query)) // 4 + 500,
                    "completion_tokens": len(full_resp) // 4,
                    "total_tokens": 0
                }
            }
        except Exception as e:
            print(f"Vision error: {e}")
            return self._text_mode(query, text_context, context)

    def _text_mode(self, query: str, text_context: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not text_context.strip():
            return {"answer": "Information not found in document", "image_analysis": None, "used_vision": False, "sources": context.get('text_sources', []) if context else []}
        
        system_prompt = """You are Smart AI Assistant with RAG. TEXT MODE.
Use emojis: 🔹 key points ⚡ important 📌 definitions. No ASCII art.
RULES: Context only, clear/structured/direct, confident.
No context → 'Information not found in document'"""
        prompt = f"{system_prompt}\nContext: {text_context}\nQuestion: {query}\nAnswer:"
        
        response = self.client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        return {
            "answer": response.choices[0].message.content,
            "image_analysis": None,
            "used_vision": False,
            "sources": context.get('text_sources', []) if context else []
        }

    def generate_image(self, prompt: str, style: str = "diagram") -> str:
        try:
            enhanced_prompt = f"Professional {style}, clean lines, technical, white background, high quality: {prompt}"
            response = self.client.images.generate(
                model="black-forest-labs/flux-schnell",
                prompt=enhanced_prompt,
                n=1,
                size="1024x1024",
                response_format="b64_json"
            )
            image_b64 = response.data[0].b64_json
            print(f"🖼️ Generated image for: {prompt[:50]}...")
            return image_b64
        except Exception as e:
            print(f"Image gen error: {e}")
            return None

def get_ai_router(client=None):
    try:
        from app_fixed_startup import llm_client as default_client
    except ImportError:
        from app import llm_client as default_client
    return AIRouter(client or default_client)

