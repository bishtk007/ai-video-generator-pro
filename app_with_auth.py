import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import requests
from PIL import Image
import os
from image_to_video import ImageToVideoConverter
import tempfile
import uuid
import io
import json
import stripe
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Set page config
st.set_page_config(page_title="AI Video Generator Pro", layout="wide")

# Constants
SD_URL = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

# Initialize default config with hashed password
hashed_passwords = stauth.Hasher(['abc123']).generate()

config = {
    'credentials': {
        'usernames': {
            'demo': {
                'email': 'demo@example.com',
                'name': 'Demo User',
                'password': hashed_passwords[0]
            }
        }
    },
    'cookie': {
        'expiry_days': 30,
        'key': 'some_signature_key',
        'name': 'some_cookie_name'
    },
    'preauthorized': {
        'emails': ['demo@example.com']
    }
}
# Initialize authenticator
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Create necessary directories
for folder in ['uploads', 'generated', 'output']:
    os.makedirs(folder, exist_ok=True)

# Initialize session state
if 'user_usage' not in st.session_state:
    st.session_state.user_usage = {}

def check_user_limits(username, tier='free'):
    """Check if user has exceeded their usage limits"""
    today = datetime.now().date()
    if username not in st.session_state.user_usage:
        st.session_state.user_usage[username] = {'date': today, 'count': 0}
    
    user_usage = st.session_state.user_usage[username]
    
    # Reset count if it's a new day
    if user_usage['date'] != today:
        user_usage['date'] = today
        user_usage['count'] = 0
    
    # Check limits based on tier
    limits = {
        'free': 3,
        'basic': 10,
        'pro': float('inf')
    }
    
    return user_usage['count'] < limits.get(tier, 0)

def increment_usage(username):
    """Increment user's usage count"""
    if username in st.session_state.user_usage:
        st.session_state.user_usage[username]['count'] += 1

def generate_image(prompt, negative_prompt="", width=1024, height=1024, steps=30):
    """Generate an image using Stability AI API"""
    api_key = os.getenv('STABILITY_API_KEY')
    if not api_key:
        st.error("Stability AI API key not found. Please set STABILITY_API_KEY in environment variables.")
        return None
        
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "text_prompts": [
            {
                "text": prompt,
                "weight": 1
            },
            {
                "text": negative_prompt,
                "weight": -1
            }
        ],
        "cfg_scale": 7,
        "height": height,
        "width": width,
        "samples": 1,
        "steps": steps,
    }
    
    try:
        response = requests.post(
            SD_URL,
            headers=headers,
            json=payload,
        )
        
        if response.status_code != 200:
            st.error(f"Error from Stability AI API: {response.text}")
            return None
            
        data = response.json()
        if not data['artifacts']:
            st.error("No image generated")
            return None
            
        # Convert base64 to image
        image_data = base64.b64decode(data['artifacts'][0]['base64'])
        image = Image.open(io.BytesIO(image_data))
        return image
        
    except Exception as e:
        st.error(f"Error generating image: {str(e)}")
        return None

# Authentication
name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status:
    # Successful login
    authenticator.logout('Logout', 'sidebar')
    st.sidebar.title(f'Welcome {name}')
    
    # Subscription Management in Sidebar
    st.sidebar.header("Subscription")
    current_tier = "free"  # You would typically get this from a database
    
    if current_tier == "free":
        st.sidebar.info("You're on the Free tier")
        if st.sidebar.button("Upgrade to Pro"):
            # Create Stripe checkout session
            try:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price': 'price_H5ggYwtDq8jGy7',  # Replace with your Stripe price ID
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url='http://localhost:8501/success',
                    cancel_url='http://localhost:8501/cancel',
                )
                st.sidebar.markdown(f"[Upgrade Now]({checkout_session.url})")
            except Exception as e:
                st.sidebar.error("Error creating checkout session")
    
    # Main App Interface
    st.title("🎬 AI Video Generator Pro")
    st.write("Generate a sequence of images that will be converted into a video!")

    # Check usage limits
    if check_user_limits(username, current_tier):
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
        
        # Create directories if they don't exist
        for folder in ['generated', 'output']:
            os.makedirs(folder, exist_ok=True)
            st.write(f"Created directory: {folder}")
        
        # Generate frames
        status_text.text("Generating frames...")
        image_paths = []
        
        for i in range(num_frames):
            progress = (i + 1) / (num_frames + 1)
            progress_bar.progress(progress)
            
            # Generate image using Stability AI API
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
            filename = f"generated_{i}.png"  # Use sequential numbers
            filepath = os.path.join('generated', filename)
            output.save(filepath)
            image_paths.append(filepath)
            
            status_text.text(f"Generated frame {i + 1}/{num_frames}")
            st.write(f"Saved image to: {filepath}")
            
            # Show the generated image
            st.image(output, caption=f"Frame {i + 1}")
        
        # Create video
        if len(image_paths) == num_frames:
            status_text.text("Creating video...")
            output_video = "output_video.mp4"  # Use fixed name for testing
            output_path = os.path.join('output', output_video)
            
            st.write(f"Starting video conversion with {len(image_paths)} frames")
            st.write(f"Image paths: {image_paths}")
            
            converter = ImageToVideoConverter(output_path=output_path, fps=fps)
            success = converter.convert_images_to_video('generated')
            
            if success:
                # Increment usage
                increment_usage(username)
                
                st.write(f"Video created at: {output_path}")
                if os.path.exists(output_path):
                    st.write(f"Video file size: {os.path.getsize(output_path)} bytes")
                    
                    # Display video
                    status_text.text("Video generated successfully!")
                    progress_bar.progress(1.0)
                    st.video(output_path)
                    
                    # Download button
                    with open(output_path, 'rb') as f:
                        video_bytes = f.read()
                        st.download_button(
                            label="Download Video",
                            data=video_bytes,
                            file_name=output_video,
                            mime="video/mp4"
                        )
                else:
                    st.error(f"Video file not found at {output_path}")
            else:
                st.error("Failed to create video - converter returned False")
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.write("Full error details:", e)
        
    finally:
        # Clean up temporary files
        try:
            for path in image_paths:
                if os.path.exists(path):
                    os.remove(path)
                    st.write(f"Cleaned up: {path}")
        except Exception as e:
            st.write(f"Cleanup error: {str(e)}")
                
            finally:
                # Clean up temporary files
                for path in image_paths:
                    if os.path.exists(path):
                        os.remove(path)
        
        # Show usage info
        if username in st.session_state.user_usage:
            st.sidebar.info(f"Generations today: {st.session_state.user_usage[username]['count']}")
    
    else:
        st.warning("You've reached your daily generation limit. Please upgrade to continue!")

elif authentication_status == False:
    st.error('Username/password is incorrect')
    # Add registration option
    st.markdown("Don't have an account? [Register here](#)")
elif authentication_status == None:
    st.warning('Please enter your username and password')
    # Add registration option
    st.markdown("Don't have an account? [Register here](#)")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p> 2024 AI Video Generator Pro. All rights reserved.</p>
</div>
""", unsafe_allow_html=True)
