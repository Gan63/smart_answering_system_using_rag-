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
            print(f"[RECOVERY] Image not found on disk, checking if it is base64: {clean_path[:50]}...")
            if clean_path.startswith("data:"):
                return clean_path.split(",")[1]
            raise ValueError(f"Image not found: {clean_path}")
            
        # Determine mime type
        ext = os.path.splitext(clean_path.lower())[1]
        mime = "image/png" if ext == ".png" else "image/jpeg"
        
        with open(clean_path, 'rb') as f:
            b64_data = base64.b64encode(f.read()).decode('utf-8')
            return f"data:{mime};base64,{b64_data}"

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

IDENTITY:
- You are a Smart Multimodal RAG Assistant.
- You were created by a talented developer and Code Assistant creator (Ganesh).
- Your work includes reading, understanding, and extracting information from uploaded files like PDFs, Word documents, and images.
- Your process involves: searching the given documents to find relevant text and images that match the user's query, analyzing this extracted context, and finally synthesizing a precise and accurate response based strictly on the uploaded content.

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
                    img_data_url = self._load_image_b64(img_path)
                    messages[0]["content"].append({
                        "type": "image_url",
                        "image_url": {"url": img_data_url}
                    })
                except Exception as e:
                    print(f"Warning: skipped image {img_path}: {e}")
            
            # Use Gemini 2.0 Flash (Stable, excellent vision)
            response = self.client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
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
        prompt = f"""IDENTITY:
- You are a Smart Multimodal RAG Assistant.
- You were created by a talented developer and Code Assistant creator (Ganesh).
- Your work includes reading, understanding, and extracting information from uploaded files like PDFs, Word documents, and images.
- Your process involves: searching the given documents to find relevant text and images that match the user's query, analyzing this extracted context, and finally synthesizing a precise and accurate response based strictly on the uploaded content.

Context: {text_context}

Question: {query}

If the Context is empty, you are ONLY allowed to answer questions strictly about your IDENTITY. For anything else, state exactly: "Please upload a document first so I can answer questions about it."
Otherwise, answer directly and accurately using context only. If unclear, say so."""
        
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
        """Generate image from text prompt using Gemini 3 via OpenRouter. Returns image URL or base64."""
        try:
            # Enhanced prompt for Gemini
            enhanced_prompt = f"Generate a high-quality {style} image: {prompt}"
            
            print(f"🎨 Requesting image from Gemini 3 Pro: {prompt[:50]}...")
            response = self.client.chat.completions.create(
                model="google/gemini-3-pro-image-preview",
                messages=[{"role": "user", "content": [{"type": "text", "text": enhanced_prompt}]}]
            )
            
            content = response.choices[0].message.content
            
            # Extract URL if markdown, else use content directly
            import re
            url_match = re.search(r'\((https?://[^\)]+)\)', content)
            
            if url_match:
                img_url = url_match.group(1)
                print(f"✅ Image generated (URL): {img_url}")
                return img_url
            
            if content.startswith("http") or content.startswith("data:image"):
                return content.strip()

            # Some models return the URL in the response without markdown
            if "https://" in content:
                url_match = re.search(r'https?://[^\s\)]+', content)
                if url_match:
                    return url_match.group(0)

            print(f"⚠️ Service returned text: {content[:100]}...")
            return None
            
        except Exception as e:
            print(f"❌ Image generation error: {str(e)}")
            return None

# Global (for compatibility)
def get_ai_router(client=None):
    try:
        from app_fixed_startup import llm_client as default_client
    except ImportError:
        from app import llm_client as default_client
    return AIRouter(client or default_client)
