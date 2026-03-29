import base64
import io
from typing import Dict, List, Optional, Any
from PIL import Image
from openai import OpenAI
import os

class AIRouter:
    def __init__(self, client: OpenAI):
        self.client = client

    def is_image_request(self, query: str) -> bool:
        """Detect image generation requests."""
        keywords = ['show diagram', 'give architecture image', 'visualize', 'generate image', 'draw', 'create diagram']
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in keywords)

    def generate_image_response(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """CASE 2: Generate image for 'show diagram' etc."""
        text_context = context.get('text_context', '')
        # Refine prompt from query + context
        prompt = f"{query}. Context: {text_context[:200]}"
        image_b64 = self.generate_image(prompt)
        if image_b64:
            return {"answer": "🖼️ Generated technical image/diagram from context.", "generated_image": image_b64, "used_vision": False}
        return {"answer": "Image generation failed - try rephrasing."}

    def generate_response(
        self, 
        query: str, 
        context: Dict[str, Any], 
        images: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Intelligent router: Vision if images present, else text-only RAG.
        Returns: {'answer': str, 'image_analysis': str or None, 'used_vision': bool, 'sources': list} OR {'images': [str]} for image requests
        """
        text_context = context.get('text_context', '')
        has_images = images and len(images) > 0
        
        if has_images:
            return self._vision_mode(query, text_context, images, context)
        else:
            # Check for image generation first (CASE 2)
            if self.is_image_request(query):
                return self.generate_image_response(query, context)
            return self._text_mode(query, text_context, context)

    def _load_image_b64(self, image_path: str) -> str:
        """Convert image path to base64."""
        if not os.path.exists(image_path):
            raise ValueError(f"Image not found: {image_path}")
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def _vision_mode(self, query: str, text_context: str, images: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Use vision LLM: describe images first, then answer."""
        try:
            vision_prompt = f"""You are Smart AI Assistant with RAG. IMAGE ANALYSIS MODE (image present):

Carefully analyze image content first:
- Identify objects, people, colors, actions, context
- Describe scene clearly/detailed
- Extract ALL visible text accurately

Then combine with text context to answer: {query}

Text context: {text_context}

RULES:
1. Clear, structured, direct output
2. Confident/precise - based on visual evidence + context  
3. NEVER: 'cannot see image', ASCII diagrams
4. Prioritize image understanding when present

Structure:
IMAGE ANALYSIS: [detailed]
Answer: [direct answer]"""
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": vision_prompt
                        }
                    ]
                }
            ]

            
            # Add images (first 4 max)
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
            
            # Parse: extract desc/answer if structured
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
            return self._text_mode(query, text_context, context)  # Fallback

    def _text_mode(self, query: str, text_context: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Text-only RAG."""
        system_prompt = """You are Smart AI Assistant with RAG. TEXT MODE (no image).\n\nUse emojis:\n🔹 key points\n⚡ important ideas\n📌 definitions\nNo ASCII diagrams.\n\nRULES:\n- Use ONLY provided context\n- Clear, structured, direct\n- Confident/precise\n- If answer not in context: 'Information not found in document'"""
        prompt = f"{system_prompt}\n\nContext: {text_context}\n\nQuestion: {query}\n\nAnswer directly and accurately using context only. If unclear, say so."""
        
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
        """Generate image from text prompt using Flux. Returns base64 PNG."""
        try:
            enhanced_prompt = f"Professional {style}, clean lines, technical diagram style, white background, high quality: {prompt}"
            
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

# Global (for compatibility)
def get_ai_router(client=None):
    """Compatible factory - pass client explicitly"""
    if client is None:
        raise ValueError("Must pass llm_client explicitly - no auto-imports")
    return AIRouter(client)

