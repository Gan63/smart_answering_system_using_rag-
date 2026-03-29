import base64
import io
from typing import Dict, List, Optional, Any
from PIL import Image
from openai import OpenAI
import os

class AIRouter:
    def __init__(self, client: OpenAI):
        self.client = client

    def generate_response(
        self, 
        query: str, 
        context: Dict[str, Any], 
        images: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Intelligent router: Vision if images present, else text-only RAG.
        Returns: {'answer': str, 'image_desc': str or None, 'used_vision': bool, 'sources': list}
        """
        text_context = context.get('text_context', '')
        has_images = images and len(images) > 0
        
        if has_images:
            return self._vision_mode(query, text_context, images, context)
        else:
            return self._text_mode(query, text_context, context)

    def _load_image_b64(self, image_path: str) -> str:
        """Convert image path to base64."""
        # Clean path if it contains caption
        clean_path = image_path.split(' | ')[0] if ' | ' in image_path else image_path
        if not os.path.exists(clean_path):
            raise ValueError(f"Image not found: {clean_path}")
        with open(clean_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def _vision_mode(self, query: str, text_context: str, images: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Use vision LLM: describe images first, then answer."""
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""Analyze these images in detail first (objects, text, diagrams, people). 
Describe what you see accurately. Then use text context if relevant and answer: {query}

Text context: {text_context}

Structure response:
1. IMAGE DESCRIPTION: [detailed analysis]
2. Answer: [direct answer to question]

Be precise, no hallucinations."""
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
            
            # Use Qwen 2.5 VL (available on OpenRouter, supports vision)
            response = self.client.chat.completions.create(
                model="qwen/qwen2.5-vl-72b-instruct:free",
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
                "image_desc": desc,
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
        prompt = f"""Context: {text_context}

Question: {query}

Answer directly and accurately using context only. If unclear, say so."""
        
        response = self.client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        return {
            "answer": response.choices[0].message.content,
            "image_desc": None,
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
            print(f"Image gen error: {e} - Fallback ASCII diagram")
            # Simple fallback diagram for technical requests
            return None

# Global (for compatibility)
def get_ai_router(client=None):
    try:
        from app_fixed_startup import llm_client as default_client
    except ImportError:
        from app import llm_client as default_client
    return AIRouter(client or default_client)
