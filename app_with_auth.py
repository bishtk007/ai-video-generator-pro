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
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Set page config
st.set_page_config(page_title="AI Video Generator Pro", layout="wide")

# Constants
SD_URL = os.getenv('SD_API_URL', 'http://127.0.0.1:7860')

# Initialize default config with plain text password (will be hashed automatically)
config = {
    'credentials': {
        'usernames': {
            'test': {
                'email': 'test@example.com',
                'name': 'Test User',
                'password': 'test123'
            }
        }
    },
    'cookie': {
        'expiry_days': 30,
        'key': 'abcdef123456789',
        'name': 'auth_cookie'
    },
    'preauthorized': {
        'emails': ['test@example.com']
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
                        # Increment usage
                        increment_usage(username)
                        
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
