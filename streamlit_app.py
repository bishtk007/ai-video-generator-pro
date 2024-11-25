import streamlit as st
import requests
from PIL import Image
import os
from image_to_video import ImageToVideoConverter
import tempfile
import uuid
import io
import json

# Set page config
st.set_page_config(page_title="AI Video Generator", layout="wide")

# Constants
SD_URL = "http://127.0.0.1:7860"

def generate_image(prompt, negative_prompt="", width=1024, height=1024, steps=30):
    """Generate an image using local Stable Diffusion WebUI API"""
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": steps,
        "width": width,
        "height": height,
        "sampler_name": "DPM++ 2M Karras",
        "cfg_scale": 7,
        "seed": -1,
    }
    
    try:
        response = requests.post(url=f"{SD_URL}/sdapi/v1/txt2img", json=payload)
        r = response.json()
        image = Image.open(io.BytesIO(bytes.fromhex(r['images'][0])))
        return image
    except Exception as e:
        st.error(f"Error generating image: {str(e)}")
        return None

# Create necessary directories
for folder in ['uploads', 'generated', 'output']:
    os.makedirs(folder, exist_ok=True)

# Title
st.title("🎬 AI Video Generator")
st.write("Generate a sequence of images that will be converted into a video!")

# Sidebar settings
with st.sidebar:
    st.header("Settings")
    num_frames = st.slider("Number of frames", min_value=4, max_value=8, value=4)
    fps = st.slider("Frames per second", min_value=1, max_value=5, value=2)
    
    st.header("Image Settings")
    width = st.select_slider("Image Width", options=[512, 768, 1024], value=1024)
    height = st.select_slider("Image Height", options=[512, 768, 1024], value=1024)
    steps = st.slider("Sampling Steps", min_value=20, max_value=50, value=30)

# Main interface
prompt = st.text_area("Enter your prompt", height=100, 
    placeholder="RAW photo, 8k uhd, dslr, high quality, film grain, hyper realistic...")

negative_prompt = st.text_area("Enter negative prompt", height=100,
    placeholder="ugly, blurry, low quality, text, watermark, signature, deformed...",
    value="ugly, blurry, low quality, text, watermark, signature, deformed, bad anatomy, bad art, amateur")

if prompt and st.button("Generate Video", type="primary"):
    try:
        # Show progress
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Generate frames
        status_text.text("Generating frames...")
        image_paths = []
        
        for i in range(num_frames):
            progress = (i + 1) / (num_frames + 1)
            progress_bar.progress(progress)
            
            # Generate image using local SD API
            output = generate_image(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps
            )
            
            if output is None:
                st.error("Failed to generate image")
                break
                
            # Save generated image
            filename = f"generated_{uuid.uuid4()}.png"
            filepath = os.path.join('generated', filename)
            output.save(filepath)
            image_paths.append(filepath)
            
            status_text.text(f"Generated frame {i + 1}/{num_frames}")
            
            # Show the generated image
            st.image(output, caption=f"Frame {i + 1}")
        
        # Create video
        if len(image_paths) == num_frames:
            status_text.text("Creating video...")
            output_video = f"output_{uuid.uuid4()}.mp4"
            output_path = os.path.join('output', output_video)
            
            converter = ImageToVideoConverter(output_path=output_path, fps=fps)
            success = converter.convert_images_to_video('generated')
            
            if success:
                # Display video
                status_text.text("Video generated successfully!")
                progress_bar.progress(1.0)
                st.video(output_path)
                
                # Download button
                with open(output_path, 'rb') as f:
                    st.download_button(
                        label="Download Video",
                        data=f.read(),
                        file_name=output_video,
                        mime="video/mp4"
                    )
            else:
                st.error("Failed to create video")
                
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        
    finally:
        # Clean up temporary files
        for path in image_paths:
            if os.path.exists(path):
                os.remove(path)
