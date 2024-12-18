# Version 1.0.4 - Fixed Indentation
import streamlit as st
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

# Set page config (MUST BE FIRST st. command)
st.set_page_config(
    page_title="AI Video Generator Pro",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Debug logging
st.write("Debug: App Started")
st.write(f"Debug: STABILITY_API_KEY exists: {bool(os.getenv('STABILITY_API_KEY'))}")
st.write(f"Debug: STRIPE_SECRET_KEY exists: {bool(os.getenv('STRIPE_SECRET_KEY'))}")
st.write(f"Debug: COOKIE_KEY exists: {bool(os.getenv('COOKIE_KEY'))}")

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Constants
SD_URL = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
PRICE_IDS = {
    'basic': 'price_H5ggYwtDq8jGy7',  # $9.99/month
    'pro': 'price_H5ggYwtDq8jGy8'     # $29.99/month
}

# Initialize session state
if 'user_usage' not in st.session_state:
    st.session_state.user_usage = {}

if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None

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
    st.write("Debug: Starting image generation")
    st.write(f"Debug: Prompt: '{prompt}'")
    
    if not os.getenv('STABILITY_API_KEY'):
        st.error("Missing Stability API key")
        return None
        
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('STABILITY_API_KEY')}"
    }
    
    # Build text prompts list
    text_prompts = [{"text": prompt, "weight": 1}]
    if negative_prompt:  # Only add negative prompt if it's not empty
        text_prompts.append({"text": negative_prompt, "weight": -1})
        st.write(f"Debug: Added negative prompt: '{negative_prompt}'")
    
    payload = {
        "text_prompts": text_prompts,
        "cfg_scale": 7,
        "height": height,
        "width": width,
        "steps": steps,
        "samples": 1,
    }
    
    st.write("Debug: Payload:", payload)
    
    try:
        st.write(f"Debug: Making API request to {SD_URL}")
        response = requests.post(SD_URL, headers=headers, json=payload)
        st.write(f"Debug: API Response Status: {response.status_code}")
        st.write(f"Debug: API Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                response_json = response.json()
                st.write("Debug: Successfully parsed JSON response")
                image_data = base64.b64decode(response_json["artifacts"][0]["base64"])
                image = Image.open(io.BytesIO(image_data))
                st.write("Debug: Image generated successfully")
                return image
            except Exception as e:
                st.error(f"Error processing API response: {str(e)}")
                st.write("Debug: Response content:", response.text[:500])  # Show first 500 chars
                return None
        else:
            st.error(f"API Error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error generating image: {str(e)}")
        st.write(f"Debug: Full error: {repr(e)}")
        return None

# Authentication
if st.session_state['authentication_status'] != True:
    # Show login form
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if username == "demo" and password == "abc123":
            st.session_state['authentication_status'] = True
            st.session_state['username'] = username
            st.session_state['name'] = "Demo User"
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")
            st.info("Demo account - Username: demo, Password: abc123")
else:
    # User is logged in
    username = st.session_state['username']
    name = st.session_state['name']
    
    # Show logout button in sidebar
    if st.sidebar.button("Logout"):
        st.session_state['authentication_status'] = False
        st.experimental_rerun()
    
    st.sidebar.title(f"Welcome {name}")
    
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
                        'price': PRICE_IDS['pro'],
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=st.get_option("server.baseUrlPath") + '/success',
                    cancel_url=st.get_option("server.baseUrlPath") + '/cancel',
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
                            placeholder="Describe what you want to generate... Be creative!")
        negative_prompt = st.text_area("Enter negative prompt (optional)", height=100,
                                     placeholder="Describe what you want to avoid in the generation...")
        
        if st.button("Generate Video", type="primary"):
            if not prompt:
                st.error("Please enter a prompt first")
            else:
                st.write(f"Debug: Starting video generation")
                st.write(f"Debug: Prompt: '{prompt}'")
                st.write(f"Debug: Settings - Frames: {num_frames}, FPS: {fps}, Size: {width}x{height}, Steps: {steps}")
                
                try:
                    # Create directories if they don't exist
                    os.makedirs('generated', exist_ok=True)
                    os.makedirs('output', exist_ok=True)
                    
                    # Show progress
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    image_paths = []
                    
                    # Generate frames
                    status_text.text("Generating frames...")
                    
                    for i in range(num_frames):
                        st.write(f"Debug: Generating frame {i+1} of {num_frames}")
                        image = generate_image(prompt, negative_prompt, width, height, steps)
                        
                        if image:
                            # Save image
                            temp_path = os.path.join('generated', f'frame_{i}.png')
                            image.save(temp_path)
                            image_paths.append(temp_path)
                            st.write(f"Debug: Saved frame {i+1}")
                            
                            # Update progress
                            progress = (i + 1) / num_frames
                            progress_bar.progress(progress)
                            
                            # Show the generated frame
                            st.image(image, caption=f"Frame {i+1}")
                        else:
                            st.error(f"Failed to generate frame {i+1}")
                            break
                    
                    if len(image_paths) == num_frames:
                        # Convert to video
                        status_text.text("Converting to video...")
                        output_path = os.path.join('output', f'video_{uuid.uuid4()}.mp4')
                        
                        converter = ImageToVideoConverter(output_path=output_path, fps=fps)
                        if converter.convert_images_to_video(image_paths):
                            # Show video
                            status_text.empty()
                            progress_bar.empty()
                            
                            st.success("Video generated successfully!")
                            st.video(output_path)
                            
                            # Increment usage
                            increment_usage(username)
                        else:
                            st.error("Failed to convert images to video")
                    
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

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>© 2024 AI Video Generator Pro. All rights reserved.</p>
    <p>Need help? Contact support@aivideogeneratorpro.com</p>
</div>
""", unsafe_allow_html=True)
