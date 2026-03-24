#!/usr/bin/env python3
"""Test AI Router."""
import os
from utils import get_ai_router

def test_text():
    router = get_ai_router()
    context = {'text_context': 'Sample document text about AI routers.'}
    result = router.generate_response('What is this?', context, [])
    print('TEXT MODE:', result)

def test_vision(image_path):
    router = get_ai_router()
    context = {'text_context': 'Document context.'}
    result = router.generate_response('Describe this image?', context, [image_path])
    print('VISION MODE:', result)

if __name__ == '__main__':
    print('🧠 Testing AI Router...')
    test_text()
    
    # Test vision (pick first image)
    image_dir = 'data/extracted_images'
    if os.path.exists(image_dir):
        images = [f for f in os.listdir(image_dir) if f.endswith('.png')]
        if images:
            test_vision(os.path.join(image_dir, images[0]))
        else:
            print('No test images found.')
    else:
        print('No images dir; vision test skipped.')
    
    print('✅ Tests complete.')
